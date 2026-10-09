# Qualification ciblée — RAG-LOCAL-16 V2.1

**Rôle :** protocole de qualification, prérequis et limites de preuve · **Propriétaire :** qualification du produit · **Statut :** Vivant · **Référence :** V2.1, décisions W001/W018/W024/W025 et base publiée `05da85c` ; correction documentaire du contrôle de chemin Linux le 2026-10-03 · **Mis à jour :** 2026-10-09 17:19 (UTC) · **Source de vérité :** ce document pour la méthode ; [DoD](DEFINITION_OF_DONE.md) pour les critères et [journal](journal/README.md) pour les exécutions

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md). **W018 (01/10/2026) : Linux natif (aarch64 et x86-64) devient une seconde plateforme**, toute machine Windows restant prise en charge comme avant ; réalisation en cours (lots J du [plan](PLAN.md)). **W024 et W025 (01/10/2026) : le CPU reste le socle, le repli et la référence de la recette D07 ; seule la génération par Ollama peut passer sur GPU, automatiquement sur les voies qualifiées par un essai réel** ([W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024)). Les mesures D07 se font en calcul CPU imposé (section 8).

## 1. Objet et limites

Qualifier les choix qui conditionnent la réussite réelle sur le poste cible, sans retarder tous les chantiers par une étude exhaustive. Les essais précoces utilisent quelques fixtures discriminantes ; ils ne remplacent pas la recette finale. Aucun benchmark de l'application ou du PC utilisateur n'a été exécuté lors de la préparation de ce dossier.

Trois vérifications sont indépendantes : Q-CPU (LLM et machine), Q-PDF (extraction/provenance) et Q-SEARCH (recherche/contraintes). Les agents peuvent préparer ces travaux en parallèle ; leurs exécutions lourdes sur une même machine sont ordonnancées sous un budget commun.

## 2. Q-CPU — réalité matérielle avant optimisation

Enregistrer CPU, cœurs physiques/logiques, instructions disponibles, OS, RAM physique/utilisable, SSD, swap, navigateur, runtime et digest du modèle. Mesurer l’hôte Windows natif et les processus du projet. Un container limité à 10 Gio sur un gros serveur ne remplace pas une qualification du PC de 16 Go.

Exécuter d'abord un smoke avec le vrai modèle Q4_K_M, CPU uniquement (`num_gpu: 0` dans la requête du smoke ; profil `llm.accelerator: cpu` pour toute mesure par l'application, section 8), non-thinking. Mesurer ensuite des entrées distinctes autour de 1 500, 3 000 et 5 000 tokens réels avec une sortie autorisée à 768. Ce sont trois points diagnostiques, pas une grille de tuning. Capturer temps de chargement, attente, prompt, génération, durée totale, tokens réels et mémoire globale.

Distinguer :

| Condition | Définition |
|---|---|
| Runtime froid | Modèle déchargé avant demande ; état du cache disque déclaré |
| Modèle chaud, contenu nouveau | Poids chargés, preuves/questions distinctes ; cache réutilisé mesuré quand disponible |
| Préfixe/contexte déjà en cache | Réutilisation connue ; ne pas la confondre avec un prompt entièrement retraité |

La disponibilité de `prompt_eval_cached_count` dépend du runtime : une métrique absente est `unknown`, pas zéro. Les durées Ollama sont converties avec l'unité documentée, et rapprochées des temps mesurés côté application. Ne pas soustraire un nombre de tokens en cache d'une métrique dont la sémantique n'est pas vérifiée.

La cible TTFT <=45 s pour environ 3 000 tokens implique, en l'absence de cache et en négligeant les autres coûts, environ 66,7 tokens d'entrée/s. Ce calcul sert à diagnostiquer, pas à prédire la machine. Si les seuils échouent, isoler la phase dominante avant de changer un seul réglage. Garder les résultats d'échec.

## 3. Q-PDF — extraction et provenance

Utiliser au minimum six cas précoces : texte natif simple, deux colonnes, table avec unités, scan FR/EN, page mixte natif + table scannée, section/table traversant une fenêtre. Ajouter dès l'intégration les rotations/CropBox, labels romains, pages blanches, textes corrompus, ligatures/césures et PDF invalides.

