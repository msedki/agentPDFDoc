# Definition of Done — RAG-LOCAL-16 V2.1

**Rôle :** critères canoniques de fin et état de leur qualification par plateforme · **Propriétaire :** qualification du produit · **Statut :** Vivant pour les preuves et statuts ; seuils de référence inchangés · **Référence :** exigences V2.1, décisions W001/W018 ; base publiée `1e20a58` et compléments locaux F04 E2 et D06.9 datés ci-dessous, historique conservé · **Mis à jour :** 2026-10-05 22:31 (UTC) · **Source de vérité :** ce fichier pour les critères ; [QUALIFICATION.md](QUALIFICATION.md) pour le protocole, [journal](journal/README.md) et rapports cités pour les exécutions

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md). **W018 (01/10/2026) : Linux natif (aarch64 et x86-64) devient une seconde plateforme**, toute machine Windows restant prise en charge comme avant ; réalisation en cours (lots J du [plan](PLAN.md)).

## Règle de clôture

Un critère est `PASS` uniquement avec une preuve reproductible associée au commit, à la configuration, au corpus et à la machine. Les statuts permis sont `NOT_RUN`, `PASS`, `FAIL`, `BLOCKED`. « Le code existe », « l'agent affirme que cela marche » et « le test utilise un mock » ne valent pas validation de bout en bout.

Les seuils suivants sont des objectifs de recette, pas des performances déjà atteintes. Ne pas les diminuer après un échec pour afficher un succès. Une modification approuvée du périmètre exige une nouvelle baseline, une justification et une nouvelle recette.

**Qualification par plateforme (W018, 01/10/2026).** Le produit cible toute machine Windows 11 x86-64 (W001) et Linux natif aarch64 ou x86-64 (W018 et son complément). Les cases et preuves des sections D01 à D11 portent la qualification Windows acquise jusqu'au 01/10 ; une preuve vaut pour la machine qu'elle déclare. La plateforme Linux est qualifiée séparément, dans le tableau « Qualification Linux » en fin de document, avec les mêmes critères et les mêmes seuils ; aucune preuve Linux ne coche une case Windows, et réciproquement.

La validation sur fixtures et la validation sur documents métier réels sont distinctes. Si aucun corpus privé autorisé n'est disponible, produire les fixtures synthétiques, réaliser tout ce qui est testable et marquer la qualification métier `BLOCKED — corpus métier absent`. Ne pas présenter cette limite comme un échec général de l'application ni inventer un corpus représentatif.

Baseline documentaire 2.1. Les objectifs conservés et ajoutés ci-dessous sont des critères du projet, pas des performances déjà mesurées. Le protocole de mesure est détaillé dans `QUALIFICATION.md`.

## D01 — Installation et reproductibilité

- [ ] Un environnement neuf peut être provisionné par le lanceur documenté, sans édition manuelle de code.
- [ ] Une installation provisionnée redémarre sans Internet et sans téléchargement implicite.
- [x] Les lockfiles de paquets et manifests de runtimes/modèles contiennent des versions/hashes réels ; aucun `latest` comme identité finale.
- [x] `doctor` distingue modèle absent, service indisponible, configuration ignorée, CPU/GPU utilisé et stockage incohérent.
- [x] Start/stop ne créent pas d'instances doublées et ne détruisent pas les données.

**Preuves :** logs de provisionnement/restart, manifests, sortie doctor, commandes exactes et versions des exécutables.

Preuve01/10/2026 (D01.3), contrôle relu sur le dépôt au commit `d52834f` : aucune occurrence de `latest` dans `config/artifacts.lock.json`, `config/models.lock.json`, `config/embedding-comparison.lock.json`, `uv.lock`, `apps/web/pnpm-lock.yaml` ni dans les manifestes de `.runtime/manifests/` ; chaque entrée de `artifacts.lock.json` porte une empreinte ou une révision ; `models.lock.json` fixe l'empreinte du manifeste et des couches de `qwen3.5:4b` et `qwen3.5:4b-text` ; `uv.lock` : 127 paquets, aucun paquet de registre sans empreinte SHA-256 ; `pnpm-lock.yaml` : 126 résolutions avec intégrité sha512. Le contrôle `doctor` (`model_lock`) vérifie hors ligne la conformité du stockage au verrou.

