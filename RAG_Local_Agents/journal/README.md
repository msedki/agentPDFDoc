# Journal des travaux

**Rôle :** index chronologique des exécutions et points de reprise · **Propriétaire :** intégration du chantier · **Statut :** Vivant · **Référence :** base publiée `19f483f` et entrées datées · **Mis à jour :** 2026-10-03 20:40 (UTC) · **Source de vérité :** chaque journal pour les faits ; [PLAN.md](../PLAN.md) pour les actions

Dates et heures en UTC. Le suivi canonique des actions demeure dans [PLAN.md](../PLAN.md).

Ajout du 3 octobre, relevé à 10:05 UTC : [R23, démarrage optionnel Qwen 2B Q4_K_M](../PLAN.md#r23--démarrage-optionnel-avec-qwen-35-2b-q4_k_m),
inscrit au plan et non exécuté ; [trace de la demande et des lectures](2026-10-03.md#ajout-du-démarrage-qwen-2b-au-plan--relevé-1005-utc).

Reprise à 15:19 UTC : [refus QA après fermeture et compositions distinctes](2026-10-03.md#contrôles-qa-après-fermeture-et-compositions-relevé-1519-utc).
Correctif de la sonde modale revu sur 46 tests purs ; assemblage corrigé de 68 tests
et enveloppe diagnostique Q05 en revue, sans nouvelle recette native à ce relevé.

Relecture à 16:02 UTC : [documentation et nouvelle tentative QA](2026-10-03.md#relecture-documentaire-et-reprise-qa-relevé-1602-utc).
58 tests documentaires PASS ; cinq cas navigateur stricts PASS mais sonde modale FAILED.
Correction ciblée de l'aide sur la publication en cours ; revues et limites conservées.

Clôture ciblée à 18:09 UTC : [E03 et recette V5](2026-10-03.md#e03--validation-ciblée-et-clôture-v5-relevé-1809-utc).
Notice corrigée, 281 unités et qualité/build conformes ; trois contextes UI
avec API doublées validés indépendamment, sans qualification du dessin PDF.
E04/E05 restent non réalisés ; clarification SPEC et contrôles documentaires
validés dans leur portée, relecture finale indépendante favorable.

Reprise à 18:48 UTC : [publication E01–E03 et corrections E04/E05](2026-10-03.md#publication-e01e03-et-reprise-e04e05--relevé-1848-utc).
Lot précédent publié dans `f8cd964`. E05 : 16 tests ciblés et 104 de
régression PASS, Ruff et mypy Linux/win32 conformes ; revue indépendante
bornée. E04 : aide corrigée, vingt tests frontend et contrôles ciblés conformes ;
gel/build/rendu neufs encore requis. Windows natif et DoD globale restent ouverts.

Complément à 19:41 UTC dans la même entrée : copie E04/E05 neuve qualifiée
sur 288 unités, typage et lint de 118 fichiers ; build isolé sortie 0,
export et conservation relus indépendamment, treize PID nommés actuellement
absents selon C et B. Programme navigateur remis et relu par ROOT,
relecture A en cours ; rendu encore non exécuté, aucune clôture E04/E05 anticipée.

Résultat du rendu à 19:45 UTC et revue à 19:56 :
[huit contextes UI sur l'export E04/E05](2026-10-03.md#e04e05--rendu-isolé-du-nouvel-export-relevé-du-3-octobre-à-1949-utc),
huit captures vues par ROOT/C/A, aides complètes aux deux tailles ; quinze PID
nommés actuellement absents selon C et B, conservation conforme. Avis techniques
indépendants favorables dans cette portée, contrôle documentaire final et
publication en cours. Toutes les API/session sont doublées ; ce n'est pas
une recette RAG native, ni la clôture de D06 ou du chantier.

Finale à 20:06 UTC : contrôles documentaires 7/7 et dossier 11/11 conformes,
brief synchronisé, cinq SVG conformes ; accord indépendant B pour publication
sélective E04/E05. La reprise F04 prépare une qualification des 31 sur le
nouveau gel et l'export réellement construit, sans rebuild ni recette anticipée.

Publication à 20:09 UTC et [reprise F04 à 20:21](2026-10-03.md#publication-e04e05-et-reprise-f04--relevé-2021-utc) :
E04/E05 sur `origin/main` dans `19f483f`, 23 chemins antérieurs préservés.
Copie QA neuve et variante 31 en préparation ; oracle de la carte d'erreur
courante à renforcer avant gel, sans nouvelle recette native à ce relevé.

Complément à 20:40 UTC : oracle F04 corrigé, 13 témoins ciblés puis
301 unités web ROOT PASS sans skip ; lint/typecheck et relecture indépendante
conformes, sans code produit ou build modifié. Delta explicite de deux tests
prévu dans le gel de 249 sources ; copie et parcours natifs encore non exécutés.

| Date | Travail effectué |
|---|---|
| [30 septembre 2026](2026-09-30.md) | Inspection (commencée le 29), réalisation des lots R0 à R22 : runtime Windows, ingestion et OCR, session locale, interface, corpus réel, évaluation W013 et W014, distribution |
| [1er octobre 2026](2026-10-01.md) | Poste Windows (00:11–12:18) : disponibilité sur base neuve, réextraction et mesures B et C (W015), EV-3 interrompu faute de mémoire, distribution DIST-03 à DIST-08, premier kit fabriqué dont l'installation d'essai s'est arrêtée au contrôle d'intégrité, R2 vérifié, D09.3 et D09.4, qualification sur instances isolées (D01 à D04, D06, D08), W016, D10.3 et D10.4, migration Qdrant W017 ; poste Linux aarch64 (depuis 13:20) : inspection en lecture seule, W018, environnement Python et artefacts Linux, corrections de l'inspection (lots J), évaluation sur le corpus réel (J10), rondes 4 et 5, étude et réalisation de l'accélération GPU (W024, W025, J11) |
| [2 octobre 2026](2026-10-02.md) | PowerShell 7.4.15 en outil de validation de syntaxe ; corrections de la revue J11 et commit `4d8ba68` ; essai GPU réel J11.8 ; génération et jugement J10 ; documentation J11.9 (`c32b759`) ; D01 Linux sur clone neuf ; qualification Linux J8 (lots L0 à L10), corrections (`419b526`), rejeux R1 à R7, finitions (`36824e2`) ; artefacts lourds et fichiers temporaires déplacés sur la carte microSD ; essai de l'atelier par l'utilisateur sous Firefox 136 et décision W027 (version moderne de PDF.js) ; audit D10/D11 et intégration documentaire du lot J9 ; W029 : ingestion, API réelle et diagnostic du scan à 90° ; R14-1 : propriétaires, spécifications et déploiement ; R15-1 : disponibilité des services, inventaire et recette du rendu |
| [3 octobre 2026](2026-10-03.md) | Pilote D03 relu ; correctifs frontend avec 277 unités, typage, lint/build PASS. QA0732 : 31 stricts ; RB1032 : 5 stricts, modale dédiée FAILED puis V2 préparée. F04 : 11 stricts/vraie génération ; réserve de carte corrompue, oracle préparé ; revue du pilote B39 détecte un refus tardif ignoré, delta ROOT45 tests purs au vert et relecture préparatoire. Q05/run1315 FAILED malgré trois ancres visibles à 300 % dans deux captures ROOT/C ; arrêt20tuples/conservation conformes bornés, diagnostic des phases requis. R23 Qwen2B Q4_K_M NOT_STARTED. Rouges et incident0510 conservés ; D06/Windows/D07 et chantier ouverts |
