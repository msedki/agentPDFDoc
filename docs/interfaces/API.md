# Interface HTTP et SSE de l'API locale

**Rôle :** référence des routes `/api/v1` réellement déclarées, de leurs erreurs notables, du flux SSE des questions et des en-têtes exigés · **Statut :** Stabilisé · **Référence :** commit `e0be4ac` · **Mis à jour :** 2026-09-30 (UTC) · **Source de vérité :** [services/api/main.py](../../services/api/main.py) (routes et frontière), [services/api/schemas.py](../../services/api/schemas.py) (corps validés), [packages/contracts/contracts.json](../../packages/contracts/contracts.json) (contrat partagé) · **Remplace :** aucun document (le contrat d'origine reste [IMPLEMENTATION.md §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http))

L'API écoute sur `http://127.0.0.1:8785` (profil `local16`, clé `app.port`) avec un seul worker uvicorn. Elle sert aussi l'interface statique sur `/` (`/workspace/` pour le poste de travail). Les exemples utilisent PowerShell 5.1, dont les cmdlets web envoient un `Host` conforme ; ils n'ont pas été rejoués pour ce document et n'emploient que les routes et champs décrits ici.

## Sommaire

1. [Frontière locale et en-têtes](#1-frontière-locale-et-en-têtes)
2. [Format des erreurs](#2-format-des-erreurs)
3. [Routes](#3-routes)
4. [Flux SSE d'une question](#4-flux-sse-dune-question)
5. [Corps de requête](#5-corps-de-requête)
6. [Écarts avec le contrat partagé](#6-écarts-avec-le-contrat-partagé)

## 1. Frontière locale et en-têtes

Chaque requête traverse le middleware `local_boundary` ([main.py:114-144](../../services/api/main.py#L114-L144)) avant toute route.

| Contrôle | Règle | Refus |
|---|---|---|
| `Host` | `127.0.0.1:<port>`, `localhost:<port>` ou `[::1]:<port>`, casse ignorée | 400 `invalid_host` « Host non autorisé. » |
| `Origin` (si présent) | `http://` suivi de l'un des hôtes ci-dessus ; `Origin: null` est refusé | 403 `invalid_origin` « Origine non autorisée. » |
| `Sec-Fetch-Site` | `cross-site` refusé | 403 `cross_site_request` « Requête intersite refusée. » |
| `Content-Length` (POST, PUT, PATCH, DELETE) | Au plus `pdf.max_file_mib` (200 Mio) + 1 Mio | 413 `request_too_large` |
| Sauvegarde en cours | Mutations hors `/api/v1/admin/` suspendues | 503 `mutations_paused` « Sauvegarde en cours ; mutations suspendues. » |
| Administration | En-tête `X-RAG-Control-Token` égal au jeton du lancement courant | 403 `invalid_control_token` |

Les réponses des requêtes admises par ces contrôles portent `X-Request-ID`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` et `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'`. Aucun en-tête CORS n'est émis. Vérification sur serveur réel : [essai du 30/09](../../RAG_Local_Agents/reports/host-origin-live-20260930T0930.json).

## 2. Format des erreurs

```json
{"code": "document_not_found", "message": "Document inconnu.", "details": {}, "request_id": "<uuid>"}
```

Une erreur de validation Pydantic rend 422 `validation_error` avec `details.fields` (emplacement et type, sans valeur). Une exception imprévue rend 500 `internal_error` « Erreur interne ; consulter les diagnostics locaux. », sans trace ([main.py:146-157](../../services/api/main.py#L146-L157)).

## 3. Routes

Préfixe `/api/v1` omis dans la colonne Chemin. Les numéros de ligne renvoient à [main.py](../../services/api/main.py).

### 3.1 Santé et diagnostic

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/health` | Processus vivant, sans accès aux stores (l. 231) | 200 `{"status": "alive", "service": "rag-api"}` |
| GET | `/readiness` | Contrôle SQLite (`quick_check`), fichiers E5 et tokenizer Qwen, collection Qdrant, modèle listé par Ollama, gouverneur (l. 235) | 200 `ready` ; 503 `blocked` avec `checks` et `blockers` (`qdrant_not_ready` tant que la collection n'existe pas) |
| GET | `/diagnostics` | Versions, ressources du gouverneur, identités dense et tokenizer, caches, empreinte du profil et du sélecteur, réconciliation (l. 518) | 200 ; aucun extrait documentaire |

### 3.2 Bibliothèque et documents

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/library/tree?limit&offset&cursor&search` | Tous les dossiers et les documents non retirés, paginés (1 à 200), filtre par sous-chaîne du chemin (l. 280) | 400 `invalid_cursor`, `invalid_pagination` |
| POST | `/documents/import` | Multipart : `files` (1 à 50 PDF) et `relative_paths` (liste JSON facultative, un chemin par fichier) (l. 297) | 202 `{imports: [{document_id, version_id, job_id, reused}]}` ; 400 `invalid_file_count`, `invalid_paths`, `invalid_path`, `invalid_pdf` ; 409 `original_integrity_failure`, `document_removed` ; 413 `file_too_large` |
| GET | `/documents/{document_id}` | Document, versions (avec `file_url`), travaux (l. 346) | 404 `document_not_found` |
| DELETE | `/documents/{document_id}` | Retrait logique : document exclu des périmètres, travaux annulés, vecteurs mis en nettoyage (l. 358) | 404 `document_not_found` |
| POST | `/documents/{document_id}/move` | Déplace ou renomme dans l'arborescence sans nouveau travail ni recalcul d'embedding (l. 368) | 404 `document_not_found` ; 409 `path_conflict` |
| POST | `/documents/{document_id}/reindex` | Nouveau travail sur la dernière version ; renvoie le travail en cours s'il existe (l. 372) | 202 `{job_id, version_id, reused}` ; 404 `document_not_found` |

Un réimport d'un contenu identique au même chemin renvoie le travail existant (`reused: true`), avec `resume_required: true` s'il est en pause ([db.py:158-187](../../services/api/db.py#L158-L187)).

### 3.3 Versions et lecture

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/versions/{version_id}/file` | PDF original, `inline`, `ETag` = SHA-256, cache immuable, plages d'octets (`Range`) prises en charge par `FileResponse` de Starlette 1.7.0 (l. 384) ; parcours ETag et plages de la recette lifecycle non exécuté | 304 si `If-None-Match` correspond ; 404 `source_removed` ; 409 `invalid_storage_path` |
| GET | `/versions/{version_id}/outline?extraction_revision_id` | Sections de la génération publiée ou de la révision demandée (l. 392) | 404 `extraction_revision_not_found` ; 409 `not_indexed` |
| GET | `/versions/{version_id}/pages/{page_index}/blocks?extraction_revision_id` | Géométrie de la page, blocs (texte, `bbox`, précision, provenance), avertissements de la génération (l. 400) | 404 `page_not_found`, `extraction_revision_not_found` ; 409 `not_indexed` |

### 3.4 Recherche, questions et citations

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| POST | `/search` | Recherche hybride sans modèle de langue : `results`, `top10`, `scope_snapshot`, `warnings`, `elapsed_ms` (l. 419) | 404 `folder_not_found`, `section_not_found`, `source_removed` ; 409 `no_document_in_scope` ; 400 `invalid_selection`, `invalid_page_range` |
| POST | `/queries` | Crée une question et lance son traitement (l. 426) | 202 `{query_id, conversation_id, events_url}` (plus `state: needs_clarification` si un référent est ambigu) ; 429 `query_queue_full` ; 404 `conversation_not_found`, `focus_not_found`, `followup_not_found` ; 409 `focus_outside_scope` |
| GET | `/queries/{query_id}/events?after` | Flux SSE reprenable (l. 430) ; voir [section 4](#4-flux-sse-dune-question) | 404 `query_not_found` ; 400 `invalid_event_id` |
| POST | `/queries/{query_id}/cancel` | Annulation immédiate ; coupe aussi l'appel au modèle (l. 458) | `{query_id, state}` ; 404 `query_not_found` |
| GET | `/citations/{query_id}/{source_id}` | Source enregistrée : document, version, page, blocs, boîtes, précision, révision (l. 462) | 404 `citation_not_found`, `source_removed` |

### 3.5 Travaux d'ingestion

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/jobs?limit` | Travaux récents avec couverture, avertissements, publication (l. 470) | 400 `invalid_pagination` |
| POST | `/jobs/{job_id}/pause` | Pause coopérative : `pausing` si le travail tourne, sinon `paused` (l. 485) | 404 `job_not_found` ; 409 `job_not_pauseable` |
| POST | `/jobs/{job_id}/resume` | Remet en file un travail `paused`, `error` ou `cancelled` (l. 481) | 409 `job_not_resumable`, `retry_limit` (trois tentatives en erreur), `interaction_active` |
| POST | `/jobs/{job_id}/cancel` | Annulation : `cancelling` si le travail tourne (l. 477) | 404 `job_not_found` |
| POST | `/jobs/{job_id}/publish-partial` | Publie une extraction `ready_partial` vérifiée (l. 507) | 404 `job_not_found` ; 409 `not_partial` |
| POST | `/runtime/mode` | `{"mode": "interactive"}` met les imports en pause ; `{"mode": "ingestion"}` lève la pause sans reprendre automatiquement les travaux en pause (l. 489) | 409 `interaction_active` ; 503 `governor_not_configured` |

### 3.6 Administration (jeton requis)

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| POST | `/admin/quiesce` | Suspend les mutations, attend celles en cours, annule les questions, met le travail actif au checkpoint, exécute `PRAGMA wal_checkpoint(FULL)` (l. 172) | 403 `invalid_control_token` |
| POST | `/admin/resume` | Relance les mutations et la réconciliation (l. 186) | 403 `invalid_control_token` |
| GET | `/admin/status` | Mutations suspendues, questions actives, travail actif (l. 195) | 403 `invalid_control_token` |
| POST | `/admin/evaluation/context` | Contexte d'une question sans appel au modèle, pour la qualification (l. 200) | 409 `ingestion_active`, `query_active` ; 503 `mutations_paused` |

Le jeton est lu dans `<data_dir>\control\admin-token` pendant la vie de l'instance ; `rag.ps1 backup` l'utilise.

### 3.7 Hors préfixe

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/openapi.json` | Schéma OpenAPI généré par FastAPI 0.142.1 |
| GET | `/api/docs` | Interface Swagger de FastAPI : ses scripts viennent d'un CDN que la CSP bloque ; page non examinée au rendu |
| GET | `/`, `/workspace/`… | Export statique de `apps/web/out` |

## 4. Flux SSE d'une question

Le flux `GET /api/v1/queries/{query_id}/events` (`text/event-stream`, `Cache-Control: no-cache`) relit les événements persistés dans SQLite : chaque événement porte `id` (entier croissant par question), `event` (type) et `data` (JSON). La reprise se fait par l'en-tête `Last-Event-ID` (envoyé automatiquement par `EventSource`) ou le paramètre `after` ; elle ne relance pas la génération. Une ligne de commentaire `: heartbeat` est émise toutes les 10 s ; le flux se ferme quand la question est terminée et que le dernier événement a été envoyé ([main.py:430-456](../../services/api/main.py#L430-L456)).

| Type | Données | Émis par |
|---|---|---|
| `status` | `state` : `queued`, `waiting_for_ingestion_checkpoint`, `searching`, `waiting_for_resources` (avec `available_mib`, `required_mib`), `generating` | [query.py:167-221](../../services/api/query.py#L167-L221) |
| `needs_clarification` | `message`, `choices` (identifiants candidats) ; aucune recherche lancée | [query.py:44-46](../../services/api/query.py#L44-L46) |
| `sources` | `sources` : sources enregistrées `S001`… (document, version, page, blocs, boîtes, précision, révision, `citation_url`) ; liste vide si aucune preuve | [query.py:199](../../services/api/query.py#L199) |
| `warning` | Objet `{code, message, …}` (périmètre, identifiants, extraction partielle, budget de contexte) | [query.py:200-201](../../services/api/query.py#L200-L201) |
| `delta` | `text` : fragment de réponse ; sans source, un seul delta dit que les preuves du périmètre ne suffisent pas | [query.py:205](../../services/api/query.py#L205), [query.py:230](../../services/api/query.py#L230) |
| `done` | `message`, `text`, `status` (`done` ou `length_limited`), `citations`, `finish_reason`, `metrics`, `warnings` | [query.py:255](../../services/api/query.py#L255) |
| `error` | `code`, `message`, `metrics` ; `resource_admission_denied` pour un refus d'admission, `interrupted` après un redémarrage de l'API | [query.py:259-265](../../services/api/query.py#L259-L265), [db.py:121-124](../../services/api/db.py#L121-L124) |
| `cancelled` | `state`, `text` (réponse partielle), `metrics` ; un seul par question | [query.py:145-155](../../services/api/query.py#L145-L155) |

Les `delta` antérieurs aux 512 derniers événements d'une question sont supprimés ([db.py:217-226](../../services/api/db.py#L217-L226)) : une reprise tardive retrouve le texte complet dans `done`. Les métriques de `done` comprennent `model_called`, `queue_wait_ms`, `retrieval_ms`, `context_ms`, `generation_admission_wait_ms`, `ttft_ms` et `elapsed_ms`, ainsi que les compteurs rendus par Ollama.

Exemple de lecture, avec l'identifiant renvoyé par `POST /queries` :

```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8785/api/v1/queries/<query_id>/events?after=0" | Select-Object -ExpandProperty Content
```

## 5. Corps de requête

Les corps sont validés par Pydantic avec `extra="forbid"` ([schemas.py](../../services/api/schemas.py)).

| Modèle | Champs | Règles |
|---|---|---|
| `Scope` | `kind` (`library`, `folder`, `documents`, `section`, `pages`, `selection`), `folderId`, `recursive` (toujours `true`), `documentIds` (1 000 au plus), `versionId`, `sectionId`, `pageStart`, `pageEnd` (à partir de 0, inclus), `spans` (128 au plus) | `folder` exige `folderId` ; `documents` au moins un identifiant ; `pages`, `section`, `selection` exigent `versionId` ; plage de pages ordonnée |
| `SelectedSpan` | `extractionRevisionId`, `blockId`, `blockTextSha256` (64 hexadécimaux), `offsetUnit` = `unicode_code_point`, `startOffset` < `endOffset` | Décalages en points de code sur le texte source haché |
| `QueryRequest` | `question` (1 à 12 000 caractères), `scope`, `mode` (`question`, `selection`, `section`, `comparison`, `compare`, `factual`, `ordinary`, `analysis`), `conversation_id`, `followup_of`, `focus` | `comparison` exige `kind: documents` avec 2 à 4 documents distincts ; `focus` limité à `query_id`, `source_id`, `version_id`, `block_id`, `identifier` |
| `DocumentMove` | `relative_path` (1 à 1 024 caractères) | Chemin relatif PDF sûr |
| `RuntimeMode` | `mode` : `interactive` ou `ingestion` | — |

Exemple de recherche sur toute la bibliothèque :

```powershell
$body = @{ question = 'pression nominale DA-P01'; scope = @{ kind = 'library' } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8785/api/v1/search -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

## 6. Écarts avec le contrat partagé

| Point | Contrat ([contracts.json](../../packages/contracts/contracts.json)) | Implémentation |
|---|---|---|
| Types d'événements SSE | `status`, `sources`, `delta`, `warning`, `done`, `error`, `cancelled` | Émet aussi `needs_clarification` |
| Modes de question | `question`, `selection`, `section`, `comparison` | Accepte aussi `compare` (converti en `comparison`), `factual`, `ordinary`, `analysis` |
| Réponse de création de question | `query_id`, `events_url` | Ajoute `conversation_id` et, le cas échéant, `state` |
| Routes non prévues par [IMPLEMENTATION.md §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http) | — | `/documents/{id}/move`, `/jobs/{id}/publish-partial`, `/admin/*` |
