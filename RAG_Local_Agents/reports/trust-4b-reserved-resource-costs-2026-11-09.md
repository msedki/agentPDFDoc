# I5 — ressources du réservé et arrêt de qualification

**Rôle :** coûts effectivement observés et limites de mesure. **Propriétaire :** qualification.
**État :** campagne réservée arrêtée par décision de root le 9 novembre 2026 à
04:40:02 UTC ; version d’ingénierie non qualifiée pour la production. Les preuves
historiques sont conservées. Ce rapport ne transforme ni les extractions partielles,
ni des états techniques, en réussite documentaire.

## Portée et résultat de la campagne

La référence reste le commit `41857e17a438fe43123e4ef8274d9d2d446bfbc2`.
Le candidat est l’instantané 8 de 172 fichiers, reçu
`1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b`.
Le gel final source/runtime v3 a été écrit à **04:05:09.595970 UTC**, avant
l’ouverture des questions et oracles. Le premier lot d’extraction candidate
avait commencé à **04:13:46.913634 UTC**. D01 et D02 ont chacun leur reçu de
worker terminé ; D03 n’a pas de reçu terminal. Le lot entier n’a produit ni
manifeste final `inputs.json`, ni reçu de fin d’action ou de dispatcher.

La [revue réservée](trust-4b-reserved-review-2026-11-09.md) conserve les
24 positions : **12 `NOT_RUN` en référence et 12 `BLOCKED` en candidat**,
aucune requête observée, aucun score documentaire. Chaque bras garde ses
8 positifs et 2 limites originaux, plus 2 dérivés positifs distincts.
Il n’existe donc aucune durée d’indexation, de génération ou de requête
réservée, aucun intervalle modèle ni pic mémoire de requête à comparer.
Le parcours HTTP/SSE v4 reste **non exécuté, bloqué** par la même absence de
preuve d’arrêt de l’ancien groupe.

## Workers clos : observations par document

Une ligne représente un worker terminé une fois. Les cinq lignes de référence
proviennent des extractions historiques complètes que le plan final réutilisait.
Elles ne constituent pas cinq nouvelles exécutions pendant cette campagne.
Les deux lignes candidates proviennent du lot final interrompu. Pour ces sept
workers seulement, les reçus indiquent retour 0, absence de timeout, chef réapé
et groupe vide ; leur état d’extraction est `ready_partial`.

| Bras | Document | Durée supervisée (s) | RSS cumulée, pic observé (Mio) | PSS cumulée, pic observé (Mio) | Minimum disponible hôte (Mio) | Échantillons |
|---|---|---:|---:|---:|---:|---:|
| Référence historique | D01 | 108.60 | 1930.45 | 1761.01 | 4424.13 | 210 |
| Référence historique | D02 | 119.60 | 1632.61 | 1627.16 | 4486.55 | 229 |
| Référence historique | D03 | 269.73 | 2024.93 | 1860.56 | 4262.92 | 512 |
| Référence historique | SCAN1 | 41.73 | 1264.64 | 1257.07 | 4913.61 | 81 |
| Référence historique | MIXED1 | 41.18 | 1259.68 | 1252.10 | 4843.34 | 79 |
| Candidat final 8 | D01 | 262.53 | 2031.53 | 1860.98 | 6412.16 | 493 |
| Candidat final 8 | D02 | 236.21 | 2069.86 | 1899.58 | 6472.32 | 439 |

`ready_partial` reste analysable avec ses limites après écriture d’un manifeste
final valide et clôture propre du lot. Ce statut n’établit pas une réponse utile,
une couverture complète ou une réussite documentaire. Le blocage actuel vient
du lot non achevé proprement, du manifeste final absent et de l’arrêt global
non vérifié ; il ne provient pas du seul mot `ready_partial`.

| Position candidate restante | Observation préservée | Durée et mémoire terminales |
|---|---|---|
| D03 original | Checkpoints 0–3, 4–7, 8–11 ; dernier événement `page_load` pour [13,13] | Non disponibles : aucun reçu terminal |
| SCAN1 dérivé | Action d’extraction non commencée | Non mesurées |
| MIXED1 dérivé | Action d’extraction non commencée | Non mesurées |

Aucun total de durée du lot candidat n’est calculé : additionner D01 et D02
occulterait le coût incomplet de D03. Un temps manquant n’est pas un temps nul.
Les horodatages de fichiers partiels de D03 ne permettent pas de reconstituer
sa durée complète, son sommet mémoire ou sa cause d’arrêt.

## Ce que mesurent les compteurs

Le [préparateur versionné](../../tools/qualification/prepare_trust_i5.py)
mesure la durée monotone à partir d’avant le lancement du worker jusqu’après
son arrêt et la fermeture du groupe. La validation du résultat et la sérialisation
finale du manifeste ont lieu ensuite ; la colonne de durée n’est donc pas le
temps complet de préparation du lot.

La boucle attend nominalement 0,5 seconde entre les observations, auxquelles
s’ajoute le coût de lecture des processus. Elle additionne la mémoire du worker
et des descendants observés. La RSS peut compter plusieurs fois des pages
partagées. La PSS est additionnée lorsqu’elle est disponible : une propriété
absente vaut 0 dans ce harnais et une erreur `psutil` fait ignorer le membre
concerné. Le reçu ne démontre pas une couverture exhaustive de tous les membres
à chaque instant. Les maxima RSS et PSS sont calculés séparément et ne sont
pas nécessairement simultanés. **1 Mio = 1 048 576 octets.**

