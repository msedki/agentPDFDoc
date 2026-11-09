# I5 — ressources du suivi de développement 7

**Rôle :** relevé technique des actions fermées, sans jugement documentaire.
**Propriétaire :** qualification. **Date :** 9 novembre 2026 UTC.
**Périmètre courant :** référence phase 5 (20 cas), candidat phase 7
(20 cas fermés), avec réemploi des extractions complètes 6.
Les vingt positions candidates prévues sont observées ; tous leurs blocs sont fermés.
La baseline 5 est réutilisée comme observation historique ; elle n’a pas été relancée.
Les résultats du candidat 6 restent dans leur rapport distinct. Le réservé reste fermé.

## Origine et limites des mesures

Le relevé `.runtime/qa/production-i5-20261108/development-phase7-closed-resources-4.json` porte le SHA-256
`685eaf3827cef04c03d686db0495a5c890019942c70688d4ca3f16fde25aa827`. Il conserve une seule observation
par couple bras/cas, les hashes des mesures et traces, les reçus de fin et les
intervalles tirés des horodatages existants. Il ne lance ni moteur, ni test,
ni nouveau relevé de mémoire. Les versions précédentes sont conservées ; leurs
observations communes ne sont pas de nouvelles tentatives à additionner.

La durée de requête est `elapsed_ms` divisée par 1 000. RSS et PSS sont les
sommets échantillonnés de la somme application, services explicitement possédés
et descendants. RSS peut compter plusieurs fois des pages partagées ; PSS
n'est renseigné que lorsque tous les processus échantillonnés le fournissent.
Le minimum disponible concerne séparément tout l’hôte. Le pas nominal est
0,5 seconde, auquel s’ajoutent le coût du relevé et un relevé explicite de fin
de cas. Ces valeurs ne sont pas des pics continus garantis. Une requête très
courte peut ne comporter qu’un ou deux relevés. La mémoire d’un cas inclut
l’état des services déjà chargés ; elle n'est pas son allocation incrémentale.

Une phase `llm.request` prouve une tentative enregistrée avant le transport ;
elle ne prouve pas l'acceptation par le serveur. Une réponse reçue exige du
contenu modèle non vide ou un événement natif de fin dans la trace vérifiée.
La seule phase `llm.response`, écrite aussi dans `finally`, ne suffit pas.
Les champs absents restent inconnus. Les états techniques et routes ne sont
jamais transformés en PASS documentaire.

Les sous-ensembles ci-dessous ont des nombres de cas et des routes différents.
Aucun gain causal, équivalence de cache froid, coût énergétique/financier,
capacité de plateforme ou qualification sur 16 Go n’en est déduit.

## Requêtes : une ligne par cas et par bras

Les mémoires sont exprimées en **Mio** ; les durées en secondes. « Demande »
et « Réponse » décrivent les phases vérifiées du modèle, pas les seuls métriques.
La mémoire de chaque ligne vient du fichier terminal de ce cas.

### Référence — phase 5

