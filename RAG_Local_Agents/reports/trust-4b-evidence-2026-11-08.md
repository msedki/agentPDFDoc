# I5 — obligations, preuves admissibles et publication contrôlée

**Rôle :** bilan technique du contrat de réponse et de ses frontières avec la recherche, l’ingestion et la génération.
**Propriétaire logique :** API RAG / contrat de preuve.
**Statut :** implémentation et essais de développement exécutés le 8 novembre 2026 UTC ; qualification native finale consignée séparément.
**Référence initiale :** `41857e17a438fe43123e4ef8274d9d2d446bfbc2`, branche `enhanced_version`.
**Critères préalables :** [protocole I5](trust-4b-protocol-2026-11-08.md), puis [addendum sur les limites de travail](trust-4b-resource-addendum-2026-11-08.md), gelé avant le correctif correspondant. Le [PLAN](../PLAN.md) reste le suivi canonique.

## 1. Résultat et périmètre

Le contrat établit les besoins explicites de la question avant la sélection générative. Il relie chaque besoin à des passages admissibles, construit la vue transmise au modèle, complète les références prouvées omises et contrôle la publication finale. Le catalogue interne conserve les extraits et diagnostics nécessaires à l’audit, y compris ceux qui ne peuvent pas soutenir une réponse.

Les essais de développement ont vérifié la récupération déterministe de preuves oubliées, l’exclusion de données étrangères à la demande, la conservation des conditions applicables, la séparation des obligations quantitatives et qualitatives, ainsi que la fermeture des associations de tableau ou des lectures dont les témoins ne sont pas vérifiables. Ils comprennent de vraies bases SQLite et extractions Office, avec des doubles identifiés pour les composants qu’ils isolent.

Ce lot ne fournit pas de mesure native d’OCR, de recherche ou d’inférence 4B. Les mesures de qualité, de latence et de mémoire sur les documents réels relèvent de la campagne globale. Aucun contenu du nouveau corpus réservé I5 n’a été utilisé pour écrire ou corriger ces règles. Les constats I4 ont servi au développement, conformément au protocole.

Le générateur reste celui fixé par le protocole, Qwen3-4B Q4_K_M. Aucun modèle de correction, d’extraction sémantique ou de jugement supplémentaire n’est ajouté. Ce lot ne modifie pas ses paramètres, ses budgets de contexte ou de sortie, ni les plafonds de RAM.

## 2. Besoins explicites avant génération

[`answer_contract.py`](../../services/api/answer_contract.py) décompose les formulations reconnues en obligations portant chacune une identité stable. Une obligation décrit le document demandé, le sujet explicite, la quantité ou le prédicat, la propriété, le rôle, la configuration d’alimentation et les conditions ponctuelles applicables. La clause demandée reste disponible pour l’audit. Les coordonnées explicites entre plusieurs quantités et les demandes mixtes, quantitatives et qualitatives, sont traitées par composants.

Une demande de valeur nominale, de plage de fonctionnement ou de configuration symétrique conserve sa propre obligation. Les signes et les conditions proviennent des passages sources ; le contrat n’en déduit pas une nouvelle plage. Les fonctions ou conditions qualitatives reposent sur une grammaire littérale finie. Une formulation que cette grammaire ne couvre pas conserve une limitation d’interprétation explicite.

Un conflit entre le sujet écrit dans un titre de liste et celui d’un élément ne produit aucun sujet numérique admissible. Lorsque l’une de ces identités est explicitement demandée, le diagnostic garde les deux passages exacts. Cette conservation explique la limite sans créditer une obligation. Le conflit entre deux autres sujets ne devient pas un diagnostic pour un troisième sujet demandé.

`relation_supports_obligation` fournit le même prédicat de correspondance au contrat final et à la couverture de recherche. Une relation ne couvre le besoin que si le document, le sujet, la propriété, le rôle, la configuration et les conditions demandés concordent. Les relations quantitatives et les prédicats qualitatifs ont des identités distinctes. Les raisons de rejet et les états d’assertion empêchent de créditer une relation qui ne soutient pas le besoin.

Le catalogue possède aussi `required_documents`, issu du scope documentaire épinglé. Ce champ est interne : une liste vide fournie ultérieurement à une méthode ne supprime pas les documents requis. Une sélection contenant une preuve pour un document et aucune pour un autre garde cette obligation manquante jusqu’au rendu.

### Limites de travail préalables

La revue a identifié le produit multiplicatif des documents, sujets, propriétés, rôles, configurations et alternatives de conditions. Le [complément de protocole](trust-4b-resource-addendum-2026-11-08.md) fixe les limites avant le correctif : **256 obligations** et **65 536 caractères cumulés de clauses demandées**.

Le contrat calcule ces deux grandeurs par multiplication et addition avant la construction du produit cartésien, avant le travail sur les candidats et avant la projection du modèle. Les composants partagent une limite globale. Un dépassement produit l’erreur bornée `question_scope_too_complex`, sans recopier la question ou les identités documentaires, sans tronquer la demande en un ensemble présenté comme complet et sans appel au générateur. La frontière exacte reste admise. Cette erreur représente une limite opérationnelle et doit être comptée comme telle dans la qualification.

## 3. Projection vérifiée et contrôle de publication

[`structured_answer.py`](../../services/api/structured_answer.py) sépare le catalogue auditable de `Catalogue.model_view()`. La vue du modèle contient seulement les intervalles de preuve admis, leurs dépendances, les obligations et les diagnostics explicitement associés. Le schéma des identifiants autorisés est construit à partir de cette même projection. Une projection vide conduit à un plan déterministe vide, avec la limitation appropriée.

La projection porte son hash et ses identifiants. L’intégration dans [`context.py`](../../services/api/context.py) et [`query.py`](../../services/api/query.py) finalise le dernier message après l’ajout des limites de retrieval, recompte le payload réellement envoyé et contrôle son hash. Les catalogues d’observations géométriques et les lectures OCR détaillées restent hors du prompt.

La publication exerce trois contrôles complémentaires :

1. **Admission des preuves.** Une relation prouvée et pertinente peut compléter les identifiants omis par le plan. Une référence sans rapport est exclue. Les conditions, en-têtes ou autres dépendances nécessaires entrent avec la valeur, dans le même ensemble indivisible.
2. **Rendu déterministe.** Les passages sont des sous-chaînes exactes, liées à leurs offsets et à leurs identités de source. Les séparateurs et messages de statut proviennent du code. Le modèle ne fournit ni prose documentaire, ni valeur, ni référence libre.
3. **Contrôle final.** Le validateur reconstruit le texte attendu, les citations, les intervalles, les entrées de calcul, les obligations et le journal de sélection. Une altération ou une perte de support empêche la publication correspondante.

`publication_control` conserve le journal des complétions et exclusions, les références bloquées et les omissions. Les champs de résultat distinguent les identifiants choisis par le modèle, ajoutés, exclus et effectivement rendus. Une preuve perdue au budget reste une perte explicite. La présence d’une citation ne suffit pas à créditer une obligation.

La projection des cellules et calculs est également restreinte aux cellules demandées et aux entrées indispensables. Une cellule étrangère à la demande reste dans l’audit sans devenir un fait publié. Les valeurs ambiguës conservent leur diagnostic et ne sont pas corrigées automatiquement.

## 4. Passages minimaux, conditions et qualité des sources

### 4.1 Texte littéral

[`literal_evidence.py`](../../services/api/literal_evidence.py) découpe des intervalles exacts en tenant compte des décimales, des lignes et de quelques structures grammaticales explicites. L’enveloppe de preuve conserve les identités immédiatement liées, les conditions, les exceptions, les continuations dépendantes et les renvois tels que « See section » ou « Voir note ».

Une incise finale exprimant seulement une conséquence pratique peut être retirée par une règle finie sur des participes explicitement reconnus. Les marqueurs de condition, restriction, comparaison ou exception empêchent cette coupe ; une phrase suivante dépendante la désactive aussi. Le test couvre une incise indépendante et des variantes contenant une réserve. Aucun mot source n’est remplacé.

Cette sélection réduit la contamination d’une preuve utile par une autre quantité ou une lecture incertaine étrangère à la question. Elle reste une grammaire bornée ; elle ne prétend pas établir toute relation sémantique possible.

### 4.2 Relecture de la qualité depuis SQLite

