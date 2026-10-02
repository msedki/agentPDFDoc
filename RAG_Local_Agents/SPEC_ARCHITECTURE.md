# Spécification et architecture — V2.1 corrigée

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md). **W018 (01/10/2026) : Linux natif (aarch64 et x86-64) devient une seconde plateforme**, toute machine Windows restant prise en charge comme avant ; réalisation en cours (lots J du [plan](PLAN.md)). **W024 et W025 (01/10/2026) : le CPU reste le socle, le repli et la référence de la recette D07 ; seule la génération par Ollama peut passer sur GPU, automatiquement sur les voies qualifiées par un essai réel** ([W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024)). L'objectif O4 garde sa formulation d'origine : aucun GPU n'est requis.

**Baseline de conception :** RAG-LOCAL-16 v2.1. Les invariants sont obligatoires ; les paramètres initiaux sont qualifiés selon `QUALIFICATION.md` puis verrouillés. Voir `DECISIONS.md` et les références de `SOURCES.md`.

## 1. Objectifs et contraintes

**O1 — Trouver :** rechercher une expression, un identifiant technique ou une notion dans un périmètre documentaire choisi.
**O2 — Comprendre :** obtenir une réponse ou une analyse explicitement appuyée sur les passages effectivement transmis au modèle.
**O3 — Vérifier :** ouvrir depuis une citation le bon original, dans la bonne version, à la page et à la zone concernées.
**O4 — Maîtriser :** exploiter le tout localement sur 16 Go de RAM sans GPU, avec reprise, diagnostic et sauvegarde.

Usage nominal mono-utilisateur. Langues de recette : français et anglais. L'arabe n'est pas interdit, mais sa qualité, notamment en OCR, n'est pas déclarée validée par la recette FR/EN.

Enveloppe de qualification choisie : bibliothèque de 1 000 PDF maximum dans le benchmark initial, avec un test de charge atteignant **au moins 25 000 chunks**. Ce n'est pas une limite absolue de la base ni une capacité déjà démontrée. Le nombre réel de pages, de chunks et de vecteurs doit être enregistré.

Un document peut aller jusqu'à 200 Mio et 2 000 pages dans la configuration initiale. Ces garde-fous sont configurables ; un dépassement provoque un refus explicite, jamais une indexation tronquée présentée comme complète.

Référence système : Windows 11 Entreprise x86-64 natif, 16 Gio physiques, SSD, CPU Intel Core i5-1235U observé (10 cœurs / 12 logiques). Aucun runtime WSL/Docker. Réserve hôte incluant navigateur et processus Windows ; espace disque observé, sans capacité inventée.

## 2. Stack retenue et décisions à qualifier

| Couche | Décision | Mise en œuvre |
|---|---|---|
| UI | Next.js + React + TypeScript | Export statique ; une route `/workspace/`, identifiants dans les query parameters |
| Composants UI | Tailwind CSS + shadcn/ui | Composants locaux, accessibles ; pas de police/CDN externe |
| État UI | Zustand + TanStack Query | Zustand : sélection/panneaux ; Query : état serveur, invalidation après indexation |
| Lecteur | PDF.js (`pdfjs-dist`) | Worker et assets locaux ; canvas + text layer + overlays de provenance |
| Backend | Python 3.12 + FastAPI + Pydantic | Un worker ASGI ; API JSON et SSE ; statique servi par le même backend |
| Métadonnées et lexical | SQLite + FTS5 | WAL, clés étrangères, transactions courtes ; BM25 et index d'identifiants |
| Vecteurs | Qdrant, serveur local | Une collection active par identité complète d’embedding ; 384D pour E5 ; filtres version/page ; graphe en RAM au départ, à mesurer |
| Embeddings | `intfloat/multilingual-e5-small` nominal | ONNX Runtime CPU INT8 ; préfixes, tokenizer, pooling et norme E5 ; un seul candidat comparatif autorisé avant gel |
| Extraction | Docling | Routage natif léger / structuré / OCR régional ; représentation et provenance canoniques communes |
| OCR | Tesseract via Docling | FR/EN préinstallés ; couverture par région, y compris texte natif + tableau scanné sur une même page |
| Précontrôle PDF | pypdfium2 | Géométrie, compte de pages, couche texte et images de contrôle à la demande |
| Génération | `qwen3.5:4b` via Ollama | Quantification Q4_K_M à vérifier au provisionnement ; contexte 8 192 ; mode non-thinking |
| Jobs | SQLite + processus supervisé | Pas de Redis ni de Celery ; checkpoints et reprise idempotente |
| Qualité | pytest, Playwright, Ruff, type-checking | Tests réels aux frontières, snapshots UI et mesures ressources |
| Dépendances | uv + pnpm | Lockfiles exacts, caches/export hors ligne ; versions enregistrées |

