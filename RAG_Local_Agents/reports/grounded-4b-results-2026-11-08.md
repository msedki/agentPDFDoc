# I3 — fiabilisation du RAG jusqu'à la réponse, 4B uniquement

**Rôle :** bilan des modifications et essais I3. **Propriétaire :** intégration RAG.
**Date :** 8 novembre 2026 (UTC). **Branche :** `enhanced_version`.
**Référence exécutée :** `3956491a2d7f1f16cefebfe79e92c638b6662c10`.
**Conclusion :** améliorations implémentées et contrôles logiciels exécutés ;
**qualification native I3-D08 non acquise**. Les échecs mémoire de la campagne
primaire et les réponses PDF incomplètes restent au bilan.

Le [protocole initial](grounded-4b-protocol-2026-11-08.md) précède les changements
produit. L'[addendum F07](grounded-4b-addendum-2026-11-08.md) précède le repli
bilingue et la correction de la grandeur principale. La
[procédure de reproduction](grounded-4b-reproduce-2026-11-08.md) fournit les
commandes. La DoD I3 complète ne se déduit ni d'un taux de terminaison ni d'une
matrice synthétique entièrement réussie.

## 1. Défauts, corrections et frontières de responsabilité

| Défaut constaté | Modification et effet vérifiable |
|---|---|
| Passages distincts perdus lorsqu'un parent long n'est pas développé | Identité des occurrences fondée sur génération, blocs et offsets. Déduplication exacte après expansion ; les positions, documents, versions et conditions distinctes restent distincts. Plafonds inchangés. |
| Note d'un tableau perdue ou provenance OCR incomplète | Conservation des notes explicitement liées, y compris chaînes bornées ; notes absentes, ambiguës ou scan incomplet signalés. Méthodes d'extraction recalculées sur tous les blocs effectivement retenus. |
| Extraction partielle invisible lorsque la recherche est vide | Avertissement construit sur les générations autorisées, avec document, version et révision d'extraction. L'absence de résultat ne devient pas une absence dans l'original. |
| Nombre reconnu sans son rôle, sa polarité ou sa condition | Contrôles locaux de condition, négation, incertitude, borne maximum/typique et divergence documentaire. Pas de priorité de version ou de vérité supposée entre sources contradictoires. |
| Citation présente mais lien à l'affirmation non contrôlé jusqu'à la fin | Registre préalable de références/relations, puis reconstruction des segments et contrôle juste avant l'événement public. Texte, citations, calculs et messages de limitation sont vérifiés. |
| Deux recherches françaises vides sur passages anglais | Repli FTS activable, au plus 16 alias techniques existants, une seule reprise lorsque les listes lexicale et exacte sont vides, même scope et plafond. Aucun changement de la question ou de l'entrée dense. |
| Condition thermique confondue avec grandeur demandée ou assertion voisine | Grammaire bornée distinguant la plage d'alimentation de ses conditions explicitement attachées. Une température de stockage voisine, une condition absente ou qualitative non reconnue n'établit pas la relation demandée. |
| Taille du générateur seulement implicite dans son alias | Vérification du manifeste, digest, Q4_K_M, famille `qwen3` et taille `4.0B`, à froid comme à chaud, avant envoi documentaire. |

L'ingestion native Office, l'indexation SQLite/FTS et Qdrant, les scopes et les
originaux restent les couches existantes. Ce lot corrige la conservation et
l'exploitation de leurs preuves ; il ne remplace pas les parseurs ni ne prétend
avoir réparé la lecture de tout PDF. Les tests de documents endommagés, erreurs
de lecture, champs incomplets, formules sans cache et budgets sont distingués
des mesures du modèle réel.

### Avant et après génération

Le générateur reçoit un catalogue de références autorisées et produit uniquement
un plan JSON : IDs à restituer et groupes à rapprocher. Aucun champ de texte
libre, chiffre, explication ou calcul généré n'est admis. Le serveur restitue les
passages exacts et produit les calculs avec du code déterministe. Pour les
relations explicites déjà entièrement couvertes, le plan peut être constitué
sans appel au générateur ; ces routes sont comptées séparément.

