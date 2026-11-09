# I5 — ressources et temps observés en développement

**Rôle :** relevé technique des actions fermées, sans jugement documentaire.
**Propriétaire :** qualification. **Date :** 9 novembre 2026 UTC.
**Périmètre courant :** référence phase 5 (20 cas), candidat phase 6
(20 cas fermés), 7 workers candidats fermés.
Les vingt positions candidates prévues sont observées ; tous leurs blocs sont fermés.
Le réservé reste fermé.

## Origine et limites des mesures

Le relevé `.runtime/qa/production-i5-20261108/development-closed-resources-4.json` porte le SHA-256
`f202f74fb4a65526bcaa3197a4c27980c18d376a4fa183c02b8af8d9b018c044`. Il conserve une seule observation
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

### Candidat — phase 6, blocs fermés

| Cas | État / erreur | Route | Durée (s) | Demande / réponse | RSS / PSS (Mio) | Disponible min (Mio) | Relevés |
|---|---|---|---:|---|---:|---:|---:|
| H01 | done | Contrat de preuve | 4.052 | Non / Non | 936.9 / 928.4 | 7280.5 | 8 |
| H02 | done | Contrat de preuve | 2.188 | Non / Non | 1025.9 / 1016.2 | 7125.6 | 5 |
| H03 | done | Génération 4B | 79.038 | Oui / Oui | 4219.6 / 4209.8 | 3965.3 | 142 |
| H04 | done | Contrat de preuve | 2.958 | Non / Non | 4284.9 / 4274.9 | 3952.8 | 5 |
| H05 | done | Contrat de preuve | 2.088 | Non / Non | 1014.7 / 1004.0 | 7178.2 | 5 |
| H06 | error / trace_write_failed | Non enregistrée | 0.489 | Non / Non | 985.1 / 976.8 | 7171.0 | 2 |
| H07 | done | Contrat de preuve | 3.723 | Non / Non | 975.3 / 967.0 | 7176.6 | 8 |
| H08 | error / trace_write_failed | Non enregistrée | 0.569 | Non / Non | 979.3 / 971.0 | 7206.2 | 2 |
| SCAN1_H04 | done | Contrat de preuve | 2.759 | Non / Non | 812.0 / 802.7 | 7379.0 | 6 |
| SCAN2_H07 | done | Contrat de preuve | 6.607 | Non / Non | 810.3 / 802.0 | 7350.9 | 11 |
| N_ina226 | done | Contrat de preuve | 4.066 | Non / Non | 1060.3 / 1052.1 | 7047.3 | 8 |
| N_tmp117 | error / trace_write_failed | Non enregistrée | 1.116 | Non / Non | 1104.1 / 1095.9 | 7018.4 | 4 |
| P01_general_condition | done | Contrat de preuve | 0.176 | Non / Non | 725.1 / 716.9 | 7380.5 | 2 |
| P05_sparse_table | done | Contrat de preuve | 0.213 | Non / Non | 727.2 / 719.0 | 7379.5 | 1 |
| P10_decimal_sum | done | Contrat cellule | 0.141 | Non / Non | 728.2 / 720.0 | 7378.7 | 2 |
| P11_conversion | done | Contrat cellule | 0.142 | Non / Non | 728.3 / 720.1 | 7391.3 | 1 |
| L01_condition_mismatch | done | Génération 4B | 66.196 | Oui / Oui | 3982.8 / 3973.2 | 4154.4 | 122 |
| L06_cross_document_conflict | done | Génération 4B | 78.476 | Oui / Oui | 3986.6 / 3976.9 | 4171.2 | 141 |
| L13_negated_value | done | Génération 4B | 39.623 | Oui / Oui | 4107.7 / 4098.0 | 4092.5 | 72 |
| L16_table_note | done | Génération 4B | 54.525 | Oui / Oui | 4106.5 / 4096.9 | 3966.6 | 98 |

Les erreurs restent dans les dénominateurs. Leurs phases de trace sont
rapportées individuellement :

