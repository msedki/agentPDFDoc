# I5 — protocole de reproduction des vérifications

**Rôle :** reproduction des essais I5. **Propriétaire :** qualification.
**Statut :** développement 8 et suivi contrôlé 30 clos ; portes code v3 closes.
Le gel final réservé a été écrit le 9 novembre 2026 à 04:05:09 UTC ; les
manifestes exacts ont ensuite été copiés et la matérialisation réelle vérifiée.
La campagne réservée v3, commencée à 04:13:46 UTC, a subi une rupture de
continuité du service d’exécution pendant D03. Root a ratifié l’arrêt à
04:40:02 UTC : référence 12 `NOT_RUN`, candidat 12 `BLOCKED`, score documentaire
non calculé (`null`). HTTP est non exécuté et bloqué. La version d’ingénierie
reste **non qualifiée pour la production**. Les six portes documentaires
5–10 ont réussi une fois, sans dérive de sources ; la publication Git reste
à terminer.
**Référence :** `41857e17a438fe43123e4ef8274d9d2d446bfbc2` et modifications
I5 identifiées par les reçus de chaque exécution. Les commandes ci-dessous
sont celles des harnais du dépôt ; leur présence ne constitue pas une preuve
d’exécution. Le bilan distingue chaque porte exécutée, échouée ou non exécutée.