Comparer le contenu source visible à l'extraction. Pour chaque route, enregistrer raison de routage, champs effectivement extraits, régions OCR, zones non résolues, ordre, unités, provenance et temps/mémoire. Une extraction qui retourne du texte sans les valeurs importantes n'est pas un succès documentaire complet.

Le chemin natif n'est accepté que sur les cas dont l'ordre et la couverture sont établis ; sinon escalade ciblée vers structuré/OCR. Une ambiguïté persistante produit un avertissement. Pas de boucles de parsing de variantes au hasard ; conserver le résultat valide et son hash.

Vérifier à la frontière des pages 4/5 que les unités de checkpoint ne modifient pas arbitrairement la structure. Les tables multi-pages ne sont fusionnées qu'avec une relation de continuation tracée. Les différents chemins doivent aboutir au même espace de coordonnées canonique.

## 4. Q-SEARCH — preuve finale, pas seulement un bon top-k

Construire des fixtures contrôlées avec références proches, mêmes valeurs dans des documents différents, unités contradictoires et passage exact peu proche sémantiquement. Tester les scopes bibliothèque/dossier/document/page/sélection et les expansions de parent.

Contre-exemple RRF obligatoire : la seule occurrence exacte arrive première en lexical, absente du dense ; six voisins bien classés dans les deux branches la chassent du top final sans contrainte. Le produit corrigé doit conserver une preuve pertinente de l'identifiant ou signaler précisément pourquoi elle ne répond pas à la demande. Une occurrence arbitraire n'est pas une preuve de réponse.

Tracer candidats → fusion → contraintes → déduplication → expansions → contexte final. Le test après coupe de tokens est distinct de celui après fusion. Mesurer les références effectivement transmises, pas les références affichées comme disponibles avant génération.

## 5. Un seul A/B d'embedding, conditionné à sa faisabilité

**Baseline :** `intfloat/multilingual-e5-small`, ONNX CPU INT8, contrat E5 vérifié.
**Candidat issu de l'audit :** `ibm-granite/granite-embedding-97m-multilingual-r2`.

Précondition : récupérer une source officielle, vérifier identité/révision/licence, tokenizer, format query/document, pooling, dimensions et possibilité d'un artefact CPU reproductible. Les pages du candidat n'ont pas pu être reconfirmées pendant cette révision. Cette limite ne prouve pas son inexistence ; elle interdit seulement d'en annoncer ici les performances comme vérifiées.

Si la précondition échoue, statut `CANDIDATE_UNAVAILABLE` ou `CANDIDATE_INCOMPATIBLE`, avec le motif précis ; E5 continue. Ne pas étendre automatiquement à dix autres modèles. L'application peut être qualifiée avec E5 si sa propre recette passe ; elle ne prétend pas avoir remporté un comparatif absent.

Si elle passe, comparer les mêmes textes extraits et unités de preuve dans deux collections séparées. Réutiliser le parsing. Vérifier que chaque fragment respecte la limite du modèle ; une différence de fragmentation est déclarée et évaluée séparément. Ne pas charger les deux modèles en parallèle pendant les mesures de RAM/latence.

Comparer Recall@10, EvidenceCoverage@Context, résultats par langue/catégorie, p50/p95 query-embedding, débit d'indexation, mémoire résidente et stockage réel. Consigner les effets de quantification. Une dimension égale ne rend pas les espaces compatibles.

Règle d'arbitrage : si E5 satisfait la recette et que le candidat n'apporte pas de gain robuste ou de réduction utile de coût, garder E5. Un gain de score agrégé qui dégrade les identifiants, les tableaux ou la latence nécessaire n'est pas suffisant. Si un candidat corrige un défaut ciblé sans régression critique et respecte le budget, le retenir via une décision documentée, puis verrouiller l'identité. Ne pas retoucher le jeu final pour favoriser le choix.

## 6. Dataset de qualification V2.1

Les premières fixtures valident l'ingénierie ; ajouter un corpus métier autorisé avant de déclarer la qualité métier. Sans corpus privé disponible, ce volet est `BLOCKED — corpus métier absent`, sans invalider les tests techniques déjà réalisés.

| Catégorie principale | Développement | Test final | Total |
|---|---:|---:|---:|
| Factuel FR/EN | 35 | 35 | 70 |
| Identifiants techniques | 15 | 15 | 30 |
| Tableaux/unités | 12 | 12 | 24 |
| Comparaisons | 10 | 10 | 20 |
| Suivis conversationnels répondables | 8 | 8 | 16 |
| Questions sans réponse dans le scope | 20 | 20 | 40 |
| **Total** | **100** | **100** | **200** |

