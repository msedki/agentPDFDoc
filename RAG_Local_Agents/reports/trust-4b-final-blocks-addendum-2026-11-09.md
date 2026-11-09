# I5 — découpage des blocs réservés avant ouverture

**Rôle :** addendum de planification du harnais final, sans changement du protocole
documentaire. **Propriétaire :** qualification. **Statut du réservé :** gel final
écrit, campagne v3 interrompue puis arrêt ratifié, le 9 novembre 2026 UTC.
**Référence :** baseline
`41857e17a438fe43123e4ef8274d9d2d446bfbc2`. La préparation réservée courante est
**v3**, après l'incident de précontrôle de la phase 5. Les campagnes de
développement 6, 7 et 8 sont fermées et conservées. Le suivi 8 garde les mêmes
vingt cas ; ses revues retiennent 12/14 positifs et 6/6 limites, avec SCAN2 et
TMP117 en échec. Le suivi contrôlé 30 est aussi fermé (12/12 et 16/18).
La reprise des cinq portes code v3 est close après un changement de test seul ; le produit
reste exactement l’instantané 8. Après lecture des contrôles par root, le gel
final réservé a été écrit à 04:05:09 UTC et l’extraction a commencé à
04:13:46 UTC. Après rupture de continuité pendant D03, root a ratifié l’arrêt
à 04:40:02 UTC : référence 12 `NOT_RUN`, candidat 12 `BLOCKED`, score
documentaire non calculé (`null`). HTTP est non exécuté et bloqué. La version
d’ingénierie reste non qualifiée pour la production. Les décisions de
découpage ci-dessous précèdent bien l’ouverture.

## Gel final et ouverture effectivement réalisés

Root a relu les preuves de développement, le suivi contrôlé 30, les cinq
portes logicielles et leur contre-vérification avant d’écrire le gel final.
Le reçu source/runtime a été écrit à **04:05:09.595970 UTC**, puis le plan
lié à **04:05:24.678669 UTC**. La copie exacte des trois manifestes a suivi
cette barrière ; les questions, critères, sources produit et tests restent
gelés. Les rouges SCAN2, TMP117, L11 et L12 du développement/contrôlé sont
conservés et ne sont pas reclassés par l’ouverture du transfert.

| Preuve locale sous `.runtime/qa/production-i5-20261108/` | SHA-256 |
|---|---|
| `root-final-reserved-prerequisites-r01.json` | `24926cc0b183c6d6d73f24d6cd5931705d22bdc86c351fc939007f6db7f0c03f` |
| `ingestion-final-code-gates-v3-review-r01.json` | `a282f6d0aeee4084aff14b8d1b115271bdd5e92e456062c940505371f2fb014e` |
| `final-reserved-source-freeze-v3.json` | `3835b9ea656e92c7cf80de04267d1b8632f346de4c6f152f1da35f8a0c091472` |
| `final-reserved-bound-plan-v3.json` | `e689708ccbc5ced018ca9c6bd438b0328b3d4c92825251ddf63d8ac143975492` |
| `trust-i5-manifest-publication-v3.json` | `4bb1771745623d6b44faa5fe616478229ceff10a9d58fa23ab1609285cf24d8c` |
| `materialization-final-v3-verification.json` | `72881ad5c49ad30bddca8fe94e6c4cee4aae55b302eb34bad8b80665c143e5eb` |
| `final-reserved-native-launch-v3.json` | `2fc8bcd515ee0c383cb31f466ffc60d00cdd4db112ef772a5ac60acd9f944274` |

Une matérialisation locale réelle a vérifié les quatre manifestes, les trois
originaux et les deux paires PDF/PNG, avec les versions de rendu figées. Elle
ne lance aucune ingestion ni requête. Le plan lié conserve ses chemins
d’entrée originaux, dont les octets sont identiques à cette nouvelle sortie.
Le dispatcher a ensuite démarré la première extraction candidate à
**04:13:46.913634 UTC**. Il prévoit toujours deux lots d’extraction et quatorze
blocs de requêtes, soit **douze positions uniques par bras** ; aucun résultat
documentaire n’est déduit du lancement ni d’un état technique `done`.