Le builder recharge les métadonnées du parent, le hash de l’original, la page, la révision d’extraction et la géométrie de page depuis la DB. Une indication fournie par un hit de retrieval ne fait pas autorité. Pour les preuves OCR, il appelle `verified_source_quality` avec le texte parent complet et le cadre de page DB, puis vérifie les intervalles de texte effectivement publiés.

Une méthode d’extraction inconnue reste indisponible. Une ancienne extraction OCR sans témoin nécessite une réingestion pour bénéficier de cette voie de publication. Ces limites sont exposées comme limites de lecture ou de vérification. Le contrat ne transforme pas un échec de parser en affirmation d’absence dans le document.

Le [rapport ingestion](trust-4b-ingestion-2026-11-08.md) décrit les observations, l’accord entre lectures et leurs limites. Les doubles de qualité utilisés ici ne constituent pas une qualification de PDFium ou de Tesseract.

### 4.3 Tableaux et dépendances

`bind_table_context` rejoue la validation de [`table_geometry.py`](../../services/ingestion/table_geometry.py) sur les métadonnées DB. Les valeurs et en-têtes doivent avoir des liaisons soutenues par les observations. Les états partiels sont traités par cellule ; une simple confiance globale du parser ne permet pas d’attribuer une valeur à Min, Typ ou Max.

Les conditions partagées d’une sous-ligne restent des dépendances exactes de leur cellule d’origine. La qualité de cette origine est contrôlée elle aussi. Les conditions générales passent par [`table_conditions.py`](../../services/api/table_conditions.py), qui revalide les blocs autorisés, leurs hashes, leurs versions, leurs offsets et leur portée. Le texte du bandeau, y compris une réserve explicite, accompagne les valeurs concernées.

Un qualificatif d’en-tête limité géométriquement à une colonne ne devient pas une condition générale des colonnes voisines. Une condition locale peut remplacer une condition générale de la même variable uniquement lorsque la réserve source autorise explicitement cette exception. Des variables différentes, notamment des températures différentes, conservent leurs identités.

[`evidence_selection.py`](../../services/api/evidence_selection.py) ajoute ces dépendances atomiquement sous le budget existant. La sélection d’une sous-ligne tient compte du libellé d’un rowspan prouvé, avec une borne de travail, sans copier artificiellement le libellé dans le texte source. Les en-têtes d’une famille de codes indexés restent des en-têtes ; leurs suffixes de registre ne sont plus interprétés comme des composants concurrents.

### 4.4 Calculs vérifiables

Le registre de [`deterministic_calculations.py`](../../services/api/deterministic_calculations.py) ajoute `ns`, `F`, `µF`, `nF` et `pF`, avec les seuls alias explicites `μF` et `uF`. Les coefficients décimaux et dimensions sont vérifiés par les tests. Les références primaires BIPM/NIST et la décision correspondante figurent dans [SOURCES](../SOURCES.md) et [DECISIONS](../DECISIONS.md).

Les conversions utilisent le mécanisme Decimal et la trace d’opérandes existants. Les dimensions incompatibles restent refusées. Ce changement n’autorise aucun calcul documentaire à partir d’entrées absentes ou sans provenance.

## 5. Essais exécutés et échecs conservés

Les contrôles ont été séquencés sous le budget commun de processus. Aucune inférence native n’a été lancée par ce lot. Les journaux de développement restent dans les preuves privées de la campagne, conformément aux instructions du dépôt.

| Passage | Périmètre et résultat observé |
|---|---|
| Référence rouge | 19 tests génériques écrits avant modification, importés depuis le checkout initial : **15 FAIL / 4 PASS en 1,93 s** |
| Premier candidat | 19 tests : **18 PASS / 1 FAIL en 1,41 s** ; une hypothèse de budget du double tokenizer était incorrecte |
| Deuxième passage | Contrats I5 et historique : **305 PASS / 38 FAIL en 9,13 s** |
| Troisième passage | Extensions SI incluses : **312 PASS / 38 FAIL en 11,34 s** |
| Quatrième passage | Conditions générales et adaptations historiques : **350 PASS / 9 FAIL en 11,51 s** |
| Cinquième passage | Dix fichiers ciblés, corrections des pertes de sous-lignes et de la famille codes→durée : **401 PASS en 11,78 s** |
| Témoin de limite de travail | Huit tests avant garde : **7 FAIL / 1 PASS en 1,51 s** ; six échecs démontrent la garde absente, le cas API rencontre alors la limite de longueur préexistante |
| Passage avant portable complet | Treize fichiers, dont la garde et les cinq attentes historiques ciblées : **423 PASS en 16,12 s** |
| Analyse statique finale | Ruff sur les seize fichiers ciblés : **PASS** ; Mypy sur les cinq modules API du lot : **PASS** |
| Reprise après portable | Trois groupes attribués : **89 PASS en 12,11 s** ; Ruff sur les quatre fichiers touchés et Mypy sur `answer_contract.py` : **PASS** |

Les passages ne forment pas un score avant/après de qualité RAG : le périmètre de tests a augmenté, et les doublures de budget et d’extraction ont été précisées. Les échecs précédents restent conservés. Le cas API de limite de travail a été reformulé en 288 combinaisons dans une question courte pour exercer `question_scope_too_complex` à l’intérieur de la limite de tokens inchangée.

Les défauts corrigés dans ces passages comprenaient la perte d’une sous-ligne avant le catalogue, une confusion entre en-tête de bits et identité de composant, la mauvaise portée d’une condition de tableau, une sélection trop large de cellules et la disparition possible d’un document requis. Les tests finaux vérifient leur comportement positif et leurs variantes de fermeture.

Le portable complet a ensuite révélé seize échecs dans trois groupes confiés à ce lot. Quatre positifs de notes de tableau utilisaient encore une extraction sans témoin géométrique ; ils emploient maintenant le helper explicite I5, avec les assertions de texte, de dépendance et de citation inchangées. Huit tests opérationnels n’atteignaient plus le générateur sur une question non analysable ; une question qualitative admise et un double nommé de routage permettent de conserver leurs vérifications de mémoire, d’attente, d’annulation, de timeout, de sortie interrompue et de libération des verrous.

Les quatre autres échecs révélaient un défaut produit : le filtre des relations rejetées éliminait un conflit d’identités de liste parce que les sujets admissibles étaient, à juste titre, vides. Le diagnostic perdait alors son titre. Le filtre conserve maintenant les conflits liés à une identité source explicitement demandée comme relations rejetées, avec leurs dépendances. Les assertions historiques des listes restent actives et sont renforcées par l’absence de toute obligation couverte ; deux cas supplémentaires vérifient qu’un troisième sujet ne récupère pas ce diagnostic. Le passage de 89 tests comprend ces deux cas. Cette reprise ne constitue pas un nouveau passage des 423 tests précédents ; le rejeu portable global reste suivi séparément.

### Matrice des garanties

| Famille | Vérifications de développement |
|---|---|
| Obligations et publication | Demandes composées ; oubli d’une preuve utile ; exclusion d’une quantité étrangère ; rôles, configurations et signes ; qualité des réserves ; impossibilité de substituer une relation qualitative par une relation quantitative |
| Qualité et DB | Métadonnées rechargées ; témoin absent ou altéré ; ancienne extraction OCR ; incertitude hors passage pertinent ; condition partagée incertaine ; maintien de l’audit |
| Tableaux et conditions | En-têtes et sous-lignes ; portée des conditions ancêtres ; bandeau général exact ; dépendance perdue au budget ; codes→durée et conversion tracée |
| Contrôle final | Texte et citations reconstruits ; frontières de sortie interrompue ; absence de delta public ou de réponse terminale sur une génération inachevée |
| Ressources | Frontières exactes 256/65 536 ; produit des dimensions ; limite globale des composants ; nombreux documents épinglés ; rejet avant candidats/faits ; aucune génération ; cas ordinaires inchangés |

### Adaptations historiques explicites

Les assertions de vérité, de citation, de refus d’un calcul ambigu et de contrôle de sortie ont été conservées. Les changements de contrat ont conduit à préciser les attentes suivantes :