Chaque question a une catégorie principale et éventuellement des tags secondaires. Séparer par document ou famille lorsque possible ; ne pas répartir des paraphrases presque identiques des deux côtés. Les anciennes questions déjà utilisées pour diagnostiquer ne restent pas dans le test aveugle. Les scénarios d'ambiguïté et de sécurité supplémentaires sont des tests de contrat, distincts de cette répartition.

Une annotation contient question, scope, versions/révisions, réponse attendue ou absence, unités de preuve requises et alternatives admises, valeurs/unités importantes et critères de complétude. Une unité peut demander plusieurs spans ; chaque span doit être présent dans le contexte ou une alternative annotée valide doit le remplacer. Ne pas compter le seul bon nom de document comme preuve retrouvée.

## 7. Métriques et dénominateurs

**Recall@k des preuves :** nombre d'unités de preuve requises couvertes par les k candidats, divisé par le nombre d'unités requises des questions répondables. Rapporter moyenne par question et agrégat, en précisant lequel est comparé au seuil ; la recette retient l'agrégat et expose toutes les catégories.

**EvidenceCoverage@Context :** même couverture, mais dans les extraits réellement envoyés après scope, RRF, contraintes, déduplication, expansion et coupe. Une unité trouvée puis éliminée est un échec de contexte. Seuil observé initial >=0,90.

**AllRequiredEvidence@Context :** fraction des questions répondables dont toutes les unités nécessaires sont présentes. Rapporter cette métrique sans lui inventer un seuil déjà approuvé ; elle révèle les échecs multi-preuves masqués par une moyenne.

**Exactitude de réponse :** questions répondables correctement résolues / toutes les questions répondables (80 dans le test final). Une abstention sur question répondable compte comme échec ; seuil observé >=0,85. Les réponses partiellement correctes sont rapportées séparément, sans être transformées en réussite complète.

**Soutien des assertions :** assertions documentaires effectivement justifiées par les preuves citées / assertions documentaires évaluées, >=0,95 observé. Ce taux ne suffit pas si le modèle s'abstient partout ; le critère d'exactitude ci-dessus le complète.

**Abstention :** abstentions appropriées / questions réellement sans réponse dans le scope, >=0,90 observé (au moins 18/20 dans le test final). Ajouter les faux refus sur les 80 questions répondables. Ne pas assimiler « non trouvé par le retrieval » à « annoté sans réponse ».

**Citations :** intégrité d'ID, version/page et localisation, séparément. Les dénominateurs de région n'incluent pas les citations dont seule la page est disponible.

Calculer un intervalle de Wilson à 95 % pour les taux binaires par question ; pour des unités ou assertions corrélées au sein d'une question, préférer un bootstrap par question ou famille documentée. Publier la méthode et la graine. Un 90 % observé sur 30 essais n'est pas une garantie à 90 % sur le corpus futur. Ne pas multiplier les passages d'une même réponse pour simuler des observations indépendantes.

## 8. Performance et ressources

Premiers essais diagnostiques : quelques requêtes distinctes. Recette : au moins 30 requêtes de performance avec corpus >=25 000 chunks, puis usage mixte de 30 minutes incluant import, scroll, zoom, questions, pause et reprise. Les tests statistiques de qualité utilisent le dataset distinct décrit plus haut.

Publier p50/p95, méthode de quantile, nombre d'échantillons, configuration, longueurs réelles et cache. Pour le scénario « 400 tokens », n'imputer un temps pour 400 tokens qu'à une génération les atteignant ; sinon rapporter la longueur réellement produite et le débit, sans fabriquer le temps manquant. Séparer temps au premier token de la génération seule et temps utilisateur incluant attente/retrieval.

Sous Linux, PSS lorsque disponible ; conserver mémoire globale hôte et swap. Sous Windows natif, expliquer la méthode non dupliquée retenue. Suivre le navigateur, les modèles, l'API, Qdrant, le parseur, les caches et les allocations raster. Ne pas conclure à partir de la seule taille des fichiers modèles ou des vecteurs.

Le scénario chat/import mesure chargements par transition, travail non validé rejoué, délai de checkpoint et progression après reprise explicite. Il vérifie absence de boucle de rechargement ; il n'exige pas une ingestion infiniment prioritaire pendant un chat continu. La reprise automatique n'est activée qu'après cette qualification.

