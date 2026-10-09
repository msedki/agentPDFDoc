# Baseline technique du projet — 9 octobre 2026

**Rôle :** état de référence avant les axes de correction ou de rationalisation · **Propriétaire :** intégration de la baseline et relecture indépendante · **Statut :** Vivant, baseline consolidée — analyse uniquement · **Référence :** HEAD `75df7600ba73283c3a77e6fa8244a2f1f82cf1cf`, avec les 29 fichiers suivis modifiés et les 7 fichiers non suivis présents au début de l'observation · **Mis à jour :** 2026-10-09 14:38 (UTC) · **Source de vérité :** ce rapport pour l'instantané du 9 octobre ; code et preuves identifiés pour chaque fait · **Remplace :** aucun document

## 1. Portée et niveau de preuve

La demande d'analyse du 9 octobre remplace, pour cette session, l'exécution du chantier R26. La baseline examine l'arbre de travail réel, ses dépendances installées, la base SQLite existante, les artefacts locaux, Git et les processus/ports observables. Elle ne corrige aucun défaut, ne modifie aucun comportement, ne recrée pas de plan et ne clôt aucun critère du [PLAN](../PLAN.md) ou de la [DoD](../DEFINITION_OF_DONE.md). Le lot Linux non commité reste distingué du code publié.

La couverture est organisée par composants et chemins critiques, avec des sondes discriminantes et les suites de contrôle indiquées en section 8. Elle ne signifie pas que chaque branche est certifiée, ni que l'absence de vulnérabilité, de code mort ou de régression est démontrée. Les tests avec doubles sont explicitement séparés du runtime natif. Aucun original privé, contenu de question ou texte de passage de la base existante n'est reproduit dans le rapport.

| Axe | Travail effectué | Limites |
|---|---|---|
| DB, API et pipeline | Schéma/migrations, publication, scopes, retrieval, contexte, SSE, ingestion, sessions ; agrégats et plans SQL de la base existante ; sondes SQLite synthétiques | Aucune migration, réindexation, génération ou extraction réelle lancée |
| Frontend | Navigation, état, transport, permissions, lecteur, provenance, build et tests ; contrôle de l'export et des assets présents | Aucun build ni navigateur E2E lancé ; rendu actuel non certifié |
| Distribution et exploitation | Fabrication, installation, mise à jour, rollback, retrait, sauvegarde, supervision, provisionnement et inventaires | Aucun kit fabriqué/installé, aucune sauvegarde/restauration native exécutée |
| Git, runtime et ressources | Références locales et distantes, changements préexistants, chemins résolus, versions, PID/ports, CPU/RAM/disques | Services étrangers laissés hors périmètre ; application arrêtée |
| Validation indépendante | Relecture des faits, des rapports d'axes et de la consolidation par un agent non auteur | Avis sur la fiabilité de la baseline, jamais GO produit ni clôture de DoD ; preuve `validation.md` |

Instructions appliquées : `AGENTS.md`, `CLAUDE.md` et leurs adaptateurs sous `RAG_Local_Agents/`, brief via ses sources canoniques, spécifications, configuration, décisions pertinentes, plan et DoD. Aucun autre fichier d'instructions local n'a été trouvé dans les zones examinées par la recherche ciblée, hors dossiers générés et dépendances.

Skills utilisés selon leur périmètre : `project-documentation`, `hybrid-rag-api`, `pdf-ingestion-windows` pour les invariants communs du pipeline, `pdf-workspace-web`, `linux-rag-runtime`, ses invariants référencés de `windows-rag-runtime`, `linux-offline-kit` et `security-best-practices` pour la partie sécurité demandée. Le skill `backend-patterns` concerne une architecture SQLAlchemy/PostgreSQL qui n'est pas celle de ce dépôt ; les skills de design, de comparaison d'embeddings et d'entraînement OCR n'ont pas été appliqués. Aucun manque de compétence indispensable n'a nécessité de créer un nouveau skill.

Les preuves de session sont conservées sous `.runtime/qa/baseline-20261009/`, sur la SD et hors Git : rapports des axes, scripts de sondes, résultats JSON, logs/JUnit, inventaires, empreintes et relecture. Les seuls fichiers destinés à être conservés comme livrable documentaire sont ce rapport et les preuves utiles ; les dossiers temporaires propres aux vérifications sont retirés après leur dernier usage. Les anciennes preuves QA ne sont pas purgées.

## 2. État Git de référence

| Élément | Observation vérifiée |
|---|---|
| Racine | `/home/safae/Bureau/agentPDFDoc`, dépôt Git à la racine |
| Branche et HEAD | `main`, `75df7600ba73283c3a77e6fa8244a2f1f82cf1cf` |
| Dernier commit | 7 octobre 2026, 14:46:48 Africa/Casablanca : « R26 : 4B par défaut, lecteur, Qdrant hors du programme, textes d'installation et provenance de l'interface » |
| Remote | `origin`, URL privée autorisée `https://github.com/msedki/agentPDFDoc.git`, identique en fetch/push |
| État distant réellement interrogé | `git ls-remote --heads --tags origin` retourne uniquement `refs/heads/main` au même SHA ; aucun écart à cet instant, aucun tag distant retourné |
| Références locales | Une branche locale `main`, suivi `origin/main` au même SHA, aucun tag ; un seul worktree ; diff indexé vide à l'entrée |
| Arbre initial | 29 fichiers suivis modifiés, 7 fichiers non suivis ; 11 308 lignes ajoutées et 998 retirées dans le diff des fichiers suivis |
| Identité locale | Auteur/committer configurés : `MOHAMED SEDKI <mohamed.sedki@live.fr>` |
| Outil | Git 2.25.1 réellement exécuté |

La vérification distante est un `ls-remote`, sans fetch, pull, changement de branche, indexation, commit, push, reset ou nettoyage Git. La concordance du remote est datée et ne garantit pas qu'il ne changera pas ensuite. Preuves : `git-status.txt`, `git-branches.txt`, `git-tags.txt`, `git-log.txt`, `git-diff-stat.txt` et `initial-state.json`.

Les changements préexistants forment plusieurs ensembles, conservés séparément dans l'observation :

