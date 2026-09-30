# Registre des décisions — V2.1

**Statut :** décisions de conception et règles de qualification. Aucune performance applicative mesurée n'est enregistrée dans cette version initiale.

| ID | Décision | Statut et condition de révision |
|---|---|---|
| D-01 | Local, CPU, hôte 16 Go maximum, mono-utilisateur | Invariant du produit ; ne pas contourner par GPU/cloud/swap soutenu |
| D-02 | Next.js statique + React/PDF.js, FastAPI, SQLite/FTS5, Qdrant | Socle retenu ; changement uniquement sur défaut démontré |
| D-03 | E5-small ONNX CPU INT8 est la baseline | Qualifier qualité, quantification et coût avant gel |
| D-04 | Un seul candidat comparatif : Granite 97M Multilingual R2 issu de l'audit | Essai conditionné à source/artefact officiel vérifiable ; sa non-vérification ne bloque pas E5 |
| D-05 | Docling routé natif / structuré / OCR régional | Couverture régionale, structure et provenance contrôlées ; pas de parsing lourd systématique |
| D-06 | Qwen3.5 4B Q4_K_M Ollama non-thinking | Candidat nominal ; CPU, template, mémoire et qualité à qualifier |
| D-07 | RRF + sélection finale sous contraintes | Invariant : identifiants explicitement visés et scope contrôlés après toutes les coupes |
| D-08 | Budgets de preuves 1 536 / 2 560 / 5 120 selon mode | Paramètres initiaux ; couverture nécessaire et plafond global respectés |
| D-09 | Pause coopérative ; reprise manuelle initiale | Aucun kill nominal de cinq secondes ; auto-reprise uniquement après qualification anti-ping-pong |
| D-10 | Vecteurs mappés, graphe Qdrant RAM/cache au départ | Placement à mesurer ; API et options relues dans le runtime verrouillé |
| D-11 | Texte source immuable, offsets Unicode et révision d'extraction | Invariant de sélection/citation ; fallback de granularité visible |
| D-12 | 200 questions annotées, 100 tenues à l'écart | Périmètre de qualification V2.1 ; dénominateurs/incertitude publiés |
| D-13 | Documents séparés canoniques, brief généré | Aucune édition manuelle divergente de la copie consolidée |

## Décisions de méthode ajoutées en V2.1

| ID | Décision | Statut et vérification |
|---|---|---|
| D-14 | Sources officielles obligatoires avant étude, décision significative, contrat nouveau ou mise à jour | Règle utilisateur ; réutilisation des preuves versionnées valides, revalidation des informations actuelles et des dérives |
| D-15 | Sélection des skills selon tâche, lecture préalable du vrai `SKILL.md`, provenance et permissions contrôlées | Cinq skills projet fournis ; installation native et comportement client non déclarés validés |
| D-16 | Étude SOTA limitée à un enjeu et à un test discriminant | Pas de benchmark brute-force ; pas de remplacement de stack motivé seulement par la nouveauté |

## Arbitrage d'une modification

Identifier le défaut et sa preuve ; définir une hypothèse ; tester un seul changement ciblé ; comparer avant/après à corpus, mode et matériel constants ; vérifier les non-régressions ; enregistrer la décision ; mettre à jour les contrats, paramètres, manifests et tests concernés. Une incompatibilité réelle de version est une raison de modifier un mapping, pas de réécrire le système.

La modification d'un choix qualifiable ne permet pas d'affaiblir un invariant ni de modifier discrètement un seuil de recette. Si le matériel ne passe pas un objectif, conserver le résultat et l'écart. Une donnée manquante n'est ni une mesure nulle ni une réussite par défaut.

Les paramètres initiaux ont un statut `BASELINE_TO_QUALIFY`. Le choix final devient `LOCKED_AFTER_EVIDENCE` uniquement avec référence à un rapport réel. Les caractéristiques du candidat non reconfirmées dans les sources restent `NOT_REVERIFIED`, sans déduction sur son existence.


Pour toute nouvelle entrée, ajouter source officielle/section, version documentée/installée, date de consultation, fait/hypothèse, résultat observé et fichiers affectés selon `RECHERCHE_ET_SKILLS.md`. Les décisions de conception préexistantes ne deviennent pas des résultats techniques validés du seul fait de leur présence dans ce registre.


## W001 Plateforme Windows native

**Date :** 30 septembre 2026, UTC. **Statut :** décision acquise de l'utilisateur ; réalisation native livrée par étapes, qualification complète encore ouverte. La description initiale ci-dessous est conservée ; PLAN et journal portent les exécutions ultérieures.

