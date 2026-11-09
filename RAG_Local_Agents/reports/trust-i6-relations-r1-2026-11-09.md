# I6 — lot R1 : portée des exclusions et prédicats

**Rôle :** point de contrôle du premier lot produit, avant R2/R3 et le final.
**Propriétaire :** intégration RAG. **Statut :** tests ciblés réussis ;
qualification complète I6 en cours. **Date :** 9 novembre 2026 (UTC).
**Référence :** protocole publié `141f77f412135b8db599b87c86395d390a664e2c`,
produit de référence `7ef57fdc38261fa4b14e077e5d1c75aee57f7eea`.

## Changements et raison

Les constructions nominales « à l'exception de », « à l'exclusion de » et
« with the exception of », y compris les apostrophes typographiques, sont
reconnues comme exclusions de points. Leur lecture reste bornée ; leurs
offsets et les exclusions explicitement coordonnées sont conservés. Une
exception dans la phrase suivante reste attachée à la preuve.

Une négation ou approximation portant sur une autre grandeur ne contamine
plus une assertion exacte lorsque deux têtes nominales et leurs prédicats
établissent des clauses distinctes. Le texte servant à la décision est
séparé du passage publié, qui conserve la phrase complète. La ponctuation
seule ne suffit pas : anaphore, précondition, tête répétée, négation
dominante, groupe traversant la frontière ou correction ultérieure empêchent
cette séparation. La grammaire ne prétend pas traiter toute portée possible.

La revue indépendante a trouvé deux problèmes pendant le développement :
la perte d'un titre court identifiant le sujet et celle d'une restriction
répétant la seconde grandeur dans la phrase suivante. Ils sont corrigés et
font partie des cinq contre-épreuves supplémentaires de revue. L'enveloppe
publique garde l'identité écrite ; sa recherche de dépendances utilise la
clause ciblée comme ancre.

## Mesures du lot

Les [reçus ciblés](trust-i6-relations-r1-validation-2026-11-09.json)
conservent les empreintes, exécutions et tentatives. Le premier groupe de
32 tests donne **18 échecs / 14 réussites** avant modification. Deux erreurs
d'attribut dans une première version des tests ont été corrigées avant ce
compte ; les deux tentatives sont conservées. Après corrections et revue,
**369 tests affectés réussissent en 9,84 s**, dont les 37 nouveaux tests R1.
Ruff réussit sur les fichiers du lot. Ces tests utilisent le catalogue et
le rendu réels, avec un compteur de tokens de test ; ils ne mesurent ni
extraction, ni recherche, ni inférence native.

Le [rejeu intégral des 24 anciens cas I5-PJ](trust-i6-relations-r1-known-2026-11-09.json)
est une régression **déjà connue**, pas le final I6. H24 passe d'un faux appui
à une réponse partielle conservant son exclusion. H06 récupère sa tension
exacte. Les faux appuis passent de **1/12 à 0/12** et les positifs couverts
de **9/12 à 10/12**, avec **28/28 littéraux** conservés. H11/H12 restent les
deux faux rejets prévus pour R2. Une seule répétition est utilisée pour ce
point de contrôle ; les latences de ce run concurrent de tests légers ne
constituent pas la mesure finale de performance.

Un premier rejeu a correctement refusé de calculer les scores après une
modification de format d'import par Ruff pendant l'exécution. Le reçu
`INVALID_SOURCE_IDENTITY` est conservé ; le rejeu retenu constate des sources
stables. Aucun résultat invalide n'est réutilisé comme réussite.

Le contrôle de revue identifie aussi une relecture quadratique des préfixes
quand une coupure est refusée. Le traitement s’arrête désormais à cette
première portée non établie, sans possibilité de la contourner plus loin.
Sur 50/100/200 clauses répétées, les médianes de trois appels du helper
sont 0,248/0,307/0,604 ms ; ce micro-contrôle ne mesure pas une requête RAG.

## Séparation et suite

Les [fixtures sont gelées](trust-i6-relations-fixture-freeze-2026-11-09.json)
avant tout changement produit : 48 DEV et 48 FINAL, 24 positifs/24 négatifs
et 24 FR/24 EN chacun. Les 96 annotations et 426 spans ont été relus par un
agent distinct, sans sortie produit et sans revendiquer une expertise
humaine. Les instances sont disjointes ; les familles grammaticales sont
largement partagées. Le FINAL reste fermé hors de l'arbre produit.

R2, R3, les ablations, la suite portable complète, la campagne native
appariée et HTTP restent à exécuter. Aucun modèle, poids, tokenizer,
dépendance, profil ou plafond n'a changé. Les critères finaux et les
réserves historiques de production restent ceux du protocole.

## Reproduction ciblée

```sh
.venv/bin/python -m pytest -q tests/unit/test_i6_relations_scope.py tests/unit/test_i6_clause_dependencies.py tests/unit/test_i5_pj_numeric_semantics.py tests/unit/test_i5_literal_scope.py tests/unit/test_i5_condition_line_scope.py tests/unit/test_i5_general_condition_lines.py tests/unit/test_i5_condition_limit_evidence.py tests/unit/test_iteration2_numeric_evidence.py tests/unit/test_iteration2_answer_contract.py tests/unit/test_enhanced_answers.py
.venv/bin/python tools/qualification/support_benchmark.py --application-root . --fixtures tests/fixtures/support_i5_pj_final.json --output /tmp/i6-r1-known.json --label I6-R1-known-I5 --repeats 1
```

Utiliser une sortie neuve et le commit R1 identifié dans les
[reçus de publication](trust-i6-relations-publications-2026-11-09.json).
Ne pas interpréter le nom historique `final` de la fixture I5 comme un
nouveau jeu réservé I6.
