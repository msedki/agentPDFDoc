# I5 — revue indépendante des 30 contrôlés

**Périmètre :** relecture des résultats appariés du 8 novembre 2026, sans nouvelle exécution ni modification des sources, oracles, harnais ou produit. Le transfert réservé n'a pas été consulté pour cette revue.

**Suivi du 9 novembre 2026 UTC :** une section finale distincte relit les
trente résultats fermés de l'instantané 8. Le primaire et le complément du
formateur restent conservés avec leurs propres dénominateurs.

## Conclusion et portée

La référence satisfait **12/12 positives et 18/18 limites** ; le candidat satisfait **12/12 positives et 16/18 limites**. Les deux contrôles de plan malformé restent **FAIL** : leur injection n'atteint plus le sélecteur. Une abstention préalable ne valide pas la frontière qu'ils devaient exercer.

La relecture des douze réponses positives, des citations et des fixtures ne relève aucun ajout factuel ni perte de condition. Toutes empruntent une route déterministe et appellent le double du générateur **zéro fois**, dans les deux bras. Ces résultats ne qualifient donc ni l'inférence 4B, ni le RAG vectoriel réel, ni les PDF/OCR, HTTP ou les contraintes de ressources. Les doubles déclarés remplacent les embeddings, la recherche vectorielle, le sélecteur et le compteur de tokens.

## Comparaison conservée

| Mesure contrôlée | Référence | Candidat |
|---|---:|---:|
| Réponses positives complètes selon les oracles gelés | 12/12 | 12/12 |
| Contrôles limites satisfaits | 18/18 | 16/18 |
| Faits littéraux attendus rendus et étayés | 15/15 | 15/15 |
| Rappel des faits au top 10, recherche avec doubles | 15/15 | 15/15 |
| Couverture littérale du contexte sérialisé, mesure brute | 14/15 | 14/15 |
| Citations positives vérifiées | 16/16 | 16/16 |
| Citations vérifiées sur tous les cas | 31/31 | 27/27 |
| Cas publiant un marqueur interdit | 0 | 0 |
| Appels au sélecteur contrôlé, tous les cas | 12 | 6 |

Les recettes de fixtures, le harnais, le profil, les versions des bibliothèques et l'ordre des cas sont identiques. Les **33 instances documentaires** ont les mêmes SHA-256 dans les deux bras ; aucun fichier applicatif n'a changé pendant chaque exécution. La diminution du nombre de citations ou d'appels au sélecteur n'est pas comptée comme un progrès de fidélité.

## Vérification des positives

| Cas | Constat de relecture |
|---|---|
| P01, P03, P04 | Condition exclusive d'étanchéité, signe négatif de température et deux plages avec leurs conditions conservés. |
| P02, P05 | Zéro conservé ; cellule vide TYP laissée vide ; bornes MIN/MAX et unité reliées aux en-têtes du tableau. |
| P06 | Plage recommandée retenue, sans la confondre avec le maximum absolu. |
| P07 | Deux passages identiques sont restitués séparément. C'est une redondance, sans fait nouveau ni preuve d'indépendance supplémentaire. |
| P08, P09 | Égalité ou différence des valeurs correctement attribuée à chaque document. La réserve sur des conditions d'essai supplémentaires non établies est adaptée aux fixtures. |
| P10, P11 | Somme décimale et conversion d'unité exactes ; entrées, références et méthode conservées dans la trace de calcul. |
| P12 | Valeur du cache distinguée de la formule, fraîcheur inconnue et absence de recalcul correctement signalées. |

Onze réponses sont identiques entre les bras. Dans P08, seuls l'ordre des deux documents et l'association des identifiants de citation à cet ordre changent ; les assertions et leurs attributions restent équivalentes.

Deux réserves de mesure ou de présentation sont héritées :

