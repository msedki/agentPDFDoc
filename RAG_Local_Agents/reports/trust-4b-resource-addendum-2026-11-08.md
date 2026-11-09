# I5 — addendum préalable : cardinalité du contrat et supervision du harnais

Statut : critères fixés avant correction, le 8 novembre 2026 UTC. Le protocole initial reste inchangé. Aucun oracle de transfert réservé n’a été ouvert par les auteurs du produit.

## Défaut constaté et objectif

La revue du contrat a constaté que le scope accepte jusqu’à 1 000 documents et la question jusqu’à 12 000 caractères. Le produit des documents, sujets, propriétés, rôles et conditions peut produire un grand nombre d’obligations avant le comptage des tokens. Répéter la clause demandée peut aggraver cette allocation. Les budgets existants du modèle ne protègent donc pas seuls cette frontière.

Avant toute construction de la liste complète, limiter à **256 obligations** et **65 536 caractères cumulés de clauses requises**. Au-delà, rendre une erreur explicite et bornée `question_scope_too_complex`, sans allocation du produit cartésien complet, sans annoncer un sous-ensemble comme couvert et sans appel génératif. Ces seuils limitent le travail local ; ils ne changent ni le nombre de fragments retenus, ni les budgets de tokens, de RAM ou les délais d’inférence.

Acceptation : tests de la frontière exacte, multiplication des dimensions, nombreuses identités documentaires et clauses longues, diagnostic stable et absence d’appel au modèle. Les demandes de complexité ordinaire doivent conserver leurs obligations et preuves. Une demande refusée pour cette borne est une limite opérationnelle, pas une réponse documentaire réussie.

## Harnais natif

La revue a aussi constaté que les 1 500 secondes de supervision globale étaient appliquées au transport HTTP seulement. Le transport direct conserve ses limites de cas existantes mais n’avait pas de deadline de bloc explicite. Le harnais doit appliquer au direct le même processus possédé, la même deadline de **1 500 s** et la même procédure d’arrêt que HTTP, pour les deux bras. Les groupes et l’expiration sont consignés ; une expiration reste un échec, jamais un résultat omis. Les tests utilisent des doubles identifiés ; les reçus natifs seront acquis par la campagne finale.

Aucun contenu, attendu, poids ni paramètre d’inférence ne change. Le hash ancien du harnais est `df1c82f0797c777080e9a596f848853e9eb44fe1cd96adcb5041a7cd56c7063c` ; les sources avant/après restent archivées dans les preuves privées.
