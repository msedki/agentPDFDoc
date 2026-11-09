# I5 — Revue documentaire des réponses de développement, phases 5 à 8

**Suivi phase 8 complet, révision r04 du 9 novembre 2026.** Les **12/12 cas
sont relus : 8/10 positifs réussissent strictement et sont complets, ainsi que
2/2 limites ; aucune erreur technique**. H06 restitue désormais les deux
alimentations et H08 conserve la condition source de 10 mV avec son refus de
maximum à 1 mV. **TMP117 régresse** : les deux plages numériques sont exactes,
mais la réponse omet leur en-tête requis « Supply range » et les précède d'une
réserve globale injustifiée. SCAN2 reste une abstention totale face à l'OCR
incertain. Les échecs TMP117 et SCAN2 restent dans les dix positifs ; la
réussite technique des douze requêtes ne les efface pas. Le corpus réservé
I5 demeure fermé. Cette campagne ne qualifie pas une diffusion en production
et ne clôt pas I5-D04.

**Historique phase 7 complet, révision r03 du 9 novembre 2026.** Les **12/12 cas
sont relus : 8/10 positifs réussissent strictement et sont complets, ainsi que
1/2 limites ; aucune erreur technique**. Les trois échecs documentaires restent
visibles : H06 refuse les deux plages d'alimentation pourtant présentes dans
les preuves livrées, H08 refuse sans conserver la condition source 10 mV et
SCAN2 s'abstient toujours devant une extraction OCR incertaine. H07 et TMP117
répondent désormais complètement. Les extractions intégrales de phase 6 sont
réutilisées avec identité contrôlée ; la phase 7 exécute de nouvelles questions,
pas de nouvelles extractions. Ce résultat ne qualifie pas une diffusion en
production et ne clôt pas I5-D04.

**Historique phase 5, révision de revue r06 conservée.** Les **12 résultats primaires
de référence sont relus** : succès strict sur 1/10 positifs et 1/2 limites,
complétude sur 5/10 positifs, une erreur technique. Le candidat est relu sur
**4/12 cas** : H01, H02 et H04 réussissent strictement ; H03 refuse sans inventer
de valeur, mais omet la limite garantie requise et échoue au critère strict.
Les quatre réponses candidates passent par la route déterministe. Les huit
autres réponses candidates restent non exécutées au point de revue. Ces
résultats ne qualifient pas une diffusion en production.

**Suivi phase 6 complet, révision r03 du 9 novembre 2026.** Les **12/12 cas
sont relus : 6/10 positifs réussissent strictement et sont complets, ainsi que
1/2 limites**. H06, H08 et TMP117 terminent en erreur de traçage. H07 s'abstient
malgré les relations numériques présentes dans les preuves livrées ; SCAN2
s'abstient à cause des lectures OCR toujours incertaines. SCAN1 et INA226
réussissent désormais sans publier le contenu supplémentaire défectueux ou la
réserve globale de référence. Ces gains n'effacent pas les cinq cas sans succès
strict ; la phase 6 ne qualifie pas une diffusion en production. Aucune mesure
phase 5 n'est remplacée.

## 1. Périmètre et méthode fixés

La revue porte sur **12 cas par bras : 10 positifs et 2 limites**. Elle couvre
H01–H08, deux scans dérivés et deux questions TI, tous déjà consommés en I4 et
désormais de développement. Aucun document ou oracle réservé I5 n'est consulté.
Les cas Office sont suivis dans leur lot propre et ne sont pas ajoutés à ces
dénominateurs.

Les [oracles I4 publiés](production-i4-corpus/questions-oracles.json) définissent
les faits, rôles, unités, conditions, limites et périmètres attendus pour H01–H08
et leurs scans. Pour TI, les deux ensembles de relations déjà évaluées en I4
sont repris dans le plan de revue et confrontés aux pages originales. La reprise
réutilise ces exigences sans les adapter aux sorties. Le plan de cette revue a
été enregistré avant la lecture des nouvelles réponses. La revue est non
aveugle et indépendante du code du contrat de réponse ; son auteur a relu
l'ingestion et corrigé le typage de `table_rules.py`. Elle ne constitue donc pas
une évaluation indépendante de l'ensemble du système.
Pour le suivi phase 6, le même auteur a aussi implémenté le regroupement
géométrique du bandeau et relu son raccord API ; cette participation est
distinguée de la relecture des réponses contre les originaux.
En phase 7, il a relu les frontières de l'autorité de sujet de page et des
sections sœurs, sans en écrire le correctif API. Les verdicts documentaires
restent distincts de cette revue technique et des tests synthétiques.
En phase 8, il a relu l'extension aux paragraphes et listes, l'autorité du titre
imprimé et la fermeture des dépendances d'identité au rendu. Le reçu technique
conserve explicitement la régression TMP117 observée hors moteur ; la présente
revue juge séparément les nouvelles réponses natives, dont trois appels réels
au modèle. Les critères, questions et dénominateurs restent identiques.

Un positif réussit strictement si tous les besoins et leurs conditions sont
exprimés, si tous les faits documentaires publiés sont soutenus par l'original,
si les citations sont exactes et si aucune réserve globale injustifiée ne
contredit cette complétude. Une limite réussit si l'insuffisance requise est
explicite, si les conditions utiles sont conservées et si aucune valeur n'est
extrapolée ou ajoutée à tort. Un fait supplémentaire erroné fait échouer la
fidélité même s'il est étranger à la question.

La vérification distingue le texte extrait de l'original : document, version,
révision, génération, page, hash du bloc parent et sous-chaîne aux offsets sont
contrôlés en SQLite en lecture seule ; la relation documentaire est relue sur
les vues originales déjà présentes. Un état `done`, un contrôle produit
`passed` ou une citation littérale ne vaut pas succès documentaire. Une erreur
technique n'est pas une abstention réussie. Sans citation publiée, la précision
est non applicable. Les réponses finales intégrales, leurs segments, les
événements, les traces et leurs empreintes sont conservés dans les reçus privés.
Aucun rendu, appel OCR, extraction ou appel de modèle supplémentaire n'a été
effectué par cette revue.

## 2. Historique conservé : matrice phase 5

Les pages ci-dessous sont les **pages physiques, base 1**. Pour un scan, la page
du dérivé et sa correspondance originale sont distinguées dans le reçu.
`AWAITING_OUTPUT` signifie qu'aucun résultat n'est encore relu dans ce rapport ;
ce statut n'est assimilé ni à un échec, ni à une réussite. `NOT_RUN` décrit un
cas candidat non exécuté au point de revue r06. Aucun résultat de référence ne
remplace un résultat candidat manquant.

