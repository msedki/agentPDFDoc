/** Source guards and regression witnesses; React/DOM/fetch substitutions are explicit unit doubles. */
import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";
import * as React from "react";
import { renderToString } from "react-dom/server";
import { api, ApiError } from "../../src/lib/api.ts";
import { launcherCommandsFrom } from "../../src/lib/launcher.ts";
import { citationLinkIds } from "../../src/lib/citation-link.ts";
import { linkInvalidFromSearch, SESSION_ENDED_EVENT } from "../../src/lib/session.ts";
import { checkSession, readLauncherCommands } from "../../src/lib/session-check.ts";
import { readSource } from "./theme-support.ts";

function declaration(file: string, name: string) {
  const source = readSource(file);
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const parsed = ts.transpileModule(source, { fileName: file, reportDiagnostics: true, compilerOptions: { jsx: ts.JsxEmit.React } });
  assert.deepEqual(parsed.diagnostics, [], `${file}: source is actually parseable`);
  const found = ast.statements.find((node): node is ts.FunctionDeclaration => ts.isFunctionDeclaration(node) && node.name?.text === name);
  assert.ok(found?.body, `${file}: actual function ${name} must exist; never pass vacuously`);
  return { ast, found };
}

/** Execute the actual isolated function body with declared dependencies replaced, not a simulated copy. */
function loadFunction(file: string, name: string, environment: Record<string, unknown>): (...args: unknown[]) => unknown {
  const { found, ast } = declaration(file, name);
  const code = ts.transpileModule(found.getText(ast).replace(/^export\s+/, ""), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React } }).outputText;
  return new Function(...Object.keys(environment), `${code}\nreturn ${name};`)(...Object.values(environment)) as (...args: unknown[]) => unknown;
}