Les identités du gel final, du plan lié et du lancement unique figurent dans
l’[addendum daté](trust-4b-final-blocks-addendum-2026-11-09.md#gel-final-et-ouverture-effectivement-réalisés).
Les sections qui relatent les préparations 5 à 8 conservent leur contexte
historique ; elles ne décrivent pas un maintien actuel du corpus fermé.
La [revue réservée](trust-4b-reserved-review-2026-11-09.md) et le
[relevé des coûts et de l’incident](trust-4b-reserved-resource-costs-2026-11-09.md)
conservent les 24 positions et les seules mesures réellement disponibles.

## Identités et séparation des bras

La référence est le commit `41857e17a438fe43123e4ef8274d9d2d446bfbc2`, dans un worktree isolé. Les extractions et réponses du candidat utilisent un instantané identifié par hash de ses fichiers. Le protocole et ses critères sont gelés dans [trust-4b-protocol-2026-11-08.md](trust-4b-protocol-2026-11-08.md). Le corpus réservé a été préparé par un validateur n’éditant pas le produit ; ses questions ne doivent être ouvertes aux auteurs qu’après le gel final du candidat.

Exécuter les commandes depuis la racine du dépôt sous Python 3.12.14, avec les artefacts déjà provisionnés. Une seule tâche lourde à la fois. Les répertoires de sortie sont neufs ; conserver chaque échec et toute reprise séparément. Placer `--basetemp` hors du dépôt pour ne pas faire entrer les répertoires pytest dans les contrôles de frontière du programme. Ne jamais réutiliser un répertoire de données utilisateur pour ces essais.

## Portes portables et intégration

Ordonnancement décidé avant ouverture, le 9 novembre 2026 UTC : exécuter ces
cinq portes code (indices **0 à 4**) après la revue du développement et avant
le gel final et l’ouverture du transfert réservé. Cet écart d’ordre au §5 du
protocole est consigné dans
l’[addendum préparatoire](trust-4b-final-blocks-addendum-2026-11-09.md) ; il ne
change aucun critère ni périmètre. Il permet de corriger une éventuelle
régression logicielle avant d’accéder aux oracles.

Ces exemples conservent les noms historiques des sorties. Sur ce poste,
elles existent déjà : choisir de nouveaux chemins pour une reproduction ;
les pilotes privés de la session refusent tout écrasement d’un résultat.

```bash
.venv/bin/python -m pytest -q -m 'not acceptance and not slow and not integration' --basetemp=../agentPDFDoc-i5-portable-final-1-tmp --junitxml=.runtime/qa/production-i5-20261108/portable-final-1.xml
.venv/bin/python -m pytest tests/integration -q -m 'integration and not slow' --basetemp=../agentPDFDoc-i5-integration-final-1-tmp --junitxml=.runtime/qa/production-i5-20261108/integration-final-1.xml
.venv/bin/python -m pytest tests/integration/test_ingestion_ocr.py -q --basetemp=../agentPDFDoc-i5-ocr-final-1-tmp --junitxml=.runtime/qa/production-i5-20261108/ocr-final-1.xml
.venv/bin/python -m ruff check services tests tools
.venv/bin/python -m mypy
```

Le module OCR est marqué `integration` **et** `slow` : il ne fait pas partie des deux premières portes. Il faut le lancer séparément pour mesurer le moteur Tesseract réel. Les marqueurs exclus restent exclus, pas réussis. Les tests unitaires identifient leurs doubles de tokenizer, d’embeddings, de transport et de sélection ; les tests de tables synthétiques portent des observations explicites, sans prétendre avoir exécuté une extraction native.

Recontrôler les empreintes des sources et des entrées figées après le
transfert. Si leurs octets exécutables et leurs entrées de test sont inchangés,
les mêmes portes qualifient la livraison finale ; aucune répétition facultative
des suites n’est nécessaire. Une modification exige une nouvelle attribution
explicite des preuves et ne permet pas de régler le produit sur le réservé
déjà ouvert.

## Matrice contrôlée de trente cas

Cette campagne utilise l’extraction Office, SQLite, FTS et QueryService réels avec des doubles identifiés pour E5, le transport vectoriel, le tokenizer et le plan génératif. Elle conserve le même corpus et les mêmes attendus avant/après.

```bash
.venv/bin/python tools/qualification/grounded_campaign.py --application-root ../agentPDFDoc-i5-baseline --profile ../agentPDFDoc-i5-baseline/config/enhanced-4b.yaml --fixtures tests/fixtures/grounded_cases.json --work-dir .runtime/qa/production-i5-20261108/controlled-baseline --output .runtime/qa/production-i5-20261108/controlled-baseline.json
.venv/bin/python tools/qualification/grounded_campaign.py --application-root . --profile config/enhanced-4b.yaml --fixtures tests/fixtures/grounded_cases.json --work-dir .runtime/qa/production-i5-20261108/controlled-candidate --output .runtime/qa/production-i5-20261108/controlled-candidate.json
```

Un suivi supplémentaire a été prévu après stabilisation du candidat final et
**avant** le gel réservé, sans charge native concurrente. Conserver le même
hash de `tests/fixtures/grounded_cases.json`, les trente cas et leurs critères,
mais utiliser de nouvelles sorties pour l'attribuer aux sources exactes de
l'instantané final. Le chemin est choisi explicitement après la revue des
corrections ; l'instantané 6 reste la preuve de sa propre campagne et n'est
plus supposé être la version finale :

```bash
: "${final_candidate_root:?Renseigner le chemin de l'instantané final approuvé}"
.venv/bin/python tools/qualification/grounded_campaign.py --application-root "$final_candidate_root" --profile "$final_candidate_root/config/enhanced-4b.yaml" --fixtures tests/fixtures/grounded_cases.json --work-dir .runtime/qa/production-i5-20261108/controlled-candidate-final-followup-1 --output .runtime/qa/production-i5-20261108/controlled-candidate-final-followup-1.json
```

Cet exemple était préparatoire. Le suivi a ensuite été exécuté sur les 172
fichiers exacts de l’instantané 8, via le pilote privé décrit plus bas. Il conserve
les primaires 12/12 positifs et 16/18 limites ainsi que les échecs L11/L12,
et ne se substitue pas au complément du formateur. Le nouveau groupe reste
distinct ; ses trente observations ne sont pas additionnées aux anciens cas
pour augmenter le dénominateur ni présentées comme des appels natifs du 4B.

## Extraction et moteurs réels

`tools/qualification/prepare_trust_i5.py` vérifie les hashes des originaux, l’identité des fichiers du produit avant/après, la couverture, les délais et l’arrêt des workers possédés. Les fenêtres `development-window` conservent les indices physiques de pages et restent des diagnostics partiels ; elles ne qualifient pas l’ensemble d’un document.

`tools/qualification/run_grounded_native.py` lance des services locaux possédés Ollama/Qdrant, E5, le tokenizer Qwen3-4B et le vrai QueryService. Les versions, poids et paramètres restent identiques dans les deux bras. Le transport `direct` et le transport `http` ont une deadline de bloc de 1 500 s ; les limites de cas et du produit ne changent pas. Une expiration conserve son résultat d’échec et le reçu d’arrêt. Les appels de provisioning servent à vérifier/importer le modèle verrouillé, sans génération documentaire à cette étape.

Les chemins précis des manifestes d’entrée, des gel et des sorties seront ajoutés au bilan après exécution. Le jeu réservé comporte dix questions (huit positives, deux limites) et deux dérivés OCR positifs, par bras. Les blocs A/B/dérivés conservent un seul primaire par cas et par bras ; une éventuelle reprise doit être bornée, identifiée et ne remplace pas le résultat primaire.

## Interface et documentation

Les portes documentaires **5 à 10** du plan final sont exécutées après le bilan
du transfert : brief généré puis contrôlé, pack, documents, diagrammes et diff.
Elles ne remplacent aucune des portes code exécutées avant l’ouverture.

Depuis `apps/web`, utiliser le Node et le pnpm verrouillés : `pnpm test:unit`, `pnpm typecheck`, `pnpm lint`, puis `pnpm build`. Une construction web n’est pas une recette visuelle native du lecteur.

La campagne `frontend-final-1` du 9 novembre a exécuté ces quatre portes :
**487/487 tests Node**, zéro skip, puis TypeScript, ESLint et build avec codes
de sortie nuls ; 242 fichiers d'export sont contrôlés. Ce sont de nouveaux
reçus, distincts des groupes historiques qui restent conservés dans le
[JSON de validation](trust-4b-validation-2026-11-08.json). Le gel
`frontend-final-1-input-freeze.json` SHA-256
`9bee48ccbf220b1030cde857e81fc4c215496addb0db10972e4ef52c058f2264`
couvre 176 fichiers avant/après, sans dérive enregistrée. Cinq configurations
racine supplémentaires, dont `next.config.mjs` et `postcss.config.mjs`, ont été
observées seulement **après** le build, identiques au HEAD à cet instant ; ce
complément ne constitue pas une capture antérieure. L'export reste construit
avant commit : la provenance de la révision livrée, le kit et le navigateur
ne sont pas qualifiés par ces quatre portes.

```bash
.venv/bin/python RAG_Local_Agents/tools/build_brief.py
.venv/bin/python RAG_Local_Agents/tools/build_brief.py --check
.venv/bin/python RAG_Local_Agents/tools/verify_pack.py --report .runtime/qa/production-i5-20261108/pack-final.json
.venv/bin/python tools/docs/check_docs.py --report .runtime/qa/production-i5-20261108/docs-final.json
git diff --check
```

Les kits natifs Windows/Linux et les qualifications de plateforme restent distincts. Un filtre de payload, un catalogue et des fichiers de modèles conformes ne prouvent pas une installation fraîche ni sa consommation mémoire.

## Reprise des campagnes après les observations de développement 4

La phase 4 reste conservée. Ses huit premières requêtes ont rencontré cinq
refus d’admission mémoire et trois réponses déterministes ; aucune n’a appelé
le générateur. La [revue des ressources](trust-4b-resource-observations-2026-11-08.md)
décrit ces résultats sans les remplacer par une reprise favorable.

Le déplacement vérifié des preuves et caches depuis tmpfs est terminé dans le
reçu `tmpfs-preserved/phase5/receipt.json`, SHA-256
`51447ed99918ab7b3b956af993ede19e0969e7c5d7852d9c9ad95b2bbe57167a`.
Ne pas rejouer cette opération : les chemins d’origine désignent désormais les
copies conservées. Les prochaines sorties pytest doivent être neuves, hors du
dépôt et sur un stockage sur disque. Le seuil de départ de la phase 5 est
6 656 Mio disponibles ; la réserve et l’admission du produit restent inchangées.

Le candidat est copié dans un nouvel instantané après stabilisation des
modifications. Le reçu de copie conserve les hashes avant et après des fichiers
`services/`, `config/`, `tools/`, `packages/`, `pyproject.toml` et `uv.lock`.
Cet instantané de développement n’ouvre pas le corpus réservé et ne constitue
pas encore son gel final. Les trois groupes PDF doivent être extraits avec le
nouveau code ; les extractions de la phase 4 ne lui sont pas réattribuées.

Depuis la racine du checkout contenant les artefacts provisionnés, les chemins
de travail pour cette reprise sont :

```bash
qa_dir=.runtime/qa/production-i5-20261108
candidate_root=../agentPDFDoc-i5-diagnostic-snapshot-5

.venv/bin/python tools/qualification/prepare_trust_i5.py --kind development-pdf --inputs .runtime/qa/production-i4-20261108/transfer-candidate-preparation/inputs.json --application-root "$candidate_root" --runtime-root . --output "$qa_dir/development-transfer-candidate-5" --execute
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind development-pdf --inputs .runtime/qa/production-i4-20261108/ocr-candidate-preparation/inputs.json --application-root "$candidate_root" --runtime-root . --output "$qa_dir/development-ocr-candidate-5" --execute
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind development-pdf --inputs .runtime/qa/production-i4-20261108/pdf-candidate-preparation/inputs.json --application-root "$candidate_root" --runtime-root . --output "$qa_dir/development-ti-candidate-5" --execute
```

Chaque commande est séquentielle. Son reçu doit montrer des sources inchangées,
des groupes de workers vides et des leaders réapés avant l’action suivante.
Une extraction échouée conserve sa sortie et bloque seulement les requêtes qui
en dépendent ; elle n’autorise pas l’utilisation silencieuse d’une ancienne
extraction.

Les vingt questions de développement restent réparties comme suit. Les
identifiants passés à `run_grounded_native.py` sont répétés avec `--case-id` ;
aucune sélection par réussite n’est autorisée.

| Bloc | Cas | Manifeste candidat |
|---|---|---|
| Transfert A | H01, H02, H03, H04 | `development-transfer-candidate-5/inputs.json` |
| Transfert B | H05, H06, H07, H08 | Même manifeste de transfert |
| Scans | SCAN1_H04, SCAN2_H07 | `development-ocr-candidate-5/inputs.json` |
| PDF TI | N_ina226, N_tmp117 | `development-ti-candidate-5/inputs.json` |
| Office | P01_general_condition, P05_sparse_table, P10_decimal_sum, P11_conversion, L01_condition_mismatch, L06_cross_document_conflict, L13_negated_value, L16_table_note | `.runtime/qa/grounded-20261108/native-inputs-v2/inputs.json` |

Exemple complet du premier bloc, après son extraction :

```bash
.venv/bin/python tools/qualification/run_grounded_native.py --application-root "$candidate_root" --label candidate --inputs "$qa_dir/development-transfer-candidate-5/inputs.json" --output "$qa_dir/development-transfer-a-candidate-queries-5" --case-id H01 --case-id H02 --case-id H03 --case-id H04
```

Le bras de référence reprend le worktree `../agentPDFDoc-i5-baseline` et ses
manifestes I4 identiques, avec les mêmes vingt cas et de nouvelles sorties
suffixées `baseline-queries-5`. Les préparations Office restent communes, leurs
adaptateurs étant inchangés. Après chaque bloc, `service-stop.json` doit porter
`all_owned_services_stopped: true` ; les erreurs de réponse restent enregistrées
et ne deviennent pas des réussites parce que les services se sont arrêtés.

## Suivi de développement 6 après l'incident de précontrôle

Les commandes phase 5 ci-dessus décrivent une campagne conservée. Son bras de
référence compte vingt mesures terminales ; le candidat a terminé seulement
les quatre requêtes du bloc A. Le bloc B échoue avant le démarrage des services
sur un bind de port. Les extractions scans et TI ont ensuite été terminées,
sans nouvelle requête ni reprise de B. La
[revue du harnais](trust-4b-harness-recovery-2026-11-09.md) conserve cet incident,
sa cause historique inconnue et le contre-exemple de sockets qui justifie le
raccord au helper `port_probe` déjà présent dans le runtime. Aucun service
étranger n'est arrêté par cette correction.

Après stabilisation et revue des correctifs H03 et du regroupement des
conditions SCAN2, root a créé l'instantané 6 de 169 fichiers et lancé la
campagne à 01:25:34 UTC. Son reçu de copie porte le SHA-256
`f6c39760709a5bdb1cd454f9a99ba850d472583e6000f396e7c9b9ee8b293690`.
L'ingestion ayant changé dans `table_geometry.py`, le plan sélectionne trois
lots PDF complets neufs et cinq blocs de requêtes. Voici les commandes de cette
reprise ; elles ne doivent pas être rejouées dans les mêmes sorties existantes :

```bash
qa_dir=.runtime/qa/production-i5-20261108
.venv/bin/python "$qa_dir/prepare-snapshot-phase6.py"
.venv/bin/python "$qa_dir/prepare-candidate-phase6.py" --snapshot-receipt "$qa_dir/diagnostic-snapshot-6.json" --fresh-extractions
.venv/bin/python "$qa_dir/run-candidate-phase6.py"
```

Sans `--fresh-extractions`, le préparateur exige l'identité complète des sources
d'extraction avec l'instantané 5 et les preuves des trois lots terminés ; il
refuse toute dérive d'ingestion, runtime, configuration, dépendance ou
préparateur. Ce mode ne doit pas être choisi si SCAN2 modifie l'ingestion. Le
mode neuf contient huit actions, le mode de réutilisation cinq ; tous deux
gardent cinq blocs de requêtes et les vingt cas de développement initiaux.
Les sorties sont suffixées `-6`, les primaires phase 5 restent conservés et
la référence phase 5 est explicitement réutilisée. Le pilote s'arrête sur tout
échec de bloc, dérive d'identité, interruption ou nettoyage non prouvé, sans
relance automatique. Cette campagne est un suivi de développement non aveugle.

Le collecteur technique phase 5 constate 24 mesures terminales sur les 40
positions prévues pour deux bras, soit 23 états `done`, un `error` et seize
positions non observées. Les traces vérifiées montrent quinze demandes modèle
enregistrées et quatorze réponses reçues. Le métrique `model_called=false`
du timeout H06 ne signifie donc pas absence de tentative. Ces observations
ne sont pas des verdicts documentaires et ne s'additionnent pas à de futurs
instantanés du même collecteur comme de nouvelles requêtes.

## Réception réservée après le gel final

Le dossier `heldout-private` n’est ouvert aux auteurs qu’après le gel final
du produit et des harnais. Le reçu de corpus déjà connu reste
`6f095117dc3a49734270ef633e5b5f94ee3dc0bfed45f0a8ff0fd8faf99f1091`.
Les commandes préparées utilisent `prepare_trust_i5.py --kind transfer` puis
`--kind ocr`, avec `--heldout "$qa_dir/heldout-private"`, le checkout candidat
gelé, `--runtime-root .`, une sortie neuve et `--execute`. Elles vérifient les
originaux, les manifestes et le Tesseract corrigé avant les workers. Aucun
téléchargement ni remplacement d’oracle n’a lieu dans ce harnais.

Le [découpage préalable des blocs réservés](trust-4b-final-blocks-addendum-2026-11-09.md)
remplace chaque ancien bloc de cinq cas par 2 + 2 + 1 : T01–T02, T03–T04, T05,
puis T06–T07, T08–T09, T10, suivis des deux dérivés ensemble. Il y a quatorze
blocs natifs au total et douze observations primaires uniques par bras. Le
plafond reste 1 500 secondes par bloc, indexation incluse ; 300 secondes est le
délai d’inactivité HTTP du produit, tandis que la tâche du harnais a une limite
de 600 secondes puis 30 secondes de cancellation. Les nouveaux coûts de
démarrage et de réindexation sont conservés dans les mesures, sans assimiler
ces latences à celles des anciens blocs de cinq.
La fidélité de tous les segments, les limites et la complétude sont relues
contre les pages originales, séparément des états techniques `done` ou `error`.
Tout changement produit après ouverture invaliderait le caractère réservé de
ce jeu pour la version suivante ; il ne doit pas être présenté comme une
nouvelle mesure indépendante sur les mêmes oracles.

La préparation de cette session utilisait `final-reserved-run-plan-v3.json`
et `run-final-reserved-v3.py`. Root a effectivement écrit
`final-reserved-source-freeze-v3.json`, SHA-256
`3835b9ea656e92c7cf80de04267d1b8632f346de4c6f152f1da35f8a0c091472`,
sur l’instantané 8 explicitement approuvé, après les cinq portes code,
le suivi contrôlé 30 et la revue du développement. Le matérialiseur est
compris dans ses 172 fichiers source. Les plans v1, v2 et v2-r2 restent
conservés sans exécution ; le reçu de l’instantané 6 reste attribué à sa
seule campagne. L’addendum lie le plan final et la décision d’arrêt, sans
modifier leur contenu après consultation des oracles.

Les paragraphes suivants relatent les préparations antérieures aux suivis
7 et 8 ; leurs attentes de correction sont des états historiques conservés.

La revue L11/L12 a confirmé une réévaluation de `displayed=[]` qui ajoute
`requested_document`, puis donne la priorité à `partial` sur `unassessed`.
Root a décidé une correction après la fin de la phase 6, sans changer ses
sources en cours d'exécution. La fidélité du périmètre H07 et les erreurs
`trace_write_failed` de H06/H08 et N_tmp117 attendent aussi leur disposition.
Les traces fermées conservent ces erreurs sans demande modèle enregistrée ;
elles ne suffisent pas à attribuer une cause native exacte. La qualification
doit distinguer une limite d'analyse d'un document manquant ; les primaires
et leurs critères restent conservés.

Le suivi de développement 7 a démarré le **9 novembre à 02:19:34 UTC**, sur
un instantané distinct de **172 fichiers**. Le constructeur a comparé les
neuf fichiers changés, explicitement approuvés par root, à leurs empreintes
réelles par rapport à 6. Le préparateur a vérifié la clôture des huit actions
6, puis l'identité des sources d'ingestion/runtime, des configurations,
dépendances et préparateurs avant de réemployer les trois groupes d'extractions
complètes 6. Il conserve vingt questions dans cinq blocs, de nouvelles sorties
et la référence phase 5 déclarée. Les diagnostics et erreurs 6 restent un
groupe distinct. L'extraction Office éventuelle reste comprise dans
l'initialisation des blocs Office, sans nouveau worker PDF.

| Identité du suivi 7 | SHA-256 |
|---|---|
| `diagnostic-snapshot-7.json` | `d496b48fc8b4119b9ff7cdd6b1e4960d84dd6b7bf3ffdfa1c16bf1e89a6539df` |
| `development-candidate-plan-7.json` | `15c4c00a40ebbb8e5fc67d138f25ae18ee21c8b99be10c206529448a44bea927` |
| `development-input-evidence-7.json` | `837106d71cccb88ffb0647f9c614f773bfe3083146f049d4445fe9a4472b5d7c` |

Ces reçus se trouvent dans `.runtime/qa/production-i5-20261108/`. Les cinq
blocs sont fermés depuis **02:27:38.761928 UTC** : vingt états `done`, cinq
demandes modèle enregistrées et cinq réponses reçues. Les arrêts et l'absence
de dérive enregistrée sont vérifiés. Les revues restent distinctes de ces
états techniques : **8/10 positifs et 1/2 limite** sur les douze cas PDF, scan
et TI, puis **4/4 positifs et 4/4 limites** sur les huit cas Office. H06, H08
et SCAN2_H07 restent des échecs documentaires. Le gel réservé attend la
disposition de ces résultats, les portes code et les trente contrôlés. Les sélections ciblées de
308, 214 et 142 tests rapportées avant cette phase se recouvrent et ne sont
pas additionnées ni réattribuées aux futures portes finales.

Cette preuve de réemploi porte sur les sources ingestion/runtime, les
configurations complètes, les verrous, les préparateurs et les sorties exactes
6. La phase 6 n'avait pas capturé de gel exhaustif préalable de tous les
binaires, poids et paquets installés. Root accepte cette portée pour le suivi
de développement ; elle ne démontre pas I5-D06 et ne remplace pas le gel
complet du runtime réservé.

### Préparation distincte du suivi 8

La décision et les motifs sont consignés dans
l'[addendum](trust-4b-final-blocks-addendum-2026-11-09.md#suivi-de-développement-8-décidé-avant-tout-accès-réservé).
Le suivi a été préparé après les défauts H06 et H08, sur les mêmes vingt cas et
cinq blocs, sans modifier critères, budgets ou historiques. Les trois scripts
privés de cette session se trouvent sous `.runtime/qa/production-i5-20261108/` :

| Préparation 8 | SHA-256 |
|---|---|
| `prepare-snapshot-phase8.py` | `ac5e1e2ef56ca8d6d84f337ad2fd04b029baafcd061d871686dd0502000c2ec5` |
| `prepare-candidate-phase8.py` | `514c21e01313939bfd03e5f039f9302dff21c4a1207b597ecdc5cf781e63cfae` |
| `run-candidate-phase8.py` | `34e36ed6ab11e761a58e9c0a5b78ec795cce3c6933135ec0a3ce13d55664f84f` |

Au relevé préparatoire, ils n'avaient créé ni instantané ni plan 8. Leur
exécution ultérieure est consignée ci-dessous. Sur une nouvelle reprise, après
stabilisation et revue, fournir au constructeur une option `--approved-change` pour chacun
des chemins effectivement modifiés depuis 7 ; la liste doit être égale au
delta réel, sans nom de fichier supposé. Puis seulement :

```bash
qa_dir=.runtime/qa/production-i5-20261108
.venv/bin/python "$qa_dir/prepare-candidate-phase8.py" --snapshot-receipt "$qa_dir/diagnostic-snapshot-8.json"
.venv/bin/python "$qa_dir/run-candidate-phase8.py"
```

Le premier de ces deux ordres exige un instantané 8 déjà créé par le
constructeur approuvé. Il vérifie directement les trois groupes d'extractions
6 complètes et les identités pertinentes 6/7/8, ainsi que la clôture des cinq
blocs 7. Il ne lance pas d'extraction PDF. Les anciennes mesures, la référence
5 réutilisée et les erreurs 6/7 ne sont ni remplacées ni additionnées aux
résultats 8. Les sorties 8 doivent être neuves, sans reprise automatique.
Le pilote est identique à la version 7 corrigée après les seules substitutions
de noms et de numéro ; la revue statique conserve les gardes avant import et
avant/après chaque bloc. Cette préparation ne qualifie pas les réponses 8.

Avant la commande de gel réservé, root doit contrôler les reçus des portes
code 0 à 4, le suivi contrôlé de trente cas et la revue de développement.
Le dispatcher v3 ne lit pas automatiquement ces reçus : son sous-ordre
`freeze` écrit la barrière source/runtime puis lit les manifestes réservés.
Le contrôle de cet ordre doit donc précéder son invocation.

Les relevés de [développement 6](trust-4b-development-resource-costs-2026-11-09.md),
du [suivi 7](trust-4b-development-phase7-resource-costs-2026-11-09.md)
et du [suivi 8](trust-4b-development-phase8-resource-costs-2026-11-09.md) séparent durées d'extraction, enveloppes d'initialisation, intervalles de
publication des générations et requêtes. Les RSS/PSS sont des sommets
échantillonnés ; aucune qualification 16 Go ou amélioration causale n'est
déduite des temps entre ces campagnes.

Le parcours HTTP/SSE possède sa préparation séparée **v4**,
`final-http-plan-v4.json` SHA-256
`9196faf0b8ceb93f1c962c94e194ba1757031ec136b76a0dd0b7d7897200b9db`.
Il n’a pas été lancé : l’arrêt de l’ancien groupe réservé n’étant pas prouvé,
la décision root interdit toute nouvelle charge native ou HTTP dans cette
session. Le pilote HTTP n’appartient pas au dispatcher réservé. Le cas HTTP01 et son
budget sont inchangés ; les versions FastAPI/Uvicorn/Starlette sont aussi
comparées à leur gel. Un résultat HTTP doit déclarer `operational_passed=true`
et prouver l'arrêt des services ; son simple fichier ou hash ne suffit pas.
Aucun succès HTTP v4 natif n’est revendiqué. Les commandes publiques de
reproduction future figurent à la fin de ce guide ; elles ne valent pas
autorisation de reprendre la session interrompue.

## Exécution 8 et contrôles préalables effectivement reçus

Les cinq blocs de développement 8 sont fermés, du 9 novembre 2026 à
03:08:51 jusqu’à 03:23:52 UTC. Le reçu de fin
`development-candidate-phase8-completion.json` porte le SHA-256
`226ac1d46120e32a0a0cc628392c689447f3d866090b8ba7bf4c2d0634dc6fe9`.
Il vérifie vingt mesures terminales, cinq arrêts complets, les leaders réapés,
l’absence de moteur restant et l’identité des 172 fichiers ROOT/instantané.

| Identité de développement 8 | SHA-256 |
|---|---|
| `diagnostic-snapshot-8.json` | `1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b` |
| `development-candidate-plan-8.json` | `0ed26792f303db5785cba66871688528ec7a1e53a5b4eeb975435889929e85bb` |
| `development-input-evidence-8.json` | `e8cfde8462a6a9283f3aae0b44bc66e16c5ea6ec10680e99d187c799004e3938` |

Les vingt états `done` restent des faits d’exécution. Les revues documentaires
explicites retiennent **12/14 positifs et 6/6 limites** ; `SCAN2_H07` et
`N_tmp117` échouent. Les treize routes déterministes et les sept demandes avec
réponses modèle sont distinguées par leurs traces. Les revues sont non
aveugles et leurs auteurs ont participé à une partie des corrections ; elles
ne constituent pas une recette humaine indépendante ni une preuve HTTP.
Le [bilan de développement](trust-4b-development-review-2026-11-09.md)
et les observations de validation conservent les décisions par cas.

Le suivi contrôlé a été exécuté une fois, de 03:25:39 à 03:25:54 UTC, sur ces
mêmes sources, avec le même profil, le même harnais et le même corpus de trente
cas. Dans cette session, la commande réellement utilisée a été :

```bash
.venv/bin/python .runtime/qa/production-i5-20261108/run-final-controlled.py --source-receipt .runtime/qa/production-i5-20261108/diagnostic-snapshot-8.json --source-sha256 1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b
```

Le pilote privé vérifie les identités avant/après et produit le reçu
`controlled-candidate-final-followup-1-execution.json`, SHA-256
`b98ba82cca716fe445fa54866f8fac8f212463595a0b2c26e0b1a864635c1d49`.
La revue distincte `controlled-candidate-final-followup-1-independent-review-r01.json`
porte `89ebc4e7e40d89f404cbd568a85b2dbd52289bc3a6571a3be9652c2751dbb332`.
Le résultat reste **12/12 positifs et 16/18 limites**, sans requalification :
`L11_plan_prose` et `L12_unknown_reference` échouent avec zéro appel au double
de sélection. L’unique état `error`, `L10_absent_location`, correspond à
l’erreur de provenance attendue et réussit son oracle fixe. Ces trente cas
utilisent les doubles nommés du protocole ; ils n’attestent aucune inférence
4B native. Ils ne s’ajoutent pas aux dénominateurs des primaires ni du complément
du formateur.

### Reprise explicite des portes après deux attentes de test invalidées

`portable-final-1` a produit 5 078 réussites, deux échecs, 25 skips et
48 désélections, sans dérive de ses 549 entrées gelées. Les deux cas supposaient
que le nom `DEV123.pdf` et la question prouvaient à eux seuls le sujet de deux
listes dont aucun texte ne nommait DEV123. Le contrat PDF durci refuse cette
inférence. Root a autorisé une correction du seul fichier
`tests/unit/test_i4_list_subjects.py` : les deux variantes restent présentes
comme négatifs explicites ; les huit vrais positifs avec sujet écrit et leurs
assertions de citations et de conditions sont inchangés. La vérification
ciblée unique conserve les 22 positions, toutes réussies.

Le changement est déclaré par les empreintes
`e7c21fe9e18010c6f516d6e40b7f22b4cc95c42a59f2b9f6aff185f767a4bec2` →
`b59cc655c2f0e9e7b242851d74c92bb009830028e44b1b7494244aba1b6c81b3`.
Le reçu API `portable-list-subject-adjustment-receipt-r01.json`
(`955c803afc78930fc9b565c4d86206e6ec748a49c5f2433d779e5a16ee2fab42`)
et sa revue indépendante
(`c245fafe962f6b89d4f1637535e174e179078179da81e8ed22be21562b039233`)
préservent le rouge et l’ancien fichier. Aucun produit, fixture contrôlée,
profil ou harnais contrôlé n’a changé : les vingt natifs et le suivi contrôlé
restent attribués à leur exécution 8, sans rejeu.

La préparation de portes **v3** est distincte du réservé v3. Elle conserve
549 entrées, dont seul ce test diffère de son gel v2, sans ajout ni suppression.
Le plan porte `9c113f7bcc687e90152302915b9f8210964466927691e0ee18150d1150b86c78`
et le gel `4105946aeef107b7f3c90153f145cea6d21ff23c3a44bf8f6b124023a249bfe0`.
Le pilote `run-final-gates-v3.py` ne change que trois noms de son prédécesseur :
plan, gel et sortie `portable-final-2`. Les autres portes n’avaient pas encore
été invoquées. Leurs reçus doivent être lus avec leur propre hash de plan ;
les sorties v3 ne deviennent jamais des réussites du plan historique v2.

`portable-final-2` est fermé : **5 080 réussites, 25 skips et 48 désélections**,
sans échec ni dérive. La porte d’intégration non lente est fermée avec
**30 réussites, 3 skips Windows et 101 désélections**. Les 22 tests ciblés se
recouvrent avec la suite portable et ne lui sont pas ajoutés. La porte OCR
complète a ensuite réussi **8/8 sans skip** ; Ruff a réussi et Mypy n’a relevé
aucun problème dans **148 fichiers source**. Les cinq portes sont fermées,
avec des empreintes externes concordantes et aucun changement de l’inventaire
code/test avant/après chaque porte. Leur reçu de clôture
`final-code-gates-v3-completion-1.json` porte le SHA-256
`a7ad9e999456423da069346880c4925c6afa9e678ec0b08e59d17de66b57f51d`.
Les sources ROOT/instantané restent les mêmes 172 fichiers. Les skips et
les désélections restent exclus ; les résultats des différents groupes ne
s’additionnent pas. Les métadonnées runtime ne constituent pas un gel
exhaustif des binaires installés.

Les indices 0 à 4 ont été exécutés séquentiellement avec les commandes
suivantes, depuis la racine du dépôt. Elles documentent les exécutions déjà
reçues ; le pilote refuse les mêmes sorties si elles existent. Chaque commande
`run` a été lancée après lecture du résultat et des empreintes de la précédente.

```bash
qa_dir=.runtime/qa/production-i5-20261108
.venv/bin/python "$qa_dir/run-final-gates-v3.py" freeze --source-receipt "$qa_dir/diagnostic-snapshot-8.json"
.venv/bin/python "$qa_dir/run-final-gates-v3.py" run 0
.venv/bin/python "$qa_dir/run-final-gates-v3.py" run 1
.venv/bin/python "$qa_dir/run-final-gates-v3.py" run 2
.venv/bin/python "$qa_dir/run-final-gates-v3.py" run 3
.venv/bin/python "$qa_dir/run-final-gates-v3.py" run 4
```

Les indices documentaires **5 à 10** emploient désormais ce même pilote v3,
après rédaction du bilan. Le pilote v2 reste historique et n’est plus choisi
pour de nouvelles portes : son gel précède la correction de test déclarée.

Root a relu les cinq portes code, le suivi contrôlé et les revues documentaires,
puis a écrit le gel réservé v3. Après la rupture de continuité, il a ratifié
l’arrêt de la campagne ; HTTP reste non exécuté et bloqué.
Aucune commande de cette section ne les ouvre. Les répertoires historiques
existent déjà : les rejouer à l’identique doit être refusé ; une reproduction
séparée utilise des sorties neuves et conserve les tentatives précédentes.

## Reproduire les entrées sur un clone neuf provisionné

Le matérialiseur I4 ne peut pas lire I5 : reçu verrouillé, schémas, nombres de
questions et rendu des scans diffèrent. Le nouvel outil versionné
`tools/qualification/materialize_trust_i5.py` réutilise ses lectures et copies
bornées, puis le validateur et le renderer I5, y compris le dérivé qui comporte
un corps scanné et un pied de page natif. Le sous-mode I5 `derived-reproduction`
ne permet pas d’initialiser un clone vide : il exige déjà les scans gelés avant
de les reproduire.

Avant le gel final, seul `freeze-receipt.json` était présent dans
`RAG_Local_Agents/reports/trust-i5-corpus/`. Après le signal explicite de root,
les **octets exacts** des trois manifestes prégelés y ont été copiés, sans
régénérer leurs questions, leurs oracles ou leurs transformations. Ils font
partie de l’arbre de livraison ; la publication Git reste une étape distincte.

| Fichier | SHA-256 attendu |
|---|---|
| `sources.json` | `4d67dc071c5aa50d0e6a33cc335c9dd727d4a39c1c5fd3ae16a186c157c9a831` |
| `questions-oracles.json` | `b36d32a580efcd644cc0d0299a0002617c64c8552dbc1964e9c7de7319b69af7` |
| `scan-transformations.json` | `ea18764c2a55db5fa61c540539777f288af6f0c52f23d73f60ee5276bedac6d1` |

Un clone doit contenir ces quatre fichiers pour matérialiser les entrées. Le
reçu de copie `trust-i5-manifest-publication-v3.json` porte le SHA-256
`4bb1771745623d6b44faa5fe616478229ceff10a9d58fa23ab1609285cf24d8c`.
Les PDF restent des téléchargements ou des copies locales vérifiées ; ils ne
sont pas ajoutés au dépôt.

Après cette publication, depuis la révision candidate identifiée au bilan et
avec son environnement et ses artefacts natifs provisionnés, utiliser un dossier
de sortie neuf sous `.runtime/qa`. Les commandes suivantes concernent une
reproduction future avec un cycle de vie des processus vérifiable, pas une
reprise de la session interrompue. Conserver cette tentative primaire et ses
24 positions sans les remplacer. La voie réseau est explicite :

```bash
I5_CORPUS=RAG_Local_Agents/reports/trust-i5-corpus
I5_BUNDLE=.runtime/qa/reproduction-i5-1/materialized

.venv/bin/python tools/qualification/materialize_trust_i5.py --corpus "$I5_CORPUS" --output "$I5_BUNDLE" --download
```

La voie locale remplace `--download` par `--source-cache "$I5_SOURCE_CACHE"`, où
ce répertoire contient `originals/` et les trois PDF aux chemins et hashes du
manifeste. Sans ces options, l’outil cherche les originaux sous le dossier des
manifestes ; il ne télécharge rien implicitement. Les seules URL autorisées
proviennent des octets authentifiés par le reçu I5. Le client exige HTTPS,
refuse les redirections et n’utilise pas de proxy d’environnement.

Le reçu `materialization-receipt.json` doit porter `status=materialized_verified`
et `frozen_inputs_verified=true`. Le matérialiseur compare les versions de
PDFium, Pillow et reportlab, les trois originaux, les deux PDF dérivés, leurs
rasters et leur texte natif, puis appelle le validateur I5 complet. Un dossier
`failed` ou `interrupted` reste conservé ; choisir un nouveau nom pour une reprise.
Cette matérialisation n’exécute ni ingestion, ni OCR, ni modèle. La préparation
avait été vérifiée par 43 tests synthétiques avec doubles explicites, plus Ruff
et Mypy. Après le gel final, une unique matérialisation réelle a été exécutée
par copie locale des trois originaux et nouveau rendu des deux paires PDF/PNG.
Elle a produit `materialized_verified`, `frozen_inputs_verified=true` et
`source_inputs_unchanged=true`, avec Pillow 12.3.0, pypdfium2 5.13.0 et reportlab
5.0.1. Le mode réseau n’a pas été exercé par cette preuve.

Le reçu `materialized-i5-1/materialization-receipt.json` porte le SHA-256
`ab31f41def13f9e6553c3548469ebce0a065ffcdc21a53668b316b54d210c67e`.
La vérification complète indépendante de la sortie, des versions et des
172 fichiers source est `materialization-final-v3-verification.json`, SHA-256
`72881ad5c49ad30bddca8fe94e6c4cee4aae55b302eb34bad8b80665c143e5eb`.
Les entrées du plan lié restent celles de `heldout-private`, dont les octets
sont identiques ; la matérialisation n’a pas remplacé silencieusement les
chemins du plan final.

Créer ensuite le worktree de référence si celui-ci n’existe pas déjà, et extraire
les originaux et les dérivés pour chacun des deux bras. Le candidat est la
révision livrée, tenue immuable pendant toute la reproduction :

```bash
I5_BASELINE_ROOT=../agentPDFDoc-i5-baseline
I5_CANDIDATE_ROOT=.
I5_RUN=.runtime/qa/reproduction-i5-1
git worktree add --detach "$I5_BASELINE_ROOT" 41857e17a438fe43123e4ef8274d9d2d446bfbc2

.venv/bin/python tools/qualification/prepare_trust_i5.py --kind transfer --heldout "$I5_BUNDLE" --application-root "$I5_BASELINE_ROOT" --runtime-root . --output "$I5_RUN/baseline-transfer" --worker-timeout 1800 --execute
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind ocr --heldout "$I5_BUNDLE" --application-root "$I5_BASELINE_ROOT" --runtime-root . --output "$I5_RUN/baseline-ocr" --worker-timeout 1800 --execute
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind transfer --heldout "$I5_BUNDLE" --application-root "$I5_CANDIDATE_ROOT" --runtime-root . --output "$I5_RUN/candidate-transfer" --worker-timeout 1800 --execute
.venv/bin/python tools/qualification/prepare_trust_i5.py --kind ocr --heldout "$I5_BUNDLE" --application-root "$I5_CANDIDATE_ROOT" --runtime-root . --output "$I5_RUN/candidate-ocr" --worker-timeout 1800 --execute
```

Ces quatre commandes sont séquentielles et réservées au superviseur Linux
utilisé ici. Vérifier après chacune les sources inchangées et les arrêts de
tous les workers dans `preparation-receipt.json`. Un lot non achevé proprement,
un manifeste final absent ou invalidé bloque les requêtes qui en dépendent ;
cela ne diminue pas le nombre de cas prévus. L’état `ready_partial` reste
analysable avec ses limites, mais ne constitue pas un succès d’utilité.
Cette reproduction effectue de nouvelles extractions
de référence ; la campagne d’origine réutilisait ses extractions de référence
déjà vérifiées. Le temps de préparation doit donc être rapporté séparément.

Les requêtes suivent les sept blocs de l’addendum, référence puis candidat pour
chaque bloc. Exemple complet A1, à reproduire avec les autres identifiants du
tableau et des noms de sortie distincts :

```bash
.venv/bin/python tools/qualification/run_grounded_native.py --application-root "$I5_BASELINE_ROOT" --label baseline --inputs "$I5_RUN/baseline-transfer/inputs.json" --output "$I5_RUN/baseline-a1" --transport direct --case-id T01 --case-id T02
.venv/bin/python tools/qualification/run_grounded_native.py --application-root "$I5_CANDIDATE_ROOT" --label candidate --inputs "$I5_RUN/candidate-transfer/inputs.json" --output "$I5_RUN/candidate-a1" --transport direct --case-id T01 --case-id T02
```

Pour le bloc dérivé, utiliser les manifestes `baseline-ocr/inputs.json` et
`candidate-ocr/inputs.json`, sans `--case-id` : chacun contient exactement les
deux primaires dérivés gelés. Les sorties `service-stop.json` doivent confirmer
les groupes vides et les leaders réapés avant la suite. Garder 6 656 Mio
disponibles au départ de chaque action et ne lancer aucune autre charge lourde.
Conserver tous les fichiers de mesure, y compris erreurs et cas non démarrés ;
ne jamais rejouer automatiquement un primaire pour améliorer son résultat.

Le code des commandes, les quatre manifestes publics et les artefacts verrouillés
suffisent à cette reproduction. Les chemins privés de la session d’origine
servent à rattacher les premières observations ; ils ne sont pas des entrées
requises sur un nouveau clone.

## Reproduction future du parcours HTTP/SSE par les outils publics

Le parcours de cette session est **NOT_RUN/BLOCKED**, selon
`root-reserved-stop-disposition-r01.json`, SHA-256
`7af3f487d920f9861965fd3542a0c786d10476af051725018c2df9ce5abad07c`.
Les commandes suivantes ne reprennent pas cette session. Elles décrivent une
nouvelle reproduction sur la révision livrée immuable, avec sorties neuves,
cycle de vie des processus vérifiable, arrêts précédents prouvés et une seule
charge lourde. Les pilotes privés de la session ne sont pas nécessaires.

```bash
I5_CANDIDATE_ROOT=.
I5_RUN=.runtime/qa/reproduction-i5-http-1

.venv/bin/python tools/qualification/prepare_production_i4.py --kind http --output "$I5_RUN/http-inputs"
.venv/bin/python tools/qualification/run_grounded_native.py --application-root "$I5_CANDIDATE_ROOT" --label candidate --inputs "$I5_RUN/http-inputs/inputs.json" --output "$I5_RUN/http-candidate" --transport http
```

Le préparateur crée trois DOCX locaux : A porte 2,8 V, B porte 3,2 V et
A_new porte 3,0 V, pour AX71 à 70 °C. A_new remplace la version de A sous
le même chemin logique `http/A.docx`. Le cas HTTP01 demande de restituer le
désaccord A/B sans arbitrage. La préparation `--kind http` n’emploie ni
`--heldout` ni `--execute` et ne lance aucun modèle.

Le nouveau manifeste contient un horodatage et des chemins absolus propres
à cette reproduction. Il ne doit pas être annoncé identique au manifeste
historique de la préparation v4, SHA-256
`60bb114321623805945851d1b28d46f448ef37dbd82e4cd634d8a91c38a1f2d2`.
Consigner les nouveaux hashes du manifeste et des trois DOCX ; vérifier
l’équivalence attendue des textes, du chemin de remplacement, du cas et des
critères d’acceptation. Une équivalence de scénario ne remplace pas une
comparaison de bytes lorsque l’on revendique la même entrée exacte.

Le lanceur utilise par défaut les ports locaux Ollama 11439 et Qdrant 6339.
Vérifier les préconditions de mémoire et l’absence de charge native concurrente
avant le lancement. Des ports libres ne prouvent pas à eux seuls l’arrêt d’un
ancien groupe. Conserver le résultat HTTP, les mesures, traces et reçus d’arrêt.
La réussite exige notamment `operational_passed=true`, un appel modèle réel,
l’absence de fragments publics non vérifiés ou d’événements structurés privés
servis au client, et l’immutabilité de l’ancienne citation et de son original
après mise à jour. Un état technique terminé ou un fichier présent ne suffit pas.

HTTP01 est un contrôle distinct des 24 positions réservées. Il exerce HTTP/SSE
sur boucle locale, les workers Office et les services natifs ; il ne qualifie
ni le navigateur, ni une installation propre sur les plateformes cibles.
