# Fixtures synthétiques V2.1

Ces outils produisent exclusivement des documents de qualification écrits pour ce
projet. Aucun fichier du corpus `PDF/` n'est lu ou modifié ; aucun service,
téléchargement ou job d'indexation n'est lancé par ces outils. Le collecteur
de bindings lit uniquement l'API loopback réelle déjà démarrée par le superviseur.
Seuls `answers.py` et `perf.py` soumettent des questions à cette API : chaque
question y déclenche la génération réelle du modèle local, dans un créneau choisi.

Exception : `corpus_eval.py` évalue la recherche sur le corpus réel publié dans
l'instance (protocole W013). Il lit par l'API le texte des blocs publiés pour en
tirer des questions, écrit ce jeu sous `.runtime/evals/` uniquement (refus
ailleurs), puis interroge `POST /api/v1/admin/evaluation/context`, qui n'appelle
pas le modèle. Son rapport ne contient que des identifiants et des agrégats ;
`reaggregate` recalcule les mesures d'un rapport depuis ses lignes. Aucun fichier
de `PDF/` n'est ouvert directement.

Les skills appliqués sont [rag-qualification-fixtures](../../.agents/skills/rag-qualification-fixtures/SKILL.md),
[rag-retrieval-evaluation](../../RAG_Local_Agents/skills/rag-retrieval-evaluation/SKILL.md) et
[local-cpu-qualification](../../RAG_Local_Agents/skills/local-cpu-qualification/SKILL.md).
Les exigences proviennent de la DoD et de `RAG_Local_Agents/QUALIFICATION.md` §3/6/7.
ReportLab 5.0.1 et PDFium viennent de la venv verrouillée par le superviseur.

Depuis `D:\enhacements\agentragpdf`, les commandes réalisées sont :

```powershell
.\.venv\Scripts\python.exe tools/qualification/generate.py
.\.venv\Scripts\python.exe tests/unit/test_qualification_fixtures.py
.\.venv\Scripts\python.exe tools/qualification/previews.py
.\.venv\Scripts\python.exe tools/qualification/check_reproducibility.py `
  --output evals/qualification-v2.1/reports/<nouveau-rapport>.json
```

La génération écrit d'abord dans un dossier temporaire, puis copie seulement les
fichiers synthétiques identifiés dans `fixtures/qualification-v2.1/` et les jeux de
`evals/qualification-v2.1/`. Elle ne supprime aucun fichier. Elle refuse, sans rien
modifier, un `final.json` existant qui ne correspond plus à `final.freeze.json`, ou
un final régénéré différent du gel (empreinte canonique documentée
`673e437138ae66a4baee730d3181012c6bf66e1d96e91c4af7a08e2a8ee546d4`). Seule l'option
explicite `--regenerate-final` remplace le final et son gel ; elle n'est pas prévue
après le début de la qualification. `check_reproducibility.py` régénère dans un
dossier temporaire, compare les octets des 32 PDF et des 5 jeux livrés et écrit un
nouveau rapport exclusif : il ne réécrit jamais les fixtures ni le final.

Les sorties d'outils sont des créations exclusives (`evidence_io.py`) : un fichier
existant n'est jamais remplacé et les noms `final.json`, `final.freeze.json`,
`questions.json`, `development.json` et `manifest.json` sont refusés partout.

`corpus_data.py` définit 7 documents pneumatiques côté développement et 7 documents
thermiques côté final. Dans chaque famille, le document 2 est un scan sans couche
texte, le document 3 contient un paragraphe natif et une table scannée, et le
document 4 comporte deux colonnes. Les valeurs sont contrôlées et différentes.
Les 200 questions respectent les six quotas ; les comparaisons requièrent une
preuve de chaque document et les relances conservent la question utilisateur
antérieure. Les fixtures de sécurité restent hors de ces questions.

Le PDF Unicode utilise des glyphes Type3 vectoriels écrits pour ce projet et un
CMap ToUnicode UTF-16BE. Il contient réellement un caractère hors BMP, un accent
combinant, une ligature et une césure visible. Cette méthode évite d'embarquer une
fonte Windows dont la redistribution n'a pas été vérifiée. Vera, embarquée dans
les autres PDF, conserve sa licence dans `fixtures/qualification-v2.1/licenses/`.

La résolution des annotations se fait après extraction réelle. Le collecteur
`capture_bindings.py` exige une génération complètement prête et publiée,
vérifie le SHA original contre la fixture gelée, puis conserve les réponses API
exactes, révisions et hashes UTF-8. Il refuse les redirections, les origines non
loopback et l'écrasement d'une preuve existante. L'utiliser seulement après
confirmation du superviseur que cette API est la cible isolée autorisée.

Port de l'instance cible : `app.port` du profil (`config/local16.yaml`, 8785 par
défaut des outils). L'API refuse un en-tête `Host` d'un autre port : passer
`--base-url` avec le port réel de l'instance visée, par exemple
`http://127.0.0.1:8795` pour l'instance restaurée du 30/09/2026.

