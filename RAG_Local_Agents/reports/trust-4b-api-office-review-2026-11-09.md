# I5 — revue de publication API et des réponses Office

**Rôle :** relecture du raccord des preuves à la réponse, puis des huit cas
Office natifs de référence phase 5 et candidats phases 6 à 8. **Propriétaire logique :** revue du contrat API.
**Date :** 9 novembre 2026 UTC. **Statut :** revue source initiale terminée ;
huit réponses relues dans chacun des quatre blocs, avec leurs verdicts séparés.
**Référence initiale :** base `41857e17a438fe43123e4ef8274d9d2d446bfbc2`, candidat
`agentPDFDoc-i5-diagnostic-snapshot-5`, reçu SHA-256
`bddd2d348b07d154e94ed652155152bb9bbede8f9bd6e2e04715902a3f14f478`.

La revue est non aveugle. Son auteur a réalisé le correctif limité de
rattachement des relatives, puis le diagnostic de condition hors plage et le
raccord API des fragments de conditions, décrits aux §§13–15 du
[rapport de preuve](trust-4b-evidence-2026-11-08.md).
Il a également réalisé les corrections d'explication et d'autorité de sujet
des lots 7 et 8, détaillées aux §§16–17 de ce rapport.
Il n'est donc pas un évaluateur entièrement extérieur au produit. Cette revue
ne réemploie pas les anciens verdicts comme résultats de la phase 5. Le
transfert réservé I5 ne fait pas partie de son périmètre.

## 1. Raccord des contrôles dans l'instantané 5 relu avant la phase 6

Les neuf modules API relus sont identiques octet pour octet à l'instantané 5
et à ses empreintes : `query`, `context`, `structured_answer`, `answer_contract`,
`evidence_coverage`, `evidence_selection`, `literal_evidence`, `table_conditions`
et `main`. Il s'agit d'une vérification des sources ; aucun nouvel essai ou
appel modèle n'a été lancé pour cette relecture.

| Frontière | Observation dans le code | Limite de la preuve |
|---|---|---|
| Source et périmètre | `StructuredAnswerBuilder.parent` et `cell` relisent les enregistrements SQLite, leurs hashes, révisions, offsets, pages et plages autorisées. Les métadonnées du hit ne remplacent pas cette autorité. | Cohérence des enregistrements et du périmètre ; fidélité à l'original à vérifier par extraction/recette. |
| Vue transmise au 4B | `Catalogue.model_view` utilise la projection de publication et ses dépendances. Le catalogue complet reste un objet d'audit ; `schema` tire les IDs de la même projection. | Une formulation hors grammaire peut avoir une projection vide et une réponse de limitation. |
| Contexte réellement envoyé | Après les diagnostics de couverture et l'éventuelle recherche complémentaire, `finalize_catalogue` reconstruit le dernier message, recompte les tokens et produit le hash du payload. `QueryService.run` le compare à celui du catalogue. | Contrôle local du payload, distinct du comptage natif et de sa dérive mesurée. |
| Plan du modèle | Le JSON n'admet que des références et des groupes de comparaison. Les références inconnues et champs supplémentaires échouent ; une référence connue mais inadmissible reste filtrée par la publication. | La normalisation des doublons ne prouve pas la pertinence du plan ; celle-ci relève du contrat de relations. |
| Publication | `publication` complète les preuves requises, filtre les ajouts et conserve les dépendances. `render` reconstruit des passages exacts ou des calculs tracés, sous budget. `verify_rendered` rejoue texte, obligations, références et citations avant l'émission du delta public. | Contrôle structurel borné, sans certification générale de l'implication sémantique. |
| Streaming | Les jetons du plan sont enregistrés comme `structured_delta`. La route SSE exclut `structured_delta` et `structured_answer`. Le delta de réponse est émis après le contrôle final ; une fin `length` du plan renforcé produit une erreur. | Cette revue source ne remplace pas le parcours HTTP/SSE ni une mesure d'annulation réelle. |