| Cas | Type / source | Référence phase 5 | Complétude réf. | Motif documentaire réf. | Candidat phase 5 |
| --- | --- | --- | --- | --- | --- |
| H01 | Positif, AD22103 p. 2 | FAIL, `done` | Non | Plage de tension de fonctionnement omise ; sa ligne était pourtant livrée. Les mêmes nombres dans le bandeau d'essai ne remplacent pas cette relation. | PASS, complet |
| H02 | Positif, AD22103 p. 1 | FAIL, `done` | Non | Pied de page légal restitué ; ajustage, tampon et linéarisation absents. Réponse hors sujet, pas abstention réussie. | PASS, complet |
| H03 | Limite, AD22103 p. 2 | FAIL, `done` | Non | Refus à 150 °C, mais ajout de 0,25 V comme minimum alors que l'original le place sous Typ ; plage garantie 0–100 °C non conservée. | FAIL : refus sûr, borne 0–100 °C omise |
| H04 | Positif, AD22105 p. 1 | FAIL, `done` | Oui | 2,7–7,0 V et −40 à +150 °C correctement restitués ; réserve générale de réponse partielle injustifiée. | PASS, complet |
| H05 | Positif, AD22105 p. 1 | FAIL, `done` | Oui | Dépassement de consigne, sortie à collecteur ouvert et fonction de l'hystérésis exacts ; réserve générale d'interprétation injustifiée. | NOT_RUN |
| H06 | Positif, LTC1540 p. 1 | ERROR | Non | `ollama_timeout`, réponse vide ; les deux modes d'alimentation ne sont pas restitués. | NOT_RUN |
| H07 | Positif, LTC1540 p. 3 | FAIL, `done` | Non | 60/50 µs et 10/100 mV regroupés sans liaisons individuelles ; bandeau général absent du texte final malgré sa livraison. | NOT_RUN |
| H08 | Limite, LTC1540 p. 1 | PASS, `done` | Oui | Insuffisance pour le maximum demandé à 1 mV, condition source 10 mV conservée, aucune extrapolation. | NOT_RUN |
| SCAN1_H04 | Positif, dérivé p. 1 ← AD22105 p. 1 | FAIL, `done` | Oui | Deux plages exactes, mais ajout de « 230 HW » au lieu de 230 µW et réserve globale injustifiée. | NOT_RUN |
| SCAN2_H07 | Positif, dérivé p. 1 ← LTC1540 p. 3 | FAIL, `done` | Non | Sous-lignes fusionnées ; unités et variables corrompues (`us ys`, `Cour`, `V*`, `OV`). | NOT_RUN |
| N_ina226 | Positif, INA226 p. 1 | FAIL, `done` | Oui | Bus 0–36 V et alimentation 2,7–5,5 V exacts ; réserve injustifiée sur une propriété prétendument manquante. | NOT_RUN |
| N_tmp117 | Positif, TMP117 p. 1 | PASS, `done`, route déterministe | Oui | Deux plages d'alimentation liées à leurs températures et à leur en-tête ; aucun appel au modèle observé. | NOT_RUN |

### Compteurs séparés

| Indicateur | Référence relue | Ensemble attendu | Candidat |
| --- | --- | --- | --- |
| Cas relus | 12 | 12 par bras | 4/12 ; 8 NOT_RUN |
| Positifs strictement réussis | 1/10 | 10 positifs par bras | 3/3 relus ; 7 NOT_RUN |
| Positifs complets | 5/10 | 10 positifs par bras | 3/3 relus ; 7 NOT_RUN |
| Limites strictement réussies | 1/2 | 2 limites par bras | 0/1 relue ; 1 NOT_RUN |
| Erreurs techniques | 1/12, dont 1/10 positifs | 12 cas par bras | 0/4 relus |
| Réserves globales injustifiées | 4/12 : H04, H05, SCAN1_H04, N_ina226 | 12 cas par bras | 0/4 relus |
| Réponses non vides dont tous les faits documentaires sont soutenus | 8/11 ; H03 et les deux scans échouent | H06 référence vide : non applicable | 4/4, dont H03 : refus fondé sans fait numérique |

| Cohorte de référence | Positifs stricts | Positifs complets | Limites strictes | Erreurs |
| --- | --- | --- | --- | --- |
| Originaux I4, entièrement relus | 0/6 | 2/6 | 1/2 | 1/8 |
| Scans I4, entièrement relus | 0/2 | 1/2 | Sans cas limite | 0/2 |
| TI2, entièrement relu | 1/2 | 2/2 | Sans cas limite | 0/2 |

**Référence.** Sur les onze réponses non vides, les **34 marqueurs** publiés renvoient à
**79 occurrences de blocs** de sources citées ; les 79 identités littérales sont
valides. Les **198 occurrences de blocs livrés** sont aussi valides, dont 34
livrées à H06 sans réponse finale. Ces comptes ne prouvent pas la justesse
sémantique : H03 et les scans restent erronés malgré des offsets et hashes exacts. Aucun passage
contrôlé ne sort de la fenêtre de pages autorisée. Les petits défauts de
transcription sans changement numérique (indice répété, unité répétée, puce
transcrite en lettre) sont signalés séparément dans les fiches privées.

Le texte des événements publics `delta` de référence reproduit exactement les onze réponses
non vides ; H06 n'émet pas de texte de réponse. Pour les onze, le contrôle produit
de support tracé et le plan déclaré validé précèdent le premier delta de prose.
Les 625 événements de progression `structured_delta` sont comptés séparément ;
ils ne sont pas assimilés à de la prose documentaire validée. Cette vérification
d'ordre de publication ne corrige pas les trois erreurs de fidélité observées.

**Candidat A.** Les **8 marqueurs** de H01, H02 et H04 renvoient à **24/24
occurrences de blocs cités exactes**. Les **106/106 occurrences livrées** sont
valides, y compris celles de H03 qui n'émet aucun marqueur. Pour H03, la précision
des citations est **non applicable**. Les quatre textes delta correspondent au
final et suivent le plan validé et le contrôle de support tracé ; aucun événement
de progression générative ni appel LLM n'est observé dans ces quatre traces.

## 3. Constats de référence et portée des observations

H01 montre une perte entre preuve livrée et réponse : la ligne de tension est
présente dans S001, offsets parent `[534,568)`, mais non publiée. H02 montre une
perte plus en amont : le corps utile est visible sur l'original, tandis que les
preuves livrées ne contiennent que le pied de page. Les deux défauts ne sont
pas confondus.

Pour H03, la colonne Min du nominal à 0 °C est vide ; 0,25 V appartient à Typ.
La reconstruction de la référence publie pourtant cette valeur comme un
minimum. Le refus de donner une valeur à 150 °C ne compense ni cette assertion
fausse ni l'omission de la limite garantie à 100 °C. Pour H07, l'original relie
60 µs à 10 mV et 50 µs à 100 mV, sous Typ, avec COUT = 100 pF partagé. Le
bandeau fixe TA = 25 °C, V+ = 5 V, V− = GND = 0 V sauf indication contraire ;
ces délais ne portent pas le repère de garantie sur toute la plage thermique.
L'absence de ces liaisons dans le rendu fait échouer la complétude. Aucun
croisement explicite des valeurs n'est imputé au texte regroupé.

