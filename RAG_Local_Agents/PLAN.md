# Plan de réalisation vivant — initialisé, aucun travail applicatif déclaré terminé

**Objectif actif depuis le `/goal` du 30 septembre 2026 :** réaliser, intégrer et qualifier l'application RAG PDF locale sur Windows natif, sans WSL ni Docker, jusqu'aux critères exacts du plan et de DEFINITION_OF_DONE. L'inspection préalable reste conservée comme référence ; elle n'est pas répétée.

**Périmètre daté :** inspection des 29/30 septembre 2026 puis réalisation autorisée le 30 septembre, UTC. Brief actif RAG-LOCAL-16 V2.1 (archive vérifiée) et décision utilisateur W001 : **Windows natif, sans WSL ni Docker**, orchestration locale comparable à Docker Compose. Sources, configuration et corpus identifiés par empreintes ; aucun dépôt Git lors de l'inspection (dépôt créé à 08:50, W005). Provisionnement isolé, téléchargements officiels, services locaux, OCR, builds et tests du chantier sont désormais autorisés. Exclusions conservées : modification globale de configuration système, destruction des originaux ou données étrangères, arrêt de services étrangers et déploiement externe. Depuis 08:50 UTC (W005), Git est initialisé et commit/push sont autorisés uniquement vers le remote privé `origin` https://github.com/msedki/agentPDFDoc.git, après chaque travail substantiel vérifié ; corpus, runtimes, modèles, données et secrets restent exclus du dépôt. Résultat attendu : application réelle, preuves de recette et documentation fidèle.

**État initial du brief conservé :** brief et configurations disponibles ; aucun code applicatif à la remise. L'inspection préalable ne valide ni le lot A complet ni D01–D11. Les états courants des lots sont actualisés ci-dessous, sans effacer cette baseline.

## Inspection autorisée et état courant

| ID | Couche et résultat attendu | Dépendances | Critère de validation | Statut | Preuve |
|---|---|---|---|---|---|
| I01 | Documents, architecture et intégrité du pack compris | Instructions applicables | Lecture des références, comparaison archive/extrait et manifestes | VERIFIED | Rapport d'inspection à consolider ; contrôles SHA-256 avant mise à jour du suivi : 20/20 et 18/18, archive 21/21 |
| I02 | CPU, RAM, GPU, disques et charge observés | Accès lecture machine | Mesures CIM datées et distinction capacité/disponibilité | VERIFIED | Relevés Windows des 29/09/2026 23:56–23:59 UTC ; rapport à consolider |
| I03 | Node, Python, OCR et plateforme disponibles identifiés | I02 | Versions exécutées, paquets et chemins vérifiés, absence PATH distinguée de l'installation | VERIFIED | Python 3.13.3 hors PATH, Node 22.17.0, pnpm 10.34.1 ; rapport à consolider |
| I04 | Corpus caractérisé et diagnostic écrit | I01, I02, I03 | Comptes/hashes/pages, inspection structurelle et visuelle, rapport et journal reliés | VERIFIED | reports/INSPECTION_DOSSIER_MACHINE_2026-09-30.md, reports/preuves-inspection-2026-09-30/corpus-inspection.json ; 182 pages et 24 échantillons visuels |
| I05 | Contrainte Windows native intégrée au référentiel | Décision utilisateur W001 | Documents actifs cohérents sans prérequis WSL/Docker ; voie native prouvée par sources officielles et contrat d'exploitation explicite | VERIFIED | DECISIONS.md, EXPLOITATION_WINDOWS.md ; les runtimes eux-mêmes ne sont pas encore qualifiés |

Les lots applicatifs du graphe suivant sont désormais autorisés par le `/goal` utilisateur du 30 septembre. Le suivi ci-dessous distingue réalisation en cours et validation acquise ; aucune case de recette n'est cochée par anticipation.

## Pilotage

Mettre à jour après résultat, décision ou blocage significatif. Un résultat `VERIFIED` doit pointer vers sa preuve et les critères de recette associés. États de travail : `NOT_STARTED`, `READY`, `IN_PROGRESS`, `BLOCKED`, `VERIFIED`. Seul le propriétaire d'intégration modifie les contrats partagés et les lockfiles communs.

## Graphe de dépendances, pas un plan en cascade

```text
A — inspection + précontrôles + contrats minimaux
├── B — ingestion, versions, provenance et géométrie
├── C — SQLite/Qdrant, embeddings, retrieval et API
├── D — UI, PDF.js, état/scope et citations
└── E — fixtures, outillage, offline, ressources et recette

B + C + D + appuis E -> V — première chaîne verticale réelle
V + résultats indépendants B/C/D/E -> F — robustesse et recette complète
```

Les branches B/C/D/E progressent en parallèle après leurs contrats minimaux, sans attendre qu'une branche entière soit achevée. V doit être intégré tôt, pas reporté après la finition de tous les écrans. La coordination ne doit pas saturer la machine avec plusieurs travaux lourds.

| ID | Résultat observable | Dépendances minimales | Propriétaire logique | État initial | Critères |
|---|---|---|---|---|---|
| A | Inventaire existant, doctor initial, contrats Scope/Citation/Chunk/QueryEvents, versions résolues | Accès dépôt/outils | Intégrateur | IN_PROGRESS | D01 ; packages/contracts/contracts.json présent, runtimes et doctor en préparation |
| B | Un PDF réel converti en blocs et provenance testable, indexation reprenable | Contrats version/page/bloc | Agent ingestion | IN_PROGRESS | D02,D03,D06 ; skill pdf-ingestion-windows créé et validé, code en cours |
| C | Requête scope → vrais BM25 et Qdrant → preuves et vraie génération locale | Contrats chunks/scope/events | Agent retrieval/API | IN_PROGRESS | D04,D05 ; frontières API/ingestion/governor partagées, code en cours |
| D | Trois panneaux et navigation citation→PDF fonctionnant contre API réelle | Contrats UI/API | Agent UI/PDF | IN_PROGRESS | D06 ; skill pdf-workspace-web créé et validé, versions npm officielles résolues |
| E | Fixtures, doctor, runners, traces réseau et mémoire, scripts exploitation | Structure et contrats utiles | Intégrateur qualité/exploitation | IN_PROGRESS | D01,D07,D08,D09 ; skill windows-rag-runtime créé, lu et validé |
| V | Import→extraction→index→question→réponse→clic→surlignage | Première version intégrable de B/C/D | Intégrateur | IN_PROGRESS | D02,D04,D05,D06 ; DEV publié, recherche et lecteur vérifiés ; première question refusée avant modèle par admission mémoire |
| F | Recette complète et rapport honnête sur machine cible | V et critères applicables | Intégrateur + vérificateur | NOT_STARTED | D01–D11 |