```powershell
.\.venv\Scripts\python.exe tools/qualification/capture_bindings.py `
  --base-url http://127.0.0.1:8785 `
  --document-id <ID-reel> --document-key development-DA-P01 `
  --output evals/qualification-v2.1/runtime/<date>-DA-P01-published.json
```

Preuves réelles existantes : `runtime/2026-09-30-DA-P01-published.json` (snapshot
publié de DA-P01) et `runtime/2026-09-30-development-partial.json` (résolution
DEV : 15 questions résolues, 85 non résolues). Pour plusieurs documents, fusionner
les snapshots par document après contrôle du SHA-256 de chaque fichier ; doublons,
IDs réels partagés entre clés, SHA original différent du manifeste et texte de
bloc altéré sont refusés :

```powershell
.\.venv\Scripts\python.exe tools/qualification/merge_bindings.py `
  --input evals/qualification-v2.1/runtime/2026-09-30-DA-P01-published.json <sha256> `
  --input evals/qualification-v2.1/runtime/<date>-DA-P02-published.json <sha256> `
  --output evals/qualification-v2.1/runtime/<date>-development-bindings.json
```

Il ne mesure pas le retrieval. Fournir un fichier
JSON `bindings` de cette forme, avec les valeurs exactes provenant de l'API :

```json
{
  "documents": {
    "development-DA-P01": {
      "document_id": "<ID API réel>",
      "version_id": "<ID API réel>",
      "extraction_revision_id": "<révision réelle>",
      "generation_id": "<génération réelle si disponible>",
      "file_sha256": "<SHA original vérifié>",
      "pages": [
        {
          "page": {"page_index": 0},
          "blocks": [
            {
              "id": "<bloc réel>",
              "version_id": "<ID API réel>",
              "extraction_revision_id": "<révision réelle>",
              "generation_id": "<génération réelle si disponible>",
              "raw_text": "<texte exact fourni par l'extraction>",
              "source_text_hash": "<SHA UTF-8 réel du texte exact>",
              "precision": "block",
              "bbox": null,
              "metadata": {}
            }
          ]
        }
      ]
    }
  }
}
```

Le tableau ci-dessus est un **template documentaire**, pas une source à importer :
remplacer toute la réponse page/blocs par la réponse API réelle, y compris sa
géométrie. Si la bbox n'est pas disponible, utiliser `null`.

```powershell
.\.venv\Scripts\python.exe tools/qualification/resolve.py `
  --dataset evals/qualification-v2.1/development.json `
  --bindings evals/qualification-v2.1/runtime/<date>-development-bindings.json `
  --output evals/qualification-v2.1/runtime/<date>-development-resolved.json
```

La sortie est limitée à `evals/qualification-v2.1/runtime/` ou `resolved/`, en
création exclusive.

Le resolver vérifie empreinte de l'original, version/révision et SHA du texte.
Il n'assouplit que les espaces et conserve les offsets en points de code Unicode.
Une preuve ambiguë, corrigée par conjecture ou absente reste `UNRESOLVED`.
Une table exige une ligne textuelle réunissant référence/valeur/unité ou des
cellules structurées de la même ligne réelle. Le seul bon nom de document ne
valide aucune unité. Une résolution ne calcule pas Recall, exactitude ou qualité
des réponses ; le statut reste explicitement « non qualifié RAG ».

## Génération, grille D05 et performance D07

Ces runners parlent à l'API loopback réelle déjà démarrée (en-têtes `Host`/`Origin`
exacts, sans proxy ni redirection) ; ils ne démarrent aucun service. Leurs tests
unitaires utilisent des doubles `httpx.MockTransport` explicites, qui ne valent pas
intégration réelle. Exécuter une génération ou une mesure seulement dans un créneau
où aucun autre moteur lourd ne tourne.

