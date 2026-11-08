# I4 — résultats de fiabilisation et état de qualification

**Statut : VÉRIFICATIONS TERMINÉES — diffusion non qualifiée ; publication en cours.**
**Date :** 8 novembre 2026, UTC. **Propriétaire :** qualification et intégration RAG.
**Référence immuable :** `fa3eabce5ab0c309b1ca8f01602fced2eb7f1dd8`, branche `enhanced_version`.
**Candidat :** fichiers produit/configuration et harnais gelés le
`2026-11-08T17:38:49.575804+00:00` ; aucun SHA de commit final attribué à ce stade.

Ce bilan distingue les corrections réalisées, leurs contrôles de développement,
les résultats de qualification et les critères non atteints. Le [protocole préalable](production-4b-protocol-2026-11-08.md)
fixe les critères ; le [PLAN](../PLAN.md) reste le suivi canonique. Les échecs de
référence et les premières tentatives de harnais sont conservés. Aucun essai
ci-dessous n'est une qualification Windows ni une décision de déploiement.

## 1. Résultat de la campagne

**Le candidat ne satisfait pas le critère de fidélité D01.** Sur H03 du transfert,
il publie `Min = C 0.25 V`, alors que le tableau original place **0,25 V sous
`Typ`**, pour une température de 0 °C, et laisse `Min` vide. L'abstention correcte
sur la valeur demandée à 150 °C ne neutralise pas cette association fausse.
Le contrôle de spans littéraux réussit sur cette réponse : il vérifie la fidélité
à l'extraction, qui porte ici une structure erronée, sans établir la fidélité de
la relation de colonne au PDF original. **Ce défaut bloque la qualification de
diffusion**, indépendamment des succès de tests ou des autres réponses. Le gel et les critères sont restés inchangés pendant toute la campagne.

La nouvelle référence I4 atteint **11/12 positifs stricts et 18/18 limites** sur les
30 cas contrôlés I3, puis **7/8 cas stricts** sur le bloc Office natif. Le seul
positif insuffisant dans ces deux blocs restitue les faits attendus mais ajoute
une réserve globale injustifiée : ce n'est pas un refus total. Le score automatique
12/12 des positifs contrôlés reste visible dans la sortie brute ; la relecture
séparée le corrige à 11/12, sans modifier la réponse ni l'oracle.

La campagne contrôlée du candidat de développement atteint, après relecture stricte des
trente sorties, **12/12 positifs et 18/18 limites** : un gain sur P01, 29 verdicts
inchangés et aucune régression observée. Les faits positifs étaient déjà complets
dans 12/12 cas en référence ; le gain retire la réserve injustifiée, sans ajouter
de fait ni augmenter les refus. Les douze positifs du candidat utilisent une voie
déterministe de restitution des preuves ; ce résultat ne mesure pas une meilleure
inférence du modèle 4B. Cette campagne précède le dernier correctif du sujet de
liste ; les contrôles ciblés de ce dernier delta sont présentés séparément.

Sur le gel final, le bloc **Office natif candidat atteint 8/8 cas stricts**, contre
7/8 en référence, après deux relectures séparées concordantes. Le gain concerne
encore la réserve inutile de P01 ; les faits positifs étaient complets dans les
deux bras, sans refus positif. Les quatre positifs du candidat suivent désormais
une voie déterministe ; ses quatre limites appellent réellement le modèle 4B.
Une redondance d'en-tête nouvelle sur L16 reste une régression de présentation.

Les deux PDF TI ont été extraits intégralement par le vrai worker de la référence,
puis indexés et interrogés sur la page d'indice 0 conformément aux questions
gelées. Les deux requêtes se terminent par **`trace_budget_exceeded` avant tout
appel au modèle**. Ces deux échecs restent les résultats primaires de référence.
La répétition des métadonnées de page dans les traces est un défaut produit
identifié pendant le développement, distinct du défaut de sélection/liaison
documentaire que ces questions doivent aussi évaluer.
L'échec concerne le mode `full` activé explicitement par le harnais ; il ne démontre
pas un échec des mêmes requêtes avec le mode `hashes` du profil par défaut.

Sur le candidat final, les deux requêtes PDF atteignent `done` et les **quatre
relations attendues sont rendues avec leur appui**. Leur score strict reste
**1/2** : TMP117 répond correctement, mais INA226 ajoute un diagnostic de propriété
manquante alors que son extrait contient bien l'alimentation demandée. Les deux
relectures concordent. La disponibilité passe donc de 0/2 à 2/2, la complétude
factuelle du candidat vaut 2/2, et son succès strict vaut 1/2 ; ces mesures ne sont
pas interchangeables. Le critère natif/transfert D07 n'est déjà pas atteint sur
ce cas primaire ; le transfert final échoue également à son seuil fixé.

Les contrôles de développement démontrent des progrès locaux sur la sélection,
les groupes de liste PDF, les réponses qualitatives et les frontières d'exploitation.
Les **sept intégrations OCR réelles passent désormais**, avec leur prérequis de
police, après provisionnement et correction ciblée. Le transfert final reste à
0/6 positifs stricts et 1/2 limites, et les deux scans à 0/2 strict. Les succès
de développement ne compensent ni la mauvaise relation de colonne H03 ni les
unités OCR erronées ensuite publiées. Le parcours HTTP/SSE réel réussit ses
contrôles opérationnels ; son verdict documentaire est conservé séparément.

La suite portable complète exécutée **sur le gel exact final**, après l’arrêt de
tous les moteurs natifs et avec un nouveau temporaire hors dépôt, termine avec
**4 105 réussites, 25 ignorés, 45 désélectionnés et un avertissement**, en
**578,02 s** selon pytest. Aucun échec ni erreur n’apparaît ; les cinq anciens
échecs CMake ne réapparaissent pas. Les 88 fichiers produit et 46 harnais restent
identiques au gel après cette exécution. L’avertissement concerne la dépréciation
d’un transport du client de test Starlette, pas une erreur de test.

La précédente suite complète à **4 085 réussites**, en 499,01 s, reste conservée
avec sa portée temporelle antérieure au correctif du sujet de liste. Les vingt
nouveaux cas de ce sujet expliquent la différence de collecte ; aucun cas
antérieur n’a été retiré et ce ne sont pas vingt défauts corrigés. Après ce
dernier correctif, le lot ciblé de 284 tests, Mypy sur 134 fichiers et Ruff sur
`services`, `tests`, `tools` avaient également réussi. Les intégrations pertinentes
hors OCR et tests longs donnent 27 réussites, trois ignorés Windows et 93
désélectionnés. Ces succès logiciels ne changent pas les échecs documentaires ni
le statut des plateformes absentes.

## 2. Protocole, corpus et conditions

Le protocole a été figé avant les changements produit, le
`2026-11-08T15:51:40.045050+00:00`, SHA-256
`7ae9c5a2c583bc05a5a652b2afbe7f1921f62ba55162d865316d3a62e656f3de`.
Le worktree de référence est séparé du candidat. Le harnais choisit le checkout
avant les imports applicatifs et contrôle l'absence de modification pendant les
blocs. Les résultats natifs ont des magasins, bases, ports et groupes de processus
isolés ; les arrêts de groupes font l'objet de reçus.

Le [certificat de gel du candidat](production-4b-candidate-freeze-2026-11-08.json)
porte le SHA-256
`be7ad4c46c89de7c3c351fa0f3fc7a79369c8e336542474b01f7586467c37d9b`.
Il fixe 88 fichiers produit/configuration, 46 fichiers de qualification et les
artefacts d'exécution. Leur contenu courant a été vérifié contre les empreintes
du certificat, sans écart, avant la qualification native du candidat. Les
modifications documentaires ultérieures n'autorisent aucun réglage du produit
sur les réponses du transfert.

