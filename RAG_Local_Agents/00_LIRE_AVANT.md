# RAG PDF local — dossier de réalisation V2.1

**Rôle :** point d'entrée du référentiel d'exigences et du chantier, distinct de la documentation du système livré · **Propriétaire :** documentation et intégration du produit · **Statut :** Vivant ; baseline d'exigences V2.1 conservée · **Référence :** baseline du 29/09/2026 et code publié `635d74a`, suivi `ee2341a` ; correction documentaire R14-2 du 2026-10-02 · **Mis à jour :** 2026-10-02 19:40 (UTC) · **Source de vérité :** fichiers canoniques indiqués ci-dessous ; [README racine](../README.md) pour entrer dans le système livré

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md). **W018 (01/10/2026) : Linux natif (aarch64 et x86-64) devient une seconde plateforme**, toute machine Windows restant prise en charge comme avant ; réalisation en cours (lots J du [plan](PLAN.md)). **W024 et W025 (01/10/2026) : le CPU reste le socle, le repli et la référence de la recette D07 ; seule la génération par Ollama peut passer sur GPU, automatiquement sur les voies qualifiées par un essai réel** ([W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024)). Les mentions « CPU uniquement » ci-dessous gardent la formulation d'origine : aucun GPU n'est requis.

**Référence :** RAG-LOCAL-16 / baseline documentaire 2.1 / 29 septembre 2026.
**Statut :** référentiel d'exigences V2.1 (spécifications et consignes révisées après audit), base de la recette. L'application est implémentée dans ce dépôt et en cours de qualification ; l'état par critère est suivi dans [PLAN.md](PLAN.md) et [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md).

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
| [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md) | Contrat d'exploitation Windows natif (W001) : lanceur, processus, disponibilité et limites |
| [QUALIFICATION.md](QUALIFICATION.md) | Vérifications précoces, A/B ciblé et protocole de mesure |
| [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md) | Critères de recette et preuves exigées |
| [PLAN.md](PLAN.md) | Dépendances, propriétaires et intégration verticale |
| [DECISIONS.md](DECISIONS.md) | Choix arrêtés, choix à qualifier et règles d'arbitrage |
| [CHANGELOG.md](CHANGELOG.md) | Corrections effectivement intégrées aux documents |
| [SOURCES.md](SOURCES.md) | Liens officiels et statut des références |
| [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md) | Vérification officielle obligatoire, étude SOTA utile et maintenance traçable |
| [SKILLS.md](SKILLS.md) | Registre des skills du pack (`skills/`) et des skills projet (`.agents/skills/` à la racine du dépôt), sélection des skills externes |
| [CLAUDE.md](CLAUDE.md) | Adaptateur de consignes sans installation ou auto-découverte supposée |
| `skills/` | Cinq dossiers avec leur vrai `SKILL.md`, à charger selon la tâche |
| `config/` | Paramètres de référence et exemples natifs |
| `tools/` | Génération du brief et vérification documentaire réellement disponibles |
| [journal/](journal/README.md), `reports/` | Journal daté des travaux et rapports de preuve du chantier |

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

La cible Windows reste Windows 11 natif, 16 Gio physiques, CPU uniquement. Les services et données sont gérés localement sans WSL ni Docker ; le budget comprend le navigateur et les processus du système. Depuis le 1er octobre 2026, les lanceurs prennent aussi en charge Linux aarch64 et x86-64 natifs ([W018](DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs)). Les essais Linux exécutés portent sur le poste aarch64 déclaré dans le [tableau Linux de la DoD](DEFINITION_OF_DONE.md#qualification-linux-w018) ; aucune machine Linux x86-64 n'a encore été qualifiée et les preuves Linux ne valent pas pour Windows. La recette D07 exige, sur chaque plateforme, un hôte de 16 Go physiques au plus en calcul CPU ; le Jetson de 61 Gio ne satisfait pas cette condition.

Les contrôles de ce dossier (`tools/`) portent sur les documents, leurs liens locaux, le SQL lexical et des exemples déterministes de référence. Ils ne valident ni Docling, ni le LLM, ni Qdrant, ni l'interface sur le poste utilisateur. Le rapport `CONTROLES_DOSSIER.json` distingue explicitement ces périmètres. Les tests de l'application sont à la racine du dépôt ; leur mode d'emploi est dans le [README racine](../README.md#14-tests-et-build).

## Contrôles du dossier disponibles

`tools/build_brief.py` n'utilise que la bibliothèque standard Python. `tools/verify_pack.py` exige Python 3.11 ou plus (`datetime.UTC`) et PyYAML, dont la version est fixée dans `tools/requirements.txt` ; le contrôle de la documentation stabilisée, `tools/docs/check_docs.py` à la racine du dépôt, exige aussi Python 3.11 ou plus (`tomllib`). L'environnement du projet fournit les deux : CPython 3.12.14 (installé par `bootstrap.ps1` sous Windows, par uv dans `.runtime/python` sous Linux ; plage `>=3.12,<3.13` dans `pyproject.toml`) et PyYAML 6.0.3 (`pyproject.toml`). Lancer les contrôles depuis la racine du dépôt avec son interpréteur, noté `<python>` ci-dessous : `.\.venv\Scripts\python.exe` sous Windows, préparé par `bootstrap.ps1` ; `.venv/bin/python` sous Linux, préparé par [`bootstrap.sh`](../bootstrap.sh), qui installe uv et CPython dans le projet puis synchronise `.venv` avec `uv sync --locked`. Préparation et prérequis : [dossier de déploiement](../docs/deploiement/DEPLOIEMENT.md#2-préparer-un-clone).

```bash
<python> RAG_Local_Agents/tools/build_brief.py --check
<python> RAG_Local_Agents/tools/verify_pack.py --report <fichier-neuf>.json
<python> tools/docs/check_docs.py
```

Sans l'option indiquée, deux de ces outils écrivent dans un fichier suivi par Git. `build_brief.py` sans `--check` régénère `RAG_LOCAL_BRIEF_COMPLET.md` : le lancer après la modification d'un document canonique et committer le brief avec elle. `verify_pack.py` sans `--report` réécrit `CONTROLES_DOSSIER.json` : pour un simple contrôle, donner un fichier neuf hors du dépôt ou sous `.runtime/qa/`, ignoré par Git. La liste complète des contrôles documentaires est tenue dans [docs/README.md](../docs/README.md#contrôles).

Ces commandes contrôlent le dossier documentaire, pas l'application. Les commandes de produit que `IMPLEMENTATION.md` décrit sous la forme `scripts/*.py` (contrat d'origine du pack) n'existent pas sous ces noms : elles sont implémentées comme sous-commandes de `services/runtime/cli.py`, appelées sous Windows par [`rag.ps1`](../rag.ps1) et sous Linux par [`rag.sh`](../rag.sh). `up` et `down` y tiennent les rôles de `start` et `stop` ; `verify` contrôle une sauvegarde, pas une suite de recette. Leur mode d'emploi est dans [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md) pour le contrat Windows et dans la [documentation d'exploitation](../docs/exploitation/EXPLOITATION.md) pour les commandes livrées sur les deux plateformes. Une procédure disponible ne prouve pas sa réussite sur un autre poste : les résultats et limites restent dans la DoD et le journal.
