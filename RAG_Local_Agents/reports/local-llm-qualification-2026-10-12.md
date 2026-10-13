# Comparaison locale Qwen3.5 9B / 4B — 12 octobre 2026

**Rôle :** rapport de preuves de la comparaison autorisée · **Propriétaire :** qualification locale des modèles, ROOT · **Statut :** première campagne arrêtée après FAIL ; comparaison appariée complémentaire exécutée et relue indépendamment, candidat non promu · **Référence :** dépôt `e253e4dec6e8213eaba6484a03b4236c0b8680eb` ; préparation F04 et entrées épinglées dans `preparation-completion-04.json`, puis correction QA R132 et exécution du harness B02 `749358fd26a360730e4dbdf3439cc1517978eacb42f476d9922aee9621c869e1` ; explicitation locale du contrat le 12 octobre, tests ciblés vérifiés · **Relevé :** 2026-10-13 14:43 UTC / 15:43 Casablanca · **Source de vérité :** reçus et sorties natives cités ci-dessous ; [PLAN](../PLAN.md) pour le suivi, [DECISIONS](../DECISIONS.md) pour les arbitrages.

L'utilisateur a autorisé le seul Qwen3.5 9B Q4_K_M, exclusivement sur GPU, pour
le comparer au 4B existant. Le provisionnement est terminé. La première campagne native est terminée : bounded PASS, Q-MIX FAIL au contrat de
plan, puis arrêt avant DA. Aucun avantage global sur le 4B n'est démontré. La comparaison reste
privée et ne modifie aucun profil livré, catalogue de sélection RAM ou modèle
par défaut.

## Comparaison complémentaire bornée — protocole avant exécution

Le 12 octobre à 14:48 UTC, à la suite de la critique utilisateur, une nouvelle
campagne est préparée. Les deux premières réponses ne permettent pas de
conclure sur la qualité générale du 9B. Le STOP sur un échec du contrat a
empêché l'essai PDF libre. Le plan 9B retenait les faits XLSX dans comparisons ;
la consigne n'explicitait pas leur inclusion obligatoire dans references à
la racine. Ce défaut de contrat est constaté ; sa responsabilité causale dans
la réponse du modèle reste une hypothèse à éprouver.

Le correctif expose cette règle dans une seule phrase du prompt. Les schémas,
validateurs, scopes et rendus restent inchangés. Le rouge d'assertion réel
compte six FAIL, puis 94 tests de contexte/restitution passent, Ruff passe.
Le premier essai avait échoué en setup sur un parent temporaire absent ; il
ne constitue pas le témoin rouge. Les XML et reçus sont conservés dans
`.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/methodology-extension-03/root-controls/`.
Les temporaires unitaires ont été supprimés après ces retours réels.

| Élément figé avant les réponses | Contrat de la nouvelle campagne |
|---|---|
| Périmètre | Six scénarios issus des extractions DEV existantes : fait PDF, faits DOCX, cellules XLSX avec cache absent, question mixte, absence de preuve PDF, analyse DOCX. Aucun corpus final utilisé pour régler le système. |
| Comparaison | Deux réponses par scénario, une du 4B existant et une du seul 9B choisi, exclusivement sur GPU ; aucun nouveau téléchargement. Les entrées appariées et les oracles sont épinglés avant les appels. |
| Paramètres | Ollama 0.35.0, contexte 8192, think=false, température0,2, top_p0,9, quatre threads, seed42. Budgets de sortie réels par mode conservés, identiques au sein de chaque paire. |
| Contrôles distincts | GPU réel et intégrité ; contrat JSON lorsqu'applicable ; faits exacts, couverture des faits demandés, citations valides et justificatives, absence de résultat de formule inventé, abstention lorsqu'aucune preuve ne répond. Aucun juge LLM supplémentaire. |
| Coûts | Chargement séparé des requêtes, premier token, temps prompt/génération, jetons et mémoire disponible/occupation réelle ; mémoire GPU et RSS peuvent se recouvrir sur cet hôte. |
| Arrêt | Douze chats primaires au maximum, sans retry ni optimisation après lecture des réponses. Un FAIL de contenu est conservé et les autres cas indépendants continuent ; transport, sécurité, intégrité, GPU absent ou ressources insuffisantes arrêtent l'exécution. |
| Décision | Matrice appariée par cas et relecture indépendante des sorties. Six cas de développement constituent un test de décision local, pas une preuve statistique de supériorité générale ni la qualification DoD sur les plateformes absentes. |

