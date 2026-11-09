# I5-PJ — revue indépendante des preuves et des réponses

**Rôle :** contrôler les annotations, les relations effectivement admises et les réponses publiées · **Propriétaire :** qualification documentaire, relecteur distinct des auteurs du produit et du jeu annoté · **Statut :** revue achevée sur DEV, FINAL, onze paires natives et HTTP01 ; critères finaux non satisfaits, qualification non acquise · **Référence :** `fe4693da07ed9e948f65e4cadb51cd43ec36ebe2`, branche `enhanced_version` · **Mis à jour :** 2026-11-09 (UTC) · **Sources de vérité :** [protocole](trust-i5-pj-protocol-2026-11-09.md), [résultats](trust-i5-pj-results-2026-11-09.md), jeux et traces identifiés ci-dessous

## Verdict de la revue

Le candidat empêche les usages exacts erronés observés dans le jeu DEV, mais
échoue encore sur le jeu FINAL conservé à l'écart du développement. Le cas
H24 admet `34 mA` au point `TA = 46 °C` alors que le passage exclut
explicitement ce point. Les trois réponses positives H06, H11 et H12 restent
incomplètes ou refusées. **Le critère PJ-D01 de zéro faux accepté et le seuil
absolu de 100 % de couverture positive échouent.** L'amélioration constatée
ne constitue pas une qualification du système.

Les citations sont conservées dans ces échecs. Une citation exacte, un
contrôle de reconstruction réussi ou le statut `covered` ne suffisent donc
pas à conclure à la justesse de l'applicabilité ou de la comparaison.

## Méthode et indépendance

Le relecteur a examiné les 24 paires référence/candidat DEV, puis les 24
paires FINAL : question, passages complets, valeur et signe, unité, sujet,
rôle, condition, relations admises et rejetées, comparaison et texte rendu.
Les annotations ont été confrontées aux passages, sans modifier les jeux,
le produit ou le barème. La revue ajoute un décompte explicite des **cas
contenant une relation numérique indûment admise** ; ce décompte ne remplace
pas la métrique gelée de fausse acceptation d'une réponse entièrement
couverte.

Le produit a été gelé à 13:34:42 UTC. Le jeu FINAL a été ouvert par
l'évaluateur à 13:35:31 UTC ; les sorties ont été produites avant 13:35:43
UTC. Le présent relecteur n'a lu ce jeu qu'après l'autorisation de la
coordination et la réception de ces résultats. Les défauts finaux sont
documentés sans retouche du produit ni nouvelle recherche de score.

Les labels sont synthétiques, produits par un agent distinct avant les
modifications, puis relus ici ; il ne s'agit pas d'une annotation par des
experts humains du domaine. Les familles documentaires distinctes sont des
familles de phrases fabriquées. Elles ne démontrent pas la généralisation à
des familles réelles de notices techniques. Les répétitions ne créent pas
de nouveaux cas indépendants.

### Artéfacts effectivement relus

Les chemins de sorties ci-dessous sont relatifs à
`.runtime/qa/i5-pj-support/`. Le [reçu durable du contrat](trust-i5-pj-support-results-2026-11-09.json)
conserve les questions, passages, réponses et mesures ; le
[reçu durable natif](trust-i5-pj-native-results-2026-11-09.json) conserve les
preuves de la chaîne complète. Les jeux sont
[`support_i5_pj_dev.json`](../../tests/fixtures/support_i5_pj_dev.json) et
[`support_i5_pj_final.json`](../../tests/fixtures/support_i5_pj_final.json).

| Artéfact | SHA-256 |
|---|---|
| Jeu DEV | `4209a27891de7af2d080094767a2b19abfab358f1bc8b735debbe2637e8bbb3b` |
| Jeu FINAL | `0b8edfb53e2d97a520a31d5df2c82d15a1955f929522696a5e1d0c8d687014ed` |
| `dev-final-baseline.json` | `79562797822e7d8f43ae39d55a93d55848904d73b7213a17fb40a7c841e0c82c` |
| `dev-final-candidate.json` | `9cfa77e46490bbc3cb0ba186bbd9f7dc138d2468efae0da5150ff76322310032` |
| `heldout-baseline.json` | `0cc52d90e33039b4c334fe527bb1895f67277462254e73d0836b6e6cf8f4b110` |
| `heldout-candidate.json` | `b33b89b609762df87c710e43f08acdf8483c600906d846f3aeea9a99c8e3ee8c` |