function loadVariable(file: string, name: string) {
  const source = readSource(file);
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found = ast.statements.flatMap(node => ts.isVariableStatement(node) ? [...node.declarationList.declarations] : []).find(node => ts.isIdentifier(node.name) && node.name.text === name);
  assert.ok(found?.initializer, `${name}: actual initializer required`);
  const code = ts.transpileModule(`const value = ${found.initializer.getText(ast)};`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(`${code}\nreturn value;`)() as unknown;
}

/** Commit/dependency model is a unit double, not React's renderer or hydration implementation. */
function hookDouble() {
  type Slot = { value: unknown; deps?: readonly unknown[]; cleanup?: () => void; setter?: (value: unknown) => void; effect?: boolean };
  const slots: Slot[] = [];
  const stateWrites: { index: number; value: unknown }[] = [];
  let cursor = 0;
  let layout: (() => void)[] = [];
  let passive: (() => void)[] = [];
  const changed = (before: readonly unknown[] | undefined, after: readonly unknown[] | undefined) => !before || !after || before.length !== after.length || before.some((value, index) => !Object.is(value, after[index]));
  const effect = (queue: (() => void)[], run: () => void | (() => void), deps?: readonly unknown[]) => {
    const index = cursor++;
    const slot = slots[index] ??= { value: undefined };
    slot.effect = true;
    if (!changed(slot.deps, deps)) return;
    queue.push(() => { slot.cleanup?.(); slot.cleanup = run() || undefined; slot.deps = deps?.slice(); });
  };
  return {
    hooks: {
      useState: (initial: unknown) => {
        const index = cursor++;
        const slot = slots[index] ??= { value: typeof initial === "function" ? (initial as () => unknown)() : initial };
        slot.setter ??= value => { slot.value = typeof value === "function" ? (value as (previous: unknown) => unknown)(slot.value) : value; stateWrites.push({ index, value: slot.value }); };
        return [slot.value, slot.setter];
      },
      useRef: (initial: unknown) => (slots[cursor++] ??= { value: { current: initial } }).value,
      useCallback: (callback: unknown, deps: readonly unknown[]) => {
        const slot = slots[cursor++] ??= { value: callback, deps: deps.slice() };
        if (changed(slot.deps, deps)) { slot.value = callback; slot.deps = deps.slice(); }
        return slot.value;
      },
      useEffect: (run: () => void | (() => void), deps?: readonly unknown[]) => effect(passive, run, deps),
      useLayoutEffect: (run: () => void | (() => void), deps?: readonly unknown[]) => effect(layout, run, deps),
      useId: () => { const index = cursor++; const slot = slots[index] ??= { value: `qa-id-${index}` }; return String(slot.value); },
    },
    render: <T>(run: () => T) => { cursor = 0; layout = []; passive = []; return run(); },
    commit: () => { for (const run of [...layout, ...passive]) run(); layout = []; passive = []; },
    peek: (index: number) => slots[index]?.value,
    stateWrites,
    dispose: () => { for (const slot of slots) { slot.cleanup?.(); slot.cleanup = undefined; } },
    replayEffects: () => { for (const slot of slots) if (slot.effect) slot.deps = undefined; },
  };
}

function elementProps(element: unknown) {
  assert.ok(React.isValidElement(element));
  return element.props as Record<string, unknown>;
}

function findElementOfType(tree: React.ReactNode, type: string): React.ReactElement | undefined {
  for (const child of React.Children.toArray(tree)) {
    if (!React.isValidElement(child)) continue;
    if (child.type === type) return child;
    const nested = findElementOfType(elementProps(child).children as React.ReactNode, type);
    if (nested) return nested;
  }
  return undefined;
}

test("AST render guard: mutable refs are not assigned in component/hook render bodies", () => {
  const checked = [
    ["components/analysis-panel.tsx", "AnalysisPanel"],
    ["components/ui/confirm-dialog.tsx", "ConfirmDialog"],
    ["components/ui/sheet.tsx", "Sheet"],
    ["lib/use-dismiss.ts", "useDismiss"],
  ];
  const offenders: string[] = [];
  for (const [file, name] of checked) {
    const { found, ast } = declaration(file, name);
    for (const statement of found.body!.statements) {
      if (!ts.isExpressionStatement(statement) || !ts.isBinaryExpression(statement.expression)) continue;
      const expression = statement.expression;
      if (expression.operatorToken.kind === ts.SyntaxKind.EqualsToken && ts.isPropertyAccessExpression(expression.left) && expression.left.name.text === "current") offenders.push(`${file}: ${expression.getText(ast)}`);
    }
  }
  assert.equal(checked.length, 4);
  assert.deepEqual(offenders, [], "actual render writes observed by the original lint report");
});

test("AST controller guard: the public ref handle uses React's imperative contract", () => {
  const { found, ast } = declaration("components/library-panel.tsx", "LibraryPanel");
  assert.match(found.getText(ast), /useImperativeHandle\(/);
  assert.doesNotMatch(found.getText(ast), /controller(?:Ref)?\.current\s*=/);
});

test("real api.tree, fetch double: an empty first page preserves total zero", async () => {
  const previous = globalThis.fetch;
  const seen: string[] = [];
  globalThis.fetch = async (url, options) => {
    seen.push(String(url));
    assert.equal(new Headers(options?.headers).get("X-RAG-Background"), "1");
    return new Response(JSON.stringify({ folders: [], documents: [], total_documents: 0 }), { status: 200 });
  };
  try {
    assert.deepEqual(await api.tree(), { folders: [], documents: [], total_documents: 0 });
    assert.deepEqual(seen, ["/api/v1/library/tree?limit=100&offset=0"]);
  } finally { globalThis.fetch = previous; }
});

test("real api.tree, fetch double: cursor pagination and final total are preserved", async () => {
  const previous = globalThis.fetch;
  const seen: string[] = [];
  const pages = [
    { folders: [{ id: "f", name: "old" }], documents: [{ id: "d1" }], total_documents: 9, next_cursor: "next /" },
    { folders: [{ id: "f", name: "new" }], documents: [{ id: "d2" }], total_documents: 2, next_cursor: null },
  ];
  globalThis.fetch = async url => {
    seen.push(String(url));
    assert.ok(pages.length, "no network or extra request is allowed");
    return new Response(JSON.stringify(pages.shift()), { status: 200 });
  };
  try {
    assert.deepEqual(await api.tree(), { folders: [{ id: "f", name: "new" }], documents: [{ id: "d1" }, { id: "d2" }], total_documents: 2 });
    assert.deepEqual(seen, ["/api/v1/library/tree?limit=100&offset=0", "/api/v1/library/tree?limit=100&offset=1&cursor=next%20%2F"]);
  } finally { globalThis.fetch = previous; }
});

test("real api.tree, fetch double: legacy offset fallback and total fallback remain intact", async () => {
  const previous = globalThis.fetch;
  const seen: string[] = [];
  const pages = [
    { folders: [], documents: [{ id: "d1" }], total: 2 },
    { folders: [], documents: [{ id: "d2" }] },
  ];
  globalThis.fetch = async url => {
    seen.push(String(url));
    assert.ok(pages.length, "no network or extra request is allowed");
    return new Response(JSON.stringify(pages.shift()), { status: 200 });
  };
  try {
    assert.deepEqual(await api.tree(), { folders: [], documents: [{ id: "d1" }, { id: "d2" }], total_documents: 2 });
    assert.deepEqual(seen, ["/api/v1/library/tree?limit=100&offset=0", "/api/v1/library/tree?limit=100&offset=1&cursor=1"]);
  } finally { globalThis.fetch = previous; }
});

test("launcher: the same 33 ASCII controls are refused, valid strings and UTF-16 bounds preserved", () => {
  for (const code of [...Array(32).keys(), 127]) {
    assert.equal(launcherCommandsFrom({ commands: { open: `./rag${String.fromCharCode(code)}.sh open` } }), null, `control ${code}`);
  }
  assert.deepEqual(launcherCommandsFrom({ commands: { open: "./répertoire😀/rag.sh open" } }), { open: "./répertoire😀/rag.sh open" });
  const exactly200 = "a".repeat(195) + " open";
  assert.equal(exactly200.length, 200);
  assert.deepEqual(launcherCommandsFrom({ commands: { open: exactly200 } }), { open: exactly200 });
  for (const value of ["a" + exactly200, " ./rag.sh open", "./rag.sh open ", "./rag.sh status", ""]) assert.equal(launcherCommandsFrom({ commands: { open: value } }), null, JSON.stringify(value));
});

test("workspace entry pure function: exact citation, no bad-citation fallback, plain link and zero-based page", () => {
  const readEntry = loadFunction("components/workspace.tsx", "readWorkspaceEntry", { citationLinkIds, URLSearchParams }) as (search: string) => { kind: string; error?: unknown };
  assert.deepEqual(readEntry("?citation_query=q&citation_source=S1&document=other&version=other"), { kind: "citation", queryId: "q", sourceId: "S1" });
  const invalid = readEntry("?citation_query=q&document=other&version=other");
  assert.equal(invalid.kind, "error");
  assert.ok(invalid.error instanceof Error);
  assert.match(invalid.error.message, /deux identifiants valides/);
  assert.deepEqual(readEntry("?document=d&version=v&page=2"), { kind: "document", documentId: "d", versionId: "v", pageIndex: 1 });
  for (const search of ["?document=d&version=v&page=0", "?document=d&version=v&page=1.5", "?document=bad%2Fid&version=v&page=1"]) assert.deepEqual(readEntry(search), { kind: "none" });
});

test("sheet transition pure function: close for document/version/source or desktop, not page/scope", () => {
  const close = loadFunction("components/workspace.tsx", "shouldCloseSheet", {});
  const source = { source_id: "S1" };
  const previous = { compact: true, documentId: "d", versionId: "v", source };
  assert.equal(close(previous, { ...previous }), false);
  assert.equal(close(previous, { ...previous, pageIndex: 3, scope: { kind: "library" } }), false);
  assert.equal(close(previous, { ...previous, documentId: "other" }), true);
  assert.equal(close(previous, { ...previous, versionId: "other" }), true);
  assert.equal(close(previous, { ...previous, source: { ...source } }), true);
  assert.equal(close(previous, { ...previous, compact: false }), true);
});

test("portal callback, React/DOM doubles: stable node through renders, owned cleanup only", () => {
  let stored: unknown = null;
  let stableCallback: ((anchor: unknown) => () => void) | undefined;
  const effects: unknown[] = [];
  const created: { className: string; removed: number; remove: () => void }[] = [];
  const usePanelNode = loadFunction("components/workspace.tsx", "usePanelNode", {
    useState: () => [stored, (value: unknown) => { stored = value; }],
    useEffect: (effect: unknown) => { effects.push(effect); },
    useCallback: (callback: (anchor: unknown) => () => void) => { stableCallback ??= callback; return stableCallback; },
    document: { createElement: () => { const element = { className: "", removed: 0, remove() { this.removed++; } }; created.push(element); return element; } },
  }) as (slotRef: { current: unknown }) => [unknown, (anchor: unknown) => () => void];
  const slotRef: { current: unknown } = { current: null };
  const initial = usePanelNode(slotRef);
  assert.ok(Array.isArray(initial));
  assert.equal(created.length, 0, "render does not create DOM nodes");
  assert.equal(effects.length, 0, "no effect cascades state for a DOM node");
  const anchor = {};
  const cleanup = initial[1](anchor);
  const next = usePanelNode(slotRef);
  assert.equal(next[0], created[0]);
  assert.equal(next[1], initial[1]);
  assert.equal(slotRef.current, anchor);
  assert.equal(created.length, 1, "portal content survives ordinary rerenders");
  cleanup();
  assert.equal(created[0].removed, 1);
  assert.equal(slotRef.current, null);
});

test("real React server render: checking is identical and the client gate/children cannot run", () => {
  const file = "components/session-gate.tsx";
  const PanelLoading = loadFunction("components/ui/panel.tsx", "PanelLoading", { React, LoaderCircle: "span" });
  const SessionChecking = loadFunction(file, "SessionChecking", { React, PanelLoading });
  const SessionGate = loadFunction(file, "SessionGate", {
    React, useSyncExternalStore: React.useSyncExternalStore,
    subscribeHydration: loadVariable(file, "subscribeHydration"),
    clientSnapshot: loadVariable(file, "clientSnapshot"), serverSnapshot: loadVariable(file, "serverSnapshot"),
    SessionChecking, SessionGateClient: () => { throw new Error("client/session must not run in SSR"); },
  }) as React.ComponentType<{ children: React.ReactNode }>;
  const html = renderToString(React.createElement(SessionGate, null, "PRIVATE_CHILD_SENTINEL"));
  assert.match(html, /Ouverture de l&#x27;atelier/);
  assert.match(html, /Vérification de la session…/);
  assert.equal((html.match(/<main\b/g) ?? []).length, 1);
  assert.doesNotMatch(html, /PRIVATE_CHILD_SENTINEL|Lien d'ouverture/);
});

function gateDouble(search: string, expired = false, sessionReply?: () => Promise<unknown>) {
  const runtime = hookDouble();
  const listeners = new Map<string, (event: unknown) => void>();
  const calls = { session: 0, health: 0, logout: 0 };
  const location = { search, pathname: "/workspace/" };
  const client = {
    session: async () => { calls.session++; if (sessionReply) return sessionReply(); if (expired) throw new ApiError("session_expired", "Session expirée."); return {}; },
    health: async () => { calls.health++; return { commands: { open: "./rag.sh open" } }; },
    logout: async () => { calls.logout++; throw new Error("revocation double unavailable"); },
  };
  const SessionContext = { Provider: "qa-provider" };
  const component = loadFunction("components/session-gate.tsx", "SessionGateClient", {
    ...runtime.hooks, React, useLauncherCommands: () => null,
    api: client, checkSession, readLauncherCommands, linkInvalidFromSearch, SESSION_ENDED_EVENT,
    retryLauncherCommands: () => () => {}, SessionContext,
    window: {
      location, history: { replaceState: () => { location.search = ""; } },
      addEventListener: (name: string, handler: (event: unknown) => void) => listeners.set(name, handler),
      removeEventListener: (name: string, handler: (event: unknown) => void) => { if (listeners.get(name) === handler) listeners.delete(name); },
    },
    PanelLoading: "qa-loading", PanelError: "qa-error", SessionEnded: "qa-ended", unreachableText: () => "unreachable double",
  });
  return { runtime, calls, listeners, location, render: () => runtime.render(() => component({ children: "CHILD_SENTINEL" })) };
}

test("client gate, hooks/API doubles: the initial effect awaits session without a redundant checking write", async () => {
  let finish: ((reply: unknown) => void) | undefined;
  const gate = gateDouble("", false, () => new Promise(resolve => { finish = resolve; }));
  gate.render();
  assert.deepEqual(gate.runtime.peek(1), { kind: "checking" });
  gate.runtime.commit();
  assert.equal(gate.calls.session, 1);
  assert.deepEqual([...gate.runtime.stateWrites], [], "initial checking is already state; no synchronous effect write");
  assert.ok(finish);
  finish({});
  await new Promise<void>(resolve => setImmediate(resolve));
  assert.deepEqual(gate.runtime.peek(1), { kind: "open" });
  assert.deepEqual(gate.runtime.stateWrites, [{ index: 1, value: { kind: "open" } }]);
  gate.runtime.dispose();
});

test("client gate, hooks/API doubles: each user retry shows checking before the pending response and uses the actual async result", async () => {
  for (const failure of [new ApiError("session_expired", "Session expirée."), new TypeError("network double unavailable")]) {
    let attempt = 0;
    let finish: ((reply: unknown) => void) | undefined;
    const gate = gateDouble("", false, () => {
      attempt++;
      return attempt === 1 ? Promise.reject(failure) : new Promise(resolve => { finish = resolve; });
    });
    gate.render(); gate.runtime.commit();
    await new Promise<void>(resolve => setImmediate(resolve));
    const expected = failure instanceof ApiError ? { kind: "ended", reason: "session_expired" } : { kind: "unreachable", failure };
    assert.deepEqual(gate.runtime.peek(1), expected);
    const screen = elementProps(gate.render()); gate.runtime.commit();
    const retryPanel = findElementOfType(screen.children as React.ReactNode, failure instanceof ApiError ? "qa-ended" : "qa-error");
    assert.ok(retryPanel, "the actual failed screen must expose its retry handler");
    const retry = elementProps(retryPanel).onRetry;
    assert.equal(typeof retry, "function");
    gate.runtime.stateWrites.splice(0);
    (retry as () => void)();
    assert.equal(gate.calls.session, 2, "the user handler starts one real shared check, not a deferred substitute");
    assert.deepEqual(gate.runtime.peek(1), { kind: "checking" }, "loading is observable before the unresolved response");
    assert.deepEqual(gate.runtime.stateWrites, [{ index: 1, value: { kind: "checking" } }]);
    assert.ok(finish);
    finish({});
    await new Promise<void>(resolve => setImmediate(resolve));
    assert.deepEqual(gate.runtime.peek(1), { kind: "open" });
    assert.equal(gate.calls.health, 2);
    assert.equal(elementProps(gate.render()).children, "CHILD_SENTINEL");
    gate.runtime.commit(); gate.runtime.dispose();
  }
});

test("client gate, hooks/API doubles: invalid link survives setup replay, never checks a session, cleans URL/listener", async () => {
  const gate = gateDouble("?session=lien-invalide");
  gate.render(); gate.runtime.commit();
  assert.deepEqual(gate.runtime.peek(1), { kind: "ended", reason: "link_invalid" });
  assert.equal(gate.location.search, "");
  assert.equal(gate.calls.session, 0);
  gate.runtime.dispose();
  // Re-create the effect subscription with retained committed state, as a setup/cleanup replay double.
  assert.equal(gate.listeners.size, 0);
  gate.runtime.replayEffects(); gate.render(); gate.runtime.commit();
  assert.deepEqual(gate.runtime.peek(1), { kind: "ended", reason: "link_invalid" });
  assert.equal(gate.listeners.size, 1);
  await new Promise<void>(resolve => setImmediate(resolve));
  assert.equal(gate.calls.health, 2);
  assert.equal(gate.calls.session, 0);
  gate.runtime.dispose(); assert.equal(gate.listeners.size, 0);
});

test("client gate, hooks/API doubles: success, expiration event, logout failure and initial expired session remain distinct", async () => {
  const gate = gateDouble("");
  gate.render(); gate.runtime.commit();
  await new Promise<void>(resolve => setImmediate(resolve));
  assert.deepEqual(gate.runtime.peek(1), { kind: "open" });
  const props = elementProps(gate.render()); gate.runtime.commit();
  assert.equal(props.children, "CHILD_SENTINEL");
  const logout = (props.value as { logout: () => Promise<void> }).logout;
  await logout();
  assert.deepEqual(gate.runtime.peek(1), { kind: "ended", reason: "session_closed" });
  assert.equal(gate.calls.logout, 1);
  const ended = gate.listeners.get(SESSION_ENDED_EVENT);
  assert.ok(ended);
  ended({ detail: "session_expired" });
  assert.deepEqual(gate.runtime.peek(1), { kind: "ended", reason: "session_expired" });
  gate.runtime.dispose(); assert.equal(gate.listeners.size, 0);
  const expired = gateDouble("", true);
  expired.render(); expired.runtime.commit();
  await new Promise<void>(resolve => setImmediate(resolve));
  assert.deepEqual(expired.runtime.peek(1), { kind: "ended", reason: "session_expired" });
  expired.runtime.dispose();
});

test("dismiss hook, React/DOM doubles: latest committed callback, Escape/default prevention, inside/outside and cleanup", () => {
  const runtime = hookDouble();
  class QaNode {}
  const inside = new QaNode();
  const container = { current: { contains: (node: QaNode) => node === inside } };
  const listeners = new Map<string, (event: unknown) => void>();
  const seen: string[] = [];
  const hook = loadFunction("lib/use-dismiss.ts", "useDismiss", {
    ...runtime.hooks, Node: QaNode,
    document: {
      addEventListener: (name: string, handler: (event: unknown) => void) => listeners.set(name, handler),
      removeEventListener: (name: string, handler: (event: unknown) => void) => { if (listeners.get(name) === handler) listeners.delete(name); },
    },
  });
  runtime.render(() => hook(true, container, (reason: string) => seen.push(`old:${reason}`))); runtime.commit();
  const onKey = listeners.get("keydown"); const onPointer = listeners.get("pointerdown");
  assert.ok(onKey && onPointer);
  runtime.render(() => hook(true, container, (reason: string) => seen.push(`new:${reason}`)));
  assert.deepEqual([...seen], [], "render does not fire the callback");
  const uncommittedEscape = { key: "Escape", defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
  onKey(uncommittedEscape);
  assert.deepEqual(seen, ["old:escape"], "the listener cannot see an uncommitted render callback");
  runtime.commit();
  assert.equal(listeners.get("keydown"), onKey, "callback change does not resubscribe listeners");
  const escape = { key: "Escape", defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
  onKey(escape); assert.equal(escape.defaultPrevented, true);
  onKey({ ...escape });
  onPointer({ target: inside }); onPointer({ target: new QaNode() }); onPointer({ target: {} });
  assert.deepEqual(seen, ["old:escape", "new:escape", "new:outside"]);
  runtime.render(() => hook(false, container, () => seen.push("closed"))); runtime.commit();
  assert.equal(listeners.size, 0); runtime.dispose();
});

test("confirmation keyboard, DOM doubles: Tab wraps only at the enabled action boundaries", () => {
  const keepTab = loadFunction("components/ui/confirm-dialog.tsx", "keepTabWithinConfirmation", {});
  const focused: string[] = [];
  const first = { focus: () => focused.push("cancel") };
  const middle = { focus: () => focused.push("middle") };
  const last = { focus: () => focused.push("confirm") };
  const heading = { focus: () => focused.push("heading") };
  const ownerDocument = { activeElement: first as unknown };
  const dialog = {
    open: true, ownerDocument,
    querySelectorAll: (selector: string) => { assert.equal(selector, "button:enabled"); return [first, middle, last]; },
    querySelector: (selector: string) => { assert.equal(selector, "h2"); return heading; },
  };
  const key = (changes: Record<string, unknown> = {}) => {
    const event = { currentTarget: dialog, key: "Tab", shiftKey: false, altKey: false, ctrlKey: false, metaKey: false, defaultPrevented: false,
      preventDefault() { this.defaultPrevented = true; }, ...changes };
    keepTab(event);
    return event;
  };
  assert.equal(key().defaultPrevented, false, "ordinary progression remains native");
  ownerDocument.activeElement = last;
  assert.equal(key().defaultPrevented, true);
  ownerDocument.activeElement = first;
  assert.equal(key({ shiftKey: true }).defaultPrevented, true);
  ownerDocument.activeElement = middle;
  assert.equal(key({ shiftKey: true }).defaultPrevented, false);
  ownerDocument.activeElement = heading;
  assert.equal(key().defaultPrevented, true);
  assert.equal(key({ shiftKey: true }).defaultPrevented, true);
  assert.deepEqual(focused, ["cancel", "confirm", "cancel", "confirm"]);
  for (const changes of [{ key: "Escape" }, { altKey: true }, { ctrlKey: true }, { metaKey: true }, { defaultPrevented: true }]) key(changes);
  dialog.open = false; key();
  assert.deepEqual(focused, ["cancel", "confirm", "cancel", "confirm"], "Escape, browser shortcuts and closed dialogs are untouched");
});

test("confirmation keyboard, DOM doubles: a single enabled action loops; pending actions retain a static focus target", () => {
  const keepTab = loadFunction("components/ui/confirm-dialog.tsx", "keepTabWithinConfirmation", {});
  let focused = 0;
  const action = { focus: () => { focused++; } };
  const heading = { focus: () => { focused++; } };
  let actions = [action];
  const dialog = { open: true, ownerDocument: { activeElement: action }, querySelectorAll: () => actions, querySelector: () => heading };
  for (const shiftKey of [false, true]) {
    let prevented = false;
    keepTab({ currentTarget: dialog, key: "Tab", shiftKey, preventDefault: () => { prevented = true; } });
    assert.equal(prevented, true);
  }
  actions = [];
  let prevented = false;
  keepTab({ currentTarget: dialog, key: "Tab", preventDefault: () => { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(focused, 3);
});

/** Append-only proposed witnesses. Uses this unit file's actual-function loader and declared hook/DOM doubles. */
function confirmationFocusDouble(cancelLabel = "Annuler") {
  const runtime = hookDouble();
  const ownerDocument = { activeElement: null as unknown };
  const focused: string[] = [];
  const target = (name: string) => ({ focus() { ownerDocument.activeElement = this; focused.push(name); } });
  const opener = target("opener");
  const heading = target("heading");
  const cancel = target("cancel");
  const confirm = target("confirm");
  ownerDocument.activeElement = opener;
  const dialog = {
    open: false, shown: 0, closed: 0,
    // Deliberate counterexample, not a claim about the historical browser's active element.
    showModal() { this.open = true; this.shown++; ownerDocument.activeElement = heading; focused.push("native:heading"); },
    close() { this.open = false; this.closed++; ownerDocument.activeElement = opener; },
    querySelector: (selector: string) => { assert.equal(selector, "h2"); return heading; },
  };
  const keepTab = loadFunction("components/ui/confirm-dialog.tsx", "keepTabWithinConfirmation", {});
  const Confirm = loadFunction("components/ui/confirm-dialog.tsx", "ConfirmDialog", {
    ...runtime.hooks, React, Button: "button", CircleAlert: "span", TriangleAlert: "span", keepTabWithinConfirmation: keepTab,
  });
  const render = (open: boolean, pending = false, error?: string) => {
    const tree = runtime.render(() => Confirm({
      open, pending, error, title: "Confirmation", message: "Conséquence", cancelLabel,
      confirmLabel: "Retirer", pendingLabel: "Retrait en cours", onConfirm: () => {}, onCancel: () => {},
    }));
    const props = elementProps(tree);
    (props.ref as { current: unknown }).current = dialog;
    const action = findElementOfType(tree as React.ReactNode, "button");
    assert.ok(action);
    assert.equal(elementProps(action).children, cancelLabel, "the actual first action is cancellation, regardless of its label");
    const ref = elementProps(action).ref as { current: unknown } | undefined;
    if (ref) ref.current = cancel; // Simulated DOM ref attachment; absent before the fix.
    return tree;
  };
  return { runtime, ownerDocument, focused, opener, heading, cancel, confirm, dialog, render };
}

test("confirmation initial focus, actual component/hooks/DOM doubles: nominal showModal heading is replaced by the cancel action", () => {
  for (const label of ["Annuler", "Retour"]) {
    const fixture = confirmationFocusDouble(label);
    try {
      fixture.render(true);
      assert.equal(fixture.ownerDocument.activeElement, fixture.opener, "render alone cannot move focus");
      fixture.runtime.commit();
      assert.equal(fixture.dialog.shown, 1);
      assert.equal(fixture.ownerDocument.activeElement, fixture.cancel);
      assert.deepEqual(fixture.focused, ["native:heading", "cancel"]);
    } finally { fixture.runtime.dispose(); }
  }
});

test("confirmation initial focus, actual component/hooks/DOM doubles: rerenders and pending completion do not steal focus", () => {
  const fixture = confirmationFocusDouble();
  try {
    fixture.render(true); fixture.runtime.commit();
    fixture.confirm.focus();
    fixture.focused.splice(0);
    fixture.render(true, false, "Erreur synthétique"); fixture.runtime.commit();
    assert.equal(fixture.ownerDocument.activeElement, fixture.confirm);
    assert.deepEqual(fixture.focused, []);
    fixture.render(true, true); fixture.runtime.commit();
    assert.equal(fixture.ownerDocument.activeElement, fixture.heading);
    assert.deepEqual(fixture.focused, ["heading"]);
    fixture.focused.splice(0);
    fixture.render(true, false); fixture.runtime.commit();
    assert.equal(fixture.ownerDocument.activeElement, fixture.heading, "still-open pending completion is not a new modal opening");
    assert.deepEqual(fixture.focused, []);
    assert.equal(fixture.dialog.shown, 1);
  } finally { fixture.runtime.dispose(); }
});

test("confirmation initial focus, actual component/hooks/DOM doubles: each nominal reopening targets cancellation", () => {
  const fixture = confirmationFocusDouble();
  try {
    fixture.render(false); fixture.runtime.commit();
    fixture.render(true); fixture.runtime.commit();
    fixture.render(false); fixture.runtime.commit();
    assert.equal(fixture.dialog.closed, 1);
    fixture.focused.splice(0);
    fixture.render(true); fixture.runtime.commit();
    assert.equal(fixture.dialog.shown, 2);
    assert.equal(fixture.ownerDocument.activeElement, fixture.cancel);
    assert.deepEqual(fixture.focused, ["native:heading", "cancel"]);
  } finally { fixture.runtime.dispose(); }
});

test("confirmation initial focus, actual component/hooks/DOM doubles: an initially pending dialog keeps its static heading", () => {
  const fixture = confirmationFocusDouble();
  try {
    fixture.render(true, true); fixture.runtime.commit();
    assert.equal(fixture.ownerDocument.activeElement, fixture.heading);
    assert.deepEqual(fixture.focused, ["native:heading", "heading"]);
    assert.equal(fixture.dialog.shown, 1);
  } finally { fixture.runtime.dispose(); }
});

test("native dialogs, React/DOM doubles: commit flags, modal/focus cleanup and pending cancellation", () => {
  const runtime = hookDouble();
  let focused = 0; let dismissed = 0;
  const opener = { isConnected: true, focus: () => { focused++; } };
  class QaHTMLElement {}
  Object.setPrototypeOf(opener, QaHTMLElement.prototype);
  let pendingFocus = 0;
  const dialog = { open: false, shown: 0, closed: 0, showModal() { this.open = true; this.shown++; }, close() { this.open = false; this.closed++; }, querySelector: () => ({ focus: () => { pendingFocus++; } }) };
  const Sheet = loadFunction("components/ui/sheet.tsx", "Sheet", { ...runtime.hooks, React, cn: (...parts: unknown[]) => parts.join(" "), HTMLElement: QaHTMLElement, document: { activeElement: opener } });
  const render = (open: boolean) => runtime.render(() => Sheet({ open, onClose: () => { dismissed++; }, side: "left", labelledBy: "heading" }));
  render(false); (runtime.peek(0) as { current: unknown }).current = dialog; runtime.commit();
  const opened = elementProps(render(true));
  assert.equal((runtime.peek(2) as { current: unknown }).current, false, "uncommitted render cannot rewrite openRef");
  runtime.commit(); assert.equal(dialog.shown, 1);
  dialog.open = false; // External/native closure precedes the React close handler.
  (opened.onClose as () => void)(); assert.equal(dismissed, 1); assert.equal(focused, 1);
  render(false); runtime.commit(); render(true); runtime.commit();
  const closed = elementProps(render(false)); runtime.commit(); (closed.onClose as () => void)();
  assert.equal(dialog.closed, 1, "a prop closure calls the native close method");
  assert.equal(dismissed, 1, "programmatic prop closure is not a second cancellation");
  render(true); runtime.commit();
  runtime.dispose();
  assert.equal(dialog.open, false, "unmount releases its modal");

  const confirmRuntime = hookDouble();
  let cancelled = 0; let prevented = 0;
  const keepTab = loadFunction("components/ui/confirm-dialog.tsx", "keepTabWithinConfirmation", {});
  const Confirm = loadFunction("components/ui/confirm-dialog.tsx", "ConfirmDialog", { ...confirmRuntime.hooks, React, Button: "button", CircleAlert: "span", TriangleAlert: "span", keepTabWithinConfirmation: keepTab });
  const confirmation = confirmRuntime.render(() => Confirm({ open: true, pending: true, title: "Confirm", message: "Consequence", confirmLabel: "Confirm", pendingLabel: "Pending", onConfirm: () => {}, onCancel: () => { cancelled++; } }));
  const confirming = elementProps(confirmation);
  assert.equal(confirming.onKeyDown, keepTab, "the real keyboard handler is wired to the dialog");
  const heading = findElementOfType(confirmation as React.ReactNode, "h2");
  assert.ok(heading);
  assert.equal(elementProps(heading).tabIndex, -1, "pending focus target is not an extra Tab stop");
  (confirmRuntime.peek(0) as { current: unknown }).current = dialog; confirmRuntime.commit();
  assert.equal(pendingFocus, 1, "disabled actions hand focus to the static heading");
  (confirming.onCancel as (event: unknown) => void)({ preventDefault: () => { prevented++; } });
  assert.equal(prevented, 1); assert.equal(cancelled, 0, "pending action refuses normal Escape");
  dialog.open = false;
  (confirming.onClose as () => void)(); assert.equal(cancelled, 1, "forced native close still updates React");
  confirmRuntime.dispose(); assert.equal(dialog.open, false);
});

test("reader title CSS guard: ellipsis is restricted to the reader heading, not a nested confirmation", () => {
  const css = readSource("app/globals.css");
  assert.doesNotMatch(css, /\.viewer-title\s+h2\s*\{/);
  assert.match(css, /\.viewer-title\s*>\s*div\s*>\s*h2\s*\{[^}]*text-overflow:\s*ellipsis/);
  assert.match(css, /\.confirm-dialog h2 > svg\s*\{[^}]*flex-shrink:\s*0/);
});
