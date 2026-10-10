# Documentation du poste documentaire local

**Rôle :** index de la documentation stabilisée, séparation avec le suivi vivant et convention d'en-tête · **Propriétaire :** documentation du produit (R14) · **Statut :** Stabilisé · **Référence :** commit `5ca3685` et modifications documentaires locales R14-1 du 2026-10-02 ; index initial `6935e13`, compléments GPU `4d8ba68` et Linux `36824e2` conservés ; lien de livraison W038 sur base `5fb5dc8` ; kit hors ligne Linux (rôles et sources du déploiement, de l'exploitation, de la sauvegarde et du dépannage, guide généré) sur la base `78ec95c` et les modifications locales R26-KIT-04 du 2026-10-07, rôle du déploiement complété après la revue U3 ; étude Office R28 du 09/10/2026 conservée ; architecture/contrats Office documentés sur base `64e191f` et modifications locales du 10/10/2026, chaîne DEV native Linux aarch64 vérifiée, réserves de qualification maintenues ; restitution réelle du kit Linux B (`5204d2e`) du 09/10/2026 · **Mis à jour :** 2026-10-10 13:28 (UTC) · **Source de vérité :** ce fichier pour l'organisation de `docs/` ; chaque document pour son sujet · **Remplace :** aucun document

`docs/` décrit le système tel qu'il est livré à la référence citée en tête de chaque document. Le suivi du chantier (plan, journal, décisions, sources, rapports de preuve) et le référentiel d'exigences V2.1 restent dans [`RAG_Local_Agents/`](../RAG_Local_Agents/), dossier vivant qui n'est pas déplacé : ses outils `build_brief.py` et `verify_pack.py` dépendent de son emplacement. Le point d'entrée général est le [README racine](../README.md).

## Documents stabilisés