## Arrêt ratifié après rupture de continuité

D01 et D02 ont terminé leur extraction candidate en 262,53 s et 236,21 s,
avec retour 0, chefs réapés et groupes vides. Leur état `ready_partial` reste
analysable avec ses limites ; ce n’est pas un succès documentaire. D03 n’a
pas de reçu terminal : trois checkpoints 0–11 sont présents, le dernier
chargement enregistré concerne [13,13] et le dernier journal est daté de
04:26:26.493150 UTC. Le service d’exécution ne retrouve plus la session 29763.
L’absence de vue sur l’ancien espace de processus empêche de vérifier son
arrêt global ; les sondes de ports et de verrou du nouveau contexte ne le
remplacent pas.

Root a ratifié la matrice des 24 positions sans réduire les dénominateurs :
8 positifs et 2 limites originaux, plus 2 dérivés positifs par bras. Les
douze références restent `NOT_RUN`, les douze candidats `BLOCKED`. Aucun
output, tentative, reçu ou log de requête n’est observé ; les jugements
documentaires restent `UNREVIEWED` et le score `null`. `BLOCKED` est la
classification de dépendance ratifiée par root, pas un reçu de fin émis par
le dispatcher interrompu.

| Preuve locale | SHA-256 |
|---|---|
| `reserved-dispatch-session-continuity-incident-r01.json` | `e8a425089ce9f0a01baf93be893a3cf2153188ae50930e0779a099dc172be2a2` |
| `reserved-dispatch-session-continuity-incident-r02.json` | `3e9036a40ef8503238ef9543aa71e7647765fc2cd6d1daf86417c7d5d593cb05` |
| `reserved-primary-24-continuity-proposal-r01.json` | `db142befc5ca283d5c3a42cad082e8f35682cade517d832a3ee8ed772bf0ce29` |
| `ingestion-reserved-continuity-review-r01.json` | `b81c89c926e3037e7c13ac83c56e31f2eff32228919391df1a5708543eaa134f` |
| `root-reserved-stop-disposition-r01.json` | `7af3f487d920f9861965fd3542a0c786d10476af051725018c2df9ce5abad07c` |

Les 172 fichiers produit et 549 entrées de portes sont inchangés. Aucun code,
critère, oracle ou plafond n’a été retouché après l’ouverture. La cause
reste inconnue ; aucun OOM, timeout ou défaut produit n’est inféré.
Aucune relance, suppression d’output, récupération forcée de verrou ou
exécution HTTP n’est autorisée dans cette session. Une future mesure exige
un cycle de vie vérifiable et de nouvelles sorties, en conservant cette
tentative. Les six portes documentaires 5–10 ont ensuite réussi une fois,
sans dérive de sources, entre 04:52:17 et 04:52:34 UTC. La publication du
travail d’ingénierie non qualifié reste à consigner.

La [revue réservée](trust-4b-reserved-review-2026-11-09.md) expose chaque
position ; le [rapport de ressources](trust-4b-reserved-resource-costs-2026-11-09.md)
conserve les coûts des seuls workers scellés. La matérialisation réelle des
entrées reste PASS dans ce périmètre distinct.

## Risque constaté dans les délais existants

Le plan réservé historique regroupait T01–T05, puis T06–T10, dans deux blocs de
cinq requêtes par bras. Le délai de 1 500 secondes de
`tools/qualification/run_grounded_native.py` couvre le processus de mesure,
donc son indexation initiale et toutes les requêtes du bloc.

Le paramètre produit de 300 secondes est un délai d’inactivité de lecture HTTP
vers Ollama. Il ne borne pas la durée totale d’une génération qui continue à
produire des fragments. Le harnais `tools/qualification/revision_campaign.py`
attend chaque tâche jusqu’à 600 secondes, puis sa cancellation jusqu’à 30
secondes. Cinq tâches peuvent donc consommer le budget du bloc avant la dernière
requête. Trois tâches de 600 secondes dépasseraient également les 1 500 secondes,
avant même de compter l’indexation et la cancellation.

