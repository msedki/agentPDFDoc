# EV4B — implémentation, essais et limites

**Rôle :** bilan de livraison du chantier 4B · **Propriétaire :** intégration EV4B · **Statut :** implémenté et testé avec réserves, commit local acquis, push bloqué ; qualification documentaire partielle · **Dates :** 7–8 novembre 2026, UTC · **Référence :** base `59d47e98a47fc652b5506727673b6b477c92eb9d`, branche `enhanced_version`, commit de code local `63487f63b947ada00db180e474d944a5ea3ed810` · **Source de vérité :** ce bilan pour la synthèse ; [protocole](enhanced-4b-protocol-2026-11-07.md) pour les critères ; traces et jugements individuels pour les observations.

## 1. Objectif et périmètre livré

Le générateur de cette étude reste **Qwen3-4B, poids Q4_K_M**. Aucun routage,
entraînement ou essai 8B n'est ajouté. L'objectif est de conserver davantage de
preuves utiles, de contrôler leur restitution et de rendre les essais
rejouables, avec des coûts bornés et des refus explicites lorsque la preuve ou la
mémoire manque.

Le profil explicite `config/enhanced-4b.yaml` active les changements. Il utilise
le modèle local `qwen3-4b-enhanced:q4km`, une fenêtre de 8 192 tokens, le KV q8_0,
la graine zéro et une résidence adaptative. Le fichier
`config/enhanced-4b.lock.json` fixe le GGUF, sa révision, les deux fichiers du
tokenizer, les paramètres d'import et Ollama 0.35.0. Le modèle de recherche E5
INT8 existant reste distinct du générateur. Les anciens profils sont conservés.

| Piste | Réalisation | Limite explicite |
|---|---|---|
| Préservation des preuves | Petites plages XLSX exactes ; conservation du zéro, des cellules utiles, des formules et de leur état de cache ; lignes de tableaux PDF avec dépendances vérifiables | Une structure PDF doit correspondre exactement au texte autorisé avant reconstruction ; sinon le tableau reste atomique |
| Sélection et suffisance | Reclassement structurel borné, conservation d'une occurrence d'identifiant utile, catalogue de références et états couvert/partiel/ambigu/contradictoire | Ces contrôles locaux ne constituent pas un juge sémantique général |
| Réponse et calcul | Contrats liés à la question ; références choisies puis validées ; rendu déterministe des valeurs ; lectures de cellules exactes sans modèle lorsque l'intention est reconnue ; calculs `Decimal` et conversions avec provenance | Les conversions et relations non reconnues ne sont pas inventées ; la formule sans résultat calculé n'est pas évaluée arbitrairement |
| Reprise bornée | Une recherche lexicale complémentaire, dans le même périmètre, limitée en termes, candidats et durée | Pas de boucle de génération, d'élargissement silencieux ni de réingestion OCR déclenchée par une question |
| OCR régional | Séparation brut/candidat/région/validation ; nouvelle lecture bornée des lignes numériques ambiguës ; rejet des conflits | Le pilote natif ne démontre pas la récupération du zéro ; résultat négatif conservé |
| Runtime et mémoire | Graine propagée jusque dans le corps HTTP ; budget du prompt et de la sortie ; f16/q8_0/q4_0 ; conserver/décharger/adaptative ; libération des caches documentaires avant admission froide ou chaude insuffisante | Les seuils du poste cible ne sont pas qualifiés par cet hôte Linux ; le gouverneur continue de refuser une admission insuffisante |
| Traces et évaluation | Événements capturés pendant la requête réelle, chaîne d'empreintes, quotas et fichiers privés ; requête HTTP exacte ; rejeu sans recherche ; analyse appariée à verdicts explicites | Le mode `hashes` ne contient pas les entrées rejouables ; `full` est un choix privé explicite. Un hash ne constitue pas une signature d'authenticité |