Aucun nouveau défaut de câblage bloquant n'a été démontré dans ce périmètre.
Les sources enregistrées peuvent contenir des passages d'audit non utilisés
dans la réponse ; seuls les IDs effectivement cités entrent dans la liste de
citations terminale. Le registre conserve explicitement
`original_extraction_fidelity_verified: false` et
`general_semantic_entailment_verified: false` : leur présence n'est pas un
succès d'extraction ou de sémantique générale.

## 2. Référence indépendante des huit cas Office

Les neuf originaux ont été ouverts directement comme archives DOCX/XLSX.
Leurs hashes concordent avec le manifeste figé, SHA-256
`a12be952db4ccb9b88e017a86381afe1d9c1406ef20111555dbdc31af0175e95`.
Les paragraphes, lignes de tableaux, cellules et unités ci-dessous proviennent
du XML original, et non d'une réponse antérieure.

| Cas | Vérification attendue contre les originaux |
|---|---|
| P01 | Conserver « uniquement lorsque le couvercle est fermé » ; ne pas transformer cette condition nécessaire en condition suffisante. |
| P05 | Restituer la tension de bus avec MIN 0, MAX 36, unité V ; la cellule TYP vide ne doit recevoir aucune valeur. |
| P10 | Entrées A1 = 1,25 et B1 = 2,75 ; somme décimale 4, indiquée comme calcul avec les deux références. |
| P11 | A1 = 125 et B1 = µs ; conversion par division par 1 000 vers 0,125 ms, unité et méthode explicites. |
| L01 | La source donne 10 mA à 25 °C. La demande à 85 °C doit conserver sa limitation sans transposer cette valeur. |
| L06 | Conserver les deux documents et la divergence entre 3,0 V et 3,6 V à 25 °C. |
| L13 | Préserver les deux négations : « not 10 mA » et courant non établi. Aucune assertion positive de 10 mA. |
| L16 | Garder la note « Only at TA = 25 °C; not established at TA = 85 °C. » attachée à la plage 2–5 V et à ses en-têtes. |

La fiche de préparation, les hashes et la lecture XML sont conservés sous
`.runtime/qa/production-i5-20261108/recovery-api/office-source-review-plan.json`,
SHA-256 `d54e88a4ebf134d62bee5911319e014f2e47431279dee86a5ceceba34e28b25e`.

## 3. Résultats natifs de référence phase 5 et candidat phase 6

Le dénominateur reste de huit cas par bras : quatre positifs et quatre limites.
Les réponses complètes sont confrontées aux XML originaux décrits au §2. Les
statuts internes `covered`, `partial` ou `conflict` ne constituent pas le verdict
de cette revue. Celle-ci distingue le respect des faits, la liaison des citations
et les défauts de présentation.

### 3.1 Baseline — huit cas relus

Le bloc `development-office-baseline-queries-5` s'est terminé le
9 novembre à 00:41:23 UTC. Les huit cas ont un terminal `done`, sans dépassement
du délai du harnais. La lecture initiale des quatre premiers résultats a utilisé
SQLite en mode lecture seule pendant la fin du bloc, sans calculer d'empreinte
supposée stable de la base. L'audit consolidé a ensuite été effectué à 00:44:45 UTC,
après confirmation de l'arrêt des groupes possédés et de la récupération de leurs
processus chefs.

