# Qualification ciblée — RAG-LOCAL-16 V2.1

**Cible active W001 (30/09/2026 UTC) : Windows 11 x86-64 natif, sans WSL ni Docker.** Cette décision utilisateur remplace la cible système du pack source V2.1 ; les autres exigences V2.1 restent applicables. Voir [DECISIONS.md](DECISIONS.md) et [EXPLOITATION_WINDOWS.md](EXPLOITATION_WINDOWS.md). **W018 (01/10/2026) : Linux natif (aarch64 et x86-64) devient une seconde plateforme**, toute machine Windows restant prise en charge comme avant ; réalisation en cours (lots J du [plan](PLAN.md)).

## 1. Objet et limites

Qualifier les choix qui conditionnent la réussite réelle sur le poste cible, sans retarder tous les chantiers par une étude exhaustive. Les essais précoces utilisent quelques fixtures discriminantes ; ils ne remplacent pas la recette finale. Aucun benchmark de l'application ou du PC utilisateur n'a été exécuté lors de la préparation de ce dossier.

Trois vérifications sont indépendantes : Q-CPU (LLM et machine), Q-PDF (extraction/provenance) et Q-SEARCH (recherche/contraintes). Les agents peuvent préparer ces travaux en parallèle ; leurs exécutions lourdes sur une même machine sont ordonnancées sous un budget commun.

## 2. Q-CPU — réalité matérielle avant optimisation

Enregistrer CPU, cœurs physiques/logiques, instructions disponibles, OS, RAM physique/utilisable, SSD, swap, navigateur, runtime et digest du modèle. Mesurer l’hôte Windows natif et les processus du projet. Un container limité à 10 Gio sur un gros serveur ne remplace pas une qualification du PC de 16 Go.

Exécuter d'abord un smoke avec le vrai modèle Q4_K_M, CPU uniquement, non-thinking. Mesurer ensuite des entrées distinctes autour de 1 500, 3 000 et 5 000 tokens réels avec une sortie autorisée à 768. Ce sont trois points diagnostiques, pas une grille de tuning. Capturer temps de chargement, attente, prompt, génération, durée totale, tokens réels et mémoire globale.

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

Mesures D07 en calcul CPU imposé (W024, W025) : démarrer l'instance mesurée avec un profil `llm.accelerator: cpu` ; la forme antérieure `llm.num_gpu: 0` impose aussi le CPU, le profil livré en `auto` ne convient pas. Lancer la série avec `tools/qualification/perf.py`, qui relit `llm_accelerator` dans `/diagnostics` au début et à la fin de la série. Un rapport ne peut servir de preuve D07 que s'il porte `d07_eligible: true`, les autres conditions de la recette restant à remplir ; un rapport `d07_eligible: false` est invalide pour la recette et `d07_ineligible_reason` en donne le motif. Les mesures sur GPU, dont le pilote `services/runtime/calibration.py --accelerator auto`, sont rapportées à part et ne cochent aucun critère D07.

## 9. Rapport et décisions

Pour chaque essai : objectif, hypothèse, données, commit, versions, machine, commande, résultats bruts, interprétation et décision. Statuts `NOT_RUN`, `PASS`, `FAIL`, `BLOCKED`. Ne pas affirmer qu'un modèle est SOTA parce qu'il est récent, ni qu'une dépendance est compatible parce qu'elle est installable.

Garder un tableau des critères DoD avec leur preuve. Les résultats de `tools/verify_pack.py` restent dans la catégorie **contrôles documentaires/de référence**, jamais parmi les essais applicatifs Q-CPU/Q-PDF/Q-SEARCH.


## Sources et skills dans chaque essai

Avant la décision ou la modification à qualifier, appliquer [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md) : source officielle actuelle, contrat de la version installée, hypothèse et critère. Le rapport d'essai relie source, artefact, skill utilisé et preuve ; une recommandation éditeur n'est pas substituée à la mesure locale.

Pour chaque skill retenu, vérifier une tâche pertinente et une tâche hors périmètre dans le client réellement utilisé ; son installation et son invocation ne sont pas déduites du seul fichier. Sources inaccessibles, outils absents et essais non exécutés restent visibles. D11 de la DoD complète les mesures techniques sans ajouter de calls LLM cachés au produit.