E5-small est la baseline opérationnelle, pas un vainqueur établi. Sa qualité doit satisfaire la recette. L'unique candidat comparatif issu de l'audit est `ibm-granite/granite-embedding-97m-multilingual-r2` : vérifier existence, licence, révision et contrat d'inférence avant essai. En l'absence d'artefact officiel vérifiable, enregistrer `CANDIDATE_UNAVAILABLE`, poursuivre avec E5 et ne pas inventer un benchmark. Procédure de choix dans `QUALIFICATION.md`. Les caractéristiques E5 sont référencées en S04.

SQLite fournit le lexical parce qu'il est déjà requis pour l'application. Qdrant reste uniquement responsable de la recherche dense. La fusion est explicite dans le backend ; aucune fonctionnalité BM25 native de Qdrant n'est supposée.

PyMuPDF n'est pas une dépendance nominale. Son projet documente AGPL/commercial (S13) ; ce choix évite d'introduire par défaut cette décision de licence. Les licences des dépendances et poids réellement livrés restent à inventorier. « Local » ne signifie pas « sans obligations de licence ».

## 3. Architecture d'exécution

```text
NAVIGATEUR — http://127.0.0.1:8765
  Next.js export statique / React / PDF.js
  ├── bibliothèque et arborescence
  ├── PDF, sommaire, texte sélectionnable, overlays
  └── recherche, analyse et chat avec sources
                         │ même origine ; REST + SSE
                         ▼
FASTAPI — un processus serveur, un worker ASGI
  ├── LibraryService / VersionService
  ├── SearchService / ScopeResolver / CitationService
  ├── ContextBuilder / OllamaGateway
  ├── EmbeddingService — une session ONNX CPU
  └── JobSupervisor / ResourceGovernor
       │                 │                   │
       ▼                 ▼                   ▼
 SQLite + FTS5        Qdrant :6333        Ollama :11434
 source de vérité     vecteurs denses     Qwen3.5 4B Q4
       │
       └── Docling/Tesseract worker isolé, lancé et libéré à la demande

DISQUE LOCAL
  originaux immuables / versions / extraction JSON / caches / modèles /
  SQLite / Qdrant / logs limités / snapshots cohérents
```

Pas de serveur Next.js en production, SSR, API routes Next ou Server Actions. Les mutations et données dynamiques passent toutes par FastAPI. L'export statique de Next.js est documenté en S09. Les fichiers PDF sont servis par une route contrôlée avec support HTTP Range, jamais par l'exposition brute d'un répertoire système.

Le navigateur ne contacte directement ni Ollama ni Qdrant. Les processus n'écoutent que sur loopback. Le mode LAN/multi-utilisateur est hors périmètre de cette version.

## 4. Parcours et UX contractuels

Disposition initiale redimensionnable : bibliothèque environ 22 %, PDF 48 %, analyse 30 %. Panneaux repliables et dimensions persistées. Interface sobre, contrastée ; pas de marque ou logo imposé sans fichiers fournis.

L'arborescence conserve les sous-dossiers importés, affiche nom, état et progression d'indexation. Elle permet sélection simple/multiple, recherche de fichier et ouverture. États distincts : importé, en attente, extraction, OCR, indexation, prêt, prêt partiellement, erreur, supprimé. Une erreur indique une cause exploitable et l'action permise.

Le lecteur fournit pages, zoom, rotation, recherche locale, sommaire disponible, sélection de texte, retour à la position précédente et ouverture de source. Les pages sont virtualisées : au plus cinq canvases haute résolution autour du viewport, sous un plafond global initial de 24 millions de pixels RGBA, miniatures incluses ; ne pas utiliser le nombre de pages comme seul contrôle mémoire. Réduire le rendu des pages hors écran et le zoom raster avant de dépasser ce budget. Les miniatures sont paresseuses et bornées. Une page scannée expose le texte OCR via une couche de sélection lorsque ses coordonnées sont disponibles ; sinon l'analyse de page reste possible avec cette limite visible.

Le panneau d'analyse possède recherche sans génération, question/réponse, analyse de sélection, analyse de section/pages et comparaison ciblée de deux à quatre PDF. Il affiche état de travail, annulation, réponse progressive, extraits des sources et statut des citations.

