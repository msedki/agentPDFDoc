# Fixtures synthétiques V2.1

Ces outils produisent exclusivement des documents de qualification écrits pour ce
projet. Aucun fichier du corpus `PDF/` n'est lu ou modifié ; aucun modèle,
OCR, téléchargement ou job d'indexation n'est lancé par ces outils. Le collecteur
de bindings lit uniquement l'API loopback réelle déjà démarrée par le superviseur.

Le skill appliqué est [rag-qualification-fixtures](../../.agents/skills/rag-qualification-fixtures/SKILL.md).
Les exigences proviennent de la DoD et de `RAG_Local_Agents/QUALIFICATION.md` §3/6/7.
ReportLab 5.0.1 et PDFium viennent de la venv verrouillée par le superviseur.

Depuis `D:\enhacements\agentragpdf`, les commandes réalisées sont :

```powershell
.\.venv\Scripts\python.exe tools/qualification/generate.py
.\.venv\Scripts\python.exe tests/unit/test_qualification_fixtures.py
.\.venv\Scripts\python.exe tools/qualification/previews.py
.\.venv\Scripts\python.exe tools/qualification/check_reproducibility.py
```

La génération remplace seulement les fichiers synthétiques identifiés dans
`fixtures/qualification-v2.1/` et les templates dans `evals/qualification-v2.1/`.
Elle ne supprime aucun fichier. La dernière commande régénère ces fichiers pour
comparer leurs octets : ne pas l'utiliser pour modifier les réponses attendues
après qualification, ni comme substitut à un gel de version.

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
confirmation du superviseur que cette API est la cible isolée autorisée :

```powershell
.\.venv\Scripts\python.exe tools/qualification/capture_bindings.py `
  --document-id <ID-reel> --document-key development-DA-P01 `
  --output evals/qualification-v2.1/runtime/<nouveau-binding>.json
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
  --bindings evals/qualification-v2.1/runtime-bindings.json `
  --output evals/qualification-v2.1/resolved/development.json
```

Le resolver vérifie empreinte de l'original, version/révision et SHA du texte.
Il n'assouplit que les espaces et conserve les offsets en points de code Unicode.
Une preuve ambiguë, corrigée par conjecture ou absente reste `UNRESOLVED`.
Une table exige une ligne textuelle réunissant référence/valeur/unité ou des
cellules structurées de la même ligne réelle. Le seul bon nom de document ne
valide aucune unité. Une résolution ne calcule pas Recall, exactitude ou qualité
des réponses ; le statut reste explicitement « non qualifié RAG ».

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
