# Amélioration et qualification du générateur 4B — EV4B

**Rôle :** protocole scientifique, critères d'acceptation et contrat des résultats · **Propriétaire :** intégration et qualification EV4B · **Statut :** protocole établi avant campagne ; résultats natifs `NOT_RUN` à sa création · **Date :** 2026-11-07 (UTC) · **Référence :** `59d47e98a47fc652b5506727673b6b477c92eb9d`, puis modifications locales de `enhanced_version` · **Source de vérité :** ce document pour le protocole ; [PLAN.md](../PLAN.md) pour l'avancement ; les traces et sorties brutes pour les résultats.

## 1. Objet et limites

La demande du 7 novembre porte sur l'implémentation des pistes issues de la
comparaison documentaire antérieure, avec **Qwen3-4B comme seul générateur**.
La branche de travail est `enhanced_version`. Le routage et les essais 8B sont
exclus. Le cas Windows de 16 Go sans GPU reste un exemple d'enveloppe contrainte ;
une mesure sur l'hôte disponible ne qualifie pas automatiquement cet autre poste.

Le document de cadrage fourni rapporte, sur 17 questions renseignables communes,
8 contextes complets, 4 partiels et 5 insuffisants, ainsi que 7 réponses 4B
entièrement exactes et soutenues. Ces nombres sont **une référence historique
rapportée**, pas une mesure réexécutée par EV4B. La perte du zéro dans la sélection
Excel `A5:F6`, l'omission de 36 et la confusion entre conditions de courbe et
limites admissibles motivent les régressions ciblées.

Une réponse est évaluée à trois niveaux distincts : conservation des faits dans
le contexte, exactitude et complétude de la réponse, soutien par les citations.
La recherche hybride et la restitution structurée existent dans la base ; leur
seule présence n'est pas une amélioration nouvelle.

## 2. Objectifs et hypothèses

| Identifiant | Hypothèse testable | Observation attendue pour conclure |
|---|---|---|
| H1 | Des preuves qui conservent les relations valeur–grandeur–unité–condition réduisent la perte documentaire. | Couverture des faits plus élevée à budget comparable ; aucune extension silencieuse du périmètre. |
| H2 | Le contrôle des faits demandés réduit les réponses erronées ou incomplètes du même 4B. | Gain sur des questions appariées, avec couverture de réponse et abstentions publiées ; aucune conclusion favorable si seul le taux de refus augmente. |
| H3 | Une trace prise au passage réel rend les expériences rejouables. | Identité des entrées et options contrôlable ; répétitions à configuration fixe mesurées, sans promesse d'identité intermatériel. |
| H4 | Le choix conjoint du contexte et de la résidence améliore la continuité sous contrainte. | Qualité, mémoire de la chaîne et latence mesurées sur des séquences complètes ; allocations KV théoriques séparées des mesures. |

Les hypothèses peuvent être infirmées. Aucun seuil de gain ni score de qualité
n'est inventé pour fermer le chantier. La réception technique exige des
invariants vérifiés ; une conclusion scientifique favorable exige les mesures
comparatives qui la soutiennent.

## 3. Definition of Done du chantier

Ces critères complètent les D04/D05/D07/D10 du référentiel existant et ne ferment
pas à eux seuls la qualification métier ou toutes les plateformes du projet.

