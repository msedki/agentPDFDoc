# Sources officielles et traçabilité — V2.1

**Révision documentaire :** 29 septembre 2026. Les décisions de ce dossier restent des choix de conception, non des résultats certifiés par les éditeurs. Les versions de production doivent être verrouillées séparément ; une documentation sur `main`/`master` ne constitue pas un verrou logiciel.

## Références

| ID | Source officielle | Usage et statut documentaire |
|---|---|---|
| S01 | [Ollama — FAQ](https://docs.ollama.com/faq) | Référence conservée de la baseline : variables, rétention, concurrence et cloud ; vérifier la version de runtime au provisionnement |
| S02 | [Ollama — API chat](https://docs.ollama.com/api/chat) | Reconsultée pour cette V2.1 : flux, options et compteurs ; disponibilité des champs à contrôler au runtime |
| S03 | [Qwen3.5-4B — fiche officielle](https://huggingface.co/Qwen/Qwen3.5-4B) ; [distribution Ollama](https://ollama.com/library/qwen3.5) | Fiche Qwen reconsultée ; artefact Ollama exact, digest et Q4_K_M à contrôler, pas de RAM déduite du téléchargement |
| S04 | [multilingual-e5-small — fiche officielle](https://huggingface.co/intfloat/multilingual-e5-small/blob/main/README.md) | Référence E5 conservée : 384D, limites, préfixes/pooling ; artefact ONNX INT8 à produire ou vérifier |
| S05 | [ONNX Runtime — threading](https://onnxruntime.ai/docs/performance/tune-performance/threading.html) | Référence des threads et du spinning ; vérifier les options de la session réellement créée |
| S06 | [Docling — dépôt officiel](https://github.com/docling-project/docling) | Référence du composant, releases/licences à verrouiller |
| S07 | [Docling — options de pipeline](https://github.com/docling-project/docling/blob/main/docling/datamodel/pipeline_options.py) | Référence générale ; ne pas déduire la compatibilité de la seule branche courante |
| S08 | [Qdrant — configuration officielle](https://github.com/qdrant/qdrant/blob/master/config/config.yaml) ; [API création collection](https://api.qdrant.tech/api-reference/collections/create-collection) | Configuration serveur reconsultée : placement mémoire et dépréciations. Le schéma API de la version installée reste à tester séparément |
| S09 | [Next.js — static exports](https://nextjs.org/docs/app/guides/static-exports) | Référence du mode export ; les fonctionnalités serveur restent hors du profil statique |
| S10 | [Mozilla PDF.js — exemples](https://mozilla.github.io/pdf.js/examples/) | Référence du rendu/viewport ; alignement des sélections et surlignages à tester dans l'application |
| S11 | [SQLite — FTS5](https://sqlite.org/fts5.html) | BM25, tokenizers, triggers et tables externes ; SQL local réellement testé dans ce dossier |
| S12 | [OpenAI Codex — AGENTS.md](https://developers.openai.com/codex/guides/agents-md) | Référence des instructions de dépôt, conservée ; ce dossier ne sélectionne pas un modèle Codex via Markdown |
| S13 | [PyMuPDF — README](https://github.com/pymupdf/PyMuPDF/blob/main/README.md) | Référence de la décision historique de ne pas introduire cette dépendance nominale ; inventorier toutes les licences livrées |
| S14 | [Docling — options avancées](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md) | Reconsultée : voie native sans modèles layout/OCR/table, threads du parseur distincts, artefacts locaux |
| S15 | [Docling — pipeline options v2.131.0](https://github.com/docling-project/docling/blob/v2.131.0/docling/datamodel/pipeline_options.py) | Code versionné reconsulté : OcrMode et voies régionales ; ce tag de référence n'est pas déclaré testé comme installation complète |
| S16 | [Granite 97M Multilingual R2 — candidat de l'audit](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2) ; [publication IBM citée par l'audit](https://huggingface.co/blog/ibm-granite/granite-embedding-multilingual-r2) | Accès non reconfirmé pendant cette V2.1. Vérifier avant essai ; aucun score ni artefact CPU ne sont présentés comme vérifiés ici |

## Ce qui relève du projet

Les tailles de fragments, top-k, RRF k=60, budgets de tokens, enveloppes mémoire, politiques d'ordonnancement, métriques de recette et choix des composants sont des décisions explicites. Les sources documentent des mécanismes ; elles ne qualifient pas leur combinaison sur le PC utilisateur.

Les calculs 25 000 × 384 × 4, le contre-exemple RRF et les exemples d'offsets Unicode sont des contrôles de référence reproductibles du dossier, pas des benchmarks éditeurs ni des tests du sélecteur applicatif futur.

Une source inaccessible est notée comme telle. Ne pas la remplacer par une information supposée. Les dates et chiffres comparatifs de l'audit non reconfirmés ne sont pas nécessaires à la réalisation de la baseline E5 ; ils ne sont donc pas recopiés comme faits certifiés.

## Procédure de verrouillage

Identifier la version installée ; consulter son schéma officiel ou son code à cette version ; écrire un test de contrat minimal ; enregistrer commande, version, source et résultat ; produire le manifeste réel. Ne jamais inventer une signature, un digest, une option CLI ou un résultat de performance pour rendre un fichier complet.

Les autres dépendances de la stack conservent leurs sources officielles dans les lockfiles et le registre de licences produits au provisionnement. Aucun jeu de poids, fichier de police ou fichier privé n'est distribué avec ce dossier.


## Sources sur les compétences et leur rédaction — vérification V2.1

Consultation : **29 septembre 2026**. Les pages ci-dessous ont été ouvertes pour cette extension. Leur contenu documentaire ne prouve ni l'installation de compétences ni leur comportement dans un client utilisateur.

| ID | Source officielle | Constat utilisé / statut |
|---|---|---|
| S17 | [Agent Skills — Specification](https://agentskills.io/specification) | Format `SKILL.md`, métadonnées, structure et chargement ciblé vérifiés ; notre procédure reste propre au projet |
| S18 | [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | Principes de descriptions précises, instructions brèves et essais d'usage consultés |
| S19 | [OpenAI — catalogue plugins](https://github.com/openai/plugins) | Catalogue officiel d'exemples ; ne pas supposer que ces plugins sont installés |
| S20 | [OpenAI — ancien catalogue skills](https://github.com/openai/skills) | README consulté : dépôt marqué déprécié et renvoi vers le catalogue plugins ; pas de prescription d'un ancien installateur |
| S21 | [OpenAI — Package your plugin](https://developers.openai.com/plugins/build/plugins) | Documentation d'empaquetage officielle consultée via sa redirection ; aucune installation native effectuée par ce pack |
| S22 | [OpenAI — Build skills](https://developers.openai.com/plugins/build/skills) | Référence officielle actuelle pour structurer une compétence ; exigences du client à vérifier lors de son intégration |
| S23 | [Anthropic — exemples skills](https://github.com/anthropics/skills) | Dépôt officiel consulté ; exemples à tester et licences par artefact ; les skills projet ne sont pas copiés de ce dépôt |

Les URLs directes historiques `developers.openai.com/codex/skills` et `developers.openai.com/codex/guides/agents-md` n'ont pas été relues avec succès lors de cette extension (erreur d'accès). Même limite pour `code.claude.com/docs/en/skills`. Les routes officielles effectivement accessibles sont listées ci-dessus ; ne pas transformer ces échecs en preuve que les fonctionnalités n'existent pas. La référence S12 reste historique, non reconfirmée ici.

Le registre s'enrichit au fil des études selon [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md). Il faut enregistrer la date de consultation et la version réelle avant chaque nouvelle décision dépendante, au lieu de présenter cette bibliographie initiale comme une vérification perpétuelle.

## Sources locales de l'inspection des 29 et 30 septembre 2026

L'inspection locale complète le brief sans revisiter ses liens web. Les versions installées sont observées sur le poste, sans nouvelle décision de stack. Les documents privés n'ont pas été transmis à un service externe par les outils d'inspection.

| ID | Source, version et date connues | Apport | Limite |
|---|---|---|---|
| OBS01 | [machine.json](reports/preuves-inspection-2026-09-30/machine.json), Windows CIM/registre, 30/09/2026 00:02:31 UTC | CPU, RAM, SSD, volumes, pagination, WSL et ports réellement observés | Photographie instantanée ; aucun benchmark ou diagnostic SMART détaillé |
| OBS02 | [environnement.json](reports/preuves-inspection-2026-09-30/environnement.json), commandes locales et métadonnées Python, session 29/30 septembre UTC | Versions exécutées, présence PATH, paquets d'un interpréteur et langues OCR | Ni inventaire de toutes les venv ni test de compatibilité applicative |
| OBS03 | [corpus-inspection.json](reports/preuves-inspection-2026-09-30/corpus-inspection.json), SHA-256 et PyMuPDF 1.28.2, 30/09/2026 | Cinq originaux identifiés, 182 pages inspectées structurellement, 24 échantillons visuels, DOCX ZIP/XML | Aucun OCR ; orientation non échantillonnée et qualité extraction métier inconnues |
| OBS04 | [integrite-pack.json](reports/preuves-inspection-2026-09-30/integrite-pack.json), ZIP et manifestes conservés, session 29/30 septembre UTC | Identité des copies du pack, puis distinction des deux mises à jour documentaires locales | Cohérence interne, pas authentification de l'auteur ni validation de runtime |
| OBS05 | [Rapport d'inspection](reports/INSPECTION_DOSSIER_MACHINE_2026-09-30.md), [journal](journal/2026-09-30.md) et brief v1.0 du 29/09/2026 | Interprétation des écarts entre matériel, corpus, logiciels et exigences | Appréciation de faisabilité conditionnelle ; D01–D09 non exécutés |

## Sources Windows et artefacts effectivement examinés — 30/09/2026 UTC

Les versions ci-dessous sont résolues à partir des métadonnées publiques du mainteneur, puis les fichiers ont été vérifiés selon config/artifacts.lock.json. Une URL de documentation explique le contrat ; seuls les rapports locaux prouvent son exécution.

| ID | Source officielle et portée | Observation et limite |
|---|---|---|
| WIN01 | https://docs.ollama.com/windows ; release ollama/ollama v0.35.0, API GitHub consultée30/09 | ZIP Windows amd641461196158octets, SHA256 verrouillé ; modèle encore en téléchargement à01:07UTC, pas d’inférence déclarée |
| WIN02 | https://github.com/qdrant/qdrant/releases/expanded_assets/v1.19.1 ; src/main.rs du tag | Serveur Windows x86-64 officiel et options config/telemetry ; binaire vérifié, démarrage applicatif à venir |
| WIN03 | https://docs.astral.sh/uv/getting-started/installation/ ; https://docs.astral.sh/uv/guides/install-python/ ; release astral-sh/uv0.12.21 | uv et Python3.12.14 isolés, bootstrap offline exécuté ; installation fraîche complète encore à tester |
| WIN04 | https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw ; https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent ; https://learn.microsoft.com/en-us/windows/console/attachconsole | Job kill-on-close, console dédiée et signal ciblé. Test Job enfant/descendant réel PASS ; arrêt réel des services encore à tester |
| MOD01 | https://huggingface.co/intfloat/multilingual-e5-small/tree/main/onnx ; API HF commit614241f622f53c4eeff9890bdc4f31cfecc418b3 | Export INT8 officiel118346824octets, tokenizer et SHA vérifiés ; smoke CPU2x384 PASS, aucune qualité de retrieval acquise |
| MOD02 | https://huggingface.co/Qwen/Qwen3.5-4B/tree/main ; commit851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a | Tokenizer/template/config/licence officiels verrouillés ; comptage local144tokens. Parité template Ollama à qualifier |
| MOD03 | API HF docling-project/docling-layout-heron commit8f39ad3c0b4c58e9c2d2c84a38465abf757272d8 ; docling-project/docling-models tagv2.3.0 commitfc0f2d45e2218ea24bce5045f58a389aed16dc23 | Seuls Heron et TableFormer accurate téléchargés, hashes vérifiés. Contrats lus dans Docling2.131 installé ; OCR/structuré encore en correction |
| OCR01 | https://github.com/tesseract-ocr/tessdata_fast ; commit87416418657359cb625c412a48b6e1d6d41c29bd | fra/eng/osd et licence téléchargés avec SHA blobGit puis SHA256 local ; exeWindows existant copié dans projet, provenance du paquet original non authentifiée indépendamment |
| FIX01 | https://docs.reportlab.com/reportlab/userguide/ch2_graphics/ ; metadata officielle PyPI reportlab5.0.1 | API PDF synthétiques lue ; dépendance dev verrouillée. Les fixtures générées ne sont pas le corpus métier |

Les ouvertures web ONNXquantization et certains chapitres ReportLab ont échoué ; aucun contrat non lu n’en est déduit. Les fichiers/source officiels téléchargés ou installés peuvent établir le contrat de leur version, sans certifier leur statut actuel de sécurité.

## Compléments examinés à 02:00 UTC

Les lignes précédentes décrivent l'état à 01:07 UTC. Depuis : services natifs démarrés et arrêtés exit0, modèle Qwen provisionné puis pilote court réel. Preuves : reports/runtime-first-up.json, runtime-first-down.json, cpu-pilot-short-4threads.json. Aucun PASS de performance finale déduit.

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| WIN05 | [Qdrant snapshot_api.rs v1.19.1](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/api/snapshot_api.rs), ouverte et raw lue le30/09 | Routes création, téléchargement et upload/recovery, priorité snapshot et checksum ; restauration vide exécutée, cas collection peuplée encore à vérifier. Pages actuelles qdrant.tech/api inaccessibles au navigateur, non données comme lues |
| WIN06 | [Ollama api/types.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/api/types.go), [adaptateur llama-server versionné](https://github.com/ollama/ollama/blob/v0.35.0/llm/llama_server.go), binaire verrouillé `llama-server --help` | num_thread/num_batch reconnus ; cache256 Mio/checkpoints2 confirmés par log réel. [common/arg.cpp actuel](https://github.com/ggml-org/llama.cpp/blob/master/common/arg.cpp) consulté comme source actuelle distincte, pas identité du build livré |
| OCR02 | [Tesseract5.4.0 config TSV](https://github.com/tesseract-ocr/tesseract/blob/1be261dc226d49bdcad0ab2fcb10f8395edc1225/tessdata/configs/tsv), commit réel derrière tag | Fichier22octets, SHA25659d079bb75d8b3d7c839a3564580cb559e362c93a9d70f234e421c0c3e767e04 ; première URL objet de tag404 conservée, URL commit téléchargée/vérifiée |
| OCR03 | [Installation officielle Tesseract, Windows](https://tesseract-ocr.github.io/tessdoc/Installation.html), [mainteneur du build UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki), consultés30/09 | L'amont renvoie au build maintenu par UB ; présence de ce canal ne prouve pas encore la provenance de l'installation locale copiée |
| WIN07 | [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), section dwShareMode, ouverte le30/09/2026 à02:28 UTC | Partage lecture/écriture/suppression et renommage ; conflit réellement reproduit par handle sans FILE_SHARE_DELETE. Lecture et écriture atomiques concurrentes corrigées, 2/2 tests Win32 PASS ; aucune modification de permissions système |

## Compléments examinés à 03:55 UTC

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| WIN08 | [Microsoft Maximum Path Length Limitation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation), ouverte30/09, page datée16/07/2024 | MAX_PATH260, chemins étendus absolus et conditions de support ; mécanisme Windows, pas garantie Qdrant. Essai étendu réel FAIL conservé ; aucun réglage global appliqué |
| QDR01 | [Qdrant config v1.19.1](https://github.com/qdrant/qdrant/blob/v1.19.1/config/config.yaml), source raw réellement téléchargée/lue dans .runtime/references/qdrant-snapshot-paths | `storage_path`, `snapshots_path`, `temp_path` existent à cette version. Seuls les deux premiers sont configurés ici ; `temp_path` n'est pas prétendu utilisé. Sources snapshots segment/shard du tag aussi reçues ; ouverture navigateur snapshot.rs échoue, raw versionnée lue |
| QDR02 | [Qdrant memory tiers](https://qdrant.tech/documentation/ops-configuration/memory-tiers/), documentation actuelle ouverte30/09, applicable1.19 | on_disk historique déprécié, tiers froid/cache et mmap ; preuve locale11points dans rapports backend. Index HNSW pas construit à11points, aucune qualification25k déduite |
| MOD04 | [IBM Granite fiche au commit](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2/raw/835ad14087e140460703cf0fae09f97d469d65c2/README.md), API HF/JSON de configuration au même commit, réponses HTTP officielles reçues30/09 | CLS/L2/384, prefixes vides, ONNX AVX2 officiel/sha/tailles et licence Apache2 déclarée. Lock comparatif distinct ; documentation éditeur ne prouve pas qualité ni débit CPU local. Aucun LICENSE dans les siblings : ne pas inventer un fichier fourni |
| MOD05 | [Ollama ps](https://docs.ollama.com/api/ps), [tags](https://docs.ollama.com/api/tags), ouvertes30/09 par l'agent API | Digest réel vérifié avant /api/chat, CPU/context et quantification contrôlés ;19 tests gateway isolés PASS, pas une génération réelle |

Les fichiers de preuve sous reports et les skills projet portent les exécutions et limites. Les sources actuelles ne remplacent pas le contrat d'une version verrouillée ; les téléchargements du candidat IBM et son inférence sont des étapes distinctes.

## Compléments examinés entre 08:50 et 09:45 UTC

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| OLL01 | [Ollama llm/llama_server.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/llm/llama_server.go), raw téléchargé 30/09 ≈ 08:57 UTC | `NewLlamaServerRunner` (l. 867-895) passe `--mmproj` sur le GGUF lui-même pour les architectures listées (dont `qwen35`) dès que des tenseurs `v.*` existent ; aucune option ne le désactive. `hasMTPDraft` active le décodage spéculatif si des tenseurs `mtp.` existent. Fonde W006 ; code source, pas mesure. |
| OLL02 | [Ollama server/sched.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/server/sched.go) | `disableMmapDefaultReason` : mmap désactivé par défaut sur CPU ; une option `use_mmap` explicite est respectée. Mesure W007 : sans effet sur le GGUF dérivé (correctif de compatibilité). |
| OLL03 | [Ollama parser/parser.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/parser/parser.go) | Commandes Modelfile acceptées : `FROM`, `PARAMETER`, `LICENSE`, `RENDERER`, `PARSER`, `REQUIRES`, `DRAFT`… ; base de l'import `ollama create` du modèle texte. |
| OLL04 | [Ollama server/model_recommendations.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/server/model_recommendations.go) et [envconfig/config.go](https://github.com/ollama/ollama/blob/v0.35.0/envconfig/config.go) | `refresh` retourne avant toute requête HTTP vers `ollama.com/api/experimental/model-recommendations` si `OLLAMA_NO_CLOUD` est actif ; observation des sockets conforme (reports/ollama-recommendations-netwatch-20260930T0909.json). |
| QDR03 | [Qdrant config v1.19.1, section service](https://github.com/qdrant/qdrant/blob/v1.19.1/config/config.yaml) et [src/actix/auth.rs](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/auth.rs) | `service.api_key` : toute requête doit porter l'en-tête `api-key` ; liste blanche de chemins sans authentification définie dans `auth.rs`. Réponse au défaut D08.3 (Host étranger accepté, reports/host-origin-live-20260930T0930.json) ; intégré le 30/09 (W010), voir QDR04. |
| GIT01 | [Git — gitattributes](https://git-scm.com/docs/gitattributes), ouverte 30/09 ≈ 09:45 UTC | « Unsetting the text attribute on a path tells Git not to attempt any end-of-line conversion upon checkin or checkout » : `* -text` fonde W005 (octets hashés préservés malgré `core.autocrlf=true`). |
| UI01 | Référence de forme locale `D:\enhacements\decodair` (dépôt de l'utilisateur, commit `afbf8e305` observé 30/09) | Principes de shell, charte, composants et format du README ; ni métier ni branding repris. Analyse en cours (R16). |
| DOC01 | [Docling backend pypdfium2 v2.131 installé](https://github.com/docling-project/docling/blob/main/docling/backend/pypdfium2_backend.py) (`.venv/Lib/site-packages/docling/backend/pypdfium2_backend.py`, `_rect_to_display_frame`, `get_text_cells`, `get_size`) ; branche principale relue le 30/09 ≈ 14:30 UTC | Les rectangles PDFium sont tournés avec la taille de la CropBox sans retrait de son origine ; fonde la translation de W009. Code source, pas mesure ; revérifier à chaque mise à jour de Docling. |
| QDR04 | [Qdrant v1.19.1 `src/settings.rs`](https://github.com/qdrant/qdrant/blob/v1.19.1/src/settings.rs), [`src/actix/mod.rs`](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/mod.rs), [`src/actix/auth.rs`](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/auth.rs), [`src/common/auth/mod.rs`](https://github.com/qdrant/qdrant/blob/v1.19.1/src/common/auth/mod.rs) ; fichiers bruts du tag téléchargés le 30/09 à 16:15 UTC dans `.runtime/references/qdrant-auth/` | Surcharge de configuration par variables `QDRANT__…` (séparateur `__`) ; liste blanche sans clé `/`, `/healthz`, `/readyz`, `/livez` (et l'interface web si son dossier existe, absent ici) ; clé lue dans `api-key` ou `Authorization: Bearer`, absence → 401. Vérifié en réel sur le binaire verrouillé (W010). |
| WIN09 | [Microsoft SetConsoleCtrlHandler](https://learn.microsoft.com/en-us/windows/console/setconsolectrlhandler), page datée 12/07/2018, ouverte le 30/09 à 16:32 UTC | « This attribute of ignoring or processing CTRL+C is inherited by child processes. » Explique l'arrêt console inopérant des enfants d'un lanceur qui ignore CTRL+C ; correction et essais dans le journal du 30/09 (16:30–16:37). |
| SEC01 | OWASP Cheat Sheet Series : [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [HTTP Headers](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html), [REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html), [Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) ; pages téléchargées le 30/09 à 16:48 UTC sous `.runtime/references/owasp/` | Entropie d'identifiant ≥ 64 bits, préfixe `__Host-` (Secure, Path=/, sans Domain), délais d'inactivité et absolu selon la criticité, renouvellement à l'ouverture, déconnexion visible ; jeton synchroniseur, en-têtes personnalisés, Fetch Metadata et SameSite en défense en profondeur. Appliqué par W011 ; recommandations génériques, les durées retenues sont un choix du projet. |
| SEC02 | Dépôt de référence `D:\enhacements\decodair` (lecture seule le 30/09), fichiers cités dans [security-reference-decodair-2026-09-30.md](reports/security-reference-decodair-2026-09-30.md) | Mécanismes de session, CSRF, révocation et en-têtes d'une application multi-utilisateur ; transposés selon W011. Ce n'est pas une source officielle : chaque choix repris est vérifié contre SEC01. |