Le registre préalable contient les segments sources, empreintes, localisateurs,
identifiants de document/version/génération/révision, méthode d'extraction,
relations reconnues, rejets et conflits. Une information inconnue reste absente
ou nulle. Les identifiants techniques de version ne deviennent pas des dates
de révision documentaire.

Le registre après restitution découpe la réponse en segments reconstruisibles :
extraits, valeurs de cellule, opérations, comparaisons et notices autorisées.
`verify_rendered()` contrôle texte, hash, provenance, citations, opérations,
couverture et raisons d'abstention avant publication. Une corruption ajoutée
après `render()` est également rejetée. Un plan tronqué ou sans fin vérifiable
ne publie aucun texte dans le profil renforcé. Le transport historique hors de
ce profil conserve son état `length_limited` sans restitution non validée.

**Limite essentielle :** un extrait exact démontre ce que dit la source, pas sa
vérité ni sa pertinence pour toute question imaginable. Le registre conserve
`general_semantic_entailment_verified=false` et
`original_extraction_fidelity_verified=false`. Les relations reconnues sont
locales et bornées. Les questions générales restent des restitutions littérales
signalées comme telles ; elles ne reçoivent pas une certification sémantique.

## 2. Conditions de comparaison

| Élément | Configuration observée |
|---|---|
| Générateur unique | Qwen3-4B, GGUF Q4_K_M, 2 497 280 256 octets |
| SHA du GGUF | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| Moteur | Ollama 0.35.0, CPU, maximum quatre threads, aucun routage 8B |
| Inférence | Contexte 8192, température 0,2, top_p 0,9, seed 0, think désactivé, KV q8_0, flash attention activée |
| Sortie | Maximum du profil 1536 tokens ; route factuelle observée à 768 ; aucun dépassement silencieux admis |
| Résidence | Politique adaptative, keep_alive 10 min ; décisions et mémoire disponibles tracées |
| Recherche native | multilingual-E5-small INT8, Qdrant 1.19.1, SQLite FTS ; verrous de poids conservés |
| Hôte | Linux x86-64, noyau 6.18.57, Python 3.12.14, 10 451 423 232 octets RAM, neuf CPU logiques visibles, aucun swap |
| Dépendances principales | Docling 2.131.0, docling-core 2.99.0, pypdfium2 5.13.0, torch 2.14.0+cpu, ONNX Runtime 1.30.0, tokenizers 0.23.2, httpx 0.28.1, Pydantic 2.13.5 |

Les profils, versions, hashes et sources sont capturés avant chaque bras. La
référence est un worktree immuable, pas un commutateur dans le code corrigé.
Les stores sont isolés ; les originaux, poids et paramètres d'inférence sont
identiques. Les UUID internes et états de cache sont propres aux exécutions et
enregistrés. Une graine fixe ne garantit pas une sortie native identique.

### Corpus et oracles

La matrice contrôlée comporte **12 positifs et 18 limites**, fixés avant ses
sorties, SHA `68a997cee3c6e3dcd1d8625d534c17631cb7ddaebedb1bfd3efa316c678fd476`.
Elle couvre conditions, bornes, zéros, négation, tableaux creux, cellules,
conversions, sommes, formules sans cache, doublons,
contradictions, longue réserve, sources manquantes, portée et plans adverses.
L'extraction Office et la pipeline applicative sont réelles ; embedding, vecteur,
compteur de tokens et sélection générative sont des doubles explicitement nommés.
La division nulle relève des tests de calcul séparés, pas de ces trente cas.

Le sous-ensemble natif réutilise huit de ces questions Office et ajoute deux
questions sur les premières pages des documents TI INA226 et TMP117. Il utilise
les véritables moteurs, tokenizer et poids. Les neuf fichiers Office et les
deux PDF sont identifiés par SHA. Les PDF sont SBOS547C (août 2026) et SNOSD82D
(septembre 2022), dans les octets observés le 8 novembre. Les URL mutables sont
protégées par des SHA attendus dans le préparateur.