| Cas | État / erreur | Route | Durée (s) | Demande / réponse | RSS / PSS (Mio) | Disponible min (Mio) | Relevés |
|---|---|---|---:|---|---:|---:|---:|
| H01 | done | Génération 4B | 261.092 | Oui / Oui | 4147.4 / 4138.1 | 3620.1 | 464 |
| H02 | done | Génération 4B | 48.301 | Oui / Oui | 4325.0 / 4315.7 | 3798.3 | 86 |
| H03 | done | Génération 4B | 88.955 | Oui / Oui | 4325.5 / 4316.2 | 3848.1 | 160 |
| H04 | done | Génération 4B | 152.481 | Oui / Oui | 4410.0 / 4400.7 | 3715.9 | 274 |
| H05 | done | Génération 4B | 122.912 | Oui / Oui | 4205.4 / 4195.8 | 4019.8 | 227 |
| H06 | error / ollama_timeout | Génération 4B | 302.781 | Oui / Non | 4386.5 / 4376.9 | 3644.1 | 541 |
| H07 | done | Génération 4B | 174.771 | Oui / Oui | 4371.3 / 4362.1 | 3752.7 | 323 |
| H08 | done | Génération 4B | 221.173 | Oui / Oui | 4394.2 / 4385.1 | 3669.8 | 399 |
| SCAN1_H04 | done | Génération 4B | 170.646 | Oui / Oui | 4049.4 / 4039.8 | 4104.6 | 309 |
| SCAN2_H07 | done | Génération 4B | 190.042 | Oui / Oui | 4262.2 / 4252.5 | 3862.8 | 343 |
| N_ina226 | done | Génération 4B | 241.416 | Oui / Oui | 4214.5 / 4205.2 | 3703.2 | 432 |
| N_tmp117 | done | Contrat de preuve | 2.614 | Non / Non | 4292.1 / 4281.3 | 3947.5 | 5 |
| P01_general_condition | done | Contrat de preuve | 0.180 | Non / Non | 724.0 / 716.0 | 7479.9 | 2 |
| P05_sparse_table | done | Contrat de preuve | 0.152 | Non / Non | 724.8 / 716.8 | 7479.5 | 1 |
| P10_decimal_sum | done | Contrat cellule | 0.113 | Non / Non | 725.0 / 717.0 | 7479.8 | 1 |
| P11_conversion | done | Contrat cellule | 0.137 | Non / Non | 725.0 / 717.0 | 7479.9 | 2 |
| L01_condition_mismatch | done | Génération 4B | 111.496 | Oui / Oui | 3977.3 / 3967.6 | 4112.6 | 190 |
| L06_cross_document_conflict | done | Génération 4B | 54.817 | Oui / Oui | 3979.1 / 3969.4 | 4212.0 | 103 |
| L13_negated_value | done | Génération 4B | 44.500 | Oui / Oui | 3979.9 / 3970.2 | 4172.6 | 81 |
| L16_table_note | done | Génération 4B | 75.401 | Oui / Oui | 3982.5 / 3972.8 | 4210.9 | 125 |

### Candidat — phase 7, blocs fermés

| Cas | État / erreur | Route | Durée (s) | Demande / réponse | RSS / PSS (Mio) | Disponible min (Mio) | Relevés |
|---|---|---|---:|---|---:|---:|---:|
| H01 | done | Contrat de preuve | 4.155 | Non / Non | 932.0 / 923.5 | 7297.9 | 9 |
| H02 | done | Contrat de preuve | 0.640 | Non / Non | 934.1 / 925.6 | 7301.0 | 2 |
| H03 | done | Génération 4B | 108.013 | Oui / Oui | 4199.7 / 4189.5 | 4041.4 | 202 |
| H04 | done | Contrat de preuve | 1.602 | Non / Non | 4202.5 / 4192.4 | 4043.2 | 4 |
| H05 | done | Contrat de preuve | 0.841 | Non / Non | 935.7 / 927.3 | 7294.5 | 3 |
| H06 | done | Contrat de preuve | 1.653 | Non / Non | 943.0 / 934.5 | 7289.0 | 4 |
| H07 | done | Contrat de preuve | 3.972 | Non / Non | 953.8 / 945.4 | 7282.8 | 8 |
| H08 | done | Contrat de preuve | 1.301 | Non / Non | 955.9 / 947.4 | 7287.2 | 4 |
| SCAN1_H04 | done | Contrat de preuve | 1.393 | Non / Non | 769.7 / 761.2 | 7438.4 | 3 |
| SCAN2_H07 | done | Contrat de preuve | 3.708 | Non / Non | 785.1 / 776.6 | 7388.2 | 7 |
| N_ina226 | done | Contrat de preuve | 1.439 | Non / Non | 985.7 / 977.3 | 7268.4 | 4 |
| N_tmp117 | done | Contrat de preuve | 1.668 | Non / Non | 994.8 / 986.1 | 7243.3 | 4 |
| P01_general_condition | done | Contrat de preuve | 0.161 | Non / Non | 725.4 / 716.9 | 7463.2 | 2 |
| P05_sparse_table | done | Contrat de preuve | 0.185 | Non / Non | 725.9 / 717.4 | 7463.7 | 1 |
| P10_decimal_sum | done | Contrat cellule | 0.171 | Non / Non | 725.9 / 717.4 | 7463.9 | 2 |
| P11_conversion | done | Contrat cellule | 0.153 | Non / Non | 725.9 / 717.4 | 7464.1 | 1 |
| L01_condition_mismatch | done | Génération 4B | 65.578 | Oui / Oui | 3971.9 / 3961.8 | 4205.6 | 122 |
| L06_cross_document_conflict | done | Génération 4B | 56.560 | Oui / Oui | 3976.1 / 3966.4 | 4185.2 | 105 |
| L13_negated_value | done | Génération 4B | 28.376 | Oui / Oui | 4097.9 / 4088.2 | 4111.2 | 53 |
| L16_table_note | done | Génération 4B | 46.955 | Oui / Oui | 4099.1 / 4089.3 | 4090.6 | 88 |