H04 et H05 contiennent les informations attendues : leur échec strict vient
de la réserve générale injustifiée, conformément aux critères antérieurs.
Les faits supplémentaires ont également été relus ; le texte d'hystérésis
approximative de 4 °C et la caractéristique typique de 4,1 °C correspondent bien
aux deux formulations de l'original AD22105.

SCAN1_H04 restitue bien les deux plages, mais le paragraphe supplémentaire de
puissance affiche **230 HW**, alors que le raster porte **230 µW**. Cet ajout
étranger à la question reste évalué : la fidélité globale échoue. La réserve
générale selon laquelle des faits demandés manquent reste également injustifiée.
Les avertissements OCR et extraction partielle sont distincts et ne rendent pas
l'unité erronée exacte.

SCAN2_H07 conserve les nombres 60 et 50 sous Typ, mais affiche `us ys` au lieu
des deux unités µs, `Cour` au lieu de COUT, `V*` au lieu de V+ et `OV` au lieu
de 0 V. Les associations aux overdrives ne sont pas séparées. Le bandeau est
cette fois partiellement publié, mais ses symboles corrompus empêchent d'en
créditer la fidélité complète. La réserve est cohérente avec cette réponse
défectueuse ; elle ne constitue pas une réussite sur le positif répondable.

Dans les deux cas, les citations identifient bien **la page 1 du PDF dérivé**. La
correspondance AD22105 p. 1 et LTC1540 p. 3 est une provenance de revue séparée,
pas un localisateur produit inventé. Les rasters déjà conservés, 1 700 × 2 200
pixels en niveaux de gris, correspondent exactement aux hashes du
[manifest de dérivation](production-i4-corpus/scan-transformations.json).

INA226 restitue bus 0–36 V et alimentation simple 2,7–5,5 V, sans confondre les
deux propriétés. Les faits supplémentaires sur courant, température et adresses
correspondent aussi à l'original. Le verdict échoue à cause de la réserve selon
laquelle une propriété ne serait pas établie. TMP117 restitue séparément
1,7–5,5 V pour −55 à 70 °C et 1,8–5,5 V pour −55 à 150 °C, sous l'en-tête
d'alimentation. La répétition de la résolution 16 bits est inutile mais fidèle.
Les avertissements distincts sur des notes de tableau ne prouvent aucune
condition manquante sur ces passages narratifs ou listes de caractéristiques.

H06 finit après **302 780,50 ms** avec `model_call_attempted=true` et
`model_called=false`. Une requête fournisseur a été tentée ; aucune réponse
réussie n'est enregistrée. Le booléen `model_called=false` ne signifie donc pas
qu'aucun appel n'a été essayé. Le résultat primaire reste ERROR ; aucune
reprise ni ancienne sortie n'est substituée à ce résultat.

Les autres latences mesurées sont H01 261 092,27 ms, H02 48 300,65 ms,
H03 88 954,93 ms, H04 152 480,74 ms, H05 122 911,77 ms,
H07 174 771,35 ms et H08 221 173,11 ms. Les sept `done` déclarent une réponse
du modèle reçue. Les deux scans sont également `done`, avec réponse du modèle
reçue, en 170 646,26 ms et 190 041,92 ms respectivement. Ces observations uniques ne permettent aucun gain causal
de performance, ni comparaison du candidat encore non exécuté. INA226 prend
241 416,26 ms, avec appel et réponse du modèle tracés. TMP117 prend 2 614,38 ms
sur `deterministic_evidence_contract` : `model_called=false`, champ
`model_call_attempted` absent, aucune phase `llm.request` ou `llm.response`.
Ce succès ne devient pas une réponse générative 4B ni une mesure de sa vitesse.
Au total, dix réponses du modèle sont observées, une tentative échoue par timeout
et un cas suit la route déterministe sans appel observé.

## 4. Candidat A : gains observés et limite restante

H01 restitue maintenant la ligne de tension de fonctionnement avec ses rôles
Min/Typ/Max, la température garantie et le bandeau général. L'en-tête AD22103K
est également conservé. La relecture séparée de la nouvelle extraction D01
vérifie les quatre côtés natifs du groupe qui encadre Min, Typ et Max. Par
rapport à l'extraction de diagnostic 4, seule la portée de cette cellule
d'en-tête change ; les 56 autres cellules canoniques et le texte du tableau sont
identiques. Ce constat d'extraction est distinct du contrôle de la réponse.

H02 publie le paragraphe utile, absent des preuves de référence, avec les trois
fonctions attendues. La lecture est confrontée au corps visible dans l'image
originale. H04 conserve les deux plages et supprime la réserve injustifiée ;
le doublon typographique d'unité V persiste, sans modification numérique. Les
faits supplémentaires de sa liste de caractéristiques sont aussi soutenus.

H03 ne publie plus le faux minimum de 0,25 V et n'extrapole aucune valeur à
150 °C. Il n'émet toutefois que le refus générique : **ni la plage garantie
0–100 °C, ni une citation ne figurent dans le texte final**. La note livrée
comme S002 contient cette plage. L'[oracle gelé](production-i4-corpus/questions-oracles.json)
exige de conserver la limite publiée ; ce cas reste donc FAIL strict, avec
abstention totale. La disparition d'une assertion fausse est un progrès de
fidélité, pas une réussite complète du cas limite.

Les quatre états sont `done`, mais tous suivent
`deterministic_evidence_contract`, avec `model_called=false`, champ de tentative
absent et aucune phase `llm.request`/`llm.response`. Leurs durées sont
H01 **3 721,52 ms**, H02 **2 253,00 ms**, H03 **1 801,11 ms** et H04
**2 811,14 ms**. Ce changement de route empêche d'attribuer l'écart de latence
à une accélération du modèle 4B. Les trois succès positifs portent uniquement
sur les cas relus ; les sept autres positifs et la seconde limite restent à
mesurer.

La nouvelle extraction D03 a aussi été relue séparément : les deux sous-lignes
de délai, les unités µs, la dépendance de COUT = 100 pF et les quatre fragments
de conditions générales sont conservés. Ses 1 202 signatures de blocs et son
tableau canonique restent identiques à la phase 4. Ce constat prépare la revue
de H07 et ne constitue pas un verdict de réponse. Les trois documents D01–D03
gardent leur état `ready_partial` ; les régions non résolues et tableaux
indisponibles ne sont pas déclarés couverts.

### 4.1 Historique phase 5 : extraction des scans relue, réponses non exécutées

Les deux extractions de scans phase 5 sont complètes au sens du parseur et
restent `ready_partial`. Leurs 23 et 18 signatures de blocs sont identiques à
celles de la phase 3 ; les nouveaux témoins de qualité sont examinés séparément.
Pour SCAN1, les fragments des plages demandées sont corroborés. Le faux signe
`+2.0°C` reste dans le texte OCR, mais le contrôle raster repère la barre
inférieure et rend cette lecture incertaine. `230 HW` reste également incertain.
Aucune de ces chaînes n'est remplacée par une valeur attendue.