- Un extrait non admissible reste dans le catalogue et l’audit ; le test exige son exclusion de la projection et de la sortie.
- Une vue modèle vide peut être traitée sans génération. Pour tester une sortie générative interrompue, un double de routage nommé force désormais le sélecteur sur une relation déjà vérifiée ; les assertions `ERROR`, absence de réponse et absence de delta public restent identiques.
- Les positifs de tableaux utilisent des témoins synthétiques complets de glyphes et de rectangles, rejoués par les fonctions réelles. Aucun booléen de qualité injecté ne remplace ces témoins.
- Deux doubles PDF de frontière textuelle déclarent explicitement leur méthode native. Le test d’une méthode DB inconnue continue à exiger la fermeture, même si un hit prétend être natif.
- Un test de budget utilise une longue provenance documentaire indispensable, car un remplissage indépendant dans le texte peut maintenant être retiré. La perte de preuve et le conflit restent contrôlés.
- Le distracteur de bus peut rester dans le catalogue interne sans consommer le budget de la vue admissible ; le test conserve le plafond initial et exige son absence du payload, du plan et de la sortie.

Les fixtures globales et les oracles d’évaluation n’ont pas été rendus permissifs.

## 6. Reproduction

Depuis la racine du dépôt, dans l’environnement déjà provisionné :

```bash
.venv/bin/python -m pytest -q \
  tests/unit/test_i5_obligation_limits.py \
  tests/unit/test_i5_obligation_publication.py \
  tests/unit/test_i5_catalogue_quality.py \
  tests/unit/test_i5_general_condition_publication.py \
  tests/unit/test_i5_evidence_coverage_mixed.py \
  tests/unit/test_enhanced_answers.py \
  tests/unit/test_iteration2_answer_contract.py \
  tests/unit/test_iteration2_table_evidence.py \
  tests/unit/test_grounded_evidence_contract.py \
  tests/unit/test_production_evidence_contract.py \
  tests/unit/test_api_structured_answer.py \
  tests/unit/test_grounded_query.py \
  tests/unit/test_i4_coverage_context.py

.venv/bin/python -m ruff check \
  services/api/answer_contract.py services/api/structured_answer.py \
  services/api/evidence_selection.py services/api/deterministic_calculations.py \
  services/api/literal_evidence.py \
  tests/unit/test_i5_obligation_limits.py tests/unit/test_i5_obligation_publication.py \
  tests/unit/test_i5_catalogue_quality.py tests/unit/test_i5_general_condition_publication.py \
  tests/unit/i5_witness_fixtures.py tests/unit/test_enhanced_answers.py \
  tests/unit/test_iteration2_answer_contract.py tests/unit/test_grounded_evidence_contract.py \
  tests/unit/test_production_evidence_contract.py tests/unit/test_grounded_query.py \
  tests/unit/test_i4_coverage_context.py

.venv/bin/python -m mypy \
  services/api/answer_contract.py services/api/structured_answer.py \
  services/api/evidence_selection.py services/api/deterministic_calculations.py \
  services/api/literal_evidence.py

.venv/bin/python -m pytest -q \
  tests/unit/test_grounded_retrieval.py \
  tests/unit/test_i4_list_subjects.py \
  tests/unit/test_i4_operational_frontiers.py

.venv/bin/python -m ruff check services/api/answer_contract.py \
  tests/unit/test_grounded_retrieval.py tests/unit/test_i4_list_subjects.py \
  tests/unit/test_i4_operational_frontiers.py

.venv/bin/python -m mypy services/api/answer_contract.py
```

Les tests utilisent leurs répertoires temporaires. Les cas SQLite/Office ne prétendent pas employer les moteurs d’embedding ou de génération réels : ces dépendances sont remplacées explicitement pour isoler le contrat. La campagne native et le portable complet ont leurs commandes et reçus dans le protocole et le bilan global.

## 7. Limites restantes et portée de la Definition of Done

Les garanties structurelles de ce lot sont implémentées et vérifiées par les tests décrits. Leur utilité sur les documents réels, le taux d’abstention, la fidélité finale, la latence et la consommation mémoire doivent être établis par la campagne globale avec ses dénominateurs et ses échecs. Le succès des tests locaux ne clôt pas cette partie de la Definition of Done.

Les grammaires numériques, qualitatives et de portée restent finies. Une formulation non analysable porte sa limite. L’accord de lectures OCR et les liaisons géométriques apportent des preuves observables, avec les limites exposées dans le rapport ingestion ; ils ne constituent pas une garantie générale de compréhension ou d’exactitude documentaire. L’amélioration de la prudence doit être évaluée conjointement à la couverture des questions auxquelles les sources permettent réellement de répondre.

Les anciens témoins absents ou incompatibles nécessitent une réingestion. Un dépassement de complexité nécessite une demande plus restreinte. Ces situations restent visibles dans les diagnostics et les résultats d’essais ; elles ne sont pas comptées comme des réponses documentaires réussies.

## 8. Correction distincte : migration explicite d’un profil installé

### Constat, décision et critères préalables

La revue de distribution a identifié un défaut dans [`linux_profiles.py`](../../tools/dist/linux_profiles.py) : `model_keys` déduisait les réglages du modèle en comparant les profils livrés entre eux. Un catalogue contenant uniquement le modèle renforcé produisait une liste vide ; une demande explicite de dérivation pouvait donc garder les réglages de l’ancien générateur.

Avant l’édition, les critères ont été fixés : le profil résultant doit passer la garde 4B réelle, conserver les chemins de données et de stockage, les ports et la sécurité personnalisés, laisser le fichier d’origine intact, garder l’idempotence et refuser une configuration ou un périmètre ambigu avant écriture. Les archives historiques doivent rester lisibles et testables. La migration exige une cible explicitement demandée ; les lecteurs de maintenance ne convertissent pas les profils.

Le choix retenu est une branche de migration dédiée à la cible renforcée unique. Elle prend dans le template la section `llm` complète, en conservant `llm.base_url`, les réglages `enhanced`, les deux estimations de charge LLM et `retrieval.history_is_evidence`. Les anciens champs LLM absents du template sont retirés, notamment l’identité d’un tokenizer précédent. Toutes les autres personnalisations restent conservées. Les clés réellement modifiées ou retirées sont renvoyées dans `replaced_keys`.

Le template et le résultat sont contrôlés par les fonctions réelles `validate_profile` et `require_generation_profile` avant la création du fichier temporaire. Les deux modules ont été ajoutés aux sources vérifiées dans `PRE_COPY_FILES`, puis chargés explicitement depuis les chemins approuvés par le chargeur existant. La lecture des emplacements historiques conserve son ensemble minimal de trois modules ; la racine du kit n’est pas ajoutée à `sys.path`.

### Portée et refus

Un catalogue mixte pour cette migration, un chemin de template non canonique ou extérieur au kit, une section non structurée, un template incomplet ou une personnalisation incompatible avec le profil résultant sont refusés. Les données, stockages de travail et chemins TLS ne sont pas réinterprétés sous la nouvelle racine du programme : les emplacements persistants effectifs doivent être absolus. L’absence d’un override Qdrant reste permise lorsque son repli conserve le même dossier de données absolu. Les profils produits par le vrai `user_profile` utilisé par `init-profile` restent une entrée admissible.

Un nom de fichier source est aussi échappé dans le commentaire du YAML généré. Un saut de ligne dans ce nom ne peut ainsi modifier le document écrit après sa validation. Le fichier d’origine n’est jamais remplacé. Un résultat identique déjà présent est réutilisé ; un résultat différent au même emplacement est refusé selon le mécanisme existant de création sans remplacement.

### Preuve exécutée et limites

[`test_i5_profile_migration.py`](../../tests/unit/test_i5_profile_migration.py) vérifie la garde réelle, la conservation exacte, les changements déclarés, `--check`, l’idempotence, les refus avant écriture, les chemins persistants ambigus, la compatibilité du vrai constructeur de profil, une archive historique et le script isolé face à un paquet ajouté. Ses **36 cas passent**, dans un groupe de **50 tests PASS en 12,96 s** exécuté par le rôle validation pendant son créneau réservé. Le groupe comprend aussi le contrôle du manifeste de sources et l’installation atomique avec ses doubles déclarés. Les reçus sont `distribution-migration-smoke-2.log` et son JUnit XML. Ruff et Mypy distribution passent également, dont `linux_profiles.py` et `linux_install.py` ; le contrôle `git diff --check` des fichiers touchés passe.

Commande du groupe exécuté :

```bash
.venv/bin/python -m pytest -q \
  tests/unit/test_dist_linux_install.py::test_install_runs_the_whole_sequence_and_switches_atomically \
  tests/unit/test_i5_profile_migration.py \
  tests/unit/test_runtime_source_manifest.py --tb=short
```