- Kit Linux : `tools/dist/{build_kit,linux_install,linux_kit,linux_profiles,notices}.py`, `tools/dist/install.sh`, `rag.sh`, quatre suites de distribution et trois suites runtime ; nouveaux `kit_guide.py`, `make_icon.py`, icône SVG, modèle du guide, `tests/unit/conftest.py`, tests du guide et de documentation Linux.
- Suivi et documentation du kit : skill `linux-offline-kit`, registre, décisions, journal du 7 octobre, CHANGELOG, README, index et références sous `docs/`.
- Modifications documentaires antérieures également présentes : `apps/web/README.md`, journal du 2 octobre et parties du README racine. Leur provenance est décrite dans le journal du 7 octobre ; elles ne sont pas assimilées à des changements de cette baseline.

L'historique proche explique l'état : `78ec95c` a publié les réserves Linux R26 le 6 octobre ; `75df760` a publié le lot stable du 7 octobre en excluant l'installateur/fabricant/guide encore en correction et les modifications documentaires antérieures étrangères au lot. Le code backend/frontend stable est donc publié, tandis que le kit Linux et sa documentation locale continuent d'évoluer dans l'arbre observé. Le plan garde R26-KIT-02 phase 2 et R26-KIT-04 en cours.

Les exclusions `.gitignore`/`.dockerignore` couvrent corpus `PDF/`, runtimes, venv, modèles, données SQLite, snapshots, secrets et résultats bruts. `.gitattributes` conserve les octets avec `* -text`. Aucun workflow suivi sous `.github/` n'est présent ; une éventuelle CI externe n'a pas été interrogée. `git diff --check` échoue sur deux détails préexistants : espace de fin dans `RAG_Local_Agents/SKILLS.md:75` et ligne vide finale de `tests/unit/test_dist_linux_install.py:3985`.

## 3. Architecture effectivement implémentée

Le produit est un monolithe modulaire local avec trois services natifs supervisés : FastAPI, Qdrant et Ollama. L'ingestion lourde tourne dans un processus enfant dédié. L'export Next.js est servi par FastAPI depuis `apps/web/out`, sur la même origine que REST, SSE et les originaux. Il n'existe ni serveur Next requis à l'exploitation, ni PostgreSQL/SQLAlchemy dans la couche documentaire, ni Redis/Celery, ni agent/outillage shell fourni au LLM du produit.

| Composant | Responsabilité et flux réel | Références source |
|---|---|---|
| Lanceur/runtime | Profil → contrôle loopback et ressources → verrou → Qdrant → Ollama → API ; état et identités persistés ; arrêt des seuls groupes possédés | `rag.sh`, `rag.ps1`, `services/runtime/cli.py:80`, `supervisor.py:557`, `posix_process.py:195` |
| Métadonnées | SQLite autoritaire : versions, révisions, générations, jobs, preuves et événements | `services/api/db.py`, trois migrations sous `services/api/migrations/` |
| Ingestion | PDFium précontrôle géométrie/texte/raster ; Docling natif ou structuré et Tesseract CLI régional ; fenêtres/checkpoints, provenance et erreurs persistées | `services/ingestion/{preflight,pipeline,docling_adapter,checkpoint,worker}.py` |
| Indexation | Génération staging → chunks/sources et embeddings → Qdrant `wait=true` et vérification → publication SQLite ; ancienne génération conservée pour les citations ; nettoyage différé | `services/api/indexing.py`, `reconcile.py`, `retrieval.py` |
| Recherche | Scope résolu depuis SQLite avant les top-k ; lexical FTS5/BM25 et dense ONNX/Qdrant ; RRF, déduplication, expansion contrôlée, couverture finale des identifiants | `services/api/scope.py`, `retrieval.py`, `context.py` |
| Réponse | Tokenizer local de Qwen, budget de preuve/sortie/marge ; génération Ollama ; sources persistées avant deltas ; événements monotones, reprise et annulation | `services/api/context.py`, `ollama.py`, `query.py`, `claims.py` |
| Interface | App Router exporté : accueil et `/workspace/` ; bibliothèque, lecteur, analyse ; Zustand pour UI et TanStack Query pour données serveur ; PDF.js et assets locaux | `apps/web/next.config.mjs:3`, `src/components/workspace.tsx`, `src/lib/{store,api,stream,pdfjs}.ts` |
| Sécurité | API loopback mono-utilisateur, lien d'ouverture à usage unique, session mémoire, cookie HttpOnly, CSRF, contrôle Host/Origin et jeton local d'administration | `services/api/main.py:53`, `security.py`, `apps/web/src/components/session-gate.tsx` |
| Distribution | Kits Windows et Linux distincts ; Linux depuis les fichiers du commit et des artefacts locaux contrôlés ; venv recréé, programme séparé des données, update/rollback/retrait gardés | `tools/dist/{build_kit,linux_kit,linux_install,linux_profiles}.py`, `install.sh` |

La frontière HTTP est `/api/v1` : bibliothèque/import/move/reindex/retrait logique ; versions/fichier/outline/blocs ; search/queries/events/cancel/citations ; jobs/pause/resume/publication partielle ; état des ressources ; administration quiesce/resume/session. `health` est une liveness publique légère, `readiness` vérifie stores/artefacts/modèle sans être une preuve du parcours. Les erreurs comprennent code/message/details filtrés/request_id. Le serveur statique est monté après les routes API (`services/api/main.py:785`).

Le contrat partagé `packages/contracts/contracts.json` est confronté aux routes, états, événements et plusieurs payloads par `test_api_contract.py`. Les types TypeScript sont cependant maintenus manuellement (`apps/web/src/lib/types.ts`) : il n'y a pas de génération complète OpenAPI → TypeScript constatée, contrairement au contrat cible d'`IMPLEMENTATION.md §2`. La protection actuelle repose sur Pydantic côté API, des validations ciblées navigateur et les tests de contrat ; elle ne constitue pas une validation runtime exhaustive de chaque réponse reçue.

## 4. Dépendances, configuration et artefacts

Les 25 dépendances Python directement déclarées sont confrontées à leurs métadonnées installées : aucune divergence applicable à Linux n'a été trouvée ; `pywin32` est conditionné à Windows. L'environnement contient 124 distributions, le verrou uv 130 entrées multi-plateformes. Les 25 dépendances npm déclarées, développement compris, correspondent exactement aux packages locaux. Cette concordance ne certifie ni l'intégrité de tous les fichiers installés ni l'absence d'avis de sécurité. Inventaire détaillé et hashes des cinq verrous : `dependencies.json`.

