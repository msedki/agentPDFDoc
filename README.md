# Atelier documentaire local

Poste de lecture et d'analyse de PDF qui fonctionne entièrement sur un PC Windows 11 de 16 Gio, sur CPU, sans WSL, Docker ni service distant. Les réponses du modèle local ne citent que des passages enregistrés pour la question, et chaque citation s'ouvre dans le PDF à sa version, sa page et son bloc d'origine.

**État au 30 septembre 2026 (commit `13d865f`) :** import, extraction, recherche, génération et ouverture des citations exercés sur une instance réelle ; 4 documents du corpus du poste extraits et publiés, 61 en pause jusqu'au feu vert de l'utilisateur ; accès à l'atelier par une session locale ouverte avec `.\rag.ps1 open` ; interface refondue et relue sur captures ; recherche évaluée sur ce corpus (157 blocs attendus sur 160 au top 10, [rapport](RAG_Local_Agents/reports/evaluation/corpus-reel-2026-09-30.md)) ; une réponse réelle complète en 298 s, dont 175 s avant le premier mot, loin de la cible D07 ([preuve](RAG_Local_Agents/reports/backend/2026-09-30-real-corpus-question-20260930T2029.json)) ; recette D01–D11 non close. Détail et prochaines actions dans le [plan du chantier](RAG_Local_Agents/PLAN.md).

---

## Sommaire

