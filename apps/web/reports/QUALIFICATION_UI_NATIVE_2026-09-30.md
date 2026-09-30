# Qualification UI native — 30 septembre 2026 UTC

Le parcours réel import→publication→recherche→source sur une fixture DEV passe.
La première question réelle échoue au contrôle mémoire avant tout appel au
modèle. La chaîne réponse du modèle→citation n'est pas validée.

Application statique courante : 278 fichiers, 6 668 994 octets,
SHA256 `/workspace/index.html`
`57e7a1e77ea00762a105daf3cf7ad81750f270d32af3b7242cd0c63be0ec8a31`.
Build exit 0 et 17 tests unitaires PASS, avec sorties distinctes dans
[build](build-2026-09-30-rendercancel.log),
[unitaires](unit-2026-09-30-rendercancel.log) et
[manifeste](export-manifest-2026-09-30-rendercancel.json).

## Source réelle et reprises

Fixture : `Atelier 1 - Banc pneumatique DA-P01.pdf`, 2 pages natives.
SHA original `791b95354f28858d3ab8670481a10f1d3c9d6e547297adf5ac765a88d6663fd5`.
Document `e01b0666-ae93-40e5-9403-35decf00ae84`, version
`11debf6d-6e3c-4874-9ea4-395c1ad6661c`, génération publiée
`57ffa153-0f74-429b-82a8-72579b163e22`, révision
`5c6d7395-f3c9-5da8-baee-d7ca8615dfb5`.

Le job `8294f3ef-100a-475e-8378-983360f88b69` a été mis en pause par
l'admission puis repris explicitement dans l'UI, sans nouvel import. Publication
à 02:35:57 UTC, couverture réelle 2/2, OCR 0 et aucun warning d'extraction.
Les premiers échecs restent dans leurs dossiers : ouverture avant publication,
locator de document ambigu, puis promesse RenderTask annulée non gérée. Le
timeout initial de 180 s ne mesure pas seul la latence d'indexation : le
locator ciblait aussi le bouton de périmètre. Un dernier échec de recette
concernait un locator singulier pour deux warnings réellement identiques.

La reprise finale du même document passe en 11,4 s : nom/page/version réels,
recherche sous scope document, ouverture du passage, rotation 90°/zoom 125 %,
centre du texte natif dans la bbox source, retour page 2, warnings structurés,
aucune erreur de page ni requête externe. Aucun ID de citation n'est fabriqué
pour un hit search. Preuves :
[sortie](e2e-2026-09-30-native-dev-source-final.log),
[géométrie et provenance](e2e-2026-09-30-native-dev-source-final-evidence.json),
[trace et captures](../test-results/2026-09-30-native-dev-source-final/results.json).
La sélection page/bloc réelle a passé séparément dans
[la reprise précédente](e2e-2026-09-30-native-dev-reprise.log).

## Question réelle refusée

POST `/queries` HTTP 202, question « Quelle est la pression nominale de DA-P01 ?
Citez sa source. », scope du seul document ci-dessus, query
`2f36429b-2ac6-4c5f-83c3-d72271f1adf9`. Le SSE conserve queued, searching,
huit sources réelles, puis l'erreur id 4 `resource_admission_denied` :
5 095 Mio disponibles pour 5 888 requis (pic froid prévu 4 352 + réserve 1 536).
Le terminal indique `model_called=false`, retrieval 545,13 ms, contexte
39,52 ms et elapsed 4 166,58 ms. Aucun delta ni texte de réponse n'est reçu.
`output_tokens=384` désigne ici un budget, pas des tokens générés.

L'UI affiche l'erreur et les sources consultables. L'essai complet échoue en
43,9 s, incluant l'attente de l'assertion d'une réponse absente ; cette durée
n'est pas un TTFT. Le test a été corrigé pour échouer dès un terminal d'erreur,
avec SSE toujours conservé. Aucune nouvelle question n'a été soumise.

Preuves : [log FAIL](e2e-2026-09-30-qwen-question-first.log),
[attachments décodés](e2e-2026-09-30-qwen-question-first-evidence.json),
[SSE brut UTF-8](e2e-2026-09-30-qwen-question-first-events-raw.sse),
[hash et terminal](e2e-2026-09-30-qwen-question-first-events-raw.json),
[trace/capture](../test-results/2026-09-30-qwen-question-first/results.json).
Le GET du SSE terminal ne déclenche pas de génération.

## Mesures du seul navigateur de recette

Pendant la question refusée, worker Node 28136 et Chromium
13672/32672/32084/22556 : à 03:03:19, WSS 49,9/57,6/33,4/104,5 Mio ;
à 03:03:26, WSS 50,4/56,9/33,5/112,9 Mio. RAM disponible
4,881→4,924 GiB. Private et USS n'étaient pas relevés par cette première sonde.
Le navigateur étant fermé à la fin du test, ces valeurs historiques restent
inconnues ; [la mesure après fermeture](e2e-2026-09-30-qwen-first-resource-diagnostic.json)
ne montre plus aucun descendant Chromium.

