# I6 — reprise des frontières de portée

**Rôle :** preuve du lot de reprise des conditions et du budget d’obligations.
**Propriétaire :** intégration et qualification RAG.
**Statut :** correctifs et contrôles ciblés validés ; qualification globale ouverte.
**Date :** 9 novembre 2026 (UTC).
**Référence :** `250a7d209aac7deb1dfb3705ae47167c56136e80`, branche `enhanced_version`.

## Défauts reproduits sur la révision publiée

Le point de reprise de l’ancien environnement décrit des correctifs non publiés,
sans fournir leurs sources. Les scénarios ci-dessous sont reproduits à nouveau ;
leurs preuves ne reprennent aucun résultat ni hash d’exécution historique.

- Une condition portant sur `MA` pouvait être validée par une source portant sur
  `mA`. La normalisation de compatibilité pouvait également confondre `x²` et
  `x₂`. Une telle égalité n’est pas établie par le document.
- Une précondition commune à une demande de tension et de courant ne restait
  attachée qu’au premier composant. Un courant documenté sous un autre mode ou
  à un autre point de température pouvait alors être admis.
- Une demande qualitative de deux sujets dans 129 documents annonçait deux
  obligations avant d’en construire 258, au-delà du plafond de 256.

## Correction

Les clés des prédicats conservent les symboles et la casse ; seuls les espaces
sont normalisés. La grammaire numérique conserve ses conversions exactes et ses
identités de variables : une égalité de température ne permet pas de confondre
`TA` et `TJ`.

Une condition écrite avant les grandeurs coordonnées s’applique à chaque
composant seulement si son délimiteur existe dans la question complète avant
la première grandeur. Les conditions verbales et les points numériques suivent
cette même frontière. Un préfixe inachevé, une exclusion ou une alternative
non interprétée restent une limite explicite ; les extraits sont cités sans
fournir d’opérandes admissibles. Les conditions locales propres à chaque
quantité restent distinctes.

Le budget qualitatif compte les documents et les sujets avant l’analyse des
candidats. Il conserve les plafonds de 256 obligations et de 65 536 caractères.
Le correctif n’introduit ni dépendance, ni modèle, ni relèvement de budget.

## Vérification et reproduction

Le module final de 50 régressions donne **42 échecs / 8 succès** sur la
référence, puis **50 succès** sur le correctif. Les 42 échecs de tests ne sont
pas 42 réponses fausses indépendantes : plusieurs assertions contrôlent la
propagation des conditions et le refus avant allocation. Le groupe de voisins
passe **526 tests en 8,62 s**, dont ces 50 cas. Ruff et Mypy passent sur les
fichiers concernés ; la revue indépendante ne garde pas de réserve bloquante.

Une première tentative de référence avait importé le candidat en raison du
répertoire courant : elle est conservée comme **INVALID** et n’a reçu aucun
score de référence. La mesure de référence suivante vérifie le chemin des
imports et les empreintes des sources. Les journaux complets, échecs et reprises
compris, sont [archivés sans perte](trust-i6-recovery-scope-logs-2026-11-09.json.gz).

Les contrôles complets, versions et empreintes sont conservés dans le
[reçu de validation](trust-i6-recovery-scope-validation-2026-11-09.json).
Les tests utilisent le véritable contrat et le rendu avec des extraits
synthétiques ; le compteur de tokens est un double identifié. Ils ne mesurent
ni retrieval, ni inférence 4B, ni généralisation à un corpus métier.

```sh
.venv/bin/python -m pytest -q tests/unit/test_i6_recovered_boundaries.py
.venv/bin/python -m ruff check services/api/answer_contract.py services/api/predicate_conditions.py tests/unit/test_i6_recovered_boundaries.py
.venv/bin/python -m mypy services/api/answer_contract.py services/api/predicate_conditions.py
```

Les régressions couvrent aussi les cas positifs, la fidélité des citations,
les formes FR/EN, les points numériques et leurs exclusions, ainsi que le
refus avant allocation au-delà du plafond. Les contrôles de code et le jeu de
développement restent distincts du final I6 gelé dans l’ancien environnement.

## Sources et limites

Le [protocole I6](trust-i6-relations-protocol-2026-11-09.md) et les références
primaires qu’il contient restent applicables. La documentation Python 3.12
sur [`unicodedata.normalize`](https://docs.python.org/3.12/library/unicodedata.html#unicodedata.normalize)
et [`str.casefold`](https://docs.python.org/3.12/library/stdtypes.html#str.casefold),
consultée le 9 novembre, décrit des transformations destinées à comparer des
formes compatibles ou sans distinction de casse. Ce contrat ne prouve pas
l’identité de symboles techniques ; cette décision est vérifiée ici par les
contre-exemples du dépôt.

L’ancien correctif de distribution Linux n’est pas repris : ses modules
concernés n’existent pas dans cette révision. Les quatre témoins de chargement
et de provisionnement ciblés passent sur la version publiée. Aucun résultat
d’installation ou de GPU réel n’en est déduit. La qualification de production
reste ouverte.

Le final I6 historique de 48 cas n’a pas été retrouvé dans les emplacements
accessibles examinés. Son SHA-256 gelé est conservé dans le reçu ; aucun score
n’est reconstruit et aucun nouveau jeu n’est substitué sous cette identité.
