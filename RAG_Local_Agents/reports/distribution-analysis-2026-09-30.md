# Distribution de l'atelier sur d'autres postes Windows : analyse

**Rôle :** rapport d'analyse du lot R22 (documentation vivante du chantier) ; il ne vaut ni décision ni réalisation. **Statut :** analyse terminée, recommandation à arbitrer par l'utilisateur. **Date :** 30 septembre 2026, travail de 17:40:21 à 18:02:04 UTC (heures relevées par `(Get-Date).ToUniversalTime()`). **Base :** commit `ae387a9` (`git log -1 --format=%h`) ; la copie de travail lue n'est pas commitée (97 entrées au `git status`, dont `services/api/security.py` non suivi et `services/api/main.py`, `services/runtime/cli.py`, `services/runtime/supervisor.py`, `tools/corpus/import_folder.py` modifiés par le chantier W011 en cours). **Propriétaire logique :** intégrateur du chantier. **Skills appliqués :** `windows-rag-runtime` (`.agents/skills/`) et `official-source-review` (`RAG_Local_Agents/skills/`).

Demande de l'utilisateur, 30/09/2026 vers 17:40 UTC : « La plateforme doit être déployable sur d'autres postes, avec la possibilité pour l'utilisateur d'y mettre ses propres documents en les important. Analyser la possibilité de distribuer l'application et comment rendre cette distribution sans friction (Electron ou autre), avec des scripts ou tout autre moyen pour tout configurer, mettre en fonction, vérifier que tout est vert, puis donner la main à l'utilisateur pour ajouter une ressource et lancer. »

**Périmètre :** cible W001 (Windows 11 x86-64 natif, sans WSL ni Docker), chaîne `bootstrap.ps1` / `rag.ps1` / `services/runtime`, artefacts et modèles verrouillés, session W011, licences de redistribution, voies de distribution (kit et scripts, Inno Setup, WiX, MSIX, Electron, Tauri, WinGet, Python embarqué). **Exclusions :** aucune lecture de `PDF/` ni du contenu de `.runtime/data` (taille seulement) ; aucune installation, aucun téléchargement de binaire, aucun service démarré ou arrêté ; aucune commande Git modifiante ; aucun avis juridique. **Méthode :** lecture du code et des documents cités avec fichier et ligne, mesures en lecture seule sur ce poste, pages officielles ouvertes le 30/09/2026 (§11). Chaque affirmation est marquée comme fait documentaire, observation locale, interprétation ou hypothèse à tester.

## 1. Synthèse