| Couche | Versions réellement constatées |
|---|---|
| Python/SQLite | CPython 3.12.14 ; SQLite lié 3.53.1 ; uv 0.12.21 |
| API | FastAPI 0.142.1, Uvicorn 0.54.0, Starlette 1.7.0, Pydantic 2.13.5, httpx 0.28.1 |
| PDF/ML CPU | Docling 2.131.0, docling-core 2.99.0, pypdfium2 5.13.0, ONNX Runtime 1.30.0, NumPy 2.5.3, torch 2.14.0+cpu, torchvision 0.29.0+cpu |
| Tokenizers/images | Transformers 5.17.0, tokenizers 0.23.2, Pillow 12.3.0 |
| Binaires disponibles | Qdrant 1.19.1 ; Tesseract 5.4.0 lié à Leptonica 1.87.0 ; Ollama 0.35.0 provisionné selon chemins/manifeste, non exécuté en serveur pendant l'analyse |
| Web | Node 24.16.0, Next 16.3.7, React/React DOM 19.3.0, PDF.js 6.3.289, TanStack Query 5.104.0, Zustand 5.0.15, Tailwind 4.3.3, TypeScript 5.9.3, Playwright 1.63.0 |
| Vérification | pytest 9.1.1, Ruff 0.16.9, mypy 2.3.1 ; pnpm 10.34.1 déclaré, aucune installation/résolution pnpm lancée ici |

Le verrou uv déclare Windows AMD64 et Linux aarch64/x86-64. Les roues torch Linux viennent de l'index CPU explicite. La dépendance ONNX utilise le fournisseur CPU ; l'option GPU concerne uniquement Ollama. Les modèles, tokenizers, langues OCR et binaires ont des verrous/manifeste locaux distincts ; aucun téléchargement de modèle n'a été lancé. L'inventaire de licences distingue avis présents, manques et autorisation interne W030 ; aucune certification juridique de redistribution n'est ajoutée.

Le lanceur/CLI choisit le profil 4B par défaut (W045), le 2B étant une option explicite. `config/local16-4b.yaml` sert `qwen3.5:4b-text` dérivé de `qwen3.5:4b`, et `config/local16.yaml` sert `qwen3.5:2b`. Les deux profils utilisent les mêmes ports et la même racine de données ; changer de modèle exige donc le cycle prévu, et non deux instances parallèles. Les plafonds de réponse actuels sont 768 tokens factuels et 1 536 pour les autres modes, contexte 8 192 et marge 256. Les valeurs de conception historiques restent distinctes des profils livrés.

L'export web existant contient 242 fichiers, 6 547 685 octets utiles, environ 7,1 Mio occupés, datés du 7 octobre. Les deux manifestes PDF.js sont identiques ; les 203 assets annoncés sous `public/pdfjs` et les 203 sous `out/pdfjs` correspondent à leurs SHA-256 et à la version 6.3.289. Le scan de chemins trouve zéro fuite, avec trois constantes amont Emscripten/OpenJPEG explicitement admises. `out/build-provenance.json` est absent : le rattachement des bundles applicatifs aux sources actuelles n'est pas démontré. Aucun build n'a remplacé cet état.

## 5. Base de données et cohérence des données

La base principale est `.runtime/data/app.sqlite3`, 279 588 864 octets, schéma 3. SQLite est utilisé directement, avec connexions par opération et transactions courtes ; les contraintes et les index sont écrits en SQL, sans ORM. Les migrations 001/002/003 sont appliquées par le runner de `Database.initialize` ; le retour arrière de schéma est prévu par restauration d'une sauvegarde, sans migration descendante. Aucune migration n'a été exécutée pendant l'analyse.

Les relations principales sont dossier → document → version → révision d'extraction/génération → pages/sections/blocs/tables/chunks ; chunk → sources/identifiants ; query → citations/événements. `documents.active_generation_id` détermine la génération publiée. Les originaux et les extractions sont des fichiers séparés référencés depuis SQLite ; Qdrant conserve les vecteurs et payloads liés aux générations.

Les clés uniques couvrent notamment chemin de document, `(document_id, sha256)`, la PK de bloc `(generation_id, id)`, UUID du chunk et `(chunk_uuid, position)`. Le contrat externe nomme cet identifiant de bloc `block_id` ; ce n'est pas le nom de la colonne PK. FTS5 est une table à contenu externe `chunks`, entretenue par les trois triggers insert/update/delete ; tokenizer `unicode61 remove_diacritics 2`, BM25 trié dans le sens croissant. Les index explicites comprennent génération/version, chunks/génération, identifiants normalisés et jobs/état/date. Certaines relations sont des invariants applicatifs plutôt que des contraintes complètes de base : pointeur de génération active, block_id des sources, JSON de couverture/états et références de parents. Cela constitue une frontière d'intégrité à connaître ; aucun lien actif orphelin n'a été trouvé par les contrôles définis.

| Agrégat réel, sans lecture de contenu métier | Nombre |
|---|---:|
| Documents / versions | 7 / 7 |
| Générations totales / actives | 11 / 5 |
| Pages / sections / blocs | 489 / 799 / 13 602 |
| Chunks totaux / actifs | 3 217 / 1 409 |
| Questions persistées | 99 : 41 `done`, 57 `length_limited`, 1 `error` |
| Citations / événements | 503 / 38 264 |
| Générations partielles non publiées | 5 |

`PRAGMA quick_check` retourne `ok` ; les contrôles de clé étrangère ne trouvent aucune violation. Six contrôles définis des liens actifs/provenance/offsets/pages/événements sont également à zéro. Ces agrégats ne sont ni une mesure de qualité OCR, ni une certification de chaque offset/citation, ni une comparaison des points Qdrant : le serveur dense est arrêté. Les plans SQL observés utilisent l'index de génération puis un tri temporaire pour les blocs ; l'historique par conversation et des recherches de jobs par document utilisent scans/tri. L'absence de certains index composés est une dette de dimensionnement observable par `EXPLAIN`, sans latence problématique démontrée sur les sept documents actuels. L'intégrité complète de FTS5 n'a pas été contrôlée : sa commande d'intégrité serait mutatrice.

La première ouverture en `mode=ro` a créé les auxiliaires SQLite WAL de 0 octet et SHM de 32 768 octets. L'effet a été détecté, les connexions fermées, l'absence de détenteur et de service ainsi que WAL vide vérifiées, puis seuls ces deux fichiers créés par l'analyse ont été retirés. Les lectures suivantes utilisent `mode=ro&immutable=1` sur la base arrêtée et stable. La taille et la date du fichier principal n'ont pas changé ; aucun hash avant cette première ouverture n'existe, donc aucune conservation binaire rétrospective n'est affirmée. La date du dossier a changé et n'a pas été restaurée. Preuves : sonde DB et trace de nettoyage de cet axe.