Mesures D07 en calcul CPU imposé (W024, W025) : démarrer l'instance mesurée avec un profil `llm.accelerator: cpu` ; la forme antérieure `llm.num_gpu: 0` impose aussi le CPU, le profil livré en `auto` ne convient pas. Lancer la série avec `tools/qualification/perf.py`, qui relit `llm_accelerator` dans `/diagnostics` au début et à la fin de la série. Un rapport ne peut servir de preuve D07 que s'il porte `d07_eligible: true`, les autres conditions de la recette restant à remplir ; un rapport `d07_eligible: false` est invalide pour la recette et `d07_ineligible_reason` en donne le motif. Les mesures sur GPU, dont le pilote `python -m services.runtime.calibration --accelerator auto`, sont rapportées à part et ne cochent aucun critère D07.

## 9. Rapport et décisions

Pour chaque essai : objectif, hypothèse, données, commit, versions, machine, commande, résultats bruts, interprétation et décision. Statuts `NOT_RUN`, `PASS`, `FAIL`, `BLOCKED`. Ne pas affirmer qu'un modèle est SOTA parce qu'il est récent, ni qu'une dépendance est compatible parce qu'elle est installable.

Garder un tableau des critères DoD avec leur preuve. Les résultats de `tools/verify_pack.py` restent dans la catégorie **contrôles documentaires/de référence**, jamais parmi les essais applicatifs Q-CPU/Q-PDF/Q-SEARCH.

## 10. Qualification sous Linux

