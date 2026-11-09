# I6 — lot R2 : sujets et documents comparés

**Rôle :** point de contrôle des obligations et conclusions comparatives.
**Propriétaire :** intégration RAG. **Statut :** validation ciblée et revue
réussies ; développement I6 et final encore ouverts. **Date :** 9 novembre
2026 (UTC). **Référence :** lot R1 publié `729524cea4372f3bd5614a380698123f25daf532`.

## Comportement livré

Une comparaison de plusieurs sujets exige une preuve applicable pour chaque
sujet et propriété dans l'ensemble des documents autorisés. Elle ne demande
plus que chaque document décrive chaque sujet. Les obligations sont à nouveau
croisées avec les documents quand la question précise « dans chaque document » ;
les sujets sont alors comparés séparément dans chacun d'eux. Les formulations
explicites de comparaison entre documents conservent cet axe.

Les signatures gardent propriété, rôle, borne, garantie, condition, configuration,
polarité et identifiants supplémentaires. Seul le sujet comparé est retiré de
la clé commune. Les références de chaque opérande restent exposées avec son
sujet, et le rendu cite ces mêmes preuves. Un nom de fichier seul n'établit
pas l'identité d'un opérande comparé.

Des valeurs concurrentes pour un même sujet dans plusieurs documents restent
un conflit lorsqu'on demande une comparaison collective des sujets. Deux
ensembles identiques de valeurs contradictoires ne deviennent pas une égalité
scalaire. Le contrôle du rendu revalide aussi les deux champs qui indiquent
l'axe et la portée par document ; leur falsification est détectée.

## Vérification et limites

Les [reçus logiciels](trust-i6-relations-r2-validation-2026-11-09.json)
conservent le rouge initial corrigé, les reprises et leurs empreintes.
Les 16 premiers contretests donnaient **8 échecs / 8 réussites** avant R2.
Le groupe final passe **248 tests ciblés en 12,19 s**, puis **23 tests de
comparaison en 2,25 s**, incluant les deux derniers contrôles de falsification.
Ruff réussit. Une revue indépendante en lecture seule ne relève aucun blocage
sur les axes, conflits, obligations et preuves du diff.

Une ancienne question de régression demandait implicitement l'axe documentaire.
Elle précise maintenant « entre les deux documents », en conservant toutes
ses assertions de divergence. La question collective d'origine est testée
séparément et doit conserver le conflit interdocuments. Il ne s'agit pas de
réduire une attente de fidélité pour rendre le test vert.

Les [48 anciens cas I5-PJ](trust-i6-relations-r2-known-2026-11-09.json)
passent : **24/24 DEV et 24/24 ancien final**, 24 positifs couverts sur 24,
aucun faux appui complet parmi les 24 négatifs et **56/56 littéraux** conservés.
D11/D12 et H11/H12 sont donc réparés, en plus de H06/H24 traités par R1.
Ces cas sont connus et ne remplacent pas les 48 cas réservés I6. Le rejeu
précède seulement l'ajout des deux champs de métadonnées à la revérification
du rendu ; cet ajout possède ses contretests dédiés.

Le nouveau DEV I6, les compléments qu'il révélera, R3, les ablations et les
portes complètes restent en cours. La grammaire choisit un axe parmi des
formulations explicites ; aucune interprétation universelle n'est revendiquée.
Le premier essai natif de référence est incomplet après rupture d'exécution
et possède un [reçu d’incident](trust-i6-relations-native-attempt1-2026-11-09.json).
L’ancien namespace n’étant pas identifié, son arrêt ne peut pas être certifié
par la seule absence observée dans le nouveau. Aucune réussite native n’est
attribuée à ce lot.

## Reproduction

```sh
.venv/bin/python -m pytest -q tests/unit/test_i6_subject_comparisons.py tests/unit/test_i6_relations_scope.py tests/unit/test_i6_clause_dependencies.py tests/unit/test_iteration2_answer_contract.py tests/unit/test_iteration2_numeric_evidence.py tests/unit/test_enhanced_answers.py tests/unit/test_api_structured_answer.py
.venv/bin/python tools/qualification/support_benchmark.py --application-root . --fixtures tests/fixtures/support_i5_pj_dev.json --output /tmp/i6-r2-known-dev.json --label I6-R2-known-DEV --repeats 1
.venv/bin/python tools/qualification/support_benchmark.py --application-root . --fixtures tests/fixtures/support_i5_pj_final.json --output /tmp/i6-r2-known-final.json --label I6-R2-known-final --repeats 1
```

Utiliser une sortie neuve et le commit R2 identifié dans les
[reçus de publication](trust-i6-relations-publications-2026-11-09.json).
