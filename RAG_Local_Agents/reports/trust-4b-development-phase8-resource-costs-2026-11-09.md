# I5 — ressources du suivi de développement 8

**Rôle :** relevé technique des actions fermées, sans jugement documentaire.
**Propriétaire :** qualification. **Date :** 9 novembre 2026 UTC.
**Périmètre courant :** référence phase 5 (20 cas), candidat phase 8
(20 cas fermés), avec réemploi des extractions complètes 6.
Les vingt positions candidates prévues sont observées ; tous leurs blocs sont fermés.
La baseline 5 est réutilisée comme observation historique ; elle n’a pas été relancée.
Les candidats 6 et 7 restent dans leurs rapports distincts. Au terme de ce suivi
de développement, le réservé était encore fermé.

## Origine et limites des mesures

Le relevé `.runtime/qa/production-i5-20261108/development-phase8-closed-resources-1.json` porte le SHA-256
`d0459cf3ef21d2e2e258339e7c72ea5da43d9dde02bb98122b91f9b5016eddee`. Il conserve une seule observation
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

### Candidat — phase 8, blocs fermés

| Cas | État / erreur | Route | Durée (s) | Demande / réponse | RSS / PSS (Mio) | Disponible min (Mio) | Relevés |
|---|---|---|---:|---|---:|---:|---:|
| H01 | done | Contrat de preuve | 5.963 | Non / Non | 936.8 / 928.3 | 7320.4 | 12 |
| H02 | done | Contrat de preuve | 5.766 | Non / Non | 937.1 / 928.7 | 7320.9 | 12 |
| H03 | done | Génération 4B | 170.161 | Oui / Oui | 4195.6 / 4185.4 | 4020.5 | 308 |
| H04 | done | Contrat de preuve | 5.268 | Non / Non | 4198.4 / 4188.2 | 4053.9 | 11 |
| H05 | done | Contrat de preuve | 7.384 | Non / Non | 936.8 / 928.3 | 7313.0 | 16 |
| H06 | done | Contrat de preuve | 15.292 | Non / Non | 943.2 / 934.7 | 7315.8 | 30 |
| H07 | done | Contrat de preuve | 8.276 | Non / Non | 952.3 / 943.8 | 7280.9 | 15 |
| H08 | done | Génération 4B | 117.959 | Oui / Oui | 4201.1 / 4191.5 | 3950.7 | 215 |
| SCAN1_H04 | done | Contrat de preuve | 3.704 | Non / Non | 770.3 / 762.0 | 7400.0 | 8 |
| SCAN2_H07 | done | Contrat de preuve | 7.141 | Non / Non | 777.7 / 769.4 | 7415.5 | 13 |
| N_ina226 | done | Contrat de preuve | 9.926 | Non / Non | 989.1 / 980.8 | 7235.3 | 20 |
| N_tmp117 | done | Génération 4B | 78.212 | Oui / Oui | 4244.4 / 4234.9 | 3896.0 | 145 |
| P01_general_condition | done | Contrat de preuve | 0.211 | Non / Non | 724.0 / 715.8 | 7460.0 | 1 |
| P05_sparse_table | done | Contrat de preuve | 0.381 | Non / Non | 724.9 / 716.7 | 7460.1 | 2 |
| P10_decimal_sum | done | Contrat cellule | 0.144 | Non / Non | 724.9 / 716.7 | 7466.1 | 2 |
| P11_conversion | done | Contrat cellule | 0.155 | Non / Non | 724.9 / 716.7 | 7466.2 | 1 |
| L01_condition_mismatch | done | Génération 4B | 94.959 | Oui / Oui | 3975.7 / 3965.7 | 4220.9 | 167 |
| L06_cross_document_conflict | done | Génération 4B | 67.951 | Oui / Oui | 3978.6 / 3968.6 | 4228.2 | 124 |
| L13_negated_value | done | Génération 4B | 39.300 | Oui / Oui | 4099.4 / 4089.4 | 4085.9 | 72 |
| L16_table_note | done | Génération 4B | 50.846 | Oui / Oui | 4101.5 / 4091.5 | 4141.8 | 94 |

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
| candidate 8 / queries-transfer-a-candidate | 247.167 | 44.343 | 37.570 | 3 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 8 / queries-transfer-b-candidate | 194.345 | 33.055 | 27.323 | 3 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 8 / queries-ocr-candidate | 29.439 | 7.348 | 3.814 | 2 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 8 / queries-ti-candidate | 154.991 | 57.862 | 51.386 | 2 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 8 / queries-office-candidate | 274.014 | 8.576 | 4.532 | 11 | Groupes vides et leaders réapés / aucune dérive enregistrée |

Chaque bloc réindexe son manifeste complet dans une nouvelle base. Le bloc
Office contient notamment onze documents indexés pour huit questions prévues.
Les contenus, caches système, modèles conservés entre cas et coûts de
démarrage ne permettent pas d’assimiler les temps de tous les blocs.

## Extractions 6 réemployées

Ce suivi utilise les sept extractions PDF complètes de la phase 6, réparties
sur trois groupes. Il ne lance aucun nouveau worker PDF. Les coûts de ces
workers restent ceux de leur exécution historique, détaillée dans le
[relevé de développement 6](trust-4b-development-resource-costs-2026-11-09.md).
Ils ne sont pas imputés une seconde fois au suivi 8.

La preuve de réemploi `development-input-evidence-8.json` porte le SHA-256
`e8cfde8462a6a9283f3aae0b44bc66e16c5ea6ec10680e99d187c799004e3938`.
Elle vérifie les sources ingestion/runtime, les configurations, les verrous,
les préparateurs, les octets des entrées et sorties complètes, ainsi que les
arrêts 6. Elle ne reconstruit pas un gel exhaustif ancien de tous les binaires,
poids ou paquets installés et ne vaut pas qualification I5-D06.

L’extraction Office éventuelle reste incluse dans l’initialisation du bloc
Office ; aucune durée isolée n’est inventée pour elle.

## Identités et suite

Chaque bloc conserve ses identités d'application, de sources, de profil, de
manifestes et d'environnement dans le relevé JSON cité. Les observations
phase 8 et leurs erreurs restent conservées. Un suivi demandé après correction
constitue un groupe distinct sur une nouvelle identité source ; il ne remplace
aucune tentative primaire par une mesure favorable.

Les mesures de processus sont propres à cet hôte de qualification et à ces
exécutions. Le statut documentaire des cas, la décision de production et la
recette de plateforme restent dans leurs rapports et décisions séparés.
