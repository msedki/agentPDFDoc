# Definition of Done — RAG-LOCAL-16 V2.1

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md).

## Règle de clôture

Un critère est `PASS` uniquement avec une preuve reproductible associée au commit, à la configuration, au corpus et à la machine. Les statuts permis sont `NOT_RUN`, `PASS`, `FAIL`, `BLOCKED`. « Le code existe », « l'agent affirme que cela marche » et « le test utilise un mock » ne valent pas validation de bout en bout.

Les seuils suivants sont des objectifs de recette, pas des performances déjà atteintes. Ne pas les diminuer après un échec pour afficher un succès. Une modification approuvée du périmètre exige une nouvelle baseline, une justification et une nouvelle recette.

La validation sur fixtures et la validation sur documents métier réels sont distinctes. Si aucun corpus privé autorisé n'est disponible, produire les fixtures synthétiques, réaliser tout ce qui est testable et marquer la qualification métier `BLOCKED — corpus métier absent`. Ne pas présenter cette limite comme un échec général de l'application ni inventer un corpus représentatif.

Baseline documentaire 2.1. Les objectifs conservés et ajoutés ci-dessous sont des critères du projet, pas des performances déjà mesurées. Le protocole de mesure est détaillé dans `QUALIFICATION.md`.

## D01 — Installation et reproductibilité

- [ ] Un environnement neuf peut être provisionné par le lanceur documenté, sans édition manuelle de code.
- [ ] Une installation provisionnée redémarre sans Internet et sans téléchargement implicite.
- [x] Les lockfiles de paquets et manifests de runtimes/modèles contiennent des versions/hashes réels ; aucun `latest` comme identité finale.
- [x] `doctor` distingue modèle absent, service indisponible, configuration ignorée, CPU/GPU utilisé et stockage incohérent.
- [x] Start/stop ne créent pas d'instances doublées et ne détruisent pas les données.

**Preuves :** logs de provisionnement/restart, manifests, sortie doctor, commandes exactes et versions des exécutables.

Preuve01/10/2026 (D01.19), contrôle relu sur le dépôt au commit `d52834f` : aucune occurrence de `latest` dans `config/artifacts.lock.json`, `config/models.lock.json`, `config/embedding-comparison.lock.json`, `uv.lock`, `apps/web/pnpm-lock.yaml` ni dans les manifestes de `.runtime/manifests/` ; chaque entrée de `artifacts.lock.json` porte une empreinte ou une révision ; `models.lock.json` fixe l'empreinte du manifeste et des couches de `qwen3.5:4b` et `qwen3.5:4b-text` ; `uv.lock` : 127 paquets, aucun paquet de registre sans empreinte SHA-256 ; `pnpm-lock.yaml` : 126 résolutions avec intégrité sha512. Le contrôle `doctor` (`model_lock`) vérifie hors ligne la conformité du stockage au verrou.

