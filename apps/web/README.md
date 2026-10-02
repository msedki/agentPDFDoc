# Poste documentaire web

Application Next.js exportée statiquement sur `/workspace/`, servie par l'API
native sur la même origine, sous Windows x86-64 ou Linux aarch64 et x86-64
([W018](../../RAG_Local_Agents/DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs)
et son complément du 01/10/2026). Les constats datés ci-dessous nomment le poste
où ils ont été faits : le poste Windows 11 x86-64 de qualification ou le poste
Linux aarch64 de développement ; aucun n'a été fait sur Linux x86-64. Ceux du
30/09/2026, antérieurs au clonage du dépôt sur le poste Linux (01/10/2026,
12:42 UTC), ont tous été faits sur le poste Windows de qualification.
Les originaux, bibliothèques, jobs, recherches et questions viennent uniquement
de `/api/v1`. Le build livré ne comporte aucune réponse simulée, fixture
embarquée, requête de fonte/CDN ou route serveur Next.

Le skill appliqué est [pdf-workspace-web](../../.agents/skills/pdf-workspace-web/SKILL.md),
avec frontend-design et les références React/general web security locales.
Les parcours réels suivent le skill `RAG_Local_Agents/skills/pdf-workspace-e2e`.

Versions résolues : Next 16.3.7, React 19.3.0, PDF.js 6.3.289, TanStack Query
5.104.0, Zustand 5.0.15, TypeScript 5.9.3 et Playwright 1.63.0. Les versions
exactes et dépendances sont dans `package.json` et `pnpm-lock.yaml`. Les états,
événements et champs partagés avec l'API sont comparés au contrat
`packages/contracts/contracts.json` par `tests/unit/contracts.test.ts`. pnpm est
fixé à 10.34.1 par le champ `packageManager` de `package.json`, avec l'empreinte
SHA-512 du paquet publiée par le [registre npm](https://registry.npmjs.org/pnpm/10.34.1)
(`dist.integrity`, convertie en hexadécimal). Node doit satisfaire `engines.node`
(22.13.0 au moins) ; par exemple, le poste Windows de qualification emploie
22.17.0 et le poste Linux aarch64 de développement 24.16.0, installé par nvm.
La commande `pnpm` dépend du système :

| Système | `pnpm` employé | Condition pour obtenir 10.34.1 |
|---|---|---|
| Windows | `pnpm.cmd` du PATH, celui que cherche `services/runtime/cli.py` (`pnpm_command`) ; `scripts/build-monitored.py` passe toujours par le `pnpm.js` du Corepack livré avec Node | `pnpm.cmd` en 10.34.1, ou, pour Corepack, la version 10.34.1 dans son cache (`%LOCALAPPDATA%\node\corepack` par défaut), le build se faisant sans réseau |
| Linux | Choix de `services/runtime/cli.py` (`pnpm_command`) : le `pnpm` du PATH s'il répond 10.34.1 à `pnpm --version` (lancé avec Corepack hors réseau) ; sinon `corepack pnpm` (Corepack du PATH) ; sans `corepack` dans le PATH, le `pnpm` du PATH quelle que soit sa version. `scripts/build-monitored.py` passe toujours par le `pnpm.js` du Corepack livré avec Node. Exemple local : sur le poste Linux aarch64 de développement, le `pnpm` du PATH est le shim de Corepack de Node 24.16.0 installé par nvm | `pnpm` du PATH en 10.34.1, ou, pour Corepack, la version 10.34.1 dans son cache (`~/.cache/node/corepack` par défaut) : Corepack la télécharge et vérifie son empreinte au premier appel avec réseau, alors que `rag.sh provision` et le build surveillé lancent Corepack hors réseau (`COREPACK_ENABLE_NETWORK=0`, voir ci-dessous). Sans `corepack` dans le PATH, le `pnpm` du PATH doit lui-même répondre 10.34.1 |

Seul Corepack est privé de réseau : `pnpm install --frozen-lockfile`, lancé par
`rag.ps1 provision` ou `rag.sh provision`, télécharge depuis le registre npm les
paquets absents du store de pnpm, sauf avec `rag.ps1 provision -Offline` ou
`rag.sh provision --offline`, qui lui passent `--offline`.

Sans réseau (`COREPACK_ENABLE_NETWORK=0`), Corepack refuse de lancer une version
absente de son cache (« Network access disabled by the environment; can't reach
https://registry.npmjs.org/pnpm/-/pnpm-10.34.1.tgz », constaté le 01/10/2026 sur
le poste Linux avec un cache vide). La [documentation de Corepack](https://github.com/nodejs/corepack) (section « corepack install »)
prévoit `corepack install`, qui télécharge et met en cache la version fixée par le
projet : exécutée une fois avec réseau depuis ce dossier, elle a ajouté 10.34.1 à
un cache vide en 8 s, après quoi `pnpm --version` hors ligne répond `10.34.1`
(poste Linux, Corepack 0.35.0, 01/10/2026). Node 22.17.0 livre Corepack 0.33.0,
dont la documentation décrit la même commande ; elle n'a pas été exécutée sur le
poste Windows.

Navigateurs Playwright : sur le poste Windows, le cache local contenait le
Chromium requis lors des recettes du 30/09/2026. Sur le poste Linux aarch64,
aucun navigateur Playwright n'est installé au 01/10/2026 (`~/.cache/ms-playwright`
ne contient qu'un lien vers un autre projet) ; `playwright install` n'y a pas été
exécuté et aucune recette E2E n'y a tourné.

Depuis ce dossier, sous un créneau de build accordé par le superviseur, sous
Windows, une fois les dépendances installées (`rag.ps1 provision` exécute
`pnpm install --frozen-lockfile`) ; si `pnpm` y est le shim Corepack,
`corepack install` doit avoir été exécuté une fois avec réseau (voir ci-dessus) :

```powershell
$env:NEXT_TELEMETRY_DISABLED='1'
$env:COREPACK_ENABLE_NETWORK='0'
$env:NODE_OPTIONS='--max-old-space-size=2048'
pnpm typecheck
pnpm test:unit
pnpm build
```

Sous Linux, depuis ce dossier :

```bash
export NEXT_TELEMETRY_DISABLED=1 COREPACK_ENABLE_DOWNLOAD_PROMPT=0
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test:unit
NODE_OPTIONS=--max-old-space-size=2048 nice -n 10 pnpm build
```

Exemple propre au poste Linux aarch64 de développement, et non étape du produit :
sa partition système n'ayant que quelques gigaoctets libres, le store pnpm y est
placé sur une carte microSD en ajoutant `--store-dir /media/safae/devsave1/agentPDFDoc-runtime/pnpm-store`
à `pnpm install` ; `node_modules` et `.next` restent dans ce dossier. Sans cette
option, pnpm emploie son store par défaut.

`scripts/build-monitored.py --tag <étiquette>`, lancé avec l'interpréteur du
projet (`.venv/Scripts/python.exe` sous Windows, `.venv/bin/python` sous Linux),
exécute le même build en relevant toutes les deux secondes la mémoire et le CPU
de l'hôte et de l'arbre de processus du build, puis écrit le journal, les relevés
et le manifeste SHA-256 de `out/` dans `reports/`. Node est choisi dans cet ordre :

1. l'exécutable désigné par la variable `RAG_WEB_NODE`, sur tout poste ; s'il
   n'existe pas, le script s'arrête au lieu de chercher ailleurs ;
2. sous Windows seulement, `D:/node/node-v22.17.0-win-x64/node.exe` s'il existe :
   repli historique propre au poste Windows de qualification, conservé pour que
   la commande qualifiée sur ce poste reste inchangée ; aucun autre poste n'a
   besoin de ce dossier ;
3. le `node` du PATH.

pnpm passe par le Corepack livré avec ce Node (`dist/pnpm.js`), sans réseau
(`COREPACK_ENABLE_NETWORK=0`). Avant d'écrire la moindre preuve, le script
vérifie que ce Corepack lance hors ligne la version de `packageManager` (10.34.1) ;
sinon il s'arrête, sans rien écrire dans `reports/`, en citant la sortie de
Corepack et la commande unique à exécuter une fois avec réseau, `corepack install`
du même Node depuis ce dossier :

```powershell
Set-Location -LiteralPath "<dépôt>\apps\web"; & "<dossier de node>\node.exe" "<dossier de node>\node_modules\corepack\dist\corepack.js" install
```

```bash
cd "<dépôt>/apps/web" && "<node>" "<préfixe de node>/lib/node_modules/corepack/dist/corepack.js" install
```

Corepack télécharge alors pnpm 10.34.1, vérifie son empreinte et le garde dans
son cache (`COREPACK_HOME`, par défaut `%LOCALAPPDATA%\node\corepack` sous
Windows et `~/.cache/node/corepack` sous Linux). Le résumé JSON final donne la
version de pnpm employée (`pnpm`) et celle de Node (`node_version`, sortie de
`node --version`), que le premier relevé de `reports/build-<étiquette>-resources.jsonl`
consigne aussi. Cette version est lue avant toute preuve, comme celle de pnpm
(même dossier, même environnement, délai de 120 s) ; si Node ne la donne pas, le
script s'arrête sans rien écrire dans `reports/`. Son message nomme la provenance
du Node retenu et l'action qui lui correspond : corriger ou retirer `RAG_WEB_NODE`
quand cette variable le désigne ; quand il vient du repli Windows du poste de
qualification, désigner un Node valide par `RAG_WEB_NODE`, prioritaire sur ce
repli ; quand il vient du PATH, désigner un Node par `RAG_WEB_NODE` ou corriger
le `node` du PATH. Les relevés antérieurs à cet ajout (30/09/2026
sur le poste Windows, 01/10/2026 sur le poste Linux) ne la contiennent pas ; elle
n'y est pas reconstituée. L'arrêt sur cache vide, sans fichier écrit
dans `reports/`, et la commande affichée ont été constatés le 01/10/2026 sur le
poste Linux aarch64 en lançant le script avec un `COREPACK_HOME` vide. Rien n'a
été exécuté sur le poste Windows : la présence de 10.34.1 dans le cache de
Corepack y reste à vérifier avant le prochain build surveillé.

`pnpm dev` lance le serveur de développement Next (Turbopack) sur
`127.0.0.1:3000`. Aucune réécriture ni proxy vers l'API n'est configuré
(`next.config.mjs`) : les appels relatifs à `/api/v1` aboutissent au serveur de
développement, qui répond 404, et l'atelier s'arrête sur l'écran « Service local
injoignable » (« Le service local a refusé la demande (HTTP 404). », constaté le
01/10/2026 sur le poste Linux). Ce mode ne sert qu'à examiner une mise en page ; tout
parcours passe par l'export servi par l'API. Effets de bord constatés : `next dev`
réécrit `next-env.d.ts` vers `.next/dev/types` (le build le rétablit) et, lancé
depuis un agent de code, crée `AGENTS.md` et `CLAUDE.md` dans ce dossier
(`node_modules/next/dist/server/lib/generate-agent-files.js`) ; ces fichiers ne
sont pas des sources du projet.

Les textes qui citent le lanceur (écran de session, info-bulle « Fermer la
session », service injoignable, échec HTTP 5xx, échec sans message, avis de
préparation) emploient les commandes que le poste annonce dans la réponse publique
de `GET /api/v1/health` (`commands.open`, `status`, `logs` et `doctor`), lue au
chargement de l'atelier, y compris sur l'écran « Lien d'ouverture expiré », et
gardée en mémoire : `.\rag.ps1 open` sous Windows, `./rag.sh open` sous Linux
(`src/lib/launcher.ts`, `tests/unit/launcher.test.ts`). Une commande annoncée est
citée telle quelle. Une commande absente de la réponse prend le lanceur livré
qu'emploient toutes les commandes annoncées : la plateforme est alors connue, et
un service qui n'annoncerait pas encore `doctor` fait tout de même afficher
`.\rag.ps1 doctor` sous Windows. Tant que la plateforme est inconnue (`/health`
sans réponse ou en échec, lanceurs mêlés, autre chemin), le texte donne les deux
formes ; l'écran de session affiche une ligne par système et parle de « la commande
de votre système ». La plateforme du navigateur ne sert pas à choisir :
`navigator.platform` est documenté comme peu fiable et `navigator.userAgentData`
est expérimental et absent de plusieurs navigateurs (MDN).

Sous Windows, dès que la plateforme est connue, chaque texte est identique mot
pour mot à celui d'avant W018 : `tests/unit/windows-texts.test.ts` les compare
aux sources du commit 26fa7a5 lues par `git show` (ignoré, avec son motif, sans
git ou sans ce commit). Un échec n'est jamais gardé sous forme de texte : chaque
composant garde l'erreur et calcule son texte au rendu avec les commandes connues
à cet instant (`src/components/ui/error-text.tsx`, `tests/unit/error-text.test.ts`),
si bien qu'une réponse de `/health` arrivée après l'échec remplace les deux formes
par la commande du poste. La vérification de session attend la réponse de
`/health` au plus 1 s (`src/lib/session-check.ts`,
`tests/unit/session-check.test.ts`) ; tant qu'aucune commande n'est connue,
l'atelier relit `/health` après des attentes de 2, 5, 15, 30 puis 60 secondes,
chacune comptée depuis la réponse précédente, une lecture à la fois, et s'arrête
dès qu'il les connaît ou après la cinquième ; « Vérifier de nouveau » relance la
série.

Le build vide `public/pdfjs/`, y copie worker, cmaps, wasm, fontes standard et
profils ICC de la version locale PDF.js, avec un manifeste de SHA (aucun fichier
d'une copie précédente n'est exporté ni inventorié), puis exporte vers `out/`.
Seules les règles TextLayer de PDF.js sont chargées, depuis
`src/app/pdf-text-layer.css`, copie cantonnée à `.pdf-paper` et comparée à la
version installée par `tests/unit/pdf-styles.test.ts` : la feuille complète
`web/pdf_viewer.css` n'est plus importée, car elle imposait `color-scheme: light dark`
à `:root` et ajoutait au build 32 icônes et les styles du visualiseur et de
l'éditeur PDF.js (163 832 octets en source dans pdfjs-dist 6.3.289), inutilisés
ici. Le premier build du poste Linux aarch64 de développement, le 01/10/2026
([manifeste](reports/export-manifest-2026-10-01-linux-aarch64.json)), exporte
243 fichiers pour 6 514 529 octets, dont une feuille CSS de 44 642 octets. Next utilise
un seul worker. Ne pas lancer de build en concurrence avec OCR/LLM lourd sur un
poste de 16 Go.

Les trois panneaux partagent un scope explicite gelé par requête. Lire un PDF,
tourner une page ou ouvrir une citation ne change pas ce scope. Les recherches
affichent le périmètre employé même après changement du périmètre actif. Les
conversations/focus de source sont réinitialisés au changement de scope.
L'original importé reste consultable avant publication, avec un état d'attente
explicite. Ses passages annotés et l'analyse de page s'activent uniquement pour
une extraction publiée ; une nouvelle version n'hérite pas de la publication
de la précédente. Le suivi de disponibilité conserve les blockers réels d'un
HTTP 503 de préparation.

Le lecteur borne à cinq canvases haute résolution et 24 millions de pixels
allocables au total. Il libère les canvases/text layers remplacés et charge les
blocs au voisinage du viewport. PDF.js lit les boîtes réelles du fichier ; les
bboxes de provenance sont en points PDF absolus non tournés, bas-gauche, CropBox
déjà conservée par l'ingestion. Aucun offset supplémentaire n'est ajouté.

Les overlays OCR requièrent `metadata.extraction_method='ocr'` ou des `ocr_spans`
exacts sur un bloc mixte, avec géométrie fiable. Un routage global OCR ne suffit
pas. La sélection envoie révision, hash et offsets Unicode du `raw_text` exact.
Ligature/césure ambiguë ou hash/révision manquante produit une limite visible et
les actions page/bloc disponibles.

Le suivi appelle les vraies routes pause/reprise, priorité questions/imports et
publication partielle. La publication partielle nécessite l'action explicite
« Utiliser cette extraction partielle ». La couverture et les limites restent
visibles.

« Réindexer ce document » suit la réponse du service, décrite pour chaque état du
dernier traitement par `reindex_outcomes` dans le contrat (`src/lib/reindex.ts`,
`tests/unit/reindex.test.ts`) :

| Dernier traitement | Réponse du service | Affiché sous le bouton |
|---|---|---|
| `queued`, `extracting`, `indexing` | 202, traitement en cours renvoyé (`reused`) | « Un traitement de ce document est déjà en cours : aucune nouvelle réindexation n'a été lancée. Sa progression s'affiche dans le Suivi. » |
| `paused` | 202, ce traitement renvoyé avec `resume_required` | avis de pause et bouton « Reprendre le traitement », qui appelle `POST /jobs/{job_id}/resume` |
| `pausing` | 409 `job_pausing`, aucun traitement créé | message du service, tel quel : « Mise en pause en cours pour ce document : attendez qu'elle aboutisse, puis reprenez ce traitement depuis le Suivi. » |
| `cancelling`, `cancelled`, `error`, `ready`, `ready_partial` | 202, traitement neuf mis en file ; pendant `cancelling`, l'annulation reste définitive et le nouveau traitement démarre après elle | « Réindexation demandée : sa progression s'affiche dans le Suivi. » |

Le bouton n'est actif que pour un document `ready`, `ready_partial` ou `error`
(comportement antérieur inchangé). Un `resume_required` avec un autre état que
`paused`, que ce service ne renvoie pas, renvoie au Suivi sans proposer de reprise.

À l'import, un fichier identique (même contenu) déjà importé au même chemin
reçoit l'issue que le contrat décrit pour le dernier traitement de cette version
(`import_outcomes`, `Database.import_original` dans `services/api/db.py`). L'avis
de la bibliothèque suit la réponse (`src/lib/import-outcome.ts`,
`tests/unit/import-outcome.test.ts`) ; les textes ci-dessous sont ceux d'un seul
fichier reçu, un import de plusieurs fichiers comptant chaque cas :

| Dernier traitement | Réponse du service | Avis de la bibliothèque |
|---|---|---|
| `queued`, `extracting`, `indexing`, `ready`, `ready_partial` | 202, ce traitement renvoyé (`reused: true`), aucun traitement créé | « Ce fichier était déjà importé à l'identique : l'import ne lance aucun nouveau traitement. Son état s'affiche dans la bibliothèque ; pour le traiter de nouveau, ouvrez-le puis choisissez « Réindexer ce document ». » (le service ne dit pas si ce traitement est terminé) |
| `paused` | 202, ce traitement renvoyé avec `job_state: "paused"` et `resume_required: true` | « Ce fichier était déjà importé à l'identique et son traitement est en pause : l'import n'en lance pas un second. Reprenez-le pour poursuivre son indexation depuis son dernier point de reprise. » et bouton « Reprendre le traitement », qui appelle `POST /jobs/{job_id}/resume` |
| `pausing` | 202, ce traitement renvoyé avec `job_state: "pausing"`, sans `resume_required` ni traitement créé : `POST /jobs/{job_id}/resume` le refuserait (409 `job_not_resumable`) | « Ce fichier était déjà importé à l'identique et son traitement est en cours de mise en pause : l'import n'en lance pas un second. Une fois la pause effective, reprenez-le depuis le Suivi. », sans bouton |
| `cancelling`, `cancelled`, `error` | 202, traitement neuf mis en file sur la même version (`reused: false`) ; pendant `cancelling`, l'annulation reste définitive et le nouveau traitement démarre après elle | avis ordinaire de l'import |

Contrairement à la réindexation, l'import ne refuse pas `pausing` : il traite
jusqu'à cinquante fichiers par requête et renvoie l'état pour que les autres
fichiers soient importés. La reprise n'est proposée que pour un `job_state`
`paused` accompagné de `resume_required: true` ; un autre `job_state`, que ce
service ne renvoie pas, renvoie au Suivi sans proposer de reprise.

Le SSE reprend le query ID et dernier event ID sans nouvelle génération ; seules
les références enregistrées deviennent des citations cliquables.

Une citation enregistrée charge les blocs et le sommaire de sa révision exacte,
avec un cache séparé. Le lien `citation_query`/`citation_source` relit le registre
réel avant ouverture ; une identité invalide ou supprimée reste une erreur.
« Retour » conserve aussi cette source. Pour une révision réellement archivée,
les actions page/section sont désactivées avec une explication, car leur contrat
ne fixe pas la révision ; la sélection et le bloc exact restent utilisables.
Une citation de la révision publiée courante conserve les actions ordinaires.
Le correctif D03 est implémenté et vérifié en tests unitaires ; son parcours
navigateur avec ancien registre reste NOT_RUN avant la recette isolée.

État des preuves au 30/09/2026 UTC : premier build statique réellement terminé
exit 0, [log](reports/build-2026-09-30.log) et
[manifeste export](reports/export-manifest-2026-09-30.json), avec mesures mémoire
ponctuelles [avant/pendant/après](reports/build-resources-2026-09-30.jsonl).
Ces snapshots ne constituent pas une mesure de pic ni un test d'usage de 30 min.
Les corrections TypeScript initiales et la reprise sont conservées séparément.

Le build V2.1 est terminé exit 0 : [sortie](reports/build-2026-09-30-v21.log).
Une reprise corrige l'ouverture avant publication et l'affichage readiness :
[build](reports/build-2026-09-30-original-publication.log),
[277 fichiers exportés](reports/export-manifest-2026-09-30-original-publication.json)
et [ressources](reports/build-2026-09-30-original-publication-resources.jsonl).
Le build ciblé précédent ajoute styles TextLayer PDF.js 6, gestion immédiate des
promesses annulables et distinction hits search/citations :
[build](reports/build-2026-09-30-rendercancel.log),
[278 fichiers exportés](reports/export-manifest-2026-09-30-rendercancel.json).
17 tests unitaires ont passé : [sortie](reports/unit-2026-09-30-rendercancel.log).
Ces tests couvrent Unicode, réconciliation, provenance OCR et limites raster ;
ils ne valident aucune extraction OCR réelle.

Le correctif de révision exacte porte la suite à 27 tests PASS :
[sortie](reports/unit-2026-09-30-navigation-provenance-corrected.log),
[typecheck](reports/typecheck-2026-09-30-navigation-provenance-corrected.log).
Les deux échecs initiaux du retour sont conservés dans
[leur log](reports/unit-2026-09-30-navigation-provenance-initial-fail.log),
et le défaut initial de chargement par version dans
[la preuve statique](reports/old-revision-2026-09-30-initial-static.json).
Le build final D03 termine exit 0 en 98,94 s :
[sortie](reports/build-2026-09-30-pinned-revision-return.log),
[278 fichiers / 6 673 451 octets](reports/export-manifest-2026-09-30-pinned-revision-return.json),
[48 relevés hôte/arbre du build](reports/build-2026-09-30-pinned-revision-return-resources.jsonl).
La RAM disponible minimale échantillonnée est de 5 228,7 Mio ; les relevés
ne prouvent aucun pic continu ni performance du parcours navigateur.

Les tests Playwright vérifient séparément la coquille/API, import→lecture→recherche
→source, puis la réponse du vrai modèle→citation. L'import n'est exécuté que
sur stockage isolé autorisé (`RAG_E2E_IMPORT_ALLOWED=1`). Une réponse LLM manquante
ne transforme pas un succès de navigation en réussite de la chaîne question.
La première exécution réelle conserve une coquille/API PASS à 1366×768 et
1920×1080, puis l'échec d'ouverture de l'original et la dépendance de sélection :
[sortie initiale](reports/e2e-2026-09-30-native-dev-first.log),
traces et captures conservées hors Git sur le poste Windows (`test-results/2026-09-30-native-dev-first/`).
Le job importé a d'abord été mis en pause par le contrôle mémoire, puis repris
explicitement via UI et publié avec 2/2 pages. La reprise garde un échec de
locator ambigu (bouton du périmètre au lieu de celui de l'arborescence) ; son
timeout de 180 s ne mesure pas seul la latence d'indexation. La sélection
réelle page/bloc a passé : [sortie](reports/e2e-2026-09-30-native-dev-reprise.log).
Le parcours source suivant a exercé recherche, rotation 90°, ancre native et
retour, puis échoué sur une RenderingCancelledException non gérée :
[sortie/trace conservées](reports/e2e-2026-09-30-native-dev-source.log).
La cause est corrigée dans le build courant. Une reprise conserve un échec de
locator de warning devenu multiple, puis le parcours recherche→source a passé
en 11,4 s : [sortie](reports/e2e-2026-09-30-native-dev-source-final.log),
traces et captures conservées hors Git sur le poste Windows (`test-results/2026-09-30-native-dev-source-final/`).
Le nom et la page proviennent de l'API ; rotation 90°/zoom 125 %, ancre native
dans la bbox réelle, retour page 2 et warnings structurés sont exercés, sans
erreur de page ni requête externe. Ce cas ne prouve pas les 95 % d'ancres ni
le scénario mixte complet.

La première question réelle a échoué avant génération : POST 202 puis SSE
`resource_admission_denied`, 5 095 Mio disponibles pour 5 888 requis, avec
`model_called=false`. Huit sources réelles ont été reçues, aucun delta ni texte
de réponse : [sortie](reports/e2e-2026-09-30-qwen-question-first.log),
[preuves décodées](reports/e2e-2026-09-30-qwen-question-first-evidence.json),
traces et captures conservées hors Git sur le poste Windows (`test-results/2026-09-30-qwen-question-first/`).
La durée de recette 43,9 s inclut l'assertion de réponse après le refus ; elle
ne mesure aucun TTFT. Le test termine désormais immédiatement sur un statut
terminal d'échec, tout en conservant le SSE. La chaîne question→réponse du
modèle→citation reste non validée ; aucune relance automatique ni substitution
n'a été effectuée.

Une deuxième question explicitement autorisée échoue aussi avant génération :
`resource_admission_denied`, 5 222 Mio disponibles pour 5 888 requis, malgré
les libérations ORT/E5/Qwen réellement mesurées. Aucun premier texte ni appel
modèle n'est observé ; la recette termine immédiatement en 17,9 s :
[sortie](reports/e2e-2026-09-30-qwen-question-second.log),
[SSE exact](reports/e2e-2026-09-30-qwen-question-second-events.sse),
[cache/RAM/CPU et navigateur propres](reports/e2e-2026-09-30-qwen-question-second-evidence.json),
traces et captures conservées hors Git sur le poste Windows (`test-results/2026-09-30-qwen-question-second/`).
Cette API expose maintenant des compteurs d'inférence d'embedding limités au
processus courant ; ce seul essai ne qualifie pas les cycles réimport/réindex.

```powershell
$env:RAG_E2E_BASE_URL='http://127.0.0.1:8785'
$env:RAG_E2E_IMPORT_ALLOWED='1'
$env:RAG_E2E_GENERATION_ALLOWED='0'
$env:RAG_E2E_OUTPUT_DIR='test-results/<nouvelle-execution>'
pnpm exec playwright test --grep 'three panels|real import|immutable block'
```

Le superviseur confirme d'abord que cette cible correspond aux services/données
isolés prévus. Depuis le 01/10,
`tools/qualification/e2e_instance.py start --state <etat.json>` fournit cette cible : instance neuve dans une racine et des ports temporaires, dont
l'état donne l'origine (`RAG_E2E_BASE_URL`) et le fichier de jeton
(`RAG_E2E_CONTROL_TOKEN_FILE`) ; `stop` l'arrête et supprime sa racine. Les scénarios
de géométrie, de balisage hostile, de canvas, d'import et de sélection y sont passés
le 01/10 ([géométrie](reports/e2e-2026-10-01-import-isole-geometrie-evidence.json),
[parcours](reports/e2e-2026-10-01-import-isole-parcours-evidence.json)), ainsi que la sélection Unicode de
`unicode-selection.spec.ts` (hors BMP, accent combinant, ligature, césure, sélection ambiguë refusée ;
[rapport](reports/e2e-2026-10-01-unicode-selection-evidence.json)). Ces exécutions ont
toutes eu lieu sur le poste Windows de qualification, avec `.venv\Scripts\python.exe`
et les mécanismes de `rag.ps1 selftest`. L'en-tête de `e2e_instance.py` documente
aussi une commande Linux, sur les mécanismes de `rag.sh selftest`, mais sous Linux
ni l'outil ni la recette E2E n'ont été exécutés : leur prise en charge reste à établir.
Une reprise fournit `RAG_E2E_REUSE_DOCUMENT_ID` et vérifie le SHA
de la même fixture DEV, sans nouvel import. La question réelle exige un créneau
distinct et `RAG_E2E_GENERATION_ALLOWED=1`. La sonde mémoire (`tests/e2e/resources.ts`,
plateforme résolue par `tests/e2e/host.ts`) utilise la venv du projet et psutil :
PID propre du worker Node, vérifié par son nom `node.exe` sous Windows et, sous
Linux, par son exécutable (`/proc/<pid>/exe` égal à `process.execPath`, Node 24
nommant son thread principal « MainThread »), descendants Chromium récursifs,
valeurs séparées par processus. Sous Windows :
RSS, private Windows (mémoire privée engagée) et USS. Sous Linux, où psutil
n'expose pas de mémoire privée Windows : RSS lu dans `/proc/<pid>/statm` et USS
calculé sur `/proc/<pid>/smaps` ; chaque relevé nomme sa méthode (champ `method`).
Elle ne lit aucun autre navigateur et ferme uniquement ce navigateur de test
si la RAM disponible passe sous 1,5 GiB. Les anciens snapshots ne disposaient
pas de private/USS ; ces valeurs ne sont pas reconstituées après coup. Le test
`resource-probe.spec.ts`, activé par `RAG_E2E_RESOURCE_PROBE_ALLOWED=1`, prépare
le formulaire et rend un PDF par GET sans soumettre de question ni changer le
mode runtime. Une exécution distincte ne remplace pas les mesures historiques.
Les résultats, traces complètes et captures sont conservés dans
`test-results/` ; aucun résultat E2E n'est déduit d'un build ou d'un healthcheck.

Lot R4 (30/09/2026, sources modifiées, build non relancé) : une précision `page`
ne dessine plus aucune boîte de région et le lecteur reprend le libellé des
cartes source ; une région déclarée sans géométrie valide s'affiche comme
localisation à la page (`src/lib/source-location.ts`). Les réponses reconnaissent
aussi les listes `[S001, S002]`, chaque ID étant validé individuellement
(`src/lib/citations.ts`) ; aucune balise HTML n'est interprétée, seuls les
paragraphes, listes à puces et passages en gras `**…**` sont mis en forme, par des
éléments React (`src/lib/answer-format.ts`, depuis `0c7fd84`). Les onglets d'analyse
suivent le motif tablist (flèches, Home/End, tabIndex itinérant, `tabpanel`) ;
la plage de pages est validée contre le nombre de pages de la version ouverte,
pas de la version active. Le gris secondaire (jeton `--muted-foreground` de
`src/app/theme.css` depuis R16) sert aussi aux
placeholders, qui remplacent le gris semi-transparent du preflight Tailwind
(environ 3,1:1) ; l'icône de périmètre de dossier perd son opacité réduite
(2,5:1). `tests/unit/accessibility.test.ts` calcule depuis `theme.css` et
`globals.css` les paires texte/fond et placeholder/champ (au moins 4,5:1) et
cette icône (au moins 3:1). Les tests unitaires prouvent les fonctions pures (`src/lib/`) et les
règles CSS ; leur câblage dans les composants (attributs `tabpanel`/`aria-*`,
tabIndex itinérant, appels de `versionPageCount` et `sourceRegionBoxes`) n'est
vérifié que par typecheck et relecture, en attente des specs E2E et du rendu
navigateur après build.

Nouveaux specs Playwright écrits, NOT_RUN : `a11y.spec.ts` et
`negative-deeplink.spec.ts` (GET seul, `RAG_E2E_READONLY_ALLOWED=1`, écritures
API bloquées dans le navigateur ; Ctrl+Entrée y est vérifié sur une recherche
interceptée, donc en test UI isolé), `geometry.spec.ts` (rotations 0/90/180/270,
CropBox et folios), `hostile-markup.spec.ts` et `canvas-budget.spec.ts` (import
sous `RAG_E2E_IMPORT_ALLOWED=1`, recherche sans génération). Les deux derniers
lisent `hostile/markup-injection.pdf` et `layouts/long-document-14p.pdf` via
leur sidecar généré (hors manifeste, SHA-256 et taille vérifiés) et sont
ignorés si la fixture est absente. Le compte de cinq canvases exclut seulement
le canvas caché de mesure que le TextLayer de pdf.js attache à `body` jusqu'à la
destruction du document ; ses pixels restent dans le budget de 24 M.

Les cycles versions anciennes, ETag/ranges, réimport, réindex, nouvelle version
et fichiers refusés sont préparés dans
[la recette lifecycle](tests/e2e/LIFECYCLE_RECETTE.md). Ils restent NOT_RUN et
requièrent des bindings réels, une cible isolée vérifiée et un permis par cas.
Ils ne soumettent aucune question au modèle. Les métriques disponibles ne
permettent pas encore de certifier zéro calcul d'embedding redondant.

## Charte, composants et gardes (lot R16, étape A)

État au 30/09/2026 UTC : sources modifiées, tests unitaires et typecheck PASS ;
build, E2E et examen du rendu non relancés par cette étape. Les principes
viennent de la [référence de forme](../../RAG_Local_Agents/reports/ui-reference-decodair-2026-09-30.md).

| Élément | Emplacement | Contrôle |
|---|---|---|
| Jetons de couleur en triplets HSL sur `:root`, exposés à Tailwind par `@theme inline` ; rayon de base 6 px et ses deux pas ; trois niveaux d'ombre ; piles de polices système (aucune police distante) ; thème clair seul (`color-scheme: light`) | `src/app/theme.css`, seul fichier autorisé à porter des couleurs ; les surlignages PDF y forment une liste blanche commentée | `tests/unit/ui-guards.test.ts`, `tests/unit/accessibility.test.ts` |
| Échelle de texte 10 (sur-titres en capitales) / 11 / 12 / 14 / 16 / 18 px, espacements multiples de 4 px, mono pour `source_id`, empreintes, versions et révisions, chiffres tabulaires pour pages, zoom et compteurs, `prefers-reduced-motion` étendu aux transitions | `src/app/globals.css` | `ui-guards.test.ts` |
| Libellés et tons des états de document, de traitement (état et étape), de réponse et des services ; un code inconnu reçoit un libellé et reste en info-bulle | `src/lib/status.ts` | `tests/unit/status.test.ts` |
| États de panneau : service local indisponible, chargement, bibliothèque vide, filtre sans résultat, index incomplet du périmètre d'une recherche | `src/lib/panel-state.ts`, `src/components/ui/panel.tsx` | `tests/unit/panel-state.test.ts` |
| `Badge` (variantes `cva` par ton), `StatusIndicator` (pastille toujours suivie de son libellé), `ActionButton` (libellé d'attente, erreur `role="alert"` sous l'action), `ConfirmDialog` (`<dialog>` natif ; remplace `window.confirm` du retrait de document et garde l'erreur dans le dialogue ; si le navigateur le ferme de lui-même pendant le retrait, Échap répété sans nouvelle activation, l'état React suit et un échec ultérieur rouvre le dialogue), `Button` (icônes 16 px, anneau sur `--ring`) | `src/components/ui/` | gardes, `shell.test.ts` et typecheck ; fermeture forcée : au rendu |
| Carte de source : `source_id`, document, page, badge de précision (famille exacte, localisation à la page, source non localisée), extrait de trois lignes, action unique « Ouvrir le passage » ; dans le lecteur, bordure pour la source citée et fond pour la recherche locale | `SourceCard` (`analysis-panel.tsx`), `sourceLocalization` (`src/lib/source-location.ts`), `globals.css` | `tests/unit/source-location.test.ts` |

Les gardes de `ui-guards.test.ts` lisent `src/` : taille de texte, espacement,
boutons-icônes nommés, champs libellés, couleurs hors jetons et palette Tailwind
brute, absence de variante `dark:`, contraste AA des badges et des boutons au
repos et au survol, pastilles d'état, tailles d'icônes, échec de requête jamais
rendu comme un vide, absence de `confirm`/`alert`. Chacune vérifie d'abord la
taille de la population examinée. Une contre-épreuve, avec violations injectées
temporairement puis fichiers restaurés à l'identique, a fait échouer chacune
des onze gardes visées.

Deux effets restent à vérifier au rendu après build : les réinitialisations
d'éléments passent en `@layer base`, si bien que les tailles `text-xs` et
`text-sm` du composant `Button` s'appliquent désormais (elles étaient écrasées
par `font: inherit` hors couche) ; l'en-tête passe de 66 à 56 px. Les specs E2E
qui cliquaient la carte de source visent désormais son bouton « Ouvrir le
passage » (`geometry`, `hostile-markup`, `workspace`) et l'état vide du lecteur
s'intitule « Aucun document ouvert » (`negative-deeplink`) ; ces specs restent
à rejouer.

## Coquille, navigation et textes (lot R16, étape B ; lot R15)

État au 30/09/2026 UTC : sources modifiées, puis corrigées après une relecture
indépendante (placement de la grille, fermeture forcée du dialogue de
confirmation, textes) ; tests unitaires (116) et typecheck PASS ; build, E2E et
examen du rendu non relancés par cette étape. La colonne
« Contrôle » distingue ce qu'un test unitaire prouve de ce qui reste à vérifier
dans le navigateur.

| Élément | Emplacement | Contrôle |
|---|---|---|
| Barre supérieure de 56 px en trois zones : bascule de la bibliothèque et marque (SVG au trait, « Atelier documentaire ») ; périmètre au centre ; état des services, Suivi, Aide, bascule de l'analyse | `src/components/app-topbar.tsx`, `scope-control.tsx` | Structure : `tests/unit/shell.test.ts` ; disposition : au rendu |
| État des services en quatre états écrits : service local injoignable (ou en erreur s'il répond mal), modèle ou worker non prêt, index en retard, services prêts ; détail en info-bulle | `serviceStatus` (`src/lib/status.ts`), `pendingIndexCount` (`panel-state.ts`), `serviceDetail` (`warnings.ts`) | `status.test.ts`, `panel-state.test.ts`, `warnings.test.ts` |
| Suivi : compteur des traitements non terminés (en cours, en pause, mis en point de reprise, interrompus ou en extraction partielle), dits « à suivre » et non « actifs » ; plafonné à « 99+ », changement annoncé par une région `aria-live="polite"`, échec de lecture dit dans le nom accessible | `app-topbar.tsx`, `activeJobsBadge`, `activeJobsSentence` | `panel-state.test.ts`, `shell.test.ts` ; annonce : lecteur d'écran à vérifier |
| Bandeau de contexte : puce de périmètre, documents interrogeables et exclus par motif (traitement, pause, erreur, état inconnu), un seul emplacement de message (erreur de l'espace de travail, sinon avis de préparation, sinon avis de repli du GPU sur le processeur) ; sous 768 px, l'état des services quitte la barre supérieure pour ce bandeau. À droite, le matériel de la génération (toujours sous 768 px ; au-delà, dès que l'arborescence est lue, ou reconnue illisible, ou qu'un message est affiché), lu dans `generation` de `GET /jobs` (W025, ajout du 02/10/2026) : « Réponses calculées sur le GPU » (modèle vu entièrement sur le GPU), « Génération prévue sur le GPU » (modèle pas encore vu chargé, ou répartition inconnue), « Réponses calculées en partie sur le processeur » et « GPU retenu, réponses calculées sur le processeur » (avertissement), « Réponses calculées sur le processeur », ou, après un repli, « GPU en échec : réponses calculées sur le processeur » (avertissement) ; libellé dans une région `role="status"`, explication ouverte par le bouton « Explication du matériel de génération », fermée par Échap ou un clic extérieur ; rien si le champ manque, est mal formé ou si la dernière lecture du suivi a échoué | `src/components/context-band.tsx` (`GenerationIndicator`), `scopeCoverage`, `coverageSentence`, `readinessSentence`, `readGeneration` et `generationView` (`src/lib/generation.ts`) | `panel-state.test.ts`, `warnings.test.ts`, `shell.test.ts`, `generation.test.ts`, `contracts.test.ts`, `accessibility.test.ts` ; indicateur : tests unitaires (217/217) et typecheck PASS le 02/10/2026 sur le poste Linux aarch64, build, E2E et rendu non relancés, état de repli jamais affiché sur une instance réelle |
| Bibliothèque en trois états (étendue et redimensionnable, rail de 64 px avec Importer, Filtrer et Sélection (n), masquée) ; bouton cyclique dont le libellé annonce l'action suivante ; Ctrl+B ou ⌘+B, ignoré dans la zone de question ; analyse en deux états | `workspace.tsx`, `LibraryRail` (`library-panel.tsx`), `src/lib/panel-preferences.ts` | `panel-preferences.test.ts` (cycle, libellés, raccourci) ; effet clavier et rail : au rendu |
| Grille des panneaux à cinq pistes fixes (bibliothèque, séparateur, lecteur, séparateur, analyse), chaque enfant placé sur la sienne : un enfant `[hidden]`, que le preflight Tailwind retire de la grille (`display: none !important`), ne décale plus le lecteur dans une piste de 0 px en mode rail, bibliothèque masquée ou sous 1 024 px | `panelGridColumns` (`panel-preferences.ts`), `workspace.tsx`, `src/app/globals.css` | `panel-preferences.test.ts` (cinq pistes, lecteur sur la troisième), `shell.test.ts` (piste explicite de chaque enfant) ; largeur réelle du lecteur : au rendu, dans chaque mode |
| Préférences locales `rag-local-panels-v2`, lecture champ par champ, migration de `rag-local-panels-v1` (la clé v1 n'est ni modifiée ni effacée) | `panel-preferences.ts`, `src/lib/panel-storage.ts` | `panel-preferences.test.ts` |
| Sous 1 024 px (`lg` de Tailwind) : bibliothèque et analyse en panneaux latéraux `<dialog>` modaux ouverts depuis la barre, avec Échap, fond inerte, retour du focus et bouton « Fermer » ; le Suivi devient un panneau latéral droit à toutes les largeurs. Chaque panneau est rendu une seule fois par portail et déplacé sans démontage : historique des questions, flux en cours et filtre survivent au franchissement de 1 024 px | `src/components/ui/sheet.tsx`, `workspace.tsx`, `jobs-panel.tsx` | `shell.test.ts` (structure) ; focus, Échap et conservation d'état : au rendu |
| Points de rupture Tailwind (80, 64, 48 et 40 rem) à la place des seuils codés 1 100 et 760 px ; cibles de 44 px sous 1 024 px dans la barre et les en-têtes | `src/app/globals.css` | `shell.test.ts` ; rendu aux six largeurs de QA à faire |
| Liens d'évitement « Aller au lecteur » et « Aller à la zone de question » (hors de `.workspace-shell`) ; zones `aside` Bibliothèque, `main` Lecteur, `aside` Analyse ; anneau de focus sur `--ring`, y compris sur le lecteur atteint par le lien | `workspace.tsx`, `library-panel.tsx`, `analysis-panel.tsx` | `shell.test.ts`, `accessibility.test.ts` |
| Menu Aide : raccourcis en `<kbd>`, chacun relié à son câblage dans le code ; signature « version {package.json} · révision non tracée », la révision n'étant lue que si `NEXT_PUBLIC_BUILD_REVISION` est injectée au build (aucun script ne le fait aujourd'hui) | `src/components/help-menu.tsx`, `src/lib/build-info.ts` | `shell.test.ts` (raccourci annoncé = raccourci câblé), `build-info.test.ts` |
| Textes : inventaire complet, réécritures et motifs ; vocabulaire document, version, page, bloc, périmètre, source, extraction, indexation ; aucun code brut affiché seul | [`reports/ui-text-inventory-2026-09-30.md`](reports/ui-text-inventory-2026-09-30.md) | `warnings.test.ts`, `status.test.ts` ; relecture au rendu |

Une contre-épreuve a injecté sept violations (raccourci inventé dans l'Aide,
seuil codé en pixels, compteur non annoncé, lien d'évitement retiré, second
emplacement de message, focus non restitué, zone d'analyse non nommée) : chacune
a fait échouer sa garde de `shell.test.ts`, puis les fichiers ont été restaurés
à l'identique (SHA-256 comparé).

Specs E2E alignés, à rejouer : le bouton d'import s'appelle « Importer des PDF »
(`workspace.spec.ts`, `lifecycle-target.ts`) ; l'ordre de tabulation attendu par
`a11y.spec.ts` suit la nouvelle barre (liens d'évitement, bascule de la
bibliothèque, périmètre, Suivi, Aide, bascule de l'analyse, puis les panneaux).
Restent à vérifier au rendu : la barre et le bandeau aux six largeurs de QA,
la largeur du lecteur en mode rail, bibliothèque masquée, analyse masquée et
sous 1 024 px (aucun E2E ne replie la bibliothèque ni ne descend sous 1 366 px),
les panneaux latéraux (centrage, fond, retour du focus, Échap), le rail, le
raccourci Ctrl+B sous Firefox (qui l'associe par défaut au panneau des
marque-pages), l'annonce du compteur par un lecteur d'écran et l'apparition des
panneaux après hydratation, puisqu'ils sont rendus par portail côté navigateur.
