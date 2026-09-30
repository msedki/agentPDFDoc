# Poste documentaire web

Application Next.js exportée statiquement sur `/workspace/`, servie par l'API
Windows native sur la même origine. Les originaux, bibliothèques, jobs, recherches
et questions viennent uniquement de `/api/v1`. Le build livré ne comporte aucune
réponse simulée, fixture embarquée, requête de fonte/CDN ou route serveur Next.

Le skill appliqué est [pdf-workspace-web](../../.agents/skills/pdf-workspace-web/SKILL.md),
avec frontend-design et les références React/general web security locales.
Les parcours réels suivent le skill `RAG_Local_Agents/skills/pdf-workspace-e2e`.

Versions résolues : Node 22.17.0, pnpm 10.34.1, Next 16.3.7, React 19.3.0,
PDF.js 6.3.289, TanStack Query 5.104.0, Zustand 5.0.15, TypeScript 5.9.3 et
Playwright 1.63.0. Les versions exactes et dépendances sont dans `package.json`
et `pnpm-lock.yaml`. Le cache Playwright local contient déjà Chromium requis ;
aucun téléchargement navigateur n'a été exécuté par ce lot.

Depuis ce dossier, sous un créneau de build accordé par le superviseur :

```powershell
$env:NEXT_TELEMETRY_DISABLED='1'
$env:COREPACK_ENABLE_NETWORK='0'
$env:NODE_OPTIONS='--max-old-space-size=2048'
pnpm typecheck
pnpm test:unit
pnpm build
```

Le build copie worker, cmaps, wasm, fontes standard et profils ICC de la version
locale PDF.js, avec un manifeste de SHA, puis exporte vers `out/`. Next utilise
un seul worker. Ne pas lancer de build en concurrence avec OCR/LLM lourd sur le
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
publication partielle. Cette dernière nécessite l'action explicite « Utiliser
cette extraction partielle ». La couverture et les limites restent visibles.
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
[traces/captures initiales](test-results/2026-09-30-native-dev-first/results.json).
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
[trace/captures](test-results/2026-09-30-native-dev-source-final/results.json).
Le nom et la page proviennent de l'API ; rotation 90°/zoom 125 %, ancre native
dans la bbox réelle, retour page 2 et warnings structurés sont exercés, sans
erreur de page ni requête externe. Ce cas ne prouve pas les 95 % d'ancres ni
le scénario mixte complet.

La première question réelle a échoué avant génération : POST 202 puis SSE
`resource_admission_denied`, 5 095 Mio disponibles pour 5 888 requis, avec
`model_called=false`. Huit sources réelles ont été reçues, aucun delta ni texte
de réponse : [sortie](reports/e2e-2026-09-30-qwen-question-first.log),
[preuves décodées](reports/e2e-2026-09-30-qwen-question-first-evidence.json),
[trace/capture](test-results/2026-09-30-qwen-question-first/results.json).
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
[trace/capture](test-results/2026-09-30-qwen-question-second/results.json).
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
isolés prévus. Une reprise fournit `RAG_E2E_REUSE_DOCUMENT_ID` et vérifie le SHA
de la même fixture DEV, sans nouvel import. La question réelle exige un créneau
distinct et `RAG_E2E_GENERATION_ALLOWED=1`. La sonde mémoire utilise la venv du
projet et psutil : PID propre du worker Node, descendants Chromium récursifs,
RSS, private Windows (mémoire privée engagée) et USS séparés par processus.
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
aussi les listes `[S001, S002]`, chaque ID étant validé individuellement, sans
interprétation HTML/Markdown (`src/lib/citations.ts`). Les onglets d'analyse
suivent le motif tablist (flèches, Home/End, tabIndex itinérant, `tabpanel`) ;
la plage de pages est validée contre le nombre de pages de la version ouverte,
pas de la version active. Le jeton `--subtle` est assombri et sert aussi aux
placeholders, qui remplacent le gris semi-transparent du preflight Tailwind
(environ 3,1:1) ; l'icône de périmètre de dossier perd son opacité réduite
(2,5:1). `tests/unit/accessibility.test.ts` calcule depuis `globals.css` les
paires texte/fond et placeholder/champ (au moins 4,5:1) et cette icône (au
moins 3:1). Les tests unitaires prouvent les fonctions pures (`src/lib/`) et les
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