## Répartition de fichiers

B possède `services/ingestion/` et ses tests. C possède les modules search/context/embedding/citations du backend et leurs tests. D possède `apps/web/`. E possède fixtures, evals et scripts qualité/exploitation. L'intégrateur possède `packages/contracts/`, les migrations partagées, les routeurs communs, la configuration et les lockfiles. Ajuster la répartition à l'existant sans écraser les travaux étrangers.

Répartition actuelle déléguée : B possède ingestion et ses tests ; C possède `services/api/`, y compris ses migrations/routeurs SQLite, et ses tests ; D possède frontend, package et lockfile propres à `apps/web/`. L'intégrateur possède `services/runtime/`, scripts, configuration, contrats, dépendances Python, fixtures/évaluations et suivi. Chaque agent crée/lit son skill spécialisé avant de coder. Les installations et tâches lourdes sont séquencées par l'intégrateur ; contrôle régulier de RAM/CPU/disque, aucun OCR/build/benchmark lourd concurrent.

## Points vérifiés et décisions restantes

Vérifiés : inventaire initial sans code/Git, corpus de cinq documents dont 182 pages PDF image, CPU 10 cœurs/12 logiques et 16 Gio, Python 3.13 installé hors PATH, Node/pnpm exécutables, sources officielles de binaires Ollama/Qdrant Windows. La présence de dépendances n'est pas une preuve d'intégration.

Décision acquise : Windows natif W001. Le noyau accepte les PDF ; le DOCX original est conservé hors de l'index PDF tant qu'un contrat métier distinct n'est pas demandé. Les scans PDF fournis constituent le corpus métier autorisé. La collision du port 8765 sera traitée par configuration explicite du projet, sans arrêt du programme existant.

Dernier relevé avant provisionnement : 30/09/2026 00:15:55 UTC, environ 4,39 Gio disponibles, 39,24 Gio libres sur D:. Ces valeurs évoluent ; aucune admission lourde n'est déduite de ce seul relevé. Prochaine action exécutable : provisionner uv/Python isolés et les dépendances verrouillées, puis intégrer les premiers résultats B/C/D et mesurer une tranche réelle.

Les mocks contractuels temporaires sont admis pour débloquer une branche, avec un marquage explicite. Ils sont retirés du chemin de livraison avant V et ne donnent aucun PASS E2E.

## Première tranche verticale

Un PDF natif FR contrôlé contenant une valeur technique identifiable, une section et une table simple. L'utilisateur l'importe, le voit dans le dossier, pose une question, obtient une réponse du vrai Ollama avec ID de preuve ; le clic ouvre la page et le bloc. Conserver la trace de toute la chaîne et les compteurs réels. Étendre ensuite aux difficultés en gardant cette tranche en non-régression.

## Règle de déblocage

Un blocage doit préciser symptôme, preuve, hypothèse, test déjà effectué, propriétaire et prochaine action discriminante. Un agent bloqué sur une dépendance ne réécrit pas le composant d'un autre : il réalise une tâche indépendante prête ou réduit le cas de test qui manque.

Un changement de stack n'est recevable que si la baseline échoue sur un cas mesuré et qu'un changement limité corrige ce cas dans le budget. Ne pas repartir en benchmark général après une erreur de paramétrage.

## État à renseigner pendant l'exécution

Le journal doit enregistrer les faits nouveaux sous forme date/ID/résultat/preuve/décision. Au moment de remise de ce brief : **aucune preuve d'exécution applicative, aucune performance cible et aucun critère D01–D11 ne sont déclarés validés**.

## Intégration V2.1 — 30/09/2026 UTC

Références : [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md), [QUALIFICATION.md](QUALIFICATION.md), décision W002. Les lots existants restent actifs ; aucun second plan. D10/D11 ajoutent qualification précoce, sources officielles, usage des skills et cohérence documentaire. OCR régional, révisions immuables, offsets en points de code, couverture du contexte final, pause coopérative et reprise manuelle sont maintenant des exigences d’implémentation. Recette : 16 PDF synthétiques minimum, 200 questions séparées 100 développement / 100 final, plus corpus métier autorisé. Les seuils ne sont ni diminués ni déclarés atteints.

Provisionnement observé à cette étape : uv 0.12.21 isolé, Python 3.12.14 local ; la résolution initiale comptait 126 paquets avant ajout du générateur de fixtures. Les résultats ultérieurs ci-dessous font foi pour l'état courant.

## Résultats partiels à 01:45 UTC — intégration en cours

A/E : premier `up` natif et second appel idempotent PASS, services Qdrant 1.19.1/Ollama 0.35.0/API en loopback, sans chargement LLM implicite. Readiness 503 cohérente sur base vide (collection absente). Preuves : reports/runtime-first-up.json, runtime-first-duplicate-up.json, doctor-first-running.json. Arrêt/reprise réels restent à qualifier.