Les manifestes du candidat correspondent aux fichiers relus :
`answer_contract.py` SHA-256
`02a71f622f96b2e33d2ad7958d7bea826717468b9368da29077c7edef65bf88f`,
`point_conditions.py`
`cbdeca5b72d04279577bbae860f64e251f723fda988197a5545b7b79975ebf96`,
`numeric_semantics.py`
`8543b390e8848963300f46d443bdd54ecfc16ccef7f8c865661caea8893e2822`.
Les sorties signalent des sources inchangées pendant les exécutions.

## Résultats du contrôle isolé

Le harnais exerce le vrai contrat et le vrai rendu. Le comptage de jetons
est doublé et le sélecteur retient les références autorisées. Il ne mesure
pas l'extraction, la récupération ni un appel réel au 4B. Les labels
négatifs signifient qu'une valeur exacte applicable n'est pas démontrée ;
ils n'effacent pas l'information utile portée par une borne.

| Mesure, avec son dénominateur | DEV référence | DEV candidat | FINAL référence | FINAL candidat |
|---|---:|---:|---:|---:|
| Faux acceptés comme réponse exacte entièrement couverte | 10/12 | 0/12 | 9/12 | 1/12 |
| Cas négatifs avec au moins un opérande indûment admis, revue manuelle | 12/12 | 0/12 | 11/12 | 1/12 |
| Réponses positives entièrement couvertes | 10/12 | 10/12 | 9/12 | 9/12 |
| Faux rejets positifs | 2/12 | 2/12 | 3/12 | 3/12 |
| Cas satisfaisant le barème gelé | 12/24 | 22/24 | 12/24 | 20/24 |
| Passages complets conservés | 28/28 | 28/28 | 28/28 | 28/28 |
| Erreurs d'exécution du harnais | 0/24 | 0/24 | 0/24 | 0/24 |

Les trois essais de chaque cas ont des textes, valeurs, conditions,
relations rejetées et comparaisons identiques. Le premier essai reste le
résultat principal ; tous les essais sont conservés. Les positions des
annotations correspondent aux passages. Sur FINAL, les 28 marqueurs de
citation correspondent aussi exactement à leurs positions dans le rendu.
Les contrôles ne masquent pas des erreurs en choisissant une meilleure
répétition.

### DEV : valeurs et conditions relues

`C` désigne le statut produit `covered` et `P` le statut `partial` ; ces
lettres ne constituent pas un jugement de justesse. Les unités et valeurs
du tableau décrivent les passages, non des valeurs extrapolées.

| Cas | Information source contrôlée | Référence → candidat | Constat manuel |
|---|---|---|---|
| D01 | RX410 : 3,7 V nominal | C → C | Exact, sujet et rôle préservés. |
| D02 | RX411 : 6,4 mA en sortie | C → C | Exact, virgule française normalisée sans changer la citation. |
| D03 | RX412 : −12 °C en fonctionnement | C → C | Signe et unité préservés. |
| D04 | RX413 : 0 V nominal | C → C | Zéro conservé comme valeur. |
| D05 | RX414 : 4,6 V ; courant < 11 mA | C → C | La borne du courant ne modifie pas la tension. |
| D06 | RX415 : 9 mA ; tension < 12 V | C → C | La borne de tension ne modifie pas le courant. |
| D07 | RX416 : 5 mA à TA = 24 °C | C → C | Point demandé identique. |
| D08 | RX417 : 7 mA à TA = 18 °C | C → C | Point demandé identique. |
| D09 | RX418 : plage 2,4 à 5,2 V | C → C | Deux extrémités et unité correctes. |
| D10 | RX419 : plage 1,6 à 4,8 V | C → C | Deux extrémités et unité correctes. |
| D11 | RX420 et RX421 : 3,9 V chacun | P → P | Deux valeurs exactes retenues, mais égalité demandée omise. Faux rejet inchangé. |
| D12 | RX422 : 2,8 V ; RX423 : 4,2 V | P → P | Deux valeurs exactes retenues, mais différence demandée omise. Faux rejet inchangé. |
| D13 | RX424 : < 3,4 V | C → P | Extrémité retirée des relations exactes admises. |
| D14 | RX425 : ≤ 4,4 V | C → P | Même protection pour une borne inclusive. |
| D15 | RX426 : ≠ 2,6 V | C → P | Valeur explicitement exclue, non employée comme égalité. |
| D16 | RX427 : supérieure à 3,8 V | C → P | Borne verbale préservée et opérande rejetée. |
| D17 | RX428 : < 4,1 V ; RX429 : 4,1 V | P → P | Référence : mauvais opérande caché par le statut partiel. Candidat : RX428 rejeté, RX429 conservé, aucune égalité fabriquée. |
| D18 | RX430 : différent de 3,2 V ; RX431 : 3,2 V | P → P | Même distinction entre statut global et relation invalide. |
| D19 | RX432 : au plus 14 mA | C → P | Borne conservée, sans égalité à 14 mA. |
| D20 | RX433 : n'excède pas 6,2 V | C → P | Borne conservée, sans valeur nominale exacte déduite. |
| D21 | RX434 : 8 mA, `unless TA = 27 °C` | C → P | Valeur non transposée au point exclu demandé. |
| D22 | RX435 : 12 mA, `sauf à TA = 21 °C` | C → P | Même contrôle en français. |
| D23 | RX436 : 4 mA, `except at TA = 32 °C` | C → P | Exception complète conservée. |
| D24 | RX437 : 13 mA, `sauf si TA = 16 °C` | C → P | Exception complète conservée. |