| Élément | Condition utilisée ou fixée |
|---|---|
| Générateur unique | Qwen3-4B, Q4_K_M, alias verrouillé `qwen3-4b-enhanced:q4km` |
| Poids GGUF | SHA-256 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| Inférence | Ollama 0.35.0 ; CPU, 4 threads au maximum ; contexte 8192 ; température 0,2 ; top_p 0,9 ; seed 0 ; `think=false` ; KV q8_0 ; flash attention activée |
| Sortie | Plafond général 1536 tokens ; plafond factuel 768 ; aucun changement exploratoire de ces paramètres |
| Recherche | Qdrant 1.19.1 ; multilingual-E5-small INT8 ; mêmes artefacts que la référence |
| Extraction | Docling 2.131.0 ; docling-core 2.99.0 ; pypdfium2 5.13.0 ; bibliothèques Office du verrou |
| OCR de référence | Tesseract 5.4.0 construit en espace utilisateur, Leptonica 1.87 ; binaire original SHA-256 `d6433dab06f0c58ff3536560b208e92c156664f7fe48210f00f7a17f75e0c3ac` ; utilisé avec le checkout de référence pour les préparations PDF, transfert et scans |
| OCR candidat | Tesseract 5.4.0 avec correctif ciblé, SHA-256 `61461b50cb385288c9c1a0382c5836202bdb7ded69b899b04f83122399959c97` ; utilisé seulement avec le candidat ; aucune substitution par le Tesseract système 5.5 |
| Hôte observé | Linux x86-64, Python 3.12.14, 9 CPU visibles, 10 451 423 232 octets RAM, sans swap |
| Réserve mémoire | 1536 Mio, conservée ; les essais injectés ne constituent pas une mesure native d'admission |
| Traces | Profil : `hashes`, 2 097 152 octets/requête, 67 108 864 octets au total. Campagne native : surcharge explicite `full`, 8 388 608 octets/requête. Ces plafonds physiques n'ont pas été augmentés par le codec. |
| Non-régression documentaire | 30 questions I3 et leurs oracles inchangés ; sources Office synthétiques, cas répondables et limites séparés |
| Développement I4 | 32 frontières prévues : sélection, structure, qualitatif, exploitation ; cas supplémentaires de garde séparés |
| Transfert | 8 questions, 6 répondables et 2 limites, sur 3 PDF officiels Analog Devices distincts des deux TI ; 2 scans déterministes dérivés ; auteurs des corrections de sélection, contrat et ingestion tenus à l’écart des oracles avant gel final, avec chevauchement de rôle du préparateur des oracles/auteur du codec déclaré ci-dessous |

Le reçu de gel du transfert porte le SHA-256
`becadc6f097cf60a67d52f7e37a3b1d4cdfe6d921ec4afc1d228fce793a2052d` ;
les questions/oracles privés portent
`748affc2f4d4ccc7d9cf60aed65af88945388e1140883ad8424d3d3b7291a241`.
Cette séparation est une discipline de travail dans un espace partagé, sans
barrière technique d’accès. Elle n’est pas absolue : le préparateur des oracles
a ensuite implémenté le codec de trace, qui est du code produit. Les auteurs des
corrections de sélection, contrat et ingestion n’ont pas consulté les oracles
avant le gel. Le booléen `implementers_have_not_consulted` du reçu historique
doit être lu avec cette limite de rôle ; le reçu gelé n’est pas réécrit. Aucune
sortie native de transfert n’a servi à ajuster le produit avant le gel, et aucun
produit, harnais ou critère n’a été modifié après ouverture des résultats. Il ne
s’agit donc pas d’un audit produit entièrement séparé de ses auteurs. Le corpus
reste électronique ; aucune généralisation interdomaines n’est inférée.

Les [quatre manifestes publics](production-i4-corpus/freeze-receipt.json) sont
désormais copiés à l'identique après le gel produit. Une première matérialisation
avec téléchargement officiel a échoué sur la résolution DNS. Cette tentative
reste conservée ; elle ne prouve pas un nouveau téléchargement réussi. Une
reprise dans un nouveau dossier à partir des originaux locaux gelés a réussi :
trois PDF originaux, deux paires scan/PDF et les quatre manifestes ont les
empreintes prévues. La revue des artefacts et des deux images existantes a été effectuée par l'agent
qui a implémenté le matérialiseur, par des contrôles distincts du rendu. Elle ne
constitue ni une seconde implémentation indépendante du rendu, ni une nouvelle
extraction, ni une réussite OCR ou documentaire.

Les poids Docling, E5 et 4B sont communs. Les binaires Tesseract sont distincts
entre référence et candidat, conformément à l'addendum OCR ; les extractions de
chaque bras sont séparées. La comparaison globale mesure donc les changements
produit **et** OCR. L'ablation locale du correctif `normmatch` reste une preuve
distincte, sans attribution causale globale au seul code applicatif.

Les réponses font l'objet d'une **relecture séparée par agent, non aveugle**.
Les rôles sont explicites : `audit_validation` a préparé les oracles et les harnais,
ainsi que le codec de trace, mais n'a pas écrit le contrat de réponse ;
`audit_grounding` a écrit ce contrat et participe aux relectures des réponses ;
`audit_ingestion` a écrit le matérialiseur et contrôle ses artefacts. Une seconde
lecture par un autre agent est distinguée de la revue par l'auteur du composant.
Les relectures comparent question, source et réponse, sans prendre le statut du
contrat comme oracle. Elles ne sont ni une évaluation humaine, ni un audit dont
tous les relecteurs seraient extérieurs à l'implémentation, ni une preuve
universelle d'implication sémantique.

## 3. Comparaison documentaire : sorties réellement exécutées

| Bloc | Référence I4 exécutée | Candidat I4 observé | Interprétation |
|---|---:|---:|---|
| Contrôlé I3, positifs stricts | **11/12** | **12/12** | Score automatique 12/12 dans les deux bras ; la relecture retrouve le défaut P01 seulement en référence. |
| Contrôlé I3, limites | **18/18** | **18/18** | Trois erreurs de blocage attendues dans chaque bras ; elles ne sont pas des réponses utiles positives. |
| Office natif, strict global | **7/8** | **8/8** | Positifs stricts 3/4 → 4/4 ; limites 4/4 → 4/4. Deux relectures concordantes ; 8 états `done` dans chaque bras, aucun échec d'admission dans ce bloc. |
| Office natif, contenu positif complet | **4/4** | **4/4** | Seule la réserve injustifiée de P01 disparaît ; zéro refus positif dans les deux bras. |
| PDF TI natif, états `done` | **0/2** | **2/2** | Les deux erreurs de trace de référence restent au dénominateur. Candidat : un appel modèle INA, une voie déterministe TMP. |
| PDF TI natif, strict | **0/2** | **1/2** | INA échoue à cause de sa réserve injustifiée ; TMP satisfait l'oracle. Deux relectures concordantes. |
| PDF TI natif, contenu demandé complet | Aucune réponse | **2/2** | Les quatre relations demandées sont citées correctement ; cette présence ne suffit pas à un succès strict. |
| Transfert réservé, strict | **0/6 positifs, 0/2 limites** | **0/6 positifs, 1/2 limites** | Gain H08 seulement ; 7 verdicts stricts inchangés. H03 conserve une fausse liaison de colonne. |
| Transfert, contenu positif complet | **2/6** | **1/6** | Régression H04 : alimentation présente dans le prompt mais absente du rendu ; H05 complet avec réserve injustifiée. |
| Transfert, états `done` | **6/8** | **7/8** | Deux erreurs de trace avant modèle en référence ; un vrai appel 4B puis timeout dans le candidat. Les erreurs restent au dénominateur. |
| Scans réservés, strict | **0/2** | **0/2** | Deux abstentions totales → aucune abstention totale, sans gain strict ; les deux réponses candidates reproduisent des transcriptions inexactes. Deux relectures concordantes. |

### Vérification des sources et des limites

Dans le bloc contrôlé, les 32 objets de citation ont été relus contre les
paragraphes/tableaux DOCX ou les cellules XLSX réellement générés et leurs hashes.
Les 27 états `done` et les trois erreurs attendues ont été conservés. Aucun ajout
factuel ou dépassement de scope n'a été observé sur cette relecture. Cela ne
constitue pas une mesure de sensibilité à tous les ajouts possibles.

Les 31 objets de citation du candidat ont fait l'objet de la même vérification,
avec contrôle supplémentaire des offsets, hashes de bloc et révisions de la base.
Les 33 fichiers originaux sont identiques octet pour octet à ceux de la référence.
La différence de nombre de citations vient de L09 : une seule fin de paragraphe,
contenant la réserve explicite à 85 °C, remplace les deux fragments de référence.
Le contrôle reste réussi ; cette différence n'est pas comptée comme un second gain.

Les limites comprennent deux abstentions faute de source applicable, deux
divergences documentaires, dix restitutions partielles/qualifiées, trois blocages
attendus et une reconstruction canonique sûre. Le cas L17 conserve le texte de la
base vérifiée, sans publier le texte altéré du résultat de recherche. Son oracle
autorise cette réponse fidèle ; il n'impose pas artificiellement un refus.

Le bloc Office natif de référence utilise le vrai générateur dans cinq cas et une
voie déterministe dans trois cas ; le candidat en utilise respectivement quatre
et quatre. Les neuf objets de citation de chaque bras sont relus contre les
originaux. La seconde lecture du candidat contrôle également ses treize blocs,
leurs hashes, versions, révisions et offsets en caractères Unicode. Les neuf
originaux Office ont les hashes gelés. La somme décimale et la conversion d'unité
sont recalculées à partir des cellules originales : `1.25 + 2.75 = 4` et
`125 µs / 1000 = 0.125 ms`. Les entrées et la méthode sont traçables ; ces résultats
ne sont pas prétendument lus dans les documents ni calculés librement par le
modèle. Les limites de température, négation et note de tableau sont conservées.

Deux défauts d'usage restent visibles. L16 répète désormais l'en-tête du tableau,
soit dix marqueurs de citation pour neuf sources distinctes dans ce bras. Cette
régression de concision ne transpose pas la plage à 85 °C et n'ajoute aucun fait.
P10 et P11 gardent, comme en référence, le warning lexical erroné
`identifier_present_no_answer_evidence` malgré leurs calculs corrects et tracés.
Le verdict strict porte sur la réponse et son appui ; il ne masque pas cette
incohérence des avertissements.

