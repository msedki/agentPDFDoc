# I5-PJ — protocole de vérification des relations documentaires

**Rôle :** protocole préalable du complément demandé avec la pièce jointe.
**Propriétaire :** qualification RAG. **Statut :** fixé avant modification du
produit, 9 novembre 2026 (UTC). **Référence :** `fe4693da07ed9e948f65e4cadb51cd43ec36ebe2`,
branche `enhanced_version`. Le [plan](../PLAN.md) reste le suivi canonique.
Les critères et résultats historiques I5 ne sont ni remplacés ni requalifiés.

## 1. Objet et état de référence

L'instruction jointe demande une chaîne documentaire vérifiable, exclusivement
avec le générateur Qwen3-4B retenu, et une mesure indépendante des vérificateurs.
Le complément traite les erreurs de relation numérique constatées sur la
version publiée. Les travaux I6 locaux non publiés restent dans leur copie de
travail ; ils ne font pas partie de cette comparaison.

Deux défauts sont reproduits avec les vrais `AnswerContract` et `Catalogue` :

- **PJ-F01, bug :** une borne « less than 3.3 V » ou `< 3.3 V` peut devenir
  la valeur exacte 3,3 V. La comparaison avec une autre source donnant
  exactement 3,3 V produit une concordance fausse, bien que les citations
  soient fidèles aux extraits.
- **PJ-F02, bug :** « Output current is 8 mA unless TA = 25 °C » peut couvrir
  une question au point TA = 25 °C, pourtant exclu par la source.

Le comptage de tokens des sondes est un double déclaré ; ces reproductions
ne constituent pas des inférences 4B. Avant correction, les 196 tests existants
ciblant contrats, obligations, garanties et frontière du formateur passent.
Leur réussite ne détectait donc pas ces deux défauts. Les résultats bruts
et commandes seront liés depuis le bilan.

## 2. Hypothèses et décision attendue

**H1 :** distinguer valeur exacte, borne et non-égalité empêche une fausse
égalité ou un calcul sur une valeur que le document n'affirme pas. Le nombre
seul ne suffit pas. Le correctif conserve l'opérateur et l'extrait littéral,
ou produit une réponse partielle explicite si la relation n'est pas prise en
charge ; il ne remplace pas une borne par sa valeur frontière.

**H2 :** une condition exclue ne constitue pas une condition positive.
La vérification doit conserver la polarité et le rattachement de la condition,
sans attribuer à une autre grandeur ou variable l'exclusion observée.

**H3 :** ces contrôles diminuent les faux appuis acceptés sans dégrader les
cas positifs à valeur exacte ou à condition explicitement applicable.
Les références ALCE, RAGTruth, Sufficient Context et FaithBench motivent
l'évaluation séparée de l'appui et de la couverture. Le
[rapport scientifique](trust-i5-pj-research-2026-11-09.md) documente les huit
références de la pièce jointe, leurs résultats et leurs limites de transfert.
Il s'agit ici d'une vérification sémantique **bornée à des relations explicites**,
pas d'un modèle général d'implication logique ou d'une autoévaluation du 4B.

## 3. Jeux, séparation et comparateurs

Un agent chargé de l'évaluation rédige des exemples synthétiques FR/EN, les
réponses attendues, leurs justifications et les localisations exactes des
passages. Les auteurs produit n'écrivent pas les annotations finales.
Cette séparation de rôles ne vaut pas annotation par un expert humain.

- Développement : au moins 24 cas, avec inégalités, valeurs exactes,
  conditions, négations, sujets, propriétés, rôles et preuves insuffisantes.
- Final : au moins 24 cas, autres familles documentaires synthétiques et
  valeurs ; fichier et empreinte gelés avant modification produit, contenu
  non consulté par les auteurs produit avant gel du candidat.
- Les jeux industriels/publics des itérations précédentes ne deviennent pas
  un nouveau test aveugle. Leurs échecs et critères restent dans leurs bilans.

Comparateurs : (A) code publié exact ; (B) restitution strictement extractive
des passages, témoin de fidélité littérale **sans certification de suffisance** ;
(C) candidat. Le témoin B n'est pas crédité d'une réponse correcte simplement
parce qu'il cite les sources. Ablations H1 et H2 séparées dans des copies
diagnostiques, sans option de désactivation ajoutée au profil de production.
Même source, question, budget et oracle pour chaque comparaison.