Pour D17/D18, le label interdit une comparaison exacte construite à partir
de l'extrémité traitée comme valeur. Il ne signifie pas que toute
information comparative serait impossible : une inégalité stricte ou une
non-égalité peut permettre une conclusion différente dans un raisonnement
algébrique. Le candidat ne réalise pas ce raisonnement.

### Ablations DEV

| Contrôle retiré | Faux acceptés entièrement couverts | Cas avec opérande invalide | Passages conservés |
|---|---:|---:|---:|
| Qualification non exacte | 6/12 | 8/12, D13–D20 | 28/28 |
| Exclusions de point | 4/12 | 4/12, D21–D24 | 28/28 |
| Les deux | 10/12 | 12/12 | 28/28 |

La différence entre les deux colonnes vient de D17/D18, déjà partiels pour
une autre raison. Le rendu extractif conserve également 28/28 passages et
n'obtient pas de score d'exactitude relationnelle. Ces observations
attribuent l'effet aux gardes sur ces cas fabriqués ; elles ne prouvent pas
une capacité générale d'inférence.

### FINAL : revue des 24 cas après gel

| Cas | Information source contrôlée | Référence → candidat | Constat manuel |
|---|---|---|---|
| H01 | KZ700 : 7,6 V nominal | C → C | Exact et correctement attribué. |
| H02 | KZ701 : 18,5 mA en sortie | C → C | Exact, unité et notation préservées. |
| H03 | KZ702 : −31 °C | C → C | Signe conservé. |
| H04 | KZ703 : −9 °C | C → C | Signe conservé en français. |
| H05 | KZ704 : 8,3 V ; courant d'entrée > 23 mA | C → C | Pas de transfert de la borne vers la tension. |
| H06 | KZ705 : 5,7 V ; courant de sortie ne dépassant pas 26 mA | P → P | Faux rejet de la tension exacte par contamination de la négation de courant ; explication publique trompeuse. |
| H07 | KZ706 : 19 mA à TA = 42 °C | C → C | Condition correcte. |
| H08 | KZ707 : 22 mA à TA = 38 °C | C → C | Condition correcte. |
| H09 | KZ708 : plage 6,1 à 9,4 V | C → C | Intervalle correctement retenu. |
| H10 | KZ709 : plage 5,6 à 8,2 V | C → C | Intervalle correctement retenu. |
| H11 | KZ710 et KZ711 : 7,1 V chacun | P → P | Égalité des deux valeurs non restituée malgré les deux opérandes exacts. |
| H12 | KZ712 : 8,8 V ; KZ713 : 9,7 V | P → P | Différence des deux valeurs non restituée malgré les deux opérandes exacts. |
| H13 | KZ714 : > 6,7 V | C → P | Opérande de borne rejetée. |
| H14 | KZ715 : ≥ 8,6 V | C → P | Borne inclusive rejetée comme valeur exacte. |
| H15 | KZ716 : != 7,9 V | C → P | Non-égalité ASCII reconnue. |
| H16 | KZ717 : inférieure à 9,2 V | C → P | Borne verbale reconnue. |
| H17 | KZ718 : au plus 8,1 V ; KZ719 : 8,1 V | P → P | Première relation indûment admise dans la référence ; rejetée dans le candidat, seconde conservée. |
| H18 | KZ720 : au moins 6,9 V ; KZ721 : 6,9 V | P → P | Même distinction pour une borne inférieure. |
| H19 | KZ722 : au moins 29 mA | C → P | Aucun courant exact déduit de la borne. |
| H20 | KZ723 : ne dépasse pas 9,6 V | P → P | Rejet préexistant via `source_assertion_negated` ; ne pas attribuer cette réussite à la nouvelle garde. |
| H21 | KZ724 : 31 mA, `unless TA = 47 °C` | C → P | Applicabilité au point exclu rejetée. |
| H22 | KZ725 : 28 mA, `sauf à TA = 43 °C` | C → P | Applicabilité au point exclu rejetée. |
| H23 | KZ726 : 33 mA, `except when TA = 52 °C` | C → P | Applicabilité au point exclu rejetée. |
| H24 | KZ727 : 34 mA, `à l’exception de TA = 46 °C` | C → C | Faux accepté persistant : 34 mA admis au point explicitement exclu. |