**Contexte :** le brief livré le 29 septembre visait Ubuntu natif ou Windows avec WSL2. L'inspection constate un poste Windows 11 et l'utilisateur impose explicitement une application fonctionnant ici sans WSL ni Docker, avec une mise en route comparable à Docker Compose.

**Choix retenu :** Windows 11 x86-64 natif est la cible de ce chantier. Aucun prérequis WSL, distribution Linux, moteur Docker ou conteneur. Conserver les composants applicatifs du brief et superviser leurs processus Windows depuis une entrée locale unique. Le contrat de cette entrée est décrit dans [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md) ; ce lanceur reste à réaliser.

**Justification :** exigence utilisateur prioritaire. Les sources officielles proposent un CLI autonome Ollama Windows, un artefact Qdrant serveur Windows x86-64 et une installation Docling Windows. Cela établit une voie documentaire native sans remplacer silencieusement Qdrant serveur par son client embarqué ; cela ne prouve pas encore leur fonctionnement ensemble sur ce poste.

**Conséquences :** provisionnement isolé, versions et hashes verrouillés, chemins NTFS explicites, environnements limités aux processus, supervision et arrêt ciblés, readiness réelle et sauvegardes cohérentes. D01/D07/D09 seront exécutés sous Windows natif. L'absence WSL/Docker est une conformité à la cible demandée, pas un prérequis manquant. Les marges de RAM restent applicables à Windows, aux processus natifs et au navigateur.

**Décision remplacée :** référence Ubuntu 24.04 et profil Windows WSL2 de la baseline documentaire v1.0. Les observations et copies canoniques initiales sont conservées comme état historique dans .runtime/reference-baseline-v1 ; les anciennes archives ont disparu lors de changements concurrents observés ; les documents séparés et cette décision portent la cible active. Aucune version exacte de runtime, aucune installation ni aucun résultat de recette n'est acquis par W001.

## W002 Adoption du brief V2.1

Date : 30/09/2026 UTC. Statut : acquise pour le chantier autorisé. L’archive V2.1 apparue dans le dossier remplace la référence v1.0 selon son propre cadrage. Le plan actif et le journal sont conservés. W001 garde priorité pour la plateforme. Aucun critère de recette n’est acquis par la seule synchronisation documentaire.

## W003 Admission mémoire mesurée et cache CPU borné

**Date :** 30 septembre 2026, 02:00 UTC. **Statut :** implémentation fondée sur pilote court, qualification complète pendante.

**Contexte :** l'estimation initiale de chargement Qwen 6144 Mio empêchait toute admission sur le poste occupé ; le pilote froid de 2970 tokens a échoué par latence de préfill, sans série mémoire persistée. Un second pilote contrôlé a réellement exécuté 279 tokens d'entrée et deux sorties de 64 tokens, CPU seul, contexte8192. [Preuve complète](reports/cpu-pilot-short-4threads.json) : somme RSS des processus du pilote, borne supérieure incluant les pages potentiellement partagées, pic3883,39 Mio ; hôte minimum2325,80 Mio. Ce n'est pas une preuve à3000/400tokens ni de résidence totale de l'application.

**Choix :** estimation froide4352 Mio (pic mesuré + environ469 Mio de marge), réserve hôte1536 Mio inchangée et surveillance active. Admission chaude distincte selon /api/ps, contexte/quantification/CPU vérifiés, estimation additionnelle512 Mio encore provisoire. Le cache de prompts llama-server est borné à256 Mio et deux checkpoints, au lieu du défaut observé8192 Mio/32 checkpoints. Les paramètres sont confirmés dans `--help` du binaire livré et dans le log du pilote réel. Première parité tokenizerHF/Ollama :279/279 ; autres formes de conversations restent à qualifier.

**Conséquences :** aucun changement de modèle, GPU ou seuil de performance. L'E5 résident est conservé tant que l'admission froide le permet ; si la marge manque après construction du contexte, seule sa session ORT peut être libérée, avec mesure du gain et du coût de rechargement. Pas de réextraction ni d'alternance LLM automatique. Toute chute de réserve annule la requête possédée ; aucun processus utilisateur arrêté. Revoir l'estimation selon les essais complets et retenir leur FAIL éventuel.