## 6. Runtime et ressources réellement observés

| Élément | État courant observé |
|---|---|
| Hôte | Jetson/Linux aarch64, Ubuntu 20.04.6 LTS, noyau 5.10.120-tegra, glibc 2.31 ; 8 CPU logiques, environ 61,3 Gio RAM |
| Volume système | `/dev/mmcblk0p1`, ext4, environ 3,8 Gio disponibles, 93 % occupé |
| Carte SD | `/dev/mmcblk1p1`, ext4, `/media/safae/devsave1`, environ 137 Gio disponibles à l'entrée |
| Runtime/venv | `.runtime` → `/media/safae/devsave1/agentPDFDoc-runtime/runtime` ; `.venv` → `…/venv` |
| Dépendances web | `node_modules` → dossier de toolchain sous une ancienne QA de la SD ; `.next` et `out` restent sur le volume système |
| Services applicatifs | Aucun processus projet identifié ; les quatre PID enregistrés (superviseur, Qdrant, Ollama, API) sont absents |
| Ports configurés | API 8785, Qdrant 6333, Ollama 11434 : aucune écoute, connexions TCP refusées (`ECONNREFUSED`) |
| Dernier état conservé | `status=stopped`, profil `config/local16.yaml`/2B ; empreinte enregistrée différente du profil actuel ; métadonnées de découverte GPU du 6 octobre seulement |

Il n'y a donc pas de chaîne DB → API → navigateur à vérifier en fonctionnement pendant cette baseline. Les anciennes valeurs `http_health=alive` et `accelerator.mode=gpu` dans `runtime.json` sont des métadonnées historiques d'une instance arrêtée, pas des healthchecks actuels. Aucun service n'a été démarré pour transformer cette observation. D'autres ports système/applications sont en écoute, notamment 80/8080/8443 et 5432 ; rien ne les rattache au RAG documentaire et ils n'ont pas été interrogés ou arrêtés.

Le manifeste de sources de cette instance arrêtée a été capturé le 6 octobre à 13:19 UTC, sur HEAD `497d901` et un arbre déjà modifié. Parmi ses 383 chemins, 310 SHA-256 correspondent encore et 73 diffèrent aujourd'hui, sans fichier manquant ; backend, frontend, profils et suivi ont évolué. Ce manifeste n'est donc pas la preuve d'une exécution de l'arbre actuel. Sa portée exclut notamment `tools/dist` et l'export web ; aucun rapprochement complet de livraison n'en est déduit. Preuve : `historical-source-comparison.json`.

L'observabilité implémentée comprend `X-Request-ID` et erreurs structurées, événements SSE/métriques persistés par requête, logs des trois services par instance et trace de ressources JSONL toutes les secondes. La trace de ressources et l'audit sécurité utilisent des fichiers de 5 Mio avec deux archives ; l'audit possède aussi une file bornée à 8 Mio et expose les compteurs d'abandon/échec (`supervisor.py:435,651`, `security.py:121,393`, `main.py:754`). Les logs conservés de la dernière instance sont datés du 6 octobre ; l'API possède les marqueurs de démarrage et d'arrêt complets. Un relevé limité aux fenêtres finales de 128 Kio compte des marqueurs `error`/`warn` dans Ollama : il ne classe ni leur cause ni leur gravité et ne les transforme pas en incident actuel. L'audit conserve des ouvertures/refus/révocations historiques. Seuls métadonnées et compteurs sont enregistrés dans `runtime-log-observation.json`, sans URL d'ouverture, token, question ou contenu brut ; absence de marqueur dans une fenêtre n'est pas preuve d'absence d'erreur.

Les emplacements lourds sont effectivement sur la SD, conformément à la précision de l'utilisateur. Ce choix local repose sur des liens et un montage, sans chemin spécifique ajouté au code du dépôt. L'outillage web dépend actuellement d'un répertoire anciennement nommé QA : il est requis par le projet et doit être conservé, même si son nom suggère un temporaire. Son indisponibilité casserait ce lien ; aucune défaillance actuelle n'est constatée.

Les relevés de charge, mémoire et disques sont enregistrés dans `resources.jsonl`, `io-sample.json` et les observations de contrôle. Les premières vérifications ont laissé environ 46–47 Gio RAM disponibles ; le CPU agrégé des huit échantillons a atteint 47,1 %. Les travaux lourds ont été limités : une suite Python séquentielle, unités web séquentielles et contrôles statiques, sans build, OCR ni LLM. Un échantillon machine de cinq secondes montre 3,364 s d'activité de la SD et 12,76 Mo écrits ; cela illustre l'activité I/O pendant les tests, avec bruit des autres applications, sans benchmark de stockage ni attribution exclusive. Après les premiers contrôles, les contrôles coûteux en fichiers ont été laissés seuls.

À 14:35 UTC, après nettoyage : environ 48,4 Gio RAM disponibles, CPU échantillonné à 11,2 %, 3,8 Gio libres sur le volume système et 136,9 Gio sur la SD. Les trois ports projet refusent encore la connexion. Le nettoyage a retiré uniquement `baseline-20261009/scratch` : données synthétiques et caches propres aux tests de cette session, 124 955 fichiers réguliers, 614 610 315 octets logiques. L'espace libre SD observé a augmenté d'environ 1,43 Gio pendant cette opération ; occupation en blocs, bruit externe et taille logique sont distingués. Aucun des anciennes QA, modèles, originaux, export, `.next` ou toolchain requise n'a été supprimé. Les processus accessibles n'avaient aucun descripteur ni cwd sous scratch ; 356 processus étaient inaccessibles à ce contrôle sans élévation, limite conservée dans la preuve.

## 7. Constats consolidés et dédupliqués

Les identifiants ci-dessous désignent des observations, pas des actions du plan. « Reproduit » signifie que le chemin réel a été exercé dans les conditions nommées ; un double HTTP, de hooks ou de disque reste un double. Le niveau d'impact dépend du scénario et n'est pas une occurrence constatée sur le runtime arrêté.