- [1. Vue d'ensemble](#1-vue-densemble)
- [2. Parcours utilisateur](#2-parcours-utilisateur)
- [3. Architecture](#3-architecture)
- [4. Structure du dépôt](#4-structure-du-dépôt)
- [5. Stack et versions](#5-stack-et-versions)
- [6. Données et stockage](#6-données-et-stockage)
- [7. API locale](#7-api-locale)
- [8. Confidentialité et périmètre réseau](#8-confidentialité-et-périmètre-réseau)
- [9. Prérequis du poste](#9-prérequis-du-poste)
- [10. Installation](#10-installation)
- [11. Démarrage et arrêt](#11-démarrage-et-arrêt)
- [12. Ingestion et OCR](#12-ingestion-et-ocr)
- [13. Recherche, analyse et citations](#13-recherche-analyse-et-citations)
- [14. Tests et build](#14-tests-et-build)
- [15. Qualification](#15-qualification)
- [16. Configuration](#16-configuration)
- [17. Exploitation](#17-exploitation)
- [18. Sauvegarde et restauration](#18-sauvegarde-et-restauration)
- [19. Dépannage](#19-dépannage)
- [20. Aide-mémoire](#20-aide-mémoire)
- [Contribution](#contribution)
- [Licence](#licence)

La documentation stabilisée (architecture, interface HTTP, exploitation) est indexée dans [docs/README.md](docs/README.md) ; l'historique des changements est dans [CHANGELOG.md](CHANGELOG.md).

---

## 1. Vue d'ensemble

Le poste importe des PDF natifs, scannés ou mixtes, en extrait le texte avec sa géométrie, l'indexe deux fois (plein texte SQLite FTS5 et vecteurs Qdrant) et répond aux questions avec un modèle Qwen exécuté par Ollama. Tout tourne en processus Windows natifs supervisés par un lanceur PowerShell unique, `rag.ps1`, sur l'adresse de bouclage 127.0.0.1.

| Composant | Rôle | Racine |
|---|---|---|
| Interface web | Trois panneaux (bibliothèque, lecteur PDF, analyse) ; export statique Next.js servi par l'API | [`apps/web/`](apps/web/) |
| API locale | FastAPI : bibliothèque, import, recherche hybride, questions en flux SSE, citations, travaux | [`services/api/`](services/api/) |
| Ingestion PDF | Worker isolé : préflight PDFium, routage Docling natif / structuré / OCR régional, fenêtres reprenables | [`services/ingestion/`](services/ingestion/) |
| Exploitation | Lanceur, superviseur, gouverneur de ressources, sauvegarde et restauration | [`services/runtime/`](services/runtime/), [`rag.ps1`](rag.ps1), [`bootstrap.ps1`](bootstrap.ps1) |
| Contrats | Périmètre, page, bloc, fragment, source, événements SSE, erreurs | [`packages/contracts/contracts.json`](packages/contracts/contracts.json) |
| Configuration | Profil `local16` et verrous d'artefacts et de modèles | [`config/`](config/) |
| Qualification | PDF synthétiques, jeux de questions, outils de capture et de notation | [`fixtures/`](fixtures/), [`evals/`](evals/), [`tools/qualification/`](tools/qualification/) |
| Suivi du chantier | Plan, critères de fin, décisions, journal, sources, preuves ; exigences V2.1 | [`RAG_Local_Agents/`](RAG_Local_Agents/) |

Ces invariants sont appliqués par le code ; un écart produit un refus explicite plutôt qu'un fonctionnement dégradé silencieux.

| Invariant | Comportement en cas d'écart |
|---|---|
| Services sur 127.0.0.1 uniquement | Profil refusé au lancement (« Le runtime exige loopback et CPU ») ; requête HTTP refusée si `Host` ou `Origin` n'est pas local (400 `invalid_host`, 403 `invalid_origin`) |
| Données accessibles seulement par une session ouverte depuis le poste ou par le jeton de contrôle de l'instance ([W011](RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique)) | 401 `session_required` ou `session_expired`, 403 `csrf_rejected` ; l'interface affiche la commande `.\rag.ps1 open` au lieu de l'espace de travail |
| Calcul sur CPU (`llm.num_gpu: 0`) | Profil refusé par `load_profile` et par l'API (« Le profil exige un calcul CPU. ») |
| Un seul travail lourd (génération ou ingestion) sur le poste | Verrou `.runtime/control/host-heavy.lock` : l'import attend en file, la question attend son admission |
| Réserve de 1 536 Mio de mémoire hôte | Question refusée à l'admission ou annulée en cours de génération (« Réserve hôte menacée pendant la génération ; requête annulée. ») |
| Originaux immuables | Copie gérée `originals/<sha256>.pdf` ; 409 `original_integrity_failure` si une copie existante est altérée ; `ORIGINAL_CHANGED` si le PDF change pendant l'extraction |
| Une citation n'existe que dans le registre de sa question | Identifiant inconnu remplacé par « [citation inconnue] » et avertissement `unknown_citations` |
| Aucune reprise automatique d'un import en pause | Profil refusé si `resources.scheduling.auto_resume_ingestion` ne vaut pas `false` |
| Aucun processus étranger arrêté | Port occupé : « Port … occupé ; aucun service existant ne sera arrêté. » |

---

## 2. Parcours utilisateur

1. Après `.\rag.ps1 up`, lancer `.\rag.ps1 open` : l'atelier s'ouvre dans le navigateur par défaut sur `http://127.0.0.1:8785/workspace/`, avec une session de 12 h au plus, fermée après 2 h sans activité. Une adresse tapée ou un signet sans session affiche « Session requise » et la commande à copier ; le bouton « Fermer la session » de la barre supérieure ferme la session du navigateur.
2. Importer un ou plusieurs PDF (« Importer des PDF »), ou un dossier entier (« Importer un dossier ») : les chemins relatifs forment l'arborescence de la bibliothèque, l'original est copié et haché, et le suivi des traitements affiche l'étape réellement en cours (file, extraction, indexation, pause).
3. Ouvrir un document dans le lecteur PDF.js : zoom, rotation, sommaire extrait, blocs de texte sélectionnables. L'original reste consultable avant la fin de l'indexation.
4. Choisir le périmètre de travail : toute la bibliothèque, un dossier et ses sous-dossiers, des documents sélectionnés, une section, une plage de pages ou une sélection de texte.
5. Lancer une recherche, poser une question ou comparer deux à quatre documents. Les sources retenues arrivent avant le texte de la réponse, qui s'affiche en flux.
6. Cliquer une citation `[S001]` : le lecteur ouvre la version, la page et le bloc enregistrés, surligne la région quand sa géométrie est connue et permet de revenir au passage précédent.

Parcours vérifiés dans un navigateur réel : trois panneaux sans requête externe à 1366 × 768 et 1920 × 1080, clavier et focus, liens de citation invalides refusés, écran « Session requise », lien d'ouverture refusé à sa deuxième présentation et fermeture de session, sur le build de l'interface refondue ([E2E du 30/09 à 18:30, 8 PASS](apps/web/reports/e2e-2026-09-30-r17-readonly-1830-evidence.json)) ; ancienne citation restaurée ouverte à l'identique, avant la session ([ancienne citation](apps/web/reports/e2e-2026-09-30-restored-source-newcode-1412.log)). La réponse complète du modèle suivie d'un clic de citation n'a pas encore passé sa recette (section [15](#15-qualification)). La coquille (barre supérieure, bibliothèque repliable en rail, panneaux latéraux sous 1 024 px, suivi, aide) et les textes de l'interface ont été refondus (lots R15 et R16, détail dans [apps/web/README.md](apps/web/README.md)) ; leur recette visuelle avec captures (lot R20 du [plan](RAG_Local_Agents/PLAN.md)) reste à faire.

---

## 3. Architecture

![Processus, ports et stockage du poste](docs/assets/diagrams/processus-ports.svg)

*Processus du poste et ports d'écoute : le navigateur ne parle qu'à l'API ; Qdrant, Ollama et le worker PDF sont des enfants possédés par le superviseur.*

| Service | Adresse | Rôle |
|---|---|---|
| Interface web | `http://127.0.0.1:8785/workspace/` | Poste de travail : bibliothèque, lecteur, analyse |
| API locale | `http://127.0.0.1:8785/api/v1` | Données, import, recherche, questions (SSE), citations, travaux |
| Ouverture de session | `http://127.0.0.1:8785/api/v1/session/open?link=…` | Lien à usage unique, valable 5 min, ouvert par `.\rag.ps1 open` |
| Schéma OpenAPI | `http://127.0.0.1:8785/openapi.json` | Description générée par FastAPI ; développement seulement |
| Qdrant | `http://127.0.0.1:6333` | Index vectoriel, joint par l'API seulement ; clé d'API propre à chaque démarrage |
| Ollama | `http://127.0.0.1:11434` | Serveur du modèle de langue, joint par l'API seulement ; lance `llama-server` sur un port local qu'il choisit |
| Ollama temporaire | `http://127.0.0.1:11444` | Pendant `rag.ps1 pull-model` uniquement |
| Qdrant temporaire | `http://127.0.0.1:6343` | Pendant `rag.ps1 restore` uniquement |
| Profil restauré | API 8795, Qdrant 6343, Ollama 11445 | Instance démarrée depuis `restored-profile.yaml` |

| Couche | Responsabilité | Source |
|---|---|---|
| Lanceur | Valide le profil, démarre le superviseur sans fenêtre, attend l'état `running`, ouvre l'atelier avec un lien de session (`open`), arrête sur demande | [`rag.ps1`](rag.ps1), [`services/runtime/cli.py`](services/runtime/cli.py), [`supervisor.py`](services/runtime/supervisor.py) |
| Superviseur | Verrous de racine et de stockage, contrôle des ports et des binaires, lancement de Qdrant, Ollama et de l'API dans un Job Object Windows, trace `resources.jsonl` | [`services/runtime/supervisor.py`](services/runtime/supervisor.py), [`windows_process.py`](services/runtime/windows_process.py) |
| API | Frontière locale (Host, Origin, CSP), session et jeton CSRF, routes `/api/v1`, SSE, file de travaux, réconciliation vectorielle | [`services/api/main.py`](services/api/main.py), [`security.py`](services/api/security.py) |
| Gouverneur | Admission mémoire, verrou lourd du poste, pause coopérative de l'ingestion, surveillance de la réserve pendant la génération | [`services/runtime/resources.py`](services/runtime/resources.py) |
| Ingestion | Worker séparé : préflight, fenêtres de pages, routage Docling et Tesseract, assemblage | [`services/ingestion/`](services/ingestion/) |
| Recherche et réponse | BM25 FTS5, E5 ONNX + Qdrant, fusion RRF, sélection contrainte, contexte, appel Ollama, validation des citations | [`retrieval.py`](services/api/retrieval.py), [`context.py`](services/api/context.py), [`query.py`](services/api/query.py) |
| Interface | Export statique Next.js, React, PDF.js, état partagé du périmètre, écran de session | [`apps/web/src/`](apps/web/src/) |

Description complète, flux, interfaces internes, sécurité et points d'observation : [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md). L'exigence d'origine reste la [spécification V2.1](RAG_Local_Agents/SPEC_ARCHITECTURE.md), dont les écarts constatés sont listés dans ce document.

---

## 4. Structure du dépôt

| Chemin | Rôle | Versionné ? |
|---|---|---|
| `apps/web/` | Interface Next.js, tests unitaires `node:test`, scénarios Playwright, preuves d'interface (`reports/`) | Oui, sauf `node_modules/`, `.next/`, `out/`, `test-results/`, `public/pdfjs/`, `playwright/.auth/` (cookies de session des E2E) |
| `services/api/` | API FastAPI, recherche, contexte, travaux, migrations SQLite (`migrations/001` à `003`) | Oui |
| `services/ingestion/` | Préflight, pipeline de fenêtres, adaptateur Docling, OCR régional, worker | Oui |
| `services/runtime/` | CLI d'exploitation, superviseur, gouverneur, sauvegarde, provisionnement, dérivation du modèle texte | Oui |
| `packages/contracts/` | Contrat JSON partagé API, interface et ingestion | Oui |
| `config/` | Profil `local16.yaml`, verrous `artifacts.lock.json`, `models.lock.json`, `embedding-comparison.lock.json` | Oui |
| `tests/unit/`, `tests/integration/` | Tests pytest ; marqueurs `integration`, `slow`, `acceptance` pour les essais natifs et lourds | Oui |
| `tools/qualification/` | Génération des fixtures, capture des annotations, réponses, notation, performance | Oui |
| `tools/corpus/` | Import d'un dossier de PDF dans une instance démarrée, avec son arborescence | Oui |
| `tools/docs/` | Générateur des schémas SVG et contrôle de la documentation | Oui |
| `fixtures/qualification-v2.1/` | PDF synthétiques (texte, scans, géométrie, erreurs, fichiers hostiles) | Oui |
| `evals/qualification-v2.1/` | Jeux de questions développement et final gelé, rapports de préparation | Oui |
| `docs/` | Documentation stabilisée et schémas générés | Oui |
| `RAG_Local_Agents/` | Dossier vivant du chantier et référentiel d'exigences V2.1 | Oui |
| `.agents/skills/` | Compétences projet et références de sécurité utilisées par les agents | Oui |
| `rag.ps1`, `bootstrap.ps1` | Entrées PowerShell du poste | Oui |
| `pyproject.toml`, `uv.lock` | Dépendances Python verrouillées | Oui |
| `RAG_Local_V2_1_Complet.zip`, `SHA256SUMS_COMPLET.txt` | Archive du brief V2.1 et ses empreintes | Oui |
| `.runtime/` | Python géré, binaires, modèles, caches, données, essais de recette | Non |
| `.venv/` | Environnement Python du projet | Non |
| `PDF/` | Corpus métier privé | Non |
| `backups/` | Emplacement par défaut des sauvegardes | Non |

Les exclusions sont définies par [`.gitignore`](.gitignore) ; [`.gitattributes`](.gitattributes) désactive toute conversion de fin de ligne pour que les empreintes SHA-256 restent vérifiables après un clone (décision [W005](RAG_Local_Agents/DECISIONS.md#w005-dépôt-git-et-publication-vers-le-remote-privé)).

---

## 5. Stack et versions

Chaque version est lue dans le fichier cité ; un changement de version passe par ce fichier et par une décision tracée.

| Couche | Technologie | Version | Source d'autorité |
|---|---|---|---|
| Système | Windows 11 x86-64, PowerShell | 5.1 | [W001](RAG_Local_Agents/DECISIONS.md#w001-plateforme-windows-native), [`EXPLOITATION_WINDOWS.md`](RAG_Local_Agents/EXPLOITATION_WINDOWS.md) |
| Outil Python | uv | 0.12.21 | [`bootstrap.ps1`](bootstrap.ps1) (archive et SHA-256) |
| Interpréteur | CPython géré dans `.runtime/python` | 3.12.14 | [`bootstrap.ps1`](bootstrap.ps1) ; plage `>=3.12,<3.13` dans [`pyproject.toml`](pyproject.toml) |
| API | FastAPI, uvicorn, Pydantic | 0.142.1, 0.54.0, 2.13.5 | [`pyproject.toml`](pyproject.toml), [`uv.lock`](uv.lock) |
| Ingestion | Docling, pypdfium2 | 2.131.0, 5.13.0 | [`pyproject.toml`](pyproject.toml) |
| Modèles Docling | Heron (mise en page), TableFormer accurate | révisions `8f39ad3c`, `fc0f2d45` | [`config/artifacts.lock.json`](config/artifacts.lock.json) |
| OCR | Tesseract CLI, données `tessdata_fast` fra, eng, osd | 5.4.0, commit `87416418` | [`config/local16.yaml`](config/local16.yaml) (`pdf.tesseract_cmd`), [`config/artifacts.lock.json`](config/artifacts.lock.json) |
| Embeddings | multilingual-e5-small ONNX int8, onnxruntime | révision `614241f6`, 1.30.0 | [`config/artifacts.lock.json`](config/artifacts.lock.json), [`pyproject.toml`](pyproject.toml) |
| Index vectoriel | Qdrant serveur Windows | 1.19.1 | [`config/artifacts.lock.json`](config/artifacts.lock.json) |
| Index plein texte | SQLite FTS5 (`unicode61 remove_diacritics 2`) | Bibliothèque embarquée par CPython, lue dans `GET /api/v1/diagnostics` (champ `sqlite`) | [`config/local16.yaml`](config/local16.yaml) (`sqlite`) |
| Serveur de modèle | Ollama Windows | 0.35.0 | [`config/artifacts.lock.json`](config/artifacts.lock.json), contrôlé par `/api/version` au lancement |
| Modèle de langue | Qwen3.5 4B Q4_K_M dérivé texte seul (`qwen3.5:4b-text`) | manifeste `de8024db…` | [`config/models.lock.json`](config/models.lock.json), [W006](RAG_Local_Agents/DECISIONS.md#w006-modèle-qwen-texte-seul-dérivé-localement-sans-encodeur-vision) |
| Build web | Node.js, pnpm | 22.17.0, 10.34.1 | [`EXPLOITATION_WINDOWS.md`](RAG_Local_Agents/EXPLOITATION_WINDOWS.md) ; `engines` de [`apps/web/package.json`](apps/web/package.json) |
| Interface | Next.js, React, pdfjs-dist, TanStack Query, Zustand, Tailwind CSS | 16.3.7, 19.3.0, 6.3.289, 5.104.0, 5.0.15, 4.3.3 | [`apps/web/package.json`](apps/web/package.json), [`pnpm-lock.yaml`](apps/web/pnpm-lock.yaml) |
| Tests | pytest, TypeScript, Playwright | 9.1.1, 5.9.3, 1.63.0 | [`pyproject.toml`](pyproject.toml), [`apps/web/package.json`](apps/web/package.json) |

Version du projet : `0.1.0`, identique dans [`pyproject.toml`](pyproject.toml) et [`apps/web/package.json`](apps/web/package.json) ; aucune version n'a été publiée.

---

## 6. Données et stockage

L'emplacement de données actif est `app.data_dir` du profil (`.runtime/data` pour `local16`), surchargeable par la variable `RAG_DATA_DIR`.

| Stockage | Contenu | Emplacement | Reproductible ? | Sauvegarde ? |
|---|---|---|---|---|
| Base SQLite (WAL, FTS5) | Dossiers, documents, versions, révisions d'extraction, générations d'index, pages, blocs, fragments, travaux, questions, événements SSE, citations, cache d'embeddings | `<data_dir>/app.sqlite3` | Non : état métier | Oui, par l'API de sauvegarde SQLite |
| Originaux | Copie gérée de chaque PDF importé, nommée par son SHA-256 | `<data_dir>/originals/` | Non | Oui |
| Extractions | Préflight, fenêtres `window-*.json`, sorties Docling, `extraction.json` | `<data_dir>/extractions/<version>/<travail>/` | Oui, par réextraction (coût OCR) | Oui |
| Index vectoriel | Collection `pdf_chunks_e5small_v1`, vecteurs sur disque, graphe HNSW en mémoire | `<data_dir>/qdrant/` ou `qdrant.storage_dir` | Oui, par réindexation | Oui, par snapshot Qdrant |
| Contrôle et journaux | État du superviseur, verrous, jeton de contrôle et clé Qdrant de l'instance (supprimés à l'arrêt), journaux par instance, journal des événements de session | `<data_dir>/control/`, `<data_dir>/logs/<instance>/`, `<data_dir>/logs/security-audit.jsonl` | Sans objet | Non |
| Modèles et binaires | Ollama, E5, tokenizer Qwen, Docling, tessdata ; Qdrant, Ollama, Tesseract | `.runtime/models/`, `.runtime/bin/` | Oui, par `rag.ps1 provision` (réseau) | Non ; manifestes seulement |
| Manifestes d'empreintes | Artefacts provisionnés, modèle source et modèle texte | `.runtime/manifests/` | Oui, par `provision` | Oui (`runtime-manifests/`) |
| Environnement Python | Python géré, cache uv, `.venv` | `.runtime/python/`, `.runtime/cache/`, `.venv/` | Oui, par `bootstrap.ps1` | Non |
| Interface compilée | Export statique | `apps/web/out/` | Oui, par `pnpm build` | Non |
| Preuves de recette | Rapports JSON, journaux, captures retenues | `RAG_Local_Agents/reports/`, `apps/web/reports/` | Non | Git |

Les sessions de navigateur ne sont pas stockées : leur registre vit dans la mémoire de l'API et disparaît à son arrêt. L'arrêt ne supprime aucune donnée. Un stockage Qdrant relocalisé par une restauration (`.runtime/q/<id8>`) appartient à sa racine restaurée : ne le déplacer ni le purger seul.

---

## 7. API locale

L'API sert l'interface et toutes les données sur `http://127.0.0.1:8785`, préfixe `/api/v1` (HTTPS à la même adresse si le profil est en production). Elle expose la santé et la disponibilité, la session, la bibliothèque, l'import multi-fichiers, la lecture des versions (PDF, sommaire, blocs), la recherche, les questions avec leur flux d'événements SSE reprenable, les citations, les travaux d'ingestion et six routes d'administration. Hors santé, disponibilité, ouverture et fermeture de session, chaque route exige la session du navigateur (avec un jeton CSRF pour les modifications) ou le jeton de contrôle de l'instance, régénéré à chaque lancement (fichier `control/admin-token` de la racine de données, supprimé à l'arrêt) ; les routes d'administration n'acceptent que ce jeton.

Toute erreur a la forme `{code, message, details, request_id}`. La référence complète des routes, des codes d'erreur et des événements est dans [docs/interfaces/API.md](docs/interfaces/API.md) ; le contrat partagé est [`packages/contracts/contracts.json`](packages/contracts/contracts.json).

---

## 8. Confidentialité et périmètre réseau

- **Réseau réservé à la préparation.** Seuls `bootstrap.ps1` (uv, Python, dépendances), `rag.ps1 provision` (artefacts verrouillés, dépendances npm, modèle) et `rag.ps1 pull-model` accèdent à Internet ; l'option `-Offline` réutilise les caches. `up`, `open`, `status`, `logs`, `down`, `doctor`, `backup`, `verify` et `restore` ne téléchargent rien.
- **Services en boucle locale.** API, Qdrant et Ollama écoutent sur 127.0.0.1 ; les processus du projet n'ont été observés qu'en écoute locale ([relevé du 30/09](RAG_Local_Agents/reports/listening-sockets-20260930T0930.json)). L'API rejette un `Host` ou une `Origin` étrangers et les requêtes intersites et envoie une politique CSP `default-src 'self'` ; Ollama refuse aussi un `Host` ou une `Origin` étrangers ([essai sur serveur réel](RAG_Local_Agents/reports/host-origin-live-20260930T0930.json)).
- **Session locale.** Pas de compte : `.\rag.ps1 open` obtient avec le jeton de contrôle un lien à usage unique de 5 min, que le navigateur échange contre un cookie `HttpOnly` et `SameSite=Strict` ; registre en mémoire de l'API, inactivité 120 min, durée absolue 12 h, jeton CSRF sur les modifications, relectures périodiques de l'atelier sans effet sur l'inactivité, journal `security-audit.jsonl` sans secret ([W011](RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique), [gardes réelles 19/19](RAG_Local_Agents/reports/http-guards-live-20260930T1829.json), [API.md, section 2](docs/interfaces/API.md#2-session-et-autorisation)).
- **Qdrant sous clé d'API.** Le superviseur tire une clé à chaque démarrage et ne la transmet qu'à Qdrant et à l'API ; sans elle, Qdrant répond 401 hors de ses sondes de santé, y compris avec un `Host` étranger ([W010](RAG_Local_Agents/DECISIONS.md#w010-clé-dapi-qdrant-propre-à-chaque-vie-du-serveur), [gardes HTTP réelles, 15/15](RAG_Local_Agents/reports/http-guards-live-20260930T1636.json)).
- **Télémétrie coupée dans les processus enfants.** Variables `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `HF_HUB_DISABLE_TELEMETRY`, `OLLAMA_NO_CLOUD`, `NEXT_TELEMETRY_DISABLED` ; Qdrant lancé avec `--disable-telemetry` ([`supervisor.py`](services/runtime/supervisor.py), fonction `environment`).
- **Corpus hors Git.** `PDF/`, `.runtime/`, les bases, snapshots et secrets sont exclus ; les rapports versionnés contiennent le nom d'hôte, le nom d'utilisateur Windows et les empreintes des documents, jamais leur texte ([W005](RAG_Local_Agents/DECISIONS.md#w005-dépôt-git-et-publication-vers-le-remote-privé)).

Limites connues, non corrigées à ce jour :

| Limite | Preuve | Suite prévue |
|---|---|---|
| Une instance lancée avant l'introduction de la clé Qdrant (commit `e0be4ac`) reste sans clé | [W010](RAG_Local_Agents/DECISIONS.md#w010-clé-dapi-qdrant-propre-à-chaque-vie-du-serveur), conséquences | `.\rag.ps1 down` puis `.\rag.ps1 up` |
| La clé Qdrant circule en clair sur la boucle locale (pas de TLS) | [W010](RAG_Local_Agents/DECISIONS.md#w010-clé-dapi-qdrant-propre-à-chaque-vie-du-serveur) | Choix documenté : trafic limité à 127.0.0.1 |
| En développement, cookie de session, jeton CSRF et jeton de contrôle circulent en clair sur la boucle locale (HTTP) | [W011](RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique) | Choix documenté ; le profil `production` sert HTTPS, vérifié seulement par un test d'intégration avec certificat de test |
| Blocage des sorties réseau au niveau du système non exécuté (D08.1) | [plan](RAG_Local_Agents/PLAN.md), points à trancher ; [journal du 30/09](RAG_Local_Agents/journal/2026-09-30.md), vers 18:17 | Une règle de pare-feu exigerait des droits administrateur, exclus depuis le 30/09 ; seule une coupure physique du réseau pendant la recette reste possible |
| `GET /api/docs`, en développement seulement, sert l'interface Swagger de FastAPI, dont les scripts viennent d'un CDN que la CSP bloque | `docs_url` dans [`services/api/main.py`](services/api/main.py) | Page non examinée au rendu ; `GET /openapi.json` reste local ; les deux sont désactivés en production |

---

## 9. Prérequis du poste

| Élément | Exigence | Contrôle |
|---|---|---|
| Système | Windows 11 x86-64, PowerShell 5.1, compte utilisateur standard (aucune étape ne demande de droits administrateur), exécution des scripts locaux autorisée (politique `RemoteSigned` observée pour l'utilisateur) ; les scripts du projet ne modifient ni la politique d'exécution ni le `PATH` | `$PSVersionTable`, `Get-ExecutionPolicy -List` |
| Mémoire | 16 Gio physiques ; une question exige 4 992 Mio disponibles à froid, un import 3 840 Mio (estimation + réserve de 1 536 Mio) | `.\rag.ps1 doctor`, rubrique `cold_admission` |
| Disque | Réserve de 2 Gio exigée avant téléchargement et avant sauvegarde ; la dérivation du modèle texte exige deux fois la taille du modèle source plus 2 Gio | messages de refus de [`artifacts.py`](services/runtime/artifacts.py), [`backup.py`](services/runtime/backup.py), [`cli.py`](services/runtime/cli.py) |
| Node.js et pnpm | 22.17.0 et 10.34.1 dans le `PATH`, pour `provision` et le build | `.\rag.ps1 doctor`, rubrique `node_tools` |
| Tesseract | Tesseract 5.4.0 Windows déjà installé, de préférence dans le profil de l'utilisateur (`%LOCALAPPDATA%\Programs\Tesseract-OCR`, emplacement du poste de référence) : une installation sous `%PROGRAMFILES%` demanderait des droits administrateur ; `provision` en copie l'exécutable, les DLL et les licences dans `.runtime/bin/` avec leurs empreintes | message « Prérequis Tesseract5.4.0 Windows absent » ([`provisioning.py`](services/runtime/provisioning.py)) |
| Ports | Libres sur 127.0.0.1 : 8785 (API), 6333 (Qdrant), 11434 (Ollama) ; 11444 pendant `pull-model` ; 6343 pendant `restore` ; 8795, 6343, 11445 pour un profil restauré | `.\rag.ps1 doctor`, rubrique `ports` |
| Internet | Uniquement pour `bootstrap.ps1`, `provision` et `pull-model` sans `-Offline` | — |

La provenance de l'installateur Tesseract n'est pas authentifiée indépendamment ; seule la copie locale est hachée.

---

## 10. Installation

Depuis la racine du dépôt, dans PowerShell 5.1 :

```powershell
.\bootstrap.ps1
.\rag.ps1 provision
.\rag.ps1 doctor
```

`bootstrap.ps1` télécharge uv 0.12.21 (SHA-256 vérifié), installe CPython 3.12.14 dans `.runtime/python` et synchronise `.venv` depuis `uv.lock`. `provision` synchronise de nouveau les dépendances Python, installe les dépendances web (`pnpm install --frozen-lockfile`), télécharge et vérifie les artefacts verrouillés (Qdrant, Ollama, E5, tokenizer Qwen, tessdata, modèles Docling), copie Tesseract, construit l'interface, puis tire le modèle source et dérive le modèle texte seul ([`cli.py`](services/runtime/cli.py), fonction `provision`).

| Variante | Commande |
|---|---|
| Hors ligne, depuis des caches déjà remplis | `.\bootstrap.ps1 -Offline` puis `.\rag.ps1 provision -Offline` |
| Sans le modèle de langue | `.\rag.ps1 provision -SkipModel` |
| Un seul groupe d'artefacts (`qdrant`, `ollama`, `e5`, `qwen-tokenizer`, `tessdata`, `docling`) | `.\rag.ps1 provision -Only qdrant` |
| Modèle seul, idempotent | `.\rag.ps1 pull-model` ou `.\rag.ps1 pull-model -Offline` |

Le provisionnement complet d'une racine neuve sans intervention (critère D01) n'a pas encore été rejoué : lot R10 du [plan](RAG_Local_Agents/PLAN.md).

---

## 11. Démarrage et arrêt

```powershell
.\rag.ps1 up
.\rag.ps1 open
.\rag.ps1 status
.\rag.ps1 down
```

`up` vérifie le profil, prend les verrous de la racine et du stockage Qdrant, contrôle ports et binaires, lance Qdrant, Ollama puis l'API et rend la main quand l'API répond sur `/api/v1/health` ; il n'ouvre pas de navigateur et ne charge pas le modèle de langue. Un second `up` avec le même profil renvoie l'instance en cours. `open` demande à l'instance démarrée un lien d'ouverture à usage unique et l'ouvre dans le navigateur par défaut, sans l'afficher ; il se relance à chaque fois qu'une session a expiré ou été fermée. `down` demande un arrêt coopératif (l'API a 180 s pour se fermer, Qdrant et Ollama 30 s chacun), met le travail d'extraction actif en pause à son checkpoint, ferme toutes les sessions et ne touche qu'aux processus possédés.

![Séquence de rag.ps1 up puis open et refus bloquants](docs/assets/diagrams/sequence-up.svg)

*Ordre des contrôles de `rag.ps1 up`, demande du lien d'ouverture par `rag.ps1 open` et message de chaque refus bloquant.*

Procédure détaillée, sessions, supervision et reprise : [docs/exploitation/EXPLOITATION.md](docs/exploitation/EXPLOITATION.md).

---

## 12. Ingestion et OCR

Un import copie l'original, crée une version et met un travail en file. Un dossier entier s'importe aussi depuis PowerShell, arborescence comprise, par [`tools/corpus/import_folder.py`](tools/corpus/import_folder.py) ([exploitation, section 6](docs/exploitation/EXPLOITATION.md#6-conduire-les-travaux-dingestion)). Le travail s'exécute dans un sous-processus Python dédié, un seul à la fois et jamais pendant une génération, par fenêtres de quatre pages qui servent de points de reprise. Chaque page est routée vers l'une de quatre voies : page blanche (sans conversion), texte natif simple, conversion structurée par les modèles de mise en page et de tableaux (tableaux, colonnes, typographie variée) ou OCR régional Tesseract (régions image non couvertes, couche texte dégradée) ; les trois dernières passent par Docling. Une page native dont la qualité mesurée est insuffisante est reconvertie par la voie structurée.

![Chaîne d'ingestion](docs/assets/diagrams/ingestion.svg)

*Étapes d'un travail d'ingestion, voies de routage d'une page et règles de révision.*

- Un mot OCR sous 0,8 de confiance devient une région non résolue. Une extraction dont seules des figures ne sont pas interprétées est publiée d'office avec ses avertissements ([W012](RAG_Local_Agents/DECISIONS.md#w012-figures-non-interprétées--limite-déclarée-publication-automatique)) ; si du texte manque (pages non converties, zones non lues, page en erreur qui avait du texte), le document reste « Extraction partielle à publier » jusqu'à une publication explicite.
- Dans la bibliothèque, un document sans génération publiée affiche l'état de son dernier traitement : en attente, en cours, en pause, annulé, en erreur ou extraction partielle à publier ; le Suivi reprend en une fois toutes les indexations en pause.
- La révision d'extraction dépend de la version, du SHA-256 du PDF et de l'empreinte du pipeline : une ancienne citation garde sa révision.
- Le backend PDF est choisi par `pdf.pdf_backend` : `pypdfium2` dans le profil selon la décision [W009](RAG_Local_Agents/DECISIONS.md#w009-backend-pdf-nominal-pypdfium2-avec-repère-cropbox-corrigé), validée sur les fixtures synthétiques et non sur le corpus métier ; `docling_parse` reste sélectionnable.

Limites de taille du profil : 200 Mio par fichier, 2 000 pages, 8 millions de pixels par page rendue et par région OCR. Détail des routes et des états : [architecture, section Ingestion](docs/architecture/ARCHITECTURE.md#4-ingestion-des-pdf).

---

## 13. Recherche, analyse et citations

La recherche combine le classement BM25 de SQLite FTS5 (les identifiants techniques exacts passent en premier) et la recherche dense E5 dans Qdrant, toutes deux filtrées par le périmètre avant le classement, puis fusionne les listes par RRF (k = 60). La sélection finale réserve une preuve à chaque identifiant cité dans la question, écarte les doublons et garde au plus 6 fragments (8 en comparaison ou pour plusieurs identifiants). Le contexte du modèle respecte un budget de preuves par mode : 1 536 jetons pour une question factuelle, 2 560 pour une question ordinaire, 5 120 pour une analyse ou une comparaison.

![Séquence d'une question](docs/assets/diagrams/sequence-question.svg)

*Échanges d'une question, de la recherche hybride à l'ouverture d'une citation.*

- Sans source retenue, l'API répond que les preuves du périmètre ne suffisent pas, sans appeler le modèle.
- Avant la génération, le gouverneur exige 3 456 + 1 536 = 4 992 Mio disponibles à froid, remesure toutes les 2 s pendant 120 s au plus (événement `waiting_for_resources`) puis admet ou refuse ([W007](RAG_Local_Agents/DECISIONS.md#w007-estimations-dadmission-recalibrées-sur-le-modèle-texte), [W008](RAG_Local_Agents/DECISIONS.md#w008-attente-bornée-à-ladmission-de-génération)).
- Pendant la génération, la réserve de 1 536 Mio est surveillée toutes les 0,5 s ; si elle est menacée, la question est annulée.
- La réponse ne garde que les identifiants `[S001]`… présents dans le registre de la question ; un clic relit ce registre avant d'ouvrir le document.

---

## 14. Tests et build

Avant toute commande lourde, vérifier la mémoire disponible ; ne pas lancer un build, un OCR ou une génération en même temps qu'un autre traitement lourd.

```powershell
# Tests Python sans services natifs ni travail lourd
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider -m "not integration and not slow and not acceptance"

# Contrôle de la documentation et des schémas
.\.venv\Scripts\python.exe tools/docs/check_docs.py
.\.venv\Scripts\python.exe tools/docs/diagrams.py --check
.\.venv\Scripts\python.exe -m pytest tests/unit/test_docs_space.py -q -p no:cacheprovider

# Interface : typage et tests unitaires (depuis apps/web)
$env:COREPACK_ENABLE_NETWORK = '0'
pnpm typecheck
pnpm test:unit
```

| Contrôle | Dernier résultat conservé | Limite |
|---|---|---|
| Suite pytest entière (unitaires et toute l'intégration : session, HTTPS réel, OCR et rendu réels) | 480 tests le 30/09 de 21:46 à 22:02 UTC sur le contenu du commit `13d865f` avant ses deux corrections de tests : 477 PASS, 3 échecs analysés ([junit](RAG_Local_Agents/reports/backend/2026-09-30-r19-r21-full.xml)) ; reprise des fichiers corrigés : 7 PASS, 2 XFAIL ([junit](RAG_Local_Agents/reports/backend/2026-09-30-r19-r21-rerun.xml)) | Les 2 XFAIL reproduisent le défaut tiers W-PDF01 de `docling_parse` avec Torch, que la voie nominale n'emploie plus ([W009](RAG_Local_Agents/DECISIONS.md#w009-backend-pdf-nominal-pypdfium2-avec-repère-cropbox-corrigé)) |
| Build de l'interface | Exit 0, 278 fichiers exportés, le 01/10 de 03:02 à 03:04 UTC sur le contenu du commit `49a2a1a` ([journal](apps/web/reports/build-2026-10-01-contrastes-legende.log)) ; dernier build surveillé avec manifeste : 30/09 ([journal](apps/web/reports/build-2026-09-30-r15-r17-integrated.log), [manifeste](apps/web/reports/export-manifest-2026-09-30-r15-r17-integrated.json)) | Mesures ponctuelles de mémoire, pas un pic continu |
| Playwright | Lecture seule et recette visuelle : 11 PASS le 01/10 à 03:04 sur l'instance principale, recette visuelle 4/4 à 03:07 ([preuves](apps/web/reports/e2e-2026-10-01-contrastes-legende-0304-evidence.json), [captures](apps/web/reports/visual-qa-20261001T0307/)) ; question réelle et clic sur la citation : PASS à 04:46 et 04:57 ([preuves](apps/web/reports/e2e-2026-10-01-r2-generation-0446/evidence.json)) ; scénarios d'import sur instance isolée (`tools/qualification/e2e_instance.py`) : géométrie 4/4, parcours d'import 5/5 ([géométrie](apps/web/reports/e2e-2026-10-01-import-isole-geometrie-evidence.json), [parcours](apps/web/reports/e2e-2026-10-01-import-isole-parcours-evidence.json)) | Cycle de vie (versions, réimport, réindexation, erreurs de fichier) non rejoué |

Le build surveillé écrit ses preuves dans `apps/web/reports/` : `.\.venv\Scripts\python.exe apps/web/scripts/build-monitored.py --tag <etiquette-neuve>` ; il attend Node sous `D:\node\node-v22.17.0-win-x64`. Les scénarios Playwright exigent une cible isolée et des autorisations explicites par variable (`RAG_E2E_IMPORT_ALLOWED`, `RAG_E2E_GENERATION_ALLOWED`, `RAG_E2E_READONLY_ALLOWED`) : voir [apps/web/README.md](apps/web/README.md). Leur préparation ouvre une session avec le jeton de contrôle de l'instance visée, lu dans `.runtime/data/control/admin-token` ou dans le fichier désigné par `RAG_E2E_CONTROL_TOKEN_FILE` ([global-setup.ts](apps/web/tests/global-setup.ts)).

---

## 15. Qualification

Les critères de fin sont définis dans [DEFINITION_OF_DONE.md](RAG_Local_Agents/DEFINITION_OF_DONE.md) (D01 à D11) et mesurés selon [QUALIFICATION.md](RAG_Local_Agents/QUALIFICATION.md). Un critère n'est `PASS` qu'avec une preuve reproductible liée au commit, au profil, au corpus et à la machine.

Le jeu synthétique comprend 32 PDF et 200 questions : 100 de développement et 100 de test final, gelé par empreinte et réservé à la recette finale ([evals/qualification-v2.1](evals/qualification-v2.1/README.md), [outils](tools/qualification/README.md)).

Sur le corpus réel du poste, `tools/qualification/corpus_eval.py` mesure la recherche sans appel au modèle, selon le protocole [W013](RAG_Local_Agents/DECISIONS.md#w013-protocole-dévaluation-sur-le-corpus-réel-sans-juge-et-sans-fuite-du-corpus) : le jeu de questions, qui contient du texte des documents, reste sous `.runtime/evals/` ; seuls les agrégats sont versionnés ([résultats et analyse](RAG_Local_Agents/reports/evaluation/corpus-reel-2026-09-30.md)).

```powershell
.\.venv\Scripts\python.exe tools/qualification/corpus_eval.py build --output .runtime\evals\corpus-reel\<horodatage>\dataset.json
.\.venv\Scripts\python.exe tools/qualification/corpus_eval.py run --dataset .runtime\evals\corpus-reel\<horodatage>\dataset.json --report RAG_Local_Agents\reports\evaluation\<nom-neuf>.json
```

L'instance doit être démarrée et sans extraction en cours (`409 ingestion_active` sinon).

Blocages actuels, détaillés dans le [plan](RAG_Local_Agents/PLAN.md) :

- génération : admise ou refusée selon la mémoire laissée par les autres applications du poste ; refus à 14:05 après 120 s d'attente à 4 709 Mio disponibles pour 4 992 requis ([preuve](RAG_Local_Agents/reports/backend/2026-09-30-restored-question-w008-20260930T1405.json)) ; admission après 67 s d'attente à 20:29, réponse complète dont les 6 citations renvoient au registre de la question ([preuve](RAG_Local_Agents/reports/backend/2026-09-30-real-corpus-question-20260930T2029.json)) ;
- D08.1 : pas de blocage réseau système sans droits administrateur, exclus depuis le 30/09 ; seule une coupure physique du réseau pendant la recette reste possible ;
- qualification métier : aucun jeu de questions annotées sur les PDF métier ;
- D07 : le préremplissage mesuré (environ 8,6 jetons/s) rend très improbable la cible de 45 s pour 3 000 jetons ; le seuil ne sera pas abaissé sans décision.

---

## 16. Configuration

Le profil actif est [`config/local16.yaml`](config/local16.yaml) (schéma version 2) ; `rag.ps1` en accepte un autre par `-Profile <chemin>`. Sa copie documentaire `RAG_Local_Agents/config/local16.yaml` doit rester identique octet pour octet ; l'explication de chaque paramètre est dans [CONFIGURATION.md](RAG_Local_Agents/CONFIGURATION.md).

| Section | Contenu principal |
|---|---|
| `app` | Adresse et port de l'API, racine des données |
| `llm` | Modèle et modèle source, quantification, contexte 8 192 jetons, sorties par mode, CPU, cache de prompt |
| `embedding` | E5 ONNX int8, préfixes `query:` et `passage:`, 384 dimensions |
| `pdf` | Routes, OCR Tesseract, langues, limites de taille et de rendu, backend PDF, seuil de confiance |
| `chunking`, `retrieval` | Taille des fragments, top-k, RRF, budgets de contexte |
| `qdrant`, `sqlite` | URL et collection, WAL, tokenizer FTS5 |
| `resources` | Réserve hôte, estimations d'admission, attente de génération, ordonnancement |
| `security` | Environnement `development` ou `production`, inactivité et durée maximale d'une session, validité du lien d'ouverture, certificat et clé TLS de production ([W011](RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique)) |
| `ui` | Budgets de rendu PDF, périmètre par défaut |
| `evaluation_targets` | Seuils de recette (non modifiables sans décision) |

Variables d'environnement lues par le code : `RAG_PROFILE` (profil de l'API), `RAG_DATA_DIR` (racine des données), `RAG_DB_PATH` (base SQLite, tests) ; `RAG_CONTROL_TOKEN`, `RAG_QDRANT_API_KEY` et `RAG_SHUTDOWN_MARKER`, posées par le superviseur pour l'API ; `RAG_CONTROL_TOKEN` aussi lue par les outils de qualification ; `RAG_E2E_CONTROL_TOKEN_FILE` pour les scénarios Playwright. Un profil modifié ne s'applique qu'après `down` puis `up` ; `doctor` signale `restart_required` tant que l'instance tourne sur l'ancien profil.

---

## 17. Exploitation

| Commande | Effet | Ce qu'elle ne prouve pas |
|---|---|---|
| `.\rag.ps1 doctor` | Chemins, versions, verrou des modèles, fichiers OCR, ports, marge d'admission, santé des services ; aucun effet destructif | Une réponse complète (`qualification: NOT_RUN`) |
| `.\rag.ps1 open` | Lien d'ouverture de session à usage unique (5 min) ouvert dans le navigateur par défaut, jamais affiché | Que l'atelier s'affiche : l'écran de session le dit si le lien a été refusé |
| `.\rag.ps1 status` | État enregistré par le superviseur et validité des identités de processus ; `stale` si le superviseur a disparu | La disponibilité des index ou du modèle |
| `.\rag.ps1 logs` | Chemins des journaux de Qdrant, Ollama et de l'API de l'instance | — |
| `-Report <fichier.json>` | Écrit le résultat JSON de n'importe quelle commande ; un fichier existant est remplacé, choisir un nom neuf pour garder une preuve | — |

Procédures complètes, supervision des ressources et reprise d'un travail : [docs/exploitation/EXPLOITATION.md](docs/exploitation/EXPLOITATION.md). Le contrat d'exploitation d'origine reste [EXPLOITATION_WINDOWS.md](RAG_Local_Agents/EXPLOITATION_WINDOWS.md).

---

## 18. Sauvegarde et restauration

```powershell
.\rag.ps1 backup -Path D:\sauvegardes\rag-20260930
.\rag.ps1 verify -Path D:\sauvegardes\rag-20260930
.\rag.ps1 restore -Path D:\sauvegardes\rag-20260930 -Target D:\restaurations\rag-20260930
.\rag.ps1 up -Profile D:\restaurations\rag-20260930\restored-profile.yaml
```

La sauvegarde exige une instance démarrée, suspend les mutations, copie la base SQLite par son API de sauvegarde, les originaux, les extractions, les manifestes et la configuration, télécharge un snapshot Qdrant par collection, puis relance les mutations. La restauration refuse toute racine existante, vérifie chaque copie avant de réécrire les chemins, restaure les snapshots dans un Qdrant temporaire sur le port 6343 et produit un profil distinct (API 8795, Qdrant 6343, Ollama 11445).

Procédure, contrôles et retour arrière : [docs/exploitation/SAUVEGARDE-RESTAURATION.md](docs/exploitation/SAUVEGARDE-RESTAURATION.md).

---

## 19. Dépannage

Les messages cités sont ceux du code ; la liste complète est dans [docs/exploitation/DEPANNAGE.md](docs/exploitation/DEPANNAGE.md).

| Symptôme | Cause | Commande |
|---|---|---|
| « Environnement isolé absent. Exécuter bootstrap.ps1… » | `.venv` absent | `.\bootstrap.ps1` puis `.\rag.ps1 provision` |
| « Port 6333 occupé ; aucun service existant ne sera arrêté. » | Autre programme ou autre instance sur le port | `.\rag.ps1 doctor` (rubrique `ports` : `owned`, `foreign`, `occupied_unknown_owner`) |
| « Instance existante avec profil différent : down puis up pour appliquer la configuration » | Profil modifié pendant que l'instance tourne | `.\rag.ps1 down` puis `.\rag.ps1 up` |
| « Chemin Qdrant trop long pour le binaire Windows verrouillé… » | Chemin `…\qdrant\storage` de plus de 57 caractères | Définir `qdrant.storage_dir` vers un dossier court dédié |
| Question en « En attente de mémoire disponible » puis « Admission generation refusée : … Mio disponibles, 4992 Mio requis … » | Mémoire hôte sous l'estimation + réserve | Fermer des applications étrangères, relancer la question ; `.\rag.ps1 doctor` (rubrique `cold_admission`) |
| « Un travail lourd est déjà en cours sur ce poste (…) ; réessayer après sa fin. » | Import, génération ou calibration tient le verrou lourd | Attendre la fin ; `GET /api/v1/jobs` pour voir le travail actif |
| `status` renvoie `stale` | Superviseur disparu sans écrire son état (redémarrage du poste, arrêt brutal) | `.\rag.ps1 up` : l'identité périmée n'empêche pas un nouveau lancement |
| Atelier sur « Session requise », « Session expirée » ou « Lien d'ouverture expiré ou déjà utilisé » | Aucune session valide dans ce navigateur : adresse tapée, 2 h sans activité, 12 h écoulées, API redémarrée, lien de plus de 5 min ou déjà utilisé | `.\rag.ps1 open` |
| « Instance non démarrée : lancer d'abord .\rag.ps1 up » | `open` lancé sans instance démarrée pour ce profil | `.\rag.ps1 up` puis `.\rag.ps1 open` |
| Document « Extraction partielle à publier » | Du texte manque ou n'est pas prouvé présent, ou extraction antérieure à W012 | Lire les avertissements du Suivi ; « Utiliser cette extraction partielle » ou réindexer |
| Appel manuel à l'API : 401 `session_required` | Route protégée appelée sans session ni jeton de contrôle | Ajouter l'en-tête `X-RAG-Control-Token` ([exploitation, section 1](docs/exploitation/EXPLOITATION.md#1-conventions)) |

---

## 20. Aide-mémoire

```powershell
# Préparation (réseau)
.\bootstrap.ps1
.\rag.ps1 provision
.\rag.ps1 pull-model

# Préparation hors ligne depuis les caches
.\bootstrap.ps1 -Offline
.\rag.ps1 provision -Offline

# Exploitation
.\rag.ps1 doctor
.\rag.ps1 up
.\rag.ps1 open
.\rag.ps1 status
.\rag.ps1 logs
.\rag.ps1 down
.\rag.ps1 status -Report D:\preuves\status.json

# Import d'un dossier de PDF dans l'instance démarrée (rapport neuf hors Git)
.\.venv\Scripts\python.exe tools\corpus\import_folder.py --source <dossier> --output .runtime\qa\import-<horodatage>.json

# Profil d'un utilisateur, données hors du dossier du programme (installation par utilisateur en préparation)
.\rag.ps1 init-profile -Target <racine-des-donnees> -QdrantStorage <dossier-court> -Ports 18785,16333,21434
.\rag.ps1 up -Profile <racine-des-donnees>\profile.yaml

# Sauvegarde et restauration
.\rag.ps1 backup -Path <dossier-neuf>
.\rag.ps1 verify -Path <snapshot>
.\rag.ps1 restore -Path <snapshot> -Target <racine-neuve>
.\rag.ps1 up -Profile <racine-neuve>\restored-profile.yaml

# Contrôles
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider -m "not integration and not slow and not acceptance"
.\.venv\Scripts\python.exe tools/docs/check_docs.py
.\.venv\Scripts\python.exe tools/docs/diagrams.py --check
.\.venv\Scripts\ruff.exe check tools/docs tests/unit/test_docs_space.py
```

---

## Contribution

Les règles de travail sont dans [CLAUDE.md](CLAUDE.md) et [AGENTS.md](AGENTS.md) ; le suivi d'un chantier vit dans son `PLAN.md` (ici [RAG_Local_Agents/PLAN.md](RAG_Local_Agents/PLAN.md)), avec journal, décisions et sources.

- Un seul dépôt Git, branche `main`, remote privé `origin` ; commit puis push après chaque travail vérifié, avec un message qui décrit le résultat et ses contrôles.
- Identité Git unique, fixée dans la configuration locale du dépôt ; aucun trailer `Co-Authored-By`, aucune mention d'assistant, aucun force-push ni réécriture d'historique sans demande dédiée.
- Avant chaque commit : relire `git status` et le diff indexé ; ni `PDF/`, ni `.runtime/`, ni secret, ni fichier volumineux injustifié.
- Fins de ligne conservées telles quelles (`* -text`) ; nouveaux fichiers en LF.
- La documentation de `docs/` ne change qu'après un changement réel et vérifié du système ; `tools/docs/check_docs.py` doit rester au vert.

---

## Licence

Aucune licence n'est déclarée pour ce dépôt : pas de fichier `LICENSE`, pas de champ `license` dans `pyproject.toml`, et `apps/web/package.json` est marqué `private`. Les licences des composants tiers provisionnés sont relevées dans [`config/artifacts.lock.json`](config/artifacts.lock.json) et dans les [inventaires du 30 septembre 2026](RAG_Local_Agents/reports/licenses-2026-09-30.json) ; le registre des avis de redistribution des artefacts livrés (critère D09.5) reste à établir (lot R11).