**Limite de mesure conservée :** le proxy automatique de présence littérale dans
le contexte donne 14/15 sur les deux bras contrôlés. Son seul négatif P05 est une
question de tableau résolue par la voie déterministe, sans appel au sélecteur
génératif. Les cellules/en-têtes du résultat final sont corrects. Ce proxy de
messages sérialisés ne doit pas être renommé « rappel sémantique » ni corrigé
rétroactivement pour afficher une couverture parfaite.

### Extraction complète des deux PDF TI

| Bras/document | Pages traitées | Pages/zones déclarées non résolues | Pages avec OCR | Temps worker | Pic RSS des processus worker surveillés |
|---|---:|---:|---:|---:|---:|
| Référence INA226 | 41/41 | 38 pages, 72 zones | 0 | 234,519 s | 2 324 111 360 octets |
| Candidat INA226 | 41/41 | 38 pages, 71 zones | 1 | 272,693 s | 2 254 065 664 octets |
| Référence TMP117 | 50/50 | 47 pages, 108 zones | 0 | 242,737 s | 2 190 942 208 octets |
| Candidat TMP117 | 50/50 | 47 pages, 108 zones | 0 | 284,022 s | 2 290 917 376 octets |

Les quatre extractions portent `ready_partial`. Des zones graphiques non interprétées
et des replis de la voie structurée vers la voie native restent déclarés. Toutes
les pages traitées ne signifient pas tout le contenu interprété. Les questions
portent toujours sur l'indice de page 0 ; le traitement intégral évite d'injecter
l'ancienne extraction limitée à une page et sans les nouvelles métadonnées.
Les workers sont arrêtés et les sources sont restées stables pendant ce bloc.

**La baisse de 72 à 71 zones non résolues sur INA226 n'est pas un gain de
fidélité OCR démontré.** Sur la page physique 13, d'indice 12, le candidat ajoute
59 fragments textuels OCR que la revue des données enregistrées signale comme
bruités, avec des mots et signes monétaires aberrants. La zone graphique reste
marquée `GRAPHIC_INTERPRETATION_UNAVAILABLE`. Les offsets et boîtes sont présents,
mais aucune confiance par mot ni nouvelle vérification visuelle n'étaye ici les
caractères ajoutés. Ce constat concerne une zone hors de la page d'indice 0
interrogée ; les blocs textuels et géométriques de cette page 0 sont inchangés
entre les deux bras. Le corpus complet demeure partiellement compris.

### Réponses PDF : faits complets, réserve encore injustifiée

INA226 restitue la plage de bus **0 à 36 V** et l'alimentation **2,7 à 5,5 V**,
dans deux sources effectivement citées sur la première page. L'alimentation est
aussi présente dans un autre fragment conservé. Le diagnostic de couverture
affirme néanmoins qu'une propriété manque. La revue du contrat constate une
grammaire locale qui reconnaît mal la propriété placée après l'intervalle et le
rôle `typical` du courant voisin. Ce rôle incorrect n'est pas repris comme une
affirmation dans le texte de réponse sur la tension ; les deux plages sont justes. **Le diagnostic de
couverture reste injustifié**, et le résultat strict est un échec. La bonne
sélection des passages ne suffit donc pas encore à une réponse sans réserve
superflue.

TMP117 conserve les deux relations sous le même titre de liste : **1,7 à 5,5 V de
−55 à 70 °C**, puis **1,8 à 5,5 V de −55 à 150 °C**. Les dépendances du titre,
des enfants et de la fermeture de liste sont réunies dans la citation de page 1.
Les conditions ne sont pas interverties. Le titre et la ligne de fermeture sur
la résolution sont répétés ; ce texte est exact mais hors question et peu concis.

Les deux relectures concordent sur **1/2 strict et 2/2 factuellement complets**.
La seconde vérifie aussi les deux images de page 0 déjà existantes, sans nouveau
rendu, ainsi que les hashes des originaux et les identités, offsets, hashes et
boîtes des onze blocs utilisés. Les sorties conservent neuf sources au total ;
trois sont effectivement utilisées par quatre marqueurs de citation. La présence
des six autres sources n'est pas créditée comme appui d'une affirmation publiée.

### Dépassement de trace et correction avant gel

Le produit sérialise les métadonnées complètes de la page dans chaque bloc source.
Pour INA226, l'événement `retrieval` occupe 3 558 697 octets. Il contient 133 copies
du même dictionnaire de page de 24 957 octets : **3 319 281 octets, soit 93,27 %**
de l'événement. La répétition entre `results`, `top10`, la recherche complémentaire
et les contextes s'ajoute à celle des blocs. TMP117 dépasse le budget dès la
première capture de recherche ; son payload refusé n'a pas été écrit et sa taille
exacte n'est donc pas présentée comme mesurée.

La correction encode seulement les gros événements `full` en version 2, avec un
registre de pages par SHA et des chemins typés. Les petits événements restent en
version 1. La chaîne stockée est vérifiée avant reconstruction, puis le hash et la
taille du payload original sont contrôlés. Aucune recherche de fichier/réseau ni
interprétation de marqueur contenu dans le texte documentaire n'est introduite.

Les seuils ont été fixés avant les essais du correctif : événement d'au moins
256 Kio, économie minimale de 4 Kio, budget physique de campagne **8 Mio inchangé**,
reconstruction limitée à 32 Mio/événement et 64 Mio/trace, 4096 références,
512 pages distinctes, profondeur 64, bornes supplémentaires du nombre de nœuds.
Cette représentation ne change ni les plafonds RAG ni le contenu des prompts ou
des citations. Les bornes logiques et physiques sont distinctes et vérifiées.

Le jouet reproduisant plus de 8 Mio de pages répétées échoue avant correction.
Après correction et revue indépendante, 121 contrôles ciblés de codec, traces,
rejeu et états terminaux passent. Un réencodage
**hors ligne** de la trace INA originale conserve exactement ses sept payloads et
réduit le fichier de **7 902 770 à 735 199 octets**. Il ne réexécute aucune requête,
ne produit aucune nouvelle réponse et n'annule aucun échec primaire.

La campagne native finale utilise ensuite cet encodage sans dépassement de
budget. Les fichiers finaux vérifiés, distincts des métriques capturées avant la
persistance terminale, donnent :

| Requête candidate | Octets stockés finaux | Payloads reconstruits | Événements finaux | Dont version 2 | État terminal vérifié |
|---|---:|---:|---:|---:|---|
| INA226 | 1 042 270 | 7 881 531 octets | 13 | 4 | `query.done` |
| TMP117 | 764 867 | 6 693 789 octets | 8 | 2 | `query.done` |

La chaîne stockée et les hashes des payloads reconstruits sont vérifiés lors des
deux relectures. Le champ `run.metrics.execution_trace` porte explicitement le
stade `before_terminal_persistence` : son compteur et son booléen terminal ne
remplacent pas cette lecture des fichiers clos. Cette preuve d'intégrité ne
change pas le verdict strict d'INA226.

### Transfert : seuil strict non atteint et régression de contenu

Les trois PDF de référence sont entièrement parcourus : 7, 11 et 14 pages, avec
2 209 blocs et neuf checkpoints dont les hashes et identités sont vérifiés. Ils
restent tous `ready_partial`, sans page traitée par OCR. Cette intégrité matérielle
ne garantit pas que les tableaux ou le corps des pages sont correctement compris.

La revue amont constate notamment un corps de description visible mais absent
des blocs pour H02 ; une ligne d'alimentation fusionnée en première colonne pour
H01 ; une valeur nominale placée en colonne `Min` au lieu de `Typ` dans la page
de H03 ; et deux conditions/valeurs fusionnées par cellule, avec en-tête général
fragmenté, pour H07. Les passages utiles à H04, H05, H06 et H08 sont présents.
Ces observations ne constituent aucun verdict de réponse : une abstention
correcte d'un cas limite ne validerait pas, à elle seule, l'extraction défectueuse
de sa page.

La référence termine six requêtes et échoue techniquement sur H06 et H08 par
`trace_budget_exceeded`, avant tout appel au modèle pour ces deux cas. Sa
relecture stricte donne **0/6 positifs et 0/2 limites**. H04 et H05 restituent les
faits demandés mais ajoutent une réserve générale injustifiée. H02 ne retrouve
aucun des trois éléments demandés et affiche des pieds de page non pertinents.
H01 conserve les nombres mais n'explicite pas correctement leurs rôles de colonne.
H07 omet les conditions générales et ne rétablit pas les deux associations
valeur–condition.