**Complément ingestion, 02:13 UTC :** première importation native via navigateur suspendue à5630 Mio disponibles contre5632 requis par estimation initiale4096+réserve1536. Nouvelle estimation parser2304 Mio fondée sur le pic réel de la suite mixte/scans1477,55 Mio RSS/1669,73 Mio private, avec environ635 Mio au-dessus du commit privé observé. Cette suite contient deux échecs OCR : la mesure de capacité ne les transforme pas en PASS de qualité. La réserve1536 reste inchangée, le worker atteint un checkpoint si elle est menacée ; borne de rendu raster et essai5pages à compléter. Reprise utilisateur explicite du même job après application du profil.

**Complément mémoire, 03:35 UTC :** la première question navigateur est refusée avant modèle,5095<5888Mio. La session E5 seule libère environ122Mio RSS/99Mio hôte ; résultat insuffisant. Étendre la même éviction conditionnelle aux caches Rust E5 et Qwen, sous leurs verrous, en conservant identités, template, configuration et contexte déjà compté.14 tests PASS ; gains/réinitialisations/parité réels encore à qualifier. Aucun changement de réserve ni arrêt de processus étranger.

## W004 Stockage Qdrant natif et chemins de restauration

**Date :** 30 septembre 2026,03:55 UTC. **Statut :** implémenté, restauration de stockage vérifiée ; parcours applicatif restant.

**Contexte :** snapshot peuplé identique restauré correctement sous racines courtes ASCII/Unicode, mais erreurs500/os3 ou os145 sur racine longue et sur essai de chemins étendus. L'inspection du snapshot trouve des suffixes jusqu'à175 caractères dans les index finaux et202 lors de la récupération temporaire. [Microsoft MAX_PATH](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation) explique le mécanisme ; ces observations ne prouvent pas que toute erreur os145 a cette unique cause. Le registre LongPathsEnabled vaut0 ; aucune modification système autorisée ni effectuée.

**Choix retenu :** `qdrant.storage_dir` désigne un stockage serveur court distinct. Une restauration neuve dont la racine dépasse le budget natif du schéma verrouillé alloue `.runtime/q/<identifiant8>`, refuse un emplacement déjà existant et inscrit le chemin absolu dans le profil/rapport. SQLite, originaux et extractions restent dans la destination Unicode longue. Le chemin storage est borné à57 caractères sur ce binaire/schéma ; la collection de diagnostic conserve un nom court. Préserver le défaut et les essais échoués, sans patch de binaire, registre ou migration de stockage actif.

**Justification et conséquences :** configuration officielle Qdrant1.19.1 `storage_path`/`snapshots_path` indépendante de la racine applicative, snapshot restauré dans un serveur neuf. [Essai réel](reports/restore-first-published-long-root-short-store-rerun.json) :21 fichiers source vérifiés,10copies de données hashées avant rebasing, comptes SQL inchangés,11points et arrêt Qdrant exit0. La destination restaurée dépend désormais aussi du stockage court indiqué ; ne la déplacer/copier ni purger seule. Utiliser backup/restore pour relocaliser l'ensemble. Un verrou Windows séparé protège ce stockage même entre profils avec racines/ports différents ;2 tests réels PASS après correction de la fixture trop longue. Les générations/réponses/anciennes citations restaurées restent à vérifier.

## W005 Dépôt Git et publication vers le remote privé

**Date :** 30 septembre 2026, 08:50 UTC. **Statut :** acquise, demande explicite de l'utilisateur.

**Contexte :** aucun dépôt Git n'existait (constat I01) ; les preuves ne pouvaient donc pas être associées à un commit comme l'exige la règle de clôture de DEFINITION_OF_DONE. L'utilisateur demande l'initialisation de Git, des fichiers d'exclusion et un commit/push de chaque travail substantiel vers `https://github.com/msedki/agentPDFDoc.git`. L'API GitHub publique répond 404 pour ce dépôt alors qu'un `git ls-remote` authentifié réussit : dépôt privé et vide au moment de l'initialisation.