Le découpage retenu est **2 + 2 + 1 pour chaque ancien bloc de cinq**, identique
sur les deux bras. Les deux dérivés restent ensemble. Ce choix est pris avant
toute ouverture des questions, des oracles ou des résultats réservés.

| Nouveau bloc | Identifiants primaires par bras | Ordre des bras |
|---|---|---|
| A1 | T01, T02 | Référence, candidat |
| A2 | T03, T04 | Référence, candidat |
| A3 | T05 | Référence, candidat |
| B1 | T06, T07 | Référence, candidat |
| B2 | T08, T09 | Référence, candidat |
| B3 | T10 | Référence, candidat |
| Dérivés | Les deux cas OCR du manifeste gelé | Référence, candidat |

Il reste **12 requêtes uniques par bras**, dont dix questions originales
(huit positives, deux limites) et deux dérivés positifs. Les questions, leurs
portées, les oracles, les critères et les paramètres du produit sont inchangés.
Les identifiants dérivés sont résolus automatiquement seulement après l’écriture
du reçu de gel final ; la matrice préparée conserve déjà leurs deux positions.

## Limites et coûts de ce choix

Deux tâches peuvent prendre 1 260 secondes avec leurs cancellations, laissant
240 secondes à l’indexation et aux autres opérations dans le bloc. Le découpage
réduit le risque de priver le dernier cas de sa tentative ; il ne garantit pas
que toute indexation et toute mesure finiront à temps. Un cas non démarré,
interrompu ou échoué reste dans son dénominateur initial.

Chaque sous-bloc démarre de nouveaux services et réindexe la totalité de son
manifeste d’entrée inchangé. Cela augmente les démarrages, le provisioning de
vérification et les indexations répétées. Les comparaisons référence/candidat
utilisent le même nouveau découpage. Les latences de ce découpage ne doivent pas
être agrégées à celles des anciens blocs A/B comme si les conditions de cache,
de démarrage et de réindexation étaient identiques. Aucun cache système n’est
vidé pour donner artificiellement une qualification « à froid ».

Les plafonds locaux restent 1 800 secondes par worker d’extraction, 1 500
secondes par bloc natif, 600 secondes par tâche et 30 secondes pour sa
cancellation. L’addition comptable des limites de cinq workers candidats et de
quatorze blocs natifs, avec démarrages, provisioning et grâces d’arrêt, est
39 970 secondes. Ce n’est ni une durée prévue ni une deadline globale : les
contrôles d’intégrité et certaines opérations de préparation s’y ajoutent.

## Plans et empreintes préservés

Les fichiers de harnais locaux sont sous
`.runtime/qa/production-i5-20261108/`. Ils ne sont pas nécessaires à la
[reproduction sur un clone provisionné](trust-4b-reproduce-2026-11-08.md), qui
utilise les outils versionnés.

| Preuve | SHA-256 | État |
|---|---|---|
| `final-reserved-run-plan.json` | `94c528ba012700cc57c301a3c13284ba37a84a6771fbdb38adbe77c98018fa48` | Historique cinq cas, conservé sans exécution |
| `final-reserved-run-plan-v2.json` | `29c8152485c6347cbc4da192a241254aa9273d8f56cb75171a7e2cf9c5d123b5` | Première préparation 2 + 2 + 1, conservée sans exécution |
| `final-reserved-run-plan-v2-r2.json` | `a5a65a68ec890c302c12f5ecc4971e4b5eda59d3739a4072478cd2e88410ebd6` | Préparation historique conservée sans exécution |
| `final-reserved-review-matrix-prepared-v2-r2.json` | `dc5a4d5a962b1a46bc0806cc5ee0de31fe6ba31df57e530ae8e7673419a7a582` | Matrice historique, 24 positions non observées |
| `final-reserved-run-plan-v3.json` | `08b2ecbc357c72dd3911daaa5fc3e680ad18cb22af42552198fda897e9f4523c` | Plan préparé conservé, lié au gel final v3 |
| `final-reserved-review-matrix-prepared-v3.json` | `c1bfa7ffb31e062910b4c6f10f7746bc1e50bbcc68ccb58a4260637c57db720a` | 24 positions, toutes non observées et non jugées |
| `run-final-reserved-v3.py` | `7baa5cae1a49328f60237cf2d6c306cf21fa14f54183bcf05c82d2b431199eae` | Dispatcher distinct, tentative unique interrompue sans reçu final |
| Reçu du corpus I5 | `6f095117dc3a49734270ef633e5b5f94ee3dc0bfed45f0a8ff0fd8faf99f1091` | Inchangé |
| Protocole documentaire I5 | `2102faf988e881c655a6b92c213a7a02705f7e268d08f93f88613f371d2e3ccc` | Inchangé |

