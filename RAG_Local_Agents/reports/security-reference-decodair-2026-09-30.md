# Sécurité applicative : transposition de decodair

**Rôle :** rapport d'analyse du lot R17 (documentation vivante). **Statut :** analyse terminée, mise en œuvre en cours. **Date :** 30 septembre 2026, 17:25 UTC. **Base :** commit `ae387a9` de ce dépôt ; decodair lu en lecture seule le 30/09 (cartographie par un agent, fichiers et lignes cités ci-dessous, aucun `.env` ouvert).

Demande utilisateur reçue vers 16:45 UTC : aligner la gestion des cookies et sessions, l'expiration, la révocation côté serveur, la déconnexion, les autorisations et les protections de l'API sur decodair, sans copie aveugle, avec l'OWASP et les sources officielles pour trancher ; en développement local ni cookie `Secure` ni TLS imposés, en production des réglages adaptés.

## Deux architectures différentes

| Point | decodair | Ce projet |
|---|---|---|
| Utilisateurs | comptes en base, six rôles, environ vingt-cinq permissions (`backend/app/config/security.py:15-154`) | poste mono-utilisateur (décision D-01) ; le mode multi-utilisateur est hors périmètre (`SPEC_ARCHITECTURE.md` §réseau) |
| Réseau | Traefik, TLS en production, écoute 127.0.0.1 sans TLS (`siana/02_generate_siana_config.sh:86-91, 524-539`) | API, Qdrant et Ollama sur 127.0.0.1 uniquement, profil refusé sinon (`services/runtime/supervisor.py`, `load_profile`) |
| Frontend | serveur Next.js `standalone` (`frontend/next.config.ts:25`) | export statique servi par FastAPI, même origine |
| Clients non navigateur | jeton `Authorization: Bearer` | outils locaux (sauvegarde, qualification, import) munis du jeton de contrôle de l'instance |

Conséquence : ce qui suppose des comptes (mots de passe, rôles, invitations, limitation des tentatives par compte) n'a pas d'objet ici. Ce qui protège une session de navigateur et l'API contre une page étrangère s'applique.

## Mécanismes repris, adaptés ou écartés

