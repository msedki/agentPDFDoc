# Inspection du dossier et de la machine

Inspection locale effectuée les 29 et 30 septembre 2026, en UTC. La demande porte sur la compréhension du dossier, du matériel et de l'environnement logiciel. Le dossier contient un brief cohérent de RAG documentaire local et un petit corpus industriel réel, mais aucune application. La machine correspond à la capacité physique visée de 16 Go ; son environnement n'est pas encore provisionné pour cette architecture et sa mémoire actuellement disponible ne couvre pas les admissions lourdes prévues.

Les observations sont conservées dans [machine.json](preuves-inspection-2026-09-30/machine.json), [environnement.json](preuves-inspection-2026-09-30/environnement.json), [corpus-inspection.json](preuves-inspection-2026-09-30/corpus-inspection.json) et [integrite-pack.json](preuves-inspection-2026-09-30/integrite-pack.json). Le suivi reste dans [PLAN.md](../PLAN.md) ; les opérations et leurs limites figurent dans le [journal](../journal/2026-09-30.md).

## Contenu et état réel

Avant l'ajout des preuves et documents de cette inspection : **29 fichiers, 13 sous-dossiers, 60 856 098 octets**, soit environ 58,04 Mio. Le corpus représente 60 572 456 octets de ce total. Aucun dépôt Git, code applicatif, environnement virtuel local, `package.json`, `pyproject.toml`, lockfile de dépendances, test ou script applicatif n'a été trouvé dans ce dossier.

| Élément | Contenu et rôle |
|---|---|
| `AGENTS.md`, `CLAUDE.md` à la racine | Instructions durables pour les outils de développement ; pas du code produit |
| `RAG_LOCAL_BRIEF_COMPLET.md` | Document agrégé de référence, avec les documents de conception et configurations |
| `RAG_Local_Agents/` | Brief séparé : architecture, implémentation cible, configuration, recette, prompt, sources et plan |
| `RAG_Local_Agents/config/` | Huit fichiers de référence : YAML, JSON, SQL, environnement et configuration Next.js |
| `RAG_Local_Complet.zip`, manifestes SHA-256 | Copie archivée du pack et empreintes de son état livré |
| `PDF/Z2m/Plan de maintenance/` | Arborescence métier : révisions et visites ; cinq documents dans les livrets de révision |

Les cinq branches `Revisions/2 modes Opérations`, `Revisions/3 Fiches - Checklists de conformité` et les trois sous-dossiers de `visites/` sont vides au moment de l'inventaire. Le DOCX de mode opératoire se trouve dans `Revisions/1 livrets des operations` ; cette classification mérite un éventuel arbitrage métier, sans déplacement effectué.

Le pack définit une baseline **RAG-LOCAL-16 v1.0 du 29 septembre 2026**. Le `PASS` de [CONTROLES_DOSSIER.json](../CONTROLES_DOSSIER.json) concerne ses contrôles documentaires et de configuration. Il exclut les runtimes applicatifs et leurs performances. Les noms de commandes dans [IMPLEMENTATION.md](../IMPLEMENTATION.md), §9, sont à implémenter : aucun lanceur `provision`, `doctor`, `start`, `stop`, `verify`, `backup` ou `restore` n'est fourni comme application exécutable.

## Compréhension du produit visé

Le produit est un poste documentaire mono-utilisateur, local après provisionnement. Il doit conserver l'arborescence et les originaux, afficher le PDF et permettre recherche, question, analyse de sélection ou de pages, et comparaison de deux à quatre documents. Chaque citation doit ouvrir la version et la page correctes, avec un surlignage limité à la précision réellement disponible.

L'interface prévue comporte trois panneaux redimensionnables : bibliothèque, lecteur et analyse. Le périmètre de recherche reste visible et ne change pas silencieusement lorsqu'une citation ouvre un autre PDF. Une sélection courte utilise directement les blocs autorisés ; elle ne déclenche pas de recherche globale.

