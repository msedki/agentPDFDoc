# Évaluation question-réponse sur le corpus réel du poste Linux — recherche et contexte

**Rôle :** rapport de mesure du lot J10 (documentation vivante, décision [W020](../../DECISIONS.md#w020-évaluation-question-réponse-sur-le-corpus-réel-du-poste-linux-pdfmgv-pdftest)). **Statut :** recherche et contexte mesurés le 1er octobre 2026 à 20:36 UTC ; génération par le modèle non encore mesurée. **Poste :** Jetson AGX Orin Developer Kit, Linux aarch64 (Ubuntu 20.04.6, `MODE_30W`), instance réelle lancée par `./rag.sh up`, code de l'arbre de travail postérieur au commit `4ec5592`. **Annotation :** `ASSISTANT_READ_NOT_EXPERT_VALIDATED`.

## Ce qui a été mesuré

La capacité de la chaîne de recherche (FTS5, E5, fusion RRF, couverture des identifiants, budget de contexte) à ramener, pour une question de métier rédigée par lecture intégrale du document, le bloc et la page qui portent la réponse attendue, puis à les placer dans le contexte transmis au modèle. Aucun appel au modèle : route `POST /api/v1/admin/evaluation/context`.

| Élément | Valeur |
|---|---|
| Corpus | `PDF/` du poste (hors Git) : 4 documents réels, 208 pages avec couche texte |
| Extraction | `MGV-B.1` (56 pages) et `MGV-D.0` (140 pages) en `ready_partial` (écrans en grille de caractères, figures, orientation OCR non résolue) publiés explicitement pour l'évaluation, réversible par réindexation ; `modelcards` `ready` (10 pages) ; `ePMO` (2 pages A3) sans aucun texte extrait, non publié |
| Jeu | 105 questions rédigées par lecture intégrale des PDF, chacune revérifiée contre le PDF par un second agent (20 corrections, 23 doutes consignés) ; 6 catégories du projet ; 83 répondables, 22 sans réponse ; conservé sous `.runtime/evals/annotated-linux-v1/` (texte du corpus, hors Git) |
| Séparation | développement : `MGV/` (66 questions, 52 répondables) ; tenu à l'écart : `TEST/` (39 questions, 31 répondables) |
| Outil | `tools/qualification/annotated_eval.py` (`resolve`, `run`) |
| Rattachement des extraits | développement : 52/52 questions répondables rattachées à leurs blocs (86 extraits exacts, 1 à cheval sur deux blocs, 4 approchés) ; tenu à l'écart : 17/31 (`modelcards` 17/19, `ePMO` 0/12) |
| Rapports agrégés | [développement](corpus-linux-2026-10-01-recherche-dev.json), [tenu à l'écart](corpus-linux-2026-10-01-recherche-test.json) : identifiants et agrégats seulement (contrôle : aucun texte de question, de réponse attendue ou d'extrait) |

## Résultats

Intervalles de Wilson à 95 %. « Bloc » : le bloc attendu ; « Contexte » : il figure parmi les sources envoyées au modèle. Périmètre « document » : la question est posée sur son document ; « bibliothèque » : sur toute la bibliothèque publiée.

| Jeu, périmètre | Questions | Bloc au top 10 | Bloc dans le contexte | MRR@10 (bloc) | Page au top 10 |
|---|---:|---|---|---:|---|
| Développement, document | 52 | 44/52 = 0,846 [0,725 ; 0,920] | 39/52 = 0,750 [0,618 ; 0,848] | 0,652 | 45/52 = 0,865 [0,747 ; 0,933] |
| Développement, bibliothèque | 52 | 43/52 = 0,827 [0,703 ; 0,906] | 37/52 = 0,712 [0,577 ; 0,817] | 0,567 | 43/52 = 0,827 |
| Tenu à l'écart, document (`modelcards`) | 17 | 16/17 = 0,941 [0,730 ; 0,990] | 14/17 = 0,824 [0,590 ; 0,938] | 0,599 | 18/19 = 0,947 (avec les 2 questions rattachées à la page seulement) |
| Tenu à l'écart, bibliothèque (avec `ePMO`) | 31 | — | — | — | 18/31 = 0,581 [0,408 ; 0,736] |

Pour `ePMO`, les 12 questions répondables échouent toutes : en périmètre document, la requête est refusée faute de document publié (`no_document_in_scope`) ; en périmètre bibliothèque, aucune page de ce document n'est indexée.

### Par catégorie (développement, périmètre document)

| Catégorie | Bloc au top 10 | Contexte |
|---|---|---|
| `factual_fr_en` | 20/21 | 20/21 |
| `technical_identifiers` | 8/10 | 8/10 |
| `tables_units` | 6/9 | 4/9 |
| `comparison` | 7/7 | 5/7 |
| `conversation_followup` | 3/5 | 2/5 |

Tenu à l'écart (`modelcards`) : factuel 8/8, identifiants 2/2, tableaux 2/2, comparaison 3/3, suivi 1/2 au top 10.

Questions manquées au top 10 (développement) : `mgv-b1-q19` (tableau), `mgv-d0-q09` (factuel), `mgv-d0-q14` et `mgv-d0-q17` (identifiants), `mgv-d0-q21` et `mgv-d0-q22` (tableaux), `mgv-d0-q28` et `mgv-d0-q30` (suivis) ; tenu à l'écart : `modelcards-q18` (suivi). Les questions de suivi reçoivent la question précédente (`prior_user_question`), comme dans une conversation : leurs échecs sont réels.

## Lecture

- **Questions factuelles :** 28/29 au top 10 sur les deux jeux ; la chaîne retrouve le passage d'une question rédigée sans recopier le texte.
- **Tableaux et unités :** point faible (développement 6/9 au top 10, 4/9 dans le contexte). Les vérificateurs ont noté que, dans la couche texte de ces documents, les marques de cellules ne sont pas rattachées à leurs colonnes (pages 29 et 31 de `MGV-B.1`) ; l'effet de l'extraction des tableaux sur la recherche reste à diagnostiquer bloc par bloc.
- **Questions de suivi :** 4/7 au top 10 sur les deux jeux ; la reformulation d'une question elliptique est à analyser sur ces cas.
- **`ePMO` :** limite d'extraction, pas de recherche : pages A3 au-delà du plafond de rendu, couche texte native perdue (point à trancher 8 du plan).
- **Objectif D04 :** l'objectif de recall à 10 de 0,90 se mesure sur le jeu final de qualification ; sur ce corpus réel, le développement est à 0,846 et l'intervalle du jeu tenu à l'écart (17 questions) est trop large pour conclure.

## Limites

Petits effectifs (52 et 17 questions rattachées) ; jeu rédigé et vérifié par l'assistant, non relu par un expert métier (point à trancher 2) ; deux documents publiés en extraction partielle ; une seule exécution ; mesures sur ce poste aarch64, qui ne valent pas pour le poste Windows. La génération (justesse des réponses, citations, abstention) est mesurée séparément.
