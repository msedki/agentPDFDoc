# I4 — reproduire les vérifications du générateur 4B

**Rôle :** procédure de reproduction et prérequis des preuves.
**Propriétaire :** intégration RAG. **Date :** 8 novembre 2026, UTC.
**Statut :** commandes vérifiées dans les scripts ; le bilan final identifie les
exécutions effectivement réalisées, leurs révisions et leurs résultats.

Cette procédure complète le [protocole I4](production-4b-protocol-2026-11-08.md)
et son [addendum OCR](production-4b-ocr-addendum-2026-11-08.md). Elle ne remplace
ni leurs critères fixés avant essais ni le [PLAN](../PLAN.md). Le
[bilan des résultats](production-4b-results-2026-11-08.md) et le
[manifeste de gel](production-4b-candidate-freeze-2026-11-08.json) relient les
exécutions à l'état du candidat. Une commande
documentée, un plan d'extraction ou une sortie `done` ne constitue pas un PASS.

Les exemples utilisent Bash depuis la racine d'un clone Linux x86-64. Les pilotes
natifs I4 possèdent et arrêtent leurs processus Linux ; ces essais ne qualifient
pas Windows, Linux aarch64, un navigateur ou le poste métier. Ne pas lancer de
suite lourde, extraction/OCR et génération en parallèle. Chaque campagne exige
un dossier neuf ; conserver séparément échecs, diagnostics et reprises.

## 1. Distinguer les révisions et ce qui vient du clone

La référence applicative est **`fa3eabce5ab0c309b1ca8f01602fced2eb7f1dd8`**.
Le candidat est le code I4 final publié sur `enhanced_version`, avec son SHA et
ses empreintes de sources consignés dans le bilan de publication. Ne pas remplacer
ce SHA par un futur HEAD de branche pour annoncer la même comparaison.

Les scripts de qualification du candidat peuvent exécuter les services du
worktree de référence grâce à `--application-root`. Ils enregistrent séparément
le code du harnais, le code applicatif, les profils et les entrées. Les bases,
index et conversations des deux bras sont distincts ; seuls les artefacts
immuables explicitement vérifiés peuvent être partagés.

| Disponible dans Git | À matérialiser localement |
|---|---|
| Code, `uv.lock`, profils, verrous d'artefacts, correctif source OCR, scripts et tests | Environnement Python, binaires natifs, poids E5/Docling/tessdata/Qwen et tokenizer |
| Matrice I3 `tests/fixtures/grounded_cases.json` et développement I4 `tests/fixtures/production_i4_development.json` | DOCX/XLSX déterministes produits par le préparateur ; PDF officiels aux SHA attendus |
| Préparateurs et pilotes natifs/HTTP | Bases, extractions, traces, profils effectifs et reçus générés dans des dossiers neufs |
| Matérialiseur, contrat de lecture et quatre manifestes du transfert gelé | Originaux téléchargés ou fournis aux SHA attendus ; scans reconstruits et vérifiés |
| Recette de construction corrigée et mode d'ablation | Pour rejouer l'ablation historique : workspace de compilation non corrigé, manifeste, raster et reçu SIGFPE d'origine |

Les chemins historiques sous `.runtime/qa/production-i4-20261108/` désignent des
preuves de la session de qualification. **Ils ne sont pas fournis par un clone.**
Les originaux et modèles volumineux ne sont pas à ajouter au dépôt. Un manifeste
de corpus public doit permettre de retrouver les URL, révisions, tailles et
SHA-256, puis de vérifier les octets avant toute mesure. Si une URL ne fournit
plus le SHA gelé, conserver l'échec ; ne pas substituer silencieusement le PDF
courant ni modifier l'oracle.

Depuis un clone neuf, installer l'environnement (section 2), puis les artefacts
natifs (sections 5 et 6) avant les campagnes qui en dépendent. Les matrices
contrôlées et le corpus HTTP sont reconstruits par les scripts versionnés ; les
PDF TI sont téléchargés ou fournis aux SHA attendus (section 8). Les quatre
manifestes versionnés permettent de matérialiser le transfert par la section 12. Un runtime
déjà provisionné doit être vérifié contre les mêmes verrous ; ne pas relancer la
construction OCR neuve sur une installation canonique existante.

L'ablation OCR historique et toutes les extractions du bras baseline utilisant
le binaire non corrigé, PDF2 comme transfert/scans, demandent des artefacts
conservés supplémentaires décrits dans les sections 7 et 10. Ils ne sont pas des
prérequis pour tester le seul candidat. Ne pas exécuter les commandes concernées
tant que `I4_UNPATCHED_BUILD`, `I4_OSD_BASELINE_RECEIPT` ou `I4_BASELINE_RUNTIME`
ne désignent pas les artefacts effectivement matérialisés et vérifiés. Employer
le runtime OCR corrigé avec le code de référence constituerait une autre
expérience, à identifier séparément du protocole avant/après de ce lot.

## 2. Environnement et paramètres à conserver

Les identités viennent de [pyproject.toml](../../pyproject.toml),
[uv.lock](../../uv.lock), [enhanced-4b.lock.json](../../config/enhanced-4b.lock.json),
[artifacts.lock.json](../../config/artifacts.lock.json) et du
[profil renforcé](../../config/enhanced-4b.yaml).