Procédure employée le 2 octobre 2026 pour la qualification Linux (lot J8 du [plan](PLAN.md)) sur le poste Linux aarch64 du chantier : Jetson AGX Orin, Jetson Linux R35.4.1, Ubuntu 20.04.6, glibc 2.31. Les critères et les seuils sont ceux de la DoD, sans adaptation. Le statut et la preuve de chaque critère sont dans le tableau « Qualification Linux » de [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md#qualification-linux-w018) ; le déroulé, les échecs et les rejeux sont dans le [journal du 2 octobre](journal/2026-10-02.md). Cette section ne décrit que les conditions d'exécution propres à Linux et ne reprend aucun résultat. Linux x86-64 n'a pas été qualifié.

### 10.1 Conditions communes

- Chaque commande part de la racine du projet avec `LD_LIBRARY_PATH` retiré et `PYTHONUTF8=1`, comme `rag.sh` le fait pour Python, y compris pour les outils lancés directement par `.venv/bin/python`.
- Un seul traitement lourd à la fois (génération, extraction, build, essais d'intégration), avec la mémoire et le disque relevés avant et après chaque lot.
- L'instance principale du chantier n'est jamais la cible d'un essai : les outils démarrent leurs propres instances (`selftest`, [`e2e_instance.py`](../tools/qualification/e2e_instance.py), `injection_check.py`, `restore_question_check.py`) et les comptes de l'instance principale sont relevés en lecture avant et après.
- Les preuves complètes restent hors Git, sous `.runtime/qa/j8-linux/` ; seuls des résumés sans texte de document sont versionnés.

### 10.2 Dossier temporaire court, sur un autre volume

`TMPDIR` désigne un dossier court de la carte microSD du poste : `/media/safae/devsave1/j8-tmp` pendant les lots L3 à L10 (valeur relevée dans `l10/tools/l10_run.sh` et dans `l4/vec-procs-after-start.json`, sous `.runtime/qa/j8-linux/`), puis `/media/safae/devsave1/tmp` à partir des rejeux. Deux raisons distinctes :

- **Volume.** Les racines des instances de contrôle (`apst…`, `ape…`, `apr…`), les dossiers temporaires de pytest et les profils temporaires du navigateur lancé par Playwright s'écrivent dans le dossier temporaire. La partition système du poste étant presque pleine, l'utilisateur a demandé le 2 octobre que les fichiers temporaires et les artefacts lourds aillent sur la carte microSD ([journal](journal/2026-10-02.md), entrées de 07:47 et 09:20). Le cache des navigateurs de Playwright (`~/.cache/ms-playwright`) ne dépend pas de `TMPDIR` : il a été déplacé sur la carte par un lien symbolique, à la même demande. Ce sont des aménagements de ce poste, pas des étapes du produit.
- **Longueur historique et contrôle actuel.** `short_root` ([selftest.py](../services/runtime/selftest.py)) crée chaque racine sous la forme `<dossier temporaire>/apst<4 caractères hexadécimaux>`. Le test de contrôle appliquait autrefois la borne Windows de 57 caractères sur toutes les plateformes : les premiers lots Linux ont utilisé un `TMPDIR` de 38 caractères au plus pour ce seul défaut de test. Dans le code actuel, `test_control_profile_isolates_data_and_ports_but_shares_the_host_heavy_lock` ([test_runtime_selftest.py](../tests/unit/test_runtime_selftest.py)) limite cette assertion à `sys.platform == "win32"`, comme le produit (`qdrant_path_bounded`, [profile_setup.py](../services/runtime/profile_setup.py), et [backup.py](../services/runtime/backup.py)). Cette borne n'est donc plus un prérequis Linux. Le choix d'un dossier temporaire sur la carte reste nécessaire sur ce poste pour son espace disque, pas pour une limite du binaire Linux. Code revérifié le 03/10/2026 ; suites R15-3 et leurs preuves au [journal](journal/2026-10-03.md), contrôles Python au [journal du 2 octobre](journal/2026-10-02.md).

### 10.3 Navigateur des scénarios Playwright

Playwright 1.63.0 ne prend plus en charge Ubuntu 20.04 (notes de version citées en LNX15 de [SOURCES.md](SOURCES.md)). Les scénarios exécutés pour D06 et D08.6 ont tourné dans Chrome Headless Shell, sur des instances isolées, avec la variable `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE` posée pour l'installation et pour chaque commande : elle fait retenir à Playwright les navigateurs d'une plateforme prise en charge, la sienne restant marquée comme non prise en charge officiellement. Version du navigateur, commandes et limites : [apps/web/README.md](../apps/web/README.md), section « Scénarios Playwright sous Linux aarch64 » ; provenance et empreinte : TOOL02 de [SOURCES.md](SOURCES.md). La méthode a été acceptée par l'utilisateur le 6 octobre 2026 (W040), pour les preuves bornées sur ce poste ; cette acceptation ne change pas le support éditeur ni la qualification des autres plateformes.

### 10.4 Session hors ligne

Pour la recette du kit R27, la garde de l'installateur refuse l'UID0. Le lanceur de QA conserve donc l'UID/GID réel dans un espace utilisateur dédié, crée son espace réseau, active loopback puis exécute les commandes sans capacités. La sonde préparatoire confirme UID1000, CapEff/Prm/Amb nuls, loopback disponible et réseau externe inaccessible. Ce contrôle ne remplace pas encore la recette applicative. Les observations historiques ci-dessous gardent leurs conditions propres.

Les critères D01.2, D08.1, D08.2 et l'observation de l'exfiltration pour D08.5 se jugent dans une session sans réseau, ouverte sans droits d'administration par `unshare -rn` : espace de noms utilisateur et réseau où le compte a l'identifiant 0 et où seule `lo` existe (LNX04 de [SOURCES.md](SOURCES.md)). La boucle locale y est distincte de celle de l'hôte : les services du poste n'y sont pas joignables.

- **Interface piège.** Dans l'espace de noms, une interface `dummy` (`j8out`, adresses de documentation `192.0.2.1/24` et `2001:db8:8::1/64`) porte les routes par défaut IPv4 et IPv6. Une tentative de sortie y est émise, donc observable, au lieu d'échouer aussitôt sur « Network is unreachable ». La première session (D01.2, à 02:49) n'avait que `lo` ; la session complète du lot L10 et son rejeu R4 ont ajouté l'interface piège et l'observateur.
- **Observateur réseau et DNS.** Un processus lancé dans l'espace de noms avant tout traitement écoute sur `127.0.0.53:53`, le résolveur nommé par `/etc/resolv.conf` de l'hôte, injoignable dans l'espace : il décode chaque requête DNS, l'attribue au processus émetteur et répond `SERVFAIL`, ce qui est une substitution déclarée du résolveur de l'hôte. Il capture aussi les trames émises sur l'interface piège, les refus sur `lo` (RST, ICMP) et relève toutes les 0,25 s les sockets non loopback. Il ne journalise aucun contenu applicatif.
- **Témoins positifs.** Avant le scénario, une requête DNS, des connexions TCP IPv4 et IPv6, un envoi UDP et une connexion à un port local fermé doivent être vus par l'observateur ; sans eux, l'absence d'événement ne prouverait rien.
- **Scénario.** `selftest`, `injection_check.py`, puis une instance isolée : `status`, `doctor`, scénarios Playwright d'import et de génération, lecture de documents, `doctor` final et arrêt ; l'environnement initial des processus de l'API et du worker est relevé pour la télémétrie d'ONNX Runtime (D08.2).

**Outils hors dépôt.** La mise en place de l'interface piège, l'observateur, l'enchaînement du scénario et l'analyse sont des scripts écrits pour ce lot. Ceux de la session hors ligne sont conservés avec les preuves, hors Git, sous `.runtime/qa/j8-linux/l10/tools/` et `.runtime/qa/j8-linux/rejeu-2026-10-02/r4/tools/`, sans être versionnés ni maintenus. L'outil versionné [`netwatch.py`](../tools/qualification/netwatch.py) ne les remplace pas : il relève les sockets d'un processus, sans les requêtes DNS ni les tentatives bloquées avant l'ouverture d'un socket. Rejouer cette session sur un autre poste demande de reprendre ou de réécrire ces scripts.

### 10.5 `injection_check` et relecture humaine (D08.5)

[`injection_check.py`](../tools/qualification/injection_check.py) éprouve deux branches dans une instance de contrôle : l'exécution d'une consigne hostile et l'élargissement du périmètre demandé par un PDF hostile. Les statuts, les codes de sortie, la règle de verdict et les limites de l'outil sont décrits dans le [README des outils](../tools/qualification/README.md#injection_checkpy--déroulement-statuts-règle-de-verdict-et-limites) et dans sa docstring. Propre à cette procédure : un `TO_REVIEW` n'est jamais compté comme réussi ; les phrases à relire du rapport sont classées à la main, et le verdict de D08.5 reprend ce classement manuel, consigné dans le tableau de la DoD.

La génération n'étant pas déterministe, l'outil a été lancé plusieurs fois, sur GPU avec le profil livré et sur CPU avec une copie du profil en `llm.accelerator: cpu` (`--profile`). Il n'observe pas le réseau : l'exfiltration se juge sur les passages lancés dans la session hors ligne (10.4).

### 10.6 Grille D05 jugée par l'assistant, sans expert

Les réponses du jeu DEV sont produites par `answers.py`, puis `grade.py grid` prépare la grille et `grade.py metrics` en calcule les mesures (section 7, [README des outils](../tools/qualification/README.md#génération-grille-d05-et-performance-d07)). Pendant J8, les champs manuels de la grille (verdict, assertions, soutien par citation) ont été remplis séparément par deux juges, puis arbitrés : juges et arbitre sont l'assistant, et aucun expert du domaine n'a revu leurs verdicts (tableau de la DoD, ligne D05). Les mesures obtenues sont un diagnostic du jeu de développement ; elles ne valident pas D05, qui se mesure une seule fois sur le jeu final, non exécuté sous Linux (point à trancher 12 du [plan](PLAN.md)).

### 10.7 Limites propres au poste

- D07 exige un hôte de 16 Go physiques au plus, en calcul CPU imposé (section 8) ; ce poste a 61 Gio, et sa hiérarchie cgroup v1 ne permet pas de borner la mémoire sans droits d'administration ([W018](DECISIONS.md#w018-double-plateforme--windows-11-x86-64-et-linux-aarch64-natifs), conséquences). Ses mesures de génération restent des pilotes, jamais des mesures D07.
- La qualification porte sur ce seul poste aarch64 : elle ne vaut ni pour un autre modèle de Jetson, ni pour Linux x86-64, ni pour Windows.


## Sources et skills dans chaque essai

Avant la décision ou la modification à qualifier, appliquer [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md) : source officielle actuelle, contrat de la version installée, hypothèse et critère. Le rapport d'essai relie source, artefact, skill utilisé et preuve ; une recommandation éditeur n'est pas substituée à la mesure locale.

Pour chaque skill retenu, vérifier une tâche pertinente et une tâche hors périmètre dans le client réellement utilisé ; son installation et son invocation ne sont pas déduites du seul fichier. Sources inaccessibles, outils absents et essais non exécutés restent visibles. D11 de la DoD complète les mesures techniques sans ajouter de calls LLM cachés au produit.
