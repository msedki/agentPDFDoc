# RAG PDF local — dossier de réalisation V2.1

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md).

**Référence :** RAG-LOCAL-16 / baseline documentaire 2.1 / 29 septembre 2026.
**Statut :** fichiers de spécification et de consignes révisés après audit ; application à implémenter et à qualifier.

## Résultat attendu

Un poste de travail documentaire local : bibliothèque de PDF en arborescence, lecteur PDF, sélection, recherche hybride et analyse conversationnelle avec citations ouvrant la bonne version, la bonne page et la zone réellement connue. Profil nominal mono-utilisateur, CPU uniquement, PC de 16 Go de RAM maximum, sans API cloud en exploitation.

## Dossier à transmettre aux agents

Cette V2.1 remplace la baseline documentaire 1.0. Elle contient les **documents complets corrigés**, et non un addendum qu'il faudrait combiner avec l'ancien audit. Les corrections A01–A12 sont intégrées dans les spécifications, le prompt, les règles, les paramètres et les critères d'acceptation. Leur réalisation applicative reste à vérifier.

Dans un dépôt existant, fusionner ces consignes avec les instructions déjà applicables, sans écraser les modifications en cours. Transmettre `PROMPT_IMPLEMENTATION.md` à l'agent principal. `AGENTS.md` porte les instructions persistantes ; l'agent de développement et le modèle Ollama du produit sont deux composants distincts.

| Fichier | Rôle |
|---|---|
| [PROMPT_IMPLEMENTATION.md](PROMPT_IMPLEMENTATION.md) | Mission exécutable, objectifs et méthode de travail |
| [AGENTS.md](AGENTS.md) | Invariants, efficacité et discipline multi-agents |
| [SPEC_ARCHITECTURE.md](SPEC_ARCHITECTURE.md) | Architecture, stack, parcours et budget de ressources |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | API, algorithmes, provenance, sélection et persistance |
| [CONFIGURATION.md](CONFIGURATION.md) | Paramétrage, mapping aux composants et provisionnement |
| [QUALIFICATION.md](QUALIFICATION.md) | Vérifications précoces, A/B ciblé et protocole de mesure |
| [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md) | Critères de recette et preuves exigées |
| [PLAN.md](PLAN.md) | Dépendances, propriétaires et intégration verticale |
| [DECISIONS.md](DECISIONS.md) | Choix arrêtés, choix à qualifier et règles d'arbitrage |
| [CHANGELOG.md](CHANGELOG.md) | Corrections effectivement intégrées aux documents |
| [SOURCES.md](SOURCES.md) | Liens officiels et statut des références |
| [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md) | Vérification officielle obligatoire, étude SOTA utile et maintenance traçable |
| [SKILLS.md](SKILLS.md) | Registre des cinq skills projet et sélection des skills externes |
| [CLAUDE.md](CLAUDE.md) | Adaptateur de consignes sans installation ou auto-découverte supposée |
| `skills/` | Cinq dossiers avec leur vrai `SKILL.md`, à charger selon la tâche |
| `config/` | Paramètres de référence et exemples natifs |
| `tools/` | Génération du brief et vérification documentaire réellement disponibles |

## Source de vérité et usage du fichier unique

Les `.md` séparés et les fichiers `config/` sont canoniques. `RAG_LOCAL_BRIEF_COMPLET.md` est **généré** à partir de ces fichiers ; ne pas le modifier à la main et ne pas demander aux agents de relire à la fois toutes les sources et leur copie consolidée. `python tools/build_brief.py` le régénère ; `python tools/build_brief.py --check` contrôle sa synchronisation.

En cas de contradiction avec une ancienne archive ou l'audit historique, utiliser la V2.1. Dans la V2.1 : invariants utilisateur → Definition of Done → contrats d'implémentation → configuration validée. Une incohérence interne est un défaut à corriger, pas un prétexte pour choisir silencieusement le réglage le plus commode. Les valeurs numériques d'exploitation sont portées par `config/local16.yaml` et documentées dans `CONFIGURATION.md`.

## Règle ajoutée à tous les agents

Consulter systématiquement les sources officielles actuelles pour les études, décisions significatives et mises à jour ; lire le skill pertinent avant usage ; vérifier versions, provenance et résultats. La procédure se trouve dans [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md) et s'applique également aux sous-agents. Elle ne déclenche ni recherche redondante à chaque ligne de code ni téléchargement du produit en exploitation.

Les skills livrés sont propres au projet, au format documenté par Agent Skills ; ils ne sont pas annoncés comme installés dans votre client. Le prompt demande leur lecture explicite. Les URLs et exemples officiels sont séparés des décisions locales dans `SOURCES.md`.

## Choix opérationnels

Conserver Next.js/React statique + PDF.js, FastAPI, SQLite/FTS5, Qdrant et Ollama. E5-small ONNX CPU INT8 est la référence de départ. Un seul candidat d'embedding issu de l'audit, Granite 97M Multilingual R2, peut être comparé après vérification de ses artefacts officiels ; son indisponibilité ne bloque pas le développement avec E5. Docling utilise un routage natif / structuré / OCR régional, et non le pipeline lourd pour chaque page. Qwen3.5 4B Q4_K_M, non-thinking, reste le modèle nominal à qualifier.

## Ce qui est fixé et ce qui ne l'est pas encore

Les invariants sont fixes : local, CPU, enveloppe 16 Go, traçabilité, périmètre explicite, sécurité, absence de résultat fabriqué. Les paramètres CPU, la stratégie de résidence des index, les budgets de contexte et le choix final d'embedding sont qualifiés par des essais ciblés avant verrouillage. Aucune prétention de supériorité SOTA ou de performance matérielle n'est déduite de ce dossier.

La machine cible est Windows 11 natif, 16 Gio physiques, CPU uniquement. Les services et données sont gérés localement sans WSL ni Docker ; le budget comprend le navigateur et les processus Windows.

Les tests disponibles dans cette archive contrôlent les documents, leurs liens locaux, le SQL lexical et des exemples déterministes de référence. Ils ne valident ni Docling, ni le LLM, ni Qdrant, ni l'interface sur le poste utilisateur. Le rapport `CONTROLES_DOSSIER.json` distingue explicitement ces périmètres.

## Contrôles du dossier disponibles

`tools/build_brief.py` utilise la bibliothèque standard Python. Le vérificateur requiert PyYAML ; sa version utilisée ici est indiquée dans `tools/requirements.txt`. Provisionner cette dépendance avant un contrôle hors ligne.

```bash
python tools/build_brief.py
python tools/build_brief.py --check
python tools/verify_pack.py
```

Ces commandes s’exécutent sur le dossier documentaire. Les commandes `scripts/provision.py`, `scripts/start.py` et les autres commandes de produit décrites dans `IMPLEMENTATION.md` restent à implémenter par les agents ; elles ne sont pas livrées comme application existante.
