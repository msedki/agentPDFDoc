# I6 — portée des relations et coût des réponses partielles

**Rôle :** protocole préalable de la poursuite demandée après I5-PJ.
**Propriétaire :** intégration et qualification RAG.
**Statut :** fixé avant les modifications produit de cette itération.
**Référence :** `7ef57fdc38261fa4b14e077e5d1c75aee57f7eea`,
branche `enhanced_version`. **Date :** 9 novembre 2026 (UTC).
Le [plan canonique](../PLAN.md) porte les actions et leurs états.

## 1. Périmètre et référence

La demande autorise l'implémentation des priorités du bilan I5-PJ, leur
qualification et un commit/push après chaque lot substantiel vérifié.
Le seul générateur reste Qwen3-4B Q4_K_M ; modèle, tokenizer, profil et
plafonds restent ceux de `config/enhanced-4b.yaml` et de son verrou.
Aucune nouvelle dépendance ni génération factuelle libre n'est prévue.

La branche distante a été relue au commit de référence. Un worktree détaché
de cette révision sert de témoin. Une autre copie contient des travaux I6
antérieurs non publiés sur l'ingestion, les titres et l'OCR : elle est
préservée. Leur éventuelle lecture fournit des pistes, sans importer leurs
preuves ou prétendre avoir livré ce chantier plus large.

Les défauts déjà exposés dans les
[résultats I5-PJ](trust-i5-pj-results-2026-11-09.md) sont les données connues :
H24 accepte une valeur au point exclu par « à l'exception de » ; H06 refuse
une tension positive en raison d'une négation portant sur un courant ;
H11/H12 et D11/D12 exigent chaque sujet dans chaque document au lieu de
lier les preuves aux sujets comparés. La médiane native I5-PJ passe de
0,591 à 53,043 s, notamment parce que quatre cas devenus partiels sollicitent
le 4B. Ces observations ne deviennent pas un nouveau test aveugle.

## 2. Hypothèses et invariants

**R1 — portée des prédicats.** Une exception ou une négation appartient
à une relation et à ses conditions. Une garde doit conserver sa portée
sans contaminer une proposition affirmative indépendante. Une ponctuation
ou conjonction seule ne suffit pas à affirmer cette indépendance :
négations dominantes, conditions globales, corrections et antécédents doivent
rester visibles ou entraîner une limite explicite.

**R2 — obligations de comparaison.** Une comparaison entre plusieurs
sujets doit exiger une preuve admissible par sujet et propriété, tout en
conservant le scope documentaire. Une demande explicite « dans chaque
document » conserve ses obligations par document. Un sujet absent, des
rôles ou conditions incompatibles, une ambiguïté ou des valeurs concurrentes
ne sont pas résolus par une association supposée.

**R3 — route partielle bornée.** Lorsqu'un contrat établit déjà une limite
et l'ensemble fermé de ses références, un appel au modèle peut être
redondant. Une route déterministe candidate doit conserver les extraits,
les obligations manquantes, les conflits et le registre de support.
Elle n'est pas étendue à toutes les réponses partielles, aux questions non
analysées ou aux contextes dont la sélection reste nécessaire.

Les mécanismes portent sur des formes explicites FR/EN et ne prétendent
pas résoudre toute implication sémantique. L'extraction, la recherche et
les annotations ne sont jamais ajustées pour rendre une réponse attendue.
Ni nom de fichier ni valeur de l'oracle ne deviennent une règle du produit.
Toutes les références publiques doivent garder leurs identités et offsets.

## 3. Fondements et portée scientifique

Les sources primaires I5-PJ demeurent le socle : précision d'appui,
complétude, contexte suffisant, abstention et citations sont évalués
séparément. La [revue précédente](trust-i5-pj-research-2026-11-09.md)
conserve les huit références et leurs limites.

Deux références complémentaires ont été consultées le 9 novembre 2026 :

