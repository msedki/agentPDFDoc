# Livraison locale Linux avec réserves — état au 9 octobre 2026

**Rôle :** synthèse de livraison, portée réelle, réserves et conditions de reprise · **Propriétaire :** intégration du produit · **Statut :** Vivant, livraison locale retenue avec réserves · **Référence :** produits publiés `5204d2e` et `aabb9808`, décision W038 et recette R27 exécutée avec réserve du bureau ; historique du 6 octobre conservé · **Mis à jour :** 2026-10-09 23:55 (UTC) · **Source de vérité :** ce rapport pour la synthèse de livraison ; [décision W038](../DECISIONS.md#w038-livraison-locale-linux-avec-réserves-et-qualification-intégrale-en-attente) pour l'acceptation, [DoD](../DEFINITION_OF_DONE.md) pour les critères, [journal du 9 octobre](../journal/2026-10-09.md) pour la recette actuelle et journaux antérieurs pour leur historique

## Portée retenue

La décision W038 du 6 octobre retient la livraison locale sur le poste
**Linux aarch64, Jetson AGX Orin**, avec ses réserves connues. Le 9 octobre,
l’utilisateur autorise la poursuite des corrections et la recette du kit
Linux à partir de la baseline ; ces travaux sont suivis dans R27 du plan.
La conformité V2.1 globale reste non acquise. La recette utilise
un compte utilisateur standard et des données synthétiques isolées,
sans toucher au corpus privé ni aux stockages de l’instance principale.
L’installation A de recette sert au cycle de mise à jour/retour arrière,
avec sauvegarde vérifiée et restauration dans une nouvelle racine.

Le modèle par défaut d’une installation neuve est désormais
**`qwen3.5:4b-text`**, selon
[W045](../DECISIONS.md#w045-qwen-35-4b-par-défaut-2b-conservé-au-lancement).
Le choix `qwen3.5:2b` en Q8_0 reste disponible au lancement. Une mise à jour
conserve le choix principal de l’utilisateur : le profil 2B de l’installation
A ne doit pas être converti. Le changement demande un redémarrage ; procédure
dans [Exploitation](../../docs/exploitation/EXPLOITATION.md). Le mode
automatique peut utiliser le GPU pour la génération sur ce couple Linux
qualifié ; cette voie ne vaut pas preuve de qualité métier ni de recette D07.

## Derniers contrôles livrés

Les résultats restent ceux de leurs exécutions datées, sur leurs entrées
et configurations propres. Aucun résultat historique 4B n'est transféré au 2B.

| Lot | Preuve disponible | Portée de la preuve |
|---|---|---|
| Corrections R27 et étude Office R28 | [Publication et validations du 9 octobre](../journal/2026-10-09.md) ; produit `5204d2e`, Python2 661 PASS/20 SKIP, API88 PASS/1 SKIP, web433 PASS, lint/types/build conformes | Corrections livrées ; étude DOCX/XLSX finalisée avec lots proposés, aucun support Office produit |
| Recette du kit B (`5204d2e`) | Fabrication, transport, installation neuve hors ligne, selftest8 et 58 cas navigateur applicables relus indépendamment ; sauvegarde réelle vérifiée | Linux aarch64/JetPack5 seulement ; inventaire DIST-02 rouge sur 4 394 caches ajoutés, échec conservé |
| Correctif RT-02 et kit C (`aabb9808`) | Fabrication/transport/intégrité, installation neuve par défaut4B, selftest huit étapes, launcher/session, arrêt/redémarrage hors ligne ; comparaison0116 stricte et avis indépendant GO971b598b… | 65 125 fichiers/1 191 liens inchangés sans nettoyage ; preuve Linux aarch64. Restauration B→C, anciennes citations/nouvelles questions4B, CPU C, mise à jour A→C et retour arrière avec restauration vérifiés. Refus de cible absente, inventaire final0131 strictement identique et retrait C frais avec données conservées validés indépendamment (GO3967c9d8…). Bureau privé non validé, réserve dans R27-INT-01 |
| Navigation de citation F05 | [Unités, lint, typage, build et parcours Chromium](../journal/2026-10-06.md#r15-3-f05--citation-page-14-déviée-vers-la-page-13) | Correction page14/retour/redimensionnement, pas toutes les géométries du corpus |
| Couverture des passages Q10 | [Essai natif, captures et arrêt](../journal/2026-10-06.md#r15-3-q10--couverture-des-passages-entiers) : huit passages, 40/40 régions distinctes, 69 fragments ; un test strict PASS | Jeu QLONG, une taille desktop ; pas le taux global d'ancres D06.5. Huit avertissements Canvas2D conservés |
| Modèle au lancement | [Parcours 4B/2B/4B et conservation de l'index](../journal/2026-10-04.md#r23--choix-au-lancement-et-parcours-natifs-validés-relevé-2202-utc) | Intégration locale réelle, pas exactitude métier ou qualification générale du 2B |

Les preuves d’installation, hors ligne et sauvegarde/restauration Linux
sont situées dans la [qualification par plateforme de la DoD](../DEFINITION_OF_DONE.md#qualification-linux-w018).
Les nouvelles preuves ne certifient ni le 2B sur toutes les charges ni les
plateformes non exécutées. Les fichiers d’exécution, captures, inventaires
et avis indépendants R27 restent dans `.runtime/qa/r27-20261009/`, sur la SD,
avec leurs cibles et empreintes ; le journal en conserve les références.
Les anciens échecs sont préservés séparément des reprises réussies.

## Réserves explicites

| Sujet | État et incidence pour l'utilisateur | Référence |
|---|---|---|
| OCR P02 | Erreurs persistantes sur signes scientifiques, unités et références dans le texte narratif. Comparer les valeurs extraites au PDF original ; une ligne de tableau exacte ne qualifie pas toute la page | [Diagnostic refusé](../journal/2026-10-06.md#r23-ocr-01--discriminant-des-lignes-réelles) |
| Réponses 2B | Jugement injustifié et assertion avec citation non probante observés ; correctif éditorial refusé. Vérifier chaque assertion dans le passage cité avant utilisation métier | [W037](../DECISIONS.md#w037-candidat-éditorial-2b-refusé-après-un-témoin-unique) |
| Admission et performance | Admission froide 2B mesurée sur un pilote local ; estimation supplémentaire chaude de 512 Mio encore provisoire. Ni charge maximale, sortie de 400 tokens ni latences D07 garanties | [W036](../DECISIONS.md#w036-admission-froide-du-2b-fondée-sur-un-pilote-cpu-local), [D07](../DEFINITION_OF_DONE.md#d07--ram-cpu-et-latence) |
| Ancres et corpus | Q10 ne couvre que le jeu déclaré. Le taux global d'ancres et les gates DEV/final ne sont pas validés ; le corpus privé R19 reste en pause | [D04–D06](../DEFINITION_OF_DONE.md), [plan](../PLAN.md) |
| Plateformes et distribution | Pas de qualification intégrale Windows, Linux x86-64, kit Windows installé ou poste physique CPU/16 Go maximum. Les 61 Gio du Jetson et le GPU ne satisfont pas ce critère | [DoD](../DEFINITION_OF_DONE.md#d07--ram-cpu-et-latence), [déploiement](../../docs/deploiement/DEPLOIEMENT.md) |
| Lanceur du bureau | Dans le bureau privé C, GNOME acquiert son nom sur le bus mais ses interfaces ne sont pas disponibles ; la garde refuse avant activation. Aucun parcours du menu qualifié et cause exacte inconnue ; commandes natives vérifiées séparément | [Recette et réserve](../journal/2026-10-09.md#r27-int-01--bureau-privé--gardes-et-réserve-réelle-23382342-utc) |
| Index et provenance | Migration d'embedding D03.8/comparatif D10.2 non réalisés, purge physique non qualifiée et soumise à autorisation distincte ; certaines traces historiques D11 restent non vérifiables | [D03/D10/D11](../DEFINITION_OF_DONE.md), [précondition du comparatif](../journal/2026-10-06.md#r24-emb-01--précondition-du-comparatif) |

Cette livraison avec réserves **ne déclare pas l'absence de défaut ni la
conformité V2.1 globale**. Une citation valide identifie une source ; elle
ne rend pas automatiquement l'affirmation générée fidèle à cette source.

## Travaux différés et reprise

La poursuite autorisée le 9 octobre se réalise dans le
[plan canonique](../PLAN.md#r27--poursuite-autorisée-du-9-octobre-à-partir-de-la-baseline).
Les seuils, cases non cochées, échecs et preuves restent conservés. Les essais
Windows sont différés par l’utilisateur ; l’hôte Linux x86-64 et le poste
physique CPU/16 Go restent absents. D06.5 n’est pas remesuré, aucune nouvelle
campagne2B n’est engagée et le corpus privé reste en pause. Ces limites
ne sont pas converties en PASS par la recette locale. L’étude Office est
finalisée ; ses lots d’implémentation I-01→08 restent proposés dans R28.