Preuve01/10/2026 (D01.20) : `doctor` distingue modèle absent (`model_lock` à `absent`, rubrique `modèle` rouge) et fichiers altérés, service arrêté ou muet (`llm_model_diagnosis` : `service_unavailable_model_files_present`), configuration non appliquée (`profile_application` à `restart_required`), usage GPU (`loaded_models[].size_vram`, et `up` refuse un profil où `llm.num_gpu` n'est pas nul) et stockage incohérent (`index_consistency` : points Qdrant et fragments SQLite par génération active, depuis `e4c7caf`) ; tests `test_runtime_doctor.py`, `test_runtime_verdict.py` (pannes provoquées) et essai d'intégration HTTP ; relevé réel du 01/10 à 06:02 : 5 générations actives, 322 fragments, cohérent, verdict vert.

Preuve (D01.21) : un second `up` rend l'instance existante sans en lancer une autre ([30/09](reports/runtime-first-duplicate-up.json)) ; le 01/10, cinq cycles `down` puis `up` de l'instance principale (04:29, 05:04, 05:11, 05:25, 06:02, chacun après contrôle d'absence de question et de traitement actifs) ont laissé ses données intactes : mêmes comptes de traitements avant et après (61 en pause, 12 partiels, 4 prêts, 1 en erreur), `readiness` 200, index cohérent après le dernier ([journal](journal/2026-10-01.md)).

## D02 — Import, bibliothèque et extraction

- [ ] Import d'un dossier et de sous-dossiers, noms Unicode/espaces et fichiers homonymes dans des dossiers distincts.
- [ ] Original copié sans modification ; SHA-256 vérifié ; version et chemin documentaire conservés.
- [ ] PDF FR/EN natifs, multi-colonnes, scan et mixte traités avec couverture par page visible.
- [ ] OCR absent des régions natives fiables ; régions/pages réellement OCRisées comptées et traçables.
- [ ] PDF simple traité par la voie native qualifiée ; page mixte « paragraphe natif + tableau scanné » couverte sans double texte.
- [ ] Régions non résolues visibles ; un schéma non interprété ne devient pas une preuve textuelle inventée.
- [ ] Section/table traversant les pages 4/5 conservée correctement ; fenêtres de checkpoint non utilisées comme frontières sémantiques.
- [ ] PDF blanc, corrompu, chiffré et trop volumineux produisent un état explicite, pas un succès silencieux.
- [ ] Extraction partielle signalée dans bibliothèque, résultats et réponses ; les pages manquantes ne sont pas déclarées lues.
- [ ] Table et unités du corpus contrôlé restent interprétables ; aucun texte de colonne mélangé non signalé.

**Preuves :** inventaire de fixtures, hashes, JSON d'extraction, compteurs de couverture et contrôles visuels sur les cas difficiles.

## D03 — Indexation et cohérence

- [ ] Un réimport identique n'ajoute pas de version inutile ni de calcul d'embedding redondant.
- [ ] Le déplacement d'un PDF dans l'arborescence ne recalcule pas ses embeddings.
- [ ] Une nouvelle version reste invisible en recherche jusqu'à publication de sa génération complète.
- [ ] Un retrait est immédiatement exclu des scopes ; les deux index actifs sont nettoyés/réconciliés.
- [ ] Arrêt forcé pendant parsing, embedding, upsert et publication : reprise sans doubles chunks ni génération fantôme.
- [ ] Une panne Qdrant au milieu d'un import ne fait pas apparaître le document comme complètement prêt.
- [ ] Les anciennes citations ouvrent l’ancienne version et révision d’extraction ; une purge indique source supprimée sans substitution.
- [ ] Changer le seul embedding ne refait pas l’OCR ; modèles de même dimension dans des collections distinctes ; aucun mélange query/documents de modèles différents.
- [ ] Les générations épinglées par une requête en cours ne sont pas nettoyées prématurément ; retrait explicite réévalué avant fourniture de nouveau contexte.

**Preuves :** compteurs avant/après, scénarios de fault injection, journal des transitions et recherche sur versions différentes.

## D04 — Recherche et périmètre

- [x] Recherche lexicale et dense réelles, sans LLM requis pour voir les résultats.
- [ ] Filtres dossier récursif, documents, section et pages appliqués avant top-k et avant assemblage de contexte.
- [ ] Aucun passage hors scope : **zéro fuite** dans le jeu de tests de périmètre, y compris expansion parent/historique.
- [ ] Requêtes avec identifiants proches correctement distinguées ; aucune suppression excessive de ponctuation.
- [ ] Ranking BM25 dans le bon sens ; fusion RRF testée sur exemples déterministes ; absence de doublons dominants.
- [ ] Le cas adverse RRF ne fait pas disparaître la preuve d’un identifiant explicitement ciblé : contrôle après déduplication, expansion et coupe finale.
- [ ] Une occurrence exacte sans information pertinente ne permet pas une réponse fabriquée ; identifiants/documents non couverts affichés.
- [ ] L'analyse d'une sélection courte ne déclenche pas de recherche globale.

**Objectif qualité :** Recall@10 >= 0,90 sur questions répondables du jeu de test tenu à l'écart du réglage, avec référence à une preuve précise et pas seulement au bon document. Rapporter aussi Recall@5, MRR et résultats par catégorie ; ne pas masquer un échec important derrière une moyenne globale.

Preuve partielle acquise30/09/2026 : [publication réelle11chunks/11points](reports/backend/2026-09-30-first-publication-readonly.json) et [recherche navigateur sans modèle](../apps/web/reports/QUALIFICATION_UI_NATIVE_2026-09-30.md). Les scopes et métriques finales de D04 restent ouverts.

**Contexte final :** `EvidenceCoverage@Context >= 0,90` sur les unités de preuve annotées des questions répondables. Rapporter aussi la proportion de questions dont toutes les preuves nécessaires sont présentes. Mesurer après toutes les transformations ; un succès top-10 n’est pas automatiquement un succès de contexte. Définitions et dénominateurs dans `QUALIFICATION.md`.

## D05 — Réponses et citations

- [ ] Appel au vrai modèle Ollama local ; aucune réponse de recette codée en dur.
- [ ] Une seule génération par question nominale ; aucun appel supplémentaire caché de rewriting/reranking/jugement.
- [ ] Relance courte résolue depuis un référent autorisé ; ambiguïté signalée sans recherche globale hasardeuse. Changement de scope testé ; ancienne réponse du LLM jamais utilisée comme preuve.
- [ ] Contexte complet compté avec le bon tokenizer/template ; pas de troncature silencieuse.
- [ ] **100 % des IDs de citation affichés comme valides** existent dans le registre autorisé de la question.
- [ ] **100 % des citations de la recette** désignent la bonne version et la bonne page physique.
- [ ] Les localisations `span/block/table/page` sont honnêtes et visibles ; aucune géométrie fabriquée.
- [ ] Inconnus, contradictions et insuffisances des sources sont signalés ; une absence de résultat n'est pas affirmée comme absence documentaire.
- [ ] Au moins **95 % des assertions documentaires vérifiées** sont soutenues par les preuves citées sur le jeu tenu à l'écart.
- [ ] Au moins **90 % des questions sans réponse** du jeu tenu à l’écart conduisent à une abstention appropriée.
- [ ] Exactitude de la réponse utile >= **85 %** des questions répondables du test final, selon grille de réponse annotée ; une abstention compte comme non-réussite sur une question répondable. Rapporter séparément erreurs de valeur/unité, réponse partielle et abstention injustifiée.

**Mesure :** vérifier manuellement les réponses, assertions et citations de toutes les questions du test final de qualification, avec dénominateur explicite par métrique. Les fixtures factuelles contrôlées permettent aussi des tests déterministes. Un auto-jugement du même petit LLM n'est pas la seule preuve d'exactitude. Conserver les dénominateurs et la grille d'annotation.

## D06 — UX réellement intégrée

- [x] Trois panneaux utilisables à 1 366 × 768 et 1 920 × 1 080, sans chevauchement bloquant.
- [ ] Arborescence, lecteur et chat partagent le bon état ; périmètre toujours visible.
- [x] Le clic sur une citation navigue vers la version/page, surligne et permet de revenir au point précédent.
- [x] Zoom, rotation 0/90/180/270°, CropBox non trivial et labels de pages romains ne cassent pas la navigation.
- [ ] Au moins 95 % des ancres de région du corpus contrôlé couvrent effectivement le passage attendu ; 100 % ouvrent la bonne page. Les cas `page` ne sont pas comptés comme surlignages de région réussis.
- [ ] Sélection native et OCR lorsque géométrie disponible ; actions page/section fonctionnelles.
- [ ] Aller-retour des offsets UTF-16/points de code, ligatures, césures, caractères hors BMP et accents combinants ; hash source vérifié ; fallback de granularité explicite.
- [x] Nombre de canvases ET budget cumulé de pixels respectés pendant zoom/scroll ; allocations obsolètes libérées.
- [ ] Réponse progressive, statut d'indexation, annulation et reconnexion SSE observables.
- [ ] Aucun bouton factice et aucun écran dépendant de données mockées dans le build de livraison.
- [x] Navigation clavier, focus visible, labels accessibles et contraste vérifiés sur les composants essentiels.

**Preuves :** Playwright utilisant l'API réelle, traces et captures annotées par nom de scénario. Un test avec Qdrant/Ollama mockés reste un test UI isolé et n'est pas compté comme E2E réel.

Disposition aux deux résolutions vérifiée contre l'API native : [rapport et captures](../apps/web/reports/QUALIFICATION_UI_NATIVE_2026-09-30.md). Ce résultat ne clôt pas navigation de toutes géométries, réponse progressive ou anciennes révisions.

Preuves01/10/2026, Playwright sur l'API réelle (Qdrant et Ollama réels) : clic sur une citation, page et surlignage ([question réelle, instance principale](../apps/web/reports/e2e-2026-10-01-r2-generation-0446/evidence.json)) et retour au passage précédent ([import réel et navigation, instance isolée](../apps/web/reports/e2e-2026-10-01-import-isole-parcours-evidence.json)) ; rotations 0/90/180/270 avec CropBox et folios romains ([géométrie, 4/4](../apps/web/reports/e2e-2026-10-01-import-isole-geometrie-evidence.json)) ; zoom à 300 % dans le budget de canvases et de pixels, canvases détachés libérés (même rapport que l'import) ; clavier, focus visible, libellés et contrastes ([E2E lecture seule](../apps/web/reports/e2e-2026-10-01-reponse-mise-en-forme-0457-evidence.json), tests unitaires `accessibility.test.ts` et `ui-guards.test.ts`, [recette](reports/ui-recette-2026-09-30.md#second-passage--1er-octobre-2026)). Traces Playwright conservées localement sous `apps/web/test-results/`, hors Git. Restent ouverts : état partagé (90), ancres de région (93), sélection OCR (94), offsets (95), annulation et reconnexion SSE (97), absence de bouton factice (98).

## D07 — RAM, CPU et latence

Recette sur un hôte **16 Go physiques maximum**, CPU uniquement, sans utilisation GPU. Déclarer CPU, cœurs, OS, navigateur, stockage, RAM visible, swap, versions et empreintes. Inclure les mesures hôte Windows, navigateur et tous les services ; ne pas compter uniquement la mémoire Python.

- [ ] Une seule génération active, un seul worker lourd, et aucune concurrence parsing/OCR lourd avec génération.
- [ ] Pas d'OOM, pas de fuite mémoire progressive, pas de swap soutenu nécessaire au fonctionnement nominal.
- [ ] Mémoire cible application <= **10 Gio** de résidence non dupliquée ; mémoire hôte disponible >= **1,5 Gio**. Préciser working set et private bytes Windows, sans addition trompeuse de pages partagées.
- [ ] Admission et pause coopérative fonctionnent ; pas de kill nominal après cinq secondes. Un job interrompu reprend au dernier checkpoint durable.
- [ ] Alternance chat/import : attente visible, reprise explicite fonctionnelle et absence de rechargement périodique sans action. Mesurer initialisations, travail utile et unités rejouées.
- [ ] Reprise automatique désactivée dans le profil livré, ou activée uniquement avec politique documentée et essai anti-ping-pong concluant.
- [ ] Avec au moins 25 000 chunks et modèle chaud : recherche hybride p95 <= **3 s** ; premier token p95 <= **45 s** pour environ 3 000 tokens d'entrée ; réponse de 400 tokens p95 <= **180 s**.
- [ ] Mesurer aussi démarrages à froid et indexation pages/minute ; séparer modèle chaud et préfixe réutilisé en cache, ainsi que chargement/prompt/génération.
- [ ] Le scénario 400 tokens autorise une sortie >400 ; une sortie plus courte naturelle n’est pas imputée comme temps pour 400 tokens. Rapporter les longueurs observées.
- [ ] Au moins 30 questions de performance et un scénario d'usage de 30 minutes : navigation, recherches, questions, import et reprise.

Si la cible CPU ne passe pas une mesure, conserver `FAIL`, identifier la phase dominante et tester une optimisation ciblée. Ne pas augmenter RAM/GPU, raccourcir secrètement les réponses ou remplacer le modèle sans nouvelle mesure déclarée. Les seuils ne sont pas garantis par ce dossier : leur atteinte est précisément l'objet de la qualification.

## D08 — Hors ligne et sécurité

- [ ] Après provisionnement, bloquer toutes les sorties non-loopback et exécuter import, OCR, embeddings, recherche, génération et lecture.
- [ ] Zéro requête externe nécessaire et aucune tentative inexpliquée de DNS/télémétrie/CDN/modèle manquant dans le scénario applicatif.
- [ ] Origines/Host non autorisés rejetés ; pas de bind LAN involontaire ; pas de CORS wildcard.
- [ ] Traversal, symlink sortant de la racine et fichiers malformés traités sans lecture arbitraire ou crash du serveur API.
- [ ] Instructions malveillantes insérées dans une fixture PDF ne provoquent ni exécution, ni exfiltration, ni élargissement du scope.
- [x] Markdown/HTML actif et liens d'images distantes ne sont pas exécutés/chargés automatiquement.
- [ ] Logs normaux sans texte privé ; originaux et modèles exclus du Git par défaut.

Preuve01/10/2026 (D08.131) : texte de document hostile rendu littéral, sans élément actif ni requête distante ni changement de périmètre (Playwright sur instance isolée, [rapport](../apps/web/reports/e2e-2026-10-01-import-isole-parcours-evidence.json)) ; côté serveur, balises retirées et images Markdown remplacées avant affichage (`validate_answer`, `services/api/context.py`, testé avec `<script>` et une image distante dans `tests/unit/test_retrieval.py`) ; côté interface, réponse rendue en éléments React sans interprétation de balise (`apps/web/src/lib/answer-format.ts`, `tests/unit/answer-format.test.ts`). Instruction hostile dans une fixture (D08.130) : sans effet sur la réponse ([rapport](reports/injection-2026-10-01-0441.json)), exfiltration et élargissement du périmètre non mesurés : critère laissé ouvert.

## D09 — Sauvegarde, restauration et maintien

- [x] Snapshot cohérent de SQLite, Qdrant, originaux, extractions et manifests.
- [x] Restauration dans un autre dossier avec vérification de hashes et comptes.
- [x] Une question et une ancienne citation fonctionnent après restauration.
- [x] Une migration de schéma/pipeline produit une nouvelle génération contrôlée ; retour arrière documenté.
- [ ] Registre des licences/avis de redistribution de tous les artefacts réellement livrés.

Preuves30/09/2026 : [backup peuplé21fichiers](reports/backup-first-published.json), [restore Unicode longue avec stockage Qdrant court](reports/restore-first-published-long-root-short-store-rerun.json). Dix fichiers copiés sont hashés avant rebasing ; SQLite intègre/comptes conservés et11points restaurés. Requête/ancienne citation applicatives encore NOT_RUN, provenance Tesseract limitée ; D09 global reste ouvert. Preuve01/10/2026 (D09.4) : [migration d'une sauvegarde au schéma2](reports/migration-2026-10-01-0414.json) par le code courant (schéma3), 8 anciennes citations ouvertes avant et après réindexation, révision d'extraction conservée, nouvelle génération active ; retour arrière dans [SAUVEGARDE-RESTAURATION.md §6](../docs/exploitation/SAUVEGARDE-RESTAURATION.md#6-retour-arrière-et-relocalisation). Preuve01/10/2026 (D09.3) : [question et ancienne citation après restauration](reports/restore-question-2026-10-01-0525.json) d'une sauvegarde au format courant : citation relue à l'identique, nouvelle question terminée avec citation.

## Jeu d'évaluation minimal

Préparer au moins 16 PDF synthétiques identifiés couvrant texte FR/EN, colonnes, tableaux, scan, mixte, rotations/recadrage, labels, versions et cas d'erreur ; ajouter des fixtures hostiles séparées. Leur contenu est contrôlé et leur statut synthétique visible.

Le jeu initial de 80 questions peut servir au développement. Pour la qualification de cette V2.1, préparer **200 questions** : 70 factuelles FR/EN, 30 identifiants, 24 tableaux/unités, 20 comparaisons, 16 suivis conversationnels et 40 sans réponse. Séparer **100 développement / 100 test final**, à parts égales par catégorie, par familles de documents lorsque possible. Les exemples déjà utilisés pour régler ou déboguer restent côté développement.

Le test final comporte donc 80 questions répondables et 20 sans réponse. Rapporter les effectifs, les taux observés et une incertitude adaptée ; 200 questions n'est pas une garantie statistique universelle. Un effectif insuffisant n'autorise pas à annoncer une qualification équivalente. Annotations : réponse attendue/absence, version, révision d'extraction, pages, unités de preuve requises et alternatives admises.

Une duplication massive d'un même texte pour atteindre 25 000 chunks ne suffit pas à prouver la qualité ; elle peut servir à un stress technique explicitement nommé. Le benchmark métier doit utiliser des questions et documents réellement représentatifs, autorisés.

## D10 — Décisions et cohérence de livraison

- [ ] Les trois contrôles précoces ont des preuves ou des blocages explicites ; l’environnement de développement n’est pas présenté comme la machine cible.
- [ ] Embedding choisi : essai ciblé et décision enregistrés, ou candidat officiellement non vérifiable/incompatible documenté et E5 qualifié sans prétendre avoir gagné un A/B.
- [ ] Placement mémoire Qdrant et paramètres effectifs relus après création ; dépréciations traitées à la version installée.
- [ ] Sources canoniques, configuration et brief complet synchronisés ; contrôles documentaires rejouables.
- [ ] Les seuls résultats annoncés correspondent à des exécutions effectives ; résultats documentaires et applicatifs restent séparés.

## D11 — Sources officielles, skills et mises à jour

- [ ] Chaque décision technique significative possède une source officielle pertinente, une date de consultation et une version/portée explicites ; aucun résultat de recherche non ouvert n'est présenté comme vérifié.
- [ ] Documentation actuelle et contrat de la version installée sont distingués ; toute mise à jour traite changements incompatibles, dépréciations, sécurité, retour arrière et tests de non-régression.
- [ ] Une affirmation de supériorité/SOTA indique protocole et limites ; une mesure éditeur n'est pas présentée comme une mesure sur la machine cible.
- [ ] Skills effectivement utilisés identifiés par nom, chemin, origine et version/hash constaté ; leurs `SKILL.md` ont été lus et leur pertinence vérifiée. Les skills manquants ne sont pas présentés comme exécutés.
- [ ] Skills projet : front matter/liens validés ; sélection et comportement vérifiés dans l'outil réel sur tâche positive et tâche hors périmètre, ou statut non testé explicite. Validation syntaxique différente de validation comportementale.
- [ ] Aucune installation massive ou exécution de script de skill tiers sans contrôle de provenance, de permissions et de dépendances ; aucun skill de développement exposé au LLM documentaire.
- [ ] Source inaccessible gérée sans invention : décision dépendante bloquée, baseline préservée, travail indépendant poursuivi ; aucune donnée privée envoyée lors des recherches.
- [ ] `SOURCES.md`, `DECISIONS.md`, `PLAN.md`, spécifications, configs, tests et brief synchronisés après les changements qui les concernent ; pas de correctif seulement décrit dans un audit séparé.

**Preuves :** registre de décision/source, diff des fichiers, références des skills lus/utilisés, résultats des tests de contrat/migration/skills et limites explicites. Ces critères concernent le travail des agents, pas des fonctionnalités réseau du produit.

## Rapport final exigé

Pour chaque D01–D11 : statut, commande, commit, configuration, environnement, corpus, résultat et chemin de preuve. Ajouter un tableau des métriques avec dénominateurs, mesures chaud/froid, limitations et écarts. Résumer uniquement ce qui est réellement exécuté ; ne pas substituer un discours de conformité aux résultats.

**Terminé = application exploitable + preuve bout en bout + qualification sur la cible déclarée + défauts/limites résiduels explicités.**
