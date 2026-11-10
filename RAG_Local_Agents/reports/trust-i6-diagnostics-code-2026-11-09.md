# I6R-06 — correctifs des diagnostics et conservation du registre rendu

**Rôle :** livraison du lot de code et de ses reproductions.
**Propriétaire :** intégration RAG.
**Statut :** implémenté et contrôlé sur régressions ciblées ; qualification finale en cours.
**Date de session :** 9 novembre 2026 UTC.
**Référence :** `0574f4e21ccaf95b25a48c6e226369376681ac18` et modifications de ce lot.

## Changements observables

Le diagnostic de conflit ne prétend plus qu'une condition d'essai commune
est établie. Il conserve les valeurs concurrentes et leurs citations,
sans arbitrage. Les obligations manquantes sont nommées : par exemple,
la plage de tension d'alimentation d'un composant, au lieu de « certaines
propriétés ». Le sujet, le rôle et le document sont précisés lorsque cela
est utile. Les noms proviennent du catalogue vérifié, restent bornés et
ne donnent aucune autorité au nom de fichier. Les UUID ne sont pas affichés.

Les qualificatifs lexicaux des mesures coordonnées restent attachés à leur
propre grandeur. La portée d'une négation dominante, des conditions et de
l'extrait source demeure entière. Les deux anomalies D28/D32 et les
variantes avec température placée avant la grandeur sont reproduites dans
les nouveaux tests. Les seuils restent 32 propositions et 32 mesures
par proposition pour cette analyse lexicale.

Après vérification structurelle, la trace privée conserve le registre des
segments rendus, le texte et les empreintes correspondantes. Les modes
`full`, `hashes`, `off` et les quotas existants restent respectés. Une
validation du rendu refusée ne produit pas de registre certifié. Une
annulation ultérieure reste possible : le terminal et le texte persisté
doivent confirmer la publication effective.

## Contrôles de cette livraison

Les [preuves et empreintes](trust-i6-diagnostics-code-validation-2026-11-09.json)
décrivent l'[archive des exécutions](trust-i6-diagnostics-code-evidence-2026-11-09.json.gz).
Les effectifs ci-dessous se recouvrent et ne s'additionnent pas.

| Contrôle | Résultat et portée |
|---|---|
| Nouveaux tests | 80 cas ajoutés : 41 qualificatifs, 28 diagnostics, 11 traces |
| Dernière série ciblée intégrée | 152 PASS ; tests nouveaux et contrats voisins |
| Voisins de la trace | 96 PASS ; QueryService, SQLite et extraction OOXML réels, moteur et recherche doublés explicitement |
| Revue parseur et trace | Aucune régression bloquante observée ; deux variantes TA puis la température nommée ont été corrigées avant le gel final |
| Premier passage unité complet | 5 390 PASS, un FAIL, 22 ignorés, deux exclus ; échec d'une ancienne assertion de formulation, corrigée et renforcée |
| Ruff et Mypy du premier passage | PASS, Mypy sur 155 fichiers ; nouveau contrôle final prévu après la dernière extension lexicale |
| DEV16 indépendant préliminaire | 10/16 → 16/16 cas stricts ; positifs 8/8 dans les deux bras, zéro faux appui sur 8 limites, 24/24 littéraux/citations |
| Suite portable finale | En cours au commit de code, résultat non anticipé |
| I6R06-F48 et campagne native | Pas encore exécutés ; final fermé et [gelé séparément](trust-i6-diagnostics-fixture-freeze-2026-11-09.json) |

Le premier passage complet était limité à `tests/unit`. La passe finale
porte sur `tests` avec les exclusions explicites `integration`, `acceptance`
et `slow`, comme le périmètre portable précédent. Les commandes et sorties
de reprise seront annexées au bilan final.

La revue du parseur et de la trace a été effectuée par l'auteur des
diagnostics ; elle n'est pas revendiquée indépendante de son propre lot.
L'évaluateur des jeux DEV/final est distinct des auteurs produit. Les
annotations ne constituent pas une qualification par un expert humain.

## Suite autorisée

Le [protocole DIAG-01 à DIAG-08](trust-i6-diagnostics-protocol-2026-11-09.md)
fixe la suite : résultat portable final, gel du candidat, nouveau final48,
puis huit blocs natifs séquentiels et vingt positions. Aucun ancien résultat
I6 v2 ni FINAL48 perdu n'est reclassé. Modèle 4B, plafonds, scopes et budgets
restent inchangés. La qualification de diffusion demeure ouverte.