- P02, P10, P11 et P12 gardent l'avertissement générique `identifier_present_no_answer_evidence`, mal adapté à ces demandes explicites de cellules auxquelles une réponse étayée est fournie. Il n'entraîne aucun refus. Le compteur `answerable_with_limitation_notice=0` examine le préambule de la réponse ; il ne démontre pas l'absence de tout avertissement superflu.
- Le 14/15 du contexte vient de P05 : la recherche de la borne lexicale de `V` sur le JSON sérialisé échoue après une tabulation échappée. Le catalogue décodé contient bien la ligne, l'unité et les en-têtes. Cette inspection explique le résultat ; **elle ne remplace pas la mesure brute par 15/15** et aucun oracle n'a été changé.

## L11 et L12 : frontière non exercée

La référence appelle une fois le double, reçoit respectivement une clé de prose non autorisée ou une référence inconnue, puis termine avec `structured_answer_invalid`, sans delta public ni réponse enregistrée.

Le candidat conserve une évaluation générale non interprétée, mais produit finalement un plan vide par la route déterministe. Il publie une limite de couverture, sans citation, avec un seul terminal `done`. Le double n'est jamais appelé. Les marqueurs interdits ne sont pas publiés, mais les attaques prévues ne sont pas soumises au validateur : **16/18 reste le résultat primaire**. Le critère I5-D05 exigeant 18/18 limites n'est donc pas démontré par cette campagne.

## Complément proposé, non exécuté lors de cette revue

Ajouter une campagne distincte de **trois variantes**, appariée sur les deux bras, à partir de la fixture déjà connue L01 dont le candidat appelle effectivement le sélecteur : plan valide témoin, clé de prose supplémentaire, référence inconnue. Figer ce complément avant exécution, conserver les trente cas et leurs résultats sans les remplacer.

Critères du complément : catalogue non vide et exactement un appel au double pour chaque variante ; témoin valide restituant le passage avec sa condition et la réserve demandée ; deux variantes invalides terminant avec `structured_answer_invalid`, sans delta public, réponse persistée, citation fabriquée, nouvel essai ou retour à la prose. Les sources et la question restent constantes ; seul le mode du double varie. Ce complément isole la validation du plan, sans affaiblir la sélection ni les contrôles de preuve. Les tests existants de transport typé couvrent aussi cette frontière avec un fournisseur simulé ; leur reçu doit rester distinct d'une preuve d'inférence 4B réelle.

## Empreintes de la revue

- `controlled-baseline.json` : `1c95b14e440c91e566a480e31b8648c577d781df99a744abadf6dcc52365d5e9`.
- `controlled-candidate.json` : `105170300eab3175203ca9af1b242965a9d0ca88b85231357ba77f53794e2815`.
- [Fixtures gelées](../../tests/fixtures/grounded_cases.json) : `68a997cee3c6e3dcd1d8625d534c17631cb7ddaebedb1bfd3efa316c678fd476`.
- [Harnais](../../tools/qualification/grounded_campaign.py) : `a9ff2e5470a6fda376623b68c88ff804da8185b8ce3cc5b48ab691af2f258237`.

Les deux résultats bruts et les traces restent dans le dossier privé de qualification I5. Cette note ne les republie pas et ne contient aucun contenu du transfert réservé.

## Suivi final de l'instantané 8 — revue du 9 novembre 2026

Le suivi `controlled-candidate-final-followup-1` a été exécuté séparément de
03:25:39,023350 à 03:25:54,461029 UTC, sur l'instantané 8 figé par le reçu
`1511c38e97c7f5a4e2c184cd8175c965cabc27b64a121b8632aec6b83dd7f00b`.
Le processus termine avec le code 0, son groupe est vide et son arrêt est
vérifié. Les identités avant/après sont identiques et aucune dérive des sources
n'est enregistrée. La présente revue n'a lancé ni campagne, ni modèle, ni test.

Les **trente positions et questions**, les critères, le harnais, le profil et
les versions déclarées sont identiques à ceux du primaire. Les **33 originaux**
ont les mêmes SHA-256 que les bras référence et candidat du 8 novembre ; une
nouvelle lecture directe de leurs archives ZIP/XML confirme toutes les
recettes documentaires, y compris cellules vides, formules et caches. Les
trente fichiers individuels correspondent exactement au rapport consolidé et
aux empreintes du reçu d'exécution. Aucune position n'est retirée ou rejugée.

