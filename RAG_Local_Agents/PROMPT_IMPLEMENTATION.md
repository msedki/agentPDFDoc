# Mission agents — RAG PDF local V2.1, CPU, 16 Go

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md). **W018 (01/10/2026) : Linux natif (aarch64 et x86-64) devient une seconde plateforme**, toute machine Windows restant prise en charge comme avant ; réalisation en cours (lots J du [plan](PLAN.md)). **W024 et W025 (01/10/2026) : le CPU reste le socle, le repli et la référence de la recette D07 ; seule la génération par Ollama peut passer sur GPU, automatiquement sur les voies qualifiées par un essai réel** ([W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024)). La mention « sans GPU » ci-dessous garde la formulation d'origine : aucun GPU n'est requis.

Tu es l'agent principal chargé de **réaliser, intégrer et vérifier une application exploitable**, pas de produire uniquement un plan, un scaffold, des écrans factices ou un nouvel audit.

## Objectif concret

Construis une bibliothèque locale de PDF en arborescence, avec lecteur, sélection, recherche et chat reliés. L'utilisateur choisit le périmètre : bibliothèque, dossier récursif, documents, section, pages ou sélection. Chaque réponse documentaire cite les preuves réellement utilisées ; un clic ouvre la bonne version du PDF, la bonne page et la zone dont la géométrie est disponible. Les limites de couverture et l'incertitude sont visibles.

Le produit fonctionne sur PC de **16 Go maximum, sans GPU**, hors ligne après provisionnement. Le développement peut utiliser des agents externes autorisés, mais aucun PDF privé ne leur est envoyé sans autorisation. Le modèle local du produit est distinct du modèle de l'agent de développement.

## Référentiel et décisions

Inspecte les instructions applicables et l'existant. Lis `AGENTS.md`, puis les sections utiles de `SPEC_ARCHITECTURE.md`, `IMPLEMENTATION.md`, `CONFIGURATION.md`, `QUALIFICATION.md`, `DEFINITION_OF_DONE.md` et `PLAN.md`. `DECISIONS.md` fixe les arbitrages ; `SOURCES.md` indique les références et leurs limites. Ne relis pas également tout le brief consolidé : c'est une copie générée.

Conserve la stack retenue : Next.js/React/TypeScript export statique, PDF.js, FastAPI, SQLite/FTS5, Qdrant local, E5-small ONNX CPU INT8, Docling/Tesseract routé, Qwen3.5 4B Q4_K_M via Ollama. E5 est la baseline ; une seule alternative d'embedding issue de l'audit, Granite 97M Multilingual R2, peut être qualifiée après vérification officielle de l'artefact. Une indisponibilité du candidat ne bloque pas les autres chantiers. Ne substitue pas un framework par préférence personnelle.

**Fige les invariants ; qualifie les paramètres.** Local, CPU, enveloppe mémoire, provenance, scope et intégrité ne sont pas négociables. Threads, contexte, stockage Qdrant, politique de reprise et embedding final sont arrêtés après essais ciblés documentés, sans grille exploratoire générale.

## Sources officielles et skills obligatoires

**Pour étudier, décider, implémenter un contrat externe ou mettre à jour, consulte systématiquement les sources officielles pertinentes et actuelles, ainsi que le contrat de la version réellement installée.** Ne te fonde pas uniquement sur ta mémoire ou le présent brief. Cherche les bonnes pratiques et avancées SOTA auprès des mainteneurs/auteurs ; distingue capacité documentée, hypothèse et mesure locale. Fige une décision seulement après le test approprié, pas après une lecture de benchmark éditeur.

Applique [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md). Découvre les compétences réellement accessibles, utilise [SKILLS.md](SKILLS.md) pour choisir la bonne, puis ouvre et applique son `SKILL.md`. Cherche une compétence officielle manquante lorsque cela apporte une valeur réelle ; vérifie sa provenance, sa compatibilité et ses permissions avant usage. N'invente ni installation ni outil, et ne charge pas toutes les compétences dans le contexte.

Réutilise les références versionnées encore valides ; revalide lorsqu'un composant, un risque ou une information actuelle change. Partage les recherches utiles entre sous-agents. Trace URL/version/date, décision, essai et preuve dans les registres, puis synchronise les `.md`, configurations et tests. Une source invérifiable reste explicitement bloquée ; continue les autres tâches prêtes sans inventer le résultat. Le réseau documentaire du développement ne doit jamais devenir un accès cloud de l'application locale.