| Document | Rôle | Statut | Source de vérité |
|---|---|---|---|
| [Architecture technique](architecture/ARCHITECTURE.md) | Composants, processus et ports, flux (démarrage, ouverture de l'atelier, arrêt), ingestion, recherche et génération, accélération GPU de la génération (mode par instance, voies qualifiées, repli sur CPU, essai réel), interfaces internes, données et identités, sécurité et session locale, déploiement sous Windows et sous Linux, distribution par le kit hors ligne Linux, observabilité ; écarts avec l'exigence V2.1 | Stabilisé | Code de `services/`, `apps/web/`, `rag.ps1`, `rag.sh`, `bootstrap.sh`, `tools/dist/`, profils `config/local16-4b.yaml` (choix par défaut) et `config/local16.yaml` |
| [Spécifications fonctionnelles](specifications/SPECIFICATIONS.md) | Règles métier, comportements livrés, cas limites et critères d'acceptation ; exigences V2.1 et décisions liées, sans recopier les résultats de recette | Stabilisé | `SPEC_ARCHITECTURE.md`, `IMPLEMENTATION.md`, `DEFINITION_OF_DONE.md`, contrats et code cités par fonction |
| [Interface HTTP et SSE](interfaces/API.md) | Routes `/api/v1` déclarées, session locale, cookies, CSRF et jeton de contrôle, erreurs, flux SSE des questions, en-têtes, corps de requête | Stabilisé | `services/api/main.py`, `services/api/security.py`, `services/api/schemas.py`, `packages/contracts/contracts.json` |
| [Déploiement](deploiement/DEPLOIEMENT.md) | Préparer un clone Windows/Linux ; fabriquer, installer, mettre à jour ou retirer un kit Windows interne ; fabriquer, transporter, installer, mettre à jour, revenir en arrière et désinstaller le kit hors ligne Linux, ce qui s'exécute avant la vérification du kit, emplacements, intégration au bureau, codes de sortie et rapports (section 8, source des procédures que résume le guide `LISEZMOI.md` du kit) ; prérequis, cibles, contrôles et reprise ; voies écrites et essais réels distingués | Stabilisé | `bootstrap.ps1`, `bootstrap.sh`, `rag.ps1`, `rag.sh`, `tools/dist/` (dont `linux_kit.py`, `linux_install.py`, `install.sh`), procédure d'exploitation ; limites tenues par R10/R22 et R26-KIT du plan |
| [Exploitation](exploitation/EXPLOITATION.md) | Préparer, démarrer, ouvrir l'atelier (`open`), gérer et révoquer les sessions, superviser, importer un dossier, arrêter, reprendre ; portée de `doctor` et `status` ; complément GPU d'un Jetson, rubrique `calcul` de `doctor`, calibration ; sous Linux, `bootstrap.sh`, `rag.sh`, correspondance des options et prérequis propres ; lanceur `atelier` et menu d'une installation par le kit Linux (section 11) | Stabilisé | `rag.ps1`, `rag.sh`, `bootstrap.sh`, `services/runtime/`, `services/api/security.py`, `tools/corpus/import_folder.py`, `tools/dist/linux_install.py` ; contrat W001 dans `RAG_Local_Agents/EXPLOITATION_WINDOWS.md` |
| [Sauvegarde et restauration](exploitation/SAUVEGARDE-RESTAURATION.md) | Snapshot cohérent, vérification, restauration dans une racine neuve, retour arrière, preuves ; commandes sous Linux ; sauvegardes d'une installation par le kit Linux (section 2) | Stabilisé | `services/runtime/backup.py`, `tools/dist/linux_install.py` |
| [Dépannage](exploitation/DEPANNAGE.md) | Symptôme, cause et commande, avec le message exact du code ou de l'écran de session ; messages de l'installateur, du lanceur `atelier` et de la garde de `rag.sh` du kit Linux, avec leur code de sortie (section 10) | Stabilisé | Messages de `rag.ps1`, `rag.sh`, `bootstrap.ps1`, `bootstrap.sh`, `services/`, `tools/` (dont `tools/dist/install.sh` et `linux_install.py`) et de `apps/web/src/lib/session.ts` et `generation.ts` |

Le guide `LISEZMOI.md` d'un kit hors ligne Linux n'est pas versionné dans `docs/` : il est généré à chaque fabrication par [`tools/dist/kit_guide.py`](../tools/dist/kit_guide.py) depuis le modèle [`tools/dist/templates/LISEZMOI-linux.md`](../tools/dist/templates/LISEZMOI-linux.md), le manifeste du kit et les constantes de l'installateur, porte le statut Généré et renvoie aux sections canoniques du déploiement, de l'exploitation, du dépannage et de la sauvegarde sans les recopier. Ces sections ne renvoient qu'à des fichiers livrés dans le kit ; une section absente arrête la fabrication.

## Schémas

Les schémas sont des SVG en couleur produits par [`tools/docs/diagrams.py`](../tools/docs/diagrams.py) (bibliothèque standard Python, sans réseau). Leur fond est explicite pour rester lisibles en thème clair comme sombre ; leur texte ne descend pas sous 12 px pour une largeur d'affichage de 880 px. Ils ne se modifient qu'en changeant le script puis en régénérant.

| Schéma | Ce qu'il montre | Statut | Source de vérité |
|---|---|---|---|
| [Processus et ports](assets/diagrams/processus-ports.svg) | Navigateur, superviseur, API et interface (8785) avec session ou jeton exigés, Qdrant (6333), Ollama (11434, modèle sur CPU ou GPU), worker PDF à la demande (schéma du flux PDF ; voie Office décrite dans l’architecture), dossiers de `.runtime/` | Généré | `tools/docs/diagrams.py`, fonction `processes` |
| [Séquence de rag.ps1 up puis open](assets/diagrams/sequence-up.svg) | Ordre des contrôles au démarrage, dont `llm.accelerator`, décision du mode de génération après le démarrage d'Ollama, demande du lien d'ouverture de session et message de chaque refus bloquant | Généré | `tools/docs/diagrams.py`, fonction `startup` |
| [Chaîne d'ingestion](assets/diagrams/ingestion.svg) | Flux PDF : import, file, admission, worker, fenêtres, routage par page, assemblage, indexation, publication d'office ou explicite (W012), révisions | Généré | `tools/docs/diagrams.py`, fonction `ingestion` |
| [Séquence d'une question](assets/diagrams/sequence-question.svg) | Requête avec cookie de session et jeton CSRF, recherche hybride, sélection, contexte, admission mémoire, génération, validation et ouverture d'une citation | Généré | `tools/docs/diagrams.py`, fonction `question` |
| [Sauvegarde et restauration](assets/diagrams/sauvegarde-restauration.svg) | Étapes de `backup` et de `restore`, contenu du snapshot, démarrage du profil restauré | Généré | `tools/docs/diagrams.py`, fonction `backup` |

## Documents vivants et exigences (hors de docs/)

| Document | Rôle |
|---|---|
| [Livraison locale Linux avec réserves](../RAG_Local_Agents/reports/livraison-locale-linux-2026-10-06.md) | Synthèse vivante du périmètre retenu par W038, des kits Linux réellement exercés et de leurs réserves ; la qualification intégrale reste distincte, sans conformité V2.1 globale |
| [Étude DOCX/XLSX](../RAG_Local_Agents/reports/extension-office-2026-10-09.md) | Comparatif et mesures exploratoires datés du 09/10/2026 ; intégration réalisée ensuite dans l’arbre de travail, preuves de chaîne DEV native suivies dans R28 du plan ; référence implémentée dans l’architecture et l’API |
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
**Rôle :** … · **Propriétaire :** responsabilité de maintien · **Statut :** Stabilisé | Vivant | Historique | Généré · **Référence :** commit court ou baseline et modifications locales datées · **Mis à jour :** AAAA-MM-JJ HH:MM (UTC) · **Source de vérité :** … · **Remplace :** … (ou **Remplacé par :** …)
```

Le propriétaire désigne une responsabilité durable, pas un agent ou une session ; le champ ne reste pas vide. Le statut porté par l'en-tête doit être celui de la ligne du document dans l'index ci-dessus. L'heure de « Mis à jour » est lue sur l'horloge du poste au moment de l'écriture ; les renvois `fichier:ligne` sont recalculés sur la référence citée : un commit, ou un commit suivi de modifications locales datées, auquel cas ils valent pour les fichiers du disque à cette date. Une référence future n'est pas une référence de travail.

## Contrôles

```powershell
.\.venv\Scripts\python.exe tools/docs/check_docs.py
.\.venv\Scripts\python.exe tools/docs/diagrams.py --check
.\.venv\Scripts\python.exe -m pytest tests/unit/test_docs_space.py tests/unit/test_docs_tooling.py -q -p no:cacheprovider
.\.venv\Scripts\ruff.exe check tools/docs tests/unit/test_docs_space.py
.\.venv\Scripts\python.exe RAG_Local_Agents/tools/verify_pack.py --report .runtime\qa\verify-pack-<horodatage>.json
```

Sans `--report`, `verify_pack.py` réécrit `RAG_Local_Agents/CONTROLES_DOSSIER.json`, fichier suivi par Git : lui donner un fichier neuf sous `.runtime\qa\` pour un simple contrôle.

`check_docs.py` vérifie, sans réseau : la résolution des liens relatifs et des ancres depuis `README.md`, `CHANGELOG.md` et `docs/`, l'absence de lien vers `.runtime/`, `.git/` ou un chemin ignoré par Git, l'en-tête (dont le propriétaire non vide) et le statut de chaque document de `docs/` et sa présence dans l'index, l'absence de dessin en caractères de boîte ou de bloc Mermaid, la validité des SVG référencés (XML, fond, titre, taille de texte, aucune ressource externe) et l'égalité des versions de `pyproject.toml` et `apps/web/package.json`. Il ne vérifie pas l'exactitude du contenu : chaque affirmation se contrôle contre le code ou la preuve qu'elle cite.