QCPU : premier pilote froid FAIL `httpx.ReadTimeout` après 300 s sans premier token. Le log natif rapporte 2970 tokens d'entrée, 23,64 s de chargement, préfill 1024 tokens/118,23 s puis 1946/229,99 s. Essai chaud non exécuté. Le runner n'avait pas persisté ses échantillons avant exception ; ce défaut est corrigé pour les essais suivants. Preuves : reports/cpu-pilot-first-failure.json et cpu-pilot-first.service.log. Aucun seuil modifié, aucune performance extrapolée.

B : révision native antérieure 8 tests PASS, révision actuelle 24 tests unitaires PASS ; rerun natif/OCR courant requis. Le mixte a révélé langues non relayées, config TSV manquante puis pertes réelles de chiffres/unités. Les deux premières causes sont corrigées ; une correction de grille sur raster dérivé récupère les valeurs au diagnostic Tesseract, conversion complète encore en cours. Un avertissement d'incertitude n'est pas une validation d'exactitude. Preuves persistantes sous .runtime/qa/ingestion-synthetic ; l'ancien manifeste temporaire pytest supprimé automatiquement n'est pas reconstitué.

C : suite préstart sous Python 3.12 42/42 PASS ; histoire/scope 10/10 PASS après correction d'un risque de reprise des anciens messages lors d'un changement de scope. HTTP ciblé 8/8 PASS après correction du corps 304 et ajout de la couverture/publication des jobs. Compteurs LLM des chunks corrigés, 2/2 ciblés PASS ; redémarrage pour intégrer ces dernières écritures. Preuves distinctes dans reports/backend. Aucun retrieval qualité ou réponse réelle annoncé.

D/E : frontend actuel 12 tests PASS et typecheck PASS, nouveau build requis après ces changements ; build antérieur conservé comme preuve de sa révision. Fixtures : 32 PDF synthétiques, 200 questions réparties 100 développement/100 final, 15 tests structurels PASS, génération stable et gel final. Préflight indépendant : 150/180 unités de preuve présentes en texte natif, 30 unités attendent OCR ; annotations API encore à résoudre. Aucun final utilisé pour tuning.

E/D09 : commandes backup/verify/restore implémentées. Sauvegarde cohérente vide et restauration vers une autre racine PASS ; 7 tests backup PASS après deux échecs liés aux handles et fichiers WAL/SHM, conservés séparément. Provenance complète et comportement de snapshots peuplés/recherche/ancienne citation encore non exécutés. Preuves reports/backup-empty-first.json, backup-empty-rerun.json, restore-empty-first.json, runtime-backup-tests*.xml. D09 reste ouvert.

Corpus : ajout concurrent de manuels Z2M observé, 67 fichiers/634,118 Mio dans PDF. Les cinq originaux initiaux sont re-hashés identiques 5/5 ; aucun import/OCR en masse implicite. Preuve reports/corpus-delta-2026-09-30.json. Ressources 01:39 UTC : environ 6,13 Gio disponibles, 30,38 Gio libres sur D ; mesures continues lors des travaux lourds, un seul moteur lourd à la fois.

Prochaine action : terminer le rerun OCR ciblé, rebuild et redémarrer la révision intégrée, puis effectuer V réelle avec une fixture de développement et mesurer l'admission Qwen. V passe IN_PROGRESS au premier import réel ; F et D01–D11 restent non clos.

Mise à jour 01:46 UTC : le rerun mixte corrigé PASS en 106,30 s, tableau 4×3 et cellules/unités exactes (24 V, 45 °C, 2 A), natif préservé sans duplication, aucune région non résolue. Preuve .runtime/qa/ingestion-synthetic/mixed-corrected-20260930T014335Z ; pic RSS arbre 1063,62 Mio, réserve hôte minimum 5,0 Gio. Les scans et échantillons métier ne sont pas encore déclarés validés.

## Résultats partiels à01:07UTC — réalisation continue

A/E : Python3.12.14 +uv0.12.21 +127paquets résolus (126installés), lock Python/npm présents ; bootstrap -Offline PASS ; doctor distingue fichiers présents et services absents. Scripts rag.ps1/bootstrap.ps1 et runtime Windows présents, start/stop réels encore non validés. Job Object vrai enfant+descendant PASS après correction initiale. Governor3tests PASS, contrôles ruff ciblés PASS.

B :18tests unitaires +8natifs offline sous envfinal PASS ; pic arbre381,27Mio, sections/pages4/5/rotations/CropBox/reprise contrôlées. Premier mixteOCR FAIL (TESSDATA_PREFIX non relayé dans certains appels Docling), correction/rerun en cours. Aucun D02 complet.

C : suite initiale22cas PASS avec doubles explicitement isolés sous Pythonglobal3.13 ; smoke E5réelCPU/tokenizerQwen .venv3.12 PASS, preuves reports/backend. Contrôles finaux3.12 en cours.

D : typecheck PASS après4erreurs initiales conservées,7tests offsets/budgets PASS, export statique réel PASS. Aucun E2E réel encore déclaré.

E : Heron/TableFormer/languesOCR/E5/tokenizers/binaires natifs téléchargés et hashes vérifiés ; Qwen4B pull en cours sans inférence. Fixtures16+PDF/dataset200questions en préparation, annotations de blocs/révisions à résoudre sur extractions réelles. V etF restent NOT_STARTED ; D01–D11 non clos.

## Résultats partiels à02:30 UTC — reprise verticale

Les entrées01:07 et01:45 ci-dessus restent historiques. États courants : A/B/C/D/E/V IN_PROGRESS, F NOT_STARTED, aucun D01–D11 clos.

QCPU : pilote court réel279 tokens d'entrée, deux sorties64 tokens, PASS_PILOT_ONLY. Froid TTFT55,844s, chaud même préfixe0,813s ; le préfill chaud réutilise275/279tokens. Pic RSS somme3883,39Mio, hôte minimum2325,80Mio, CPU seul/contexte8192. Profil froid4352Mio, chaud additionnel512Mio, cache256Mio/deux checkpoints ; réserve1536 inchangée. Preuve reports/cpu-pilot-short-4threads.json. Aucun résultat3000/400tokens ni estimation de ces latences. Governor surveille la réserve et annule seulement la requête possédée ; six contrôles ciblés PASS, reports/governor-watch-final.xml.

