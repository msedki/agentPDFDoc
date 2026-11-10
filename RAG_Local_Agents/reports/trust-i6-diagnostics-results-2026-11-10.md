# I6R-06 — diagnostics, relations locales et preuve du rendu

**Rôle :** bilan du complément et critères DIAG-01 à DIAG-08.
**Propriétaire :** intégration et qualification RAG.
**Statut :** livré avec un écart préexistant au final ; qualification globale non acquise.
**Date :** 10 novembre 2026 (UTC).
**Référence :** `0574f4e21ccaf95b25a48c6e226369376681ac18`.
**Candidat mesuré :** `522d86839d5c803c57daec0e799bfa48ee5aa8e7`.

## Résultat et comportement livré

Les diagnostics de conflit n'affirment plus une condition commune absente
des sources. Les propriétés demandées mais non établies sont nommées depuis
les obligations du contrat, avec une portée limitée aux passages retenus.
Les qualificatifs de chaque mesure restent locaux à son prédicat, sans
supprimer la négation dominante, les conditions ou la citation intégrale.
La trace privée conserve désormais le registre effectivement rendu après
validation, lié au texte et au catalogue par leurs empreintes.

Le nouveau final indépendant passe de **39/48 à 47/48**. Les huit progrès
couvrent six diagnostics et deux métadonnées ; aucun cas conforme de la
référence ne régresse. Les **68/68 littéraux et citations attendus** restent
présents dans les deux bras. Un écart préexistant demeure : une question
sur la tension d'entrée admet aussi une relation de sortie imprimée dans
la même citation. Ce résultat reste définitivement celui d'I6 ; un nouveau
[lot I7](trust-i7-property-protocol-2026-11-10.md) le traite séparément.

Les [preuves archivées](trust-i6-diagnostics-evidence-2026-11-10.json.gz),
leur [inventaire](trust-i6-diagnostics-collection-2026-11-10.json), le
[final détaillé](trust-i6-diagnostics-final-2026-11-10.md) et la
[revue native](trust-i6-diagnostics-documentary-2026-11-10.json) distinguent
contrat, transport, fidélité documentaire et exécution réelle du modèle.
Le [protocole préalable](trust-i6-diagnostics-protocol-2026-11-09.md)
et les résultats natifs historiques restent inchangés.

## Vérifications logicielles

| Contrôle | Résultat et portée |
|---|---|
| Nouvelles régressions | 80 tests : 28 diagnostics, 41 qualificatifs locaux et 11 trace du rendu |
| Dernière série ciblée | 152 PASS ; elle recouvre les nouveaux tests, sans addition des dénominateurs |
| Suite portable finale | 5 480 PASS, 25 SKIP, 48 exclus par marqueurs ; 322,26 s |
| Ruff | PASS |
| Mypy | PASS, 155 fichiers |
| Sources avant/après la suite | Identiques, manifeste complet conservé |
| Revue séparée | Portée lexicale, capture et distinction validation/publication relues ; auteur des diagnostics déclaré comme tel |

La suite portable exclut `integration`, `acceptance` et `slow` ; elle ne
constitue pas une recette native. Elle commence le 9 novembre à 23:58:53 UTC
et termine le 10 novembre à 00:04:20 UTC. La première suite limitée aux
unités, avec 5 390 succès, un échec et 22 ignorés, reste archivée : l'échec
portait sur l'ancienne formule du diagnostic. L'assertion a été alignée sur
la formulation demandée et renforcée par le maintien des citations et
l'absence d'arbitrage, avant le gel et l'ouverture du final.

La capture `answer.rendered_support_ledger` respecte les modes `full`,
`hashes`, `off` et les quotas existants. Son contenu n'est pas ajouté au SSE
public. Un registre validé atteste le rendu capturé ; son existence seule
n'atteste pas sa publication. Le terminal confirmé et le texte persisté
sont contrôlés séparément dans les essais natifs.

## Nouveau jeu indépendant I6R06-F48

Le jeu est gelé le 9 novembre à 23:47:21 UTC, avant l'exécution du candidat
publié. Son SHA-256 est
`6f6210d4ce376bee739fbacd45c0de1e3c3a691aac2ca49386dc28fcc2f58412`.
Il contient 24 positifs et 24 limites/négatifs, 24 cas français et 24 anglais.
Il ne reconstitue pas le FINAL48 historique introuvable, auquel aucun score
n'est attribué.