| ID / classement | Fait et preuve précise | Impact et limite |
|---|---|---|
| B01 — bug reproduit, chemins | La garde lit `profile.app.data_dir` (`tools/dist/linux_profiles.py:78,104`) tandis que le superviseur privilégie `RAG_DATA_DIR` (`services/runtime/supervisor.py:62`). `rag.sh:167` et `linux_install.child_environment:356` conservent cette variable. Vraies fonctions, profil/ROOT fictifs : garde `ok`, racine runtime sous le programme. | Une variable héritée peut diriger contrôle/journaux/données ailleurs que le profil validé, y compris dans le programme. Aucun démarrage ni perte de données réelle provoqués. |
| B02 — bug reproduit, recherche | Diagnostic collection dense courante absente ; `_candidates` appelle néanmoins `QdrantStore.query` (`services/api/retrieval.py:375`), dont le 404 devient `qdrant_unavailable`. SQLite synthétique contient un passage lexical ; recherche finit 503. | Le repli lexical annoncé n'est pas assuré dans ce scénario de nouvelle identité dense. HTTP/embedding doublés, SQLite/FTS5 réels ; pas incident natif Qdrant. |
| B03 — bug reproduit, provenance | `ScopeResolver.selected_sources` omet l'état/couverture d'extraction (`services/api/scope.py:194`) ; warning conditionné à cet état (`retrieval.py:481`). Même génération `ready_partial` : warning en scope document, absent en sélection exacte. | Une sélection issue d'une extraction partielle perd ce signal de limite. La sélection reste hashée/versionnée ; aucun texte ni localisation fabriqués démontrés. |
| B04 — bug reproduit, interaction | `submit` omet `searchMutation.isPending` (`analysis-panel.tsx:145`) ; Ctrl/Meta+Entrée l'appelle directement (`:197`). Composant réel transpilé, hooks/mutations doublés : bouton désactivé, une mutation supplémentaire déclenchée. | Recherche concurrente possible ; réponse ancienne susceptible de remplacer la plus récente via callback sans numéro d'opération. Arrivée inversée non mesurée sur serveur. |
| B05 — bug limite reproduit, bibliothèque | `api.tree` coupe à 10 000 (`api.ts:59`), conserve `total_documents` mais retire curseur/signal. `library-panel.tsx:152,171` affiche total et documents chargés, filtrés localement. Fonction réelle, fetch paginé doublé : 10 000 chargés sur 10 001. | Documents absents de navigation/sélection/filtre au-delà de cette borne sans annonce. Les sept documents de la base actuelle n'exercent pas le cas. |
| B06 — bug source et test existant, session | `session-gate.tsx:71` avale le rejet de logout puis rend `session_closed`. Le test `react-lifecycle.test.ts:253,344` attend ce comportement avec un rejet injecté. L'API révoque seulement si la requête et son CSRF lui parviennent (`main.py:318`). | Une panne réseau peut être présentée comme une session réellement fermée alors que cookie/registre restent valides. Aucun cookie réel utilisé pour cette sonde. Référence OWASP S05. |
| B07 — bug reproduit, disque | `create_backup` contrôle `ROOT` lorsque `output.parent` n'existe pas (`services/runtime/backup.py:146`). Fonction réelle extraite par AST, disque/chemins doublés. | Refus ou admission sur le mauvais volume pour une nouvelle sous-racine de sauvegarde SD. Aucun backup réel exécuté. |
| F08 — fragilité diagnostique, backup | Le `finally` de reprise peut lever après l'échec primaire (`backup.py:219,224`). Sonde à deux erreurs : erreur reprise remontée, primaire conservée dans `__context__` et manifeste `failed`. | Le JSON opérateur masque le premier défaut ; aucune perte de preuve ou de données déduite. Sémantique Python S06. |
| F09 — fragilité source, verrous | Deux acquisitions de verrou rattrapent tout `OSError` comme contention et retirent la cause (`supervisor.py:383,565`). | Un autre défaut de `flock` serait annoncé « autre instance », contrairement au skill Linux qui distingue EAGAIN/EWOULDBLOCK. Aucune erreur de verrou actuelle observée. |
| R10 — risque conditionnel, upload | Borne middleware sur `Content-Length`, borne par fichier après parsing (`main.py:241,488,508`). FastAPI installé parse `request.form` ; Starlette distingue fichiers spoulés et champs texte. | Requête locale déjà authentifiée sans Content-Length : stockage temporaire consommé avant le refus applicatif. Pas de saturation testée, ni accès anonyme/distant démontré. Contrat Starlette S07. |
| E11 — état intermédiaire, provenance/build | Export sans `build-provenance.json` ; fabricant courant l'exige (`linux_kit.py:547`). Trois fichiers requis du guide/icône présents mais absents de HEAD (`linux_kit.py:86`, `git cat-file -e HEAD:…`). | Le kit B courant ne peut être considéré fabricable/qualifié depuis ce HEAD et cet export. Les gardes sont cohérentes ; pas un bug du fabricant. Doublon F04/DIST-S05 fusionné ici. |
| E12 — incohérence prouvée, suivi | `build_brief --check` échoue ; `verify_pack` échoue sur brief et hash périmé du skill du kit. Le plan cite une base antérieure et décrit R26-KIT-04 comme audit/spécification malgré code/journal plus récents. | Lire le brief seul ou son registre donne une référence désynchronisée. Aucune régénération ni mise à jour de suivi effectuée pour effacer ce constat. |
| E13 — écart au contrat cible, configuration/types | CONFIGURATION §1 demande profil Pydantic strict et rejet des inconnues ; `Settings` est une dataclass avec `safe_load` et validations ciblées (`settings.py:71`). Superviseur et API valident séparément, v2 d'un côté, v1/v2 de l'autre. Types TS manuels. | Couplage de compatibilité et risque de paramètre inconnu/ignoré ; aucun profil livré refusé ni erreur live prétendue. Le contrat cible est distinct de la documentation stabilisée du système actuel. |
| E14 — incohérence documentaire, plateforme | Le skill Linux indique encore une acceptation Playwright en attente ; le plan la consigne comme acceptée le 6 octobre (`PLAN.md:21`). | Ambiguïté de méthode de preuve, sans changement du support éditeur : Ubuntu 20.04 reste hors support actuel. Aucun E2E nouveau qualifié. |
| D15 — dette observée, accès SQL | Plans SQL : tri temporaire des blocs après filtre génération ; scans/tri pour jobs par document et historique par conversation. | Opportunité de dimensionnement par index composés ; aucun ralentissement métier mesuré, ni index proposé comme adoption automatique. |
| D16 — couplages cohérents, maintenance | Versions natives présentes dans verrous et plusieurs adaptateurs ; formats Windows/Linux distincts ; constantes kit/profils partagées par imports et scripts ; source-manifest runtime exclut `tools/dist` et `out`. | Une évolution traverse plusieurs frontières. Les manifestes runtime/artefacts/programme/export ont des portées distinctes ; égalité d'une seule empreinte ne prouve pas identité de toute la livraison. Aucun défaut déduit de la duplication seule. |
| U17 — inconnue de performance, lecteur | Recherche locale absente peut parcourir toutes les pages en texte/blocs (`pdf-search.ts:20`, `pdf-viewer.tsx:262`) ; ce parcours ne fait pas le cleanup explicite du rendu. | Latence/cache sur très grand PDF à mesurer. Virtualisation des canvases et AbortController présents ; fuite mémoire non démontrée. |
| D18 — dette observée, concurrence API | Accès SQLite synchrones directs depuis des fonctions async, notamment état et chaque delta (`services/api/query.py:192,252`, `db.py:145`). Relectures par chunk/génération/document dans les candidats (`retrieval.py:389,397,429`). | Attente de verrou/accès disque susceptible de retarder la boucle API/SSE. FTS et embeddings sont déjà déportés, la bibliothèque principale est un JOIN paginé. Aucune contention ou latence mesurée ; sémantique FastAPI S10. |
| F19 — fragilité reproduite, oracle de test | `test_runtime_selftest.py:36` compare le chemin physique renvoyé par `runtime_location` (`artifacts.py:41`) à `root / "backups"` lexical ; `.runtime` est un lien SD. Échec dans la suite complète, PASS avec TMPDIR physique, mêmes sources. | Assertion dépendante de la représentation du chemin. Aucun défaut d'isolation des données n'en découle ; l'échec de la suite demeure enregistré, sans normalisation du code ni assertion modifiée. |