Les contrôles ciblés se reproduisent aussi avec :

```bash
.venv/bin/python -m ruff check tools/dist/linux_profiles.py tests/unit/test_i5_profile_migration.py
.venv/bin/python -m mypy tools/dist/linux_profiles.py
```

Cette correction ne vérifie pas les poids du modèle, n’installe aucun kit et ne démarre aucun service. Les empreintes d’artefacts, le contrôle préalable de la copie, la sauvegarde et la bascule de l’installation conservent leurs portes existantes. Une ancienne configuration manuelle aux emplacements relatifs doit être rendue explicite avant cette migration ; aucun déplacement automatique de données n’est effectué.

## 9. Correction distincte : premier provisionnement 4B hors ligne

La revue des points d’entrée actifs a trouvé une branche inaccessible dans `services/runtime/cli.py`. Le provisionnement hors ligne exigeait le manifeste source avant d’appeler l’importateur, alors que le profil renforcé utilise le même fichier pour ce manifeste et le résultat de l’import. Le premier import d’un GGUF local vérifié ne pouvait donc pas créer son manifeste par cette voie.

La correction autorise cette première importation pour la seule identité générative renforcée. Le contrôle du GGUF et de sa somme de contrôle reste celui de l’importateur ; un fichier absent ou invalide échoue sans déclarer le provisionnement réussi. Les références historiques de maintenance gardent leur exigence précédente. La voie hors ligne conserve ce mode lors de la préparation des artefacts et ne devient pas une demande de téléchargement.

La même revue a relevé une collision du port temporaire de provisionnement. Un profil valide dont l’application ou Qdrant utilisait le port 11444 pouvait devenir invalide après la réécriture temporaire du point d’accès LLM. Le port est maintenant choisi de façon déterministe dans l’ensemble borné 11444–11447, en excluant le port de l’application, celui de Qdrant et son voisin gRPC. Le contrôle d’occupation reste obligatoire avant le lancement. Si le port retenu appartient à un autre processus, l’opération échoue ; aucun service utilisateur n’est arrêté. Le processus lancé par le provisionnement reste possédé et fermé par son `ProcessJob`, y compris après une erreur de vérification ou un délai dépassé.

Les **20 tests de `test_i5_gguf_provision.py` passent en 1,90 s**, exécutés par le rôle principal dans son créneau réservé. Ils vérifient le dispatch complet hors ligne, la garde réelle `Settings.load` sur les profils temporaires, les collisions de ports, l’arrêt du seul processus possédé, les refus de GGUF absent ou non conforme et le contrôle d’artefact hors ligne sans accès réseau. L’importateur natif et les processus sont des doubles explicitement nommés ; les refus réseau d’artefacts emploient la fonction réelle sur de petits fichiers synthétiques. Le fichier source de profil reste inchangé.

```bash
.venv/bin/python -m pytest -q tests/unit/test_i5_gguf_provision.py
.venv/bin/python -m ruff check services/runtime/cli.py tests/unit/test_i5_gguf_provision.py
.venv/bin/python -m mypy services/runtime/cli.py
```

Le reçu de 20 tests porte sur la première commande. Les contrôles statiques et le provisionnement natif complet ont leurs reçus séparés dans le bilan global. Ces tests ne constituent pas une installation neuve avec les poids réels.

## 10. Raccord des tableaux explicites à valeur unique

L’extension ingestion reconnaît une famille bornée de tableaux dont les trois en-têtes explicites nomment le libellé, une valeur et l’unité. La revue aval a identifié que cette nouvelle preuve géométrique n’était pas encore consommée par le contrat de réponse : la sélection des valeurs de tableau attendait une borne, une statistique ou une correspondance de code.

Le raccord ajoute le rôle structurel `quantity` pour `Value` ou `Valeur`, uniquement dans cette famille PDF complète. La relation n’est admissible qu’après relecture et validation du témoin géométrique depuis SQLite. Les colonnes peuvent être permutées ; leurs positions dans une chaîne de caractères ne déterminent pas leur sens. Les aliases de libellé restent confinés à cette grammaire et les règles des tableaux Word ne changent pas.

L’en-tête `Value` ne devient ni typique, ni nominal, ni minimum, ni maximum. Une question sur la valeur simple peut être couverte ; une demande de statistique ou de borne reste non couverte sans preuve littérale distincte. Une valeur rejetée pour ce besoin peut rester un diagnostic explicitement qualifié, sans créditer une obligation. Les citations, versions, dépendances et contrôles après rendu restent ceux du contrat existant.

`tests/unit/test_i5_explicit_value_table.py` contient 18 cas synthétiques FR/EN : valeurs et unités exactes, permutation des colonnes, aliases de libellé, demandes typique/max, citations et révisions, puis ajout frauduleux d’un rôle après publication. Les observations de glyphes sont des données de test nommées ; SQLite, le catalogue et le contrôle de publication sont réels. **Ces 18 cas passent**, dans le groupe de **41 tests PASS en 3,24 s** exécuté par le rôle ingestion pendant son créneau réservé. Les reçus `orientation-api-1.log` et `orientation-api-1.xml` ont été relus ; ce groupe inclut également les 13 frontières SQLite de la section suivante et 10 régressions de qualité du catalogue.

```bash
.venv/bin/python -m pytest -q tests/unit/test_i5_explicit_value_table.py
```

## 11. Autorité externe du repère et de la boîte du tableau

La revue de l’orientation locale a identifié une frontière insuffisante : le rejeu géométrique reconstruisait le tableau avec le cadre de page et la boîte inscrits dans le témoin lui-même. La cohérence interne de ce témoin ne prouvait pas sa concordance avec la page et le bloc enregistrés dans la base.

Le seul appelant produit de `validate_table_quality`, dans `StructuredAnswerBuilder.catalogue`, fournit désormais systématiquement deux autorités indépendantes : `geometry_json` relu dans `pages` pour la génération et la page autorisées, et `bbox_json` relu dans le bloc parent. Ces données ne viennent pas du hit de recherche. L’extension coordonnée du validateur compare le cadre normalisé et la boîte physique avant le rejeu. Une donnée absente ou invalide est transmise comme absente et ferme la relation ; l’API n’emploie jamais la compatibilité d’omission réservée aux tests purs de témoins.

Le fichier `test_i5_table_authority.py` conserve un témoin synthétique cohérent puis modifie séparément les autorités SQLite : rotation, cadres crop/effectif, index ou hash source de page, données absentes ou invalides, et boîte du bloc. Il contrôle également le cas inverse : un hit aux coordonnées falsifiées ne peut pas remplacer des autorités DB valides. Les assertions portent sur l’absence de relation et d’obligation couverte, l’exclusion des valeurs du payload et de la réponse, le maintien de l’audit, ainsi que le contrôle positif avec citations exactes. **Ses 13 cas passent dans le même groupe de 41 tests en 3,24 s**, sans double comptage avec la section précédente.

L’absence réelle d’une CropBox reste une absence : le cadre effectif valide suffit au calcul géométrique et se compare séparément. La garde ne fabrique pas une CropBox pour la faire coïncider avec le témoin.

Un ancien double de ce lot déclarait une page de 550 × 400 alors que ses observations étaient produites sur 500 × 400. La dimension enregistrée est maintenant donnée explicitement à ce seul appel de fixture. Ses assertions et valeurs sources restent inchangées ; aucun assouplissement de la frontière produit n’a été ajouté pour ce double incohérent.

```bash
.venv/bin/python -m pytest -q \
  tests/unit/test_i5_table_authority.py \
  tests/unit/test_i5_catalogue_quality.py \
  tests/unit/test_i5_explicit_value_table.py
```

La revue de l’orientation a aussi signalé au rôle ingestion l’absence de liaison entre le hash OSD et le preprocessing. Son correctif et ses tests sont décrits dans le rapport ingestion ; ce lot API ne prétend ni réexécuter l’OSD ni qualifier son exactitude.


## 12. Addendum de développement : portée littérale et garantie explicite

### Constats et critères figés avant la correction

Décision enregistrée avant l’édition du contrat : 2026-11-08T23:30:22.873616+00:00. La campagne native de développement 4 conserve ses résultats initiaux. H01 a terminé en erreur d’admission de ressources, sans appel du générateur ; son catalogue avait aussi perdu le sujet de la plage de température. H02 a publié une abstention d’analyse alors que le passage utile était retrouvé, complet et corroboré par le contrôle OCR. Ces essais restent des échecs sur des questions répondables ; une reprise ultérieure sera identifiée séparément.