| Couche | Choix du brief | Conséquence concrète |
|---|---|---|
| Interface | Next.js, React, TypeScript, PDF.js ; export statique | FastAPI sert aussi l'interface ; pas de serveur Next.js en exploitation |
| API | Python **3.12**, FastAPI/Pydantic, REST et SSE, un worker | Une origine locale `127.0.0.1:8765`, réponses progressives et annulation |
| Métadonnées et recherche lexicale | SQLite/WAL/FTS5/BM25 | Source de vérité sur documents, versions, jobs et générations actives |
| Recherche dense | Qdrant serveur local, cosinus, vecteurs 384D | Filtrage du périmètre avant top-k ; pas de BM25 Qdrant présumé |
| Embeddings | multilingual-e5-small, ONNX Runtime CPU INT8 | Tokenizer local, préfixes query/passage, pooling et normalisation à vérifier |
| PDF et OCR | pypdfium2 en précontrôle, Docling structuré, Tesseract FR/EN sélectif | Provenance conservée, tableaux et coordonnées, traitement borné par fenêtres |
| Génération | Qwen3.5 4B via Ollama, Q4_K_M exigée | CPU, une génération, contexte 8 192 et sortie maximale 768 tokens |
| Exploitation Windows | Une WSL2 Ubuntu ; référence Ubuntu 24.04 x86-64 | Services et stockage actif dans Linux ; Windows et navigateur inclus dans le budget |

La chaîne cible est : import et copie immuable SHA-256 → précontrôle → extraction/OCR → blocs et provenance → chunks → deux index → recherche dans le scope → preuves → génération → citation → navigation PDF. Les chunks sont structurels, cible 320 tokens E5, entrée préfixée maximale 448. Dense top 24 et lexical top 24 sont fusionnés par RRF, puis limités à six fragments initiaux ; la sélection et l'expansion ne doivent introduire aucun passage hors périmètre.

La cohérence SQLite/Qdrant repose sur une génération préparée puis publiée par une transaction SQLite. Les points d'une génération non active restent invisibles à la recherche. Une version partielle ne remplace pas automatiquement une version complète. Les anciennes citations conservent la référence à l'ancien original. Ces choix sont décrits dans [IMPLEMENTATION.md](../IMPLEMENTATION.md), §3 et §5–7 ; ils ne sont pas encore implémentés.

La séparation entre ingestion lourde et génération est déterminante : un seul worker PDF, une seule génération, jamais simultanés. L'ingestion doit checkpoint et libérer son processus pour une question interactive, puis reprendre après l'inactivité prévue. Les paramètres du YAML sont un contrat futur ; ils ne règlent pas automatiquement les bibliothèques.

Le brief exclut cloud, télémétrie, CDN, vision d'indexation, agents autonomes au runtime, GraphRAG, reranker neural et Redis/Celery. Un schéma graphique sans texte exploitable ne devient pas une connaissance fiable du modèle par simple OCR. Les fichiers PDF restent des données non fiables, sans exécution de JavaScript ou pièces jointes.

## Corpus effectivement disponible

Inventaire exhaustif des fichiers et inspection structurelle des **182 pages PDF**, avec PyMuPDF 1.28.2 déjà installé. Cet outil sert uniquement à cette inspection ; il n'est pas ajouté à la stack nominale. Inspection visuelle de 24 pages échantillonnées ; DOCX lu comme ZIP/XML, sans ouverture de contenu actif ni rendu Word.

| Document | Taille en Mio | Pages PDF |
|---|---:|---:|
| Distributeur SW4 Partie1 | 12,58 | 36 |
| Distributeur SW4 Partie2 | 9,45 | 32 |
| Robinet de mécanicien Z2M A-8-E3 | 18,92 | 58 |
| Cylindre de frein PBECP(2C) Z2M | 14,88 | 56 |
| Mode opératoire de soudure des pins de connecteur Z2M, DOCX | 1,94 | Sans pagination PDF ; métadonnée Word : 5 pages, non rendue |

Les quatre PDF sont des **scans sans couche texte extractible** : zéro caractère sur chacune des 182 pages, une image par page, aucun signet, aucun chiffrement et rotation PDF égale à zéro. Les pages mesurent 595 × 842 points et les images 1 646 × 2 331 pixels, avec environ 99,3 % de couverture. La résolution estimée est d'environ 200 dpi ; cela ne constitue pas une mesure de qualité OCR.

Les échantillons montrent principes pneumatiques, démontage, contrôle, nettoyage, remontage et essais, avec photos annotées, schémas, tableaux, signatures et tampons. Certaines pages sont presque blanches ou présentent une transparence du verso. Le corpus n'est donc pas un exemple de PDF natifs immédiatement indexables.

Deux particularités sont importantes pour les citations et l'extraction :

- SW4 Partie1 et Partie2 prolongent le même livret. Les folios observés passent de 0/65 à 33/65 dans P1, puis de 34/65 à 65/65 dans P2. Page physique, folio imprimé et fichier doivent rester distincts.
- Les pages non blanches échantillonnées 1, 3, 5, 10 et 58 du robinet sont retournées de 180° dans les pixels, malgré `/Rotate=0`. L'orientation des autres pages non examinées reste inconnue. Un traitement fondé seulement sur cette métadonnée ne suffit pas.

