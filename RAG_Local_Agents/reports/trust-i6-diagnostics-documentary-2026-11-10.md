# R4 — Revue documentaire indépendante des vingt positions natives

**Rôle :** relecture documentaire des réponses et citations R4.
**Propriétaire :** qualification indépendante.
**Statut :** exécuté, verdicts historiques conservés.
**Date :** 10 novembre 2026, UTC.
**Référence :** `0574f4e21ccaf95b25a48c6e226369376681ac18`.
**Candidat :** `522d86839d5c803c57daec0e799bfa48ee5aa8e7`.
**Évaluateur :** agent distinct des auteurs ; aucune validation humaine ou experte revendiquée.

La revue des dix questions natives connues, exécutées une fois par bras, donne
**3/10 conformes au critère documentaire strict pour la référence et 10/10 pour
le candidat**. Les sept différences correspondent aux diagnostics et aux
métadonnées visés par le protocole. Les deux bras préservent les **18 littéraux
requis avec leurs citations**, ainsi que les 16 relations numériques affirmées
correctement attribuées. Aucun nombre nié n'est promu en valeur affirmée, aucune
fausse couverture complète et aucune conclusion comparative interdite ne sont
observés sur ces positions.

Ce résultat porte sur dix questions et vingt positions appariées. Il reste
distinct du nouveau FINAL I6R06, dont le résultat définitif est 39/48 contre
47/48, et du nouveau final I7 fermé. Il ne requalifie aucune campagne historique.

## Critères et preuves

Les critères ont été consignés avant lecture des réponses R4 dans
`native-review-criteria.json`, SHA256
`286d9690b6612b928de65ed73bf4cffa1bd08a615582e2017a4cc71f71bea37c`.
Ils reprennent les annotations des entrées natives gelées, complétées par les
critères I6 déjà définis : propriété/rôle locaux des relations rejetées,
absence de condition commune inventée, et propriété manquante nommée dans les
passages retenus. Aucun seuil ni verdict attendu n'a été changé après lecture.

Le présent jugement repose sur la lecture de chaque réponse réellement publiée,
des relations admises et rejetées, des comparaisons et de leurs références.
Le statut du contrat ne suffit pas à décider de la conformité : plusieurs
réponses de référence ont un statut partiel ou conflit correct tout en manquant
le critère de diagnostic ou de métadonnées.

Les 15 originaux pertinents sont à nouveau contrôlés par SHA256. Les paragraphes
des 13 DOCX sont relus directement dans l'OOXML. Pour les deux PDF, le contrôle
emploie l'original hashé et son extraction antérieure dont l'identité avait été
vérifiée ; aucun nouveau moteur d'extraction n'est exécuté. Chaque littéral est
relié au document et à la version réellement cités. Les empreintes de blocs,
offsets, marqueurs et précision des localisateurs sont contrôlés. Les DOCX
conservent une précision d'élément et une page inconnue ; les PDF citent leur
page réelle. Les deltas persistés reconstruisent exactement la réponse publiée
sur les vingt positions.

Le JSON détaillé `native-r4-documentary-review.json`, SHA256
`0319f8015795eb511746e25edcda01d04568d32850c771aa27896199649af620`,
conserve les vingt textes, les jugements motivés, les faits lus, les contrôles
de citations et les chemins/empreintes des mesures, traces, bindings et
readbacks techniques. `build_native_r4_review.py` consigne les jugements de
lecture et reproduit les vérifications de données sans importer le produit.

## Résultats par groupe et par bras

Le critère strict associe fidélité du texte et du diagnostic, métadonnées
locales, provenance des citations et présence effective de la réponse.
L'intégrité du nouveau registre rendu est rapportée séparément pour ne pas
pénaliser artificiellement son absence historique dans la référence.

| Groupe | Questions par bras | Strict référence | Strict candidat | Texte/diagnostic référence → candidat | Métadonnées référence → candidat | Littéraux cités référence → candidat |
|---|---:|---:|---:|---:|---:|---:|
| Six régressions originales | 6 | 2/6 | 6/6 | 4/6 → 6/6 | 4/6 → 6/6 | 13/13 → 13/13 |
| Sélection réelle, deux questions | 2 | 0/2 | 2/2 | 0/2 → 2/2 | 2/2 → 2/2 | 2/2 → 2/2 |
| HTTP, conflit explicite | 1 | 1/1 | 1/1 | 1/1 → 1/1 | 1/1 → 1/1 | 2/2 → 2/2 |
| HTTP, sélection réelle | 1 | 0/1 | 1/1 | 0/1 → 1/1 | 1/1 → 1/1 | 1/1 → 1/1 |
| **Total** | **10** | **3/10** | **10/10** | **5/10 → 10/10** | **8/10 → 10/10** | **18/18 → 18/18** |

Les deux erreurs de métadonnées et les cinq erreurs de texte/diagnostic
concernent des positions différentes. Cela explique que le strict de la
référence soit 3/10 alors que le texte seul est conforme sur 5/10.

| Contrôle atomique | Référence | Candidat |
|---|---:|---:|
| Relations numériques affirmées, exactes et attribuées | 16/16 | 16/16 |
| Relations numériques rejetées pour négation | 2 | 2 |
| Erreurs de métadonnées parmi les deux rejets ciblés | 2/2 | 0/2 |
| Diagnostics ciblés conformes | 0/5 | 5/5 |
| Littéraux et citations liés au bon document/version | 18/18 | 18/18 |
| Positions avec citations conformes | 10/10 | 10/10 |
| Faux complets | 0 | 0 |
| Opérandes niés affirmés | 0 | 0 |
| Conclusions comparatives interdites | 0 | 0 |
| Positions manquantes ou en erreur | 0 | 0 |