B : dernier essai mixte/scans1PASS+2FAIL (valeurs/unités manquantes sur scan0, orientation erronée sur scan90) ; journal de faute native observé au second extract, pytest exit1. Les corrections orientation/OCR de cellules, limites raster8M et quarantaine sont implémentées,30 unités PASS, mais ne constituent pas un rerun réel du défaut. Fenêtres4+1 dans un même worker et échantillons métier encore à exécuter, sans moteur lourd concurrent.

C : suite intégrée59PASS, admission E5 conditionnelle5PASS, hook réserve4PASS. Retrait d'un document avant reprise du job : premier contrôle3FAIL/1PASS conservé, correction6PASS. Code actuel chargé dans API ; publication/collections réelles et évaluations100DEV/100final encore non exécutées.

D/V : build V2.1 PASS et15 unités PASS. Premier import navigateur créé, job8294f3ef-100a-475e-8378-983360f88b69 suspendu à5630Mio contre5632requis par ancienne estimation parser4096. Estimation parser2304Mio fondée sur mesure réelle1477,55RSS/1669,73private, réserve conservée. Version11debf6d-6e3c-4874-9ea4-395c1ad6661c et document e01b0666-ae93-40e5-9403-35decf00ae84 conservés ; reprise explicite, aucun reset/réimport. Premier E2E révèle viewer bloqué avant publication ; correction/build PASS, styles PDF.js6 encore en correction avant reprise. Preuve apps/web/test-results/2026-09-30-native-dev-first.

A/E : deux arrêts natifs réels exit0 des trois services. Premier redémarrage calibré FAIL WinError5 sur remplacement de runtime.json ; log conservé reports/runtime-calibrated-first-start-failure.log et rapport runtime-calibrated-up.json. Temporaires uniques et reprises bornées lecture/écriture NTFS corrigés ; premier test concurrent1PASS/1FAIL conservé, rerun réel Win32 2/2PASS, reports/runtime-atomic-windows-rerun.xml. Nouveau up PASS instancea0b20f3477944f73b22ad7328ebb4c31, reports/runtime-calibrated-up-rerun.json. Aucun processus tiers arrêté.

E/D09 : inventaire licences réellement installé126distributionsPython/71versionsnpm/26artefacts/18avis, reports/licenses-2026-09-30.json ; métadonnées, pas certification juridique ni preuve complète des runtimes prérequis. Snapshot peuplé/restauration/requête/ancienne citation toujours à faire.

Ressources02:29:24 UTC : RAM disponible6114,09Mio, D31070,55Mio, CPU3,8%. Prochaine action exécutable : achever styles PDF.js/build puis reprendre le jobDEV existant ; contrôler index réel, afficher sa version puis poser une question Qwen. OCR lourd attend ce créneau.

## Résultats partiels à 03:55 UTC — sources réelles et robustesse

A/B/C/D/E/V restent IN_PROGRESS ; F et la recette complète restent ouverts. Les mentions précédentes constituent l'historique.

V : même job repris explicitement, publié à02:35:57 UTC : document e01b0666-ae93-40e5-9403-35decf00ae84, version11debf6d-6e3c-4874-9ea4-395c1ad6661c, génération57ffa153-0f74-429b-82a8-72579b163e22. Deux pages structurées,11 blocs/11 chunks SQLite=11 points Qdrant, original et hashes source vérifiés. Preuve [publication](reports/backend/2026-09-30-first-publication-readonly.json). La fixture contient une table ; elle ne qualifie pas la voie native simple.

D :17 unités/typecheck/build PASS, export278 fichiers ; E2E source réel PASS11,4s après corrections TextLayer/PDF.js, rejet de promesse de rendu et metadata de recherche. Échec du locator de bibliothèque puis échec RenderingCancelledException conservés séparément, sans les convertir en durée d'indexation. [Rapport UI](../apps/web/reports/QUALIFICATION_UI_NATIVE_2026-09-30.md). Recherche sans LLM, sélection réelle, source physique, rotation90/zoom125 et warnings objets vérifiés ; aucune réponse modèle encore qualifiée. Bindings DEV15/100 résolus sur cette seule famille ;85 questions restent à résoudre, final non utilisé pour réglage.

V/QCPU : question2f36429b-2ac6-4c5f-83c3-d72271f1adf9,03:03:19–03:03:23 UTC, FAIL admission froide5095Mio<5888 requis. `model_called=false`, aucune génération ni delta ;384 est le budget de sortie. La libération E5 récupère122,38Mio RSS et99,46Mio disponibles, insuffisant. [Preuve navigateur](../apps/web/reports/e2e-2026-09-30-qwen-question-first-evidence.json). Éviction conditionnelle supplémentaire des caches Rust E5/Qwen implémentée,14 contrôles PASS ; effet réel et coût/parité de rechargement encore à mesurer. Réserve1536 et seuils de performance conservés. Digest Qwen maintenant vérifié avant envoi du contexte,19 tests gateway PASS ; doubles HTTP explicitement identifiés.

E/D09 : sauvegarde peuplée20260930T031052Z-920d8a2a vérifiée,21 fichiers, SQLite intègre, snapshot248032768octets checksum4a6ee822a7df94997110ef189199a1f719559cc1d88c1c4d7951cb866a2f647e. Restauration initiale longue FAIL500/os3 ; variante chemins étendus FAIL500/os145 ; stockage court intermédiaire encore FAIL au temporaire, tous conservés. Restores ASCII court et Unicode court PASS ; solution avec stockage Qdrant plus court explicite et destination Unicode longue PASS : [preuve](reports/restore-first-published-long-root-short-store-rerun.json). Dix copies de données hashées avant rebasing, comptes identiques et11 points récupérés, Qdrant exit0. Démarrage applicatif/requête/ancienne citation sur restauration encore NOT_RUN. Verrou distinct du stockage Qdrant ajouté : premier contrôle2FAIL dû aux chemins de fixtures trop longs, reprise2PASS avec deux vrais superviseurs isolés, [preuve](reports/runtime-shared-storage-rerun.xml).