Le DOCX contient du texte natif court, 15 images et cinq éléments tableaux, dont des tableaux imbriqués. Le tableau opératoire a trois colonnes, Phase/Intervention/Illustration, et 11 phases après l'en-tête. Les nœuds texte totalisent 1 703 caractères en étant comptés une seule fois. Aucun VBA, objet incorporé ou relation externe n'a été détecté. Son import n'est pas défini par le contrat d'upload PDF actuel : sa prise en charge reste un point de périmètre à trancher, pas une fonctionnalité acquise.

**Limite : aucun OCR n'a été exécuté.** La reconnaissance des références, valeurs, unités, repères de schéma et cellules de tableaux reste à qualifier. Les comptes de chunks, temps d'indexation et qualité retrieval sont inconnus.

## Machine et disponibilité

Photographie de référence : **30 septembre 2026 à 00:02:31 UTC**, voir [machine.json](preuves-inspection-2026-09-30/machine.json). Les valeurs disponibles évoluent avec les programmes actifs.

| Élément | Observation |
|---|---|
| Poste | Dell Latitude 5330 |
| Système | Windows 11 Entreprise 64 bits, version 10.0.22631, build 22631 |
| CPU | Intel Core i5-1235U, 12e génération ; **10 cœurs, 12 processeurs logiques** |
| RAM installée | Deux capacités de 8 Gio : **16 Gio physiques**, vitesse déclarée 3 200 |
| RAM visible par Windows | **15,692 Gio** |
| RAM disponible | **3,784 Gio** à la photographie ; environ 4,1 Gio au premier relevé |
| Graphique détecté | Intel Iris Xe Graphics ; aucune carte NVIDIA détectée dans l'inventaire CIM |
| Disque physique | **Un SSD NVMe Micron 2550 512 GB**, état Windows `Healthy` ; deux volumes, pas deux disques physiques |
| Volume C: | 194,81 Gio au total, **34,14 Gio libres** |
| Volume D:, contenant ce dossier | 281,25 Gio au total, **39,25 Gio libres** |
| Pagination Windows | Environ 15,69 Gio alloués, 893 Mio utilisés, pic depuis démarrage 3 284 Mio |

Le GPU intégré ne valide aucune voie d'accélération du RAG ; la baseline est CPU uniquement. Les fréquences CIM et le champ AdapterRAM ne sont pas utilisés pour déduire une fréquence turbo ni une capacité GPU dédiée exploitable. L'état `Healthy` est celui de Windows, sans diagnostic SMART détaillé ni mesure de débit. La pagination observée ne prouve pas un swap soutenu ; il faudrait une mesure temporelle.

Plusieurs processus Node/Python et un navigateur sont actifs. Le relevé de charge instantanée à 23:59:29 UTC indiquait 15 % de CPU, sans benchmark. Aucun processus utilisateur n'a été arrêté.

Le budget du brief demande une réserve hôte de 1,5 Gio, avec estimations initiales additionnelles de 6 Gio pour le chargement LLM et 4 Gio pour le worker PDF. **Interprétation des règles du brief :** tant que ces estimations ne sont pas remplacées par des pics mesurés, il faudrait environ 7,5 Gio disponibles pour admettre le chargement LLM et 5,5 Gio pour l'ingestion lourde. Les 3,784 Gio observés ne couvrent pas ces marges. La présence physique de 16 Gio n'est donc pas une preuve que le profil peut être démarré dans la charge actuelle.

Les 39,25 Gio libres sur D: dépassent largement les 57,77 Mio du corpus actuel. Ils ne certifient pas le provisionnement complet : poids, caches de paquets, extractions, index, éventuel disque WSL et snapshots doivent être comptés après résolution des artefacts. Aucun modèle ou disque virtuel n'a été téléchargé ou créé pour produire cette analyse.

## Environnement logiciel

Les versions ci-dessous ont été observées localement ; elles ne sont pas des recommandations ni un ensemble de dépendances validées pour le projet.