| Action | Réception technique | Preuve nécessaire et limite |
|---|---|---|
| EV4B-01 — Graine et identité | La graine, dont zéro, et les options sélectionnées atteignent le moteur. Version, modèle, poids, tokenizer/gabarit disponibles sont identifiés. | Test de contrat et capture native ; une option YAML seule ne prouve pas son application. |
| EV4B-02 — Traces et rejeu | Sources, identité d'extraction, candidats, contexte ordonné, requête native et événements sont capturés au passage réel, sous limites de taille. | Rejeu à contexte figé ; hash incompatible refusé ; erreur/annulation conservée. Aucun second retrieval destiné à reconstruire la trace. |
| EV4B-03 — Preuves structurées | Valeurs, unités, rôles, conditions et provenance restent associés. La petite plage autorisée conserve ses cellules utiles, notamment 0 et 36. | Régressions Excel et tableaux ; entête hors périmètre signalé, jamais importé silencieusement. |
| EV4B-04 — OCR ciblé | Brut, région, lecture candidate et validation restent distincts. Reprise régionale bornée, ambiguïté non résolue conservée. | Cas `OV`/`0 V`, O dans une référence, signe moins, colonnes ; une correction inférée par le générateur ne vaut pas OCR. |
| EV4B-05 — Suffisance et sélection | Le système distingue fait retrouvé, incomplet, ambigu et contradictoire pour ses familles prises en charge. Sélection et coûts plafonnés. | Faits tracés dans extraction, candidats et contexte ; classement structurel comparé à candidats identiques. |
| EV4B-06 — Contrôle de réponse | La validation reçoit la question ou son contrat de faits. Valeur, intervalle, comparaison, configuration/code et calcul sont contrôlés dans leur domaine explicite. | Borne manquante, mauvaise grandeur, composant omis, référence existante mais non probante, JSON invalide. Aucune garantie sémantique générale déduite de règles lexicales. |
| EV4B-07 — Calculs | Les calculs simples conservent entrées, unités, opération et références ; les cas invalides sont refusés. | Zéro, signes, unités incompatibles, division par zéro, formule sans résultat calculé, arrondi. |
| EV4B-08 — Reprise bornée | Au plus une récupération complémentaire utile, dans le périmètre et les budgets. Puis réponse établie, partielle ou abstention motivée. | Budget épuisé, reprise sans nouvelle preuve, OCR impossible, contradiction persistante. |
| EV4B-09 — Contexte et KV | Budget de toutes les composantes du prompt et sortie réservée ; variantes KV observées dans le moteur. | Prompts identiques pour isoler le KV ; poids Q4_K_M distincts du cache FP16/q8_0/q4_0. |
| EV4B-10 — Résidence | Politiques conserver/décharger/adaptative et admission exerçables sur des transitions successives. | Extraction → recherche → génération → recherche ; refus, reprise, annulation, modèle résident mais marge insuffisante. |
| EV4B-11 — Évaluation | Annotations, dénominateurs, hashes, appariements et répétitions vérifiables ; jugements non effectués conservés comme inconnus. | Outil d'analyse indépendant du modèle, tests de cohérence et rapport relié aux données brutes. |
| EV4B-12 — Livraison | Diff relu, régressions expliquées, résultats et réserves consignés, commit/push vérifiés sur `enhanced_version`. | Aucun modèle, secret ou corpus lourd dans Git ; branche distante et SHA confirmés. |

Chaque ligne reste ouverte dans le plan tant que son critère exact n'est pas
satisfait. « Implémenté », « testé avec doubles », « exécuté nativement » et
« qualifié sur la cible » sont des états différents.

## 4. Corpus et référence

1. Conserver les documents historiques comme développement et régression.
2. Associer à chaque question le document, sa famille/révision, le périmètre,
   l'état renseignable, les faits obligatoires, leurs unités/conditions et les
   références de preuve. Hacher les sources et conserver l'identité d'extraction.
3. Réserver un jeu distinct par famille documentaire si disponible. Une nouvelle
   question sur le même document n'est pas une validation documentaire indépendante.
4. Enregistrer la méthode de jugement : expert humain, lecture par l'agent, règle
   déterministe ou non relu. Ne jamais présenter une annotation de l'agent comme
   une validation humaine. Une occurrence de nombre ne prouve pas sa signification.
5. Garder séparés le contexte fourni par le produit et un contexte vérifié
   manuellement. Ce dernier est un diagnostic de génération, pas un score du produit.

L'objectif d'extension de 100–200 questions dans le cadrage n'établit ni une
puissance statistique ni un dénominateur acquis. Le nombre effectivement exécuté,
les documents indépendants et les exclusions sont publiés. Les répétitions d'une
question évaluent sa stabilité ; elles ne créent pas de nouvelles questions.

## 5. Comparaisons et ordre d'exécution

Avant le premier essai, consigner le commit de base, le diff local, l'hôte,
l'enveloppe mémoire, les versions, les poids et leurs hashes, le tokenizer,
le gabarit, les options, les documents et l'identité de l'index. Préserver les
extractions valides ; ne pas déclencher une nouvelle ingestion pour une différence
de chemin si les identités n'ont pas été établies.