B : scan90 avec drain lifecycle FAIL sur journal natif ; parser/rendu sans Torch3PASS, avec Torch contre-exemple FAIL puis stress16cycles : deux AV dans docling_parse/pdf_parsers.cp312-win_amd64.pyd+0x7e4a57, lecture0xffffffffffffffff. Les processus continuent : le titre faulthandler first-chance ne prouve pas terminaison et les stacks d'autres threads ne localisent pas le fautif. Backend officiel pypdfium2 : journal natif vide, mais fidélité/orientation OCR encore FAIL (ready_partial/table3×4). Preuves séparées sous .runtime/qa/ingestion-synthetic. Correction géométrique ciblée en cours ; scans5pages4+1 et métier non validés.

Points vérifiés : arrêt/redémarrage natifs sans perte, dernière instancec87c102408de4d10aab9f8040b4e0be3 ; aucun service étranger arrêté. Qdrant1.19 utilise des tiers mémoire mmap ;11 points ne construisent pas encore HNSW. Licences/prérequis126 Python/71 npm/26 artefacts/18 notices inventoriés, provenance installateur Tesseract toujours limitée. Candidat IBM officiellement identifié (commit835ad14087e140460703cf0fae09f97d469d65c2, CLS/L2/384), skill lu/validé et lock séparé ; aucun téléchargement/inférence/A/B encore annoncé.

| Action | Classe / couche | Dépendance et livrable | Validation exacte | État / preuve |
|---|---|---|---|---|
| W-P01 | Bug / stockage Windows | Snapshot peuplé ; chemins courts explicites sans réglage global | Hashes/comptes puis API/recherche/ancienne source sur destination longue | Implémenté ; stockage PASS, parcours restant ; rapport restore ci-dessus |
| W-M01 | Amélioration / mémoire | Contexte déjà compté, modèle froid ; éviction mesurée et verrouillée | Admission et réponse Qwen réelles avec réserve ; rechargement/parité | Implémenté/tests PASS ; mesure applicative restante |
| W-PDF01 | Bug ou interaction native inconnue / ingestion | Backend officiel distinct ; même PDF et assertions | Scan90 exact, aucune faute/unresolved, puis scan0/mixte/4+1 | FAIL fidélité ; essai PDFium034739 conservé |
| W-REV01 | Incohérence / API et lecteur | Route blocks/outline révision explicite, sélection fixée | Ancienne révision après reindex, sans fallback courant ni fuite de scope | Correctifs intégrés au redémarrage04:36 ;10 tests API et27 unités web PASS ; parcours réel après reindex restant |
| W-CACHE01 | Amélioration / observabilité | Compteurs d'inférence/cache/worker et cas blanc | Réimport/reindex réellement sans calcul redondant ; blanc visible |14 tests PASS, nouveau restart requis ; E2E restant |

Prochaine action : achever le correctif OCR discriminant et la révision du lecteur, intégrer la révision stabilisée, mesurer l'éviction mémoire puis reprendre la première question réelle. Les contrôles de restauration applicative, évaluation DEV/comparatif/final,25k/30 questions/30min et blocage réseau OS restent à exécuter ; aucune case globale de Done anticipée.

## Résultats partiels à04:36 UTC — révision intégrée

A/V : arrêt de l'instancec87c102408de4d10aab9f8040b4e0be3 et redémarrage natifcc0b7e974ab14645af67f0f7c27bc8dc PASS, trois services arrêtés exit0, santé/readiness200, aucun modèle chargé implicitement. Le démarrage conserve désormais un manifeste des fichiers réellement observés, empreinte4b23a6a7af8db2ad3f24c347a02041d4eb1105ecde055095f5a1f2651867877d, sans inventer de révision Git. Doctor confirme le profil appliqué et le stockage Qdrant Windows valide. Preuves : reports/runtime-integrated-down-20260930T0436.json, runtime-integrated-up-20260930T0436.json, doctor-integrated-20260930T0437.json. Mémoire disponible au doctor5672,35Mio ; D27979,64Mio. La nouvelle question réelle attend son résultat ; aucune réponse anticipée.

C/D : routes de révision historique et sélection épinglée corrigées après trois échecs API conservés ;10 tests API PASS. Le bouton Retour perdait encore la source/révision archivée : deux unités en échec conservées, correction puis27 unités web/typecheck PASS. Build final PASS98,94s,278 fichiers/6673451octets, workspace/index.html SHA25698d86335841d59c28c4be723ac0f70fe872206180c4f32031301f101705e0253. Minimum RAM disponible pendant ce build5228,7Mio. Les dix nouveaux parcours lifecycle restent NOT_RUN ; un build n'établit pas leur réussite. Preuves sous apps/web/reports, tag2026-09-30-pinned-revision-return.

B : essai cinq pages PDFium terminé avec fenêtres4+1, journal de faute native vide et lifecycle drainé, mais FAIL sur fidélité des cellules/unités ; ceci ne ferme pas D02. Lecture TSV corrigée pour conserver les textes numériques et chaînes littérales ;42 contrôles purs PASS. Géométrie bitmap et bordures de cellules préparées sous options expérimentales désactivées par défaut ; aucun nouvel essai OCR ni adoption nominale à cette étape.

D10 : dix artefacts Granite provisionnés et hashes réels vérifiés, sans inférence. Runner séparé préparé sur export SQLite immuable,17 tests PASS après correction d'une fixture et d'une étiquette erronée, échecs conservés. Comparaison DEV100 et smoke de graphe restent NOT_RUN ;15 bindings DEV résolus ne constituent pas une évaluation complète. Preuves reports/backend/2026-09-30-comparison-runner-export-corrected.* et granite-identity-static.json.