La première campagne et son STOP restent historiques et inchangés. Les
résultats de cette nouvelle campagne sont **NOT_RUN** à ce relevé. La méthode
s'appuie sur les skills existants `local-llm-qualification`,
`local-cpu-qualification` pour les mesures séparées, `linux-rag-runtime` pour
le GPU et `hybrid-rag-api` pour le contrat. La documentation
[Ollama sur les sorties structurées](https://docs.ollama.com/capabilities/structured-outputs),
reconsultée le 12 octobre, distingue la contrainte de schéma, son explicitation
dans le prompt et la validation applicative. Elle ne garantit pas les faits.

Le gel ROOT `methodology-extension-03/cohort.json` (`713ac90f…`), après
contrôle des six packets et des faits/versions/blocs, fixe trois phases :
4B sur les cas1–3,9B sur les six cas, puis4B sur les cas4–6 ; trois paires
de chaque ordre, un modèle résident. Les chargements et caches restent
distincts, aucune moyenne de vitesse globale non comparable. Les principes
de scénarios contrôlés, mesures multiples et lacunes explicites viennent de
[HELM, publication officielle Stanford CRFM](https://crfm.stanford.edu/2022/11/17/helm.html)
et de la [documentation mainteneur EleutherAI](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/interface.md).
Six paires est une adaptation bornée, pas une prescription de ces sources.
R135 (`d7a1ff00…`) est une revue méthode/source, sans preuve native anticipée.

La [fiche Qwen exacte](https://huggingface.co/Qwen/Qwen3.5-9B/blob/c202236235762e1c871ad0ccb60c8ee5ba337b9a/README.md)
publie MMLU-Pro82,5/79,1 et GPQA Diamond81,7/76,2 pour9B/4B, et recommande
pour les tâches générales non-thinking0,7/0,8 plutôt que0,2/0,9. Ces chiffres
ne mesurent ni notre quantification ni notre corpus. La nouvelle campagne
conserve le profil produit pour isoler le changement de modèle ; elle ne
mesure pas son optimum de réglage. Stabilité entre seeds/répétitions inconnue,
mode comparison distinct non couvert, chaîne retrieval/API/frontend complète
non réexécutée par ces appels directs. Aucun score de supériorité globale.

## Provisionnement et stockage réellement vérifiés

Le téléchargement repris s'est terminé le 12 octobre à 13:14:02 UTC, après
258,44 s. Les six blobs, configuration comprise, totalisent **6 550 825 550
octets** et ont chacun une vérification SHA-256 complète. Le reçu
[`download-completion-02.json`][download] porte l'empreinte
`22716e9ae86497ac51ec751d7d2d74c13c9c59bb88e09d32c6047ff6dac9f0b6`.
La [récolte ROOT][download-root], SHA
`d6fd0b9cceb9566fab10cae8447e3cdaf1e7a8916c057ebc2e0583a8be143505`,
conserve le véritable retour de l'outil `f5e3e0`, code 0, et l'absence fraîche
de son propriétaire. Les identités/stat des six objets sont liées à cette
vérification ; aucune nouvelle lecture des poids n'a été faite pour ce rapport.
L'échec réseau et les données partielles du premier téléchargement restent
conservés séparément.

L'artefact officiel Ollama `qwen3.5:9b-q4_K_M` est épinglé par le manifeste
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`
et la configuration registre
`08f9698c1116d2ba3d2c1751f6e98919823e13bb28ff5eb7451c7bc9b40907c5`.
Les paramètres constatés sont `qwen35`, `9.0B`, `Q4_K_M`, parser et renderer
`qwen3.5` : [préflight officiel][preflight], [manifeste conservé][manifest].
Le total des seules couches est 6 550 825 373 octets ; la configuration ajoute
177 octets au total des six blobs ci-dessus.

Le tokenizer, son template et la licence proviennent de
[Qwen/Qwen3.5-9B à la révision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`](https://huggingface.co/Qwen/Qwen3.5-9B/tree/c202236235762e1c871ad0ccb60c8ee5ba337b9a).
Les OID Git et le SHA LFS officiels sont conservés dans
[`publisher-files-exact-01.json`][publisher]. Le [reçu de provisionnement][tokenizer]
verrouille six fichiers, dont la
[configuration éditeur](https://huggingface.co/Qwen/Qwen3.5-9B/blob/c202236235762e1c871ad0ccb60c8ee5ba337b9a/config.json).
`tokenizer.json`, `tokenizer_config.json` et `chat_template.jinja` sont
byte-identiques à ceux du 4B. La configuration du modèle diffère ; cette
identité des trois fichiers ne qualifie ni la génération 9B ni son coût mémoire.
Le paquet 9B contient aussi un projecteur, contrairement à la référence 4B
textuelle ; aucune entrée image n'est utilisée ni qualifiée ici.

Les deux stockages privés Gemma abandonnés ont été retirés conformément au
choix utilisateur, sans toucher aux preuves ou aux modèles Qwen.
[`after-02.json`][gemma], SHA
`f588695b8d2996371fb10ebf80ae1a6d152659cda9b8f1177159efe728a2af44`,
enregistre **2 448 114 784 octets logiques** retirés et un gain disponible
observé de **2 448 130 048 octets**. Ces deux mesures restent distinctes.
Les trois producteurs connus sont fraîchement absents dans ce reçu ; il ne
prétend pas établir l'absence de tous les processus du poste.

## Références 4B et entrées de comparaison

| Cas | Référence réellement exécutée | Résultat de qualité | Jetons d'entrée / preuves | État 9B au présent relevé |
|---|---|---|---|---|
| A-BOUNDED-TOTAL, cellules A2:C2 | 4B GPU, query `14365689-e028-4a9e-a4c1-fca753985dd7` | **PASS du cas** R124 ; erreur QA native distincte conservée, oracle corrigé et rejoué hors ligne R126 | 876 / 316 | **PASS du cas** [ROOT][bounded9] et [R133][r133], reprise B02 ; 4B également PASS, gain de qualité non établi |
| Q-MIX, trois documents PDF/DOCX/XLSX | 4B GPU P09, query `46f29c62-4dad-4c9d-8eeb-5335d0e5c14d` | **FAIL**, omission des références XLSX B2/C2, R131 | 1 855 / 1 239 | **FAIL du contrat de plan** [ROOT][qmix9] ; aucun rendu publié |
| DA-FR-HISTORICAL, PDF seul | 4B historique CPU, sans repli | **FAIL**, fausse abstention malgré la périodicité source 1020 h | 764 / 574 | **NOT_RUN**, arrêt au premier FAIL 9B ; qualité libre non mesurée |

Pour bounded, l'erreur QA originale comptait uniquement le parent du bloc :
les deux champs C2 autorisés partagent ce parent. [R124][r124] conserve la
réponse native et son PASS sémantique ; [R126][r126] valide la correction de
sélection par parent, hash et containment du segment exact, avec cinq
contre-témoins refusés. Le replay hors ligne ne constitue pas une nouvelle
inférence et ne transforme pas l'ancien retour natif 1 en retour 0.

Pour Q-MIX, [R131][r131] établit que le catalogue détenait `R003`/B2 «72 V» et
`R004`/C2 formule/cache absent. Le plan 4B sélectionne
`R001/R005/R007/R008`, couvrant deux documents sur les trois demandés et aucune
référence XLSX. Le registre de sources contient XLSX, mais son existence ne
prouve pas sa citation dans la réponse. Les compteurs réellement acquis sont
un POST de question et un appel modèle ; A-MIX, CMP4 et les lecteurs n'ont pas
été exécutés. La base froide P09 conserve 13 questions et 77 citations.

Le [packet Q-MIX][qmix-packet], SHA
`d579b7084ff88677485257a08dad7c52adb9a85f2b1d6e0d264181a693d061f3`,
reprend le schéma et le catalogue SQL exacts, les faits et leur provenance,
la question et les options réellement utilisées. Les messages sont
**reconstruits** depuis les fonctions exécutées épinglées et l'historique
vide enregistré. Les comptes natif 4B, local 4B et local 9B sont égaux ; les
serializations locales 4B/9B sont identiques. Cette parité ne remplace pas une
capture des octets de la requête native, absente de ces journaux.

Pour DA, le [packet historique][da-packet] retrouve les empreintes capturées
avant évaluation : messages
`23fbf31bf7a8546e8013a12003eefbce0b4371e3fbf863ae23b0b5ab3bca4bc8`
et serialization
`9a02ae2878ddcc8b0e43b512ed4a1bd7474091198836c96069dc8d2ee39b17c2`.
La preuve relie les instructions figées, les extraits SSE et la source PDF
1020 h au compte natif 764. Elle n'est pas une capture du corps HTTP natif.
Cette branche conserve les messages historiques ; elle n'emploie ni schéma
JSON ni catalogue typé. Seul `num_gpu: 0` est retiré pour imposer le placement
GPU du candidat ; les autres options de génération restent identiques.
La référence DA CPU permet une comparaison qualitative secondaire, **aucune
comparaison de latence GPU/GPU** et aucune attribution causale au seul nombre
de paramètres.

## Protocole arrêté et résultats 9B

La [préparation finale][preparation] limite la comparaison à **trois appels
9B au maximum**, dans l'ordre bounded → Q-MIX → DA historique. Un échec du
candidat arrête la suite ; aucune réponse 4B supplémentaire n'est prévue.
Une baseline 4B FAIL demeure une référence admissible pour mesurer une
amélioration, avec son verdict original conservé. Le candidat doit satisfaire
ses propres contrôles de faits, couverture et citations. Deux appels 9B ont
été réellement exécutés ; le troisième, DA, a été suspendu conformément à
l'arrêt au premier FAIL.

Ollama 0.35.0 est utilisé dans une instance privée hors ligne. Avant chaque
chat, un chargement sans génération par prompt vide doit produire le statut
`load`, puis les contrôles de digest, découverte CUDA/JetPack5, résidence et
offload complet doivent réussir. Le contrat du chargement est celui de
[`GenerateHandler` v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/server/routes.go#L467-L485).
Un profil GPU demandé ou `size_vram > 0` seul ne prouve pas un offload complet.
Les observations RAM physique, RSS/PSS, `size_vram/size` et latences sont
conservées séparément ; elles peuvent se recouvrir sur la mémoire unifiée.

Le premier dispatch a été **refusé par la QA avant Ollama, chargement et
chat** : assertion erronée sur `HOME`, alors que le superviseur définit
`state/home`. Le collecteur réel `1de139` revient 1 ; le broker est fermé puis
récolté par `27f3e9`, code 0, avec onze identités connues fraîchement absentes.
Le [reçu ROOT du premier refus][native-red] conserve le rouge et **zéro
génération 9B**. Aucun défaut de modèle n'est déduit de cet échec QA.

La [correction R132][r132] est limitée au harness QA dans
`benchmark-execution-02` et au dispatcher `native-session-02`, avec sorties
distinctes. Le [harness B02 exécuté][b02-harness] reste distinct du harness
F04 de préparation ; leurs empreintes ne sont pas interchangeables. Elle reprend le même
premier cas ; elle ne rééchantillonne aucune génération antérieure. Les
résultats modèle attendus sont ceux de cette reprise B02, pas ceux du dossier
B01 refusé. La reprise bounded B02 a été réellement récoltée par `09966b`, code 0
(session 67632). Le [verdict ROOT][bounded9], SHA
`65eecf2e0c16ed262f5f42197117bd2eaf05e07cae94302ab1c7034edcfc937b`,
est **PASS du cas** : une génération, 876 jetons d'entrée, 77 jetons générés
et 272 jetons de rendu. Le [terminal B02][bounded9-completion] enregistre un
préchargement froid de 91,343 s, une requête de 16,864 s et le premier fragment
à 5,104 s ; offload CUDA 33/33 avant et après, wait du service 0, récolte et
absences connues acquises, aucune erreur. Le [rendu validé][bounded9-render]
conserve les faits A2/B2/C2, sans calcul de formule ni total hors périmètre.
Le 4B ayant déjà PASS sur ce cas, ce résultat ne démontre pas une amélioration
de qualité.

Q-MIX 9B a été réellement récolté par `b8b172`, code 1 (session 84588). Le
[terminal du cas][qmix9-completion] conserve un `ApiError` de validation :
les références de premier niveau sont `R001/R005/R007/R008`, tandis que le
groupe `comparisons` contient `R002/R003/R004`. Ces sept identifiants existent
dans le catalogue autorisé, mais les trois références du groupe ne figurent
pas dans la sélection principale, ce que le contrat existant refuse. Il ne
s'agit pas de références inconnues ni d'un résultat rendu à corriger :
**aucun rendu validé n'a été produit**. Le [verdict ROOT][qmix9], SHA
`28dfb4b221b9d3584670babcdc652814c1c240bf70df80dc6d0aea282ef3b312`,
conserve ce FAIL et arrête la suite sans retry.

Une génération Q-MIX a été observée, avec offload CUDA 33/33 avant le chat,
1 855 jetons d'entrée et 85 générés. Le [terminal Ollama][qmix9-done] mesure
23,735 s au total, dont 10,638 s d'évaluation du prompt et 13,074 s de
génération. L'absence d'un contrôle de résidence après validation échouée
n'est pas remplacée par une mesure supposée. Wait du service 0, récolte et
absences connues sont acquis ; aucune erreur de sampling ou de cleanup,
sources et stat des blobs inchangés.

DA 9B reste **NON EXÉCUTÉ** : le FAIL historique CPU4B est conservé, mais
aucune comparaison de réponse libre n'a eu lieu. La [clôture ROOT][campaign-cold],
SHA `dd8fd79845f7729c186347bb72352ef1fa80a3b21177936975fcf1158f7ac266`,
enregistre finish `5f2e91` code 0, récolte du propriétaire `53144a` code 0
(session 5859), et 58 identités connues fraîchement absentes. Aucun appel
CPU9B, aucune nouvelle inférence 4B, aucune promotion. La [revue indépendante
R133][r133], SHA
`ff59a4b5ffcd288f871a83e3eef150f0ea5eb7b4f2930bf326849d12082fbc6b`,
lie 45 preuves et confirme bounded PASS, Q-MIX FAIL et DA non exécuté : deux
chats GPU9B et deux chargements sans génération, puis clôture réelle. Le
contrôle `/api/ps` après chat existe pour bounded uniquement ; pour Q-MIX,
la validation échoue avant cette capture. La résidence pré-chat CUDA33/33 est
établie pour les deux cas, sans résidence post-chat Q-MIX inventée.

Les cas typés mesurent le choix de références, la couverture, la fidélité des
faits et le coût d'exécution. Le rendu XLSX déterministe ne mesure pas une
amélioration du style libre du modèle. Seul DA fournit une réponse libre
historique comparable, avec les limites CPU/GPU et d'ancienneté indiquées.
Ce lot ne vaut ni promotion en production, ni seuil RAM qualifié, ni recette
sur 16 Gio, Windows ou x86-64, ni qualification RAG complète.

[download]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/download-completion-02.json
[download-root]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/download-actual-root-02.json
[preflight]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/official-preflight-01.json
[manifest]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/registry-manifest-01.json
[publisher]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/publisher-files-exact-01.json
[tokenizer]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/tokenizer-provision-01.json
[gemma]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/cleanup-gemma-choice-01/after-02.json
[r124]: ../../.runtime/qa/r28-implementation/c05-history/review/typed-native-bounded-actual-semantic-and-qa-failure-review-124.json
[r126]: ../../.runtime/qa/r28-implementation/c05-history/review/typed-clipped-oracle-correction-and-captured-replay-review-126.json
[r131]: ../../.runtime/qa/r28-implementation/c05-history/review/typed-p09-qmix-actual-semantic-review-131.json
[qmix-packet]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/benchmark-preparation-01/qmix-p09-packet-01/actual-4b-qmix-reconstructed-01.json
[da-packet]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/benchmark-preparation-01/prose-baseline-option-01/historical-prose-packet-01.json
[preparation]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/benchmark-preparation-01/preparation-completion-04.json
[native-red]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/native-session-01/root-owner-actual-01.json
[bounded9]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/native-session-02/root-semantic-a-bounded-total.json
[bounded9-completion]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/benchmark-execution-02/gpu-a-bounded-total/completion.json
[bounded9-render]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/benchmark-execution-02/gpu-a-bounded-total/validated-render.json
[qmix9]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/native-session-02/root-semantic-q-mix.json
[qmix9-completion]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/benchmark-execution-02/gpu-q-mix/completion.json
[qmix9-done]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/benchmark-execution-02/gpu-q-mix/native-done.json
[campaign-cold]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/native-session-02/root-owner-actual-02.json
[r132]: ../../.runtime/qa/r28-implementation/c05-history/review/qwen9-private-home-guard-correction-review-132.json
[r133]: ../../.runtime/qa/r28-implementation/c05-history/review/qwen9-native-comparison-actual-review-133.json
[b02-harness]: ../../.runtime/qa/r28-implementation/root/qmix-document-formula-context-20261011/model-qwen9-gpu-13/benchmark-execution-02/benchmark.py

## Résultats appariés du 13 octobre — douze réponses réelles

Le batch corrigé est réellement récolté à0 : dispatch `a221bb`, session94453,
retour `852ce9`. Douze chats, trois préchargements sans génération et trois
déchargements ; 588,27 s de campagne. Aucune génération CPU, reprise de réponse,
modification des entrées ni erreur de transport/ressources. Les douze comptes
natifs de prompt égalent les comptes locaux ; les corps partagés concordent
pour chaque paire, seul le modèle diffère. GPU complet contrôlé avant et après
chaque chat : 4B 34/34, 9B 33/33, CUDA/JetPack5 et contexte 8192. Service arrêté,
wait0/reapedTrue ; contrôle ROOT frais seize identités absentes, sources et
artefacts partagés conservés. Reçu `methodology-extension-03/root-native-actual-02.json`
SHA `7301ae81…`. Ces appels directs Ollama et les vrais validateurs/rendus ne
constituent pas un nouveau parcours retrieval/API/SSE/navigateur de bout en bout.

### Relecture indépendante avant identification des modèles

Le paquet A/B est randomisé par cas, sans identités ni durées, à partir des
sources, catalogues, critères préannoncés et réponses/rendus exacts. Revue
indépendante `blind-quality-review-01.json`, SHA `80f95c41…`, entrée compacte
SHA `4960b1a2…` ; matrice dévoilée seulement après cette revue,
`unblinded-quality-matrix-01.json`, SHA `777c8f3506da25bee9feb1cfb234da9483aebba98b4133859006731acce62bc3`.
PASS signifie que les exigences matérielles du cas sont remplies, avec les
réserves accessoires explicitement consignées ; il ne signifie pas une réponse
parfaite ou une qualification globale. Les plans JSON des quatre réponses
structurées sont tous valides, y compris les deux réponses multi-documents FAIL.

| Cas figé | 4B | 9B | Préférence qualitative |
|---|---|---|---|
| PDF-DIRECT | FAIL | PASS | 9B |
| DOCX-CONSTRAINT | PASS | PASS | tie |
| XLSX-BOUNDED | PASS | PASS | tie |
| MIX-PER-DOCUMENT | FAIL | FAIL | 4B |
| PDF-NO-EVIDENCE | PASS | PASS | 4B |
| DOCX-ANALYSIS | PASS | PASS | 9B |

Sur ces seuls six cas, 4B a quatre réponses acceptables, 9B cinq. Deux préférences
pour chaque modèle et deux égalités : aucun score statistique ni supériorité
universelle déduits. Dans PDF-DIRECT, le 4B donne correctement1020h mais écrit
« extrait S001 » sans balise reconnue ; le 9B fournit une citation exploitable.
DOCX-CONSTRAINT distingue correctement40°C et72V dans les deux réponses.
XLSX-BOUNDED conserve A2/B2/C2, formule et cache absent sans LEN ni total global.
MIX-PER-DOCUMENT reste FAIL pour les deux : le 4B couvre72V dans les trois
sources mais omet la formule/cache C2 ; le 9B omet le document XLSX. La présence
du mêmeSID pour B2 et C2 ne prouve pas la sélection des deux champs.

L'abstention PDF est bornée aux extraits dans les deux réponses ; celle du 4B
est préférée, les détails accessoires du 9B ont des citations/libellés moins
rigoureux. L'analyse DOCX du 9B est mieux ancrée ; celle du 4B introduit des
interprétations accessoires sur une « limite » et la mise en forme non attestée.
La conclusion sur le statut normatif reste prudente dans les deux réponses.
Le contrat de sous-ensemble est respecté après explicitation de consigne ;
l'absence de répétition et le changement de seed par rapport aux essais
historiques ne permettent pas d'attribuer ce résultat uniquement au correctif.

### Coût réellement observé sur ce poste GPU

Durées HTTP en secondes, prompt et sortie complets inclus ; volumes de réponse
différents. Les tokens, TTFT et durées natives séparées restent dans
`technical-matrix-01.json` et les douze `native-done.json`.

| Cas | 4B secondes | 9B secondes |
|---|---:|---:|
| PDF-DIRECT | 16.43 | 17.36 |
| DOCX-CONSTRAINT | 12.26 | 18.76 |
| XLSX-BOUNDED | 13.50 | 15.62 |
| MIX-PER-DOCUMENT | 19.65 | 24.29 |
| PDF-NO-EVIDENCE | 24.58 | 25.46 |
| DOCX-ANALYSIS | 62.76 | 120.39 |

Débit médian de décodage :4B 9.74
jetons/s ;9B 6.69jetons/s.
Chargements sans modèle résident :4B 55,77 s puis50,69 s ;9B 77,51 s. Le cache disque
n'est pas neutralisé, et le cache de prompt est activé par le runtime ;
prompt_eval_cached_count est présent dans les douze réponses :131 pour DOCX-CONSTRAINT et137 pour DOCX-ANALYSIS, pour chaque modèle, zéro pour les quatre autres cas. Ces tokens réutilisés sont observés ; l'efficacité propre du cache n'est pas mesurée. Ce ne sont pas des temps
CPU ni une comparaison de coûts mémoire disjoints sur Jetson.
563 observations ressources : minimum de mémoire disponible hôte
44778635264octets (41.70Gio), au-dessus de la réserve 8 Gio.
RSS et mémoire GPU peuvent se recouvrir ; aucun seuil d'installation ni preuve
physique16Go n'est déduit de cette campagne.

### Décision de fin de campagne

Les douze essais annoncés sont terminés et conservés. Le9B apporte un gain
local de citation et une analyse mieux étayée, avec coût supérieur ; il ne
résout pas le cas multi-documents. Garder le 4B actuel par défaut, ne promouvoir
ni livrer automatiquement le 9B, et conserver le candidat choisi comme ressource
d'essai utile. Aucune grille ni nouveau replay pour obtenir un vainqueur.
Le lot W060 de sélection des profils reste distinct de la qualification d'un
profil haute mémoire. Les réserves métier et plateformes de la DoD restent ouvertes.