Deux corrections de grammaire sont autorisées dans ce lot. Premièrement, la question sur les circuits externes ne doit pas perdre une source qui supprime explicitement le besoin de **tout** circuit d’une catégorie nommée. Le quantificateur universel doit porter directement sur l’objet de la clause de suppression. La réponse conserve le passage littéral ; elle n’ajoute ni le mot « externe », ni une catégorie, ni une conséquence. Une quantité partielle, une portée limitée aux circuits internes, un quantificateur présent dans une autre proposition, une négation, une incertitude ou un autre sujet ne doivent pas satisfaire cette demande. Les conditions et réserves de la clause restent publiées avec elle. Le simple retrait de la garde lexicale « external » est exclu.

Deuxièmement, une demande de plage garantie doit conserver une qualification `guaranteed` explicitement présente dans la source. Une plage de fonctionnement, une valeur typique ou une plage non qualifiée ne remplace pas une garantie. Les tests opposent des plages synthétiques différentes et vérifient les obligations, le choix des preuves, la réponse littérale, les citations et le rejet d’une qualification modifiée après rendu. La question distincte sur la non-garantie de fonctionnement sous limites absolues doit conserver son interprétation et son contrôle existants.

La portée géométrique du sujet de tableau reste une question séparée. La cellule parseur du titre était fusionnée avec le seul en-tête Typ ; son rectangle ne prouve pas une portée sur Min et Max. Aucun élargissement à la table entière par proximité ou nom de fichier n’est autorisé dans ce lot. Une preuve géométrique supplémentaire doit être examinée par le lot ingestion avant toute modification de cette portée.

Protocole prévu : ajouter des exemples inventés FR/EN aux frontières de publication, conserver les tests historiques de rôles et de limites absolues, puis exécuter le groupe ciblé et les contrôles statiques dans le prochain créneau réservé. Aucun résultat de ces nouveaux tests n’est encore acquis au moment de ce gel. Aucune donnée ni exigence du corpus réservé I5 n’est utilisée.

Le premier groupe ciblé a ensuite donné **216 PASS en 5,81 s**, avec Mypy et Ruff réussis après une correction d’espacement d’import. Une relecture a toutefois trouvé un contre-exemple absent de ce groupe : exclure seulement les premiers mots numériques laisserait passer une cardinalité explicite différente. Avant la correction complémentaire, le critère est donc précisé : les cardinalités FR/EN, les collectifs bornés (paire, douzaine), les sélections et possessifs qui limitent l’objet empêchent de déduire le sous-ensemble externe. Cette vérification porte sur l’objet avant les conditions explicites ; une condition « only when two sensors agree » ne doit pas devenir à tort une cardinalité de circuits. De nouveaux contre-tests positifs et négatifs sont ajoutés avant le prochain reçu. Le succès du groupe initial ne qualifie pas cette frontière supplémentaire.

Une seconde relecture a établi, avant l’édition suivante, que la garantie ne doit pas remplacer le rôle d’exploitation : « guaranteed operating temperature range » doit répondre à une demande de plage de fonctionnement, avec sa garantie et ses conditions conservées. Une demande de plage de fonctionnement garantie doit exiger ces deux propriétés sur la même relation. À l’inverse, « Guaranteed Temperature Range » n’autorise pas à inventer le rôle operating. Le contrat portera donc la qualification séparément : `guarantee_required` dans la demande et l’obligation, et `guarantee: explicit` dans un fait positivement étayé ; `null` signifie seulement que cette qualification n’est pas établie. Les deux bornes d’une plage doivent partager leur qualification. La comparaison, la couverture et le registre doivent la conserver dans l’identité des preuves. Les contre-tests ajouteront les formulations composées, les rôles différents, les deux bornes à portée distincte et les conditions qui limitent une garantie. Une négation ou une incertitude ne fournit aucune garantie positive. Cette adaptation remplace les assertions de rôle `guaranteed` des seuls nouveaux tests, en gardant leurs exigences sémantiques et leurs données synthétiques.

## 13. Reprise du 9 novembre : antécédent d'une fonction relative

La relecture du contrat repris a identifié un faux positif distinct : la présence
du terme demandé n'importe où dans une phrase permettait de prendre le premier
`which` ou `qui`, même lorsque cette relative décrivait un autre antécédent.
Quatre contre-exemples inventés FR/EN ont reproduit ce défaut de couverture ;
les quatre contrôles positifs initiaux passent. La première exécution est
conservée avec **4 FAIL / 4 PASS**, avant modification du produit.

Le critère complémentaire est fixé avant correction : la relative retenue doit
suivre immédiatement le terme demandé dans son antécédent littéral, avec la
seule ponctuation séparatrice. Une mention située dans la conséquence, dans une
proposition ultérieure ou avant un autre groupe nominal ne permet pas de
créditer la fonction demandée. Lorsqu'une phrase contient plusieurs relatives,
le rattachement doit conserver la qualification de celle qui suit le terme
visé. Les exemples existants, leurs citations et le texte source intégral sont
conservés. Une construction grammaticale non reconnue reste non couverte ;
aucune résolution sémantique générale n'est introduite.

Cette revue n'a consulté aucun document ni oracle du transfert réservé I5.

L'assertion supplémentaire sur la qualification exacte du second antécédent
porte le témoin rouge final à **5 FAIL / 3 PASS en 0,89 s**, toujours avant le
correctif. Après correction, les huit cas et cinq groupes de non-régression
(obligations, portées, garanties, identité des preuves et couverture mixte)
donnent **118 PASS en 9,11 s**. Ruff sur les deux fichiers touchés, Mypy sur le
contrat et `git diff --check` passent. Les deux rouges et le groupe final sont
conservés séparément dans `.runtime/qa/production-i5-20261108/recovery-api/`,
avec leurs JUnit, logs et empreintes dans `receipt.json`.

Ces 118 contrôles incluent huit cas nouveaux ; ils ne s'additionnent pas aux
108 tests ciblés précédemment exécutés sur le code repris. Ils ne rejouent ni
la campagne native ni la matrice primaire des trente questions. La correction
n'ajoute aucun modèle, ne change aucun poids ou plafond et conserve la réponse
comme citation littérale de la source.

## 14. Développement du 9 novembre : preuve d'une condition hors plage

**Statut :** correctif API implémenté et contrôlé par tests ciblés ; nouvelle
qualification native encore attendue. L'auteur de ce lot a lu l'échec H03 de
développement avant de corriger le mécanisme : cette évaluation est non aveugle.
Le corpus réservé I5 n'a pas été consulté.

### Défaut conservé et mécanisme corrigé

Dans la phase 5, H03 termine avec une abstention générique, sans citation ni
plage garantie. Le passage natif utile est pourtant retenu dans R007. Le contrat
cherche des faits de tension ; une plage de température ne devient donc pas
une preuve de cette tension, mais ne pouvait pas non plus expliquer la limite.
L'espace interne à l'unité extraite `° C` empêchait en outre son interprétation
par le lecteur de quantités.

Le nouveau diagnostic de condition hors plage conserve une relation distincte
de la grandeur demandée. Il exige un intervalle littéral de fonctionnement ou
explicitement garanti, un sujet écrit, un passage complet, une lecture native
ou corroborée, et une condition ponctuelle située strictement hors des bornes
après conversion avec le registre Decimal existant. Il ne couvre jamais
l'obligation quantitative : `coverage_effect: none` et le motif de rejet
empêchent cette relation de satisfaire une obligation. Le passage exact devient
obligatoire dans la projection et le rendu ; l'omission du modèle ne le retire
pas. Aucun nombre demandé n'est produit par extrapolation.

Le contrôle conserve les identités de document, version, génération et
extraction. Une autre identité de sujet, une variable nommée différente, une
propriété de température non établie par la demande, un maximum absolu, une
restriction supplémentaire, une plage divergente dans la même révision ou une
lecture non corroborée ne deviennent pas une enveloppe applicable. Une valeur
déjà établie au point demandé empêche ce diagnostic. Les plages à polarité `±`
sont exclues : une amplitude positive ne réfute pas un point négatif. Ce
mécanisme borné porte sur des passages de prose ; il n'assouplit aucune garde
de tableau et n'assemble pas de bornes prises dans des cellules séparées.