| Comparaison | Éléments constants | Variable étudiée |
|---|---|---|
| Extraction initiale / reprise ciblée | Région, document, question | Lecture et conservation des relations |
| Sélection actuelle / preuves structurées | Candidats, question, budget | Composition et ordre du contexte |
| Contexte retrouvé / contexte vérifié | 4B, options et budget comparable | Part imputable à la recherche |
| Réponse actuelle / contrôle des faits | **Même contexte exact** | Validation et rendu |
| FP16 / q8_0 / q4_0 | **Même requête tenant dans toutes les configurations** | Précision du cache KV |
| Contexte 8192 / 4096 | Documents, question, 4B et options de décodage | Budget et conservation des preuves |
| Conserver / décharger / adaptative | Séquence documentaire identique | Résidence et coût des transitions |
| Collecte minimale / complète | Entrées et paramètres identiques | Coût de l'instrumentation |

La référence instrumentée peut utiliser l'ancienne sélection avec la graine et
la capture corrigées communes aux deux variantes. Elle doit alors être appelée
« référence instrumentée », pas « commit historique inchangé ».

Les variantes sont alternées par blocs de questions, ou leur ordre est tiré avec
une graine enregistrée. Aucune concurrence de tâches lourdes sur le moteur ou
l'index partagé. Les erreurs, refus et interruptions restent dans la campagne.
Une reprise reçoit une nouvelle identité et ne remplace pas son échec initial.

Un essai « modèle déchargé » conserve potentiellement les caches de fichiers du
système. Décrire cet état sans le nommer « cache froid » intégral. Un format KV
non disponible est `NOT_RUN` ou refusé, jamais assimilé au format demandé.

## 6. Mesures et règles de calcul

| Mesure | Numérateur et dénominateur |
|---|---|
| Service | Positions prévues, soumissions, réponses terminées, refus, erreurs, annulations et non-exécutées séparés. |
| Réponse complète confirmée | Questions renseignables avec tous les faits exacts et sans affirmation fausse supplémentaire / soumissions renseignables. Les non-relues ne sont pas déclarées exactes et leur nombre reste visible. |
| Exactitude des réponses relues | Réponses entièrement exactes / réponses renseignables effectivement publiées et jugées. Ne pas confondre avec le rendement précédent. |
| Citations | Faits requis soutenus et absence d'affirmation supplémentaire non soutenue. Les faits non jugés restent inconnus ; intégrité d'identifiants distincte de soutien sémantique. |
| Couverture des preuves | Faits présents dans le contexte / faits requis jugés, avec le total des faits requis et les non-jugés ; publier aussi le rapport confirmé/total. |
| Risque et couverture | Erreurs parmi les réponses publiées et jugées, avec proportion de soumissions donnant une réponse. Une politique qui s'abstient davantage est visible. |
| Stabilité | Questions répétées, états identiques, réponses identiques, identité des requêtes. Les échecs ne sont pas supprimés du contrôle de stabilité. |
| Ressources | Latences totale et par phase, chargements inclus ; mémoire avec périmètre de mesure explicite et nombre de relevés. Une RSS d'Ollama seule ne représente pas la chaîne. |

Pour la comparaison appariée, calculer d'abord le résultat moyen des répétitions
communes de chaque question. L'estimation principale donne ensuite le même poids
à chaque question ; le nombre de répétitions n'augmente pas son poids. Les
intervalles exploratoires rééchantillonnent les **familles documentaires** avec
remise, en conservant toutes leurs questions et les paires. La méthode, la graine,
le nombre de tirages et le nombre de familles sont enregistrés. Un seul groupe ne
permet pas de fournir cet intervalle ; peu de familles ne justifient pas une
conclusion de généralisation. Le percentile est une approximation descriptive,
pas un test de significativité ni une méthode BCa.

Un score de sélection sert seulement à ordonner les décisions : ce n'est pas une
probabilité calibrée. La courbe risque–couverture ne coupe pas arbitrairement un
groupe de scores ex æquo et publie les données non jugées/non scorées exclues.

## 7. Contrat JSONL de la campagne

L'outil [enhanced_eval.py](../../tools/qualification/enhanced_eval.py) lit les
annotations et les exécutions. Il ne lance ni API, ni recherche, ni génération et
ne juge pas automatiquement la sémantique des réponses.

Annotation minimale, une ligne JSON par question :

```json
{"question_id":"Q01","document_id":"doc-a","family_id":"family-a","split":"regression","question":"Quelle plage de tension ?","answerable":true,"required_facts":[{"id":"min","description":"borne inférieure et unité","references":["table 2, colonne min"]},{"id":"max","description":"borne supérieure et unité","references":["table 2, colonne max"]}]}
```

Exécution jugée ; une nouvelle répétition change `repeat`, une reprise conserve
l'échec antérieur et peut employer une variante identifiant cette reprise :

