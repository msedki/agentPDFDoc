# Configuration et provisionnement — V2.1, profil local16

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md). **W018 (01/10/2026) : Linux natif (aarch64 et x86-64) devient une seconde plateforme**, toute machine Windows restant prise en charge comme avant ; réalisation en cours (lots J du [plan](PLAN.md)). **W024 et W025 (01/10/2026) : le CPU reste le socle, le repli et la référence de la recette D07 ; seule la génération par Ollama peut passer sur GPU, automatiquement sur les voies qualifiées par un essai réel** ([W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024)). La clé `llm.accelerator` est décrite en [section 3](#3-ollama).

## 1. Nature des configurations

`config/local16.yaml` décrit les paramètres **de l'application à implémenter**. Un modèle Pydantic strict doit valider ses types, ses bornes et ses relations ; les clés inconnues sont rejetées. Ces paramètres ne deviennent effectifs dans Docling, Ollama ou Qdrant qu'après traduction par leurs adaptateurs. Une option écrite dans le YAML mais non appliquée est un défaut.

Les fichiers Ollama, Next.js, Qdrant et SQL sont des exemples de leurs formats natifs ; ils ne sont pas annoncés comme testés contre des services en fonctionnement. Le provisionnement valide les capacités de la version retenue, résout les chemins absolus et enregistre la configuration effective. Un `.env` chargé dans FastAPI ne configure pas un serveur Ollama déjà démarré.

Les valeurs suivantes sont une baseline initiale à qualifier. Aucune n'est présentée comme un optimum universel. La recette ne peut pas être affaiblie après un échec sans changement de baseline explicite.

**Évolution R23 du 4 octobre 2026 :** la table ci-dessous conserve la baseline de conception 4B. Le runtime [config/local16.yaml](../config/local16.yaml) choisit désormais `qwen3.5:2b` Q8_0, source et servi identiques ; [config/local16-4b.yaml](../config/local16-4b.yaml) conserve le 4B Q4_K_M et sa dérivation texte seule. Choix au démarrage, exclusivité modèle/profil et conditions de bascule : [exploitation](../docs/exploitation/EXPLOITATION.md#91-changer-le-modèle-de-génération). Les commandes Ollama brutes de la section 3 et le smoke JSON restent des exemples 4B ; ils ne provisionnent ni ne vérifient le profil 2B. Pour le modèle choisi, utiliser `rag.ps1`/`rag.sh` avec `-Model`/`--model` ou un profil explicite. Les preuves 4B historiques ne qualifient pas le 2B.

## 2. Paramètres initiaux et qualification

| Domaine | Valeur de départ | Vérification exigée |
|---|---|---|
| LLM | `qwen3.5:4b`, Q4_K_M, CPU, non-thinking | Digest, quantification, capacités et exécution CPU effectifs |
| Contexte | 8 192 maximum ; marge 256 | Tokenizer + chat template exacts, pas de troncature silencieuse |
| Preuves factuelles | 1 536 tokens | Couverture de la preuve nécessaire, extension autorisée si besoin |
| Preuves ordinaires | 2 560 tokens | Coût CPU et couverture finale |
| Preuves analyse/comparaison | 5 120 maximum | Preuves des documents comparés conservées |
| Sortie | 384 factuel ; 768 ordinaire/analyse | Fin anticipée ou limite de longueur visible |
| Sampling | Température 0,2 ; top_p 0,9 | Baseline applicative, non recette éditeur ; qualifier la fidélité |
| Embedding nominal | E5-small ONNX CPU INT8, 384D | Parité FP32/INT8 et qualité de recherche |
| Candidat unique | Granite 97M Multilingual R2 issu de l'audit | Vérifier son artefact officiel avant tout A/B ; sinon garder E5 |
| ONNX | Batch 8, intra-op 2, inter-op 1, spinning désactivé | RAM et temps embedding sur CPU cible |
| Chunking E5 | Cible 320 ; entrée préfixée max 448 ; overlap max 48 | Comptage exact et frontières structurelles |
| Retrieval | Dense 24 + lexical 24 ; RRF k=60 | Filtrage préalable et contrainte d'identifiant après fusion |
| Fragments | Six ordinaires ; huit max pour contraintes multiples | Le budget de tokens et la couverture priment |
| Qdrant | Vecteurs mappés ; HNSW initialement en RAM/cache | Mémoire totale et latence ; repli graphe froid si justifié |
| Parseur | Docling natif / structuré / OCR régional | Couverture, ordre et provenance identiques entre routes |
| Threads PDF | Parser natif 2 ; inférence 2 ; worker lourd 1 | Configurer séparément, ne pas supposer une limite globale implicite |
| Tableaux | Structuré accurate sur régions/pages nécessitant ce traitement | Pas de modèle tableau systématique sur tous les PDF simples |
| Checkpoints | Fenêtre initiale quatre pages | Persistance et continuité des structures aux frontières |
| Ordonnancement | Pause coopérative ; reprise manuelle initiale | Pas de kill nominal après cinq secondes ni de reprise périodique aveugle |
| Viewer | Cinq canvases max et 24 000 000 pixels RGBA cumulés | Allocations raster réelles et mémoire navigateur |
| Mémoire | Cible application 10 Gio ; réserve hôte 1,5 Gio | Hôte Windows + navigateur + services natifs |

**Plafonds livrés depuis W039, 6 octobre 2026 :** la ligne « Sortie » conserve
la baseline initiale. Les profils runtime 2B et 4B, et leurs copies documentaires,
utilisent désormais `llm.num_predict: 1536`, avec `output_tokens_by_mode`
à 768 pour `factual` et 1 536 pour `ordinary`, `analysis` et `compare`.
Le contexte reste à 8 192 et la marge à 256 : entrée sérialisée autorisée
jusqu'à 6 400 tokens, puis retrait contrôlé des fragments et couverture
revérifiée. Modifier seulement `num_predict` ne change pas un plafond explicite
par mode. Le changement s'applique après arrêt puis démarrage de l'instance.

Le maximum de preuves et les budgets `analysis`/`compare` sont ramenés
de 5 120 à 4 864 tokens pour respecter aussi la somme des plafonds :
4 864 + 512 (historique) + 1 024 (instructions/question) + 1 536 (sortie) + 256 (marge) = 8 192.
Budgets factuel/ordinaire de preuves inchangés,
modèles, tokenizer et garde du contexte complet conservés. Le template
et le prompt réellement assemblés restent comptés ; cette somme ne suffit
pas à elle seule à garantir leur taille.
[Décision, limites et validation ciblée](DECISIONS.md#w039-plafonds-de-réponse-et-avertissement-de-longueur).

## 3. Ollama

Injecter `config/ollama.env` dans le processus ou service Ollama. Pendant le provisionnement autorisé, exécuter :

```bash
ollama pull qwen3.5:4b
ollama show qwen3.5:4b
curl --fail http://127.0.0.1:11434/api/show \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.5:4b"}'
```

Lire la liste des modèles locaux pour obtenir le digest réel. Contrôler Q4_K_M, la capacité attendue et `think=false`. Un tag mutable ne constitue pas un verrou. Ne pas fabriquer `models.lock.json` : le produire à partir des fichiers réellement provisionnés. Une quantification différente nécessite une décision tracée et de nouveaux essais, pas un renommage trompeur.

Le smoke JSON vérifie seulement la connectivité :

```bash
curl --fail --no-buffer http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  --data-binary @config/ollama.chat.smoke.json
ollama ps
```

Une seule génération et un modèle chargé. `keep_alive=10m` est une rétention initiale ; décharger explicitement le LLM avant l'ingestion lourde si nécessaire. Le lanceur résout d'abord `num_thread=min(4, max(1, cœurs_physiques-1))` ; qualifier un changement si le prétraitement ou la génération est limitant. Ne pas confondre quatre threads Ollama avec quatre threads pour toute l'application.

Accélération de la génération (W024, W025, 01/10/2026) : `llm.accelerator` accepte `auto`, valeur livrée (génération sur GPU quand Ollama en découvre un sur une voie qualifiée par un essai réel, et, pour un GPU intégré à mémoire partagée comme celui d'un Jetson, sur un poste de plus de 16 Gio de mémoire totale ; CPU sinon), `cpu` (calcul CPU imposé, à retenir pour la recette D07) ou `gpu` (essai du GPU sur un poste non qualifié, avec la même détection et le même repli). La forme antérieure `llm.num_gpu: 0` vaut `cpu`, seulement en l'absence de `llm.accelerator` ; toute autre valeur de `llm.accelerator` ou de `llm.num_gpu`, ou la présence des deux clés, fait refuser le profil par le runtime et par l'API, avec un message qui nomme la clé en cause. Sans aucune des deux clés, le profil vaut `auto`. Seule la génération est concernée : Docling, l'OCR et E5 restent sur CPU. Décision du mode au démarrage de l'instance et options envoyées à Ollama (`num_gpu: 0` en CPU, option omise en GPU) : [ARCHITECTURE.md, section 5.1](../docs/architecture/ARCHITECTURE.md#51-accélération-gpu-de-la-génération) ; repli sur CPU : [API.md, section 5](../docs/interfaces/API.md#5-flux-sse-dune-question). Le smoke `config/ollama.chat.smoke.json` garde `num_gpu: 0` et vérifie donc la connectivité en calcul CPU. La section `llm` n'entre pas dans l'empreinte d'extraction (amendement de W022 par W025).

Ne pas activer Flash Attention, un KV cache quantifié ou une autre option sans support vérifié sur ce runtime/modèle/CPU. Mesurer chargement, traitement du prompt, cache réutilisé et génération via les champs réellement exposés [S01–S03]. Le scénario froid est distinct du modèle chaud et du préfixe en cache.

## 4. Embeddings et gel

E5 nominal : tokenizer officiel, préfixes `query: ` et `passage: ` même en français, pooling et normalisation selon S04. Plafond absolu modèle 512 tokens ; pour les chunks, entrée entière <=448 incluant titres, préfixe et tokens spéciaux. Export/quantification une seule fois au provisionnement, SHA-256 de chaque artefact, session ONNX locale CPUExecutionProvider ; pas de PyTorch résident dans l'API.

La comparaison avec Granite est une tâche de qualification bornée, pas une dépendance bloquant l'UI ou le parseur. Vérifier le candidat dans ses sources officielles ; ne pas lui copier la recette E5. Si ses artefacts ne sont pas accessibles ou compatibles, enregistrer ce constat et poursuivre E5. La vérification documentaire de cette V2.1 n'a pas reconfirmé l'accès aux deux pages Granite ; aucun chiffre comparatif de l'audit n'est utilisé comme preuve de choix.

Un seul embedding actif en production. Des espaces de même dimension ne sont pas interchangeables. L'A/B utilise deux collections isolées et le même corpus extrait, avec les différences de format d'entrée déclarées. Toute bascule crée une nouvelle identité de pipeline et conserve les preuves historiques. Voir `QUALIFICATION.md`.

## 5. Docling, OCR et couvertures

Préinstaller seulement les artefacts des chemins retenus. `artifacts_path` doit pointer vers le répertoire local résolu ; désactiver les services distants et vérifier qu'aucun téléchargement implicite n'est nécessaire. `generate_page_images=False` évite un export permanent, pas les rendus internes nécessaires aux modèles [S14].

Le profil applicatif `native` se mappe au `NativePdfPipeline`/`NativePdfFormatOption` disponibles dans la version verrouillée. Mapper `parser_threads` indépendamment de `AcceleratorOptions(...num_threads=...)`. La voie native n'exécute pas les modèles de layout/tableaux/OCR ; un succès technique d'extraction n'établit pas automatiquement la qualité sémantique.

Pour les pages/régions complexes, mapper les options structurées et Tesseract. La source S15 expose `OcrMode.PDF_AWARE_LAYOUT_REGIONS`. Utiliser la propriété exacte de l'option OCR réellement installée ; ne pas passer la chaîne du YAML applicatif au mauvais niveau. L'ancien `force_full_page_ocr` ne doit pas coexister avec une nouvelle option contradictoire. Les pages scannées intégrales et couches texte corrompues utilisent un chemin de remplacement explicite, sans concaténation en double.

FR/EN : installer `fra` et `eng` et vérifier leur disponibilité. Le précontrôle de moins de 40 caractères utiles ou plus de 2 % de caractères de remplacement reste un **signal**, jamais la décision OCR unique. Contrôler les images/régions non couvertes. Une page mixte native + tableau scanné et une page purement graphique ont des attentes différentes.

Ne pas appeler à nouveau Docling pour chaque petite modification de chunking ou d'embedding. Les changements de parsing, eux, créent une révision d'extraction distincte, sans invalider silencieusement les citations anciennes.

## 6. Qdrant et SQLite

Un serveur Qdrant local ; pas de substitution silencieuse par le mode embarqué Python. Lancer avec configuration et chemins absolus validés. `config/qdrant.yaml` utilise `storage.payload.memory: cold` dans le schéma officiel consulté [S08]. Si le binaire verrouillé ne supporte pas ce champ, générer un overlay de compatibilité explicite avec son option documentée et le tester ; ne jamais ignorer une option inconnue.

Le JSON de collection exprime le placement par `memory`, successeur de `on_disk` et `on_disk_payload` dépréciés à la version installée 1.19.1 (W017) : vecteurs `cold`, payload `cold`, graphe HNSW `cached`. Une collection créée avant W017 garde l'ancienne forme (`on_disk=true` pour les vecteurs, `false` pour HNSW, `on_disk_payload=true`), équivalente et encore acceptée par le contrôle. Pour une version ultérieure, migrer selon son schéma OpenAPI exact, sans dupliquer des paramètres incompatibles. Relire la configuration effective de la collection après création. La dépréciation du champ serveur n'autorise pas à deviner une forme équivalente de la requête API.

Créer les index de payload generation_id, version_id, document_id et page_indices. Le modèle actif impose collection, dimension et identité du pipeline ; une query emploie le vecteur nommé `dense`. BM25 reste dans SQLite. Ne pas optimiser l'index selon la seule taille des vecteurs : mesurer payloads, graphe, caches, segments et processus.

SQLite : WAL, foreign_keys, busy_timeout 5 000 ms et cache initial 32 Mio par connexion, peu de connexions et transactions courtes. `sqlite.busy_timeout_ms` et `sqlite.cache_size_kib` sont lus ; `journal_mode`, `foreign_keys` et `fts_tokenizer` n'ont qu'une valeur prise en charge, refusée sinon au démarrage (W021) ; `sqlite.path` est informatif : la base effective est `<app.data_dir>/app.sqlite3`. Tester FTS5 avec une vraie table temporaire. `config/lexical.sql` valide les triggers et le classement de base, pas toutes les migrations métier.

## 7. Ordonnancement, UI et plateformes

`resources.scheduling.pause_policy=cooperative_checkpoint`. La reprise automatique reste désactivée ; l'UI expose pause/reprise et les unités réellement achevées. Watchdog du worker d'extraction (`WorkerWatchdog`, `services/api/jobs.py`) : deux limites indépendantes lues dans `resources.scheduling` (interprétation à confirmer, point à trancher 7 du plan). Absence de progrès, `watchdog_no_progress_seconds_initial` (300 s) : aucun fichier nouveau ou modifié dans le dossier du travail (`window-*.json`, `docling-*.json`, `preflight.json`, `worker-lifecycle.jsonl`, `extraction.json`) et un temps CPU du worker et de ses descendants (Tesseract) inférieur à 10 % d'un cœur, mesuré toutes les 5 s. Durée maximale d'une fenêtre, `watchdog_window_seconds_initial` (900 s) : temps écoulé depuis la dernière fenêtre durable, même si le worker reste actif. Les deux seuils de mesure du CPU (10 % d'un cœur, 5 s) sont fixés dans le code. Chaque seconde de CPU est comptée une fois : sous Linux, celle d'un enfant terminé est lue dans les champs `children_*` de son parent ; sous Windows, la dernière valeur lue d'un enfant terminé est conservée. Le motif (`watchdog_no_progress` ou `watchdog_window_deadline`) et les durées observées sont enregistrés ; le travail passe en pause, reprise manuelle depuis les fenêtres durables. Ces plafonds sont des protections à qualifier, non une promesse de latence interactive. Une question peut attendre le prochain checkpoint ; elle doit voir cette attente. Annulation explicite et pression mémoire restent des motifs d'arrêt contrôlé.

Le nombre de workers ne borne pas toutes les allocations. Le gouverneur prend les pics mesurés et la réserve hôte avant admission. Remplacer progressivement les estimations prudentes par les mesures enregistrées, sans effacer leurs conditions.

L'UI utilise Next.js export statique, `out/` servi par FastAPI ; pas de serveur Node permanent. Worker PDF.js et viewer de même version, assets locaux. Le plafond de pixels inclut les miniatures ; libérer les canvases, annuler les rendus obsolètes et réduire le raster hors écran. Les positions des sélections sont des points de code Unicode dans le texte canonique hashé ; l'API ne reçoit pas des offsets UTF-16 non convertis.

Windows natif constitue la cible W001 ; Linux natif (aarch64, x86-64) la seconde plateforme (W018). Les données actives sont stockées dans la racine gérée (NTFS sous Windows, système de fichiers POSIX local sous Linux ; `.runtime/` et `.venv/` peuvent y être des liens vers un autre volume). Sous Linux, `pdf.tesseract_cmd` désigne le même emplacement sans le suffixe `.exe` (`platforms.native_executable`) : le binaire y est compilé par `provision` depuis les sources verrouillées. Clés lues ou bornées par le runtime sur les deux plateformes (W021) : `app.offline: true` et `app.telemetry: false` (profil refusé sinon), `app.asgi_workers: 1`, `llm.keep_alive` (transmis à Ollama et à la calibration), `llm.accelerator` (section 3), `resources.scheduling.initial_mode: interactive`, `resources.unload_llm_before_ingestion` (décharge le modèle avant chaque extraction). Clés informatives, sans lecteur dans le code : `qdrant.vector_storage_initial`, `qdrant.hnsw_storage_initial` (le placement réel vient de `qdrant.collection.json`), `embedding.qualification.*`, `resources.application_target_max_mib` (cible de mesure D07), `resources.scheduling.record_checkpoint_and_reload_costs`, la plupart des `ui.*` et `evaluation_targets.*`, et les clés `pdf.*` que l'ingestion gelée ne lit pas (W022). La recette inclut les services, le navigateur et la mémoire hôte. Aucun swap soutenu ne doit servir à masquer un dépassement de mémoire.

## 8. Versions, hors ligne et fichiers dérivés

`provision` résout puis verrouille les versions compatibles, modèles, tokenizers, quantifications, langues OCR et assets dans les manifests réels. `start` (sous-commande `up` du lanceur) ne télécharge rien. Pas de `latest` comme identité finale. Les `.env` ne remplacent pas le test de blocage réseau, la vérification Host/Origin et la suppression des chargements distants dans le rendu Markdown/PDF.

Après chaque changement canonique : régénérer le brief avec `python tools/build_brief.py`, puis contrôler avec `python tools/build_brief.py --check` et `python tools/verify_pack.py --report <fichier-neuf>.json` (Python 3.11 ou plus et PyYAML ; sans `--report`, `verify_pack.py` réécrit `CONTROLES_DOSSIER.json`, rapport suivi par Git). Ces outils, présents dans `tools/`, ne démarrent pas l'application. Les commandes produit décrites dans `IMPLEMENTATION.md` sont implémentées, sous d'autres noms et avec d'autres options, comme sous-commandes de `services/runtime/cli.py` (lanceur `rag.ps1` sous Windows) : `up` et `down` au lieu de `start` et `stop`, `verify` contrôle une sauvegarde et non une suite de recette, `restore` exige `--path` et `--target` ; détail des correspondances et des écarts dans [00_LIRE_AVANT.md](00_LIRE_AVANT.md#contrôles-du-dossier-disponibles) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md).


## Révision des paramètres et des dépendances

Avant toute décision significative de configuration ou mise à jour, consulter les sources officielles actuelles et le schéma de la version verrouillée conformément à [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md). Capturer les paramètres effectivement acceptés par le runtime ; ne pas transposer une option de branche récente à un ancien binaire.

Les recherches des agents ne sont pas une option réseau du profil `local16`. Aucun changement ici n'active la navigation, le téléchargement de skills ou la mise à jour automatique dans le produit. Les valeurs initiales restent à qualifier ; les changements et skills utilisés sont traçables dans les registres.
