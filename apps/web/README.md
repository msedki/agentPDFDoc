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
isolés prévus. Depuis le 01/10, `tools/qualification/e2e_instance.py start --state <etat.json>`
fournit cette cible : instance neuve dans une racine et des ports temporaires, dont
l'état donne l'origine (`RAG_E2E_BASE_URL`) et le fichier de jeton
(`RAG_E2E_CONTROL_TOKEN_FILE`) ; `stop` l'arrête et supprime sa racine. Les scénarios
de géométrie, de balisage hostile, de canvas, d'import et de sélection y sont passés
le 01/10 ([géométrie](reports/e2e-2026-10-01-import-isole-geometrie-evidence.json),
[parcours](reports/e2e-2026-10-01-import-isole-parcours-evidence.json)), ainsi que la sélection Unicode de
`unicode-selection.spec.ts` (hors BMP, accent combinant, ligature, césure, sélection ambiguë refusée ;
[rapport](reports/e2e-2026-10-01-unicode-selection-evidence.json)).
Une reprise fournit `RAG_E2E_REUSE_DOCUMENT_ID` et vérifie le SHA
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
| Bandeau de contexte : puce de périmètre, documents interrogeables et exclus par motif (traitement, pause, erreur, état inconnu), un seul emplacement de message (erreur de l'espace de travail, sinon avis de préparation) ; rien sous 768 px de plus que l'état des services | `src/components/context-band.tsx`, `scopeCoverage`, `coverageSentence`, `readinessSentence` | `panel-state.test.ts`, `warnings.test.ts`, `shell.test.ts` |
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