**Choix retenu :** dépôt à la racine du projet, branche `main`, remote `origin`. `.gitignore` exclut `.runtime/` (binaires, modèles, données, QA, jetons d'administration), `.venv/`, `node_modules/`, builds, caches, corpus `PDF/`, bases SQLite, snapshots, secrets et sorties brutes Playwright ; les assets PDF.js régénérés au build sont exclus. `.gitattributes` désactive toute conversion de fin de ligne (`* -text`) pour que les manifestes SHA-256 restent vérifiables après clone, `core.autocrlf=true` étant configuré sur ce poste. `.dockerignore` protège un éventuel contexte de build, sans faire de Docker une cible (W001). Règle ajoutée à `CLAUDE.md` et `AGENTS.md` racine.

**Conséquences :** l'identité de révision des preuves ultérieures est le commit Git ; les preuves antérieures restent liées aux manifestes de fichiers observés (`source_identity_kind: working_files_sha256_manifest`). Les rapports versionnés contiennent le nom d'hôte, le nom d'utilisateur Windows et les chemins/hashes des documents du corpus, jamais leur texte ni les originaux. Pas de force-push, de réécriture d'historique ni d'autre remote sans nouvelle demande. **Complément 09:20 UTC :** identité unique `MOHAMED SEDKI <mohamed.sedki@live.fr>` en configuration locale, aucun trailer `Co-Authored-By` ni préfixe ; sur demande explicite, le seul commit publié `d349fa2` a été réécrit (arbre identique) et poussé avec `--force-with-lease` : `2d735f2`.

## W006 Modèle Qwen texte seul dérivé localement (sans encodeur vision)

**Date :** 30 septembre 2026, 09:20 UTC. **Statut :** implémenté et vérifié (dérivation, import, chargement, pilote mémoire) ; qualification applicative en cours.

**Contexte :** deux questions réelles refusées avant modèle par l'admission (5095 puis 5222 Mio disponibles contre 5888 requis). Le journal natif du pilote (reports/cpu-pilot-short-4threads.service.log) montre que llama-server charge le GGUF Qwen3.5 une seconde fois comme projecteur multimodal (`handle_qwen35_like_clip`, « estimated worst-case memory usage of mmproj is 961.74 MiB », tampon CLIP 223,30 Mio). Le code officiel d'Ollama v0.35.0 ([llm/llama_server.go](https://github.com/ollama/ollama/blob/v0.35.0/llm/llama_server.go), NewLlamaServerRunner, l. 867-895, consulté le 30/09/2026) active `--mmproj` dès que le GGUF d'architecture `qwen35` contient des tenseurs `v.*` ; aucune option ne le désactive. Le RAG n'envoie jamais d'image. Le blob verrouillé contient 393 tenseurs `v.*` (667 686 912 octets).

**Choix retenu :** `services/runtime/text_model.py` dérive un GGUF texte seul en retirant uniquement les tenseurs `v.*`/`mm.*` ; métadonnées KV et 441 tenseurs texte (dont la tête MTP, conservée pour garder le décodage spéculatif d'Ollama) sont recopiés octet pour octet et vérifiés tenseur par tenseur (SHA-256) avant publication. L'import passe par la voie officielle `ollama create` avec un Modelfile reprenant `RENDERER`/`PARSER`/`REQUIRES`, paramètres et licence de la source ([parser/parser.go](https://github.com/ollama/ollama/blob/v0.35.0/parser/parser.go)). Profil : `llm.model: qwen3.5:4b-text`, `llm.source_model: qwen3.5:4b`, manifeste d'identité séparé `.runtime/manifests/ollama-model-text.json`. `rag.ps1 pull-model [-Offline]` rejoue source puis dérivation, de façon idempotente.

**Preuves :** dérivation [text-model-derivation-20260930T0906.json](reports/text-model-derivation-20260930T0906.json) et manifeste complet [text-model-manifest-20260930T0906.json](reports/text-model-manifest-20260930T0906.json) : couche modèle `sha256:79b59ad9…` identique sur deux dérivations successives (déterminisme), licence `sha256:7339fa41…` et paramètres identiques à la source, manifeste `de8024db…`. Premier import conservé : licence altérée en CRLF par l'écriture Windows du Modelfile ([rapport](reports/text-model-derivation-first-crlf-license-20260930T0902.json)), corrigé (écriture LF + contrôle des couches licence/params) puis réimporté. Pilote [cpu-pilot-text-900-4threads-20260930T0911.json](reports/cpu-pilot-text-900-4threads-20260930T0911.json) : aucun projecteur chargé, 919 tokens, chute maximale de mémoire disponible 3327 Mio (contre ≈ 3810 avec vision au pilote de 279 tokens), RSS max 3329 Mio, privé max 4196 Mio.

**Conséquences :** même modèle texte (poids identiques), capacité image retirée ; `ollama show` liste encore `vision` car les clés KV sont conservées volontairement (aucune métadonnée modifiée). L'estimation d'admission doit être recalibrée sur ce modèle (décision suivante). Coût disque : +2,72 Go ; la source reste conservée pour la reproductibilité hors ligne.

## W007 Estimations d'admission recalibrées sur le modèle texte

**Date :** 30 septembre 2026, 09:25 UTC. **Statut :** acquise pour le profil `local16` ; réserve et seuils de recette inchangés.

**Contexte :** W003 fixait `initial_llm_load_peak_estimate_mib: 4352` (pic RSS 3883 Mio au pilote de 279 tokens avec projecteur vision + ≈ 469 Mio de marge non mesurée). W006 retire le projecteur. L'admission compare la mémoire disponible de l'hôte à « estimation + réserve 1536 Mio » ; la grandeur à prévoir est donc la baisse de mémoire disponible provoquée par le chargement et la génération.

**Mesures (modèle `qwen3.5:4b-text`, contexte 8192, 4 threads, CPU seul) :** [pilote 900 tokens](reports/cpu-pilot-text-900-4threads-20260930T0911.json) : baisse max 3327 Mio (minimum disponible 1954 Mio ; froid 3155, même préfixe 3193, contenu nouveau 3327) ; [pilote use_mmap](reports/cpu-pilot-text-900-4threads-mmap-20260930T0918.json) : baisse max 3298 Mio (départ 4945 Mio, minimum 1647 Mio). Chargements E5 relevés à l'E2E de 04:40 : tokenizer −266 Mio, session −146 Mio (≈ 412 Mio).

**Choix retenu :** `initial_llm_load_peak_estimate_mib: 3456` (baisse max mesurée 3327 + 129 Mio, ≈ 3,9 %) ; `embedding_load_peak_estimate_mib: 512` (412 mesurés + ≈ 24 %) lu par l'API au lieu du défaut codé 768 ; `warm_llm_additional_peak_estimate_mib` reste 512 (surcoût chaud observé ≈ 150 Mio, marge conservée faute de série). La marge réduite s'appuie sur la surveillance active du gouverneur, qui annule la requête possédée si la réserve est menacée ; la réserve `host_available_min_mib: 1536` n'est pas modifiée.

**Optimisation testée et rejetée :** `use_mmap: true` explicite, respecté par Ollama 0.35.0 ([server/sched.go](https://github.com/ollama/ollama/blob/v0.35.0/server/sched.go), `disableMmapDefaultReason`), est neutralisé pour ce GGUF par le correctif de compatibilité (« compat patch disabled mmap for transformed text tensors » ; tampon modèle `CPU` 812,70 Mio, non `CPU_Mapped`) : aucun gain, profil inchangé.

**Conséquences :** admission froide possible à partir de 4992 Mio disponibles (contre 5888). Sur ce poste partagé, la mémoire disponible observée varie entre ≈ 4,9 et 6,1 Gio selon la charge étrangère : une question peut encore être refusée ou attendre, ce qui est le comportement voulu. Le préfill (≈ 8,6 tokens/s, sans réutilisation de préfixe pour un contenu nouveau) reste la phase dominante des latences D07.

## W008 Attente bornée à l'admission de génération

**Date :** 30 septembre 2026, 14:05 UTC. **Statut :** implémenté, tests unitaires PASS ; effet réel mesuré au prochain essai.

**Contexte :** avec le modèle texte (W007), l'admission froide exige 4992 Mio disponibles. Sur ce poste partagé, la mémoire disponible fluctue entre environ 4,4 et 6,1 Gio selon des processus étrangers (navigateur, antivirus, autres outils) que le projet n'arrête pas. Question du 13:58 UTC sur l'instance restaurée : 5050 Mio avant la question, 4413 après chargement d'E5 pour la recherche, 4722 après libération des caches (+308 Mio), refus immédiat à 4723 < 4992 ([preuve](reports/backend/2026-09-30-restored-question-newcode-20260930T1358.json)). L'interface prévoyait déjà l'état « En attente de mémoire disponible » (`waiting_for_resources`) sans que l'API l'émette.

**Choix retenu :** `resources.generation_admission_wait_seconds: 120`. Le gouverneur remesure toutes les 2 s jusqu'à cette limite ; la première insuffisance émet un événement SSE `waiting_for_resources` (mémoire disponible et requise), puis la question est admise dès que le seuil est atteint ou refusée à l'échéance. La réserve de 1536 Mio, les estimations et la surveillance pendant la génération sont inchangées ; l'annulation reste possible pendant l'attente. 0 rétablit le refus immédiat.

**Conséquences :** une fluctuation de courte durée ne fait plus échouer une question ; une pénurie durable reste refusée avec son motif. Pendant l'attente, le verrou lourd du poste est tenu : aucun import ne démarre.