H24 conserve exactement le passage et ses marqueurs. Sa relation admise a
`values=["34"]`, `unit="mA"` et
`condition="à l’exception de TA = 46 °C."`, sans motif de rejet. La
question porte précisément sur ce point. Le problème se trouve dans
l'interprétation de l'exclusion, pas dans l'absence de citation. Le rendu
ne formule pas de limitation d'applicabilité.

H06 conserve aussi la source, mais la phrase publique invoque une négation
portant sur la donnée repérée. La négation limite le courant à 26 mA ; elle
ne nie pas la tension de 5,7 V demandée. Cette défaillance préexistante
explique pourquoi une abstention ne vaut pas automatiquement une réponse
correcte ou utile. H11/H12 sont des pertes de couverture, pas des valeurs
numériques inventées.

## Revue ciblée du produit avant gel

Les modifications examinées portent sur
[`answer_contract.py`](../../services/api/answer_contract.py),
[`point_conditions.py`](../../services/api/point_conditions.py) et
[`numeric_semantics.py`](../../services/api/numeric_semantics.py).
Les qualifications non exactes sont ajoutées aux motifs de contrôle ; le
texte de source et les métadonnées de qualité ne sont pas réécrits. Les
régressions ciblées se trouvent dans
[`test_i5_pj_numeric_semantics.py`](../../tests/unit/test_i5_pj_numeric_semantics.py).

Des sondes de développement ont révélé puis vérifié les corrections de
l'exception parenthésée, du second point directement coordonné, du point
positif également exclu, de la conservation d'une exception en début de
phrase et de la confusion entre `VDD` comme condition et comme seconde
quantité demandée. Une vraie demande composée conserve les unités et les
conditions distinctes : tension à 25 °C, courant à 85 °C. Un courant donné
à 25 °C ne satisfait pas cette seconde obligation.

Les témoins positifs relus conservent notamment un point TA = 25 °C avec
exception à TA = 50 °C, une variable TJ distincte de TA, une exception
portant sur une autre grandeur, `unless otherwise noted`, ainsi qu'une
tension exacte dont seule la température est bornée. Les suffixes
`maximum`, `minimum`, `max`, `min` ne deviennent plus des tensions nominales
exactes ; les demandes explicites sur une limite `Maximum/Minimum supply
voltage` restent prises en charge avec le rôle de borne approprié.

La recherche arrière répétée de portée a été remplacée par une propagation
en un passage. La sonde indépendante de 100, 300 et 1 000 points a retrouvé
tous les points en environ 1,81, 3,51 et 12,95 ms. Cela écarte le
ralentissement quadratique observé dans une version intermédiaire sur
cette sonde ; ce n'est pas une mesure de latence native ni un engagement
pour toutes les entrées.

Ces vérifications précèdent l'ouverture FINAL et couvrent une grammaire
finie. Le résultat H24 démontre sa limite. Ni la résolution algébrique des
inégalités, ni une logique générale des exceptions et des conditions, ni
la justesse sémantique universelle ne sont acquises.

## Chaîne native : onze paires relues après clôture

La référence a été relue sur dix sorties initiales et sur le complément
NP03 ; les onze sorties candidates ont été relues après la clôture du
pilote. Le premier essai NP03 a échoué avant la création de la requête à
cause du champ de préparation `document_key` absent ; sa reprise ne doit
pas effacer cet échec. La base contient donc **11 cas terminés et 12
tentatives de préparation/exécution**, dont une erreur de préparation.

