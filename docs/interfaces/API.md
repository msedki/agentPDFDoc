# Interface HTTP et SSE de l'API locale

**Rôle :** référence des routes `/api/v1` réellement déclarées, de la session locale qui en protège l'accès, des erreurs notables, du flux SSE des questions et des en-têtes · **Propriétaire :** contrats HTTP et sécurité applicative · **Statut :** Stabilisé · **Référence :** commit `dfb8dbd`, sections 2.5, 4.1, 4.3, 4.6 et 7 au commit `ea49d05` plus le lot J5 et sa ronde 4 (non commités) ; renvois de code vérifiés sur l'arbre de travail le 2026-10-01 à 20:20 (UTC), ceux qui étaient périmés remplacés par le nom de la fonction ; section 2.2 relue contre `cli.py` et `main.py` de l'arbre de travail le 2026-10-01 à 21:47 (UTC) (W023) ; champs de l'accélération GPU (`llm_accelerator` en 4.1, `generation` en 4.6, `llm_execution`, repli et second statut `generating` en 5, contrôle de contrat en 7) au commit `4d8ba68`, relus le 2026-10-02 contre `ollama.py`, `settings.py`, `main.py`, `query.py`, `contracts.json` et `test_api_contract.py` ; états `identifier_coverage_states` (section 5) et contrôle de contrat correspondant (section 7) au commit `419b526`, rejoués sur instance le 2026-10-02 (rejeu R7 de la qualification Linux) ; propriétaire et renvois documentaires R14-1 sur le commit `5ca3685` et modifications locales du 2026-10-02 ; section 3 confrontée au code sur la base `f8cd964` et au correctif E05 du 2026-10-03, validation ASGI isolée décrite au journal ; choix de modèle R23 relu dans le code intégré et modifications locales du 2026-10-04, sans qualification native transférée ; disponibilité Qdrant corrigée sur la base `1e20a58` et modifications locales D06.9 du 2026-10-05, tests isolés et parcours natif distingués ; affichage des limites de longueur sur la base `497d901` et correctif W039 du 2026-10-06, flux SSE inchangé ; provenance d'extraction des sources et avertissements de réponse R26 (OCR-01, ANS-01, ANS-02) sur la base `011a817` et modifications locales du 2026-10-06, prouvés par tests isolés et rejeu hors ligne, sans parcours natif de question ; couverture dense de l'identité courante et nettoyage multi-collections R26-IDX-02 (sections 4.1, 4.5, 5 et 7), mêmes base et date, tests isolés et sonde native d'identité rejouée ; correctifs R27 du 09/10/2026 sur la base `75df760`, vérifiés en tests isolés et revue indépendante, recette native de livraison en attente ; extension Office R28 (contrat partagé v3, base `64e191f` et modifications locales du 10/10/2026), relue contre routes/schémas réels et tests isolés, recette DEV Linux aarch64 vérifiée, autres cibles non qualifiées · **Mis à jour :** 2026-10-10 13:28 (UTC) · **Source de vérité :** [services/api/main.py](../../services/api/main.py) (routes et frontière), [services/api/security.py](../../services/api/security.py) (session, CSRF, audit), [services/api/ollama.py](../../services/api/ollama.py) (appel du modèle, repli sur CPU), [services/api/schemas.py](../../services/api/schemas.py) (corps validés), [services/api/errors.py](../../services/api/errors.py) (messages de validation), [packages/contracts/contracts.json](../../packages/contracts/contracts.json) (contrat partagé) · **Remplace :** aucun document (le contrat d'origine reste [IMPLEMENTATION.md §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http))

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

Chaque requête traverse le middleware `local_boundary` de [main.py](../../services/api/main.py) (contrôles de `admitted`, en-têtes de `protected`) avant toute route. Les contrôles s'appliquent dans l'ordre du tableau ; le premier refus termine la requête.

