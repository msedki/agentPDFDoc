# I6 — bilan natif v2, route partielle et limites de qualification

**Rôle :** résultats de la campagne figée et état des critères I6R-D01 à D08.
**Propriétaire :** intégration et qualification RAG.
**Statut :** bilan avec réserves ; qualification globale non acquise.
**Date :** 9 novembre 2026 (UTC).
**Référence native :** `250a7d209aac7deb1dfb3705ae47167c56136e80`.
**Candidat natif :** `6394f624704fed6d18c2a230bebb2f6f571d5439`.

## 1. Résultat et portée

Sur les 18 positions natives originales, le candidat produit 18 réponses,
contre 13 réponses et cinq erreurs de protection mémoire pour la référence.
La revue documentaire distingue **16 réponses candidat sans réserve publiée**
et **deux réponses dont le diagnostic de conflit dépasse les conditions
explicites des sources**. Les 29 littéraux requis du candidat et leurs
citations du document attendu sont conservés. Ces deux réserves empêchent
de présenter les 18 textes comme intégralement conformes.

Le candidat élimine les appels redondants sur les neuf positions admissibles
à la route `deterministic_evidence_limit`. Il ne réalise plus qu'un échange
4B sur les 18 positions originales : le quota préalable de deux échanges
terminés par bras n'est donc pas atteint. Les témoins supplémentaires restent
des observations séparées et ne réparent pas ce dénominateur.

Les [mesures techniques](trust-i6-native-v2-technical-2026-11-09.json), la
[revue documentaire](trust-i6-native-v2-documentary-2026-11-09.json) et les
[preuves sélectionnées](trust-i6-native-v2-evidence-2026-11-09.json.gz), avec
leur [inventaire](trust-i6-native-v2-collection-2026-11-09.json), permettent
de distinguer le résultat applicatif, le transport, la fidélité documentaire
et l'exécution réelle du modèle. Aucun statut de contrat n'est utilisé seul
comme oracle sémantique.

La [contre-revue technique](trust-i6-native-v2-review-2026-11-09.json)
recoupe les décomptes, identités, traces et ressources avec les fichiers bruts.

## 2. Gel, environnement et dénominateurs

Le candidat est gelé le 9 novembre à 20:45:00 UTC. Le plan v2 porte le SHA-256
`8fb1ab32e45d5699ee01d4b3fbf42e28b33af75c63fb5275254683a2041f8b52`.
Ses huit blocs sont exécutés dans l'ordre prévu, avec services, ports, HOME,
bases et sorties isolés. Seuls les binaires et artefacts immuables sont
partagés. L'ordre séquentiel ne garantit pas des caches système froids et
ne constitue pas une étude de latence randomisée.

L'environnement observé est Linux x86-64, Python 3.12.14, neuf processeurs
logiques accessibles et **10 451 427 328 octets de mémoire physique exposée**
(environ 10,45 Go décimaux / 9,73 Gio, soit 9 967 Mio). Il ne représente pas
la recette sur un poste physique de 16 Go. Ollama 0.35.0, Qdrant 1.19.1, E5 small int8 et le
tokenizer sont ceux des artefacts provisionnés et vérifiés.

