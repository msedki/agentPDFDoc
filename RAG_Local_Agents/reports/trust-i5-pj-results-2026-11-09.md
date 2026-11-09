# I5-PJ — opérateurs numériques, conditions et évaluation du vérificateur

**Rôle :** bilan des changements et preuves du complément I5 demandé avec la
pièce jointe. **Propriétaire :** intégration et qualification RAG.
**Statut :** essais et portes logicielles terminés avec leurs échecs et
limites conservés ; sources publiées et arbre distant vérifié ; qualification
de production non acquise.
**Référence :** `fe4693da07ed9e948f65e4cadb51cd43ec36ebe2` et modifications
I5-PJ du 9 novembre 2026 (UTC), branche `enhanced_version` ; commit technique
[5502cf42](https://github.com/msedki/agentPDFDoc/commit/5502cf424b1d9211b5a63014b01c7ab8b998dc85).
**Source de vérité :** ce bilan pour les résultats ; [protocole gelé](trust-i5-pj-protocol-2026-11-09.md)
pour les critères ; [plan](../PLAN.md) pour les actions.

## 1. Défauts et correction

La référence publiée peut transformer une borne numérique en valeur exacte.
Le défaut n'est pas la disparition du signe dans la citation : le passage
reste exact, mais le contrat accepte son nombre pour établir une égalité.
Une comparaison avec une autre source donnant la valeur frontière peut ainsi
afficher une concordance injustifiée. Une autre sonde montre qu'une condition
explicitement exclue peut être reconnue comme point d'application de la valeur.

Les contrôles ajoutés distinguent les opérateurs locaux de l'opérande et la
polarité des points d'application. Les extraits restent littéraux ; une borne
ou non-égalité ne devient ni valeur exacte ni entrée de comparaison/calcul.
Une condition exclue reconnue par cette grammaire ne couvre pas une condition
positive demandée. Les
parenthèses, coordinations reconnues et exceptions placées avant la valeur
restent dans le champ de cette correction. Les messages de réponse partielle
expliquent ce qui est établi et ce que le contrat ne peut pas conclure.

Il n'y a ni changement de modèle, ni ajout d'un juge génératif, ni nouveau
paramètre de production permettant de désactiver ces contrôles. Cette
grammaire FR/EN est bornée aux relations explicites ; elle ne démontre pas
une compréhension générale du langage. Les limites d'OCR, de qualité de
document et de couverture du corpus restent distinctes.

## 2. Protocole et lecture des mesures

La [bibliographie examinée](trust-i5-pj-research-2026-11-09.md) distingue les
résultats publiés et les hypothèses locales. Les
[empreintes des jeux](trust-i5-pj-fixture-freeze-2026-11-09.json) sont fixées
avant la modification produit : 24 cas de développement et 24 cas finaux.
Chaque jeu contient 12 appuis exacts positifs et 12 cas qui n'établissent pas
une valeur exacte applicable à la question. Les passages, valeurs et
identifiants documentaires sont distincts entre jeux ; il s'agit de familles
synthétiques de clauses, pas de domaines industriels indépendants.

Les annotations ont été rédigées par un rôle distinct de l'auteur produit,
puis relues séparément. Elles ne constituent pas une annotation par des
experts humains. Les cas négatifs peuvent contenir des informations utiles :
une borne, une non-égalité ou une exception reste une information à restituer.

Le taux de faux acceptés mesure la **décision d'appui exact du contrat**.
Ce taux ne compte pas directement les phrases publiques inventées. Les
littéraux rendus, les conclusions de comparaison et les réponses natives ont
leurs contrôles séparés. Les répétitions servent à mesurer la variabilité et
les coûts ; elles ne multiplient pas l'effectif indépendant. Le premier essai
est la mesure de qualité principale, tous les essais restent conservés.

La restitution extractive de référence affiche tous les extraits. Elle
mesure la conservation littérale, sans décision de suffisance et donc sans
taux de faux acceptés/rejetés. Les ablations désactivent chaque nouveau
contrôle uniquement dans le processus de diagnostic, jamais dans le profil
du produit. Les tests du harnais vérifient qu'elles réintroduisent effectivement
les défauts qu'elles doivent isoler.

## 3. Observations initiales conservées

- Référence distante vérifiée et worktree détaché exact ; travaux I6 locaux
  non publiés préservés dans leur copie existante.
- Régression ciblée initiale : **196 PASS**. Les nouveaux contre-exemples
  produisent **26 FAIL / 10 PASS** avant correction : les tests existants
  ne couvraient pas ces frontières.
- Matrice contrôlée historique rejouée sur la référence : **12/12 positifs**,
  **16/18 limites**, citations **27/27**. L11/L12 conservent leur échec de
  frontière non exercée ; le supplément historique n'est pas substitué.
- Deux PDF synthétiques sont réellement extraits par la voie native
  Docling/PDFium. Le texte des deux clauses, les hashes, les coordonnées et
  l'absence d'OCR sont contrôlés avant les questions. Aucun résultat OCR
  n'est déduit de cette observation.

Les essais de développement intermédiaires restent distincts du candidat
final. Une tentative d'ablation a observé une modification des sources pendant
la mesure : elle est invalide et ne contribue pas aux métriques finales.
Le défaut de synchronisation et sa reprise sont conservés dans le journal.

## 4. Résultats finaux

### 4.1 Appui exact et conservation des preuves

Le [reçu complet des contrôles](trust-i5-pj-support-results-2026-11-09.json)
contient les 48 questions, annotations, passages, premières réponses,
relations retenues et rejetées, résultats des répétitions et empreintes.
La [relecture indépendante](trust-i5-pj-review-2026-11-09.md) vérifie également
valeurs, unités, sujets, conditions et formulation publique, sans considérer
le statut donné par le produit comme une vérité de référence.

| Mesure | Développement référence | Développement candidat | Final référence | Final candidat |
|---|---:|---:|---:|---:|
| Cas prévus et exécutés | 24/24 | 24/24 | 24/24 | 24/24 |
| Faux appuis exacts acceptés, sur 12 négatifs | 10/12 | **0/12** | 9/12 | **1/12** |
| Vrais appuis rejetés, sur 12 positifs | 2/12 | **2/12** | 3/12 | **3/12** |
| Couverture positive exacte | 10/12 | **10/12** | 9/12 | **9/12** |
| Cas conformes à toutes leurs attentes | 12/24 | **22/24** | 12/24 | **20/24** |
| Passages justificatifs complets conservés | 28/28 | **28/28** | 28/28 | **28/28** |
| Erreurs d'exécution | 0 | 0 | 0 | 0 |

Les taux de faux appuis sont donc 83,3 % → 0 % en développement et
75 % → 8,3 % au final. Ces proportions décrivent les cas volontairement
adversariaux de ces petits jeux ; elles n'estiment pas un taux d'erreur en
production. Il n'y a aucun nouveau faux rejet positif, mais la cible absolue
de 12/12 positifs de chaque fixture reste **non atteinte**. Les 3 répétitions
de chaque cas ont les mêmes verdicts et restitutions utiles ; elles ne font
pas de 24 cas un échantillon de 72 questions indépendantes.

Le comptage manuel des **opérandes incorrects admis** est distinct :
12/12 → 0/12 négatifs en développement, 11/12 → 1/12 au final. Un cas peut
déjà être partiel pour une autre raison tout en admettant une mauvaise donnée
intermédiaire. C'est notamment le cas des comparaisons D17/D18 ; le chiffre
10/12 de faux appuis complets ne signifie pas que les deux autres cas
négatifs avaient une représentation entièrement correcte.

La restitution strictement extractive conserve 28/28 passages dans chaque
jeu. Elle n'émet aucune décision d'appui exact : ses taux de faux acceptés et
faux rejetés restent `null`. Citer un passage qui porte une exception ne
prouve pas que cette exception est comprise.

### 4.2 Contribution de chaque contrôle

Les ablations utilisent exclusivement les données de développement et un
processus diagnostic isolé. Elles ne modifient ni le profil ni le code livré.

| Configuration de développement | Faux appuis complets / 12 | Opérandes incorrects admis / 12, relecture | Positifs couverts / 12 | Littéraux |
|---|---:|---:|---:|---:|
| Candidat complet | 0 | 0 | 10 | 28/28 |
| Contrôle d'exactitude numérique désactivé | 6 | 8 | 10 | 28/28 |
| Contrôle des points exclus désactivé | 4 | 4 | 10 | 28/28 |
| Deux contrôles désactivés | 10 | 12 | 10 | 28/28 |

Ces contre-épreuves réintroduisent les erreurs attendues. Elles soutiennent
le bénéfice local des deux contrôles, sans démontrer la compréhension de
toutes les formes linguistiques. Aucun seuil ni correctif n'est ajusté sur
les résultats finaux.

### 4.3 Échecs finaux conservés

**H24 — faux appui, critère zéro erreur non atteint.** Le document donne
« Le courant de sortie du KZ727 est de 34 mA à l’exception de TA = 46 °C. ».
La question demande le courant à ce point exclu. Le texte source est
fidèlement reproduit, mais le contrat accepte encore 34 mA comme valeur
applicable et indique `covered`, sans limite explicite. La forme française
« à l'exception de » n'appartient pas aux formes reconnues par la garde
gelée. C'est une erreur du vérificateur, pas une perte de citation. La version
n'est pas retouchée après cette découverte sur le test final.

**H06 — faux rejet préexistant.** La source donne une tension exacte de
5,7 V et indique séparément que le courant ne dépasse pas 26 mA. La négation
de la clause de courant contamine encore le statut de la tension. Le passage
entier reste présent, mais le refus et son explication sont incorrects.

**H11/H12 — comparaisons préexistantes incomplètes.** Les deux fiches donnent
respectivement 7,1/7,1 V et 8,8/9,7 V, correctement cités. Le croisement
excessif des obligations sujet/document empêche encore la comparaison
demandée. Les mêmes défauts D11/D12 restent visibles en développement.
Ces échecs ne sont ni retirés des dénominateurs ni transformés en abstentions
réussies.

### 4.4 Coût du contrôle isolé

| Jeu et révision | Médiane | p95 | RSS du processus, maximum échantillonné |
|---|---:|---:|---:|
| Développement référence | 59,70 ms | 113,40 ms | 54,98 Mio |
| Développement candidat | 53,55 ms | 100,56 ms | 55,05 Mio |
| Final référence | 46,77 ms | 89,84 ms | 54,93 Mio |
| Final candidat | 65,86 ms | 118,70 ms | 55,17 Mio |

Le p95 candidat reste sous le budget préalable de 250 ms pour le catalogue,
le contrat et le rendu instrumentés avec `tracemalloc`. La mémoire est celle
du processus Python, échantillonnée après les essais ; elle n'est ni une
mesure de pointe continue ni la consommation de la chaîne native. Les coûts
varient selon les formulations et ne démontrent pas un gain de vitesse
général. Les doubles de comptage de tokens et de sélection sont déclarés ;
aucune latence de ce tableau n'est présentée comme celle du 4B.

### 4.5 Chaîne native et parcours HTTP

Le [reçu natif détaillé](trust-i5-pj-native-results-2026-11-09.json) conserve
les réponses, citations, relations, paramètres, empreintes, compteurs et
preuves d'arrêt. Les douze originaux sont dix DOCX et deux PDF synthétiques.
Les paragraphes DOCX et les clauses PDF sont préservés dans les extractions
réelles ; chaque original conserve son empreinte. Les PDF ont été extraits
par le préparateur réel, puis leurs extractions vérifiées sont réemployées
par les deux bras ; ils ne sont pas présentés comme une réextraction
indépendante par bras. Aucun OCR n'est exécuté dans ce complément.

| Mesure sur les 11 questions natives | Référence | Candidat |
|---|---:|---:|
| Questions terminées | 11, dont 1 supplément | 11/11 |
| Faux appuis complets, sur 7 cas négatifs | 4/7 | **0/7** |
| Cas avec opérande incorrect admis, relecture | 5/7 | **0/7** |
| Couverture positive exacte | 3/4 | **3/4** |
| Passages complets présents dans réponse et citations | 14/14 | **14/14** |
| Appels 4B réels reçus et terminés | 4 | **8** |
| Tokens effectivement reçus du 4B | 214 | **411** |
| Médiane des latences de question | 0,591 s | **53,043 s** |
| p95 empirique au rang supérieur / maximum | 144,310 s | **153,920 s** |
| Somme des latences des 11 questions | 363,015 s | **603,484 s** |
| Pic de somme RSS des processus suivis | 4 193,26 Mio | **4 164,10 Mio** |
| Pic de somme PSS | 4 185,46 Mio | **4 155,48 Mio** |
| Pic de somme USS | 4 182,47 Mio | **4 151,67 Mio** |

Les quatre cas devenus partiels N_D13, N_D21, NP01 et NP03 passent de la
route déterministe à une sélection de références par le 4B. Ils prennent
environ 48 à 71 secondes contre moins de 0,7 seconde auparavant. Le gain de
fidélité a donc un **coût natif mesuré**, malgré le faible coût isolé des
gardes. Aucun gain général de vitesse ni de mémoire n'est revendiqué. Le
faux rejet positif N_D11 reste un échec de complétude.

Sur NP03, la référence publie une concordance entre « less than 3.3 V » et
« exactly 3.3 V », alors que les citations sont exactes. Le candidat conserve
les deux extraits et précise que la borne ne fournit pas une valeur exacte
pour la comparaison. Le contrôle de reconstruction de la référence passait
malgré son erreur ; cette relecture illustre la nécessité d'évaluer aussi
le vérificateur.

Les appels réels sont établis par une requête au modèle verrouillé, une
`llm.response` avec `received_done=true`, une capture complète et un nombre
de tokens reçus positif. Le champ `model_called` seul n'est pas la preuve.
Les corps de requête et identités sont conservés. Les options de serveur
demandées restent distinguées de leur vérification effective ; les traces
indiquent `server_options_verified=false`.

Le premier bloc de référence produit dix réponses puis s'arrête en erreur
avant NP03 : le manifeste omettait `document_key`, lu par défaut même avec
un scope explicite. Cet échec du dispositif reste conservé. Un nouveau
manifeste ajoute ce seul champ, sans changer documents, textes, question,
scope ou annotation ; NP03 est exécuté dans un supplément neuf. Le bilan
de référence comprend donc **12 tentatives, une erreur avant requête et
11 réponses**, avec leur provenance. Aucun essai échoué n'est remplacé
silencieusement. Le candidat termine les onze questions sans erreur, sur
ce même manifeste réparé. Les trois blocs ferment tous leurs processus
possédés et ne présentent aucune dérive du code.

L'hôte est un environnement Linux x86-64 de développement, CPU Intel Xeon
Platinum 8573C, neuf CPU logiques visibles, mémoire déclarée
10 451 423 232 octets. Les services natifs lourds s'exécutent séquentiellement ;
de courts contrôles de contrat et travaux de revue ont partagé l'hôte.
Les latences sont des observations locales, pas une recette du poste
physique cible. Avec onze observations, le p95 au rang supérieur est le
maximum. Le supplément NP03 redémarre ses services ; sa mesure n'est pas
une comparaison contrôlée d'état froid/chaud. RSS additionne des pages
éventuellement partagées ; PSS/USS restent rapportées séparément.

Le parcours HTTP01 est un essai distinct du candidat, avec le manifeste
historique prévu pour ce harnais : deux DOCX donnant 2,8 V et 3,2 V pour
AX71 à 70 °C, puis remplacement de la première version par une nouvelle.
Trois workers d'ingestion natifs sont lancés, sans substitut. Un appel réel
au 4B se termine avec 52 tokens reçus ; le harnais HTTP mesure 149,375 secondes
entre la soumission et la lecture du résultat (149,053 secondes dans les
métriques applicatives de la requête).

La relecture confirme une réponse qui cite les deux valeurs et leur
condition, expose le désaccord et n'arbitre pas les sources. Les neuf
contrôles de publication et les sept contrôles de versions passent : pas de
delta public avant validation, aucun événement structuré privé exposé,
terminal unique, réponse stockée identique, anciennes citations et anciens
originaux inchangés après remplacement. La reprise du flux après son
terminal est vide. L'API ferme son écoute, les services possédés sont
arrêtés, le code reste inchangé et le bloc retourne 0. Ce résultat concerne
un parcours HTTP/SSE local ; aucun navigateur ni installation neuve n'est
qualifié par cet essai. Les résultats du parcours I5 historique interrompu
ne sont pas réécrits.

### 4.6 Portes logicielles et documentation

Le [reçu logiciel complet](trust-i5-pj-validation-2026-11-09.json) conserve
les commandes, empreintes, échecs initiaux, reprises et comptes exacts.

| Contrôle exécuté | Résultat observé |
|---|---|
| Régressions existantes sur référence, avant correction | 196 PASS |
| Premiers contre-exemples sur référence | 26 FAIL attendus, 10 PASS ; avant extension de la matrice de régression |
| Suite ciblée finale | 351 PASS, dont 64 nouvelles régressions numériques |
| Tests du nouveau banc de mesure | 23 PASS ; inclus dans la suite portable |
| Suite portable complète | **5 166 PASS, 1 FAIL préexistant, 25 SKIP, 48 désélectionnés**, 879,50 s |
| Reproduction du FAIL sur référence immuable | Même test documentaire en échec, 1 FAIL en 1,43 s |
| Reprise après correction documentaire | **105 PASS** en 95,71 s, dans les trois modules documentaires concernés |
| Ruff, `services tests tools` | PASS |
| Mypy configuré | PASS, 152 fichiers source |
| Matrice contrôlée historique appariée | 12/12 positifs et 16/18 limites dans chaque bras, citations 27/27 |

L'unique échec portable est `test_no_document_denies_the_linux_kit` : la date
du document de déploiement (8 novembre) précédait celle du commit I5 du kit,
publié le 9 novembre. Le même échec est reproduit sur `fe4693da`. L'en-tête
est actualisé, avec la référence publiée et la distinction entre hôte Linux
préparé et installation/kit neuf. Aucune règle du produit ni assertion de
test n'est changée. Les 105 tests documentaires sont rejoués ; le premier
résultat portable rouge reste conservé. La suite complète n'est pas relancée
après cette modification uniquement documentaire. Le produit correspond
toujours aux 143 fichiers du gel, dont 87 fichiers de services.

La matrice historique conserve les échecs L11/L12 : la route déterministe
n'exerce pas la frontière du sélecteur injecté. Ils ne deviennent pas des
PASS par absence de texte interdit. L10 bloque correctement un localisateur
absent par l'erreur attendue `invalid_source_locator`. Le proxy de recherche
littérale donne 15/15, celui de contexte sérialisé 14/15 ; P05 garde son
motif de tableau non retrouvé par ce contrôle. Ces mesures avec doubles
ne certifient pas le retrieval natif. Leurs coûts observés sont conservés
dans le reçu ; l'exécution candidate chevauche Mypy et les tests
documentaires et n'est pas une comparaison de performances isolée.

Les portes de documentation passent : liens et métadonnées, index, versions,
schémas SVG, synchronisation du brief régénéré, vérification du pack et
`git diff --check`. Le reçu conserve les avertissements préexistants du
registre de skills tiers ; aucune skill n’est modifiée. Ces contrôles de
cohérence ne qualifient pas les réponses, les moteurs natifs ou le matériel.

Les autres risques de la pièce jointe sont couverts par des régressions
existantes à des niveaux différents. Ils ne sont pas tous réévalués par les
48 nouvelles questions ni par les onze essais natifs.

| Risque | Exemples de modules de test | Portée et limite |
|---|---|---|
| Contradictions et preuves partielles | `test_grounded_evidence_contract`, `test_production_evidence_contract`, `test_i5_obligation_publication`, `test_i5_unassessed_diagnostic` | Préservation des variantes, absence d'arbitrage inventé, demande non analysée distincte d'une absence ; témoins contrôlés. |
| Tableaux, unités, conditions | `test_i5_single_value_tables`, `test_i5_table_condition_scope`, `test_enhanced_units`, `test_i5_pj_numeric_semantics` | Géométrie, cellules, relecture SQLite, conversions et relations ; aucune nouvelle qualification de tableaux OCR industriels. |
| Versions et doublons | `test_api_storage`, `test_grounded_retrieval`, `test_retrieval` | Générations, déduplication et provenance ; la persistance après remplacement est aussi vérifiée séparément par le parcours HTTP natif. |
| Ordre et contexte long | `test_enhanced_retrieval`, `test_api_context`, `test_i5_model_context`, `test_generation_output_budget` | Classement déterministe, preuves nécessaires, quotas et coupures ; pas de nouvelle étude des effets de position du vrai 4B. |
| Injection et sortie non autorisée | `test_development_instruction_isolation`, `test_api_structured_answer`, `test_api_typed_answer_transport`, `test_qualification_restore_injection` | Isolation des instructions, refus de prose/références non autorisées ; transports simulés, pas de nouvelle attaque documentaire native. |
| Pannes et publication | `test_i4_operational_frontiers`, `test_trace_provision_fail_closed`, `test_query_trace_terminal` | Délais, sorties tronquées, échecs de persistance et absence de delta non validé ; fautes injectées et logique réelle. |
| Interruptions et ressources | `test_runtime_resources`, `test_api_jobs`, `test_i5_native_deadline`, `test_ingestion_checkpoint` | Admission, leases, annulation, reprise et checkpoints ; pressions simulées, arrêts réels documentés séparément. |
| Extraction PDF/OCR | `test_ingestion_pdfium_crop`, `test_ingestion_docling_contract`, `test_ingestion_numeric_evidence`, `test_i5_ocr_recheck` | PDFium réel sans modèle pour géométrie ; observations OCR contrôlées. Les campagnes OCR `integration`/`slow` restent hors suite portable. |

Les modules cités sont sous `tests/unit/`. La sélection portable filtre les
marqueurs, pas les noms de dossiers : les tests HTTP/session sous
`tests/integration/` non marqués sont sélectionnés, avec faux embeddings,
vecteurs, tokenizer et Ollama déclarés. Inversement, certaines fonctions sous
`tests/unit/` marquées `integration` sont exclues. Les résultats effectifs et
les skips sont ceux du reçu terminal, jamais déduits du nom du répertoire.

### 4.7 État de la Definition of Done

| Critère fixé avant essais | État du complément | Preuve et limite |
|---|---|---|
| PJ-D01 — zéro faux appui numérique/condition exclue | **NON ATTEINT** | Développement 0/12 et natif 0/7, mais final 1/12 : H24 reste accepté au point exclu. Aucun réglage après ouverture. |
| PJ-D02 — aucun nouveau faux rejet positif | **ATTEINT** | Positifs 10/12 en développement, 9/12 au final et 3/4 en natif, identiques à la référence. La cible absolue de couverture 100 % reste non atteinte. |
| PJ-D03 — littéraux, références et contrôle des données du 4B | **ATTEINT dans le périmètre vérifié** | 28/28 passages de chaque jeu, 14/14 passages natifs avec citations ; le 4B sélectionne des IDs et le code restitue les faits. L'applicabilité sémantique reste en échec sous PJ-D01. |
| PJ-D04 — régressions, suite portable, Ruff et Mypy | **ATTEINT avec reprise documentaire tracée** | 5 166 PASS et seul FAIL préexistant reproduit ; date corrigée, 105 contrôles documentaires PASS. Produit gelé inchangé, 351 ciblés et Ruff/Mypy PASS ; premier résultat rouge conservé. |
| PJ-D05 — final séparé, gel et absence d'ajustement | **ATTEINT** | Fichier final hashé avant produit, ouvert après gel, 24/24 cas exécutés sans dérive, faux acceptés/rejetés et échecs conservés. Annotation séparée par agents, pas expertise humaine. |
| PJ-D06 — chaîne native et au moins deux vrais appels 4B par bras | **ATTEINT** | E5/Qdrant/SQLite/tokenizer/4B réels, 4 appels référence et 8 candidat terminés ; un appel HTTP distinct. Aucun substitut compté comme inférence. |
| PJ-D07 — plafonds, coût du contrôle et arrêts | **ATTEINT dans le périmètre local** | p95 contrôle final 118,70 ms < 250 ms ; caps inchangés, coûts natifs rapportés, tous processus possédés arrêtés. Forte hausse de latence des cas devenus partiels ; poste cible physique non qualifié. |
| PJ-D08 — reproduction, documentation et publication | **ATTEINT** | 32 fichiers publiés dans [5502cf42](https://github.com/msedki/agentPDFDoc/commit/5502cf424b1d9211b5a63014b01c7ab8b998dc85), arbre identique au commit local, parent et branche relus après mise à jour sans force ; [reçu](trust-i5-pj-publication-2026-11-09.json). Portes documentaires PASS. |

**Préparation à la production : non acquise.** Les réussites de conservation,
de protocole et d'exploitation ne compensent ni H24, ni les faux rejets, ni
les limites documentaires et de plateformes héritées. La livraison du
correctif porte sur un bénéfice mesuré et ses réserves.

## 5. Limites déjà identifiées

Les deux comparaisons positives D11/D12 du jeu de développement sont partielles
sur la référence malgré des valeurs exactes correctement citées. Les
obligations croisent chaque sujet avec chaque document, ce qui demande à une
fiche d'établir également la valeur de l'autre équipement. Leurs échecs restent
au dénominateur ; les annotations ne sont pas modifiées. Corriger ce problème
exige un travail distinct sur la portée comparative et les dépendances entre
sujets, documents et propriétés, avec ses propres contre-exemples.

Le complément ne requalifie pas SCAN2, TMP117, le transfert industriel
interrompu, une installation neuve, Windows ou Linux aarch64. Le petit jeu
synthétique et les essais natifs Linux x86-64 ne démontrent pas l'exactitude
générale ni l'aptitude à une diffusion de production.

Le jeu final est séparé par identités documentaires, textes et valeurs,
mais reste composé de clauses synthétiques proches des mécanismes étudiés.
Les annotations et leur revue sont produites par des agents distincts,
sans validation experte humaine. Le périmètre des nouveaux jeux couvre les
relations numériques et conditions ; les tableaux complexes, documents
périmés, ordres de lecture difficiles, attaques documentaires et longs
contextes ne reçoivent pas une nouvelle qualification native par ces 48 cas.
Leurs régressions logicielles historiques restent identifiées comme telles.

La recherche lexicale, dense, hybride et le reclassement restent inchangés.
Les défauts reproduits disposent déjà des passages nécessaires ; l'erreur
survient dans leur interprétation. Une hausse du nombre de fragments ou une
compression n'est donc pas adoptée sans gain démontré. Aucun résultat nouveau
comparant ces approches, le découpage ou l'ordre du contexte n'est revendiqué.
Une campagne dédiée sur un corpus représentatif reste nécessaire avant une
décision sur ces composants.

## 6. Décisions et suite du chantier

Le bénéfice mesuré justifie de conserver les gardes H1/H2, à coût de contrôle
borné et sans nouvelle perte des positifs de référence. La comparaison
algébrique des bornes, les poids spécialisés HalluGuard et tout autre modèle
génératif restent différés. Le seul générateur est Qwen3-4B Q4_K_M ; le modèle
d'embeddings E5 ne produit pas de contenu factuel.

La priorité suivante est la portée sémantique des conditions et négations
(H24/H06), puis celle des obligations comparatives (H11/H12). Les cas finaux
ouverts deviennent désormais des données connues : une prochaine évaluation
finale devra employer de nouveaux documents et annotations figés avant
correction. Les critères initiaux restent inchangés.

Sources, [décision](../DECISIONS.md#i5-pj-d01--qualifier-lopérande-et-la-polarité-des-conditions-09112026),
[reproduction](trust-i5-pj-reproduction-2026-11-09.md),
[relecture](trust-i5-pj-review-2026-11-09.md) et
[plan canonique](../PLAN.md) permettent de distinguer implémentation,
preuve locale, échecs et travaux encore nécessaires. La publication du
correctif ne constitue pas une qualification de production.

## 7. Publication vérifiée

Le commit technique `5502cf424b1d9211b5a63014b01c7ab8b998dc85` est publié sur
`enhanced_version`, parent `fe4693da07ed9e948f65e4cadb51cd43ec36ebe2`.
Son arbre `14c56e7783a8b2a73eb26f59315909686e641934` est strictement
identique au commit local examiné `7388f0f61ebaa2ed45091f8854fa0cd47722e10b`.
Les 32 blobs modifiés ont été comparés avant création de l’arbre ; la
référence a avancé avec contrôle de son ancienne valeur, sans force.
Une lecture GitHub puis une récupération Git distincte ont confirmé
le commit, le parent et l’arbre à 14:21:50 UTC le 9 novembre 2026.

Le [reçu détaillé](trust-i5-pj-publication-2026-11-09.json) conserve les
identités, empreintes et limites du transport. La mise à jour documentaire
qui le conserve ne touche ni le produit gelé, ni les annotations, ni les
seuils. PJ-D08 devient atteint ; H24, les faux rejets et les réserves de
production restent inchangés.
