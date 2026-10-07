/**
 * Commandes du lanceur affichées par l'interface (W018) : celles que le poste annonce dans
 * `GET /api/v1/health` ; une commande non annoncée prend le lanceur livré des autres quand elles
 * l'emploient toutes (plateforme connue), sinon le texte donne les deux formes livrées.
 * Sous Windows, les textes restent ceux d'avant la prise en charge de Linux, mot pour mot
 * (comparaison avec le commit de référence dans windows-texts.test.ts).
 */
import assert from "node:assert/strict";
import test from "node:test";
import { knownLauncherCommands, launcherCommandsFrom, launcherShell, launcherText, openCommandChoices, rememberLauncherCommands, type LauncherCommands } from "../../src/lib/launcher.ts";
import { sessionCloseTitle, sessionScreen, type SessionEndReason } from "../../src/lib/session.ts";
import { httpFailureMessage, readinessSentence, serviceUnreachableMessage } from "../../src/lib/warnings.ts";
import { errorMessage } from "../../src/lib/utils.ts";
import { readSource, sourceFiles, stripScriptComments } from "./theme-support.ts";

// Réponses de /health antérieures à l'annonce de `doctor` (open, status et logs seulement).
const windowsHealth = { status: "alive", service: "rag-api", commands: { open: ".\\rag.ps1 open", status: ".\\rag.ps1 status", logs: ".\\rag.ps1 logs" } };
const linuxHealth = { status: "alive", service: "rag-api", commands: { open: "./rag.sh open", status: "./rag.sh status", logs: "./rag.sh logs" } };
const windows = launcherCommandsFrom(windowsHealth)!;
const linux = launcherCommandsFrom(linuxHealth)!;
// Réponses actuelles de /health (services/api/main.py, `launcher_commands`) : doctor est annoncé.
const windowsWithDoctor = launcherCommandsFrom({ commands: { ...windowsHealth.commands, doctor: ".\\rag.ps1 doctor" } })!;
const linuxWithDoctor = launcherCommandsFrom({ commands: { ...linuxHealth.commands, doctor: "./rag.sh doctor" } })!;

test("the commands announced by /health are kept as is; none is added to the announced set", () => {
  assert.deepEqual(windows, { open: ".\\rag.ps1 open", status: ".\\rag.ps1 status", logs: ".\\rag.ps1 logs" });
  assert.deepEqual(linux, { open: "./rag.sh open", status: "./rag.sh status", logs: "./rag.sh logs" });
  assert.equal(windowsWithDoctor.doctor, ".\\rag.ps1 doctor");
  assert.equal(linuxWithDoctor.doctor, "./rag.sh doctor");
});

test("a health reply without usable commands leaves them unknown instead of guessing", () => {
  for (const health of [null, "alive", { status: "alive", service: "rag-api" }, { commands: null }, { commands: "./rag.sh open" }, { commands: {} }]) {
    assert.equal(launcherCommandsFrom(health), null, JSON.stringify(health));
  }
  // Valeurs refusées une à une : autre type, retour à la ligne, action différente de la clé, espaces de bord.
  const refused = launcherCommandsFrom({ commands: { open: 42, status: "./rag.sh status\nrm -rf /", logs: "./rag.sh status", doctor: " ./rag.sh doctor" } });
  assert.equal(refused, null);
  // Lanceurs mêlés : chaque commande annoncée est gardée telle quelle.
  assert.deepEqual(launcherCommandsFrom({ commands: { open: "./rag.sh open", status: ".\\rag.ps1 status" } }), { open: "./rag.sh open", status: ".\\rag.ps1 status" });
  assert.deepEqual(launcherCommandsFrom({ commands: { open: "./rag.sh open" } }), { open: "./rag.sh open" });
});

