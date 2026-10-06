# Livraison locale Linux avec réserves — 6 octobre 2026

**Rôle :** synthèse de livraison, portée réelle, réserves et conditions de reprise · **Propriétaire :** intégration du produit · **Statut :** Vivant, livraison locale retenue avec réserves · **Référence :** produit publié jusqu'à `e58ff24`, base documentaire `5fb5dc8` et décision W038 · **Mis à jour :** 2026-10-06 09:36 (UTC) · **Source de vérité :** ce rapport pour la synthèse de livraison ; [décision W038](../DECISIONS.md#w038-livraison-locale-linux-avec-réserves-et-qualification-intégrale-en-attente) pour l'acceptation, [DoD](../DEFINITION_OF_DONE.md) pour les critères, [journal](../journal/2026-10-06.md) pour les exécutions

## Portée retenue

L'utilisateur retient la livraison locale sur le poste **Linux aarch64,
Jetson AGX Orin**, avec ses réserves connues. La qualification intégrale
V2.1 est mise en attente à sa demande. L'application et ses données ne
sont pas modifiées pour cet arbitrage ; aucune installation sur un autre
poste, mise en service externe ou nouvelle recette n'est effectuée.

Le choix du modèle est livré au lancement ; le défaut est **`qwen3.5:2b`
en Q8_0**, pas Q4_K_M. Le profil 4B conservé et la procédure de changement
sont décrits dans [W032](../DECISIONS.md#w032-modèle-choisi-au-démarrage-qwen-35-2b-par-défaut)
et [Exploitation](../../docs/exploitation/EXPLOITATION.md). Le changement
demande un redémarrage, pas une bascule depuis le chat. Le mode automatique
peut utiliser le GPU pour la génération sur ce couple Linux qualifié ;
cette voie ne vaut pas preuve de qualité équivalente ou de recette D07.

## Derniers contrôles livrés

Les résultats restent ceux de leurs exécutions datées, sur leurs entrées
et configurations propres. Aucun résultat historique 4B n'est transféré au 2B.

| Lot | Preuve disponible | Portée de la preuve |
|---|---|---|
| Navigation de citation F05 | [Unités, lint, typage, build et parcours Chromium](../journal/2026-10-06.md#r15-3-f05--citation-page-14-déviée-vers-la-page-13) | Correction page14/retour/redimensionnement, pas toutes les géométries du corpus |
| Couverture des passages Q10 | [Essai natif, captures et arrêt](../journal/2026-10-06.md#r15-3-q10--couverture-des-passages-entiers) : huit passages, 40/40 régions distinctes, 69 fragments ; un test strict PASS | Jeu QLONG, une taille desktop ; pas le taux global d'ancres D06.5. Huit avertissements Canvas2D conservés |
| Modèle au lancement | [Parcours 4B/2B/4B et conservation de l'index](../journal/2026-10-04.md#r23--choix-au-lancement-et-parcours-natifs-validés-relevé-2202-utc) | Intégration locale réelle, pas exactitude métier ou qualification générale du 2B |

Les preuves d'installation, hors ligne et sauvegarde/restauration Linux
sont situées dans la [qualification par plateforme de la DoD](../DEFINITION_OF_DONE.md#qualification-linux-w018).
Elles ne certifient pas le profil 2B actuel sur toutes les charges ni les
plateformes non exécutées. La dernière QA Q10 a été arrêtée avec conservation
contrôlée ; aucun démarrage supplémentaire n'est effectué pour cette livraison.

## Réserves explicites

| Sujet | État et incidence pour l'utilisateur | Référence |
|---|---|---|
| OCR P02 | Erreurs persistantes sur signes scientifiques, unités et références dans le texte narratif. Comparer les valeurs extraites au PDF original ; une ligne de tableau exacte ne qualifie pas toute la page | [Diagnostic refusé](../journal/2026-10-06.md#r23-ocr-01--discriminant-des-lignes-réelles) |
| Réponses 2B | Jugement injustifié et assertion avec citation non probante observés ; correctif éditorial refusé. Vérifier chaque assertion dans le passage cité avant utilisation métier | [W037](../DECISIONS.md#w037-candidat-éditorial-2b-refusé-après-un-témoin-unique) |
| Admission et performance | Admission froide 2B mesurée sur un pilote local ; estimation supplémentaire chaude de 512 Mio encore provisoire. Ni charge maximale, sortie de 400 tokens ni latences D07 garanties | [W036](../DECISIONS.md#w036-admission-froide-du-2b-fondée-sur-un-pilote-cpu-local), [D07](../DEFINITION_OF_DONE.md#d07--ram-cpu-et-latence) |
| Ancres et corpus | Q10 ne couvre que le jeu déclaré. Le taux global d'ancres et les gates DEV/final ne sont pas validés ; le corpus privé R19 reste en pause | [D04–D06](../DEFINITION_OF_DONE.md), [plan](../PLAN.md) |
| Plateformes et distribution | Pas de qualification intégrale Windows, Linux x86-64, kit Windows installé ou poste physique CPU/16 Go maximum. Les 61 Gio du Jetson et le GPU ne satisfont pas ce critère | [DoD](../DEFINITION_OF_DONE.md#d07--ram-cpu-et-latence), [déploiement](../../docs/deploiement/DEPLOIEMENT.md) |
| Index et provenance | Migration d'embedding D03.8/comparatif D10.2 non réalisés, purge physique non qualifiée et soumise à autorisation distincte ; certaines traces historiques D11 restent non vérifiables | [D03/D10/D11](../DEFINITION_OF_DONE.md), [précondition du comparatif](../journal/2026-10-06.md#r24-emb-01--précondition-du-comparatif) |

Cette livraison avec réserves **ne déclare pas l'absence de défaut ni la
conformité V2.1 globale**. Une citation valide identifie une source ; elle
ne rend pas automatiquement l'affirmation générée fidèle à cette source.

## Travaux différés et reprise

La qualification intégrale, ses corrections restantes et ses campagnes
ne reprennent que sur demande explicite. Les objectifs, seuils, cases
non cochées, échecs et preuves sont conservés, pas remplacés par ce rapport.
Le [plan canonique](../PLAN.md#périmètre-courant--décision-w038-du-6-octobre-2026)
porte les actions différées ; aucun second suivi n'est créé ici.
À la reprise, contrôler les prérequis du lot retenu, obtenir le matériel
approprié et les autorisations nécessaires, puis vérifier les seules
entrées affectées. Pas de nouvelle campagne exhaustive automatique.