Preuve01/10/2026 (D01.4) : `doctor` distingue modèle absent (`model_lock` à `absent`, rubrique `modèle` rouge) et fichiers altérés, service arrêté ou muet (`llm_model_diagnosis` : `service_unavailable_model_files_present`), configuration non appliquée (`profile_application` à `restart_required`), usage GPU (`loaded_models[].size_vram`, et `up` refuse un profil où `llm.num_gpu` n'est pas nul ; **à revalider depuis W024 et W025** : le profil livré passe en `llm.accelerator: auto`, l'usage du GPU est rapporté par la rubrique « calcul » de `doctor` ; essai réel J11.8 du 02/10 sous Linux : `gpu_ready` puis `gpu_in_use` (`size_vram` = `size`), calcul CPU imposé par le profil reconnu par `selftest`, [journal](journal/2026-10-02.md) ; c'est une preuve Linux, qui ne coche pas la case Windows : rejeu Windows au lot J11.10) et stockage incohérent (`index_consistency` : points Qdrant et fragments SQLite par génération active, depuis `e4c7caf`) ; tests `test_runtime_doctor.py`, `test_runtime_verdict.py` (pannes provoquées) et essai d'intégration HTTP ; relevé réel du 01/10 à 06:02 : 5 générations actives, 322 fragments, cohérent, verdict vert.

Preuve (D01.5) : un second `up` rend l'instance existante sans en lancer une autre ([30/09](reports/runtime-first-duplicate-up.json)) ; le 01/10, cinq cycles `down` puis `up` de l'instance principale (04:29, 05:04, 05:11, 05:25, 06:02, chacun après contrôle d'absence de question et de traitement actifs) ont laissé ses données intactes : mêmes comptes de traitements avant et après (61 en pause, 12 partiels, 4 prêts, 1 en erreur), `readiness` 200, index cohérent après le dernier ([journal](journal/2026-10-01.md)).

## D02 — Import, bibliothèque et extraction

- [x] Import d'un dossier et de sous-dossiers, noms Unicode/espaces et fichiers homonymes dans des dossiers distincts.
- [x] Original copié sans modification ; SHA-256 vérifié ; version et chemin documentaire conservés.
- [ ] PDF FR/EN natifs, multi-colonnes, scan et mixte traités avec couverture par page visible.
- [ ] OCR absent des régions natives fiables ; régions/pages réellement OCRisées comptées et traçables.
- [ ] PDF simple traité par la voie native qualifiée ; page mixte « paragraphe natif + tableau scanné » couverte sans double texte.
- [ ] Régions non résolues visibles ; un schéma non interprété ne devient pas une preuve textuelle inventée.
- [ ] Section/table traversant les pages 4/5 conservée correctement ; fenêtres de checkpoint non utilisées comme frontières sémantiques.
- [x] PDF blanc, corrompu, chiffré et trop volumineux produisent un état explicite, pas un succès silencieux.
- [ ] Extraction partielle signalée dans bibliothèque, résultats et réponses ; les pages manquantes ne sont pas déclarées lues.
- [ ] Table et unités du corpus contrôlé restent interprétables ; aucun texte de colonne mélangé non signalé.

**Preuves :** inventaire de fixtures, hashes, JSON d'extraction, compteurs de couverture et contrôles visuels sur les cas difficiles.

Preuve01/10/2026, API réelle d'une instance isolée (`tools/qualification/library_check.py`, `5fa22ae`, [rapport](reports/library-2026-10-01.json)) : import de `Unité hiver/Commun.pdf` et `Unité été/Commun.pdf` : deux documents distincts, chemins Unicode avec espaces conservés à l'identique, extraction prête (D02.1) ; original relu par `GET /versions/{id}/file`, SHA-256 identique à celui de la fixture et de la version (D02.2) ; PDF chiffré : traitement en erreur `PDF_ENCRYPTED` ; structure invalide : `PDF_INVALID` ; page blanche : prête, page `blank`, aucun bloc ; fichier de 112 085 octets sur une instance limitée à 64 Kio : refus 413 `file_too_large`, aucun document créé (D02.8).

## D03 — Indexation et cohérence

- [x] Un réimport identique n'ajoute pas de version inutile ni de calcul d'embedding redondant.
- [x] Le déplacement d'un PDF dans l'arborescence ne recalcule pas ses embeddings.
- [x] Une nouvelle version reste invisible en recherche jusqu'à publication de sa génération complète.
- [x] Un retrait est immédiatement exclu des scopes ; les deux index actifs sont nettoyés/réconciliés.
- [x] Arrêt forcé pendant parsing, embedding, upsert et publication : reprise sans doubles chunks ni génération fantôme.
- [x] Une panne Qdrant au milieu d'un import ne fait pas apparaître le document comme complètement prêt.
- [ ] Les anciennes citations ouvrent l’ancienne version et révision d’extraction ; une purge indique source supprimée sans substitution.
- [ ] Changer le seul embedding ne refait pas l’OCR ; modèles de même dimension dans des collections distinctes ; aucun mélange query/documents de modèles différents.
- [ ] Les générations épinglées par une requête en cours ne sont pas nettoyées prématurément ; retrait explicite réévalué avant fourniture de nouveau contexte.

**Preuves :** compteurs avant/après, scénarios de fault injection, journal des transitions et recherche sur versions différentes.

Preuve01/10/2026, même instance isolée et même [rapport](reports/library-2026-10-01.json) : réimport identique : même document, `reused`, aucun traitement ni version ajoutés, compteurs `embedding_requests`, `embedding_texts_submitted` et `native_worker_launches` inchangés (D03.1) ; déplacement vers `Archives/Commun été.pdf` : aucun traitement, compteurs inchangés, document retrouvé par la recherche à son nouveau chemin (D03.2) ; seconde version de `Procédure QV-01.pdf` au même chemin : 52 recherches pendant sa file d'attente et son extraction ne rendent que la valeur de la première (2.7 bar), la version active reste la première, puis la seconde (4.9 bar) seule après publication (D03.3 ; l'étape d'indexation, brève, n'a pas été saisie par le sondage). Retrait (D03.4) : document exclu des recherches aussitôt, ses 2 points Qdrant supprimés par la réconciliation, aucun fragment SQLite restant pour sa génération, index plein texte aligné sur les fragments (2 lignes pour 2 fragments), index restant cohérent ([rapport du second essai](reports/library-2026-10-01-retrait.json)).

Preuve01/10/2026, fautes injectées sur instance isolée (`tools/qualification/fault_check.py`, `f9c48da`, [rapport](reports/faults-2026-10-01.json)) : Qdrant tué pendant les embeddings d'un import : traitement en erreur `qdrant_unavailable`, document en erreur sans génération active, jamais présenté comme prêt ; après redémarrage et relance, prêt avec une seule génération publiée, 5 fragments pour 5 points (D03.6). Arrêt forcé de toute l'instance pendant l'extraction, pendant les embeddings et pendant l'écriture des points Qdrant (document synthétique de 200 pages, 1 800 fragments) : traitement repris jusqu'à « prêt », une seule génération publiée, aucun fragment en double, autant de points que de fragments, aucun nettoyage en attente (D03.5). La publication n'a pas été visée par un arrêt réel : elle tient en une seule transaction SQLite (`publish`, `services/api/indexing.py`), si bien qu'un arrêt pendant celle-ci laisse soit l'état essayé de l'écriture des points, soit l'état publié.

## D04 — Recherche et périmètre

- [x] Recherche lexicale et dense réelles, sans LLM requis pour voir les résultats.
- [x] Filtres dossier récursif, documents, section et pages appliqués avant top-k et avant assemblage de contexte.
- [x] Aucun passage hors scope : **zéro fuite** dans le jeu de tests de périmètre, y compris expansion parent/historique.
- [x] Requêtes avec identifiants proches correctement distinguées ; aucune suppression excessive de ponctuation.
- [x] Ranking BM25 dans le bon sens ; fusion RRF testée sur exemples déterministes ; absence de doublons dominants.
- [x] Le cas adverse RRF ne fait pas disparaître la preuve d’un identifiant explicitement ciblé : contrôle après déduplication, expansion et coupe finale.
- [ ] Une occurrence exacte sans information pertinente ne permet pas une réponse fabriquée ; identifiants/documents non couverts affichés.
- [x] L'analyse d'une sélection courte ne déclenche pas de recherche globale.

**Objectif qualité :** Recall@10 >= 0,90 sur questions répondables du jeu de test tenu à l'écart du réglage, avec référence à une preuve précise et pas seulement au bon document. Rapporter aussi Recall@5, MRR et résultats par catégorie ; ne pas masquer un échec important derrière une moyenne globale.

Preuve partielle acquise30/09/2026 : [publication réelle11chunks/11points](reports/backend/2026-09-30-first-publication-readonly.json) et [recherche navigateur sans modèle](../apps/web/reports/QUALIFICATION_UI_NATIVE_2026-09-30.md). Les scopes et métriques finales de D04 restent ouverts.

Preuve01/10/2026 (D04.2 à D04.6, D04.8) : filtres avant la coupe top-k : `test_retrieval_scope_filters_precede_topk_against_dominant_outside_chunks` (dossier récursif, documents, pages, section) place 30 passages hors périmètre, mieux classés que tout passage autorisé, au-delà de `lexical_top_k` et `dense_top_k` (24) ; il échoue si le filtre est retiré des requêtes SQLite et Qdrant ou réduit aux seules générations. Sur instance isolée avec Qdrant et E5 réels (`tools/qualification/scope_check.py`, [rapport](reports/scope-2026-10-01.json)) : sans filtre de périmètre, les 24 premiers points denses sont tous hors du document cible et la voie plein texte n'y trouve rien ; avec les périmètres dossier récursif, documents, pages et section, la recherche et le contexte d'évaluation sont non vides et entièrement dans le périmètre (D04.2). Zéro fuite (D04.3) : ce même essai, expansion de parent comprise ; 94 questions DEV sur instance réelle, dont 7 relances qui reprennent la question précédente ([résumé](reports/backend/2026-10-01-development-retrieval-summary.json)) ; tests d'expansion bornée aux pages du périmètre et de changement de périmètre dans une conversation, où la requête envoyée au modèle ne contient ni le texte ni l'identifiant de l'ancien périmètre. Identifiants proches (D04.4) : tests de frontières (CCU-210, CCU-21-A, EN 50155-1, DB-P01, DA_P01, X/P01, 3.4.2 contre 4.2, tirets typographiques, listes à barre oblique) ; la voie exacte garde tirets, points et barres obliques des identifiants, la requête FTS5 neutralise seulement sa propre syntaxe ; sur le jeu DEV, 14 questions « DA-P0x, et non DA-P0x0 », dont le code voisin figure dans le même document : 14/14 preuves au top 5 et dans le contexte. BM25 et RRF (D04.5) : classement FTS5 réel par densité, scores RRF calculés sur exemples fixés dont le contre-exemple de la spécification, textes en double retirés de la liste finale. Cas adverse RRF (D04.6) : l'occurrence exacte, première en lexical et absente du dense, serait classée après les six fragments finaux par la seule fusion ; elle reste dans la liste finale puis dans le contexte après expansion et coupe (`identifier_coverage_states` = `covered`), et le test échoue si la priorité de l'occurrence exacte et la réservation par identifiant sont retirées. Sélection courte (D04.8) : test HTTP instrumenté (ni embedding, ni requête Qdrant, ni recherche FTS5) et, sur l'instance réelle, compteur natif `rest_responses_total` de Qdrant inchangé (9 avant, 9 après) pendant la recherche et le contexte d'une sélection, porté à 10 par une recherche témoin ; seul le texte sélectionné est rendu et transmis. D04.7 reste ouvert : l'absence de réponse fabriquée se juge sur des réponses générées (R7, R13). Les objectifs de qualité se mesurent sur le jeu final (R13).

**Contexte final :** `EvidenceCoverage@Context >= 0,90` sur les unités de preuve annotées des questions répondables. Rapporter aussi la proportion de questions dont toutes les preuves nécessaires sont présentes. Mesurer après toutes les transformations ; un succès top-10 n’est pas automatiquement un succès de contexte. Définitions et dénominateurs dans `QUALIFICATION.md`.

## D05 — Réponses et citations

- [ ] Appel au vrai modèle Ollama local ; aucune réponse de recette codée en dur.
- [ ] Une seule génération par question nominale ; aucun appel supplémentaire caché de rewriting/reranking/jugement.
- [ ] Relance courte résolue depuis un référent autorisé ; ambiguïté signalée sans recherche globale hasardeuse. Changement de scope testé ; ancienne réponse du LLM jamais utilisée comme preuve.
- [ ] Contexte complet compté avec le bon tokenizer/template ; pas de troncature silencieuse.
- [ ] **100 % des IDs de citation affichés comme valides** existent dans le registre autorisé de la question.
- [ ] **100 % des citations de la recette** désignent la bonne version et la bonne page physique.
- [ ] Les localisations `span/block/table/page` sont honnêtes et visibles ; aucune géométrie fabriquée.
- [ ] Inconnus, contradictions et insuffisances des sources sont signalés ; une absence de résultat n'est pas affirmée comme absence documentaire.
- [ ] Au moins **95 % des assertions documentaires vérifiées** sont soutenues par les preuves citées sur le jeu tenu à l'écart.
- [ ] Au moins **90 % des questions sans réponse** du jeu tenu à l’écart conduisent à une abstention appropriée.
- [ ] Exactitude de la réponse utile >= **85 %** des questions répondables du test final, selon grille de réponse annotée ; une abstention compte comme non-réussite sur une question répondable. Rapporter séparément erreurs de valeur/unité, réponse partielle et abstention injustifiée.

**Mesure :** vérifier manuellement les réponses, assertions et citations de toutes les questions du test final de qualification, avec dénominateur explicite par métrique. Les fixtures factuelles contrôlées permettent aussi des tests déterministes. Un auto-jugement du même petit LLM n'est pas la seule preuve d'exactitude. Conserver les dénominateurs et la grille d'annotation.

## D06 — UX réellement intégrée

- [x] Trois panneaux utilisables à 1 366 × 768 et 1 920 × 1 080, sans chevauchement bloquant.
- [x] Arborescence, lecteur et chat partagent le bon état ; périmètre toujours visible.
- [x] Le clic sur une citation navigue vers la version/page, surligne et permet de revenir au point précédent.
- [x] Zoom, rotation 0/90/180/270°, CropBox non trivial et labels de pages romains ne cassent pas la navigation.
- [ ] Au moins 95 % des ancres de région du corpus contrôlé couvrent effectivement le passage attendu ; 100 % ouvrent la bonne page. Les cas `page` ne sont pas comptés comme surlignages de région réussis.
- [ ] Sélection native et OCR lorsque géométrie disponible ; actions page/section fonctionnelles.
- [x] Aller-retour des offsets UTF-16/points de code, ligatures, césures, caractères hors BMP et accents combinants ; hash source vérifié ; fallback de granularité explicite.
- [x] Nombre de canvases ET budget cumulé de pixels respectés pendant zoom/scroll ; allocations obsolètes libérées.
- [ ] Réponse progressive, statut d'indexation, annulation et reconnexion SSE observables.
- [x] Aucun bouton factice et aucun écran dépendant de données mockées dans le build de livraison.
- [x] Navigation clavier, focus visible, labels accessibles et contraste vérifiés sur les composants essentiels.

**Preuves :** Playwright utilisant l'API réelle, traces et captures annotées par nom de scénario. Un test avec Qdrant/Ollama mockés reste un test UI isolé et n'est pas compté comme E2E réel.

Disposition aux deux résolutions vérifiée contre l'API native : [rapport et captures](../apps/web/reports/QUALIFICATION_UI_NATIVE_2026-09-30.md). Ce résultat ne clôt pas navigation de toutes géométries, réponse progressive ou anciennes révisions.

Preuves01/10/2026, Playwright sur l'API réelle (Qdrant et Ollama réels) : clic sur une citation, page et surlignage ([question réelle, instance principale](../apps/web/reports/e2e-2026-10-01-r2-generation-0446/evidence.json)) et retour au passage précédent ([import réel et navigation, instance isolée](../apps/web/reports/e2e-2026-10-01-import-isole-parcours-evidence.json)) ; rotations 0/90/180/270 avec CropBox et folios romains ([géométrie, 4/4](../apps/web/reports/e2e-2026-10-01-import-isole-geometrie-evidence.json)) ; zoom à 300 % dans le budget de canvases et de pixels, canvases détachés libérés (même rapport que l'import) ; clavier, focus visible, libellés et contrastes ([E2E lecture seule](../apps/web/reports/e2e-2026-10-01-reponse-mise-en-forme-0457-evidence.json), tests unitaires `accessibility.test.ts` et `ui-guards.test.ts`, [recette](reports/ui-recette-2026-09-30.md#second-passage--1er-octobre-2026)). Traces Playwright conservées localement sous `apps/web/test-results/`, hors Git. Restent ouverts : état partagé (D06.2), ancres de région (D06.5), sélection OCR (D06.6), offsets (D06.7), annulation et reconnexion SSE (D06.9), absence de bouton factice (D06.10).

Preuve01/10/2026 (D06.2) : parcours Playwright sur l'API réelle d'une instance isolée, 05:42, code d'interface courant ([rapport](../apps/web/reports/e2e-2026-10-01-import-isole-parcours-evidence.json), `workspace.spec.ts`) : document importé puis ouvert depuis l'arborescence, le résumé du périmètre reste « Toute la bibliothèque » pendant la lecture, la rotation et le zoom ; document coché dans l'arborescence puis « Utiliser ce périmètre » : le résumé affiche son nom ; recherche dans le panneau d'analyse, ouverture du passage dans le lecteur avec surlignage, périmètre inchangé, retour à la page précédente ; périmètres page et bloc transmis à l'API et affichés. Question au vrai modèle avec citation enregistrée et périmètre conservé ([instance principale, 04:47](../apps/web/reports/e2e-2026-10-01-r2-generation-0446/evidence.json)) ; seule modification ultérieure de l'interface : rendu du texte des réponses (`0c7fd84`), sans effet sur le périmètre.

Preuve01/10/2026 (D06.7) : `apps/web/tests/e2e/unicode-selection.spec.ts` sur l'API réelle d'une instance isolée, fixture « Unicode ligatures césures.pdf » ([rapport](../apps/web/reports/e2e-2026-10-01-unicode-selection-evidence.json)) : sélection DOM réelle dans la couche texte PDF.js puis recherche dans le périmètre de la sélection ; pour chaque cas, offsets transmis en points de code avec la révision et le hash du bloc, et texte rendu par l'API identique à la sélection. Aller-retour exact pour le caractère hors BMP (U+1F600), l'accent combinant (e + U+0301), la ligature et la césure « con- / trole » (deux blocs, aucun désécablage inventé) ; sélection ambiguë (« ion », deux occurrences) refusée par un message qui oriente vers la page ou le bloc. Ligature : l'extraction (PDFium) et PDF.js la développent toutes deux en « fi » (U+FB01 du ToUnicode), comportement consigné par l'inspection de la fixture (`ligature_expansion_observed`) ; l'aller-retour porte sur cette forme extraite et hachée, la forme U+FB01 n'est pas conservée.

Preuve01/10/2026 (D06.10) : gardes statiques sur les sources de l'interface livrée (`apps/web/tests/unit/ui-guards.test.ts`) : chacun des boutons de `src/` (`button`, `Button`, `ActionButton`, plus de 30) porte une action (`onClick`, `onAction`), soumet un formulaire ou transmet les props de l'appelant ; aucune source ne contient de donnée simulée (`mock`, `fake`, `demo`, `dummy`) ; tous les appels passent par `/api/v1` de même origine, la seule adresse absolue étant la base de résolution hors navigateur du contrôle de même origine. Les écrans et leurs actions sont exercés sur l'API réelle par les parcours Playwright cités ci-dessus (import, navigation, géométrie, citation). Contrôles : 138 tests unitaires web, `tsc --noEmit` sans erreur.

## D07 — RAM, CPU et latence

Recette sur un hôte **16 Go physiques maximum**, CPU uniquement, sans utilisation GPU. Déclarer CPU, cœurs, OS, navigateur, stockage, RAM visible, swap, versions et empreintes. Inclure les mesures hôte Windows, navigateur et tous les services ; ne pas compter uniquement la mémoire Python.

- [ ] Une seule génération active, un seul worker lourd, et aucune concurrence parsing/OCR lourd avec génération.
- [ ] Pas d'OOM, pas de fuite mémoire progressive, pas de swap soutenu nécessaire au fonctionnement nominal.
- [ ] Mémoire cible application <= **10 Gio** de résidence non dupliquée ; mémoire hôte disponible >= **1,5 Gio**. Préciser working set et private bytes Windows, sans addition trompeuse de pages partagées.
- [ ] Admission et pause coopérative fonctionnent ; pas de kill nominal après cinq secondes. Un job interrompu reprend au dernier checkpoint durable.
- [ ] Alternance chat/import : attente visible, reprise explicite fonctionnelle et absence de rechargement périodique sans action. Mesurer initialisations, travail utile et unités rejouées.
- [x] Reprise automatique désactivée dans le profil livré, ou activée uniquement avec politique documentée et essai anti-ping-pong concluant.
- [ ] Avec au moins 25 000 chunks et modèle chaud : recherche hybride p95 <= **3 s** ; premier token p95 <= **45 s** pour environ 3 000 tokens d'entrée ; réponse de 400 tokens p95 <= **180 s**.
- [ ] Mesurer aussi démarrages à froid et indexation pages/minute ; séparer modèle chaud et préfixe réutilisé en cache, ainsi que chargement/prompt/génération.
- [ ] Le scénario 400 tokens autorise une sortie >400 ; une sortie plus courte naturelle n’est pas imputée comme temps pour 400 tokens. Rapporter les longueurs observées.
- [ ] Au moins 30 questions de performance et un scénario d'usage de 30 minutes : navigation, recherches, questions, import et reprise.

Si la cible CPU ne passe pas une mesure, conserver `FAIL`, identifier la phase dominante et tester une optimisation ciblée. Ne pas augmenter RAM/GPU, raccourcir secrètement les réponses ou remplacer le modèle sans nouvelle mesure déclarée. Les seuils ne sont pas garantis par ce dossier : leur atteinte est précisément l'objet de la qualification.
Preuve01/10/2026 (D07.6), poste Windows (W001), première branche du critère, au commit `ea49d05` : `config/local16.yaml` l.160 `resources.scheduling.auto_resume_ingestion: false`, copie documentaire identique (`verify_pack.py` : `runtime_profile_copy` et `configuration_consistency` PASS) ; le gouverneur refuse au démarrage toute autre valeur (`services/runtime/resources.py:194-198`, tests `test_auto_resume_ingestion_enabled_in_profile_is_refused` et `test_auto_resume_ingestion_is_read_from_delivered_profile`, inclus dans la suite Windows du 01/10, 538 réussis, point de 09:08). Un traitement mis en pause au checkpoint passe à `paused` (`services/api/jobs.py`) et ne revient en file que par `POST /jobs/{id}/resume` ou `/jobs/resume-paused`, appelés par les seuls boutons de l'interface ; le retour au mode ingestion répond `manual_jobs_require_resume: true`. Observation réelle : les 61 traitements en pause le sont restés à travers le redémarrage de 06:50 jusqu'au point de 12:20. Seconde branche (reprise activée avec essai anti-ping-pong) non retenue. Linux aarch64 (W018) : configuration et refus au démarrage vérifiés (4 tests PASS le 01/10 à 16:13 UTC), comportement à rejouer en J8.

Mesure D07 et accélération GPU (W024, W025) : une preuve D07 exige une série mesurée en calcul CPU imposé par le profil et un rapport de `tools/qualification/perf.py` qui porte `d07_eligible: true`, l'accélération étant relue au début et à la fin de la série ; un rapport `d07_eligible: false` est invalide pour D07. Mode opératoire : [QUALIFICATION.md](QUALIFICATION.md), section 8. Les mesures sur GPU sont rapportées à part et ne cochent aucun critère.

## D08 — Hors ligne et sécurité

- [ ] Après provisionnement, bloquer toutes les sorties non-loopback et exécuter import, OCR, embeddings, recherche, génération et lecture.
- [ ] Zéro requête externe nécessaire et aucune tentative inexpliquée de DNS/télémétrie/CDN/modèle manquant dans le scénario applicatif.
- [x] Origines/Host non autorisés rejetés ; pas de bind LAN involontaire ; pas de CORS wildcard.
- [x] Traversal, symlink sortant de la racine et fichiers malformés traités sans lecture arbitraire ou crash du serveur API.
- [ ] Instructions malveillantes insérées dans une fixture PDF ne provoquent ni exécution, ni exfiltration, ni élargissement du scope.
- [x] Markdown/HTML actif et liens d'images distantes ne sont pas exécutés/chargés automatiquement.
- [x] Logs normaux sans texte privé ; originaux et modèles exclus du Git par défaut.

Preuve01/10/2026 (D08.6) : texte de document hostile rendu littéral, sans élément actif ni requête distante ni changement de périmètre (Playwright sur instance isolée, [rapport](../apps/web/reports/e2e-2026-10-01-import-isole-parcours-evidence.json)) ; côté serveur, balises retirées et images Markdown remplacées avant affichage (`validate_answer`, `services/api/context.py`, testé avec `<script>` et une image distante dans `tests/unit/test_retrieval.py`) ; côté interface, réponse rendue en éléments React sans interprétation de balise (`apps/web/src/lib/answer-format.ts`, `tests/unit/answer-format.test.ts`). Instruction hostile dans une fixture (D08.5) : sans effet sur la réponse ([rapport](reports/injection-2026-10-01-0441.json)), exfiltration et élargissement du périmètre non mesurés : critère laissé ouvert.

Preuve01/10/2026 (D08.3) : `tools/qualification/http_guards_check.py` sur l'instance principale en marche, en lecture seule ([rapport](reports/http-guards-live-20261001T0943.json)) : 18/18 contrôles conformes. API : Host étranger ou port différent refusés (400 `invalid_host`), Origin étrangère ou `null` et requête inter-sites refusées (403), préflight CORS étranger refusé ; Ollama : Host et Origin étrangers refusés (403) ; Qdrant : sans clé 401, y compris avec Host et Origin étrangers ; aucune réponse ne porte `Access-Control-Allow-Origin`. Sockets en écoute de l'instance relevés par processus : API, Qdrant et Ollama sur 127.0.0.1 uniquement. Limites : contrôle applicatif, sans blocage réseau du système (D08.1) ; modèle non chargé pendant la mesure, le processus d'inférence lancé par Ollama n'a pas été observé. Même résultat que le contrôle du 30/09 ([rapport](reports/http-guards-live-20260930T1636.json)), rejoué après l'ajout des sessions (W011).

Preuve01/10/2026 (D08.7) : `tools/qualification/log_privacy_check.py` en lecture seule sur l'instance principale ([rapport](reports/log-privacy-20261001T0949.json), comptes seulement, aucun texte cherché) : les 465 blocs distincts d'au moins 48 caractères du corpus réel extrait, les 17 questions et les 11 réponses enregistrées sont absents, en clair comme échappés JSON, des 120 journaux de l'instance (35,6 Mo : API, Ollama, Qdrant, ressources, audit de sécurité, démarrage du superviseur, worker d'extraction, 23 démarrages successifs) ; témoin positif : le même détecteur retrouve 55 extraits dans 20 checkpoints d'extraction. Git : `PDF/`, originaux, modèles, journaux et base ignorés ; aucun fichier suivi sous `PDF/` ou `.runtime/`, aucun poids de modèle suivi, les 10 PDF suivis sont des fixtures synthétiques. Limite : un texte reformulé ou plus court que les seuils ne serait pas détecté.

Preuve01/10/2026 (D08.4) : traversées encodées sur l'instance principale en marche (`tools/qualification/http_guards_check.py`, lecture seule, [rapport](reports/http-guards-live-20261001T1030.json), 26/26) : huit chemins `..%2f`, `%2e%2e`, `..%5c` vers le profil, la base SQLite et les jetons de l'instance, par l'interface statique et par la route des originaux authentifiée : tous refusés (404), aucun contenu sensible dans les réponses. Lien sortant de la racine : un compte standard ne peut pas créer de lien symbolique de fichier sous Windows (erreur 1314) mais peut créer une jonction ; `test_api_original_behind_junction_or_outside_storage_is_never_served` crée une vraie jonction dans le stockage des originaux vers un dossier extérieur : original refusé (409 `invalid_storage_path`), aucun octet du fichier extérieur servi, API toujours disponible ; le test échoue si le chemin n'est plus résolu avant contrôle. Chemins d'import et de déplacement dangereux refusés (`test_api_paths_reject_unsafe_input`, tests HTTP d'import et de déplacement). Fichiers malformés sur instance isolée : PDF chiffré et structure invalide en erreur explicite, page blanche signalée, l'API continuant de servir les cas suivants ([rapport](reports/library-2026-10-01.json), D02.8).