Prochaine action exécutable : mesurer la question Qwen sur cette révision, puis qualifier API/source sur la restauration Unicode longue ; réserver ensuite le créneau lourd à l'OCR discriminant. D08 prépare un aperçu de règles Windows, sans modification du pare-feu ; contrôle réseau OS toujours non exécuté.

## Reprise du 30/09 à 08:43 UTC — état consolidé et lots R

Les sections précédentes restent l'historique. Entre 04:36 et 04:49, sans mise à jour du suivi : seconde question Qwen refusée avant modèle (5222 < 5888 Mio), arrêt de l'instance principale `cc0b7e97…` (04:44), démarrage de l'instance restaurée (API 8795), E2E ancienne citation en échec. État des lieux de 08:46 par six cartographies en lecture seule relues par l'intégrateur (rapports de sous-agents non versionnés ; constats repris ci-dessous avec leurs preuves).

**Statut par critère à 09:30 UTC** (seules les puces avec preuve sont PASS) : D04.1, D06.1, D07.6, D09.1, D09.2 PASS ; D09.3 citation PASS après restauration, question en cours ; D02.3, D02.6, D02.10, D04.4 (identifiants parasites), D03.2 (déplacement absent), D10.4, D11.8 FAIL ; D08.1 BLOCKED (pas de droits administrateur : blocage réseau OS impossible sans décision utilisateur) ; tous les autres critères PARTIAL ou NOT_RUN. Aucune recette globale close.

**Contrôles précoces (D10.1)** : Q-CPU PARTIAL — pilotes texte 900 tokens PASS_PILOT_ONLY, préfill ≈ 8,6 tokens/s sans réutilisation de préfixe pour un contenu nouveau, TTFT ≈ 106 s à 919 tokens ; la cible D07 (45 s à ≈ 3000 tokens) est très probablement hors d'atteinte sur ce CPU (projection ≈ 350 s, à mesurer). Q-PDF FAIL (W-PDF01). Q-SEARCH PARTIAL (tests unitaires, une requête réelle).