**Les PDF sont partiels et dégradés :** seule la page d'index 0 est extraite ;
le contrôle d'ordre vertical n'est pas satisfait. Le bloc conserve ce défaut et
publie explicitement les éléments disponibles en `ready_partial`. Cela ne valide
ni la qualité complète du PDF ni l'OCR. Les originaux ne sont pas modifiés.

## 3. Mesures et résultats

### Matrice contrôlée appariée

Les [observations par cas](grounded-4b-controlled-2026-11-08.json) conservent les
questions, sorties, citations, verdicts, empreintes et bras intermédiaires. Le
[rapport du gradeur](grounded-4b-grader-review-2026-11-08.json) explique les
réévaluations symétriques ; aucun document ni oracle n'a changé.

| Mesure | Référence réévaluée | C0, avant F07 | C2 final |
|---|---:|---:|---:|
| Positifs conformes selon le gradeur automatique conservé | 9/12 | 10/12 | 12/12 |
| Positifs complets, sans réserve injustifiée, après relecture | **9/12** | Non relu dans ce contrôle final | **11/12** |
| Positifs contenant tous les faits utiles, selon relecture | 10/12 | Non relu dans ce contrôle final | **12/12** |
| Refus totaux sur les positifs, selon relecture | 2/12 | Non relu dans ce contrôle final | **0/12** |
| Contrôles limites conformes | 15/18 | 18/18 | **18/18** |
| Faits requis restitués avec appui documentaire | 12/15 | 12/15 | **15/15** |
| Rappel littéral des faits au top 10 | 12/15 | 12/15 | **15/15** |
| Présence littérale dans le contexte sérialisé, mesure brute | 11/15 | 11/15 | **14/15** |
| Citations structurellement valides | 27/27 | 27/27 | **32/32** |
| Positifs avec message d'insuffisance reconnu par le gradeur | 3/12 | 2/12 | 0/12 |
| Erreurs sur positifs | 0/12 | 0/12 | **0/12** |
| Sentinelle générative interdite publiée | 0/30 | 0/30 | **0/30** |

Le gradeur automatique conservé donne six gains, aucune régression et vingt-quatre
égalités. **La relecture retire le gain P01** : le fait utile est complet et fidèle
dans les deux bras, mais le candidat garde un préambule générique indiquant que
l'interprétation complète reste à vérifier. Cette réserve est inutile pour la
question et la source simples de P01. Le score automatique ne détectait pas cette
nouvelle formulation ; sa sortie reste conservée, sans lui attribuer le verdict
de la relecture. Les gains positifs stricts sont donc **P04 et P06**.
L18 était déjà correct en sortie de référence ; la correction antérieure du
gradeur n'est pas un gain produit.
La relecture des dix-huit limites confirme 15/18 → 18/18. Au total, elle confirme
**cinq gains, aucune régression et vingt-cinq cas inchangés** : P04/P06,
L01/L06/L09. Pour L09, la réserve 25/85 °C était déjà présente à la fin de
l'extrait long de référence ; le gain est son signalement explicite, pas la
correction d'une valeur à 85 °C qui aurait été inventée.
Les trois erreurs terminales finales sont les rejets attendus de L10
(`invalid_source_locator`), L11 et L12 (`structured_answer_invalid`). L17
restitue la preuve originale, sans sa sentinelle altérée.

Le gain factuel ne provient pas d'une hausse des refus : les douze positifs
restituent leurs faits requis, sans erreur ni refus total. P01 garde toutefois
une réserve inutile ; la réponse utile et sa qualité de communication sont
comptées séparément. Les critères des contrôles adverses exigent une limite ou
un rejet selon le cas ; ils ne confondent pas tout silence avec une bonne réponse.
La [relecture finale](grounded-4b-output-review-2026-11-08.json) est non aveugle,
réalisée par un agent contributeur, et ne constitue pas une évaluation humaine
ou externe indépendante.