Les seuils UI (cinq canvases, 24 millions de pixels, zoom 50–300 %), les valeurs E5 et les bornes de ressource sont des choix explicites du produit avec gardes ; leur présence dans le code n'est pas, à elle seule, une dette. Aucun code mort significatif n'est déclaré sur le seul fondement d'un lint vert ou d'une recherche TODO vide.

## 8. Vérifications exécutées sur l'état courant

| Contrôle | Résultat | Preuve / conditions |
|---|---|---|
| Unités Python `tests/unit` | 2 513 PASS, 2 FAIL, 20 SKIP, 1 warning ; 1 147,97 s | `python-unit.log/xml` ; une exécution séquentielle, HOME/XDG isolés par conftest Linux, TMPDIR/basetemp dédié sur SD, pas cache pytest/bytecode |
| Sonde TMPDIR physique | 1 PASS, 0,40 s pytest | `python-canonical-path.log/xml/json` ; seul test de F19, une réexécution pour isoler la représentation du chemin, pas remplacement du résultat global |
| API HTTP/session | 79 PASS, 1 SKIP Windows, 1 warning, 71,42 s | `api-integration.log/xml` ; vraies routes ASGI/SQLite isolées, embedding/vecteurs/Ollama/gouverneur doublés explicitement ; pas recette native |
| Unités web | 426 PASS, 0 FAIL/SKIP | `frontend-unit.log`, Node strip-types, concurrence 1 |
| Lint et types web | PASS / PASS | ESLint `--max-warnings 0` ; tsc `--noEmit --incremental false` ; logs dédiés |
| Ruff | PASS | `ruff check --no-cache services tools tests RAG_Local_Agents/tools` |
| mypy Linux / win32 | PASS / PASS, 98 fichiers chacun | `--no-incremental`, caches dédiés ; plateforme win32 simulée, aucune exécution Windows |
| Espace documentaire | 7/7 PASS | `tools/docs/check_docs.py --report <QA>/docs.json` |
| SVG documentaires | PASS | `tools/docs/diagrams.py --check` |
| Brief | FAIL | `RAG_Local_Agents/tools/build_brief.py --check`, fichier dérivé désynchronisé |
| Pack | 9/11 PASS, 2 FAIL | `verify_pack.py --report <QA>/pack.json` ; `skills_registry`, `consolidated_brief` |
| Export/PDF.js | Scan PASS, assets PASS | Zéro constat de chemin ; SHA-256 203 assets par dossier |
| Préservation des sources | Contrôle terminal PASS | `final-preservation.json` : 1 110 empreintes identiques, aucun fichier absent, HEAD/index inchangés, diff indexé vide ; seul ajout au status complet : ce rapport |
| Nettoyage des temporaires | Effectué | Scratch propre à cette session absent ; preuves utiles conservées hors scratch ; détail et limites de contrôle dans `final-preservation.json` |

Le warning API est la dépréciation de `httpx` dans le TestClient Starlette, qui recommande désormais `httpx2`. Il concerne l'outillage des tests ; le transport produit httpx 0.28.1 n'est pas déclaré incompatible sur cette seule base. Le passage de 79 tests démontre le fonctionnement actuel de ces contrats isolés, pas leur maintien dans toutes les versions futures.

Les deux échecs Python sont distincts : `test_docs_tooling.py::test_registry_real_repository` retrouve exactement le SHA périmé du skill du kit (E12, même cause que le pack) ; `test_runtime_selftest.py::test_control_profile_isolates_data_and_ports_but_shares_the_host_heavy_lock` expose F19. Le test de chemin résout déjà les chemins données/Qdrant à la ligne 32, mais pas son attente `backups` à la ligne 36. La sonde avec TMPDIR physique confirme cette différence sans corriger le test. Les 20 SKIP correspondent à quatre tests d'installation Windows, deux de raccourcis, trois de retrait, dix nécessitant PowerShell absent et un lecteur Win32/pywin32. Le SKIP API est une jonction Windows. Aucun n'est reclassé en réussite.

Les commandes exactes, cwd, durées et codes de sortie sont conservés dans `static-check-results.json`, `frontend-checks.json`, `python-test-commands.json` et `python-canonical-path.json`. Les commandes Python initiales ont été consignées après terminaison, sans réexécution. Les sondes ont leur propre script et résultat : `backend_dense_probe.py/json`, `frontend-probes.mjs/json`, `distribution-probes.py/json` et `backend_db_probe.py/json`. Elles exercent les causes nommées avec des substitutions identifiées. Les échecs ne sont ni masqués ni corrigés dans cette baseline.

## 9. Points vérifiés et conformes dans leur portée

