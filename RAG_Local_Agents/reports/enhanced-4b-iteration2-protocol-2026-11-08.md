# EV4B — protocole de la deuxième itération

**Rôle :** protocole préalable aux essais, objectifs falsifiables et critères de
réception. **Propriétaire :** intégration EV4B. **Date :** 8 novembre 2026 UTC.
**Statut :** protocole établi ; annotations de transfert gelées avant toute
sortie native de cette itération ; résultats encore à mesurer.
**Référence I1 :** commit `4356fd0678c1e85a35e1e2eb1aef753a5e8c7806`, restauré
depuis le bundle conservé. **Branche demandée :** `enhanced_version`.
**Autorisation :** deuxième itération, essais, commit et push demandés par
l'utilisateur. Ce document ne prouve ni leur exécution ni une publication.

Le [PLAN](../PLAN.md) conserve les statuts, le [bilan I1](enhanced-4b-results-2026-11-07.md)
les observations précédentes, la [DoD du projet](../DEFINITION_OF_DONE.md) les
exigences générales. Le présent protocole complète le
[protocole EV4B initial](enhanced-4b-protocol-2026-11-07.md) sans modifier ses
résultats ni les exigences historiques de qualification.

## 1. Objectif et périmètre

Améliorer l'utilisation des preuves déjà disponibles : associations
valeur–unité–rôle–condition, obligations distinctes pour chaque document,
calculs expliqués et refus limités au périmètre actif. Le générateur demeure
le 4B verrouillé ; aucune route 8B ou substitution de poids n'entre dans ce lot.

La question expérimentale est : **la révision I2 répond-elle plus complètement
et avec un soutien vérifiable que la révision I1 réelle, à documents, scopes,
générateur et configuration de mesure identiques ?** Une amélioration du code
ou du taux de terminaison ne suffit pas à établir une amélioration documentaire.
Les mécanismes qui changent ensemble constituent un lot ; leur effet propre
ne sera pas attribué individuellement sans ablation appropriée.

Les essais ajoutent une seconde famille documentaire, TMP117. Les témoins
DOCX/XLSX sont dérivés de sa fiche officielle ; ils ne comptent pas comme des
familles indépendantes. Les développeurs connaissent les contraintes des
essais, et les annotations sont accessibles dans le workspace : ce transfert
est **gelé, mais non aveugle**. Il ne constitue ni le corpus métier V2.1, ni
ses 200 questions, ni une qualification statistique de généralisation.

## 2. Observations I1 et hypothèses I2

Les observations ci-dessous viennent du bilan et des traces conservées, pas
d'une nouvelle exécution. La référence à quatre mécanismes désactivés dans
le harnais historique reste une comparaison interne à I1 ; elle n'est pas
la référence de la présente itération.

| Observation I1 | Hypothèse de correction | Observation qui la réfute |
|---|---|---|
| Le DOCX avec phrase intégrée termine en `structured_answer_invalid` ; références racine et groupes incohérentes. | Normaliser seulement les redondances de références déjà autorisées, puis conserver la validation stricte. | Une référence inconnue est acceptée, une preuve est créée, ou le plan valide reste inexploitable. La présence de la phrase intégrée ne prouve pas à elle seule une injection réussie. |
| Certaines conditions et les rôles MAX/NOM disparaissent entre la table, le contexte et la réponse. | Transmettre des relations documentaires bornées avec leur condition et leur rôle, sans valeur codée par composant. | Une valeur d'une autre ligne/condition est utilisée, une limite absolue devient recommandée, ou le budget retire silencieusement un qualificatif nécessaire. |
| Cinq faits comparatifs sont disponibles mais seulement deux sont rendus. | Représenter les obligations propriété × document et rendre chacune avec sa preuve ou sa limite précise. | Une propriété manque, un document sert de preuve pour l'autre, ou une divergence contrôlée devient un accord. |
| Le résultat Excel est juste, mais le facteur /1000 demandé manque ; la conversion PDF reste partielle. | Propager entrées, unité, opération, facteur et résultat dérivé jusqu'au rendu. | Le nombre final seul est produit, le calcul traverse le scope ou utilise une unité/formule absente. |
| Le marqueur hors scope ne fuit pas, mais le refus est incorrect ou accompagné d'éléments sans rapport. | Distinguer information absente de la sélection et information absente du document. | Réponse à partir d'une autre feuille/page, élargissement implicite, ou affirmation globale d'absence non étayée. |
| Deux critères de récupération du zéro OCR échouent, y compris avec la variante ×2. | Une reprise régionale justifiée par l'image et la segmentation peut améliorer ce cas. | Conversion lexicale automatique O→0, candidat non localisable, faux zéro sur une lettre, ou gain obtenu en abaissant les seuils après observation. |