Le verdict distingue faux appui accepté, vrai appui rejeté, question pleinement
couverte, réponse partielle, conflit, abstention et erreur technique. Un cas
non exécuté reste au dénominateur prévu et ne reçoit aucun score inventé.

## 4. Definition of Done du complément

| Identifiant | Critère fixé avant essais | Justification |
|---|---|---|
| PJ-D01 | Zéro fausse égalité ou donnée de calcul issue d'une borne/non-égalité dans les cas annotés du périmètre ; zéro condition exclue reconnue applicable | Défauts bloquants reproduits ; aucun taux positif acceptable sur ces scénarios contrôlés |
| PJ-D02 | Aucun nouveau faux rejet sur les positifs pris en charge par la référence ; couverture positive candidate au moins égale à la référence | Une abstention systématique ne constitue pas une amélioration |
| PJ-D03 | Références exactes, opérateurs, unités, conditions et exceptions conservés ; aucune donnée factuelle libre introduite par le 4B | Exigence centrale de la pièce jointe |
| PJ-D04 | Tests de régression touchés, suite portable, Ruff et Mypy sans nouvelle erreur ; échecs préexistants distingués | Frontière partagée par sélection, comparaison et rendu |
| PJ-D05 | Jeu final indépendant exécuté une fois après gel, métriques de faux acceptés/rejetés et résultats complets conservés ; pas de réglage après ouverture | Réduire l'ajustement aux exemples de développement |
| PJ-D06 | Essais natifs appariés avec E5, Qdrant, SQLite, tokenizer et Qwen3-4B verrouillé ; au moins deux appels 4B réels par bras, réponses et compteurs conservés | Une route déterministe ou un double ne prouve pas une inférence réelle |
| PJ-D07 | Plafonds inchangés ; coût du contrôle mesuré, p95 de contrôle inférieur à 250 ms sur cette machine ; mémoire/latences natives rapportées, arrêt de tous les processus possédés vérifié | Budget de contrôle borné ; coût natif et recette physique D07 restent distincts |
| PJ-D08 | Sources, protocole, configurations, corpus, commandes, résultats et limites versionnés ; commit et publication sans force sur `enhanced_version` vérifiés | Livraison reproductible et préservation de l'historique |

Le seuil de 250 ms est un budget d'ingénierie local pour les seuls contrats,
pas une cible issue de la littérature. Les latences natives restent confrontées
aux objectifs du profil existant ; aucun seuil mémoire ou timeout produit
n'est relevé pour terminer la campagne. Un échec d'une porte reste `FAIL` ou
`BLOCKED`, même lorsque le correctif est livré avec ses réserves.

## 5. Exécution et périmètre de preuve

La référence est un worktree détaché au commit indiqué. Les fichiers produit
du candidat sont hachés avant le final. Les deux bras sont chargés dans des
processus séparés ; les scripts conservent les sources, versions Python et
dépendances, paramètres, latence et consommation mémoire observée.

Les contrôles de contrats ne font ni extraction PDF ni inférence. Les essais
natifs emploient des documents Office synthétiques réellement extraits et des
instances neuves, séquentielles, avec stockage, HOME et ports isolés. Seuls les
poids/binaires immuables déjà provisionnés sont partagés. Les modèles et
tokenizers sont vérifiés contre `config/enhanced-4b.lock.json`. Le générateur
reste Qwen3-4B Q4_K_M, contexte 8192, seed 0, CPU, paramètres du profil actif.

Extraction, récupération, suffisance des preuves, restitution, citations,
abstentions et coûts ont leurs mesures distinctes. L'extraction Office est
contrôlée contre les paragraphes générés ; cette campagne ne requalifie ni
l'OCR SCAN2 ni la mise en page PDF TMP117. Les nouvelles grammaires sont aussi
exercées avec les tableaux et calculs par les tests pertinents. Les versions
documentaires inconnues restent inconnues : aucune date de validité inférée.

Les limites héritées (OCR, transfert historique interrompu, installation neuve,
Windows/aarch64, cible physique) restent ouvertes sauf preuve dédiée dans ce
complément. Une absence d'erreur sur le jeu synthétique ne certifie pas la
justesse générale ni la préparation à la production.