| Cas | Réponse confrontée à l'original | Route observée | Temps, ms | Verdict documentaire borné |
|---|---|---|---:|---|
| P01 | Extrait intégral avec « uniquement lorsque le couvercle est fermé » ; aucune transformation en condition suffisante. | Déterministe | 179,79 | PASS |
| P05 | MIN = 0, TYP vide, MAX = 36, UNIT = V ; ligne et en-têtes conservés. | Déterministe | 152,34 | PASS |
| P10 | Somme explicitement annoncée : A1 = 1,25, B1 = 2,75, résultat = 4 ; références des deux entrées et recalcul décimal concordants. | Déterministe | 112,84 | PASS |
| P11 | A1 = 125, unité B1 = µs, résultat = 0,125 ms ; division par 1 000 explicite et vérifiée. | Déterministe | 136,77 | PASS |
| L01 | Limitation sur les conditions demandées ; 10 mA reste lié à 25 °C, sans valeur affirmée à 85 °C. | Qwen3 4B | 111 495,52 | PASS |
| L06 | Les valeurs 3,0 V et 3,6 V à 25 °C sont restituées séparément avec leurs deux documents ; aucune valeur arbitrée. | Qwen3 4B | 54 817,29 | PASS |
| L13 | Les deux négations sont conservées ; 10 mA n'est pas affirmé comme courant établi. | Qwen3 4B | 44 499,57 | PASS |
| L16 | La note complète reste liée à la ligne 2–5 V et aux en-têtes ; la réponse ne transpose pas cette plage à 85 °C. | Qwen3 4B | 75 400,73 | PASS |

Ce bloc respecte donc les **8/8 critères documentaires prévus**, dont **4/4
positifs** et **4/4 limites**. Les quatre premiers n'appellent pas le modèle :
leurs traces contiennent zéro événement `llm.request`. Chacun des quatre derniers
contient un seul appel `qwen3-4b-enhanced:q4km` et une réponse du fournisseur terminée.
Le digest observé est
`0d75b13ba9d0cd42fb445d6979708adacb2679a777fb4cf717d4e6b907bccfdf`,
avec le manifeste
`aca799db2a4683a3cbd9002592ca065ed110ab29c5f4059ee65a10012348921e`.
Ces observations ne constituent pas huit preuves de génération du 4B.

Pour les huit résultats, la revue a vérifié les citations terminales contre les
citations persistées, le périmètre de la requête, la génération, la version,
la révision d'extraction, les octets de l'original conservé et les tranches de
texte désignées par les offsets. Les marqueurs de citation pointent sur les
positions exactes de la réponse. Les calculs XLSX conservent les références des
cellules A1/B1 ; leurs valeurs ont aussi été recalculées indépendamment avec
`Decimal`. Tous ces contrôles de liaison passent ; le jugement documentaire du
tableau provient de la lecture séparée des originaux et des réponses.

Trois réserves de présentation restent visibles dans cette baseline : P05 affiche
`TYP = ;`, ce qui conserve le vide sans le nommer ; P10/P11 affichent encore
l'avertissement `identifier_present_no_answer_evidence` malgré le calcul sourcé.
L16 répète aussi l'en-tête du tableau. Aucun de ces points n'ajoute une valeur
fausse dans les huit réponses observées. Ils doivent être comparés au candidat,
sans modifier le verdict factuel ni relancer la baseline.

Preuve consolidée :
`.runtime/qa/production-i5-20261108/recovery-api/office-baseline-phase5-linkage-audit.json`,
SHA-256 `36c631ca7db2880dc90ee6ad47e5e189aa7efbe8b7fdf14452904d5a16cd0d3c`.
Le collecteur ne score pas le sens documentaire. Il ouvre SQLite avec
`mode=ro` et `query_only=ON`. L'empreinte de la base est identique avant et après
lecture : `686d425b9cb57b387e3734a70565bfa0de3c4b096eebd26127b5716735cab79f`.
Le reçu d'arrêt confirme des groupes vides et des chefs récupérés.
`source-stability.json` ne relève aucune altération du code depuis le gel du bloc.

### 3.2 Candidat phase 6 — huit cas relus, un échec conservé

Le bloc `development-office-candidate-queries-6` s'est achevé le 9 novembre
à 01:53:49,716436 UTC, avec arrêt vérifié des groupes possédés. Les huit réponses
ont un terminal `done`, sans dépassement du délai du harnais. Elles ont été
relues intégralement avec les huit critères du §2, qui restent inchangés.