- **La distribution est faisable sans Electron ni Tauri.** La chaîne existante tourne déjà sans droits d'administration, sans modifier le PATH ni la politique d'exécution, et vérifie les artefacts par SHA-256. Il manque quatre éléments : une installation depuis un kit hors ligne (aujourd'hui `provision` exige Node, pnpm, Internet ou des archives en cache, et un Tesseract déjà installé), la séparation programme/données, la commande `open` prévue par W011 et un contrôle final qui exerce réellement la chaîne.
- **Taille mesurée :** recopier l'existant nécessaire donne un kit de 10,9 Gio non compressé et 12,1 Gio installés. Trois réductions, chacune soumise à test ou à décision (archives déjà extraites, bibliothèques CUDA/Vulkan inutiles en CPU, modèle Qwen source), ramènent le kit à 4,6 Gio. La taille compressée n'a pas été mesurée.
- **Constats structurants :** programme et données partagent la racine du dépôt (C01) ; `.venv` contient un chemin absolu (C02) ; le chemin de stockage Qdrant est limité à 57 caractères, ce qui contraint le dossier de données sous `%LOCALAPPDATA%` (C09) ; le port 11434 est celui d'un Ollama déjà installé (C10) ; readiness répond 503 sur une base vide, donc « tout vert » doit être défini (C13) ; Tesseract est une copie de poste, sans avis de licence, à la signature expirée (C05).
- **Recommandation :** construire d'abord l'option A (kit hors ligne et scripts, par utilisateur, données séparées, `install`/`open`/`selftest`/`uninstall`), qui est le socle de toutes les autres ; l'envelopper ensuite, si l'utilisateur le souhaite, dans un installateur Inno Setup par utilisateur (option B). Différer Electron et Tauri ; écarter MSIX et WinGet.
- **Licences :** les licences lues (Apache-2.0, MIT, CDLA-Permissive-2.0, PSF) n'interdisent pas une redistribution interne, mais leurs obligations d'avis ne sont pas remplies par le contenu actuel de `.runtime` (§6). Restent non lus : conditions NVIDIA des DLL CUDA, MPL-2.0, licences des 51 DLL du build Windows de Tesseract (Leptonica et bibliothèques tierces).

## 2. État actuel mesuré

### 2.1 Chaîne d'installation et d'exploitation

| Étape | Effet réel (code) | Réseau | Limite pour un autre poste |
|---|---|---|---|
| `.\bootstrap.ps1` | Télécharge l'archive uv 0.12.21 depuis GitHub et vérifie son SHA-256 (`bootstrap.ps1:12-16`) ; `uv python install 3.12.14 --install-dir .runtime/python --no-bin --no-registry` (`:40`) ; `uv sync --locked` (`:45`) | Oui, sauf `-Offline` qui exige `uv.exe` déjà présent (`:9`) | Installe le groupe `dev` (uv synchronise `dev` par défaut, [DST33]) |
| `.\rag.ps1 provision` | Nouveau `uv sync` (`cli.py:388-390`), `pnpm install --frozen-lockfile` (`:392-396`), artefacts verrouillés (`:397`), copie de Tesseract (`:399-400`), `pnpm run build` (`:403-404`), modèle Ollama (`:405-415`) | Oui, sauf `-Offline` | Exige pnpm dans le PATH (`:392-394`) et un Tesseract 5.4.0 installé (`provisioning.py:26-33`) ; en hors ligne, exige les archives ZIP en cache (`artifacts.py:85-88`) |
| `.\rag.ps1 pull-model` | Ollama temporaire sur 11444, `/api/pull`, dérivation du modèle texte (`cli.py:326-380`) | Oui, sauf `-Offline` | Dérivation : deux fois la taille du modèle source plus 2 Gio de disque (`cli.py:292-293`) |
| `.\rag.ps1 doctor` | Chemins, verrou des modèles, fichiers OCR, ports, marge d'admission, santé (`cli.py:122-230`) | Non | Déclare lui-même `qualification: NOT_RUN` (`cli.py:229`) |
| `.\rag.ps1 up` / `status` / `down` / `logs` | Superviseur détaché (`supervisor.py:443-447`), Job Object avec arrêt à la fermeture (`windows_process.py:72-75`), Qdrant, Ollama puis API | Non | Ports fixes du profil (`config/local16.yaml:5,13,128`) |
| `.\rag.ps1 backup` / `verify` / `restore` | Snapshot SQLite et Qdrant, restauration dans une racine neuve | Non | Sortie par défaut sous la racine du programme (`backup.py:141`) |
| `open` (W011) | Absente : ni dans `ValidateSet` (`rag.ps1:5`) ni dans le CLI (`cli.py:421`) | — | Le message d'erreur de l'API y renvoie déjà (`services/api/security.py:25`) |

### 2.2 Ce que `provision` récupère

| Composant | Version ou révision | Source | Taille publiée | Destination | Vérification | Licence déclarée au verrou |
|---|---|---|---|---|---|---|
| uv | 0.12.21 | release GitHub astral-sh/uv | 17 992 232 octets [DST54] | `.runtime/bootstrap/bin` | SHA-256 codé dans `bootstrap.ps1:15` | — (MIT ou Apache-2.0 [DST53]) |
| CPython | 3.12.14 (python-build-standalone) | via uv [DST35] | non relevée | `.runtime/python` | aucune empreinte propre dans le dépôt | — |
| Dépendances Python | `uv.lock` | PyPI et index PyTorch CPU (`pyproject.toml:33-39`) | — | `.venv` | hashes du verrou uv | inventaire [LOC-LIC] |
| Qdrant | 1.19.1 | release GitHub | 29 671 153 octets [DST43] | `.runtime/bin/qdrant-1.19.1` | SHA-256 (`config/artifacts.lock.json:5-16`) | Apache-2.0 |
| Ollama | 0.35.0 | release GitHub | 1 461 196 158 octets [DST40] | `.runtime/bin/ollama-0.35.0` | SHA-256 (`artifacts.lock.json:17-28`) | MIT |
| E5 multilingual small (ONNX int8, tokenizer) | révision `614241f6` | Hugging Face | 118 346 824 octets pour `model.onnx` | `.runtime/models/e5-small-int8` | SHA-256 ou SHA-1 de blob Git | MIT |
| Tokenizer, gabarit et licence Qwen3.5-4B | révision `851bf6e8` | Hugging Face | 12 807 982 octets pour `tokenizer.json` | `.runtime/models/qwen3.5-4b-tokenizer` | idem | Apache-2.0 |
| tessdata_fast fra, eng, osd et `configs/tsv` | commit `87416418`, Tesseract `1be261dc` | GitHub raw | 1 130 365 / 4 113 088 / 10 562 727 octets | `.runtime/models/tessdata` | SHA-1 de blob Git | Apache-2.0 |
| Docling Heron (mise en page) | révision `8f39ad3c` | Hugging Face | 171 658 996 octets | `.runtime/models/docling/…heron` | SHA-256 | apache-2.0 |
| Docling TableFormer accurate | révision `fc0f2d45` | Hugging Face | 212 758 388 octets | `.runtime/models/docling/…models` | SHA-256 | cdla-permissive-2.0 |
| Modèle Qwen3.5 4B Q4_K_M | manifeste `2a654d98…` | registre Ollama | couche modèle 3 389 971 840 octets (`config/models.lock.json:15`) ; « 3.4GB » affiché [DST52] | `.runtime/models/ollama` | digests Ollama, verrou `models.lock.json` | licence en couche : en-tête Apache 2.0 (`models.lock.json:19`) |
| Modèle texte seul dérivé | manifeste `de8024db…` | dérivé localement (W006) | couche 2 722 262 304 octets (`models.lock.json:29`) | idem | idem | même couche licence |
| Tesseract 5.4.0 Windows | `tesseract v5.4.0.20240606` | copie d'une installation existante du poste | — | `.runtime/bin/tesseract-5.4.0` | SHA-256 par fichier au manifeste local | provenance non authentifiée (OCR03) |
| Interface | Next.js 16.3.7, export statique | build local | — | `apps/web/out` | manifeste d'export | inventaire npm [LOC-LIC] |

### 2.3 Volumétrie mesurée sur ce poste

Mesure du 30/09/2026 vers 17:45 UTC, `Get-ChildItem -LiteralPath <dossier> -Recurse -Force -File | Measure-Object Length -Sum`, en Mio (1 048 576 octets). PowerShell 5.1 ne suit pas la jonction `.runtime/python/cpython-3.12-windows-x86_64-none` (cible absolue vers le dossier `3.12.14`), comptée une seule fois. `.runtime/data` : taille seulement, contenu non ouvert.

| Dossier | Taille | Fichiers | Rôle pour une distribution |
|---|---:|---:|---|
| `.runtime/bin` | 2 081,6 | 135 | Exécution. Dont Ollama 1 840,8 (bibliothèques `cuda_v12` 1 104,4, `cuda_v13` 631,7, `vulkan` 41,7), Tesseract 159,7 (52 fichiers), Qdrant 81,1 (`qdrant.exe` seul) |
| `.runtime/models` | 6 470,7 | 45 | Exécution. Dont stockage Ollama 5 829,1 (source 3 232,9 et texte 2 596,2), Docling 366,6, E5 129,6, Granite 117,9 (comparatif de développement, D-04), tokenizer Qwen 12,3, tessdata 15,1 |
| `.runtime/python` | 62,9 | 3 464 | Exécution |
| `.runtime/bootstrap` | 41,9 | 18 | Installation (uv 41,1 et ses licences) |
| `.runtime/cache` | 2 743,6 | 33 047 | Dont archives ZIP 1 421,8 (utiles au mode hors ligne actuel seulement), cache uv 1 186,0 (installation hors ligne), mypy 117,8 et pip 17,9 (développement) |
| `.runtime/manifests` | 0,1 | 5 | Exécution et vérification |
| `.runtime/data` | 1 214,9 | 324 | Données de l'utilisateur de ce poste, jamais distribuées |
| `.runtime/q`, `qstores`, `qa`, `rt-qkey-*`, `qtest`, `cpu-pilot`, `references*` | 1 655,5 / 236,5 / 2 108,8 / 1,8 / 0,0 / 0,0 / 1,1 | — | Essais, recette et références : exclus |
| Autres (`model-metadata`, `reference-baseline-v1`, `provision-service`, `control`) | 2,4 | 23 | Rôle de `model-metadata` non examiné ; exclus sauf besoin établi |
| `.venv` | 1 246,4 | 36 817 | Recréé à l'installation. Dont torch 474,3, cv2 112,4, scipy 88,6 ; outils de développement ≈ 56 (ruff.exe 25,2, faker 9,6, mypy 9,1, reportlab 5,9, mypyc 3,6, _pytest 2,8) |
| `apps/web/out` | 6,4 | 278 | Exécution (interface) |
| `apps/web/node_modules`, `apps/web/.next` | 479,7 / 134,4 | — | Build seulement |
| Code et configuration (`services`, `tools`, `config`, `packages`, `uv.lock`) | ≈ 0,9 | — | Exécution |
| `backups` | 237,5 | 24 | Données de ce poste : exclues |

### 2.4 Dépendances au poste

| Dépendance | Preuve | Conséquence ailleurs |
|---|---|---|
| Racine unique déduite de l'emplacement du code | `ROOT = Path(__file__).resolve().parents[2]` (`services/runtime/artifacts.py:17`) ; même principe dans `services/api/settings.py:18` | Tout chemin relatif du profil est résolu sous le dossier du programme |
| Données sous le programme par défaut | `app.data_dir: .runtime/data` (`config/local16.yaml:7`), `data_path()` (`supervisor.py:43`) | Surchargeable par un chemin absolu ou `RAG_DATA_DIR` (`settings.py:37-43`) |
| Écritures d'exécution sous le programme | verrou lourd `.runtime/control/host-heavy.lock` (`services/runtime/resources.py:21`) ; sauvegardes `backups/` (`backup.py:141`) ; stockages de restauration `.runtime/q/` (`backup.py:269`) ; `HF_HOME` et `OLLAMA_MODELS` (`supervisor.py:128,134`) | Le dossier du programme doit rester inscriptible |
| Chemins absolus figés | `.venv/pyvenv.cfg` : `home = D:\enhacements\agentragpdf\.runtime\python\cpython-3.12-windows-x86_64-none` (observé) ; jonction de `.runtime/python` à cible absolue (observé) ; manifeste Tesseract `source = C:\Users\P47599\AppData\Local\Programs\Tesseract-OCR` (observé, écrit par `provisioning.py:50-52`) ; profils restaurés (`backup.py:298`) | `.venv` à recréer ; le manifeste Tesseract divulgue un nom d'utilisateur du poste de fabrication |
| Droits administrateur | Aucun requis par le code ; exécution non administrateur constatée (journal du 30/09, ligne 77) | Compatible avec une installation par utilisateur |
| PATH | `pnpm.cmd` (`cli.py:392`), `node.exe`/`pnpm.cmd` pour doctor (`cli.py:185`), `tesseract.exe` (`provisioning.py:26`), `git` (`source_manifest.py:28`) ; aucun PATH modifié | Sur un poste sans Node ni Tesseract, `provision` échoue |
| Variables globales | Aucune écrite ; environnement des enfants construit explicitement (`supervisor.py:117-140`) | Sans effet |
| Réseau après installation | Aucun pour `up`, `doctor`, `status`, `down`, `backup`, `verify`, `restore` (README §8) ; blocage système D08.1 non réalisé | Conforme au hors ligne ; D08.1 reste une décision |
| Ports | 8785, 6333, 11434 (`local16.yaml:5,13,128`) ; refus si occupé (`supervisor.py:63-69`) | Conflit probable avec un Ollama déjà installé (C10) |
| Longueur de chemin | `…\qdrant\storage` ≤ 57 caractères (`supervisor.py:193-194`, W004) ; `LongPathsEnabled = 0` (observé) | Contraint le dossier de données (C09) |
| Politique d'exécution | `Get-ExecutionPolicy -List` : MachinePolicy et UserPolicy `Undefined`, CurrentUser `RemoteSigned` (observé) ; scripts non signés | Dépend de la stratégie de groupe du poste cible (§4.1) |
| Fichiers du dossier de chantier | Configuration de collection lue dans `RAG_Local_Agents/config/qdrant.collection.json` faute de `config/qdrant.collection.json` (`services/api/retrieval.py:138-140`, fichier `config/` absent observé) | Le kit ne peut pas omettre ce fichier |

### 2.5 Import des documents de l'utilisateur aujourd'hui

- **Interface :** bouton d'import de PDF multiples et import d'un dossier entier (`webkitdirectory`, `apps/web/src/components/library-panel.tsx:123-124`) ; les chemins relatifs sont envoyés avec les fichiers à `POST /api/v1/documents/import` (`apps/web/src/lib/api.ts:63-65`) et forment l'arborescence de la bibliothèque. L'original est copié dans `originals/<sha256>.pdf` de la racine de données ; le dossier source n'est ni modifié ni déplacé (README §1). Limites du profil : 200 Mio par fichier, 2 000 pages.
- **Outil :** `tools/corpus/import_folder.py --source <dossier> --output <rapport-neuf>` envoie chaque PDF à la même route, du plus petit au plus grand, et refuse d'écrire son rapport dans le dépôt hors `.runtime/` (`import_folder.py:76-77`). Il envoie seulement un en-tête `Origin` (`:39-46`) : après activation de W011, qui refuse par défaut toute route hors session ou jeton de contrôle (`services/api/main.py:33,124-142`), il recevra un refus tant qu'il ne présente pas `x-rag-control-token` (déduction du code, non exécutée).

### 2.6 Session W011

L'API est prête (W011, tests in-process PASS) ; le lanceur ne l'est pas. Tout moyen d'ouverture doit : lire `control/admin-token` de la racine de données du profil (écrit par `supervisor.py:337-338`, supprimé à l'arrêt `:423`), appeler `POST /api/v1/admin/session-links` avec l'en-tête `x-rag-control-token` (`main.py:124-126,230-233`), puis ouvrir `http://127.0.0.1:<port>` suivi du chemin reçu dans les 300 secondes par défaut (`security.py:50`). Un script, un raccourci, la dernière étape d'un installateur ou une coquille Electron/Tauri se branchent tous sur ce même appel.

