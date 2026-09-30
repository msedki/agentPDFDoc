---
name: embedding-comparison-windows
description: Comparer uniquement E5-small INT8 et Granite 97M Multilingual R2 ONNX CPU sur les mêmes extractions et preuves de développement, dans des collections séparées, pour qualifier le choix d'embedding du RAG Windows.
---

# Comparatif ciblé d'embedding

Lire `RAG_Local_Agents/QUALIFICATION.md` section5, `DECISIONS.md` D03/D04 et le skill `rag-retrieval-evaluation`. Aucun benchmark massif, aucun ajustement au jeu final, aucun remplacement silencieux du modèle actif.

## Contrats vérifiés avant implémentation

- E5-small conserve son tokenizer officiel, préfixes `query: `/`passage: `, moyenne masquée par attention puis L2, graphe INT8 déjà verrouillé. Réutiliser l'implémentation et son identité complète.
- Granite `ibm-granite/granite-embedding-97m-multilingual-r2`, révision `835ad14087e140460703cf0fae09f97d469d65c2` : `1_Pooling/config.json` demande CLS (premier token), `modules.json` ajoute normalisation, `config_sentence_transformers.json` déclare les prompts query/document vides. Ne lui appliquer ni moyenne E5 ni préfixes E5.
- Dimension384, pad179935 et limite éditeur32768 proviennent de `config.json` et `sentence_bert_config.json`. Le comparatif emploie les mêmes textes de chunks existants ; vérifier leurs longueurs avec chacun des tokenizers et annoncer toute modification indispensable de fragmentation. Aucun padding/troncature implicite.
- Graphe CPU officiel `onnx/model_quint8_avx2.onnx`,98247878octets, SHA256 `a6022dd8220ea6f6595562a1328ee216f4a94faa55362f2f4747c80f1e78772e`. Tokenizer25301672octets, SHA256 `4f2842d568e2724370aec203652a42ac783c7937f8347a1a2cc7506d71f1582f`. Inspecter réellement entrées/sorties du graphe avant smoke ; ne présumer ni forme ni provider à partir du nom.

## Exécution contenue

1. Verrou séparé de qualification : URLs au commit officiel, tailles et SHA LFS ou SHA blobGit pour les petits fichiers. Downloads explicites, aucune résolution réseau lors d'inférence. Licence Apache2 déclarée dans la fiche ; conserver aussi un avis officiel de licence avec source/hash, sans affirmer qu'un fichier LICENSE absent existe.
2. Charger un seul graphe ONNX à la fois, CPUExecutionProvider uniquement, threads bornés et spinning désactivé. Surveiller hôte/RSS/private/disque et conserver réserve1536Mio. Ne pas lancer cet essai pendant OCR/génération/build lourd.
3. Figer les extractions et annotations de développement, exporter leur identité réelle. Collections/cache distincts déterminés par modèle, commit, graph/tokenizer hashes, pooling, préfixes, normalisation et dimension. Ne jamais modifier la collection E5 active ou retraiter l'OCR pour le seul comparatif.
4. Reprendre scope, lexical, RRF, expansion et ContextBuilder réels ; seul embedding/collection change. Mesurer Recall@5/@10, MRR de preuve, EvidenceCoverage@Context, par langue/catégorie, durées et stockage. Les calculs sur simples listes de vecteurs restent un smoke et ne valent pas A/B de la chaîne.
5. Enregistrer décision selon qualité/coût et non fiche éditeur ; seuils DoD inchangés. Tout candidat effectivement incompatible garde preuve FAIL et motif, baseline préservée. Une source manquante ne donne pas droit d'inventer un résultat.

## Sources officielles ouvertes le30/09/2026

- [Fiche IBM au commit](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2/raw/835ad14087e140460703cf0fae09f97d469d65c2/README.md) : l'ouverture navigateur blob a échoué ; réponse HTTP raw mainteneur réellement reçue et conservée sous `.runtime/references/granite-97m-readme.md`.
- [Métadonnées HF versionnées](https://huggingface.co/api/models/ibm-granite/granite-embedding-97m-multilingual-r2/revision/835ad14087e140460703cf0fae09f97d469d65c2?blobs=true) : commit, tailles, hashes LFS/blobGit ; copie `.runtime/references/granite-97m-metadata.json`.
- [Pooling officiel](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2/raw/835ad14087e140460703cf0fae09f97d469d65c2/1_Pooling/config.json), config_sentence_transformers.json, modules.json, config.json et sentence_bert_config.json : réponses JSON réelles conservées dans `.runtime/references/granite-contract/contracts.json`.
- [ONNX Runtime sessions et providers](https://onnxruntime.ai/docs/api/python/api_summary.html), source officielle déjà examinée pour la baseline ; vérifier le contrat Python1.30 installé.

Les scores MTEB et débits H100 de la fiche sont des résultats éditeur, pas des mesures sur le i5 Windows. Le skill n'est validé comportementalement qu'après une tâche réelle appropriée ; front matter correct seul ne suffit pas.