Pour SCAN2, les huit bindings des deux sous-lignes de délai restent ambigus :
`us`/`ys`, `Cour`, `V*` et `OV` ne correspondent pas aux unités et signes de
l'original. Le bandeau échoue aussi pour une raison indépendante : ses
13 fragments OCR dépassent la limite de 8 pièces. **Les réponses candidates
SCAN1_H04 et SCAN2_H07 restent NOT_RUN ; une qualité locale ou une abstention
ne vaut pas réussite de la question.**

Une sonde fixée avant exécution reconstruit le raster exact de SCAN2, puis
exécute **24 appels OCR en 6,522 s** : huit régions observées, avec les conditions
PSM 6 ×2, PSM 6 ×1 et PSM 7 ×1. Les 24 appels se terminent sans erreur ; leurs
processus sont réapés et leurs groupes sont vides. Les crops consomment
1 383 450 pixels cumulés, sous les plafonds inchangés. Les régions plus petites
évitent les pipes issus des filets, mais ne rétablissent ni COUT, ni µs, ni V+,
ni 0V. Le résultat est **négatif pour la récupération des symboles** ; toutes
les lectures sont conservées et aucune substitution n'est adoptée. Reçu :
`scan2-segmentation-probe-r01/receipt.json`, SHA-256
`40ffb621be1dbdcd270dc10217148fc85789d6387fb8a3abb62e5c73b4862425`.

Le correctif géométrique distinct regroupe les **13 fragments originaux en
2 pièces de ligne**. Chaque sous-référence conserve son parent, son texte,
ses offsets, son hash, sa version, sa révision et son rectangle. Les limites
restent **8 pièces / 256 blocs / 4 096 caractères**. Un rejeu pur vérifie ce
regroupement et l'identité des 15 annotations des tableaux D01–D03 ; il ne
modifie pas les extractions phase 5. Les qualités OCR de SCAN2 restent
incertaines. De nouvelles extractions et réponses sont requises avant toute
conclusion sur l'utilité ; **I5-D04 n'est pas acquis**.

### 4.2 Phase 6 : trois nouvelles extractions fermées, revue distincte

La campagne de développement suivante réextrait entièrement D01–D03 sous le
snapshot 6. Ses trois workers se terminent sans timeout ni erreur, avec leaders
réapés et groupes vides. Le fingerprint d'ingestion est
`df7d4c9bc6e7b819c039d5976ebdf4731e0b97e6cd0037bcf28907876f2804de`.
Les **32 pages et 2 244 blocs** conservent exactement les textes, types,
références de parseur et rectangles de la phase 5. Les quinze qualités de
tableaux conservent leurs observations, bindings et dépendances ; les bandeaux
portent les nouvelles identités de blocs et révisions attendues.

| Document | Pages / blocs | Résultat de la relecture d'extraction |
| --- | --- | --- |
| D01 | 7 / 321 | Parent couvrant Min/Typ/Max, limites garanties, conditions générales et valeurs nominales en colonne Typ conservés |
| D02 | 11 / 721 | Plages, déclenchement et rôle de l'hystérésis dans les trois blocs utiles conservés ; doublon V inchangé |
| D03 | 14 / 1 202 | Sous-lignes 60/50 µs, overdrives distincts, COUT partagé par offsets exacts et bandeau général conservés |

Les trois documents restent `ready_partial`, avec trois tableaux soutenus et
douze indisponibles. Les régions non résolues ne sont pas créditées comme
couvertes. Cette relecture s'appuie sur les vues originales déjà contrôlées,
dont les hashes sont revérifiés, sans nouveau rendu ni moteur. Elle ne remplace
ni les résultats phase 5, ni la revue des réponses phase 6 encore attendues.
Le reçu final `development-transfer-6-ingestion-review-r02.json` porte le
SHA-256 `019216a6568f2a3315843b22c2f9ae0f42abf55d4a8c448f3341cfc5985c75cb`.

### 4.3 Réponses phase 6 : huit premiers cas terminaux

| Cas | Verdict strict | Observation déterminante |
| --- | --- | --- |
| H01 | PASS positif | Plages, rôles et conditions générales complets ; texte identique au candidat phase 5 |
| H02 | PASS positif | Ajustage, tampon et linéarisation explicitement cités ; texte identique à la phase 5 |
| H03 | PASS limite | Plage garantie 0–100 °C désormais citée ; aucune tension extrapolée à 150 °C |
| H04 | PASS positif | Deux plages complètes, sans réserve injustifiée ; doublon V typographique conservé |
| H05 | PASS positif | Seuil utilisateur, sortie collecteur ouvert et prévention des commutations rapides complets |
| H06 | ERROR | `trace_write_failed`, 489,04 ms, réponse vide ; reste dans les six positifs relus |
| H07 | FAIL positif | Abstention totale ; délais/conditions présents au catalogue, sujet fourni séparément par l'en-tête de page |
| H08 | ERROR | `trace_write_failed`, 569,46 ms, réponse vide ; reste dans les deux limites |
| SCAN1_H04, SCAN2_H07, N_ina226, N_tmp117 | Revue ultérieure en §4.4 | Le reçu r01 conserve l'état antérieur de cette revue progressive |

H03 a été confronté de nouveau à l'image originale p. 2 : l'extrait cite
précisément la plage garantie de 0 à +100 °C. L'équation de non-linéarité ajoutée
dans cette citation figure aussi dans la note source. Le refus d'extrapoler est
justifié. Cette réponse appelle le générateur local, en **79 037,85 ms** ; les
cinq autres réponses non vides de ce groupe suivent la route déterministe.
Les deux erreurs ne sont pas comptées comme abstentions documentaires.

H07 conserve dans les preuves livrées les deux relations Typ, les overdrives
distincts, la capacité partagée et les conditions générales vérifiées. Le
bandeau imprimé `LTC1540` est une source distincte sur la même page ; les
relations retenues gardent pourtant un sujet vide. Ce défaut d'association
empêche une réponse utile. La seule présence du nom dans le fichier ou la
question n'autoriserait pas à le réattribuer à un tableau.

Les **10 marqueurs publiés** de ce groupe renvoient à **34/34 occurrences de
blocs exactes** ; les **169/169 occurrences livrées** sont aussi valides. Les
six réponses non vides sont identiques aux deltas de prose et suivent le plan
validé et le contrôle de support tracé. Les **49 événements de progression
structurée** sont comptés séparément. Ces contrôles d'identité n'effacent ni
l'échec H07 ni les erreurs de traçage. Reçu distinct :
`development-phase6-independent-review-r01.json`, SHA-256
`2a2464bad143bae06ff59bd4c8babf48fea63b24522cf864d6dbcdbfa5fff6d3`.

### 4.4 Phase 6 complète : scans, TI et dénominateurs finaux