La seule différence de la révision historique r2 était l'ajout des versions de
FastAPI, Uvicorn et Starlette aux bibliothèques vérifiées lors du gel commun.
Les blocs, sorties, cas et limites ne changent pas. Le contrôle HTTP/SSE séparé
peut vérifier à nouveau ces trois bibliothèques ; il ne s’ajoute pas aux douze
primaires réservés par bras.

La version **v3** raccorde le précontrôle des ports au helper existant
`services.runtime.supervisor.port_probe`, comme le lanceur natif corrigé. La
[revue du harnais](trust-4b-harness-recovery-2026-11-09.md) distingue le
contre-exemple reproductible de la cause historique inconnue du bloc B de la
phase 5. Elle ne change ni le produit, ni les questions, ni les budgets, ni le
découpage. Le script, le plan, le reçu de gel, le plan lié au gel, la matrice et
les sorties portent de nouveaux noms v3 ; les versions préparées précédentes
restent conservées sans exécution.

## Barrières du dispatcher

`run-final-reserved-v3.py freeze` exige la cohérence des sources du candidat
avec l’instantané, un checkout de référence immuable, l’identité des harnais,
du protocole et des artefacts natifs. Le matérialiseur versionné est inclus
dans les instantanés depuis la phase 6 ; la commande préparée ne demande donc
aucune addition hors instantané. Le reçu source final sera choisi après les
correctifs et revues du développement. Les instantanés 6 et 7 identifient
leurs propres campagnes ; ils ne constituent pas le gel final réservé.

Le reçu final est écrit **avant** le premier parsing des cas réservés. Ensuite,
le plan lié au gel résout les deux identifiants dérivés et vérifie douze cas
distincts par bras, avec empreinte de chaque définition complète de cas. Aucune
question n’apparaît dans les résumés opérationnels.

Le dispatcher exécute les deux extractions complètes candidates, puis les
quatorze blocs, séquentiellement. Avant chaque action, il vérifie les sources,
les versions, les artefacts, l’absence de charge native concurrente et au moins
6 656 Mio disponibles. Il crée une marque de première tentative avant de
lancer le sous-processus ; aucune sortie, marque ou mesure déjà présente n’est
écrasée. Une interruption reçoit un signal transmis au sous-processus possédé
pour permettre son arrêt normal.

Après chaque action, tous les groupes possédés doivent être vides et leurs
leaders réapés. Un échec de requête peut laisser continuer les autres blocs
indépendants seulement après ces vérifications. Une extraction échouée bloque
ses requêtes dépendantes, qui restent comptées. Un arrêt non prouvé, une
variation de source ou d’artefact, ou une contention de l’hôte arrête le
dispatcher. Une invocation ultérieure conserve les primaires déjà reçus ; une
tentative interrompue sans reçu terminal n’est jamais relancée automatiquement.

Douze tests synthétiques ont vérifié le découpage, les dénominateurs, la barrière
avant accès aux cas, les empreintes, les dépendances, l’interdiction d’écraser
une tentative, la continuation après échec propre et l’arrêt sur nettoyage non
prouvé. Ce sont des tests de harnais avec substituts explicites, pas des appels
natifs ni une qualification documentaire.

## Ordre des portes logicielles avant ouverture