Une sonde distincte GET-only passe en 8,0 s : worker 29844, un contexte, une
page, headless shell Chromium 153.0.8010.12, zéro argument personnalisé, zéro
mutation ni erreur de page. À 03:19:11, formulaire non soumis, les descendants
2448/6588/32392/3360 montrent :

| PID | RSS Mio | Private Windows Mio | USS Mio |
| --- | ---: | ---: | ---: |
| 2448 | 49,6 | 18,5 | 12,6 |
| 6588 | 56,1 | 27,1 | 20,9 |
| 32392 | 32,7 | 14,5 | 8,9 |
| 3360 | 99,2 | 41,6 | 30,8 |
| Node 29844 | 151,9 | 151,6 | 109,6 |

Après rendu du PDF à 03:19:14, le renderer PID 3360 passe à
RSS 161,8/private 77,9/USS 64,9 Mio ; worker Node
164,8/164,8/122,4 Mio. RAM hôte disponible 4,832→4,733 GiB.
Private Windows est la mémoire privée engagée ; USS est relevé séparément.
Ce sont des snapshots, aucune somme RSS ni pic hôte n'est revendiqué. La sonde
utilise psutil 7.2.2 depuis le PID vivant du propre worker et ses descendants
récursifs uniquement. Son navigateur est fermé à la fin.
Preuves : [log](e2e-2026-09-30-own-browser-memory.log),
[mesures](e2e-2026-09-30-own-browser-memory-evidence.json),
[trace/capture](../test-results/2026-09-30-own-browser-memory/results.json).