Les erreurs restent dans les dénominateurs. Leurs phases de trace sont
rapportées individuellement :

- `baseline 5 / H06` : `ollama_timeout` ; demande enregistrée **oui**, réponse reçue **non**, trace `verified`.

Les états `done` n'expriment aucun jugement de fidélité ou de complétude.

## Initialisation et indexation des blocs

La durée totale de bloc provient du reçu du dispatcher, et comprend aussi
démarrage, provisioning de vérification et arrêts. L’enveloppe avant requête
va de l’horodatage du protocole à la première tentative ; elle inclut le
démarrage applicatif, la lecture des extractions figées, l’extraction Office
éventuelle, le découpage, l’indexation et la publication.

La colonne « Générations DB » additionne les intervalles **création de la
génération → publication** des documents du bloc. La création de génération
intervient après la préparation des chunks : ces intervalles ne sont donc
pas une durée complète et isolée d’indexation. Cette dernière est **absente**,
et n’est pas reconstruite par soustraction du temps des requêtes.

| Bras / bloc | Total bloc (s) | Enveloppe avant requête (s) | Générations DB (s) | Documents indexés | Arrêts / dérive |
|---|---:|---:|---:|---:|---|
| baseline 5 / queries-transfer-a-baseline | 610.385 | 40.428 | 33.005 | 3 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| baseline 5 / queries-transfer-b-baseline | 859.276 | 21.211 | 17.199 | 3 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| baseline 5 / queries-ocr-baseline | 380.616 | 6.161 | 3.311 | 2 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| baseline 5 / queries-ti-baseline | 310.158 | 55.608 | 49.339 | 2 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| baseline 5 / queries-office-baseline | 309.989 | 9.254 | 4.936 | 11 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 7 / queries-transfer-a-candidate | 147.672 | 22.564 | 18.405 | 3 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 7 / queries-transfer-b-candidate | 39.022 | 23.016 | 19.129 | 3 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 7 / queries-ocr-candidate | 19.496 | 5.640 | 2.907 | 2 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 7 / queries-ti-candidate | 62.795 | 51.014 | 45.142 | 2 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 7 / queries-office-candidate | 215.039 | 8.561 | 4.662 | 11 | Groupes vides et leaders réapés / aucune dérive enregistrée |

Chaque bloc réindexe son manifeste complet dans une nouvelle base. Le bloc
Office contient notamment onze documents indexés pour huit questions prévues.
Les contenus, caches système, modèles conservés entre cas et coûts de
démarrage ne permettent pas d’assimiler les temps de tous les blocs.

## Extractions 6 réemployées

Ce suivi utilise les sept extractions PDF complètes de la phase 6, réparties
sur trois groupes. Il ne lance aucun nouveau worker PDF. Les coûts de ces
workers restent ceux de leur exécution historique, détaillée dans le
[relevé de développement 6](trust-4b-development-resource-costs-2026-11-09.md).
Ils ne sont pas imputés une seconde fois au suivi 7.

La preuve de réemploi `development-input-evidence-7.json` porte le SHA-256
`837106d71cccb88ffb0647f9c614f773bfe3083146f049d4445fe9a4472b5d7c`.
Elle vérifie les sources ingestion/runtime, les configurations, les verrous,
les préparateurs, les octets des entrées et sorties complètes, ainsi que les
arrêts 6. Elle ne reconstruit pas un gel exhaustif ancien de tous les binaires,
poids ou paquets installés et ne vaut pas qualification I5-D06.

L’extraction Office éventuelle reste incluse dans l’initialisation du bloc
Office ; aucune durée isolée n’est inventée pour elle.

## Identités et suite

Chaque bloc conserve ses identités d'application, de sources, de profil, de
manifestes et d'environnement dans le relevé JSON cité. Les observations
phase 7 et leurs erreurs restent conservées. Un suivi demandé après correction
constitue un groupe distinct sur une nouvelle identité source ; il ne remplace
aucune tentative primaire par une mesure favorable.

Les mesures de processus sont propres à cet hôte de qualification et à ces
exécutions. Le statut documentaire des cas, la décision de production et la
recette de plateforme restent dans leurs rapports et décisions séparés.
