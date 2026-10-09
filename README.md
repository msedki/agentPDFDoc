# Atelier documentaire local

**Rôle :** point d'entrée du projet et de sa documentation · **Propriétaire :** intégration et documentation du produit · **Statut :** Stabilisé · **Référence :** base publiée `05da85c` et commande lint R15-3 locale vérifiée le 2026-10-03 ; réextraction W029-6 validée sur `635d74a` ; choix de modèle R23 sur la base `3e56c75` et modifications locales du 2026-10-04, qualification suivie dans le plan ; modèle par défaut W045, estimations d'admission W041 et W046 et renvois aux kits d'installation (introduction, sections 1, 4, 5, 6, 9, 10, 13, 16, 19 et 20) sur la base `78ec95c` et les modifications locales R26-MOD-01 et R26-KIT-04 du 2026-10-07, vérifiés en unités ; corrections R27 et étude préalable Office R28 sur base `75df760` le 09/10/2026, statuts et preuves dans le PLAN · **Mis à jour :** 2026-10-09 18:16 (UTC) · **Source de vérité :** code et références liés ci-dessous ; état du chantier dans [PLAN.md](RAG_Local_Agents/PLAN.md), organisation documentaire dans [docs/README.md](docs/README.md) · **Remplace :** aucun document

Poste de lecture et d'analyse de PDF pour Windows 11, sans WSL, Docker ni service distant. La recette de performance vise un poste physique de 16 Go au plus en calcul CPU. Le code comporte aussi une voie Linux native aarch64 et x86-64 ([W018](RAG_Local_Agents/DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs)) ; seule aarch64 a été exercée sur le poste Jetson du chantier. La génération peut passer sur un GPU NVIDIA là où cette voie est qualifiée. Le modèle local répond à partir de passages enregistrés pour la question, et une citation valide s'ouvre dans le PDF à sa version, sa page et son bloc d'origine. La recette complète reste ouverte, notamment ses exigences de performance sur cet hôte.

**État au 2 octobre 2026 (code livré `abfc1e0`, suivi W029/R14/R15).** La recette D01–D11 n'est close sur aucune plateforme. Depuis [W018](RAG_Local_Agents/DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs), chaque critère se qualifie par plateforme et une preuve ne vaut que pour la machine qu'elle déclare ([DEFINITION_OF_DONE.md](RAG_Local_Agents/DEFINITION_OF_DONE.md), règle de clôture) ; détail et prochaines actions dans le [plan du chantier](RAG_Local_Agents/PLAN.md). Les correctifs W029, y compris la reprise ciblée du petit glyphe à 90°, passent la campagne réelle et les contrôles API sur une instance neuve Linux aarch64. La régression Python et les relectures indépendantes passent sur ce périmètre ; le lot est publié sur `origin/main`. La réextraction du corpus du poste est terminée : conservation et états de publication vérifiés, qualité globale non qualifiée. Résultats et limites au [journal du 2 octobre](RAG_Local_Agents/journal/2026-10-02.md) ; aucune validation globale de D02 ou de Windows n'en est déduite.

- **Windows 11 x86-64, cible d'origine ([W001](RAG_Local_Agents/DECISIONS.md#w001-plateforme-windows-native)).** État de la qualification au 1er octobre 2026 sur le poste de 16 Gio : cases et preuves des sections D01 à D11 de la DoD. Import, extraction, recherche, génération et ouverture des citations y ont été exercés sur une instance réelle ; 4 documents du corpus du poste sont extraits et publiés, 61 en pause jusqu'au feu vert de l'utilisateur ; recherche évaluée sur ce corpus (157 blocs attendus sur 160 au top 10, [rapport](RAG_Local_Agents/reports/evaluation/corpus-reel-2026-09-30.md)) ; une réponse réelle complète a pris 298 s, dont 175 s avant le premier mot, loin de la cible D07 ([preuve](RAG_Local_Agents/reports/backend/2026-09-30-real-corpus-question-20260930T2029.json)). Aucun essai n'y a été refait depuis le passage au poste Linux (clone du 1er octobre à 12:42 UTC) : les évolutions suivantes, dont l'accélération GPU et les corrections de la qualification Linux, n'y sont couvertes que par des tests en plateforme simulée, par `mypy --platform win32` et par l'analyse syntaxique et quelques exécutions ciblées des scripts PowerShell du dépôt sous PowerShell 7.4.15 (`test_powershell_syntax.py`), jamais sous Windows PowerShell 5.1 ([journal du 2 octobre](RAG_Local_Agents/journal/2026-10-02.md)).
- **Linux aarch64.** Qualification exécutée en partie le 2 octobre 2026 sur un Jetson AGX Orin de 61 Gio (lot J8), qui ne représente pas l'hôte de 16 Go visé par D07 : installation sur clone neuf et démarrage hors ligne (D01) et sécurité hors ligne (D08) réussis ; les corrections des défauts d'extraction J8 et du scan synthétique à 90° sont vérifiées sur les fixtures de W029 ; D07 bloqué ; jeu final non exécuté. D09.5 est satisfait dans le cadre de l'usage interne décidé par [W030](RAG_Local_Agents/DECISIONS.md#w030-usage-interne--registre-des-licences-sans-validation-de-redistribution), avec les manques de textes de licence déclarés. Le statut et la preuve de chaque critère sont dans le tableau « Qualification Linux » de la [DoD](RAG_Local_Agents/DEFINITION_OF_DONE.md#qualification-linux-w018), la procédure employée dans [QUALIFICATION.md, section 10](RAG_Local_Agents/QUALIFICATION.md#10-qualification-sous-linux), les corrections qui en sont issues dans le [CHANGELOG](CHANGELOG.md). Les suites autorisées et les décisions acquises restent dans le plan ; W029-6 est vérifié pour sa réextraction et sa conservation, pas pour la qualité globale du corpus. Le jeu final reste non exécuté.
- **Linux x86-64.** Verrou uv et artefacts résolus ; jamais exécuté, faute de machine de qualification (même tableau de la DoD).