Le seul générateur est Qwen3-4B Q4_K_M, GGUF SHA-256
`7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.
Chaque appel est relié au manifeste de son bloc, au verrou et au corps
effectivement envoyé. Un événement `received_done=true` lié à une requête
vérifiée est nécessaire pour compter un échange terminé ; une tentative ou
le seul booléen `model_called` ne suffit pas.

Les groupes restent distincts : 18 + 18 positions originales, deux témoins
de sélection par bras, un HTTP historique par bras et un HTTP de sélection
supplémentaire par bras, soit **44 positions observables**. Les délais sont
inchangés : préparation des services 45 s, import modèle 600 s, bloc 1 500 s,
requête 600 s, import documentaire HTTP 180 s. Les protections mémoire et
leurs réserves ne sont pas abaissées.

La [tentative v1](trust-i6-native-api-mode-repair-2026-11-09.md) reste archivée
avec ses 11 réponses, son erreur d'enveloppe API N_I6D35 et six positions non
exécutées. La v2 réutilise ses 23 originaux et six extractions PDF à l'identique ;
seul le mode API N_I6D35 est corrigé pour sa comparaison entre deux sujets
d'un même document. Aucun résultat v1 n'est ajouté à la v2.

## 3. Mesures natives

| Groupe | Réponses / positions | Erreurs | Requêtes 4B terminées | Médiane (s) | p95 (s) |
|---|---:|---:|---:|---:|---:|
| Original — référence | 13/18 | 5 | 5 | 26.881 | 123.502 |
| Original — candidat | 18/18 | 0 | 1 | 0.154 | 73.159 |
| Sélection — référence | 2/2 | 0 | 2 | 43.534 | 55.535 |
| Sélection — candidat | 2/2 | 0 | 2 | 39.488 | 50.092 |
| HTTP historique — référence | 1/1 | 0 | 1 | 65.118 | 65.118 |
| HTTP historique — candidat | 1/1 | 0 | 0 | 0.189 | 0.189 |
| HTTP sélection — référence | 1/1 | 0 | 1 | 63.761 | 63.761 |
| HTTP sélection — candidat | 1/1 | 0 | 1 | 67.216 | 67.216 |

| Groupe | Pic RSS cumulé (Mio) | Pic PSS cumulé (Mio) | Mémoire hôte disponible minimale (Mio) |
|---|---:|---:|---:|
| Original — référence | 4781.88 | 4773.92 | 1542.59 |
| Original — candidat | 3934.61 | 3926.76 | 2426.46 |
| Sélection — référence | 4476.30 | 4468.09 | 2326.40 |
| Sélection — candidat | 4187.59 | 4178.53 | 2504.56 |
| HTTP historique — référence | 3979.64 | 3970.58 | 2961.67 |
| HTTP historique — candidat | 738.89 | 724.46 | 6116.30 |
| HTTP sélection — référence | 3978.29 | 3969.27 | 2925.30 |
| HTTP sélection — candidat | 3975.38 | 3966.49 | 2953.67 |

Les latences sont celles des terminaux observés, erreurs comprises. Le p95
utilise le rang le plus proche ; sur 18 positions, il est égal au maximum.
Les pics RSS/PSS sont les sommes échantillonnées des processus suivis et de
leurs descendants, pas une consommation physique exclusive. Le minimum de
mémoire disponible concerne l'hôte. Le JSON conserve aussi les distributions
des seules réponses `done`, les échantillons et chaque position.

### Référence originale : cinq erreurs conservées

N_I6D42 est annulé pendant la génération lorsque la réserve de l'hôte est
menacée. N_I6D45, N_I6D48, N17 et N18 échouent ensuite à l'admission dans le
budget d'attente prévu : le runtime demande 5 888 Mio disponibles, réserve
incluse. Ces cinq positions ont une réponse vide, aucun delta et aucune
citation publiée ; les sources préparatoires persistées ne valent pas un
rendu documentaire qualifié. Elles restent dans les 18 positions.

### Effet observé de R3

| Cas | Référence : état et temps (s) | Candidat R3 (ms) | Échange 4B candidat |
|---|---|---:|---:|
| N_I6D09 | done, 47.990 | 164.16 | 0 |
| N_I6D11 | done, 27.248 | 159.41 | 0 |
| N_I6D14 | done, 52.845 | 122.22 | 0 |
| N_I6D28 | done, 26.514 | 111.50 | 0 |
| N_I6D32 | done, 46.684 | 112.89 | 0 |
| N_I6D45 | error, 121.618 | 202.16 | 0 |
| N_I6D48 | error, 123.149 | 180.33 | 0 |
| N17 | error, 123.293 | 99.58 | 0 |
| N18 | error, 123.502 | 118.85 | 0 |

Les cinq premiers cas ci-dessus avaient un échange 4B terminé sur la
référence. Les quatre derniers y avaient une erreur mémoire. La seule position
originale du candidat avec un échange 4B terminé, N_I6D42, présente une latence
applicative totale de 73,159 s. Sa réponse annonce une restitution partielle
et ne publie aucune conclusion comparative. Les obligations manquantes —
SV6142B dans A et SV6142 dans B — restent détaillées dans le contrat.
Aucun appel n'est forcé pour atteindre le quota initial.

## 4. Relecture des faits, diagnostics et citations

La revue recoupe les textes complets avec les annotations gelées et les
sources effectivement citées : sujets, propriétés, valeurs, rôles,
conditions, relations admises/rejetées et conclusions comparatives. Les
identités de document/version/génération/révision, empreintes, extraits et
offsets sont examinés ; les deltas sont rapprochés du terminal et du texte
persisté. Les sources retenues mais non citées ne sont pas comptées comme
citations publiées. Une seconde lecture indépendante porte notamment sur
les comparaisons et les réserves.

La revue couvre les 39 réponses publiées et conserve cinq erreurs sans score
documentaire. Elle distingue 31 réponses sans écart observé, deux réserves de
formulation et six échecs d'un critère documentaire gelé. Cette répartition
des 44 positions décrit les observations ; elle ne constitue pas un taux de
justesse généralisable ni un remplacement des dénominateurs par groupe.

Le registre interne des segments rendus n'est pas persisté dans ces captures.
Son empreinte ne permet pas de le reconstruire : aucun contrôle indépendant
de son contenu absent n'est déclaré réussi. La relecture des textes et des
citations disponibles est explicitement bornée à ces éléments.

Les deux réserves publiées concernent N_I6D45 et N_I6D48 : l'introduction
affirme « une même condition » alors que les sources ne donnent aucune
condition d'essai et que les relations ont un champ condition vide. Les
opérandes restent liés aux bons sujets et documents ; les valeurs concurrentes
ne sont pas arbitrées. La réserve porte sur le diagnostic ajouté, pas sur
une valeur numérique substituée. La formulation provient de
`services/api/answer_contract.py`, fonction de diagnostic du conflit.

Deux imprécisions distinctes existent dans les métadonnées de relations
rejetées : D28 attribue `property=output` à la tension nominale, tandis que
ce qualificatif concerne le courant coordonné ; D32 attribue `role=nominal`
au courant de sortie, tandis que ce rôle concerne la tension précédente.
Ces relations restent rejetées pour négation et aucune relation n'est admise.
La revue n'établit pas la cause exacte dans le parseur ; ces pistes ne sont
pas assimilées à un faux appui publié.

Les quatre réponses des témoins directs de sélection conservent les plages
de bus et leurs citations : RX742, 1 V à 26 V ; KX563, 2 V à 27 V. Elles
n'inventent aucune plage d'alimentation. Elles échouent néanmoins au critère
gelé qui exige de nommer la propriété manquante dans la réponse : le texte
évoque seulement « certaines propriétés », sans préciser alimentation ou
`supply`. Le contrat technique détaille le manque, ce qui ne satisfait pas
son explicitation dans le texte. Les quatre échecs restent au dénominateur.

Les deux parcours HTTP de sélection présentent le même échec documentaire
sur HX864 : la plage de bus 3 V à 29 V est citée, mais la plage d'alimentation
manquante n'est pas explicitement nommée. Les réussites du modèle, du flux et
des versions ne remplacent pas ce critère. Au total, les suppléments portent
six réponses avec ce défaut d'explicitation, réparties entre leurs groupes.


## 5. HTTP/SSE, persistance et arrêts

| Parcours | Publication historique | Persistance des versions | Échange 4B terminé | Verdict opérationnel enregistré |
|---|---:|---:|---:|---|
| HTTP01 référence | 9/9 contrôles | 7/7 contrôles | 1 | PASS |
| HTTP01 candidat | 7/9 contrôles | 7/7 contrôles | 0 | FAIL, code de sortie 1 |
| HTTP sélection référence | 9/9 contrôles | 7/7 contrôles | 1 | PASS |
| HTTP sélection candidat | 9/9 contrôles | 7/7 contrôles | 1 | PASS |

HTTP01 conserve les deux tensions AX71, 2.8 V et 3.2 V à 70 °C, avec leurs
citations et sans arbitrage. Après remplacement du document A par une version
à 3.0 V, les citations de l'ancienne réponse restent identiques et attachées
aux versions initiales. Dans le parcours supplémentaire, la citation A/S001
de HX864 conserve 3 V à 29 V après remplacement par 4 V à 31 V. La comparaison
indépendante des snapshots de citations avant/après confirme cette stabilité.

Le contrôle `old_query_unchanged` est vrai dans les quatre reçus du harnais ;
le snapshot complet de la requête après remplacement n'est pas conservé.
Cette observation enregistrée n'est pas présentée comme une seconde relecture
indépendante de ce snapshot absent.

Le FAIL HTTP01 candidat provient exactement de `actual_model_exchange=false`
et `locked_4b_identity_observed=false`. Le modèle n'est pas appelé sur cette
route R3 ; il ne s'agit pas d'une identité 4B différente observée. Les sept
autres contrôles de publication passent, mais les deux attentes historiques
et le verdict global ne sont pas modifiés après l'exécution. Ce cas a une
latence applicative de 188,57 ms, contre 65 118,09 ms pour la référence.

Les quatre parcours vérifient la reprise vide après le dernier événement,
trois lancements de workers d'ingestion natifs par parcours et aucun runner
injecté. Leurs contrôles opérationnels ne constituent pas des verdicts
documentaires : les deux HTTP de sélection gardent l'échec d'explicitation
décrit au §4 malgré leurs PASS de transport et de versions.


Les huit blocs confirment l'arrêt de tous leurs groupes de processus
possédés, l'absence de changement des sources gelées et l'intégrité du GGUF
partagé. Les quatre serveurs API HTTP s'arrêtent proprement et ferment leur
listener. Aucun bloc n'atteint son délai maximal, aucun résultat n'est rejoué
pour améliorer son verdict. Le code de sortie 1 du HTTP historique candidat
reste conservé avec la raison de ses deux contrôles négatifs.

## 6. Preuves logicielles déjà publiées

Le [lot R3](trust-i6-r3-2026-11-09.md) a passé **5 397 tests portables**, avec
25 ignorés et 48 exclus par les marqueurs prévus, puis Ruff et Mypy sur
155 fichiers. Ses premières six erreurs de garde sur les liaisons de listes
sont conservées, avec les corrections et deux reproductions supplémentaires.
Le [correctif de recette API](trust-i6-native-api-mode-repair-2026-11-09.md)
ajoute trois contrôles et passe 106 tests ciblés ; il ne change pas les
services produit qualifiés par la suite complète.

Sur DEV48, les trois bras séquentiels passent 48/48 cas, 24/24 positifs,
sans faux appui complet sur les 24 négatifs, avec 69/69 littéraux et citations.
Le p95 du contrat passe de 119,13 ms pour R1b à 70,88 ms pour le candidat
(−40,50 %), sous le seuil inchangé de 250 ms. Les 144 comparaisons par
référence ne montrent aucune différence de résultat. Ces mesures du contrat
emploient les doubles déclarés ; elles ne sont pas des latences natives.

Les lots de portée `d65ae09`, R3 `26a0eb8` et recette `6394f62` sont publiés.
Le [reçu de publication de la recette](trust-i6-native-api-mode-publication-2026-11-09.json)
vérifie son arbre et son parent, comme les reçus des deux lots précédents.
Le bilan courant ne modifie pas le candidat produit exécuté.

## 7. Critères I6 et suites bornées

| Critère | État à cette livraison | Preuve et limite |
|---|---|---|
| I6R-D01 | Acquis sur DEV et opérandes natifs examinés ; final non évalué | DEV : zéro faux appui complet sur 24 négatifs. Aucun opérande interdit publié dans les cas natifs examinés ; diagnostics textuels réservés séparément. |
| I6R-D02 | Couverture acquise sur le périmètre disponible ; final non évalué | DEV : 24/24 positifs. Les positifs natifs conservent leurs faits ; le manque de propriété n'est pas assez explicite sur les suppléments. |
| I6R-D03 | NON ACQUIS dans toute sa portée textuelle | 69/69 littéraux/citations DEV, 29/29 candidat original. Deux diagnostics de condition et les propriétés manquantes empêchent la conformité documentaire intégrale ; ledger rendu non persisté. |
| I6R-D04 | PASS logiciel | 5 397 tests portables du produit, puis 106 ciblés de recette, Ruff et Mypy155 ; aucune modification des services pendant/après les blocs. |
| I6R-D05 | BLOQUÉ | Le FINAL48 historique manque ; aucun score ou nouvelle annotation ne lui est substitué. |
| I6R-D06 | NON ACQUIS selon le protocole initial | 18 positions par bras exécutées, mais cinq erreurs référence et un seul échange 4B candidat original. HTTP historique candidat conserve son FAIL ; suppléments séparés. |
| I6R-D07 | Contrat et route R3 acquis ; ressources natives rapportées | p95 contrat 70,88 ms <250 ms ; neuf cas R3 sans modèle ; plafonds inchangés. Pas de qualification d'un poste physique de 16 Go. |
| I6R-D08 | Trois lots publiés vérifiés ; bilan prêt à publication | Reçus des arbres/parents liés ; contrôles documentaires puis publication sans force avec contrôle de tête attendue. Confirmation du présent commit dans le compte rendu de livraison. |

Le FINAL48 historique reste introuvable. Son SHA-256 gelé
`cfd02c4646cb23be05dd7fb912a265cceb72dc15d6038f47746f53f61ac9e797`
est conservé ; aucune reconstruction, ouverture ou note de final n'est
attribuée à cette campagne. Une nouvelle annotation ne serait pas ce jeu
historique et demanderait un protocole distinct avant exécution.

Les prochains correctifs documentaires doivent rendre explicites les
propriétés manquantes et éviter d'affirmer une condition absente. Les deux
pistes de métadonnées rejetées demandent des reproductions discriminantes.
Le présent bilan reste attaché au candidat figé, avec ses défauts et ses
dénominateurs ; aucune correction ultérieure ne pourra le reclasser.

Les qualifications métier sur corpus réel, OCR, installation neuve, Windows,
aarch64 et poste physique restent hors du résultat acquis ici. Les preuves
synthétiques ne les remplacent pas.

## 8. Reproduction et conservation

Le plan, le lanceur, les recettes, les entrées, les manifestes, les sources
synthétiques et les traces utiles sont archivés avec leur contenu exact et
leurs empreintes. Les bases, HOME, clés, poids et journaux privés `.log`
restent hors de l'archive publiée. Les flux sélectionnés, ainsi que les
membres des conteneurs ZIP inclus, sont contrôlés avant publication.

L'archive comprend **427 fichiers sélectionnés**, soit 6 586 601 octets
compressés. Leur décompression et leurs tailles/empreintes individuelles
sont vérifiées. Les huit absences de l'inventaire sont uniquement les fichiers
conditionnels `block-failure.json` : aucune exception de harnais n'en a créé.
Les cinq erreurs applicatives et le verdict HTTP négatif sont présents dans
leurs résultats et traces. Le [reçu de livraison](trust-i6-native-v2-validation-2026-11-09.json)
consigne cette vérification et les contrôles documentaires du bilan.

Une nouvelle exécution doit utiliser des sorties distinctes. Les identifiants
des huit blocs, budgets, étapes et empreintes figurent dans le plan archivé.
Le script d'inventaire technique est joint aux preuves ; il ne reconstruit
pas un oracle ni un registre rendu absent. Les commandes documentaires du
bilan sont :

```sh
.venv/bin/python RAG_Local_Agents/tools/build_brief.py
.venv/bin/python RAG_Local_Agents/tools/build_brief.py --check
.venv/bin/python tools/docs/check_docs.py
.venv/bin/python RAG_Local_Agents/tools/verify_pack.py
git diff --check
```