| Cas | Réponse confrontée à l'original | Route observée | Temps, ms | Verdict documentaire borné |
|---|---|---|---:|---|
| P01 | La condition « uniquement lorsque le couvercle est fermé » reste entière, sans implication inverse. | Déterministe | 175,75 | PASS |
| P05 | MIN 0, MAX 36, unité V ; TYP reste vide et aucune valeur ne lui est attribuée. | Déterministe | 213,39 | PASS |
| P10 | Somme annoncée comme calcul : 1,25 + 2,75 = 4 ; les deux entrées A1/B1 sont référencées. | Déterministe | 140,56 | PASS |
| P11 | 125 µs devient 0,125 ms par division par 1 000 ; la cellule d'unité B1 reste citée. | Déterministe | 142,12 | PASS |
| L01 | Refus de transposer 10 mA à 85 °C ; le seul nombre cité reste explicitement associé à TA = 25 °C. | Qwen3 4B | 66 195,76 | PASS |
| L06 | 3,6 V et 3,0 V à TA = 25 °C sont conservés avec leurs deux documents ; aucune valeur n'est arbitrée. | Qwen3 4B | 78 476,12 | PASS |
| L13 | La réponse garde « The output current is not 10 mA. » mais omet « The output current is not established by this document. », présente dans l'original et S001. | Qwen3 4B | 39 623,25 | **FAIL** |
| L16 | Plage 2–5 V, en-têtes et note complète « Only at TA = 25 °C; not established at TA = 85 °C. » conservés ensemble. | Qwen3 4B | 54 524,65 | PASS |

Le résultat strict est **7/8**, avec **4/4 positifs** et **3/4 limites**. L13
est une omission de limite documentaire. Aucun courant positif de 10 mA n'est
affirmé, mais le préambule général sur la négation ne remplace pas l'affirmation
source explicite de courant non établi. Le statut interne `partial` et le
contrôle structurel réussi ne suffisent donc pas à son acceptation. Le rouge
phase 6 reste conservé, même après un correctif ou un suivi ultérieur.

Les quatre positifs n'appellent aucun modèle. Les quatre limites ont chacune
un appel `qwen3-4b-enhanced:q4km` et une réponse fournisseur terminée, avec le
même digest et le même manifeste indiqués au §3.1. La revue indépendante a
observé dix marqueurs de citation et 200 événements `structured_delta`, avec
une validation structurée avant chaque texte public. Ces événements de plan
ne constituent pas du texte documentaire publié. P05 affiche toujours
`TYP = ;`, P10/P11 conservent l'avertissement
`identifier_present_no_answer_evidence`, et L16 répète son en-tête : ces
réserves de présentation ne sont pas requalifiées en nouvelles erreurs factuelles.

Le collecteur préparé avant les sorties a été exécuté après l'arrêt, à
02:00:27 UTC. Les **8/8 contrôles de provenance** passent : états et réponses
persistés, deltas publics, versions/générations/révisions, hashes des neuf
originaux, tranches source, offsets des marqueurs et calculs décimaux. SQLite
est ouvert avec `mode=ro`, `query_only=ON` et une courte transaction de lecture ;
son hash avant/après reste
`c8b889e0b3bfa51e3fe910cae0096eb4f3d2956651b4d91303646fb341a363b6`.
Ce résultat technique ne remplace pas les verdicts documentaires du tableau.

Preuves scellées, sous `.runtime/qa/production-i5-20261108/` :

- `recovery-api/office-candidate-phase6-linkage-audit.json`, SHA-256
  `77a1b4b4fc76ee7f012f1a14269a37103eed4f812370a802d8d096c111c3b76c`.
- `ingestion-office-phase6-independent-review-r01.json`, SHA-256
  `4ee280431442dc843bfa4eb139474ae3ac22b828dc9ba791dc5baebdc4558cd4` :
  seconde lecture des huit réponses contre les XML, avec le même échec L13.
- `ingestion-office-phase6-original-xml-r01.json`, SHA-256
  `f078ba1e323aa172ff9afea5cbc16615ea3ac7981ab3356c7d33810634036a93` :
  lecture directe des neuf archives originales et de leurs empreintes.

