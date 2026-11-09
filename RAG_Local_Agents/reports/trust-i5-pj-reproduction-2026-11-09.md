# I5-PJ — reproduction des mesures et lecture des preuves

**Rôle :** procédure de reproduction du complément I5 demandé avec la pièce jointe. **Propriétaire :** intégration et qualification RAG. **Statut :** Vivant ; procédures et identités vérifiées, réception décrite dans le bilan. **Référence :** `fe4693da07ed9e948f65e4cadb51cd43ec36ebe2` et modifications I5-PJ gelées le 9 novembre 2026 à 13:34:42 UTC. **Mis à jour :** 2026-11-09 13:39 (UTC). **Source de vérité :** ce document pour les commandes ; [protocole](trust-i5-pj-protocol-2026-11-09.md) pour les critères ; [bilan](trust-i5-pj-results-2026-11-09.md) pour les résultats et limites.

Une commande documentée ne constitue pas une preuve d'exécution. Les reçus
identifiés en dernière section permettent de retrouver les sorties réellement
obtenues, les erreurs conservées et les reprises. Le jeu final a été ouvert
après le gel du candidat ; aucune modification produit n'est admise à partir
de ses résultats. Il est désormais connu et ne peut plus servir de nouveau
jeu final aveugle.

## 1. Révisions, environnement et répertoires

La référence est un worktree détaché au commit ci-dessus. Le candidat utilise
le même socle, avec les fichiers identifiés par le
[reçu de gel du candidat](trust-i5-pj-candidate-freeze-2026-11-09.json).
Le harnais charge les modules `services` du checkout choisi et refuse les
imports provenant d'une autre révision. Le même environnement Python et les
mêmes poids immuables sont utilisés pour les deux bras ; SQLite, Qdrant,
stockages de services, conversations et sorties restent séparés.

Depuis la racine du checkout candidat, préparer des destinations **neuves** :

```bash
PJ_ROOT="$PWD"
PJ_PYTHON="$PJ_ROOT/.venv/bin/python"
PJ_BASELINE="$PJ_ROOT/../agentPDFDoc-baseline"
PJ_QA="$PJ_ROOT/.runtime/qa/i5-pj-reproduction-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$PJ_ROOT/.runtime/qa"
mkdir -m 700 "$PJ_QA"

# Seulement si ce worktree n'existe pas déjà :
git worktree add --detach "$PJ_BASELINE" fe4693da07ed9e948f65e4cadb51cd43ec36ebe2
git -C "$PJ_BASELINE" rev-parse HEAD
git -C "$PJ_BASELINE" status --short
```

Lors de la campagne, les racines étaient
`/workspace/scratch/37dafe3f3244/agentPDFDoc` et
`/workspace/scratch/37dafe3f3244/agentPDFDoc-baseline`.
L'environnement Python existant a été partagé en lecture avec l'ancienne
copie de travail ; son code I6 non publié n'a pas été importé dans ces bras.
Les commandes enregistrées utilisent `.venv/bin/python` du checkout courant.
Il faut disposer de cet environnement et des artefacts locaux avant le natif ;
la présente procédure ne décrit pas une installation neuve hors ligne.

Relevé local du 9 novembre 2026 : Python **3.12.14**, Linux
**6.18.57 x86-64**, glibc **2.41**, 9 processeurs logiques visibles et
10 451 423 232 octets de mémoire physique déclarée par `psutil`.
Les métadonnées d'environnement propres à chaque bloc sont dans son
`measurements/protocol-frozen.json`. Elles ne qualifient ni un poste Windows,
ni Linux aarch64, ni un autre budget matériel.

| Ensemble | Versions installées relevées |
|---|---|
| API et transport | FastAPI 0.142.1 ; Uvicorn 0.54.0 ; Pydantic 2.13.5 ; HTTPX 0.28.1 |
| Inférence et tokenisation | ONNX Runtime 1.30.0 ; tokenizers 0.23.2 ; NumPy 2.5.3 |
| Extraction et génération des témoins | Docling 2.131.0 ; pypdfium2 5.13.0 ; python-docx 1.2.0 ; openpyxl 3.1.5 ; ReportLab 5.0.1 |
| Utilitaires | PyYAML 6.0.3 ; psutil 7.2.2 ; lxml 6.1.3 ; defusedxml 0.7.1 |
| Contrôles logiciels | pytest 9.1.1 ; Ruff 0.16.9 ; Mypy 2.3.1 |
| Services natifs verrouillés | Ollama 0.35.0 ; Qdrant 1.19.1, versions contrôlées par le pilote lors de leur disponibilité |