**Périmètre actif :** toujours explicite et visible. Les options sont bibliothèque, dossier avec descendants, documents sélectionnés, section, plage de pages, sélection. Une question garde le snapshot de périmètre et de versions pris à son envoi. Un clic de citation n'élargit pas le périmètre. Le scope par défaut est résolu une seule fois à l'initialisation ou lors d'une action explicite, jamais recalculé automatiquement parce qu'une citation a ouvert un autre PDF. Changer de page ne le change pas non plus. Pour une réponse ultérieure portant sur le passage affiché, l'utilisateur choisit « Analyser cette page/sélection ».

**Sélection directe :** envoyer les références de spans/blocs et positions sélectionnés ; le backend recharge le texte depuis la version connue. Ne pas prendre un texte client arbitraire comme preuve documentaire. Les offsets sont en points de code Unicode sur le texte exact immuable du bloc, avec hash et révision d’extraction ; le front convertit ses offsets UTF-16. Aucun retrieval global pour une sélection qui tient dans le budget.

**Comparaison :** assurer une recherche par document puis un contexte équilibré. Présenter convergences, différences et éléments non trouvés, avec sources de chaque côté. L'absence de résultat n'est pas une preuve d'absence dans le document.

**Résumé :** un résumé de section courte peut utiliser son texte intégral. Un résultat issu de top-k doit être nommé « synthèse des passages retrouvés », jamais « résumé exhaustif du PDF ». La synthèse intégrale de très gros dossiers est exclue du noyau initial.

## 5. Données et provenance

SQLite est la source de vérité pour : `folders`, `documents`, `document_versions`, `extraction_revisions`, `index_generations`, `pages`, `blocks`, `sections`, `tables`, `chunks`, `chunk_sources`, `identifiers`, `jobs`, `conversations`, `messages`, `citations`, `query_runs` et `events`.

| Objet | Champs indispensables |
|---|---|
| Document | UUID logique, dossier, nom original, chemin relatif, état, génération active |
| Version | UUID, document UUID, SHA-256 des octets, blob immuable, nombre de pages, métadonnées sources |
| Génération d'index | UUID, version UUID, fingerprint du pipeline, état, compte attendu/réel de chunks |
| Page | index physique zéro-based, numéro UI un-based, label imprimé/PDF facultatif, MediaBox, CropBox, rotation, dimensions |
| Révision d’extraction | UUID, version, fingerprint parseur/routage, couverture et blocs immuables |
| Bloc | ID stable dans la révision d’extraction, type, texte source exact + SHA-256, normalisation et mapping séparés, section, provenance originale |
| Chunk | UUID, génération, parent, contenu, nombre de tokens E5 et LLM, sources ordonnées, hash |
| Citation | query ID, source ID, version + révision d’extraction + génération, page(s), bloc(s), texte exact retenu, bbox/polygones ou précision page |

Ne pas fabriquer date, auteur ou version métier depuis une supposition. `version_id` technique est distinct d'une mention « V3 » imprimée. Le nom de fichier n'est ni un ID ni une garantie de version.

**Géométrie canonique :** enregistrer les coordonnées PDF non tournées, en points dans l'espace utilisateur du PDF, avec CropBox et rotation. Conserver aussi la géométrie originale du parseur et son origine. Un adaptateur testé transforme celle de Docling en géométrie canonique. Le frontend utilise le viewport PDF.js pour le zoom, la rotation et les overlays. Ne pas réduire la conversion à `y = hauteur - y` sans examiner origine, recadrage et rotation.

La granularité annoncée est `span`, `block`, `table` ou `page`. Si seule une bbox de bloc existe, afficher « passage/bloc source », pas « mots exacts ». Sans coordonnées fiables, ouvrir la page et afficher « localisation à la page ». Aucune bbox ne doit être inventée pour embellir l'interface.

Les textes d'embedding peuvent contenir un préfixe de section et des en-têtes de tableau répétés. Ces ajouts servent la recherche ; ils ne deviennent pas automatiquement des citations supplémentaires.

## 6. Pipeline documentaire

Importer en streaming, valider taille/signature/chemin, copier les octets dans un blob immuable identifié par SHA-256. Dédupliquer sur hash + fingerprint de l'étape ; conserver séparément les caches d'extraction, de découpage et d'embeddings. Changer le modèle dense ne justifie pas de recommencer l'OCR.