- Publication autoritaire SQLite, générations conservées et nettoyage différé ; scopes filtrés avant top-k et contexte ; sélection Unicode ancrée à révision/hash/offsets ; relecture des versions historiques sans substitution par la plus récente.
- Séparation UI/état serveur, caches de blocs/sommaire par révision, même origine, citations enregistrées, reconnexion SSE sur query ID sans nouveau POST, annulation/destroy des tâches PDF.
- Cookies/session/CSRF/Host/Origin et routes administratives protégées dans les tests isolés. Développement local sans TLS/cookie Secure conforme au mandat ; production contrôlée par certificat/configuration. Absence de multi-utilisateur et d'autorisation par rôle cohérente avec D-01.
- Originaux référencés hors export statique ; validation des chemins et Range, absence de HTML actif ou d'images distantes dans les réponses. Les données PDF restent non fiables et le LLM ne reçoit aucun shell, navigateur ou skill de développement.
- Liste blanche d'environnement des services, HOME propre, supervision par identités et groupes possédés, pas d'élévation ni service système. B01 concerne l'environnement du lanceur avant cette construction.
- Sauvegarde via Online Backup API et snapshots, quiesce préalable, restauration dans une nouvelle racine, contrôle de hashes ; source relue, procédure actuelle non réexécutée.
- SQLite installé 3.53.1 est au-delà de la version de correction 3.51.3 du WAL-reset bug documenté officiellement (S08). Aucun défaut de ce mécanisme n'est déduit de l'usage de WAL.

La confidentialité locale des fichiers dépend aussi des permissions/ACL de la cible : DB mode 0644 et dossiers mode 0775 observés, mais ancêtre `/media/safae` mode 0750 avec ACL accordée au seul compte `safae`, autres comptes refusés à cet ancêtre. Ces modes ne démontrent donc pas une lecture par n'importe quel utilisateur sur ce poste. Un compte du même utilisateur peut lire les fichiers comme le worker ; la liste blanche d'environnement n'est pas un sandbox de fichiers. Cette limite est déjà documentée dans le code d'ingestion.

## 10. Qualification historique, inconnues et décisions futures

La livraison locale Linux aarch64 avec réserves W038 demeure le statut du projet. La qualification intégrale V2.1 est différée. Les succès historiques ne sont pas reclassés par la baseline et leurs échecs restent conservés. En particulier :

- Linux D06.6 dispose d'un assemblage de preuves bornées native/OCR/page/section et D06.9 d'une recette QLONG/SSE bornée ; les cases Windows et D06 global restent distinctes. Le tableau ancien de la DoD doit être lu avec ses compléments datés, pas isolément.
- Le plan R26 conserve le surlignage à 155/169 régions (91,7 %) et 161/169 bonnes pages (95,3 %) avec ambiguïtés sur texte répété ; ces mesures historiques ne sont pas refaites aujourd'hui.
- Les diagnostics 2B et 4B, limites OCR P02 et refus de certains faits restent des réserves de qualité. Les 57 réponses `length_limited` présentes en base ne suffisent pas à qualifier qualité, cause ou gravité de chacune.
- Le kit A a une phase 1 historique exercée ; le kit B courant, son update/rollback/retrait, son menu et l'E2E complet sur export final restent non qualifiés par ce rapport.
- Windows natif, Linux x86-64 et CPU sur un hôte de 16 Go physiques au plus ne sont pas qualifiés par le Jetson de 61 Gio ; aucune restriction système, calibration ou nouvelle campagne n'a été engagée.
- Le comparatif E5/Granite et le jeu final sont différés ; aucun modèle/collection supplémentaire ni score SOTA local n'est inventé.

Les prochains axes restent à définir par l'utilisateur. Les sujets qui nécessitent encore un choix ou une mesure sont identifiés sans devenir des tâches : contrat d'override `RAG_DATA_DIR` avec profil explicite ; garantie/annonce de déconnexion en cas de panne ; comportement lexical en migration dense ; indication de bibliothèque partielle ; volumétrie nécessitant des index composés ; latence/cache du lecteur sur gros PDF ; limite du corps multipart avant parsing ; rattachement du build à une révision ; périmètre de qualification des plateformes et de redistribution. Aucun choix de refonte, nouveau framework, ORM, moteur ou architecture n'est recommandé par défaut.

## 11. Références techniques officielles et applicabilité

Les références suivantes ont été consultées le 9 octobre 2026 pour les mécanismes pertinents. Le code installé ou les fichiers verrouillés établissent la version réellement utilisée ; une documentation courante ne certifie pas une version ancienne ni une mesure sur ce poste. Le tableau sépare recommandation documentaire et observation locale, sans adoption.