Le cas limite H03 montre pourquoi une abstention ne suffit pas à garantir la
fidélité : la réponse ne calcule pas une valeur à 150 °C, mais publie une liaison
`Min = 0,25 V` alors que l'original place 0,25 V dans `Typ` pour 0 °C. Elle omet
aussi la limite garantie à 100 °C. **Cette liaison de colonne est une affirmation
documentaire non étayée**, malgré des extraits littéralement fidèles à
l'extraction. Les six réponses `done` passent les contrôles littéraux de spans et
de validation avant `delta`, mais aucune ne satisfait l'oracle strict complet.
Les défauts d'extraction et les limites de contrôle de leur sens restent donc
distincts de l'intégrité technique des traces.

La référence est relue par l’auteur du contrat ; le candidat est relu séparément
par l’auteur des oracles, harnais et codec, qui n’a écrit ni le sélecteur ni le
contrat de réponse. Les deux relectures sont non aveugles et utilisent les cinq
images originales gelées, les mêmes questions et les sorties réelles. Aucun
ajustement du produit ou des critères n’est tiré de ces résultats.

**Le candidat obtient 0/6 positifs et 1/2 limites, soit 1/8 strict.** Il termine
sept requêtes et échoue sur H06. Le seul gain strict est H08, qui ne certifie pas
un maximum à 1 mV et conserve la condition imprimée de 10 mV. Les sept autres
verdicts stricts sont inchangés. Cela ne signifie pas absence de régression :
H04 perd un fait auparavant rendu, et la complétude des positifs passe de **2/6
à 1/6**. Aucun succès positif supplémentaire n’est démontré sur ce transfert.

| Cas | Verdict candidat | Frontière observée |
|---|---|---|
| H01 | FAIL | Les conditions générales et la température garantie sont conservées ; la ligne d’alimentation aplatie ne relie pas explicitement minimum, typique et maximum. La réserve partielle correspond ici à une association réellement non établie dans l’extraction. |
| H02 | FAIL | Aucun des trois circuits demandés ; seuls des pieds de page sont rendus. Ce résultat sans information utile n’est ni une erreur technique ni un refus total explicite. |
| H03 | FAIL, fidélité | L’abstention à 150 °C est appropriée, mais la colonne `Min` attribuée à 0,25 V est fausse ; la limite garantie à 100 °C n’est pas rappelée. |
| H04 | FAIL, régression | Température correcte, alimentation omise bien qu’elle soit dans la citation et dans le prompt. La réserve de couverture est injustifiée. |
| H05 | FAIL strict, faits complets | Condition de déclenchement et rôle de l’hystérésis exacts, mais réserve générale injustifiée. Les qualificatifs approximatif/typique des valeurs supplémentaires restent préservés. |
| H06 | FAIL technique | Requête 4B réellement tentée puis `ollama_timeout` ; aucun contenu fournisseur ni réponse finale reçu. |
| H07 | FAIL | Les deux délais, leur rôle typique et la capacité sont cités ; les couples délai/overdrive ne sont pas explicités et les conditions générales manquent du rendu. Le texte du repère thermique est tronqué. |
| H08 | PASS limite | Insuffisance bornée au périmètre sélectionné, citation exacte des 60 µs à 10 mV, aucune extrapolation à 1 mV ni rôle maximal/typique ajouté à cette page. |

Pour H04, la trace contient bien l’alimentation comme référence **R003** dans la
requête exacte envoyée au modèle. Le plan retourné choisit **R002 et R005**, puis
le plan effectif conserve ces deux références : température et phrase sur une
LED. L’alimentation n’est donc perdue ni par la recherche ni par le budget du
prompt ; elle est omise dans la sélection générative et n’est pas rétablie au
contrôle final. Cette observation ne permet pas d’attribuer l’écart à une seule
modification du produit.

Pour H06, `model_called=false` dans la mesure brute ne signifie pas qu’aucune
requête n’a été faite. `model_call_attempted=true`, un événement `llm.request`
et le journal serveur attestent une requête et du travail sur le prompt. Après
300 secondes d’attente, aucun contenu ni événement de fin fournisseur n’est
reçu ; l’état terminal est `ollama_timeout` à **303,169 s**. Le champ
`model_called` passe actuellement à vrai lorsqu’un événement de flux accepté
est reçu. Ce bloc compte donc **8 tentatives réelles, 7 réponses fournisseur
complètes et une erreur**, sans `delta` public pour l’erreur. Il reste distinct
des deux blocages de trace avant modèle de la référence.

Les douze objets de citation effectivement utilisés contiennent 53 occurrences
de blocs contrôlées : versions, générations, révisions, page, boîte, hash du
texte complet et offsets en caractères Unicode correspondent aux blocs
importés. Les trente occurrences d’extraits sont littérales ; 29 marqueurs sont
publiés. **Cette intégrité ne constitue pas une précision sémantique de 100 %** :
la fausse liaison de H03 passe ces contrôles et les citations de H02 restent
non pertinentes. Les huit traces finales sont vérifiées, avec sept `query.done`
et un `query.error`. Le lecteur est celui du produit gelé, écrit par le
relecteur du codec ; aucune seconde implémentation indépendante du décodeur
n’est revendiquée. Les services sont arrêtés et le gel est inchangé.

L’extraction avant/après confirme que les **2 209 blocs sont identiques en texte,
hash textuel, géométrie, métadonnées et ordre** ; seules les identités, révisions
et sections évoluent. Les quatre défauts amont restent présents. Le compteur
`coverage.ocr=0` indique ici qu’aucun texte OCR n’est retenu, pas que la voie OCR
n’a jamais été tentée. La page d’indice 6 de D03 porte la route `regional_ocr`
et 190 enregistrements OSD non résolus, avec reconnaissance sautée, dans chaque
bras. Aucun gain documentaire du correctif OCR n’est démontré sur ces originaux.

### Scans : OCR repris, fidélité encore insuffisante

La référence termine les deux questions, mais ne répond utilement à aucune :
les pages sont en erreur d’extraction, sans texte ni OCR. Les deux abstentions
sont sûres face à cette preuve vide ; elles restent **0/2 strict**, car les
scans positifs sont lisibles dans les images gelées. Il n’y a aucune citation :
leur précision est non applicable, pas 100 %. Les logs vides de ces deux
extractions ne prouvent pas un nouveau crash SIGFPE.

Le candidat récupère du texte par OCR sur les mêmes deux rasters : **0 → 2 pages
OCR et 0 → 39 blocs textuels**, avec 319 spans et 97 cellules dont les liens
matériels sont vérifiés. Les deux pages restent `ready_partial`. Les plages du
premier scan sont récupérées correctement. Le second garde notamment des
altérations de l’unité µs et de `COUT`, `V+`, `0 V`, ainsi que des sous-lignes
aplaties ; toutes ne recoupent pas une zone de basse confiance. D’autres signes
±, hors de la question, sont également mal transcrits. **D05 échoue sur la
fidélité de ce second scan**, même si les sept intégrations OCR de développement
passent. La réussite d’extraction matérielle et le verdict des réponses finales
sont évalués séparément.

Les deux relectures des réponses candidates concordent sur **0/2 strict**.
SCAN1 rend les deux plages demandées — alimentation 2,7–7,0 V et fonctionnement
−40 à +150 °C — mais maintient une réserve globale injustifiée. Surtout, son
paragraphe supplémentaire publie **« 230 HW » au lieu de « 230 µW »**, visible
sur l’image originale. Cette erreur hors question compte dans la fidélité de
tout le contenu publié. SCAN2 garde les chiffres 60/50 et 10/100, mais les
sous-lignes ne sont pas reliées explicitement et le rendu reproduit `us ys`,
`Cour`, `V*` et `OV` à la place des unités et symboles originaux. Sa prudence
annoncée ne transforme pas ces transcriptions en faits vérifiés.

Les abstentions totales passent de deux à zéro, sans succès strict supplémentaire.
Deux des six groupes de faits demandés sont complets — les deux plages de SCAN1 —
mais aucune des deux réponses n’est entièrement fidèle et conforme. Les trois
citations utilisées, leurs dix-neuf occurrences de blocs, les offsets et les
hashes sont cohérents avec l’extraction ; ils citent correctement la page 1 du
**document dérivé**. Pour SCAN2, la page 3 de l’original est une correspondance de
revue, pas un numéro à inventer dans la citation du scan. Les alertes OCR restent
visibles et signalent le besoin de vérifier l’original ; elles ne remplacent pas
le contrôle de fidélité exigé avant publication.

## 4. Tests de développement et limites de leur portée

