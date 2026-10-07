import { test } from "node:test";
import assert from "node:assert/strict";
import { csrfFromCookies, isSessionFailure, linkInvalidFromSearch, sessionCloseTitle, sessionScreen, type SessionEndReason } from "../../src/lib/session.ts";
import { launcherCommandsFrom, openCommandChoices } from "../../src/lib/launcher.ts";

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

// Installation par le kit Linux (R26-KIT-04, KIT4-13) : menu des applications s'il existe, et commande à taper dans un
// terminal ; aucun renvoi au dossier du projet. Le clone et Windows gardent leurs textes (launcher.test.ts, windows-texts).
const ATELIER = "/home/atelier/.local/share/atelier-documentaire/programme/atelier";
const installed = (menu: string | null) => launcherCommandsFrom({ status: "alive", service: "rag-api",
  commands: { open: `${ATELIER} ouvrir`, status: `${ATELIER} etat`, logs: `${ATELIER} journaux`, doctor: `${ATELIER} diagnostic` },
  launcher: { kind: "installation", menu } });

test("installation screens offer the applications menu and the command to type in a terminal", () => {
  const withMenu = installed("Atelier documentaire");
  assert.deepEqual(sessionScreen("session_required", withMenu), { title: "Session requise",
    body: "L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. Ouvrez-le depuis le menu des applications (Atelier documentaire), ou lancez la commande ci-dessous dans un terminal : il s'affiche dans un nouvel onglet." });
  assert.equal(sessionScreen("session_expired", withMenu).body, "La session s'est fermée après une période sans activité ou a atteint sa durée maximale. Rouvrez l'atelier depuis le menu des applications (Atelier documentaire) ou avec la commande ci-dessous, dans un terminal ; documents, index et conversations enregistrés restent intacts.");
  assert.equal(sessionScreen("session_closed", withMenu).body, "La session de ce navigateur est fermée. Pour reprendre le travail, rouvrez l'atelier depuis le menu des applications (Atelier documentaire) ou avec la commande ci-dessous, dans un terminal.");
  assert.equal(sessionScreen("link_invalid", withMenu).body, "Chaque lien d'ouverture ne sert qu'une fois et expire après quelques minutes. Demandez-en un nouveau depuis le menu des applications (Atelier documentaire) ou avec la commande ci-dessous, dans un terminal.");
  assert.deepEqual(openCommandChoices(withMenu), [{ system: null, command: `${ATELIER} ouvrir` }]);
});

test("an installation without menu entry names only the terminal command", () => {
  const withoutMenu = installed(null);
  assert.equal(sessionScreen("session_required", withoutMenu).body, "L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. Dans un terminal, lancez la commande ci-dessous : elle ouvre l'atelier dans un nouvel onglet.");
  assert.equal(sessionScreen("session_expired", withoutMenu).body, "La session s'est fermée après une période sans activité ou a atteint sa durée maximale. Rouvrez l'atelier avec la commande ci-dessous, dans un terminal ; documents, index et conversations enregistrés restent intacts.");
  for (const reason of ["session_required", "session_expired", "session_closed", "link_invalid"] as SessionEndReason[]) {
    assert.doesNotMatch(sessionScreen(reason, withoutMenu).body, /menu|dossier du projet|commande de votre système/, reason);
  }
});

test("the closing tooltip names the way back of this host", () => {
  assert.equal(sessionCloseTitle(installed("Atelier documentaire")), `Ferme la session de ce navigateur. Pour revenir : menu des applications (Atelier documentaire), ou ${ATELIER} ouvrir dans un terminal.`);
  assert.equal(sessionCloseTitle(installed(null)), `Ferme la session de ce navigateur. Pour revenir : ${ATELIER} ouvrir dans un terminal.`);
  // Clone Linux et Windows : texte d'avant l'installation par le kit.
  assert.equal(sessionCloseTitle({ open: "./rag.sh open" }), "Ferme la session de ce navigateur. Pour revenir : ./rag.sh open depuis le dossier du projet.");
  assert.equal(sessionCloseTitle({ open: ".\\rag.ps1 open" }), "Ferme la session de ce navigateur. Pour revenir : .\\rag.ps1 open depuis le dossier du projet.");
});