| Ordre | Contrôle | Règle | Refus |
|---|---|---|---|
| 1 | `Host` | `127.0.0.1:<port>`, `localhost:<port>` ou `[::1]:<port>`, casse ignorée | 400 `invalid_host` « Host non autorisé. » |
| 2 | `Origin` (si présent) | Schéma de l'environnement (`http://` en développement, `https://` en production) suivi de l'un des hôtes ci-dessus (`allowed_origins`, [main.py](../../services/api/main.py)) ; `Origin: null` est refusé | 403 `invalid_origin` « Origine non autorisée. » |
| 3 | `Sec-Fetch-Site` | `cross-site` refusé | 403 `cross_site_request` « Requête intersite refusée. » |
| 4 | Session ou jeton de contrôle | Toute route `/api/v1/*` hors sondes, ouverture et fermeture de session, et hors `/api/v1/admin/` : voir [section 2](#2-session-et-autorisation) | 401 `session_required` ou `session_expired` ; 403 `csrf_rejected` |
| 5 | `Content-Length` (POST, PUT, PATCH, DELETE) | Au plus `pdf.max_file_mib` (200 Mio) + 1 Mio | 413 `request_too_large` « Requête trop volumineuse. » |
| 6 | Sauvegarde en cours | Mutations hors `/api/v1/admin/` suspendues | 503 `mutations_paused` « Sauvegarde en cours ; mutations suspendues. » |
| 7 | Administration (contrôle fait par la route) | En-tête `X-RAG-Control-Token` égal au jeton du lancement courant | 403 `invalid_control_token` « Contrôle d'administration non autorisé. » |

Après cette frontière, `RequestBodyLimitMiddleware` compte aussi les octets
réellement reçus avant leur passage au parseur : la même borne s'applique
sans `Content-Length` ou lorsque la taille annoncée est inférieure au corps.
Le dépassement produit le même JSON413 `request_too_large` ; les fichiers
temporaires déjà ouverts par le parseur multipart sont fermés. Tests ASGI
isolés R27 dans `test_api_http.py`, sans saturation d'un disque réel.

Toutes les réponses, refus des contrôles 1 à 6 compris, portent les en-têtes suivants (`protected`, [main.py](../../services/api/main.py)). Aucun en-tête CORS n'est émis.

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

Un refus 401 efface en plus les cookies de session (`refused`, [main.py](../../services/api/main.py)). Jusqu'au commit `10b5dd9`, les refus des contrôles 1 à 6 ne portaient que leur corps JSON ; ils reçoivent désormais les mêmes en-têtes (`test_refusals_carry_the_security_headers_and_are_not_cached` dans [test_api_session.py](../../tests/integration/test_api_session.py)). Vérifications sur serveur réel : [Host et Origin, 30/09 à 09:30](../../RAG_Local_Agents/reports/host-origin-live-20260930T0930.json) ; [gardes réelles avec session, 19/19, 30/09 à 18:29](../../RAG_Local_Agents/reports/http-guards-live-20260930T1829.json).

## 2. Session et autorisation

Le poste est mono-utilisateur et sans compte : l'accès aux données passe par une session de navigateur ouverte depuis le poste, ou par le jeton de contrôle de l'instance pour les outils locaux. Le registre des sessions vit dans la mémoire du seul processus API (`SessionRegistry`, [security.py](../../services/api/security.py)) : il ne conserve que les empreintes SHA-256 des identifiants de session, des jetons CSRF et des liens d'ouverture, et un redémarrage de l'API ferme toutes les sessions. Choix et mécanismes écartés : [W011](../../RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique) et [analyse de la référence decodair](../../RAG_Local_Agents/reports/security-reference-decodair-2026-09-30.md).

### 2.1 Accès par chemin

| Chemins | Accès | Code |
|---|---|---|
| `/api/v1/health`, `/api/v1/readiness` | Public (sondes de disponibilité) | `PUBLIC_PATHS`, [main.py](../../services/api/main.py) |
| `/api/v1/session/open`, `/api/v1/session/logout` | Public : la route contrôle elle-même le lien d'ouverture ou le jeton CSRF | `open_session` et `logout`, [main.py](../../services/api/main.py) |
| `/api/v1/admin/*` | Jeton de contrôle seulement ; une session de navigateur n'y donne pas accès | `admitted` (préfixe `/api/v1/admin/`) et `control_authorized`, [main.py](../../services/api/main.py) |
| Toute autre route `/api/v1/*`, y compris une route inexistante | Session valide, avec jeton CSRF pour `POST`, `PUT`, `PATCH` et `DELETE` ; ou jeton de contrôle | `authenticate`, [main.py](../../services/api/main.py) |
| Hors `/api/v1` : `/`, `/workspace/`, fichiers statiques ; `/openapi.json` et `/api/docs` en développement | Public ; l'interface affiche l'écran de session tant que `GET /api/v1/session` répond 401 | `docs_url`, `openapi_url` et montage de `StaticFiles` dans `create_app`, [main.py](../../services/api/main.py) |

Le refus par défaut est vérifié route par route sur toutes les routes montées (`test_every_mounted_api_route_refuses_requests_without_session` dans [test_api_session.py](../../tests/integration/test_api_session.py)).

### 2.2 Ouverture, usage et fermeture

1. `.\rag.ps1 open` (sous Linux, `./rag.sh open`) vérifie que l'instance du profil est `running`, lit `<data_dir>\control\admin-token` et appelle `POST /api/v1/admin/session-links` avec l'en-tête `X-RAG-Control-Token` (`open_workspace`, [cli.py](../../services/runtime/cli.py)).
2. L'API rend `{"path": "/api/v1/session/open?link=<lien>", "expires_in_seconds": 300}` : le lien est un jeton aléatoire de 256 bits (`secrets.token_urlsafe(32)`), valable `security.launch_link_ttl_seconds` (`SessionRegistry.issue_link`, [security.py](../../services/api/security.py)).
3. Le lanceur ouvre `<origine><path>` dans le navigateur par défaut sans l'afficher : `os.startfile` sous Windows, `webbrowser.open` sous Linux (`xdg-open`, `gio` ou le navigateur par défaut, selon la session ; [W023](../../RAG_Local_Agents/DECISIONS.md#w023-ouverture-de-session-sous-linux--url-de-boucle-locale-directe)). `.\rag.ps1 open -NoBrowser` et `./rag.sh open --no-browser` l'affichent au lieu de l'ouvrir. Sous Linux, si `webbrowser.open` ne trouve aucun navigateur, la commande échoue sans afficher le lien et indique `./rag.sh open --no-browser` ; le lien déjà émis expire sans avoir servi. Dans tous les cas, le rapport `--report` ne contient jamais le lien (`main` de [cli.py](../../services/runtime/cli.py) retire `url` du rapport de `open`). Sous Linux, le lien figure dans la ligne de commande des processus lancés : risque résiduel et repli dans [W023](../../RAG_Local_Agents/DECISIONS.md#w023-ouverture-de-session-sous-linux--url-de-boucle-locale-directe).
4. `GET /api/v1/session/open?link=…` retire le lien du registre dès sa présentation, valide ou non. S'il est valide, l'API crée une session, révoque celle que le navigateur portait déjà, pose les deux cookies et redirige en 303 vers `/workspace/` (`open_session` dans [main.py](../../services/api/main.py), `SessionRegistry.open` dans [security.py](../../services/api/security.py)). Un lien inconnu, déjà présenté ou expiré redirige en 303 vers `/workspace/?session=lien-invalide` et efface les cookies ; l'interface affiche « Lien d'ouverture expiré ou déjà utilisé » puis retire le paramètre de l'adresse.
5. Chaque requête de l'interface porte le cookie de session ; `POST`, `PUT`, `PATCH` et `DELETE` ajoutent l'en-tête `X-CSRF-Token`, copie du cookie CSRF lisible par le script (`authenticate` dans [main.py](../../services/api/main.py), `csrfHeader` dans [api.ts](../../apps/web/src/lib/api.ts)). Les lectures, y compris le flux SSE ouvert par `EventSource`, n'en ont pas besoin.
6. `POST /api/v1/session/logout` efface toujours les deux cookies, mais ne révoque la session côté serveur qu'avec son jeton CSRF (réponse `{"revoked": true}`) : une page étrangère ne peut pas fermer la session de l'utilisateur (`logout`, [main.py](../../services/api/main.py)). Le bouton « Fermer la session » de la barre supérieure appelle cette route ([app-topbar.tsx](../../apps/web/src/components/app-topbar.tsx)).

### 2.3 Cookies, durées et révocation

| Élément | Développement (défaut) | Production |
|---|---|---|
| Cookie de session | `rag_session`, `HttpOnly` | `__Host-rag_session`, `HttpOnly`, `Secure` |
| Cookie CSRF | `rag_csrf`, lisible par le script de l'interface | `__Host-rag_csrf`, `Secure` |
| Attributs communs | `SameSite=Strict`, `Path=/`, `Max-Age` égal à la durée absolue, sans `Domain` | Identiques |
| Transport | HTTP sur 127.0.0.1 | HTTPS sur 127.0.0.1 avec le certificat et la clé du profil, HSTS |

Sources : `SecurityPolicy` (noms des cookies) et `cookie_attributes` (attributs) dans [security.py](../../services/api/security.py), pose des cookies par `open_session` dans [main.py](../../services/api/main.py).

| Clé du profil (`security`) | Valeur `local16` | Effet |
|---|---|---|
| `environment` | `development` | `development` ou `production` ; toute autre valeur empêche l'API de démarrer |
| `session_idle_minutes` | 120 | Session fermée après ce délai sans requête authentifiée comptée comme activité (voir ci-dessous) |
| `session_absolute_hours` | 12 | Durée maximale depuis l'ouverture, et `Max-Age` des cookies |
| `launch_link_ttl_seconds` | 300 | Validité d'un lien d'ouverture, 3 600 s au plus |
| `tls_cert_file`, `tls_key_file` | `null` | Exigés et lisibles en production ; chemin relatif à la racine du dépôt ou absolu |

Valeurs lues dans [config/local16.yaml:164-171](../../config/local16.yaml#L164-L171) et contrôlées au démarrage de l'API (`SecurityPolicy.from_settings`, [security.py](../../services/api/security.py)) : l'inactivité doit rester inférieure ou égale à la durée absolue.

L'inactivité se mesure entre deux requêtes authentifiées comptées comme activité. L'atelier relit la disponibilité, la bibliothèque et le suivi des traitements toutes les 3 à 10 s avec l'en-tête `X-RAG-Background: 1` ([api.ts:43-72](../../apps/web/src/lib/api.ts#L43-L72)) : ces requêtes vérifient la session sans la prolonger (`authenticate` dans [main.py](../../services/api/main.py), `SessionRegistry.check` dans [security.py](../../services/api/security.py)) ; `/readiness`, public, ne consulte pas la session. Les autres requêtes, dont celles déclenchées par l'utilisateur, remettent l'inactivité à zéro. Tant qu'un document sans extraction publiée est ouvert, le lecteur relit ses métadonnées toutes les 3 s avec ce même en-tête (`api.document(…, signal, true)` dans [pdf-viewer.tsx](../../apps/web/src/components/pdf-viewer.tsx)) : cette relecture ne prolonge pas non plus la session. La durée absolue s'applique dans tous les cas.

| Événement | Effet |
|---|---|
| Ouverture d'une session dans un navigateur qui en portait déjà une | L'ancienne est révoquée (rotation contre la fixation de session) |
| `POST /api/v1/admin/sessions/revoke` avec le jeton de contrôle | Toutes les sessions et tous les liens en attente sont supprimés ; réponse `{"revoked": <nombre de sessions>}` |
| Redémarrage de l'API (`.\rag.ps1 down` puis `up`) | Registre en mémoire perdu : toutes les sessions sont fermées |
| Délai dépassé | Session supprimée à son prochain contrôle ou à la purge faite à chaque ouverture et émission de lien ; son motif (`session_idle_expired` ou `session_absolute_expired`) est gardé pour les 256 dernières sessions expirées et rendu à la requête suivante (`SessionRegistry._purge` et `SessionRegistry.check`, [security.py](../../services/api/security.py)) |

### 2.4 Jeton de contrôle des outils locaux

Le superviseur tire un jeton aléatoire à chaque lancement, l'écrit dans `<data_dir>\control\admin-token` (fichier supprimé à l'arrêt) et le transmet à l'API par la variable `RAG_CONTROL_TOKEN` (`supervise`, [supervisor.py](../../services/runtime/supervisor.py)). Présenté dans l'en-tête `X-RAG-Control-Token`, il est comparé en temps constant (`control_token_valid`, [main.py](../../services/api/main.py)) et ouvre toutes les routes `/api/v1`, mutations comprises, sans session ni jeton CSRF ; `GET /api/v1/session` répond alors `"method": "control_token"`. Il ne doit figurer ni dans une URL, ni dans un rapport, ni dans un journal.

| Client | Origine du jeton | Code |
|---|---|---|
| `rag.ps1 open`, `rag.ps1 doctor` (lecture des diagnostics) | `control\admin-token` de l'instance du profil | `control_headers`, [supervisor.py](../../services/runtime/supervisor.py) |
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

Les messages des refus 401 se terminent par « Ouvrir l'atelier avec « .\rag.ps1 open » depuis le dossier du projet. » sous Windows ; sous Linux ([W018](../../RAG_Local_Agents/DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs)), la commande citée est « ./rag.sh open » ([security.py:29-30](../../services/api/security.py#L29-L30), commande fournie par `launcher_command` de [platforms.py](../../services/runtime/platforms.py)). Vérification : `test_session_help_names_the_launcher_of_this_platform_and_keeps_the_windows_text` et `test_refused_session_and_public_health_announce_the_launcher_commands` dans [test_api_platform_profile.py](../../tests/unit/test_api_platform_profile.py).

| Statut | Code | Début du message | `details.reason` | Cause |
|---|---|---|---|---|
| 401 | `session_required` | « Session requise. » | `session_required` | Aucun cookie de session |
| 401 | `session_expired` | « Session inconnue ou fermée. » | `session_unknown` | Cookie absent du registre : API redémarrée, session fermée, révoquée ou remplacée, cookie forgé |
| 401 | `session_expired` | « Session expirée après inactivité. » | `session_idle_expired` | 120 min sans requête authentifiée comptée comme activité |
| 401 | `session_expired` | « Session arrivée à sa durée maximale. » | `session_absolute_expired` | 12 h depuis l'ouverture |
| 403 | `csrf_rejected` | « Jeton anti-falsification absent ou invalide : recharger l'atelier. » (message complet) | `csrf_token_mismatch` | Mutation en session sans `X-CSRF-Token` égal au cookie CSRF |
| 403 | `invalid_control_token` | « Contrôle d'administration non autorisé. » | — | Route d'administration sans jeton valide |

Le journal `<data_dir>\logs\security-audit.jsonl` reçoit une ligne JSON par événement, avec `utc`, `event` et des empreintes tronquées à 12 caractères hexadécimaux, jamais un identifiant, un jeton ni un texte de document (`SessionRegistry.audit` dans [security.py](../../services/api/security.py)). Il est borné comme la trace de ressources du superviseur : fichier courant d'au plus 5 Mio, puis archives `security-audit.jsonl.1` et `.2`, lignes jamais coupées. Un renommage refusé (sous Windows : fichier ouvert sans partage de suppression, analyse antivirus) reporte la rotation de 30 s sans perdre de ligne, puis la rotation est retentée. Un fil dédié écrit les événements (`AuditLog`) : le middleware ne fait aucune écriture disque, et l'arrêt de l'API écrit ceux encore en file. Une écriture impossible, quelle que soit l'exception, est consignée dans le journal de l'API sans faire échouer la requête ni arrêter le fil ; si le fil est mort malgré tout, l'événement suivant le relance. Au-delà de 8 Mio d'événements en attente (disque qui ne répond plus), un événement est abandonné et compté au lieu de bloquer la requête ou de faire croître la mémoire. Les compteurs `failures`, `dropped`, `writer_restarts`, `rotations_deferred`, `pending_bytes` et `queue_limit_bytes`, comptés depuis le démarrage du processus, sont publiés dans `security.audit_log` de `GET /diagnostics` ([section 4.1](#41-santé-et-diagnostic)). Vérification : [test_api_security_audit.py](../../tests/unit/test_api_security_audit.py) et `test_diagnostics_expose_the_security_audit_writer_counters` dans [test_api_session.py](../../tests/integration/test_api_session.py).

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

Une erreur de validation Pydantic rend 422 `validation_error` avec `details.fields` (emplacement et type, sans valeur). Le message donne une aide fixe pour une erreur unique de longueur sur `body.scope.documentIds` ; dans les autres cas, il invite à vérifier les champs renseignés. La limite porte sur les éléments de la liste de sélection, pas sur le corpus. Les textes sont définis par `request_validation_message` dans [errors.py](../../services/api/errors.py), sans interpolation des valeurs ni des messages de Pydantic. Les gestionnaires et ce refus sont exercés par les [tests ASGI de validation](../../tests/unit/test_api_validation_copy.py), avec services doublés et stockage temporaire : ils ne qualifient pas un parcours RAG natif.

Une exception imprévue rend 500 `internal_error`, sans trace dans la réponse. Son aide indique de réessayer puis, si nécessaire, d'utiliser la commande de journal du lanceur correspondant à la plateforme (`unexpected_error`, [main.py](../../services/api/main.py) ; [contrôles de plateforme](../../tests/unit/test_api_platform_profile.py)). Les refus de session portent le motif dans `details.reason` ([section 2.5](#25-refus-et-journal-daudit)).

## 4. Routes

Préfixe `/api/v1` omis dans la colonne Chemin. Chaque route est déclarée dans [main.py](../../services/api/main.py) sous la forme `@application.<méthode>(prefix + "<chemin>")`, à retrouver par son chemin. Sauf mention « public » ou « jeton », une route exige la session du navigateur (avec le jeton CSRF pour une mutation) ou le jeton de contrôle ; sans eux, elle rend 401 avant tout traitement.

### 4.1 Santé et diagnostic

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/health` | Public. Processus vivant, sans accès aux stores ; annonce les commandes du lanceur de ce poste, citées par l'atelier | 200 `{"status": "alive", "service": "rag-api", "commands": {"open": ".\\rag.ps1 open", "status": ".\\rag.ps1 status", "logs": ".\\rag.ps1 logs", "doctor": ".\\rag.ps1 doctor"}}` sous Windows ; `./rag.sh open`, `./rag.sh status`, `./rag.sh logs`, `./rag.sh doctor` sous Linux |
| GET | `/readiness` | Public. Contrôle SQLite (`quick_check`), fichiers E5 et tokenizer Qwen, collection Qdrant, modèle listé par Ollama, gouverneur ; couverture dense de l'identité courante (R26-IDX-02) | 200 `ready` ; 503 `blocked` avec `checks` et `blockers` (`qdrant_not_ready` si Qdrant ne répond pas, ou si la collection manque alors que des générations sont publiées) ; champ `qdrant_collection` : `present`, `absent_empty_library`, `absent_with_published_generations` ou `unreachable` ; champ `dense_index` : `complete`, `dense_migration_incomplete` (jamais bloquant), `unverifiable` ou `not_applicable`, avec `documents_to_reindex` (identifiants seulement) |
| GET | `/diagnostics` | `dense_coverage` (état dense, `collection` : `present`, `absent` ou `unverified`, documents à réindexer avec leur nom, code d'erreur d'une liste ou d'un compte), versions, ressources du gouverneur, `security` (environnement, nombre de sessions actives et compteurs `audit_log` du journal d'audit, [section 2.5](#25-refus-et-journal-daudit)), identités dense et tokenizer, caches, empreinte du profil et du sélecteur, réconciliation ; `llm_accelerator`, accélération de la génération ([W025](../../RAG_Local_Agents/DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024)) : `requested` (`auto`, `cpu` ou `gpu`), `requested_source` (`profile`, `legacy_num_gpu` pour la forme antérieure `llm.num_gpu: 0`, `default` sans aucune des deux clés), `mode` (`gpu` ou `cpu`), `reason` (avec un profil en CPU imposé, `imposed_by_profile` ou, pour la forme antérieure, `legacy_profile_cpu`, que l'API ait été lancée par le superviseur ou non ; avec un profil `auto` ou `gpu`, raison de la décision prise par le superviseur au démarrage, `null` pour une API lancée sans cette décision ou si la raison transmise est inconnue ou contredit le mode) et `fallback` (`null`, ou `{utc, http_status, error}` après un échec du chargement sur GPU ; l'instance répond alors sur CPU jusqu'au redémarrage, `reason` gardant la décision du démarrage) | 200 ; aucun extrait documentaire ; le matériel n'est publié par aucune route publique |

Si la lecture des détails de la collection échoue, `/readiness` examine la
liste des collections. Une absence n'est déclarée que si une liste valide
ne contient pas le nom attendu. Si le nom est présent, une seule reprise
des détails est autorisée ; elle doit réussir pour rendre `present`. Une
liste invalide ou inaccessible, une identité non provisionnée ou un nouvel
échec des détails rendent `unreachable` et restent bloquants. La sonde ne
crée pas de collection et ne charge aucun modèle. Ce correctif est couvert
par 29 tests HTTP isolés avec doubles ; la recette native vérifie le parcours
SSE, pas une panne Qdrant provoquée ni toutes les branches de reprise.
[Exécution et limites D06.9](../../RAG_Local_Agents/journal/2026-10-05.md#d069--flux-progressif-reconnexion-et-annulation).

Depuis R26-IDX-02, `/readiness` nomme aussi l'état de l'index sémantique sans en faire un blocage : `dense_index` vaut `dense_migration_incomplete` quand une génération active portant des fragments n'a aucun point dans la collection de l'identité dense courante (identité d'embedding changée, réindexation partielle, retour à une identité précédente), et `documents_to_reindex` liste ces documents. Le statut et le code HTTP restent ceux des autres contrôles : la branche lexicale sert toujours ces documents et le lanceur ne dépend pas de cette sonde. Collection courante absente avec des générations publiées (cas déjà bloquant) : tous les documents actifs portant des fragments y sont listés, sans compte. `unverifiable` signale Qdrant injoignable, une liste de collections ou un compte en échec ; `not_applicable`, un double de vecteurs sans compte. Hors de `/readiness` (démarrage, `/diagnostics`, recherche), la liste des collections du projet est relue avant de compter une génération nouvelle : une collection courante absente est nommée `collection: absent`, avec tous les documents actifs à réindexer, et non comme une erreur Qdrant. Seuls les identifiants figurent dans cette route publique ; les noms sont dans `dense_coverage` de `/diagnostics`, derrière la session ou le jeton. Les comptes viennent de `count_generation` sur la seule collection courante : établis au démarrage sans retarder l'API (une ligne du journal de l'API annonce un état incomplet, une collection absente ou toute exception de cette tâche), gardés pour la vie du processus et rapprochés à chaque consultation de l'ensemble des générations actives relu dans SQLite sous le même verrou (`DenseCoverage`, [retrieval.py](../../services/api/retrieval.py)). Aucune migration SQLite. Le nettoyage d'une génération remplacée ou retirée supprime ses points dans toutes les collections du projet (préfixe `qdrant.collection` suivi de 16 caractères hexadécimaux d'empreinte, identité courante ou précédente), avec un filtre sur cette seule génération ; une liste de collections illisible ou une suppression en échec laisse le nettoyage en attente pour une reprise (`QdrantStore.delete_generation`, `Reconciler.run_once` dans [reconcile.py](../../services/api/reconcile.py)). Les points laissés par des nettoyages antérieurs à ce correctif ne sont pas repris.

### 4.2 Session

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/session/open?link` | Public. Échange un lien d'ouverture contre les cookies de session | 303 vers `/workspace/` ; 303 vers `/workspace/?session=lien-invalide` si le lien est inconnu, déjà présenté ou expiré |
| GET | `/session` | État de l'accès : `authenticated`, `environment`, `idle_timeout_minutes`, `method` (`session` ou `control_token`) et, pour une session, `created_at`, `idle_expires_at`, `absolute_expires_at` | 401 `session_required`, `session_expired` |
| POST | `/session/logout` | Public. Efface les cookies ; révoque la session si le jeton CSRF est valide | 200 `{"revoked": true}` ou `{"revoked": false}` |

### 4.3 Bibliothèque et documents

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/library/tree?limit&offset&cursor&search` | Tous les dossiers et les documents non retirés, paginés (1 à 200), filtre par sous-chaîne du chemin | 400 `invalid_cursor`, `invalid_pagination` |
| POST | `/documents/import` | Multipart : `files` (1 à 50 PDF/DOCX/XLSX) et `relative_paths` (liste JSON facultative, un chemin par fichier) | 202 `{imports: [{document_id, version_id, job_id, reused}]}`, avec `job_state` (et `resume_required` pour `paused`) quand un traitement suspendu est renvoyé ; avec un seul fichier, les champs de `imports[0]` sont repris à la racine ; 400 `invalid_file_count`, `invalid_paths`, `invalid_path`, `invalid_pdf` ; 409 `original_integrity_failure`, `document_removed` ; 413 `file_too_large` |
| GET | `/documents/{document_id}` | Document et versions (`format`, `mime_type`, `file_url`), révision active (`active_extraction_revision_id`), travaux | 404 `document_not_found` |
| DELETE | `/documents/{document_id}` | Retrait logique : document exclu des périmètres, travaux annulés, vecteurs mis en nettoyage | 404 `document_not_found` |
| POST | `/documents/{document_id}/move` | Déplace ou renomme dans l'arborescence sans nouveau travail ni recalcul d'embedding | 404 `document_not_found` ; 409 `path_conflict` |
| POST | `/documents/{document_id}/reindex` | Nouveau travail sur la dernière version ; renvoie le travail en cours s'il existe (`queued`, `extracting`, `indexing`). Selon le dernier travail de cette version : `paused`, il est renvoyé, à reprendre, au lieu d'un second qui recommencerait l'extraction ; `pausing`, la demande est refusée sans créer de travail, la pause doit d'abord aboutir ; `cancelling`, l'annulation reste définitive et un travail neuf est mis en file, exécuté après elle (la file traite un travail à la fois). Un document non publié affiche aussitôt l'état `queued` du travail neuf, que l'annulation qui se termine ne remplace pas. Issue de chaque état du dernier travail : `reindex_outcomes` du contrat | 202 `{job_id, version_id, reused: false}` ; `{job_id, reused: true}` pour un travail en cours ; `{job_id, version_id, reused: true, job_state: "paused", resume_required: true}` pour un travail en pause, à reprendre par `POST /jobs/{job_id}/resume` ; 404 `document_not_found` ; 409 `job_pausing` « Mise en pause en cours pour ce document : attendez qu'elle aboutisse, puis reprenez ce traitement depuis le Suivi. », `details` `{job_id, version_id, job_state}` |

Un réimport d'un contenu identique au même chemin dépend du dernier travail de cette version (`import_outcomes` du contrat, `Database.import_original` dans [db.py](../../services/api/db.py)) : `queued`, `extracting`, `indexing`, `ready` ou `ready_partial`, ce travail est renvoyé (`reused: true`) et aucun travail n'est créé ; `paused`, il est renvoyé avec `job_state: "paused"` et `resume_required: true`, à reprendre par `POST /jobs/{job_id}/resume` ; `pausing`, il est renvoyé avec `job_state: "pausing"`, sans `resume_required` ni travail créé, car `POST /jobs/{job_id}/resume` le refuse (409 `job_not_resumable`) tant que la pause n'a pas abouti ; `cancelling`, `cancelled` ou `error`, un travail neuf est mis en file sur la même version (`reused: false`), exécuté après l'annulation en cours s'il y en a une. La réindexation (`reindex_outcomes`), qui considère la dernière version du document, diffère pour trois de ces états : `ready` et `ready_partial` y donnent un travail neuf au lieu du travail existant, et `pausing` un refus 409 `job_pausing` ; l'import, qui traite jusqu'à cinquante fichiers par requête, renvoie cet état au lieu de refuser, pour que les autres fichiers soient importés.

Le champ `state` d'un document publié suit sa génération active (`ready` ou `ready_partial`). Un document sans génération publiée prend l'état de son dernier travail : `queued`, `extracting`, `indexing`, `paused` (y compris pendant `pausing`), `cancelled` (y compris pendant `cancelling`), `error` ou `ready_partial` (extraction partielle vérifiée, à publier) ; ce réalignement est fait au démarrage de l'API, à chaque pause, reprise ou annulation, à la création d'un travail par réindexation, à la fin d'un travail interrompu (pause, annulation ou erreur, `JobSupervisor.record_failure` dans [jobs.py](../../services/api/jobs.py)) et à la publication différée (`Database.align_document_states` dans [db.py](../../services/api/db.py)). Un travail plus ancien qui se termine ne masque donc pas un travail plus récent déjà en file. L'interface distingue un `ready_partial` sans `active_generation_id` (« Extraction partielle à publier »), qui n'est pas interrogeable.

### 4.4 Versions et lecture

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/versions/{version_id}/file` | Original à son MIME validé : PDF `inline`, DOCX/XLSX `attachment` ; `ETag` = SHA-256, cache immuable, plages d'octets (`Range`) prises en charge par `FileResponse` de Starlette 1.7.0 ; parcours ETag et plages de la recette lifecycle non exécuté | 304 si `If-None-Match` correspond ; 404 `source_removed` ; 409 `invalid_storage_path` |
| GET | `/versions/{version_id}/outline?extraction_revision_id` | Sections de la génération publiée ou de la révision demandée ; hiérarchie/éléments DOCX et feuilles XLSX, sans page Office inventée | 404 `extraction_revision_not_found` ; 409 `not_indexed` |
| GET | `/versions/{version_id}/pages/{page_index}/blocks?extraction_revision_id` | Géométrie de la page, blocs (texte, `bbox`, précision, provenance), avertissements de la génération | 404 `page_not_found`, `extraction_revision_not_found` ; 409 `not_indexed` |

L’extension Office conserve les mêmes contrôles de session et d’origine. L’import identifie DOCX/XLSX depuis le contenu OPC et l’extension validée ; le MIME envoyé par le client n’est pas une autorité. Avec plusieurs fichiers, les succès sont dans `imports` et les refus par fichier dans `errors` (`relative_path`, `code`, `message`) ; un fichier invalide n’efface pas les imports acceptés. Avec un fichier seul, le refus conserve le statut HTTP de l’erreur. Les contrôles `office_*` du package, notamment corruption, macros, chemins/relations et quotas, interviennent avant l’enregistrement de sa version.

| Méthode | Chemin | Données et bornes | Erreurs notables |
|---|---|---|---|
| GET | `/versions/{version_id}/representation?extraction_revision_id&cursor&limit` | `format`, version/génération/révision, unités (`id`, `kind`, `title`, `part`, ordre, parent, métadonnées), couverture, avertissements et limites ; curseur à partir de 0, limite de 1 à 100 (défaut 50), `next_cursor` nul à la fin | `invalid_document_format`, `invalid_pagination`, `extraction_revision_not_found`, `not_indexed` |
| GET | `/versions/{version_id}/units/{unit_id:path}/blocks?extraction_revision_id&cursor&limit&block_id` | Blocs d’une unité enregistrée, texte/hash, structure et localisateur typé ; mêmes bornes de pagination. `block_id` positionne le curseur sur un ancrage enregistré pour ouvrir une citation | `office_unit_not_found`, `block_not_found`, `invalid_pagination` |
| GET | `/versions/{version_id}/sheets/{sheet_id:path}/cells?extraction_revision_id&row_start&row_end&column_start&column_end` | Cellules présentes, types/valeurs/formules/caches, feuille, tables et métadonnées ; bornes à partir de 1 incluses. Défaut lignes 1–50 et colonnes 1–20 ; au plus 10 000 positions dans la fenêtre | `invalid_document_format`, `sheet_not_found`, `invalid_cell_range` ; 413 `office_window_too_large` |
| GET | `/versions/{version_id}/assets/{asset_id}?extraction_revision_id` | Image DOCX enregistrée par SHA-256 : PNG/JPEG/GIF/BMP/WebP vérifiés, au plus 16 Mio et 16 millions de pixels ; contrôle du hash original et de l’image | `asset_not_found`, `asset_not_available`, `original_integrity_failure` |

Les réponses JSON de représentation, blocs et cellules renvoient `version_id`, `generation_id`, `extraction_revision_id` et `format`. La route des assets renvoie le binaire avec son type MIME vérifié. La révision passée en paramètre doit correspondre à une génération publiée enregistrée de cette version ; elle n’est jamais remplacée silencieusement par la plus récente. Les IDs d’unité/feuille peuvent contenir `/` : les convertisseurs de chemin les résolvent contre les enregistrements SQLite. Aucun chemin de partie OPC, XPath ou texte source fourni par le client n’est évalué. Les SVG, HTML et objets OLE ne sont pas affichés en ligne. Sources exécutables : [office.py](../../services/api/office.py), [routes de main.py](../../services/api/main.py) et [tests API Office](../../tests/unit/test_office_api.py).

Une source Office porte `format`, `locator`, `extraction_revision_id` et `extraction_methods: ["office_native"]`. `page_index` et `page_number` sont nuls, les pages sont vides ; la précision est `element`, `cell` ou `range`. Une sélection XLSX limitée au préfixe textuel d’un bloc, sans binding de cellule, reste de précision `block` et ne reçoit aucun localisateur de cellule. Un localisateur DOCX désigne `unit_id`, `part`, `element_path` ; un localisateur XLSX désigne unité/feuille/partie, adresse/plage et bornes. Ces métadonnées accompagnent `/search`, les événements `sources`/`done.citations` et le registre des citations. Le lecteur utilise ce registre, sans déduire une page du nom du fichier.

### 4.5 Recherche, questions et citations

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| POST | `/search` | Recherche hybride sans modèle de langue : `results` (chacun avec `extraction_methods`, voir [section 5](#5-flux-sse-dune-question)), `top10`, `scope_snapshot`, `warnings` (dont `ocr_evidence` avec `source_ids` vide), `elapsed_ms` | 404 `folder_not_found`, `section_not_found`, `source_removed` ; 409 `no_document_in_scope` ; 400 `invalid_selection`, `invalid_page_range` |
| POST | `/queries` | Crée une question et lance son traitement | 202 `{query_id, conversation_id, events_url}` (plus `state: needs_clarification` si un référent est ambigu) ; 429 `query_queue_full` ; 404 `conversation_not_found`, `focus_not_found`, `followup_not_found` ; 409 `focus_outside_scope` |
| GET | `/queries/{query_id}/events?after` | Flux SSE reprenable ; voir [section 5](#5-flux-sse-dune-question) | 404 `query_not_found` ; 400 `invalid_event_id` |
| POST | `/queries/{query_id}/cancel` | Annulation immédiate ; coupe aussi l'appel au modèle | `{query_id, state}` ; 404 `query_not_found` |
| GET | `/citations/{query_id}/{source_id}` | Source enregistrée : document, version, révision, page PDF ou localisateur Office, blocs (avec `extraction_method`), boîtes, précision, `extraction_methods` ; une citation enregistrée avant R26 est rendue avec `extraction_methods: ["unknown"]` et `extraction_method: "unknown"` par bloc, la ligne stockée restant inchangée (`with_extraction_provenance`, [scope.py](../../services/api/scope.py)) | 404 `citation_not_found`, `source_removed` |

### 4.6 Travaux d'ingestion

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| GET | `/jobs?limit` | Travaux récents avec couverture, avertissements, publication ; `progress` vaut 0,05 au lancement de l'extraction, puis suit la part des pages du préflight couvertes par les fenêtres durables jusqu'à 0,65, relevée par la boucle qui surveille le worker et écrite à chaque fenêtre nouvelle ; l'indexation va de 0,65 à 0,95, la publication donne 1 ; une extraction reprise du cache reste à 0,05 jusqu'à l'indexation ; `runtime_mode` : priorité choisie, `interactive` (priorité aux questions, imports suspendus) ou `ingestion` (priorité aux imports) ; le mode instantané du gouverneur n'est plus exposé ici ; `generation` : matériel de la génération, relu par l'atelier avec le suivi (W025, P7), `{"device": "gpu" | "cpu", "fallback": bool, "processor": str | null, "model": str}`, `fallback` passant à `true` après un repli sur CPU, valable jusqu'au redémarrage ; `processor` : dernière occupation du modèle relue par l'API dans `/api/ps` d'Ollama, sous la forme de la colonne PROCESSOR d'`ollama ps` (`100% GPU`, `100% CPU`, `25%/75% CPU/GPU` ou `Unknown`), avant chaque question et, en mode GPU, après chaque réponse, jamais par cette route ; `null` tant que le modèle n'a pas été vu chargé depuis le démarrage de l'API et de nouveau après un repli, qui le décharge (`generation` vaut `null` avec un double de test de la passerelle Ollama) ; le détail reste dans `llm_accelerator` de `/diagnostics` | 400 `invalid_pagination` |
| POST | `/jobs/resume-paused` | Remet en file, dans leur ordre d'import, tous les travaux à l'état `paused` (`JobSupervisor.resume_paused`, [jobs.py](../../services/api/jobs.py)) | 200 `{"resumed": n}` ; 409 `interaction_active` si une question est active, avant toute reprise (tout ou rien) |
| POST | `/jobs/{job_id}/pause` | Pause coopérative : `pausing` si le travail tourne, sinon `paused` | 404 `job_not_found` ; 409 `job_not_pauseable` |
| POST | `/jobs/{job_id}/resume` | Remet en file un travail `paused`, `error` ou `cancelled` | 409 `job_not_resumable`, `retry_limit` (trois tentatives en erreur), `interaction_active` |
| POST | `/jobs/{job_id}/cancel` | Annulation : `cancelling` si le travail tourne | 404 `job_not_found` |
| POST | `/jobs/{job_id}/publish-partial` | Publie une extraction `ready_partial` vérifiée ; nécessaire seulement quand du texte manque, une extraction dont seules des figures ne sont pas interprétées étant publiée d'office ([W012](../../RAG_Local_Agents/DECISIONS.md#w012-figures-non-interprétées--limite-déclarée-publication-automatique)) | 404 `job_not_found` ; 409 `not_partial` |
| POST | `/runtime/mode` | `{"mode": "interactive"}` met les imports en pause ; `{"mode": "ingestion"}` lève la pause sans reprendre automatiquement les travaux en pause | 409 `interaction_active` ; 503 `governor_not_configured` |

`generation.model` est le nom exact servi par le profil de démarrage, fourni par `generation_device` dans [main.py](../../services/api/main.py), sans appel supplémentaire à Ollama et sans preuve que le modèle est chargé. Le bandeau explique le redémarrage nécessaire pour en changer. Une API antérieure peut omettre ce champ ; un nom absent ou non imprimable n'efface pas un matériel valide (`readGeneration`, [generation.ts](../../apps/web/src/lib/generation.ts)). `QueryRequest` ne reçoit aucun choix de modèle : les questions utilisent celui de l'instance. Procédure dans l'[exploitation](../exploitation/EXPLOITATION.md#91-changer-le-modèle-de-génération). L'intégration de ce champ ne prouve pas son parcours natif R23.

### 4.7 Administration (jeton requis)

| Méthode | Chemin | Rôle | Réponses et erreurs notables |
|---|---|---|---|
| POST | `/admin/session-links` | Émet un lien d'ouverture de session à usage unique | 200 `{path, expires_in_seconds}` ; 403 `invalid_control_token` |
| POST | `/admin/sessions/revoke` | Révoque toutes les sessions et tous les liens en attente | 200 `{revoked}` ; 403 `invalid_control_token` |
| POST | `/admin/quiesce` | Suspend les mutations, attend celles en cours, annule les questions, met le travail actif au checkpoint, exécute `PRAGMA wal_checkpoint(FULL)` | 403 `invalid_control_token` |
| POST | `/admin/resume` | Relance les mutations et la réconciliation | 403 `invalid_control_token` |
| GET | `/admin/status` | Mutations suspendues, questions actives, travail actif | 403 `invalid_control_token` |
| POST | `/admin/evaluation/context` | Contexte d'une question sans appel au modèle, pour la qualification | 409 `ingestion_active`, `query_active` ; 503 `mutations_paused` |

Le jeton est celui de la [section 2.4](#24-jeton-de-contrôle-des-outils-locaux) ; `rag.ps1 open` et `rag.ps1 backup` l'utilisent.

### 4.8 Hors préfixe

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/openapi.json` | Schéma OpenAPI généré par FastAPI 0.142.1 ; développement seulement (`openapi_url`, [main.py](../../services/api/main.py)) |
| GET | `/api/docs` | Interface Swagger de FastAPI, développement seulement ; ses scripts viennent d'un CDN que la CSP bloque ; page non examinée au rendu |
| GET | `/`, `/workspace/`… | Export statique de `apps/web/out` (montage de `StaticFiles`, [main.py](../../services/api/main.py)) |

## 5. Flux SSE d'une question

Depuis [W039](../../RAG_Local_Agents/DECISIONS.md#w039-plafonds-de-réponse-et-avertissement-de-longueur),
l'interface regroupe `finish_reason: length` et l'avertissement
`answer_length_limit` en un seul message de réponse incomplète. Les événements,
compteurs et autres avertissements restent conservés ; aucune génération
supplémentaire n'est déclenchée. Les plafonds des profils livrés et leur réserve
de contexte sont définis dans [IMPLEMENTATION.md, section 7](../../RAG_Local_Agents/IMPLEMENTATION.md#7-contexte-conversation-et-génération)
et dans les profils runtime canoniques. Une fin `stop` ne certifie pas la
fiabilité documentaire ni la présence de citations valides dans la réponse.

Le flux `GET /api/v1/queries/{query_id}/events` (`text/event-stream`, `Cache-Control: no-cache`) relit les événements persistés dans SQLite : chaque événement porte `id` (entier croissant par question), `event` (type) et `data` (JSON). La reprise se fait par l'en-tête `Last-Event-ID` (envoyé automatiquement par `EventSource`) ou le paramètre `after` ; elle ne relance pas la génération. Une ligne de commentaire `: heartbeat` est émise toutes les 10 s ; le flux se ferme quand la question est terminée et que le dernier événement a été envoyé (`query_events`, [main.py](../../services/api/main.py)). Le flux suit les règles de la [section 2](#2-session-et-autorisation) : `EventSource` envoie le cookie de session de la même origine, un outil local présente le jeton de contrôle.

| Type | Données | Émis par |
|---|---|---|
| `status` | `state` : `queued`, `waiting_for_ingestion_checkpoint`, `searching`, `waiting_for_resources` (avec `available_mib`, `required_mib`), `generating` ; après un repli sur CPU dont la nouvelle admission a attendu de la mémoire, `generating` est émis de nouveau avant la relance | [query.py:176-244](../../services/api/query.py#L176-L244) |
| `needs_clarification` | `message`, `choices` (identifiants candidats) ; aucune recherche lancée | [query.py:49](../../services/api/query.py#L49) |
| `sources` | `sources` : sources enregistrées `S001`… (document, version, page PDF ou localisateur Office, blocs, boîtes, précision, révision, `extraction_methods`, `citation_url`) ; liste vide si aucune preuve | [query.py:210](../../services/api/query.py#L210) |
| `warning` | Objet `{code, message, …}` (périmètre, identifiants, extraction partielle, lecture OCR, budget de contexte), émis avant le premier `delta` ; codes ci-dessous | [query.py:211-212](../../services/api/query.py#L211-L212) |
| `delta` | `text` : fragment de réponse ; sans source, un seul delta dit que les preuves du périmètre ne suffisent pas | [query.py:216](../../services/api/query.py#L216), [query.py:252](../../services/api/query.py#L252) |
| `done` | `message`, `text`, `status` (`done` ou `length_limited`), `citations` (avec `extraction_methods`), `finish_reason`, `metrics`, `warnings` (avertissements du flux et contrôles de la réponse) | [query.py:280](../../services/api/query.py#L280) |
| `error` | `code`, `message`, `metrics` ; `resource_admission_denied` pour un refus d'admission, `interrupted` après un redémarrage de l'API | [query.py:284-292](../../services/api/query.py#L284-L292), `Database.initialize` dans [db.py](../../services/api/db.py) |
| `cancelled` | `state`, `text` (réponse partielle), `metrics` ; un seul par question | [query.py:154-164](../../services/api/query.py#L154-L164) |

Chaque source et chaque citation portent `extraction_methods`, liste triée sans doublon des méthodes d'extraction de leurs blocs, et chaque bloc `extraction_method` : valeur `metadata.extraction_method` écrite par l'ingestion (`native`, `ocr`, `mixed`, `office_native`, `unknown`), recopiée telle quelle ; un bloc sans cette métadonnée (index antérieur, extraction contrôlée) vaut `unknown`, jamais `native` (`block_extraction_method` et `ScopeResolver.source_for_chunk` dans [scope.py](../../services/api/scope.py)). Les événements enregistrés avant R26 (2026-10-06) n'ont pas ces champs et un client les lit `unknown` ; `GET /citations` les complète ainsi pour une citation de cette époque. Le contexte transmis au modèle n'en porte rien ; chaque preuve y garde `source_id`, `version_id`, `pages` et `text`.

| Code d'avertissement | Champs en plus de `code` et `message` | Émission |
|---|---|---|
| `document_not_in_scope`, `comparison_incomplete`, `dense_unavailable_for_historical_revision` | `document_id` et `reason`, comptes, révision | Résolution du périmètre ([scope.py](../../services/api/scope.py)), événement `warning` |
| `dense_identity_mismatch` | `document_ids`, `document_names` | Recherche, en tête de ses avertissements : documents du périmètre dont la génération active n'a aucun point dans la collection de l'identité dense courante ; ils restent servis par la branche lexicale ; jamais pour une sélection. Message : « Recherche sémantique incomplète : « nom » n'a pas d'index sémantique pour le modèle d'embedding actuel. La recherche par mots peut encore le retrouver ; réindexez-le pour rétablir la recherche sémantique. » (forme plurielle avec le nombre de documents, cinq noms au plus et « peut encore les retrouver ») |
| `identifier_not_found_in_scope`, `comparison_gap` | `identifier` ou `document_id` | Recherche ([retrieval.py](../../services/api/retrieval.py)), événement `warning` |
| `partial_extraction` | `document_id` | Recherche, un par document dont la génération publiée est `ready_partial` ; le message, valable pour une recherche comme pour une question, dit que des pages ou régions manquent ou ont été lues avec une confiance insuffisante, que des informations peuvent manquer, et demande de vérifier les passages retrouvés sur la page originale |
| `ocr_evidence` | `document_id`, `document_name`, `extraction_methods` (`ocr`, `mixed`), `source_ids` | Un par document dont une source porte un bloc `ocr` ou `mixed` ; dans une question, calculé sur les sources transmises au modèle et émis avant le premier `delta`, `source_ids` listant ces sources ; `POST /search` et l'évaluation le calculent sur leurs passages finals, avec `source_ids` vide. `native` et `unknown` ne le déclenchent pas (`ocr_evidence_warnings`, [retrieval.py](../../services/api/retrieval.py)) |
| `exact_identifier_not_in_context`, `identifier_present_no_answer_evidence`, `context_fragments_excluded_by_budget`, `comparison_document_not_in_context` | `identifiers`, `count` ou `document_ids` | Assemblage du contexte ([context.py](../../services/api/context.py)), événement `warning` |
| `tokenizer_template_drift`, `unknown_citations`, `answer_length_limit` | `difference` ou `source_ids` | Après la génération, dans `done.warnings` seulement |
| `answer_without_valid_citation` | — | `done.warnings` seulement, quand le modèle a été appelé sur au moins une source et que la réponse validée ne contient aucune citation `[Sxxx]` d'une source transmise |
| `source_id_mentioned_without_citation` | `source_ids` | Avec le précédent seulement : identifiants de sources transmises écrits sans crochets (`S001`, `(S001)`, `Source ID: S001`), dans l'ordre des sources ; jamais émis pour une réponse qui contient une citation valide |
| `cited_value_not_in_cited_sources` | `values` : `value`, `number`, `unit`, `cited_source_ids`, `holder_source_ids` | `done.warnings` seulement : nombre d'une phrase ou d'une puce absent des sources qu'elle cite, présent dans une autre source transmise |
| `value_not_in_context` | `values` : `value`, `number`, `unit`, `cited_source_ids` | `done.warnings` seulement : nombre de la réponse absent de toutes les sources transmises (valeur calculée, déduite ou mal reprise) |

Les quatre derniers codes viennent de `answer_warnings` ([claims.py](../../services/api/claims.py)) : ce sont des signaux, sans retrait ni réécriture du texte, des citations ou des événements déjà émis ([W037](../../RAG_Local_Agents/DECISIONS.md#w037-candidat-éditorial-2b-refusé-après-un-témoin-unique) : ni filtre ni réécriture de réponse). Les nombres sont comparés en décimal (virgule ou point, espace ou séparateur de milliers ambigu « 1,020 ») ; les identifiants à lettres (`DA-P02`, `QV-01`, `S001`), les mentions de page, les balises de citation et les numéros de liste sont ignorés côté réponse, tous les nombres comptent côté sources. L'unité est affichée avec la valeur mais n'est pas comparée. Côté réponse sont aussi ignorés les plages de pages (`pp. 3-4`), les paragraphes (`§ 4.3`), les rangs (`2e`, `3ème`, `1er`, `2nde`, `3rd`) et les dates à séparateur répété (`12/03/2024`, `12-03-2024`, `2024-03-12`) ; une plage de décimaux (`12.5-13.5`, `10.25-10.50`) reste contrôlée ; une lettre isolée n'est affichée comme unité que si c'est un symbole courant (`V`, `A`, `W`, `m`, `g`, `s`, `h`, `l`, `L`, `K`, `N`, `J`, `T`). Côté sources, un nombre groupé par espaces (« 120 150 180 ») vaut aussi chacun de ses groupes. Une phrase sans citation qui reprend un nombre de la question (abstention « à 20 °C ») n'est pas signalée ; une phrase citée reste contrôlée sans tenir compte de la question. Une citation qui suit une fin de phrase sur la même ligne, ou seule sur sa ligne, conclut la phrase précédente ; une citation qui ouvre une puce suivie d'un texte (`*   [S002] confirme…`) reste à cette puce. Limites restantes : le découpage est local à la phrase ou à la puce (une citation placée dans la phrase suivante échappe au rapprochement), l'unité n'est pas comparée (une valeur reprise avec la mauvaise unité passe), un nombre écrit en lettres ou un signe (`-5` contre `5`) n'est pas contrôlé, une suite de trois entiers reliés par le même séparateur (`10-12-15`, `1/2/50`) est lue comme une date, un identifiant de document de la forme `S00x` peut être pris pour une source, et une valeur calculée juste est signalée comme absente des sources.

Les `delta` antérieurs aux 512 derniers événements d'une question sont supprimés (`Database.add_event`, [db.py](../../services/api/db.py)) : une reprise tardive retrouve le texte complet dans `done`. Les métriques de `done` comprennent `model_called`, `queue_wait_ms`, `retrieval_ms`, `context_ms`, `generation_admission_wait_ms`, `ttft_ms` et `elapsed_ms`, ainsi que les compteurs rendus par Ollama et, quand le modèle a été appelé (`model_called: true`), `llm_execution` (W025) : `{"mode": "gpu" | "cpu", "fallback": bool}`, absent du `done` d'une abstention. `mode` est le mode d'exécution demandé à Ollama pour cette réponse (option `num_gpu` omise en `gpu`, `num_gpu: 0` en `cpu`), non l'occupation constatée du modèle : en mode `gpu`, Ollama peut le charger en partie ou en totalité sur le CPU, ce que rapportent `generation.processor` de `GET /jobs` et la rubrique « calcul » de `doctor`. `fallback` vaut `true` quand la réponse a été régénérée sur CPU dans la même question : en mode GPU, Ollama a répondu 500 avant tout événement (échec du chargement, dont il ne se relève pas seul) ; l'API a consigné l'erreur (`fallback` de `llm_accelerator` dans `/diagnostics`, message d'Ollama tronqué à 300 caractères), passé l'instance en CPU jusqu'au redémarrage, déchargé le modèle (un déchargement non confirmé est journalisé sans arrêter le repli), libéré les caches comme avant tout chargement à froid, obtenu du gouverneur une nouvelle admission à froid dans le bail en cours (`readmit_generation`, appelée par `before_cpu_fallback` de [main.py](../../services/api/main.py)), puis relancé une seule fois avec `num_gpu: 0`. Si cette admission est refusée, la question se termine par `resource_admission_denied`, sans relance. Les autres échecs (503, 499, autre statut 4xx ou 5xx, erreur de transport, événement `error` du flux, erreur après le premier fragment) sont rapportés comme auparavant, sans repli (`OllamaGateway.stream` et `fall_back_to_cpu` dans [ollama.py](../../services/api/ollama.py)).

Quand la recherche a rendu des passages, les métriques de `done` reprennent aussi celles de l'assemblage du contexte (`ContextBuilder.build`, [context.py](../../services/api/context.py)), dont `identifier_coverage_states` : pour chaque identifiant exact de la question, `covered` (un passage du contexte final porte l'identifiant et un terme de la question), `identifier_present_no_answer_evidence` (identifiant présent sans aucun terme de la question, signalé par l'avertissement du même code : « ne pas en déduire de réponse »), `identifier_present_languages_differ` (identifiant présent sans terme commun, mais la question et un passage qui le porte sont rédigés dans deux langues reconnues différentes, français et anglais : l'état n'affirme ni une réponse ni son absence et n'émet aucun avertissement), `not_covered_due_to_budget` (retrouvé puis écarté par le budget de contexte) ou `not_found_in_scope` (absent des passages retrouvés dans le périmètre). Ce contrôle est lexical : il ne juge pas la réponse générée.

Exemple de lecture, avec l'identifiant renvoyé par `POST /queries` et le jeton `$controle` de la [section 2.4](#24-jeton-de-contrôle-des-outils-locaux) :

```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8785/api/v1/queries/<query_id>/events?after=0" -Headers $controle | Select-Object -ExpandProperty Content
```

## 6. Corps de requête

Les corps sont validés par Pydantic avec `extra="forbid"` ([schemas.py](../../services/api/schemas.py)).

| Modèle | Champs | Règles |
|---|---|---|
| `Scope` | `kind` (`library`, `folder`, `documents`, `section`, `pages`, `selection`, `sheet`, `cell_range`), `folderId`, `recursive` (toujours `true`), `documentIds` (1 000 au plus), `versionId`, `sectionId`, `pageStart`, `pageEnd` (à partir de 0, inclus), `spans` (128 au plus), `extractionRevisionId`, `sheetId`, `rowStart`, `rowEnd`, `columnStart`, `columnEnd` | `folder` exige `folderId` ; `documents` au moins un identifiant ; `pages`, `section`, `selection` exigent `versionId` ; plage de pages ordonnée ; `sheet`/`cell_range` exigent version, révision et feuille ; `cell_range` exige les quatre bornes ordonnées, entiers stricts, lignes 1–1 048 576 et colonnes 1–16 384 incluses |
| `SelectedSpan` | `extractionRevisionId`, `blockId`, `blockTextSha256` (64 hexadécimaux), `offsetUnit` = `unicode_code_point`, `startOffset` < `endOffset` | Décalages en points de code sur le texte source haché |
| `QueryRequest` | `question` (1 à 12 000 caractères), `scope`, `mode` (`question`, `selection`, `section`, `comparison`, `compare`, `factual`, `ordinary`, `analysis`), `conversation_id`, `followup_of`, `focus` | `comparison` exige `kind: documents` avec 2 à 4 documents distincts ; `focus` limité à `query_id`, `source_id`, `version_id`, `block_id`, `identifier` |
| `DocumentMove` | `relative_path` (1 à 1 024 caractères) | Chemin relatif PDF/DOCX/XLSX sûr ; le déplacement ne change pas le format |
| `RuntimeMode` | `mode` : `interactive` ou `ingestion` | — |

Les scopes XLSX sont versionnés : `sheet` vise une feuille entière ; `cell_range` vise une plage dans la révision exacte annoncée. Une section Office peut également épingler `extractionRevisionId`. Une version archivée reste accessible à un scope Office épinglé tant que sa révision publiée est conservée et autorisée ; une révision absente ou une source retirée est refusée. Les plages PDF conservent leur indexation à partir de 0 ; les cellules XLSX utilisent des bornes à partir de 1.

Pour `cell_range`, le contenu est projeté **avant** les identifiants, les statistiques lexicales, le scoring dense, RRF et le top-k. Le serveur refuse par 413 `office_scope_too_large` une plage dépassant 1 000 cellules présentes, 200 000 caractères ou 2 048 fragments. Cette borne de recherche est distincte des 10 000 positions du lecteur. Aucun en-tête, parent ou focus hors de la plage ne complète implicitement ses preuves. Formule et valeur du cache sont séparées ; le contexte annonce l’absence de recalcul et la fraîcheur inconnue du cache ([office_search.py](../../services/api/office_search.py), [context.py](../../services/api/context.py), [tests de périmètre Office](../../tests/unit/test_office_rag.py)).

Exemple de recherche sur toute la bibliothèque, avec le jeton de contrôle (aucun jeton CSRF n'est alors exigé) :

```powershell
$body = @{ question = 'pression nominale DA-P01'; scope = @{ kind = 'library' } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8785/api/v1/search -Headers $controle -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

## 7. Écarts avec le contrat partagé

Depuis l’intégration Office du 10 octobre 2026, le contrat partagé est en version **3** ; le schéma SQLite est indépendamment en version **4**. Les routes Office, formats/MIME, scopes feuille/plage, localisateurs, précisions et provenance native sont décrits par le contrat et contrôlés avec [test_api_contract.py](../../tests/unit/test_api_contract.py). Les ajouts préservent les corps et localisations PDF ; les preuves de qualification restent propres à chaque plateforme.

Le contrat [contracts.json](../../packages/contracts/contracts.json) a été réaligné sur l'API le 1er octobre 2026 (lot J5, constat C1) : routes montées et accès, réponse de `/health`, sélection (`blockTextSha256`, `offsetUnit`), états des documents (`paused`, `cancelled` ; `imported` et `ocr`, jamais produits, retirés) et des travaux, réponse de réindexation, modes, `followup_of` et `focus`, réponse de création de question, événement `needs_clarification` et données de chaque événement, frontières du gouverneur et de l'ingestion, lancement réel par `services.runtime.api_entry`. [test_api_contract.py](../../tests/unit/test_api_contract.py) compare le contrat aux routes montées, aux événements émis par `services/api` et écoutés par [stream.ts](../../apps/web/src/lib/stream.ts), aux états produits, aux corps validés, aux commandes annoncées par `/health` (dont `doctor`), à la réponse réelle de la réindexation pour chaque état du dernier travail (`reindex_response` et `reindex_outcomes` : `resume_required` pour `paused` seulement, 409 `job_pausing` pendant `pausing`, travail neuf pendant `cancelling`), à celle de l'import d'un contenu identique (`import_response` et `import_outcomes` : `resume_required` pour `paused` seulement, `job_state` sans reprise pendant `pausing`, travail neuf pendant `cancelling`) et aux signatures réelles : toute nouvelle dérive fait échouer la suite. Depuis l'accélération GPU ([W025](../../RAG_Local_Agents/DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024)), il compare aussi `diagnostics_llm_accelerator`, `jobs_response.generation` et `done_data.metrics.llm_execution` aux réponses réelles de l'API (`test_contract_generation_accelerator_fields_match_the_api`), vérifie l'absence de `llm_execution` dans le `done` d'une question sans appel au modèle (`test_contract_llm_execution_is_absent_from_an_abstention_that_calls_no_model`) et la raison rendue sans décision du superviseur, profil par profil (`test_contract_accelerator_reason_without_the_supervisor_decision_matches_the_api`) ; `readmit_generation`, appelée avant une relance sur CPU, figure dans la frontière du gouverneur (`test_contract_governor_boundary_matches_the_resource_governor`). Les états de `done_data.metrics.identifier_coverage_states` sont comparés aux valeurs qu'affecte `ContextBuilder.build` dans [context.py](../../services/api/context.py) (`test_contract_identifier_coverage_states_are_those_the_context_builder_assigns`). Depuis R26 (2026-10-06), les valeurs de `source.extraction_methods` sont comparées à celles que rend `source_method` de l'ingestion, plus `unknown` (`test_contract_source_extraction_methods_are_the_ingestion_vocabulary`), et les champs de `query_events.warning_data` à ceux des avertissements que construisent réellement [retrieval.py](../../services/api/retrieval.py) et [claims.py](../../services/api/claims.py) (`test_contract_r26_warning_fields_match_the_warnings_built_by_the_api`), et `readiness_dense_index` aux champs et valeurs de `GET /readiness` (`test_contract_readiness_dense_index_fields_are_those_of_the_api`) ; ces ajouts au contrat sont additifs, aucun champ n'est retiré.

| Point | Référence | Implémentation |
|---|---|---|
| Authentification | Absente d'[IMPLEMENTATION.md §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http) ; décrite par la section `access` du contrat | Session ou jeton de contrôle exigés (W011) ; codes `session_required`, `session_expired`, `csrf_rejected` |
| Routes non prévues par [IMPLEMENTATION.md §2](../../RAG_Local_Agents/IMPLEMENTATION.md#2-contrats-http) | Listées par le contrat | `/session`, `/session/open`, `/session/logout`, `/documents/{id}/move`, `/jobs/{id}/publish-partial`, `/jobs/resume-paused`, `/admin/*` |