| Famille | Résultat observé | Ce que le résultat ne démontre pas |
|---|---|---|
| Sélection, huit tests initiaux | Référence 0/8 ; candidat de développement 8/8 ; 11 gardes supplémentaires passent | La preuve native INA et les résultats de transfert sont des blocs distincts, présentés en section 3. |
| Manifeste exact R04/R05 | R04 passe ; R05 échoue d'abord malgré conservation des deux valeurs ; correction locale puis lot de 221 tests réussi | Les variantes initiales R04/R05 ne sont pas présentées comme les entrées exactes de ce manifeste. |
| Structure PDF | Référence 2/8, candidat passe les huit frontières ; lot final structure 38 tests réussi | La preuve des deux relations TMP117 vient de la revue native distincte, pas de ces seuls groupes synthétiques. |
| Qualitatif | Neuf replays de catalogue (P01 et Q01–Q08) et contrôles unitaires locaux | Un statut de catalogue conforme ne remplace pas une relecture des nouvelles sorties natives. |
| Exploitation O01–O08 | 9 tests réussis en 8,459 s ; O06 a deux variantes de JSON tronqué | Admission/mémoire, transport modèle et délais sont explicitement injectés ; ce ne sont pas neuf essais du vrai modèle. |
| Harnais I4 | 8 tests réussis en 0,883 s | Ces tests de harnais ne constituent pas eux-mêmes les exécutions HTTP ou OCR réservées. |
| OCR réel + police | Référence 3 réussites/5 échecs ; candidat 8 réussites, aucun ignoré ; 150,850 s → 178,740 s | Les 8 comprennent 7 intégrations OCR et un prérequis de police. Les deux scans de transfert restent distincts. |
| Préparation/CMake ciblée | Lot de référence 85 réussites/5 échecs/3 ignorés ; candidat 90 réussites/3 ignorés | Le contrôle ciblé ne mesure pas à lui seul l'installation ou l'exécution sur toutes les plateformes. |
| Suite portable complète antérieure au correctif de sujet | **4 085 réussites, 25 ignorés, 45 désélectionnés, 1 avertissement**, 499,01 s | Exécution historique conservée ; le contrôle du gel final est le lot suivant, sans substitution de ce journal. |
| Suite portable complète sur gel exact final | **4 105 réussites, 25 ignorés, 45 désélectionnés, 1 avertissement**, 578,02 s | Vingt cas de sujet de liste ajoutés à la collecte, aucun retiré ; pas vingt défauts nouveaux corrigés. Ne qualifie ni les réponses documentaires ni Windows. |
| Intégrations hors OCR/tests longs | **27 réussites, 3 ignorés Windows, 93 désélectionnés**, 21,59 s | L'OCR est compté dans son bloc séparé ; les essais Windows absents restent non exécutés. |
| Mypy/Ruff et reprise ciblée | Mypy : **134 fichiers PASS** ; Ruff : `services`, `tests`, `tools` PASS ; **91 tests ciblés PASS** après annotations, 7,73 s | Les six erreurs initiales de typage sont conservées ; aucune qualification métier ne découle du typage statique. |
| Dernier correctif du sujet de liste | **284 tests ciblés PASS**, puis Mypy **134 fichiers PASS** et Ruff PASS ; revue indépendante de l'ingestion sans bloqueur | Ce lot vérifie le delta après la suite complète ; il ne transforme pas cette dernière en exécution sur le gel exact final. |

Les compteurs de ces lots se recouvrent : ils ne sont pas additionnés en un total
de cas indépendants. Le premier lancement opérationnel a donné neuf erreurs de
fixture (`resources` absent dans un profil minimal). Le profil de test a été
corrigé, sans affaiblir les assertions ; les deux journaux sont conservés.

R08 impose explicitement un budget de **six fragments à la primitive** de
sélection. C'est une contrainte injectée pour vérifier l'incomplétude annoncée
lorsque toutes les variantes ne peuvent pas tenir. Certaines routes applicatives
de comparaison ou avec plusieurs identifiants autorisent déjà huit fragments ;
le test R08 n'est pas présenté comme la reproduction de leur budget effectif.

La première tentative de suite portable (`portable-final`) conserve **4 024
réussites et 15 échecs**, plus 25 ignorés et 45 désélectionnés. Son répertoire
`basetemp` était à l'intérieur du dépôt : les gardes d'isolation du kit, de
restauration, des profils et du superviseur refusaient donc ces chemins, et une
assertion de chemin de qualification devenait différente. La tentative finale
`portable-external` utilise un temporaire extérieur et passe. Elle inclut aussi
les **46 tests du nouveau matérialiseur** absents de la première collecte ;
aucun test de la première collecte n'a été retiré. L'écart de 61 réussites ne doit
donc pas être présenté comme 61 défauts corrigés. Les journaux et JUnit des deux
tentatives sont conservés ; leurs temps JUnit internes sont respectivement
549,397 s et 498,734 s, distincts des durées de synthèse du processus pytest.

L'unique avertissement de ce lot est une dépréciation de Starlette/TestClient concernant
HTTPX dans les dépendances verrouillées. Aucun changement de dépendance n'a été
introduit pour masquer cet avertissement.

Le premier contrôle Mypy a signalé six erreurs d'inférence/annotation dans le
sélecteur de couverture et le provisionneur OCR. Le journal est conservé.
La correction des annotations est suivie d'un Mypy réussi sur 134 fichiers,
d'un Ruff réussi sur les trois racines indiquées et de 91 tests ciblés réussis.
Les trois ignorés de l'intégration finale correspondent à la collecte du contrôle
Windows Job et à deux scénarios NTFS/Win32. Les durées JUnit internes des lots
d'intégration et de reprise ciblée sont 21,572 s et 7,691 s ; les synthèses pytest
rapportent respectivement 21,59 s et 7,73 s.

R05 exact a exposé un défaut utile avant le gel final : « la même tension » ne
déclenchait pas le contrat de comparaison ; les valeurs de documents différents,
dont le rôle n'était pas écrit, étaient conservées mais leur divergence n'était
pas signalée. La correction conserve le rôle absent comme inconnu, montre les
deux valeurs sous leur condition commune et n'arbitre aucune valeur. Le manifeste,
le premier échec et les assertions de contrôle restent inchangés.

**Bug de portée du sujet dans une liste, identifié avant le gel final.** La
dernière revue a trouvé une attribution incorrecte lorsque le nom du fichier
désigne un composant et que le titre explicite de la liste en désigne un autre.
Le sujet écrit dans la preuve ne doit pas être remplacé par celui du nom de
fichier. Le contre-exemple de développement et ses variantes sont conservés dans
[`test_i4_list_subjects.py`](../../tests/unit/test_i4_list_subjects.py) ; la correction
générique concerne [`answer_contract.py`](../../services/api/answer_contract.py).
Les premières preuves `list-subject-before.json` et `list-subject-before.xml`
restent conservées : **12 échecs et 8 réussites** avant correction. Le sujet
explicite du titre ou de l'élément empêche désormais une attribution différente
fondée sur le nom du fichier ; des sujets explicites contradictoires restent
ambigus. Après correction, **284 tests ciblés passent**, puis Mypy sur 134 fichiers
et Ruff passent. La revue de l'agent ingestion n'a trouvé aucun bloqueur. Ces
contrôles précèdent le gel définitif ; les auteurs du correctif de sujet, du
sélecteur, du contrat et de l’ingestion n’avaient pas consulté les oracles
réservés. Le rôle du préparateur des oracles, également auteur du codec produit,
est déclaré en section 2. La suite complète antérieure n’est pas présentée comme
une validation de ce dernier delta.

Les snapshots structurels gelés sont la source des entrées réellement exécutées.
Ils précisent notamment la largeur de page du cas à deux colonnes et le parent
ambigu. La proposition générale de 32 cas ne doit pas masquer ces variantes
documentées ni donner l'impression qu'un seul fichier les a tous exécutés.

## 5. Ressources, latence et reproductibilité

Pour le bloc Office de référence, les trois voies déterministes durent entre
123 et 165 ms ; les cinq voies avec appel modèle entre 27,424 et 104,399 s.
Les pics RSS agrégés des processus surveillés vont d'environ 718 Mio pour les
voies déterministes à 4400 Mio sur la voie modèle. Ces observations ne sont ni
des seuils de performance validés ni une mesure de la RAM totale de l'hôte.

Sur le candidat, les quatre voies déterministes durent de **165,05 à 232,11 ms** ;
les quatre appels modèle de **40,933 à 98,356 s**. Leur pic RSS agrégé observé est
d'environ **722,4 à 3979,3 Mio** selon la route. Tous les services du bloc sont
arrêtés et les fichiers gelés sont restés inchangés.

La comparaison des **quatre mêmes cas avec appel modèle** conserve les
ralentissements observés : médiane **38,460 s → 64,809 s**, trois cas plus lents et
un plus rapide. P01 est exclu de cette médiane : sa suppression d'appel modèle
modifie la route et ne démontre pas une accélération de l'inférence.

| Cas commun avec modèle | Temps applicatif, référence → candidat | Tokens de prompt évalués | Tokens générés |
|---|---:|---:|---:|
| L01, condition différente | 104,399 → 98,356 s | 991 → 999 | 50 → 50 |
| L06, divergence | 42,273 → 78,119 s | 1165 → 1179 | 52 → 52 |
| L13, négation | 27,424 → 40,933 s | 944 → 952 | 45 → 45 |
| L16, note de tableau | 34,646 → 51,500 s | 1148 → 1153 | 45 → 52 |