`answers.py` pose chaque question d'un split résolu par `POST /api/v1/queries`
(question, scope résolu, mode ; une relance reprend `conversation_id` et
`followup_of` de la question utilisateur antérieure), lit le SSE jusqu'à
l'événement terminal et conserve SSE brut, texte, IDs cités, sources, métriques
(`model_called`, tokens, durées API et client). Une seule soumission par question,
en séquence. Le journal JSONL est créé exclusivement ; `--resume` saute les
questions terminées et relit le SSE d'une question déjà créée sans nouveau POST,
après contrôle du même jeu, du même gel et de la même identité API. Le split final
exige `--final-freeze evals/qualification-v2.1/final.freeze.json` valide, toutes ses
annotations résolues et aucune limite.

```powershell
.\.venv\Scripts\python.exe tools/qualification/answers.py --split development `
  --dataset evals/qualification-v2.1/runtime/<date>-development-resolved.json `
  --source-dataset evals/qualification-v2.1/development.json `
  --base-url http://127.0.0.1:8785 `
  --output evals/qualification-v2.1/runtime/<date>-development-answers.jsonl
```

`grade.py grid` produit la grille manuelle (pré-contrôle numérique valeur/unité et
identifiants, citations avec version/page, champs `manual` à remplir : verdict,
assertions et soutien par citation, relecteur). `grade.py metrics` refuse une grille
dont une donnée automatique a changé, puis calcule exactitude, abstention, faux
refus, soutien des assertions (bootstrap par question, graine 20260930), intégrité
des IDs et version/page des citations, avec dénominateurs, par catégorie et par
langue ; les seuils viennent de `evaluation_targets` du profil. Le pré-contrôle
n'est pas un verdict et aucun modèle ne juge les réponses.

```powershell
.\.venv\Scripts\python.exe tools/qualification/grade.py grid --dataset <jeu-résolu> `
  --answers <journal.jsonl> --output evals/qualification-v2.1/runtime/<date>-development-grid.json
.\.venv\Scripts\python.exe tools/qualification/grade.py metrics --dataset <jeu-résolu> `
  --answers <journal.jsonl> --grid <grille-remplie.json> `
  --output evals/qualification-v2.1/runtime/<date>-development-d05.json
.\.venv\Scripts\python.exe tools/qualification/perf.py --dataset <jeu-résolu> --searches 30 --queries 30 `
  --base-url http://127.0.0.1:8785 --output evals/qualification-v2.1/runtime/<date>-perf.json