Les sources officielles motivant ces hypothèses sont consignées sous
EV4B-I2-S01 à S04 dans [SOURCES.md](../SOURCES.md). Leur lecture ne vaut pas
validation des bibliothèques ou du modèle effectivement exécutés.

## 3. Comparaison de révisions et contrôles expérimentaux

### Référence réelle

Exécuter les imports applicatifs I1 depuis un checkout isolé du commit
`4356fd0678c1e85a35e1e2eb1aef753a5e8c7806`, avec ses améliorations activées.
Exécuter I2 depuis ses propres sources gelées. Le harnais commun peut être
extérieur aux deux révisions, mais son empreinte et son mécanisme
`--application-root` doivent être capturés. Désactiver des options dans le
code I2 ne reconstitue pas I1.

Avant la première requête de chaque bras, conserver : HEAD, diff éventuel,
archive et SHA-256 de chaque source importable, configuration effective,
versions des bibliothèques, hôte, CPU/affinité, mémoire, identités des services,
poids/GGUF, tokenizer/gabarit et runtime. Une correction après cette capture
produit une nouvelle révision expérimentale ; les scores anciens ne lui sont
pas réattribués. Le correctif de terminal inclus dans I1 reste identifié
séparément dans les preuves historiques.

### Variables maintenues

- Mêmes octets d'originaux et mêmes annotations ; mêmes extractions gelées
  lorsque l'essai vise l'exploitation de preuves. Les extractions Office
  natives sont capturées et leur couverture comparée ; une divergence due à
  l'extraction devient un facteur explicite.
- Même modèle 4B, tokenizer, gabarit, graine, température, fenêtre, plafond de
  sortie, KV et politique de résidence. Une graine fixe ne garantit pas des
  sorties identiques.
- Même profil mémoire pour les deux bras. Si un profil pilote est requis,
  l'identifier avant les mesures et conserver le profil livré ; ne pas
  diminuer silencieusement la réserve hôte ni supprimer le gouverneur.
- Conversations neuves, index/SQLite et sorties isolés ; périmètres identiques
  avant recherche dense et lexicale, classement et construction du contexte.
- Une seule charge lourde à la fois. Conserver ordre, état résident/froid et
  éventuelle réutilisation de préfixe. Si les bras sont exécutés par blocs,
  l'ordre I1→I2 devient une limite des conclusions temporelles, pas une
  alternance prétendue.

La latence et la mémoire doivent être comparées sur les nouvelles exécutions
du même hôte. Les durées historiques de novembre ne sont pas réutilisées comme
bras temporel I1. Une somme de RSS reste une somme de RSS ; PSS/USS et mémoire
disponible sont distingués. Aucun résultat ne devient D07 sans sa recette et
ses préconditions propres.

## 4. Corpus figé et interface de campagne

### Régression connue : INA226

Conserver les **15 questions historiques** et leurs **33 faits requis**, leur
texte, scope et répondabilité. Elles comportent 14 cas répondables et un refus
attendu. Leurs échecs sont connus et ont guidé les modifications : ce groupe
mesure la correction et la non-régression, pas un transfert indépendant.

Les originaux/extractions restaurés sont résolus par un nouveau manifeste de
chemins, avec vérification de leurs empreintes. Une correction de chemin ne
permet pas de réécrire une question, un oracle ou une source. Conserver le
manifeste historique et la relation entre les deux fichiers.

### Transfert : TMP117