| Composant | Configuration du lot |
|---|---|
| Python | 3.12.14 observé ; projet `>=3.12,<3.13`, environnement installé par le verrou |
| Générateur unique | Qwen3-4B, famille `qwen3`, 4.0B, Q4_K_M, alias `qwen3-4b-enhanced:q4km` |
| GGUF | 2 497 280 256 octets ; SHA-256 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| Runtime génératif | Ollama 0.35.0 ; CPU imposé par le pilote natif, au plus quatre threads |
| Inférence | `num_ctx=8192`, température 0,2, `top_p=0.9`, seed 0, `think=false`, cache KV `q8_0` |
| Sortie et contexte | Au plus 1 536 tokens de sortie, 768 en mode factuel ; plafonds effectifs selon le mode dans le profil ; réserve de contexte 256 tokens |
| Recherche | Qdrant 1.19.1, multilingual-E5-small INT8 ONNX, dimension 384, tokenizer verrouillé ; pas de reranker ajouté |
| Extraction | Docling 2.131.0, docling-core 2.99.0, pypdfium2 5.13.0, Torch 2.14.0 CPU ; versions transitives dans `uv.lock` |
| OCR | Tesseract 5.4.0, Leptonica 1.87.0 ; candidat avec correctif amont de normalisation identifié séparément |
| Ressources | Réserve hôte 1 536 Mio ; estimation de chargement initial 4 352 Mio, soit admission froide à 5 888 Mio ; aucun abaissement pour obtenir une réponse |

L'hôte de mesure initial est Linux x86-64, glibc 2.41, avec 10 451 423 232 octets
de RAM, neuf CPU visibles et sans swap, selon l'inventaire lié au protocole.
Une autre machine doit publier son propre inventaire et ses mesures ; ces nombres
ne sont pas des performances garanties. Le profil effectif et les reçus précisent
les routes déterministes, les appels réels au modèle, les paramètres d'inférence,
les durées par phase et les pics mémoire disponibles.

Préparer un environnement et des chemins propres avec `uv` accessible et Python
3.12. Le verrou fixe les dépendances ; les reçus doivent relever la version
effective de Python, pas seulement la contrainte du projet :

```bash
uv sync --frozen --group dev
I4_ROOT="$(pwd -P)"
I4_PYTHON="$I4_ROOT/.venv/bin/python"
I4_BASELINE="$(dirname "$I4_ROOT")/agentPDFDoc-i4-reference"
I4_RUN="$I4_ROOT/.runtime/qa/I4-reproduction-20261108-01"
I4_TMP_ROOT="$(dirname "$I4_ROOT")/agentPDFDoc-i4-reproduction-20261108-01"
mkdir -p "$I4_ROOT/.runtime/qa"
mkdir "$I4_RUN"
mkdir "$I4_TMP_ROOT"
git worktree add --detach "$I4_BASELINE" fa3eabce5ab0c309b1ca8f01602fced2eb7f1dd8
git rev-parse HEAD > "$I4_RUN/candidate-commit.txt"
git status --short > "$I4_RUN/candidate-worktree-status.txt"
git -C "$I4_BASELINE" rev-parse HEAD > "$I4_RUN/baseline-commit.txt"
sha256sum uv.lock config/enhanced-4b.yaml config/enhanced-4b.lock.json config/artifacts.lock.json > "$I4_RUN/config-hashes.txt"
```

Choisir un autre suffixe pour une nouvelle reproduction. Si un chemin existe,
examiner son contenu plutôt que de le supprimer. Le worktree de référence reste
immuable pendant les essais. Les outils détectent une modification des sources
pendant la mesure ; un résultat obtenu avant la dernière modification ne qualifie
pas automatiquement le candidat final.

`I4_TMP_ROOT` est explicitement **extérieur au dépôt**, sous
`../agentPDFDoc-i4-reproduction-20261108-01`. Les sous-dossiers transmis à
`pytest --basetemp` sont réservés à une seule exécution : pytest peut nettoyer
ce chemin. Ne jamais y désigner un dossier contenant des données à conserver,
ni replacer ces temporaires sous le dépôt. Cette séparation est nécessaire aux
contrôles qui exercent les frontières entre dépôt applicatif et espace utilisateur.

## 3. Tests portables, unités et contrôles statiques

La suite portable exclut les marqueurs demandant services réels, corpus cible ou
travail lourd. Elle se lance avec le même interpréteur verrouillé sur les deux
révisions :

```bash
(
  cd "$I4_BASELINE"
  "$I4_PYTHON" -m pytest -q -m 'not acceptance and not slow and not integration' --basetemp="$I4_TMP_ROOT/portable-baseline" --junitxml="$I4_RUN/portable-baseline.xml"
)
"$I4_PYTHON" -m pytest -q -m 'not acceptance and not slow and not integration' --basetemp="$I4_TMP_ROOT/portable-candidate" --junitxml="$I4_RUN/portable-candidate.xml"
```

Les contrôles de développement I4 et de contrat peuvent être isolés :

```bash
"$I4_PYTHON" -m pytest -q tests/unit/test_i4_*.py tests/unit/test_production_*.py --basetemp="$I4_TMP_ROOT/i4-unit" --junitxml="$I4_RUN/i4-unit.xml"
"$I4_PYTHON" -m pytest -q tests/unit/test_grounded_evidence_contract.py tests/unit/test_enhanced_answers.py tests/unit/test_grounded_query.py tests/unit/test_grounded_retrieval.py tests/unit/test_grounded_runtime.py --basetemp="$I4_TMP_ROOT/grounded-unit" --junitxml="$I4_RUN/grounded-unit.xml"
"$I4_PYTHON" -m pytest tests/integration -q -m 'integration and not slow' --basetemp="$I4_TMP_ROOT/integration-without-slow" --junitxml="$I4_RUN/integration-without-slow.xml"
.venv/bin/ruff check services tools/qualification tests/unit
"$I4_PYTHON" -m mypy
"$I4_PYTHON" RAG_Local_Agents/tools/build_brief.py --check
"$I4_PYTHON" RAG_Local_Agents/tools/verify_pack.py --report "$I4_RUN/pack.json"
git diff --check
```

