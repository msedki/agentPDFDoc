# Documentation du poste documentaire local

**Rôle :** index de la documentation stabilisée, règle de séparation entre documents vivants et stabilisés, en-tête obligatoire · **Statut :** Stabilisé · **Référence :** commit `e0be4ac` · **Mis à jour :** 2026-09-30 (UTC) · **Source de vérité :** ce fichier pour l'organisation de `docs/` ; chaque document pour son sujet · **Remplace :** aucun document

`docs/` décrit le système tel qu'il est livré à la référence citée en tête de chaque document. Le suivi du chantier (plan, journal, décisions, sources, rapports de preuve) et le référentiel d'exigences V2.1 restent dans [`RAG_Local_Agents/`](../RAG_Local_Agents/), dossier vivant qui n'est pas déplacé : ses outils `build_brief.py` et `verify_pack.py` dépendent de son emplacement. Le point d'entrée général est le [README racine](../README.md).

## Documents stabilisés

| Document | Rôle | Statut | Source de vérité |
|---|---|---|---|
| [Architecture technique](architecture/ARCHITECTURE.md) | Composants, processus et ports, flux, ingestion, recherche et génération, interfaces internes, données et identités, sécurité, déploiement, observabilité ; écarts avec l'exigence V2.1 | Stabilisé | Code de `services/`, `apps/web/`, `rag.ps1`, profil `config/local16.yaml` |
| [Interface HTTP et SSE](interfaces/API.md) | Routes `/api/v1` déclarées, erreurs, flux SSE des questions, en-têtes exigés, corps de requête | Stabilisé | `services/api/main.py`, `services/api/schemas.py`, `packages/contracts/contracts.json` |
| [Exploitation](exploitation/EXPLOITATION.md) | Préparer, démarrer, superviser, arrêter, reprendre ; portée de `doctor` et `status` | Stabilisé | `rag.ps1`, `services/runtime/` ; contrat W001 dans `RAG_Local_Agents/EXPLOITATION_WINDOWS.md` |
| [Sauvegarde et restauration](exploitation/SAUVEGARDE-RESTAURATION.md) | Snapshot cohérent, vérification, restauration dans une racine neuve, retour arrière, preuves | Stabilisé | `services/runtime/backup.py` |
| [Dépannage](exploitation/DEPANNAGE.md) | Symptôme, cause et commande, avec le message exact du code | Stabilisé | Messages de `rag.ps1`, `bootstrap.ps1` et `services/` |

## Schémas

Les schémas sont des SVG en couleur produits par [`tools/docs/diagrams.py`](../tools/docs/diagrams.py) (bibliothèque standard Python, sans réseau). Leur fond est explicite pour rester lisibles en thème clair comme sombre ; leur texte ne descend pas sous 12 px pour une largeur d'affichage de 880 px. Ils ne se modifient qu'en changeant le script puis en régénérant.

