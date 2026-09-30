# Registre et usage des skills — RAG-LOCAL-16 V2.1

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md).

## Point d'entrée

Les cinq dossiers ci-dessous contiennent de **vrais `SKILL.md` rédigés pour ce projet**. Ils organisent le travail des agents de développement ; ils ne sont pas des plugins installés ni des compétences certifiées par OpenAI, Anthropic ou un éditeur de la stack.

Lire les noms/descriptions, choisir le skill utile, puis ouvrir son fichier. Si l'environnement fournit déjà un skill plus adapté, en contrôler les instructions et la compatibilité avant de le réutiliser ; ne pas charger les deux intégralement par réflexe. Les décisions externes restent soumises à [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md).

| Tâche | Skill projet et chemin exact | Sortie attendue |
|---|---|---|
| Étudier une option, décider, migrer, vérifier SOTA/API | [official-source-review](skills/official-source-review/SKILL.md) | Source primaire, contrat de version, décision et test |
| Implémenter ou corriger parsing, OCR, provenance et citations | [rag-pdf-provenance](skills/rag-pdf-provenance/SKILL.md) | Extraction traçable et fixtures de géométrie/couverture |
| Optimiser ou vérifier embeddings, lexical, fusion et contexte | [rag-retrieval-evaluation](skills/rag-retrieval-evaluation/SKILL.md) | Preuves finales, scope et mesures de recherche/réponse |
| Qualifier RAM, CPU, chargements, offline et mises à jour | [local-cpu-qualification](skills/local-cpu-qualification/SKILL.md) | Mesures séparées, non-régression et décision de configuration |
| Développer ou tester arborescence/PDF/chat et E2E | [pdf-workspace-e2e](skills/pdf-workspace-e2e/SKILL.md) | Parcours réel, sélections, sources et budget de rendu |

## Découverte et compatibilité avec les agents

Le chemin `skills/` est un rangement portable du projet, **pas une promesse d'auto-découverte universelle**. Le prompt et `AGENTS.md` demandent de lire ces chemins explicitement ; cela permet leur usage même si le client ne les installe pas comme skills natifs. La lecture du fichier et son installation par le client sont deux opérations différentes.

Avant une intégration native Codex, Claude Code ou autre : identifier la version du client ; consulter sa documentation actuelle ; utiliser son format de manifeste, son emplacement et sa procédure de validation réels ; tester la découverte et l'invocation. Ne pas inventer une commande, un champ YAML, un outil `skill-installer` disponible ni un chemin global. Aucun identifiant de modèle « Astra » n'est fixé par un Markdown.

Ces skills pointent vers les documents canoniques situés deux niveaux plus haut. Conserver le dossier complet. Une copie dans un autre emplacement doit adapter les références ou embarquer les fichiers nécessaires, puis contrôler les liens et l'absence de divergence ; ne pas déplacer un `SKILL.md` seul en prétendant qu'il reste autonome.

**Sources actuelles vérifiées pour ce cadrage :** la spécification Agent Skills documente le format ; OpenAI propose un catalogue d'exemples `openai/plugins` et une documentation Build skills ; Anthropic publie ses pratiques d'écriture et des exemples. Le README actuel de `openai/skills` le marque déprécié : ne pas le traiter comme catalogue actuel sans suivre la redirection officielle. Les liens et limites d'accès sont enregistrés dans [SOURCES.md](SOURCES.md), S17–S23.

## Sélection d'un skill externe

Découvrir les capacités réellement installées avant de chercher ailleurs. Rechercher ensuite uniquement une compétence manquante et son fournisseur officiel. Évaluer sa portée, ses déclencheurs, ses dépendances, ses permissions, ses scripts, ses licences et ses preuves d'usage. Un exemple officiel n'est pas une certification de notre environnement.

Ne pas importer un skill de déploiement cloud, un connecteur documentaire externe ou un moteur OCR distant dans le chemin nominal local. Un skill Playwright déjà présent peut aider l'E2E, mais ses mocks ne remplacent pas le test avec le vrai backend. Un skill de création de PDF n'est pas, à lui seul, un skill d'ingestion RAG structurée.

En cas d'absence, utiliser la documentation officielle et le workflow projet. Créer une nouvelle compétence uniquement si une répétition réelle justifie son coût ; ne pas générer un skill par fonction, route ou fichier.

## Contrôle de format et contrôle de comportement

Les fichiers livrés utilisent `name`, `description`, `compatibility` et `metadata` dans le front matter ; aucun `allowed-tools` n'accorde des pouvoirs supposés. Le nom correspond au dossier, en minuscules avec tirets. Les instructions restent courtes et renvoient aux fichiers utiles. S17/S18 établissent les principes de format et de chargement progressif ; le seuil interne de 150 lignes par skill est un choix de ce projet.

`python tools/verify_pack.py` contrôle leur structure et leurs liens, pas leur activation dans un client. La recette agent doit ajouter une tâche de bon déclenchement, une de non-déclenchement et un résultat vérifiable. Enregistrer nom/chemin, origine, hash/version réellement calculés et preuve, ou `NOT_RUN`.

Au moment de livraison de ce dossier : **cinq skills projet disponibles comme fichiers ; aucune installation de skill externe ni activation native d'un client ne sont déclarées réalisées.**