test("known commands are shown exactly; unknown ones give both delivered forms", () => {
  assert.equal(launcherText("open", windows), ".\\rag.ps1 open");
  assert.equal(launcherText("status", linux), "./rag.sh status");
  assert.equal(launcherText("logs", null), ".\\rag.ps1 logs sous Windows ou ./rag.sh logs sous Linux");
  assert.equal(launcherText("logs", {}), ".\\rag.ps1 logs sous Windows ou ./rag.sh logs sous Linux");
  // Plateforme connue par les commandes annoncées : le lanceur livré qu'elles emploient toutes.
  assert.equal(launcherText("doctor", { open: "./rag.sh open" }), "./rag.sh doctor");
  assert.equal(launcherText("doctor", windows), ".\\rag.ps1 doctor");
  assert.equal(launcherText("doctor", linux), "./rag.sh doctor");
  // Plateforme inconnue : lanceurs mêlés, ou chemin qui n'est pas celui d'un lanceur livré.
  assert.equal(launcherText("doctor", { open: "./rag.sh open", status: ".\\rag.ps1 status" }), ".\\rag.ps1 doctor sous Windows ou ./rag.sh doctor sous Linux");
  assert.equal(launcherText("doctor", { open: "C:\\outils\\rag.ps1 open" }), ".\\rag.ps1 doctor sous Windows ou ./rag.sh doctor sous Linux");
  // Une commande annoncée prime toujours, même hors des lanceurs livrés.
  assert.equal(launcherText("open", { open: "C:\\outils\\rag.ps1 open" }), "C:\\outils\\rag.ps1 open");
  assert.equal(launcherShell(windows), "dans PowerShell");
  assert.equal(launcherShell(linux), "dans un terminal");
  assert.equal(launcherShell(null), "dans PowerShell sous Windows ou dans un terminal sous Linux");
  assert.equal(launcherShell({ status: "./rag.sh status" }), "dans un terminal");
  assert.equal(launcherShell({ open: "./rag.sh open", status: ".\\rag.ps1 status" }), "dans un terminal");
  assert.equal(launcherShell({ status: "./rag.sh status", logs: ".\\rag.ps1 logs" }), "dans PowerShell sous Windows ou dans un terminal sous Linux");
});

test("Windows texts are unchanged word for word once the service has announced its commands", () => {
  assert.equal(serviceUnreachableMessage(windows), "Le service local ne répond pas. Vérifiez qu'il est démarré (.\\rag.ps1 status), puis réessayez.");
  assert.equal(httpFailureMessage(500, windows), "Le service local a échoué (HTTP 500). Réessayez ; si l'échec persiste, consultez son journal : la commande .\\rag.ps1 logs en donne l'emplacement.");
  assert.equal(errorMessage(null, windows), "L'opération a échoué sans message exploitable. Réessayez ; si l'échec persiste, consultez le journal du service : la commande .\\rag.ps1 logs en donne l'emplacement.");
  assert.equal(readinessSentence(["qdrant_not_ready"], windowsWithDoctor), "Préparation du poste incomplète : Index vectoriel indisponible. Les recherches et les questions qui en dépendent échouent tant que ces composants ne sont pas prêts. La commande .\\rag.ps1 doctor détaille chaque contrôle ; l'état est relu toutes les 10 secondes.");
  assert.equal(sessionScreen("session_required", windows).body, "L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. Dans PowerShell, depuis le dossier du projet, lancez la commande ci-dessous : elle ouvre l'atelier dans un nouvel onglet.");
  assert.equal(sessionScreen("session_expired", windows).body, "La session s'est fermée après une période sans activité ou a atteint sa durée maximale. Rouvrez l'atelier avec la commande ci-dessous ; documents, index et conversations enregistrés restent intacts.");
  assert.equal(sessionScreen("session_closed", windows).body, "La session de ce navigateur est fermée. Pour reprendre le travail, rouvrez l'atelier avec la commande ci-dessous.");
  assert.equal(sessionScreen("link_invalid", windows).body, "Chaque lien d'ouverture ne sert qu'une fois et expire après quelques minutes. Demandez-en un nouveau avec la commande ci-dessous.");
});

test("without an announced doctor command, the readiness notice follows the known platform, or gives both forms", () => {
  const windowsText = "Préparation du poste incomplète : Index vectoriel indisponible. Les recherches et les questions qui en dépendent échouent tant que ces composants ne sont pas prêts. La commande .\\rag.ps1 doctor détaille chaque contrôle ; l'état est relu toutes les 10 secondes.";
  assert.equal(readinessSentence(["qdrant_not_ready"], windows), windowsText);
  assert.equal(readinessSentence(["qdrant_not_ready"], windowsWithDoctor), windowsText);
  assert.equal(readinessSentence(["qdrant_not_ready"], linux), windowsText.replace(".\\rag.ps1 doctor", "./rag.sh doctor"));
  assert.equal(readinessSentence(["qdrant_not_ready"], null), windowsText.replace(".\\rag.ps1 doctor", ".\\rag.ps1 doctor sous Windows ou ./rag.sh doctor sous Linux"));
});

