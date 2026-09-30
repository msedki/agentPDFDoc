# Évaluation de la recherche sur le corpus réel — séries 1 et 2

**Rôle :** rapport de mesure et d'analyse du lot R21 (documentation vivante). **Statut :** mesures exécutées ; diagnostic et premier essai d'amélioration ajoutés à 22:35 UTC (non adopté) ; génération des réponses non mesurée. **Date :** 30 septembre 2026, 21:25 UTC. **Base :** instance principale `c4016e9a…` sur le code du commit `ed26508` augmenté des corrections non commitées de 20:41–21:10 (résultat de worker périmé, découpes OCR bornées à la page) ; protocole [W013](../../DECISIONS.md) ; méthode et sources : [evaluation-methodology-sources-2026-09-30.md](../evaluation-methodology-sources-2026-09-30.md).

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

## Diagnostic des pertes et premier essai (22:20–22:35 UTC)

Rangs relus par branche sur une image SQLite figée de l'instance et sa collection Qdrant, sans texte affiché (scripts de diagnostic hors dépôt, sorties sous `.runtime/evals/`) :

- 9 pertes sur 10 : le bloc attendu est absent du top 24 lexical (rang 12 à 203 sans limite), alors que la branche dense le classe 1er dans 4 cas et dans son top 24 pour 9 cas sur 10. La fusion RRF le relègue alors aux rangs 7 à 10.
- Cause 1, mots de la question : la requête FTS5 est un `OR` de tous les mots ; « quelle » (3 chunks sur l'index) et « valeur » (7 chunks) sont rares dans ce corpus procédural, donc fortement pondérés par BM25, et attirent des chunks sans rapport.
- Cause 2, taille des chunks : le découpage actuel (`codepoint-block-v1`) coupe chaque bloc à 320 tokens mais ne regroupe jamais les blocs courts : 13 à 41 tokens E5 en moyenne selon le document, un parent par chunk. La normalisation de longueur de BM25 pénalise alors les blocs attendus, plus longs (240 à 1 031 caractères contre 77 en moyenne). La spécification demande une « cible 320 tokens » aux frontières structurelles ([SPEC_ARCHITECTURE.md](../../SPEC_ARCHITECTURE.md), découpage) : écart constaté.
- Cause 3, propre à l'outil : quelques mots porteurs n'ont aucune occurrence dans l'index ; l'expression régulière des gabarits ignorait les lettres hors Latin-1 (« œ » par exemple) et coupait le mot. Corrigé à 23:53 (commit `6682ef0`, lettres Unicode, test sur « manœuvre ») ; les jeux déjà construits restent figés par leur empreinte, une nouvelle construction avec la même graine peut donc différer.

Essai apparié ([série 2](ev1-mots-outils-serie2-20260930T2225.json), [série 3](ev1-mots-outils-serie3-20260930T2233.json), agrégats et identifiants seulement) : retirer de la requête FTS5 les mots-outils déjà listés dans `STOPWORDS` (`services/api/retrieval.py`), repli sur la requête complète si rien ne reste ; même chaîne que la route d'évaluation, exécutée en processus (elle reproduit exactement la série 2 de référence : 157/160, 150/160, MRR 0,8315).

| Série | Contexte, référence | Contexte, sans mots-outils | Gagnées / perdues | McNemar exact |
|---|---|---|---|---|
| 2 (180 questions, source du diagnostic) | 150/160 | 155/160 | 5 / 0 | p = 0,0625 |
| 3 (82 questions neuves, graine 20261001, blocs et identifiants des séries 1 et 2 exclus) | 52/52 | 51/52 | 0 / 1 (une question de référence passée du rang 6 au rang 8) | p = 1 |
| Cumul | — | — | 5 / 1 | p = 0,22 |

Décision : changement non adopté. L'effet va dans le bon sens sur les questions courtes mais n'est pas établi, et la série de confirmation, faute de questions de valeur neuves (4 seulement après exclusion), manque de puissance. À remesurer sur le corpus complet, et après la correction du découpage, qui agit sur la même cause de classement.

## Jeu de référence établi par lecture intégrale (W014) — mesure A

85 questions rédigées après lecture complète des 4 documents (CPR-07A 30, MR2_30A 30, essais MIGBT 19, en italien, Evaluation module4 6), au schéma V2.1, dont 72 avec réponse et 13 sans réponse vérifiée ; jeu sous `.runtime/evals/annotated-v1/`, non validé par un expert. Rattachement automatique des 139 extraits exacts (`tools/qualification/annotated_eval.py resolve`) : 93 exacts, 8 à cheval sur deux blocs, 21 approchés sur la page annoncée, 17 non rattachés ; 64 questions sur 72 rattachées au bloc, les 8 autres mesurées à la page. Mesure du 30/09 à 23:09 UTC, extraction et découpage en service à cette heure ([rapport](annotated-v1-reference-20260930T2310.json)) :

| Périmètre | Page au top 10 | Page dans le contexte | Bloc dans le contexte |
|---|---|---|---|
| Document de la question | 61/72 [0,747 ; 0,912] | 59/72 [0,715 ; 0,891] | 47/64 [0,615 ; 0,827] |
| Toute la bibliothèque | 50/72 [0,580 ; 0,789] | 47/72 [0,538 ; 0,752] | 37/64 [0,456 ; 0,691] |

Par difficulté (document, page dans le contexte) : directes 22/24, paraphrases 16/17, sur plusieurs pages 4/5, tableaux 17/24, pages images 0/2. Sur toute la bibliothèque, les tableaux tombent à 10/24. Les séries générées (150/160) surestimaient donc nettement la recherche réelle : elles reprenaient les mots du bloc.

Causes établies pendant le rattachement, en lecture seule sur la base :
- **Pages sans texte extrait** : MR2_30A pages 18, 19 et 27 en erreur dans l'extraction active, antérieure au correctif des découpes ; 3 questions ne peuvent pas trouver leur preuve avant réextraction.
- **Perte silencieuse de la voie `structured`** : la couche texte du PDF compte 1 066 et 239 caractères alphanumériques sur MR2_30A pages 7 et 8, 1 162 et 1 125 sur CPR-07A pages 8 et 9 ; les blocs extraits en gardent 8, 13, 73 et 43. Le contrôle de couverture à 95 % ne s'applique qu'à la voie `native` (`services/ingestion/pipeline.py:82-91,162-166`), si bien que ces pages ne déclarent aucune limite et que le document ne signale pas cette perte. Couverture de la couche texte sur l'ensemble : CPR-07A 0,887, MR2_30A 0,917, MIGBT et Evaluation module4 1,0.

## Améliorations proposées, par ordre de preuve attendue

| Id | Hypothèse | Expérience appariée | Coût à surveiller |
|---|---|---|---|
| EV-1 | Regrouper les blocs courts d'une même section jusqu'à la cible de 320 tokens, comme le demande la spécification, rend la branche lexicale comparable entre blocs et fait entrer les blocs attendus dans les 6 fragments | Découpage révisé (nouvelle révision de chunker, réindexation des 4 documents), séries 2 et 3 rejouées, test exact apparié sur « contexte » ; contrôle des citations au bloc et du filtrage par page | Réindexation complète ; les sources d'un chunk deviennent multiples (table `chunk_sources` déjà prévue pour) ; découpe au périmètre avant contexte pour une sélection partielle. Écartés : 8 fragments au lieu de 6 (la spécification fixe « au plus six fragments par défaut », [SPEC_ARCHITECTURE.md](../../SPEC_ARCHITECTURE.md), recherche) et reranker neuronal (hors périmètre sans preuve de valeur ni requalification CPU/RAM, même document, exclusions) |
| EV-2 | Des questions en langage courant sans réponse mesurent l'abstention réelle | Gabarits sans identifiant sur des notions absentes du corpus, vérifiées par recherche plein texte | Vérification manuelle de l'absence |
| EV-3 | Une série de génération sur 20 questions de développement mesure exactitude et citations | `tools/qualification/answers.py` sur un créneau réservé | Environ 40 min de CPU, mémoire (W007) |
| EV-4 | Le corpus complet change la difficulté de la recherche à l'échelle de la bibliothèque | Même protocole après extraction des 61 documents en pause | Durée d'extraction (≈ 22 000 pages) |

Chaque expérience compare une seule configuration à la référence sur les mêmes questions (protocole §3.1) ; aucune n'est lancée sans créneau libre sur le poste.