La validité structurelle des citations était déjà élevée avant correction.
Elle ne suffisait pas à signaler les conditions non établies ou les divergences :
ces propriétés sont évaluées séparément. La métrique brute de contexte manque
P05 à cause de l'échappement JSON de la tabulation avant `V`, confirmé par
relecture du même catalogue décodé. **14/15 ne signifie donc pas qu'un fait a
été retiré de ce contexte.** Le chiffre brut reste conservé ; le détail est dans
la [revue d'association et de mesure](grounded-4b-association-review-2026-11-08.json).

### Sondes de mécanismes

Les quatre sondes de conservation passent de **0/4 à 4/4**, avec les mêmes
entrées : parent long, note, extraction partielle sans résultat et provenance
mixte OCR/native. Les [résultats avant](grounded-4b-retrieval-baseline-2026-11-08.json)
et [après](grounded-4b-retrieval-after-2026-11-08.json) sont accompagnés d'un
script de rejeu. Sa version publiée ajoute seulement le refus d'écraser une
sortie et des corrections de lint ; le rejeu confirme les mêmes observations.

Les cinq défauts de relations initiaux sont détectés : condition différente,
négation, désaccord entre documents pour le même objet, maximum non établi,
conditions préfixées différentes. Les contrôles positifs restent disponibles.
Les dix entrées et leurs sorties figurent dans les sondes
[avant](grounded-4b-grounding-baseline-2026-11-08.json) et
[après](grounded-4b-grounding-after-2026-11-08.json). Le script publié reproduit
exactement le texte et l'évaluation des dix sorties de référence.

Sept paires FR/EN isolent le repli lexical : désactivé, aucun passage ; activé,
passage exact ; désactivé de nouveau, aucun passage. Le filtre de portée et les
caps restent identiques. Les sources n'ont pas changé. Ce test n'est pas une
ablation des embeddings natifs.

La [sonde extérieure à la matrice après correction](grounded-4b-association-after-2026-11-08.json)
confirme **3/3** : température de stockage indépendante refusée comme condition,
condition `for TA` conservée, température affichée indépendante toujours refusée.
La réussite de la matrice précédente n'avait pas révélé cette faille ; ce résultat
justifie la revue distincte des sorties et des relations.

### Régression logicielle et contrôles statiques

Les [résultats des gates](grounded-4b-validation-2026-11-08.json) conservent les
comptes, commandes, échecs, motifs d'ignorance et empreintes des journaux.

| Vérification exécutée | Référence immuable | Candidat final | Interprétation |
|---|---:|---:|---|
| Suite portable, hors acceptance/slow/integration | 3 635 PASS, 5 FAIL, 25 SKIP, 45 désélectionnés | 3 801 PASS, 5 FAIL, 25 SKIP, 45 désélectionnés | 166 cas réussis supplémentaires ; mêmes cinq échecs, aucun nouvel échec dans cette suite. |
| Intégrations marquées `integration` | 32 PASS, 12 SKIP, 87 désélectionnés | 33 PASS, 11 SKIP, 87 désélectionnés | Le binaire Qdrant est présent seulement dans le checkout candidat ; ce test supplémentaire exécuté n'est pas un gain produit. |
| Mypy | — | PASS, 128 fichiers sources | Contrôle du candidat complet. |
| Ruff | — | PASS | Tous les fichiers Python modifiés et ajoutés. |
| Compatibilité et chemins d'erreur ciblés après correction | — | 33 PASS | Provenance enrichie et état de transport historique ; aucun texte non validé autorisé. |
| Harnais natif final ciblé | — | 4 PASS | Page zéro, SHA PDF attendu, arrêt des descendants possédés, y compris ceux ignorant SIGTERM. |

Les durées de la suite portable sont 493,29 s avant et 407,57 s après ; celles
des intégrations sont 38,82 s et 36,55 s. Ce sont des durées de validation dans
un environnement dont les caches et le nombre de tests diffèrent, pas une mesure
de vitesse de l'application. Les tests ciblés recouvrent la suite complète ;
leurs nombres ne doivent pas être additionnés.

Les cinq échecs sont les mêmes tests de construction de runtime dans les deux
révisions : installation/réutilisation, verrou `flock`, échec de copie,
archive régénérée locale et archive régénérée en ligne (paramètre `True`).
Le compilateur C est présent, mais **CMake est absent**. Les fixtures neutralisent
le contrôle des prérequis puis `toolchain_versions` tente d'exécuter `None
--version`. Ce défaut préalable est reproduit et conservé ; aucune assertion
n'est retirée pour rendre la suite verte. Les identifiants exacts sont dans le
rapport JSON. Les sept intégrations OCR réelles restent ignorées faute des
poids Docling nécessaires ; les autres ignorances incluent les cas Windows.

Les suites `acceptance` et `slow`, la recette graphique, Windows et le poste
physique cible **ne sont pas exécutés** dans I3. Les contrôles de documentation
et de cohérence sont indiqués dans le même rapport de validation.

### Mesures natives

Les observations natives et leur revue sont publiées dans le
[rapport natif](grounded-4b-native-2026-11-08.json). Elles restent séparées des
trente cas utilisant des doubles. Les mesures sont des observations par cas,
avec une répétition par bras, sans intervalle de confiance ni comparaison de
performance à froid strictement appariée.

| Mesure de qualité native | Référence | Candidat primaire | Reprise distincte |
|---|---:|---:|---:|
| Office : tentatives terminées avec réponse | 8/8 | **5/8** | 3/3 |
| Office : réponses conformes à la relecture stricte | 5/8 | **5/8** | 2/3 |
| Office : faits utiles des quatre questions répondables | 4/4 | **3/4** | P01 récupère son fait ; réserve inutile maintenue |
| Office : erreurs d'admission de ressources | 0/8 | **3/8** | 0/3 |
| Office : appels effectifs au générateur | 6/8 | 2/8 | 3/3 |
| PDF : questions complètement répondues | **0/2** | **0/2** | Aucun rejeu supplémentaire |
| PDF : relations demandées complètement restituées | 1/4 | 1/4 | — |
| PDF : terminaisons / appels effectifs au générateur | 2/2 / 2/2 | 2/2 / 2/2 | — |

Sur Office, P05 (tableau), P10 (somme), P11 (conversion), L06 (divergence) et
L13 (négation) sont conformes au candidat primaire. **L06 progresse réellement** :
les deux valeurs incompatibles sont citées et le désaccord est explicite, sans
arbitrage. L13 était déjà conforme. P01, L01 et L16 échouent avant l'appel au
modèle pour manque de mémoire disponible ; la présence de leurs preuves dans
la recherche ne leur vaut aucun crédit de réponse. L16 est une régression de
fonctionnement par rapport à la réponse conforme de référence.

La première erreur observe environ 4 910 Mio disponibles pour **5 888 Mio
requis**. Des fixtures volumineuses créées par nos suites précédentes occupaient
la mémoire du même environnement. Leur nettoyage ciblé préserve les rapports,
originaux, traces et fixtures des tests échoués. L06 est ensuite admis après
attente ; une décharge adaptative du modèle et la pression restante précèdent
l'échec L16. Un second nettoyage de nos fixtures interrompues précède les blocs
suivants. Aucun seuil de réserve ni paramètre d'inférence n'est abaissé.

La reprise était déclarée avant ses sorties, avec **un seul essai supplémentaire
par cas**. P01, L01 et L16 terminent ensuite sans erreur. L01 signale correctement
que 25 °C n'établit pas une valeur à 85 °C ; L16 conserve sa note restrictive.
P01 restitue le fait demandé mais garde la réserve inutile observée dans la
matrice : **2/3 conformes**, et non 3/3. Ces observations établissent une reprise
dans un autre état de ressources ; elles ne remplacent pas les erreurs primaires
et ne sont pas fusionnées en un score favorable de huit cas.

Sur les PDF, la relecture visuelle des premières pages originales confirme les
quatre relations demandées. INA226 restitue seulement la plage de bus ; sa plage
d'alimentation manque. TMP117 ne restitue aucune des deux plages d'alimentation
avec leurs conditions. Le candidat ajoute une limitation explicite pour TMP117,
sans améliorer le nombre de relations demandées fournies. Les **six citations
affichées par bras sont littéralement fidèles**, mais **une seule soutient une
relation demandée complète**. Ce résultat illustre précisément pourquoi la
présence d'une citation ne suffit pas à valider la réponse.

La frontière de perte est localisée dans les données conservées : les trois
relations manquantes sont présentes dans l'extraction gelée, mais absentes du
catalogue transmis au modèle. Pour INA226, le passage d'alimentation apparaît
au rang 8 du top 10 initial, puis est éliminé des six résultats sélectionnés et
n'est pas rétabli par la recherche complémentaire. Pour TMP117, les deux lignes
contenant chacune tension et condition thermique ne sont pas dans les top 10
tracés ; leur titre d'alimentation est un bloc séparé sans lien déclaré.
**Aucun fragment de ces requêtes n'est exclu par dépassement du budget de
contexte.** Attribuer ces trois pertes seulement à l'extraction partielle serait
donc inexact ; elles se situent ici dans la recherche et la sélection.

#### Durées et mémoire observées

Les temps ci-dessous mesurent la requête, y compris attente d'admission ; ils
excluent provisionnement, démarrage des services et ingestion/indexation initiale.

| Cas | Référence, secondes | Candidat primaire, secondes | Reprise, secondes |
|---|---:|---:|---:|
| P01 | 74,316 | 121,435 — erreur | 59,296 |
| P05 | 106,189 — modèle appelé | 2,700 — plan déterministe | — |
| P10 | 0,140 | 0,213 | — |
| P11 | 0,112 | 0,146 | — |
| L01 | 26,383 | 121,615 — erreur | 26,383 |
| L06 | 48,693 | 126,277 | — |
| L13 | 30,237 | 29,907 | — |
| L16 | 45,023 | 124,043 — erreur | 42,050 |
| INA226 | 109,969 | 108,527 | — |
| TMP117 | 53,762 | 49,539 | — |

P05 évite désormais une génération pour une relation déjà vérifiée. Son temps
de référence comprend aussi 29,64 s d'attente d'admission ; L06 candidat en
comprend 35,42 s. Le changement de route, la résidence du modèle, l'état des
caches et la pression mémoire interdisent d'attribuer ces écarts à une seule
optimisation ou de promettre une accélération générale.

Le pic RSS cumulé échantillonné atteint **4 386,7 Mio** sur Office en référence,
**4 435,6 Mio** sur Office candidat primaire, et **3 979,1 Mio** dans sa reprise.
Sur PDF, il atteint **4 101,0 → 4 117,8 Mio**. Les PSS/USS et minima de mémoire
disponible sont conservés par cas dans le JSON ; RSS peut compter plusieurs
fois des pages partagées. Ce sont des processus surveillés sur cet hôte,
pas une garantie de capacité sur tous les postes. Les services possédés par les
derniers blocs sont arrêtés avec vérification de la disparition de leurs groupes.

## 4. Errata et reprises conservés

- Deux PDF du premier pilote demandaient l'index 1 alors que l'extraction portait
  sur l'index 0. Leurs sorties sans preuve restent des erreurs de préparation,
  exclues des paires valides. Un manifeste distinct corrige uniquement les quatre
  champs de portée ; les PDF de référence sont rejoués séparément. Les huit cas
  Office du pilote restent valides.
- Le premier gradeur ne reconnaissait pas certaines formulations explicites
  d'insuffisance ni la ponctuation de `4.` ; il exigeait aussi les deux assertions
  d'un conflit dans un seul extrait. Les corrections sont appliquées aux deux
  bras sur les réponses conservées. L18 était déjà correct en référence : il
  n'est pas compté comme gain produit. Les critères et fixtures restent inchangés.
- La métrique brute de contexte peut manquer une unité dans une chaîne JSON
  encore échappée (`\\tV`). P05 contient pourtant la ligne et son unité dans le
  catalogue décodé. La mesure brute et le diagnostic restent distincts.
- La revue F07 a découvert une association abusive entre température de stockage
  et condition d'alimentation malgré la réussite de la matrice. Ce contre-exemple
  extérieur au jeu figé est conservé et corrigé par une régression supplémentaire.
- Deux écarts détectés dans la suite intermédiaire sont traités explicitement :
  assertion de provenance complétée avec les nouveaux identifiants de révision ;
  état du transport historique préservé hors du profil renforcé. Les assertions
  d'absence de texte non validé ne sont pas supprimées.
- Le harnais natif a été revu pour arrêter les descendants qui ignorent SIGTERM
  et vérifier la disparition du groupe avant son reçu. Les processus de contrôle
  sont possédés par le test ; aucun service externe n'est visé.
- La relecture finale a trouvé un faux positif du gradeur automatique sur P01 :
  la nouvelle réserve générique reste inutile. Les sorties et scores automatiques
  9/12 → 12/12 sont conservés ; le bilan strict retenu est 9/12 → 11/12.
- Les trois erreurs d'admission Office restent au dénominateur primaire. Le
  nettoyage de nos fixtures et la reprise préenregistrée sont datés et séparés ;
  aucune meilleure sortie n'est substituée à une tentative initiale.

## 5. Pistes retenues, différées et portée des conclusions

Les copies de preuve, notes, contrôles de relations, calculs, traces, repli lexical
et plans déterministes répondent aux défauts reproduits sans ajouter de modèle.
Les sept ablations lexicales à sources identiques isolent l'effet du repli.
Les sondes de conservation et de relations isolent leurs frontières respectives.
Les campagnes globales changent plusieurs mécanismes : elles ne constituent pas
une ablation causale complète de chaque amélioration.

Un reranker neural supplémentaire, GraphRAG, un modèle 8B et le réglage exploratoire
des poids/quantifications sont écartés de ce lot : ils ne sont pas nécessaires
pour réparer les invariants reproduits, et demanderaient un autre protocole de
coût/qualité. Le 8B est explicitement hors périmètre. Les profils et rapports
historiques restent dans le dépôt pour conserver l'historique.

L'OCR à la demande, le traitement structuré complet de ces PDF, l'interprétation
sémantique générale et une validation sur corpus indépendant restent à démontrer.
Leur absence interdit de conclure à une fiabilité documentaire générale. Les
tests `acceptance`, Windows et l'hôte physique cible ne sont pas remplacés par
une mesure dans ce conteneur Linux. Les nouvelles grammaires peuvent produire
une abstention conservatrice sur des formulations hors de leur domaine ; ces
limites sont explicites et doivent être évaluées sur des documents distincts.

### Pistes différées après localisation des pertes PDF

| Piste | Raison technique du report | Conséquence observée et validation nécessaire |
|---|---|---|
| Sélection selon les propriétés encore absentes, à budget constant | Remplacer un résultat selon une propriété peut évincer une preuve d'identifiant, de rôle ou d'un autre document. Le rappel du top 10 ne prouve pas la qualité du sous-ensemble final. Une règle générique doit être comparée sur des questions indépendantes, sans coder les valeurs des deux composants. | Le passage d'alimentation INA226 au rang 8 reste perdu à la sélection de six résultats. Prévoir des oracles de couverture propriété × document × condition et un contrôle des pertes induites. |
| Liens entre titre de liste PDF et lignes numériques | Les blocs concernés n'ont pas de dépendance explicite. La proximité seule, notamment sur une page à colonnes, ne suffit pas à attribuer le titre à une valeur. Les notes explicitement liées corrigées dans I3 ne créent pas ces relations absentes. | Deux relations TMP117 restent hors des résultats tracés. Qualifier la création de liens structurels contre les pages originales, puis leur indexation et leur expansion, sans emprunt à une autre colonne. |
| Réserve générique sur questions simples | Les questions générales restent hors des grammaires locales reconnues. Supprimer toute réserve par défaut masquerait cette limite ; reconnaître uniquement le boîtier du cas P01 serait un ajustement spécifique à la fixture. | P01 reste utile mais inutilement réservé. Étendre un contrat de question/réponse générique et le vérifier sur des formulations distinctes avant de promettre une couverture sémantique. |
| OCR réel et PDF complet | Les poids Docling requis par les intégrations OCR ne sont pas provisionnés dans cette session ; les pages natives préparées ne démontrent pas la reconnaissance des zones scannées. | Sept tests OCR ignorés ; aucun gain OCR attribué à I3. Il reste à provisionner les artefacts verrouillés et comparer extraction, unités, conditions et citations aux images originales. |
| Construction du runtime dans un environnement sans CMake | Les cinq échecs sont antérieurs et concernent les fixtures/versions de chaîne de compilation, hors de la voie 4B binaire exécutée. | La suite portable n'est pas entièrement verte. Corriger le prérequis ou les fixtures de construction dans un lot distinct, puis reproduire les cinq cas. |

Ces pistes restent ouvertes. Leur description n'est pas une preuve de réalisation
ou d'efficacité. La conservation des erreurs évite de convertir l'abstention
ou le simple fait de citer un document en réussite de la réponse.

## 6. Bilan de la Definition of Done I3

| Critère préenregistré | État à la clôture technique | Preuve et limite |
|---|---|---|
| I3-D01 — références et portée | **Atteint dans les contrôles exécutés** | Citations et localisations vérifiées, plans adverses et corruption après rendu bloqués. Les références exactes ne constituent pas une preuve sémantique générale. |
| I3-D02 — relations | **Atteint dans le domaine borné** | Cinq défauts initiaux détectés, contrôles positifs conservés ; contre-exemple thermique extérieur à la matrice corrigé. |
| I3-D03 — conservation | **Atteint sur les sondes** | 0/4 → 4/4 ; notes, positions distinctes, provenance mixte et extraction partielle. L'OCR réel n'est pas qualifié. |
| I3-D04 — réponse utile | **Partiellement atteint** | 12/12 positifs livrent leurs faits, mais seulement 11/12 satisfont le critère strict : réserve P01 persistante. 18/18 limites conformes ; aucune réussite automatique 12/12 présentée comme verdict final. |
| I3-D05 — calculs et restitution | **Atteint dans les contrôles exécutés** | Calculs déterministes, entrées et méthodes traçables ; deux calculs natifs vérifiés indépendamment, erreurs et altérations rejetées avant texte public. |
| I3-D06 — reproductibilité | **Atteint avec conditions explicites** | Deux révisions, corpus figé, poids et paramètres verrouillés, snapshots stables, traces et hashes. Ressources/caches différents, doubles séparés et reprise distincte ; aucune promesse de performance générale. |
| I3-D07 — non-régression | **Exécuté avec réserves préexistantes** | 3 801 PASS, cinq mêmes FAIL ; intégrations et contrôles statiques exécutés. OCR, acceptance, slow, Windows et cible physique non couverts. |
| I3-D08 — essais natifs | **Non atteint** | Trois erreurs primaires, disponibilité Office en baisse et deux réponses PDF incomplètes. La reprise ne remplace pas ces résultats. |
| I3-D09 — livraison | **Atteint pour la livraison technique** | Commit [fdc51187](https://github.com/msedki/agentPDFDoc/commit/fdc51187aabbdfd16e561dc32c50ac1c107e15bc) publié sans force sur `enhanced_version` ; parent, SHA et arbre distant vérifiés identiques à la livraison locale. [Reçu et identités](grounded-4b-publication-2026-11-08.json). |

**La DoD I3 complète n'est pas atteinte.** Le lot apporte des mécanismes vérifiés
et des gains mesurés dans leur périmètre ; il ne constitue pas une réception
documentaire générale ni une qualification du poste cible.