| Cas | Chargement modèle, référence → candidat | Évaluation du prompt | Génération du plan |
|---|---:|---:|---:|
| L01 | 10,185 → 12,582 s | 41,160 → 52,422 s | 17,082 → 33,014 s |
| L06 | 0,0065 → 0,0075 s | 27,442 → 41,820 s | 12,948 → 35,716 s |
| L13 | 0,0034 → 0,0034 s | 16,724 → 16,211 s | 10,327 → 24,425 s |
| L16 | 0,0025 → 0,0034 s | 23,460 → 27,592 s | 10,851 → 23,507 s |

Ces durées fournisseur sont distinctes du temps applicatif et ne l'expliquent
pas entièrement. Les compteurs de cache valent zéro pour L01 et 639 pour chacun
des trois autres cas, dans les deux bras. Une seule mesure existe par cas et par
bras ; le travail et la chauffe ne sont pas identiques. Les différences de tokens
et de durées restent des observations, sans cause isolée attribuée.

Pour les deux PDF candidats, INA226 prend **206,807 s** avec un appel 4B
(`prompt_eval_count=2575`, `eval_count=57`) et TMP117 **3,774 s** par la voie
déterministe. Les pics RSS agrégés surveillés sont respectivement **4208,0 et
4285,3 Mio**. Le modèle reste résident pendant TMP117 : cette seconde valeur ne
mesure pas la mémoire propre du calcul déterministe. Les erreurs de référence
survenaient avant le modèle ; aucune accélération avant/après de l'inférence
PDF n'est calculée à partir de ces échecs.

Sur le transfert, les six cas qui terminent avec le modèle dans les deux bras
ont une médiane de **138,633 s → 136,945 s** ; trois sont plus lents et trois plus
rapides. Les échecs H06/H08 sont conservés dans le tableau complet et exclus
uniquement de cette comparaison de route achevée commune. Les sept réponses
modèle candidates prennent **61,061 à 190,725 s**, et le timeout H06 **303,169 s**.
Le pic RSS agrégé surveillé varie de **4201,1 à 4467,2 Mio**, avec un minimum de
mémoire disponible observée de **2919,4 Mio**. Une mesure par cas ne démontre
ni gain de performance général ni respect d’un objectif de latence de production.

**Confusion expérimentale déclarée :** une analyse Mypy de l'agent structure a
chevauché une partie du bloc Office de référence, approximativement de 16:07:21 à
16:08 UTC, puis a été interrompue avec code 130. Son empreinte CPU/RAM n'a pas été
mesurée. Les réponses restent des preuves fonctionnelles ; ce bloc ne permet pas
d'attribuer une différence de latence du candidat au seul produit. Aucune charge
manquante n'est estimée rétrospectivement. Le reçu d'interruption est conservé.
Le sous-critère I4-D08 « pas de travail lourd concurrent » est donc **NON
SATISFAIT** pour cette mesure de référence. Les arrêts de services réussis sont
un contrôle distinct ; ils ne compensent pas ce défaut expérimental.

Le `ttft_ms` actuel des mesures directes correspond au premier fragment privé du
plan structuré reçu du fournisseur. **Ce n'est pas le délai d'apparition de la
réponse vérifiée pour l'utilisateur.** Le délai jusqu'au premier `delta` public
persisté est une autre mesure ; seul le parcours HTTP/SSE peut observer en plus
son arrivée côté client. Ces métriques ne seront pas fusionnées.

### Ablation locale OCR et limites

La sonde OSD utilise le même raster enregistré et le même modèle OSD verrouillé.
Le binaire Tesseract 5.4.0 original termine avec le code **−8** sur cette entrée.
Après application du correctif source ciblé `normmatch`, le binaire candidat
termine avec le code **0** et une orientation explicite de 0°. Seul l’objet
`normmatch.cpp.o` est recompilé ; 223 objets et la bibliothèque Leptonica sont
réutilisés. Ce n’est pas une nouvelle construction complète. L’essai isole cette
correction sur **une entrée** ; il ne prouve pas une précision OCR générale.

La première exécution de l’ablation construit et installe le binaire, puis échoue
sur un contrôle de configuration trop large : deux fichiers de dépendances
`compiler_depend.make` ont été régénérés. Cet échec est conservé. La reprise
contrôle séparément ces métadonnées, conserve les hashes du cache, des options,
des règles et des autres objets, **ne recompile pas**, puis exécute une seule
sonde OSD. Le hash du binaire accepté figure dans le manifeste de construction, les reçus et le gel ; le verrou fixe les archives et le correctif source.

Les sept intégrations d’ingestion restent une comparaison plus large : même hôte,
mêmes tests et rasters de référence, avec le code structurel I4 également présent
mais aucune annotation de liste dans les seize pages relues. Six PDF sont
identiques octet pour octet ; pour le document de cinq pages, seuls la date et
l’identifiant PDF varient, et les cinq rasters OSD restent identiques. Cette
revue porte sur les artefacts enregistrés, sans nouvel OCR. Elle ne couvre pas
les signes ±, les valeurs négatives, les exposants ou les virgules décimales.
Les limites constatées ensuite sur les scans réservés restent donc décisives.
Aucune conclusion causale globale n’est acquise et aucune sortie primaire native
n’est remplacée par une reprise favorable.

### Achèvement opérationnel et périmètre HTTP

Les vingt cas directs candidats se répartissent en **14 générations 4B achevées,
une tentative 4B échouée par timeout et cinq voies sans tentative de génération**.
La référence compte onze générations, cinq voies sans tentative et quatre
erreurs avant modèle. Ces compteurs décrivent l’exécution, pas une qualité
agrégée mélangeant Office, PDF, transfert et scans.

Les deux requêtes OCR candidates prennent **201,536 et 188,466 s**, avec des pics
RSS agrégés de **4037,6 et 4250,3 Mio**. Les références sont deux abstentions sans
modèle, en 2,769 s et 80,4 ms : ces routes différentes ne permettent pas une
comparaison de vitesse d’inférence. La durée d’extraction est consignée séparément.

Le parcours HTTP/SSE réel utilise trois lancements du worker natif, aucun résultat
d’extraction injecté et aucun cache réutilisé. Les contrôles de publication après
validation applicative du rendu, de conservation de citations de l’ancienne
version après remplacement, de reprise du flux après son état terminal, de
stabilité du gel et d’arrêt des trois groupes détenus passent. Le résultat
opérationnel final est **PASS**. L’ordre vérifié établit que le garde s’exécute
avant le `delta` public ; il ne transforme pas ce garde en preuve sémantique
générale, comme le montrent les échecs documentaires séparés.

Le verdict documentaire HTTP est également **1/1 PASS**, après deux lectures
non aveugles dont celle de l’auteur du harnais : A donne **2,8 V à 70 °C**, B
**3,2 V à 70 °C**, et la réponse signale leur divergence sans arbitrer. Les deux
citations exactes portent quatre marqueurs ; aucun rôle minimum/typique/maximum
absent n’est ajouté. Après import de la nouvelle version de A à **3,0 V**, les
anciens originaux, la réponse et ses citations conservent leurs valeurs et versions
antérieures. Aucune seconde question sur la nouvelle version n’était prévue.

Un échange 4B réel est confirmé. La requête prend **87,162 s** côté application
et **87,428 s** dans l’observateur HTTP. Le premier `delta` est observé **87,249 s**
après le `created_at` de la requête API, avec les horloges UTC du même hôte.
Il arrive après le contrôle enregistré ; ce délai n’est ni le TTFT privé du modèle
ni un temps d’affichage navigateur. Un seul cas synthétique et aucun bras HTTP
de référence ont été exécutés. Le navigateur et l’ergonomie ne sont pas qualifiés.

La consolidation terminale relit les reçus de **neuf blocs natifs** — quatre blocs
appariés et HTTP — et de **six préparations, avec quatorze workers**. Tous les
arrêts détenus et contrôles de stabilité sont attestés. Les 88 fichiers produit
et 46 fichiers de harnais correspondent toujours au gel ; la copie publique est
identique. Il s’agit d’une consolidation des reçus du runner, **pas d’une nouvelle
inspection indépendante des espaces de processus de l’hôte**. Ces succès ne
rattrapent ni le chevauchement Mypy de référence ni les échecs documentaires.

## 6. Definition of Done I4 — bilan des essais