| Mesure contractuelle | Référence | Candidat |
|---|---:|---:|
| Conformité stricte | 39/48 | 47/48 |
| Positifs stricts | 23/24 | 23/24 |
| Limites/négatifs stricts | 16/24 | 24/24 |
| Faux appuis complets sur les négatifs | 0/24 | 0/24 |
| Cas avec opérande interdit ou conclusion comparative interdite | 0/48 | 0/48 |
| Cas avec relation admise supplémentaire non annotée | 1/48 | 1/48 |
| Littéraux requis et citations locales | 68/68 | 68/68 |
| Registres rendus et empreintes | 48/48 | 48/48 |
| p95 contractuel descriptif | 75,73 ms | 69,35 ms |

F05 restitue correctement l'entrée de MT9205 à 5,83 V et le passage entier,
mais admet aussi la sortie maximale à 11,92 V parmi les relations demandées.
Cette seconde valeur est présente dans la source : l'échec fermé de
pertinence ne doit pas être décrit comme une hallucination ou une entrée
incorrecte. Aucun code, annotation ou seuil d'I6 n'a été modifié après
l'ouverture du final.

Le DEV16 distinct passe de 10/16 à 16/16 avec 24/24 littéraux/citations.
Son rejeu sur le commit publié confirme 16/16 ; les répétitions ne sont pas
additionnées. Le catalogue et le rendu sont applicatifs ; la sélection de
toutes les références autorisées et le compteur de caractères sont des
doubles déclarés. Aucun modèle, embedding ou OCR n'est exécuté par ce banc.
Chaque cas final n'est mesuré qu'une fois par bras, avec tracemalloc : les
latences sont descriptives et ne constituent pas un gain causal démontré.

## Recette native R4

Les huit blocs terminent leurs **20/20 positions techniques**. Les dix
réponses candidat passent aussi la relecture documentaire stricte, contre
trois sur dix pour la référence. Les **18/18 littéraux cités** et les
**16/16 relations affirmées exactes** de chaque bras sont conservés. Les
sept écarts corrigés sont cinq diagnostics et deux métadonnées de relations
rejetées ; aucun opérande nié n'est promu et aucune conclusion comparative
interdite n'est publiée.

| Groupe | Strict documentaire référence | Strict documentaire candidat | Échanges 4B terminés par bras |
|---|---:|---:|---:|
| Six questions originales | 2/6 | 6/6 | 0 / 0 |
| Deux sélections directes | 0/2 | 2/2 | 2 / 2 |
| HTTP conflit | 1/1 | 1/1 | 0 / 0 |
| HTTP sélection | 0/1 | 1/1 | 1 / 1 |

Les six échanges réellement terminés utilisent le 4B verrouillé. Les dix
registres rendus candidat sont recalculés et rapprochés des terminaux et
textes publiés. L'absence historique de ce registre côté référence est
documentée sans lui inventer un contenu. Les quatre parcours HTTP vérifient
aussi que les anciennes citations et réponses survivent au remplacement
des documents.

Les sélections directes prennent 45,07/25,40 s en référence et 44,97/79,24 s
sur le candidat. La politique mémoire a déchargé le modèle après la première
sélection candidat, puis l'a rechargé pour la seconde. Cette différence de
contexte et une seule répétition empêchent d'en déduire une régression ou un
gain causal. Les pics agrégés maximums par bras sont 4 047,6/3 967,1 Mio RSS.
Les mesures par bloc, PSS, disponibilité et routes sont dans le
[bilan technique](trust-i6-diagnostics-native-2026-11-10.md) et son
[JSON complet](trust-i6-diagnostics-native-2026-11-10.json). La
[relecture documentaire détaillée](trust-i6-diagnostics-documentary-2026-11-10.md)
conserve les motivations de chaque jugement.