### 2.7 Signatures et environnement observés

| Élément | Observation (`Get-AuthenticodeSignature`, registre en lecture) |
|---|---|
| `ollama.exe`, `lib/ollama/libllama.dll`, `cuda_v12/cudart64_12.dll` | Signature valide, sujet « Ollama Inc. » |
| `uv.exe` 0.12.21 | Signature valide, sujet « OpenAI OpCo, LLC » |
| `qdrant.exe` 1.19.1 | Non signé |
| `python.exe` (python-build-standalone) et `.venv\Scripts\python.exe` | Non signés |
| `tesseract.exe` 5.4.0 | Signature invalide : certificat « Universität Mannheim » expiré le 2023-12-09 |
| WebView2 Evergreen | Présent, `pv = 154.0.4258.37` sous `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` (clé documentée [DST29]) |
| `winget.exe` | Introuvable dans le PATH de la session (`Get-Command`) |
| PowerShell | 5.1.22621.4391 ; Windows 11 Enterprise 10.0.22631 |

## 3. Constats

Types : **B** bug, **I** incohérence, **A** amélioration, **U** inconnue. « Prouvé » renvoie à une ligne de code, une observation ou une source lue ; « hypothèse » reste à tester.

| ID | Type | Constat et preuve | Impact | Correction envisagée |
|---|---|---|---|---|
| C01 | I | Programme et données partagent la racine du dépôt ; plusieurs écritures d'exécution visent cette racine (§2.4). Prouvé | Une mise à jour qui remplace le dossier programme peut emporter les données du profil par défaut ; un dossier programme en lecture seule (MSIX, `Program Files`) est incompatible | Profil par utilisateur généré à l'installation avec `app.data_dir` absolu ; déplacer vers la zone de données le verrou lourd, les sauvegardes par défaut et les stockages de restauration ; installer `qdrant.collection.json` dans `config/` |
| C02 | B | `.venv` non déplaçable (`pyvenv.cfg` à chemin absolu, observé) alors que `rag.ps1:17-20` l'exige. Prouvé | Copier une installation ailleurs casse le lanceur | Recréer `.venv` à l'installation : `uv sync --offline --locked --no-dev` (options présentes dans `uv sync --help` de la version 0.12.21, observé). `uv venv --relocatable` existe dans cette version (observé), mais son effet sur `home` n'est établi par aucune source lue : non retenu |
| C03 | I | Groupe `dev` installé par `bootstrap.ps1:45` et `cli.py:388` ; uv le synchronise par défaut [DST33]. Prouvé | ≈ 56 Mio et des outils de développement dans le produit ; 126 distributions à couvrir par les avis au lieu du seul runtime | `--no-dev` en mode installation |
| C04 | I | Le poste cible devrait avoir Node 22.17.0 et pnpm 10.34.1 pour `provision` (`cli.py:391-404`, README §9). Prouvé | Prérequis inutile : l'export statique fait 6,4 Mio | Livrer `apps/web/out` vérifié ; ne lancer ni pnpm ni build à l'installation ; livrer aussi `apps/web/pnpm-lock.yaml`, exigé par doctor (`cli.py:170`), ou adapter ce contrôle |
| C05 | I | Tesseract : aucun téléchargement prévu, recherche d'une installation locale (`provisioning.py:26-33`) ; la copie existante et son manifeste sont réutilisables (`:17-23`), mais le manifeste contient le chemin du poste de fabrication, aucune licence n'a été copiée (0 fichier sur 52, observé), la signature est invalide (§2.7) et la provenance reste non authentifiée (OCR03). Prouvé | Sans le kit, le poste cible doit installer Tesseract lui-même ; avec le kit, avis de licence manquants et exécutable dont la signature ne se vérifie pas | Livrer la copie et son manifeste nettoyé ; établir les licences des DLL tierces ; décider de conserver 5.4.0 ou de requalifier un build actuel (UB Mannheim publie 5.5.3.20260724 [DST45]) |
| C06 | I | Le hors ligne actuel exige les ZIP en cache puis réextrait (`artifacts.py:85-88,152-153`) : 1 421,8 Mio d'archives en plus des 2 081,6 Mio extraits. Prouvé | Kit alourdi de 1,4 Gio | Vérifier les fichiers extraits contre `.runtime/manifests/artifacts.json`, qui conserve déjà un SHA-256 par fichier (`artifacts.py:137`) ; `native_paths()` le fait déjà pour `qdrant.exe` et `ollama.exe` (`supervisor.py:166-185`) |
| C07 | A | L'archive Ollama embarque CUDA 12, CUDA 13 et Vulkan (1 777,8 Mio) ; la documentation la décrit comme la CLI avec les dépendances GPU NVIDIA [DST39] ; le profil impose le CPU (`num_gpu: 0`, refus sinon dans `load_profile`). Hypothèse H1 : Ollama démarre et génère sans ces dossiers | −1,7 Gio ; les conditions NVIDIA ne s'appliqueraient plus au kit | Tester H1 ; si PASS et décision P3, ne livrer que les fichiers requis, hachés au manifeste du kit |
| C08 | A | Modèle source Qwen (3 232,9 Mio) conservé pour la reproductibilité (W006) et exigé par doctor (`models.lock.json:8-21`, `cli.py:82-104`). Prouvé | −3,2 Gio possibles | Décision P2 ; si le source est retiré, verrou et doctor distinguent « source non livrée » d'un défaut |
| C09 | I | `…\qdrant\storage` ≤ 57 caractères (`supervisor.py:193-194`). Sous `%LOCALAPPDATA%`, `C:\Users\<u>\AppData\Local\<X>\storage` fait 32 + len(u) + len(X) caractères : il faut len(u) + len(X) ≤ 25. Avec `X = AtelierPDF\q` (12), le dossier de profil doit faire au plus 13 caractères ; avec `X = adp\q` (5), au plus 20. Prouvé (arithmétique sur le code) | Un emplacement « naturel » dépasse la borne pour la plupart des profils | `qdrant.storage_dir` court calculé à l'installation et vérifié avant copie ; doctor le refuse déjà |
| C10 | I | Ports fixes ; 11434 est le port par défaut d'Ollama [DST39] ; `up` refuse un port occupé sans rien arrêter (`supervisor.py:63-69`). Prouvé | Échec de `up` sur tout poste où Ollama tourne déjà | Ports choisis libres à l'installation, écrits dans le profil généré, contrôlés par doctor |
| C11 | I | Pas de commande `open` (`rag.ps1:5`, `cli.py:421`) ; `import_folder.py` sans jeton (`:39-46`). Prouvé | Après W011, pas de parcours de lancement pour l'utilisateur ; l'import en ligne de commande sera refusé | Lot W011 en cours ; prérequis DIST-01 |
| C12 | I | Configuration de collection dans le dossier du chantier (`retrieval.py:138-140`) ; repli du profil sur `RAG_Local_Agents/config/local16.yaml` (`settings.py:20-21`). Prouvé | Un kit sans `RAG_Local_Agents/` casse la première indexation | Déplacer le fichier sous `config/` avec le reste du contrat de profil |
| C13 | I | Readiness répond 503 sur une base vide tant que la collection n'existe pas (`EXPLOITATION_WINDOWS.md`, section Disponibilité et sécurité). Prouvé | « Tout est vert » inatteignable juste après l'installation | Définir l'état attendu « base vide, prête à importer » dans le verdict, ou créer la collection vide à l'installation ; le contrôle réel passe par une racine temporaire (DIST-05) |
| C14 | U | À chaque `up`, `source_manifest.capture()` hache `tests/`, `RAG_Local_Agents/*.md`, etc., et interroge `git` s'il existe (`source_manifest.py:15-22,28,59-67`). Comportement sans ces dossiers et sans Git non testé (hypothèse H3) | Démarrage éventuellement refusé ou identité de source incomplète dans un kit | Tester H3 ; définir l'identité de source d'une version livrée (manifeste du kit) |
| C15 | U | `qdrant.exe` et `python.exe` non signés, `tesseract.exe` à signature invalide (§2.7) ; SmartScreen, Smart App Control et AppLocker peuvent bloquer ou avertir selon la politique [DST16, DST17]. État de Smart App Control sur ce poste non interprété | Blocage possible sur un parc géré | Obtenir la politique du parc (P4) ; signer ce qui relève du projet ; ne pas modifier les binaires officiels |
| C16 | I | Avis de licence manquants dans les artefacts livrés (§6). Prouvé | Obligations d'avis non satisfaites à la redistribution | Dossier `LICENSES/` et `THIRD_PARTY_NOTICES` générés par le constructeur de kit (DIST-07) |
| C17 | U | Dépendance à un Visual C++ Redistributable système : `vcruntime140*.dll` présents dans le Python géré, `msvcp140*.dll` seulement dans `cuda_v12` d'Ollama (observé) ; besoin des roues torch, onnxruntime et opencv non établi (hypothèse H4) | Échec possible sur un poste vierge, surtout si C07 retire `cuda_v12` | Test sur poste ou compte vierge (DIST-10) |

## 4. Options de distribution