Le contre-contrôle séparé de qualification confirme L13 sur la mesure
`046e628abe3b705844c2229d13d8a01bed16e69410ac1875b921fd866baf25fa`
et le DOCX original
`7503dffce5f6007570225d88956754e7fdd50d4e701c3ba38d8fc31c71bf4ec1`.
Ce corpus de développement déjà consommé ne remplace ni le transfert réservé
I5, ni le parcours HTTP/SSE, ni une revue dans le navigateur. Les phases et
leurs huit dénominateurs restent distincts.

## 4. Disposition L11/L12 et limite du diagnostic général

### Résultat primaire conservé

Cette relecture du 9 novembre est limitée aux fixtures publiques, rapports
contrôlés déjà consommés et sources du code. Aucun modèle, corpus réservé ou
nouvelle campagne n'est exécuté. Les empreintes de la fixture primaire
`68a997ce…d476`, du rapport référence `1c95b14e…5d5e9` et du rapport candidat
`10517030…e2815` sont inchangées.

L11 et L12 utilisent la même demande générale sur une propriété du boîtier et
le même passage indiquant qu'il reste fermé pendant le lavage. La référence
appelle le double une fois et rejette respectivement la clé de prose ajoutée
et la référence inconnue avec `structured_answer_invalid`, sans delta public.
Le candidat produit une projection vide et une abstention déterministe, avec
zéro appel au double. Le validateur n'a donc pas reçu les deux plans injectés.

Le critère de `grounded_campaign.py`, branche `invalid_plan`, exige une erreur
autorisée **et** un appel au sélecteur. La précondition d'injection n'est plus
réunie sur ce chemin ; les deux résultats restent **FAIL** et le primaire
**12/12 positives, 16/18 limites**. I5-D05, qui demande 18/18 limites, n'est pas
démontré par cette campagne. Il serait incorrect de retirer ces cas, de
réécrire leur critère ou d'ouvrir le générateur pour améliorer le compteur.

Le [complément du formateur](trust-4b-formatter-boundaries-2026-11-08.md) vérifie
séparément les deux malformations et un plan valide sur une route qui appelle
effectivement le double : **3/3 par bras, 6/6 au total**. Il n'ajoute pas six
réussites au candidat primaire et ne mesure pas l'inférence 4B ni le parcours
HTTP/SSE. La lecture AST confirme que `Catalogue.validate`, `schema`,
`deterministic_plan`, `publication` et `verify_rendered` gardent le même code
que dans l'instantané 4 ; `query.py` est identique octet pour octet. Dans
`model_view`, seule la version du schéma d'obligations passe de la valeur 2
à la constante de version 3. Cette concordance source ne remplace pas un essai
natif du nouvel instantané.

### Défaut d'explication résiduel observé

Les deux traces montrent une limite distincte du rejet de plan : le contrat de
contexte est `kind=general`, `status=unassessed`, avec R001 présent. Après
projection et plan vides, le contrat final devient `partial` et ajoute
`missing=requested_document`. Il affiche alors une restitution partielle,
alors que la cause première est une question que la grammaire n'analyse pas.
La réponse n'invente aucun fait, mais elle peut faire confondre une limite du
moteur avec une insuffisance des preuves. La couverture des questions générales
reste également une limite réelle, que les six essais de formateur ne lèvent pas.

Chemin vérifié dans le code préparé pour l'instantané 6 :

1. `QueryService.run` évalue le catalogue complet, avec les documents requis.
2. `Catalogue.model_view` supprime les IDs pour la famille générale ;
   `deterministic_plan` produit le plan vide sans ouvrir le modèle.
3. `_render_contract.evaluate` réévalue les références affichées, ici aucune.
4. `AnswerContract.assess` déduit les documents sélectionnés de ces références
   vides, puis ajoute `requested_document` pour le document requis.
5. La priorité `partial if missing` précède le repli `unassessed`. Le rendu
   utilise donc le message partiel ; le message d'analyse non prise en charge
   existe déjà mais n'est plus sélectionné.

### Correction proposée, non implémentée pendant la phase 6

