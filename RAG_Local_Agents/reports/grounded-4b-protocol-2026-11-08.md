# I3 — protocole préalable : preuves jusqu'à la réponse

**Rôle :** protocole et critères d'acceptation du lot I3. **Propriétaire :** intégration RAG.
**Statut :** fixé avant modification du code produit, 8 novembre 2026 (UTC).
**Référence :** `3956491a2d7f1f16cefebfe79e92c638b6662c10`, branche `enhanced_version`.
Le plan canonique reste [PLAN.md](../PLAN.md). Ce protocole ne remplace pas la DoD globale du produit.

## Objectif, limites et hypothèses

Conserver uniquement Qwen3-4B pour les essais génératifs et renforcer la chaîne
documentaire : extraction et portée honnêtes, preuves complètes, sélection bornée,
plan de restitution limité aux références, calculs par code, vérification avant
publication. Aucun gain scientifique général n'est présumé. Les anciens profils
et rapports restent historiques ; aucun essai 2B/8B, nouveau générateur, entraînement,
GraphRAG, service distant ou changement des poids n'entre dans ce lot.

| ID | Constat avant correction | Hypothèse et contrôle discriminant |
|---|---|---|
| I3-F01 | `retrieval.py` déduplique au parent ; `expand_parent` refuse un parent trop long. Deux passages distincts peuvent devenir un seul. | Dédupliquer les preuves réellement identiques, conserver les passages disjoints dans le cap ; deux faits conservés sur deux. |
| I3-F02 | `evidence_selection.py` peut garder une ligne de tableau et perdre sa note `(1)` ; méthodes d'extraction non recalculées après ajout d'un titre OCR. | Conserver les dépendances de la ligne autorisées, signaler une note manquante, unir la provenance des blocs retenus. |
| I3-F03 | Avertissement de couverture partielle lié aux seuls résultats retenus. | Signaler une extraction incomplète du périmètre même sans résultat ; ne pas affirmer une absence dans l'original. |
| I3-F04 | Contre-exemples exécutés : condition demandée 85 °C/source 25 °C ; négation ; maximum demandé/typique ; même objet à valeurs divergentes dans deux documents ; conditions en préfixe ignorées. | Contrôler rôle, polarité, condition et identité de l'objet avant d'établir la couverture ; garder les citations contradictoires sans choisir arbitrairement. |
| I3-F05 | Plans par IDs déjà présents ; suivi pré/post incomplet et chemins d'erreur encore coûteux. | Registre de preuves avant génération, validation du plan et des segments rendus, routes déterministes pour relations explicitement vérifiables, aucun texte libre du modèle publié. |
| I3-F06 | L'identité du modèle vérifie nom/digest/quantification ; la taille 4B doit être une contrainte exécutable du profil actif. | Refuser une identité incompatible avant tout envoi documentaire ; conserver le verrou 4B. |

Les rapports I1/I2 constituent des observations historiques, jamais le bras
temporel de cette étude. L'état de référence courant est exécuté sur un worktree
immuable du commit ci-dessus. Les défauts et contrôles positifs sont enregistrés
avec questions, sources et verdicts avant correction.

## Definition of Done I3

| Critère | Acceptation fixée avant les essais |
|---|---|
| I3-D01 — références et portée | Zéro ID inconnu, citation fabriquée, unité empruntée hors portée ou segment génératif libre publié dans les essais adversaires ; 100 % des citations publiées rattachables à leurs preuves/version/positions disponibles. |
| I3-D02 — relations | Les cinq défauts F04 sont détectés ; contrôles positifs correspondants conservés. Condition absente/incomparable reste inconnue. Un désaccord n'est pas une preuve que l'une des sources est vraie. |
| I3-D03 — conservation | Deux passages disjoints d'un parent long conservés ; note applicable dans le scope conservée ; provenance OCR mixte et couverture partielle visibles. Aucun dépassement silencieux des plafonds. |
| I3-D04 — réponse utile | Matrice contrôlée préalable : au moins 12 cas répondables et 12 limites, oracles figés avant sorties. Tous les positifs doivent rester utiles ; un refus ou une erreur sur un positif est un échec. Résultats par famille et dénominateur, aucune moyenne avec les tests logiciels. |
| I3-D05 — calculs et restitution | Calcul déterministe traçable (entrées, unités, opération, références), division nulle/formule sans cache/unité absente refusées ; vérification finale avant événements publics. |
| I3-D06 — reproductibilité | Même corpus, mêmes paramètres et versions explicites ; empreintes des entrées, code et sorties ; deux révisions réellement distinctes. Latence et mémoire des doubles rapportées comme telles, séparées du 4B natif. |
| I3-D07 — non-régression | Tests ciblés puis suite portable, intégrations pertinentes, Ruff, Mypy, contrats HTTP ; échecs préexistants et indisponibilités conservés. Pas de modification cosmétique des assertions pour obtenir du vert. |
| I3-D08 — essais natifs | Sous-ensemble réel PDF/Office→recherche→réponse avec modèle 4B verrouillé si provisionnement possible ; génération effective et routes sans modèle distinguées. Objectif zéro sortie non étayée, zéro erreur et aucune baisse de couverture sur les paires répondables. Toute non-exécution laisse ce critère ouvert. |
| I3-D09 — livraison | Documentation, résultats bruts compacts, limites, commandes ; commit et push sans force sur `enhanced_version`, SHA et arbre distants vérifiés. |