Les listes plus larges ci-dessus sont des commandes de reproduction disponibles,
pas une affirmation qu'elles ont toutes été exécutées sous cette forme exacte.
Les reçus du bilan donnent les sélections réellement lancées. Les tests de
sélection/contexte utilisent SQLite et les vrais contrôles de provenance, avec
doubles nommés pour ranking, embeddings et tokenizer ; ils ne mesurent pas le
rappel d'un modèle dense réel. Les tests qualitatifs ne constituent pas une preuve
générale d'implication sémantique. Les contrôles de harnais ne remplacent pas leur
exécution native. Un test ignoré reste `SKIP`, avec sa raison.

## 4. Matrice contrôlée I3 : trente cas inchangés

Le pilote [grounded_campaign.py](../../tools/qualification/grounded_campaign.py)
recrée les documents Office déterministes à partir de la fixture versionnée. Il
utilise extraction Office, SQLite, FTS et QueryService, mais des doubles pour les
embeddings, le transport vectoriel, le tokenizer et le sélecteur génératif.

```bash
"$I4_PYTHON" tools/qualification/grounded_campaign.py --application-root "$I4_BASELINE" --profile "$I4_BASELINE/config/enhanced-4b.yaml" --fixtures tests/fixtures/grounded_cases.json --work-dir "$I4_RUN/controlled-baseline" --output "$I4_RUN/controlled-baseline.json"
"$I4_PYTHON" tools/qualification/grounded_campaign.py --application-root "$I4_ROOT" --profile config/enhanced-4b.yaml --fixtures tests/fixtures/grounded_cases.json --work-dir "$I4_RUN/controlled-candidate" --output "$I4_RUN/controlled-candidate.json"
```

Les douze cas positifs et les dix-huit limites doivent rester séparés pour
détecter les réponses utiles perdues ou l'augmentation des abstentions. Une
réévaluation d'un rapport conservé, sans rejouer l'application, s'écrit :

```bash
"$I4_PYTHON" tools/qualification/grounded_campaign.py --review-report "$I4_RUN/controlled-baseline.json" --fixtures tests/fixtures/grounded_cases.json --output "$I4_RUN/controlled-baseline-reviewed.json"
```

Ne pas remplacer le rapport initial par sa relecture. Documenter la version du
gradeur et la raison d'une nouvelle notation. Les citations et exigences de la
fixture priment sur le statut interne `covered` ou `partial`.

## 5. Provisionnement explicite des artefacts natifs

Les commandes suivantes ont un effet réseau explicite et vérifient les empreintes
du verrou. Le fonctionnement normal de l'application reste hors ligne. Les poids
d'extraction et d'embedding ne sont pas des générateurs supplémentaires.

```bash
for I4_GROUP in ollama qdrant e5 docling tessdata; do
  "$I4_PYTHON" -m services.runtime.artifacts --only "$I4_GROUP"
done
"$I4_PYTHON" - <<'PY'
import json
from services.runtime.artifacts import ROOT, download

lock = json.loads((ROOT / "config/enhanced-4b.lock.json").read_text())
download(lock["gguf"], ROOT / ".runtime/models/Qwen3-4B-Q4_K_M.gguf")
tokenizer = lock["tokenizer"]
for name, checksum in tokenizer["files"].items():
    entry = {"url": f"https://huggingface.co/{tokenizer['repository']}/resolve/{tokenizer['revision']}/{name}",
             "sha256": checksum}
    download(entry, ROOT / ".runtime/models/qwen3-4b-tokenizer" / name)
PY
```

`--offline` est disponible pour les groupes de `services.runtime.artifacts` quand
les fichiers sont déjà présents et conformes. Un artefact absent ou corrompu est
un prérequis non satisfait, pas une autorisation de changer son verrou.

Le pilote natif démarre ses propres services, vérifie les versions, importe le
GGUF par `provision_enhanced_4b.py` et contrôle son identité. Il ne fait pas de
`pull` d'un autre générateur. Les ports loopback **11439, 6339 et 6340** doivent
être libres ; `--ollama-port` et `--qdrant-port` permettent des ports dédiés.
Conserver le reçu `service-stop.json` après chaque bloc.

## 6. OCR corrigé : construction neuve et intégrations réelles

La recette [provision_production_ocr.py](../../tools/qualification/provision_production_ocr.py)
est propre à **Debian 13 x86-64**. Elle requiert un compilateur C/C++, `make`,
`dpkg-deb`, `ldd`, `readelf`, au moins 2 Gio libres et les bibliothèques système
`libpng16.so.16`, `libjpeg.so.62`, `libtiff.so.6`. Elle télécharge explicitement
CMake 3.31.12 et les en-têtes Debian vérifiés dans son workspace utilisateur ;
elle ne lance pas d'installation système ni de commande avec élévation.

```bash
"$I4_PYTHON" tools/qualification/provision_production_ocr.py --output "$I4_RUN/ocr-fresh-build" --download-official
```