Le profil est [enhanced-4b.yaml](../../config/enhanced-4b.yaml), avec le
[verrou du générateur](../../config/enhanced-4b.lock.json). Le pilote natif
force le CPU et conserve le générateur `qwen3-4b-enhanced:q4km`, Qwen3 4.0B,
Q4_K_M, contexte effectif 8 192, seed 0 et `think=false`. Le GGUF verrouillé
porte le SHA-256
`7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.
E5 reste `intfloat/multilingual-e5-small`, ONNX CPU INT8, dimension 384.
Les limites de contexte, de génération et de ressources du produit ne sont
pas relevées pour les essais.

## 2. Gels et séparation développement/final

Les [empreintes des jeux](trust-i5-pj-fixture-freeze-2026-11-09.json) ont été
fixées avant l'édition du produit. Chaque jeu contient 24 cas : 12 appuis
exacts positifs et 12 cas n'établissant pas une valeur exacte applicable.
Les instances de sources et leurs familles déclarées sont disjointes.
Les annotations proviennent d'un rôle distinct de l'auteur produit ; elles
ne constituent pas une annotation par un expert humain.

| Objet gelé | SHA-256 |
|---|---|
| Protocole Markdown | `5ae83f77322c19599a602c335c4b0204e382893da5746f12b88cf1cbcfc219ba` |
| `tests/fixtures/support_i5_pj_dev.json` | `4209a27891de7af2d080094767a2b19abfab358f1bc8b735debbe2637e8bbb3b` |
| `tests/fixtures/support_i5_pj_final.json` | `0b8edfb53e2d97a520a31d5df2c82d15a1955f929522696a5e1d0c8d687014ed` |
| `tools/qualification/support_benchmark.py` | `0f9ea042729a57349a65cbad7aa0d8d1c0ef9d355cf60bf9ce52b176686102e5` |
| Reçu de gel du candidat | `e63c0c08f321fcab0bb86de9be62221a0efaaf99ff4edb8e7dfb6be560fe5243` |

Le gel produit est daté de **13:34:42 UTC**. L'ouverture du final est datée
de **13:35:31 UTC** ; ses trois bras ont été exécutés sans ablation et sans
réglage ultérieur du produit. Le rédacteur du présent guide a utilisé les
métadonnées et les reçus du rôle d'évaluation, sans ouvrir les cas finaux.
Une reproduction après publication mesure ce jeu connu ; une nouvelle
réception aveugle exige de nouvelles sources et un nouveau gel préalable.

## 3. Mesure du contrat et ablations

[support_benchmark.py](../../tools/qualification/support_benchmark.py)
exécute le vrai catalogue, les obligations, la décision d'appui et le rendu
du contrat. Deux substitutions sont explicites : un compteur de caractères
remplace le tokenizer et un sélecteur autorise toutes les références connues.
Il n'exécute ni extraction, ni retrieval, ni E5, ni Qdrant, ni inférence 4B,
ni HTTP. `extractive_all` restitue les extraits avec leurs références, sans
certifier leur suffisance ; ses taux de faux acceptés/rejetés restent sans
objet.

Exécuter chaque bras dans un processus Python séparé. Voici les paramètres
de la campagne, avec des fichiers de sortie neufs :

```bash
pj_support() {
  "$PJ_PYTHON" tools/qualification/support_benchmark.py \
    --application-root "$1" --fixtures "$2" --output "$PJ_QA/$3.json" \
    --label "$4" --mode "$5" --ablation "$6" --repeats 3
}