| Schéma | Ce qu'il montre | Statut | Source de vérité |
|---|---|---|---|
| [Processus et ports](assets/diagrams/processus-ports.svg) | Navigateur, superviseur, API et interface (8785), Qdrant (6333), Ollama (11434), worker PDF à la demande, dossiers de `.runtime/` | Généré | `tools/docs/diagrams.py`, fonction `processes` |
| [Séquence de rag.ps1 up](assets/diagrams/sequence-up.svg) | Ordre des contrôles au démarrage et message de chaque refus bloquant | Généré | `tools/docs/diagrams.py`, fonction `startup` |
| [Chaîne d'ingestion](assets/diagrams/ingestion.svg) | Import, file, admission, worker, fenêtres, routage par page, assemblage, indexation, publication, révisions | Généré | `tools/docs/diagrams.py`, fonction `ingestion` |
| [Séquence d'une question](assets/diagrams/sequence-question.svg) | Recherche hybride, sélection, contexte, admission mémoire, génération, validation et ouverture d'une citation | Généré | `tools/docs/diagrams.py`, fonction `question` |
| [Sauvegarde et restauration](assets/diagrams/sauvegarde-restauration.svg) | Étapes de `backup` et de `restore`, contenu du snapshot, démarrage du profil restauré | Généré | `tools/docs/diagrams.py`, fonction `backup` |

## Documents vivants et exigences (hors de docs/)

| Document | Rôle |
|---|---|
| [PLAN.md](../RAG_Local_Agents/PLAN.md) | Suivi canonique du chantier : lots, statuts, blocages, prochaine action |
| [DEFINITION_OF_DONE.md](../RAG_Local_Agents/DEFINITION_OF_DONE.md) | Critères de fin D01 à D11 et règle de clôture |
| [DECISIONS.md](../RAG_Local_Agents/DECISIONS.md) | Décisions de conception (D-01 à D-16) et décisions du chantier (W001 et suivantes) |
| [Journal](../RAG_Local_Agents/journal/README.md) | Travaux effectués, commandes, résultats, échecs et reprises, par date |
| [SOURCES.md](../RAG_Local_Agents/SOURCES.md) | Sources officielles consultées, avec version, date, apport et limite |
| [SPEC_ARCHITECTURE.md](../RAG_Local_Agents/SPEC_ARCHITECTURE.md), [IMPLEMENTATION.md](../RAG_Local_Agents/IMPLEMENTATION.md) | Exigences d'architecture et contrats d'implémentation V2.1 |
| [CONFIGURATION.md](../RAG_Local_Agents/CONFIGURATION.md) | Explication des paramètres du profil `local16` |
| [QUALIFICATION.md](../RAG_Local_Agents/QUALIFICATION.md) | Protocole de mesure, jeux de questions, métriques et dénominateurs |
| [EXPLOITATION_WINDOWS.md](../RAG_Local_Agents/EXPLOITATION_WINDOWS.md) | Contrat d'exploitation Windows natif (W001) |
| [Rapports de preuve](../RAG_Local_Agents/reports/) et [preuves d'interface](../apps/web/reports/) | Sorties JSON, journaux et captures des exécutions réelles |
| [CHANGELOG.md](../CHANGELOG.md) | Changements notables du produit, avec commit et preuve |

## Règle vivant, stabilisé, généré, historique

| Statut | Emplacement | Règle |
|---|---|---|
| Vivant | `RAG_Local_Agents/`, `apps/web/reports/`, `CHANGELOG.md` | Évolue avec le travail ; peut décrire un état intermédiaire, un échec ou une reprise, avec sa preuve |
| Stabilisé | `docs/`, `README.md` | Décrit uniquement ce qui est livré à la référence citée ; ce qui n'est que codé ou testé unitairement est dit comme tel ; ne change qu'après un changement réel et vérifié du système, tracé dans `DECISIONS.md` lorsqu'il est structurant |
| Généré | `docs/assets/diagrams/` | Produit par un script versionné ; jamais édité à la main |
| Historique | Document remplacé conservé | Garde son contenu et renvoie vers son remplaçant par « Remplacé par » |

Une information n'a qu'une source de vérité : un autre document y renvoie sans la recopier. Les valeurs volatiles (mémoire disponible, durées mesurées) ne figurent dans `docs/` qu'avec le lien de leur preuve.

## En-tête obligatoire

Chaque document de `docs/` commence par un titre de niveau 1 suivi d'une ligne d'en-tête dont les champs sont séparés par « · » :

```text
**Rôle :** … · **Statut :** Stabilisé | Vivant | Historique | Généré · **Référence :** commit court ou baseline · **Mis à jour :** AAAA-MM-JJ (UTC) · **Source de vérité :** … · **Remplace :** … (ou **Remplacé par :** …)
```

Le statut porté par l'en-tête doit être celui de la ligne du document dans l'index ci-dessus.

## Contrôles

```powershell
.\.venv\Scripts\python.exe tools/docs/check_docs.py
.\.venv\Scripts\python.exe tools/docs/diagrams.py --check
.\.venv\Scripts\python.exe -m pytest tests/unit/test_docs_space.py -q -p no:cacheprovider
```

`check_docs.py` vérifie, sans réseau : la résolution des liens relatifs et des ancres depuis `README.md`, `CHANGELOG.md` et `docs/`, l'absence de lien vers `.runtime/`, `.git/` ou un chemin ignoré par Git, l'en-tête et le statut de chaque document de `docs/` et sa présence dans l'index, l'absence de dessin en caractères de boîte ou de bloc Mermaid, la validité des SVG référencés (XML, fond, titre, taille de texte, aucune ressource externe) et l'égalité des versions de `pyproject.toml` et `apps/web/package.json`. Il ne vérifie pas l'exactitude du contenu : chaque affirmation se contrôle contre le code ou la preuve qu'elle cite.