| Mécanisme decodair | Preuve decodair | Décision ici | Justification |
|---|---|---|---|
| Session serveur faisant autorité, relue à chaque requête | `backend/app/api/dependencies.py:76-80`, table `iam.auth_sessions` (`infrastructure/db/models/iam.py:146-178`) | **Adapté** : registre de sessions en mémoire du processus API | Une seule instance mono-utilisateur ; le redémarrage de l'API révoque toutes les sessions, ce qui est voulu |
| Identifiant de session aléatoire de 256 bits | `api/routers/auth.py:154` (`token_urlsafe(32)`) | **Repris** | OWASP Session Management : au moins 64 bits d'entropie |
| Identifiant stocké en clair côté serveur | `models/iam.py:162` | **Écarté** : seul le SHA-256 de l'identifiant est conservé | Une fuite du registre (diagnostic, vidage mémoire) ne donne pas de session utilisable |
| Cookie `HttpOnly`, `SameSite` configurable (défaut `lax`), `Path=/`, `Max-Age` absolu | `api/routers/auth.py:60-94` | **Repris**, `SameSite=Strict` | Aucun parcours entrant depuis un autre site n'a besoin du cookie ; Strict est le réglage le plus restrictif compatible |
| `Secure` selon l'environnement, pas de préfixe `__Host-` | `config/settings.py:606-609`, Siana `02_generate_siana_config.sh:524-539` | **Adapté** : développement sans `Secure` ; production avec `Secure` et préfixe `__Host-` | Demande utilisateur ; OWASP : `__Host-` impose `Secure`, `Path=/` et l'absence de `Domain` |
| Expiration d'inactivité 60 min et absolue 12 h | `config/settings.py:590-594`, `iam_service.py:442-462` | **Repris** avec des valeurs de profil (`security.session_idle_minutes`, `security.session_absolute_hours`) | OWASP : durées selon la criticité ; valeurs par défaut 120 min et 12 h pour un poste de consultation documentaire |
| Rotation à la connexion, session précédente révoquée | `api/routers/auth.py:107-148` | **Repris** : ouvrir une session révoque celle que portait le navigateur | Protection contre la fixation de session (OWASP) |
| Connexion par identifiant et mot de passe | `api/routers/auth.py:262-335` | **Adapté** : lien d'ouverture à usage unique, valable 5 min, émis par le lanceur local (`rag.ps1 open`) avec le jeton de contrôle de l'instance | Pas de compte sur un poste mono-utilisateur ; le secret provient du dossier de contrôle, lisible par le seul utilisateur Windows qui a démarré l'instance |
| Jeton CSRF synchroniseur lié à la session, en-tête `X-CSRF-Token` sur les mutations | `api/dependencies.py:137-153`, `frontend/src/lib/api.ts:49-65` | **Repris** : remis dans un cookie lisible (`rag_csrf`, sans `HttpOnly`) que le frontend renvoie dans `X-CSRF-Token` ; seul son SHA-256 est conservé côté serveur | OWASP CSRF : jeton synchroniseur pour une application à état ; s'ajoute aux contrôles `Origin` et `Sec-Fetch-Site` déjà en place |
| Déconnexion : cookie toujours effacé, révocation seulement avec CSRF valide | `api/routers/auth.py:338-381` | **Repris** | Une page étrangère ne peut pas révoquer la session ; OWASP : bouton de déconnexion visible |
| Révocations multiples (mot de passe, rôle, admin) | `iam_service.py:488-532` | **Adapté** : déconnexion, révocation de toutes les sessions par l'administration locale (jeton de contrôle), redémarrage de l'API | Pas de compte ni de rôle à changer |
| Purge périodique des sessions expirées | `main.py:1293-1333` | **Adapté** : purge à chaque ouverture et à chaque contrôle | Registre en mémoire, quelques entrées |
| RBAC par route, test de matrice | `api/dependencies.py:381-410`, `tests/test_permission_matrix_from_routes.py:114-130` | **Adapté** : refus par défaut de toute route `/api/v1/` sans session ni jeton de contrôle, liste blanche explicite (`/health`, `/readiness`, ouverture de session) et test qui parcourt les routes montées | Un seul rôle ; le refus par défaut évite l'oubli d'une route, que decodair compense par un test |
| En-têtes : `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` | `api/middleware.py:13-23` | **Repris** et complétés (`Cross-Origin-Opener-Policy: same-origin`, `Cache-Control: no-store` sur les réponses JSON de l'API) ; `X-XSS-Protection` **écarté** | OWASP HTTP Headers : `X-XSS-Protection` est obsolète ; la CSP existante reste |
| HSTS | `next.config.ts:36-41` (inconditionnel), Siana (TLS seulement) | **Repris selon Siana** : production avec TLS uniquement | HSTS sur HTTP n'a pas d'effet et gênerait un retour au développement |
| Limitation de débit SlowAPI | `api/rate_limit.py:16-19` | **Écarté** | Sur 127.0.0.1 l'adresse est toujours la même ; aucune authentification par secret devinable (lien de 256 bits à usage unique) |
| Journal d'audit des événements de sécurité | `application/common/audit_service.py:16-35` | **Adapté** : JSONL sous `logs/` de l'instance (ouverture, refus, expiration, révocation, CSRF refusé) | Aucun secret ni texte de document écrit |
| Documentation OpenAPI publique | `main.py:126-127` | **Adapté** : `/api/docs` en développement, désactivé en production | Surface d'API utile au diagnostic local seulement |
| Absents de decodair : liste blanche d'hôtes, contrôle `Origin`/`Sec-Fetch-Site` | cartographie §4 | **Conservés** (déjà en place ici, D08.3) | Défense contre le rebinding DNS sur 127.0.0.1 |

## Réglages par environnement

| Réglage | `development` (défaut) | `production` |
|---|---|---|
| Transport | HTTP loopback | HTTPS loopback, certificat et clé du profil (`security.tls_cert_file`, `security.tls_key_file`) |
| Cookie de session | `rag_session`, `HttpOnly`, `SameSite=Strict`, `Path=/` | `__Host-rag_session`, mêmes attributs plus `Secure` |
| HSTS | absent | `max-age=31536000` |
| `/api/docs` | disponible | désactivé |
| Refus au démarrage | — | environnement inconnu, TLS absent ou fichiers illisibles |

## Sources

- OWASP Cheat Sheet Series, fichiers téléchargés le 30/09 à 16:48 UTC sous `.runtime/references/owasp/` : [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) (entropie ≥ 64 bits, préfixe `__Host-`, délais d'inactivité et absolu, renouvellement, déconnexion visible), [CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) (jeton synchroniseur, en-têtes personnalisés, Fetch Metadata, SameSite en défense en profondeur), [HTTP Headers](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html), [REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html), [Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).
- decodair : chemins et lignes cités dans le tableau (lecture seule, 30/09).

## Limites

Le registre en mémoire suppose un seul processus API (`app.asgi_workers: 1`, imposé par le profil). Le mode production n'est vérifié que sur ce poste, avec un certificat de test ; aucune exposition réseau n'est prévue ni couverte.