- Saha, Nie et Bansal, **ConjNLI**, EMNLP 2020,
  [publication primaire](https://aclanthology.org/2020.emnlp-main.661/),
  DOI 10.18653/v1/2020.emnlp-main.661. Le travail éprouve des inférences
  sous ajout, retrait ou remplacement de propositions coordonnées,
  avec négations et quantificateurs. Il motive ici des contre-exemples de
  portée ; il ne valide pas notre grammaire française ni notre CPU.
- Min et al., **FActScore**, EMNLP 2023,
  [publication primaire](https://aclanthology.org/2023.emnlp-main.741/),
  DOI 10.18653/v1/2023.emnlp-main.741. La décomposition en faits atomiques
  soutient une mesure séparée de chaque appui. Notre évaluation conserve
  aussi l'utilité et les obligations manquantes ; elle ne reprend ni le
  corpus biographique ni l'évaluateur automatique de cette publication.

Ces sources motivent des hypothèses et contre-épreuves, sans score publié
transféré au produit. Aucun modèle NLI, autre générateur ou poids ajusté
n'est adopté.

## 4. Jeux et séparation

Un agent évaluateur distinct prépare **48 cas de développement et 48 cas
finaux**, chacun avec 24 positifs répondables et 24 négatifs ou cas dont la
conclusion demandée n'est pas établie. Les catégories couvrent exceptions,
négations locales ou dominantes, coordination, sujets, propriétés, conditions,
rôles, comparaisons collectives ou explicitement par document, preuves
manquantes et conflits. Les textes, identités et valeurs du final diffèrent
du développement et des cas connus I5-PJ.

Les annotations donnent la réponse ou limite attendue, sa justification,
les passages exacts et offsets en points de code, ainsi que les relations
et conclusions comparatives admissibles. Elles sont écrites avant exécution
sur le candidat. Leur production par agents ne vaut pas expertise humaine.

Le développement est visible pour le diagnostic. Le final est conservé hors
de l'arbre produit, son SHA-256 et sa répartition seulement sont publiés avant
modification. Il est ouvert après gel du candidat et de ses outils. Aucun
ajustement produit, annotation ou seuil n'est effectué après cette ouverture.
Un échec découvert reste au dénominateur et est remis à un prochain lot
avec un nouveau jeu final, sans interrompre la publication du bilan.

Les anciens 48 cas I5-PJ servent de régression connue ; les cas H24/H06 et
D11/D12/H11/H12 constituent les réparations attendues. Les autres campagnes
historiques restent distinctes.

## 5. Comparateurs et mesures

Comparateurs : (A) révision publiée exacte ; (B) témoin extractif sans
décision de suffisance ; (C) candidat. Les entrées, annotations et budgets
sont identiques. Les mesures légères du contrat ne sont ni un test du
retrieval ni une inférence 4B. Trois répétitions mesurent la stabilité,
la première étant la mesure primaire ; elles ne multiplient pas le nombre
de documents ou de cas indépendants.

Chaque cas conserve réponse intégrale, relations admises/rejetées, état des
obligations, conclusion comparative, citations et éventuelle erreur.
Les faux appuis complets et les opérandes incorrectement admis sont séparés
des faux rejets, de la couverture positive et de la fidélité littérale.
Une simple occurrence d'un nombre ou un statut seul ne vaut pas preuve.

Ablations de développement : retrait de R1, retrait de R2 et retour à la
route antérieure R3 dans des copies diagnostiques. Le code livré ne reçoit
aucun drapeau permettant de désactiver une garde. Les commits intermédiaires
fournissent des références pour attribuer les effets sans modifier le final.

Une campagne native appariée prévoit **16 questions du développement connu
et deux questions complémentaires conservant une véritable sélection 4B**,
sur documents synthétiques DOCX/PDF. Sources, questions et évaluations sont
figées avant exécution. La matérialisation/extraction est réelle et ses
éventuels réemplois sont prouvés par empreinte. Au moins deux appels 4B
terminés par bras doivent être observés ; aucun appel n'est forcé dans le
produit pour satisfaire ce nombre. Un parcours HTTP/SSE distinct vérifie
persistance, citations et versions. Les résultats du contrat, du retrieval,
du rendu, de la chaîne native et de HTTP restent séparés.

## 6. Critères de réception préalables

| ID | Critère | Portée |
|---|---|---|
| I6R-D01 | Zéro faux appui complet et zéro opérande interdit accepté sur les négatifs annotés ; H24 correctement limité | Relations explicites du jeu, sans garantie générale |
| I6R-D02 | Tous les positifs annotés couverts ; aucun positif couvert par la référence nouvellement rejeté ; H06 et les quatre comparaisons connues corrigés | Utilité distincte de l'abstention sûre |
| I6R-D03 | Tous les littéraux requis et leurs citations conservés ; aucune conclusion comparative hors relation admissible ; aucun fait libre du 4B | Vérification par segments et obligations, pas seulement présence des chiffres |
| I6R-D04 | Tests affectés, suite portable, Ruff et Mypy sans nouvelle erreur ; échecs antérieurs explicités | Régression logicielle, avec intégrations pertinentes |
| I6R-D05 | Deux jeux gelés et disjoints, final ouvert après gel du candidat, résultats complets et ablations conservés, aucune adaptation après ouverture | Reproductibilité et séparation, annotation humaine non revendiquée |
| I6R-D06 | Chaîne native 18 positions par bras, au moins deux appels 4B réels terminés par bras, parcours HTTP/SSE et arrêts vérifiés | Services isolés et modèles verrouillés ; aucune qualification d'installation déduite |
| I6R-D07 | Contrat p95 inférieur à 250 ms ; aucun plafond relevé ; les cas admissibles à R3 n'appellent plus le modèle, sans perte de support ; ressources et latences natives intégrales rapportées | Budget local d'ingénierie ; pas une recette physique D07 |
| I6R-D08 | Chaque lot substantiel vérifié committé et publié sans force sur enhanced_version ; contenu distant comparé ; plan, décisions, journal, commandes et bilan à jour | Publication des sources avec réserves explicites |

Le taux positif cible est volontairement absolu sur ce petit jeu annoté.
Un résultat partiel ne devient pas PASS par diminution du dénominateur.
Le p95 de 250 ms reprend le budget d'ingénierie local de I5-PJ ; les objectifs
physiques historiques restent inchangés. Une amélioration publiée ne suffit
pas à acquérir la qualification de production.

## 7. Exécution, ressources et publication

Les blocs natifs sont séquentiels. Données SQLite/Qdrant, métadonnées Ollama,
HOME, ports et sorties sont propres à chaque essai ; seuls les artefacts
immuables provisionnés sont partagés. Aucun service existant n'est arrêté
sans preuve de propriété. Les erreurs de préparation, reprises et sorties
intermédiaires sont conservées avec leur périmètre.

Les lots sont : protocole et gels ; portée des exceptions/négations ;
comparaisons ; route partielle et intégration ; final et bilan. Chaque lot
produit est publié après ses tests et sa revue, avec état réel des autres
critères. Le reçu du commit précédent peut être conservé dans le lot suivant
pour éviter une référence circulaire.

La voie de publication disponible est le connecteur GitHub demandé.
La configuration locale reste MOHAMED SEDKI <mohamed.sedki@live.fr> ; le
connecteur attribue ses objets commit au compte connecté, sans champ
author/committer paramétrable. Les reçus distinguent ces identités et
vérifient l'égalité des arbres, le parent et l'ancienne tête attendue.
Aucune réécriture distante n'est autorisée.

Les limites d'OCR, de transfert industriel, d'installation neuve, Windows,
aarch64 et de poste physique héritées restent ouvertes sans nouvelle preuve
dédiée. Les tests synthétiques de cette itération ne les requalifient pas.