**Accélération GPU de la génération, état au 2 octobre 2026 (commits `4d8ba68` et `c32b759`) :** livrée selon [W024](RAG_Local_Agents/DECISIONS.md#w024-accélération-gpu-détectée-proposée-et-utilisée-automatiquement-quand-elle-est-disponible) et [W025](RAG_Local_Agents/DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024). Seul le modèle de réponse change de matériel ; extraction, OCR et embeddings restent sur CPU. Le GPU n'est employé d'office que sur une voie qualifiée par un essai réel : aujourd'hui un Jetson sous Jetson Linux R35 (JetPack 5) avec le complément officiel d'Ollama, essayé le 2 octobre sur le Jetson AGX Orin du poste Linux aarch64 de développement (provisionnement du complément, démarrage, `doctor`, `selftest` sur GPU puis en CPU imposé, calibration ; [résultats et limites](docs/architecture/ARCHITECTURE.md#51-accélération-gpu-de-la-génération)). Un Jetson de 16 Go en mode GPU n'est pas qualifié : en `auto`, un Jetson de 16 Gio de mémoire totale ou moins, ou dont la mémoire est illisible, reste sur CPU, et `doctor` y propose un essai par `llm.accelerator: gpu`. L'essai suggère qu'une partie de la mémoire prise par le GPU échappe à `MemAvailable`, sur laquelle repose le gouverneur (hypothèse H-GPU-2, non mesurable sans droits root sous Jetson Linux R35.4.1). Sur un Jetson R36 et sur un poste Linux ou Windows doté d'un GPU NVIDIA que découvre Ollama, voies jamais essayées, `doctor` propose un essai par `llm.accelerator: gpu` sans employer le GPU d'office. Un poste sans GPU utilisable, dont le poste Windows de qualification, reste sur CPU avec des requêtes inchangées, ce que vérifient des tests sur plateforme simulée ; son rejeu réel reste à faire. La recette D07 se mesure en calcul CPU imposé ([QUALIFICATION.md, section 8](RAG_Local_Agents/QUALIFICATION.md#8-performance-et-ressources)).

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

La documentation stabilisée est indexée dans [docs/README.md](docs/README.md) : architecture, [spécifications fonctionnelles](docs/specifications/SPECIFICATIONS.md), interface HTTP, [déploiement](docs/deploiement/DEPLOIEMENT.md) (clone, kit Windows interne, [kit hors ligne Linux](docs/deploiement/DEPLOIEMENT.md#8-kit-hors-ligne-linux)) et exploitation. L'historique des changements est dans [CHANGELOG.md](CHANGELOG.md).

L'[étude DOCX/XLSX](RAG_Local_Agents/reports/extension-office-2026-10-09.md)
définit leur intégration avec structures et citations sources. Les lots et
critères sont dans [R28 du plan canonique](RAG_Local_Agents/PLAN.md#r28--étude-de-lextension-docxxlsx-avant-implémentation) ;
ces formats ne sont pas encore pris en charge par l'application.

---

## 1. Vue d'ensemble

Le poste importe des PDF natifs, scannés ou mixtes, en extrait le texte avec sa géométrie, l'indexe deux fois (plein texte SQLite FTS5 et vecteurs Qdrant) et répond aux questions avec un modèle Qwen exécuté par Ollama. Tout tourne en processus natifs supervisés par un lanceur unique, `rag.ps1` (PowerShell, Windows) ou `rag.sh` (shell POSIX, Linux), sur l'adresse de bouclage 127.0.0.1.

| Composant | Rôle | Racine |
|---|---|---|
| Interface web | Trois panneaux (bibliothèque, lecteur PDF, analyse) ; export statique Next.js servi par l'API | [`apps/web/`](apps/web/) |
| API locale | FastAPI : bibliothèque, import, recherche hybride, questions en flux SSE, citations, travaux | [`services/api/`](services/api/) |
| Ingestion PDF | Worker isolé : préflight PDFium, routage Docling natif / structuré / OCR régional, fenêtres reprenables | [`services/ingestion/`](services/ingestion/) |
| Exploitation | Lanceur, superviseur, gouverneur de ressources, sauvegarde et restauration | [`services/runtime/`](services/runtime/), [`rag.ps1`](rag.ps1), [`bootstrap.ps1`](bootstrap.ps1), [`rag.sh`](rag.sh), [`bootstrap.sh`](bootstrap.sh) |
| Contrats | Périmètre, page, bloc, fragment, source, événements SSE, erreurs | [`packages/contracts/contracts.json`](packages/contracts/contracts.json) |
| Configuration | Profils `local16-4b` (4B, défaut) et `local16` (2B), verrous d'artefacts et de modèles | [`config/`](config/) |
| Qualification | PDF synthétiques, jeux de questions, outils de capture et de notation | [`fixtures/`](fixtures/), [`evals/`](evals/), [`tools/qualification/`](tools/qualification/) |
| Suivi du chantier | Plan, critères de fin, décisions, journal, sources, preuves ; exigences V2.1 | [`RAG_Local_Agents/`](RAG_Local_Agents/) |

Ces invariants sont appliqués par le code ; un écart produit un refus explicite plutôt qu'un fonctionnement dégradé silencieux.

| Invariant | Comportement en cas d'écart |
|---|---|
| Services sur 127.0.0.1 uniquement | Profil refusé au lancement (« Le runtime exige loopback ») ; requête HTTP refusée si `Host` ou `Origin` n'est pas local (400 `invalid_host`, 403 `invalid_origin`) |
| Données accessibles seulement par une session ouverte depuis le poste ou par le jeton de contrôle de l'instance ([W011](RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique)) | 401 `session_required` ou `session_expired`, 403 `csrf_rejected` ; l'interface affiche la commande `.\rag.ps1 open` au lieu de l'espace de travail |
| Accélération déclarée par `llm.accelerator` : `auto` (profil livré), `cpu` ou `gpu` ; forme antérieure `llm.num_gpu: 0` acceptée seule, équivalente à `cpu` | Profil refusé par `load_profile` et par l'API (400 `invalid_profile`, clés en cause dans `details.keys`), avec un message qui nomme la clé ([dépannage, section 2](docs/exploitation/DEPANNAGE.md#2-démarrage)) |
| GPU employé seulement s'il est découvert par Ollama, avec des bibliothèques vérifiées, sur une voie qualifiée (ou à l'essai en `gpu`) | Instance démarrée sur CPU, avec sa raison dans la rubrique `calcul` de `doctor` ; un échec du chargement sur GPU fait relancer la question une fois sur CPU et laisse l'instance sur CPU jusqu'au redémarrage, ce que signalent `doctor` et l'atelier (« GPU en échec : réponses calculées sur le processeur ») |
| Un seul travail lourd (génération ou ingestion) sur le poste | Verrou `.runtime/control/host-heavy.lock` : l'import attend en file, la question attend son admission |
| Réserve de 1 536 Mio de mémoire hôte | Question refusée à l'admission ou annulée en cours de génération (« Réserve hôte menacée pendant la génération ; requête annulée. ») |
| Originaux immuables | Copie gérée `originals/<sha256>.pdf` ; 409 `original_integrity_failure` si une copie existante est altérée ; `ORIGINAL_CHANGED` si le PDF change pendant l'extraction |
| Une citation n'existe que dans le registre de sa question | Identifiant inconnu remplacé par « [citation inconnue] » et avertissement `unknown_citations` |
| Aucune reprise automatique d'un import en pause | Profil refusé si `resources.scheduling.auto_resume_ingestion` ne vaut pas `false` |
| Aucun processus étranger arrêté | Port occupé : « Port … occupé ; aucun service existant ne sera arrêté. » |

---

## 2. Parcours utilisateur

1. Après `.\rag.ps1 up`, lancer `.\rag.ps1 open` (sous Linux, `./rag.sh up` puis `./rag.sh open`, ouverture qui n'a pas encore été essayée dans le navigateur d'une session graphique : lot J7 du [plan](RAG_Local_Agents/PLAN.md)) : l'atelier s'ouvre dans le navigateur par défaut sur `http://127.0.0.1:8785/workspace/`, avec une session de 12 h au plus, fermée après 2 h sans activité. Une adresse tapée ou un signet sans session affiche « Session requise » et la commande à copier ; le bouton « Fermer la session » de la barre supérieure ferme la session du navigateur.
2. Importer un ou plusieurs PDF (« Importer des PDF »), ou un dossier entier (« Importer un dossier ») : les chemins relatifs forment l'arborescence de la bibliothèque, l'original est copié et haché, et le suivi des traitements affiche l'étape réellement en cours (file, extraction, indexation, pause).
3. Ouvrir un document dans le lecteur PDF.js : zoom, rotation, sommaire extrait, blocs de texte sélectionnables. L'original reste consultable avant la fin de l'indexation.
4. Choisir le périmètre de travail : toute la bibliothèque, un dossier et ses sous-dossiers, des documents sélectionnés, une section, une plage de pages ou une sélection de texte.
5. Lancer une recherche, poser une question ou comparer deux à quatre documents. Les sources retenues arrivent avant le texte de la réponse, qui s'affiche en flux.
6. Cliquer une citation `[S001]` : le lecteur ouvre la version, la page et le bloc enregistrés, surligne la région quand sa géométrie est connue et permet de revenir au passage précédent.

Parcours vérifiés dans un navigateur réel : trois panneaux sans requête externe à 1366 × 768 et 1920 × 1080, clavier et focus, liens de citation invalides refusés, écran « Session requise », lien d'ouverture refusé à sa deuxième présentation et fermeture de session, sur le build de l'interface refondue ([E2E du 30/09 à 18:30, 8 PASS](apps/web/reports/e2e-2026-09-30-r17-readonly-1830-evidence.json)) ; ancienne citation restaurée ouverte à l'identique, avant la session ([ancienne citation](apps/web/reports/e2e-2026-09-30-restored-source-newcode-1412.log)). La réponse réelle du modèle suivie d'un clic sur sa citation est passée le 1er octobre sur le poste Windows ([preuves](apps/web/reports/e2e-2026-10-01-r2-generation-0446/evidence.json)) ; la qualité des réponses (D05) reste à mesurer sur le jeu final (section [15](#15-qualification)). La coquille (barre supérieure, bibliothèque repliable en rail, panneaux latéraux sous 1 024 px, suivi, aide) et les textes de l'interface ont été refondus (lots R15 et R16, détail dans [apps/web/README.md](apps/web/README.md)) ; leur recette visuelle avec captures (lot R20 du [plan](RAG_Local_Agents/PLAN.md)) a fait l'objet de deux passages, le 30 septembre et le 1er octobre ([rapport de recette](RAG_Local_Agents/reports/ui-recette-2026-09-30.md)), ses points A (sur-titres) et D (contrôle d'accessibilité automatique, lecteur d'écran) restant ouverts (plan, point du 1er octobre à 03:13). Sous Linux aarch64, les scénarios Playwright ont été rejoués le 2 octobre dans Chromium headless (critères D06 du tableau « Qualification Linux » de la [DoD](RAG_Local_Agents/DEFINITION_OF_DONE.md#qualification-linux-w018) ; mode d'exécution dans [apps/web/README.md](apps/web/README.md)).

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
| Ollama temporaire | `http://127.0.0.1:11444` | Pendant `rag.ps1 pull-model`, la sonde de découverte des GPU de `provision` et la calibration uniquement |
| Qdrant temporaire | `http://127.0.0.1:6343` | Pendant `rag.ps1 restore` uniquement |
| Profil restauré | API 8795, Qdrant 6343, Ollama 11445 | Instance démarrée depuis `restored-profile.yaml` |

| Couche | Responsabilité | Source |
|---|---|---|
| Lanceur | Valide le profil, démarre le superviseur sans fenêtre, attend l'état `running`, ouvre l'atelier avec un lien de session (`open`), arrête sur demande | [`rag.ps1`](rag.ps1), [`rag.sh`](rag.sh), [`services/runtime/cli.py`](services/runtime/cli.py), [`supervisor.py`](services/runtime/supervisor.py) |
| Superviseur | Verrous de racine et de stockage, contrôle des ports et des binaires, lancement de Qdrant, Ollama et de l'API dans un Job Object sous Windows ou un groupe de processus sous Linux, choix du mode de génération (GPU ou CPU) d'après la découverte journalisée par Ollama, trace `resources.jsonl` | [`services/runtime/supervisor.py`](services/runtime/supervisor.py), [`windows_process.py`](services/runtime/windows_process.py), [`posix_process.py`](services/runtime/posix_process.py) |
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
| `config/` | Profils `local16-4b.yaml` (4B, défaut) et `local16.yaml` (2B), verrous `artifacts.lock.json`, `models.lock.json`, `embedding-comparison.lock.json` | Oui |
| `tests/unit/`, `tests/integration/` | Tests pytest ; marqueurs `integration`, `slow`, `acceptance` pour les essais natifs et lourds | Oui |
| `tools/qualification/` | Génération des fixtures, capture des annotations, réponses, notation, performance | Oui |
| `tools/corpus/` | Import d'un dossier de PDF dans une instance démarrée, avec son arborescence | Oui |
| `tools/docs/` | Générateur des schémas SVG et contrôle de la documentation | Oui |
| `fixtures/qualification-v2.1/` | PDF synthétiques (texte, scans, géométrie, erreurs, fichiers hostiles) | Oui |
| `evals/qualification-v2.1/` | Jeux de questions développement et final gelé, rapports de préparation | Oui |
| `docs/` | Documentation stabilisée et schémas générés | Oui |
| `RAG_Local_Agents/` | Dossier vivant du chantier et référentiel d'exigences V2.1 | Oui |
| `.agents/skills/` | Compétences projet et références de sécurité utilisées par les agents | Oui |
| `rag.ps1`, `bootstrap.ps1` | Entrées PowerShell du poste Windows | Oui |
| `rag.sh`, `bootstrap.sh` | Entrées shell POSIX du poste Linux | Oui |
| `pyproject.toml`, `uv.lock` | Dépendances Python verrouillées | Oui |
| `RAG_Local_V2_1_Complet.zip`, `SHA256SUMS_COMPLET.txt` | Archive du brief V2.1 telle que reçue ; une fois extraite, son `RAG_Local_V2_1/SHA256SUMS.txt` vérifie ses 34 fichiers. `SHA256SUMS_COMPLET.txt` et `RAG_Local_Agents/SHA256SUMS.txt` sont les empreintes fournies avec le dossier inspecté les 29 et 30 septembre 2026, conformes lors de l'inspection (I01 : 20/20 et 18/18) : ils ne vérifient plus l'arbre courant et ne sont pas le manifeste de l'archive | Oui |
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
| Système | Linux aarch64 ou x86-64, glibc, shell POSIX | glibc 2.28 au moins | [W018](RAG_Local_Agents/DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs), [`bootstrap.sh`](bootstrap.sh) |
| Outil Python | uv | 0.12.21 | [`bootstrap.ps1`](bootstrap.ps1) et [`bootstrap.sh`](bootstrap.sh) (archive et SHA-256 par plateforme) |
| Interpréteur | CPython géré dans `.runtime/python` | 3.12.14 | [`bootstrap.ps1`](bootstrap.ps1) et [`bootstrap.sh`](bootstrap.sh) ; plage `>=3.12,<3.13` dans [`pyproject.toml`](pyproject.toml) |
| API | FastAPI, uvicorn, Pydantic | 0.142.1, 0.54.0, 2.13.5 | [`pyproject.toml`](pyproject.toml), [`uv.lock`](uv.lock) |
| Ingestion | Docling, pypdfium2 | 2.131.0, 5.13.0 | [`pyproject.toml`](pyproject.toml) |
| Modèles Docling | Heron (mise en page), TableFormer accurate | révisions `8f39ad3c`, `fc0f2d45` | [`config/artifacts.lock.json`](config/artifacts.lock.json) |
| OCR | Tesseract CLI (sous Linux, compilé avec Leptonica 1.87.0 depuis les sources), données `tessdata_fast` fra, eng, osd | 5.4.0, commit `87416418` | [`config/local16.yaml`](config/local16.yaml) (`pdf.tesseract_cmd`), [`config/artifacts.lock.json`](config/artifacts.lock.json) |
| Embeddings | multilingual-e5-small ONNX int8, onnxruntime | révision `614241f6`, 1.30.0 | [`config/artifacts.lock.json`](config/artifacts.lock.json), [`pyproject.toml`](pyproject.toml) |
| Index vectoriel | Qdrant serveur (archive Windows, archives Linux musl) | 1.19.1 | [`config/artifacts.lock.json`](config/artifacts.lock.json) |
| Index plein texte | SQLite FTS5 (`unicode61 remove_diacritics 2`) | Bibliothèque embarquée par CPython, lue dans `GET /api/v1/diagnostics` (champ `sqlite`) | [`config/local16.yaml`](config/local16.yaml) (`sqlite`) |
| Serveur de modèle | Ollama (archives Windows et Linux) | 0.35.0 | [`config/artifacts.lock.json`](config/artifacts.lock.json), contrôlé par `/api/version` au lancement |
| Bibliothèques GPU d'Ollama pour Jetson | Compléments officiels `ollama-linux-arm64-jetpack5` (Jetson Linux R35) et `-jetpack6` (R36), extraits par-dessus l'archive de base | 0.35.0 | [`config/artifacts.lock.json`](config/artifacts.lock.json), groupe `ollama-gpu` |
| Modèle de langue (défaut) | Qwen3.5 4B Q4_K_M dérivé texte seul, choisi par `qwen3.5:4b` et servi par `qwen3.5:4b-text` | manifeste `de8024db…` | [`config/local16-4b.yaml`](config/local16-4b.yaml), [`config/models.lock.json`](config/models.lock.json), [W006](RAG_Local_Agents/DECISIONS.md#w006-modèle-qwen-texte-seul-dérivé-localement-sans-encodeur-vision), [W045](RAG_Local_Agents/DECISIONS.md#w045-qwen-35-4b-par-défaut-2b-conservé-au-lancement) |
| Modèle de langue (option 2B) | Qwen3.5 2B Q8_0 (`qwen3.5:2b`), tag officiel direct | manifeste `0689d440…` | [`config/local16.yaml`](config/local16.yaml), [`config/models.lock.json`](config/models.lock.json) |
| Build web | Node.js, pnpm | 22.17.0, 10.34.1 | [`EXPLOITATION_WINDOWS.md`](RAG_Local_Agents/EXPLOITATION_WINDOWS.md) ; `engines` de [`apps/web/package.json`](apps/web/package.json) |
| Interface | Next.js, React, pdfjs-dist, TanStack Query, Zustand, Tailwind CSS | 16.3.7, 19.3.0, 6.3.289, 5.104.0, 5.0.15, 4.3.3 | [`apps/web/package.json`](apps/web/package.json), [`pnpm-lock.yaml`](apps/web/pnpm-lock.yaml) |
| Tests | pytest, TypeScript, Playwright | 9.1.1, 5.9.3, 1.63.0 | [`pyproject.toml`](pyproject.toml), [`apps/web/package.json`](apps/web/package.json) |

Version du projet : `0.1.0`, identique dans [`pyproject.toml`](pyproject.toml) et [`apps/web/package.json`](apps/web/package.json) ; aucune version n'a été publiée.

Le modèle se choisit au lancement : `./rag.sh up` utilise `qwen3.5:4b` par défaut ([W045](RAG_Local_Agents/DECISIONS.md#w045-qwen-35-4b-par-défaut-2b-conservé-au-lancement)) ; `./rag.sh up --model qwen3.5:2b` choisit le 2B. Sous Windows, utiliser `-Model` avec `rag.ps1`. Un profil utilisateur explicite conserve son modèle et ses chemins de données ; il ne se combine pas avec l'option modèle. Dans une installation par le kit hors ligne Linux, le modèle principal se choisit à l'installation (`--model`) et se change par `atelier modele <modèle>` ([déploiement, section 8.8](docs/deploiement/DEPLOIEMENT.md#88-état-réparation-vérification-et-modèle-principal)). Préparation, arrêt et redémarrage : [procédure de changement de modèle](docs/exploitation/EXPLOITATION.md#91-changer-le-modèle-de-génération). Aucun changement à chaud ni choix par question.

---

## 6. Données et stockage

Les lanceurs et l'installateur utilisent `app.data_dir` du profil (`.runtime/data`
pour les profils livrés `local16-4b` et `local16`). Le superviseur transmet cette
racine à l'API par `RAG_DATA_DIR` ; une variable héritée ne remplace pas le
profil. L'API lancée directement et les tests lisent encore cette variable,
hors du parcours supervisé ([W050](RAG_Local_Agents/DECISIONS.md#w050-reprise-dexécution-et-clôture-depuis-la-baseline-du-9-octobre),
[exploitation](docs/exploitation/EXPLOITATION.md)).

| Stockage | Contenu | Emplacement | Reproductible ? | Sauvegarde ? |
|---|---|---|---|---|
| Base SQLite (WAL, FTS5) | Dossiers, documents, versions, révisions d'extraction, générations d'index, pages, blocs, fragments, travaux, questions, événements SSE, citations, cache d'embeddings | `<data_dir>/app.sqlite3` | Non : état métier | Oui, par l'API de sauvegarde SQLite |
| Originaux | Copie gérée de chaque PDF importé, nommée par son SHA-256 | `<data_dir>/originals/` | Non | Oui |
| Extractions | Préflight, fenêtres `window-*.json`, sorties Docling, `extraction.json` | `<data_dir>/extractions/<version>/<travail>/` | Oui, par réextraction (coût OCR) | Oui |
| Index vectoriel | Collection `pdf_chunks_e5small_v1`, vecteurs sur disque, graphe HNSW en mémoire | `<data_dir>/qdrant/` ou `qdrant.storage_dir` | Oui, par réindexation | Oui, par snapshot Qdrant |
| Contrôle et journaux | État du superviseur, verrous, jeton de contrôle et clé Qdrant de l'instance (supprimés à l'arrêt), journaux par instance, journal des événements de session | `<data_dir>/control/`, `<data_dir>/logs/<instance>/`, `<data_dir>/logs/security-audit.jsonl` | Sans objet | Non |
| Modèles et binaires | Ollama, E5, tokenizer Qwen, Docling, tessdata ; Qdrant, Ollama, Tesseract | `.runtime/models/`, `.runtime/bin/` | Oui, par `rag.ps1 provision` (réseau) | Non ; manifestes seulement |
| Manifestes d'empreintes | Artefacts provisionnés, modèle source et modèle texte ; découverte des GPU confirmée par Ollama lors de `provision` (`ollama-discovery.json`) | `.runtime/manifests/` | Oui, par `provision` | Oui (`runtime-manifests/`) |
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

- **Réseau réservé à la préparation.** Seuls `bootstrap.ps1` (uv, Python, dépendances), `rag.ps1 provision` (artefacts verrouillés, dépendances npm, modèle) et `rag.ps1 pull-model` accèdent à Internet ; l'option `-Offline` réutilise les caches. Sous Linux, il s'agit de `bootstrap.sh`, `rag.sh provision` et `rag.sh pull-model`, avec `--offline`. `up`, `open`, `status`, `logs`, `down`, `doctor`, `backup`, `verify` et `restore` ne téléchargent rien.
- **Services en boucle locale.** API, Qdrant et Ollama écoutent sur 127.0.0.1 ; les processus du projet n'ont été observés qu'en écoute locale ([relevé du 30/09](RAG_Local_Agents/reports/listening-sockets-20260930T0930.json)). L'API rejette un `Host` ou une `Origin` étrangers et les requêtes intersites et envoie une politique CSP `default-src 'self'` ; Ollama refuse aussi un `Host` ou une `Origin` étrangers ([essai sur serveur réel](RAG_Local_Agents/reports/host-origin-live-20260930T0930.json)).
- **Session locale.** Pas de compte : `.\rag.ps1 open` obtient avec le jeton de contrôle un lien à usage unique de 5 min, que le navigateur échange contre un cookie `HttpOnly` et `SameSite=Strict` ; registre en mémoire de l'API, inactivité 120 min, durée absolue 12 h, jeton CSRF sur les modifications, relectures périodiques de l'atelier sans effet sur l'inactivité, journal `security-audit.jsonl` sans secret ([W011](RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique), [gardes réelles 19/19](RAG_Local_Agents/reports/http-guards-live-20260930T1829.json), [API.md, section 2](docs/interfaces/API.md#2-session-et-autorisation)).
- **Qdrant sous clé d'API.** Le superviseur tire une clé à chaque démarrage et ne la transmet qu'à Qdrant et à l'API ; sans elle, Qdrant répond 401 hors de ses sondes de santé, y compris avec un `Host` étranger ([W010](RAG_Local_Agents/DECISIONS.md#w010-clé-dapi-qdrant-propre-à-chaque-vie-du-serveur), [gardes HTTP réelles, 15/15](RAG_Local_Agents/reports/http-guards-live-20260930T1636.json)).
- **Télémétrie coupée dans les processus enfants.** Variables `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `HF_HUB_DISABLE_TELEMETRY`, `OLLAMA_NO_CLOUD`, `NEXT_TELEMETRY_DISABLED` ; Qdrant lancé avec `--disable-telemetry` ([`supervisor.py`](services/runtime/supervisor.py), fonction `environment`). ONNX Runtime, qui exécute le modèle de recherche, lit `ORT_DISABLE_TELEMETRY` une seule fois, à son chargement : l'API la pose à `1` à l'import de [`embedding.py`](services/api/embedding.py), avant tout chargement, et le worker d'extraction la reçoit aussi (`WORKER_FIXED_ENVIRONMENT`, [`jobs.py`](services/api/jobs.py)). Elle n'agit que sous Linux ; sous Windows, ONNX Runtime ne la lit pas (voir les limites ci-dessous).
- **Corpus hors Git.** `PDF/`, `.runtime/`, les bases, snapshots et secrets sont exclus ; les rapports versionnés contiennent le nom d'hôte, le nom d'utilisateur Windows et les empreintes des documents, jamais leur texte ([W005](RAG_Local_Agents/DECISIONS.md#w005-dépôt-git-et-publication-vers-le-remote-privé)).

Limites connues, non corrigées à ce jour :

| Limite | Preuve | Suite prévue |
|---|---|---|
| Une instance lancée avant l'introduction de la clé Qdrant (commit `e0be4ac`) reste sans clé | [W010](RAG_Local_Agents/DECISIONS.md#w010-clé-dapi-qdrant-propre-à-chaque-vie-du-serveur), conséquences | `.\rag.ps1 down` puis `.\rag.ps1 up` |
| La clé Qdrant circule en clair sur la boucle locale (pas de TLS) | [W010](RAG_Local_Agents/DECISIONS.md#w010-clé-dapi-qdrant-propre-à-chaque-vie-du-serveur) | Choix documenté : trafic limité à 127.0.0.1 |
| En développement, cookie de session, jeton CSRF et jeton de contrôle circulent en clair sur la boucle locale (HTTP) | [W011](RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique) | Choix documenté ; le profil `production` sert HTTPS, vérifié seulement par un test d'intégration avec certificat de test |
| Sous Windows, blocage des sorties réseau au niveau du système non exécuté (D08.1) | [plan](RAG_Local_Agents/PLAN.md), points à trancher ; [journal du 30/09](RAG_Local_Agents/journal/2026-09-30.md), vers 18:17 | Une règle de pare-feu exigerait des droits administrateur, exclus depuis le 30/09 ; seule une coupure physique du réseau pendant la recette reste possible. Sous Linux, l'essai s'est fait sans droits d'administration, dans un espace de noms réseau utilisateur ([QUALIFICATION.md, section 10](RAG_Local_Agents/QUALIFICATION.md#10-qualification-sous-linux)) : D08.1 PASS le 2 octobre 2026 (tableau « Qualification Linux » de la [DoD](RAG_Local_Agents/DEFINITION_OF_DONE.md#qualification-linux-w018)) |
| Sous Windows, le produit ne coupe pas la télémétrie d'ONNX Runtime : elle passe par ETW (TraceLogging), qui ne lit pas `ORT_DISABLE_TELEMETRY`. D'après l'éditeur, ses événements ne sont enregistrés que si une session de traces externe les collecte, et le système ne les transmet à Microsoft que selon le consentement de l'utilisateur | [Privacy.md d'ONNX Runtime 1.30.0](https://github.com/microsoft/onnxruntime/blob/v1.30.0/docs/Privacy.md#disabling-telemetry), section « Disabling Telemetry » ; [telemetry_environment.h](https://github.com/microsoft/onnxruntime/blob/v1.30.0/onnxruntime/core/platform/telemetry_environment.h), `IsTelemetryDisabledByEnvironment` ; comportement non observé sous Windows | À trancher : aucune désactivation propre à Windows n'est en place ; l'effet de l'API qui retire les événements non essentiels n'y a pas été vérifié |
| `GET /api/docs`, en développement seulement, sert l'interface Swagger de FastAPI, dont les scripts viennent d'un CDN que la CSP bloque | `docs_url` dans [`services/api/main.py`](services/api/main.py) | Page non examinée au rendu ; `GET /openapi.json` reste local ; les deux sont désactivés en production |

---

## 9. Prérequis du poste

| Élément | Exigence | Contrôle |
|---|---|---|
| Système | Windows 11 x86-64, PowerShell 5.1, compte utilisateur standard (aucune étape ne demande de droits administrateur), exécution des scripts locaux autorisée (politique `RemoteSigned` observée pour l'utilisateur) ; les scripts du projet ne modifient ni la politique d'exécution ni le `PATH` | `$PSVersionTable`, `Get-ExecutionPolicy -List` |
| Mémoire | 16 Gio physiques ; à froid, une question exige 5 888 Mio disponibles avec le 4B, modèle par défaut ([W046](RAG_Local_Agents/DECISIONS.md#w046-admission-du-4b-relevée-après-un-pilote-exclusif-aux-limites-w039)), 5 504 Mio avec le 2B ([W041](RAG_Local_Agents/DECISIONS.md#w041-admission-froide-du-2b-relevée-après-un-pilote-exclusif-aux-limites-w039)), et un import 3 840 Mio (estimation + réserve de 1 536 Mio) | `.\rag.ps1 doctor`, rubrique `cold_admission` |
| Disque | Réserve de 2 Gio exigée avant téléchargement et avant sauvegarde ; la dérivation du modèle texte exige deux fois la taille du modèle source plus 2 Gio | messages de refus de [`artifacts.py`](services/runtime/artifacts.py), [`backup.py`](services/runtime/backup.py), [`cli.py`](services/runtime/cli.py) |
| Node.js et pnpm | 22.17.0 et 10.34.1 dans le `PATH`, pour `provision` et le build | `.\rag.ps1 doctor`, rubrique `node_tools` |
| Tesseract | Tesseract 5.4.0 Windows déjà installé, de préférence dans le profil de l'utilisateur (`%LOCALAPPDATA%\Programs\Tesseract-OCR`, emplacement du poste de référence) : une installation sous `%PROGRAMFILES%` demanderait des droits administrateur ; `provision` en copie l'exécutable, les DLL et les licences dans `.runtime/bin/` avec leurs empreintes | message « Prérequis Tesseract5.4.0 Windows absent » ([`provisioning.py`](services/runtime/provisioning.py)) |
| GPU | Facultatif : seule la génération l'emploie, d'office sur une voie qualifiée (pour un GPU intégré de Jetson, sur un poste de plus de 16 Gio de mémoire) ; le projet n'installe aucun pilote ([architecture, section 5.1](docs/architecture/ARCHITECTURE.md#51-accélération-gpu-de-la-génération)) | `.\rag.ps1 doctor`, rubrique `calcul` |
| Ports | Libres sur 127.0.0.1 : 8785 (API), 6333 (Qdrant), 11434 (Ollama) ; 11444 pendant `pull-model`, la sonde de découverte de `provision` et la calibration ; 6343 pendant `restore` ; 8795, 6343, 11445 pour un profil restauré | `.\rag.ps1 doctor`, rubrique `ports` |
| Internet | Uniquement pour `bootstrap.ps1`, `provision` et `pull-model` sans `-Offline` ; sous Linux, `bootstrap.sh`, `rag.sh provision` et `rag.sh pull-model` sans `--offline` | — |

La provenance de l'installateur Tesseract n'est pas authentifiée indépendamment ; seule la copie locale est hachée. Sous Linux, les prérequis propres à la plateforme (architecture, glibc, outils de compilation de Tesseract, Corepack) sont décrits dans [EXPLOITATION.md, section 2](docs/exploitation/EXPLOITATION.md#2-préparer-le-poste) ; mémoire, disque, ports et GPU suivent le tableau ci-dessus, avec `./rag.sh doctor`.

---

## 10. Installation

Depuis la racine du dépôt, dans PowerShell 5.1 :

```powershell
.\bootstrap.ps1
.\rag.ps1 provision
.\rag.ps1 doctor
```

Sous Linux, depuis un shell POSIX : `./bootstrap.sh`, `./rag.sh provision`, puis `./rag.sh doctor` ([EXPLOITATION.md, section 2](docs/exploitation/EXPLOITATION.md#2-préparer-le-poste) ; les options s'écrivent `--offline`, `--skip-model`, `--only <groupe>`).

Sur un poste qui reçoit l'atelier sans le dépôt, l'installation passe par un kit : kit Windows interne ([déploiement, sections 3 à 7](docs/deploiement/DEPLOIEMENT.md#3-fabriquer-et-vérifier-un-kit-windows-interne)) ou kit hors ligne Linux, installé pour le compte de l'utilisateur par `./installer.sh` depuis le dossier extrait, avec son guide `LISEZMOI.md` ([déploiement, section 8](docs/deploiement/DEPLOIEMENT.md#8-kit-hors-ligne-linux)).

`bootstrap.ps1` télécharge uv 0.12.21 (SHA-256 vérifié), installe CPython 3.12.14 dans `.runtime/python` et synchronise `.venv` depuis `uv.lock`. `provision` synchronise de nouveau les dépendances Python, installe les dépendances web (`pnpm install --frozen-lockfile`), télécharge et vérifie les artefacts verrouillés (Qdrant, Ollama, E5, tokenizer Qwen, tessdata, modèles Docling, et, sur un Jetson Linux R35 ou R36, le complément GPU d'Ollama sauf profil en calcul CPU), copie Tesseract, construit l'interface, prépare le modèle et le tokenizer du profil choisi (2B directement, 4B avec dérivation texte seule), puis consigne la découverte des GPU par Ollama ([`cli.py`](services/runtime/cli.py), fonction `provision` ; [exploitation, section 2](docs/exploitation/EXPLOITATION.md#2-préparer-le-poste)).

| Variante | Commande |
|---|---|
| Hors ligne, depuis des caches déjà remplis | `.\bootstrap.ps1 -Offline` puis `.\rag.ps1 provision -Offline` |
| Sans le modèle de langue | `.\rag.ps1 provision -SkipModel` |
| Un seul groupe d'artefacts (`qdrant`, `ollama`, `ollama-gpu`, `e5`, `qwen-tokenizer`, `tessdata`, `docling`) ; `ollama-gpu` n'a d'objet que sur un Jetson Linux R35 ou R36, où il est téléchargé quel que soit le profil | `.\rag.ps1 provision -Only qdrant` ; sous Linux, `./rag.sh provision --only ollama-gpu` |
| Modèle seul, idempotent | `.\rag.ps1 pull-model` ou `.\rag.ps1 pull-model -Offline` |

Sous Windows, le provisionnement complet d'une racine neuve sans intervention (critère D01) n'a pas encore été rejoué : lot R10 du [plan](RAG_Local_Agents/PLAN.md). Sous Linux aarch64, il l'a été le 2 octobre 2026 sur un clone neuf du commit `4d8ba68` ; les modifications ultérieures de `services/runtime/cli.py` (commits `c32b759` et `419b526`) n'ont pas été rejouées en provisionnement neuf (tableau « Qualification Linux » de la [DoD](RAG_Local_Agents/DEFINITION_OF_DONE.md#qualification-linux-w018)).

---

## 11. Démarrage et arrêt

```powershell
.\rag.ps1 up
.\rag.ps1 open
.\rag.ps1 status
.\rag.ps1 down
```

`up` vérifie le profil, prend les verrous de la racine et du stockage Qdrant, contrôle ports et binaires, lance Qdrant puis Ollama, décide le mode de génération (GPU ou CPU) d'après la découverte des GPU qu'Ollama a journalisée, lance l'API et rend la main quand elle répond sur `/api/v1/health` ; il n'ouvre pas de navigateur et ne charge pas le modèle de langue. Un second `up` avec le même profil renvoie l'instance en cours. `open` demande à l'instance démarrée un lien d'ouverture à usage unique et l'ouvre dans le navigateur par défaut, sans l'afficher ; il se relance à chaque fois qu'une session a expiré ou été fermée. `down` demande un arrêt coopératif (l'API a 180 s pour se fermer, Qdrant et Ollama 30 s chacun), met le travail d'extraction actif en pause à son checkpoint, ferme toutes les sessions et ne touche qu'aux processus possédés.

![Séquence de rag.ps1 up puis open et refus bloquants](docs/assets/diagrams/sequence-up.svg)

*Ordre des contrôles de `rag.ps1 up`, demande du lien d'ouverture par `rag.ps1 open` et message de chaque refus bloquant.*

Sous Linux : `./rag.sh up`, `./rag.sh open` (ou `./rag.sh open --no-browser`, qui affiche le lien au lieu d'ouvrir un navigateur), `./rag.sh status` et `./rag.sh down` ; Qdrant et Ollama y sont arrêtés par SIGTERM à leur groupe de processus. Procédure détaillée, correspondance des options entre les deux lanceurs, sessions, supervision et reprise : [docs/exploitation/EXPLOITATION.md](docs/exploitation/EXPLOITATION.md).

---

## 12. Ingestion et OCR

Un import copie l'original, crée une version et met un travail en file. Un dossier entier s'importe aussi depuis PowerShell, arborescence comprise, par [`tools/corpus/import_folder.py`](tools/corpus/import_folder.py) ([exploitation, section 6](docs/exploitation/EXPLOITATION.md#6-conduire-les-travaux-dingestion)). Le travail s'exécute dans un sous-processus Python dédié, un seul à la fois et jamais pendant une génération, par fenêtres de quatre pages qui servent de points de reprise. Chaque page est routée vers l'une de quatre voies : page blanche (sans conversion), texte natif simple, conversion structurée par les modèles de mise en page et de tableaux (tableaux, colonnes, typographie variée) ou OCR régional Tesseract (régions image non couvertes, couche texte dégradée) ; les trois dernières passent par Docling. En routage automatique, une page native dont la qualité mesurée est insuffisante peut être reconvertie par la voie structurée si le budget de rendu l'autorise. Après `PDF_RENDER_LIMIT`, un repli peut conserver sa couche native fiable sans rendre la page, mais l'extraction reste partielle et la limite visible ; les conditions sont dans l'[architecture, ingestion](docs/architecture/ARCHITECTURE.md#4-ingestion-des-pdf).

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
- Avant la génération, le gouverneur exige à froid l'estimation du profil plus la réserve de 1 536 Mio : 4 352 + 1 536 = 5 888 Mio pour le 4B, modèle par défaut ([W046](RAG_Local_Agents/DECISIONS.md#w046-admission-du-4b-relevée-après-un-pilote-exclusif-aux-limites-w039)), 3 968 + 1 536 = 5 504 Mio pour le 2B ([W041](RAG_Local_Agents/DECISIONS.md#w041-admission-froide-du-2b-relevée-après-un-pilote-exclusif-aux-limites-w039)) ; il remesure toutes les 2 s pendant 120 s au plus (événement `waiting_for_resources`) puis admet ou refuse ([W007](RAG_Local_Agents/DECISIONS.md#w007-estimations-dadmission-recalibrées-sur-le-modèle-texte), [W008](RAG_Local_Agents/DECISIONS.md#w008-attente-bornée-à-ladmission-de-génération)).
- Pendant la génération, la réserve de 1 536 Mio est surveillée toutes les 0,5 s ; si elle est menacée, la question est annulée.
- La génération tourne sur le GPU ou sur le CPU selon le mode décidé au démarrage de l'instance, avec la même admission. En mode GPU, si Ollama ne parvient pas à charger le modèle (erreur 500 avant le flux), l'API relance la question une seule fois sur CPU, après une nouvelle admission à froid, et l'instance reste sur CPU jusqu'au redémarrage ([architecture, section 5.1](docs/architecture/ARCHITECTURE.md#51-accélération-gpu-de-la-génération)).
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

# Interface : lint, typage et tests unitaires (depuis apps/web)
$env:COREPACK_ENABLE_NETWORK = '0'
pnpm lint
pnpm typecheck
pnpm test:unit
```

Sous Linux, les commandes Python sont les mêmes avec `.venv/bin/python`, depuis un shell POSIX ; celles de l'interface sous Linux sont dans [apps/web/README.md](apps/web/README.md). La borne de 57 caractères du stockage Qdrant concerne uniquement le binaire Windows : le produit et `test_control_profile_isolates_data_and_ports_but_shares_the_host_heavy_lock` la contrôlent seulement sur cette plateforme. Le lint frontend refuse erreurs et avertissements ; sa composition et ses limites sont décrites par [W031](RAG_Local_Agents/DECISIONS.md#w031-contrôle-lint-frontend-maintenu-et-explicite).

Le [plan](RAG_Local_Agents/PLAN.md) et les journaux liés portent les contrôles du contenu actuel, avec leurs échecs et reprises. Le tableau suivant conserve des preuves historiques : il ne remplace pas ce suivi et ne qualifie pas une révision ultérieure.

| Contrôle | Résultat historique conservé | Limite |
|---|---|---|
| Suite pytest entière (unitaires et toute l'intégration : session, HTTPS réel, OCR et rendu réels) | 480 tests le 30/09 de 21:46 à 22:02 UTC sur le contenu du commit `13d865f` avant ses deux corrections de tests : 477 PASS, 3 échecs analysés ([junit](RAG_Local_Agents/reports/backend/2026-09-30-r19-r21-full.xml)) ; reprise des fichiers corrigés : 7 PASS, 2 XFAIL ([junit](RAG_Local_Agents/reports/backend/2026-09-30-r19-r21-rerun.xml)) | Les 2 XFAIL reproduisent le défaut tiers W-PDF01 de `docling_parse` avec Torch, que la voie nominale n'emploie plus ([W009](RAG_Local_Agents/DECISIONS.md#w009-backend-pdf-nominal-pypdfium2-avec-repère-cropbox-corrigé)) |
| Build de l'interface | Exit 0, 278 fichiers exportés, le 01/10 de 03:02 à 03:04 UTC sur le contenu du commit `49a2a1a` ([journal](apps/web/reports/build-2026-10-01-contrastes-legende.log)) ; dernier build surveillé avec manifeste : 30/09 ([journal](apps/web/reports/build-2026-09-30-r15-r17-integrated.log), [manifeste](apps/web/reports/export-manifest-2026-09-30-r15-r17-integrated.json)) | Mesures ponctuelles de mémoire, pas un pic continu |
| Playwright | Lecture seule et recette visuelle : 11 PASS le 01/10 à 03:04 sur l'instance principale, recette visuelle 4/4 à 03:07 ([preuves](apps/web/reports/e2e-2026-10-01-contrastes-legende-0304-evidence.json), [captures](apps/web/reports/visual-qa-20261001T0307/)) ; question réelle et clic sur la citation : PASS à 04:46 et 04:57 ([preuves](apps/web/reports/e2e-2026-10-01-r2-generation-0446/evidence.json)) ; scénarios d'import sur instance isolée (`tools/qualification/e2e_instance.py`) : géométrie 4/4, parcours d'import 5/5 ([géométrie](apps/web/reports/e2e-2026-10-01-import-isole-geometrie-evidence.json), [parcours](apps/web/reports/e2e-2026-10-01-import-isole-parcours-evidence.json)) | Cycle de vie (versions, réimport, réindexation, erreurs de fichier) non rejoué |
| Playwright sous Linux aarch64 | Scénarios de lecture seule, d'import, de session, de recette visuelle et de génération rejoués le 2 octobre 2026 dans Chromium headless 153, sur instance isolée et en session hors ligne ; statuts par critère dans le tableau « Qualification Linux » de la [DoD](RAG_Local_Agents/DEFINITION_OF_DONE.md#qualification-linux-w018) | Preuves hors Git (`.runtime/qa/j8-linux/`) ; plateforme hors de celles que Playwright 1.63 prend en charge officiellement ([apps/web/README.md](apps/web/README.md)) |

Le build surveillé écrit ses preuves dans `apps/web/reports/`, suivi par Git, ou dans le dossier donné par `--evidence-dir <dossier>` pour garder hors de Git celles d'une campagne (dossier créé après les sondes de Node et de pnpm ; un dossier sous `apps/web/out/` ou un chemin qui désigne un fichier sont refusés avant elles) : `.\.venv\Scripts\python.exe apps/web/scripts/build-monitored.py --tag <etiquette-neuve>` sous Windows, `.venv/bin/python apps/web/scripts/build-monitored.py --tag <etiquette-neuve>` sous Linux ; il retient Node dans l'ordre `RAG_WEB_NODE`, puis, sous Windows seulement, le repli `D:\node\node-v22.17.0-win-x64\node.exe` propre au poste de qualification, puis le `node` du PATH ([apps/web/README.md](apps/web/README.md)). Les scénarios Playwright exigent une cible isolée et des autorisations explicites par variable (`RAG_E2E_IMPORT_ALLOWED`, `RAG_E2E_GENERATION_ALLOWED`, `RAG_E2E_READONLY_ALLOWED`) : voir [apps/web/README.md](apps/web/README.md). Leur préparation ouvre une session avec le jeton de contrôle de l'instance visée, lu dans `.runtime/data/control/admin-token` ou dans le fichier désigné par `RAG_E2E_CONTROL_TOKEN_FILE` ([global-setup.ts](apps/web/tests/global-setup.ts)).

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

Sous Linux, la qualification reprend les mêmes critères et les mêmes seuils, dans le tableau « Qualification Linux » de la [DoD](RAG_Local_Agents/DEFINITION_OF_DONE.md#qualification-linux-w018) ; la procédure employée le 2 octobre 2026 sur le Jetson AGX Orin (dossier temporaire, navigateur de Playwright, session hors ligne, relecture des résultats d'`injection_check`, grille D05 jugée par l'assistant) est décrite dans [QUALIFICATION.md, section 10](RAG_Local_Agents/QUALIFICATION.md#10-qualification-sous-linux). Le jeu de questions rédigé par l'assistant sur les documents de `PDF/` ([W020](RAG_Local_Agents/DECISIONS.md#w020-évaluation-question-réponse-sur-le-corpus-réel-du-poste-linux-pdfmgv-pdftest)) et le jugement de ses réponses n'ont pas été relus par un expert : point à trancher 2 du plan.

Blocages actuels sur le poste Windows, détaillés dans le [plan](RAG_Local_Agents/PLAN.md) :

- génération : admise ou refusée selon la mémoire laissée par les autres applications du poste ; refus à 14:05 après 120 s d'attente à 4 709 Mio disponibles pour 4 992 requis ([preuve](RAG_Local_Agents/reports/backend/2026-09-30-restored-question-w008-20260930T1405.json)) ; admission après 67 s d'attente à 20:29, réponse complète dont les 6 citations renvoient au registre de la question ([preuve](RAG_Local_Agents/reports/backend/2026-09-30-real-corpus-question-20260930T2029.json)) ;
- D08.1 : pas de blocage réseau système sans droits administrateur, exclus depuis le 30/09 ; seule une coupure physique du réseau pendant la recette reste possible ;
- qualification métier : le jeu de questions établi par l'assistant sur le corpus du poste ([W014](RAG_Local_Agents/DECISIONS.md#w014-jeu-de-questions-de-référence-établi-par-lecture-intégrale-des-documents), 85 questions) n'a pas été relu par un expert : point à trancher 2 du plan ;
- D07 : le préremplissage mesuré (environ 8,6 jetons/s) rend très improbable la cible de 45 s pour 3 000 jetons ; le seuil ne sera pas abaissé sans décision. Les mesures D07 se font avec un profil en `llm.accelerator: cpu`, contrôlé par `tools/qualification/perf.py` (`d07_eligible`) ; une mesure sur GPU est rapportée à part et ne coche aucun critère D07 ([QUALIFICATION.md, section 8](RAG_Local_Agents/QUALIFICATION.md#8-performance-et-ressources)).

---

## 16. Configuration

Le profil par défaut est [`config/local16-4b.yaml`](config/local16-4b.yaml) (4B, [W045](RAG_Local_Agents/DECISIONS.md#w045-qwen-35-4b-par-défaut-2b-conservé-au-lancement)) ; [`config/local16.yaml`](config/local16.yaml) sert le 2B (`--model qwen3.5:2b`, `-Model` sous Windows). Les deux suivent le schéma version 2 ; `rag.ps1` accepte un autre profil par `-Profile <chemin>`, `rag.sh` par `--profile <chemin>`. Leurs copies documentaires `RAG_Local_Agents/config/local16-4b.yaml` et `RAG_Local_Agents/config/local16.yaml` doivent rester identiques octet pour octet ; l'explication de chaque paramètre est dans [CONFIGURATION.md](RAG_Local_Agents/CONFIGURATION.md).

| Section | Contenu principal |
|---|---|
| `app` | Adresse et port de l'API, racine des données |
| `llm` | Modèle et modèle source, quantification, contexte 8 192 jetons, sorties par mode, accélération (`accelerator` : `auto`, `cpu` ou `gpu`), cache de prompt |
| `embedding` | E5 ONNX int8, préfixes `query:` et `passage:`, 384 dimensions |
| `pdf` | Routes, OCR Tesseract, langues, limites de taille et de rendu, backend PDF, seuil de confiance |
| `chunking`, `retrieval` | Taille des fragments, top-k, RRF, budgets de contexte |
| `qdrant`, `sqlite` | URL et collection, WAL, tokenizer FTS5 |
| `resources` | Réserve hôte, estimations d'admission, attente de génération, ordonnancement |
| `security` | Environnement `development` ou `production`, inactivité et durée maximale d'une session, validité du lien d'ouverture, certificat et clé TLS de production ([W011](RAG_Local_Agents/DECISIONS.md#w011-session-locale-du-poste-ouverte-par-un-lien-à-usage-unique)) |
| `ui` | Budgets de rendu PDF, périmètre par défaut |
| `evaluation_targets` | Seuils de recette (non modifiables sans décision) |

Variables d'environnement lues par le code : `RAG_PROFILE` (profil de l'API), `RAG_DATA_DIR` (racine transmise par le superviseur ; lue aussi par l'API directe et les tests), `RAG_DB_PATH` (base SQLite, tests) ; `RAG_CONTROL_TOKEN`, `RAG_QDRANT_API_KEY`, `RAG_SHUTDOWN_MARKER`, `RAG_LLM_ACCELERATOR` et `RAG_LLM_ACCELERATOR_REASON` (mode de génération et sa raison), posées par le superviseur pour l'API ; `RAG_CONTROL_TOKEN` aussi lue par les outils de qualification ; `RAG_E2E_CONTROL_TOKEN_FILE` pour les scénarios Playwright. Un profil modifié ne s'applique qu'après `down` puis `up` ; `doctor` signale `restart_required` tant que l'instance tourne sur l'ancien profil.

---

## 17. Exploitation

| Commande | Effet | Ce qu'elle ne prouve pas |
|---|---|---|
| `.\rag.ps1 doctor` | Chemins, versions, verrou des modèles, fichiers OCR, ports, marge d'admission, santé des services, matériel de la génération et propositions d'accélération GPU (rubrique `calcul`) ; aucun effet destructif | Une réponse complète (`qualification: NOT_RUN`) |
| `.\rag.ps1 open` | Lien d'ouverture de session à usage unique (5 min) ouvert dans le navigateur par défaut, jamais affiché | Que l'atelier s'affiche : l'écran de session le dit si le lien a été refusé |
| `.\rag.ps1 status` | État enregistré par le superviseur et validité des identités de processus ; `stale` si le superviseur a disparu ; ligne `generation`, mode de génération décidé au démarrage | La disponibilité des index ou du modèle ; un repli sur CPU survenu depuis le démarrage |
| `.\rag.ps1 logs` | Chemins des journaux de Qdrant, Ollama et de l'API de l'instance | — |
| `-Report <fichier.json>` | Écrit le résultat JSON de n'importe quelle commande ; un fichier existant est remplacé, choisir un nom neuf pour garder une preuve | — |

Sous Linux, les mêmes commandes passent par `./rag.sh`, et `-Report` s'écrit `--report`. Procédures complètes, supervision des ressources et reprise d'un travail : [docs/exploitation/EXPLOITATION.md](docs/exploitation/EXPLOITATION.md). Le contrat d'exploitation d'origine reste [EXPLOITATION_WINDOWS.md](RAG_Local_Agents/EXPLOITATION_WINDOWS.md).

---

## 18. Sauvegarde et restauration

```powershell
.\rag.ps1 backup -Path D:\sauvegardes\rag-20260930
.\rag.ps1 verify -Path D:\sauvegardes\rag-20260930
.\rag.ps1 restore -Path D:\sauvegardes\rag-20260930 -Target D:\restaurations\rag-20260930
.\rag.ps1 up -Profile D:\restaurations\rag-20260930\restored-profile.yaml
```

La sauvegarde exige une instance démarrée, suspend les mutations, copie la base SQLite par son API de sauvegarde, les originaux, les extractions, les manifestes et la configuration, télécharge un snapshot Qdrant par collection, puis relance les mutations. La restauration refuse toute racine existante, vérifie chaque copie avant de réécrire les chemins, restaure les snapshots dans un Qdrant temporaire sur le port 6343 et produit un profil distinct (API 8795, Qdrant 6343, Ollama 11445).

Sous Linux : `./rag.sh backup --path <dossier-neuf>`, `./rag.sh verify --path <snapshot>`, `./rag.sh restore --path <snapshot> --target <racine-neuve>`, puis `./rag.sh up --profile <racine-neuve>/restored-profile.yaml`. Procédure, contrôles et retour arrière : [docs/exploitation/SAUVEGARDE-RESTAURATION.md](docs/exploitation/SAUVEGARDE-RESTAURATION.md).

---

## 19. Dépannage

Les messages cités sont ceux du code ; la liste complète, avec les messages propres à Linux (`bootstrap.sh`, compilation de Tesseract, processus d'une instance précédente), est dans [docs/exploitation/DEPANNAGE.md](docs/exploitation/DEPANNAGE.md).

| Symptôme | Cause | Commande |
|---|---|---|
| « Environnement isolé absent. Exécuter bootstrap.ps1… » | `.venv` absent | `.\bootstrap.ps1` puis `.\rag.ps1 provision` |
| « Port 6333 occupé ; aucun service existant ne sera arrêté. » | Autre programme ou autre instance sur le port | `.\rag.ps1 doctor` (rubrique `ports` : `owned`, `foreign`, `occupied_unknown_owner`) |
| « Instance existante avec profil différent : down puis up pour appliquer la configuration » | Profil modifié pendant que l'instance tourne | `.\rag.ps1 down` puis `.\rag.ps1 up` |
| « Chemin Qdrant trop long pour le binaire Windows verrouillé… » | Chemin `…\qdrant\storage` de plus de 57 caractères | Définir `qdrant.storage_dir` vers un dossier court dédié |
| Question en « En attente de mémoire disponible » puis « Impossible de démarrer la génération de la réponse : … Mio disponibles, 5888 Mio requis (pic prévu 4352 + réserve 1536) … » (5504 et 3968 avec le 2B) | Mémoire hôte sous l'estimation à froid + réserve du profil livré | Fermer des applications étrangères, relancer la question ; `.\rag.ps1 doctor` (rubrique `cold_admission`) |
| « Un travail lourd est déjà en cours sur ce poste (…) ; réessayer après sa fin. » | Import, génération ou calibration tient le verrou lourd | Attendre la fin ; `GET /api/v1/jobs` pour voir le travail actif |
| `status` renvoie `stale` | Superviseur disparu sans écrire son état (redémarrage du poste, arrêt brutal) | `.\rag.ps1 up` : l'identité périmée n'empêche pas un nouveau lancement |
| Atelier sur « Session requise », « Session expirée » ou « Lien d'ouverture expiré ou déjà utilisé » | Aucune session valide dans ce navigateur : adresse tapée, 2 h sans activité, 12 h écoulées, API redémarrée, lien de plus de 5 min ou déjà utilisé | `.\rag.ps1 open` |
| « Instance non démarrée : lancer d'abord .\rag.ps1 up » | `open` lancé sans instance démarrée pour ce profil | `.\rag.ps1 up` puis `.\rag.ps1 open` |
| Document « Extraction partielle à publier » | Du texte manque ou n'est pas prouvé présent, ou extraction antérieure à W012 | Lire les avertissements du Suivi ; « Utiliser cette extraction partielle » ou réindexer |
| Appel manuel à l'API : 401 `session_required` | Route protégée appelée sans session ni jeton de contrôle | Ajouter l'en-tête `X-RAG-Control-Token` ([exploitation, section 1](docs/exploitation/EXPLOITATION.md#1-conventions)) |
| Atelier : « GPU en échec : réponses calculées sur le processeur » ; `doctor`, rubrique `calcul` : « Le chargement du modèle sur le GPU a échoué (…) : l'atelier répond sur CPU jusqu'au prochain redémarrage. … » | En mode GPU, Ollama n'a pas pu charger le modèle ; l'instance s'est repliée sur CPU | Journal d'Ollama (`.\rag.ps1 logs`), puis `down` et `up` pour réessayer le GPU, ou `llm.accelerator: cpu` dans le profil ([dépannage, section 8](docs/exploitation/DEPANNAGE.md#8-accélération-gpu-de-la-génération)) |

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

# Profil d'un utilisateur, données hors du dossier du programme (installation par utilisateur par un kit : docs/deploiement/DEPLOIEMENT.md, sections 4 et 8)
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

Sous Linux, depuis un shell POSIX à la racine du dépôt :

```bash
# Préparation (réseau)
./bootstrap.sh
./rag.sh provision

# Exploitation
./rag.sh doctor
./rag.sh up
./rag.sh open
./rag.sh open --no-browser
./rag.sh status
./rag.sh down

# Sauvegarde et restauration
./rag.sh backup --path <dossier-neuf>
./rag.sh verify --path <snapshot>
./rag.sh restore --path <snapshot> --target <racine-neuve>
./rag.sh up --profile <racine-neuve>/restored-profile.yaml

# Contrôles
.venv/bin/python -m pytest tests -q -p no:cacheprovider -m "not integration and not slow and not acceptance"
.venv/bin/python tools/docs/check_docs.py
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

Aucune licence n'est déclarée pour ce dépôt : pas de fichier `LICENSE`, pas de champ `license` dans `pyproject.toml`, et `apps/web/package.json` est marqué `private`. Les licences des composants tiers sont déclarées par [`config/artifacts.lock.json`](config/artifacts.lock.json) et l'inventaire de [`services/runtime/inventory.py`](services/runtime/inventory.py), qui relève les avis présents et les manques. Depuis [W030](RAG_Local_Agents/DECISIONS.md#w030-usage-interne--registre-des-licences-sans-validation-de-redistribution), ce registre suffit à D09.5 dans le cadre de l'usage interne ; le résultat par plateforme est dans la [DoD](RAG_Local_Agents/DEFINITION_OF_DONE.md#qualification-linux-w018). Aucune validation juridique de redistribution n'est annoncée. Une distribution hors de l'organisation rouvrirait ce critère.