Les principaux modules sont `evidence_selection.py`, `answer_contract.py`,
`deterministic_calculations.py` et `execution_trace.py`. Ils sont intégrés aux
services existants de recherche, contexte, réponse, ingestion et runtime. Les
outils de campagne, rejeu, évaluation, OCR et matrice mémoire se trouvent dans
`tools/qualification/` ; leur [mode d'emploi](../../tools/qualification/README.md)
décrit les commandes et prérequis réels.

## 2. Méthode et portée scientifique

### Référence, corpus et appariement

La grille comporte **15 questions**, dont **14 renseignables** au sens de leurs
faits attendus et une demande hors périmètre, avec **33 faits requis**. Elle a été
figée avant les nouvelles réponses : empreinte
`a114cc9803387c543f635a0f495f82ccc0f1449a018abac6da5e94b1bdee1827`.
Les refus attendus, notamment formule sans cache, unité absente et division par
zéro, sont eux-mêmes des réponses vérifiables à la question ; ils ne sont pas
confondus avec un échec de service.

Les cinq originaux sont un PDF INA226, deux DOCX et deux XLSX dérivés du même
composant. Ils représentent **une seule famille documentaire indépendante**.
Les fichiers Office sont réellement extraits et indexés. Le PDF utilise un
sous-ensemble récupéré de **231 blocs, dont 37 tableaux**, dont les textes
correspondent aux empreintes historiques. Les **1 468 blocs non récupérés restent
absents**. L'association de ce sous-ensemble avec le PDF original est documentée :
la copie historique différait par sa métadonnée `Subject`, avec identité des
contenus de pages vérifiée dans les preuves antérieures.

La campagne ne constitue donc ni une nouvelle ingestion complète du PDF, ni la
réexécution des six PDF historiques, ni une validation sur des documents inconnus.
Les cas sont des **diagnostics et régressions de développement** ; plusieurs
correctifs ont été conçus après lecture des erreurs de la première campagne.

Dans chaque campagne complète, les deux variantes partagent les documents,
versions, index, modèle, graine et paramètres de runtime. L'ordre baseline/enhanced
alterne selon la question, avec conversation neuve à chaque soumission. La
**référence instrumentée** désactive les quatre drapeaux de préservation,
reclassement, contrat et reprise complémentaire dans le code courant. Ce n'est
pas un ancien binaire intact du commit de base.

La comparaison principale porte sur **l'ensemble recherche–contexte–restitution**.
Le contexte peut donc changer entre variantes. Elle n'isole pas l'effet causal
du seul reclassement, du seul contrat ou de la seule voie déterministe. Les
extractions, profils, sources Python et options effectives de la **campagne
finale** sont gelés avant les requêtes, puis reliés aux réponses par leurs
empreintes. Le snapshot de v1 a été constitué manuellement pendant cette
première campagne, avant les corrections suivantes ; il n'est pas présenté
comme un gel automatique préalable à sa première requête.

### Jugements et dénominateurs

Chaque fait reçoit trois verdicts distincts : exactitude dans la réponse, soutien
par la citation, présence des preuves nécessaires dans le contexte réellement
capturé. Pour un calcul ou un refus technique, des opérandes et états autorisés
peuvent établir le fait sans que son résultat soit stocké littéralement dans la
source. Une référence existante ne suffit pas à prouver son soutien sémantique.

Les réponses sont relues par des agents sur une grille commune, séparément pour
PDF/DOCX/comparaison et XLSX. Cette relecture assistée **n'est pas une validation
humaine indépendante**. Les sorties du contrôle de suffisance ne servent pas de
vérité de référence. Les erreurs gardent un verdict d'exactitude/citation inconnu
et restent dans le dénominateur des soumissions.

Le rendement principal est le nombre de réponses entièrement exactes et
complètes, sans affirmation fausse supplémentaire, divisé par les **14
soumissions renseignables de chaque variante**. Les abstentions, résultats
partiels et erreurs restent visibles. Le soutien intégral des citations est
rapporté séparément. Un gain de taux calculé seulement sur les réponses acceptées
ne remplace pas ce rendement. Le risque d’affirmation fausse est aussi calculé
sur toutes les réponses terminées relues, abstentions comprises : une fausse
affirmation d’absence suivie d’un refus n’est pas comptée comme un refus correct.

Il n'y a qu'une répétition documentaire par question et variante dans une
campagne. Les répétitions de la matrice runtime utilisent un seul contexte et ne
créent pas de nouvelles questions. Avec une seule famille documentaire,
**l'intervalle de confiance par familles n'est pas estimable**. Aucun score de
confiance calibré ni courbe risque–couverture exploitable n'est revendiqué.

## 3. Résultats documentaires

<!-- NATIVE_RESULTS_START -->
### Résultat principal et dénominateurs

La campagne finale s'achève le **8 novembre à 00:29:04 UTC**. Les trente
soumissions sont conservées : **28 réponses terminées et deux erreurs**, une
dans chaque variante. Le wrapper a été récolté avec code zéro. Les
[résultats structurés](enhanced-4b-quality-results-2026-11-07.json) donnent les
verdicts par fait, les empreintes, les dénominateurs et les mesures individuelles.

| Mesure finale | Référence instrumentée | Enhanced |
|---|---:|---:|
| Soumissions prévues et effectuées | 15/15 | 15/15 |
| Réponses terminées / erreurs | 14 / 1 | 14 / 1 |
| Réponses complètes confirmées / questions renseignables soumises | **4/14 — 28,6 %** | **9/14 — 64,3 %** |
| Réponses complètes avec soutien des citations / même dénominateur | **4/14** | **9/14** |
| Faits dont les preuves nécessaires sont présentes dans le contexte | **19/33 — 57,6 %** | **31/33 — 93,9 %** |
| Réponses terminées relues contenant une affirmation explicitement fausse | **4/14** | **0/14** |
| Dont abstentions contenant une affirmation fausse | 3 | 0 |
| Question hors portée : abstention motivée correcte | 0/1 | 0/1 |
| Appels réels au 4B | 15 | 9 |
| Réponses par voie déterministe sans modèle | 0 | 6 |
| Latence médiane des réponses terminées | 47,64 s | 78,32 s |

Le gain descriptif de rendement est de **5 réponses sur 14, soit 35,7 points de
pourcentage**. Il porte sur la chaîne complète, dont les voies déterministes ;
il ne mesure pas une amélioration intrinsèque du raisonnement du modèle. Les
quatorze paires renseignables sont toutes jugées. Avec une seule famille,
l'intervalle par familles est **non estimable** : aucune significativité ou
généralisation n'est affirmée.

La mesure de contexte porte sur les **preuves nécessaires**. Pour un calcul,
les opérandes complets et l'opération explicitement demandée peuvent suffire,
sans que le résultat soit écrit littéralement dans le document. La revue XLSX
v3 harmonise six verdicts de contexte selon cette règle, trois dans chaque
variante ; elle conserve séparément l'absence littérale du résultat et ne change
aucun verdict de réponse. Les premières revues et le mapping sont archivés.

L'absence d'affirmation explicitement fausse observée dans enhanced ne signifie
pas absence d'erreur : quatre réponses sont partielles, une réponse est bloquée,
la demande hors portée reçoit des extraits hors sujet, et plusieurs valeurs
supplémentaires perdent leur qualification nominale/maximale. Ces ambiguïtés
restent documentées même lorsque tous les faits demandés sont corrects.

### Cas, gains et contre-exemples

| Cas | Référence instrumentée | Enhanced et limite observée |
|---|---|---|
| PDF : bus et alimentation | 0/2 faits ; contexte insuffisant | **2/2** : bus 0–36 V et VS 2,7–5,5 V ; lignes supplémentaires 6 V/3,3 V insuffisamment qualifiées |
| PDF : VBUSCT 000 et 111 | Abstention affirmant faussement que la table ne donne pas les temps | **2/2** : 000 → 140 µs ; 111 → 8,244 ms |
| PDF : exprimer les deux temps en ms | Abstention avec fausse absence documentaire | **1/2** : 8,244 ms rendu ; 0,140 ms omis malgré les 140 µs disponibles |
| PDF : conditions PSRR et limites | Trois faits numériques corrects, mais fausse définition de PSRR et soutien insuffisant du rôle de la plage VS | **1/3** : VS rendu ; bus et distinction condition/limite omis. La couverture du contexte régresse ici de 2/3 à 1/3 |
| DOCX témoin : deux plages | **2/2** | **2/2**, avec préambule de couverture trop prudent |
| DOCX avec instruction intégrée | **2/2**, instruction non suivie | **Erreur de plan**, aucun texte final. Le groupe cite R001/R002 mais la racine seulement R001 |
| XLSX A5:F6 : minimum, maximum, unité | 0/3 faits rendus | **3/3 : 0, 36 et V** avec en-têtes et coordonnées ; l'avis de suffisance reste trop prudent |
| XLSX B6/C6 : valeurs exactes | **2/2** | **2/2**, lecture déterministe |
| XLSX D8 seule : valeur et unité attestable | Erreur de plan, doublon de référence | **2/2** : valeur conservée, unité non attestable dans la sélection |
| XLSX D10 : formule sans résultat en cache | **2/2** | **2/2**, état de formule conservé sans inventer un résultat calculé |
| XLSX : somme B6+C6 | Opérandes restitués, somme absente | **2/2**, somme 36 calculée et citée |
| XLSX : rapport C6/B6 | Opérandes restitués, diagnostic absent | **2/2**, division par zéro explicitement refusée |
| XLSX : marqueur de la deuxième feuille hors sélection | En-têtes hors sujet, refus motivé absent | Même défaut de formulation ; **aucune fuite du marqueur** dans les deux variantes |
| XLSX : conversion D8 avec unité E8 | Entrées seulement | **Partiel** : 0,14 ms et provenance corrects, facteur /1000 demandé absent du rendu |
| Comparaison PDF/DOCX | Abstention affirmant à tort l'absence des plages dans les documents | **2/5** : plages DOCX seules ; les cinq faits sont pourtant disponibles dans le contexte |

La comparaison finale localise un échec **après récupération** : R005/S003
contient le bus PDF, R019/S008 son alimentation, R002/S002 les plages DOCX et
R001/S001 la provenance dérivée du témoin. Le plan sélectionne R002 et R012 ;
le rendu PDF se limite à la tension nominale 3,3 V, sans indiquer NOM. Il ne
conclut ni sur l'accord des valeurs ni sur le caractère dérivé du témoin. Une
présence de preuve correcte ne suffit donc pas encore à obtenir une réponse
complète du 4B.

La reprise documentaire possède un apport natif ponctuel établi : sur la
question PDF bus/alimentation, une unique reprise de **119,79 ms** ajoute la
ligne VS 2,7–5,5 V absente du contexte initial, puis citée en S004. Onze reprises
complémentaires sont capturées au total, chacune bornée ; cet exemple ne prouve
pas que toute reprise améliore le résultat. Aucune ablation native du seul
classement à candidats identiques n'a été exécutée.

La fausse expansion de PSRR dans la baseline est distinguée d'un simple manque
de citation. La définition officielle « Power Supply Rejection Ratio » est
vérifiée dans [Texas Instruments AN-1873, §9](https://www.ti.com/lit/an/snoa532a/snoa532a.pdf).
Cette source de terminologie ne fournit pas les plages propres à l'INA226.

### Itérations conservées

La première campagne complète v1 comprend également trente soumissions, dont
trois erreurs. Son rendement relu est **3/14 contre 5/14**. Ses extractions,
traces, jugements et analyse révisée restent séparés dans
`analysis-v1-revised-complete/`. Les anciennes analyses sont gardées comme
intermédiaires ; elles ne remplacent pas cette synthèse révisée.

V1 et la campagne finale diffèrent par les correctifs, le profil de résidence,
le gel de code et l'état du runtime. La comparaison valide est **appariée dans
chaque campagne** ; la différence entre leurs deux taux n'isole pas un correctif
particulier. Les essais v2/v3 interrompus ne sont pas ajoutés aux paires finales.
<!-- NATIVE_RESULTS_END -->

## 4. Exécution réelle, mémoire et reproductibilité

Les campagnes utilisent réellement SQLite, E5 INT8, Qdrant, le tokenizer Qwen,
`QueryService`, le gouverneur et Ollama. Elles passent par le service de questions
et enregistrent ses événements ; elles n'exercent pas le transport public HTTP,
le navigateur ou les lecteurs graphiques. Les tests unitaires de ces contrats
restent distincts des essais natifs.

L'hôte est Linux x86-64, CPU, avec environ **9,7 Gio de RAM visible**. Les poids
4B restent identiques entre essais. La campagne finale emploie la résidence
adaptative et une estimation froide **pilote de 3 840 Mio**, établie à partir du
pic conservateur observé de **3 562,24 Mio** pour la famille Ollama de v1, soit
277,76 Mio de marge. La réserve hôte reste **1 536 Mio**, le surcroît chaud
**640 Mio**. Le profil livré conserve son estimation froide de **4 352 Mio** :
le pilote ne devient pas silencieusement un seuil de production.

Les tentatives intermédiaires sont conservées. V2 comprend une erreur d'admission
sans appel modèle, suivie d'une attente interrompue. V3 comprend une réponse
baseline terminée puis une trace enhanced ayant atteint `llm.request`, sans réponse terminale
capturée avant interruption. Le constat initial « encore en attente » de cette
dernière requête est corrigé par sa trace finale. Ces essais ne sont pas effacés,
fusionnés avec la campagne finale ou comptés comme des succès de qualité.

La libération des caches ne se limite plus au démarrage froid : un modèle résident
peut lui aussi manquer de marge pour le prochain contexte. Le hook réutilise
l'exigence exacte du gouverneur, libère les caches une fois puis laisse le
gouverneur relire la RAM disponible. Un gain insuffisant reste un refus. Les
tests couvrent le seuil exact, l'absence de gain, l'état de résidence inconnu et
la conservation du diagnostic froid.

La campagne finale contient **24 appels modèle et six réponses déterministes**.
Les 24 générations sont suivies d'un déchargement `unloaded_verified` sous
disponibilité naturelle inférieure à 2 560 Mio, y compris les deux plans ensuite
refusés. Le pic de la chaîne mesurée application + Qdrant + Ollama et descendants
atteint **4 023,55 Mio RSS** et **4 017,01 Mio PSS** ; la disponibilité hôte
minimale est de **2 029,23 Mio**. La RSS peut compter des pages partagées plusieurs
fois. Les cas déterministes très courts ne possèdent chacun qu'un relevé mémoire.

Les six voies déterministes prennent **49,17 à 59,14 ms**, médiane **55,63 ms**.
Les neuf soumissions enhanced appelant le modèle, erreur comprise, prennent
**36,41 à 267,18 s**, médiane **104,26 s**. Les plus grands contextes PDF coûtent
cher : 232,29 s pour les codes VBUSCT et 267,18 s pour leur conversion en ms.
Cette dernière réponse reste partielle. Le coût supplémentaire ne constitue
donc pas, à lui seul, un gain de qualité. Ces latences sont celles du service
local mesuré, sans transport navigateur.

Le [rapport runtime](enhanced-4b-runtime-2026-11-07.md) et ses
[mesures individuelles](enhanced-4b-runtime-results-2026-11-07.json) détaillent :

- **12 générations** : f16/q8_0/q4_0 × 4 096/8 192, deux appels par cellule ;
- **4 générations** pour les politiques de résidence, avec contrôles `/api/ps` ;
- **1 rejeu exact** des octets HTTP et du digest, sortie brute identique sur cet essai ;
- un import réellement exécuté dans un store vide, puis revalidation, avec digest
  strictement identique au modèle déjà utilisé ;
- un microbenchmark de sérialisation des mêmes événements réels, **20 passages
  par mode**, distinct d'une mesure du surcoût de la chaîne complète.

À 8 192 tokens, les allocations KV mesurées sont **1 152 Mio en f16, 612 en q8_0
et 324 en q4_0**. Le pic PSS de la famille Ollama est respectivement d'environ
3 822,9, 3 291,5 et 3 005,2 Mio sur ce contexte. Cette mémoire exclut l'application
documentaire. Les latences quantifiées observées sont plus longues pour le
premier contenu que celles de f16 ; aucune supériorité générale de vitesse ou de
qualité n'en est déduite.

La graine zéro n'a pas garanti une identité de plan pour toutes les répétitions :
les seconds appels f16 omettent une référence racine conservée dans les dix autres
sorties. La différence persiste après canonicalisation JSON. C'est un résultat de
stabilité, pas un jugement documentaire.

## 5. OCR : résultat négatif conservé

Le [rapport OCR](enhanced-4b-ocr-2026-11-07.md) présente trois campagnes bornées,
avec Tesseract 5.5.0 réellement exécuté sur des régions synthétiques. La lecture
naturelle transforme notamment `0 V` en `OV`. Chaque campagne obtient **1 contrôle
réussi sur 3** : le conflit d'unité est rejeté, mais les **deux cas de récupération
du zéro échouent**. Le redimensionnement ×2 n'a pas apporté de gain.

La reprise et sa provenance sont implémentées ; le texte brut n'est pas remplacé
par une correction lexicale supposée. L'ambiguïté non résolue reste signalée.
Ces résultats ne qualifient ni le moteur Windows 5.4 du projet, ni une nouvelle
ingestion Docling complète, ni la récupération OCR générale sur des PDF réels.

## 6. Vérifications du code et cas limites

Le [relevé de validation](enhanced-4b-validation-2026-11-07.json) conserve les
commandes, résultats, motifs de skip, empreintes des logs et sources testées.

| Contrôle final | Résultat |
|---|---|
| Suite `tests/unit` complète avant le dernier correctif de terminal | **3 409 PASS, 0 échec, 23 SKIP**, 217,81 s dans le log console |
| Delta final de l’évaluateur après ce gel | **40 PASS**, dont 31 cas recouvrants et 9 nouveaux ; Ruff et Mypy ciblés conformes |
| Correctif de terminal après campagne | **19 PASS** : 18 nouveaux cas et une régression existante ; puis **74 PASS** de compatibilité trace/rejeu/matrice/route, avec recouvrement |
| Mypy configuré du dépôt, réexécuté après ce correctif | **PASS**, 122 fichiers sources |
| Ruff sur tous les Python modifiés/nouveaux après ce correctif | **PASS**, 39 fichiers ; le contrôle précédent portait sur 38 |
| Vérification documentaire après consolidation | **105 PASS**, contrôles espace/liens, brief, schémas et pack conformes ; tests recouvrant la suite globale |
| Écriture courte de trace | Refus avant `/api/chat`, chaîne non avancée, fichier partiel détectable |
| Manifeste existant différent/incomplet | Refus si verrou complet ou empreintes d'entrée incompatibles ; aucune adoption implicite |
| Admission mémoire après libération | Seuil réel réappliqué ; absence de gain et état chargé inconnu ne deviennent pas un succès |

Les 23 skips concernent principalement Windows/PowerShell, ainsi que des artefacts
locaux de provisionnement absents des chemins spécifiques de leurs tests. Ils
ne sont pas des tests réussis. L'avertissement Starlette sur `TestClient/httpx`
est conservé. Les tests unitaires comprennent des doubles explicitement nommés
et des traitements réels de fichiers locaux ; ce ne sont pas 3 409 inférences.

Les erreurs de démarrage de l'environnement et les cinq échecs liés à CMake
absent sont archivés. Les dépendances du projet ont été synchronisées avec le
verrou, puis CMake 3.31.10 fourni dans un répertoire utilisateur isolé. Aucun
oracle n'a été supprimé pour fermer ces cinq échecs.

Quatre écarts historiques ont été reproduits et corrigés séparément : distinction
entre SSE public et audit interne ; arrondi du délai de watchdog ; budget d'une
fixture inférieur au seul prompt système ; messages de refus déjà émis par
l'installateur mais absents du dépannage. L’invariance des fonctions SSE, watchdog et installateur a été vérifiée par
comparaison de leurs AST. L’échec de budget de la fixture se reproduit également
avec le constructeur de contexte de base, même si ce module évolue dans EV4B. Les preuves avant/après restent dans le dossier
privé, avec leurs empreintes.

### Correctif de terminal après la campagne

La dernière revue reproduit deux courses d'annulation : une annulation persistée
avant `finish()` pouvait être tracée comme `query.done`, et une annulation
signalée après le commit pouvait ajouter `query.cancelled` à une réponse déjà
enregistrée comme terminée. Le reproducteur utilise le vrai service, SQLite,
OOXML et les traces ; les embeddings/vecteurs/tokenizers sont des doubles nommés
et le gateway interdit tout appel modèle.

Le correctif ne change qu'un module des **75 sources du snapshot expérimental**,
`services/api/query.py`, et ajoute un fichier de tests. Les trois événements
avant persistance deviennent des intentions. Une lecture jointe de l'état SQL
et de son dernier événement public confirme ensuite un unique terminal dans
le worker, même si l'attente asynchrone reçoit une annulation. Une incohérence ou
un échec de lecture est signalé comme persistance non confirmée, sans inventer
de succès. Les méthodes de publication SQL et la sélection/réponse ne sont pas
modifiées.

Les trois scénarios avant/après conservent **types, identifiants et états des
événements publics, ainsi que les textes de réponse vérifiés par empreinte**.
Le payload JSON entier n'est pas déclaré identique : le diagnostic
`execution_trace` change volontairement. Il est marqué comme instantané avant
persistance ; son compteur et son dernier hash peuvent précéder la confirmation
dans le fichier. Aucune seconde écriture SQL n'est ajoutée pour le resynchroniser.

Les 19 tests ciblés couvrent les annulations avant/après commit et pendant
l'observation, les échecs de persistance/lecture, les incohérences d'événement,
la limite de longueur, le quota de trace et le mode désactivé. Les 74 régressions
complémentaires vérifient les lecteurs de traces, le rejeu, la matrice runtime et
la route de questions. Ces nombres se recouvrent ; ils ne s'additionnent pas à
la suite complète comme des tests indépendants.

Un audit en lecture seule des **30 essais natifs** trouve **zéro divergence**
entre leur SQLite, leur artefact et leur trace, et aucune annulation demandée.
Les scores restent donc attribués au snapshot qui les a produits. **Aucune
nouvelle inférence native n'a été effectuée après ce correctif de trace.**
L'[attestation du delta](enhanced-4b-terminal-fix-2026-11-08.json) conserve les
empreintes avant/après et les preuves de validation ; l'archive prévue contiendra
aussi les 75 sources réellement expérimentées. Le code livré diffère explicitement
de ce snapshot par ce seul correctif applicatif.

## 7. Definition of Done et réserves

<!-- DOD_RESULTS_START -->
Le [plan canonique](../PLAN.md) reprend les mêmes états. Un critère partiel
signifie que le mécanisme est livré mais que son exigence complète n'est pas
acquise ; il n'est pas coché pour obtenir une clôture artificielle.

| Critère | État à cette livraison | Preuve acquise et réserve |
|---|---|---|
| EV4B-01 — graine/identité | **Complet dans le périmètre testé** | Graine zéro et identités capturées ; poids, tokenizer et moteur vérifiés |
| EV4B-02 — traces/rejeu | **Complet dans le périmètre testé** | Captures réelles, chaîne et quotas, rejet des incohérences ; un rejeu exact exécuté ; terminal corrigé après campagne et vérifié séparément |
| EV4B-03 — preuves structurées | **Partiel** | Zéro, plages exactes et relations conservés sur les cas directs ; rôles MAX/NOM et conditions encore perdus dans certains rendus |
| EV4B-04 — OCR | **Partiel** | Brut/candidat/provenance et refus vérifiés ; zéro non récupéré dans 2/2 cas ; pas d'OCR déclenché par une question |
| EV4B-05 — suffisance/classement | **Partiel** | Contrôles et limites actifs ; bénéfice global mesuré ; ablation native à candidats identiques absente |
| EV4B-06 — contrôle de réponse | **Partiel** | Contrats intégrés et nombreux cas limites couverts ; erreur DOCX et omissions de comparaison/conditions persistantes |
| EV4B-07 — calculs | **Partiel** | Lectures, somme, unité explicite et refus vérifiés ; explication /1000 manquante dans la conversion demandée |
| EV4B-08 — reprise | **Partiel** | Reprise lexicale unique et apport VS observé ; utilité générale et autres branches non qualifiées |
| EV4B-09 — contexte/KV | **Complet dans le périmètre testé** | Budgets contrôlés et six cellules runtime réellement exécutées ; aucune clôture D07 de qualité sur la cible |
| EV4B-10 — résidence | **Partiel** | Trois politiques et déchargements naturels vérifiés ; activité mixte/annulation sur cible non qualifiées et gain propre du hook cache non isolé |
| EV4B-11 — évaluation | **Complet pour l'outil et le protocole** | Trente jugements reliés aux preuves, erreurs/dénominateurs/révisions conservés ; aucune validation externe ou intervalle non estimable fabriqué |
| EV4B-12 — publication | **Ouvert : commit local, push bloqué** | `63487f63` acquis ; HTTPS sans identifiant utilisable, identité auteur/committer non garantie par le connecteur, SSH refusé sur les permissions de configuration. Conservation séparée selon le §8 ; SHA distant non confirmé |
<!-- DOD_RESULTS_END -->

Les conclusions sont bornées aux cinq fichiers et à l'hôte effectivement
observés. Il reste nécessaire, pour une qualification métier, de disposer de
plusieurs familles documentaires, de documents tenus à l'écart du développement,
d'une relecture technique humaine, d'une recette complète sur le poste cible et
d'une mesure du coût de l'instrumentation dans la chaîne entière. Une série de
100–200 questions serait une extension du corpus, pas à elle seule une garantie
de puissance statistique.

Les échecs OCR, variations de sélection, omissions, ambiguïtés et refus de
mémoire font partie du résultat. Les corrections exécutables, la qualification
documentaire et la qualification de toutes les plateformes sont des niveaux
distincts.

## 8. Reproduction et conservation des preuves

Utiliser le profil et le verrou livrés, provisionner les fichiers locaux
identifiés puis suivre le [README de qualification](../../tools/qualification/README.md).
Le générateur de campagne exige un répertoire de sortie nouveau et vérifie les
originaux et extractions déclarés. L'évaluateur exige les annotations et verdicts
explicites ; il ne remplace pas la relecture des documents.

La campagne finale et v1 ont des identités séparées. Les versions intermédiaires,
les refus et les interruptions sont conservés avec les fichiers de gel. Le
dossier de preuves privé contient les réponses, citations, traces, verdicts,
originaux nécessaires, extractions, logs, mesures et scripts de consolidation.
Les modèles, binaires et index volumineux ne sont pas ajoutés à Git. Les sources
réutilisables, rapports compacts et empreintes y sont versionnés.

Le commit de code local `63487f63b947ada00db180e474d944a5ea3ed810` est acquis
sur `enhanced_version` avec l'identité auteur/committer exigée. Le push est
bloqué techniquement ; les motifs HTTPS, connecteur et SSH sont détaillés au
[journal](../journal/2026-11-08.md#commit-local-et-push-bloqué) et dans
`.runtime/qa/enhanced-4b/publication/publication-attempts.json`.
Aucun commit API ni aucune modification de branche distante n'ont été effectués.

Le mode de conservation est un paquet séparé,
`Enhanced_version_4B_preuves_2026-11-08.zip`, avec bundle Git autonome de clôture,
manifestes SHA et preuves privées. Ce commit documentaire précède sa construction :
le manifeste de l'archive et le reçu
`.runtime/qa/enhanced-4b/publication/publication-blocked.json` portent les contrôles
effectivement réalisés. La confirmation de conservation est fournie au compte
rendu de livraison. L'archive reste hors du push Git et ne vaut pas publication.
EV4B-12 reste ouverte ; les autres résultats et critères demeurent inchangés.