NP03 établit une erreur publique : les passages `less than 3.3 V` et
`exactly 3.3 V` sont cités intégralement, puis le rendu affirme que les
valeurs concordent, avec `numeric_agreement="equal"`. Le contrôle de
reconstruction réussit néanmoins. Le résultat du complément a pour
SHA-256
`6aee31b9937e7df24a99237ef19f7e42e02dabe8e87de42812268894f9b37c1c`.
Le candidat garde les deux passages, retient seulement l'opérande exacte et
n'émet plus d'égalité. Son résultat NP03 a pour SHA-256
`b05de1d508ed938937eab6c57a386bbf5a7d49294cc1d8baa26d5f5d8262d6ca`.

| Cas natif | Source et question contrôlées | Référence → candidat | Conclusion de la revue |
|---|---|---|---|
| N_D01 | RX410 : tension nominale 3,7 V | C → C | Valeur, unité, sujet et citation corrects. |
| N_D05 | RX414 : 4,6 V ; courant < 11 mA | C → C | La tension exacte reste utilisable. |
| N_D11 | RX420/RX421 : 3,9 V chacun, comparaison demandée | P → P | Deux bonnes valeurs, égalité omise : faux rejet inchangé. |
| N_D13 | RX424 : tension nominale < 3,4 V | C → P | La borne ne devient plus une valeur exacte. |
| N_D17 | RX428 : < 4,1 V ; RX429 : 4,1 V | P → P | Le candidat rejette l'opérande bornée ; la référence la conservait malgré son statut partiel. |
| N_D21 | RX434 : 8 mA sauf à TA = 27 °C ; question à 27 °C | C → P | Applicabilité au point exclu correctement rejetée. |
| N07 | 17 mA à TA = 33 °C ; question à 67 °C | P → P | Valeur et condition originales conservées, transfert explicitement refusé. |
| N08 | 23 mA à TA = 28 °C ; question à 74 °C | P → P | Même limitation correcte. |
| NP01 | PDF : tension nominale d'alimentation < 3,3 V | C → P | Borne citée, sans exactitude indue. |
| NP02 | PDF : tension nominale d'alimentation exactement 3,3 V | C → C | Valeur exacte préservée. |
| NP03 | Comparaison des deux PDF précédents | C → P | Fausse concordance publique supprimée, deux sources intégralement rendues. |

Les 14 passages attendus sont intégralement présents dans les réponses et
dans les objets de citation des deux bras. Les identifiants `R001`/`S001`
peuvent désigner des documents différents selon l'ordre de récupération :
la revue compare le texte et le document effectif. En particulier, NP03
candidat place le PDF exact avant le PDF borné ; aucun opérande erroné ne
reste admis sous l'effet de ce changement d'ordre.

| Mesure native | Référence | Candidat |
|---|---:|---:|
| Cas terminés, sur 11 cas planifiés | 11/11, dont un complément | 11/11 |
| Tentatives de préparation/exécution | 12 | 11 |
| Erreurs de préparation conservées | 1 | 0 |
| Faux appuis exacts complets, sur 7 négatifs | 4/7 | 0/7 |
| Cas avec opérande invalide admis, revue manuelle | 5/7 | 0/7 |
| Couverture positive, sur 4 positifs | 3/4 | 3/4 |
| Fausses égalités publiées | 1, NP03 | 0 |
| Passages complets dans réponses et citations | 14/14 | 14/14 |
| Cas avec appel réel au 4B | 4/11 | 8/11 |

Les huit traces candidates ont été relues : `llm.request` appelle
`qwen3-4b-enhanced:q4km` avec le digest verrouillé
`0d75b13ba9d0cd42fb445d6979708adacb2679a777fb4cf717d4e6b907bccfdf` ;
`llm.response` comporte `received_done=true` et le résultat un `eval_count`
positif. Les cas exacts N_D01, N_D05 et NP02 suivent le chemin déterministe.
Déclarer un modèle dans le profil ne prouverait pas ces appels.

La protection entraîne aussi un coût : N_D13, N_D21, NP01 et NP03 passent
du contrat déterministe à une génération structurée par le 4B. Leurs temps
de requête observés passent respectivement d'environ 0,46, 0,59, 0,31 et
0,67 seconde à 55,60, 47,51, 53,04 et 71,29 secondes. Il s'agit d'un essai
par cas, avec effets de chargement et de cache ; aucune accélération
générale n'est revendiquée. Les temps du contrôle isolé Python ne décrivent
pas ce coût natif.