Pour une famille générale explicitement non analysable, la suppression de
toutes les références par le contrôleur ne doit pas devenir un document
manquant. Préserver le diagnostic `unassessed` et son message existant,
l'abstention, le plan vide, les citations vides et les zéro appels. Les vrais
manques de documents sur les demandes reconnues doivent rester `partial`.
Vérifier aussi le maintien de cette distinction lorsque `Catalogue.assess`
ajoute une limite de recherche : les deux causes restent auditables, sans
transformer l'une en l'autre. Aucune extension sémantique ou génération libre
n'est proposée.

Contre-exemple public proposé pour un lot ultérieur : document « Le carter
reste verrouillé pendant le rinçage. », question générale « Quelle propriété
du carter est décrite ? », périmètre contenant ce document. Le résultat doit
garder le diagnostic d'analyse non prise en charge, sans absence documentaire
artificielle, fait ou citation inventé ; le terminal reste `done` et le
générateur n'est pas appelé. Un témoin quantitatif reconnu avec document
réellement manquant doit rester partiel. Une vérification de `QueryService`
doit observer les deltas et faire échouer un double qui serait appelé.
Ces critères nouveaux ne remplacent ni ne reclassent L11/L12.

### Mise en œuvre après clôture de la phase 6

Après l'arrêt confirmé du bloc, le correctif borné est appliqué au candidat
préparé pour l'instantané 7. `AnswerContract.assess` ne transforme plus la
projection vide d'une demande générale non analysée en document manquant.
`Catalogue.assess` conserve une éventuelle limite de recherche dans un
diagnostic distinct, et le rendu évite alors le message de réponse partielle.
`verify_rendered` contrôle que le message de recherche limitée correspond
bien à cet état recalculé. Aucun fait, citation ou appel modèle n'est ajouté.

Les **six tests dédiés** `test_i5_unassessed_diagnostic.py` passent. Ils incluent
le contre-exemple public ci-dessus avec et sans limite de recherche, deux
parcours `QueryService` avec SQLite/OOXML réels et un générateur qui ferait
échouer le test s'il était appelé, et deux demandes quantitatives reconnues
qui conservent leur vrai document manquant. Ils sont inclus, sans addition de
dénominateurs, dans les **308 contrôles ciblés** du lot API 7.

La revue indépendante de qualification ne relève pas de défaut bloquant dans
ce delta ; reçu `unassessed-diagnostic-independent-review-1.json`, SHA-256
`c86ac8bcf24a96f15c11c0c9462e6d7823ed7d7406b765c28a2452b3f946e8f4`.
La correction porte sur l'explication de l'abstention. L11/L12 restent deux
échecs du critère primaire d'injection de plan, qui exige un appel au sélecteur.
Le compte **16/18 limites** et l'absence de démonstration du jalon I5-D05
restent inchangés. Le correctif L13 de dépendance littérale appartient au lot
racine, et ne modifie pas le résultat Office 6 décrit au §3.2.

## 5. Candidat phase 7 — huit critères documentaires et huit provenances vérifiés

Le bloc Office 7 s'est achevé le 9 novembre à 02:27:38,761928 UTC, puis ses
groupes possédés ont été arrêtés et réapés. Les huit cas ont un terminal
`done`, sans dérive par rapport à leur instantané. La même référence XML et
les mêmes huit critères du §2 sont conservés ; aucun résultat de phase 6
n'est remplacé.

| Cas | Vérification documentaire | Route observée | Temps, ms | Verdict |
|---|---|---|---:|---|
| P01 | La condition nécessaire « uniquement lorsque le couvercle est fermé » reste entière. | Déterministe | 161,47 | PASS |
| P05 | MIN 0 et MAX 36 V sont cités ; aucune valeur n'est attribuée au TYP vide. | Déterministe | 184,96 | PASS |
| P10 | Calcul explicite 1,25 + 2,75 = 4 avec ses deux cellules sources. | Déterministe | 170,88 | PASS |
| P11 | Conversion explicite de 125 µs vers 0,125 ms, cellule d'unité conservée. | Déterministe | 152,54 | PASS |
| L01 | Pas de transposition à 85 °C de la valeur sourcée à 25 °C. | Qwen3 4B | 65 577,68 | PASS |
| L06 | Les deux documents et leur divergence 3,0/3,6 V restent présents. | Qwen3 4B | 56 560,04 | PASS |
| L13 | Les deux négations exactes sont publiées : courant « not 10 mA » et courant « not established by this document ». | Qwen3 4B | 28 376,09 | PASS |
| L16 | La note complète « Only at TA = 25 °C; not established at TA = 85 °C. » reste attachée à la plage 2–5 V. | Qwen3 4B | 46 954,58 | PASS |

