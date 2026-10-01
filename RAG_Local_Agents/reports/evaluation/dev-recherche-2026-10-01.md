# Évaluation de la recherche sur le jeu DEV synthétique — 1er octobre 2026

**Rôle :** rapport d'essai du lot R7 (documentation vivante) : recherche et contexte, sans modèle, sur les 100 questions du jeu de développement V2.1. **Statut :** mesure exécutée, partie génération non faite. **Date :** 1er octobre 2026, 07:06 UTC. **Code :** commit `a604a76` (plafond OCR de [W016](../../DECISIONS.md#w016-plafond-de-rendu-dune-région-ocr-porté-à-13-millions-de-pixels) compris). **Preuve :** [résumé versionné](../backend/2026-10-01-development-retrieval-summary.json) ; le rapport complet (72,8 Mo) reste hors Git sous `.runtime/evals/qualification-v2.1/`, son empreinte figure dans le résumé.

## Méthode

1. Instance isolée neuve (`tools/qualification/e2e_instance.py`), profil livré : import des 7 documents pneumatiques du jeu DEV (`fixtures/qualification-v2.1/development/`, dont un scan, un document mixte et un document à deux colonnes) par `tools/corpus/import_folder.py`.
2. Extractions terminées en 12 minutes ; DA-P02 (scan) et DA-P03 (paragraphe natif et table scannée) en extraction partielle, publiées explicitement, comme le ferait l'utilisateur.
3. Liaisons capturées par document (`capture_bindings.py`, `--allow-published-partial` pour les deux partiels), fusionnées (`merge_bindings.py`), puis annotations résolues sur le texte réellement extrait (`resolve.py`) : 94 questions sur 100 résolues.
4. Évaluation par `python -m services.api.qualification --split development` : chaque question passe par `POST /api/v1/admin/evaluation/context` (recherche hybride, assemblage du contexte, aucun appel au modèle).

Les 6 questions non résolues le sont par de vraies erreurs d'OCR que le résolveur refuse de rapprocher par conjecture : sur le scan DA-P02, « ± 3.0 % » lu « + 3.0 % » (4 questions) et « 14 N·m » lu « 14 N-m » (1 question) ; sur DA-P03, une ligne du tableau scanné dont l'association des cellules n'est pas établie (1 question).

## Résultats

| Mesure | Résultat | Dénominateur |
|---|---|---|
| Unités de preuve dans les 5 premiers résultats | 83 | 83 unités, 74 questions répondables évaluées |
| Unités de preuve dans le contexte assemblé | 83 | 83 unités |
| Questions dont toutes les preuves sont dans le contexte | 74 (IC 95 % de Wilson : 95,1 % à 100 %) | 74 |
| MRR@10 (rang de la première preuve) | 0,955 | 74 questions |
| Questions sans fuite de périmètre | 94 (IC 95 % : 96,1 % à 100 %) | 94 évaluées, 0 passage hors périmètre |

| Catégorie | Demandées | Évaluées | Non résolues | Preuves au top 5 |
|---|---|---|---|---|
| Factuelles FR/EN | 35 | 33 | 2 | 33/33 |
| Identifiants techniques | 15 | 14 | 1 | 14/14 |
| Tableaux et unités | 12 | 11 | 1 | 11/11 |
| Comparaisons | 10 | 9 | 1 | 18/18 |
| Relances de conversation | 8 | 7 | 1 | 7/7 |
| Sans réponse dans le périmètre | 20 | 20 | 0 | sans objet |

## Lecture critique

- Le jeu DEV est synthétique, à petits documents (2 pages) et à valeurs contrôlées : un rappel de 100 % y montre que la chaîne ne perd pas de preuve sur des cas propres, pas qu'elle tiendrait sur le corpus réel, où la série W014 mesure 61 pages sur 72 dans le contexte du document visé ([rapport du corpus réel](corpus-reel-2026-09-30.md)).
- Les 6 questions écartées sont toutes sur les documents scannés : la limite principale est l'OCR, avant la recherche ; elles sont exclues des pourcentages, qui ne valent donc pas PASS (statut `INCOMPLETE`).
- Les 20 questions sans réponse ne mesurent ici que l'absence de fuite de périmètre ; l'abstention correcte se juge sur les réponses générées.
- Le jeu final scellé n'a pas été ouvert ; son exécution unique appartient à la recette finale (R13).

## Suite

Génération des 100 réponses DEV (`answers.py`) et grille D05 (`grade.py`) : plusieurs heures de génération réelle, l'instance principale étant arrêtée pendant l'essai faute de mémoire pour deux instances et un modèle chargé.