[Playwright](https://playwright.dev/docs/browsers) confirme que le headless shell
est déjà utilisé sans option `channel`. Sa
[documentation BrowserType](https://playwright.dev/docs/api/class-browsertype)
signale que les arguments personnalisés peuvent casser ses fonctions.
L'[architecture Chromium](https://www.chromium.org/developers/design-documents/multi-process-architecture/)
explique la séparation des processus, et
[psutil](https://psutil.readthedocs.io/stable/#psutil.Process.memory_info)
distingue RSS/private/USS. Sources officielles consultées par recherche le
30/09/2026 ; les ouvertures directes supplémentaires ont été refusées par le
lecteur web. Aucune option de réduction de processus fondée sur ces sources
et préservant les fonctions n'a été identifiée ; aucun flag n'a été appliqué.

Restent la vraie réponse/citation admise, les cas OCR/mixte dans le viewer,
comparaison multi-document, les autres parcours V2.1 et les seuils globaux de
qualification. Le binding DEV actuel est partiel 15/100 ; il ne valide pas
Recall ni les 200 questions. Ce rapport ne clôt aucun critère global du DoD.

## Révision exacte des anciennes citations — correctif D03

Le défaut initial est conservé dans [la preuve statique](old-revision-2026-09-30-initial-static.json) :
le chargement de blocs par version pouvait substituer la dernière extraction à
celle d'une citation. Ce fichier n'est pas une reproduction navigateur. C a
reproduit deux extractions différentes d'une même version dans ses tests HTTP,
puis ajouté `extraction_revision_id` optionnel aux routes blocks et outline.
Une révision inconnue, d'une autre version ou non publiée donne une erreur 404,
sans substitution. Les tests backend appartiennent à leur preuve séparée.

Le viewer fixe maintenant la révision de la source enregistrée, sépare les
clés de cache et vérifie version/page/révision retournées. Le deep-link query/
source relit le vrai registre et refuse une identité invalide ou sans révision.
La navigation ordinaire et les hits de recherche gardent leur fonctionnement.
Les actions page/section sont désactivées seulement après vérification que la
révision citée est réellement archivée ; sélection/bloc exact restent
disponibles. « Retour » restaure aussi la source et sa révision. Deux tests ont
d'abord reproduit la perte de source par Retour :
[FAIL initial](unit-2026-09-30-navigation-provenance-initial-fail.log).

La suite corrigée passe 27/27 :
[tests](unit-2026-09-30-navigation-provenance-corrected.log),
[TypeScript exit 0](typecheck-2026-09-30-navigation-provenance-corrected.log).
Le premier [build D03](build-2026-09-30-pinned-revision.log) reste conservé ;
le [build final avec Retour](build-2026-09-30-pinned-revision-return.log) termine
exit 0 en 98,94 s, puis calcule les SHA des artefacts (wrapper 104,05 s).
[Export final](export-manifest-2026-09-30-pinned-revision-return.json) :
278 fichiers, 6 673 451 octets ; SHA256 de `workspace/index.html`
`98d86335841d59c28c4be723ac0f70fe872206180c4f32031301f101705e0253`.

Les [48 snapshots](build-2026-09-30-pinned-revision-return-resources.jsonl)
montrent une RAM disponible de 5 701,2 à 5 757,1 Mio, minimum 5 228,7 Mio,
CPU hôte maximum échantillonné 29,0 %, disque libre après 29 339 910 144 octets.
Le plus grand RSS d'un seul processus propre observé est 437,2 Mio, mémoire
privée engagée 447,0 Mio. Aucun RSS
partagé n'est sommé ; ce ne sont pas des mesures continues de pic.
Aucun navigateur, import ou modèle n'a été lancé pendant ces builds.

Le parcours navigateur d'une ancienne citation est **NOT_RUN**, préparé dans
[la recette lifecycle](../tests/e2e/LIFECYCLE_RECETTE.md). Il attend les IDs
réels et l'instance restaurée isolée fournis par le superviseur, après arrêt de
la primaire. La nouvelle question Qwen reste également en attente d'un signal
explicite ; le premier refus d'admission reste FAIL.

## Deuxième question réelle — cache libéré, admission refusée

La primaire redémarrée `cc0b7e974ab14645af67f0f7c27bc8dc` et l'export final D03
sont utilisés après signal explicite. Même question, même scope document,
POST 202 à 04:40:49 UTC, query `3d5d61bf-50bf-48ce-aa1e-fc575dbb5de4`.
Le SSE produit queued, searching, huit sources, puis l'erreur terminale
`resource_admission_denied` à 04:40:59 : 5 222 Mio disponibles pour 5 888 requis
(pic froid 4 352 + réserve 1 536), `model_called=false`. Aucun événement
generating/delta, premier texte DOM, TTFT ou réponse modèle n'est observé.
La recette échoue immédiatement en 17,9 s et ferme son navigateur ; aucune
relance n'est effectuée. Le contrôle terminal n'attend plus 30 s une réponse
absente comme le premier essai.

Métriques réelles : retrieval 5 460,86 ms, contexte 62,50 ms, elapsed serveur
10 045,78 ms, prompt local 892 tokens, preuves 715 tokens. `output_tokens=384`
reste un budget. Le profil API canonique observé est
`f0230c27707406b94ad9770eff298570482ffb9c7a325c21771b3e721170f96f` ;
il est distinct du SHA du fichier YAML utilisé par le superviseur.

| Libération réelle | Baisse RSS API Mio | Gain RAM disponible Mio | Durée ms |
| --- | ---: | ---: | ---: |
| Session ORT E5 | 125,07 | 111,40 | 159,04 |
| Tokenizer E5 | 254,48 | 254,91 | 687,19 |
| Tokenizer Qwen | 55,77 | 57,13 | 247,78 |

Ce sont les mesures par étape renvoyées par l'API, aucune attribution isolée
ni somme de pics. Les prochains reloads/parités restent `pending` : cet essai
ne vérifie pas leur reprise. Les compteurs d'inférence nouveaux montrent un
appel E5 terminé, une entrée query et zéro entrée passage, de 0 à 1 dans ce
processus ; ils ne prouvent rien sur un réimport/réindex non exécuté.

La sonde propre mesure avant question, à 04:40:48, RAM disponible 5,159 GiB,
CPU hôte sur 100 ms 7,1 %, worker Node 33484 RSS/private/USS
156,8/155,7/114,4 Mio. Au terminal à 04:41:00 : 5,068 GiB, CPU 7,5 %, worker
172,8/172,5/130,4 Mio. Son renderer Chromium 9576 passe de
RSS/private/USS 106,4/46,9/33,7 à 113,0/50,3/37,1 Mio ; les autres descendants
16484/18476/27220 sont conservés séparément dans l'attachment. Aucun navigateur
utilisateur n'est lu ou fermé ; les snapshots ne donnent pas de pic continu.
La capture examinée montre l'erreur 5222/5888 et les huit sources consultables.

Preuves : [log FAIL](e2e-2026-09-30-qwen-question-second.log),
[attachments décodés](e2e-2026-09-30-qwen-question-second-evidence.json),
[SSE UTF-8 exact](e2e-2026-09-30-qwen-question-second-events.sse),
[hash/terminal](e2e-2026-09-30-qwen-question-second-events.json),
[trace/capture](../test-results/2026-09-30-qwen-question-second/results.json).
SSE 40 752 octets, SHA256
`0773b4202adc117c4785160808d755706f71ae582543f2898d7b83c7df8d12c9`.
Les octets proviennent du replay GET de cette query terminale, sans autre
POST ni génération. La chaîne question→réponse modèle→citation reste FAIL.