Le résultat documentaire est **8/8 : quatre positifs et quatre limites**.
L13 phase 6 reste un échec distinct ; le succès de ce suivi montre que les
deux négations sont présentes dans cette nouvelle réponse. Les quatre appels
et réponses fournisseur sont vérifiés, ainsi que les quatre routes sans
modèle, neuf marqueurs de citation et 193 événements de progrès structuré.
Ces événements de plan ne sont pas assimilés à du texte documentaire public.

Le collecteur API a ouvert la base fermée en lecture seule et vérifié **8/8
provenances** : version, génération, révision, original, hashes, tranches et
offsets, marqueurs publics, réponse persistée et calculs. Le hash SQLite avant
et après reste
`f15a74b7dfcf815dd21038bf2bfd0dea25f3494fc14a1422869b06ac74fb7144`.
La revue indépendante d'ingestion ouvre directement les neuf archives OOXML
et relit les huit réponses complètes ; elle est reliée au reçu technique
sans confondre les deux types de contrôle.

Reçus scellés sous `.runtime/qa/production-i5-20261108/` :

- `recovery-api/office-candidate-phase7-linkage-audit.json`, SHA-256
  `df7edd11edd1b63028277d788d21d37ce249e76ca42ad94174aa752d4038e90c`.
- `ingestion-office-phase7-original-xml-r01.json`, SHA-256
  `81a82266f838615bddfb533743bcc039fa13d0c517611596037c0190f766e923`.
- `ingestion-office-phase7-independent-review-r01.json`, SHA-256
  `cc8bdfbf5b65b202430843e9c2d90598188fc2b86adbe2110c71cf8c3c36f846`,
  revue sémantique initiale conservée.
- `ingestion-office-phase7-independent-review-r02.json`, SHA-256
  `db88485b03ef32638e49dcd8aec92daa2de6623661858f7f582089c29b613fa8`,
  même verdict, avec liaison explicite aux huit mesures et au reçu DB.

Cette revue de développement n'est pas aveugle : ses auteurs ont participé
aux corrections et aux revues croisées. Elle ne remplace pas la campagne
réservée, HTTP/SSE ou navigateur ; leurs dénominateurs restent séparés.

## 6. Candidat phase 8 — suivi fermé sur les mêmes huit critères

Le bloc Office 8 s'est achevé le 9 novembre à 03:23:52,344186 UTC. Avant
d'ouvrir sa base, le collecteur a vérifié le reçu d'exécution : code retour 0,
arrêt des trois services possédés, groupes vides et chefs réapés. Le reçu
global des cinq blocs confirme leur clôture. Les sources exécutables sont
celles de l'instantané 8, reçu SHA-256
`1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b`.
Aucun moteur, suite ou rendu supplémentaire n'a été lancé pour cette revue.