| Cas complémentaire | Verdict strict | Observation déterminante |
| --- | --- | --- |
| SCAN1_H04 | PASS positif, 2 758,72 ms | Alimentation simple 2,7–7,0 V et fonctionnement −40 à +150 °C cités ; aucun « 230 HW » dans la réponse finale |
| SCAN2_H07 | FAIL positif, 6 607,50 ms | Refus total ; les unités, la variable COUT et les signes du bandeau ne sont pas récupérés avec une qualité suffisante |
| N_ina226 | PASS positif, 4 066,31 ms | Bus 0–36 V et alimentation simple 2,7–5,5 V complets, sans réserve globale injustifiée |
| N_tmp117 | ERROR, 1 115,88 ms | `trace_write_failed`, réponse vide ; les deux plages conditionnelles originales ne sont pas restituées |

Les quatre originaux ou rasters déjà conservés ont été revus sans nouveau
rendu. SCAN1 cite uniquement les deux fragments utiles ; le parent OCR livré
contient encore « 230 HW », mais cette unité n'est plus publiée dans la prose.
Le signe négatif est conservé sous la forme typographique d'un tiret cadratin,
sans changement du sens de la plage. Les avertissements OCR et extraction
partielle restent visibles et ne sont pas confondus avec une réserve injustifiée
sur les besoins demandés.

L'extraction SCAN2 fraîche contient bien les **13 parents exacts regroupés en
2 pièces géométriques**, avec leurs offsets, hashes et rectangles. Les huit
bindings des deux sous-lignes de délai restent ambigus ; `us`/`ys`, `Cour`,
`V*` et `OV` sont toujours présents dans le texte extrait. La réponse finale
n'en publie aucun et ne fournit aucune valeur. Cette abstention est justifiée
par la qualité de l'extraction ; elle reste un **échec sur un cas positif**
dont l'original contient la réponse. Le regroupement du bandeau ne constitue
pas une récupération des unités et **I5-D04 reste non acquis**.
Le reçu d'extraction distinct `development-ocr-6-ingestion-review-r01.json`
porte le SHA-256
`2f3091f55a73ff6d0b33ccd63cfcfba076a3be7be6b938f785435b44d9a97fbe`.

Les deux documents TI ont été réextraits entièrement : **91 pages et
3 781 blocs**. Les signatures de texte, type, référence de parseur et rectangle
restent identiques à la phase 5 ; les documents gardent leur état
`ready_partial`. La première page TMP117 contient toujours l'en-tête
« Supply range » et les relations 1,7–5,5 V pour −55 à 70 °C et 1,8–5,5 V
pour −55 à 150 °C. Leur présence ne compense pas l'erreur d'exécution de la
question. Le succès de référence n'est pas réattribué au candidat.
Reçu d'extraction : `development-ti-6-ingestion-review-r01.json`, SHA-256
`373fda351fe950063d91ad897f43ed7de8992801c17e387272e13a4bea7b0829`.

| Indicateur final PDF | Référence phase 5 | Candidat phase 6 |
| --- | --- | --- |
| Cas relus | 12/12 | 12/12 |
| Positifs strictement réussis | 1/10 | 6/10 |
| Positifs complets | 5/10 | 6/10 |
| Limites strictement réussies | 1/2 | 1/2 |
| Erreurs techniques | 1/12 | 3/12 : H06, H08, N_tmp117 |
| Refus totaux sur des positifs | 0/10 | 2/10 : H07, SCAN2_H07 |
| Réserves globales injustifiées | 4/12 | 1/12 : H07 |

Les **15 marqueurs publiés** du candidat phase 6 renvoient à **49/49 occurrences
de blocs exactes** ; les **278/278 occurrences livrées** passent les contrôles
d'identité et de périmètre. Les sept réponses avec des faits documentaires
publiés sont soutenues par les originaux ; les deux autres réponses non vides
sont des refus sans valeur. Leur précision de citation est non applicable,
comme celle des trois erreurs vides. Les neuf textes non vides correspondent
exactement à leurs deltas de prose et sont précédés par le plan validé et le
contrôle de support. Les 49 événements de progression structurée sont comptés
séparément. H03 est le seul résultat de ce lot documentaire qui appelle le
générateur local ; huit réponses non vides suivent la route déterministe.

La revue finale `development-phase6-independent-review-r03.json` conserve les
réponses intégrales, leurs segments publics, erreurs, avertissements, citations
et empreintes. Son SHA-256 est
`630d2dc64bfb1e62e7242e9a09b3975c91d64d6d309136c4e745673fe93706e0`.
Les révisions r01 et r02 sont conservées séparément. La cause exacte des erreurs
de traçage relève d'un diagnostic technique distinct ; aucun succès n'est
inféré à partir de la trace incomplète.

### 4.5 Phase 7 complète : nouveaux résultats, extractions 6 conservées

Les quatre blocs PDF, scans et TI sont fermés avec retour nul, arrêt vérifié
et sans dérive de sources. Le snapshot 7 contient 172 fichiers ; les
**27 fichiers d'ingestion sont identiques au snapshot 6**. Le reçu de réemploi
lie les extractions complètes déjà contrôlées à cette nouvelle campagne de
questions. Les douze réponses sont relues à nouveau, sans transférer de verdict
de phase 6 et sans ouvrir le corpus réservé I5.

| Cas | État technique phase 7 | Verdict strict | Constat contre l'original |
| --- | --- | --- | --- |
| H01 | `done`, déterministe | PASS | Fonctionnement 2,7–3,6 V, Typ 3,3 V ; température garantie 0–100 °C ; sujet et conditions générales conservés. |
| H02 | `done`, déterministe | PASS | Les trois circuits externes supprimés sont explicitement cités : ajustage, tampon et linéarisation. |
| H03 | `done`, modèle appelé | PASS limite | Refus à 150 °C avec la plage garantie 0–100 °C. La citation supplémentaire de 0,25 V garde son rôle Typ et ses conditions TA = 0 °C, VS = 3,3 V ; aucune transposition à 150 °C. |
| H04 | `done`, déterministe | PASS | Alimentation 2,7–7,0 V et fonctionnement −40 à +150 °C ; les faits supplémentaires publiés sont également exacts. |
| H05 | `done`, déterministe | PASS | Dépassement de consigne, sortie à collecteur ouvert et prévention des commutations thermiques rapides correctement cités. |
| H06 | `done`, déterministe | FAIL positif | Abstention totale malgré la présence du paragraphe donnant 2–11 V en alimentation simple et ±1–±5,5 V en alimentation symétrique. |
| H07 | `done`, déterministe | PASS | 60 µs Typ à 10 mV et 50 µs Typ à 100 mV séparés ; COUT = 100 pF commun, bandeau TA = 25 °C / V+ = 5 V / V− = GND = 0 V et sujet LTC1540 cités. |
| H08 | `done`, déterministe | FAIL limite | Refus sans garantie fausse, mais condition originale 10 mV et citation absentes. La seule absence de valeur inventée ne satisfait pas le critère strict. |
| SCAN1_H04 | `done`, déterministe | PASS | Les deux plages et leurs signes sont conservés ; le parent contient encore « 230 HW », mais ce texte erroné n'est pas publié dans la réponse. |
| SCAN2_H07 | `done`, déterministe | FAIL positif | Refus total justifié par les lectures OCR encore incertaines ; aucune unité ou condition réparée sans preuve n'est publiée. |
| N_ina226 | `done`, déterministe | PASS | Bus 0–36 V et alimentation simple 2,7–5,5 V distincts, sans réserve globale injustifiée. |
| N_tmp117 | `done`, déterministe | PASS | 1,7–5,5 V pour −55 à 70 °C et 1,8–5,5 V pour −55 à 150 °C, chaque plage liée à son en-tête et ses températures. |

