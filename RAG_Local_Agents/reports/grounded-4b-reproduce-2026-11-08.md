# I3 — reproduire les vérifications 4B

**Rôle :** procédure de reproduction. **Propriétaire :** intégration RAG.
**Statut :** commandes du lot I3, 8 novembre 2026 (UTC), limites dans le bilan.

À exécuter depuis la racine du dépôt. Les sorties utilisent des dossiers neufs ;
ne pas réutiliser un dossier de campagne. Le [protocole](grounded-4b-protocol-2026-11-08.md),
l'[addendum F07](grounded-4b-addendum-2026-11-08.md) et le
[bilan](grounded-4b-results-2026-11-08.md) définissent les critères et limites.
Les commandes ci-dessous ne lancent aucun autre générateur.

## Environnement et référence

```bash
uv sync --frozen --group dev
git worktree add --detach ../agentPDFDoc-baseline 3956491a2d7f1f16cefebfe79e92c638b6662c10
```

La référence conserve ses propres sources et son profil. Les deux bras partagent
l'interpréteur verrouillé et les seuls poids immuables. Ils utilisent des bases,
index, conversations et traces distincts. Les pilotes enregistrent empreintes,
versions, profils, ordre et erreurs ; une modification des sources pendant une
mesure est refusée. Les ports 11439/6339/6340 doivent être disponibles.

## Régression logicielle

```bash
.venv/bin/python -m pytest -q -m 'not acceptance and not slow and not integration'
.venv/bin/python -m pytest tests/integration -q -m integration
.venv/bin/python -m pytest -q tests/unit/test_grounded_campaign.py tests/unit/test_grounded_evidence_contract.py tests/unit/test_grounded_query.py tests/unit/test_grounded_retrieval.py tests/unit/test_grounded_runtime.py tests/unit/test_grounded_native_harness.py
.venv/bin/ruff check services/api/answer_contract.py services/api/evidence_selection.py services/api/ollama.py services/api/query.py services/api/retrieval.py services/api/structured_answer.py services/runtime/profile_schema.py tools/qualification/revision_campaign.py tools/qualification/grounded_campaign.py tools/qualification/prepare_grounded_native.py tools/qualification/run_grounded_native.py tools/qualification/replay_grounded_contract.py tools/qualification/replay_grounded_retrieval.py tests/unit/test_api_ocr_provenance.py tests/unit/test_grounded_*.py
.venv/bin/python -m mypy
.venv/bin/python RAG_Local_Agents/tools/build_brief.py --check
.venv/bin/python RAG_Local_Agents/tools/verify_pack.py --report .runtime/qa/I3/pack.json
git diff --check
```

Pour le bras de référence, lancer les deux premières commandes depuis son
worktree, avec le chemin absolu de l'interpréteur du candidat. Un test marqué
ignoré, une dépendance native absente ou une sortie en erreur ne sont pas une
réussite. Les tests `acceptance` demandent le poste/corpus cible et ne sont pas
couverts par la campagne I3. Le bilan identifie les exécutions réellement faites.

## Sondes discriminantes et matrice contrôlée

```bash
.venv/bin/python tools/qualification/replay_grounded_retrieval.py --repository ../agentPDFDoc-baseline --output .runtime/qa/I3/retrieval-before.json
.venv/bin/python tools/qualification/replay_grounded_retrieval.py --repository . --output .runtime/qa/I3/retrieval-after.json
.venv/bin/python tools/qualification/replay_grounded_contract.py --repository ../agentPDFDoc-baseline --inputs RAG_Local_Agents/reports/grounded-4b-grounding-baseline-2026-11-08.json --output .runtime/qa/I3/contract-before.json
.venv/bin/python tools/qualification/replay_grounded_contract.py --repository . --inputs RAG_Local_Agents/reports/grounded-4b-grounding-baseline-2026-11-08.json --output .runtime/qa/I3/contract-after.json
.venv/bin/python tools/qualification/grounded_campaign.py --application-root ../agentPDFDoc-baseline --profile ../agentPDFDoc-baseline/config/enhanced-4b.yaml --fixtures tests/fixtures/grounded_cases.json --work-dir .runtime/qa/I3/controlled-before --output .runtime/qa/I3/controlled-before.json
.venv/bin/python tools/qualification/grounded_campaign.py --application-root . --profile config/enhanced-4b.yaml --fixtures tests/fixtures/grounded_cases.json --work-dir .runtime/qa/I3/controlled-after --output .runtime/qa/I3/controlled-after.json
```

Ces trente cas utilisent l'extraction Office, SQLite, FTS et QueryService réels,
avec doubles nommés pour embedding, transport vectoriel, tokenizer et sélection
générative. Ils ne mesurent pas la qualité intrinsèque du 4B. Le gradeur repose
sur les exigences de la fixture et les citations, pas sur le verdict interne
du contrat. Pour réévaluer une sortie conservée avec un gradeur corrigé :

```bash
.venv/bin/python tools/qualification/grounded_campaign.py --review-report .runtime/qa/I3/controlled-before.json --fixtures tests/fixtures/grounded_cases.json --output .runtime/qa/I3/controlled-before-reviewed.json
```

## Provisionner explicitement les composants natifs

Les commandes suivantes téléchargent des artefacts volumineux et vérifient leurs
empreintes. Le lancement nominal reste sans téléchargement. Le pilote I3 est
prévu pour Linux ; les essais publiés sont Linux x86-64 CPU.