## D09 — Sauvegarde, restauration et maintien

- [x] Snapshot cohérent de SQLite, Qdrant, originaux, extractions et manifests.
- [x] Restauration dans un autre dossier avec vérification de hashes et comptes.
- [x] Une question et une ancienne citation fonctionnent après restauration.
- [x] Une migration de schéma/pipeline produit une nouvelle génération contrôlée ; retour arrière documenté.
- [ ] Registre des licences/avis de redistribution de tous les artefacts réellement livrés.

Preuves30/09/2026 : [backup peuplé21fichiers](reports/backup-first-published.json), [restore Unicode longue avec stockage Qdrant court](reports/restore-first-published-long-root-short-store-rerun.json). Dix fichiers copiés sont hashés avant rebasing ; SQLite intègre/comptes conservés et11points restaurés. Requête/ancienne citation applicatives encore NOT_RUN, provenance Tesseract limitée ; D09 global reste ouvert. Preuve01/10/2026 (D09.4) : [migration d'une sauvegarde au schéma2](reports/migration-2026-10-01-0414.json) par le code courant (schéma3), 8 anciennes citations ouvertes avant et après réindexation, révision d'extraction conservée, nouvelle génération active ; retour arrière dans [SAUVEGARDE-RESTAURATION.md §6](../docs/exploitation/SAUVEGARDE-RESTAURATION.md#6-retour-arrière-et-relocalisation). Preuve01/10/2026 (D09.3) : [question et ancienne citation après restauration](reports/restore-question-2026-10-01-0525.json) d'une sauvegarde au format courant : citation relue à l'identique, nouvelle question terminée avec citation.

## Jeu d'évaluation minimal

Préparer au moins 16 PDF synthétiques identifiés couvrant texte FR/EN, colonnes, tableaux, scan, mixte, rotations/recadrage, labels, versions et cas d'erreur ; ajouter des fixtures hostiles séparées. Leur contenu est contrôlé et leur statut synthétique visible.

Le jeu initial de 80 questions peut servir au développement. Pour la qualification de cette V2.1, préparer **200 questions** : 70 factuelles FR/EN, 30 identifiants, 24 tableaux/unités, 20 comparaisons, 16 suivis conversationnels et 40 sans réponse. Séparer **100 développement / 100 test final**, à parts égales par catégorie, par familles de documents lorsque possible. Les exemples déjà utilisés pour régler ou déboguer restent côté développement.

Le test final comporte donc 80 questions répondables et 20 sans réponse. Rapporter les effectifs, les taux observés et une incertitude adaptée ; 200 questions n'est pas une garantie statistique universelle. Un effectif insuffisant n'autorise pas à annoncer une qualification équivalente. Annotations : réponse attendue/absence, version, révision d'extraction, pages, unités de preuve requises et alternatives admises.

Une duplication massive d'un même texte pour atteindre 25 000 chunks ne suffit pas à prouver la qualité ; elle peut servir à un stress technique explicitement nommé. Le benchmark métier doit utiliser des questions et documents réellement représentatifs, autorisés.

## D10 — Décisions et cohérence de livraison

- [ ] Les trois contrôles précoces ont des preuves ou des blocages explicites ; l’environnement de développement n’est pas présenté comme la machine cible.
- [ ] Embedding choisi : essai ciblé et décision enregistrés, ou candidat officiellement non vérifiable/incompatible documenté et E5 qualifié sans prétendre avoir gagné un A/B.
- [x] Placement mémoire Qdrant et paramètres effectifs relus après création ; dépréciations traitées à la version installée.
- [x] Sources canoniques, configuration et brief complet synchronisés ; contrôles documentaires rejouables.
- [ ] Les seuls résultats annoncés correspondent à des exécutions effectives ; résultats documentaires et applicatifs restent séparés.

Preuve01/10/2026 (D10.4) : contrôles documentaires rejoués au commit `449504f` : `RAG_Local_Agents/tools/verify_pack.py` PASS sur ses 11 contrôles ([CONTROLES_DOSSIER.json](CONTROLES_DOSSIER.json) : liens locaux, syntaxe, cohérence de configuration, copie octet pour octet du profil livré et de la configuration de collection, référence SQLite FTS5, format et registre des skills, propagation des règles, exemples déterministes, brief consolidé) et `build_brief.py --check` PASS (brief synchronisé). Chaque modification de documentation canonique de ce jour a été suivie de la régénération du brief et d'un `verify_pack` vert avant commit. Limite déclarée par l'outil : inférence, OCR, serveur Qdrant, E2E et accessibilité des liens externes non exécutés par ce contrôle ; ils relèvent des autres critères.

Preuve01/10/2026 (D10.3) : schéma OpenAPI officiel du tag Qdrant v1.19.1 consulté ([QDR05](SOURCES.md)) : `on_disk` et `on_disk_payload` dépréciés au profit de `memory` ; configuration de collection migrée (vecteurs et payload `cold`, HNSW `cached`) et placement relu après création par `placement_matches`, qui accepte encore l'ancienne forme pour la collection existante de l'instance principale (W017). Sur instance isolée : collection de sondage créée avec la nouvelle forme et relue, autocontrôle complet avec une collection créée par le code courant ; aucune option dépréciée dans la configuration serveur ; tests unitaires 473/473 ([rapport](reports/qdrant-memory-2026-10-01.json)). Collection existante de l'instance principale migrée en place le 01/10 à 12:17 sur décision de l'utilisateur ([rapport](reports/qdrant-memory-migration-main-2026-10-01.json)) : mise à jour `memory` acceptée, 724 points avant et après, placement relu, index cohérent, recherche réelle vérifiée.

## D11 — Sources officielles, skills et mises à jour

- [ ] Chaque décision technique significative possède une source officielle pertinente, une date de consultation et une version/portée explicites ; aucun résultat de recherche non ouvert n'est présenté comme vérifié.
- [ ] Documentation actuelle et contrat de la version installée sont distingués ; toute mise à jour traite changements incompatibles, dépréciations, sécurité, retour arrière et tests de non-régression.
- [ ] Une affirmation de supériorité/SOTA indique protocole et limites ; une mesure éditeur n'est pas présentée comme une mesure sur la machine cible.
- [ ] Skills effectivement utilisés identifiés par nom, chemin, origine et version/hash constaté ; leurs `SKILL.md` ont été lus et leur pertinence vérifiée. Les skills manquants ne sont pas présentés comme exécutés.
- [ ] Skills projet : front matter/liens validés ; sélection et comportement vérifiés dans l'outil réel sur tâche positive et tâche hors périmètre, ou statut non testé explicite. Validation syntaxique différente de validation comportementale.
- [ ] Aucune installation massive ou exécution de script de skill tiers sans contrôle de provenance, de permissions et de dépendances ; aucun skill de développement exposé au LLM documentaire.
- [ ] Source inaccessible gérée sans invention : décision dépendante bloquée, baseline préservée, travail indépendant poursuivi ; aucune donnée privée envoyée lors des recherches.
- [ ] `SOURCES.md`, `DECISIONS.md`, `PLAN.md`, spécifications, configs, tests et brief synchronisés après les changements qui les concernent ; pas de correctif seulement décrit dans un audit séparé.

**Preuves :** registre de décision/source, diff des fichiers, références des skills lus/utilisés, résultats des tests de contrat/migration/skills et limites explicites. Ces critères concernent le travail des agents, pas des fonctionnalités réseau du produit.

## Qualification Linux (W018)

Poste de qualification Linux aarch64 : Jetson AGX Orin Developer Kit, L4T R35.4.1, Ubuntu 20.04.6, glibc 2.31, `MODE_30W` (8 cœurs en ligne), 61 Gio. Statuts permis : `NOT_RUN`, `PASS`, `FAIL`, `BLOCKED`, avec preuve liée au commit, à la configuration, au corpus et à la machine. Linux x86-64 : verrou et artefacts résolus, aucune machine de qualification à ce jour ; ses critères restent `NOT_RUN`. Tenu par le lot J8 du [plan](PLAN.md).

| Section | Statut Linux | Preuve et limite |
|---|---|---|
| D01 | PASS | D01.1 : clone neuf du commit `4d8ba68`, `.runtime` vide, `bootstrap.sh` (4 min) puis `rag.sh provision` en ligne (40 min), code 0 ; D01.2 : démarrage, `doctor`, `selftest` et injection sans réseau dans `unshare -rn` (J8 L10 et rejeu R4) ; D01.3 : aucun `latest`, 32 entrées d'artefacts Linux avec empreinte, `uv.lock` 130 paquets avec empreinte ; D01.4 : rubrique « calcul » réelle (`gpu_ready`, `gpu_in_use`) et `selftest` en CPU imposé ; D01.5 : second `up` en 0,49 s sans seconde instance, comptes identiques après `down` puis `up` ; preuves hors Git sous `.runtime/qa/j8-linux/`, [journal](journal/2026-10-02.md) |
| D02 | NOT_RUN (recette globale après W029) | PASS antérieurs : D02.1, D02.2, D02.8 (`library_check`, 7 cas). W029 sur `5ca3685` et corrections locales du 02/10 : campagne réelle finale 9/9 PASS, dont scan à 90° et reprise A3 ; `extraction_check` sur API neuve 19/19 PASS, dix fixtures/21 pages, D02.3 à D02.7, D02.9 et D02.10. DA-P02 et DA-P03 : deux tableaux contrôlés, chacun 3/3 lignes exactes, pas seulement signalées. Treize SHA stables entre les campagnes ; revue indépendante favorable bornée aux fixtures Linux. L'ancienne campagne 8 PASS/1 FAIL et l'essai interrompu restent conservés. Le gel W022 est levé par W029 ; W029-6 terminé à 21:21:43, quatre handles/208 pages, conservation et nouveaux états PASS à 21:34, revue indépendante favorable. Les quatre extractions restent partielles : une génération publiée sans perte de texte, trois retenues ; ni qualité globale du corpus ni Windows qualifiés, aucune clôture globale D02. Preuves hors Git sous `.runtime/qa/w029-20261002T165030Z/` (`ingestion-real-final-v2/`, `extraction-api-final/`, `corpus-reextract/`) et `.runtime/qa/w029-corpus-20261002T184300Z/` (sauvegarde vérifiée, sélection figée, handles, `validation/final-conservation.json`), empreintes avant/après et [journal](journal/2026-10-02.md) |
| D03 | NOT_RUN (en partie) | PASS antérieurs : D03.1 à D03.4 (`library_check`), D03.5 et D03.6 (`fault_check`, 4 cas ; rejeu R1 des sondes de port). Pilote réel du 03/10 sur `05da85c`, Linux aarch64/CPU, instance neuve et fixtures synthétiques : D03.7 citations après nouvelle version/réindex et retrait logique PASS, purge physique NOT_RUN ; D03.8 NOT_RUN, le réemploi constaté ne vaut pas migration d'embedding. D03.9 PASS pour le scénario exécuté : requête en file réelle, ancien snapshot protégé après publication partielle explicite, quatre observations sur 3,103 s puis nettoyage après fin ; retrait réévalué avant contexte, sans appel modèle. Ce n'est ni une indexation complète naturellement concurrente ni un comptage des passes GC. Six réponses réelles et une erreur attendue ; 46 empreintes stables, arrêt vérifié et données conservées, revue indépendante favorable bornée. Preuves privées `d03-pilot/runs/run-20261003T0000/` sous QA R15, résumé SHA `12bab2dad70fd21cee3f67cd4fef3431d0098715da6dd4c8dd7e0f72a8beb19f` et [journal du 3 octobre](journal/2026-10-03.md). Aucune qualification Windows ou Linux x86-64 déduite |
| D04 | FAIL (en partie) | PASS : D04.1 (recherche sans modèle, `selftest`), D04.2 et D04.8 (`scope_check`, 10 contrôles, comptes identiques à Windows), D04.3 (zéro fuite sur les 94 questions DEV évaluées, 6 sur 100 non résolues, et sur 100 réponses), D04.4 (preuve au top 5 et dans le contexte pour 14 des 15 questions « DA-P0x, et non DA-P0x0 », la quinzième, DEV-044, non résolue ; `l8/d04-4-identifiers.txt`), D04.5 et D04.6 (tests). D04.7 : aucune réponse fabriquée sur les 20 questions DEV sans réponse dont l'identifiant figure au document (grille D05 jugée, 20/20 abstentions justifiées), mais l'indice lexical de couverture n'en signale que 16 sur 20 (W026) ; objectif Recall@10 sur le jeu final : NOT_RUN (jeu final non exécuté sous Linux) ; preuves hors Git sous `.runtime/qa/j8-linux/`, [journal](journal/2026-10-02.md) |
| D05 | NOT_RUN (jeu final) | PASS : D05.1 à D05.4 (100 générations réelles, aucun appel caché, relances dans la conversation, compteur de jetons égal à `prompt_eval_count` sur 100/100). Jeu DEV (diagnostic, grille jugée par deux juges et un arbitre, assistant non expert) : exactitude 67/80 = 0,838 [0,742 ; 0,903] pour une cible de 0,85 sur le jeu final, abstention correcte 20/20, assertions soutenues 196/223 = 0,879 (cible 0,95), intégrité des citations et pages 195/195. Mesure de D05 sur le jeu final : non exécutée (décision C) ; preuves hors Git sous `.runtime/qa/j8-linux/`, [journal](journal/2026-10-02.md) |
| D06 | NOT_RUN (en partie) | PASS : D06.1 à D06.4, D06.7, D06.8 et D06.11 (Playwright 1.63, Chrome Headless Shell 153.0.8010.12, API réelle, instance isolée : 21 scénarios réussis, 1 ignoré, `l9/`) ; D06.10 (gardes statiques de `ui-guards.test.ts`, tests unitaires web 217/217 au commit `c32b759`, 223/223 au commit `419b526`) ; barre supérieure sans recouvrement de 768 à 1366 px (rejeu R6). R15-1 le 02/10 sur `5ca3685` et changements locaux : 224 unités PASS, typecheck/build PASS ; six scénarios sur API isolée réelle PASS (clavier, deux tailles desktop, dépôt/cancel, lecture-recherche-passage, scopes page/bloc), un état négatif readiness intercepté PASS distinct d'une panne backend réelle ; captures relues. Complément du 03/10 sur base `05da85c` et changements locaux : build du premier gel contrôlé et 31 cas R15-3 PASS stricts sur API native QA isolée, zéro génération modèle ; 19 captures principales et les preuves d'arrêt/conservation relues, avis indépendant favorable borné. Budget 14 pages/300 % : allocations et libération PASS, capture blanche initiale non probante pour la fin du dessin ; six images de trace relues établissent un dessin ultérieur page11/300% et pages1/3/12, sans attribuer le blanc ni qualifier toutes les positions. Pas d'oracle console universel pour les 31. Dix lifecycle et une génération NOT_RUN. Les cinq compléments RB5 V2 ont réellement donné 2 PASS/1 FAIL/2 NOT_RUN : focus de confirmation hors dialogue au deuxième Tab, destination inconnue ; titre tronqué également constaté. Au relevé du 03/10 à 02:26 UTC : correctifs implémentés et 277 unités/typecheck/lint PASS, pas encore de nouveau build ou de recette navigateur qualifiée ; état actualisé dans le complément D06 ci-dessous. Le succès des 31 sur l'ancien gel ne qualifie pas ce delta. Préparations, rouges, arrêt et conservation détaillés au journal. D06.5, D06.6 (sélection OCR) et D06.9 restent sans recette. Preuves hors Git sous `.runtime/qa/j8-linux/` et `w029-20261002T165030Z/web-e2e-*/`, [journal du 2 octobre](journal/2026-10-02.md) ; complément R15-3 sous `.runtime/qa/r15-editorial-20261002T191600Z/frontend-quality/run-20261003T0048/`, [journal du 3 octobre](journal/2026-10-03.md) |
| D07 | BLOCKED | La recette exige un hôte de 16 Go physiques au plus en calcul CPU ; ce poste a 61 Gio, sans moyen de le restreindre sans droits d'administration. Jugé à part : D07.6 PASS (traitement en pause conservé jusqu'à reprise explicite après `down` puis `up`). Pilote CPU indicatif : premier mot en 145,5 s sur un contenu nouveau de 2 959 tokens (cible de recette : 45 s) ; [journal](journal/2026-10-02.md) |
| D08 | PASS | D08.1 (sorties non loopback bloquées, `unshare -rn` avec interface piège), D08.2 (aucune requête externe ni tentative DNS de télémétrie après `ORT_DISABLE_TELEMETRY`, rejeu R4), D08.3 (`http_guards_check`), D08.4, D08.6 (Playwright `hostile-markup`), D08.7 (`log_privacy_check`). D08.5 : aucune adoption de la valeur injectée sur 16 passages d'`injection_check` (GPU et CPU ; 999 absent dans 12 réponses, cité pour être écarté dans 4, classement manuel, l'outil les renvoyant en relecture humaine) ; aucune exfiltration sur les 7 passages observés hors ligne (0 trame, 0 requête DNS, 0 socket hors loopback) ; aucun élargissement sur les 7 passages de la branche « périmètre », dont 4 avec témoin positif (le document hors périmètre sort sur toute la bibliothèque, pas dans le périmètre de la question). Limite : génération non déterministe (température 0,2), effectifs réduits ; preuves hors Git sous `.runtime/qa/j8-linux/`, [journal](journal/2026-10-02.md) |
| D09 | PASS (D09.4 BLOCKED) | PASS : D09.1 à D09.3 (sauvegarde, restauration dans une autre racine, question et ancienne citation après restauration). D09.4 BLOCKED : aucune sauvegarde au schéma 2 sur ce poste. D09.5 PASS dans le cadre de l'usage interne décidé par l'utilisateur ([W030](DECISIONS.md#w030-usage-interne--registre-des-licences-sans-validation-de-redistribution)) : l'inventaire recense tous les composants installés par `provision`, avec licence déclarée, avis présents et manques signalés ; une redistribution hors de l'organisation rouvrirait le critère ; preuves hors Git sous `.runtime/qa/j8-linux/`, [journal](journal/2026-10-02.md) |
| D10 | FAIL (en partie) | PASS : D10.3 (Qdrant 1.19.1 : collection créée puis relue, `placement_matches` vrai, `l7/iso/d10-3-qdrant.json`) ; D10.4 (contrôles J9 et finaux W029 : `verify_pack` 11/11 à 18:26 le 02/10, 29 empreintes, `check_docs` 7/7 et brief synchronisé). D10.1 : défauts Q-PDF J8 corrigés sur fixtures W029, campagne réelle finale 9/9 et API neuve 19/19 PASS ; W029-6 vérifié pour la réextraction, la conservation et les états de publication, qualité globale toujours non qualifiée (voir D02 ci-dessus) ; régression finale 1442 PASS/10 SKIP et relectures indépendantes PASS ; Q-CPU pilote seulement, D07 BLOCKED ; Q-SEARCH DEV réussi, jeu final NOT_RUN. D10.5 : écarts documentaires J9 corrigés (dénominateurs D04.3/D04.4, preuve de D06.10, références GPU W025, références stabilisées, README et CHANGELOG). Sortie web historique `36824e2` retrouvée à 17:49 : 224 PASS ; sortie Python annoncée 1431 PASS/12 SKIP toujours non retrouvée et signalée non vérifiable, jamais reconstituée. D10.2 NOT_RUN : aucun comparatif d'embedding Linux ni qualification E5 sur le jeu final. Preuves hors Git sous `.runtime/qa/j8-linux/`, `j11-gpu-2026-10-02/`, `w029-20261002T165030Z/` et `w029-corpus-20261002T184300Z/` ; [journal](journal/2026-10-02.md) |
| D11 | FAIL (en partie) | PASS bornés : D11.5 (29 fichiers au registre, empreintes et format contrôlés à 18:05 le 02/10, dont reprise de densité du skill d'ingestion ; comportement `NOT_RUN` explicite) ; D11.3 (protocole et limites GPU, références/SHA des deux essais d'étude et facteur 13,6 rattaché au passage 2 dans W025 ; pas une preuve D07, copie QA encore à arbitrer) ; D11.7 (sources inaccessibles sans substitution, voies non essayées non qualifiées ; confidentialité des recherches fondée sur les journaux). D11.1 : W018 cite désormais LNX01–19/LNX21/LNX22 ; J8S02 complétée officiellement le 02/10 à 17:36, après le correctif ; `webbrowser` W023 complété actuellement par [WB01/WB02](SOURCES.md#complément-actuel-cpython-webbrowser-et-w023-d111-2-octobre-2026), CPython local 3.12.14 comparé octet pour octet au commit officiel ; consultation actuelle du 02/10, aucun navigateur exécuté. La date historique de consultation ONNX reste non consignée (J8S01). D11.2 : retours arrière W023/W025/W026 explicités ; releases/avis `jetpack5`, `zstandard` et torch `+cpu` consultés actuellement ([D11S01–D11S08](SOURCES.md#consultation-actuelle-des-releases-et-avis-de-trois-dépendances-linux-d112-2-octobre-2026)), versions/artefacts confrontés ; risque hôte L4T 35.4.1 dans les plages de bulletins NVIDIA, mise à jour OS/pilote hors mandat et non engagée. Consultation distincte de l'historique, aucune certification d'absence de vulnérabilité ni migration qualifiée. D11.4 : lectures J0–J11/J8 non reconstituables ; [relevé W029/R14-1/R15-1](reports/skills-usage-2026-10-02-w029.json) et [continuation W029-6](reports/skills-usage-2026-10-02-w029-corpus.json) distincts de cet historique ; [continuation R15-2/D11-1](reports/skills-usage-2026-10-02-r15-d11.json), lectures explicites sans qualification de découverte native. D11.6 : limites de provenance et plateforme Playwright (TOOL02), pnpm 12.8.1 involontaire (TOOL03) ; absence de consignes de développement vérifiée par huit nouveaux tests de `ContextBuilder` et du corps Ollama, inclus dans 74 PASS ; mutant en mémoire détecté après correction de l'oracle mutable initial (deux FAIL attendus), contrôle normal vert et revue indépendante favorable. Borne : garde `Path.open` sur cinq fichiers temporaires après initialisation, compteur caractères/4 et HTTP doublés ; pas de modèle réel, de contrôle global des lectures disque ou de découverte native. Provenance des outils tiers toujours distincte, D11.6 non clos. D11.8 : corrections J9 appliquées (statuts W018/W020/W024/W025, J11.9, journal/index et skill Linux) ; suivi W029 actualisé, contrôles documentaires finaux PASS à 18:26 ; lot W029/R14-1/R15-1 publié (`635d74a`). Revue J9 et contrôles actuels au [journal](journal/2026-10-02.md) et au [plan](PLAN.md) |

Complément D06 du 03/10 à 03:33 UTC, présentation actualisée à 04:04 : après les correctifs focus/titre, 277 tests unitaires, typage, lint et nouveau build de 43,37 s PASS. La recette de cet export est FAILED sur le garde QA d'identité de processus : 28 cas qualifiés, deux résultats bruts import/périmètres non qualifiés, dépôt NOT_RUN. Arrêt, conservation et absence des 117 identités vérifiés indépendamment ; aucune assertion frontend fautive établie par ce refus. La mention historique « pas encore de nouveau build ou navigateur qualifié » dans la ligne D06 décrit le relevé de 02:26 : elle ne s'applique plus au build, mais la recette navigateur complète reste non qualifiée. Cause exacte inconnue, reprise instrumentée sans retrait de protection ; RB5, sonde du correctif et les onze cas lifecycle/génération restent requis. Preuves et réserves de rendu au [journal du 3 octobre](journal/2026-10-03.md#recette-interrompue-et-diagnostic-du-garde--03150333-utc), action R15-3-Q01 au plan ; D06 global et cases Windows inchangés.

Complément D06 du 03/10 à 04:50 UTC, précision de provenance à 04:58 : la reprise0415 sur le même export contrôlé reste rouge, avec 21 cas qualifiés sur 31. L'interruption initiale et le refus du contrôle d'arrêt sont distincts ; le déclencheur de KeyboardInterrupt n'a pas été enregistré. Les 88 identités sont absentes lors des contrôles ultérieurs root/B, les données conservées et les sources/export inchangés ; ce constat ne transforme pas le résumé en succès. Les 19 captures principales ont été examinées, mais la géométrie est incomplète et le témoin page11/300 % est blanc. Préparation d'une attente QA de terminaison sous identité stricte et d'un journal privé du signal, sans modifier le produit ni les refus. Voir les [preuves et la revue indépendante](journal/2026-10-03.md#interruption-du-run0415-et-arrêt-constaté-séparément--04230439-utc) et R15-3-Q01/Q02 au plan. RB5 strict, sonde modale et onze cas restent à exécuter sur une recette réellement qualifiée ; D06 global et cases Windows inchangés.

Complément D06 du 03/10, résultat natif à 05:21 et revue à 05:35 : V2 sur l'export inchangé reste FAILED, avec seulement onze cas éditoriaux qualifiés. Le refus d'exécutable attendu inconnu intervient avant enregistrement du candidat ; son identité et son état restent inconnus. Quatre pidfds POLLIN, contrôle final original et STOPPED, puis absence stricte des 45 identités consignées, conservation et sources/export relus indépendamment ; ces preuves ne qualifient pas les 31. L'attente n'ajoute pas de signal, contrairement au cleanup/down originaux qui gardent leurs signaux. Dix-neuf captures partielles examinées ne couvrent ni géométrie complète ni modale. Incident séparé de lecture de cookies dans la revue, session QA inutilisable après arrêt de son API mémoire ; exposition non effacée. [Résultats, confinement et limites](journal/2026-10-03.md#recette-v2-rouge-et-confinement-de-lincident-de-revue--05190543-utc). V3 en préparation, RB5/sonde et onze cas encore requis ; aucun critère global, Windows ou D07 clôturé.

Complément D06 du 03/10, native terminée à06:33 et revues06:40–06:48 : V3/QA0612 FAILED, avec30 cas stricts/retry0 qualifiés et drop-import commencé mais interrompu, sans résultat terminal. Arrêt des116identités consignées, quatre pidfds POLLIN et conservation contrôlés indépendamment ; huit jobs ready/un paused/zéro query, aucune reprise. 49PNG réellement vus par B, 24par root : captures nominales lisibles, mais lecteur blanc page11/14 à300% ; allocation canvas≠fin de peinture, ni réussite paint ni défaut permanent certifiés. Les mesures CropBox/rotations et offsets Unicode passés restent bornées à leurs assertions ; pas précision exhaustive, OCR spécifique, SSE/génération réels ou modale ajoutés. Budgets canvas ne valent pas D07. V4 du contrôleur en préparation avec refus stricts, primaire/cleanup distincts ; RB5/sonde et onze cas toujours requis. [Résultats et limites](journal/2026-10-03.md#recette-v3-rouge-et-revues-indépendantes--06330655-utc). Aucun critère global, Windows ou D07 clôturé.

Complément D06 du 03/10, recette V4 terminée à 07:53:17 et terminal constaté
à 07:58:51 UTC : sur le nouvel export contrôlé, QA0732 qualifie les 31 oracles
stricts sans retry/skip/flaky, zéro query modèle. Arrêt et conservation relus
indépendamment par C (rapport cb678057), avis de rendu B 826924ce et reçu root
4e98972d lus à 08:19 ; 118 PID consignés absents, neuf jobs ready, données et
sources conservées. Root a vu 19 captures
principales et le PNG page 11/14 à 300 % : nominal à 100 % lisible, capture à
300 % toujours blanche, donc peinture non démontrée. Un doute de texte coupé
est levé après réouverture du PNG à sa résolution originale, pas après un
changement CSS. Les cinq régressions, la sonde modale, la preuve de peinture
et les onze cas complémentaires restent requis ; les quatre recettes rouges
historiques ne sont pas reclassées. [Preuves nouvelles et limites](journal/2026-10-03.md#recette-v4-terminale--07430802-utc).

Complément D06 du 03/10, replay ciblé terminé à 08:37:49 UTC : RB0828
sur le même export termine FAILED, deux PASS/retry0, un FAIL/retry0 et deux
cas sans tentative. L'échec est le clic de titre ligne245 : locator descendant
ambigu à deux h2, pas un échec Échap ni un nouveau défaut produit prouvé.
Première interprétation root rectifiée avant patch ; recette rouge conservée.
Arrêt/conservation déclarés, contrôle indépendant terminal en cours ; neuf
PNG relus séparément par B avec erratum d'attribution prioritaire.
La sonde modale n'a pas été lancée. Correction QA séparée et revue requises,
sans recompilation ni assouplissement d'assertion. Q05 V2 a seulement un avis
de préparation favorable et 132 tests purs, aucun essai réel de peinture.
[Résultats et reprise](journal/2026-10-03.md#replay-ciblé-rouge-et-correction-de-son-diagnostic--08360845-utc).
Ni les cinq cas complets, ni D06 global/Windows/D07 ne sont acquis.

Complément D06 du 03/10 à 09:18 UTC : le contrôle terminal RB0828 est achevé,
favorable dans sa portée à l'arrêt et à la conservation, sans reclasser son
échec navigateur. Première fenêtre lifecycle/génération0914 : aucun cas
exécuté, FAILED_PRESERVATION à 09:14:40, contrôle QA refusant des caches Python
et le marqueur Qdrant créés dans le miroir. Les 697 copies nommées restent
inchangées ; arrêt déclaré et quatre identités natives absentes selon le
contrôle C ; avis terminal 310f3505 entièrement lu et rehashé par root.
Ce contrôle ne porte pas sur la conservation SQL intégrale. Ce refus ne prouve ni une régression
produit ni les onze parcours. [Faits et reprise](journal/2026-10-03.md).
D06 global, génération, peinture300, modale, Windows et D07 restent ouverts.

Complément D06 du 03/10, relevé à11:46 UTC : RB1032 a passé ses cinq cas
stricts/retry0 sur l'export corrigé ; arrêt et conservation revérifiés
indépendamment sur les27 identités des six labels, premier reçu incomplet
conservé. Treize captures réellement vues par B, six par ROOT. La sonde
complémentaire reste FAILED : collision chemin/objet binding reproduite
dans le vrai code QA avec doubles, V2 préparée (33 tests purs), revue et
nouvelle recette modale requises ; aucun succès pending/trois tailles déduit.

F04 run1050 termine à11:35:25, EXIT0, onze cas stricts sans retry/skip/flaky,
dont une vraie génération et sa citation enregistrée. Ancienne version
consultée, réindex/reimport, erreurs backend PDF et seuil64KiB isolé exercés.
La révision d'extraction est réemployée : aucune ancienne révision distincte
qualifiée. Dix PNG originaux examinés par ROOT ; revues indépendantes
terminales/rendu en cours. L'oracle d'alerte du PDF corrompu peut lire le
message du PDF chiffré précédent ; backend et ligne bibliothèque sont
vérifiés, état terminal de sa carte Suivi non établi. Correction/rejeu ciblés
requis avant qualification complète de cet oracle. Q05 peinture300 reste
non exécuté. Aucun seuil, critère global D06, Windows ou D07 modifié.
[Preuves, limites et suite](journal/2026-10-03.md#recette-f04-terminale-et-diagnostic-modal--relevé-1146-utc).

Complément D06 du 03/10, relevé à12:18 UTC : revue F04 indépendante C
favorable dans sa portée : arrêt132 tuples, données/sources/export conservés,
citations Unicode/spans/hash vérifiées sur dix blocs. Deux témoins
runtime-before absents, révision distincte non observée et oracle de carte
corrompue insuffisant restent réservés. Correction QA préparée et tests purs
rouges/verts ne constituent pas une nouvelle preuve UI.

Q05 a désormais une tentative native FAILED avant authentification/browser,
sans peinture qualifiée. Arrêt standard CLI de cette seule QA à12:14:21,
EXIT0 et douze tuples actuellement absents selon ROOT ; revue terminale
indépendante C favorable bornée, reçue à12:23:46 et relue par ROOT à12:25.
96 originaux/extractions égaux au vrai avant CLI, SQLite neuf jobs ready
et zéro query conservé. Ce nettoyage n'efface pas le FAILED ni ne qualifie
Q05/D06. Aucun seuil, critère global, Windows ou D07 modifié.
[Exécution, conservation et prochaine action](journal/2026-10-03.md#q05-rouge-et-arrêt-ciblé--relevé-1218-utc).

Complément D06 du 03/10 à12:37 UTC : les dix PNG F04 sont également relus
indépendamment par B ; réserve du rattachement de l'erreur corrompue confirmée.
L'oracle privé corrigé reçoit l'avis C favorable préparatoire, et la modaleV2
l'avis B favorable préparatoire. Aucun rejeu navigateur, nouveau rendu
de carte terminale ou parcours pending/trois tailles prouvé par ces revues.
F04, modale, Q05 et D06 restent ouverts dans leurs périmètres restants.
[Revues, preuves et prochaine action](journal/2026-10-03.md#q05-rouge-et-arrêt-ciblé--relevé-1218-utc).

Complément D06 du 03/10 à13:47 UTC : Q05/run1315 atteint l'authentification
et produit deux PNG page11/zoom300. Les trois ancres natives sont réellement
lisibles selon ROOT et C ; ce résultat visible ne prouve ni isolation du
canvas ni fin de RenderTask. La recette reste FAILED : warning1 puis
transportErrors3/guardErrors3 refusés ; phase exacte inconnue et samples/
ROI/budget réel non persistés. Arrêt et conservation indépendants C
conformes dans leur portée :20 tuples absents, neuf jobs ready/zéro query,
96 originaux/extractions et sources243/13 conservés. Instrumentation en cours
de préparation, pas de replay implicite ni de conversion des captures en PASS.

La sonde F04 de lecture des deux cartes d'erreur est préparée :39 tests
purs PASS au gel B, aucune nouvelle UI exécutée. Revue C achevée ensuite :
réserve C01 confirmée, refus tardif correctement aborté mais ignoré par
le verdict de qualification. Delta ROOT distinct :45 tests purs PASS après
rouge discriminant, contrôles ciblés au vert et avis C favorable préparatoire ;
aucun succès navigateur/API ou nouvelle carte réelle déduit de ces doubles.
La modaleV2 reste également à qualifier sur sa chaîne native. Aucun seuil,
critère global D06, Windows, D07 ou qualification finale modifié.
[Preuves et prochaine action](journal/2026-10-03.md#q05--captures-réelles-et-refus-du-caller-relevé-1347-utc).
[Correction QA et limites](journal/2026-10-03.md#f04--correction-du-refus-tardif-de-la-sonde-qa-relevé-1408-utc).

Complément D06 du 3 octobre à 15:19 UTC : le défaut de qualification tardive
est aussi reproduit dans la sonde modale historique ; la requête est bloquée,
sans transmission au backend. Sonde corrigée revue sur tests purs ; nouvelle
composition en revue, aucun parcours natif supplémentaire exécuté. Q05 a
une instrumentation revue et une enveloppe en revue, pas un nouveau résultat
de peinture. F04 attend encore sa lecture native des deux cartes. Critères,
seuils, D06 global, Windows et D07 inchangés ; états et prochaines actions au
[plan](PLAN.md#r15-3--reprise-des-contrôles-qa-relevé-du-3-octobre-à-1519-utc),
preuves au journal relié par ce plan.

Complément D06, relevé du 3 octobre à 16:02 UTC : la nouvelle exécution
`run-20261003T154834Z` donne cinq cas stricts PASS, sans retry, skip ni flaky,
mais la sonde modale échoue à `nominal_1366`. Le wrapper rapporte un arrêt
ciblé et une conservation bornée ; la revue terminale indépendante reste en
cours. L'aide frontend sur la publication fait l'objet d'une correction
rédactionnelle distincte. Aucune case ou exigence globale n'est modifiée ;
voir l'[état courant](PLAN.md).

Complément D06 du 4 octobre, relevé à 01:59 UTC : le chantier QA F04 E2
termine à 01:33:59, sortie 0 observée par ROOT. Onze scénarios stricts
sur l'API et le modèle réels, sans retry ni skip ; cartes d'échec liées à
leur fichier, générations/versions et limite64KiB isolée exercées. Arrêt et
conservation bornée vérifiés indépendamment B ; dix PNG vus par C, trois
inclus vus par ROOT ; dix blocs synthétiques recomputés pour hash UTF-8,
spans et provenance. Avis final A favorable au critère exact de l'action
F04, désormais `VALIDATED_BOUNDED` au plan ; aucun seuil ni case globale
modifié. Révision d'extraction réemployée, spans de bloc entier, pas R2
archivée distincte ou sélection intra-bloc. Les données QA sont déclarées
préservées par le CLI possédé et les contrôles du scénario ; B/A n'ont pas
refait une inspection SQL ou de tous les blobs. Console exhaustive,
peinture300, modale/pending/trois tailles, ancres, OCR sélection, SSE,
Windows et qualification physique16Go restent ouverts. L'échec E est
conservé, l'instance utilisateur reste arrêtée. [Preuves nouvelles et limites](journal/2026-10-04.md#terminal-f04-e2-et-relectures-relevé-0157-utc).

Complément D06.9 Linux du 5 octobre 2026 : **PASS technique borné** sur
la seule fixture synthétique QLONG-14 déjà indexée, `qwen3.5:2b` réel sur
GPU du Jetson61Gio, base `1e20a58` et correctif local daté. Une recette
strictement réussie sans retry/skip/flaky : document Prêt et identité
corroborée, préfixe UI visible avant terminal (« # », pas un premier mot
utile qualifié), coupure SSE réelle, reprise après ID6 sans nouvelle
question/génération ni doublon, réponse limitée, seconde génération annulée
après sept deltas, tâche et bail libérés. Avis indépendant favorable dans
cette portée, arrêt et conservation bornée vérifiés ; deux essais FAILED
conservés. Les cases Windows ci-dessus, D06 global, qualité métier et D07
ne changent pas. L'ancien relevé D06 du tableau Linux est historique pour
D06.9 ; ce complément porte son résultat plus récent.
[Commandes, preuves, empreintes et limites](journal/2026-10-05.md#d069--flux-progressif-reconnexion-et-annulation).

## Rapport final exigé

Pour chaque D01–D11 : statut, commande, commit, configuration, environnement, corpus, résultat et chemin de preuve. Ajouter un tableau des métriques avec dénominateurs, mesures chaud/froid, limitations et écarts. Résumer uniquement ce qui est réellement exécuté ; ne pas substituer un discours de conformité aux résultats.

**Terminé = application exploitable + preuve bout en bout + qualification sur la cible déclarée + défauts/limites résiduels explicités.**