Décision de root du 9 novembre 2026 UTC, prise avant l’ouverture du réservé :
les portes code **0 à 4** du plan de vérification finale sont exécutées après
la revue du candidat sur le développement et **avant** le gel final et
l’ouverture du transfert réservé. Elles comprennent la suite portable, les
intégrations non lentes, le module OCR réel complet, Ruff et Mypy. C’est un
écart explicite à l’ordre du §5 du protocole, qui plaçait les régressions après
le transfert. Ce déplacement permet de traiter une éventuelle régression
logicielle avant toute consultation des oracles ; aucun critère, périmètre de
test, exclusion déclarée ou seuil n’est réduit.

Les sources et les entrées de ces portes sont identifiées par leurs empreintes.
Après le transfert, leurs identités exécutables sont vérifiées à nouveau. Si
aucun octet exécutable ni aucune entrée de test figée n’a changé, les mêmes
résultats de portes restent la preuve de la livraison finale ; les suites ne
sont pas répétées facultativement. Une variation interdit de leur attribuer
la validation de nouveaux octets et doit être traitée explicitement, en
conservant les premiers résultats et la règle d’absence de mise au point sur
le réservé ouvert.

Les portes documentaires **5 à 10** sont exécutées après la rédaction du bilan :
génération et vérification du brief, vérification du pack, contrôles des
documents et des diagrammes, puis contrôle du diff. Le parcours HTTP/SSE
reste une mesure séparée sur les sources gelées, après les arrêts vérifiés.
Cette décision d’ordre est conservée dans la préparation v3. Elle ne modifie
aucun critère du transfert et ne permet aucune consultation anticipée des
questions ou des oracles réservés.

Un suivi des **trente cas contrôlés** est aussi prévu avant le gel réservé, sur
les octets du candidat final stabilisé, sans charge native concurrente. Il
utilise le harnais public existant `grounded_campaign.py`, la même fixture
identifiée par son hash et les mêmes critères, avec un dossier et un JSON neufs
`controlled-candidate-final-followup-1`. Cette reprise donne une attribution
exacte au candidat livré. Elle ne remplace ni les primaires conservés
12/12 positifs et 16/18 limites, ni le complément séparé du formateur. Ses
doubles explicites et son périmètre demeurent ceux de la campagne contrôlée ;
elle ne compte pas comme une nouvelle preuve native ou réservée.

La revue L11/L12 confirme qu'une réévaluation de `displayed=[]` ajoute
`requested_document`, puis privilégie `partial` par rapport à `unassessed`.
La correction est décidée après la fermeture de la phase 6 ; aucune édition
de ses sources n'est autorisée pendant son exécution. Les erreurs
`trace_write_failed` et la fidélité du périmètre H07 demandent également une
disposition avant gel. Une limite d'analyse ne doit pas être attribuée à tort
à une absence de document. Ces diagnostics ne changent ni les primaires
16/18 ni les critères ; le complément formateur conserve **3/3 par bras**,
soit six observations au total.

Le suivi de développement 7, démarré par root le 9 novembre à 02:19:34 UTC,
conserve vingt questions dans cinq blocs et de nouvelles sorties. Son reçu
source de 172 fichiers porte le SHA-256
`d496b48fc8b4119b9ff7cdd6b1e4960d84dd6b7bf3ffdfa1c16bf1e89a6539df`.
Les extractions complètes 6 ne sont réemployées que
si toute l'ingestion, le runtime, les configurations, les dépendances et les
préparateurs restent identiques, après contrôle de tous les reçus de fin et
d'arrêt 6. La liste de sources modifiées a été approuvée explicitement puis
comparée au delta réel ; aucun nom de fichier futur n'est accepté par défaut.
Les erreurs et observations 6, ainsi que la référence phase 5 réutilisée avec
sa portée déclarée, restent conservées. Les préparateurs ont reçu une revue
statique indépendante et le pilote une revue accompagnée de 22 contrôles
synthétiques courants ; ses tentatives précédentes restent distinctes. Aucun
résultat natif 7 n'est déduit de ces vérifications de harnais. Les portes code
et les trente contrôlés devront porter le reçu final après revue du suivi,
pas implicitement celui de l'instantané 6.

