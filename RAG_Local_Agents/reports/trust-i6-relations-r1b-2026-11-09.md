# I6 — compléments de portée après le nouveau développement

**Rôle :** point de contrôle R1b, après R1 et R2.
**Propriétaire :** intégration et qualification RAG.
**Statut :** qualité de développement vérifiée ; coût et qualification finale ouverts.
**Date :** 9 novembre 2026 (UTC). **Référence :** R2 publié
`5184200c5fb7cc26d7b1738c0494fa2d708fd5a4`.

## Correction et preuve documentaire

Le premier passage du nouveau DEV expose trois faux appuis complets et quatre
rejets de statut sur les 24 positifs. Les corrections portent sur les formes
publiques reproduites : « exception faite de », exclusion d'une condition
verbale, négation dominante « No part of… », prédicats indépendants, propriétés
entrée/sortie et deux valeurs dont une seule est explicitement niée.

La partition exige des têtes mesurées explicites. Elle conserve les négations
dominantes, dépendances, anaphores et groupements non résolus ; une coordination
gouvernée par une condition n'est pas transformée en affirmation indépendante.
Elle examine au plus 32 clauses par phrase et garde les offsets Unicode ainsi
que la citation complète. Deux valeurs affirmatives concurrentes restent un
conflit. Une affirmation et sa négation pour la même valeur, y compris après
conversion exacte d'unités, ne deviennent pas un appui certain.

Une condition verbale demandée doit être présente littéralement avec une
polarité positive. Les mots ne sont pas remplacés par des synonymes. Une
exclusion gouvernante survit à un marqueur vide ou à une clause composée d'un
seul point numérique ; des états différents ne sont pas présumés incompatibles.
La grammaire existante des points numériques reste distincte.

Un maximum demandé comme nominal, ou une valeur attribuée à « l'un ou l'autre »
de deux sujets sans identité établie, reste cité comme diagnostic. Il n'entre
pas parmi les opérandes admissibles. Une courbe de caractérisation d'un rôle
incompatible conserve son exclusion historique.

## Résultat apparié de développement

Les [résultats et reçus](trust-i6-relations-r1b-validation-2026-11-09.json)
portent les empreintes exactes et les 48 verdicts de chaque bras. Les trois
sorties complètes, avec leurs trois répétitions, sont conservées sans perte
dans les archives gzip liées par ce reçu ; elles ne sont pas tronquées aux
seuls cas réussis.

| Mesure primaire | Référence I5-PJ | Candidat R1b + R2 |
|---|---:|---:|
| Cas réussis | 27/48 | 48/48 |
| Faux appuis complets sur négatifs | 7/24 | 0/24 |
| Positifs entièrement corrects | 13/24 | 24/24 |
| Littéraux requis avec citation | 64/69 | 69/69 |
| Cas avec opérande interdit | 6 | 0 |
| Cas avec conclusion interdite | 3 | 0 |
| p95 du contrat | 176,90 ms | 319,59 ms |

Le témoin extractif conserve 69/69 littéraux ; il n'émet pas de décision de
suffisance et ne reçoit donc pas de score d'appui sémantique. Les trois
répétitions ne multiplient pas les effectifs : 48 cas distincts, premier
passage primaire, aucune variation ou erreur d'exécution. Sources, fixture
et harnais sont identiques avant/après les mesures.

**Le coût n'est pas validé à ce point :** médiane candidat 138,33 ms,
p95 319,59 ms et maximum 516,88 ms. Le p95 dépasse le seuil préalable de
250 ms. Le prochain lot examine les répétitions de calcul et la route partielle,
sans augmenter ce seuil ni les plafonds du modèle.

## Vérifications et corrections de l'évaluation

Le groupe élargi conserve son premier rouge : 288 succès et une régression
sur la caractérisation. Après correction, il passe 289 tests. La revue ajoute
les frontières d'exclusion verbale vide et de coordination conditionnelle ;
les groupes affectés passent respectivement 130 puis 78 tests. Ces groupes
se recouvrent et ne forment pas un cumul de tests indépendants. Ruff et Mypy
des fichiers concernés passent ; l'annotation de type manquante du premier
contrôle Mypy a été corrigée. La revue indépendante est levée sur ces deltas.

Le [reçu de revue de l'oracle](trust-i6-relations-oracle-review-2026-11-09.json)
conserve ses corrections avant ouverture du final. Un littéral minimal requis
avait été confondu avec tout le contexte verbal admissible d'un fait : seul
D07 change de verdict lors du rescorage des sorties antérieures, dans les
deux bras. Le contrôle des points numériques reste lié à la clause atomique,
et D04 de référence reste rejeté. Les annotations et seuils n'ont pas changé.
Les anciens rapports et le harnais précédent restent conservés.

Le préparateur natif joint construit les 23 originaux synthétiques des 18
positions prévues et conserve leurs SHA ainsi que leurs liaisons aux passages.
Ses contrôles ne constituent pas une campagne native. La première tentative
interrompue reste décrite dans son [reçu](trust-i6-relations-native-attempt1-2026-11-09.json).
R3, les ablations, la suite portable, la nouvelle campagne native/HTTP et
les 48 cas finaux restent à exécuter. Le final n'est pas ouvert par ce lot.

## Reproduction

```sh
.venv/bin/python -m pytest -q tests/unit/test_i6_development_scope.py tests/unit/test_i6_diagnostic_scope.py tests/unit/test_i6_subject_comparisons.py tests/unit/test_i6_relations_scope.py tests/unit/test_i6_clause_dependencies.py tests/unit/test_iteration2_answer_contract.py tests/unit/test_iteration2_numeric_evidence.py tests/unit/test_enhanced_answers.py tests/unit/test_api_structured_answer.py
.venv/bin/python tools/qualification/relations_benchmark.py --application-root . --fixtures tests/fixtures/support_i6_dev.json --output /tmp/i6-r1b-dev-fresh.json --label candidate-r1b --mode contract --repeats 3
```

Utiliser une sortie neuve et le commit identifié dans les
[publications vérifiées](trust-i6-relations-publications-2026-11-09.json).
Ce point de contrôle ne qualifie ni le transfert industriel ni les plateformes.