Le parseur d'unités reconnaît les deux alias typographiques `° C` et `° C`
(espace ordinaire ou insécable unique). Il ne réécrit ni l'extrait ni ses offsets.
Le contre-exemple anglais `approximate` a aussi complété le détecteur existant
d'incertitude, qui reconnaissait déjà `approximately`.

### Contrôles exécutés et limites

- Le premier groupe discriminant donne **3 FAIL et 19 PASS** avant correction.
  Le contre-exemple ajouté sur `±` donne ensuite **1 FAIL et 1 PASS**, avec
  22 cas non sélectionnés, avant l'exclusion de cette polarité.
- Le groupe dédié final donne **24 PASS en 1,23 s**. Il vérifie la température,
  la conversion Kelvin, un autre domaine de quantité (pression), les refus
  précédents, les offsets, la citation obligatoire, la non-couverture de la
  grandeur demandée et le rejet d'un rendu modifié.
- La non-régression adjacente donne **248 PASS en 8,48 s** sur six fichiers
  ciblés (contrat, obligations, conditions, publication et calculs). Ce reçu
  précède la dernière exclusion conservatrice de `±` ; les 24 cas dédiés sont
  rejoués après celle-ci. Ces nombres se recouvrent et ne s'additionnent pas.
- Ruff sur les trois fichiers et Mypy sur les deux modules API passent, ainsi
  que `git diff --check`. Aucun moteur, OCR, extraction native ou appel du 4B
  n'a été exécuté dans ces contrôles.

Le rejeu en mémoire du catalogue de développement H03 rend uniquement R007
obligatoire. Il cite le passage original entre les offsets **172 et 308**, qui
porte la plage garantie `0 ° C to +100 ° C`, avec S002. Le statut reste
`partial`, aucun fait de tension n'est établi, et `verify_rendered` passe.
Le reçu privé `recovery-api/h03-condition-range-replay-1.json`, sous le dossier
QA de production I5, porte le SHA-256
`7c1b83eefafe714334553e67713c598a784624b41314ebc319f8e180d56170ac`.
Il n'est pas un succès natif : extraction, recherche, contexte et modèle ne
sont pas rejoués. L'enregistrement H03 de phase 5 reste inchangé avant/après,
SHA-256 `5433745977e469cb54f233837db627bf43736177d3461e6d750b99a5649ef25d`.

Empreintes du correctif contrôlé :

| Fichier | SHA-256 |
|---|---|
| `services/api/answer_contract.py` | `6f877ed98c49673a2799e0291d91e6c2c80409cf90e1b1bcd51efa5dd302130b` |
| `services/api/deterministic_calculations.py` | `969b651710294a9f671fdcdb1b62c7696cd3646ce3fcec271bb4ad6a57c64c45` |
| `tests/unit/test_i5_condition_limit_evidence.py` | `c0fa37dc93631c62f161f792b97838c5dad344c30fee7e20b88633e187f7659f` |

### Relecture indépendante et durcissement avant instantané 6

La relecture du rôle qualification a démontré deux défauts de la version
précédente : un opérateur `<` ou `≤` devant la borne pouvait être perdu par
l'analyse numérique, et une phrase suivante commençant par « Only the
laboratory prototype… » pouvait limiter une plage sans entrer dans la citation
extraite. Le reçu privé `h03-independent-review-1.json` porte le SHA-256
`4f1525234fabade1c21e1117cea673ddd33a91ebff273d02e90f0c36a9d0e895`.
Les cas `<`, `≤`, une polarité `±` non symétrique et la restriction suivante
produisent **4 FAIL avant correction** ; ce reçu reste conservé.

Le contrôle du nouveau diagnostic examine désormais les restrictions explicites
sur le passage source complet. Il refuse les opérateurs de borne non interprétés
et les qualifications supplémentaires avant de retenir une phrase. L'égalité
mathématique `=` reste admise ; elle ne modifie aucune borne. La grammaire
globale des extraits n'a pas changé. Ce refus conservateur peut laisser sans
diagnostic une plage valide mêlée à une restriction indépendante ; il ne tente
pas de résoudre cette portée par inférence.

La version corrigée donne **254 PASS, zéro erreur, zéro échec et zéro cas
ignoré**, en **8,947 s**, sur les six fichiers ciblés, dont **28 cas dédiés**.
Ruff et Mypy passent. JUnit final SHA-256 :
`1ef484e96c65624292b3954e878919c233f2fe42a19aeae2a99d4277b6724aa7`.
Les contrôles précédents ne sont ni remplacés ni additionnés à ce dénominateur.

Le rejeu en mémoire v2 conserve le même passage H03, les offsets 172–308, S002,
le statut partiel et l'absence de fait de tension. Le fichier natif de phase 5
reste inchangé. Le reçu `recovery-api/h03-condition-range-replay-2.json` porte
le SHA-256 `5e29583a126bfb26121e681b4e7ac75ae08524ba8156eaae58a86793e57945f6`.
Il garde la même limite méthodologique que v1 : aucune mesure native ni appel
modèle. La version proposée à la seconde relecture indépendante est :

| Fichier | SHA-256 après relecture |
|---|---|
| `services/api/answer_contract.py` | `8ff31bc6a31cf3055abe312f0556e87c939b5ef8197ce3241812cf89026f755d` |
| `services/api/deterministic_calculations.py` | `969b651710294a9f671fdcdb1b62c7696cd3646ce3fcec271bb4ad6a57c64c45` |
| `tests/unit/test_i5_condition_limit_evidence.py` | `731ab9baa51fd2793179abe36a78a8aa7c179e8df77bb6d94c16f282c6b5371e` |

La seconde relecture indépendante conclut sans défaut bloquant dans ce périmètre.
Ses **sept sondes synthétiques** passent, dont les bornes opérées, la restriction
suivante et l'alias à espace insécable. Elle vérifie séparément la non-couverture
de la grandeur demandée et le rendu. Reçu `h03-independent-review-2.json`, SHA-256
`37a40fc5bdc7dbbfa0c9bb3332f8ae38eaae99bf1c5c29b7ae916de0c0c454cd`.
Cette revue porte sur les trois empreintes finales ci-dessus et ne transforme
aucun essai natif antérieur en succès.

## 15. Raccord API des fragments de conditions v2

**Statut :** raccord implémenté, tests ciblés exécutés et revue croisée du rôle
ingestion effectuée ; une campagne native sur le nouvel instantané reste à
exécuter. Le regroupement géométrique et son protocole appartiennent au lot
ingestion ; les décisions canoniques sont I5-D07/D08 dans `DECISIONS.md`.

`table_conditions_bundle` n'aplatit les pièces de lignes v2 qu'après
`validate_table_general_conditions`, qui reconstruit l'annotation depuis les
blocs autorisés de SQLite. Il applique ensuite à chaque fragment d'origine
les mêmes vérifications d'identité, hash, texte, offsets et sélection que pour
une pièce v1. Le catalogue de réponse refait le contrôle de chaque parent,
intervalle de référence et qualité de lecture. La complétude est comparée au
nombre de fragments d'origine, et non au nombre de lignes géométriques.
Le raccord ne crée aucun bloc, texte ou hash de parent concaténé et ne promeut
pas une qualité OCR incertaine en preuve publiable.

Le nouveau groupe `test_i5_condition_line_scope.py` commence par **3 FAIL et
4 PASS** avant le raccord, puis donne **7 PASS en 2,24 s**. Sa fabrication
d'extraction est explicitement synthétique ; indexation SQLite, reconstruction
géométrique, périmètre, projection et rendu sont réels, avec les doubles
existants d'embedding, vecteurs et compteur de tokens. Le cas positif conserve
**13 parents originaux dans deux pièces géométriques**, avec leurs citations,
hashes et offsets. Les contre-exemples couvrent fragment manquant ou rogné,
hash ou ordre de témoin altéré, et lecture inconnue d'un seul fragment.

Un contrôle distinct conserve la limite sémantique : lorsque les éléments
d'un point `TA = 18 °C` sont répartis entre plusieurs blocs, le regroupement
géométrique seul ne reconstruit pas ce point. L'obligation reste non couverte.
Le cas positif garde le point numérique dans un seul bloc ; le titre et la
définition de marqueur forment la ligne fragmentée. Aucune règle de lecture
des conditions ni le correctif H03 stabilisé n'a été modifié pour ce raccord.