Le pilote candidat termine avec code 0, sans dépassement de délai. Ses
reçus confirment les groupes possédés vides, les leaders récoltés et
`all_owned_services_stopped=true`, avec les données préservées. Les blocs
de référence, y compris celui contenant l'erreur de préparation, ont aussi
leurs reçus d'arrêt. L'arrêt réussi ne transforme pas l'erreur historique
en succès.

Ces essais exercent l'ingestion DOCX réelle ; les PDF utilisent les
extractions natives préparées et vérifiées avant les deux bras. Ils
n'exercent pas l'OCR. Le corpus est issu du développement, distinct du jeu
FINAL de réception : le zéro faux accepté natif ne corrige pas le résultat
H24 et n'annule pas la perte de couverture N_D11.

### Parcours HTTP/SSE distinct

Le scénario HTTP01 historique emploie un manifeste propre au transport ;
il n'est pas un second passage des onze cas natifs. Après clôture, la revue
de la question, des DOCX originaux, de la réponse, des citations et de la
trace conclut à une restitution documentaire correcte pour ce cas :

- A donne `Composant AX71. Supply voltage: 2.8 V at 70 °C.` ; B donne
  `Composant AX71. Supply voltage: 3.2 V at 70 °C.`. Les deux passages sont
  intégralement cités ; leurs valeurs, unité, composant et température sont
  conservés.
- La réponse signale des valeurs différentes et n'arbitre aucune source.
  Le contrat indique `conflict` et `numeric_agreement="different"`. Il
  précise que le rôle des valeurs n'est pas établi, ce qui correspond à
  l'absence de rôle nominal, typique ou maximal dans ces deux phrases.
- La trace comprend un échange réel complet avec le même 4B verrouillé,
  avec `received_done=true` et 52 jetons produits. La mesure de la requête
  est d'environ 149,05 secondes ; aucun compteur de profil seul n'est
  interprété comme preuve d'inférence.
- Les neuf contrôles de publication sont vrais, notamment le rendu
  vérifié avant les deltas publics, l'absence d'événements structurés privés
  dans le flux public, un seul terminal de succès et l'identité entre
  réponse stockée et publiée. Les sept contrôles de persistance des
  versions sont également vrais.

Le nouveau DOCX A donne 3,0 V à 70 °C. Après son ingestion, les objets de
citation de l'ancienne réponse sont identiques et restent attachés à la
version portant 2,8 V. Les hashes des deux originaux avant/après sont
identiques ; les trois fichiers d'entrée correspondent à leurs empreintes
gelées. Le texte des originaux a aussi été vérifié directement dans leur
contenu DOCX.

La télémétrie compte trois lancements du worker natif, sans appel injecté
ni réutilisation d'extraction. Le reçu terminal vaut code 0, sans dépassement
de délai ; le listener API est fermé, les groupes possédés sont vides et
les services sont arrêtés. `measurements/query.json` porte le SHA-256
`871fd3e5ffe6c5e600900e60b36264bdbeaafdbee7fa0877fa9658896681f173` et
`http-final-result.json`
`f6e366cca9054cc169e2b266370db4371aa8730061e72e13f9a55d4a91c8a2fb`,
dans `.runtime/qa/i5-pj-support/native-http-candidate/`.

Ce résultat démontre le parcours HTTP/SSE et la persistance des preuves sur
un scénario candidat, avec son contrôle documentaire distinct. Il ne
représente pas un échantillon natif supplémentaire du jeu FINAL, une
comparaison de versions produit sur HTTP ou une qualification navigateur.

## Portée de la conclusion

La revue bibliographique [associée](trust-i5-pj-research-2026-11-09.md)
justifie la séparation entre fidélité des citations, applicabilité,
exactitude, couverture et abstention. Les chiffres ci-dessus restent des
résultats locaux sur des données fabriquées. Ils ne sont pas les scores
des publications et ne qualifient ni l'OCR, ni un corpus réel complet, ni
les autres plateformes. L'ajout de HalluGuard ou d'un second modèle reste
différé.

Les erreurs H24, H06 et les comparaisons omises sont des constats à
conserver pour une itération ultérieure avec un nouveau protocole. Les
intégrer immédiatement au développement puis annoncer ce même jeu comme
validation indépendante détruirait la séparation qui rend ce résultat
interprétable.