**Routage Docling :** précontrôle natif et géométrique → voie native sur les contenus simples validés → voie structurée sur les layouts/tables difficiles → OCR régional sur les zones imprimées sans texte fiable. La voie native actuelle n'exécute pas les modèles de layout, de tableaux ou d'OCR ; elle doit être entourée d'un contrôle applicatif de qualité [S14].

| Route | Entrée et comportement | Condition de succès |
|---|---|---|
| `native` | Texte numérique fiable ; cellules et images natives ; pas de modèles lourds | Ordre de lecture contrôlé, structure utile récupérée ou limite visible |
| `structured` | Colonnes, tableaux ou ordre de lecture ambigus | Blocs/sections/tableaux cohérents ; contrôle des unités et cellules |
| `regional_ocr` | Région scannée ou texte corrompu, même sur une page contenant déjà du texte natif | Région reconnue, géométrie conservée, absence de duplication avec le texte natif |
| `unresolved` | Contenu graphique ou extraction non fiable | Figure conservée, limite explicite, aucune interprétation inventée |

Ne pas décider « pas d'OCR » à partir du seul nombre de caractères d'une page. La fixture obligatoire « paragraphe natif + tableau scanné » doit indexer les deux régions. Une image décorative ou un schéma sans texte exploitable ne justifie pas un OCR systématique. Les métriques sont par page **et par région** : native, OCR, non résolue, blanche, graphique.

Contrôler séparément les threads du parseur natif et ceux des modèles. Les noms d'API et d'options sont mappés à la version verrouillée, pas envoyés tels quels depuis le YAML applicatif. Vérifier les modes OCR de S15 ; ne pas mélanger option ancienne et option nouvelle.

Les fenêtres de quatre pages restent des unités initiales de checkpoint, pas des frontières sémantiques. Persister les pages/blocs terminés et leur manifeste. Reconstituer sections, listes et tables traversant une fenêtre ; une continuation de table n'est validée que si sa relation est démontrée. Réutiliser un worker et ses modèles pendant une session bornée d'ingestion sans cumuler plusieurs pipelines lourds résidents. Le test de frontière utilise notamment les pages physiques 4 et 5.

Découper aux frontières structurelles. Baseline E5 : cible 320 tokens, entrée préfixée maximale 448 tokens, recouvrement maximal 48 seulement pour une coupe de bloc nécessaire. Garder le texte canonique et la provenance distincts du texte enrichi d'embedding. Lors de la comparaison d'embeddings, utiliser un manifeste commun de fragments dont chaque entrée respecte le tokenizer et le format du modèle concerné ; toute adaptation de découpage doit être déclarée, pas assimilée à un pur gain de modèle.

Conserver figures/légendes et structure des tableaux. Sérialiser les tableaux avec unités et en-têtes répétés pour les groupes de lignes, sans inventer les cases manquantes. Ne pas prétendre analyser le graphique en l'absence de voie vision qualifiée.

## 7. Recherche et réponse

Chemin nominal : scope et versions figés → résolution du référent conversationnel → recherche exacte/lexicale + embedding query et recherche dense → RRF → sélection finale contrainte → contexte vérifiable → une génération Ollama → validation des citations.

Les filtres sont appliqués avant top-k dans les deux branches, puis après expansion des parents. Les scores ne sont pas des probabilités. Une requête visant explicitement un identifiant nécessite une preuve pertinente portant cet identifiant **dans le contexte final**, pas seulement en tête du lexical. La contrainte ne remplace pas la pertinence : sinon, afficher « identifiant trouvé, information demandée non trouvée » ou « référence non retrouvée ».

Dense top 24 + lexical top 24 restent les valeurs de départ. RRF k=60 est conservé pour la fusion. Au plus six fragments par défaut, extensibles à huit pour une comparaison ou plusieurs identifiants, toujours sous le plafond de tokens ; si toutes les preuves nécessaires ne tiennent pas, signaler la couverture partielle. Ne pas compléter un quota avec des passages non pertinents.

Budget ordinaire de preuves : 2 560 tokens LLM, cible réduite à 1 536 pour une question factuelle, jusqu'à 5 120 pour analyse/comparaison. Ce sont des plafonds de modes, pas des objectifs à remplir. Une preuve obligatoire ne doit pas être perdue pour respecter un budget nominal : étendre jusqu'au plafond autorisé ou annoncer la limite. Mesurer `EvidenceCoverage@Context` après la sélection, les déduplications et toutes les coupes.

