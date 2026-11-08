# I3 — addendum préalable F07 : recherche bilingue et grandeur principale

**Date :** 8 novembre 2026 (UTC). **Statut :** fixé après le premier candidat
contrôlé C0, avant correction F07. Le [protocole initial](grounded-4b-protocol-2026-11-08.md)
et la matrice de 30 questions restent inchangés. Aucun critère n'est abaissé.

## Observation et hypothèse

La référence et C0 ne retrouvent aucun candidat lexical pour P04/P06 : questions
françaises, passages anglais, branche dense volontairement vide dans ce harnais.
Les bases SQLite isolées contiennent les preuves. L'alias existant `supply`
retrouve les passages dans le même périmètre. Cette observation ne démontre pas
un défaut des embeddings E5 natifs.

P04 révèle aussi une erreur de classement de la question : « plages
d'alimentation … avec leurs conditions de température » est interprété comme
une demande de température. La condition masque la grandeur principale implicite,
alors que le contrat reconnaît déjà l'alimentation comme tension en l'absence
du mot température.

**Hypothèse F07 :** un repli lexical borné sur les alias techniques déjà connus,
uniquement lorsque la recherche lexicale initiale est vide, récupère ces preuves
sans augmenter le plafond ni élargir le scope. La distinction explicite entre
plage d'alimentation et condition de température conserve les deux relations
sources ; elle n'autorise aucune inférence sur une condition numérique absente.

## Acceptation avant essai F07

- Les cas P04/P06 restent dans les douze positifs du protocole, avec leurs sources,
  questions et oracles d'origine. Ils doivent contenir tous leurs faits et conditions.
- Les autres positifs doivent rester utiles, les contrôles limites restent au
  dénominateur. C0 est conservé comme bras intermédiaire, y compris ses échecs.
- Repli limité aux alias statiques, dans la portée SQL/projection existante,
  sans appel de modèle, nombre, identifiant ou valeur ajouté à la question source.
- Pas de repli si la requête initiale retourne déjà des candidats. Pas de confusion
  entre une demande de température d'alimentation et des conditions de température.
- Tests négatifs de portée, de requête inconnue et de budget ; désactivation du
  repli testée pour isoler son effet sur la récupération.

L'évaluation C0 utilisait le gradeur mécanique initial. Les éventuelles erreurs
du gradeur sont revues symétriquement sur les sorties conservées, sans nouvelles
requêtes ni modification des oracles. Les scores bruts restent publiables séparément.