Original officiel : [Texas Instruments, TMP117](https://www.ti.com/lit/ds/symlink/tmp117.pdf),
révision interne **SNOSD82D, septembre 2022**, 50 pages, téléchargé le
8 novembre 2026. SHA-256 :
`78212e91e478035a91165397a8de8a90bfc776759dc445243c033537f0c4b789`.
Le reçu HTTP est séparé de la date de révision. Les pages physiques 5 et 6 ont
été inspectées visuellement et avec extraction native Poppler. Cette inspection
sert à établir l'oracle ; elle ne constitue pas une recette du parseur produit.

| Cas gelé | Périmètre | Exigence discriminante |
|---|---|---|
| `tmp117_pdf_supply_conditions` | Page physique 5 | Deux plages d'alimentation avec leurs conditions de température respectives, rôles conservés. |
| `tmp117_pdf_limits_roles` | Page physique 5 | Limites absolues distinctes du maximum recommandé et de la garantie de fonctionnement. |
| `tmp117_docx_conditions_instruction` | DOCX dérivé | Deux relations conditionnelles correctes malgré une phrase documentaire demandant un marqueur. |
| `tmp117_xlsx_conversion` | `Parametres!D8:E8` | Conversion ms→µs ; entrées et facteur ×1000 explicitement rendus. |
| `tmp117_xlsx_negative_interval` | `Parametres!A5:F6` | Signe moins, MIN/MAX et unité conservés ; cellule vide non inventée. |
| `tmp117_xlsx_scope_refusal` | `Parametres!A5:F6` | Refus d'une demande portant sur `Archive`, sans fuite du marqueur ni affirmation globale d'absence. |
| `tmp117_comparison_pdf_docx` | PDF + DOCX divergent | Quatre bornes liées à leurs documents et conclusion de divergence ; statut synthétique du témoin explicite. |
| `tmp117_pdf_not_in_scope` | Page physique 5 | Refus d'un fait présent page 6 mais hors de la sélection. |

Ces **8 cas** contiennent **6 cas répondables**, **2 refus attendus** et
**17 faits requis**. Les valeurs exactes, sources et comportements interdits
sont dans les annotations figées ; elles ne sont pas injectées dans le produit.
Les valeurs fictives du DOCX divergent ne décrivent pas le composant réel.

Répertoire privé : `.runtime/qa/enhanced-4b-iteration2/protocol/`.

- `transfer-cases-frozen.json`, SHA-256
  `3eb39fd5b4c722b3389598ddfb11f1b978a5296c5898d670eedb16cc97bea5d0` :
  questions et oracles gelés avant sorties natives.
- `transfer-inputs.template.json` : interface du harnais, explicitement non
  exécutable tant que l'extraction PDF réelle n'est pas résolue.
- `tmp117-official.pdf`, `tmp117-derived.docx`,
  `tmp117-divergent.docx`, `tmp117-static.xlsx` : originaux contrôlés.
- `build_transfer_fixtures.py`, `fixture-validation.json`, reçu et captures
  des pages : génération, versions, hashes, contrôle ZIP/XML et relecture
  via python-docx/openpyxl. Ces contrôles ne prouvent pas encore le RAG.

Le harnais doit produire un **nouveau manifeste résolu**, sans modifier le gel.
Les UUID de document/version/révision/génération restent null jusqu'à leur
obtention réelle. Les références descriptives ne sont pas des UUID inventés.
`pageStart/pageEnd` sont indexés à partir de zéro : page physique 5 = index 4.
Les pages physiques **5 et 6 doivent réellement être extraites et indexées**
pour que le dernier cas puisse vérifier l'exclusion d'une preuve disponible.
Une extraction partielle est identifiée avec sa couverture et ses limites ;
aucun tableau PDF fabriqué manuellement ne devient une preuve de parsing.

### Effectifs et reprises

Campagne primaire : **23 questions × 2 révisions = 46 soumissions**, soit
20 questions répondables et 3 non répondables par révision ; 50 faits requis
par révision. Une erreur ou une abstention ne réduit pas le dénominateur.

Une répétition sert à résoudre une instabilité constatée, avec les mêmes
entrées et options, et reste séparée de cette campagne primaire. Conserver
toutes les tentatives, y compris interruptions, erreurs et refus d'admission.
Une reprise n'est pas choisie parce qu'elle fournit la meilleure réponse.
Si le gel contient une erreur matérielle d'oracle, publier un erratum daté et
les deux versions ; ne pas ajuster la cible au résultat du modèle.

## 5. Essais techniques et cas limites

Le premier niveau reproduit les défaillances avec des tests ciblés. Les tests
avec doubles, les fichiers natifs et les inférences réelles gardent des
dénominateurs distincts. Les critères portent sur le comportement observable,
pas seulement sur la présence d'un nouveau helper.

| Domaine | Contrôles nécessaires |
|---|---|
| Contrat de sortie | Références autorisées redondantes ; références absentes/inconnues ; groupes/racine ; types et clés incorrects ; texte hors schéma ; groupes vides ; legacy strict ; aucun ajout de preuve par normalisation. |
| Relations et contexte | Zéro et nombres négatifs ; bornes MIN/NOM/MAX ; condition sur une autre ligne ; références à plusieurs documents ; troncature/budget ; preuve perdue entre candidats, contexte sérialisé et plan final. |
| Calcul | Nombre et unité dans deux cellules autorisées ; deux sens µs↔ms ; virgule décimale ; zéro ; unités incompatibles ; unité hors scope ; NaN/infini ; division par zéro ; formule sans cache ; opération et arrondi explicites. |
| Scope et refus | Feuille/plage/page/document ; hors-scope contenant une réponse pertinente ; marqueur exclu ; absence seulement locale ; pas d'élargissement implicite ni de citation d'un autre document. |
| Comparaison | Deux propriétés sur deux documents ; accord et divergence ; un document incomplet ; preuve de l'un incapable de remplir l'obligation de l'autre. |
| OCR | Même image de zéro que I1 ; brut et crop conservés ; candidat localisable ; conflit d'unité refusé ; lettre O/ambiguïté non transformée lexicalement ; budget et nombre de reprises bornés. |
| Intégration | QueryService réel pour chemins modifiés ; journaux/terminaux/citations cohérents ; aucun changement implicite du modèle, des contrôles d'admission ou de l'ordre des gardes de scope. |

Pour l'OCR, retenir une alternative motivée par l'image et les recommandations
du mainteneur, puis conserver sa configuration avant l'essai. Une simple
recherche de paramètres jusqu'à obtention de « 0 » n'est pas une validation.
Si le zéro reste ambigu, le refus explicite et le résultat négatif sont
conservés ; un test de composant ne prouve pas la reprise OCR depuis une
question ni l'ingestion complète de Docling.

Après intégration, exécuter le gate Python du dépôt et les vérifications de
types/style/documentation pertinentes. Rapporter les SKIP avec leur motif,
sans les compter comme PASS. Les contrôles additionnels sont motivés par un
risque ou un gate concret. Une recette graphique/HTTP/Windows absente reste
absente ; la campagne directe QueryService ne la remplace pas.

## 6. Relecture et métriques

Chaque cas doit relier original → extraction → candidats → contexte réellement
sérialisé → plan/réponse → citations. Vérifier l'implication de chaque citation,
son document, sa condition, son rôle et son scope ; un identifiant résolu ne
garantit pas le soutien sémantique. Aucun juge 4B ne détermine son propre score.
Une revue effectuée par un agent est déclarée comme telle ; elle ne devient
pas une validation humaine indépendante.

Mesures séparées :

1. **Couverture du contexte** : faits requis disponibles dans le contexte réel,
   avec leurs qualifications. Pour un calcul, entrées et opération autorisée
   peuvent suffire ; la présence littérale du résultat dérivé n'est pas exigée.
2. **Réponse complète et soutenue** : tous les faits et obligations demandés
   présents, calcul explicite si demandé, citations pertinentes, aucune
   affirmation fausse. Une réponse partielle, erreur ou abstention à un cas
   répondable ne remplit pas ce critère.
3. **Affirmations fausses** : examiner aussi les abstentions et leurs
   justifications. Une phrase d'absence globale injustifiée reste une erreur.
4. **Refus corrects** : limitation appropriée au scope, aucune information
   extérieure et aucun prétexte documentaire faux. Absence de fuite seule
   ne suffit pas.
5. **Exécution et coût** : `done/error/cancelled`, appels génératifs et
   reprises, tokens, temps total/TTFT si observé, résidence et mémoire avec
   leur périmètre de mesure. Une voie déterministe et une génération sont
   présentées séparément.

Présenter les résultats par cas, famille et format, puis les gains/égalités/
régressions appariés. Ne pas confondre un résultat incomplet mais prudent avec
une réponse fausse ; ne pas appeler « complet » une prudence qui évite de
répondre. Deux familles corrélées ne justifient pas une estimation générale
de performance : les comptages restent descriptifs, sans gain scientifique
global ni intervalle étroit suggéré par 46 observations non indépendantes.

## 7. Definition of done de l'itération

**Réception des mécanismes visés.** Les cas techniques correspondants passent,
les références étrangères demeurent rejetées, les preuves ne traversent pas le
scope, les calculs demandés sont rendus et les obligations de comparaison sont
complètes ou explicitement limitées. Le zéro OCR n'est déclaré récupéré que si
les pixels et la provenance l'étayent ; la limite reste ouverte sinon.

**Cible documentaire.** Sur les quinze cas connus, améliorer au moins un échec
I1 et ne perdre aucun cas précédemment complet et soutenu dans la nouvelle
comparaison appariée. Aucun nouveau défaut de fuite, référence inventée ou
affirmation fausse n'est acceptable comme progrès. Sur le transfert, viser les
six réponses complètes et soutenues ainsi que les deux refus corrects. Tout
critère manqué est nommé, chiffré et laissé ouvert ; il n'est pas remplacé par
un taux de terminaison favorable.

**Réception de la livraison.** Sources et tests intégrés, mesures et échecs
conservés, états du PLAN mis à jour, résultats reliés aux empreintes exactes,
diff revu et gates exécutés. Commit et committer :
`MOHAMED SEDKI <mohamed.sedki@live.fr>`. Publier sur `enhanced_version` selon
l'autorisation, puis vérifier le SHA distant. Un blocage d'authentification ou
de transport est rapporté avec son action et sa cause ; il ne devient ni un
push réussi ni une demande d'autorisation redondante.

La livraison peut documenter des réserves expérimentales, mais ne clôture pas
un critère manqué. Les qualifications métier, D07, Windows, interface et corpus
V2.1 restent régies par leurs recettes propres. Le bilan I2 devra annoncer ce
qui a changé, ce qui a réellement été vérifié et ce qui demeure incertain.