PJ_DEV=tests/fixtures/support_i5_pj_dev.json
pj_support "$PJ_BASELINE" "$PJ_DEV" dev-final-baseline baseline contract none
pj_support "$PJ_ROOT" "$PJ_DEV" dev-final-candidate candidate contract none
pj_support "$PJ_ROOT" "$PJ_DEV" dev-final-no-exactness no-exactness contract nonexact_guard
pj_support "$PJ_ROOT" "$PJ_DEV" dev-final-no-exceptions no-exceptions contract exception_guard
pj_support "$PJ_ROOT" "$PJ_DEV" dev-final-no-guards no-guards contract both_guards
pj_support "$PJ_BASELINE" "$PJ_DEV" dev-final-extractive extractive extractive_all none

# Uniquement après le gel ; ces données sont désormais publiées et connues.
PJ_FINAL=tests/fixtures/support_i5_pj_final.json
pj_support "$PJ_BASELINE" "$PJ_FINAL" heldout-baseline baseline contract none
pj_support "$PJ_ROOT" "$PJ_FINAL" heldout-candidate candidate contract none
pj_support "$PJ_BASELINE" "$PJ_FINAL" heldout-extractive extractive extractive_all none
```

Les ablations remplacent les fonctions de garde uniquement dans le processus
de mesure ; aucun drapeau de désactivation n'est ajouté au produit. Le
premier essai reste la mesure principale de chaque cas. Les trois répétitions,
erreurs et variations sont toutes conservées ; elles ne transforment pas
24 cas en 72 observations indépendantes. La latence concerne ce contrôle
Python isolé ; les allocations `tracemalloc` et le RSS du processus ne sont
pas la mémoire de la chaîne native complète.

Le harnais compare les empreintes des sources, du jeu et de lui-même avant
et après le bloc. Une dérive invalide le résultat ; elle n'autorise pas à
conserver le meilleur essai. Les sorties refusent l'écrasement. Une tentative
historique a effectivement été interrompue pour dérive de sources : son
journal reste distinct des six bras `dev-final-*` valides.

## 4. Corpus natif : préparer une fois, partager les entrées

[prepare_support_native.py](../../tools/qualification/prepare_support_native.py)
produit dix DOCX et huit cas à partir du jeu de développement gelé.
[prepare_support_pdf.py](../../tools/qualification/prepare_support_pdf.py)
ajoute deux PDF synthétiques et trois cas ; il réalise leur extraction native
avec PDFium et vérifie littéraux, empreintes de texte, coordonnées et absence
d'OCR. Ces préparateurs ne réalisent aucune inférence 4B.

```bash
"$PJ_PYTHON" tools/qualification/prepare_support_native.py \
  --fixtures tests/fixtures/support_i5_pj_dev.json --output "$PJ_QA/native-inputs"