```

`perf.py` enchaîne N recherches `POST /api/v1/search` puis M questions distinctes
(`--searches`, `--queries`), sans relance ni split final. Il rapporte p50/p95
(interpolation linéaire), TTFT API et client, durée totale, `prompt_eval_count`,
`eval_count`, débits mesurés et la classe froid/chaud selon `load_duration`
rapporté par l'API et le seuil déclaré `--cold-load-ms`. Une réponse n'atteignant
pas 400 tokens reste `NOT_OBSERVED` pour ce scénario ; le rapport est
`MEASURED_NOT_QUALIFIED` et ne vérifie pas la taille du corpus exigée par D07.

## Essais réels sur instances isolées

Ces outils démarrent leurs propres instances dans une racine et des ports temporaires
(`%TEMP%\ape…`, `apst…`, `apr…`), avec le verrou lourd du poste partagé, et suppriment
leurs racines en fin d'essai ; la bibliothèque de l'utilisateur n'est jamais la cible.
Une génération réelle demande la mémoire d'une instance complète : sur un poste de
16 Gio, l'instance principale est arrêtée pendant l'essai, puis redémarrée.

| Outil | Ce qu'il établit | Critères |
|---|---|---|
| `e2e_instance.py start` / `stop` | Instance isolée pour Playwright ou pour les outils ci-dessous ; `--max-file-mib` règle la limite de taille | — |
| `library_check.py <cas>` | Import d'un dossier Unicode avec homonymes, originaux intacts, réimport et déplacement sans calcul, seconde version invisible avant publication, retrait nettoyé, fichiers en erreur et trop volumineux | D02.1, D02.2, D02.8, D03.1 à D03.4 |
| `fault_check.py <cas>` | Arrêts forcés pendant l'extraction, les embeddings ou l'écriture des points (`--pages` produit un document long), panne de Qdrant pendant un import | D03.5, D03.6 |
| `scope_check.py` | Filtres de périmètre (dossier récursif, documents, pages, section) appliqués avant la coupe top-k avec Qdrant et E5 réels ; sélection courte sans requête dense, mesurée par le compteur `rest_responses_total` de Qdrant | D04.2, D04.8 |
| `extraction_check.py` | Extraction confrontée à la vérité terrain des fixtures : couverture par page, OCR compté, page mixte sans double texte, schéma sans texte inventé, frontière pages 4/5, extraction partielle signalée, tableaux et deux colonnes. Écrit le 01/10, pas encore exécuté jusqu'au bout (premier essai interrompu faute de mémoire sur le poste) | D02.3 à D02.10 |
| `migration_check.py` | Sauvegarde d'un schéma antérieur restaurée et migrée, anciennes citations, réindexation, `--question` pour une question réelle | D09.4 |
| `restore_question_check.py prepare` / `restore` | Question et ancienne citation après restauration d'une sauvegarde au format courant | D09.3 |
| `injection_check.py` | Instruction hostile placée dans un PDF sans effet sur la réponse | D08.5 (en partie) |
| `log_privacy_check.py` | Lecture seule : texte extrait, questions et réponses de l'instance cherchés dans tous ses journaux (témoin positif sur les checkpoints), exclusions Git des originaux, du corpus et des modèles | D08.7 |
| `http_guards_check.py` | Lecture seule sur une instance en marche (par défaut l'instance principale) : Host et Origin étrangers, requêtes inter-sites, préflight CORS, Qdrant sans clé, traversées encodées vers le profil, la base et les jetons, sockets en écoute limités au bouclage | D08.3, D08.4 |

Rapports du 01/10 : `RAG_Local_Agents/reports/library-2026-10-01*.json`,
`faults-2026-10-01.json`, `scope-2026-10-01.json`, `http-guards-live-20261001T0943.json`, `http-guards-live-20261001T1030.json`, `log-privacy-20261001T0949.json`, `migration-2026-10-01-0414.json`,
`restore-question-2026-10-01-0525.json`, `injection-2026-10-01-0441.json`.

## Fixtures séparées D08.5/D08.6 et D06.8

`extra_fixtures.py` crée, hors manifeste et hors jeux de questions,
`fixtures/qualification-v2.1/hostile/markup-injection.pdf` (balisage HTML/Markdown
actif, image distante, lien `javascript:` et instruction d'élargissement du
périmètre en texte natif) et `fixtures/qualification-v2.1/layouts/long-document-14p.pdf`
(14 pages natives numérotées), chacun avec un sidecar `.sidecar.json` (SHA-256,
pages, marquage `SYNTHETIQUE`). La génération est déterministe ; un fichier existant
identique est conservé, un fichier différent est refusé. `--check` compare une
régénération en dossier temporaire aux fichiers livrés.

```powershell
.\.venv\Scripts\python.exe tools/qualification/extra_fixtures.py
.\.venv\Scripts\python.exe tools/qualification/extra_fixtures.py --check
```

Sources éditeur consultées le 30/09/2026 UTC :

- [ReportLab, graphiques](https://docs.reportlab.com/reportlab/userguide/ch2_graphics/)
  et [fonctions PDF](https://docs.reportlab.com/reportlab/userguide/ch4_pdffeatures/).
  Plusieurs ouvertures web ont échoué ; les signatures et implémentations du
  paquet 5.0.1 installé ont été lues pour `Canvas`, `setCropBox`, `setPageRotation`,
  `addPageLabel`, `PDFPageLabel`, `StandardEncryption` et les fontes.
- [PDF 32000-1:2008 publié par Adobe](https://opensource.adobe.com/dc-acrobat-sdk-docs/standards/pdfstandards/pdf/PDF32000_2008.pdf),
  §9.6.5 / §9.10.3, référence Type3/ToUnicode. La recherche officielle a retrouvé
  cette référence mais l'ouverture complète a échoué (404/restricted) : elle
  n'est pas présentée comme page intégralement relue. Les octets du CMap et son
  extraction sont contrôlés par les tests locaux indépendants du générateur.

Les fichiers [résultats et limites](../../evals/qualification-v2.1/README.md)
décrivent les contrôles exécutés et les écarts observés.