Le plan est gelé avant lancement, SHA-256
`61d207b8a2c019e1568be2c33b401343c55bf2a8296c0460cca722d0e7441e4e`.
Le candidat est figé le 10 novembre à 00:04:57 UTC ; ses 142 fichiers
services/outils et 55 artefacts du runtime sont vérifiés. Les blocs utilisent
Ollama 0.35.0, Qdrant 1.19.1, E5 small int8 et exclusivement Qwen3-4B Q4_K_M,
GGUF `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.
Le manifeste, le verrou et le corps de la requête sont reliés à chaque
échange effectivement terminé ; une simple tentative ne compte pas.

Les positions sont des régressions connues, distinctes du final : six
questions originales, deux sélections et deux parcours HTTP par bras.
Les 23 documents originaux sont indexés pour les six premières questions.
Les extractions réutilisées et les sources sont vérifiées par empreinte.
Ports, HOME, bases et sorties sont isolés ; seuls les artefacts immuables
sont partagés. Les services possédés sont arrêtés avant le bloc suivant.
Il n'y a pas de reprise favorable ni de modification des preuves brutes.

L'ancien évaluateur HTTP exigeait un échange modèle même sur la route de
conflit déterministe. Ses deux FAIL restent conservés, sans réécriture.
Le protocole R4, défini avant exécution, évalue séparément cette route sans
modèle et la route de sélection avec un vrai échange 4B. La fidélité du
texte est relue indépendamment des statuts techniques.

## Critères et limites

| Critère | État observé |
|---|---|
| DIAG-01 — diagnostics | Conforme sur les cas annotés ; six diagnostics contractuels et cinq diagnostics natifs ciblés corrigés |
| DIAG-02 — qualificatifs locaux | Conforme sur les reproductions, nouveau final et deux rejets natifs ciblés ; négations et passages conservés |
| DIAG-03 — appui et citations | Aucun nouveau faux appui, opérande ou conclusion interdite ; littéraux/citations conservés ; relation supplémentaire préexistante F05 explicitement réservée |
| DIAG-04 — registre rendu | Contrôles de confidentialité et refus logiciels conformes ; dix registres natifs candidat et leur publication vérifiés |
| DIAG-05 — logiciel | Suite portable, ciblés, Ruff et Mypy conformes dans leur périmètre |
| DIAG-06 — nouveau final | Exécuté et figé à 47/48 ; écart strict F05 conservé, qualification générale non déduite |
| DIAG-07 — natif et HTTP | 20/20 critères techniques R4, 10/10 documentaires candidat, six échanges 4B et huit arrêts ; verdicts HTTP historiques séparés |
| DIAG-08 — traçabilité et publication | Code `522d868` publié et relu à distance ; le commit documentaire contenant ce bilan conserve les preuves et actualise le suivi |


La nouvelle campagne clôt le complément de diagnostics avec ses résultats
observés et laisse F05 au lot I7. Elle ne reclasse pas les campagnes I5,
I5-PJ ou I6 v1/v2, leurs quotas non atteints, leurs erreurs mémoire, leurs
échecs de diagnostic ou leur jeu historique manquant.

Les annotations sont synthétiques et réalisées par un agent distinct des
auteurs du produit, sans validation humaine ni corpus métier. L'hôte est
Linux x86-64 et ne constitue pas le poste physique de 16 Go de la recette.
Windows, aarch64, installation neuve, fidélité générale des tableaux et OCR
et qualification de diffusion restent ouverts dans la DoD.

## Reproduction et publication

Le [reçu de livraison documentaire](trust-i6-diagnostics-delivery-2026-11-10.json)
conserve les 62 tests documentaires réussis, les contrôles de liens, pack,
brief et schémas, ainsi que la relecture de cohérence et l'inspection de
l'export. Ces vérifications de documentation ne sont pas ajoutées aux
résultats natifs ou au score final.


Le [reçu du code](trust-i6-diagnostics-code-publication-2026-11-10.json)
atteste parent, arbre et tête distante de `522d868`, publiés sans force sur
`enhanced_version`. Le commit local d'identité projet est conservé ; le
connecteur GitHub publie avec les métadonnées du compte connecté, comme
documenté dans les livraisons précédentes.

L'archive à liste blanche conserve les jeux, gels, évaluateurs, commandes,
sorties, traces synthétiques, revues et reçus d'arrêt. Elle n'inclut ni poids,
base, HOME, jeton ni journal de service privé. Ses chemins d'exécution sont
ceux de cette session ; une reproduction doit fournir les mêmes artefacts
vérifiés dans des racines neuves, sans écraser une exécution conservée.

Commandes réellement utilisées sur le candidat :

```sh
PYTHONPATH=. /workspace/scratch/2967c8ebdcb2/agentPDFDoc/.venv/bin/python -m pytest tests -m 'not integration and not acceptance and not slow' -q --basetemp=/workspace/scratch/edbeb2c37c03/qa/portable-r2-tmp --junitxml=/workspace/scratch/edbeb2c37c03/qa/portable-r2.xml
/workspace/scratch/2967c8ebdcb2/agentPDFDoc/.venv/bin/python -m ruff check .
/workspace/scratch/2967c8ebdcb2/agentPDFDoc/.venv/bin/python -m mypy
```

Le plan R4 et les scripts archivés définissent chaque `--step` de
`launch_step.py`, suivi de `review_step.py`. Le final utilise
`run_i6r06.py` et les identités enregistrées dans ses reçus. Le suivi vivant
reste [PLAN.md](../PLAN.md), avec journal du 10 novembre et contrôles
documentaires distincts des preuves d'exécution.