## Ce que montrent les dix paires

| Question | Référence | Candidat | Lecture documentaire |
|---|---|---|---|
| N_I6D28 | Échec métadonnées | Conforme | Le refus dominant reste visible dans les deux bras. La tension nominale rejetée hérite à tort de la propriété « sortie » dans la référence. Le candidat conserve `property=null` et `role=nominal`. |
| N_I6D32 | Échec métadonnées | Conforme | Aucun courant n'est affirmé et la négation est préservée. La référence emprunte le rôle nominal à la tension coordonnée ; le candidat conserve `property=output` et `role=null`. |
| N_I6D33 | Conforme | Conforme | Deux PDF établissent la même valeur nominale pour deux sujets. Chaque opérande est lié à son sujet et à sa source ; aucune condition d'essai supplémentaire ni indépendance documentaire n'est inférée. |
| N_I6D35 | Conforme | Conforme | Deux paragraphes du même DOCX suffisent à comparer deux sujets. Les citations restent correctes malgré l'ordre de leurs identifiants ; le rendu n'exige pas deux documents distincts. |
| N_I6D45 | Échec diagnostic | Conforme | Les trois valeurs concurrentes sont fidèles dans les deux bras, sans arbitrage ni comparaison interdite. La référence affirme une condition commune absente ; le candidat se limite à la concurrence des valeurs. |
| N_I6D48 | Échec diagnostic | Conforme | Les quatre valeurs inversées entre sujets et documents restent correctement attribuées. Les divergences par sujet sont permises. Le candidat supprime l'affirmation d'une condition commune non documentée. |
| I6S01 | Échec diagnostic | Conforme | Le bus RX742 1–26 V reste exact. Le candidat nomme la plage d'alimentation manquante dans les passages retenus ; la référence donne seulement un avertissement générique. |
| I6S02 | Échec diagnostic | Conforme | Même distinction pour KX563 2–27 V. La propriété absente est explicitée sans transformer le bus en preuve d'alimentation. |
| HTTP01 | Conforme | Conforme | Les sources donnent réellement 2.8 et 3.2 V à 70 °C. La référence ne fabrique donc pas la condition dans ce cas. Les deux bras exposent le conflit sans arbitrage et réservent les rôles non établis. |
| HTTP_I6S01 | Échec diagnostic | Conforme | A établit le bus HX864 3–29 V ; B ne donne qu'un identifiant. Le candidat nomme l'alimentation manquante de A et les deux propriétés absentes de B. L'ancienne réponse n'intègre pas le remplacement 4–31 V. |

Les trois contrôles de sélection ne mesurent pas une nouvelle aptitude du modèle
à rédiger les diagnostics : ils vérifient le chemin réel de sélection puis le
contrat et le rendu appliqués aux preuves retenues. Le texte du diagnostic du
candidat reste en français pour les questions anglaises de ce jeu. Aucune
exigence de traduction automatique n'était incluse dans les critères gelés.

## Chaîne technique et persistance : résultats séparés

Les readbacks techniques R4 rapportent vingt positions conformes aux critères
techniques complémentaires, six échanges réels du modèle au total — trois par
bras — et les dix registres rendus du candidat intégralement vérifiés.
Les six régressions originales et le conflit HTTP suivent la route déterministe
prévue ; l'absence d'appel modèle n'est pas présentée comme une exécution du 4B.

Le verdict historique du harnais HTTP conflit reste **FAIL dans les deux bras**,
car son ancien critère exigeait un échange modèle. La revue documentaire
**PASS** et le readback technique complémentaire **PASS** restent des jugements
séparés ; ils ne réécrivent pas ce verdict historique. Le chemin HTTP de
sélection, qui appelle effectivement le modèle, conserve son verdict historique
PASS dans les deux bras.

Sur les quatre positions HTTP, les citations avant et après remplacement sont
identiques, leurs empreintes originales sont inchangées et l'identité de
document se prolonge vers une nouvelle version. Les citations restent attachées
aux anciennes versions et le texte publié reste celui de la requête initiale.
Les valeurs des remplacements ne sont pas injectées dans cette réponse.

## Portée de la conclusion

Cette recette confirme les corrections ciblées sur ces dix questions natives
connues, avec les sources, moteurs et routes réellement observés. Elle ne
constitue pas un nouveau jeu réservé, un échantillon métier représentatif ou
une évaluation humaine. La lecture indépendante est réalisée par un autre
agent, avec des contrôles de données reproductibles.

Les campagnes ont un seul passage par question et par bras. Leur durée et leurs
pics de ressources restent des observations descriptives à consulter dans le
bilan technique ; aucune généralisation de performance n'est tirée de cette
revue. Les qualifications OCR, corpus métier, Windows, aarch64, installation
neuve et poste physique de 16 Go ne sont pas closes par ces résultats.

Le strict FINAL I6R06 reste immuable à 47/48 pour le candidat. Son F05 demeure
un échec de pertinence d'une relation supplémentaire, sans invention numérique,
et devient seulement un cas de développement connu de la nouvelle itération
I7. Les dénominateurs de ces trois preuves restent distincts.