**H06 demeure un besoin positif non satisfait.** Le paragraphe de description
est déjà livré, dans S001, bloc
`20eaeb6e-86e7-5fd2-b60f-d96c4466c63b`, offsets 0–474. Sur l'original, il suit
directement le paragraphe qui présente le LTC1540 comme comparateur, dans la
même colonne sous « DESCRIPTION ». Le moteur termine sa requête, mais le
refus ne fournit aucune des deux relations demandées. L'absence d'erreur de
traçage et l'utilité documentaire sont donc comptées séparément.

**H08 conserve une limite sûre mais incomplète.** Le passage source de la
première page indique 60 µs pour un overdrive de 10 mV ; il n'établit pas le
maximum garanti demandé à 1 mV. La référence phase 5 conservait ce passage
avec le refus. Le candidat 7 le livre encore parmi ses sources, mais ne le
cite plus dans sa réponse. Le verdict FAIL applique la même exigence de
conservation des conditions utiles ; il ne transforme pas cette omission en
affirmation numérique fausse.

**H07 et TMP117 sont complets dans ces exécutions.** H07 cite le header de
page et les deux sous-lignes du tableau, avec leurs rôles et dépendances.
Les répétitions d'en-têtes et de la ligne origine rendent la présentation
longue ; elles ne fusionnent pas les couples délai/overdrive. Le point plein
du bandeau est transcrit « l », sans attribuer ce repère thermique aux deux
délais qui n'en portent pas. TMP117 reprend inutilement la résolution de
16 bits, 0,0078 °C par LSB, dans les deux groupes ; ce fait est exact sur
l'original et ne remplace aucune condition de température.

| Indicateur final PDF | Référence phase 5 | Candidat phase 6 | Candidat phase 7 |
| --- | --- | --- | --- |
| Cas relus | 12/12 | 12/12 | 12/12 |
| Positifs strictement réussis | 1/10 | 6/10 | 8/10 |
| Positifs complets | 5/10 | 6/10 | 8/10 |
| Limites strictement réussies | 1/2 | 1/2 | 1/2 |
| Erreurs techniques | 1/12 | 3/12 | 0/12 |
| Refus totaux sur des positifs | 0/10 | 2/10 | 2/10 : H06, SCAN2_H07 |
| Réserves globales injustifiées | 4/12 | 1/12 | 1/12 : H06 |

Les **33 marqueurs publiés** renvoient à **73/73 occurrences de blocs exactes** ;
les **474/474 occurrences livrées** passent les contrôles de texte, d'identité
et de périmètre. Les neuf réponses comportant des faits documentaires sont
soutenues par les originaux. Les trois autres sont des refus totaux, dont la
précision de citation est non applicable. Ces contrôles ne compensent pas leur
incomplétude. Les **12 textes finaux correspondent à leurs deltas de prose**,
après plan validé et contrôle de support ; les **111 événements de progression
structurée** sont comptés séparément. Onze réponses suivent la route
déterministe. H03 comporte les phases réelles `llm.request` et `llm.response`.
Aucun gain causal de vitesse n'est déduit de ces routes et observations uniques.

Le reçu final `development-phase7-independent-review-r03.json`, SHA-256
`f7c335d692308899b320770d222fcfc09f0a8ed10c5ba0d36a181de9763ea3cd`,
conserve les réponses intégrales, segments, conditions, refus, avertissements,
citations, traces et empreintes. Les révisions r01 et r02 et toutes les revues
antérieures sont préservées. SCAN2 reste un échec positif ; l'abstention sûre
et le regroupement géométrique du bandeau ne sont pas décrits comme une
récupération de ses unités ou une acquisition de I5-D04.

### 4.6 Phase 8 complète : deux corrections utiles et une régression conservée

Les quatre blocs PDF, scans et TI sont fermés avec retour nul, arrêt vérifié
et sans dérive de sources. Le snapshot 8 et son plan exécutent de nouvelles
questions sur les **extractions intégrales de phase 6 explicitement réemployées**.
Les 27 fichiers d'ingestion sont inchangés. La revue n'exécute aucun nouveau
moteur : elle relit les réponses finales, leurs citations et événements, les
bases SQLite en lecture seule, et les vues originales déjà conservées.

| Cas | État technique phase 8 | Verdict strict | Constat contre l'original |
| --- | --- | --- | --- |
| H01 | `done`, déterministe | PASS | Min/Typ/Max de tension distincts, température garantie et conditions générales complètes. |
| H02 | `done`, déterministe | PASS | Ajustage, tampon et linéarisation tous présents dans la citation exacte. |
| H03 | `done`, modèle appelé | PASS limite | Pas de valeur à 150 °C ; garantie 0–100 °C citée. Le supplément de 0,25 V garde Typ, TA = 0 °C et VS = 3,3 V. |
| H04 | `done`, déterministe | PASS | 2,7–7,0 V et −40 à +150 °C complets ; le « V » final redondant ne change aucune valeur. |
| H05 | `done`, déterministe | PASS | Dépassement de consigne, collecteur ouvert et rôle anti-commutations de l'hystérésis soutenus. |
| H06 | `done`, déterministe | PASS | Alimentation simple 2–11 V et symétrique ±1–±5,5 V, avec le header LTC1540 cité dans le même groupe. |
| H07 | `done`, déterministe | PASS | 60 µs Typ à 10 mV et 50 µs Typ à 100 mV, COUT = 100 pF commun et conditions générales conservés. |
| H08 | `done`, modèle appelé | PASS limite | Maximum demandé non établi ; le passage 60 µs à 10 mV et l'identité LTC1540 sont effectivement publiés et cités. |
| SCAN1_H04 | `done`, déterministe | PASS | Plages et signes fidèles au raster ; les lectures erronées étrangères à la question restent hors de la prose publiée. |
| SCAN2_H07 | `done`, déterministe | FAIL positif | Refus total, sans réparation indue des unités ou conditions OCR ; aucune complétude positive acquise. |
| N_ina226 | `done`, déterministe | PASS | Bus 0–36 V et alimentation simple 2,7–5,5 V distincts ; préfixe INA226 du titre imprimé cité. |
| N_tmp117 | `done`, modèle appelé | FAIL positif, régression | Les deux plages et températures sont exactes ; l'en-tête requis « Supply range » n'est pas publié et la réserve globale est injustifiée. |

**H06 et H08 sont des gains constatés dans de nouvelles exécutions natives.**
H06 cite le header et les deux configurations avec leurs signes, en
15 292,33 ms par la route déterministe. H08 comporte réellement `llm.request`
et `llm.response`, en 117 959,11 ms. Son texte final indique que la borne
demandée n'est pas établie, puis cite « 60µs Propagation Delay with 10mV
Overdrive » avec LTC1540. Il ne présente ni ce délai comme maximum garanti,
ni une transposition à 1 mV. Ces observations ne sont pas les sélections
simulées des rejeux de diagnostic, qui restent conservés séparément.

