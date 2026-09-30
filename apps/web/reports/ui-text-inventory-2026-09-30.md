# Inventaire des textes de l'interface (lot R15, étape B du lot R16)

**Rôle :** inventaire de tous les textes visibles ou restitués par `apps/web/src/`, avec leur réécriture et son motif · **Propriétaire :** lots R15/R16 (frontend) · **Statut :** Vivant ; textes implémentés et couverts en partie par les tests unitaires, rendu et parcours E2E à vérifier · **Référence :** commit `ae387a9` et modifications non commitées des étapes A et B du lot R16, corrections de la relecture indépendante comprises · **Mis à jour :** 2026-09-30 (UTC) · **Source de vérité :** `apps/web/src/` pour les textes livrés ; ce document pour les motifs.

« Avant » désigne l'état au début de l'étape B (après l'étape A, non commitée). Un texte marqué *inchangé* a été relu et gardé. « Nouveau » signale un texte introduit par l'étape B. Les textes produits par le service (message d'erreur d'API, `job.error_message`, avertissements structurés, noms de documents et de sections) sont affichés tels qu'ils arrivent et ne figurent pas ici ; seuls leurs textes de repli, écrits dans `src/`, sont inventoriés.

## Vocabulaire retenu

| Terme | Emploi | Écarté |
|---|---|---|
| document | Fichier importé dans la bibliothèque, quelle que soit sa version | « PDF » comme nom d'objet (gardé pour le format : « Importer des PDF », « original PDF ») |
| version | Contenu d'un document à une empreinte SHA-256 donnée ; « version active » pour celle qu'utilisent recherches et questions | « active » seul |
| page, folio | Page physique numérotée depuis 1 ; folio = étiquette imprimée | « p. » réservé aux compteurs compacts |
| bloc, passage | Bloc = unité extraite ; passage = extrait retrouvé ou cité | « résultat de recherche » pour un passage |
| périmètre | Ensemble interrogé : bibliothèque, dossier, documents sélectionnés, section, pages, texte sélectionné | « type », « analyser le dossier » pour un simple choix de périmètre |
| source, citation | Source = passage enregistré dans une réponse ; citation = sa référence `Sxxx` dans le texte | « identifiant absent du registre » |
| extraction, indexation | Extraction = lecture du texte et de sa géométrie ; indexation = écriture dans l'index ; publication = mise à disposition | « transmis », « réellement exécutées » |

## Barre supérieure, liens d'évitement et bandeau de contexte

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| `workspace.tsx`, `nav.skip-links` (aria-label) | — | Accès rapide | Nouveau : zone des liens d'évitement |
| `workspace.tsx`, lien d'évitement | — | Aller au lecteur | Nouveau |
| `workspace.tsx`, lien d'évitement | — | Aller à la zone de question | Nouveau ; ouvre l'analyse si elle est repliée ou sous 1 024 px |
| `workspace.tsx`, `main` (aria-label) | — | Lecteur | Nouveau : zone principale nommée |
| `app-topbar.tsx`, sur-titre de marque | Poste documentaire local | *inchangé* | Sous-titre arrêté par la référence de forme |
| `app-topbar.tsx`, `h1` | Atelier documentaire | *inchangé* | Nom de produit arrêté |
| `app-topbar.tsx` / `panel-preferences.ts`, bascule de la bibliothèque (aria-label) | Replier la bibliothèque · Afficher la bibliothèque | Replier la bibliothèque · Masquer la bibliothèque · Afficher la bibliothèque ; sous 1 024 px : Ouvrir la bibliothèque | Trois états ; le libellé annonce l'action suivante |
| idem, info-bulle | — | « {libellé} (Ctrl+B ou ⌘+B) » | Nouveau : rappelle le raccourci |
| `app-topbar.tsx` / `panel-preferences.ts`, bascule de l'analyse | Replier l'analyse · Afficher l'analyse | *inchangé* ; sous 1 024 px : Ouvrir l'analyse | Panneau latéral sous 1 024 px |
| `status.ts` `serviceStatus`, état des services | Connexion… | Connexion au service local… | Dit ce qui est attendu |
| idem | Service indisponible | Service local injoignable · Service local en erreur | Coupure de connexion et réponse en erreur distinguées |
| idem | Préparation requise | Modèle ou worker non prêt | « Préparation requise » ne disait pas quoi |
| idem | — | Index en retard | Nouveau : documents importés que l'index ne couvre pas encore |
| idem | Services prêts | *inchangé* | |
| `warnings.ts` `serviceDetail`, info-bulle de l'état | Composants joints par « · », ou message d'erreur | Non prêts : {composants}. · Le service n'a pas confirmé que ses composants sont prêts. · 1 document attend son indexation : il n'est pas encore interrogeable. · {n} documents attendent leur indexation : ils ne sont pas encore interrogeables. · Base documentaire, modèles, index vectoriel et contrôle des ressources prêts. · message d'erreur | Explique chaque état |
| `app-topbar.tsx`, bouton Suivi | Suivi | *inchangé* | Libellé lu par les E2E |
| idem, texte masqué | « , traitements actifs : {n} » | « , {n} traitements à suivre » · « , aucun traitement à suivre » · « , lecture du suivi en échec » | Phrase accordée ; un échec de lecture n'est pas un zéro. « À suivre » et non « actifs » : le compte inclut les traitements en pause, mis en point de reprise, interrompus ou en extraction partielle |
| idem, pastille | {n} | {n}, plafonné à « 99+ » | Tient dans la pastille |
| idem, info-bulle | — | La dernière lecture du suivi a échoué : ouvrez-le pour voir l'erreur. | Nouveau |
| idem, annonce `aria-live="polite"` | — | Suivi : {n} traitements à suivre | Nouveau : annonce d'un changement de compte, pas de la première lecture |
| `help-menu.tsx`, bouton | — | Aide | Nouveau |
| `panel-state.ts` `scopeKindLabel`, puce du bandeau | — | Bibliothèque entière · Dossier · Documents sélectionnés · Section · Pages · Texte sélectionné | Nouveau |
| `panel-state.ts` `coverageSentence` | — | {n} documents interrogeables · {m} exclus : {k} en cours de traitement, {k} indexation en pause, {k} en erreur, {k} état non reconnu ; Aucun document interrogeable ; Aucun document dans ce périmètre | Nouveau : couverture avant l'envoi, exclusions par motif |
| `context-band.tsx` | — | Couverture inconnue : la bibliothèque n'a pas pu être lue | Nouveau : une panne n'est pas une couverture vide |
| `warnings.ts` `readinessSentence`, message de préparation | {composants joints par « · »} | Préparation du poste incomplète : {composants}. Les recherches et les questions qui en dépendent échouent tant que ces composants ne sont pas prêts. La commande .\rag.ps1 doctor détaille chaque contrôle ; l'état est relu toutes les 10 secondes. | Conséquence et action ; intervalle réel (`refetchInterval: 10000`) |
| `context-band.tsx`, info-bulle du message | — | Contrôles non satisfaits : {codes} | Nouveau : codes gardés pour le diagnostic |
| `context-band.tsx`, fermeture de l'erreur | Fermer le message | *inchangé* | Libellé lu par les E2E |
| ancienne barre de périmètre | Les réponses gardent leur périmètre et leurs versions. | supprimé | Repris dans l'aide du choix de périmètre |
| `workspace.tsx`, documents comparés (aria-label) | Documents comparés | *inchangé* | |
| idem, intitulé | Comparer {n} PDF | Comparer {n} documents | Vocabulaire : document |
| idem, info-bulle d'un bouton désactivé | — | Ce document n'a pas encore de version consultable. | Nouveau : dit pourquoi le bouton est inactif |
| `workspace.tsx`, séparateurs | Largeur de la bibliothèque · Largeur de l'analyse | *inchangé* | Libellés lus par les E2E |
| `workspace.tsx`, fermeture des panneaux latéraux | — | Fermer (nom accessible : Fermer la bibliothèque · Fermer l'analyse) | Nouveau : bouton Fermer libellé |
| `workspace.tsx` `sourceClick` | Cette citation ne possède pas d'identifiant enregistré. | Cette citation ne possède pas d'identifiant enregistré : elle ne peut pas être ouverte. | Conséquence |
| idem | Cette source ne contient pas de version documentaire consultable. | Cette source ne désigne aucune version de document consultable. | Vocabulaire |

## Menu Aide

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| `help-menu.tsx`, titre | — | Raccourcis clavier | Nouveau |
| raccourci Ctrl+B, ⌘+B | — | Replier, masquer ou afficher la bibliothèque ; sous 1 024 px, ouvrir ou fermer son panneau. Sans effet pendant la saisie d'une question. | Câblé dans `workspace.tsx` (`isLibraryShortcut`) |
| raccourci Ctrl+Entrée, ⌘+Entrée | — | Depuis la zone de saisie : envoyer la question ou lancer la recherche. | Câblé dans `analysis-panel.tsx` |
| raccourci ←, →, Début, Fin | — | Sur un onglet d'analyse (Question, Recherche, Comparer) : passer à un autre onglet. | Câblé par `tabKeyTarget` |
| raccourci ←, → | — | Sur un séparateur de panneaux : élargir ou rétrécir la bibliothèque ou l'analyse. | Câblé dans `workspace.tsx` |
| raccourci Entrée | — | Dans « Rechercher dans ce document » : aller à la page suivante qui contient l'expression, comme « Chercher plus loin ». | Formulaire de `pdf-viewer.tsx` |
| raccourci Échap | — | Fermer le panneau latéral, le suivi, cette aide, le choix du périmètre ou la boîte de confirmation. | `Sheet`, `ConfirmDialog`, `useDismiss`, `ScopeControl` |
| séparateur de combinaisons | — | ou | Nouveau |
| titre | — | Version de l'interface | Nouveau |
| `build-info.ts`, signature | — | Atelier documentaire · version {package.json} · révision non tracée (ou révision {12 caractères}) | Nouveau : aucune révision n'est injectée aujourd'hui |
| `build-info.ts`, détail | — | Aucune révision n'a été injectée à la construction : cette interface ne peut pas être rattachée à un commit précis. · Révision complète {hash}, injectée à la construction. | Nouveau : aveu explicite plutôt qu'une provenance supposée |

## Choix du périmètre (`scope-control.tsx`, déplacé depuis `workspace.tsx`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| déclencheur, sur-titre | Périmètre | *inchangé* | Nom accessible lu par l'E2E clavier |
| titre (`h3` devenu `h2`) | Définir le périmètre | *inchangé* | Niveau de titre sous le `h1` de la barre |
| aide | La lecture et les citations ne le changent pas. | Les recherches et les questions portent sur ce périmètre ; chaque réponse garde celui de son envoi, avec les versions consultées. Ouvrir un document ou une citation ne le modifie pas. | Dit à quoi sert le périmètre ; reprend la phrase de l'ancienne barre |
| libellé du choix | Type | Portée | « Type » ne disait pas de quoi |
| option | Toute la bibliothèque | *inchangé* | |
| option | Dossier et descendants | Dossier et ses sous-dossiers | Vocabulaire courant |
| option | PDF sélectionnés | Documents sélectionnés | Vocabulaire : document |
| option | Section du PDF ouvert | Section du document ouvert | Idem |
| option | Pages du PDF ouvert | Pages du document ouvert | Idem |
| option | Sélection de texte | Texte sélectionné dans le document | Même terme que la puce et le libellé de périmètre |
| aide « documents » | {n} documents sélectionnés dans la bibliothèque. | *inchangé* | |
| dossiers | Liste des dossiers indisponible : {message} · Chargement des dossiers… · Dossier · Choisir un dossier… · Aucun dossier dans la bibliothèque | *inchangé* | |
| pages | Nombre de pages indisponible : {message} · De la page · À la page | *inchangé* | |
| sections | Sommaire indisponible : {message} · Chargement du sommaire… · Section · Choisir une section… · Aucune section extraite pour ce document · Ouvrez un document pour choisir une section | *inchangé* | |
| texte sélectionné | « {extrait} » | *inchangé* | |
| idem, sans sélection | Aucune sélection réconciliée avec les blocs source. | Aucun texte sélectionné ne correspond aux blocs extraits. Sélectionnez un passage dans le lecteur. | Jargon « réconciliée » ; action indiquée |
| erreur | La révision doit être vérifiée. | La révision de la citation ouverte doit d'abord être vérifiée. | Dit quelle révision |
| erreur | Sélectionnez au moins un PDF dans la bibliothèque. | Cochez au moins un document dans la bibliothèque. | Geste réel (case à cocher) et vocabulaire |
| erreur | Choisissez un dossier existant. | Choisissez un dossier dans la liste. | Action précise |
| erreur | Sélectionnez un texte rattaché aux blocs extraits du document. | Sélectionnez dans le lecteur un texte qui correspond aux blocs extraits, puis appliquez de nouveau. | Où agir et quoi faire ensuite |
| erreur | Choisissez une section extraite disponible. | Choisissez une section dans la liste. | Action précise |
| erreur | Ouvrez un document pour définir ce périmètre. | Ouvrez d'abord un document dans le lecteur. | Action précise |
| libellé de périmètre, un document sans nom | PDF sélectionné | 1 document sélectionné | Vocabulaire |
| libellé de périmètre, plusieurs documents | {n} PDF sélectionnés | {n} documents sélectionnés | Vocabulaire |
| libellé de périmètre, texte | Sélection de texte du document | Texte sélectionné dans le document | Un seul terme |
| libellés de périmètre | Toute la bibliothèque · {chemin} · sous-dossiers inclus · {document} · pages {a}–{b} · {document} · {section} · Document ouvert | *inchangé* | « page » lu par les E2E |
| boutons | Fermer · Appliquer | *inchangé* | « Fermer » évite une collision avec « Annuler » (annulation d'une réponse) |

## Bibliothèque (`library-panel.tsx`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| titre | Bibliothèque | *inchangé* | Titre lu par les E2E |
| compteur (info-bulle, texte masqué) | Documents présents dans la bibliothèque · Documents présents : | *inchangé* | |
| panne | Service local indisponible | *inchangé* | |
| erreur de lecture | Bibliothèque illisible | Lecture de la bibliothèque impossible | Décrit l'échec, pas le contenu |
| message d'erreur | {message} La liste affichée date de la dernière lecture réussie. | *inchangé* | |
| chargement | Chargement de la bibliothèque… | *inchangé* | |
| bouton d'import | PDF | Importer des PDF | Un format n'est pas une action |
| bouton d'import | Dossier | Importer un dossier | Idem |
| attente d'import | Import… | Import en cours… | Libellé d'attente complet |
| actualisation | Actualiser la bibliothèque | *inchangé* | Libellé lu par les E2E |
| transfert | Transfert des fichiers · {n} % | *inchangé* | |
| import reçu | Import reçu : {n} PDF transmis[, {k} fichiers non PDF ignorés]. Le suivi indique les étapes réellement exécutées. | {n} PDF reçus par le service[ ; {k} fichiers non PDF ignorés]. Leur extraction et leur indexation s'affichent dans le Suivi. (accord au singulier) | « transmis », « réellement exécutées » sans valeur ; dit où suivre |
| fichiers ignorés | 1 fichier non PDF ignoré · {n} fichiers non PDF ignorés | *inchangé* | |
| ouverture impossible | « {nom} » n'a pas encore de version consultable : attendez la fin de son import dans le Suivi. | *inchangé* | |
| sélection sans PDF | Aucun fichier PDF dans cette sélection : seuls les PDF sont importés. | *inchangé* | |
| filtre (aria-label) | Filtrer les fichiers | *inchangé* | Libellé lu par l'E2E clavier |
| filtre (placeholder) | Filtrer les fichiers… | Nom ou chemin de fichier… | Le placeholder répétait le libellé ; il dit maintenant ce qui est comparé |
| bouton bibliothèque entière | Toute la bibliothèque | *inchangé*, info-bulle « Définir le périmètre sur toute la bibliothèque » | L'action n'était pas dite |
| arborescence (aria-label) | Arborescence documentaire | *inchangé* | Libellé lu par les E2E |
| bibliothèque vide | Aucun document dans la bibliothèque | *inchangé* | |
| idem, description | Importez un PDF ou un dossier de PDF avec les boutons ci-dessus. Les fichiers originaux sont conservés tels quels. | Importez des fichiers avec « Importer des PDF » ou tout un dossier avec « Importer un dossier ». Les fichiers originaux sont conservés tels quels. | Nomme les actions au lieu d'une position (« ci-dessus ») |
| filtre sans résultat | Aucun fichier ne correspond à « {filtre} » · Le filtre porte sur le nom et le chemin relatif des fichiers. · Effacer le filtre | *inchangé* | |
| périmètre d'un dossier (aria-label) | Analyser le dossier {nom} | Définir le périmètre sur le dossier {nom} | Le bouton fixe le périmètre, il ne lance aucune analyse |
| idem (info-bulle) | Définir le périmètre : {chemin} et sous-dossiers | Périmètre : {chemin} et ses sous-dossiers | Évite la redite du nom accessible |
| case à cocher | Sélectionner {nom} | *inchangé* | Libellé lu par les E2E |
| ligne de document | {état} · {n} p. · {a}/{b} | {état} · {n} p. · {a}/{b} p. traitées | Compteur sans unité |
| pied de sélection | Aucun document sélectionné · 1 document sélectionné · {n} documents sélectionnés | *inchangé* | |
| bouton | Utiliser ce périmètre | *inchangé*, info-bulle « Cochez au moins un document pour en faire le périmètre. » quand il est inactif | Libellé lu par les E2E ; raison de l'inactivité |
| libellé de périmètre | {n} PDF sélectionnés | {n} documents sélectionnés | Vocabulaire |
| rail (groupe) | — | Bibliothèque repliée | Nouveau |
| rail | — | Importer des PDF (info-bulle : la bibliothèque se rouvre pour suivre le transfert) | Nouveau |
| rail | — | Filtrer la bibliothèque (info-bulle : par nom ou chemin de fichier) | Nouveau ; distinct du champ « Filtrer les fichiers » |
| rail | — | {n} documents sélectionnés : afficher la bibliothèque pour définir le périmètre | Nouveau : Sélection (n) |

## Lecteur (`pdf-viewer.tsx`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| en-tête sans document | Lecture | Lecteur | Même nom que la zone `main` |
| sur-titre | Original et provenance | *inchangé* | |
| état vide | Aucun document ouvert · Ouvrez un PDF depuis la bibliothèque ou importez-en un. Une source citée dans une réponse s'ouvre ici, à la page et au passage utilisés. | Aucun document ouvert (*inchangé*) · Ouvrez un document depuis la bibliothèque ou importez un PDF. Une source citée dans une réponse s'ouvre ici, à la page et au passage utilisés. | Titre lu par les E2E ; vocabulaire : document pour l'objet, PDF pour le format |
| sur-titre du document | Lecture de l'original | *inchangé* | |
| titre de repli | Document sans métadonnées · Chargement du document… | Document sans informations · *inchangé* | « métadonnées » : jargon |
| retour | Revenir au passage précédent | *inchangé* | Libellé lu par les E2E |
| erreur | Informations du document indisponibles · {message} Sans ces informations, les versions et l'état d'extraction de ce document ne sont pas vérifiés. | *inchangé* | |
| barre d'outils | Afficher le sommaire · Page précédente · Numéro de page · / {n} · Page suivante · Réduire le zoom · {n} % · Augmenter le zoom · Pivoter de 90 degrés · Rotation {n}° · Analyser cette page | *inchangé* | Libellés lus par les E2E |
| recherche locale | Rechercher dans ce PDF | Rechercher dans ce document | Vocabulaire : document |
| bouton | Suivant | Chercher plus loin, avec l'info-bulle « Aller à la page suivante qui contient l'expression » | « Suivant » seul ne disait pas quoi ; la recherche avance de page en page, pas d'occurrence en occurrence |
| attente | Recherche… · Recherche dans le texte du document… | *inchangé* | |
| résultat | Occurrence page {n} | Expression trouvée page {n} | Phrase complète |
| aucun résultat | Aucune occurrence dans le texte disponible. Le contenu graphique n'est pas interprété. | Expression absente du texte disponible de ce document. Le contenu des images sans texte extrait n'est pas lu. | Dit précisément ce qui n'est pas lu |
| avis de publication | Original consultable · extraction et publication en attente. Les passages annotés seront disponibles après indexation. | Original consultable ; son extraction n'est pas encore publiée. Les passages, le sommaire et l'analyse de page s'activeront à la fin de l'indexation, visible dans le Suivi. | Ce qui s'activera et où suivre |
| repère de source | {Sxxx} ou Résultat de recherche · {précision} · version {id} · révision {id} | {Sxxx} ou Passage retrouvé · *inchangé* | Même terme que la carte de source (« Passage ») |
| sommaire (titre) | Sommaire disponible | Sommaire | « disponible » superflu |
| sommaire | Chargement du sommaire… · Sommaire indisponible : {message} · Aucune section extraite pour cette version. · Le sommaire sera disponible après publication de l'extraction. · p. {n} | *inchangé* | |
| sommaire, bouton | Analyser | *inchangé*, nom accessible « Analyser la section {titre} » | Boutons homonymes distingués |
| chargement | Lecture de l'original impossible · Recharger la page · Chargement de l'original PDF… | *inchangé* | |
| pied | Texte extrait & provenance · Version {id} | *inchangé* | Libellé lu par les E2E |
| blocs extraits | Page {n} · blocs réellement extraits | Page {n} · blocs extraits | « réellement » superflu |
| blocs extraits | Chargement des blocs extraits… · Blocs extraits indisponibles : {message} · Aucun texte extrait pour cette page. · Les blocs extraits seront disponibles après publication de l'extraction. · Analyser ce bloc | *inchangé* | « Analyser ce bloc » lu par les E2E |
| bloc non sélectionnable (info-bulle) | Révision et empreinte du bloc requises pour la sélection. | Ce bloc n'a pas de révision ou d'empreinte vérifiable : il ne peut pas servir de périmètre. | Dit la conséquence |
| libellés de périmètre | Bloc source · page {n} · {document} · page {n} · Document | *inchangé* | Lus par les E2E |
| légende de page | Page {n} · folio {étiquette} · Page blanche · Texte OCR · Texte natif | *inchangé* | Lus par les E2E |
| légende de page | Natif + régions OCR | Texte natif et régions OCR | Phrase au lieu d'un symbole |
| légende de page | Image | Aucun texte extrait | « Image » ne disait pas l'état du texte |
| canevas (aria-label) | Original PDF, page {n} | Page {n} de l'original PDF | Ordre naturel |
| calque OCR (aria-label) | Texte OCR extrait sélectionnable | *inchangé* | |
| sélection refusée | La provenance de cette révision n'est pas disponible ; aucune extraction récente n'est substituée. · La sélection annotée sera disponible après publication de l'extraction. | *inchangé* | |
| sélection ambiguë | Cette sélection ne correspond pas de façon unique aux blocs extraits. Utilisez l'analyse de page ou sélectionnez le texte extrait. | … Utilisez « Analyser cette page » ou choisissez un bloc dans « Texte extrait & provenance ». | Nomme les actions réelles |
| provenance | Provenance indisponible : {message} | *inchangé* | |
| rendu impossible | Le navigateur ne permet pas le rendu du PDF. | Ce navigateur ne fournit pas de contexte de dessin 2D : la page ne peut pas être affichée. | Cause précise |

## Outils du document (`document-tools.tsx`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| menu (aria-label, info-bulle) | Actions et versions du document | *inchangé* | Lu par les E2E |
| choix de version | Version affichée | *inchangé* | Lu par les E2E |
| option | {id} · {n} p. / pages en attente · active | {id} · {n} p. / nombre de pages inconnu · version active | « pages en attente » ambigu ; « active » seul |
| empreinte | SHA-256 {début} / indisponible | Empreinte SHA-256 {début} / non communiquée | Nomme la valeur ; l'API ne la fournit pas toujours |
| réindexation | Réindexer ce document · Demande de réindexation… · Réindexation possible une fois le traitement en cours terminé. | *inchangé* | Lu par les E2E |
| avis | Réindexation demandée. Le suivi affiche sa progression. | Réindexation demandée : sa progression s'affiche dans le Suivi. | Même nom que le bouton « Suivi » |
| retrait | Retirer de la bibliothèque · Retirer ce document de la bibliothèque ? · « {nom} » ne sera plus proposé… · Retirer le document · Retrait en cours… · Annuler | *inchangé* | Conséquence déjà dite (étape A) |

## Analyse (`analysis-panel.tsx`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| titre, sur-titre | Analyse · Réponses avec sources | *inchangé* | Titre lu par les E2E |
| onglets | Mode d'analyse · Question · Recherche · Comparer | *inchangé* | Lus par les E2E |
| périmètre actif | Périmètre actif · 1 passage référencé · {n} passages référencés | *inchangé* | |
| recherche | Périmètre de cette recherche : {libellé} · {n} passages retrouvés · {n} ms | *inchangé* | |
| index incomplet | Index incomplet pour ce périmètre · Aucun passage retrouvé dans les documents déjà indexés. {n documents…} : relancez la recherche une fois leur traitement terminé dans le Suivi. | *inchangé* | |
| aucun passage | Aucun passage retrouvé · Aucun passage indexé de ce périmètre ne contient ces termes… | *inchangé* | |
| résultat non ouvrable | Le résultat reçu n'expose pas de source consultable. | Ce résultat ne désigne aucune version de document : il ne peut pas être ouvert dans le lecteur. | Dit la cause et la conséquence |
| état initial recherche | Retrouver un passage · Recherchez un code, une expression ou une notion dans le périmètre actif. La recherche lit l'index sans appeler le modèle de réponse. | *inchangé* | |
| état initial question | Aucune question posée · Posez une question sur le périmètre actif… | *inchangé* | |
| état initial comparaison | Comparer des documents · Définissez un périmètre de deux à quatre PDF, puis… | … deux à quatre documents, puis… | Vocabulaire |
| reconnexion | Reconnexion | Reconnecter | Un bouton porte un verbe |
| limite de longueur | La réponse a atteint sa limite de longueur. Reformulez ou demandez explicitement une suite dans le même périmètre. | *inchangé* | |
| réponse incomplète | Cette réponse est incomplète. | Cette réponse est incomplète : elle a été annulée ou interrompue avant la fin. | Dit pourquoi |
| sources | 1 source consultable · {n} sources consultables | *inchangé* | |
| carte de source | Passage · p. {n} · folio {étiquette} · version {id} · Ouvrir le passage | *inchangé* | Lus par les E2E |
| carte de source, nom de repli | Document source | Document sans nom | Le repli dit l'absence |
| citation (info-bulle) | Ouvrir {document}, page {n} | *inchangé* | |
| citation inconnue | [Sxxx] · non validée | [Sxxx] (référence inconnue) | Dit ce qui manque |
| idem (info-bulle) | Identifiant absent du registre de sources | Cette référence n'est pas enregistrée dans les sources de la réponse : elle n'ouvre aucun passage. | Jargon « registre » ; conséquence |
| sélection | Analyser la sélection | *inchangé* | |
| libellé de périmètre | Sélection de texte du document | Texte sélectionné dans le document | Un seul terme |
| comparaison impossible | Définissez un périmètre de deux à quatre PDF pour comparer. | … deux à quatre documents pour comparer. | Vocabulaire |
| saisie | Votre recherche · Votre question · Expression ou référence à retrouver… · Quels points comparer entre ces documents ? · Posez une question sur ce périmètre… | *inchangé* | Libellés lus par les E2E |
| aide de saisie | Ctrl + Entrée | Ctrl + Entrée pour envoyer / pour rechercher (touches en `<kbd>`) | Dit ce que fait le raccourci |
| boutons | Annuler · Annulation… · Rechercher · Envoyer | *inchangé* | Lus par les E2E |
| attente | Envoi… (recherche et question) | Recherche… (recherche) · Envoi… (question) | Une recherche n'envoie rien au modèle |
| flux | Précisez le référent documentaire de votre question. · La réponse a été interrompue par une erreur du service. · Une référence non enregistrée dans les sources a été signalée et reste non cliquable. | *inchangé* | |

## Suivi des traitements (`jobs-panel.tsx`, déplacé depuis `workspace.tsx`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| titre | Suivi des traitements | *inchangé* | |
| fermeture | (icône seule, nom accessible « Fermer le suivi ») | Fermer (nom accessible « Fermer le suivi ») | Bouton Fermer libellé ; nom lu par les E2E |
| erreur de lecture | Suivi illisible | Lecture du suivi impossible | Décrit l'échec |
| panne, message | Service local indisponible · {message} La liste affichée date de la dernière lecture réussie. | *inchangé* | |
| priorité | Priorité aux questions · Priorité aux imports · Changement de priorité… | *inchangé* | Lus par les E2E |
| avis | Priorité aux questions demandée. Les imports se reprennent explicitement. | Priorité aux questions demandée : les indexations en cours s'arrêtent à leur prochain point de reprise. Relancez-les ensuite avec « Reprendre l'indexation ». | Comportement réel de `POST /runtime/mode` (`request_pause_all`) |
| avis | Priorité aux imports demandée. Le service gère la transition en cours. | Priorité aux imports rétablie. Les indexations mises en pause restent à relancer une par une avec « Reprendre l'indexation ». | Formule vague remplacée ; `manual_jobs_require_resume: true` |
| chargement, vide | Chargement des traitements… · Aucun traitement enregistré · Les imports et réindexations apparaissent ici… | *inchangé* · *inchangé* · Les imports et les réindexations apparaissent ici… | Correction |
| document de repli | Document non identifié : bibliothèque indisponible · Traitement documentaire | Document non identifié : la bibliothèque n'a pas pu être lue · Document absent de la bibliothèque · Identification du document… | Trois cas distincts ; « Traitement documentaire » ne disait rien |
| avancement (aria-label) | Avancement du traitement | Avancement du traitement de {document} | Plusieurs barres distinguées |
| couverture | {a}/{b} pages traitées · {n} pages avec OCR | {a}/{b} pages traitées · {n} page(s) lue(s) par OCR (si n > 0) | Accord ; « 0 page » masqué |
| extraction partielle | Extraction partielle publiée : les réponses restent limitées aux pages traitées. | *inchangé* | |
| extraction partielle | Extraction partielle vérifiée. Les pages manquantes ne seront pas recherchées. | Extraction partielle vérifiée, non publiée. Les pages manquantes ne seront pas recherchées ; publiez-la pour interroger les pages traitées. | Action possible |
| actions | Utiliser cette extraction partielle · Publication… · Mettre en pause · Mise en pause… · Reprendre l'indexation · Reprise… · Annuler ce traitement · Annulation… | *inchangé* | « Reprendre l'indexation » lu par les E2E |

## Composants communs (`components/ui/`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| `panel.tsx` `PanelError` | Service local indisponible (titre par défaut) · Réessayer | *inchangé* | |
| `confirm-dialog.tsx` | Annuler | *inchangé* | |
| `status-indicator.tsx` (info-bulle d'un code inconnu) | Code transmis par le service : {code} / absent | *inchangé* | Le code reste en diagnostic |

## États (`lib/status.ts`) et localisation (`lib/source-location.ts`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| états de document | Importé · En attente · Extraction en cours · OCR en cours · Indexation en cours · Prêt · Extraction partielle · Erreur · Retiré · En pause · Mise en pause en cours · État de document non reconnu | *inchangé* | « Prêt » et « Erreur » lus par les E2E |
| états de traitement | En attente · Traitement en cours · Extraction en cours · OCR en cours · Indexation en cours · Mise en pause en cours · Indexation en pause — reprise manuelle · Point de reprise enregistré — reprise manuelle · Interrompu — reprise manuelle · Annulation en cours · Annulé · Terminé · Extraction partielle · Échec · État de traitement non reconnu | *inchangé* | |
| étapes de traitement | extraction du texte · passages découpés, vectorisation à venir · vectorisation et écriture dans l'index · publication terminée · reprise demandée · arrêt au dernier point de reprise | *inchangé* | |
| statut de réponse `running` | Travail en cours | Traitement de la question en cours | Formule générique |
| autres statuts de réponse | Question enregistrée · En attente · Recherche des passages · Préparation des preuves · Preuves prêtes · Sources retrouvées · Rédaction en cours · En attente de la pause de l'indexation · En attente de mémoire disponible · Annulation demandée · Réponse terminée · Réponse limitée par la longueur · Précision nécessaire · Preuves insuffisantes · Réponse annulée · Réponse interrompue · Échec · Statut de réponse non reconnu | *inchangé* | Libellés terminaux lus par les E2E |
| précision de source | Localisation à la page · Table source · Passage source · Bloc source · Source non localisée | *inchangé* | Lus par les E2E et les tests unitaires |

## Messages des modules `lib/`

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| `api.ts`, service injoignable | Le service local ne répond pas. Vérifiez qu'il est démarré, puis réessayez. | … Vérifiez qu'il est démarré (.\rag.ps1 status), puis réessayez. | Commande de vérification |
| `api.ts`, adresse refusée | L'adresse de la ressource n'est pas autorisée. · Adresse de ressource invalide. | Adresse refusée : seules les ressources de l'API locale (/api/v1) sont chargées. | Deux formulations pour un même refus |
| `api.ts` → `warnings.ts` `httpFailureMessage`, refus sans message | Le service répond {statut}. | 5xx : Le service local a échoué (HTTP {statut}). Réessayez ; si l'échec persiste, consultez son journal : la commande .\rag.ps1 logs en donne l'emplacement. · 4xx : Le service local a refusé la demande (HTTP {statut}). | Statut brut remplacé par une phrase ; action pour les pannes |
| `api.ts`, import interrompu | Import interrompu : connexion au service perdue. | Import interrompu : la connexion au service local a été perdue. Vérifiez qu'il est démarré, puis relancez l'import. | Action |
| `api.ts`, import refusé sans message | Import refusé par le service. | `httpFailureMessage(statut)` | Même règle que les autres refus |
| `utils.ts`, erreur sans message | Le service n'a pas pu terminer cette opération. | L'opération a échoué sans message exploitable. Réessayez ; si l'échec persiste, consultez le journal du service : la commande .\rag.ps1 logs en donne l'emplacement. | Formule générique ; action. `logs` imprime le chemin du journal de chaque service, pas son contenu (`services/runtime/cli.py`) |
| `stream.ts`, événement illisible | Le flux du service contient un événement invalide. | Le flux de la réponse contient un événement illisible : la réponse est interrompue. Posez de nouveau la question pour relancer le traitement. | Conséquence et action |
| `warnings.ts`, avertissement sans message | {code brut} | Le service signale une limite sans la décrire (code {code}). | Aucun code brut affiché seul |
| `warnings.ts`, avertissement vide | Le service signale une limite. | Le service signale une limite sans la décrire. | Dit qu'aucun détail n'est disponible |
| `warnings.ts`, composant non prêt | Base documentaire illisible · Base documentaire non vérifiée · Modèle de recherche absent · Index vectoriel indisponible · Modèle de réponse indisponible · Contrôle des ressources inactif | *inchangé* | |
| idem | Tokenizer du modèle absent | Tokenizer du modèle de réponse absent | Précise lequel |
| idem, code inconnu | {code brut} | Composant local non prêt (code {code}) | Aucun code brut affiché seul |
| `provenance-revision.ts` | La citation ne fournit pas sa révision d'extraction… · La révision courante ne peut pas être vérifiée… · Vérification de la révision courante… · Cette citation utilise une révision archivée… · Les blocs reçus ne correspondent pas… Aucune extraction récente n'est substituée. · Le sommaire reçu ne correspond pas à la révision de la citation. | *inchangé* | Précis ; testés |
| `citation-link.ts` | Le lien de citation ne contient pas deux identifiants valides. · Le registre ne fournit pas la version, page et révision exactes de cette citation… | *inchangé* | Premier message lu par l'E2E `negative-deeplink` |
| `page-range.ts` | Le nombre de pages de la version ouverte n'est pas encore connu. · La plage doit correspondre aux pages de la version ouverte (1 à {n}). | *inchangé* | |
| `selection.ts` | Invalid UTF-16 offset · Offset splits a surrogate pair | *inchangé* | Exceptions internes, jamais affichées |

## Page d'accueil et métadonnées (`app/`)

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| `layout.tsx`, titre de page | Atelier documentaire local | Atelier documentaire | Nom de produit arrêté, identique à la barre |
| `layout.tsx`, description | Lecture et analyse documentaire avec sources vérifiables. | Poste documentaire local : lecture des PDF, recherche de passages et questions avec sources citées. | Formule vague ; usages réels |
| `page.tsx`, sur-titre | Poste local | Poste documentaire local | Sous-titre unique |
| `page.tsx`, titre | Atelier documentaire | *inchangé* | |
| `page.tsx`, texte | Lire, retrouver et vérifier les sources de vos documents. | Importez des PDF, retrouvez un passage et posez vos questions : chaque réponse renvoie à la page et au texte qu'elle cite. | Dit ce que fait l'outil |
| `page.tsx`, lien | Ouvrir l'espace de travail → | Ouvrir l'espace de travail (flèche masquée aux lecteurs d'écran) | Flèche décorative |

## Limites

- Relecture faite sur le code ; le rendu (longueur réelle des libellés dans la barre de 56 px, retours à la ligne, troncatures) reste à examiner aux largeurs de QA 320, 360, 768, 1 024, 1 280 et 1 440 px.
- Les messages rédigés par le service (`services/api`) ne sont pas réécrits ici ; plusieurs sont précis (« Référence non retrouvée dans les passages de ce périmètre. »), d'autres restent techniques (« Entrée invalide. »). Leur reprise relève du backend.
- « Modèle ou worker non prêt » reprend la formulation demandée pour l'état des services ; le détail des composants en cause figure dans l'info-bulle et dans le bandeau de contexte.
