# I6R-06 — résultat du nouveau final indépendant

**Rôle :** bilan du contrat et du rendu sur le nouveau jeu tenu à l'écart.
**Propriétaire :** qualification indépendante.
**Statut :** exécuté, avec un échec strict conservé ; qualification globale non acquise.
**Date :** 10 novembre 2026 (UTC).
**Référence :** `0574f4e21ccaf95b25a48c6e226369376681ac18`.
**Candidat :** `522d86839d5c803c57daec0e799bfa48ee5aa8e7`.

## Résultat

Sur les 48 cas du nouveau final, la conformité stricte passe de **39/48 à
47/48**. Les huit écarts corrigés concernent six diagnostics publiés et
deux métadonnées de relations rejetées. Aucun cas strictement conforme sur
la référence ne régresse. Un échec préexistant reste présent dans les deux
révisions ; il porte sur l'admission d'une relation supplémentaire hors de la
propriété demandée, et non sur un chiffre inventé ou une tension d'entrée incorrecte.

| Mesure | Référence | Candidat |
|---|---:|---:|
| Cas strictement conformes | 39/48 | 47/48 |
| Positifs strictement conformes | 23/24 | 23/24 |
| Limites/négatifs strictement conformes | 16/24 | 24/24 |
| Faux appuis complets sur les négatifs | 0/24 | 0/24 |
| Cas avec opérande interdit accepté | 0/48 | 0/48 |
| Cas avec conclusion comparative interdite | 0/48 | 0/48 |
| Cas avec relation admise non annotée | 1/48 | 1/48 |
| Littéraux requis conservés | 68/68 | 68/68 |
| Littéraux avec citation localement liée | 68/68 | 68/68 |
| Diagnostics ciblés conformes | 0/6 | 6/6 |
| Métadonnées ciblées conformes | 5/7 | 7/7 |
| Registres et empreintes de rendu conformes | 48/48 | 48/48 |
| Erreurs d'exécution | 0/48 | 0/48 |
| Médiane du contrat (ms) | 34,81 | 31,62 |
| p95 du contrat, rang le plus proche (ms) | 75,73 | 69,35 |
| Maximum du contrat (ms) | 107,89 | 85,87 |

La baisse descriptive du p95 est de 8,42 %. Chaque cas n'a été exécuté qu'une
fois par révision, dans l'ordre référence puis candidat, avec tracemalloc.
Cette différence n'est ni une estimation causale robuste ni une mesure de
latence de la chaîne native. Le budget contractuel de 250 ms n'est pas relevé.

## Changements observés

| Famille de cas | Référence | Candidat |
|---|---:|---:|
| Propriété locale dans les propositions coordonnées | 2/4 | 4/4 |
| Rôle local dans les propositions coordonnées | 3/4 | 3/4 |
| Plage d'alimentation manquante | 2/4 | 4/4 |
| Plage de sortie manquante | 2/4 | 4/4 |
| Conflit sans condition imprimée | 2/4 | 4/4 |
| Valeur/conflit avec point d'essai explicite | 4/4 | 4/4 |
| Polarité des exceptions | 4/4 | 4/4 |
| Négation locale | 4/4 | 4/4 |
| Comparaison par sujets | 4/4 | 4/4 |
| Comparaison explicitement par document | 4/4 | 4/4 |
| Point de condition demandé | 4/4 | 4/4 |
| Borne et valeur exacte | 4/4 | 4/4 |

Les cas F03/F04 conservent désormais le rôle et la propriété de la relation
rejetée sans emprunt à la proposition voisine. Les cas F11/F12 nomment la
plage d'alimentation manquante, et F15/F16 la plage de sortie manquante,
dans le diagnostic publié et avec une portée limitée aux passages retenus.
F19/F20 n'affirment plus une condition commune absente des sources.

Ces changements sont contrôlés dans les segments du texte rendu et dans
les relations structurées. La présence d'un mot dans une citation, le seul
statut `covered` ou le seul verdict `support_validation=passed` ne suffisent
pas à ces critères.

## Échec F05 conservé

La question demande la tension d'entrée de MT9205. La source indique
5,83 V à l'entrée puis 11,92 V comme tension maximale de sortie. Les deux
révisions restituent fidèlement le passage entier avec sa citation et
établissent correctement l'obligation d'entrée à 5,83 V. Elles conservent
aussi la relation de sortie dans `matched_relations`, avec `property=output`
et `bound_role=maximum`.

Le jeu gelé n'autorise comme relation admise que celle de la propriété
demandée. La relation supplémentaire fait donc échouer le critère fermé
d'ensemble des relations dans les deux révisions. Le verdict reste FAIL.
Il ne faut pas le décrire comme une valeur fabriquée, une substitution de
la tension d'entrée ou une affirmation fausse dans la citation publiée.
Le contrat attendu pour les relations contextuelles supplémentaires devra
être clarifié dans un lot distinct, puis évalué avec un nouveau protocole.
Aucun correctif produit ni élargissement de l'oracle n'a été réalisé après
l'ouverture de ce final.

## Identités et séparation

Le final est un nouveau jeu distinct, annoté avant exécution : 24 positifs
et 24 limites ou négatifs, 24 cas FR et 24 EN. Le gel du jeu date du
9 novembre à 23:47:21 UTC. Il a été ouvert après autorisation sur le
candidat publié et propre, dont le gel date du 10 novembre à 00:04:57 UTC.
Il ne reconstitue pas le FINAL48 historique perdu et ne modifie aucun
résultat des campagnes précédentes.

Les empreintes du final, du DEV16, de l'extension d'oracle et des deux
fichiers d'aide du dépôt sont inchangées. Les 88 fichiers Python des services
sont contrôlés avant/après chaque mesure. Ils correspondent au gel externe
du candidat, dont les 142 fichiers services/outils ont aussi été revérifiés
après l'évaluation.

Le DEV16 rejoué sur le candidat publié passe 16/16, avec 24/24 littéraux et
citations. Ce résultat confirme l'état final des cas connus ; il reste
séparé du final et du DEV préliminaire, sans addition des répétitions au
nombre de cas indépendants.

## Limites et pièces reproductibles

Les documents sont synthétiques et les annotations proviennent d'un agent
indépendant des auteurs du produit, sans expertise humaine revendiquée.
Les sources et familles documentaires diffèrent entre jeux, mais les
catégories grammaticales recouvrent celles étudiées en développement.
Les résultats ne mesurent pas une généralisation à un corpus métier.

Le catalogue et le rendu sont réels. Le sélecteur de toutes les références
autorisées et le compteur de caractères sont des doubles déclarés.
Extraction, retrieval, embeddings, OCR, modèle 4B, HTTP et ressources natives
ne sont pas exécutés par cette évaluation.

Les preuves sont `final48-baseline-v1.json`, `final48-candidate-v1.json`,
`dev16-candidate-final.json` et `i6r06-final-comparison.json`. Le jeu,
`i6r06-freeze.json`, `i6r06-protocol.md` et `run_i6r06.py` permettent de
reproduire les mesures sans remplacer les sorties d'origine.