Les cinq blocs 7 sont fermés depuis le 9 novembre à 02:27:38.761928 UTC :
vingt mesures terminales `done`, cinq demandes modèle enregistrées et cinq
réponses réellement reçues, sans dérive de sources enregistrée et avec tous
les groupes possédés arrêtés et leurs leaders réapés. Ce constat technique
ne valide pas leur contenu documentaire. La revue des douze cas PDF, scan
et TI conserve **8/10 positifs** et **1/2 limite** : H06, H08 et SCAN2_H07
échouent. La revue Office séparée conserve **4/4 positifs** et **4/4 limites**,
avec huit contrôles de provenance concordants. Les reçus et leurs limites de
revue non aveugle sont rattachés au JSON de validation ; les vues cumulatives
ne sont jamais additionnées comme de nouvelles exécutions.

La portée du réemploi reste celle du développement : code ingestion/runtime,
configurations, verrous, préparateurs et sorties 6 exactes. Elle ne prétend pas
reconstruire un gel exhaustif des binaires, poids et paquets installés qui
n'avait pas été enregistré avant 6, et ne constitue pas I5-D06. Le gel réservé
effectuera sa propre capture complète. Root vérifie les reçus code 0 à 4 et
le suivi contrôlé avant d'invoquer `freeze` ; le dispatcher v3 ne consomme pas
automatiquement ces reçus et ouvre les manifestes après sa barrière durable.

## Suivi de développement 8 décidé avant tout accès réservé

Après les résultats 7, root autorise deux corrections génériques bornées :
H06 refuse une demande positive malgré les valeurs livrées, faute de liaison
avec le sujet du paragraphe ; H08 refuse sans restituer ni citer la condition
source de 10 mV. Ces défauts restent des échecs documentaires de la phase 7.
Ils motivent un suivi distinct sur les mêmes vingt questions, les mêmes
critères et les mêmes cinq blocs. Aucun plafond ni budget n'est augmenté.
SCAN2_H07 reste aussi un échec conservé de la phase 7 ; la préparation ne
présume pas sa résolution.

La décision préalable conditionnait l’invocation du constructeur 8 à la
stabilisation et à la revue des sources, avec la liste exacte des changements
7 → candidat approuvée par root. Le
préparateur exige les cinq clôtures 7, la cohérence des instantanés 6, 7 et 8,
l'identité des fichiers d'ingestion/runtime, configurations, verrous et
préparateurs, puis vérifie directement les originaux, sorties et arrêts des
trois groupes d'extractions complètes 6. Il ne prépare aucune nouvelle
extraction PDF. La lecture Office reste incluse dans le nouveau bloc Office.
Une différence dans le périmètre de réemploi bloque la préparation et demande
une disposition explicite ; elle ne déclenche aucun repli ou reprise caché.

La référence phase 5 est réutilisée avec sa portée historique. Les mesures
primaires 5, l'incident B non démarré, les erreurs 6, les vingt résultats 7 et
leurs revues restent intacts. Les sorties 8 sont neuves, une seule tentative
par cas, sans relance automatique. Le pilote 8 conserve les gardes corrigées
du pilote 7 : empreinte des octets du plan chargés avant/après chaque bloc,
contrôle du module de préflight avant son import, transmission des signaux et
arrêts vérifiés. La revue statique des trois scripts porte le reçu
`ingestion-phase8-preparation-static-review-r01.json`, SHA-256
`886d8a58a0b12ecb7c04a190b335d2fd56202bf683ca1851abf36754113d1c3c`.
Elle n'a exécuté ni préparateur ni moteur ; aucun résultat 8 n'en est déduit.

Cette décision précède tout gel réservé. Les portes code 0 à 4 et le suivi
contrôlé des trente cas porteront l'identité finalement approuvée après cette
revue de développement. Les préparations réservée v3 et HTTP v4 ne sont pas
modifiées par le suivi 8. Le réemploi reste limité au développement, sans
reconstitution d'un gel binaire exhaustif ancien ni qualification I5-D06.