| Critère | Statut actuel | Preuve acquise et reste à démontrer |
|---|---|---|
| D01 — fidélité/portée | FAIL | H03 publie une colonne `Min` contredite par `Typ` dans l’original ; les deux scans reproduisent aussi des transcriptions erronées, dont 230 HW pour 230 µW. Spans exacts et réserves ne bloquent pas ces altérations. |
| D02 — sélection | PASS sur la matrice prévue | Huit contrôles initiaux et gardes ; cas exacts R04/R05 traités ; bus et alimentation INA conservés jusqu'au rendu et cités. La réserve de couverture erronée reste un échec strict distinct. |
| D03 — structure | PASS sur la matrice prévue | Huit frontières et 38 tests ; les deux relations TMP117 et leurs conditions sont justifiées jusqu'au rendu natif. Répétition de fermeture de liste conservée comme défaut de présentation. |
| D04 — réponse simple | PARTIAL au niveau de l’objectif | La matrice prévue passe : contrôlé 12/12+18/18, Office 4/4 positifs et 4/4 limites. Sur le transfert H05, les faits sont complets mais la réserve globale injustifiée persiste. La réussite locale ne suffit pas à l’objectif général. |
| D05 — OCR | FAIL | Sept intégrations réelles passent ; les deux rasters réservés sont effectivement traités. Le second scan altère unités/conditions et des signes sans signaler toutes les ambiguïtés ; récupération de texte et intégrité des spans ne prouvent pas la fidélité. |
| D06 — non-régression | PASS sur les contrôles prévus ici | Suite complète sur gel exact : **4 105 PASS, 25 SKIP, aucun FAIL/ERROR** ; intégrations 27 PASS, Mypy 134 fichiers/Ruff PASS, HTTP opérationnel et documentaire PASS. Brief synchronisé et 11 contrôles du pack PASS ; 12 avertissements tiers existants conservés. Historique 4 085 conservé ; Windows et autres suites non exécutées restent NOT_RUN. |
| D07 — natif/transfert | FAIL | Office 7/8 → 8/8 ; PDF 0/2 → 1/2 strict. Transfert 0/6+0/2 → 0/6+1/2, inférieur au seuil 6/6+2/2. Réserve INA, erreur H06, contenu manquant et fausse association H03 restent au dénominateur ; H04 perd un fait. |
| D08 — ressources/exploitation | PARTIAL | Neuf tests d’exploitation, HTTP/SSE réel et arrêts natifs contrôlés réussissent ; les latences et pics observés ne sont pas une qualification générale de performance. Sous-critère d'absence de travail lourd concurrent **NON SATISFAIT** pour Office référence : chevauchement Mypy conservé, distinct des arrêts réussis. |
| D09 — reproductibilité | PARTIAL | Protocole, entrées, hashes, worktree séparé, gel final vérifié et matérialisation locale fidèle. Limites déclarées : une mesure native par cas, chevauchement Mypy et préparateur des oracles également auteur du codec produit. La séparation prévue entre validation et tous les auteurs produit n’est donc pas absolue. |
| D10 — livraison | PUBLICATION EN COURS | Implémentation, essais, revues, brief et pack vérifiés. Commit/push et contrôle du SHA/arbre distant constituent la dernière étape autorisée. |

Un statut partiel ne signifie pas un critère abaissé. Les seuils 12/12+18/18,
6/6+2/2 de transfert et la fidélité des scans demeurent ceux du protocole.

### Corrections différées après la qualification

Aucun réglage n’est appliqué au candidat gelé à partir des échecs du corpus
réservé. Les priorités suivantes nécessitent une nouvelle itération et un nouveau
jeu de transfert, afin de conserver une évaluation distincte du développement.

| Point restant | Conséquence observée | Travail nécessaire avant une nouvelle qualification |
|---|---|---|
| Liaison de cellules au document original | H03 transforme une valeur typique en minimum malgré des hashes valides. | Vérifier les rôles de colonne et les cellules contre la géométrie/source originale ; bloquer la relation si cette preuve manque. |
| Texte OCR encore incertain | Des unités et signes erronés sont publiés, y compris dans un paragraphe supplémentaire hors question. | Étendre le contrôle aux valeurs, unités, signes et conditions réellement rendus ; les alertes générales et seuils de confiance ne suffisent pas à établir leur exactitude. |
| Complétude du plan final | H04 perd l’alimentation alors que R003 est disponible dans le prompt. | Contrôler la couverture de chaque obligation jusqu’au plan effectif et au rendu, sans attribuer au générateur le choix d’omettre un fait demandé établi. |
| Portée des réserves | INA et H05 restent incomplets au sens strict alors que les faits demandés sont déjà présents. | Distinguer l’incertitude documentaire effective de la limite des contrôles de grammaire ; vérifier sur de nouvelles questions génériques. |
| Budget CPU et définition des métriques | H06 traite un prompt puis atteint 300 s sans réponse ; le champ brut `model_called` peut masquer la tentative. | Qualifier latence, annulation et libération sur un ensemble répété ; distinguer explicitement tentative, événement fournisseur reçu et fin de génération. |

Ces pistes sont différées pour préserver les critères et les résultats du gel,
non parce que les défauts seraient acceptables en production. Les tests et
améliorations d’ingénierie livrés restent utiles ; la fidélité de bout en bout,
l’OCR intégral et la performance générale ne sont pas qualifiés par cette itération.

## 7. Preuves et reproduction

Les résultats détaillés restent dans `.runtime/qa/production-i4-20261108/`, hors
Git : ils contiennent les sources et traces privées de qualification. Les résumés
livrés devront suffire à comprendre les verdicts sans prétendre que ces fichiers
sont automatiquement présents dans un clone neuf. Le protocole et les outils
versionnés restent les points de départ des nouvelles exécutions.