Cette commande exige l'absence d'une installation OCR canonique existante. Elle
ne l'écrase pas. La version finale du script applique le correctif source
[normmatch](../../config/source-fixes/tesseract-5.4.0-normmatch.json) verrouillé
avant compilation : elle construit donc directement le candidat corrigé, pas le
binaire historique non corrigé. Le manifeste distingue les deux états, conserve
les empreintes avant/après et refuse de réutiliser un ancien reçu sans le correctif
requis. Les archives originales restent inchangées.

Pour les sept intégrations OCR et le contrôle de police associé :

```bash
"$I4_PYTHON" -m pytest tests/integration/test_ingestion_ocr.py -q --basetemp="$I4_TMP_ROOT/ocr-candidate" --junitxml="$I4_RUN/ocr-candidate.xml"
```

Ce module est marqué `integration` **et** `slow` ; ne pas le masquer avec
`-m 'not slow'` pour annoncer une couverture OCR. Il utilise les réglages PDF de
`config/local16.yaml`, sans charger son générateur. Sous Linux, les fixtures
requièrent **Liberation Sans Regular**, recherchée dans les répertoires usuels et
utilisateur. Les propriétés JUnit consignent chemin, SHA et révision de la police.
Ne pas substituer une autre famille pour faire passer une cellule. Les poids
Docling, tessdata et le binaire Tesseract doivent être provisionnés ; leurs
absences produisent un échec ou un test ignoré, jamais une preuve OCR.

Une comparaison avec la référence demande que son worktree résolve effectivement
le **binaire non corrigé et les mêmes modèles/police**. Exécuter le module depuis
ce worktree avec l'interpréteur verrouillé seulement après avoir matérialisé ce
runtime et enregistré ses empreintes. Relier les deux XML au profil PDF effectif,
aux versions et à la police, pas uniquement au numéro « Tesseract 5.4.0 ».

## 7. Ablation OCR historique et reprise explicite

L'ablation isole le correctif amont `dac6b18a4764d13d670e7f304bbdb80f756b8431` :
seul `normmatch.cpp.o` doit être recompilé, avec mêmes sources hors correctif,
compilateur, options, Leptonica, bibliothèques, raster et modèle OSD. Elle ne
désactive pas les exceptions flottantes ni ne force une orientation.

Les empreintes observées sont :

| Élément | SHA-256 |
|---|---|
| Binaire non corrigé | `d6433dab06f0c58ff3536560b208e92c156664f7fe48210f00f7a17f75e0c3ac` |
| Binaire corrigé de la session | `61461b50cb385288c9c1a0382c5836202bdb7ded69b899b04f83122399959c97` |
| Pixels du raster discriminant | `a5b899ec216980cc14d3e074e405524b5bdcdede1540e2012c30fecf24b70f53` |

Ces hashes identifient les artefacts mesurés ; une construction sur un autre hôte
n'est pas annoncée identique octet pour octet. Pour rejouer l'ablation, fournir
`I4_UNPATCHED_BUILD`, le workspace conservé contenant `build/` et son
`build-receipt.json`, ainsi que `I4_OSD_BASELINE_RECEIPT`, le reçu original de la
sonde par défaut terminée en SIGFPE. Le raster, le modèle et l'installation
canonique non corrigée auxquels ce reçu renvoie doivent encore être disponibles.
Ces prérequis **ne peuvent pas être recréés par la seule construction corrigée
ci-dessus** et ne sont pas livrés dans Git.

```bash
"$I4_PYTHON" tools/qualification/provision_production_ocr.py --ablate-existing-build "$I4_UNPATCHED_BUILD" --probe-receipt "$I4_OSD_BASELINE_RECEIPT" --output "$I4_RUN/ocr-ablation-plan" --plan-only
"$I4_PYTHON" tools/qualification/provision_production_ocr.py --ablate-existing-build "$I4_UNPATCHED_BUILD" --probe-receipt "$I4_OSD_BASELINE_RECEIPT" --output "$I4_RUN/ocr-ablation"
```

Le plan valide les fichiers et versions sans compiler ni lancer d'OCR. L'exécution
publie le binaire canonique seulement après la sonde réussie ; un échec de
publication restaure l'installation précédente. La sonde accepte un code zéro et
un angle explicite parmi les quarts de tour reconnus ; cela ne démontre ni
l'exactitude de l'orientation ni la qualité des caractères reconnus.

La session a conservé un premier échec de harnais après compilation et installation
réussies : les listings générés `compiler_depend.make` avaient changé. La reprise
est explicitement limitée à ce reçu et vérifie le candidat déjà construit, sans
recompiler ni changer les sources. Si ce cas exact survient et que les preuves
conservées satisfont les gardes du script :

```bash
"$I4_PYTHON" tools/qualification/provision_production_ocr.py --ablate-existing-build "$I4_UNPATCHED_BUILD" --probe-receipt "$I4_OSD_BASELINE_RECEIPT" --resume-built-ablation "$I4_RUN/ocr-ablation/ablation-receipt.json" --output "$I4_RUN/ocr-ablation-resume-plan" --plan-only
"$I4_PYTHON" tools/qualification/provision_production_ocr.py --ablate-existing-build "$I4_UNPATCHED_BUILD" --probe-receipt "$I4_OSD_BASELINE_RECEIPT" --resume-built-ablation "$I4_RUN/ocr-ablation/ablation-receipt.json" --output "$I4_RUN/ocr-ablation-resume"
```