| Mesure du suivi contrôlé | Résultat |
|---|---:|
| Positifs satisfaisant les critères gelés | 12/12 |
| Limites satisfaisant les critères gelés | 16/18 |
| Faits positifs littéraux rendus et étayés | 15/15 |
| Rappel des faits au top 10 avec doubles | 15/15 |
| Couverture brute du contexte sérialisé | 14/15 |
| Citations vérifiées par le harnais | 27/27 |
| Cas publiant un marqueur interdit | 0 |
| Erreurs de harnais | 0 |
| Appels au double du sélecteur | 6, dont 0 sur les positifs |

La lecture intégrale des réponses, citations et fixtures confirme les
conditions, signes, rôles et calculs des douze positifs. Onze réponses sont
identiques à celles du candidat primaire ; P08 change seulement l'ordre des
documents et des IDs de citation. L06 et L18 changent aussi l'ordre de leurs
preuves, sans perdre le conflit ni son attribution. L13 conserve désormais
les deux négations exactes du passage, y compris le courant non établi par
le document. L16 conserve toute la note à 25/85 °C. Les refus pour périmètre,
unité absente, formule sans cache, lecture ambiguë, mauvaise propriété ou
mauvais rôle n'introduisent aucune valeur de substitution. L17 publie la
source intacte reconstruite ; le marqueur de corruption injecté n'est pas
publié, conformément au critère de provenance gelé.

L'unique état applicatif `error` est **L10, PASS** : le localisateur a été
volontairement supprimé et `invalid_source_locator` fait partie des erreurs
autorisées. Il n'y a ni texte public, ni citation, ni appel au sélecteur dans
ce cas. Ce refus de provenance attendu est distinct d'une erreur de harnais.

**L11 et L12 restent FAIL**, avec zéro appel au double, un plan vide et aucune
citation. Leur réponse garde maintenant l'état `unassessed` et explique la
limite d'analyse sans déduire une absence documentaire. Cette amélioration
ne soumet toujours pas les deux plans malformés au validateur. L'objectif
gelé de **18/18 limites** n'est donc pas atteint par ce suivi ; I5-D05 n'est
pas démontré. Le primaire **12/12 et 16/18** reste intact. Le
[complément du formateur](trust-4b-formatter-boundaries-2026-11-08.md), exécuté
après la première revue, garde son résultat séparé de **3/3 par bras**, soit
6/6 au total, sans ajout aux trente cas.

Les quatre doubles déclarés restent actifs. Le libellé de route
`local_4b_generation` sur six cas ne constitue donc pas une mesure 4B réelle.
Les réserves de présentation et le 14/15 brut du contexte décrits plus haut
restent conservés. La relecture est indépendante du dispatcher et de la
production des jugements, mais non aveugle : son auteur a participé aux
correctifs API. Elle ne qualifie pas l'inférence native, PDF/OCR, le transfert
réservé, HTTP/SSE, le navigateur ou les ressources de la cible.

Reçus privés scellés sous `.runtime/qa/production-i5-20261108/` :

- `controlled-candidate-final-followup-1.json`, SHA-256
  `326fb9de896e57965cc3623798897bfa21d46bca1791eb8159f959ef142e8214`.
- `controlled-candidate-final-followup-1-execution.json`, SHA-256
  `b98ba82cca716fe445fa54866f8fac8f212463595a0b2c26e0b1a864635c1d49`.
- `controlled-candidate-final-followup-1-independent-review-r01.json`, SHA-256
  `89ebc4e7e40d89f404cbd568a85b2dbd52289bc3a6571a3be9652c2751dbb332` :
  trente constats individuels, contrôles d'identité, lecture des 33 XML et
  distinction explicite des résultats primaires et du supplément.
