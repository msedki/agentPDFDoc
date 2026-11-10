# I7 — pertinence des relations pour la propriété demandée

**Rôle :** protocole préalable du correctif consécutif au cas I6R06-F05.
**Propriétaire :** intégration et qualification RAG.
**Statut :** critères définis avant modification du produit ; résultats à produire.
**Date :** 10 novembre 2026 (UTC).
**Référence :** `522d86839d5c803c57daec0e799bfa48ee5aa8e7`.

## Défaut et périmètre

Le nouveau final I6R06 conserve son résultat définitif de 47/48, contre
39/48 pour sa référence. Son cas F05 demande la tension d'entrée et cite un
passage contenant aussi la tension maximale de sortie. La valeur d'entrée
est correcte et la citation est fidèle, mais `matched_relations` contient
également la relation de sortie. Cette relation supplémentaire ne satisfait
pas le critère de pertinence du jeu gelé. Ce n'est ni un nombre inventé ni
une substitution de valeur. F05 devient un cas connu de développement I7 ;
son résultat I6 n'est pas reclassé après correction.

Le lot précise la frontière entre les relations admises pour répondre à la
question et les autres informations présentes dans la citation intégrale.
Une propriété explicitement reconnue doit contraindre la relation de la
grandeur correspondante. Une demande générique ou une demande portant sur
plusieurs propriétés conserve son périmètre explicite. Le correctif reste
dans le contrat documentaire ; il ne change ni extraction, retrieval,
générateur, budgets, protections de ressources, API publique ou stockage.
Le seul générateur demeure Qwen3-4B Q4_K_M.

Les références primaires ConjNLI et FActScore déjà consultées et consignées
dans SOURCES.md restent applicables : distinguer portée des propositions,
appui factuel et couverture de la demande. Ces publications ne prouvent
pas la correction de notre grammaire ni une généralisation métier.

## Critères avant implémentation

| ID | Critère et preuve attendue |
|---|---|
| PROP-01 | Une relation numérique portant sur une autre propriété explicite de la même grandeur ne figure pas parmi les relations admises pour la demande ; la propriété est liée à sa grandeur, sans filtre global mélangeant tension et courant |
| PROP-02 | Les relations effectivement demandées restent admises lorsqu'elles sont étayées ; les demandes génériques, inversées et portant explicitement sur plusieurs propriétés ne perdent pas de faits autorisés |
| PROP-03 | L'extrait intégral, ses valeurs contextuelles, les conditions, négations, sujets, références, offsets et empreintes restent fidèles ; filtrer une relation ne raccourcit pas sa citation |
| PROP-04 | L'absence d'une propriété demandée reste une limite, sans promotion d'une autre propriété ni d'une relation niée ; aucune nouvelle fausse couverture complète ou conclusion comparative interdite sur les cas annotés |
| PROP-05 | Régressions ciblées et suite portable applicable sans régression, Ruff/Mypy conformes ; échecs initiaux et reprises conservés séparément |
| PROP-06 | Nouveau final indépendant de 16 cas, 8 positifs et 8 limites, FR/EN équilibré, annoté et gelé avant exécution ; référence/candidat exacts, aucun changement du produit ou de l'oracle après ouverture |
| PROP-07 | Chaîne native appariée sur quatre questions connues par bras : propriété d'entrée seule, propriété de sortie seule, plusieurs propriétés explicites et propriété absente avec négation ; originaux synthétiques, moteur réel quand la route l'appelle, texte publié/citations/registre et arrêts vérifiés |
| PROP-08 | Code, résultats et suivi committés puis poussés après chaque lot substantiel vérifié sur enhanced_version ; parent/arbre/tête vérifiés sans force ; résultats I6 et limites de qualification conservés |

La distinction entre relation non demandée et relation fausse reste explicite
dans les preuves. Une valeur contextuelle présente dans une citation fidèle
ne compte pas comme une hallucination. Aucun identifiant, texte de fixture,
nombre ou verdict attendu n'est codé dans le produit.

## Organisation et gel

Le développement se fait dans un worktree séparé de la révision I6 en cours
de recette native. Il ne modifie pas le candidat `522d868`. L'évaluateur
indépendant prépare le nouveau final hors de l'arbre produit ; seuls le
périmètre et les empreintes sont transmis aux auteurs avant le gel. Un jeu
de développement distinct est autorisé. Les résultats I6, même désormais
connus, ne deviennent pas un nouveau jeu réservé.

Les vérifications natives et les suites lourdes sont séquentielles. Les
quatre positions natives par bras sont des régressions connues, distinctes
du final ; leurs sources et annotations sont gelées avant lancement. Les
moteurs et artefacts immuables déjà provisionnés sont réutilisés après
vérification. Chaque bras possède ses ports, bases, HOME et sorties, avec
les mêmes limites et réserves. Une erreur reste au dénominateur et aucune
reprise favorable ne remplace la tentative d'origine.

L'ouverture du final attend un candidat figé, ses contrôles de développement
et sa recette native. Tout défaut nouveau découvert ensuite reste un
résultat du candidat et demanderait un autre lot, sans adaptation de ce
final. Les observations de coût restent descriptives à faible effectif ;
aucune qualification de performance générale n'en est déduite.

## Limites de livraison

Les annotations sont réalisées par un évaluateur distinct des auteurs du
correctif, sans validation humaine revendiquée. Le final contractuel emploie
le catalogue/rendu réels et les doubles déclarés du banc existant ; il ne
mesure pas l'extraction, le retrieval ou le modèle. La recette native est
rapportée séparément. Les qualifications du corpus métier, de l'OCR, de
Windows, d'aarch64, d'une installation neuve et du poste physique de 16 Go
restent celles de la DoD, sans fermeture implicite par ce lot.

Le suivi des actions demeure dans [PLAN.md](../PLAN.md). Le journal et les
rapports conserveront les commandes, révisions, dénominateurs et preuves.