Ne pas provoquer cet échec pour exercer une reprise, fabriquer son reçu, réutiliser
un résultat après publication, ou étendre cette option à un échec OCR. Les reçus
historiques `ocr-ablation-pr4259` et `ocr-ablation-pr4259-resume` restent deux
tentatives distinctes.

## 8. Préparer les originaux Office8/PDF2

Le préparateur I3 versionné reconstruit les fichiers Office et vérifie les deux
originaux TI avant de produire `inputs.json` :

```bash
"$I4_PYTHON" tools/qualification/prepare_grounded_native.py --output "$I4_RUN/native-inputs" --download-official
```

Sans téléchargement, fournir un dossier contenant exactement `ina226.pdf` et
`tmp117.pdf` aux hashes attendus :

```bash
"$I4_PYTHON" tools/qualification/prepare_grounded_native.py --output "$I4_RUN/native-inputs" --pdf-directory "$I4_OFFICIAL_PDF_DIRECTORY"
```

Choisir une seule de ces préparations et employer son manifeste ensuite. Les URL
et SHA sont dans [prepare_grounded_native.py](../../tools/qualification/prepare_grounded_native.py).
Les documents Office proviennent de la matrice versionnée et leurs octets ZIP et
propriétés temporelles sont stabilisés. Les extractions de première page produites
par ce préparateur sont les entrées historiques I3 ; **le bloc PDF I4 les remplace
par le worker complet de chaque révision**.

## 9. Office8 : mesures natives appariées

```bash
I4_OFFICE_CASES=(
  --case-id P01_general_condition
  --case-id P05_sparse_table
  --case-id P10_decimal_sum
  --case-id P11_conversion
  --case-id L01_condition_mismatch
  --case-id L06_cross_document_conflict
  --case-id L13_negated_value
  --case-id L16_table_note
)
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_BASELINE" --label baseline --inputs "$I4_RUN/native-inputs/inputs.json" --output "$I4_RUN/native-baseline-office" "${I4_OFFICE_CASES[@]}"
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_ROOT" --label candidate --inputs "$I4_RUN/native-inputs/inputs.json" --output "$I4_RUN/native-candidate-office" "${I4_OFFICE_CASES[@]}"
```

Les moteurs E5, Qdrant et Ollama sont réels ; une route déterministe peut répondre
sans appel au générateur. Rapporter la route, `model_call_attempted`, `model_called`
et les échanges observés dans la trace (`llm.request`, `llm.response` et terminal).
Un indicateur `model_called=false` ne suffit pas à exclure un appel interrompu :
le transfert candidat H06 a exposé ce défaut de télémétrie après un timeout réel.
Une latence sans appel au 4B n'est pas une mesure de sa vitesse. Les erreurs d'admission,
de trace ou de génération restent au dénominateur. Une reprise éventuelle demande
un protocole annoncé avant ses sorties et un nouveau dossier ; elle ne remplace
pas la mesure primaire.

La référence Office de cette session a chevauché un contrôle Mypy, consigné dans
`structure-mypy-overlap-receipt.json` ; son effet sur les ressources n'a pas été
isolé. De plus, P01 passe d'une voie modèle à une voie déterministe. Les durées
appariées doivent donc rester ventilées par route ; elles ne démontrent pas un
gain d'inférence ni un effet causal unique. Pour une nouvelle comparaison de
latence, exécuter les deux bras sans charge concurrente et conserver leur propre
inventaire de ressources.

## 10. PDF2 : extraction complète de chaque bras, questions page zéro

Le préparateur I4 conserve les originaux complets INA226/TMP117 et les mêmes
questions/oracles I3. Le périmètre de réponse reste la page physique d'index zéro.
Il exécute un worker réel par document ; les 41 et 50 pages des originaux figés
ne sont pas remplacées par une fixture de texte.

Pour reproduire **l'avant historique**, `I4_BASELINE_RUNTIME` doit désigner un
runtime matérialisé contenant le binaire OCR non corrigé, les modèles vérifiés et
`config/artifacts.lock.json` cohérent. Ce n'est pas un simple chemin vers un
exécutable. Son Tesseract doit avoir le SHA-256
`d6433dab06f0c58ff3536560b208e92c156664f7fe48210f00f7a17f75e0c3ac`.
Dans la session, `../agentPDFDoc-i4-baseline/.runtime/bin/tesseract-5.4.0` pointe
vers l'installation conservée `ocr-unpatched-5.4.0`. Ce lien et sa cible ne sont
pas fournis par Git. `I4_BASELINE_RUNTIME` peut désigner le worktree seulement
après matérialisation et vérification de cette arborescence complète. Le candidat
emploie le runtime corrigé du clone ; les modèles Docling, E5 et 4B restent communs.

```bash
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind development-pdf --inputs "$I4_RUN/native-inputs/inputs.json" --application-root "$I4_BASELINE" --runtime-root "$I4_BASELINE_RUNTIME" --output "$I4_RUN/pdf-baseline-plan"
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind development-pdf --inputs "$I4_RUN/native-inputs/inputs.json" --application-root "$I4_BASELINE" --runtime-root "$I4_BASELINE_RUNTIME" --output "$I4_RUN/pdf-baseline-preparation" --execute
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind development-pdf --inputs "$I4_RUN/native-inputs/inputs.json" --application-root "$I4_ROOT" --runtime-root "$I4_ROOT" --output "$I4_RUN/pdf-candidate-plan"
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind development-pdf --inputs "$I4_RUN/native-inputs/inputs.json" --application-root "$I4_ROOT" --runtime-root "$I4_ROOT" --output "$I4_RUN/pdf-candidate-preparation" --execute
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_BASELINE" --label baseline --inputs "$I4_RUN/pdf-baseline-preparation/inputs.json" --output "$I4_RUN/native-baseline-pdf" --case-id N_ina226 --case-id N_tmp117
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_ROOT" --label candidate --inputs "$I4_RUN/pdf-candidate-preparation/inputs.json" --output "$I4_RUN/native-candidate-pdf" --case-id N_ina226 --case-id N_tmp117
```