## Raccord des résultats 8 et reprise de portes sur un changement de test seul

L’instantané 8 a été créé puis mesuré après revue, avec 172 fichiers identifiés
par `diagnostic-snapshot-8.json`, SHA-256
`1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b`.
Les cinq blocs se sont arrêtés proprement et les vingt états terminaux sont
conservés. Les revues documentaires non aveugles retiennent 12/14 positifs et
6/6 limites. H06 et H08 réussissent dans ce suivi ; SCAN2_H07 et N_tmp117
échouent. Le PASS de TMP117 en phase 7 demeure distinct de son FAIL en phase 8.
Le caractère sûr d’un refus ne suffit pas à réussir un cas positif.

Le suivi contrôlé des trente cas a précédé les portes code : son reçu
`b98ba82cca716fe445fa54866f8fac8f212463595a0b2c26e0b1a864635c1d49`
vérifie l’identité avant/après sur les mêmes sources 8. Les critères fixes
restent 12/12 positifs et 18/18 limites attendus ; les résultats sont 12/12 et
16/18. Les deux cas L11/L12 ne deviennent pas réussis parce que le diagnostic
est plus précis. L10 conserve son erreur de provenance attendue. Aucun
critère du corpus contrôlé ni du réservé n’a été modifié.

La première suite portable du gel logiciel v2 a ensuite échoué sur deux
attentes qui utilisaient le fichier/la question comme preuve de sujet PDF.
Root a autorisé une correction de test seulement, après diagnostic sur les
textes des fixtures : mêmes 22 positions dans le fichier, deux négatifs
explicitement nommés et huit positifs avec sujet écrit conservés avec toutes
leurs assertions. L’inventaire des 549 fichiers démontre une seule différence,
`tests/unit/test_i4_list_subjects.py`, sans ajout/suppression. Les 172 fichiers
produit, le profil, la fixture et le harnais contrôlé demeurent identiques.
La reprise ne relance donc ni les vingt natifs ni les trente contrôlés et
n’efface pas les deux échecs du portable historique.

Le nouveau plan de portes `final-gates-plan-v3.json` porte
`9c113f7bcc687e90152302915b9f8210964466927691e0ee18150d1150b86c78` ;
son gel logiciel porte
`4105946aeef107b7f3c90153f145cea6d21ff23c3a44bf8f6b124023a249bfe0`.
Il est distinct du plan réservé v3. Le pilote conserve la même logique, avec
les seuls noms de plan/gel et de sortie portable modifiés. Le rouge
`portable-final-1` (5 078 PASS, 2 FAIL, 25 skips) reste attribué au gel v2 ;
`portable-final-2` (5 080 PASS, 25 skips) est attribué au gel v3. Les portes
intégration/OCR/Ruff/Mypy ne sont lancées qu’une fois sous ce nouveau gel.
Chaque porte est conditionnée à la clôture vérifiée de la précédente ; tout
nouvel échec logiciel ou dérive impose une nouvelle disposition de root.
La reprise est fermée : intégration non lente 30 PASS/3 skips Windows,
OCR réel complet 8/8 sans skip, Ruff PASS et Mypy PASS sur 148 fichiers.
Le reçu `final-code-gates-v3-completion-1.json`, SHA-256
`a7ad9e999456423da069346880c4925c6afa9e678ec0b08e59d17de66b57f51d`,
vérifie les 549 entrées de portes et les 172 sources ROOT/instantané8 après
la dernière porte. Aucun succès documentaire ou de plateforme n’est déduit
de ces résultats ; les exclusions restent explicites.

Cet écart de test est explicite et antérieur à toute ouverture du réservé.
Il ne réduit ni les dénominateurs documentaires, ni les seuils de réussite,
ni les plafonds runtime. Les décisions de production restent séparées des
réussites logicielles. Le guide de reproduction et les reçus de validation
conservent les horaires, empreintes, exclusions et limites de chaque groupe.

## Parcours HTTP/SSE séparé

