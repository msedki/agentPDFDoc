# I5 — transfert réservé : revue des sources et qualification bloquée

**État au 9 novembre 2026, décision root du 04:40:02 UTC :** les 12 positions
de requête de référence sont **NOT_RUN** ; les 12 positions candidates sont
**BLOCKED**. Aucune requête réservée n'a de tentative ou de mesure terminale
observée. Aucun score documentaire n'est calculable. La qualification de
production et la recette HTTP/SSE finale ne sont pas acquises.

Cette disposition conserve le candidat gelé et toutes les preuves de
l'exécution interrompue. Deux workers d'extraction ont leur propre arrêt
vérifié ; la continuité de l'ordonnanceur a été perdue pendant le troisième
document, sans reçu terminal de ce worker ni du lot. La cause reste inconnue
et l'arrêt de l'ancien groupe natif n'est pas établi. Aucun nouveau moteur,
aucune reprise automatique et aucune recette HTTP ne sont autorisés dans cet
état.

Le présent rapport porte sur le **nouveau transfert réservé I5**. Les campagnes
de développement 5 à 8, les contrôles logiciels et leurs échecs conservent leurs
rapports séparés : [revue de développement](trust-4b-development-review-2026-11-09.md),
[Office](trust-4b-api-office-review-2026-11-09.md) et
[bilan de l'itération](trust-4b-results-2026-11-08.md). Leurs résultats ne sont
pas additionnés aux positions réservées sans réponse.

## 1. Protocole, gel et portée prévue

Le [protocole préalable](trust-4b-protocol-2026-11-08.md) exigeait, pour chaque
bras, huit positives originales complètes, deux limites pertinentes et deux
positives dérivées strictes. Il impose le soutien de tous les segments publics,
la conservation des conditions et des rôles, des citations justifiantes et
l'absence de réserve d'information manquante injustifiée. Une abstention sûre
sur une positive ne satisfait pas l'utilité. Une simple égalité au texte
extrait ne prouve pas la relation documentaire.

Le corpus a été gelé le **8 novembre à 20:05:19 UTC**. Le candidat final a été
gelé le **9 novembre à 04:05:09 UTC**, avant l'ouverture des sources et oracles
réservés aux relecteurs. Le plan lié a été scellé à **04:05:24 UTC**. La
référence est le commit `41857e17a438fe43123e4ef8274d9d2d446bfbc2` ; le candidat
est la copie isolée `agentPDFDoc-i5-diagnostic-snapshot-8`.

Le plan prévoyait deux extractions candidates complètes — trois originaux puis
deux dérivés — avant les blocs de questions appariés référence/candidat. Chaque
bloc devait réindexer le corpus complet et redémarrer ses services. Ce plan et
ses plafonds n'ont pas été modifiés après l'ouverture. Les relectures de
l'incident ont confirmé l'identité des ensembles complets de **172 fichiers
produit dans ROOT, 172 dans la copie candidate et 549 fichiers du gel logiciel**.
Ces identités attestent les octets examinés ; elles ne remplacent aucune
réponse native ni preuve d'arrêt.

## 2. Sources originales et deux dérivés

Les manifestes publics ci-dessous sont des copies octet pour octet des
manifestes gelés : [sources](trust-i5-corpus/sources.json),
[questions et oracles](trust-i5-corpus/questions-oracles.json),
[transformations](trust-i5-corpus/scan-transformations.json).

| Document | Source et révision gelées | Pages originales | Questions originales |
|---|---|---:|---|
| D01 | STMicroelectronics, TS881, DocID023340 Rev 3, août 2024 | 22 | T01–T03 |
| D02 | Microchip, MCP970X, DS20001942L, 2024 | 26 | T04–T06 et T09 |
| D03 | Texas Instruments, LM35, SNIS159H, révision décembre 2017 ; addendum d'emballage observé au 9 avril 2026 | 38 | T07–T08 et T10 |

Il s'agit de trois fabricants et de **86 pages originales dans un seul domaine,
les fiches techniques électroniques**. Cette sélection ne constitue pas une
preuve de généralisation à d'autres domaines documentaires.

`SCAN1_T05` reprend la page physique 3 de D02 dans un PDF d'une page, image
seule, sans texte natif. `MIXED1_T07` reprend la page physique 1 de D03 dans un
PDF d'une page dont le corps est une image et dont seul le pied de page légal
de 210 caractères est natif. Les rasters gelés sont en niveaux de gris, à
200 dpi, sans rotation, redimensionnement ultérieur ni augmentation.

Les deux dérivés reprennent des faits de T05 et T07 : ils ne sont donc pas deux
documents originaux indépendants. Leur mapping vers l'original sert à l'audit.
Une éventuelle citation du produit devra viser la **page physique 1 du dérivé**,
sans remplacer son localisateur par celui de l'original.

## 3. Revue préalable des oracles, avant toute réponse

Après le gel final, le relecteur candidat a contrôlé les empreintes des trois
PDF originaux, des deux PDF dérivés et de leurs deux rasters. Il a relu les
**neuf vues déjà conservées** : sept pages originales et les deux pages
dérivées. Il n'a lancé aucun rendu, OCR, modèle ou test. Les dix oracles et leurs
deux dérivés concordent avec les pages inspectées ; aucun désaccord d'oracle
n'a été relevé.

Cette revue vérifie notamment les sous-lignes et les inégalités de T01, les
colonnes Typ/Max et les conditions de T02/T03, les groupes et notes de T04/T05,
les négations explicites de T06/T07, les variantes de T08, la case Min vide de
T09 et la distinction absolu/recommandé de T10. Les fractions de T07, le signe
± de T05 et les dépendances des notes restent des obligations. Les valeurs
attendues intégrales sont conservées dans l'oracle gelé, sans réécriture.

Le reçu candidat a été scellé **avant toute consultation d'une sortie native
réservée**. Le relecteur référence a également scellé sa propre revue préalable
des sources et oracles avant toute réponse. Aucun des deux n'a ensuite reçu
de réponse réservée à juger.

Ces revues sont indépendantes de la préparation des oracles, mais **ne sont
pas des évaluations externes aveugles**. L'agent chargé du candidat a contribué
au code d'ingestion pendant le développement ; celui chargé de la référence
est l'auteur de correctifs API. Les rôles sont déclarés. La préparation
initiale de l'oracle reposait sur un seul préparateur qui n'avait pas modifié
le produit ; les deux contre-revues après gel en complètent la traçabilité,
sans transformer une revue de source en réussite native.

## 4. Exécution observée et incident de continuité

| Étape candidate | Observation conservée | Portée de la preuve |
|---|---|---|
| Extraction D01 | Worker terminé en 262,53 s, code retour 0 ; groupe possédé vide et leader réapé ; sortie `ready_partial` | Fin de ce worker d'extraction uniquement |
| Extraction D02 | Worker terminé en 236,21 s, code retour 0 ; groupe possédé vide et leader réapé ; sortie `ready_partial` | Fin de ce worker d'extraction uniquement |
| Extraction D03 | Checkpoints 0–11 ; dernier événement enregistré `page_load`, plage 13–13, à 04:26:26 UTC ; aucun reçu terminal | Extraction incomplète ; aucune validation de document complet |
| Lot des trois originaux | Aucun reçu terminal d'action ou d'ordonnanceur ; manifeste d'entrées candidat absent | Précondition des requêtes originales non satisfaite |
| Extraction des deux dérivés | Non démarrée dans les artefacts observés ; manifeste d'entrées candidat absent | Précondition des requêtes dérivées non satisfaite |
| Requêtes réservées | Aucun dossier de sortie, tentative, log ou reçu de requête observé pour les 14 blocs prévus | Aucune réponse documentaire à noter |

Le handle d'exécution `29763` n'était plus accessible lors du contrôle de
continuité. L'observation du retour « Unknown process id » est bornée par les
lectures d'horloge **04:32:50.761962–04:33:08.215536 UTC** ; elle n'est pas un
reçu d'arrêt natif. Les journaux de faute native et de worker D03 étaient vides
dans l'observation conservée.

Le contexte d'exécution courant ne montrait aucun processus natif de la
campagne ; les ports étaient disponibles et un verrou existant pouvait être
pris puis immédiatement relâché dans ce contexte. Ces observations ne
prouvent pas la terminaison d'un groupe dans un autre contexte. La courte
sonde ultérieure de continuité Python prouve seulement qu'une nouvelle
exécution légère peut fonctionner. Elle ne prouve pas l'arrêt de l'ancienne.

La cause reste **indéterminée** : aucun OOM, dépassement de délai, défaut produit
ou arrêt de l'hôte n'est attribué sans preuve. `cleanup_verified` reste
**false**. Les observations et les sorties partielles sont préservées. Aucun
verrou n'a été supprimé, aucune sortie écrasée et aucune reprise native
automatique n'a été créditée.

## 5. Matrice ratifiée : toutes les positions sont conservées

La décision root du **9 novembre 2026 à 04:40:02.143061 UTC** ratifie les états
ci-dessous. `BLOCKED` désigne l'impossibilité de poursuivre la dépendance
candidate et le maintien de l'arrêt opérationnel. C'est une disposition
d'audit explicite, **pas un reçu terminal fabriqué par l'ordonnanceur**.
`NOT_RUN` ne permet pas de relancer le bras de référence : l'absence de preuve
d'arrêt de l'ancien groupe s'applique aux deux bras.

| Cas | Besoin gelé | Cohorte | Référence | Candidat |
|---|---|---|---|---|
| T01 | Deux plages d'alimentation TS881 liées à leurs températures | Positive originale | NOT_RUN | BLOCKED |
| T02 | TPLH TS881 à 0,9 V : Typ/Max, deux overdrives et conditions | Positive originale | NOT_RUN | BLOCKED |
| T03 | ICC TS881 à 1,2 V : sorties basse/haute, VID et VICM | Positive originale | NOT_RUN | BLOCKED |
| T04 | Alimentation des deux groupes MCP970X et conditions générales | Positive originale | NOT_RUN | BLOCKED |
| T05 | Précision MCP9700B : Min/Typ/Max, deux températures et tension de test | Positive originale | NOT_RUN | BLOCKED |
| T06 | Conditionnement du signal MCP970X et entrée ADC | Positive originale | NOT_RUN | BLOCKED |
| T07 | Calibration/ajustage LM35 et précisions typiques | Positive originale | NOT_RUN | BLOCKED |
| T08 | Températures recommandées des variantes LM35 et alimentation | Positive originale | NOT_RUN | BLOCKED |
| T09 | Minimum garanti absent pour la sortie MCP9700B à 0 °C | Limite originale | NOT_RUN | BLOCKED |
| T10 | Absence de garantie de fonctionnement LM35 à l'absolu maximal de 35 V | Limite originale | NOT_RUN | BLOCKED |
| SCAN1_T05 | T05 sur une page image seule | Positive dérivée | NOT_RUN | BLOCKED |
| MIXED1_T07 | T07 sur une page à corps image et pied natif | Positive dérivée | NOT_RUN | BLOCKED |

Chaque bras conserve **8 positives originales + 2 limites originales +
2 positives dérivées = 12 positions**. Les 24 identités
`bras/action/cas/tentative primaire 0` ont été comparées à la matrice liée et
sont identiques. Le statut documentaire reste `UNREVIEWED` et `strict_pass`
reste `null` pour chaque position.

Il n'y a **ni note « 0/24 », ni taux de réussite, ni taux d'erreur documentaire**.
L'absence de mesures ne permet de compter des réussites, des réponses fausses
ou des abstentions. Elle ne permet pas non plus de conclure à « zéro erreur »
ou « zéro réserve injustifiée ». Les deux fins de worker ne changent aucun de
ces compteurs.

## 6. Conséquences pour les critères de confiance

**I5-D01 examine tous les segments publics, réserves comprises.** Une citation
copiée exactement, un hash de bloc valide ou une bonne valeur numérique ne
suffit pas à établir ce critère. Il faudrait encore vérifier que chaque rôle,
condition, référence, ajout et réserve est soutenu par les preuves. Le réservé
ne contient aucune réponse permettant cette évaluation : D01 y reste non
évalué. Les réserves injustifiées déjà constatées en développement restent
dans le bilan global ; en particulier, les deux bonnes plages de TMP117 en
phase 8 n'effacent ni sa réserve globale injustifiée ni la disparition du
parent « Supply range ». Aucun succès de copie/citation n'annule ce constat.

**I5-D06 est BLOCKED.** Les huit positives originales, deux limites et deux
dérivés prévus n'ont pas de mesure candidate. Les dérivés ne fournissent donc
aucune nouvelle acquisition d'I5-D04. Les contrôles d'ingestion de développement
peuvent garder leur conclusion bornée aux témoins prévus sans qualifier ce
transfert incomplet.

**I5-D07 reste bloqué pour la clôture native finale.** Les arrêts propres de D01
et D02 ne valent pas arrêt du worker D03 ou de l'ordonnanceur. La recette
HTTP/SSE finale est **NOT_RUN**, bloquée par cette absence de preuve. Aucune
latence de requête, absence de delta prématuré, libération globale de ressources
ou capacité de production n'est déduite de cet essai.

**I5-D08 distingue deux faits.** Les gels, empreintes, séparation des bras,
critères et positions primaires sont conservés, sans ajustement produit après
ouverture. La campagne primaire complète et sa comparaison documentaire ne
sont pas disponibles. Le respect des règles de conservation ne remplace pas
l'exécution manquante.

Une reprise future doit d'abord disposer d'une preuve indépendante du cycle
de vie et de l'arrêt de l'ancien groupe. Elle devra conserver cet essai primaire
interrompu, utiliser des sorties nouvelles et déclarer sa portée. Les ports
libres ou un nouveau contexte d'exécution ne constituent pas cette preuve.
Les oracles étant désormais ouverts et publiés, toute future correction devra
aussi déclarer cette exposition ; ce corpus ne redeviendra pas aveugle par
renommage d'une campagne.

## 7. Reçus et empreintes de référence

Les reçus privés sont conservés sous
`.runtime/qa/production-i5-20261108/`. Les noms et empreintes ci-dessous
permettent de les identifier sans publier le runtime ou les données
d'authentification. Les manifestes documentaires publics restent accessibles
par les liens de la section 2.

| Preuve | SHA-256 |
|---|---|
| Gel final `final-reserved-source-freeze-v3.json` | `3835b9ea656e92c7cf80de04267d1b8632f346de4c6f152f1da35f8a0c091472` |
| Plan lié `final-reserved-bound-plan-v3.json` | `e689708ccbc5ced018ca9c6bd438b0328b3d4c92825251ddf63d8ac143975492` |
| Matrice liée `final-reserved-review-matrix-bound-v3.json` | `3df80ea806526d5444af6cf2971cf118bdb1b943be1bc23be3844aeb83a4b2ad` |
| Gel des 549 fichiers `final-gates-input-freeze-v3.json` | `4105946aeef107b7f3c90153f145cea6d21ff23c3a44bf8f6b124023a249bfe0` |
| Pré-revue candidate `reserved-candidate-oracle-source-review-r01.json` | `e4a7ebbf2795562732061d3b030768b0e2c7fbe4832b9ebc31175f67b27bf5ad` |
| Pré-revue référence `reserved-baseline-oracle-source-review-r01.json` | `36f07fcfead6289e14c7d7edcb2b4e4c079fac434b368e75cdd0733937aed1bf` |
| Incident initial `reserved-dispatch-session-continuity-incident-r01.json` | `e8a425089ce9f0a01baf93be893a3cf2153188ae50930e0779a099dc172be2a2` |
| Incident complémentaire `reserved-dispatch-session-continuity-incident-r02.json` | `3e9036a40ef8503238ef9543aa71e7647765fc2cd6d1daf86417c7d5d593cb05` |
| Proposition conservée `reserved-primary-24-continuity-proposal-r01.json` | `db142befc5ca283d5c3a42cad082e8f35682cade517d832a3ee8ed772bf0ce29` |
| Contre-revue `ingestion-reserved-continuity-review-r01.json` | `b81c89c926e3037e7c13ac83c56e31f2eff32228919391df1a5708543eaa134f` |
| Décision root `root-reserved-stop-disposition-r01.json` | `7af3f487d920f9861965fd3542a0c786d10476af051725018c2df9ce5abad07c` |
| Manifeste public `sources.json` | `4d67dc071c5aa50d0e6a33cc335c9dd727d4a39c1c5fd3ae16a186c157c9a831` |
| Oracle public `questions-oracles.json` | `b36d32a580efcd644cc0d0299a0002617c64c8552dbc1964e9c7de7319b69af7` |
| Dérivations publiques `scan-transformations.json` | `ea18764c2a55db5fa61c540539777f288af6f0c52f23d73f60ee5276bedac6d1` |

Cette revue n'a modifié aucun produit, test, oracle, plafond ou ancien reçu.
Elle établit l'état des preuves disponibles et le blocage ratifié ; elle
n'attribue aucune qualification de production à la livraison des sources.
