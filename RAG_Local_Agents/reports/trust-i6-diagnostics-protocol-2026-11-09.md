# I6R-06 — diagnostics, portée des qualificatifs et preuve du rendu

**Rôle :** protocole du complément aux constats natifs I6 v2.
**Propriétaire :** intégration et qualification RAG.
**Statut :** critères définis avant évaluation ; résultats à produire.
**Date de session :** 9 novembre 2026 (UTC).
**Référence :** `0574f4e21ccaf95b25a48c6e226369376681ac18`.

## Périmètre et hypothèses

Les résultats de la campagne [native v2](trust-i6-native-v2-2026-11-09.md)
restent figés. Ce complément traite quatre défauts observés : condition
commune ajoutée dans les diagnostics de conflit D45/D48, propriété manquante
non nommée dans six suppléments, propriété empruntée à une autre proposition
dans D28, rôle emprunté dans D32. Il conserve aussi le contenu du registre
des segments rendus, dont seule l'empreinte était disponible dans les
captures précédentes.

Trois lots indépendants sont autorisés :

1. **I6R-06a :** les diagnostics déterministes décrivent les obligations
   effectivement non couvertes. Ils n'ajoutent aucune condition commune,
   ne déclarent pas une absence dans tout le document et n'arbitrent pas
   entre sources concurrentes.
2. **I6R-06b :** les qualificatifs lexicaux d'une mesure restent locaux à
   son prédicat, tandis que la négation, les dépendances, les conditions et
   l'extrait intégral conservent leur portée. Une limite de parsing demeure
   une limite, sans relation positive déduite d'une proposition niée.
3. **I6R-06c :** une trace distincte conserve le registre effectivement
   rendu après sa vérification. Elle lie segments, texte et catalogue par
   leurs empreintes, selon les modes de confidentialité existants. Cette
   vérification structurelle ne prouve pas une justesse sémantique générale.

Le modèle reste Qwen3-4B Q4_K_M, sans nouveau modèle ni dépendance. Les
budgets, seuils de ressources, règles de scope, citations et droits d'accès
restent ceux de la référence. Les sources primaires ConjNLI et FActScore,
déjà enregistrées pour I6, ont été consultées de nouveau : elles motivent
respectivement les contre-exemples de coordination et la vérification
atomique des énoncés ; elles ne valident pas notre grammaire ou notre CPU.

## Jeux et séparation

Les régressions publiées I5-PJ/I6 et les nouvelles reproductions servent au
développement. Un évaluateur distinct prépare un nouveau **I6R06-F48**,
avec 24 cas positifs et 24 limites/négatifs FR/EN, familles documentaires
disjointes du développement. Les textes, offsets, valeurs, relations,
qualificatifs et diagnostics attendus sont annotés avant exécution.
Le manifeste et les empreintes sont conservés hors de l'arbre produit ;
seuls les comptes et empreintes sont visibles aux auteurs avant le gel.

Ce nouveau jeu ne remplace pas le FINAL48 historique introuvable. Aucun
score n'est attribué à ce dernier. I6R06-F48 est ouvert uniquement après
gel du code et de l'évaluateur. Tous les résultats sont conservés ; aucun
réglage produit, oracle ou seuil n'est effectué après ouverture. Les
nouveaux défauts éventuels restent des résultats de ce candidat.

Comparateurs : référence publiée exacte et candidat, mêmes entrées et
budgets. Les mesures du contrat utilisent le catalogue/rendu applicatifs
et le double de tokenisation déclaré du banc existant ; ce ne sont ni
des mesures de recherche documentaire ni des inférences 4B.

## Critères préalables

| ID | Critère et preuve attendue |
|---|---|
| DIAG-01 | Aucun diagnostic n'affirme une condition non établie ; les obligations manquantes sont nommées, bornées au contexte retenu et à leurs sujets/documents lorsqu'ils sont distincts |
| DIAG-02 | Aucun qualificatif d'une autre mesure n'est attribué à la relation locale ; négations, dépendances et extraits intégraux conservés, y compris pour les relations rejetées |
| DIAG-03 | Aucun nouveau faux appui ni opérande interdit sur les cas annotés ; littéraux, identités, offsets, citations et vérification du registre conservés |
| DIAG-04 | Registre rendu persisté après validation, empreintes recalculables ; absence de contenu documentaire dans les traces hashes/off et de registre certifié après refus de validation du rendu |
| DIAG-05 | Tests ciblés, suite portable applicable, Ruff et Mypy sans régression ; chaque résultat historique et chaque limitation distingués |
| DIAG-06 | Nouveau final gelé et indépendant, 48 cas conservés, référence/candidat comparés ; aucune adaptation après ouverture |
| DIAG-07 | Vérification native appariée et HTTP/SSE, identités 4B réelles quand le modèle est appelé, citations persistantes et arrêts des seuls processus possédés |
| DIAG-08 | Chaque lot substantiel vérifié committé puis publié sans force sur enhanced_version ; parent, arbre et tête distante vérifiés ; documentation tenue à jour |

Le registre atteste la validation structurelle du rendu capturé. Une
annulation ou une erreur peut encore survenir ensuite : sa publication
effective exige aussi le terminal confirmé et le texte persisté concordants.

La vérification native est distincte du final contractuel : six positions
connues N_I6D28, N_I6D32, N_I6D33, N_I6D35, N_I6D45, N_I6D48 et deux
témoins de sélection RX742/KX563 par bras. Deux parcours HTTP par bras
contrôlent la route de conflit sans modèle et la sélection HX864 avec 4B.
Ces dix positions par bras sont des régressions connues, pas des documents
inconnus. Le plan d'exécution fige leurs identités et entrées avant lancement.
Deux échanges 4B directs et un HTTP sont attendus dans les témoins de
sélection ; aucun appel n'est forcé pour obtenir ce nombre. Une erreur ou
une route différente reste au dénominateur et est rapportée telle quelle.

Les blocs natifs sont séquentiels, hors tests lourds ; ports, HOME, bases et
sorties sont isolés. Seuls les artefacts immuables sont partagés. Les
extractions existantes sont réutilisables uniquement après vérification de
leurs identités et empreintes. Les premières erreurs et les reprises
éventuelles sont conservées séparément. La mémoire et les délais restent
ceux de la recette précédente, sans abaissement des protections.

## Livraison et limites

Le suivi canonique reste [PLAN.md](../PLAN.md), le journal conserve les
commandes et les preuves. Les fichiers de résultat distinguent contrôles
structurels, fidélité documentaire, chaîne native et transport HTTP.
Un manque d'environnement ou d'artefact bloque seulement la preuve qui en
dépend ; il n'autorise pas une réussite reconstituée.

Les qualifications OCR, corpus métier, installation neuve, Windows,
aarch64 et poste physique ne sont pas acquises par ces tests. Le complément
livre ses correctifs et son bilan complet avec les réserves observées.