| ID | Source primaire et section utile | Apport / limite |
|---|---|---|
| S01 | [Git status](https://git-scm.com/docs/git-status), sortie porcelain ; [Git ls-remote](https://git-scm.com/docs/git-ls-remote) | Distinguer HEAD/index/arbre/non suivis et interroger des refs distantes. Commandes exécutées avec Git local 2.25.1, pas fetch. |
| S02 | [SQLite URI](https://www.sqlite.org/uri.html), `mode`/`immutable` ; [WAL §5](https://www.sqlite.org/wal.html#read_only_databases) | Une ouverture SQL ro peut encore créer WAL/SHM ; immutable n'est sûr que si le fichier reste stable. Incident de méthode explicité en §5. |
| S03 | [Next.js Static Exports](https://nextjs.org/docs/app/guides/static-exports) | Export/mécanismes navigateur ; guide courant 16.4.0, configuration et dépendance locale 16.3.7 comme preuve exacte ; pas migration décidée. |
| S04 | [TanStack Query cancellation](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation), [React useEffect](https://react.dev/reference/react/useEffect), [WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html#the-last-event-id-header) | AbortSignal, cleanup et Last-Event-ID cohérents avec le code ; aucune latence ou rendu réel déduit. Versions locales Query 5.104.0/React 19.3.0. |
| S05 | [OWASP Session Management — expiration manuelle](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#manual-session-expiration) | Invalidation serveur lors du logout. Écart B06 dans l'annonce du succès après rejet, sans défaut TLS inventé en développement. |
| S06 | [Python 3.12 finally](https://docs.python.org/3.12/reference/compound_stmts.html#finally-clause), [venv](https://docs.python.org/3.12/library/venv.html), [uv cache](https://docs.astral.sh/uv/concepts/cache/) | Exception secondaire en finally ; venv à recréer plutôt que présumer déplaçable ; cache distinct. Python local 3.12.14, documentation 3.12.15 ; aucune relocation essayée. |
| S07 | [Starlette Requests](https://www.starlette.dev/requests/), [release notes](https://www.starlette.dev/release-notes/) et code FastAPI/Starlette installé | Limites du parseur multipart et protection de corps disponibles dans Starlette 1.7.0 ; R10 est relié à l'ordre middleware/parsing réel, pas à une attaque exercée. |
| S08 | [SQLite WAL-reset §11](https://www.sqlite.org/wal.html#the_wal_reset_bug), [release 3.51.3](https://www.sqlite.org/releaselog/3_51_3.html) | Conditions précises du défaut et version corrigée ; SQLite local 3.53.1 hors plage affectée. |
| S09 | [Linux /proc](https://docs.kernel.org/filesystems/proc.html) | Interprétation MemAvailable/identités et limites de visibilité ; kernel local 5.10, pas preuve d'un hôte 16 Go ou de mémoire GPU complète. |
| S10 | [FastAPI async](https://fastapi.tiangolo.com/async/) | Une fonction utilitaire synchrone appelée directement depuis `async def` reste dans ce thread ; distinct du handler `def` automatiquement déporté. Applicable aux appels observés de FastAPI 0.142.1 ; aucune mesure de latence. |
| S11 | [SQLite Foreign Keys](https://sqlite.org/foreignkeys.html), [FTS5 BM25](https://sqlite.org/fts5.html#the_bm25_function) | Contraintes composites/activation par connexion et score FTS inférieur mieux classé ; schéma et ordre local vérifiés. Aucun index supplémentaire adopté ni rappel sémantique certifié. |
| S12 | [Qdrant Query points](https://api.qdrant.tech/api-reference/search/query-points), [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) | Contrat de requête dans une collection et validation stricte/champs supplémentaires ; documentation courante confrontée aux adaptateurs installés et au contrat cible. Aucun serveur Qdrant interrogé ni migration Pydantic proposée. |

Les APIs E5, Qdrant, Ollama, Docling, PDFium et Tesseract ont également leurs sources versionnées dans les skills et le registre existant [SOURCES](../SOURCES.md). Leur comparaison ici porte sur les adaptateurs et versions installées, sans veille générale ni prétention de supériorité SOTA. Aucun benchmark officiel ne remplace une mesure de fidélité/recherche sur les PDF du projet.

## 12. Trace de l'analyse et état de reprise

Premiers relevés : Git/arbre/ressources vers 14:01 UTC ; empreintes de 1 110 fichiers à 14:05 UTC ; contrôles web 14:06–14:07 ; tests Python à partir de 14:06 ; contrôles statiques puis API isolée ; trois axes parallèles, ensuite relecture indépendante. Les sondes frontend ont été confirmées une seconde fois pour conserver un script reproductible après suppression du harnais temporaire initial, avec ce motif enregistré. Aucun résultat natif n'est reconstitué à partir d'un double.

Le contrôle terminal est exécuté : les 1 110 fichiers préexistants sont identiques à leurs empreintes initiales, HEAD et index conservés, aucun diff indexé. Le seul nouveau fichier visible dans le status Git complet est ce rapport. Les vérifications ont terminé avec les résultats et échecs consignés ; scratch est supprimé, preuves requises conservées sur la SD. Le fichier SQLite principal conserve taille/mtime, ses auxiliaires créés par l'analyse sont absents, et les services applicatifs restent arrêtés. Les limites de la comparaison DB sont celles de la section 5.

Cette remise établit une baseline technique ; elle ne livre aucun correctif, commit, push, démarrage, campagne réelle de modèles ou clôture du PLAN/DoD. Les prochains axes sont à définir par l'utilisateur à partir de ces observations.

### Index des preuves conservées

Les chemins ci-dessous, relatifs à la racine du dépôt, dépendent du montage SD local et restent hors Git. Les résultats non versionnés sont référencés comme chemins de preuve, conformément au contrôle documentaire ; les liens vers des fichiers externes au projet ne sont pas publiables. Ils ne sont pas des fichiers temporaires à purger tant que cette baseline doit être vérifiable. Le rapport présent est le livrable documentaire consolidé ; les détails d'axes et preuves d'exécution complètent sa traçabilité.

| Objet | Preuve locale |
|---|---|
| Analyse DB/API/ingestion | `.runtime/qa/baseline-20261009/backend.md`, `.runtime/qa/baseline-20261009/backend_db_probe.json`, `.runtime/qa/baseline-20261009/backend_dense_probe.json`, `.runtime/qa/baseline-20261009/backend_ro_aux_cleanup.json` |
| Analyse frontend | `.runtime/qa/baseline-20261009/frontend.md`, `.runtime/qa/baseline-20261009/frontend-probes.json`, `.runtime/qa/baseline-20261009/frontend-checks.json`, `.runtime/qa/baseline-20261009/frontend-export-scan.json` |
| Analyse runtime/distribution | `.runtime/qa/baseline-20261009/distribution.md`, `.runtime/qa/baseline-20261009/distribution-probes.json`, `.runtime/qa/baseline-20261009/runtime-observed.json`, `.runtime/qa/baseline-20261009/historical-source-comparison.json`, `.runtime/qa/baseline-20261009/runtime-log-observation.json` |
| Suites exécutées | `.runtime/qa/baseline-20261009/python-unit.log`, `.runtime/qa/baseline-20261009/api-integration.log`, `.runtime/qa/baseline-20261009/frontend-unit.log`, `.runtime/qa/baseline-20261009/python-canonical-path.json`, `.runtime/qa/baseline-20261009/static-check-results.json`, `.runtime/qa/baseline-20261009/pack.json` |
| Git/dépendances/ressources | `.runtime/qa/baseline-20261009/initial-state.json`, `.runtime/qa/baseline-20261009/dependencies.json`, `.runtime/qa/baseline-20261009/resources.jsonl` |
| Préservation et relecture | `.runtime/qa/baseline-20261009/final-preservation.json`, `.runtime/qa/baseline-20261009/validation.md` |

Correction de présentation du 9 octobre, reprise R27 : les 24 liens locaux vers les preuves QA non versionnées sont devenus des chemins explicites ; aucune observation, mesure ou conclusion de la baseline n’a changé. La version relue initiale est conservée sous `.runtime/qa/r27-20261009/root/baseline-before-proof-links.md` (SHA-256 `935b1d2d88d7697cce32cea396e707a8978d505b5860cd4488da701bcfb803aa`).