test("Linux texts name rag.sh and a terminal, never PowerShell", () => {
  const texts = [serviceUnreachableMessage(linux), httpFailureMessage(503, linux), errorMessage(undefined, linux), readinessSentence(["ollama_not_ready"], linuxWithDoctor),
    ...(["session_required", "session_expired", "session_closed", "link_invalid"] as SessionEndReason[]).map(reason => sessionScreen(reason, linux).body)];
  for (const text of texts) {
    assert.doesNotMatch(text, /rag\.ps1|PowerShell/, text);
  }
  assert.match(serviceUnreachableMessage(linux), /\(\.\/rag\.sh status\)/);
  assert.match(httpFailureMessage(500, linux), /la commande \.\/rag\.sh logs en donne l'emplacement\.$/);
  assert.match(readinessSentence(["ollama_not_ready"], linuxWithDoctor), /La commande \.\/rag\.sh doctor détaille chaque contrôle/);
  assert.match(sessionScreen("session_required", linux).body, /^L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste\. Dans un terminal, depuis le dossier du projet/);
});

test("while the service is silent, each text gives both forms without choosing a platform", () => {
  assert.equal(serviceUnreachableMessage(null), "Le service local ne répond pas. Vérifiez qu'il est démarré (.\\rag.ps1 status sous Windows ou ./rag.sh status sous Linux), puis réessayez.");
  assert.match(httpFailureMessage(500, null), /la commande \.\\rag\.ps1 logs sous Windows ou \.\/rag\.sh logs sous Linux en donne l'emplacement\.$/);
  assert.equal(sessionScreen("session_required", null).body, "L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. Dans PowerShell sous Windows ou dans un terminal sous Linux, depuis le dossier du projet, lancez la commande de votre système ci-dessous : elle ouvre l'atelier dans un nouvel onglet.");
  // Deux lignes de commande sont affichées : chaque écran dit de choisir celle de son système.
  for (const reason of ["session_required", "session_expired", "session_closed", "link_invalid"] as SessionEndReason[]) {
    const body = sessionScreen(reason, null).body;
    assert.match(body, /la commande de votre système ci-dessous/, body);
    assert.doesNotMatch(body, /la commande ci-dessous/, body);
  }
  // Commandes annoncées sans `open` : la plateforme est connue, une seule ligne et le texte d'avant W018 sous Windows.
  assert.equal(sessionScreen("session_closed", { status: ".\\rag.ps1 status" }).body, "La session de ce navigateur est fermée. Pour reprendre le travail, rouvrez l'atelier avec la commande ci-dessous.");
  assert.deepEqual(openCommandChoices({ status: ".\\rag.ps1 status" }), [{ system: null, command: ".\\rag.ps1 open" }]);
  // Lanceurs mêlés sans `open` : deux lignes, donc « la commande de votre système ».
  assert.match(sessionScreen("session_closed", { status: ".\\rag.ps1 status", logs: "./rag.sh logs" }).body, /la commande de votre système ci-dessous\.$/);
});

test("the remembered commands feed the texts computed after the health reply", () => {
  const before: LauncherCommands | null = knownLauncherCommands();
  assert.equal(before, null, "aucune commande connue avant la réponse du service");
  assert.match(httpFailureMessage(500), /sous Windows ou .* sous Linux/);
  rememberLauncherCommands(linux);
  assert.equal(knownLauncherCommands(), linux);
  assert.match(httpFailureMessage(500), /la commande \.\/rag\.sh logs en donne/);
  // Une réponse ultérieure sans commandes ne fait pas oublier celles déjà annoncées.
  rememberLauncherCommands(launcherCommandsFrom({ status: "alive" }));
  assert.equal(knownLauncherCommands(), linux);
});

test("no launcher command is written outside lib/launcher.ts", () => {
  const scripts = sourceFiles(/\.tsx?$/);
  assert.ok(scripts.length >= 25, `${scripts.length} scripts examinés`);
  const offenders = scripts.filter(file => file !== "lib/launcher.ts" && /rag\.ps1|rag\.sh|PowerShell/.test(stripScriptComments(readSource(file))));
  assert.deepEqual(offenders, []);
  // La lecture publique des commandes est lancée au chargement de l'atelier, avec la vérification de session.
  const check = stripScriptComments(readSource("lib/session-check.ts"));
  assert.match(check, /client\.health\(\)\.then\(reply => rememberLauncherCommands\(launcherCommandsFrom\(reply\)\)/);
  assert.ok(check.indexOf("client.health()") < check.indexOf("client.session()"), "/health part avant /session");
  assert.match(stripScriptComments(readSource("components/session-gate.tsx")), /checkSession\(api\)/);
});

// --- Installation par le kit Linux (R26-KIT-04, KIT4-13) ---------------------------------------------------------------
// Le service installé annonce `launcher.kind = "installation"` et les commandes du lanceur `atelier` de la destination,
// terminées par l'action française ; `--modele <tag>` suit ouvrir et diagnostic quand il sert un autre modèle.
const DESTINATION = "/home/atelier/.local/share/atelier-documentaire/programme";
const installedHealth = { status: "alive", service: "rag-api",
  commands: { open: `${DESTINATION}/atelier ouvrir`, status: `${DESTINATION}/atelier etat`, logs: `${DESTINATION}/atelier journaux`, doctor: `${DESTINATION}/atelier diagnostic` },
  launcher: { kind: "installation", menu: "Atelier documentaire" } };

test("an installation announces the atelier launcher; its French actions are read and English ones refused", () => {
  const installed = launcherCommandsFrom(installedHealth)!;
  assert.deepEqual(installed, { ...installedHealth.commands, installation: { menu: "Atelier documentaire" } });
  assert.equal(launcherText("doctor", installed), `${DESTINATION}/atelier diagnostic`);
  assert.equal(launcherShell(installed), "dans un terminal");
  assert.deepEqual(openCommandChoices(installed), [{ system: null, command: `${DESTINATION}/atelier ouvrir` }]);
  // Action anglaise, ou action d'une autre clé : refusées dans une installation.
  assert.equal(launcherCommandsFrom({ ...installedHealth, commands: { open: `${DESTINATION}/atelier open`, status: `${DESTINATION}/atelier ouvrir`, logs: "./rag.sh logs" } }), null);
  // Autre modèle que le principal : --modele après ouvrir et diagnostic seulement.
  const other = launcherCommandsFrom({ ...installedHealth, launcher: { kind: "installation", menu: null }, commands: {
    open: `${DESTINATION}/atelier ouvrir --modele qwen3.5:2b`, doctor: `${DESTINATION}/atelier diagnostic --modele qwen3.5:2b`,
    status: `${DESTINATION}/atelier etat --modele qwen3.5:2b` } })!;
  assert.deepEqual(other, { open: `${DESTINATION}/atelier ouvrir --modele qwen3.5:2b`, doctor: `${DESTINATION}/atelier diagnostic --modele qwen3.5:2b`,
    installation: { menu: null } });
  // Commande non annoncée : même lanceur, action française, sans modèle ; jamais rag.sh ni rag.ps1.
  assert.equal(launcherText("logs", other), `${DESTINATION}/atelier journaux`);
  assert.equal(launcherText("status", other), `${DESTINATION}/atelier etat`);
  assert.deepEqual(openCommandChoices(launcherCommandsFrom({ ...installedHealth, commands: { status: `${DESTINATION}/atelier etat` } })),
    [{ system: null, command: `${DESTINATION}/atelier ouvrir` }]);
  // Chemin cité entre apostrophes par le service (espace dans la destination) : gardé tel quel.
  const quoted = launcherCommandsFrom({ ...installedHealth, commands: { open: "'/home/atelier/Mes documents/atelier' ouvrir" } })!;
  assert.equal(launcherText("doctor", quoted), "'/home/atelier/Mes documents/atelier' diagnostic");
});

test("a clone or a Windows host keeps its commands whatever the launcher field says", () => {
  assert.deepEqual(launcherCommandsFrom({ ...linuxHealth, launcher: { kind: "projet", menu: null } }), linux);
  assert.deepEqual(launcherCommandsFrom({ ...windowsHealth, launcher: { kind: "projet", menu: null } }), windows);
  // Champ absent, inconnu ou mal formé : lu comme un projet ; une forme française n'y est pas reconnue.
  assert.deepEqual(launcherCommandsFrom({ ...linuxHealth, launcher: { kind: "autre" } }), linux);
  assert.deepEqual(launcherCommandsFrom({ ...linuxHealth, launcher: "installation" }), linux);
  assert.equal(launcherCommandsFrom({ commands: { open: `${DESTINATION}/atelier ouvrir` } }), null);
});

test("the menu name is kept only when it is a printable string", () => {
  for (const menu of [null, "", 42, "Atelier\ndocumentaire", " Atelier documentaire"]) {
    assert.deepEqual(launcherCommandsFrom({ ...installedHealth, launcher: { kind: "installation", menu } })!.installation, { menu: null }, JSON.stringify(menu));
  }
});

test("installation texts name the atelier launcher, a terminal and the menu, never rag.sh nor the project folder", () => {
  const installed = launcherCommandsFrom(installedHealth)!;
  const texts = [serviceUnreachableMessage(installed), httpFailureMessage(500, installed), errorMessage(undefined, installed),
    readinessSentence(["ollama_not_ready"], installed), sessionCloseTitle(installed),
    ...(["session_required", "session_expired", "session_closed", "link_invalid"] as SessionEndReason[]).map(reason => sessionScreen(reason, installed).body)];
  for (const text of texts) assert.doesNotMatch(text, /rag\.ps1|rag\.sh|PowerShell|dossier du projet/, text);
  assert.equal(serviceUnreachableMessage(installed), `Le service local ne répond pas. Vérifiez qu'il est démarré (${DESTINATION}/atelier etat), puis réessayez.`);
  assert.match(httpFailureMessage(500, installed), new RegExp(`la commande ${DESTINATION}/atelier journaux en donne l'emplacement\\.$`));
  assert.match(readinessSentence(["ollama_not_ready"], installed), new RegExp(`La commande ${DESTINATION}/atelier diagnostic détaille chaque contrôle`));
});