**TMP117 est un échec documentaire malgré des nombres exacts.** Les deux
citations finales donnent 1,7–5,5 V pour −55 à 70 °C et 1,8–5,5 V pour
−55 à 150 °C. Le parent « Supply range » est livré dans S006, mais absent
du texte final ; sa conservation est requise par le plan de revue inchangé.
L'ouverture affirme en outre qu'aucune valeur fiable ne peut être fournie.
Cette réserve n'est pas justifiée par les plages lisibles sur l'original.
La complétude numérique des deux intervalles est donc reconnue séparément
de la complétude avec le contexte requis et du succès strict, tous deux en
échec. La requête appelle réellement le modèle, termine en 78 212,40 ms,
et son diagnostic produit reste `partial`, avec **0/1 obligation couverte**.
Le verdict documentaire ne se déduit pas de ce diagnostic : il repose sur
les omissions et la réserve effectivement publiées.

Cette régression avait été identifiée avant le gel. Le titre TMP117 n'obtient
pas l'autorité exigée par le mécanisme actuel, car d'autres blocs typés corps,
issus du bandeau de navigation et de la ligne de révision, le précèdent. La
revue de l'original identifie notamment un pictogramme de navigation lu par OCR
comme « [à] » ; elle n'autorise aucune exclusion générale de ces blocs. Le
premier item TMP117 des caractéristiques est un frère, sans relation persistée
de parent introducteur des plages. Aucun retour au nom du fichier, aucune
exemption de révision et aucun nouveau lien par simple voisinage n'ont été
introduits pour faire réussir ce cas. Le PASS primaire de phase 7 et les
rejeux négatifs restent visibles.

| Indicateur PDF | Candidat phase 7 | Candidat phase 8 |
| --- | --- | --- |
| Cas relus | 12/12 | 12/12 |
| Positifs strictement réussis | 8/10 | 8/10 |
| Positifs complets avec contexte requis | 8/10 | 8/10 |
| Limites strictement réussies | 1/2 | 2/2 |
| Erreurs techniques | 0/12 | 0/12 |
| Refus totaux sur des positifs | 2/10 | 1/10 : SCAN2_H07 |
| Réserves globales injustifiées | 1/12 : H06 | 1/12 : N_tmp117 |
| Échecs stricts conservés | H06, H08, SCAN2_H07 | SCAN2_H07, N_tmp117 |

Les **29 marqueurs publiés** renvoient à **120/120 occurrences de blocs
exactes** ; les **474/474 occurrences livrées** satisfont les contrôles
littéraux, d'identité et de périmètre. Les onze réponses contenant des faits
documentaires ne publient pas de nombre ou de condition contraire à l'original.
La réserve TMP117 reste un défaut distinct ; ces contrôles de fidélité ne
compensent aucune omission. Les **12 textes finaux sont identiques à leurs
deltas publics**, après plan et support validés. Les **158 événements de
progression structurée** sont comptés séparément. Neuf routes sont déterministes ;
H03, H08 et TMP117 comportent les deux phases réelles du modèle. Ces mesures
uniques ne démontrent pas un gain causal de vitesse.

Le reçu final `development-phase8-independent-review-r04.json`, SHA-256
`f1e404e764d6cb3211d60bd0819c2b79e019f3ab21749ac4bf99e2728c86cc34`,
conserve les réponses intégrales et tous les contrôles. Les reçus r01–r03 et
ceux des phases précédentes ne sont pas réécrits. L'abstention sûre de SCAN2
ne clôt toujours pas I5-D04 ; la non-régression TI complète n'est pas satisfaite.

## 5. Sources primaires et traçabilité