```bash
.venv/bin/python -m services.runtime.artifacts --only ollama
.venv/bin/python -m services.runtime.artifacts --only qdrant
.venv/bin/python -m services.runtime.artifacts --only e5
.venv/bin/python - <<'PY'
import json
from services.runtime.artifacts import ROOT, download
lock = json.loads((ROOT / 'config/enhanced-4b.lock.json').read_text())
download(lock['gguf'], ROOT / '.runtime/models/Qwen3-4B-Q4_K_M.gguf')
tokenizer = lock['tokenizer']
for name, sha256 in tokenizer['files'].items():
    entry = {'url': f"https://huggingface.co/{tokenizer['repository']}/resolve/{tokenizer['revision']}/{name}",
             'sha256': sha256}
    download(entry, ROOT / '.runtime/models/qwen3-4b-tokenizer' / name)
PY
```

`run_grounded_native.py` démarre ses propres services, vérifie leurs versions,
importe le GGUF via `provision_enhanced_4b.py` et contrôle le modèle. Il arrête
uniquement ses groupes de processus, puis conserve le reçu d'arrêt. Le modèle
peut rester chargé entre questions selon la politique adaptative du profil.

## Geler le corpus puis exécuter les deux blocs natifs

```bash
.venv/bin/python tools/qualification/prepare_grounded_native.py --output .runtime/qa/I3/native-inputs --download-official
```

Les deux PDF sont téléchargés depuis TI et comparés aux SHA du corpus observé.
Un changement d'original bloque la préparation ; il faut alors un nouveau corpus
et de nouveaux oracles explicites. Un exemplaire déjà conservé peut être fourni
avec `--pdf-directory`, sans `--download-official`. Les neuf fichiers Office sont
générés depuis la matrice figée. Les deux PDF conservent leur original complet,
mais seule la page physique d'index **0** est extraite pour ce bloc. L'état partiel
et les erreurs de qualité de cette extraction restent présents.

Pour chaque bras, exécuter Office8 puis PDF2 dans des services fraîchement lancés :

```bash
.venv/bin/python tools/qualification/run_grounded_native.py --application-root ../agentPDFDoc-baseline --label baseline --inputs .runtime/qa/I3/native-inputs/inputs.json --output .runtime/qa/I3/native-before-office --case-id P01_general_condition --case-id P05_sparse_table --case-id P10_decimal_sum --case-id P11_conversion --case-id L01_condition_mismatch --case-id L06_cross_document_conflict --case-id L13_negated_value --case-id L16_table_note
.venv/bin/python tools/qualification/run_grounded_native.py --application-root ../agentPDFDoc-baseline --label baseline --inputs .runtime/qa/I3/native-inputs/inputs.json --output .runtime/qa/I3/native-before-pdf --case-id N_ina226 --case-id N_tmp117
.venv/bin/python tools/qualification/run_grounded_native.py --application-root . --label candidate --inputs .runtime/qa/I3/native-inputs/inputs.json --output .runtime/qa/I3/native-after-office --case-id P01_general_condition --case-id P05_sparse_table --case-id P10_decimal_sum --case-id P11_conversion --case-id L01_condition_mismatch --case-id L06_cross_document_conflict --case-id L13_negated_value --case-id L16_table_note
.venv/bin/python tools/qualification/run_grounded_native.py --application-root . --label candidate --inputs .runtime/qa/I3/native-inputs/inputs.json --output .runtime/qa/I3/native-after-pdf --case-id N_ina226 --case-id N_tmp117
```

Ne pas exécuter de suites lourdes pendant ces mesures. Relever séparément :
qualité de recherche et contexte, réponse finale, chaque affirmation et son
passage, calculs, abstentions, erreurs, appel réel au modèle, durée par phase et
pics RSS/PSS/USS. Les mesures natives ne sont pas automatiquement notées : une
relecture des exigences fixées et des sources est nécessaire. Le bilan conserve
les erreurs de préparation, les bras intermédiaires et les limites de comparabilité.

## Mémoire et reprise diagnostique observée

La campagne primaire Office du candidat comporte trois erreurs d'admission,
conservées au dénominateur. Des fixtures temporaires de nos suites précédentes
occupaient une partie de la RAM ; leurs répertoires reproductibles ont été
nettoyés, en préservant originaux, traces, rapports et fixtures des tests échoués.
Le seuil froid reste **5 888 Mio** (4 352 prévus + 1 536 de réserve), sans baisse
des exigences ni modification du modèle. Le [rapport natif](grounded-4b-native-2026-11-08.json)
conserve horodatages, mémoire disponible, empreintes et protocole de reprise.

La reprise a été déclarée avant ses sorties : un essai supplémentaire maximum
pour P01, L01 et L16, après le bloc PDF, dans un nouveau dossier. Elle ne remplace
jamais les huit tentatives primaires. La commande correspondante, sur un corpus
préparé par la version corrigée du préparateur, est :

```bash
.venv/bin/python tools/qualification/run_grounded_native.py --application-root . --label candidate --inputs .runtime/qa/I3/native-inputs/inputs.json --output .runtime/qa/I3/native-after-recovery --case-id P01_general_condition --case-id L01_condition_mismatch --case-id L16_table_note
```

Ne pas interpréter trois terminaisons réussies comme trois réponses conformes :
la relecture du contenu et des réserves reste nécessaire. La qualité de
l'interprétation et le statut d'exécution sont rapportés séparément.

## Activer les changements dans l'application

Après provisionnement des artefacts verrouillés et prérequis du dépôt :

```bash
./rag.sh up --profile config/enhanced-4b.yaml
```

Le profil de lancement par défaut reste le 4B historique. Les profils historiques
restent dans le dépôt ; seul le profil renforcé et ses essais 4B sont concernés
par I3. Aucun essai d'un générateur 2B ou 8B n'a été exécuté dans ce lot.