Sans `--execute`, le préparateur écrit seulement `extraction-plan.json` ; aucun
`inputs.json` issu d'extractions exécutées n'est promis. Les workers sont bornés
par `--worker-timeout` (1 800 s par défaut), avec reçu d'arrêt, couverture et
extraction conservés. Un statut partiel reste partiel. Ne pas attribuer une donnée
à une page absente de la source ou modifier l'oracle en fonction de l'extraction.

Cette comparaison historique combine **code applicatif et correction OCR**. Elle
mesure un résultat global ; elle n'isole pas à elle seule l'effet du classement
RAG ou du contrat qualitatif. L'isolation repose sur les tests discriminants à
entrées constantes, le rejeu des blocs canoniques et l'ablation OSD sur le raster
exact. Les manifestes historiques des bras sont `pdf-baseline-preparation/inputs.json`
et `pdf-candidate-preparation/inputs.json`, à relier à leur reçu de code final.

## 11. Parcours HTTP/SSE réel

Le corpus synthétique HTTP peut être matérialisé sans source privée :

```bash
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind http --output "$I4_RUN/http-inputs"
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_ROOT" --label candidate --inputs "$I4_RUN/http-inputs/inputs.json" --output "$I4_RUN/native-candidate-http" --transport http
```

Le pilote lance les services dédiés, puis
[production_i4_http.py](../../tools/qualification/production_i4_http.py) démarre
l'API loopback avec une session réelle. Il importe les DOCX par workers natifs,
interroge le flux public, vérifie que les événements de support et la validation
précèdent tout delta publié, constate l'identité 4B et l'appel effectif, puis
remplace un document et contrôle la conservation des citations effectivement
publiées vers son ancienne version. Les secrets de session ne doivent pas être
copiés dans un rapport public.

La preuve opérationnelle finale est **`http-final-result.json`**, écrite après
arrêt vérifié des groupes possédés. Lire également `measurements/transport-result.json`,
`measurement-process.json` et `service-stop.json`. Une API démarrée, une requête
terminée ou un test unitaire du harnais ne prouve pas ce parcours. La qualité
documentaire de la réponse exige sa relecture séparée ; aucun navigateur n'est
qualifié par cet essai HTTP.

## 12. Transfert et scans réservés : après gel seulement

La séparation du transfert est une discipline expérimentale. Avant le gel du
produit, le responsable de validation conserve les huit questions/oracles ; les
développeurs ne les consultent pas. La lecture du code du préparateur ou de ses
options n'expose pas ces fichiers. **En revanche, même une préparation sans
`--execute` lit les oracles et les écrit dans son plan** : l'exécuter seulement
après gel, ou dans le travail indépendant du responsable de validation.

Le préparateur attend un dossier `I4_HELDOUT` contenant les octets gelés de
`freeze-receipt.json`, `sources.json`, `questions-oracles.json`,
`scan-transformations.json`, ainsi que les originaux et scans désignés. Il vérifie
le hash du reçu fixé dans son code, les manifestes et chaque fichier.

Le [matérialiseur](../../tools/qualification/materialize_production_i4.py) construit
ce dossier depuis les quatre manifestes versionnés dans
`RAG_Local_Agents/reports/production-i4-corpus`, publiés après le gel du
produit : [reçu de gel](production-i4-corpus/freeze-receipt.json),
[sources](production-i4-corpus/sources.json),
[questions et oracles](production-i4-corpus/questions-oracles.json) et
[transformations des scans](production-i4-corpus/scan-transformations.json).
Ne pas supposer qu'un dossier historique `.runtime` existe dans un clone. Les quatre fichiers
doivent garder leurs octets exacts, y compris les questions copiées sans affichage.
Un déplacement ne doit pas conduire à réécrire un manifeste déjà hashé.

```bash
I4_MANIFESTS="$I4_ROOT/RAG_Local_Agents/reports/production-i4-corpus"
```

Choisir **une seule** des trois commandes suivantes. Toutes exigent un nouveau
dossier de sortie sous `.runtime/qa`, avec permissions 0700 et fichiers vérifiés
en 0600 ; aucune écriture sur un dossier existant ni reprise implicite n'est admise.
Pour autoriser les seuls téléchargements officiels désignés dans les manifestes :

```bash
I4_HELDOUT="$I4_RUN/transfer-inputs"
"$I4_PYTHON" tools/qualification/materialize_production_i4.py --manifests "$I4_MANIFESTS" --output "$I4_HELDOUT" --download-official
```

Alternative hors ligne : `I4_ORIGINALS` désigne une racine contenant le
sous-dossier `originals/` et les trois PDF exacts. Les options `--originals` et
`--download-official` sont mutuellement exclusives :

```bash
I4_HELDOUT="$I4_RUN/transfer-inputs"
"$I4_PYTHON" tools/qualification/materialize_production_i4.py --manifests "$I4_MANIFESTS" --output "$I4_HELDOUT" --originals "$I4_ORIGINALS"
```

