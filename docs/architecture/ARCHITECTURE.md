# Architecture technique du poste documentaire local

**Rôle :** architecture de l'état livré (composants, flux, interfaces, données, sécurité, déploiement, observabilité) et écarts avec l'exigence V2.1 · **Statut :** Stabilisé · **Référence :** commit `e0be4ac` · **Mis à jour :** 2026-09-30 (UTC) · **Source de vérité :** le code de `services/`, `apps/web/`, `rag.ps1` et le profil `config/local16.yaml` ; les renvois `fichier:ligne` pointent vers la référence · **Remplace :** aucun document (l'exigence reste [SPEC_ARCHITECTURE.md](../../RAG_Local_Agents/SPEC_ARCHITECTURE.md))

Ce document décrit ce qui est implémenté et ce qui a été exécuté, avec la preuve correspondante. Ce qui n'est que codé ou testé unitairement est signalé comme tel ; les écarts avec la [spécification V2.1](../../RAG_Local_Agents/SPEC_ARCHITECTURE.md) sont regroupés en [section 11](#11-écarts-constatés-avec-lexigence-v21).

## Sommaire

1. [Contexte et contraintes](#1-contexte-et-contraintes)
2. [Composants et processus](#2-composants-et-processus)
3. [Flux principaux](#3-flux-principaux)
4. [Ingestion des PDF](#4-ingestion-des-pdf)
5. [Recherche, contexte et génération](#5-recherche-contexte-et-génération)
6. [Interfaces](#6-interfaces)
7. [Données et identités](#7-données-et-identités)
8. [Sécurité](#8-sécurité)
9. [Déploiement](#9-déploiement)
10. [Exploitation et observabilité](#10-exploitation-et-observabilité)
11. [Écarts constatés avec l'exigence V2.1](#11-écarts-constatés-avec-lexigence-v21)

## 1. Contexte et contraintes

| Contrainte | Origine | Effet sur l'architecture |
|---|---|---|
| Un poste Windows 11 x86-64, sans WSL ni Docker | [W001](../../RAG_Local_Agents/DECISIONS.md#w001-plateforme-windows-native) | Binaires Windows officiels de Qdrant et d'Ollama, Python 3.12 isolé, supervision par Job Object |
| 16 Gio physiques partagés avec le navigateur et d'autres applications, CPU seul | D-01, [DEFINITION_OF_DONE.md](../../RAG_Local_Agents/DEFINITION_OF_DONE.md) D07 | Un seul travail lourd à la fois, admission mémoire avant chaque chargement, réserve hôte de 1 536 Mio |
| Mono-utilisateur, hors ligne en exploitation | D-01, D08 | Toutes les écoutes sur 127.0.0.1, même origine pour l'interface et l'API, aucun téléchargement hors provisionnement |
| Traçabilité des réponses | D05, D-11 | Texte source immuable par révision d'extraction, registre de citations par question |

## 2. Composants et processus

![Processus, ports et stockage du poste](../assets/diagrams/processus-ports.svg)

*Processus du poste, ports d'écoute et dossiers de `.runtime/` ; tirets : propriété de processus, trait plein : HTTP local.*

| Composant | Processus lancé | Écoute | Responsabilités | Code |
|---|---|---|---|---|
| Lanceur | `.\rag.ps1 <commande>` dans PowerShell 5.1, qui exécute `.venv\Scripts\python.exe -m services.runtime.cli <commande>` | — | Valide l'environnement, transmet profil et options, rend le code de sortie | [rag.ps1:1-40](../../rag.ps1), [cli.py:416-467](../../services/runtime/cli.py#L416-L467) |
| Superviseur | `python -m services.runtime.cli _serve`, sans fenêtre | — | Verrous, contrôles, lancement et surveillance des enfants dans un Job Object avec arrêt à la fermeture, trace des ressources, arrêt coopératif | [supervisor.py:314-426](../../services/runtime/supervisor.py#L314-L426), [windows_process.py:55-76](../../services/runtime/windows_process.py#L55-L76) |
| Qdrant 1.19.1 | `qdrant.exe --config-path <data>\control\qdrant.yaml --disable-telemetry`, clé d'API reçue par `QDRANT__SERVICE__API_KEY` | 127.0.0.1:6333 HTTP, gRPC désactivé | Vecteurs denses, filtres de périmètre, snapshots ; toute requête hors `/`, `/healthz`, `/readyz`, `/livez` exige l'en-tête `api-key` | [supervisor.py:212-241](../../services/runtime/supervisor.py#L212-L241), [W010](../../RAG_Local_Agents/DECISIONS.md#w010-clé-dapi-qdrant-propre-à-chaque-vie-du-serveur) |
| Ollama 0.35.0 | `ollama.exe serve` ; lance lui-même `llama-server` | 127.0.0.1:11434 ; `llama-server` sur un port local choisi par Ollama | Chargement et exécution de `qwen3.5:4b-text` sur CPU | [supervisor.py:116-139](../../services/runtime/supervisor.py#L116-L139), [relevé des écoutes](../../RAG_Local_Agents/reports/listening-sockets-20260930T0930.json) |
| API | `python -m services.runtime.api_entry` : uvicorn, un worker, `timeout_graceful_shutdown=120` | 127.0.0.1:8785 | Routes `/api/v1`, SSE, file de travaux, réconciliation vectorielle, service de l'export statique | [api_entry.py:10-31](../../services/runtime/api_entry.py#L10-L31), [main.py:32-545](../../services/api/main.py#L32-L545) |
| Worker d'ingestion | `python -m services.ingestion.worker --request … --result …`, sans fenêtre, sorties muettes | — | Préflight, conversion par fenêtres, OCR, écriture des fenêtres et de l'extraction | [jobs.py:80-158](../../services/api/jobs.py#L80-L158), [worker.py:31-77](../../services/ingestion/worker.py#L31-L77) |
| Interface | Fichiers statiques de `apps/web/out`, montés sur `/` par l'API | — | Bibliothèque, lecteur PDF.js, analyse, suivi des traitements | [main.py:542-544](../../services/api/main.py#L542-L544), [apps/web/src/](../../apps/web/src/) |

Les enfants reçoivent un environnement construit explicitement : quelques variables Windows utiles, puis `RAG_PROFILE`, `RAG_DATA_DIR`, les variables hors ligne et sans télémétrie (Hugging Face, Next.js, Ollama), les limites de threads (`OMP_NUM_THREADS=2`…) et la configuration d'Ollama (`OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_MAX_QUEUE=2`, `OLLAMA_CONTEXT_LENGTH`, `OLLAMA_KEEP_ALIVE=10m`, cache de prompt de 256 Mio et deux checkpoints de contexte) ([supervisor.py:116-139](../../services/runtime/supervisor.py#L116-L139)). La clé d'API de Qdrant, tirée à chaque démarrage, n'est transmise qu'à l'enfant Qdrant (`QDRANT__SERVICE__API_KEY`) et à l'API (`RAG_QDRANT_API_KEY`) ; elle n'est écrite ni dans `qdrant.yaml` ni dans `runtime.json`, et le fichier `control/qdrant-api-key` destiné aux outils de l'instance est supprimé à l'arrêt ([supervisor.py:212-226](../../services/runtime/supervisor.py#L212-L226)). Avant chaque création d'enfant, `WindowsJob.launch` rétablit le traitement de CTRL+C, que le lanceur aurait sinon transmis ignoré à Qdrant et Ollama ([windows_process.py:55-63](../../services/runtime/windows_process.py#L55-L63)).

## 3. Flux principaux

### 3.1 Démarrage

`rag.ps1 up` valide le profil (schéma 2, URL `http://127.0.0.1:<port>` sans identifiant ni chemin, `num_gpu` nul), borne le chemin du stockage Qdrant, puis lance le superviseur et attend 150 s au plus son état `running`. Le superviseur prend le verrou de la racine, vérifie les ports, prend le verrou du stockage Qdrant, capture le manifeste des sources, contrôle l'empreinte des binaires, tire la clé d'API de Qdrant et lance Qdrant, Ollama et l'API en attendant la réponse de chacun ([supervisor.py:314-387](../../services/runtime/supervisor.py#L314-L387), [start 429-462](../../services/runtime/supervisor.py#L429-L462)). Toute exception arrête les enfants de la tentative par fermeture du Job Object et écrit l'état `failed` ([supervisor.py:412-426](../../services/runtime/supervisor.py#L412-L426)).

![Séquence de rag.ps1 up](../assets/diagrams/sequence-up.svg)

*Contrôles de `rag.ps1 up` dans l'ordre du code et message de chaque refus.*

Exécutions conservées : premier démarrage et second `up` idempotent ([premier up](../../RAG_Local_Agents/reports/runtime-first-up.json), [second up](../../RAG_Local_Agents/reports/runtime-first-duplicate-up.json)) ; profil restauré relancé sur le code du lot R4 ([up du 30/09 à 13:57](../../RAG_Local_Agents/reports/runtime-restored-newcode-up-20260930T1357.json)).

### 3.2 Arrêt

`rag.ps1 down` crée le marqueur `control/shutdown-<instance>`. Le superviseur passe à `stopping`, crée le marqueur de l'API ; uvicorn s'arrête, la fermeture de l'application annule les questions, demande un checkpoint au worker actif et attend sa fin ([main.py:76-90](../../services/api/main.py#L76-L90), [jobs.py:254-264](../../services/api/jobs.py#L254-L264)). Le superviseur attend l'API 180 s puis envoie une interruption console à Ollama et Qdrant, 30 s chacun ; au-delà, le Job Object termine les processus restants et le mode est consigné (`forced_job_close_after_stop_timeout`) ([supervisor.py:395-411](../../services/runtime/supervisor.py#L395-L411)). `down` rend la main quand l'état devient `stopped` ou `failed`, 250 s au plus ([supervisor.py:465-480](../../services/runtime/supervisor.py#L465-L480)). Exécutions conservées : arrêt forcé de Qdrant et d'Ollama quand le lanceur avait hérité d'un CTRL+C ignoré ([avant correction](../../RAG_Local_Agents/reports/runtime-down-before-ctrlc-fix-20260930T1636.json)), puis arrêt par interruption console, code 0 pour les trois services ([après correction](../../RAG_Local_Agents/reports/runtime-down-after-ctrlc-fix-20260930T1637.json)).

### 3.3 Import, question et sauvegarde

L'ingestion est décrite en [section 4](#4-ingestion-des-pdf), la question en [section 5](#5-recherche-contexte-et-génération), la sauvegarde dans [SAUVEGARDE-RESTAURATION.md](../exploitation/SAUVEGARDE-RESTAURATION.md).

## 4. Ingestion des PDF

![Chaîne d'ingestion](../assets/diagrams/ingestion.svg)

*Étapes d'un travail d'ingestion, voies de routage d'une page et règles de révision.*

| Étape | Comportement livré | Code |
|---|---|---|
| Import | 1 à 50 fichiers par requête, chemins relatifs validés (ni absolu, ni `..`, ni nom réservé Windows, extension `.pdf`), flux écrit dans `uploads/*.part` avec SHA-256 et limite de taille, signature `%PDF-` exigée dans le premier kilo-octet, déplacement atomique vers `originals/<sha256>.pdf`, version et travail créés ; réponse 202 | [main.py:297-344](../../services/api/main.py#L297-L344), [db.py:26-46](../../services/api/db.py#L26-L46) |
| File | Un travail `queued` à la fois, dans l'ordre de création ; attend tant qu'une question est active, qu'une pause est demandée ou que le verrou lourd du poste est tenu ailleurs | [jobs.py:54-78](../../services/api/jobs.py#L54-L78), [resources.py:246-249](../../services/runtime/resources.py#L246-L249) |
| Admission | Verrou lourd du poste, déchargement du modèle Ollama, admission à 2 304 + 1 536 Mio ; sinon travail `paused` avec son motif | [resources.py:298-317](../../services/runtime/resources.py#L298-L317), [main.py:48-50](../../services/api/main.py#L48-L50) |
| Worker | Réutilise une extraction vérifiée en cache ; sinon lance le worker, relaie annulation et pause par le fichier `checkpoint-request` ; chien de garde : 300 s sans nouvelle fenêtre durable, arrêt ciblé du worker, travail en pause avec le code `interrupted` et repris depuis les fenêtres écrites | [jobs.py:80-158](../../services/api/jobs.py#L80-L158) |
| Préflight | PDFium : taille, nombre de pages (2 000 au plus), chiffrement (`PDF_ENCRYPTED`), boîtes MediaBox, CropBox et boîte effective, classement natif, scan ou blanc | [preflight.py:63-100](../../services/ingestion/preflight.py#L63-L100) |
| Fenêtres | Fenêtres de 4 pages ; chaque fenêtre complète est écrite (`window-XXXXXX-YYYYYY.json`) et relue à la reprise ; une fenêtre en échec de conversion est reconvertie ; contrôle `ORIGINAL_CHANGED` en fin de lecture | [pipeline.py:241-298](../../services/ingestion/pipeline.py#L241-L298), [checkpoint.py](../../services/ingestion/checkpoint.py) |
| Routage | Voir le tableau suivant ; une page native qui échoue au contrôle de qualité est reconvertie en structuré (`NATIVE_ESCALATED_TO_STRUCTURED`) | [pipeline.py:44-90](../../services/ingestion/pipeline.py#L44-L90), [pipeline.py:161-180](../../services/ingestion/pipeline.py#L161-L180) |
| Assemblage | Sections portées d'une fenêtre à l'autre ; continuité de tableau entre pages adjacentes seulement avec mêmes en-têtes, mêmes colonnes, même section et positions en bord de page ; couverture par page ; état `ready`, `ready_partial` ou `interrupted` | [pipeline.py:206-238](../../services/ingestion/pipeline.py#L206-L238) |
| Indexation | Fragments d'environ 320 jetons E5 (chevauchement de 48 au plus), embeddings mis en cache par identité du modèle et hash du texte, envoi à Qdrant par lots de 64 avec attente puis relecture des hash | [indexing.py:20-195](../../services/api/indexing.py#L20-L195), [retrieval.py:164-173](../../services/api/retrieval.py#L164-L173) |
| Publication | Compte des fragments vérifié ; génération active remplacée dans une transaction ; ancienne génération marquée pour nettoyage vectoriel ; une extraction partielle n'est publiée que par `POST /jobs/{id}/publish-partial` | [indexing.py:197-216](../../services/api/indexing.py#L197-L216), [main.py:507-516](../../services/api/main.py#L507-L516) |
| Redémarrage de l'API | Travaux en cours passés à `paused` avec le code `interrupted` ; reprise manuelle | [db.py:118-124](../../services/api/db.py#L118-L124) |

| Voie (`page_route`) | Condition | Traitement |
|---|---|---|
| `blank` | Aucun contenu visible | Page comptée, aucun bloc |
| `regional_ocr` | Régions image non couvertes ou couche texte dégradée (`needs_ocr`) | Pipeline Docling de mise en page et de tableaux avec OCR Tesseract CLI `fra`+`eng` limité aux régions (mode `PDF_AWARE_LAYOUT_REGIONS` quand la version installée le propose) ; mot sous 0,8 de confiance : région non résolue |
| `structured` | 8 tracés vectoriels ou plus, deux colonnes de 3 régions au moins, texte clairsemé avec tracés, tailles de police différentes (rapport ≥ 1,3 et écart ≥ 2 pt), ou page non native | Pipeline Docling avec modèles locaux de mise en page (Heron) et de tableaux (TableFormer, mode `ACCURATE`), sans OCR |
| `native` | Page native simple | Pipeline natif de Docling (`NativePdfPipelineOptions`), sans OCR ; contrôle : 95 % des caractères alphanumériques retrouvés, blocs localisés, ordre vertical monotone |

Les options de chaque voie sont fixées dans [docling_adapter.py:67-99](../../services/ingestion/docling_adapter.py#L67-L99). Le backend PDF de Docling est choisi par `pdf.pdf_backend` ([config.py:37](../../services/ingestion/config.py#L37) : `docling_parse` par défaut du code, `pypdfium2` accepté). Le profil `local16` retient `pypdfium2` avec une translation des coordonnées PDFium vers la CropBox d'origine zéro, appliquée par `crop_translation` et `crop_consistent_pdfium_page_class` ([lifecycle.py:107-165](../../services/ingestion/lifecycle.py#L107-L165)) ([W009](../../RAG_Local_Agents/DECISIONS.md#w009-backend-pdf-nominal-pypdfium2-avec-repère-cropbox-corrigé)). Cette correction est validée sur les fixtures synthétiques, pas sur le corpus métier, et doit être revérifiée à chaque mise à jour de Docling.

Le worker active `faulthandler` : une faute native observée rend l'extraction non publiable (`INGESTION_NATIVE_FAULT`), et un journal de faute antérieur met l'extraction en quarantaine (`EXTRACTION_QUARANTINED`) ([worker.py:41-65](../../services/ingestion/worker.py#L41-L65)).

## 5. Recherche, contexte et génération

![Séquence d'une question](../assets/diagrams/sequence-question.svg)

*Échanges d'une question, de la recherche hybride à l'ouverture d'une citation.*

| Étape | Comportement livré | Code |
|---|---|---|
| File des questions | Au plus 1 + `llm.max_pending_generations` (2) questions `queued` ou `running`, sinon 429 `query_queue_full` ; une seule question traitée à la fois | [query.py:27-54](../../services/api/query.py#L27-L54), [query.py:172](../../services/api/query.py#L172) |
| Périmètre | Résolution en générations publiées, versions, pages et blocs autorisés, avec avertissements (`document_not_in_scope`, `comparison_incomplete`, `dense_unavailable_for_historical_revision`) | [scope.py](../../services/api/scope.py) |
| Relances | Référent repris des questions précédentes de la conversation seulement s'il est unique et encore dans le périmètre ; plusieurs candidats : événement `needs_clarification` ; l'historique n'est jamais une preuve | [query.py:56-110](../../services/api/query.py#L56-L110) |
| Lexical | FTS5 `bm25(chunks_fts, 2.0, 1.0)` filtré par périmètre ; identifiants exacts (table `identifiers`) placés en tête puis classés par le BM25 de la question ; 24 résultats | [retrieval.py:183-204](../../services/api/retrieval.py#L183-L204) |
| Dense | Requête E5 préfixée `query: `, requête Qdrant `points/query` sur le vecteur `dense`, filtre de périmètre, `hnsw_ef` 64, 24 résultats | [retrieval.py:154-162](../../services/api/retrieval.py#L154-L162) |
| Fusion | RRF k = 60, identifiants exacts gardés devant | [retrieval.py:92-98](../../services/api/retrieval.py#L92-L98), [retrieval.py:206-231](../../services/api/retrieval.py#L206-L231) |
| Sélection | Preuve réservée à chaque identifiant de la question, dédoublonnage par parent et par texte, 6 fragments au plus (8 en comparaison ou pour plusieurs identifiants), avertissements `identifier_not_found_in_scope`, `partial_extraction` | [retrieval.py:233-309](../../services/api/retrieval.py#L233-L309) |
| Contexte | Expansion au parent (900 jetons au plus), budget d'instructions de 1 024 jetons, budget de preuves 1 536, 2 560 ou 5 120 selon le mode, comptage par le tokenizer Qwen ; fragments écartés signalés | [context.py:157-245](../../services/api/context.py#L157-L245) |
| Admission | Verrou lourd du poste ; si le modèle n'est pas chargé et la mémoire insuffisante, libération des sessions E5 et des tokenizers ; admission à 3 456 + 1 536 Mio (modèle froid) ou au pic additionnel déclaré par le modèle chargé ; attente de 120 s au plus avec remesure toutes les 2 s | [main.py:51-68](../../services/api/main.py#L51-L68), [resources.py:141-155](../../services/runtime/resources.py#L141-L155), [resources.py:319-376](../../services/runtime/resources.py#L319-L376) |
| Génération | Vérification de l'identité du modèle (digest et manifeste), `POST /api/chat` en flux, `think: false`, `num_gpu: 0`, `num_thread` = min(4, cœurs physiques − 1) ; réserve surveillée toutes les 0,5 s | [ollama.py:111-135](../../services/api/ollama.py#L111-L135) |
| Validation | Dépassement du contexte réel refusé (`runtime_context_exceeded`), écart de comptage signalé ; identifiants inconnus remplacés, images Markdown et balises HTML retirées ; `done.citations` ne contient que les sources citées, toutes les sources retenues restant enregistrées et consultables par leur `citation_url` | [query.py:234-255](../../services/api/query.py#L234-L255), [context.py:252-265](../../services/api/context.py#L252-L265) |

État d'exécution : une génération réelle a été admise sur l'instance restaurée (réponse partielle « 3,1 bar [S001] ») puis annulée par la surveillance de la réserve ([preuve](../../RAG_Local_Agents/reports/backend/2026-09-30-restored-question-20260930T0927.json)) ; la dernière tentative est refusée à l'échéance de l'attente ([preuve](../../RAG_Local_Agents/reports/backend/2026-09-30-restored-question-w008-20260930T1405.json)). Aucune réponse complète n'est encore qualifiée.

## 6. Interfaces

| Interface | Participants | Forme | Référence |
|---|---|---|---|
| HTTP `/api/v1` et SSE | Navigateur, outils de qualification, CLI (administration) | JSON, `text/event-stream` | [API.md](../interfaces/API.md) |
| Contrat partagé | API, interface, ingestion | JSON versionné (`schema_version` 2) : périmètre, page, bloc, fragment, source, événements, erreur, frontières | [contracts.json](../../packages/contracts/contracts.json) |
| API ↔ worker | `JobSupervisor`, `services.ingestion.worker` | Fichiers `worker-request.json`, `worker-result.json` (`{"ok": true, "result": …}` ou `{"ok": false, "error": …}`), `checkpoint-request`, `window-*.json`, `extraction.json` | [jobs.py:80-158](../../services/api/jobs.py#L80-L158), [worker.py](../../services/ingestion/worker.py) |
| Superviseur ↔ API | Superviseur, `api_entry` | Variables `RAG_SHUTDOWN_MARKER`, `RAG_CONTROL_TOKEN` et `RAG_QDRANT_API_KEY` ; en-tête `X-RAG-Control-Token` | [supervisor.py:378-383](../../services/runtime/supervisor.py#L378-L383), [main.py:166-170](../../services/api/main.py#L166-L170) |
| CLI ↔ superviseur | `start`, `stop`, `status`, `backup` | `control/runtime.json` (état, identités PID + date de création + exécutable), marqueur `shutdown-<instance>` | [supervisor.py:45-60](../../services/runtime/supervisor.py#L45-L60) |
| API ↔ gouverneur | `QueryService`, `JobSupervisor` | `snapshot()`, `generation()`, `ingestion()`, `begin_interactive()`, `allow_ingestion()`, `should_checkpoint()` | [resources.py:179-376](../../services/runtime/resources.py#L179-L376) |
| API ↔ Qdrant | `QdrantStore` | HTTP REST avec en-tête `api-key` (variable de l'instance, sinon `control/qdrant-api-key`) : collections, index de payload, `points`, `points/query`, snapshots | [retrieval.py:100-176](../../services/api/retrieval.py#L100-L176), [settings.py:50-57](../../services/api/settings.py#L50-L57) |
| API ↔ Ollama | `OllamaGateway` | `/api/tags`, `/api/ps`, `/api/chat` (flux), `/api/generate` avec `keep_alive: 0` pour décharger | [ollama.py](../../services/api/ollama.py) |

## 7. Données et identités

La base SQLite (`<data_dir>/app.sqlite3`, WAL, clés étrangères) est la source de vérité ; Qdrant n'en porte qu'une projection vectorielle. Tables des migrations `001` à `003` : `schema_version`, `folders`, `documents`, `document_versions`, `extraction_revisions`, `index_generations`, `pages`, `sections`, `blocks`, `tables_data`, `chunks`, `chunk_sources`, `identifiers`, `chunks_fts`, `jobs`, `conversations`, `query_runs`, `messages`, `citations`, `events`, `embedding_cache`, `vector_cleanup`. Au démarrage, une base de schéma plus récent que le code est refusée (`database_schema_too_new`) et la présence de FTS5 est contrôlée ([db.py:104-117](../../services/api/db.py#L104-L117)).

| Identité | Construction | Rôle |
|---|---|---|
| Version | Document + SHA-256 de l'original (unique par document) | Un réimport identique ne crée pas de nouvelle version |
| Révision d'extraction | `uuid5(version, SHA-256, empreinte du pipeline)` | Une citation garde la révision qui l'a produite |
| Génération d'index | Empreinte de l'extraction, identités E5 et du tokenizer Qwen, réglages de découpage ([indexing.py:70-74](../../services/api/indexing.py#L70-L74)) | Une nouvelle génération reste invisible jusqu'à sa publication |
| Fragment | `uuid5(génération, bloc:début:fin)` | Identifiant de point Qdrant, stable pour une génération |
| Citation | `(query_id, source_id)` avec `S001`, `S002`… | Registre propre à chaque question |

Coordonnées : points PDF de l'espace utilisateur non tourné, boîtes MediaBox, CropBox et rotation conservées, `page_index` à partir de 0 et `page_number` = `page_index` + 1 (`coordinate_system` de [contracts.json](../../packages/contracts/contracts.json)). Les décalages de sélection sont des points de code Unicode sur le texte source haché.

La collection Qdrant `pdf_chunks_e5small_v1` est créée à la première indexation depuis `RAG_Local_Agents/config/qdrant.collection.json`, puis ses paramètres effectifs sont relus et refusés s'ils diffèrent : vecteur `dense` de 384 dimensions en cosinus sur disque, payload sur disque, graphe HNSW en mémoire, une seule réplique, un thread d'optimisation ; index de payload `generation_id`, `version_id`, `document_id`, `page_indices`, `block_ids` ([retrieval.py:134-152](../../services/api/retrieval.py#L134-L152)).

## 8. Sécurité

| Mesure | Comportement | Code | Vérification |
|---|---|---|---|
| Profil en boucle locale | URL HTTP `127.0.0.1` à port explicite, sans identifiant, chemin, requête ni fragment ; `num_gpu` nul | [supervisor.py:24-38](../../services/runtime/supervisor.py#L24-L38), [settings.py:14-32](../../services/api/settings.py#L14-L32) | [tests de profil](../../RAG_Local_Agents/reports/runtime-profile-loopback.xml) |
| Frontière HTTP | `Host` limité à `127.0.0.1:<port>`, `localhost:<port>`, `[::1]:<port>` (400) ; `Origin` étrangère (403) ; `Sec-Fetch-Site: cross-site` (403) ; corps limité à la taille maximale de PDF + 1 Mio (413) ; en-têtes `nosniff`, `no-referrer`, CSP `default-src 'self'`, `frame-ancestors 'none'` | [main.py:114-144](../../services/api/main.py#L114-L144) | [essai sur serveur réel](../../RAG_Local_Agents/reports/host-origin-live-20260930T0930.json) |
| Administration | Jeton aléatoire de 32 octets régénéré à chaque lancement, comparé en temps constant, fichier supprimé à la fin du superviseur | [supervisor.py:336-337](../../services/runtime/supervisor.py#L336-L337), [main.py:166-170](../../services/api/main.py#L166-L170) | [Tests HTTP en processus](../../tests/integration/test_api_http.py) |
| Qdrant | Clé d'API aléatoire propre à chaque démarrage ; sans elle, 401 sur toute route hors `/`, `/healthz`, `/readyz`, `/livez`, y compris avec un `Host` ou une `Origin` étrangers ; la restauration utilise sa propre clé | [supervisor.py:212-226](../../services/runtime/supervisor.py#L212-L226), [backup.py:299-333](../../services/runtime/backup.py#L299-L333) | [Gardes HTTP réelles, 15/15](../../RAG_Local_Agents/reports/http-guards-live-20260930T1636.json), [test sur le binaire](../../tests/integration/test_runtime_qdrant_auth.py) |
| Chemins importés | Chemin relatif sûr exigé (décodage répété, `..`, lecteurs, caractères et noms réservés Windows refusés) | [db.py:26-46](../../services/api/db.py#L26-L46) | [Tests de stockage](../../tests/unit/test_api_storage.py) |
| Sauvegardes | Chemins de snapshot relatifs sans `..`, antislash ni deux-points ; liens symboliques et points de reparse refusés à la copie | [backup.py:82-124](../../services/runtime/backup.py#L82-L124) | [tests de sauvegarde](../../RAG_Local_Agents/reports/runtime-backup-tests-final.xml) |
| Réponses | Aucun HTML ni image distante rendus ; identifiants de citation filtrés par le registre | [context.py:252-265](../../services/api/context.py#L252-L265) | Scénario E2E `hostile-markup` écrit, non exécuté |
| Environnement des enfants | Seules des variables Windows listées sont héritées : aucun identifiant de service ni réglage d'autres projets | [supervisor.py:116-123](../../services/runtime/supervisor.py#L116-L123) | Relecture de code |

Limites : une instance démarrée avant l'introduction de la clé (W010) reste sans clé jusqu'à son redémarrage ; la clé circule en clair sur la boucle locale (pas de TLS) ; le blocage réseau système (D08.1) n'est pas exécuté ; la page `/api/docs` dépend d'un CDN bloqué par la CSP (non examinée au rendu).

## 9. Déploiement

Un seul poste, sans installation système : `bootstrap.ps1` prépare uv et CPython dans `.runtime/`, `rag.ps1 provision` récupère les artefacts verrouillés par [`artifacts.lock.json`](../../config/artifacts.lock.json) (URL figée sur une version ou un commit, licence, SHA-256 de l'éditeur ou SHA-1 de blob Git) et réutilise tout fichier déjà vérifié ([artifacts.py:64-86](../../services/runtime/artifacts.py#L64-L86)), construit l'interface avec `NODE_OPTIONS=--max-old-space-size=2048` et prépare le modèle ([cli.py:382-413](../../services/runtime/cli.py#L382-L413)). Les empreintes réellement extraites sont écrites dans `.runtime/manifests/artifacts.json` et revérifiées à chaque lancement pour Qdrant et Ollama ([supervisor.py:165-184](../../services/runtime/supervisor.py#L165-L184)). Le modèle `qwen3.5:4b-text` est dérivé localement du modèle source en retirant les seuls tenseurs de vision, chaque tenseur texte étant vérifié par SHA-256 ([W006](../../RAG_Local_Agents/DECISIONS.md#w006-modèle-qwen-texte-seul-dérivé-localement-sans-encodeur-vision), [text_model.py](../../services/runtime/text_model.py)). Procédures : [EXPLOITATION.md](../exploitation/EXPLOITATION.md).

## 10. Exploitation et observabilité

| Point d'observation | Ce qu'il montre | Emplacement | Ce qu'il ne montre pas |
|---|---|---|---|
| `rag.ps1 status` | État enregistré, identités revalidées, `stale` si le superviseur a disparu, concordance du profil | `control/runtime.json` | La disponibilité des index et du modèle |
| `rag.ps1 doctor` | Versions, verrou des modèles, fichiers OCR et embedding, ports (`owned`, `foreign`, `occupied_unknown_owner`), marge d'admission, santé et disponibilité HTTP, modèles chargés | sortie JSON, `-Report` | Une réponse complète ; la cohérence SQLite/Qdrant (`index_consistency: not_exposed`) |
| `GET /api/v1/health` | Processus API vivant | HTTP | Stores, modèles |
| `GET /api/v1/readiness` | SQLite, fichiers E5 et tokenizer, collection Qdrant, modèle listé par Ollama, gouverneur ; 503 avec `blockers` | HTTP | Qualité ou latence |
| `GET /api/v1/diagnostics` | Versions, ressources du gouverneur, identités dense et tokenizer, caches, empreintes du profil et du sélecteur, réconciliation | HTTP | Contenu documentaire (jamais exposé) |
| `GET /api/v1/jobs` | État, étape, progression, tentatives, couverture, avertissements | HTTP | Progression intra-fenêtre |
| Événements SSE `done` | Métriques par question : `queue_wait_ms`, `retrieval_ms`, `context_ms`, `generation_admission_wait_ms`, `ttft_ms`, `elapsed_ms`, compteurs de jetons | SQLite `events` | Mesures agrégées (p95) |
| Journaux d'instance | `qdrant.log`, `ollama.log`, `api.log` (sans journal d'accès), `resources.jsonl` (un relevé par seconde, 5 Mio × 3 fichiers), `source-manifest.json` | `<data_dir>/logs/<instance>/` | — |
| Démarrage du superviseur | Sortie du superviseur avant son état `running` | `<data_dir>/control/supervisor-start.log` | — |
| Traces du worker | `worker-lifecycle.jsonl`, `worker-native-fault.log`, `native-fault.json` | `<data_dir>/extractions/<version>/<travail>/` | — |

## 11. Écarts constatés avec l'exigence V2.1

| Exigence (source) | État livré | Preuve | Conséquence |
|---|---|---|---|
| Interface sur le port 8765 ([SPEC §3](../../RAG_Local_Agents/SPEC_ARCHITECTURE.md#3-architecture-dexécution)) | Port 8785 : un programme Python existant du poste occupe 8765 | [config/local16.yaml](../../config/local16.yaml), [plan](../../RAG_Local_Agents/PLAN.md#points-vérifiés-et-décisions-restantes) | Aucune ; la spécification garde l'ancienne valeur |
| Commandes `uv run python scripts/provision.py`, `start.py`, `verify.py --suite smoke`… ([IMPLEMENTATION §9](../../RAG_Local_Agents/IMPLEMENTATION.md#9-déploiement-et-commandes-à-livrer)) | Entrée unique `rag.ps1 <commande>` ; `verify -Path` contrôle un snapshot, pas une suite de tests ; `restore` exige `-Path` et `-Target` | [rag.ps1](../../rag.ps1) | Les suites de tests se lancent par pytest et Playwright |
| Types TypeScript générés depuis OpenAPI ([IMPLEMENTATION §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http)) | Types écrits à la main, alignés sur `contracts.json` | [types.ts](../../apps/web/src/lib/types.ts) | Dérive possible entre API et interface, couverte par les tests unitaires et E2E |
| Liste des événements SSE du contrat | `contracts.json` liste 7 types ; le code émet aussi `needs_clarification`, prévu par IMPLEMENTATION §2 | [query.py:45](../../services/api/query.py#L45) | Contrat partagé à compléter |
| États de travail `pause_requested`, `checkpointed`, `completed` ([IMPLEMENTATION §10](../../RAG_Local_Agents/IMPLEMENTATION.md#10-extraction-et-ordonnancement--contrats-de-processus)) | États `queued`, `extracting`, `indexing`, `pausing`, `paused`, `cancelling`, `cancelled`, `ready`, `ready_partial`, `error` | [jobs.py:212-252](../../services/api/jobs.py#L212-L252) | Même sémantique coopérative, noms différents |
| `status` distingue disponible, dégradé et mémoire insuffisante ([EXPLOITATION_WINDOWS.md](../../RAG_Local_Agents/EXPLOITATION_WINDOWS.md#commandes-et-prérequis)) | `status` rend l'état du superviseur (`stopped`, `starting`, `running`, `stopping`, `failed`, `stale`) ; disponibilité et mémoire relèvent de `doctor` et de `/readiness` | [supervisor.py:483-493](../../services/runtime/supervisor.py#L483-L493) | Utiliser `doctor` pour un diagnostic |
| Schéma de collection sous `config/` | Lu depuis `RAG_Local_Agents/config/qdrant.collection.json`, faute de copie dans `config/` | [retrieval.py:134-141](../../services/api/retrieval.py#L134-L141) | Le runtime dépend d'un fichier du dossier vivant |
| Clés de profil déclaratives | Non lues par le code : `app.log_document_text`, `app.telemetry`, `app.asgi_workers` (un worker codé en dur), `llm.max_active_generations`, `resources.application_target_max_mib`, `resources.unload_llm_before_ingestion` (déchargement systématique), `resources.scheduling.kill_on_interactive_request`, `qdrant.vector_storage_initial`, `qdrant.hnsw_storage_initial`, `sqlite.path` (base placée dans `app.data_dir`, sauf variable `RAG_DB_PATH`) | recherche dans `services/` | Le comportement tient au code ; modifier ces clés n'a pas d'effet |
| Aucune ressource distante | `GET /api/docs` (Swagger de FastAPI) référence un CDN, bloqué par la CSP | [main.py:92](../../services/api/main.py#L92) | Scripts de la page bloqués par la CSP, rendu non examiné ; `/openapi.json` reste local |