Le minimum de mémoire disponible concerne l’hôte entier, pas seulement le
worker. Ces valeurs sont des observations échantillonnées ; elles ne démontrent
ni le vrai pic instantané, ni une exigence mémoire minimale, ni une qualification
sur machine 16 Go. Les extractions de référence et candidates ont eu lieu à des
moments et avec des disponibilités hôte différentes. Les caches ne sont pas
contrôlés entre elles. Les durées D01/D02 observées ne suffisent pas à attribuer
un changement causal de performance au produit. Aucun ratio global de vitesse
n’est tiré de ce lot incomplet.

## Matérialisation effectivement vérifiée

Après le gel final, les trois manifestes manquants ont été copiés exactement
dans l’arbre de livraison, puis une matérialisation locale a vérifié les quatre
manifestes et trois originaux et a régénéré les deux paires PDF/PNG. Elle porte
`materialized_verified`, `frozen_inputs_verified=true` et
`source_inputs_unchanged=true`. Les versions de rendu étaient Pillow 12.3.0,
pypdfium2 5.13.0 et reportlab 5.0.1. Le mode réseau n’a pas été exercé.

Ce résultat est **PASS pour la matérialisation des entrées seulement**. Aucun
worker d’ingestion, OCR ou modèle de réponse n’est lancé par cet outil.
Aucune mesure de mémoire de cette commande n’est inventée ici. Le plan lié
conserve les chemins d’entrée originaux dont les octets ont été comparés à la
sortie matérialisée. La publication Git des manifestes est une étape distincte.

## Rupture de continuité et décision d’arrêt

Le dernier journal de cycle de vie D03 a été écrit à **04:26:26.493150 UTC**.
Lors d’un poll borné par les deux observations **04:32:50–04:33:08 UTC**, le
service d’exécution a répondu `Unknown process id` pour la session 29763.
Les invocations suivantes ne voyaient que leur propre petit espace de processus.
Un verrou disponible et des ports libres dans ce nouveau contexte n’ont pas
été utilisés pour prétendre que l’ancien groupe était arrêté.

La contre-revue indépendante a confirmé les 24 identités, l’absence de fichiers
de requête, l’intégrité des 172 sources ROOT/candidat et des 549 entrées de portes.
Elle n’a pas lancé de moteur ou sondé des processus. Root a ratifié l’arrêt :
**aucune relance, suppression, récupération forcée de verrou ou ouverture HTTP**.
La cause demeure inconnue ; aucun OOM, timeout ou défaut produit n’est déduit
de la perte du handle. Les reçus D01/D02 ne prouvent pas l’arrêt global de D03
ou de son superviseur.

Une future mesure exige un cycle de vie et un arrêt vérifiables, des sorties
nouvelles et la conservation de cette tentative interrompue. Elle ne remplace
pas rétroactivement les 24 positions de ce plan. Aucun code produit, test,
critère, oracle ou plafond n’a été changé après le gel pour traiter cet incident.

## Preuves et disponibilité

Les données détaillées de cette observation sont conservées localement sous
`.runtime/qa/production-i5-20261108/` ; elles ne sont pas présentées comme des
artefacts versionnés. La [validation publique](trust-4b-validation-2026-11-08.json)
et les tableaux ci-dessus exposent leurs résultats et limites sans nécessiter
une lecture de bases actives.

| Preuve locale | SHA-256 |
|---|---|
| `reserved-closed-extraction-resource-observations-r01.json` | `136367cdb4ccaf105d1bade60d1b0f1e26e918ee4b8a66c5f53bb9e3108edcc7` |
| `heldout-baseline-extraction/preparation-receipt.json` | `aab9826927e36f7898cd22f630e9f222cf0a4e2e1d29aced98d6ea656b5cca8e` |
| `heldout-baseline-ocr-extraction/preparation-receipt.json` | `42171f6d3f6f51a05941f17b45dcdafd7efcc085424bbf8a59160381bb2827a8` |
| `final-reserved-technical-observations-v3.json` | `c3455cdca7cefc0a23e664c4936dff14023fe7082e176eb87862a3f3ba398a05` |
| `final-reserved-model-attempts-v3.json` | `eec400c06cfdf734a3e3ae3719b6a939d1cf7f141328ad8cfe209f8619682a06` |
| `materialization-final-v3-verification.json` | `72881ad5c49ad30bddca8fe94e6c4cee4aae55b302eb34bad8b80665c143e5eb` |
| `reserved-dispatch-session-continuity-incident-r01.json` | `e8a425089ce9f0a01baf93be893a3cf2153188ae50930e0779a099dc172be2a2` |
| `reserved-dispatch-session-continuity-incident-r02.json` | `3e9036a40ef8503238ef9543aa71e7647765fc2cd6d1daf86417c7d5d593cb05` |
| `ingestion-reserved-continuity-review-r01.json` | `b81c89c926e3037e7c13ac83c56e31f2eff32228919391df1a5708543eaa134f` |
| `root-reserved-stop-disposition-r01.json` | `7af3f487d920f9861965fd3542a0c786d10476af051725018c2df9ce5abad07c` |

Le collecteur technique compte 24 positions non observées. Son compteur
`model_called_cases=0` compte seulement les valeurs vraies présentes ; les
24 mesures sont absentes. Le complément des traces renvoie donc 24 valeurs
inconnues pour les demandes et réponses modèle. Ces absences ne deviennent
ni une route déterministe démontrée, ni un coût nul, ni un PASS documentaire.
