import { test } from "node:test";
import assert from "node:assert/strict";
import { csrfFromCookies, isSessionFailure, linkInvalidFromSearch, OPEN_COMMAND, sessionScreen, type SessionEndReason } from "../../src/lib/session.ts";

test("le jeton CSRF est lu dans le cookie lisible, nom préfixé de production d'abord", () => {
  assert.equal(csrfFromCookies("rag_csrf=abc-123; autre=1"), "abc-123");
  assert.equal(csrfFromCookies("rag_csrf=dev; __Host-rag_csrf=prod"), "prod");
  assert.equal(csrfFromCookies("rag_csrf=a%2Bb"), "a+b");
  assert.equal(csrfFromCookies(""), null);
  assert.equal(csrfFromCookies("rag_session=secret"), null);
  assert.equal(csrfFromCookies("rag_csrf="), null);
});

test("seuls les refus de session déclenchent l'écran de réouverture", () => {
  assert.equal(isSessionFailure("session_required"), true);
  assert.equal(isSessionFailure("session_expired"), true);
  for (const code of ["csrf_rejected", "NETWORK_ERROR", "invalid_origin", "HTTP_401"]) assert.equal(isSessionFailure(code), false);
});

test("le lien refusé est reconnu par son paramètre de redirection seulement", () => {
  assert.equal(linkInvalidFromSearch("?session=lien-invalide"), true);
  assert.equal(linkInvalidFromSearch("?session=autre"), false);
  assert.equal(linkInvalidFromSearch(""), false);
});

test("chaque écran de session dit la cause et renvoie à la commande d'ouverture", () => {
  const reasons: SessionEndReason[] = ["session_required", "session_expired", "session_closed", "link_invalid"];
  const titles = new Set<string>();
  for (const reason of reasons) {
    const screen = sessionScreen(reason);
    assert.ok(screen.title.length > 0 && screen.body.length > 40, reason);
    assert.match(screen.body, /commande ci-dessous/, reason);
    titles.add(screen.title);
  }
  assert.equal(titles.size, reasons.length);
  assert.equal(OPEN_COMMAND, ".\\rag.ps1 open");
});