- `baseline 5 / H06` : `ollama_timeout` ; demande enregistrée **oui**, réponse reçue **non**, trace `verified`.
- `candidate 6 / H06` : `trace_write_failed` ; demande enregistrée **non**, réponse reçue **non**, trace `verified`.
- `candidate 6 / H08` : `trace_write_failed` ; demande enregistrée **non**, réponse reçue **non**, trace `verified`.
- `candidate 6 / N_tmp117` : `trace_write_failed` ; demande enregistrée **non**, réponse reçue **non**, trace `verified`.

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
| candidate 6 / queries-transfer-a-candidate | 125.325 | 24.083 | 20.153 | 3 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 6 / queries-transfer-b-candidate | 40.596 | 22.776 | 18.640 | 3 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 6 / queries-ocr-candidate | 27.365 | 7.283 | 3.614 | 2 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 6 / queries-ti-candidate | 72.270 | 55.131 | 48.156 | 2 | Groupes vides et leaders réapés / aucune dérive enregistrée |
| candidate 6 / queries-office-candidate | 259.495 | 8.532 | 4.536 | 11 | Groupes vides et leaders réapés / aucune dérive enregistrée |

Chaque bloc réindexe son manifeste complet dans une nouvelle base. Le bloc
Office contient notamment onze documents indexés pour huit questions prévues.
Les contenus, caches système, modèles conservés entre cas et coûts de
démarrage ne permettent pas d’assimiler les temps de tous les blocs.

## Extractions complètes candidates déjà fermées

Ces coûts sont ceux des workers d’extraction, séparés des blocs de requêtes.
Les PDF de référence phase 5 utilisent des extractions déjà préparées :
**aucune nouvelle durée de worker PDF de référence n’appartient à cette
phase 5**. L’extraction Office durant l’initialisation n’a pas de durée isolée
dans ces fichiers. Aucun coût absent n’est remplacé par zéro.

| Groupe / PDF candidat | Durée worker (s) | RSS / PSS max (Mio) | Disponible min (Mio) | Relevés | Fin |
|---|---:|---:|---:|---:|---|
| extract-transfer-candidate / D01 | 86.652 | 1602.0 / 1444.5 | 6868.4 | 167 | rc 0, groupe vide, leader réapé |
| extract-transfer-candidate / D02 | 75.864 | 1911.9 / 1741.1 | 6482.4 | 144 | rc 0, groupe vide, leader réapé |
| extract-transfer-candidate / D03 | 122.332 | 1974.4 / 1806.3 | 6349.7 | 233 | rc 0, groupe vide, leader réapé |
| extract-ocr-candidate / SCAN1 | 40.546 | 1218.5 / 1209.9 | 7113.4 | 79 | rc 0, groupe vide, leader réapé |
| extract-ocr-candidate / SCAN2 | 54.100 | 1275.0 / 1268.1 | 7026.2 | 103 | rc 0, groupe vide, leader réapé |
| extract-ti-candidate / ina226 | 351.759 | 2173.9 / 2023.0 | 6242.8 | 665 | rc 0, groupe vide, leader réapé |
| extract-ti-candidate / tmp117 | 432.830 | 2013.6 / 1843.9 | 6379.2 | 813 | rc 0, groupe vide, leader réapé |

Les 7 workers terminent sans timeout, et leurs reçus déclarent des sources
inchangées. Ce résultat d’exécution ne juge ni les lectures OCR ni les tables produites.

## Identités et suite

Chaque bloc conserve ses identités d'application, de sources, de profil, de
manifestes et d'environnement dans le relevé JSON cité. Les observations
phase 6 et leurs erreurs restent conservées. Un suivi demandé après correction
constitue un groupe distinct sur une nouvelle identité source ; il ne remplace
aucune tentative primaire par une mesure favorable.

Les mesures de processus sont propres à cet hôte de qualification et à ces
exécutions. Le statut documentaire des cas, la décision de production et la
recette de plateforme restent dans leurs rapports et décisions séparés.
