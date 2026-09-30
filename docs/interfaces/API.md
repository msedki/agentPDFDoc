# Interface HTTP et SSE de l'API locale

**Rôle :** référence des routes `/api/v1` réellement déclarées, de la session locale qui en protège l'accès, des erreurs notables, du flux SSE des questions et des en-têtes · **Statut :** Stabilisé · **Référence :** commit `10b5dd9` + modifications de l'intégrateur du 30/09 19:47 UTC · **Mis à jour :** 2026-09-30 19:59 (UTC) · **Source de vérité :** [services/api/main.py](../../services/api/main.py) (routes et frontière), [services/api/security.py](../../services/api/security.py) (session, CSRF, audit), [services/api/schemas.py](../../services/api/schemas.py) (corps validés), [packages/contracts/contracts.json](../../packages/contracts/contracts.json) (contrat partagé) · **Remplace :** aucun document (le contrat d'origine reste [IMPLEMENTATION.md §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http))

L'API écoute sur `http://127.0.0.1:8785` (profil `local16`, clés `app.port` et `security.environment: development`) avec un seul worker uvicorn ; en production (`security.environment: production`), la même adresse est servie en HTTPS. Elle sert aussi l'interface statique sur `/` (`/workspace/` pour le poste de travail). Depuis la session locale ([W011](../../RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique)), toute route `/api/v1` autre que les sondes et l'ouverture de session exige une session de navigateur ou le jeton de contrôle de l'instance. Les exemples utilisent PowerShell 5.1, dont les cmdlets web envoient un `Host` conforme, et le jeton de contrôle défini en [section 2.4](#24-jeton-de-contrôle-des-outils-locaux) ; ils n'ont pas été rejoués pour ce document et n'emploient que les routes et champs décrits ici.

## Sommaire

1. [Frontière locale et en-têtes](#1-frontière-locale-et-en-têtes)
2. [Session et autorisation](#2-session-et-autorisation)
3. [Format des erreurs](#3-format-des-erreurs)
4. [Routes](#4-routes)
5. [Flux SSE d'une question](#5-flux-sse-dune-question)
6. [Corps de requête](#6-corps-de-requête)
7. [Écarts avec le contrat partagé](#7-écarts-avec-le-contrat-partagé)

## 1. Frontière locale et en-têtes

Chaque requête traverse le middleware `local_boundary` (contrôles de `admitted`, en-têtes de `protected`) ([main.py:161-211](../../services/api/main.py#L161-L211)) avant toute route. Les contrôles s'appliquent dans l'ordre du tableau ; le premier refus termine la requête.

| Ordre | Contrôle | Règle | Refus |
|---|---|---|---|
| 1 | `Host` | `127.0.0.1:<port>`, `localhost:<port>` ou `[::1]:<port>`, casse ignorée | 400 `invalid_host` « Host non autorisé. » |
| 2 | `Origin` (si présent) | Schéma de l'environnement (`http://` en développement, `https://` en production) suivi de l'un des hôtes ci-dessus ([main.py:119-121](../../services/api/main.py#L119-L121)) ; `Origin: null` est refusé | 403 `invalid_origin` « Origine non autorisée. » |
| 3 | `Sec-Fetch-Site` | `cross-site` refusé | 403 `cross_site_request` « Requête intersite refusée. » |
| 4 | Session ou jeton de contrôle | Toute route `/api/v1/*` hors sondes, ouverture et fermeture de session, et hors `/api/v1/admin/` : voir [section 2](#2-session-et-autorisation) | 401 `session_required` ou `session_expired` ; 403 `csrf_rejected` |
| 5 | `Content-Length` (POST, PUT, PATCH, DELETE) | Au plus `pdf.max_file_mib` (200 Mio) + 1 Mio | 413 `request_too_large` « Requête trop volumineuse. » |
| 6 | Sauvegarde en cours | Mutations hors `/api/v1/admin/` suspendues | 503 `mutations_paused` « Sauvegarde en cours ; mutations suspendues. » |
| 7 | Administration (contrôle fait par la route) | En-tête `X-RAG-Control-Token` égal au jeton du lancement courant | 403 `invalid_control_token` « Contrôle d'administration non autorisé. » |

Toutes les réponses, refus des contrôles 1 à 6 compris, portent les en-têtes suivants ([main.py:161-177](../../services/api/main.py#L161-L177)). Aucun en-tête CORS n'est émis.

| En-tête | Valeur | Portée |
|---|---|---|
| `X-Request-ID` | Identifiant de la requête, repris dans `request_id` des erreurs | Toutes les réponses |
| `X-Content-Type-Options`, `Referrer-Policy` | `nosniff`, `no-referrer` | Idem |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'` | Idem |
| `X-Frame-Options`, `Cross-Origin-Opener-Policy` | `DENY`, `same-origin` | Idem |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=(), usb=()` | Idem |
| `Cache-Control` | `no-store`, sauf si la route fixe le sien : PDF original `private, max-age=31536000, immutable`, flux SSE `no-cache` | Chemins `/api/`, refus compris ; un refus sur un autre chemin (par exemple `Host` étranger sur `/workspace/`) n'en porte pas |
| `Vary` | `Cookie`, ajouté à une valeur existante | Chemins `/api/` |
| `Strict-Transport-Security` | `max-age=31536000` | Production seulement |

Un refus 401 efface en plus les cookies de session ([main.py:129-137](../../services/api/main.py#L129-L137)). Jusqu'au commit `10b5dd9`, les refus des contrôles 1 à 6 ne portaient que leur corps JSON ; ils reçoivent désormais les mêmes en-têtes (`test_refusals_carry_the_security_headers_and_are_not_cached` dans [test_api_session.py](../../tests/integration/test_api_session.py)). Vérifications sur serveur réel : [Host et Origin, 30/09 à 09:30](../../RAG_Local_Agents/reports/host-origin-live-20260930T0930.json) ; [gardes réelles avec session, 19/19, 30/09 à 18:29](../../RAG_Local_Agents/reports/http-guards-live-20260930T1829.json).

## 2. Session et autorisation

Le poste est mono-utilisateur et sans compte : l'accès aux données passe par une session de navigateur ouverte depuis le poste, ou par le jeton de contrôle de l'instance pour les outils locaux. Le registre des sessions vit dans la mémoire du seul processus API ([security.py:85-204](../../services/api/security.py#L85-L204)) : il ne conserve que les empreintes SHA-256 des identifiants de session, des jetons CSRF et des liens d'ouverture, et un redémarrage de l'API ferme toutes les sessions. Choix et mécanismes écartés : [W011](../../RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique) et [analyse de la référence decodair](../../RAG_Local_Agents/reports/security-reference-decodair-2026-09-30.md).

### 2.1 Accès par chemin

| Chemins | Accès | Code |
|---|---|---|
| `/api/v1/health`, `/api/v1/readiness` | Public (sondes de disponibilité) | `PUBLIC_PATHS`, [main.py:33](../../services/api/main.py#L33) |
| `/api/v1/session/open`, `/api/v1/session/logout` | Public : la route contrôle elle-même le lien d'ouverture ou le jeton CSRF | [main.py:247-277](../../services/api/main.py#L247-L277) |
| `/api/v1/admin/*` | Jeton de contrôle seulement ; une session de navigateur n'y donne pas accès | [main.py:188](../../services/api/main.py#L188), [main.py:233-235](../../services/api/main.py#L233-L235) |
| Toute autre route `/api/v1/*`, y compris une route inexistante | Session valide, avec jeton CSRF pour `POST`, `PUT`, `PATCH` et `DELETE` ; ou jeton de contrôle | [main.py:139-159](../../services/api/main.py#L139-L159) |
| Hors `/api/v1` : `/`, `/workspace/`, fichiers statiques ; `/openapi.json` et `/api/docs` en développement | Public ; l'interface affiche l'écran de session tant que `GET /api/v1/session` répond 401 | [main.py:99-101](../../services/api/main.py#L99-L101), [main.py:657-659](../../services/api/main.py#L657-L659) |

Le refus par défaut est vérifié route par route sur toutes les routes montées (`test_every_mounted_api_route_refuses_requests_without_session` dans [test_api_session.py](../../tests/integration/test_api_session.py)).

### 2.2 Ouverture, usage et fermeture

1. `.\rag.ps1 open` vérifie que l'instance du profil est `running`, lit `<data_dir>\control\admin-token` et appelle `POST /api/v1/admin/session-links` avec l'en-tête `X-RAG-Control-Token` ([cli.py:422-443](../../services/runtime/cli.py#L422-L443)).
2. L'API rend `{"path": "/api/v1/session/open?link=<lien>", "expires_in_seconds": 300}` : le lien est un jeton aléatoire de 256 bits (`secrets.token_urlsafe(32)`), valable `security.launch_link_ttl_seconds` ([security.py:115-122](../../services/api/security.py#L115-L122)).
3. Le lanceur ouvre `<origine><path>` dans le navigateur par défaut (`os.startfile`) sans l'afficher. L'option `--no-browser` de la CLI Python l'affiche au lieu de l'ouvrir ; `rag.ps1` ne l'expose pas. Dans les deux cas, le rapport `--report` ne contient jamais le lien ([cli.py:491-493](../../services/runtime/cli.py#L491-L493)).
4. `GET /api/v1/session/open?link=…` retire le lien du registre dès sa présentation, valide ou non. S'il est valide, l'API crée une session, révoque celle que le navigateur portait déjà, pose les deux cookies et redirige en 303 vers `/workspace/` ([main.py:247-259](../../services/api/main.py#L247-L259), [security.py:124-139](../../services/api/security.py#L124-L139)). Un lien inconnu, déjà présenté ou expiré redirige en 303 vers `/workspace/?session=lien-invalide` et efface les cookies ; l'interface affiche « Lien d'ouverture expiré ou déjà utilisé » puis retire le paramètre de l'adresse.
5. Chaque requête de l'interface porte le cookie de session ; `POST`, `PUT`, `PATCH` et `DELETE` ajoutent l'en-tête `X-CSRF-Token`, copie du cookie CSRF lisible par le script ([main.py:155-158](../../services/api/main.py#L155-L158), [api.ts:17-21](../../apps/web/src/lib/api.ts#L17-L21)). Les lectures, y compris le flux SSE ouvert par `EventSource`, n'en ont pas besoin.
6. `POST /api/v1/session/logout` efface toujours les deux cookies, mais ne révoque la session côté serveur qu'avec son jeton CSRF (réponse `{"revoked": true}`) : une page étrangère ne peut pas fermer la session de l'utilisateur ([main.py:269-277](../../services/api/main.py#L269-L277)). Le bouton « Fermer la session » de la barre supérieure appelle cette route ([app-topbar.tsx:67-68](../../apps/web/src/components/app-topbar.tsx#L67-L68)).

### 2.3 Cookies, durées et révocation

| Élément | Développement (défaut) | Production |
|---|---|---|
| Cookie de session | `rag_session`, `HttpOnly` | `__Host-rag_session`, `HttpOnly`, `Secure` |
| Cookie CSRF | `rag_csrf`, lisible par le script de l'interface | `__Host-rag_csrf`, `Secure` |
| Attributs communs | `SameSite=Strict`, `Path=/`, `Max-Age` égal à la durée absolue, sans `Domain` | Identiques |
| Transport | HTTP sur 127.0.0.1 | HTTPS sur 127.0.0.1 avec le certificat et la clé du profil, HSTS |

Sources : [security.py:68-75](../../services/api/security.py#L68-L75), [security.py:207-209](../../services/api/security.py#L207-L209), [main.py:257-258](../../services/api/main.py#L257-L258).

| Clé du profil (`security`) | Valeur `local16` | Effet |
|---|---|---|
| `environment` | `development` | `development` ou `production` ; toute autre valeur empêche l'API de démarrer |
| `session_idle_minutes` | 120 | Session fermée après ce délai sans requête authentifiée comptée comme activité (voir ci-dessous) |
| `session_absolute_hours` | 12 | Durée maximale depuis l'ouverture, et `Max-Age` des cookies |
| `launch_link_ttl_seconds` | 300 | Validité d'un lien d'ouverture, 3 600 s au plus |
| `tls_cert_file`, `tls_key_file` | `null` | Exigés et lisibles en production ; chemin relatif à la racine du dépôt ou absolu |

Valeurs lues dans [config/local16.yaml:164-171](../../config/local16.yaml#L164-L171) et contrôlées au démarrage de l'API ([security.py:42-58](../../services/api/security.py#L42-L58)) : l'inactivité doit rester inférieure ou égale à la durée absolue.

L'inactivité se mesure entre deux requêtes authentifiées comptées comme activité. L'atelier relit la disponibilité, la bibliothèque et le suivi des traitements toutes les 3 à 10 s avec l'en-tête `X-RAG-Background: 1` ([api.ts:43-72](../../apps/web/src/lib/api.ts#L43-L72)) : ces requêtes vérifient la session sans la prolonger ([main.py:144-146](../../services/api/main.py#L144-L146), [security.py:141-162](../../services/api/security.py#L141-L162)) ; `/readiness`, public, ne consulte pas la session. Les autres requêtes, dont celles déclenchées par l'utilisateur, remettent l'inactivité à zéro. Exception relevée dans le code : tant qu'un document sans extraction publiée est ouvert, le lecteur relit ses métadonnées toutes les 3 s sans cet en-tête et prolonge la session ([pdf-viewer.tsx:131](../../apps/web/src/components/pdf-viewer.tsx#L131)). La durée absolue s'applique dans tous les cas.

| Événement | Effet |
|---|---|
| Ouverture d'une session dans un navigateur qui en portait déjà une | L'ancienne est révoquée (rotation contre la fixation de session) |
| `POST /api/v1/admin/sessions/revoke` avec le jeton de contrôle | Toutes les sessions et tous les liens en attente sont supprimés ; réponse `{"revoked": <nombre de sessions>}` |
| Redémarrage de l'API (`.\rag.ps1 down` puis `up`) | Registre en mémoire perdu : toutes les sessions sont fermées |
| Délai dépassé | Session supprimée à son prochain contrôle ou à la purge faite à chaque ouverture et émission de lien ; son motif (`session_idle_expired` ou `session_absolute_expired`) est gardé pour les 256 dernières sessions expirées et rendu à la requête suivante ([security.py:95-106](../../services/api/security.py#L95-L106)) |

### 2.4 Jeton de contrôle des outils locaux

Le superviseur tire un jeton aléatoire à chaque lancement, l'écrit dans `<data_dir>\control\admin-token` (fichier supprimé à l'arrêt) et le transmet à l'API par la variable `RAG_CONTROL_TOKEN` ([supervisor.py:363-364](../../services/runtime/supervisor.py#L363-L364), [supervisor.py:405-407](../../services/runtime/supervisor.py#L405-L407)). Présenté dans l'en-tête `X-RAG-Control-Token`, il est comparé en temps constant ([main.py:124-127](../../services/api/main.py#L124-L127)) et ouvre toutes les routes `/api/v1`, mutations comprises, sans session ni jeton CSRF ; `GET /api/v1/session` répond alors `"method": "control_token"`. Il ne doit figurer ni dans une URL, ni dans un rapport, ni dans un journal.

| Client | Origine du jeton | Code |
|---|---|---|
| `rag.ps1 open`, `rag.ps1 doctor` (lecture des diagnostics) | `control\admin-token` de l'instance du profil | `control_headers`, [supervisor.py:155-158](../../services/runtime/supervisor.py#L155-L158) |
| `rag.ps1 backup` | Idem, lu directement | [backup.py:137](../../services/runtime/backup.py#L137) |
| [`tools/corpus/import_folder.py`](../../tools/corpus/import_folder.py), [`tools/qualification/http_guards.py`](../../tools/qualification/http_guards.py) | Idem, par `control_headers` | [import_folder.py:80-82](../../tools/corpus/import_folder.py#L80-L82), [http_guards.py:67](../../tools/qualification/http_guards.py#L67) |
| Outils de qualification qui passent par `api_client` | Variable `RAG_CONTROL_TOKEN` du processus appelant ; sans elle, aucun en-tête n'est envoyé | [api_client.py:32-35](../../tools/qualification/api_client.py#L32-L35) |
| Scénarios Playwright | `.runtime/data/control/admin-token` ou le fichier désigné par `RAG_E2E_CONTROL_TOKEN_FILE` | [global-setup.ts:15-25](../../apps/web/tests/global-setup.ts#L15-L25) |

Appel manuel depuis la racine du dépôt, pour l'instance du profil `local16` :

```powershell
$controle = @{ 'X-RAG-Control-Token' = Get-Content .runtime\data\control\admin-token }
Invoke-RestMethod http://127.0.0.1:8785/api/v1/jobs -Headers $controle
```

`api_client.py` et `http_guards.py` construisent des adresses `http://` : en production (HTTPS), ces deux outils ne joignent pas l'API (constat de lecture du code, non exécuté).

### 2.5 Refus et journal d'audit

Les messages des refus 401 se terminent par « Ouvrir l'atelier avec « .\rag.ps1 open » depuis le dossier du projet. » ([security.py:25](../../services/api/security.py#L25), [main.py:139-159](../../services/api/main.py#L139-L159)).

| Statut | Code | Début du message | `details.reason` | Cause |
|---|---|---|---|---|
| 401 | `session_required` | « Session requise. » | `session_required` | Aucun cookie de session |
| 401 | `session_expired` | « Session inconnue ou fermée. » | `session_unknown` | Cookie absent du registre : API redémarrée, session fermée, révoquée ou remplacée, cookie forgé |
| 401 | `session_expired` | « Session expirée après inactivité. » | `session_idle_expired` | 120 min sans requête authentifiée comptée comme activité |
| 401 | `session_expired` | « Session arrivée à sa durée maximale. » | `session_absolute_expired` | 12 h depuis l'ouverture |
| 403 | `csrf_rejected` | « Jeton anti-falsification absent ou invalide : recharger l'atelier. » (message complet) | `csrf_token_mismatch` | Mutation en session sans `X-CSRF-Token` égal au cookie CSRF |
| 403 | `invalid_control_token` | « Contrôle d'administration non autorisé. » | — | Route d'administration sans jeton valide |

Le journal `<data_dir>\logs\security-audit.jsonl` reçoit une ligne JSON par événement, avec `utc`, `event` et des empreintes tronquées à 12 caractères hexadécimaux, jamais un identifiant, un jeton ni un texte de document ([security.py:197-204](../../services/api/security.py#L197-L204)).

| Événement | Champs |
|---|---|
| `session_link_issued` | `link` (empreinte) |
| `session_link_rejected` | `reason` : `unknown_or_used` ou `expired` |
| `session_opened` | `session` (empreinte), `replaced_previous` |
| `request_refused` | `reason`, `method`, `path` |
| `csrf_rejected` | `method`, `path` |
| `session_revoked` | `session` (empreinte), `reason` : `logout` |
| `sessions_revoked_all` | `count`, `reason` : `admin` |

Vérifications : 9 tests de session et un test HTTPS réel avec certificat de test dans la [série du 30/09 à 18:13, 417 tests PASS](../../RAG_Local_Agents/reports/backend/2026-09-30-r17-r18-full.xml) ([test_api_session.py](../../tests/integration/test_api_session.py), [test_api_tls.py](../../tests/integration/test_api_tls.py)) ; sur l'instance principale, [gardes réelles 19/19](../../RAG_Local_Agents/reports/http-guards-live-20260930T1829.json) (401 `session_required` sans cookie, 401 `session_expired` avec un cookie forgé, 403 sur `/admin/session-links` sans jeton, 200 avec le jeton) et [E2E de session 3/3](../../apps/web/reports/e2e-2026-09-30-r17-readonly-1830-evidence.json). Le mode production n'a été exercé que par le test d'intégration, pas par `rag.ps1 up`.

## 3. Format des erreurs

```json
{"code": "document_not_found", "message": "Document inconnu.", "details": {}, "request_id": "<uuid>"}
```

Une erreur de validation Pydantic rend 422 `validation_error` avec `details.fields` (emplacement et type, sans valeur). Une exception imprévue rend 500 `internal_error` « Erreur interne ; consulter les diagnostics locaux. », sans trace ([main.py:213-224](../../services/api/main.py#L213-L224)). Les refus de session portent le motif dans `details.reason` ([section 2.5](#25-refus-et-journal-daudit)).

## 4. Routes

Préfixe `/api/v1` omis dans la colonne Chemin. Les numéros de ligne renvoient à [main.py](../../services/api/main.py). Sauf mention « public » ou « jeton », une route exige la session du navigateur (avec le jeton CSRF pour une mutation) ou le jeton de contrôle ; sans eux, elle rend 401 avant tout traitement.

### 4.1 Santé et diagnostic

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/health` | Public. Processus vivant, sans accès aux stores (l. 338) | 200 `{"status": "alive", "service": "rag-api"}` |
| GET | `/readiness` | Public. Contrôle SQLite (`quick_check`), fichiers E5 et tokenizer Qwen, collection Qdrant, modèle listé par Ollama, gouverneur (l. 342) | 200 `ready` ; 503 `blocked` avec `checks` et `blockers` (`qdrant_not_ready` tant que la collection n'existe pas) |
| GET | `/diagnostics` | Versions, ressources du gouverneur, `security` (environnement et nombre de sessions actives), identités dense et tokenizer, caches, empreinte du profil et du sélecteur, réconciliation (l. 632) | 200 ; aucun extrait documentaire |

### 4.2 Session

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/session/open?link` | Public. Échange un lien d'ouverture contre les cookies de session (l. 247) | 303 vers `/workspace/` ; 303 vers `/workspace/?session=lien-invalide` si le lien est inconnu, déjà présenté ou expiré |
| GET | `/session` | État de l'accès : `authenticated`, `environment`, `idle_timeout_minutes`, `method` (`session` ou `control_token`) et, pour une session, `created_at`, `idle_expires_at`, `absolute_expires_at` (l. 261) | 401 `session_required`, `session_expired` |
| POST | `/session/logout` | Public. Efface les cookies ; révoque la session si le jeton CSRF est valide (l. 269) | 200 `{"revoked": true}` ou `{"revoked": false}` |

### 4.3 Bibliothèque et documents

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/library/tree?limit&offset&cursor&search` | Tous les dossiers et les documents non retirés, paginés (1 à 200), filtre par sous-chaîne du chemin (l. 387) | 400 `invalid_cursor`, `invalid_pagination` |
| POST | `/documents/import` | Multipart : `files` (1 à 50 PDF) et `relative_paths` (liste JSON facultative, un chemin par fichier) (l. 404) | 202 `{imports: [{document_id, version_id, job_id, reused}]}` ; 400 `invalid_file_count`, `invalid_paths`, `invalid_path`, `invalid_pdf` ; 409 `original_integrity_failure`, `document_removed` ; 413 `file_too_large` |
| GET | `/documents/{document_id}` | Document, versions (avec `file_url`), travaux (l. 454) | 404 `document_not_found` |
| DELETE | `/documents/{document_id}` | Retrait logique : document exclu des périmètres, travaux annulés, vecteurs mis en nettoyage (l. 466) | 404 `document_not_found` |
| POST | `/documents/{document_id}/move` | Déplace ou renomme dans l'arborescence sans nouveau travail ni recalcul d'embedding (l. 476) | 404 `document_not_found` ; 409 `path_conflict` |
| POST | `/documents/{document_id}/reindex` | Nouveau travail sur la dernière version ; renvoie le travail en cours s'il existe (l. 480) | 202 `{job_id, version_id, reused}` ; 404 `document_not_found` |

Un réimport d'un contenu identique au même chemin renvoie le travail existant (`reused: true`), avec `resume_required: true` s'il est en pause ([db.py:190-219](../../services/api/db.py#L190-L219)).

Le champ `state` d'un document publié suit sa génération active (`ready` ou `ready_partial`). Un document sans génération publiée prend l'état de son dernier travail : `queued`, `extracting`, `indexing`, `paused` (y compris pendant `pausing`), `cancelled` (y compris pendant `cancelling`), `error` ou `ready_partial` (extraction partielle vérifiée, à publier) ; ce réalignement est fait au démarrage de l'API, à chaque pause, reprise ou annulation et à la publication différée ([db.py:158-188](../../services/api/db.py#L158-L188)). L'interface distingue un `ready_partial` sans `active_generation_id` (« Extraction partielle à publier »), qui n'est pas interrogeable.

### 4.4 Versions et lecture

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/versions/{version_id}/file` | PDF original, `inline`, `ETag` = SHA-256, cache immuable, plages d'octets (`Range`) prises en charge par `FileResponse` de Starlette 1.7.0 (l. 492) ; parcours ETag et plages de la recette lifecycle non exécuté | 304 si `If-None-Match` correspond ; 404 `source_removed` ; 409 `invalid_storage_path` |
| GET | `/versions/{version_id}/outline?extraction_revision_id` | Sections de la génération publiée ou de la révision demandée (l. 500) | 404 `extraction_revision_not_found` ; 409 `not_indexed` |
| GET | `/versions/{version_id}/pages/{page_index}/blocks?extraction_revision_id` | Géométrie de la page, blocs (texte, `bbox`, précision, provenance), avertissements de la génération (l. 508) | 404 `page_not_found`, `extraction_revision_not_found` ; 409 `not_indexed` |

### 4.5 Recherche, questions et citations

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| POST | `/search` | Recherche hybride sans modèle de langue : `results`, `top10`, `scope_snapshot`, `warnings`, `elapsed_ms` (l. 527) | 404 `folder_not_found`, `section_not_found`, `source_removed` ; 409 `no_document_in_scope` ; 400 `invalid_selection`, `invalid_page_range` |
| POST | `/queries` | Crée une question et lance son traitement (l. 534) | 202 `{query_id, conversation_id, events_url}` (plus `state: needs_clarification` si un référent est ambigu) ; 429 `query_queue_full` ; 404 `conversation_not_found`, `focus_not_found`, `followup_not_found` ; 409 `focus_outside_scope` |
| GET | `/queries/{query_id}/events?after` | Flux SSE reprenable (l. 538) ; voir [section 5](#5-flux-sse-dune-question) | 404 `query_not_found` ; 400 `invalid_event_id` |
| POST | `/queries/{query_id}/cancel` | Annulation immédiate ; coupe aussi l'appel au modèle (l. 566) | `{query_id, state}` ; 404 `query_not_found` |
| GET | `/citations/{query_id}/{source_id}` | Source enregistrée : document, version, page, blocs, boîtes, précision, révision (l. 570) | 404 `citation_not_found`, `source_removed` |

### 4.6 Travaux d'ingestion

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/jobs?limit` | Travaux récents avec couverture, avertissements, publication ; `runtime_mode` : priorité choisie, `interactive` (priorité aux questions, imports suspendus) ou `ingestion` (priorité aux imports) ; le mode instantané du gouverneur n'est plus exposé ici (l. 578) | 400 `invalid_pagination` |
| POST | `/jobs/resume-paused` | Remet en file, dans leur ordre d'import, tous les travaux à l'état `paused` (l. 587 ; [jobs.py:243-248](../../services/api/jobs.py#L243-L248)) | 200 `{"resumed": n}` ; 409 `interaction_active` si une question est active, avant toute reprise (tout ou rien) |
| POST | `/jobs/{job_id}/pause` | Pause coopérative : `pausing` si le travail tourne, sinon `paused` (l. 599) | 404 `job_not_found` ; 409 `job_not_pauseable` |
| POST | `/jobs/{job_id}/resume` | Remet en file un travail `paused`, `error` ou `cancelled` (l. 595) | 409 `job_not_resumable`, `retry_limit` (trois tentatives en erreur), `interaction_active` |
| POST | `/jobs/{job_id}/cancel` | Annulation : `cancelling` si le travail tourne (l. 591) | 404 `job_not_found` |
| POST | `/jobs/{job_id}/publish-partial` | Publie une extraction `ready_partial` vérifiée ; nécessaire seulement quand du texte manque, une extraction dont seules des figures ne sont pas interprétées étant publiée d'office ([W012](../../RAG_Local_Agents/DECISIONS.md#w012-figures-non-interprétées--limite-déclarée-publication-automatique)) (l. 621) | 404 `job_not_found` ; 409 `not_partial` |
| POST | `/runtime/mode` | `{"mode": "interactive"}` met les imports en pause ; `{"mode": "ingestion"}` lève la pause sans reprendre automatiquement les travaux en pause (l. 603) | 409 `interaction_active` ; 503 `governor_not_configured` |

### 4.7 Administration (jeton requis)

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| POST | `/admin/session-links` | Émet un lien d'ouverture de session à usage unique (l. 237) | 200 `{path, expires_in_seconds}` ; 403 `invalid_control_token` |
| POST | `/admin/sessions/revoke` | Révoque toutes les sessions et tous les liens en attente (l. 242) | 200 `{revoked}` ; 403 `invalid_control_token` |
| POST | `/admin/quiesce` | Suspend les mutations, attend celles en cours, annule les questions, met le travail actif au checkpoint, exécute `PRAGMA wal_checkpoint(FULL)` (l. 279) | 403 `invalid_control_token` |
| POST | `/admin/resume` | Relance les mutations et la réconciliation (l. 293) | 403 `invalid_control_token` |
| GET | `/admin/status` | Mutations suspendues, questions actives, travail actif (l. 302) | 403 `invalid_control_token` |
| POST | `/admin/evaluation/context` | Contexte d'une question sans appel au modèle, pour la qualification (l. 307) | 409 `ingestion_active`, `query_active` ; 503 `mutations_paused` |

Le jeton est celui de la [section 2.4](#24-jeton-de-contrôle-des-outils-locaux) ; `rag.ps1 open` et `rag.ps1 backup` l'utilisent.

### 4.8 Hors préfixe

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/openapi.json` | Schéma OpenAPI généré par FastAPI 0.142.1 ; développement seulement ([main.py:99-101](../../services/api/main.py#L99-L101)) |
| GET | `/api/docs` | Interface Swagger de FastAPI, développement seulement ; ses scripts viennent d'un CDN que la CSP bloque ; page non examinée au rendu |
| GET | `/`, `/workspace/`… | Export statique de `apps/web/out` ([main.py:657-659](../../services/api/main.py#L657-L659)) |

## 5. Flux SSE d'une question

Le flux `GET /api/v1/queries/{query_id}/events` (`text/event-stream`, `Cache-Control: no-cache`) relit les événements persistés dans SQLite : chaque événement porte `id` (entier croissant par question), `event` (type) et `data` (JSON). La reprise se fait par l'en-tête `Last-Event-ID` (envoyé automatiquement par `EventSource`) ou le paramètre `after` ; elle ne relance pas la génération. Une ligne de commentaire `: heartbeat` est émise toutes les 10 s ; le flux se ferme quand la question est terminée et que le dernier événement a été envoyé ([main.py:538-564](../../services/api/main.py#L538-L564)). Le flux suit les règles de la [section 2](#2-session-et-autorisation) : `EventSource` envoie le cookie de session de la même origine, un outil local présente le jeton de contrôle.

| Type | Données | Émis par |
|---|---|---|
| `status` | `state` : `queued`, `waiting_for_ingestion_checkpoint`, `searching`, `waiting_for_resources` (avec `available_mib`, `required_mib`), `generating` | [query.py:173-227](../../services/api/query.py#L173-L227) |
| `needs_clarification` | `message`, `choices` (identifiants candidats) ; aucune recherche lancée | [query.py:45-47](../../services/api/query.py#L45-L47) |
| `sources` | `sources` : sources enregistrées `S001`… (document, version, page, blocs, boîtes, précision, révision, `citation_url`) ; liste vide si aucune preuve | [query.py:205](../../services/api/query.py#L205) |
| `warning` | Objet `{code, message, …}` (périmètre, identifiants, extraction partielle, budget de contexte) | [query.py:206-207](../../services/api/query.py#L206-L207) |
| `delta` | `text` : fragment de réponse ; sans source, un seul delta dit que les preuves du périmètre ne suffisent pas | [query.py:211](../../services/api/query.py#L211), [query.py:236](../../services/api/query.py#L236) |
| `done` | `message`, `text`, `status` (`done` ou `length_limited`), `citations`, `finish_reason`, `metrics`, `warnings` | [query.py:261](../../services/api/query.py#L261) |
| `error` | `code`, `message`, `metrics` ; `resource_admission_denied` pour un refus d'admission, `interrupted` après un redémarrage de l'API | [query.py:265-271](../../services/api/query.py#L265-L271), [db.py:121-124](../../services/api/db.py#L121-L124) |
| `cancelled` | `state`, `text` (réponse partielle), `metrics` ; un seul par question | [query.py:151-161](../../services/api/query.py#L151-L161) |

Les `delta` antérieurs aux 512 derniers événements d'une question sont supprimés ([db.py:249-258](../../services/api/db.py#L249-L258)) : une reprise tardive retrouve le texte complet dans `done`. Les métriques de `done` comprennent `model_called`, `queue_wait_ms`, `retrieval_ms`, `context_ms`, `generation_admission_wait_ms`, `ttft_ms` et `elapsed_ms`, ainsi que les compteurs rendus par Ollama.

Exemple de lecture, avec l'identifiant renvoyé par `POST /queries` et le jeton `$controle` de la [section 2.4](#24-jeton-de-contrôle-des-outils-locaux) :

```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8785/api/v1/queries/<query_id>/events?after=0" -Headers $controle | Select-Object -ExpandProperty Content
```

## 6. Corps de requête

Les corps sont validés par Pydantic avec `extra="forbid"` ([schemas.py](../../services/api/schemas.py)).

| Modèle | Champs | Règles |
|---|---|---|
| `Scope` | `kind` (`library`, `folder`, `documents`, `section`, `pages`, `selection`), `folderId`, `recursive` (toujours `true`), `documentIds` (1 000 au plus), `versionId`, `sectionId`, `pageStart`, `pageEnd` (à partir de 0, inclus), `spans` (128 au plus) | `folder` exige `folderId` ; `documents` au moins un identifiant ; `pages`, `section`, `selection` exigent `versionId` ; plage de pages ordonnée |
| `SelectedSpan` | `extractionRevisionId`, `blockId`, `blockTextSha256` (64 hexadécimaux), `offsetUnit` = `unicode_code_point`, `startOffset` < `endOffset` | Décalages en points de code sur le texte source haché |
| `QueryRequest` | `question` (1 à 12 000 caractères), `scope`, `mode` (`question`, `selection`, `section`, `comparison`, `compare`, `factual`, `ordinary`, `analysis`), `conversation_id`, `followup_of`, `focus` | `comparison` exige `kind: documents` avec 2 à 4 documents distincts ; `focus` limité à `query_id`, `source_id`, `version_id`, `block_id`, `identifier` |
| `DocumentMove` | `relative_path` (1 à 1 024 caractères) | Chemin relatif PDF sûr |
| `RuntimeMode` | `mode` : `interactive` ou `ingestion` | — |

Exemple de recherche sur toute la bibliothèque, avec le jeton de contrôle (aucun jeton CSRF n'est alors exigé) :

```powershell
$body = @{ question = 'pression nominale DA-P01'; scope = @{ kind = 'library' } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8785/api/v1/search -Headers $controle -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

## 7. Écarts avec le contrat partagé

| Point | Contrat ([contracts.json](../../packages/contracts/contracts.json)) | Implémentation |
|---|---|---|
| Authentification | Absente du contrat et d'[IMPLEMENTATION.md §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http) | Session ou jeton de contrôle exigés (W011) ; codes `session_required`, `session_expired`, `csrf_rejected` hors contrat |
| Types d'événements SSE | `status`, `sources`, `delta`, `warning`, `done`, `error`, `cancelled` | Émet aussi `needs_clarification` |
| Modes de question | `question`, `selection`, `section`, `comparison` | Accepte aussi `compare` (converti en `comparison`), `factual`, `ordinary`, `analysis` |
| Réponse de création de question | `query_id`, `events_url` | Ajoute `conversation_id` et, le cas échéant, `state` |
| Routes non prévues par [IMPLEMENTATION.md §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http) | — | `/session`, `/session/open`, `/session/logout`, `/documents/{id}/move`, `/jobs/{id}/publish-partial`, `/jobs/resume-paused`, `/admin/*` |
| États de document | `imported`, `queued`, `extracting`, `ocr`, `indexing`, `ready`, `ready_partial`, `error`, `deleted` | Emploie aussi `paused` et `cancelled` pour un document sans génération publiée |