Une relance telle que « Et sa tolérance ? » utilise un référent explicite issu de la question utilisateur, d'une sélection ou d'une source choisie, jamais un fait affirmé par le modèle précédent. Si le référent est ambigu, demander une précision sans lancer de recherche globale hasardeuse. Un changement de scope invalide les référents hors périmètre ; l'historique n'est pas un canal de réintroduction de documents exclus.

Qwen reçoit uniquement les preuves autorisées et le contexte conversationnel explicitement non probant. Pas de navigateur, de shell, de système de fichiers ni de tool calling. Les sources sont des données non fiables délimitées. La recette distingue intégrité de citation, localisation et soutien de l'assertion.

## 8. Budget CPU/RAM et ordonnancement

Une génération LLM active maximum ; un worker PDF lourd maximum ; pas de parsing/OCR lourd simultané avec la génération. E5 dispose d'une session ONNX indépendante. Le worker d'extraction reste hors du processus API. L'indexation lourde ne doit pas bloquer les routes de santé et de navigation.

Deux modes visibles : `interactive` et `ingestion`. À l'arrivée d'une question pendant l'ingestion, demander une pause coopérative, persister la frontière sûre la plus proche, libérer les modèles lourds, puis admettre la génération. Afficher `waiting_for_ingestion_checkpoint` si nécessaire. **Ne pas tuer le worker au bout de cinq secondes en fonctionnement normal.** L'arrêt forcé est réservé à un watchdog de blocage, une limite de ressource ou une demande explicite de l'utilisateur, avec motif et reprise vérifiable.

La reprise automatique après inactivité est désactivée dans la baseline initiale : l'utilisateur choisit « Reprendre l'indexation ». Elle pourra être activée après mesure, avec un délai dérivé des coûts de checkpoint et de rechargement et un essai chat/import prouvant l'absence de ping-pong. Les jobs en pause restent visibles ; ne pas prétendre empêcher automatiquement toute attente ou famine alors que l'utilisateur reste en mode interactif.

En session ingestion, réutiliser les modèles compatibles tant que le budget le permet ; à la bascule interactive, vérifier réellement leur libération. Mesurer nombre de chargements, temps de travail utile, temps d'initialisation et travail repris après interruption. Les fenêtres initiales de quatre pages sont ajustables selon les durées observées, en conservant les mêmes contrats de provenance.

Budget de conception : application <= 10 Gio de résidence non dupliquée et au moins 1,5 Gio disponibles sur l'hôte. Admettre un travail lourd seulement si son pic additionnel prévu, sa marge et la réserve hôte peuvent être tenus. Estimations prudentes initiales : 6 Gio pour un chargement LLM et 4 Gio pour le worker structuré, à remplacer par les mesures. Ce ne sont pas des garanties constructeur.

Le profil Qdrant débute avec vecteurs mappés et graphe en mémoire/cache ; repli sur graphe froid si la mesure de l'ensemble le nécessite. Les 25 000 vecteurs 384D float32 représentent seuls environ 36,6 Mio : ajouter graphe, payloads, caches et processus au budget. Le stockage sur disque n'est donc ni interdit ni imposé sans mesure. Les API de placement mémoire doivent être validées contre le runtime retenu [S08].

Qualifier très tôt le CPU réel : mémoire totale, chargement, traitement du contexte, génération, navigation et cache chaud/froid. Ne pas inférer la vitesse à partir des seuls 16 Go. Les cibles de latence restent des objectifs de recette ; conserver `FAIL` si elles ne sont pas atteintes.

## 9. Exclusions explicites du noyau

Pas de GraphRAG, reranker neural, indexation vision, agents autonomes au runtime, fine-tuning, cloud fallback, moteurs de recherche multiples interchangeables, collaboration multi-utilisateur ou éditions du PDF original. Pas de synthèse prétendument exhaustive d'un gros corpus à partir de six passages. Ajouter une extension uniquement après preuve de valeur et requalification CPU/RAM.


## Gouvernance technique des agents

La décision, l'étude d'une amélioration et la maintenance suivent [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md) : sources officielles actuelles, contrat de version, essai pertinent et décision tracée. Les invariants restent fixes ; une nouvelle publication peut justifier un essai, pas un changement automatique de stack.

Le registre [SKILLS.md](SKILLS.md) oriente les agents vers les compétences utiles. Ce dispositif est extérieur au runtime du RAG : le petit LLM local ne reçoit ni ces skills, ni Internet, ni shell. Consigner les changements dans `DECISIONS.md`, les contrats, le profil et les tests concernés.