- [AD22103, Analog Devices, révision B](https://www.analog.com/media/en/technical-documentation/data-sheets/AD22103.pdf) : description p. 1 ; tableau et conditions p. 2.
- [AD22105, Analog Devices, révision A](https://www.analog.com/media/en/technical-documentation/data-sheets/ad22105.pdf) : caractéristiques et description p. 1.
- [LTC1540, Analog Devices, révision B](https://www.analog.com/media/en/technical-documentation/data-sheets/1540fb.pdf) : description et caractéristiques p. 1 ; tableau électrique p. 3.
- [INA226, Texas Instruments, SBOS547C, août 2026](https://www.ti.com/lit/ds/symlink/ina226.pdf) : caractéristiques et description p. 1.
- [TMP117, Texas Instruments, SNOSD82D, septembre 2022](https://www.ti.com/lit/ds/symlink/tmp117.pdf) : liste des plages d'alimentation et températures p. 1.
- [Manifest des originaux](production-i4-corpus/sources.json), [oracles gelés](production-i4-corpus/questions-oracles.json) et [transformations des scans](production-i4-corpus/scan-transformations.json). Les empreintes des fichiers locaux, et non une future version des URL, fixent les sources effectivement relues.

| Source TI contrôlée | SHA-256 de l'original |
| --- | --- |
| `ina226.pdf` | `c9b67f886d4a5241a5e070723f7b61867409eeb27eed768b9cdd9cb17e03ca2d` |
| `tmp117.pdf` | `78212e91e478035a91165397a8de8a90bfc776759dc445243c033537f0c4b789` |

La référence exécutée est le commit
`41857e17a438fe43123e4ef8274d9d2d446bfbc2`. Les manifestes de code des quatre
blocs ont le même SHA-256
`f70922b69455d738a527ddbe4dab085163c56143ac3493d4fd41e4cc27dfab5e`.
Les fichiers de mesure sont nommés `Hxx-baseline-0.json`, dans les répertoires
privés `development-transfer-a-baseline-queries-5/measurements` pour H01–H04
et `development-transfer-b-baseline-queries-5/measurements` pour H05–H08.
Les mesures `SCAN1_H04-baseline-0.json` et `SCAN2_H07-baseline-0.json` sont dans
`development-ocr-baseline-queries-5/measurements`.
Les mesures `N_ina226-baseline-0.json` et `N_tmp117-baseline-0.json` sont dans
`development-ti-baseline-queries-5/measurements`.

Le candidat A est identifié par le manifest
`3508213ceebbef3bfeb20f931f8c1100c1d276eccfdeb2d946694e32a6f4a621`,
de type `working_source_files_before_first_query` : 84 fichiers, archive SHA-256
`b69aa7a751e5d57309c3da12b06045997c4f1389b54c9109627275ef7078fc94`.
Le HEAD de départ est le même commit que la référence ; ce candidat est une
copie du travail en cours, pas un nouveau commit publié. Ses quatre mesures sont
dans `development-transfer-a-candidate-queries-5/measurements`.

| Reçu privé sous `.runtime/qa/production-i5-20261108/` | SHA-256 |
| --- | --- |
| `development-phase5-independent-review-plan.json` | `895385bb0a8ac1a57ec4a8d4dcdaa25c79d3e849480ab6ecea1b504bee3083f0` |
| `development-phase5-independent-review-r01.json` | `b411017ca0e118ba923f2ff21be4386a2972d3b5684498a18c3244011e516434` |
| `development-phase5-independent-review-r02.json` | `b97f3ca3006c3a687d8061faed9988697ed96831991156fd41ec78c742f5569a` |
| `development-phase5-independent-review-r03.json` | `61165018a2f1fbe7ad69dbd11221ac032033bc5b7bdae9adc1aecdf3e9074b66` |
| `development-phase5-independent-review-r04.json` | `dfe285d79a573caaa0ee99526587b88edd5adb473b19e82c6fb1a02987229790` |
| `development-phase5-independent-review-r05.json` | `58e16e6fb94190dd9e8f4c70f71d9347f7dda2be61b84ce073dd72f1ac3f1aaa` |
| `development-phase5-independent-review-r06.json` | `90f376ed7fdb7df2fddeff32180c4ea0c41b5f1cb1ba2ff44bb63e9c449147c5` |
| `development-transfer-5-ingestion-review-D01.json` | `a9ab2f5428a3e437389ab0b86a16d2d0b95857c27b3b68136490fb8c521ee578` |
| `development-transfer-5-ingestion-review-D02.json` | `2c6c2927d033bdc5f8ae4a519aca7d0b9f3a0518a79c837074342c22a0803550` |
| `development-transfer-5-ingestion-review-D03.json` | `8a73857d3f4be231eb3bd5aec9838c2a78da6a7b3e25ddb182c6047b01d74435` |
| `development-ocr-5-ingestion-review-r01.json` | `dc55dfb19afdfbe9e9b2034719071b127a4e515ac9bae7726daf258bd85ba87c` |
| `scan2-segmentation-probe-plan-r01.json` | `0d5d4040a1f376e6610e711c1d84fd18c54a7a315d72bb8fe774cf7dd5dfa7a2` |
| `scan2-segmentation-probe-r01/receipt.json` | `40ffb621be1dbdcd270dc10217148fc85789d6387fb8a3abb62e5c73b4862425` |
| `general-condition-lines-development-replay-r01.json` | `5de044b82762e776eb631fa14ab67ef25bb1115fa8efcbc6c67af10ad0462f87` |
| `diagnostic-snapshot-6.json` | `f6c39760709a5bdb1cd454f9a99ba850d472583e6000f396e7c9b9ee8b293690` |
| `development-candidate-plan-6.json` | `a737527139241f525646ac4c463d6f40530858906590352777d4ebe56bde23fb` |
| `development-phase6-independent-review-plan.json` | `ac16f42419aa209474aa31f5ac1c1cf86e98e2a663562ed6868154d58c0cfbe9` |
| `development-phase6-independent-review-r01.json` | `2a2464bad143bae06ff59bd4c8babf48fea63b24522cf864d6dbcdbfa5fff6d3` |
| `development-phase6-independent-review-r02.json` | `8d5092b7837ce4a75a59cd9d9c5a7a896966660ba76eb0a90478133bf8194458` |
| `development-phase6-independent-review-r03.json` | `630d2dc64bfb1e62e7242e9a09b3975c91d64d6d309136c4e745673fe93706e0` |
| `development-transfer-6-ingestion-review-r02.json` | `019216a6568f2a3315843b22c2f9ae0f42abf55d4a8c448f3341cfc5985c75cb` |
| `development-ocr-6-ingestion-review-r01.json` | `2f3091f55a73ff6d0b33ccd63cfcfba076a3be7be6b938f785435b44d9a97fbe` |
| `development-ti-6-ingestion-review-r01.json` | `373fda351fe950063d91ad897f43ed7de8992801c17e387272e13a4bea7b0829` |
| `diagnostic-snapshot-7.json` | `d496b48fc8b4119b9ff7cdd6b1e4960d84dd6b7bf3ffdfa1c16bf1e89a6539df` |
| `development-candidate-plan-7.json` | `15c4c00a40ebbb8e5fc67d138f25ae18ee21c8b99be10c206529448a44bea927` |
| `development-input-evidence-7.json` | `837106d71cccb88ffb0647f9c614f773bfe3083146f049d4445fe9a4472b5d7c` |
| `development-phase7-independent-review-plan.json` | `a20e608508683249bbcadec68165a34d6274dca867ce3920eaa6e4c7ba812e5c` |
| `development-phase7-independent-review-r01.json` | `e04e1585ddb34f298c917bc09388ea41a9f54e7588fdc4f8ce6cd58f43f9101b` |
| `development-phase7-independent-review-r02.json` | `ec2253e33c49263dbc1afa44a8fc07b19deb6fd1e2c7b484a8ae8f24f1b17169` |
| `development-phase7-independent-review-r03.json` | `f7c335d692308899b320770d222fcfc09f0a8ed10c5ba0d36a181de9763ea3cd` |
| `diagnostic-snapshot-8.json` | `1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b` |
| `development-candidate-plan-8.json` | `0ed26792f303db5785cba66871688528ec7a1e53a5b4eeb975435889929e85bb` |
| `development-input-evidence-8.json` | `e8cfde8462a6a9283f3aae0b44bc66e16c5ea6ec10680e99d187c799004e3938` |
| `development-phase8-independent-review-plan.json` | `142b3e9e30da00a6bb0a3149aa8896a1a73f806b9ff37ddf7602f0f5160175c5` |
| `development-phase8-independent-review-r01.json` | `42b56334278ab1cc53641a153091a08ee183c82c47bac4798e2bf4c920e10529` |
| `development-phase8-independent-review-r02.json` | `715d796044ba124b7f5222fe7b98b5c4cdf2caa00652a190a60cb4bd866046b1` |
| `development-phase8-independent-review-r03.json` | `bade788321dc4bcd256248cbb76a3568916ef3d2522ade697894c53568d7f096` |
| `development-phase8-independent-review-r04.json` | `f1e404e764d6cb3211d60bd0819c2b79e019f3ab21749ac4bf99e2728c86cc34` |
| `ingestion-prose-page-subject-review-r02.json` | `7810a8695aa1634ccb49fef5243003d4df7346b6eac7176c19400c5a4d23eb47` |
| `tmp117-upper-icon-source-review-r01.json` | `84276a6ee84acf6be9aa95eedfc0f51f20edded459b8ef2af2640bb2cedee6af` |
| `recovery-api/source8-four-case-replay-r01.json` | `4bda707e089c8d356dd4ff1478d67301a654c77375b46bf582615b6f0d8e2ed6` |

Les snapshots antérieurs restent intacts. Le dernier reçu contient les
empreintes individuelles des mesures, réponses, traces, vues originales et
sources ainsi que tous les verdicts. Les 12 réponses documentaires de chacune
des phases 6, 7 et 8 sont entièrement relues. Tout suivi ultérieur conserve ces résultats primaires
et porte son identité de sources, ses exécutions et sa revue propres.