| Outil | État réel |
|---|---|
| PowerShell | 5.1.22621.4391 ; `pwsh` non trouvé dans le PATH |
| Node.js | **22.17.0**, `D:\node\node-v22.17.0-win-x64\node.exe` |
| npm | **11.18.0** ; la copie globale de l'utilisateur précède celle du répertoire Node dans le PATH |
| pnpm | **10.34.1**, commande exécutée avec accès réseau Corepack désactivé |
| Corepack | 0.33.0, lu dans son `package.json` |
| Yarn | Shim présent ; version non disponible sans accès au registre dans le contrôle effectué ; aucun téléchargement autorisé ou effectué |
| Python | **3.13.3 64 bits**, installé hors PATH ; exécution par chemin absolu réussie |
| Lanceur Python | `C:\Users\P47599\AppData\Local\Programs\Python\Launcher\py.exe` présent ; `-0p` retrouve Python 3.13 |
| pip | **25.0.1**, disponible avec cet interpréteur ; commande simple absente du PATH |
| Git | 2.50.1.windows.1 ; ce dossier n'est pas un dépôt |
| Tesseract | **5.4.0.20240606**, langues `eng` et `osd` ; **`fra` absente** |
| SQLite Python | **3.49.1**, FTS5 créé et interrogé avec succès sur une base uniquement en mémoire |
| uv | Non trouvé dans le PATH, les chemins utilisateur ciblés ou les paquets de l'interpréteur examiné |
| Ollama et Docker | Non trouvés dans le PATH, le registre d'applications et les chemins d'installation usuels contrôlés ; aucun service détecté sur les ports ciblés |
| Qdrant | Aucun service/processus observé sur les ports ciblés ; binaire non provisionné dans ce projet |
| WSL/Ubuntu | `wsl.exe` existe, mais le sous-système n'est pas opérationnel dans les contrôles ; aucune distribution utilisateur ni package Ubuntu/WSL détecté |

Python se lance actuellement avec :

```powershell
& 'C:\Users\P47599\AppData\Local\Programs\Python\Python313\python.exe' --version
& 'C:\Users\P47599\AppData\Local\Programs\Python\Python313\python.exe' -m pip --version
```

Le Python installé **3.13** diffère du Python **3.12** retenu par [SPEC_ARCHITECTURE.md](../SPEC_ARCHITECTURE.md), §2. Aucune compatibilité Docling/ONNX complète n'a été testée et aucune version n'a été remplacée.

Dans cet interpréteur global, les métadonnées identifient FastAPI 0.141.1, Uvicorn 0.52.3, Pydantic 2.13.4, NumPy 2.5.2, Pillow 12.3.0, PyMuPDF 1.28.2, PyYAML 6.0.3, pytest 9.1.1, Ruff 0.16.3, mypy 2.3.1 et httpx 0.28.1. Cela prouve leur installation, pas l'intégration de l'application.

Docling, docling-core, qdrant-client, ONNX Runtime, transformers, sentence-transformers, torch, pypdfium2, huggingface-hub, optimum et uv sont absents de **cet interpréteur**. D'autres environnements virtuels de la machine peuvent posséder des dépendances différentes ; un processus Python d'un autre chantier a été observé et n'a pas été inspecté ni modifié.

Les fonctionnalités Windows WSL, VirtualMachinePlatform et Hyper-V retournent `InstallState=2` dans CIM. Aucune distribution n'est enregistrée dans le registre utilisateur ciblé. Les commandes `wsl --status`, `--list --verbose`, `--version` n'ont pas établi une installation fonctionnelle. La présence d'un hyperviseur signalée par Windows n'est pas une preuve de WSL2 et les autres drapeaux CIM ne suffisent pas à conclure à une impossibilité matérielle de virtualisation. Aucun changement BIOS/Windows n'a été tenté.

Un répertoire utilisateur Ollama subsiste, mais ses sous-répertoires standards de manifests/blobs de modèles n'ont pas été trouvés. Les fichiers d'identité n'ont pas été lus. Aucun Qwen/E5 n'est provisionné dans le dossier projet ; l'absence globale de tous modèles sur tous chemins n'a pas été recherchée.

Les ports locaux **3000 et 8765 sont déjà occupés** au relevé final, respectivement par Node PID 9424 et Python PID 10020. L'appartenance de ces services n'a pas été établie. Le port 8765 est celui prévu par le brief : un futur lancement doit détecter cette collision, sans arrêter ni remplacer un service existant.

## Constats et portée