| Reçu/rapport | Empreinte ou preuve utile |
|---|---|
| `controlled-baseline-review.json` | SHA-256 `2ba3b28424fae0015807ffd1aa3d3570d4d89448fc19296f4e92e28e24e80099` ; relecture des 30 cas, 11/12+18/18 |
| `controlled-candidate-review.json` | SHA-256 `a979513ef8a9fc3ada36e5ff2ff40472d4608ae0d9a985bea7d06152dd42da6d` ; relecture des 30 cas, 12/12+18/18, un gain strict |
| `native-baseline-office-review.json` | SHA-256 `e02940122cca8b37515d253a8ba7564b6faa808b0996ab63043eaadb47012428` ; relecture des huit cas réels |
| `native-candidate-office-review.json` | SHA-256 `1cbf9c7a100e313fb3d301f8a433729ce0deaa2927f416a1d65eb4a33abea4d4` ; première relecture par l'auteur du contrat, 8/8 strict |
| `native-candidate-office-cross-review.json` | SHA-256 `be5dd5fada1ec15730c11a189539ac9bf1ebdacbbd80441a6cd43a395ed11a4e` ; seconde relecture non aveugle, mêmes huit verdicts ; neuf originaux et treize blocs vérifiés |
| `native-office-paired-performance.json` | SHA-256 `e5e5bd0c7223d4a61c3c0b10631036a10b1622274c1f86bdac0bc310ee5d0fbb` ; quatre voies modèle communes, tokens et durées par phase ; trois ralentissements observés, aucune attribution causale |
| `qualification-harness-review.json` | SHA-256 `2ffd216a0f7000bf42d6d877e5c06c5ae6e6bab5f343df97efcda7979d22f4db` ; snapshot historique des gardes du harnais, pas un résultat natif HTTP |
| `pdf-baseline-preparation/` et `native-baseline-pdf/` | Extractions complètes, sources/code stables, deux erreurs primaires et reçus d'arrêt |
| `pdf-extraction-review-conclusion.json` | SHA-256 `b62a8f7d851433b2b4c3e6a388557dd88a2efa690ec0bbce4e65c1855a9f14bd` ; cohérence des quatre extractions, page 0 inchangée, ajout OCR INA bruité sans gain de fidélité démontré |
| `native-candidate-pdf-review.json` | SHA-256 `10db11011653e6358ad80fd441686f6440d24f9e339889f46f6256ecbd8625ac` ; première relecture PDF par l'auteur du contrat, 1/2 strict et 4/4 relations rendues |
| `native-candidate-pdf-cross-review.json` | SHA-256 `0af24d5e6af017634d17b500e998fc67d5f58b8a9241049b101eeb59b2207035` ; seconde relecture concordante avec images existantes, onze blocs de citation et deux traces finales vérifiés |
| `transfer-baseline-extraction-review.json` | SHA-256 `9de2cdcc10e70b311b0f9ca6e9e6da42b47b461bdacf00c4866a0474a94deb84` ; trois documents partiels, intégrité vérifiée et défauts d'extraction distincts des verdicts de réponse |
| `native-baseline-transfer-review.json` | SHA-256 `53584f41774e6c2d65497cbe483bf10713563a5e5beada2b11671cf86d209327` ; référence 0/6 positifs et 0/2 limites stricts, six `done`, deux erreurs et une fausse liaison de colonne rendue |
| `transfer-extraction-before-after-review.json` | SHA-256 `66687ce2c7cb2956b6bfb0135731b2b5b9e640ec907c12923116946eb65977c1` ; 2 209 blocs identiques, quatre défauts sémantiques inchangés |
| `native-candidate-transfer-review.json` | SHA-256 `de77550c3844d91143a5a3da5fca28601fd1f8320ec220638dcc98c82e80a6ae` ; 0/6+1/2 strict, sept réponses et un timeout, fausse colonne H03 et régression de contenu H04 |
| `transfer-h04-omission-diagnostic.json` | SHA-256 `d55a069e365b02a78f060bb7a71e9850218c9be717d6a92cf533219c386d570e` ; alimentation R003 présente dans la requête, plan modèle/effectif R002+R005 |
| `transfer-h06-timeout-diagnostic.json` | SHA-256 `0c524c4c8fbc717cc0070fce7f70ca7d837d429624e090d98f57d1f06781b7f7` ; véritable requête 4B et travail serveur, aucune réponse fournisseur reçue avant timeout |
| `native-candidate-transfer-trace-review.json` | SHA-256 `7ab3683c650113272328f996b1b04000e4d3ad42f73619522857cc6614998f02` ; huit traces finales, sept fins et une erreur vérifiées |
| `native-transfer-paired-performance.json` | SHA-256 `1efeda3c7fb9ff1f1b3910e03a4d0bcb3e13798d473e6c77d97f13372ef7a27e` ; huit mesures par bras et comparaison limitée des six routes modèle achevées communes |
| `native-baseline-ocr-review.json` | SHA-256 `90a764f2d05af79010336b2e0ed6882b58cbd71c47b5cbacf4b77f2228cad7f9` ; deux abstentions sûres mais 0/2 utiles après extraction vide |
| `ocr-scan-before-after-review.json` | SHA-256 `4449379a8d43484010ef897c7893629e12a71eef34bfba2ba176da7fbe0bd1a1` ; OCR récupéré sur deux rasters identiques, unités/conditions du second encore altérées |
| `ocr-osd-diagnostic/receipt.json` | SHA-256 `7efd5d422b2bbb684ea6dc493675a0f491dcc665a72c25ddd9f4accd07659c2f` ; Sonde du raster identique avec binaire original : code −8 ; aucune extension de ce constat aux logs vides des scans |
| `ocr-ablation-pr4259/ablation-receipt.json` | SHA-256 `fe14e9790abd969d8832c01b3c1d8262e7e416dcab8152c92691e5dedd357b67` ; Première construction terminée, contrôle de métadonnées CMake échoué et conservé |
| `ocr-ablation-pr4259-resume/ablation-receipt.json` | SHA-256 `b5f9e89aa33ef2cb4e33c70fd09f1f0bb8b9c67a73f6aa28e53eb1b9769926c9` ; Reprise sans compilation, un objet modifié/223 réutilisés, sonde OSD code 0 |
| `ocr-before-after-review.json` | SHA-256 `c7b1556a965fc9cf7869f1371c9b8741a50e126ba7f19b4326e4fb5eee423ee0` ; Revue séparée des sept intégrations : entrée/raster et limites des signes documentés |
| `native-candidate-ocr-review.json` | SHA-256 `7042c5162482a3a4c0693dd821537bf96409267b9f8e5e06a188bfba35602e97` ; Première relecture : 0/2 strict, OCR repris et erreurs de transcription rendues |
| `native-candidate-ocr-cross-review.json` | SHA-256 `e96432b6d1c8495d3c142c048a41b43e37c79d0a9fd45dde4e7f6c7989725c1f` ; Seconde lecture concordante des deux PNG gelés, trois citations et dix-neuf occurrences de blocs |
| `native-candidate-http-review.json` | SHA-256 `3e6625ae592d5f232d7352d40c96d098604bb48c2ca984a0f0c256c2b6edc591` ; Relecture documentaire HTTP : divergence justifiée 1/1, citations anciennes persistantes, ordre de publication vérifié |
| `native-candidate-http-cross-review.json` | SHA-256 `c7860b3e47c3f560f3327df4e49c79f7162e9afd57b26e95a6cad9abf4b3a90a` ; Seconde lecture des trois originaux OOXML et de la réponse, même verdict ; rôle d’auteur du harnais déclaré |
| `native-execution-counts-review.json` | SHA-256 `9926774ea7fba3847c3b7cde560dd79523ca1d1b0c4e4ed3c006138a6c43fbb7` ; Vingt cas directs par bras, distinction tentative/contenu reçu/génération achevée |
| `native-candidate-http/http-final-result.json` | SHA-256 `1c21e6f04fdadc60ad2b23a6d332845fc111d1884629ae084e140560f015c3e5` ; PASS opérationnel du parcours réel après arrêt et stabilité, jugement documentaire séparé |
| `completion-runtime-audit.json` | SHA-256 `3e04c64ed909f638c39c3ab2cff07a21bdd85c3047a12e5ec1fa707b222397bb` ; Consolidation de neuf blocs natifs et quatorze workers ; aucune inspection OS indépendante |
| `i4-final-freeze-identity-and-git-review.json` | SHA-256 `764cc60a4d4f74d0bec81acb9e98b295a50a66d0c73fa2f03e4a8ecd33a0b2a0` ; 88+46 fichiers au gel ; identité4B conservée, sources et binaires hors Git |
| `trace-compaction-protocol.json` | SHA-256 `66b0a8bd55ab7f86f4862a370a4bd08636a942420d1469a16bc42eda7fb56f73` ; seuils avant reproduction/correction |
| `trace-compaction-offline-review.json` | SHA-256 `974fdbf918c1c7698bb385b0710e60c0ff3444be2c0a5101869a0dadc2f06d1c` ; sept payloads INA exacts, aucune nouvelle requête |
| `trace-compaction-checks.json` | SHA-256 `575ea3af675f4ceb7084bcc44f854d5d0f686e04c0f02e7942388ff2a7583990` ; gel du codec, 121 tests ciblés et revues |
| `structure-mypy-overlap-receipt.json` | Interruption observée et chevauchement déclaré ; aucune mesure de charge reconstruite |
| `portable-final.xml` / `portable-final.log` | Première tentative conservée : 15 échecs liés au temporaire intérieur, 4 024 réussites ; aucun résultat favorable substitué silencieusement |
| `portable-external.xml` / `portable-external.log` | Tentative hors dépôt avant le dernier delta de sujet : 4 085 réussites, 25 ignorés, 45 désélectionnés ; 46 nouveaux tests de matérialisation dans cette collecte |
| `portable-frozen-final-receipt.json` | SHA-256 `8b92830e09cd7d4a7276af3a3df80dcd9865997ee9c9b9dbfa8f0a38466f763d` ; suite finale 4 105 PASS sur gel exact, JUnit 4 130 cas/25 ignorés, aucun échec ; 88+46 fichiers inchangés après |
| `pre-freeze-gates.json` | SHA-256 `9cfa5eb853306231e444630234f932af78811eed62e62166cb0b34ecfbf32354` ; consolidation portable, intégrations, Mypy/Ruff et reprise ciblée, avec hashes des reçus |
| `list-subject-after.xml` | SHA-256 `210c6667e6176c61202e89ef0e9d33fdf1a8943f05ec859eb2cf0a00da26d82e` ; 284 tests ciblés après le dernier correctif |
| `candidate-freeze.json` | Copie publique liée ci-dessus, SHA-256 `be7ad4c46c89de7c3c351fa0f3fc7a79369c8e336542474b01f7586467c37d9b` ; 88 fichiers produit/configuration et 46 fichiers de qualification |
| `heldout-materialized-offline/materialization-receipt.json` | SHA-256 `d9973460cd2a057048cbb28c6e5270d6d5a6af3b65dd9ed89fd7ccd951234b8a` ; copie/rendu natif fidèle depuis les originaux locaux gelés, sans téléchargement réussi |
| `materialization-independent-review.json` | SHA-256 `50c7b24fae8cc424ce45936e65d2e54d6aa0be40ff5d92e99958844f2cb456f1` ; contrôle des artefacts et revue des deux images existantes, distincts de l'évaluation OCR/réponse |

Un [agrégat public compact](production-4b-validation-2026-11-08.json) rassemble les
compteurs, statuts, limites et empreintes des preuves. Il ne recopie aucun journal
brut ni contenu du transfert réservé.

Le [guide de reproduction](production-4b-reproduce-2026-11-08.md) fournit les
prérequis du verrou, la préparation des entrées et les commandes des deux bras
contrôlés, natifs, transfert et scans, ainsi que le HTTP candidat. Il distingue
le runtime OCR original de référence du runtime corrigé candidat. Les commandes
créent de nouveaux dossiers et conservent les sorties précédentes. Les vingt-deux
blocs Bash du guide ont été vérifiés syntaxiquement ; ce contrôle documentaire
n’est pas une nouvelle exécution des campagnes. Aucun fichier de preuve privé
n’est supposé déjà présent dans un clone neuf.

### Contrôles documentaires avant publication

Le brief généré correspond à ses sources canoniques. Les onze contrôles de `verify_pack.py` passent ; les douze avertissements relatifs au rangement de fichiers tiers de skills déjà présents sont conservés. Reçu privé `pack-prepublication.json`, SHA-256 `358e7996b2145ab44772451c1d2c7f35fc62f53ffed53ae638beef651cfdf16e`. Le contrôle du brief porte le SHA-256 `ba027670c3af147c1125fd9572f70d6ffcdad9a5a6d421b66e95d93704864d88` pour son journal. Ces vérifications ne sont pas des essais de moteur, de navigateur ou de cible matérielle.