## Configuration et mesures

Le verrou `config/enhanced-4b.lock.json` fixe Qwen3-4B, Q4_K_M,
GGUF SHA-256 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`,
Ollama 0.35.0 et tokenizer officiel. Référence : contexte 8192, température 0,2,
top_p 0,9, seed 0, `think=false`, KV q8_0, maximum quatre threads, CPU imposé.
E5-small INT8 et Qdrant 1.19.1 restent les composants de recherche natifs.
Les tests de composants peuvent injecter des doubles explicitement nommés ; ils
ne qualifient ni embeddings, ni LLM, ni performance cible.

Environnement actuel : Linux x86-64, Python 3.12.14, 10 451 423 232 octets de RAM,
neuf CPU logiques visibles, aucun swap. Dépendances installées avec
`uv sync --frozen --group dev`. L'inventaire exact sera joint aux résultats.
Ce n'est pas une recette du poste Windows ni une preuve sur tous les CPU.

Mesures séparées : rappel des preuves retrouvées et réellement retenues,
couverture des faits requis, exactitude des références, absence de prose ajoutée,
refus justifiés, sur-refus, erreurs, durée par phase, pic RSS/PSS/USS lorsque
disponible. Les erreurs restent au dénominateur. Le silence n'est pas un succès.
Le benchmark contrôlé publie les observations individuelles ; son oracle n'est
pas dérivé du statut du contrat qu'il évalue.

## Ordre et isolement des essais

1. Figer protocole, révision et cas ; exécuter les reproductions et la référence.
2. Corriger indépendamment conservation documentaire et relations/restitution.
3. Rejouer mêmes cas sur les deux révisions, avec fichiers/SQLite isolés ; mesurer
   les gains/pertes appariés. Les ablations utilisent les frontières réelles
   (candidats, contexte, registre, rendu), pas un changement du modèle.
4. Exécuter les contrôles de non-régression pertinents puis les essais natifs
   séquentiellement. Ne pas concurrencer les charges lourdes pendant une mesure.
5. Documenter PASS/FAIL/BLOCKED/NOT_RUN ; publier le code même avec des limites
   explicitement ouvertes, sans transformer une implémentation en qualification.

Les nouveaux cas découverts après gel sont des régressions supplémentaires,
identifiées séparément ; ils ne remplacent pas les cas initiaux. Les gros poids,
originaux téléchargés et traces runtime restent hors Git. Les fixtures publiques
synthétiques et résultats compacts peuvent être versionnés.

## Sources de méthode

- [Ollama, Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs),
  consulté le 08/11/2026 : format JSON Schema et validation côté client ; cela ne prouve pas la vérité des données.
- [Gao et al., ALCE, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.398/) :
  séparer exactitude et qualité des citations ; aucun score publié transféré ici.
- [Joren et al., Sufficient Context, v3](https://arxiv.org/abs/2411.06037) :
  séparer insuffisance documentaire et mauvaise exploitation du contexte ; contrôles bornés dans ce produit.
- Document de pistes joint par l'utilisateur et rapports I1/I2 du dépôt :
  conservation valeur–grandeur–unité–condition, suivi des pertes et coût/abstention.