Si `originals/` est déjà présent sous le dossier des manifestes, aucune option de
source supplémentaire n'est nécessaire ; cette forme ne réalise aucun accès réseau :

```bash
I4_HELDOUT="$I4_RUN/transfer-inputs"
"$I4_PYTHON" tools/qualification/materialize_production_i4.py --manifests "$I4_MANIFESTS" --output "$I4_HELDOUT"
```

La voie réseau accepte exactement les trois URL HTTPS `www.analog.com` gelées,
sans redirection ni proxy. Chaque PDF doit respecter sa taille attendue et le
plafond de 16 Mio. Le délai d'E/S est de 15 s ; une échéance totale de 120 s est
contrôlée entre les blocs reçus. Si l'éditeur fournit d'autres octets, l'outil
refuse le fichier : obtenir une archive au SHA gelé, sans changer l'oracle.

La reconstruction impose **pypdfium2 5.13.0, Pillow 12.3.0 et reportlab 5.0.1**.
Le renderer partagé utilise 200 dpi (`scale=200/72`), niveaux de gris, rotation
zéro, `Canvas(invariant=1)` et aucune couche de texte. Les deux PDF et deux PNG
doivent retrouver exactement leurs SHA gelés. Le statut `materialized_verified`
n'est écrit dans `materialization-receipt.json` qu'après vérification des quatre
manifestes, des trois originaux, des deux paires reconstruites et de
`frozen_inputs()`. Un échec garde son reçu et ses sorties distincts.

Cette matérialisation n'exécute ni OCR, ni RAG, ni modèle génératif. Les tests avec
doubles et le préflight d'empreintes du matérialiseur ne prouvent pas une
matérialisation native réussie ; le bilan doit identifier son exécution réelle
séparément. Les résultats d'extraction et de réponse exigent les étapes suivantes.

Dans la session de qualification, la première tentative réseau a échoué lors de
la résolution DNS. Son reçu reste conservé sous `heldout-materialized/`, avec le
statut `failed`. Une seconde invocation, dans le nouveau dossier
`heldout-materialized-offline/`, a utilisé les trois originaux archivés aux SHA
gelés et obtenu `materialized_verified`. Il ne s'agit ni d'une réussite du
téléchargement ni d'une reprise dans le dossier ayant échoué. Le bilan relie les
deux reçus et leur revue d'intégrité. Pour reproduire la voie hors ligne depuis
un clone, fournir réellement ces trois fichiers dans `I4_ORIGINALS/originals/` ;
les dossiers historiques de la session ne sont pas des dépendances livrées.

Après matérialisation et gel du candidat, préparer **les deux bras**. La référence
`fa3eabc` utilise `I4_BASELINE_RUNTIME` et son Tesseract original non corrigé,
épinglé au SHA `d6433dab…` complet de la section 10. Le candidat seul utilise
`I4_ROOT` et le moteur corrigé `61461b50…` identifié dans la section 7. Les poids
Docling, E5 et 4B restent communs ; relever l'identité effective des binaires dans
les reçus. Ce choix est le même que pour la référence PDF2 déjà exécutée.

La comparaison de bout en bout mesure donc l'ensemble des changements applicatifs
et OCR. Elle ne permet pas d'attribuer à elle seule un gain au classement RAG,
au contrat de réponse ou au correctif du moteur. L'ablation distincte de
`normmatch`, avec un seul objet recompilé et le raster conservé, ainsi que les
tests discriminants à entrées constantes, servent à isoler ces mécanismes.

Les plans, sans exécution des workers, s'écrivent :

```bash
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind transfer --heldout "$I4_HELDOUT" --application-root "$I4_BASELINE" --runtime-root "$I4_BASELINE_RUNTIME" --output "$I4_RUN/transfer-baseline-plan"
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind transfer --heldout "$I4_HELDOUT" --application-root "$I4_ROOT" --runtime-root "$I4_ROOT" --output "$I4_RUN/transfer-candidate-plan"
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind ocr --heldout "$I4_HELDOUT" --application-root "$I4_BASELINE" --runtime-root "$I4_BASELINE_RUNTIME" --output "$I4_RUN/ocr-baseline-plan"
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind ocr --heldout "$I4_HELDOUT" --application-root "$I4_ROOT" --runtime-root "$I4_ROOT" --output "$I4_RUN/ocr-candidate-plan"
```

Pour vérifier séparément une reconstruction des scans gelés :

```bash
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind scan-reproduction --heldout "$I4_HELDOUT" --output "$I4_RUN/scans-reconstructed"
```

Cette commande rend les deux pages selon les transformations figées et
vérifie les octets PNG/PDF, l'absence de texte incorporé et l'intégrité de
l'original. Elle ne réalise pas d'OCR et exige les versions de rendu figées. Le
matérialiseur effectue déjà ce contrôle : ce rejeu séparé est optionnel et ne
constitue pas un essai OCR supplémentaire. Les plans ne prouvent aucun résultat
d'extraction ou de réponse.

Exécuter les workers et requêtes de chaque bras dans leurs dossiers propres :

