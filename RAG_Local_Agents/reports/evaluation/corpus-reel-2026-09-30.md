# Évaluation de la recherche sur le corpus réel — séries 1 et 2

**Rôle :** rapport de mesure et d'analyse du lot R21 (documentation vivante). **Statut :** mesures exécutées ; génération des réponses non mesurée. **Date :** 30 septembre 2026, 21:25 UTC. **Base :** instance principale `c4016e9a…` sur le code du commit `ed26508` augmenté des corrections non commitées de 20:41–21:10 (résultat de worker périmé, découpes OCR bornées à la page) ; protocole [W013](../../DECISIONS.md) ; méthode et sources : [evaluation-methodology-sources-2026-09-30.md](../evaluation-methodology-sources-2026-09-30.md).

## Ce qui a été mesuré

La capacité de la chaîne de recherche (FTS5 + E5 + fusion RRF + couverture des identifiants + budget de contexte) à ramener le bloc d'où une question a été tirée, et à s'abstenir quand la réponse n'existe pas dans le périmètre. Aucun appel au modèle de réponse : `POST /api/v1/admin/evaluation/context` renvoie le top 10 fusionné, la liste finale et les sources réellement sérialisées pour le modèle.

| Élément | Valeur |
|---|---|
| Documents | 4 documents du corpus `PDF/` publiés (dont 3 extractions partielles publiées explicitement pour l'évaluation), fixture synthétique exclue |
| Blocs lus | 1 162 |
| Outil | `tools/qualification/corpus_eval.py` (tests : `tests/unit/test_qualification_corpus_eval.py`, 12) |
| Jeux | série 1 : 80 questions, empreinte `dac025e5…` ; série 2 : 180 questions, empreinte `7f17470b…` ; conservés sous `.runtime/evals/corpus-reel/` (texte du corpus, hors Git) |
| Rapports agrégés | [série 1](corpus-reel-20260930T211831Z-serie1.json), [série 2](corpus-reel-20260930T212256Z-serie2.json) : identifiants et agrégats seulement |

## Résultats

Intervalles de Wilson à 95 %. « Contexte » = le bloc attendu (ou une alternative déclarée) figure parmi les sources envoyées au modèle.

| Série, variante | Questions | Success@10 | Contexte | MRR@10 |
|---|---:|---|---|---|
| 1, référence (périmètre = document d'origine) | 60 | 60/60 [0,940 ; 1] | 59/60 [0,911 ; 0,997] | 0,911 |
| 2, référence | 60 | 60/60 | 59/60 | — |
| 2, toute la bibliothèque | 60 | 60/60 | 59/60 | — |
| 2, indices réduits (3 mots porteurs) | 40 | 37/40 [0,801 ; 0,974] | 32/40 [0,652 ; 0,895] | — |
| 2, ensemble répondable | 160 | 157/160 [0,946 ; 0,994] | 150/160 [0,889 ; 0,966] | 0,832 |
| 1 et 2, abstention de recherche (hors périmètre, sans réponse) | 20 | 20/20 [0,839 ; 1] | — | — |
| 1 et 2, fuite de périmètre | 20 | 0 | — | — |

Par voie d'extraction (série 2) : pages OCR 10/10, pages structurées 147/150 au top 10 et 140/150 dans le contexte. Par catégorie : identifiants 40/40, valeurs 117/120 au top 10 et 110/120 dans le contexte. Par partition : développement 101/106 et questions tenues à l'écart 49/54 dans le contexte, écart compatible avec le hasard à ces effectifs.

Les 10 questions répondables perdues dans la série 2 se répartissent ainsi (rangs lus dans les lignes du rapport) :

| Cause | Questions | Rang du bloc attendu |
|---|---:|---|
| Absent du top 10 | 3, toutes à indices réduits | — |
| Au top 10 mais au-delà des 6 fragments de la liste finale | 6 (4 à indices réduits, 1 de référence, sa variante bibliothèque) | 7 à 10 |
| Dans la liste finale mais écarté par le budget de preuve (1 536 tokens en mode factuel) | 1, à indices réduits | 3 |

## Analyse critique

1. **Les scores de référence sont une borne haute.** Les questions reprennent les mots du bloc, et celles d'identifiant contiennent le code exact, que la couverture forcée des identifiants garantit par construction. 60/60 mesure la retrouvabilité d'un bloc à partir de ses propres mots, pas la recherche d'un utilisateur.
2. **Le levier réel est le classement, pas le rappel.** Avec des indices réduits, le bloc est encore au top 10 dans 37 cas sur 40, mais n'entre dans le contexte que 32 fois. Sur l'ensemble, 7 des 10 pertes concernent un bloc bien retrouvé et mal classé (rangs 7 à 10) ou coupé par le budget de preuve ; seules 3 sont des échecs de recherche. La mesure au seul top 10 aurait masqué cette distinction.
3. **L'élargissement du périmètre ne coûte rien ici**, mais le corpus ne compte que 4 documents : ce résultat ne vaut pas pour les 65 documents une fois extraits.
4. **Les questions sans réponse et hors périmètre sont toutes détectées au stade de la recherche**, car elles portent sur des identifiants ; une question sans réponse formulée en langage courant n'est pas encore testée.
5. **Défauts de l'outil relevés et corrigés entre les séries :** recouvrement lexical faussé par les mots des gabarits ; gabarit « sujet est de valeur » sans aucune occurrence dans ce corpus procédural (0/1 162 blocs), remplacé par un gabarit sur les mots précédant la valeur ; pages OCR absentes (1/60) avant l'ajout d'un quota ; terciles de recouvrement confondus (bornes 1,0 et 1,0), remplacés par des tranches fixes (faible < 0,5 ≤ partiel < 1 = complet) recalculées sur les lignes existantes (`corpus_eval.py reaggregate`). Constat qui en découle : les 10 pertes de la série 2 sont toutes dans la tranche « complet » (118/128 dans le contexte, contre 32/32 pour les deux autres). Les questions courtes reprennent tous leurs mots porteurs mais en donnent trop peu pour distinguer le bloc ; le nombre de mots porteurs, et non leur proportion, décrit la difficulté. Le recouvrement de la série 1 garde l'ancienne définition (mots des gabarits inclus) et ne se compare pas.
6. **Non mesuré :** exactitude des réponses, fidélité, citations et abstention du modèle, qui exigent une génération par question (environ 2 min par question sur ce poste, créneaux sans utilisateur) ; validité métier (aucune question d'expert).

## Améliorations proposées, par ordre de preuve attendue

| Id | Hypothèse | Expérience appariée | Coût à surveiller |
|---|---|---|---|
| EV-1 | Les 6 blocs classés 7e à 10e perdent sur une seule branche (lexicale ou dense) ; corriger le classement de cette branche pour les requêtes courtes les fait entrer dans les 6 fragments | Relever, sans texte, le rang de chaque branche pour les 10 pertes, puis une seule modification du classement rejouée sur la série 2, test exact apparié sur « contexte » | Porter la liste à 8 fragments est exclu : la spécification fixe « au plus six fragments par défaut » ([SPEC_ARCHITECTURE.md](../../SPEC_ARCHITECTURE.md), recherche) ; un reranker neuronal est hors périmètre sans preuve de valeur et requalification CPU/RAM (même document, exclusions) |
| EV-2 | Des questions en langage courant sans réponse mesurent l'abstention réelle | Gabarits sans identifiant sur des notions absentes du corpus, vérifiées par recherche plein texte | Vérification manuelle de l'absence |
| EV-3 | Une série de génération sur 20 questions de développement mesure exactitude et citations | `tools/qualification/answers.py` sur un créneau réservé | Environ 40 min de CPU, mémoire (W007) |
| EV-4 | Le corpus complet change la difficulté de la recherche à l'échelle de la bibliothèque | Même protocole après extraction des 61 documents en pause | Durée d'extraction (≈ 22 000 pages) |

Chaque expérience compare une seule configuration à la référence sur les mêmes questions (protocole §3.1) ; aucune n'est lancée sans créneau libre sur le poste.