La seule préparation HTTP courante est `final-http-plan-v4.json`, SHA-256
`9196faf0b8ceb93f1c962c94e194ba1757031ec136b76a0dd0b7d7897200b9db`.
Son dispatcher `run-final-http-v4.py`, SHA-256
`7a3a1b9a99821fff85b270d3f67c3a1d09fb491227dcf9856762a4e70e1ba25a`,
réutilise le gel réservé v3 et le nouveau lanceur. Les préparations HTTP
précédentes sont conservées sans exécution ; une tentative existante de ces
versions bloque aussi une nouvelle primaire automatique. Le cas HTTP01, ses
critères et ses budgets sont inchangés. Vingt tests de gardes synthétiques
passent ; une première erreur d'initialisation des fixtures de ces tests est
conservée séparément, sans être présentée comme une exécution HTTP native.

Ce parcours était prévu hors du lot réservé, sur les sources gelées et après
arrêts vérifiés. Il reste désormais `NOT_RUN`, bloqué par l’arrêt global non
prouvé. Pour toute future exécution, il exige `operational_passed=true` dans le résultat natif,
vérifie aussi les versions FastAPI/Uvicorn/Starlette, transmet les interruptions
et écrit son reçu final. La seule présence ou empreinte d'un fichier de résultat
ne vaut pas réussite. Aucun parcours HTTP v4 natif n’a été exécuté. Le guide
décrit une [reproduction future par les outils publics](trust-4b-reproduce-2026-11-08.md#reproduction-future-du-parcours-httpsse-par-les-outils-publics),
avec un manifeste horodaté et des chemins nouveaux ; elle ne promet pas le
SHA identique de l’entrée historique et ne reprend pas cette session.

## Commandes historiques de la session de qualification

Cette recette a été préparée avant l’ouverture. Le gel et le lancement du
dispatcher ont chacun été invoqués une fois, après revue du développement et
des portes code 0–4. Le lancement s’est interrompu sans reçu terminal. Les
collecteurs ont ensuite lu les sorties existantes, sans moteur. Les chemins
ci-dessous sont historiques : ne pas réexécuter le gel ou le lancement pour
écraser ou remplacer la tentative interrompue.

```bash
: "${final_source_receipt:?Renseigner le reçu source final approuvé après les corrections}"
.venv/bin/python .runtime/qa/production-i5-20261108/run-final-reserved-v3.py freeze --source-receipt "$final_source_receipt"
.venv/bin/python .runtime/qa/production-i5-20261108/run-final-reserved-v3.py run
.venv/bin/python .runtime/qa/production-i5-20261108/collect-native-results.py --plan .runtime/qa/production-i5-20261108/final-reserved-bound-plan-v3.json --output .runtime/qa/production-i5-20261108/final-reserved-technical-observations-v3.json
.venv/bin/python .runtime/qa/production-i5-20261108/collect-native-attempts.py --plan .runtime/qa/production-i5-20261108/final-reserved-bound-plan-v3.json --output .runtime/qa/production-i5-20261108/final-reserved-model-attempts-v3.json
```

Le dernier fichier ne porte que des observations techniques : cas prévus,
cas terminaux, erreurs, routes, appels du modèle, mesures de temps, identités,
reçus d’arrêt et références des fichiers. `done`, des citations présentes ou
un contrat accepté ne deviennent jamais un PASS documentaire. Chaque verdict
reste `UNREVIEWED` tant qu’une revue explicite n’a pas vérifié la réponse
complète contre les preuves originales.

Le champ métrique `model_called=false` ne prouve pas qu’aucun essai vers le
modèle n’a eu lieu : un timeout peut survenir après l’enregistrement de
`llm.request`. Le collecteur complémentaire vérifie les chaînes de traces et
sépare `model_request_recorded`, `model_response_received`, le marqueur natif
`done` et les métriques du produit. La phase `llm.response` seule ne prouve pas
non plus une réponse : le code la consigne dans `finally`, même après timeout.
Une trace absente, incomplète ou invérifiable produit une information inconnue,
jamais une absence de tentative inventée. Ce complément ne modifie pas le
collecteur dont l’empreinte est incluse dans le plan réservé.