La non-régression ciblée sur six fichiers donne **111 PASS en 6,46 s**, y compris
les contrôles H03, conditions v1/v2, portée et publication. Ce dénominateur se
recouvre avec les groupes précédents et ne s'y additionne pas. Ruff et Mypy
passent ; Ruff a demandé une mise en forme des deux imports, corrigée après
les tests sans changement de comportement. `git diff --check` passe.
JUnit SHA-256 : `1591c475811819b7ccd3f477297821180ae93d69ec06b11d36aa13c3319c10fa`.
La revue croisée ne relève pas de défaut bloquant dans ce raccord ; elle ne
constitue pas une mesure native ni une preuve de fidélité OCR.

| Fichier | SHA-256 |
|---|---|
| `services/api/table_conditions.py` | `b2a3087e355fb2bfd6a2c6e519586088b7a2a87726f9a8b1a36a3962e2b816f1` |
| `services/api/structured_answer.py` | `56a4772732835db508bebc5fbb462617dc89f8379f6813c99d8580245b1a4a1a` |
| `tests/unit/test_i5_condition_line_scope.py` | `a19a21f77561aaae5d2aee5a22011a52b3e156e8462680b8340dead93e0942c9` |

## 16. Lot API 7 après les échecs de développement 6

**Statut :** code et tests ciblés terminés après la clôture de phase 6 ; aucun
moteur natif ou appel modèle lancé par ce lot. Les résultats natifs de phase 6
restent conservés. Le transfert réservé I5 reste fermé pour ce rôle.

### Diagnostic d'une demande non analysée

La revue L11/L12 a isolé un défaut d'explication : une projection vide de
question générale devenait `partial` avec un faux `requested_document` au
rendu. Le contrat garde maintenant `unassessed`, avec plan et citations vides.
Une limite de recherche reste auditable séparément et son message n'affirme
pas une couverture partielle de relations non analysées. Les demandes
reconnues conservent leurs vrais documents manquants et leur statut partiel.

Les six tests dédiés couvrent l'état initial/final, les deux formes de
diagnostic, les deltas/terminal de `QueryService` et les zéro appels du modèle.
La revue indépendante de qualification est sans défaut bloquant dans ce
périmètre, SHA-256
`c86ac8bcf24a96f15c11c0c9462e6d7823ed7d7406b765c28a2452b3f946e8f4`.
Elle ne fait pas passer les scénarios primaires L11/L12 : le sélecteur n'y est
toujours pas appelé, et **16/18 limites** reste le résultat contrôlé primaire.

### Autorité explicite du sujet de page

H07 phase 6 disposait de deux délais, de leurs conditions et du bandeau
imprimé du composant, mais aucune relation vérifiée ne reliait ce bandeau au
tableau. `table_subjects.py` reconstruit désormais une autorité bornée
`page_header → table`. La page entière doit être autorisée ; les scopes de
blocs ou de caractères ne peuvent pas établir son unicité. Le seul en-tête
autonome explicitement typé `page_header` doit contenir un identifiant unique,
être déjà retenu intégralement, avoir une lecture native ou corroborée et
se situer au-dessus du tableau et de tous les blocs de corps examinés dans
le repère PDF/display vérifié. Les caps restent 256 blocs, 200 000 caractères
de texte et 2 000 000 caractères de métadonnées.

Génération, document, version importée, version d'extraction, révision, page,
hash, rectangle et offsets sont relus depuis SQLite. Le sujet ne vient ni du
nom du fichier, ni de la question, ni d'une section inventée. Un en-tête
concurrent, une section intermédiaire contradictoire, une lecture incertaine,
une géométrie invalide ou un budget insuffisant empêchent l'héritage. Le sujet
écrit dans la ligne ciblée ou ses parents garde priorité ; une variante
mentionnée sur une autre ligne ne devient ni un alias, ni un conflit global.
Le `section_id` historique du bandeau reste inchangé.

Le bandeau devient une dépendance citée avec ses offsets exacts, également
consignée dans la relation et le registre de preuve. Sa suppression retire
la couverture des valeurs. Le repli vers `document_name` est désactivé sur
les seules relations de tables PDF dont la géométrie est revalidée ; les
chemins Office et prose conservent leur comportement. Le constructeur final
refait les vérifications, puis le rendu contrôle l'ensemble des dépendances.

### Section sœur et publication

Le premier rejeu pur H07 a montré une seconde cause : le catalogue nouvellement
couvert ne pouvait pas être publié. La ligne de section « Comparator » était
une dépendance obligatoire ; son contexte propre manquait parce que
`_table_context` lui imposait à tort la section précédente « Power Supply ».
Le témoin géométrique relu depuis SQLite attestait pourtant sa cellule et
ses dix glyphes natifs exacts. La correction locale fait commencer un nouveau
groupe à une ligne de section ; elle n'en fait plus l'enfant de la section
sœur précédente. Les lignes de données gardent leur dépendance à leur propre
section. Aucune qualité n'est directement promue et aucun seuil de publication
n'est relâché : le reconstructeur ordinaire vérifie la section avant admission.

Deux contre-exemples inventés échouent avant cette correction, puis passent
avec les deux ordres de sections. Les tests vérifient les deux groupes positifs,
le sujet local distinct, ainsi que le refus d'une section manquante, rognée ou
contradictoire. Le groupe `test_i5_page_subject.py` contient **41 contrôles**,
avec les cas de sujet, scope, qualité, identité, rotation/crop, limites de
lecture, citations et sections sœurs.

### Projection des cadres et vérifications finales

Les émissions de `evidence_selection._section_heading`,
`table_conditions_bundle` et du nouveau témoin de sujet utilisent le helper
racine `source_page_geometry`. Les diagnostics volumineux ne sont plus copiés
dans chaque fragment ; leur hash `stored_geometry_sha256` rattache le cadre
émis au JSON DB complet. Les lectures de preuve de géométrie et de qualité
continuent d'utiliser le JSON complet. Un contrôle vérifie la conservation
des faits/citations et l'absence de modification de la DB après cette projection.

La constante et la fonction de conditions ponctuelles ont été déplacées par
racine dans `point_conditions.py`. Le raccord de ce lot est uniquement un
import ; l'identité AST avant déplacement a été vérifiée. Le correctif L13
sur les dépendances littérales appartient à racine et a sa revue séparée.

La dernière suite ciblée donne **308 PASS en 20,70 s**, zéro échec/erreur/cas
ignoré, sur dix fichiers ; Ruff et Mypy passent. Les essais intermédiaires
restent conservés et ne s'additionnent pas : six tests initiaux de diagnostic,
deux défauts de sujet reproduits, puis 42 contrôles, 41 contrôles dédiés après
la correction de sections et 271 contrôles intermédiaires. La première
fixture de sujet avait omis MIN/MAX et n'atteignait pas la frontière de sujet ;
elle a été corrigée avant le delta produit. Une assertion utilisait aussi
`source_ids` au lieu de `source_id` pour un marqueur, corrigée dans le test.

Trois reçus de rejeu pur sont conservés sous `recovery-api/` : r01 expose la
dépendance de section bloquée ; r02 conserve encore le marqueur d'idempotence
de l'ancien bundle et reste rouge ; r03 reconstruit les hints de bundle depuis
la même DB et exige l'égalité de l'ensemble exact des spans retenus. **R03
couvre les deux obligations et publie 60/50 µs, les overdrives 10/100 mV, la
charge COUT 100 pF, le bandeau général et l'en-tête LTC1540, tous cités.** Son
hash est `64c791ee61eb1a9288ba46c48f1fe230faf44cbf752fa469b8a3ec1dff3bdc71`.
DB et mesure native phase 6 sont identiques avant/après ; le compteur de
tokens est un double explicite. Ce rejeu ne mesure ni fidélité OCR, ni modèle,
ni latence native, et ne requalifie pas H07 phase 6 en succès.

Les empreintes finales, commandes, JUnit et reçus de revue sont consolidés
dans `recovery-api/source7-api-final-receipt.json`. La campagne native suivante
doit encore vérifier le candidat nouvellement gelé ; les dénominateurs de la
phase 6 et de la recette réservée restent distincts.

## 17. Après la phase 7 — identité de prose, dépendances atomiques et limite TMP117

La phase 7 est close avant ce lot. H06 et H08 restent deux échecs documentaires
de cette phase, malgré leurs terminaux `done` : H06 refuse les deux plages
d'alimentation présentes dans le catalogue ; H08 refuse sans citer la
condition source de 10 mV. L'auteur de ce correctif participe à son évaluation,
qui n'est donc pas aveugle. Aucun moteur, modèle, rendu PDF ou corpus réservé
n'est exécuté ou ouvert par ce lot API.