```bash
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind transfer --heldout "$I4_HELDOUT" --application-root "$I4_BASELINE" --runtime-root "$I4_BASELINE_RUNTIME" --output "$I4_RUN/transfer-baseline-preparation" --execute
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_BASELINE" --label baseline --inputs "$I4_RUN/transfer-baseline-preparation/inputs.json" --output "$I4_RUN/native-baseline-transfer"
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind transfer --heldout "$I4_HELDOUT" --application-root "$I4_ROOT" --runtime-root "$I4_ROOT" --output "$I4_RUN/transfer-candidate-preparation" --execute
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_ROOT" --label candidate --inputs "$I4_RUN/transfer-candidate-preparation/inputs.json" --output "$I4_RUN/native-candidate-transfer"
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind ocr --heldout "$I4_HELDOUT" --application-root "$I4_BASELINE" --runtime-root "$I4_BASELINE_RUNTIME" --output "$I4_RUN/ocr-baseline-preparation" --execute
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_BASELINE" --label baseline --inputs "$I4_RUN/ocr-baseline-preparation/inputs.json" --output "$I4_RUN/native-baseline-ocr"
"$I4_PYTHON" tools/qualification/prepare_production_i4.py --kind ocr --heldout "$I4_HELDOUT" --application-root "$I4_ROOT" --runtime-root "$I4_ROOT" --output "$I4_RUN/ocr-candidate-preparation" --execute
"$I4_PYTHON" tools/qualification/run_grounded_native.py --application-root "$I4_ROOT" --label candidate --inputs "$I4_RUN/ocr-candidate-preparation/inputs.json" --output "$I4_RUN/native-candidate-ocr"
```

L'absence de `--case-id` exécute tous les cas de chaque manifeste : huit questions
sur les trois PDF originaux, puis deux questions sur les deux PDF image-only,
dans chacun des bras. Chaque bras extrait ses trois originaux une fois pour ses
huit questions ; il extrait séparément ses deux scans. Ne réutiliser aucune
extraction entre référence et candidat, ni entre un original et son scan. Seuls
les octets d'entrée et les poids immuables sont partagés.

Pour les scans, distinguer la requête terminée, le texte effectivement extrait,
les faits restitués et la conformité de l'abstention. `ready_partial`, un worker
terminé avec le code zéro ou une requête `done` ne prouvent pas que l'OCR a
reconnu du texte. Une abstention honnête devant une extraction vide reste un
échec de réponse sur un document dont l'oracle est positif. Sans citation,
l'exactitude sémantique des citations est non applicable, et non égale à 100 %.

Les citations du produit doivent désigner la **page 1 du PDF dérivé** `SCAN1.pdf`
ou `SCAN2.pdf`. Le numéro de page de l'original, notamment la page 3 reproduite
dans `SCAN2`, appartient à la provenance de revue ; il ne remplace pas le
localisateur du document effectivement interrogé. Vérifier les chiffres, signes,
colonnes, conditions et réserves sur les PNG gelés. Une copie exacte d'une
extraction ne certifie pas à elle seule la justesse de son tableau par rapport
à la page originale.

Conserver le premier résultat de chaque cas. Un échec découvert sur le transfert
qualifie l'état gelé comme insuffisant sur ce critère ; il n'autorise pas un réglage
sur ces réponses puis la présentation de la nouvelle tentative comme essai tenu
à l'écart. Les six positifs et deux limites restent dénombrés séparément. Ce
transfert électronique ne démontre pas une généralisation à d'autres domaines.

## 13. Pièces nécessaires au bilan et à la publication

Les blocs contrôlé30, Office8, PDF2, transfert8 et scans2 ont été exécutés sur
les deux bras dans cette session. Le parcours HTTP a été exécuté sur le seul
candidat. La matérialisation hors ligne, les intégrations OCR et l'ablation
`normmatch` possèdent également leurs reçus distincts. Ces exécutions comportent
des échecs et des limites ; leur statut par critère appartient au
[bilan des résultats](production-4b-results-2026-11-08.md), avec les revues
documentaires séparées des statuts techniques.

Le passage portable final sur le gel exact est identifié par
`portable-frozen-final.xml` et `portable-frozen-final.log` dans les preuves de la
session. Le bilan doit en donner le résultat effectif, sans réutiliser le total
d'un passage antérieur à la dernière correction du produit. Les chemins de ces
reçus historiques sont des localisateurs de preuves, pas des fichiers supposés
présents dans un clone neuf.

Pour chaque commande réellement exécutée, conserver l'heure UTC, le répertoire,
les arguments, le code retour, les sorties complètes et le reçu de sources.
Publier une synthèse expurgée, avec liens/empreintes des preuves disponibles,
sans secrets, corpus privé ou poids. Le bilan final doit renseigner :

- SHA du candidat final, SHA de référence, hash du harnais et état propre ou
  modifié du worktree ; distinguer une mesure d'un gel antérieur.
- Manifeste des entrées, hashes des originaux/extractions, versions des composants,
  profils effectifs, identité du binaire OCR et paramètres du 4B.
- Tests exécutés, ignorés, non exécutés et bloqués ; échecs initiaux et reprises
  séparés, sans substitution favorable.
- Qualité de recherche et des relations retenues, fidélité de chaque affirmation,
  citations réellement justificatives, abstentions correctes et sur-refus.
- Latence et mémoire par phase/route, appel au modèle, erreurs au dénominateur,
  arrêt des services et limites de comparabilité.
- Pour chaque critère D01–D10 : preuve et statut, sans déduire une qualification
  globale de diffusion de la seule réussite des unités ou d'une sonde native.

Les commandes de ce guide proviennent des interfaces actuelles des scripts. Le
bilan d'exécution et le manifeste de publication sont les autorités pour le
dernier SHA testé et les commandes effectivement réalisées dans cette session.