| ID | Classe | Constat, impact et preuve | Suite éventuelle, non réalisée |
|---|---|---|---|
| C01 | Inconnue levée | Dossier documentaire, aucune application ni Git ; inventaire initial et IMPLEMENTATION §1/§9 | Commencer une réalisation uniquement sur demande distincte |
| C02 | Incohérence environnement/cible | Python installé 3.13.3, cible 3.12 ; environnement.json et SPEC §2 | Provisionner un environnement isolé conforme si réalisation autorisée |
| C03 | Incohérence environnement/cible | OCR français absent alors que les PDF sont français ; environnement.json et corpus-inspection.json | Préparer `fra` et mesurer l'OCR, après autorisation de provisionnement |
| C04 | Inconnue d'intégration | WSL2/Ubuntu, Docling, ONNX, Qdrant et modèle non provisionnés dans la cible examinée | Résoudre runtimes/versions/artefacts et verrouiller leurs identités |
| C05 | Incohérence charge/budget | RAM disponible inférieure aux marges prudentes d'admission ; machine.json et SPEC §8 | Mesurer une session cible et résoudre la disponibilité sans arrêter de tâches sans accord |
| C06 | Inconnue qualité | Scans seuls, certaines pages retournées et folios différents des pages physiques ; corpus-inspection.json | Précontrôle/orientation/OCR avec contrôles visuels et conservation des originaux |
| C07 | Inconnue de périmètre | Un DOCX réel mais upload PDF dans le contrat courant ; corpus et IMPLEMENTATION §2 | Arbitrer son inclusion, sa conversion éventuelle ou son maintien hors index |
| C08 | Inconnue exploitation | Port cible 8765 occupé par un autre Python ; machine.json | Identifier la cible lors d'une éventuelle mise en service |
| C09 | Amélioration documentaire | PLAN d'origine non actualisé et vocabulaire `DONE`/`VERIFIED` mélangé, lignes initiales 3/7 | Inspection et suivi actualisés ; vocabulaire original de pilotage conservé |

Aucun bug applicatif n'est prouvé puisque le code n'existe pas ici. Les contrôles effectués portent sur les fichiers, configurations, documents et capacités installées ; aucun D01–D09 n'est validé par cette inspection.

## Intégrité et limites de la vérification

Avant les mises à jour du suivi : **20/20** empreintes du manifeste complet, **18/18** du manifeste interne et **21/21** fichiers du ZIP étaient identiques aux fichiers locaux. Neuf sections documentaires et huit blocs de configuration du brief agrégé correspondent aux fichiers séparés, hors fins de ligne terminales. Les JSON du pack sont parsables. SHA-256 du ZIP : `d430c868c3a6769e355acca86b7b40cdd07d80a101120474d78f318e01634ef7`.

L'archive, le brief agrégé, les configurations et les originaux du corpus sont conservés. Seuls `PLAN.md` et `SOURCES.md` du pack sont actualisés pour tracer cette inspection ; les manifestes historiques ne sont pas réécrits. Ils doivent donc signaler ces **deux différences documentaires attendues** dans la copie de travail après inspection. [integrite-pack.json](preuves-inspection-2026-09-30/integrite-pack.json) distingue l'état livré archivé et l'état de travail. Une comparaison SHA-256 établit la cohérence interne, pas l'authenticité de l'auteur.

Le contrôle FTS5 de cette session utilise uniquement `:memory:` avec une insertion et une recherche : il ne requalifie pas les migrations futures ou la cohérence avec Qdrant. Aucun OCR, embedding, modèle LLM, build UI, scénario RAG, test de performance ou contrôle réseau applicatif n'a été exécuté. Les sources web mentionnées par le brief n'ont pas été revisitées ; leurs informations restent des assertions documentaires du pack.

## Appréciation après inspection

Le brief est précis sur les difficultés importantes : scope, provenance, versions, cohérence de publication, limites de RAM et distinction entre citation formelle et soutien réel de la réponse. La séparation du lexical et du dense et celle de l'ingestion lourde et du LLM sont des décisions cohérentes avec son objectif de poste local limité.

Pour ce corpus, **la difficulté initiale est la qualité de l'OCR et de la provenance**, avant le choix ou l'optimisation du LLM : les 182 pages sont des scans, certains échantillons sont retournés, les tableaux et petits repères sont métier, et deux fichiers prolongent le même livret. Une réponse fluide ne compenserait pas une référence ou une unité mal reconnue.

Le matériel correspond à la cible de capacité, avec un SSD NVMe et 16 Gio physiques, mais l'environnement et la disponibilité instantanée ne permettent pas de conclure à une application prête ou à des latences acceptables. Le prochain résultat technique utile, **si une réalisation est demandée**, serait une première chaîne complète sur quelques pages métier contrôlées, accompagnée de mesures RAM/temps et d'un clic de citation réellement vérifié. Les lots applicatifs restent hors de la présente autorisation.
