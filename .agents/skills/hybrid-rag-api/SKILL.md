---
name: hybrid-rag-api
description: Implémenter et vérifier le backend local RAG PDF de ce dépôt, ses scopes, recherche hybride, indexation cohérente, streaming et citations versionnées.
---

# Backend RAG local

Appliquer les contrats actifs de `RAG_Local_Agents/IMPLEMENTATION.md`, la recette
`DEFINITION_OF_DONE.md` et la décision Windows native de `DECISIONS.md`. Les sources
suivantes décrivent des APIs ; elles ne certifient pas une performance sur ce poste.

- SQLite est autoritaire : génération staged, upsert Qdrant avec `wait=true`,
  vérification des comptes/empreintes, puis transaction de publication. Conserver
  la dernière génération complète lors d'une erreur et les versions citées.
- Résoudre le scope depuis SQLite avant les top-k lexical et dense. Couper les
  sources multi-pages aux blocs autorisés ; une sélection recharge les offsets
  backend. Aucun texte client arbitraire ne devient une preuve.
- FTS5 : échapper la syntaxe MATCH et paramétrer SQL ; `bm25()` croissant,
  identifiants exacts avant BM25, fusion RRF sur rangs. Ne pas confondre score et
  probabilité. Qdrant est le serveur Windows loopback, jamais le client embedded.
- E5-small : tokenizer local officiel, préfixes query/passage, entrée totale
  bornée, ONNX CPU INT8, moyenne masquée si nécessaire puis normalisation L2.
  Inspecter les entrées/sorties du graphe ; aucun téléchargement au runtime.
  Les hashes réellement calculés du graphe/tokenizer, la révision, les préfixes
  et le pooling identifient collection et cache. L'extraction possède son propre
  fingerprint ; changer les embeddings ne doit pas recommencer l'OCR.
- Révisions d'extraction immuables : hash UTF-8 du texte source exact, offsets
  en points de code Unicode et vérification de la révision/hash du bloc avant
  sélection. Préserver les métadonnées OCR et la géométrie effective du parser.
- Les identifiants obligatoires doivent figurer dans le contexte final après
  expansion et coupe de tokens. Rapporter distinctement absence dans le scope et
  preuve écartée par budget ; mesurer EvidenceCoverage@Context.
- Un suivi utilise un focus explicite, une référence nommée ou un référent
  utilisateur unique encore autorisé ; ambiguïté = needs_clarification sans LLM.
  Filtrer également l'historique côté backend : scope identique et générations
  toujours autorisées. Une ancienne réponse n'est jamais une preuve.
- Compter le contexte avec le tokenizer local correspondant au LLM/template,
  réserver sortie et marge, contrôler `prompt_eval_count` réel. Ollama reçoit
  `think=false`, `num_gpu=0`, un seul appel actif et des preuves délimitées.
- Persistences SSE : IDs monotones, reprise sans régénération, tampon borné,
  annulation du transport HTTP, redémarrage marqué interrupted. Sources avant
  deltas, citations inconnues refusées. Une limite de sortie reste visible.
- Host/Origin loopback, chemins relatifs sûrs, originaux immuables, Range contrôlé.
  Sessions, cookies, révocation et protections de l'API : suivre la règle « Référence
  de sécurité applicative » du `CLAUDE.md` racine (decodair, OWASP, sources officielles).
  Aucun worker PDF ni modèle PyTorch résident dans le processus API.
- La pause nominale est coopérative ; reprise manuelle depuis un checkpoint
  vérifié. Un watchdog distinct conserve motif et frontières durables. Avant une
  sauvegarde, suspendre les mutations, terminer requêtes/checkpoints et bloquer
  les nettoyages ; le contrôle utilise un nonce en en-tête, jamais dans l'URL.
  Le nettoyage attend aussi les écrivains d'indexation encore actifs.
- Une admission à chaud s'appuie sur `/api/ps` : modèle configuré, contexte
  attendu, quantification et résidence CPU vérifiés. Conserver la réserve hôte ;
  l'estimation du pic supplémentaire reste provisoire jusqu'à mesure réelle.
- L'évaluation protégée emprunte le même scope, retrieval, expansion et contexte
  que les requêtes, sans génération. Garder top10 et preuves du contexte final,
  les annotations sources indépendantes et le gel du lot final. Wilson concerne
  les questions binaires ; grouper les unités corrélées pour le bootstrap.

## Sources primaires à consulter selon la frontière

- [FastAPI UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/) et
  [réponses streaming](https://fastapi.tiangolo.com/advanced/custom-response/).
- [SQLite FTS5](https://sqlite.org/fts5.html), sections MATCH et BM25 ;
  [transactions SQLite](https://sqlite.org/lang_transaction.html).
- [Qdrant Query API](https://api.qdrant.tech/api-reference/search/query-points),
  [filtres](https://qdrant.tech/documentation/concepts/filtering/) et
  [snapshots](https://qdrant.tech/documentation/concepts/snapshots/).
- [ONNX Runtime Python](https://onnxruntime.ai/docs/api/python/api_summary.html)
  et [threads](https://onnxruntime.ai/docs/performance/tune-performance/threading.html).
- [E5-small officiel](https://huggingface.co/intfloat/multilingual-e5-small),
  préfixes, moyenne masquée, 384 dimensions et normalisation.
- [Ollama chat](https://docs.ollama.com/api/chat), streaming NDJSON,
  options, `done_reason` et compteurs réels.
  [Déchargement par keep_alive](https://docs.ollama.com/api/generate) avant
  admission d'une ingestion, confirmé par le statut des modèles résidents.
  [Modèles résidents](https://docs.ollama.com/api/ps), contexte et mémoire CPU/GPU.

Vérifier les signatures sur les versions installées, verrouillées par le
provisionnement du projet. Les doubles de tests sont explicitement identifiés et
ne valident jamais le parcours réel. Tester les défauts de publication, les
scopes et la reprise sur données isolées avant de compter une recette conforme.