### 4.1 A. Kit hors ligne et scripts PowerShell

**Principe :** un dossier ou une archive `AtelierPDF-<version>` contenant le code, l'interface construite, uv, CPython, les roues Python du runtime, les binaires et modèles déjà vérifiés, les manifestes, les licences et un `SHA256SUMS` du kit. Un `install.cmd` à double-cliquer appelle `powershell.exe -NoProfile -ExecutionPolicy Bypass -File install.ps1`, qui copie vers le dossier programme de l'utilisateur, recrée `.venv`, vérifie, génère le profil, lance doctor et le contrôle réel, crée les raccourcis puis ouvre l'atelier.

- **Politique d'exécution :** `-ExecutionPolicy` fixe la politique de la session sans toucher au registre [DST01] ; la portée `Process` prime sur `CurrentUser` et `LocalMachine`, mais pas sur une stratégie de groupe, qui l'emporte dans toutes les portées [DST02]. Conforme à la règle « ne pas modifier la politique d'exécution » (`EXPLOITATION_WINDOWS.md`). Si le parc impose `AllSigned` par GPO, les scripts doivent être signés.
- **Marque de zone :** un fichier téléchargé par navigateur reçoit un flux `Zone.Identifier` et `RemoteSigned` bloque alors un script non signé ; `Unblock-File` retire ce flux [DST02, DST03]. `Bypass` et `AllSigned` ne demandent pas de contrôle de zone [DST02]. Les fichiers extraits d'une archive marquée peuvent l'être aussi (hypothèse H5, non sourcée ici).
- **Usage quotidien sans PowerShell :** `rag.ps1` ne fait qu'appeler `.venv\Scripts\python.exe -m services.runtime.cli` (`rag.ps1:26-36`). Un raccourci peut donc viser directement `pythonw.exe -m services.runtime.cli open --profile <profil>` et ne plus dépendre de la politique PowerShell ; il dépend alors d'AppLocker ou d'App Control pour un `python.exe` non signé [DST17].
- **Emplacements par utilisateur :** programme sous `%LOCALAPPDATA%\Programs` (FOLDERID_UserProgramFiles), raccourcis sous `%APPDATA%\Microsoft\Windows\Start Menu\Programs` (FOLDERID_Programs) [DST04].
- **Désinstallation et mise à jour :** à écrire (`uninstall`, `update`) ; aucune entrée « Applications installées ».
- **Compatibilité :** aucune modification du superviseur, des Job Objects ni de W011 ; réutilise les manifestes SHA-256 existants.

### 4.2 B. Installateur Inno Setup par utilisateur (enveloppe de A)

- `PrivilegesRequired=lowest` : l'installateur ne demande jamais l'élévation et fonctionne en mode non administrateur [DST05] ; dans ce mode, les clés d'installation et de désinstallation vont sous `HKEY_CURRENT_USER` et le groupe du menu Démarrer dans le profil [DST06] ; `{autopf}` devient le dossier Program Files de l'utilisateur, `{userprograms}` le menu Démarrer de l'utilisateur [DST07].
- Au-delà de 4 200 000 000 octets compressés, `DiskSpanning=yes` est obligatoire et produit `Setup.exe` plus des fichiers `Setup-*.bin` [DST08] ; probable avec le kit complet (10,9 Gio non compressés), à mesurer pour le kit réduit.
- Le désinstalleur ne supprime par défaut que ce que l'installation a créé ; `[UninstallDelete]` sert aux fichiers créés ensuite [DST09]. `.venv`, créé après la copie, doit y figurer ; les données, hors de `{app}`, restent.
- `SignTool` signe l'installateur et le désinstalleur [DST10]. Licence d'Inno Setup : usage commercial permis, avis de copyright et adresses conservés dans les binaires [DST11].
- Mise à jour : réinstallation de la même application ; l'étape finale lance le même script que A (mécanisme `[Run]` non lu ici).

### 4.3 C. WiX Toolset (MSI)

La page du mainteneur indique que WiX v3, v4 et v5 sont hors support communautaire [DST12] ; le dépôt conditionne l'usage au paiement de l'« Open Source Maintenance Fee » pour qui en tire un revenu [DST13]. La prise en charge d'une installation MSI par utilisateur et les limites de taille des cabinets n'ont pas été lues. Le maker WiX d'Electron Forge exige WiX v3 [DST21], hors support. Aucun avantage identifié sur B pour ce besoin : écarté.

### 4.4 D. MSIX

Installation par utilisateur, fichiers du paquet en lecture seule et verrouillés ; pour une application virtualisée, les nouveaux fichiers sous `AppData` sont redirigés vers un emplacement privé supprimé à la désinstallation [DST14]. Le paquet doit être signé par un certificat chaîné à une racine de confiance du poste [DST15]. Incompatibilités : dossier programme non inscriptible (C01), risque de perte de données à la désinstallation si elles restent dans `AppData` redirigé, certificat à distribuer. Comportement des Job Objects dans ce conteneur non établi. Écarté.

### 4.5 E. Electron

- **Apports :** fenêtre dédiée sans navigateur, cycle de vie lié à la fenêtre (le superviseur deviendrait un enfant ; les Job Objects imbriqués existent depuis Windows 8 [DST30], compatibilité à tester), accès direct au lien W011.
- **Coûts :** archive Windows x64 de la v44.5.1 publiée le 30/09/2026 : 157 998 329 octets [DST23], soit un Chromium et un Node en plus, à maintenir à jour [DST18] ; bonnes pratiques à tenir (isolation de contexte par défaut depuis 12.0.0, bac à sable depuis 20.0.0, pas d'intégration Node pour un contenu distant, validation de la navigation) [DST18] ; le service de mise à jour `update.electronjs.org` exige un dépôt GitHub public [DST20], ce qui exclut ce dépôt privé ; installation Squirrel sans droits [DST21] ; signature pour SmartScreen [DST16, DST19]. Consommation mémoire d'un Chromium supplémentaire sur un poste où la génération demande 4 992 Mio libres : non mesurée.
- **Verdict :** différé. N'apporte rien aux points durs (kit hors ligne, séparation des données, intégrité, licences) et ajoute une base de code et un runtime à suivre.

### 4.6 F. Tauri

- **Apports :** utilise WebView2, inclus dans Windows 11 selon Microsoft [DST29] et présent sur ce poste (§2.7) ; binaires externes livrés comme sidecars nommés avec le suffixe du triplet cible, lancés par le plugin shell avec permissions explicites [DST25] ; installateur NSIS `currentUser` sans droits d'administrateur, sous `%LOCALAPPDATA%` [DST26].
- **Coûts :** chaîne Rust et Microsoft C++ Build Tools sur le poste de fabrication [DST27] ; nouvelle base de code ; WebView2 embarqué si nécessaire : ≈ 127 Mo (installateur hors ligne) ou ≈ 180 Mo (version fixe) selon Tauri [DST26], plus de 250 Mo de binaires pour la version fixe selon Microsoft [DST29] ; limites de taille de NSIS pour des gigaoctets de ressources non lues ; mécanisme de mise à jour non évalué.
- **Verdict :** différé ; premier choix si une fenêtre dédiée devient une exigence.

### 4.7 G. WinGet

Un manifeste exige une URL d'installateur et son SHA-256 [DST32] ; ajouter une source demande des droits d'administrateur [DST31] ; le dépôt communautaire est public. Sans intérêt pour un produit interne distribué hors ligne ; `winget.exe` est introuvable dans la session de ce poste (§2.7). Écarté. La page Microsoft sur les dépôts privés n'a pas pu être ouverte (§12).

### 4.8 Autres moyens examinés

- **Paquet Python embarquable officiel :** prévu pour être intégré à une application, sans pip ; les paquets tiers doivent être installés par l'installateur de l'application [DST37]. Aucun gain sur le CPython géré par uv déjà utilisé.
- **CPython géré par uv :** distributions python-build-standalone d'Astral, enregistrées par défaut dans le registre Windows selon PEP 514 [DST35] ; `bootstrap.ps1:40` l'évite avec `--no-registry` et `--no-bin` (options présentes dans uv 0.12.21, observé). À conserver.
- **Installation de `.venv` hors ligne :** `--offline`, `--find-links`, `--no-index`, `--no-dev`, `--locked`, `--compile-bytecode` existent dans `uv sync` 0.12.21 (observé) ; `uv sync` est exact par défaut et retire les paquets hors verrou [DST33].
- **Outil de télédistribution de l'entreprise :** hors périmètre, non évalué ; le kit A et l'installateur B restent compatibles avec une installation silencieuse (`/SILENT` ou `/VERYSILENT` pour Inno Setup [DST32]).

### 4.9 Matrice comparative

| Critère | A. Kit + scripts | B. Inno Setup | C. WiX/MSI | D. MSIX | E. Electron | F. Tauri | G. WinGet |
|---|---|---|---|---|---|---|---|
| Prérequis du poste | Windows 11 x64, PowerShell 5.1, 16 Gio (D-01) | idem A | idem A | idem + certificat de confiance | idem A | idem A + WebView2 (présent sur Windows 11) | `winget` et une source |
| Droits admin | Non (chaîne actuelle exécutée sans) | Non (`lowest`) | Non établi | Non pour le paquet ; certificat à faire approuver | Non (Squirrel) | Non (NSIS `currentUser`) | Oui pour `source add` |
| Taille ajoutée au kit | 0 | exécutable d'installation, découpage au-delà de 4,2 Go | non mesurée | non mesurée | ≈ 158 Mo publiés | 0 à ≈ 180 Mo selon mode WebView2 | 0 |
| Hors ligne | Oui | Oui | Oui | Oui | Oui ; mises à jour à héberger | Oui | Non (installateur par URL) |
| Mise à jour | Script côte à côte | Réinstallation | Mise à niveau MSI | Native | Squirrel ou serveur privé | Non évaluée | `winget upgrade` |
| Désinstallation | Script | Entrée système, fichiers installés seulement | MSI | Paquet et `AppData` redirigé supprimés | Squirrel | NSIS | Via l'installateur |
| Données conservées | Oui, dossier séparé | Oui si hors `{app}` | Oui si hors dossier | Risque de perte | Oui si hors dossier | Oui si hors dossier | Selon l'installateur |
| Signature et SmartScreen | `.ps1` non signés, `Bypass` par processus ; GPO prioritaire | `setup.exe` signable | Signable | Signature obligatoire | Signature recommandée | Signable | SHA-256 obligatoire |
| Intégrité SHA-256 | Manifestes existants + `SHA256SUMS` du kit | idem (script A) | idem | + intégrité du paquet | idem | idem | + hash d'installateur |
| Superviseur, Job Objects, écritures | Inchangés | Inchangés | Selon dossier | Dossier en lecture seule : refonte | Superviseur enfant, imbrication à tester | Sidecar, imbrication à tester | Sans effet |
| W011 | `open` puis navigateur par défaut | Étape finale `open` | idem | idem | Lien chargé dans la fenêtre | idem | Sans effet |
| Effort | Faible à moyen | Moyen (A + script `.iss`) | Moyen à élevé | Élevé | Élevé | Élevé | Moyen + hébergement |
| Verdict | **Socle retenu** | **Étape 2 facultative** | Écarté | Écarté | Différé | Différé | Écarté |

## 5. Tailles estimées

Sommes de mesures du §2.3, en Mio, non compressées. Les réductions S2 dépendent de H1 (CUDA), P2 (modèle source) et C06 (archives).

| Scénario | Calcul | Total |
|---|---|---:|
| S1 : kit recopiant l'existant nécessaire | bin 2 081,6 + modèles hors Granite 6 352,7 + Python 62,9 + uv 41,9 + manifestes 0,1 + interface 6,4 + code 0,9 + cache uv 1 186,0 + archives 1 421,8 | 11 154,3 (10,9 Gio) |
| S1 installé | S1 + `.venv` 1 246,4 | 12 400,7 (12,1 Gio) |
| S2 : kit réduit | S1 − archives 1 421,8 − CUDA et Vulkan 1 777,8 − modèle source 3 232,9 | 4 721,8 (4,6 Gio) |
| S2 installé | S2 + `.venv` sans outils de développement ≈ 1 190 ; −1 186 si le cache uv est supprimé après installation | ≈ 5 912 ou ≈ 4 726 |

À ajouter : les données de l'utilisateur (originaux, extractions, index ; 1 214,9 Mio sur ce poste pour l'import en cours, non généralisable) et, par option, le runtime de la coquille (§4.9). Le cache uv mesuré contient aussi les roues de développement ; un cache fabriqué avec `--no-dev` sera plus petit, taille non mesurée.