### Cause vérifiée et frontière du correctif

Les bornes, unités, configurations et qualités de lecture sont déjà présentes.
H06 possède deux relations natives, simple 2–11 V et symétrique ±1–±5,5 V,
mais sans sujet admis. H08 possède le passage natif complet « 60µs Propagation
Delay with 10mV Overdrive ». Sa demande de maximum est reconnue ; le rejet
`requested_bound_not_established` est également disponible, mais le filtre de
sujet empêche de le publier comme diagnostic. Le titre de page autonome
LTC1540 est déjà retenu dans les deux catalogues.

L'autorité de sujet existante est étendue aux paragraphes et items PDF
complets, dans une page réellement autorisée en entier. Le constructeur relit
source, document, versions, génération, révision, hashes et repère géométrique
depuis SQLite, sous les caps existants. Le sujet vient d'un en-tête autonome
explicitement typé, déjà retenu, natif ou corroboré, au-dessus du corps. Les
identités écrites locales gardent priorité. Un sujet concurrent dans le
paragraphe ciblé ou un prédécesseur de la même colonne bloque l'héritage.
La détection de `DEV®941` ne sert que de veto : elle ne crée aucun alias et
ne répare jamais le texte source. Les blocs rognés, tables ou `table_data`
non revalidés ne peuvent emprunter cette voie.

Le repli du nom de fichier est fermé pour ces références de prose PDF
reconnues depuis la DB, même lorsqu'aucune autorité de page n'est disponible.
Les grammaires de grandeur, de borne, de garantie et de condition restent
identiques à l'instantané 7. L'ablation causale initiale, séparée de toute
preuve produit, confirme que cette seule liaison rend les deux plages et le
diagnostic de maximum exprimables sans étendre ces grammaires.

### Sélection et budget ne peuvent séparer l'identité du passage

Un contre-exemple additionnel sélectionne seulement le passage numérique
H08, sans son identité. Avant fermeture, il était publié sans l'en-tête et
passait le contrôle structurel. Le correctif complète uniquement la dépendance
exacte d'une relation déjà admise et sélectionnée ; il ne sélectionne aucun
nouveau diagnostic à la place du modèle. La valeur et l'identité forment une
unité de rendu entière sous le budget. Si la qualité ou l'intégrité de
l'identité manque, le passage ne peut subsister seul.

La revalidation vérifie le texte complet, le hash, les offsets, les identités
de révision et la qualité de la référence dépendante. Elle refuse sa
suppression ou son altération avant le rendu. Cette fermeture s'applique aux
relations qui utilisent réellement le témoin ; un fait qualitatif autonome
ne reçoit pas une dépendance de page artificielle. Les citations sont placées
à la fin de cette unité documentaire entière, avec leurs liaisons exactes.

### Régression TI recherchée et autorité de titre bornée

Le contrôle ciblé demandé sur les mêmes preuves TI de phase 7 découvre une
régression réelle après fermeture du nom de fichier : TMP117 passe à zéro
obligation couverte sur une, et INA226 à une sur deux. Aucun repli vers le
fichier n'est rétabli. Les deux titres imprimés sont déjà retenus et natifs.
Une seconde autorité, réservée à la prose, admet un titre typé
`heading/section_header`, commençant par l'unique identifiant explicite de
son texte et dominant le corps et les sections de la page. Le titre complet
reste revalidé ; seul son segment littéral d'identité est cité. Un en-tête
composite n'est pas une autorité positive et un préfixe concurrent bloque.
Aucune référence hors du budget, nouvelle section ou propagation interpages
n'est ajoutée.

Le rejeu groupé final conserve exactement les mêmes spans que les mesures
fermées et donne les résultats suivants :

| Cas consommé | Résultat API du rejeu | Limite de cette preuve |
|---|---|---|
| H06 | Deux obligations couvertes, plages 2–11 V et ±1–±5,5 V, identité citée. | Route déterministe ; compteur de tokens doublé, aucune mesure native. |
| H08 | Maximum non établi ; condition exacte de 10 mV et identité citées, zéro obligation couverte. | Plan simulé ne sélectionnant que le passage ; identité complétée par l'API. Le sélecteur modèle réel reste à mesurer. |
| INA226 | Deux obligations couvertes : bus 0–36 V et alimentation 2,7–5,5 V, titre explicite cité pour les relations qui l'empruntent. | Même corpus de développement déjà consommé, pas de nouveau résultat natif. |
| TMP117 | **Toujours partiel : zéro obligation couverte sur une.** Les deux plages retenues restent citées sous la limitation. | Régression connue, refus conservé ; aucune déclaration de réussite. |

TMP117 échoue au garde de dominance : au-dessus du titre figurent quinze
fragments OCR de navigation/logo, typés comme texte et de qualité incertaine,
un doublon natif autonome TMP117 et une ligne native de révision. Les figures
persistées corroborent la position de certaines icônes, sans fournir un rôle
de corps ou d'en-tête utilisable pour tous ces blocs. La ligne de révision
n'a pas de rôle structurel attesté distinct. Aucun filtre de chaîne, de
constructeur ou de coordonnées n'est ajouté pour l'écarter.

La dernière piste est également vérifiée : l'item natif retenu
« TMP117 high-accuracy temperature sensor » partage la section Features,
mais le reconstructeur de liste ne le désigne pas comme parent. Les deux
plages dépendent seulement du parent explicite « Supply range: » et des
marqueurs de leur groupe. Le premier item est un frère ; ni sa proximité,
ni leur section commune ne lui donnent une autorité d'introduction. Le
diagnostic TMP117 est clos comme limite réelle à mesurer en phase 8.

### Validation et historique préservé

La dernière suite ciblée donne **364 PASS en 33,44 s**, zéro échec, erreur ou
cas ignoré, sur onze fichiers. Elle comprend les **56 contrôles** du nouveau
fichier de prose et les 308 contrôles de non-régression du lot API précédent.
Ruff et Mypy passent. Les rouges sont conservés séparément : défaut initial
de sujet et fallback fichier, dépendance orpheline, titre absent, régression
qualitative intermédiaire, régression TI et rejeu final TMP117. Une première
passe d'implémentation avait omis `kind` dans la lecture de parent DB ; elle
est corrigée avant les résultats finaux. Deux assertions de placement des
marqueurs ont ensuite été adaptées au rendu atomique, sans changement produit.

Le reçu `recovery-api/source8-four-case-replay-r01.json`, SHA-256
`4bda707e089c8d356dd4ff1478d67301a654c77375b46bf582615b6f0d8e2ed6`,
conserve le résultat défavorable TMP117 et les hashes avant/après. Les bases
SQLite et mesures de phase 7 restent strictement inchangées. Les trois
sources finales sont identiques à celles de ce rejeu ; il n'est pas répété
pour obtenir le même résultat. Les empreintes, commandes, journaux et avis
indépendants sont liés dans `recovery-api/source8-api-final-receipt.json`.
La campagne native suivante doit mesurer cette source, y compris la
régression connue, sans remplacer les résultats des phases antérieures.

Le reçu API final est scellé sous SHA-256
`94b8fa47a6b0cb0b45fd6c9e04f7c40fd8d93739cc68ca7df97ebaa357215042`.
La revue indépendante `ingestion-prose-page-subject-review-r02.json`, SHA-256
`7810a8695aa1634ccb49fef5243003d4df7346b6eac7176c19400c5a4d23eb47`,
est close **avec la réserve TMP117 et une non-régression TI non satisfaite**.
Elle n'est ni une approbation globale sans réserve, ni une qualification de
production. L'état du présent rapport référencé par ce reçu reste conservé
dans `recovery-api/source8-evidence-report-at-seal.md`, SHA-256
`231be2c240ae305772100efff24c3779135e3cdf7423a3a547ff24b1d9794c03`.

L'instantané 8 a ensuite été gelé par racine, reçu SHA-256
`1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b`,
avec le plan des cinq blocs et vingt questions, SHA-256
`0ed26792f303db5785cba66871688528ec7a1e53a5b4eeb975435889929e85bb`.
La revue Office 8 conserve les huit critères du rapport dédié ; son collecteur
ne peut ouvrir ou hasher SQLite qu'après la fermeture vérifiée du bloc.