## Résultats techniques indispensables

Le parsing route vers une extraction native légère lorsque sa qualité est suffisante, une extraction structurée pour les contenus difficiles et l'OCR régional quand nécessaire. Un paragraphe natif ne doit pas masquer un tableau scanné sur la même page. Les fenêtres de checkpoint ne coupent pas les sections et tableaux sémantiquement. Tous les chemins produisent une provenance canonique commune.

La recherche hybride applique les filtres avant top-k. RRF ne doit pas faire disparaître une référence exacte explicitement visée : vérifier sa couverture après fusion, déduplication, expansion et budget final. Une occurrence sans preuve de la réponse ne suffit pas. Mesurer la présence des preuves dans le contexte réellement transmis, pas seulement Recall@10.

Les citations et les offsets viennent des données persistées, pas du modèle. Sélections : texte source immuable hashé, offsets en points de code Unicode, conversion UTF-16 au frontend, mapping explicite des normalisations. Une géométrie approximative est signalée, jamais inventée.

Le chat conserve les référents utilisateur autorisés sans transformer une réponse précédente du LLM en source. Une relance ambiguë demande une précision ciblée ; un changement de scope ne doit pas laisser fuiter les preuves de l'ancien périmètre.

L'indexation est incrémentale et reprenable, avec versions et révisions d'extraction conservées. Un nouveau modèle dense utilise une autre identité d'index, même si ses dimensions sont identiques. Une nouvelle génération est publiée après validation ; les anciennes citations restent résolubles.

Le gouverneur sépare calcul lourd PDF et génération LLM. Pause coopérative au checkpoint ; pas de kill nominal après cinq secondes, pas de reprises périodiques provoquant des rechargements en boucle. Reprise manuelle initiale, politique automatique seulement après mesure. L'UI montre attente, progression, annulation et limites.

## Travail efficace : dépendances et preuves

Établis rapidement les contrats minimaux Scope/Citation/Selection/Query/Checkpoint, puis mène les chantiers indépendants en parallèle : ingestion/provenance, retrieval/backend, interface PDF et qualification/exploitation. Utilise subagents, workflows, skills et worktrees seulement s'ils réduisent le chemin critique ou améliorent une vérification réelle. Chaque délégation possède résultat attendu, fichiers, dépendances, tests et preuve ; un seul propriétaire intègre chaque zone partagée.

Mène très tôt trois vérifications ciblées : modèle sur CPU cible, extraction/provenance sur PDF difficiles, recherche sur identifiants/périmètres adverses. Ne transforme pas ces vérifications en tunnel séquentiel empêchant le développement UI ou les tests indépendants. Les travaux de développement peuvent être parallèles ; les benchmarks lourds sur un même PC partagent un budget et ne doivent pas se concurrencer.

Intègre tôt la tranche verticale réelle : **import PDF → extraction → index → question → réponse → citation → ouverture/surlignage**. Fais-la évoluer sans la casser. Les mocks débloquent éventuellement une branche mais ne prouvent jamais l'intégration.

À chaque défaut : observation → hypothèse causale → test discriminant → correction minimale → vérification. Pas d'essai répété sans information nouvelle, pas de réindexation/OCR complet par réflexe, pas de changements simultanés de nombreux paramètres. Réutilise les caches valides ; changer l'embedding ne justifie pas de refaire le parsing. Après un diagnostic, choisis au maximum une alternative justifiée, compare puis décide.

## Validation et livraison

Applique `DEFINITION_OF_DONE.md`. Distingue tests documentaires, application implémentée, E2E réel, mesures sur la cible et qualification métier. Aucun statut PASS sans commande, commit, configuration, corpus et preuve. Ne pas baisser un seuil après échec, inventer des chiffres ou présenter la présence de code comme une validation.

Tiens `PLAN.md` à jour après résultat, décision ou blocage significatif ; ne documente pas chaque détail au détriment du travail utile. Conserve les défauts et les limites restantes. Les scripts, tests et commandes produit annoncés comme disponibles doivent réellement exister et avoir été exécutés. Les documents canoniques modifiés régénèrent le brief unique ; pas de copies divergentes.

Commence par l'inspection ciblée du dépôt et de la machine, fixe les contrats qui débloquent les travaux, puis implémente et vérifie. Ne t'arrête pas au plan et ne demande pas de confirmation pour une décision déjà spécifiée.