## 6. Licences de redistribution

La licence déclarée au verrou est recoupée avec la source officielle lue ; « Dans le kit actuel » décrit les fichiers présents sous `.runtime` ou `apps/web/out`. L'inventaire existant (`reports/licenses-2026-09-30-prerequisites.json`, [LOC-LIC]) recense 126 distributions Python, 71 paquets npm, 26 artefacts, 18 avis natifs et trois runtimes ; il précise lui-même ne pas être un avis de compatibilité ni de redistribution. Ce tableau n'en est pas un non plus.

| Composant | Licence (source lue) | Ce qu'elle permet pour une redistribution interne | Obligations principales | Dans le kit actuel | Manque |
|---|---|---|---|---|---|
| Qdrant 1.19.1 | Apache-2.0, « Copyright 2026 Qdrant Solutions GmbH » [DST42] | Redistribution sous conditions de la section 4 [DST46] | Joindre la licence ; conserver les avis ; NOTICE s'il existe | `qdrant.exe` seul ; la release n'a aucun fichier de licence [DST43] | Texte de licence de la version ; avis des dépendances Rust : inconnus |
| Ollama 0.35.0 | MIT, « Copyright (c) Ollama » [DST41] | Copie, distribution | Inclure l'avis de copyright et de permission dans toute copie [DST41] | 16 avis tiers sous `lib/ollama` [LOC-LIC] ; pas de licence d'Ollama | `LICENSE` d'Ollama ; conditions NVIDIA des DLL CUDA non lues (inutile si C07 validé) |
| Tesseract 5.4.0 | Apache-2.0 [DST44] | Comme Qdrant | Licence ; avis | 52 fichiers, aucun avis ; 51 DLL, dont `libtesseract` et Leptonica, les autres tierces d'après leurs noms (ICU, OpenSSL, GLib, Pango, Cairo, HarfBuzz, libarchive, etc.) | Licences des DLL tierces du build UB Mannheim non établies ; provenance non authentifiée |
| tessdata_fast fra/eng/osd, `configs/tsv` | Apache-2.0 (fichier `LICENSE` du commit verrouillé) | idem | Licence | `LICENSE` provisionné | — |
| E5 multilingual small | MIT (`license: mit` dans la fiche à la révision verrouillée, ligne 97 du README local) | Copie, distribution | Avis de copyright et de permission | Fiche `README.md` provisionnée ; aucun fichier `LICENSE` dans le dépôt à cette révision [DST51] | Titulaire du copyright non établi |
| Qwen3.5-4B (tokenizer, gabarit, poids GGUF via Ollama) | Apache-2.0 (fiche [DST48], `LICENSE` provisionné, couche licence Ollama) | Redistribution, y compris d'une œuvre modifiée | Licence ; fichiers modifiés porteurs d'une mention de modification (§4 b) [DST46] | `LICENSE` provisionné ; couche licence dans le stockage Ollama | Mention de modification pour le modèle texte dérivé (retrait des tenseurs `v.*` et `mm.*`, W006) |
| Docling Heron | Apache-2.0 (fiche [DST49] et README verrouillé) | idem | Licence | README ; pas de `LICENSE` dans le dépôt [DST51] | Texte Apache-2.0 à joindre |
| Docling TableFormer (`docling-models`) | CDLA-Permissive-2.0 (README à la révision verrouillée ; la fiche actuelle affiche aussi apache-2.0 [DST50]) | Partage des données, modifiées ou non | Mettre à disposition le texte de l'accord avec les données (§2.1) ; aucune restriction sur les résultats (§3.1) [DST47] | README ; pas de `LICENSE` [DST51] | Texte CDLA-Permissive-2.0 à joindre |
| uv 0.12.21 | MIT ou Apache-2.0 au choix [DST53] | Distribution | Licence choisie | `LICENSE-MIT` et `LICENSE-APACHE` dans `.runtime/bootstrap/uv-0.12.21.dist-info` | — |
| CPython 3.12.14 (python-build-standalone) | PSF ; composants tiers listés [DST38] ; GPL évitée par le distributeur (libedit, `_gdbm` désactivé) [DST36] | Distribution | Conserver l'accord de licence et l'avis PSF [DST38] | `LICENSE.txt` (25 066 octets), avis Tcl/Tk ; pas de `PYTHON.json` dans l'archive `install_only` (observé) | Présence des textes de toutes les bibliothèques liées statiquement : non établie |
| Paquets Python du runtime | Inventaire : majorité MIT, BSD, Apache-2.0 ; MPL-2.0 pour certifi, pathspec, tqdm [LOC-LIC] | Selon chaque licence | Avis par paquet | Avis recensés dans l'inventaire | Obligations MPL-2.0 non lues ; inventaire à rejouer sur le runtime sans `dev` |
| Interface (`apps/web/out`) | pdfjs-dist Apache-2.0 ; React, Next.js, TanStack Query, Zustand, Radix, clsx, tailwind-merge MIT ; lucide-react ISC ; @swc/helpers, class-variance-authority Apache-2.0 [LOC-LIC] | Distribution | Avis de chaque paquet inclus dans le bundle | 11 fichiers de licence PDF.js sous `out/pdfjs` ; aucun autre avis (observé) | Avis MIT, ISC et Apache des paquets regroupés dans les scripts `_next` |
| Outils de build npm (sharp LGPL-3.0-or-later, lightningcss MPL-2.0, Playwright) | [LOC-LIC] | — | — | Hors `out/` (dossiers observés : `404`, `pdfjs`, `workspace`, `_next`, `_not-found`) | Absence à confirmer par l'inventaire du kit |
| Node.js | Non lu | — | — | Non livré dans A et B | Sans objet si non embarqué |
| Electron (si retenu) | MIT, « Copyright (c) Electron contributors », « Copyright (c) 2013-2020 GitHub Inc. » [DST24] | Distribution | Avis MIT ; avis Chromium et Node | — | Avis Chromium non vérifiés |
| Tauri (si retenu) | MIT ou MIT/Apache 2.0 selon le code [DST28] | Distribution | Avis | — | Licence du runtime WebView2 non lue (non redistribué s'il est déjà présent) |
| Inno Setup (si retenu) | Licence propre : usage commercial permis ; avis et adresses conservés dans les binaires [DST11] | Distribution de l'installateur | Ne pas retirer les avis | — | — |
| WiX (écarté) | Maintenance Fee pour un usage générant un revenu [DST13] ; `LICENSE.TXT` non lu | — | — | — | — |

## 7. Parcours cible

### 7.1 Du poste vierge à la première question

| # | Étape | Action de l'utilisateur | Automatisme et contrôle | Message proposé (échec) | Reprise |
|---|---|---|---|---|---|
| 0 | Fabrication du kit (poste de fabrication, réseau autorisé) | — | `build_kit` : liste blanche, exclusions (`PDF/`, `.runtime/data`, essais, sauvegardes, `node_modules`, Granite), vérification des manifestes, `SHA256SUMS`, licences | — | Refabrication à l'identique |
| 1 | Transfert | Copier le dossier depuis le partage ou le support prévu (P1) | — | — | — |
| 2 | Lancement | Double-clic sur `Installer l'atelier.cmd` (ou `setup.exe` en option B) | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File install.ps1` | « Les scripts sont bloqués par une stratégie de groupe de ce poste (AllSigned). Contactez l'administrateur ; rien n'a été installé. » | Relancer après décision |
| 3 | Prérequis, sans rien modifier | — | Windows 11 x64, PowerShell 5.1, mémoire physique ≥ 16 Gio, espace disque (taille installée + 2 Gio), longueur du chemin Qdrant (C09), ports libres (C10) | « Ce poste a 8 Gio de mémoire physique ; l'atelier en demande 16. Installation arrêtée, aucun fichier copié. » | Aucune trace laissée |
| 4 | Intégrité du kit | — | `SHA256SUMS` du kit, manifestes d'artefacts, `models.lock.json`, manifeste Tesseract | « Fichier altéré : models/ollama/blobs/sha256-79b5… (empreinte différente). Recopiez le kit. » | Relance idempotente |
| 5 | Copie | — | Programme vers `%LOCALAPPDATA%\Programs\<nom>\<version>` ; données vers `%LOCALAPPDATA%\<nom court>` ; profil généré (données, stockage Qdrant court, ports) | « Chemin de l'index trop long (61 caractères, maximum 57). Choisissez un dossier de données plus court. » | Étapes journalisées dans `install-<UTC>.json` |
| 6 | Python | — | `uv sync --offline --locked --no-dev` depuis le cache du kit ; `python --version` = 3.12.14 | Sortie uv conservée au journal | Relance |
| 7 | Vérification | — | `doctor` : binaires, modèles, OCR, ports, marge d'admission, profil appliqué | Rubrique en échec et action, par exemple « Port 11434 occupé par ollama.exe (PID 4120) ; l'atelier utilisera 11534. Rien n'a été arrêté. » | Correction puis relance |
| 8 | Démarrage | — | `up` ; santé ; readiness interprétée (base vide attendue, C13) | « Qdrant n'a pas répondu en 90 s ; journal : …\logs\<instance>\qdrant.log » | `down` puis relance ; données intactes |
| 9 | Contrôle réel | — | `selftest` dans une racine et des ports temporaires : import d'un PDF synthétique du dépôt, extraction native et OCR, recherche plein texte et dense, citation, génération si l'admission le permet ; racine temporaire supprimée | « Génération non admise maintenant : 4 100 Mio disponibles, 4 992 requis. L'atelier fonctionne ; fermez des applications avant de poser une question. » | Relance de `selftest` seule |
| 10 | Rapport | — | Verdict par rubrique (vert, orange, rouge) et chemin du rapport | « Tout est prêt : services démarrés, index vide, modèle vérifié, contrôle réel réussi. » | — |
| 11 | Ouverture | Aucune (ouverture automatique en fin d'installation), puis raccourci « Atelier documentaire » | `open` : `up` si nécessaire, lien à usage unique, navigateur par défaut | « Le lien d'ouverture a expiré ; relancez le raccourci. » | Nouveau lien |
| 12 | Premiers documents | « Importer des PDF » ou « Importer un dossier » | Copie gérée des originaux, suivi des traitements | Messages existants de l'interface | Reprise manuelle d'un import en pause (D-09) |
| 13 | Première question | Choisir le périmètre, poser la question | Admission mémoire, sources puis réponse, citations cliquables | « En attente de mémoire disponible » (W008) | — |

### 7.2 Données de l'utilisateur

- **Emplacement :** hors du dossier programme, par utilisateur, dans un dossier non synchronisé : `%LOCALAPPDATA%\<nom court>` (FOLDERID_LocalAppData) avec `data\` et `q\` pour Qdrant (C09). Nom court à décider (P5).
- **Conservation :** jamais touchées par `update` ni par `uninstall`, sauf option explicite confirmée (P6). Les originaux déposés par l'utilisateur restent dans leur dossier d'origine ; l'atelier travaille sur sa copie gérée.
- **Sauvegarde :** `rag.ps1 backup -Path <dossier-neuf>` existe ; la destination par défaut doit quitter la racine du programme (C01) ; proposer un raccourci « Sauvegarder » vers un dossier choisi par l'utilisateur.

### 7.3 Mise à jour et désinstallation

- **Mise à jour :** `down`, sauvegarde vérifiée (`backup` puis `verify`, qui exigent une instance démarrée pour la première), nouvelle version installée à côté de l'ancienne, migrations SQLite appliquées à l'initialisation de la base (`services/api/db.py:103-113`), `doctor` et `selftest`, bascule des raccourcis. Retour arrière : raccourcis vers l'ancienne version et `restore` de la sauvegarde ; l'ancienne version refuse une base migrée (`database_schema_too_new`, `db.py:108-110`), la sauvegarde préalable est donc obligatoire (retour de migration : lot R11). Une nouvelle identité d'embedding impose une réindexation (collection nommée selon le modèle).
- **Désinstallation :** retrait du dossier programme, de `.venv` et des raccourcis ; rapport des données conservées et de leur taille.

## 8. Recommandation

**Retenir A comme socle, B comme enveloppe facultative.** Les points durs de la demande (hors ligne, intégrité, séparation des données, contrôle réel, W011, licences) se règlent dans le code existant, quel que soit l'emballage. A les règle sans nouveau runtime, sans droit d'administrateur et sans toucher au superviseur. B ajoute une installation en quelques clics, une entrée de désinstallation et une signature d'installateur, pour un effort limité une fois A terminé. Electron et Tauri ajoutent une base de code et un runtime à maintenir pour un gain limité à la fenêtre dédiée ; leur coût mémoire n'est pas mesuré. MSIX exige une refonte des chemins et expose les données à la désinstallation. WinGet ne sert pas un produit interne hors ligne.

### 8.1 Étapes ordonnées

Statut de toutes les actions : **proposé**. La réalisation est autorisée par l'utilisateur après cette analyse (PLAN R22) ; les points P1 à P10 conditionnent certaines étapes.

| ID | Couche | Dépend de | Livrable | Critère de réussite vérifiable |
|---|---|---|---|---|
| DIST-01 | Lanceur, outils | W011 API (fait) | Commande `open` (`rag.ps1` et CLI) ; `import_folder.py` avec `x-rag-control-token` | Test d'intégration : lien obtenu, cookie posé, second usage refusé ; import en ligne de commande 2xx sur une instance W011 |
| DIST-02 | Runtime, configuration | — | Profil par utilisateur (données absolues, stockage Qdrant court, ports) ; écritures d'exécution hors du dossier programme ; `qdrant.collection.json` sous `config/` | Inventaire SHA-256 du dossier programme identique avant et après `up` → import → question → `backup` → `down` ; tests unitaires existants PASS |
| DIST-03 | Installation | DIST-02 | `install` hors ligne : `SHA256SUMS`, copie, `uv sync --offline --locked --no-dev`, vérification des fichiers extraits sans archives (C06), Tesseract par manifeste, profil, rapport JSON | Compte Windows neuf ou poste de test sans Node, Python, Tesseract ni Ollama, réseau coupé : installation sans intervention ; relance idempotente ; reprise après interruption provoquée |
| DIST-04 | Fabrication | DIST-02, DIST-03 | `build_kit` : liste blanche, exclusions, cache uv sans `dev`, manifeste du kit (versions, tailles, sources), nettoyage des chemins du poste de fabrication | Contrôle automatique : aucune entrée interdite, aucun motif de secret, aucun chemin `C:\Users\` du fabricant ; deux fabrications à entrées identiques donnent les mêmes empreintes de contenu |
| DIST-05 | Contrôle | DIST-01, DIST-03 | Verdict synthétique de `doctor` (état « base vide attendue ») ; `selftest` réel en racine temporaire | Rapport JSON PASS par étape ; tests de pannes provoquées (port occupé, binaire altéré, modèle absent) avec le message attendu |
| DIST-06 | Poste utilisateur | DIST-01, DIST-03 | Raccourcis « Atelier documentaire », « Arrêter », « Diagnostic », « Sauvegarder » (menu Démarrer de l'utilisateur) | Clic : atelier ouvert avec session ; second clic : nouvelle session sans second `up` ; rendu examiné |
| DIST-07 | Licences | DIST-04 | `LICENSES/`, `THIRD_PARTY_NOTICES`, mention de modification du modèle texte ; inventaire rejoué sur le kit (R11, D09.5) | Chaque composant livré a un texte de licence ou figure dans la liste des manques soumise à P7 |
| DIST-08 | Cycle de vie | DIST-02, DIST-03 | `uninstall` (données conservées par défaut), `update` côte à côte avec sauvegarde | Mise à jour sur données peuplées : une ancienne citation s'ouvre ; désinstallation : inventaire des données inchangé |
| DIST-09 | Emballage (facultatif, P8) | DIST-03 à DIST-08 | Script Inno Setup (`lowest`, `{autopf}`, `{userprograms}`, `[UninstallDelete]` pour `.venv`, découpage si nécessaire, signature si P4) | Installation et désinstallation sur compte standard sans invite UAC ; entrée dans « Applications installées » ; données conservées |
| DIST-10 | Recette | DIST-03 à DIST-08 | Recette sur un second poste (R10, D01) : H1 à H5 tranchées, rapport, captures | Parcours §7.1 complet sans intervention hors clics prévus, réseau coupé ; écarts consignés |

### 8.2 Hypothèses à tester

| ID | Hypothèse | Test discriminant |
|---|---|---|
| H1 | Ollama 0.35.0 démarre et génère en CPU sans `cuda_v12`, `cuda_v13` ni `vulkan` | Copie isolée sans ces dossiers, `pull-model -Offline` puis génération courte ; journal Ollama |
| H2 | `.venv` se recrée sans la jonction `cpython-3.12-windows-x86_64-none` | Kit extrait par ZIP sur une autre racine, `uv sync --offline` |
| H3 | `up` fonctionne sans `tests/`, sans `RAG_Local_Agents/*.md` et sans Git | Kit minimal, `up` puis lecture de `source-manifest.json` |
| H4 | Aucun Visual C++ Redistributable système n'est requis | Poste ou machine virtuelle vierge : import d'un PDF (torch, onnxruntime, opencv) puis question |
| H5 | Les fichiers extraits d'une archive téléchargée héritent de la marque de zone | `Get-Item -Stream Zone.Identifier` sur les scripts extraits |
| H6 | Taille compressée du kit | Mesure après fabrication |

## 9. Points à trancher par l'utilisateur

| ID | Question | Options et conséquences |
|---|---|---|
| P1 | Canal de distribution | Partage réseau interne (SmartScreen distingue les emplacements intranet de confiance selon la politique [DST16]), support amovible ou téléchargement interne (marque de zone, H5) |
| P2 | Livrer le modèle Qwen source (3,2 Gio) | Oui : reproductibilité de la dérivation hors ligne (W006). Non : kit plus léger, verrou et doctor à adapter |
| P3 | Retirer les bibliothèques GPU d'Ollama (1,7 Gio) | Seulement si H1 passe ; le kit ne contient plus l'archive officielle intacte mais des fichiers hachés un à un |
| P4 | Signature de code et politique du parc | Certificat interne, service Microsoft de signature, ou absence de signature avec avertissements ; obtenir de l'administrateur la GPO d'exécution des scripts, AppLocker, App Control et Smart App Control |
| P5 | Nom court et emplacement des données | Contrainte de 57 caractères (C09) ; proposition `%LOCALAPPDATA%\<nom de 3 à 5 lettres>` |
| P6 | Désinstallation | Conserver les données par défaut ; suppression sur option confirmée |
| P7 | Validation de la redistribution interne | Lecture juridique des manques du §6 (titulaire E5, DLL Tesseract, NVIDIA si C07 non retenu, MPL-2.0) |
| P8 | Installateur et fenêtre dédiée | Inno Setup après A, oui ou non ; Tauri seulement si une fenêtre dédiée devient une exigence |
| P9 | Ports du kit | Ports par défaut distincts de 6333 et 11434, ou choix dynamique à l'installation |
| P10 | Version de Tesseract | Garder la copie 5.4.0 (signature expirée, provenance non authentifiée) ou requalifier un build actuel : changement de version, donc décision et recette OCR |

## 10. Limites

- Aucune installation n'a été exécutée ; toutes les étapes DIST restent à réaliser et à vérifier. Les tailles sont des sommes de mesures locales non compressées ; aucune taille compressée n'est donnée.
- Les licences viennent des fichiers et pages officielles lus ; ce n'est pas un avis juridique. Les conditions NVIDIA, la MPL-2.0, les licences des DLL du build Tesseract et les avis Chromium n'ont pas été lus.
- La copie de travail évolue (W011, R18, R19) ; les numéros de ligne cités valent pour l'état lu entre 17:40 et 18:02 UTC.
- Le comportement mémoire d'Electron ou de WebView2 sur ce poste n'est pas mesuré. La signification de la valeur de registre de Smart App Control relevée (0) n'a pas été vérifiée dans une source officielle et n'est pas interprétée.
- L'analyse ne couvre qu'un poste Windows 11 Enterprise ; les politiques d'un autre parc (GPO, AppLocker, antivirus) sont inconnues.

## 11. Sources

Consultées le 30/09/2026 entre 17:45 et 18:00 UTC. Les dates entre parenthèses sont celles affichées par la page.

| ID | Source | Ce qu'elle établit | Limite |
|---|---|---|---|
| DST01 | [Microsoft, about_PowerShell_exe (5.1)](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_powershell_exe?view=powershell-5.1) (2024-07-23) | `-ExecutionPolicy` fixe la politique de la session, sans modifier le registre ; `-File` doit être le dernier paramètre | — |
| DST02 | [Microsoft, about_Execution_Policies (5.1)](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1) (2026-08-31) | Portées et priorités ; la GPO l'emporte sur `Process` ; `RemoteSigned` et fichiers téléchargés ; `Bypass`/`AllSigned` sans contrôle de zone | — |
| DST03 | [Microsoft, Unblock-File (5.1)](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/unblock-file?view=powershell-5.1) (2022-12-12) | Retrait du flux `Zone.Identifier` | — |
| DST04 | [Microsoft, KNOWNFOLDERID](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid) (2020-07-27) | `FOLDERID_Programs` = `%APPDATA%\Microsoft\Windows\Start Menu\Programs` ; `FOLDERID_UserProgramFiles` = `%LOCALAPPDATA%\Programs` | Méthode de création d'un raccourci non lue |
| DST05 | [Inno Setup, PrivilegesRequired](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm) | `lowest` : jamais d'élévation, mode non administrateur | — |
| DST06 | [Inno Setup, Non Administrative Install Mode](https://jrsoftware.org/ishelp/topic_admininstallmode.htm) | Clés sous `HKEY_CURRENT_USER`, groupe dans le profil | — |
| DST07 | [Inno Setup, constantes](https://jrsoftware.org/ishelp/topic_consts.htm) | `{autopf}`, `{userpf}`, `{userprograms}`, `{app}` | — |
| DST08 | [Inno Setup, DiskSpanning](https://jrsoftware.org/ishelp/topic_setup_diskspanning.htm) | Obligatoire au-delà de 4 200 000 000 octets compressés | — |
| DST09 | [Inno Setup, [UninstallDelete]](https://jrsoftware.org/ishelp/topic_uninstalldeletesection.htm) | Le désinstalleur ne supprime par défaut que ce qui a été installé | — |
| DST10 | [Inno Setup, SignTool](https://jrsoftware.org/ishelp/topic_setup_signtool.htm) | Signature de l'installateur et du désinstalleur | — |
| DST11 | [Licence d'Inno Setup](https://jrsoftware.org/files/is/license.txt) | Usage commercial permis ; conditions de redistribution | — |
| DST12 | [FireGiant, WiX Toolset](https://www.firegiant.com/wixtoolset/) (redirection de wixtoolset.org) | WiX v3, v4 et v5 hors support communautaire | Licence et version courante non indiquées sur la page |
| DST13 | [Dépôt wixtoolset/wix](https://github.com/wixtoolset/wix) | Maintenance Fee exigée pour un usage générant un revenu | `LICENSE.TXT` non ouvert |
| DST14 | [Microsoft, packaged desktop apps (MSIX)](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes) (2025-09-09) | Installation par utilisateur, paquet en lecture seule, redirection d'`AppData` et suppression à la désinstallation (applications virtualisées) | Job Objects non traités |
| DST15 | [Microsoft, signer un paquet MSIX](https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview) (2026-04-14) | Signature obligatoire, chaîne vers une racine de confiance, horodatage | — |
| DST16 | [Microsoft, réputation SmartScreen](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) (2026-05-04) | Avertissements pour les fichiers non signés ; un certificat EV ne contourne plus SmartScreen ; politiques d'entreprise ; Smart App Control bloque les fichiers non signés sans réputation | — |
| DST17 | [Microsoft, AppLocker](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/applocker/applocker-overview) (2026-03-29) | Contrôle des exécutables, scripts, MSI, DLL et applications empaquetées ; règles par éditeur, chemin ou hash | — |
| DST18 | [Electron, Security](https://www.electronjs.org/docs/latest/tutorial/security) | Valeurs par défaut de sécurité et mise à jour d'Electron, Chromium et Node | — |
| DST19 | [Electron, Code Signing](https://www.electronjs.org/docs/latest/tutorial/code-signing) | Recommandations de signature | Affirmation sur l'exigence EV divergente de DST16 ; DST16 fait foi pour SmartScreen |
| DST20 | [Electron, Updating Applications](https://www.electronjs.org/docs/latest/tutorial/updates) | `update.electronjs.org` exige un dépôt GitHub public ; serveurs privés possibles | — |
| DST21 | [Electron Forge, Squirrel.Windows](https://www.electronforge.io/config/makers/squirrel.windows) et [WiX MSI](https://www.electronforge.io/config/makers/wix-msi) | Squirrel sans droits d'administrateur ; maker WiX limité à WiX v3 | Emplacement d'installation non précisé |
| DST22 | [Electron, Application Packaging](https://www.electronjs.org/docs/latest/tutorial/application-distribution) | Electron Forge recommandé | — |
| DST23 | [API GitHub, release Electron v44.5.1](https://api.github.com/repos/electron/electron/releases/latest) | `electron-v44.5.1-win32-x64.zip` : 157 998 329 octets, publié le 2026-09-30 | Taille d'une application complète non mesurée |
| DST24 | [Electron, LICENSE](https://github.com/electron/electron/blob/main/LICENSE) | MIT | Branche `main` |
| DST25 | [Tauri v2, sidecars](https://v2.tauri.app/develop/sidecar/) | `externalBin`, suffixe du triplet cible, permissions du plugin shell | — |
| DST26 | [Tauri v2, installateur Windows](https://v2.tauri.app/distribute/windows-installer/) | NSIS `currentUser` sans droits ; MSI via WiX v3 ; tailles des modes WebView2 | — |
| DST27 | [Tauri v2, prérequis](https://v2.tauri.app/start/prerequisites/) | WebView2 présent depuis Windows 10 1803 ; Rust et C++ Build Tools pour le développement | — |
| DST28 | [Dépôt tauri-apps/tauri](https://github.com/tauri-apps/tauri) | MIT ou MIT/Apache 2.0 | — |
| DST29 | [Microsoft, distribuer WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution) (2024-06-27, mise à jour 2026-09-14) | Evergreen inclus dans Windows 11 ; détection par `pv` ; version fixe de plus de 250 Mo | — |
| DST30 | [Microsoft, Nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs) (2025-07-14) | Jobs imbriqués depuis Windows 8 | — |
| DST31 | [Microsoft, winget source](https://learn.microsoft.com/en-us/windows/package-manager/winget/source) (2026-07-19) | `source add` exige des droits d'administrateur ; types de source | — |
| DST32 | [Microsoft, manifeste WinGet](https://learn.microsoft.com/en-us/windows/package-manager/package/manifest) (2026-09-14) | `InstallerUrl` et `InstallerSha256` requis ; commutateurs silencieux d'Inno Setup | — |
| DST33 | [uv, Locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/) | Groupe `dev` synchronisé par défaut ; `--no-dev` ; `--locked` ; synchronisation exacte | Page courante ; contrat de 0.12.21 confirmé par `--help` local |
| DST34 | [uv, référence CLI](https://docs.astral.sh/uv/reference/cli/) et `uv 0.12.21 --help` local | `--offline`, `--no-dev`, `--compile-bytecode` (page) ; `--relocatable`, `--install-dir`, `--no-bin`, `--no-registry`, `--find-links`, `--no-index` (aide locale) | Page tronquée à la lecture |
| DST35 | [uv, Python versions](https://docs.astral.sh/uv/concepts/python-versions/) | Distributions python-build-standalone d'Astral ; enregistrement PEP 514 sous Windows | — |
| DST36 | [python-build-standalone, Running Distributions](https://gregoryszorc.com/docs/python-build-standalone/main/running.html) | Licences variées, GPL évitée, métadonnées et textes de licence dans l'archive | Contenu exact des archives `install_only` non précisé |
| DST37 | [Python 3.12, Using Python on Windows](https://docs.python.org/3.12/using/windows.html) | Paquet embarquable sans pip, paquets tiers à la charge de l'installateur | — |
| DST38 | [Python 3.12, History and License](https://docs.python.org/3.12/license.html) | Conditions PSF ; composants tiers | — |
| DST39 | [Ollama, Windows](https://docs.ollama.com/windows) | Installation sans droits d'administrateur ; archive autonome avec dépendances GPU NVIDIA ; `OLLAMA_MODELS` ; port 11434 | — |
| DST40 | [API GitHub, release Ollama v0.35.0](https://api.github.com/repos/ollama/ollama/releases/tags/v0.35.0) | Tailles des archives Windows, publication le 2026-09-28 | — |
| DST41 | [Ollama v0.35.0, LICENSE](https://github.com/ollama/ollama/blob/v0.35.0/LICENSE) | MIT, « Copyright (c) Ollama » | — |
| DST42 | [Qdrant v1.19.1, LICENSE](https://github.com/qdrant/qdrant/blob/v1.19.1/LICENSE) | Apache-2.0, Qdrant Solutions GmbH | — |
| DST43 | [API GitHub, release Qdrant v1.19.1](https://api.github.com/repos/qdrant/qdrant/releases/tags/v1.19.1) | Archive Windows de 29 671 153 octets ; aucun fichier de licence parmi les assets | — |
| DST44 | [Tesseract 5.4.0, LICENSE](https://github.com/tesseract-ocr/tesseract/blob/5.4.0/LICENSE) | Apache-2.0 | Ne couvre pas les DLL tierces du build Windows |
| DST45 | [UB Mannheim, wiki Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) | Installateur actuel 5.5.3.20260724 ; mise à jour 5.4.0 du 2024-06-06 | Licences du build et signature non traitées |
| DST46 | [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) | Section 4, conditions de redistribution | — |
| DST47 | [CDLA-Permissive-2.0](https://cdla.dev/permissive-2-0/) | Texte de l'accord à joindre aux données ; aucune obligation sur les résultats | — |
| DST48 | [Hugging Face, Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) | Licence apache-2.0 | Page courante ; révision verrouillée recoupée par le README local |
| DST49 | [Hugging Face, docling-layout-heron](https://huggingface.co/docling-project/docling-layout-heron) | Licence apache-2.0 | idem |
| DST50 | [Hugging Face, docling-models](https://huggingface.co/docling-project/docling-models) | Licences affichées : cdla-permissive-2.0 et apache-2.0 | La révision verrouillée ne déclare que cdla-permissive-2.0 |
| DST51 | API Hugging Face, arborescences aux révisions verrouillées : [E5](https://huggingface.co/api/models/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3), [docling-models](https://huggingface.co/api/models/docling-project/docling-models/tree/fc0f2d45e2218ea24bce5045f58a389aed16dc23), [Heron](https://huggingface.co/api/models/docling-project/docling-layout-heron/tree/8f39ad3c0b4c58e9c2d2c84a38465abf757272d8) | Aucun fichier `LICENSE` ou `NOTICE` à la racine | — |
| DST52 | [Ollama, bibliothèque qwen3.5](https://ollama.com/library/qwen3.5) | `qwen3.5:4b` : 3.4GB | Licence non affichée sur la page |
| DST53 | [Dépôt astral-sh/uv](https://github.com/astral-sh/uv) | MIT ou Apache-2.0 au choix | — |
| DST54 | [API GitHub, release uv 0.12.21](https://api.github.com/repos/astral-sh/uv/releases/tags/0.12.21) | Archive Windows de 17 992 232 octets, publiée le 2026-09-29 | — |
| LOC-LIC | `RAG_Local_Agents/reports/licenses-2026-09-30-prerequisites.json` (dépôt) | Inventaire des licences installées au 30/09 02:52 UTC | Métadonnées, pas d'avis ; inclut le groupe `dev` |

Preuves locales : fichiers et lignes cités dans le texte ; mesures du §2.3 et observations du §2.7 obtenues par les commandes PowerShell indiquées, en lecture seule ; `.runtime/models/*/README.md` et `LICENSE` provisionnés aux révisions verrouillées.

## 12. Sources non ouvertes ou inexploitables

- `https://learn.microsoft.com/en-us/windows/package-manager/package/private-repository` : réponse 404.
- `https://docs.firegiant.com/wix/` et `https://docs.firegiant.com/wix/osmf/` : contenu non restitué par l'outil (menus seulement).
- `https://nsis.sourceforge.io/License` : contenu vide à la lecture ; licence de NSIS non établie.
- `https://huggingface.co/intfloat/multilingual-e5-small` et son arborescence HTML : contenu non restitué ; remplacés par l'API (DST51) et le README local à la révision verrouillée.
- `https://www.electronforge.io/config/makers` : page d'index sans la liste des makers ; pages de makers lues séparément (DST21).
- `https://v2.tauri.app/concept/size/` : ouverte, sans chiffre de taille.
- Documentation uv décrivant l'effet exact de `--relocatable` sur `pyvenv.cfg` : non trouvée dans la documentation officielle ; seuls des résumés de moteur de recherche renvoyant à des issues et PR ont été vus, non utilisés.
- Non ouverts faute de temps ou hors besoin immédiat : `LICENSE.TXT` de WiX, conditions de redistribution NVIDIA CUDA, texte MPL-2.0, avis Chromium d'Electron, licence du runtime WebView2, licence de Node.js, section `[Run]` d'Inno Setup, documentation de création de raccourci (WScript.Shell), documentation de Smart App Control.