| ID | Lot / couche | Dépendances | Livrable | Validation | Statut / preuve |
|---|---|---|---|---|---|
| R0 | Git / publication | — | Dépôt, exclusions, remote privé, identité unique | Push sans corpus/runtime/secret ; auteur MOHAMED SEDKI sans trailer | VERIFIED — `2d735f2`, `e877c6a` ; W005 |
| R1 | Mémoire / génération (W-M01) | R0 | Modèle texte seul, estimations mesurées | Admission possible sous réserve 1536 ; pilotes conservés | VERIFIED pilotes — W006, W007 ; reports/cpu-pilot-text-900-* |
| R2 | V — première réponse réelle | R1 | Question → sources → réponse Qwen → citation cliquable | SSE brut, model_called, IDs de citation dans le registre, clic UI | IN_PROGRESS — 09:27 admise, `model_called=true`, réponse partielle correcte « 3,1 bar [S001] » puis annulée par le gouverneur (réserve 1500 < 1536 sous charge) ; à rejouer hors charge concurrente ([preuve](reports/backend/2026-09-30-restored-question-20260930T0927.json)) |
| R3 | D09.3 après restauration | R1 | Ancienne citation + question sur la restauration | E2E lifecycle PASS + réponse réelle | Citation VERIFIED ([preuve](../apps/web/reports/e2e-2026-09-30-restored-source-rerun-0910-evidence.json)) ; question IN_PROGRESS |
| R4 | Code (7 zones : retrieval, API, runtime, ingestion, outils qualification, outillage docs, frontend) | R0 | Corrections des défauts prouvés, tests, revue adversariale | Tests unitaires/in-process PASS, junit sous reports/backend/…-lotR4-*, revue sans constat bloquant | VERIFIED (niveau unitaire et in-process) — commits c3f9a72, 61e5d78, 4c87775, bc1494f, 0fabf03, 72a10e5, b4c940b ; 7 revues indépendantes, 4 constats majeurs corrigés avec tests de reproduction ; suite complète 355 tests ([junit](reports/backend/2026-09-30-lotR4-full-unit.xml)). Parcours réels, build et E2E relèvent de R2/R3/R5/R6. |
| R5 | Build UI + E2E de non-régression | R4 frontend | Export rebuild, specs a11y/deeplink/géométrie/markup/canvas | Build surveillé PASS, E2E réels PASS sur cible isolée | NOT_STARTED |
| R6 | Ingestion OCR (W-PDF01) | R4 ingestion (E1) | Voie scan fiable ou limite déclarée | scan90/scan0/mixte/5 pages exacts ou ready_partial honnête | VERIFIED sur fixtures synthétiques (W009) : 4/4 OCR sur le profil nominal, voie native 8/8 ; corpus métier et réindex des fixtures DEV restent à faire (R7) |
| R7 | Évaluation DEV (retrieval, contexte, génération) | R4, R6 | Import DA-P02..07, bindings fusionnés, rapports DEV | 100/100 résolues ; métriques avec dénominateurs | NOT_STARTED |
| R8 | D07 performance | R2, R7 | Stress 25k nommé, 30 questions, scénario 30 min | p95 mesurés, FAIL conservés avec phase dominante | NOT_STARTED |
| R9 | D08 sécurité / hors ligne | R4 | Host/Origin sur serveur réel, clé d'API Qdrant, fixture hostile, observation sockets | Rapports ; blocage OS BLOCKED sauf décision utilisateur | PARTIAL — D08.3 VERIFIED sur l'instance principale : clé d'API Qdrant par démarrage (W010), [gardes HTTP réels 15/15](reports/http-guards-live-20260930T1636.json) (API 400/403, Ollama 403, Qdrant 401 sans clé) ; sockets loopback, Ollama sans socket externe. Restent : fixture hostile en E2E réel, D08.1 BLOCKED (décision utilisateur) |
| R10 | D01 provisionnement neuf | R4 runtime | Racine neuve provisionnée sans édition, redémarrage hors ligne | Rapport provision/doctor | NOT_STARTED |
| R11 | D09.4/D09.5 migration, licences | R4 API | Migration 003 + retour arrière, inventaire livré | Test migration sur sauvegarde, inventaire rejoué | NOT_STARTED |
| R12 | D10/D11 documentation | R4 docs, résultats | Documents canoniques synchronisés, brief, verify_pack PASS, registre skills | verify_pack --report PASS | IN_PROGRESS (outillage dans R4) |
| R13 | Recette finale | R2–R12 | Final exécuté une fois, rapport D01–D11 | Rapport final honnête | NOT_STARTED |
| R14 | Espace documentaire (demande utilisateur reçue vers 09:34 UTC) | R4 docs-tooling, R12 | `docs/` : index documentaire, documentation stabilisée du système livré (architecture technique détaillée avec schémas SVG, spécifications, interfaces HTTP/SSE, dossiers d'exploitation et de déploiement, procédures, référentiels) ; `RAG_Local_Agents/` conservé comme dossier de chantier vivant (plan, journal, décisions, sources, preuves) et référentiel d'exigences V2.1 ; README racine point d'entrée | Chaque document : rôle, statut, date/commit en tête ; aucune information dupliquée entre documents ; liens vérifiés par l'outil documentaire ; procédures rejouées sur le poste | NOT_STARTED — décision d'arborescence W008 à consigner à l'exécution |
| R15 | Textes de l'interface et relecture éditoriale | R4 frontend, R5 | Inventaire de tous les textes UI, réécriture des libellés génériques/bruts, vocabulaire unifié ; réécriture des passages génériques de la documentation existante | Revue de l'inventaire, tests unitaires/E2E mis à jour, captures relues | NOT_STARTED |
| R16 | Interface alignée sur la référence de forme decodair (demande utilisateur reçue vers 09:36 UTC) | Analyse decodair (lecture seule), R4 frontend, R15 | Principes retenus/adaptés/écartés documentés (reports/ui-reference-decodair-2026-09-30.md) ; shell (topbar, panneaux repliables/masquables, pied de page si utile, en-têtes), charte (tokens de couleur, typographie, icônes, densité, espacements), composants (cartes, listes, formulaires, filtres, actions, retours, états) et responsive harmonisés ; README racine au format de référence | Aucune régression : tests unitaires, typecheck, build, E2E existants rejoués ; captures 1366×768 et 1920×1080 examinées ; contraste et clavier contrôlés | IN_PROGRESS — analyse decodair lancée à 09:37 |
| R17 | Sécurité applicative alignée sur decodair (demande utilisateur reçue vers 16:45 UTC) | R9, analyse decodair (lecture seule) | Mécanismes repris/adaptés/écartés avec preuves decodair, OWASP et sources officielles ; réglages par environnement (développement sans `Secure` ni TLS, production durcie et refus au démarrage si incohérent) | Décision consignée, tests de refus (Host/Origin, CSRF, session expirée ou révoquée), contrôle réel | IN_PROGRESS — règle ajoutée aux chartes ; cartographie decodair reçue 17:00 |
| R18 | Contrôles au vert (demande utilisateur reçue vers 17:00 UTC : lint, typage, build et autres contrôles absolument verts) | — | `ruff check .`, `mypy services`, `tsc`, lint web, tests unitaires Python et web, build surveillé, E2E | Chaque contrôle PASS sur le même commit, sorties conservées | IN_PROGRESS — ruff PASS sur tout le dépôt ; mypy 141 erreurs dans 21 fichiers (base 17:05) |
| R19 | Corpus réel `PDF/` pour l'usage, les tests et l'évaluation (demande utilisateur reçue vers 16:55 et 17:00 UTC) | R6, R9 | Import des 65 PDF lisibles avec leur arborescence, extraction complète ou limites déclarées ; E2E et évaluation sur ce corpus sans qu'aucun contenu ne quitte le poste | Documents `ready`/`ready_partial` avec couverture ; rapports agrégés versionnés, jeux dérivés du corpus hors Git | IN_PROGRESS — import 17:01–17:10 : 65 acceptés, 1 refusé (signature PDF absente), 1 `.docx` non pris en charge ; extraction lancée 17:11 |
| R20 | Recette visuelle et UX de l'interface (demande utilisateur reçue vers 17:05 UTC) | R15, R16, R19 | Captures 1366×768 et 1920×1080 sur le corpus réel, écarts relevés contre WCAG 2.2, WAI-ARIA APG, Fluent 2, GOV.UK Design System ; corrections | Captures relues avant/après, E2E et tests unitaires web PASS | NOT_STARTED — après intégration du workflow interface |

**Règles ajoutées le 30/09 (commits f8fbb1c 09:35 et d4924d9 09:37 UTC) :** référence de forme `D:\enhacements\decodair` (principes UI et format du README, sans métier ni branding) ; section « Documentation et textes de l'interface » dans `CLAUDE.md`/`AGENTS.md` racine, renvoi dans `RAG_Local_Agents/AGENTS.md`, section « Textes de l'interface » du skill `pdf-workspace-web`.

**Points à trancher (décisions utilisateur, non déductibles) :** (1) D08.1 — accepter une coupure réseau physique pendant la recette (mode avion/câble) ou obtenir une règle pare-feu de l'administrateur ; sinon D08.1 reste BLOCKED. (2) Corpus métier : jeu de questions métier annotées sur les PDF autorisés (expert métier) — sinon qualification métier BLOCKED. (3) D07 — si les seuils de latence échouent comme projeté, ils restent FAIL (aucune baisse de seuil sans décision explicite).

**Ressources 09:27 UTC :** 5690 Mio disponibles, D: ≈ 24,8 Gio libres ; un seul moteur lourd à la fois ; les agents du lot R4 n'exécutent que des tests légers après contrôle mémoire.

Prochaine action : lire le résultat de la question restaurée, puis intégrer R4 (revue, tests, commit), rebuild UI et E2E question/citation sur l'instance principale.

## Point à 13:55 UTC — lot R4 intégré

R4 VERIFIED au niveau unitaire et in-process (voir le tableau). Aucun parcours réel n'est déduit de ces tests. Conséquences à traiter : réindexation nécessaire pour les nouvelles règles d'identifiants (table `identifiers`), empreinte d'extraction modifiée par les changements d'ingestion (le prochain réindex relancera le worker), nouvelle fixture hostile et document de 14 pages disponibles pour R5/R9.

Prochaine action exécutable : arrêter l'instance restaurée (ancien code), build surveillé de l'interface (R5), relancer l'instance restaurée sur le nouveau code pour la question D09.3 (R3), puis instance principale, réindex de DA-P01 et E2E réels (R2/R5). Un seul traitement lourd à la fois.

## Point à 14:10 UTC — génération bloquée par la mémoire hôte

Deux questions réelles sur l'instance restaurée (nouveau code, modèle texte) : 13:58 refus immédiat à 4723 < 4992 Mio ; 14:05 avec W008, état `waiting_for_resources` émis (4932 Mio), refus après 120 s à 4709 Mio ([preuve](reports/backend/2026-09-30-restored-question-w008-20260930T1405.json)). Nos services occupent ≈ 115 Mio après libération des caches ; la pression vient de processus étrangers (navigateur ≈ 1,5 Gio, antivirus, sessions Claude). Admettre la génération sans cette marge ferait tomber l'hôte sous la réserve de 1536 Mio (baisse mesurée 3327 Mio) : aucun seuil n'est abaissé.

**BLOCKED — décision utilisateur :** libérer ≈ 0,5 Gio pendant les créneaux de génération (fermer le navigateur Edge hors de la recette ou d'autres applications), ou laisser D05/D07 génération et la question D09.3 bloquées sur ce poste. Travaux indépendants poursuivis : E2E sans génération (R5), OCR réel (R6), interface decodair (R16), documentation (R14).

## Point à 16:40 UTC — D08.3 corrigé, arrêt console rétabli

- W009 publié (`4c172dd`). Workflow interface (R15/R16) et documentation (R14) toujours en cours, fichiers disjoints de ce lot.
- D08.3 : clé d'API Qdrant tirée à chaque démarrage (W010), transmise au seul enfant Qdrant, lue par l'API et les outils de l'instance ; restauration avec sa propre clé. Contrôle réel 15/15, test d'intégration sur le binaire verrouillé, sauvegarde puis restauration (11 points).
- Défaut trouvé pendant ces essais : un lanceur qui ignore CTRL+C (terminal d'outil) transmet cet attribut aux enfants (WIN09) ; Qdrant et Ollama étaient alors terminés par le Job après 30 s au lieu d'un arrêt console. [Avant](reports/runtime-down-before-ctrlc-fix-20260930T1636.json) : `forced_job_close_after_stop_timeout` ; [après correction](reports/runtime-down-after-ctrlc-fix-20260930T1637.json) : `console_sigint`, code 0. Test d'intégration qui échoue sans la correction.
- Restauration : un premier essai a échoué sur une erreur d'E/S Windows transitoire dans Qdrant (os error 145, répertoire temporaire encore tenu) ; le second a réussi. Reprise bornée (3 essais, collection absente seulement) ajoutée et testée ; échec et reprise manuelle conservés ([rapports](reports/runtime-restore-transient-20260930/)) ; la racine `.runtime/rt-qkey-20260930T162754Z` et le stockage `.runtime/q/feeaad73` de l'essai échoué restent en place.
- Dette relevée : `ruff check services/` signale 18 constats préexistants dans `services/api` (imports non triés, alias `datetime.UTC`, `B008` sur `File`) ; aucun nouveau constat dans les fichiers modifiés. À traiter dans un lot dédié.

Prochaine action exécutable : intégrer les livrables du workflow (tests unitaires web, typecheck, build surveillé, E2E en lecture seule, captures), puis R7 (import DA-P02..07 et réindex DA-P01) sur l'instance principale. Génération toujours BLOCKED (décision utilisateur du point 14:10).

## Point à 17:15 UTC — nouvelles demandes intégrées (R17–R20)

- Demandes reçues entre 16:38 et 17:05 UTC : règles de documentation renouvelées (déjà en place, précisées) ; sécurité applicative sur le modèle de decodair (R17) ; lancement de la plateforme (fait à 16:43, instance `0c0cd4d9…`) ; utilisation du corpus réel `PDF/` pour l'usage, les tests et l'évaluation (R19) ; contrôles absolument verts (R18) ; recette UX avec captures (R20).
- Contrainte retenue pour R19 : le corpus est privé ; aucun texte de document n'est affiché dans les sorties d'outils ni envoyé hors du poste. Les jeux d'évaluation dérivés du corpus restent sous `.runtime/` (hors Git) ; seuls les rapports agrégés sont versionnés. Les questions sans annotation d'un expert métier seront déclarées comme telles.
- Contrainte d'ordonnancement : l'empreinte d'extraction inclut les sources `services/ingestion/*.py` ; toute modification de ces fichiers pendant l'extraction du corpus change l'empreinte des documents suivants. Les corrections de typage de l'ingestion sont faites au début de l'extraction ; les documents déjà extraits seront réindexés.
- R18 : `ruff check .` PASS après correction des 79 constats (fixtures réexportées, instructions séparées, `Annotated` pour l'import, variable de boucle renommée) ; reproductibilité des fixtures PASS (37 fichiers identiques) ; 340 tests unitaires PASS (échec intermédiaire du registre des skills dû au hash périmé du skill modifié, corrigé puis rejoué 19/19).

Prochaine action exécutable : typage mypy au vert (services puis outils), backend de R17, intégration du workflow interface puis R20 ; extraction du corpus surveillée en continu.

