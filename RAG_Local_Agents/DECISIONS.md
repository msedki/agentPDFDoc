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

**Conséquences :** l'identité de révision des preuves ultérieures est le commit Git ; les preuves antérieures restent liées aux manifestes de fichiers observés (`source_identity_kind: working_files_sha256_manifest`). Les rapports versionnés contiennent le nom d'hôte, le nom d'utilisateur Windows et les chemins/hashes des documents du corpus, jamais leur texte ni les originaux. Pas de force-push, de réécriture d'historique ni d'autre remote sans nouvelle demande.