"$PJ_PYTHON" tools/qualification/prepare_support_pdf.py --output "$PJ_QA/pdf-inputs"
"$PJ_PYTHON" - "$PJ_QA" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
paths = [root / "native-inputs/inputs.json", root / "pdf-inputs/inputs.json"]
native, pdf = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
assert pdf["extraction_passed"] is True
combined = {
    "documents": native["documents"] + pdf["documents"],
    "cases": native["cases"] + pdf["cases"],
    "kind": "I5-PJ-synthetic-development-native-paired",
    "inputs_source_sha256": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    },
    "pdf_extraction_checks": pdf["extraction_checks"],
}
assert len(combined["documents"]) == 12 and len(combined["cases"]) == 11
assert all("document_key" in case for case in combined["cases"])
with (root / "native-combined-inputs-v2.json").open("x", encoding="utf-8") as stream:
    json.dump(combined, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
PY
```

Le manifeste inclut des chemins absolus : le déplacer ou le régénérer dans
un autre dossier change son hash. Comparer aussi les hashes des originaux,
les questions, les annotations et les recettes, puis employer **le même
manifeste** pour les deux bras. Les dix DOCX ont été régénérés indépendamment
à l'identique ; le reçu `native-reproduction-verification.json` le conserve.
La campagne native extrait réellement les DOCX dans chaque bras. Elle
réutilise les extractions PDF déjà vérifiées et gelées : elle ne démontre
pas une nouvelle extraction PDF indépendante à chaque invocation.

## 5. Campagnes natives directes

[run_grounded_native.py](../../tools/qualification/run_grounded_native.py)
exige Linux et les binaires/poids déjà provisionnés sous `.runtime/bin`,
`.runtime/models`, `.runtime/manifests` et `.runtime/cache/huggingface` du
checkout qui contient le pilote. Il lance Ollama, Qdrant et
[revision_campaign.py](../../tools/qualification/revision_campaign.py)
avec des stockages propres au bloc. Les ports loopback 11439, 6339 et 6340
doivent être libres. Le pilote refuse un port occupé et n'arrête aucun
service préexistant. Exécuter les bras **séquentiellement**, une seule charge
native à la fois :

```bash
"$PJ_PYTHON" tools/qualification/run_grounded_native.py \
  --application-root "$PJ_BASELINE" --label baseline \
  --inputs "$PJ_QA/native-combined-inputs-v2.json" --output "$PJ_QA/native-baseline" \
  --ollama-port 11439 --qdrant-port 6339

"$PJ_PYTHON" tools/qualification/run_grounded_native.py \
  --application-root "$PJ_ROOT" --label candidate \
  --inputs "$PJ_QA/native-combined-inputs-v2.json" --output "$PJ_QA/native-candidate" \
  --ollama-port 11439 --qdrant-port 6339
```

Le processus de mesure a une borne globale de 1 500 secondes ; le harnais
direct a une attente de 600 secondes par requête. Ce sont des limites du
harnais, distinctes des délais du produit. Tous les cas demandés restent
dans leur ordre gelé, avec une conversation neuve et sans reprise favorable.

### Reprise historique du cas PDF manquant

Le premier bras baseline a terminé dix cas, puis a rencontré un `KeyError`
sur `document_key` pour `NP03_pdf_compare`, **avant création de requête**
(`query_id=null`). La correction de manifeste a ajouté ce champ par défaut,
sans changer question, documents, scope explicite, annotation ni produit.
Le manifeste corrigé de la session porte le SHA-256
`ae176e4a45d288c5d6bc246301af267272c93a739feb7c7b697471cfb17e6d19`.
Le reçu `native-manifest-repair.json` conserve ancien et nouveau hashes.

Le supplément baseline exécute uniquement le cas manquant ; ses résultats
s'ajoutent aux dix premiers, sans les remplacer. Sa commande est la première
commande native ci-dessus avec `--case-id NP03_pdf_compare` et une sortie
neuve `native-baseline-pdf-supplement`. Le candidat utilise le manifeste
corrigé pour les onze cas. Une nouvelle reproduction avec le préparateur
corrigé n'a pas à recréer volontairement cette erreur.

### Prouver un échange réel avec le 4B et l'arrêt des services

Pour chaque cas, rapprocher le fichier `measurements/<cas>-<bras>-0.json`
de `measurements/data/traces/<query_id>.jsonl`. Un modèle déclaré dans le
profil ou un état `done` seul ne suffit pas. Vérifier ensemble :

1. `run.metrics.model_called=true` dans le résultat du cas ;
2. une phase `llm.request` avec `data.body.model=qwen3-4b-enhanced:q4km` ;
3. `data.verified_model_identity.digest` et `manifest_sha256` identiques au
   manifeste 4B provisionné et vérifié ;
4. une phase `llm.response` avec `data.received_done=true`.

Le manifeste observé porte le SHA-256
`aca799db2a4683a3cbd9002592ca065ed110ab29c5f4059ee65a10012348921e` ;
le digest Ollama est
`0d75b13ba9d0cd42fb445d6979708adacb2679a777fb4cf717d4e6b907bccfdf`.
Ses détails sont `family=qwen3`, `parameter_size=4.0B` et
`quantization_level=Q4_K_M`. N07/N08 du baseline fournissent des points de
lecture de cette chaîne. Les cas résolus ou limités avant génération peuvent
légitimement avoir `model_called=false` ; les compter comme appels 4B serait
incorrect. Le sens documentaire exige une revue séparée de la réponse et
des originaux, même si `support_validation=passed`.

Après chaque bloc, lire `measurement-process.json` (code de retour et
`harness_timeout`) et `service-stop.json`. Ce dernier doit confirmer
`all_owned_services_stopped=true`, groupes possédés vides, leaders récoltés
et `data_preserved=true`. L'erreur d'un cas et l'arrêt réussi sont deux faits
distincts. Le pilote préserve les sorties et ses `finally` arrêtent seulement
les processus qu'il a lancés. Les profils et fichiers Qdrant locaux peuvent
contenir des clés temporaires : publier les reçus examinés, jamais le dossier
d'exécution entier.

## 6. Parcours HTTP/SSE : manifeste propre au transport

La voie `--transport http` délègue au harnais
[production_i4_http.py](../../tools/qualification/production_i4_http.py).
Celui-ci exige le protocole `production-I4-HTTP-SSE-v1`, **un seul cas** et
une version documentaire de remplacement. Le manifeste natif I5 à onze cas
n'est pas une entrée compatible ; deux options `--case-id` ne le convertissent
pas. La procédure compatible existante est :

```bash
"$PJ_PYTHON" tools/qualification/prepare_production_i4.py \
  --kind http --output "$PJ_QA/http-inputs"
"$PJ_PYTHON" tools/qualification/run_grounded_native.py \
  --application-root "$PJ_ROOT" --label candidate --transport http \
  --inputs "$PJ_QA/http-inputs/inputs.json" --output "$PJ_QA/native-http-candidate" \
  --ollama-port 11439 --qdrant-port 6339
```

Le manifeste HTTP de la session, préparé dans
`.runtime/qa/i5-pj-support/http-inputs/inputs.json`, porte le SHA-256
`0cf664a6998d5ccc0e90bff538fc36c912f13af3a9212a388deeb274037dee6e`.
Cette préparation n'a lancé ni requête ni modèle. Le scénario historique
HTTP01 est conservé sans modification du harnais ni de la question.

Cette commande décrit un parcours de transport distinct, avec ingestion
Office réelle, authentification, requête, flux SSE, récupération des citations,
remplacement d'un original et contrôle de l'immuabilité des versions citées.
Elle ne mesure pas les onze questions natives I5 et n'exerce aucun navigateur.
Son exécution effective et son état restent ceux du bilan, pas ceux du présent
exemple. Les preuves attendues sont `measurements/query.json`,
`public-sse.jsonl`, `version-persistence.json`, `api-stop.json`,
`transport-result.json`, puis le reçu parent `http-final-result.json`.
Ce dernier combine le résultat opérationnel et l'arrêt des services ; il
ne certifie pas automatiquement la vérité documentaire.

## 7. Contrôles logiciels et documentaires

Les marqueurs exclus de la suite portable restent exclus. Les tests avec
doubles ne constituent pas une recette native. Exécuter depuis la racine,
sans charge native concurrente ; choisir pour `--basetemp` un dossier neuf
**hors du dépôt**, que pytest pourra nettoyer :

```bash
"$PJ_PYTHON" -m pytest -q -m 'not acceptance and not slow and not integration' \
  --basetemp="$PJ_ROOT/../$(basename "$PJ_QA")-portable-tmp" \
  --junitxml="$PJ_QA/portable.xml"
"$PJ_PYTHON" -m ruff check services tests tools
"$PJ_PYTHON" -m mypy

"$PJ_PYTHON" -m pytest -q tests/unit/test_docs_space.py tests/unit/test_docs_tooling.py \
  --basetemp="$PJ_ROOT/../$(basename "$PJ_QA")-docs-tmp" --junitxml="$PJ_QA/docs.xml"
"$PJ_PYTHON" tools/docs/check_docs.py --report "$PJ_QA/check-docs.json"
"$PJ_PYTHON" tools/docs/diagrams.py --check
"$PJ_PYTHON" RAG_Local_Agents/tools/build_brief.py
"$PJ_PYTHON" RAG_Local_Agents/tools/build_brief.py --check
"$PJ_PYTHON" RAG_Local_Agents/tools/verify_pack.py --report "$PJ_QA/verify-pack.json"
git diff --check
```

`build_brief.py` régénère le brief dérivé à partir des Markdown canoniques ;
ne pas éditer ce brief à la main. Le rapport explicite de `verify_pack.py`
évite de réécrire le reçu historique suivi par Git. Les contrôles
documentaires prouvent la structure et les liens, pas la justesse scientifique
des procédures. Les versions du harnais, du produit et des jeux doivent rester
identiques à celles auxquelles les tests sont attribués.

La commande de suite portable exécutée pour cette session utilise
`--basetemp=/workspace/scratch/37dafe3f3244/qa/portable-temp`,
`--junitxml=.runtime/qa/i5-pj-support/portable-final.xml` et le journal
`/workspace/scratch/37dafe3f3244/qa/portable-final.log`. Le reçu logiciel conserve 5 166 PASS, 1 FAIL documentaire préexistant, 25 SKIP
et 48 désélectionnés, puis la reproduction sur référence et les 105 tests
documentaires réussis après correction de date. Le produit reste gelé ;
la suite entière n’est pas rejouée après cette seule correction documentaire.

## 8. Carte des reçus de cette campagne

Les chemins ci-dessous sont relatifs à la racine du dépôt, sauf la dernière
ligne. Les résultats publiés et leur interprétation sont centralisés dans
le [bilan](trust-i5-pj-results-2026-11-09.md) et les
[mesures structurées](trust-i5-pj-support-results-2026-11-09.json).

| Preuve | Emplacement réel et portée |
|---|---|
| Critères avant correction | `RAG_Local_Agents/reports/trust-i5-pj-protocol-freeze-2026-11-09.json` et protocole associé |
| Jeux et candidat | `trust-i5-pj-fixture-freeze-2026-11-09.json` et `trust-i5-pj-candidate-freeze-2026-11-09.json`, dans le même dossier de rapports |
| Six bras de développement définitifs | `.runtime/qa/i5-pj-support/development-final-execution.json` et `dev-final-*.json` ; commandes absolues, sorties et stabilité des sources |
| Ouverture et trois bras finaux | `.runtime/qa/i5-pj-support/heldout-open.json`, `heldout-execution.json`, `heldout-baseline.json`, `heldout-candidate.json`, `heldout-extractive.json` |
| Tentatives antérieures | `.runtime/qa/i5-pj-support/development-execution.json`, `dev-baseline*.json`, `dev-candidate.json` ; ne pas les substituer aux mesures définitives |
| Préparation du corpus natif | `.runtime/qa/i5-pj-support/native-inputs/`, `pdf-inputs/`, `native-reproduction-verification.json`, `native-combined-inputs.json`, `native-combined-inputs-v2.json`, `native-manifest-repair.json` |
| Baseline natif initial | `.runtime/qa/i5-pj-support/native-baseline/` ; dix cas terminés, erreur prérequête NP03 conservée, code de bloc 1, services possédés arrêtés |
| Cas baseline manquant | `.runtime/qa/i5-pj-support/native-baseline-pdf-supplement/` ; un cas NP03, code de bloc 0, services possédés arrêtés |
| Candidat natif | `.runtime/qa/i5-pj-support/native-candidate/` ; 11 cas terminés, retour 0 et tous services possédés arrêtés |
| HTTP exécuté | `.runtime/qa/i5-pj-support/http-inputs/inputs.json` et `native-http-candidate/` ; retour 0, contrôles opérationnels et revue documentaire PASS, arrêt API/services vérifié |
| Reproductions du défaut et régression ciblée | `../qa/evidence/` : `baseline.json`, essais `red*.xml`, `final.xml`, `stable-candidate-final.json` ; fichiers de session distincts des benchmarks indépendants |

Le reçu `development-final-execution.json` porte le SHA-256
`6193b151b15418f21e2f580ce1d4c6140a770fe8d7f7fa77ecfcf8e6eafc44ff` ;
`heldout-execution.json` porte
`f2cea41ecc252caad4a45267bd054bb4187bbd8d3cb274572709b61307dba60b`.
Les identités des sorties permettent de rattacher une mesure à son essai ;
elles ne remplacent pas l'examen des dénominateurs, erreurs et cas non exercés.

Le corpus est synthétique et borné. Cette reproduction ne requalifie ni les
cas OCR historiques, ni SCAN2/TMP117, ni le transfert industriel interrompu.
Les limites de portée sémantique et la décision de réception restent celles
du bilan ; une amélioration locale ne vaut pas qualification de production.

Les rapports durables [natif et HTTP](trust-i5-pj-native-results-2026-11-09.json)
et [portes logicielles](trust-i5-pj-validation-2026-11-09.json) contiennent
les observations utiles, leurs empreintes et leurs limites ; les chemins
de session ci-dessus permettent une inspection plus fine tant que la copie
de travail est disponible.