| Cas | Vérification contre l'original | Route observée | Temps, ms | Verdict |
|---|---|---|---:|---|
| P01 | Condition nécessaire entière : « uniquement lorsque le couvercle est fermé ». | Déterministe | 211,23 | PASS |
| P05 | MIN 0, MAX 36 V et en-têtes conservés ; aucune valeur attribuée au TYP vide. | Déterministe | 381,29 | PASS |
| P10 | Somme décimale 1,25 + 2,75 = 4, avec A1 et B1 et la méthode de calcul. | Déterministe | 144,11 | PASS |
| P11 | 125 µs / 1 000 = 0,125 ms ; cellule de valeur et cellule d'unité liées. | Déterministe | 154,59 | PASS |
| L01 | Valeur 10 mA à 25 °C citée, sans la transposer à 85 °C. | Qwen3 4B | 94 959,38 | PASS |
| L06 | Désaccord 3,0/3,6 V à 25 °C explicite, les deux documents restent cités. | Qwen3 4B | 67 951,11 | PASS |
| L13 | « not 10 mA » et « not established by this document » sont toutes deux publiées dans l'extrait exact. | Qwen3 4B | 39 300,39 | PASS |
| L16 | Plage 2–5 V avec ses en-têtes et toute la note « Only at TA = 25 °C; not established at TA = 85 °C. ». | Qwen3 4B | 50 845,80 | PASS |

Les **quatre positifs et quatre limites** satisfont les critères du §2. La
lecture complète des huit réponses ne relève aucun fait ajouté, négation
perdue ou condition détachée. Les neuf originaux ont de nouveau été ouverts
directement en ZIP/XML ; leurs empreintes et contenus correspondent aux
originaux figés. L13 phase 6 reste FAIL dans son propre dénominateur.

Les traces attestent quatre routes déterministes et quatre requêtes/réponses
réelles de `qwen3-4b-enhanced:q4km`, digest
`0d75b13ba9d0cd42fb445d6979708adacb2679a777fb4cf717d4e6b907bccfdf`,
manifest SHA-256
`aca799db2a4683a3cbd9002592ca065ed110ab29c5f4059ee65a10012348921e`.
Les huit réponses sont validées avant leur premier delta public. Les dix
marqueurs de citation sont liés aux passages exacts ; les 200 événements de
progrès structuré restent des événements de plan, distincts de la prose.

Le collecteur en lecture seule vérifie **8/8 liaisons de provenance** :
mesures et réponses persistées, originaux, versions/générations/révisions,
tranches, hashes, marqueurs et calculs. Le hash SQLite avant/après est
`62d6fa56c9e6d76cf5995f428229a5342f6d66b6f8187c2e292c57f0af7f7f21` ;
aucune dérive source n'est enregistrée. La revue indépendante d'ingestion
recoupe les huit hashes de mesure, réponse et trace avec cet audit sans
réexécuter le collecteur.

Les réserves de présentation restent explicites : P05 affiche `TYP = ;`
sans inventer de valeur ; les calculs P10/P11 gardent des avertissements
génériques de cellule et d'identifiant ; L16 répète les en-têtes. Ces points
ne modifient pas les critères documentaires figés ni leur résultat.

Reçus scellés sous `.runtime/qa/production-i5-20261108/` :

- `development-candidate-phase8-completion.json`, SHA-256
  `226ac1d46120e32a0a0cc628392c689447f3d866090b8ba7bf4c2d0634dc6fe9`.
- `queries-office-candidate-execution-8.json`, SHA-256
  `0637b10f3039dabc0f91522bc372325e9681c09b586f3f4b352724f9557b7e1f`.
- `recovery-api/office-candidate-phase8-linkage-audit.json`, SHA-256
  `7836fc7c0d963e0ad350437b95091749d44e8ce71f6a9349289281b37fd0d65c`.
- `ingestion-office-phase8-original-xml-r01.json`, SHA-256
  `a3dca29a30c9cc9957787ef5a18884a41a7760e32e51896cbed989bdfa097547`.
- `ingestion-office-phase8-independent-review-r01.json`, SHA-256
  `a495a051146e2251d9414067e955dd2538d55b68dff85d4331109ad62bfb851f`,
  première revue documentaire conservée.
- `ingestion-office-phase8-independent-review-r02.json`, SHA-256
  `fbb2c31152e106481c01f21c565f07813eb0fd8542969c5e1ec9b4568a872a9e`,
  liaison finale à l'audit DB et même verdict documentaire.

Ce résultat qualifie ces huit cas de développement déjà connus. Il ne
constitue pas un verdict global de production ni une validation des autres
cas PDF/OCR/TI, du transfert réservé ou des parcours HTTP et navigateur.
