import { test } from "node:test";
import assert from "node:assert/strict";
import { csrfFromCookies, isSessionFailure, linkInvalidFromSearch, sessionScreen, type SessionEndReason } from "../../src/lib/session.ts";
import { openCommandChoices } from "../../src/lib/launcher.ts";

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
    const screen = sessionScreen(reason, { open: ".\\rag.ps1 open" });
    assert.ok(screen.title.length > 0 && screen.body.length > 40, reason);
    assert.match(screen.body, /la commande ci-dessous/, reason);
    // Commande d'ouverture inconnue : deux lignes, une par système, et le texte le dit.
    assert.match(sessionScreen(reason, null).body, /la commande de votre système ci-dessous/, reason);
    titles.add(screen.title);
  }
  assert.equal(titles.size, reasons.length);
});

test("the opening command shown is the one of this host, or one line per delivered launcher while unknown", () => {
  assert.deepEqual(openCommandChoices({ open: ".\\rag.ps1 open" }), [{ system: null, command: ".\\rag.ps1 open" }]);
  assert.deepEqual(openCommandChoices({ open: "./rag.sh open" }), [{ system: null, command: "./rag.sh open" }]);
  assert.deepEqual(openCommandChoices(null), [{ system: "Windows", command: ".\\rag.ps1 open" }, { system: "Linux", command: "./rag.sh open" }]);
  // Plateforme connue par une autre commande annoncée : le lanceur livré qu'elle emploie.
  assert.deepEqual(openCommandChoices({ status: "./rag.sh status" }), [{ system: null, command: "./rag.sh open" }]);
  // Lanceurs mêlés ou autre chemin : plateforme inconnue, une ligne par lanceur livré.
  assert.deepEqual(openCommandChoices({ status: "./rag.sh status", logs: ".\\rag.ps1 logs" }), openCommandChoices(null));
  assert.deepEqual(openCommandChoices({ status: "/opt/rag/rag.sh status" }), openCommandChoices(null));
});