```json
{"question_id":"Q01","variant":"enhanced","repeat":0,"status":"completed","answer":"Exemple à remplacer par la réponse observée.","abstained":false,"fact_verdicts":{"min":{"correct":true,"citation_supported":true,"in_context":true},"max":{"correct":false,"citation_supported":null,"in_context":true}},"has_false_claims":false,"has_unsupported_claims":null,"judgment":{"method":"agent","reviewer":"lecture documentée","notes":"Borne supérieure omise."},"latency_s":null,"memory_peak_mib":null}
```

Les booléens de jugement sont `true`, `false` ou `null`. Une omission établie est
`correct:false` ; une absence de relecture est `null`. `has_false_claims` et
`has_unsupported_claims` portent sur **toute la réponse**, y compris les ajouts.
Pour `completed`, `answer` et `abstained` sont obligatoires. Les autres états sont
`refused`, `error`, `cancelled` et `not_run`.

Les champs facultatifs `request`, `request_sha256`, `prompt`, `prompt_sha256`,
`context`, `context_sha256`, `source_sha256` et `selection_score` portent les
preuves disponibles. Un hash JSON utilise UTF-8, clés triées, séparateurs compacts,
Unicode préservé et aucun NaN ; l'ordre des listes et le contenu des chaînes sont
conservés. C'est l'identité du **JSON canonique**, pas celle des octets HTTP, du
gabarit caché ou des tokens internes. Un hash fourni avec son contenu est vérifié.
Un hash seul ne prouve pas que le contenu a été capturé nativement.

```bash
python tools/qualification/enhanced_eval.py \
  --annotations .runtime/qa/ev4b/annotations.jsonl \
  --runs .runtime/qa/ev4b/runs.jsonl \
  --baseline baseline --output .runtime/qa/ev4b/summary.json
```

Pour une ablation à preuves identiques, ajouter `--require-same-context` ; pour
les mêmes messages, `--require-same-prompt`. Ces contrôles refusent les paires
sans empreinte ou avec une empreinte différente. Les erreurs de format,
doublons, valeurs non finies et fuites de familles entre développement et holdout
sont des erreurs de données, pas des résultats du générateur.

## 8. Fondement documentaire et portée

Les références primaires ont été consultées le 7 novembre 2026 ; leurs scores
ne sont pas transposés au 4B ni au corpus local. Registre : [SOURCES.md](../SOURCES.md),
entrées EV4B-S01 à EV4B-S05.

- [Sufficient Context](https://arxiv.org/abs/2411.06037v3) motive la séparation entre insuffisance du contexte et mauvaise exploitation de preuves suffisantes.
- [ALCE](https://aclanthology.org/2023.emnlp-main.398/) motive la séparation entre justesse et qualité des citations.
- [Selective Question Answering under Domain Shift](https://aclanthology.org/2020.acl-main.503/) motive la mesure conjointe du risque et de la couverture, sans assimiler un score brut à une probabilité de justesse.
- [ARES](https://aclanthology.org/2024.naacl-long.20/) distingue pertinence du contexte, fidélité et pertinence de la réponse ; sa calibration humaine ne doit pas être revendiquée ici sans annotations humaines.
- [Documentation bootstrap de SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) décrit rééchantillonnage, appariement et intervalles. Le regroupement par famille et l'implémentation stdlib d'EV4B sont des choix explicites du protocole ; SciPy n'est pas ajouté aux dépendances.

## 9. Résultats et clôture

**État initial : `NOT_RUN`.** Les [premiers résultats OCR](enhanced-4b-ocr-2026-11-07.md)
consignent ensuite une absence de récupération du zéro et les contrôles acquis.
Les autres exécutions et réserves sont ajoutées dans le
[journal du 7 novembre](../journal/2026-11-07.md) et reliées depuis le plan.
Le [bilan EV4B des 7–8 novembre](enhanced-4b-results-2026-11-07.md) rassemble
désormais les exécutions, leurs dénominateurs et leurs réserves, avec la suite du
[journal du 8 novembre](../journal/2026-11-08.md). Ce renvoi ne modifie aucune
exigence ni aucun critère d'acceptation préétabli du présent protocole.
Le rapport final devra indiquer pour chaque critère : implémentation, commande,
preuve, résultat et limite. Les tests de composants, les essais natifs et la
qualité documentaire garderont leurs dénominateurs distincts.
