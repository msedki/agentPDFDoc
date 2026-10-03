# Inventaire des textes de l'interface (lot R15, étape B du lot R16)

**Rôle :** inventaire des textes visibles ou restitués par `apps/web/src/`, avec leur réécriture et son motif · **Propriétaire :** frontend documentaire (R15/R16) · **Statut :** Vivant ; R15-2 vérifié dans sa portée, E03 validé sur recette UI doublée ; R15/D06 ouverts · **Référence :** inventaire initial sur `ae387a9`, compléments R15-1/R15-2 datés conservés ; base publiée `f331421` et correction locale E03 du 03/10/2026 · **Mis à jour :** 2026-10-03 18:09 (UTC) · **Source de vérité :** `apps/web/src/` pour les textes livrés ; ce document pour les motifs ; journal pour les résultats d'exécution.

« Avant » désigne l'état au début de l'étape B (après l'étape A, non commitée). Un texte marqué *inchangé* a été relu et gardé. « Nouveau » signale un texte introduit par l'étape B. Ces tables gardent leur rôle historique : les compléments datés les remplacent lorsqu'un texte ou un contrat a évolué. Les messages rédigés par le service, `job.error_message`, noms, chemins, titres de sections, texte extrait, questions et réponses sont affichés tels qu'ils arrivent et ne sont pas réécrits ici. Les traductions frontend des codes d'avertissement sans message et les textes de repli sont en revanche inventoriés.

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
| idem | Préparation requise, puis Modèle ou worker non prêt | Service local pas encore prêt | L'état global n'identifie pas une cause unique ; les composants concernés restent nommés dans l'info-bulle et le bandeau |
| idem | — | Index incomplet | Documents importés que l'index ne couvre pas encore |
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

## Commandes du lanceur selon le poste (W018, 1er octobre 2026)

Le poste annonce ses commandes dans `GET /api/v1/health` (`commands.open`, `status`, `logs`, `doctor`) ; l'atelier les lit au chargement (`src/lib/launcher.ts`). Une commande annoncée est citée telle quelle ; une commande absente de la réponse prend le lanceur livré qu'emploient toutes les commandes annoncées (plateforme connue). « Windows » et « Linux » désignent le texte affiché une fois la plateforme connue ; « inconnues » le texte affiché tant qu'elle ne l'est pas (`/health` sans réponse ou en échec, lanceurs mêlés). Sous Windows, chaque texte est identique à celui d'avant W018 dès que la plateforme est connue, quel que soit l'ordre d'arrivée de `/health` et de la requête en échec : chaque composant garde l'échec et calcule son texte au rendu (`src/components/ui/error-text.tsx`). `tests/unit/windows-texts.test.ts` compare ces textes à ceux du commit 26fa7a5 lus par `git show` ; `tests/unit/launcher.test.ts`, `tests/unit/session-check.test.ts` et `tests/unit/error-text.test.ts` couvrent les autres cas.

| Emplacement | Windows | Linux | Commandes inconnues |
|---|---|---|---|
| `warnings.ts` `serviceUnreachableMessage`, service injoignable | … Vérifiez qu'il est démarré (.\rag.ps1 status), puis réessayez. | … (./rag.sh status) … | … (.\rag.ps1 status sous Windows ou ./rag.sh status sous Linux) … |
| `warnings.ts` `httpFailureMessage` (5xx) et `utils.ts` `errorMessage` | … la commande .\rag.ps1 logs en donne l'emplacement. | … ./rag.sh logs … | … .\rag.ps1 logs sous Windows ou ./rag.sh logs sous Linux … |
| `warnings.ts` `readinessSentence` | La commande .\rag.ps1 doctor détaille chaque contrôle … | ./rag.sh doctor | .\rag.ps1 doctor sous Windows ou ./rag.sh doctor sous Linux |
| `session.ts`, écran « Session requise » | Dans PowerShell, depuis le dossier du projet, lancez la commande ci-dessous … | Dans un terminal, … | Dans PowerShell sous Windows ou dans un terminal sous Linux, depuis le dossier du projet, lancez la commande de votre système ci-dessous … |
| `session.ts`, écrans « Session expirée », « Session fermée », « Lien d'ouverture expiré ou déjà utilisé » | … avec la commande ci-dessous … | idem | … avec la commande de votre système ci-dessous … (deux lignes de commande affichées) |
| `session-gate.tsx`, commande d'ouverture | `.\rag.ps1 open`, bouton « Copier la commande » | `./rag.sh open` | Deux lignes titrées « Windows » et « Linux », boutons « Copier la commande Windows » et « Copier la commande Linux » |
| `app-topbar.tsx`, info-bulle « Fermer la session » | … Pour revenir : .\rag.ps1 open depuis le dossier du projet. | ./rag.sh open | .\rag.ps1 open sous Windows ou ./rag.sh open sous Linux |

## Réindexation d'un document (1er octobre 2026)

`POST /documents/{id}/reindex` répond selon le dernier traitement du document (contrat `reindex_outcomes`) : traitement en cours renvoyé (`reused`), traitement `paused` renvoyé avec `resume_required`, refus 409 `job_pausing` pendant une mise en pause, traitement neuf dans les autres cas, y compris pendant une annulation. Le menu du document lit cette réponse (`src/lib/reindex.ts`, `tests/unit/reindex.test.ts`).

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| `document-tools.tsx`, avis après un nouveau traitement | Réindexation demandée : sa progression s'affiche dans le Suivi. | *inchangé* | — |
| idem, traitement déjà en cours (`reused`) | Réindexation demandée : sa progression s'affiche dans le Suivi. | Un traitement de ce document est déjà en cours : aucune nouvelle réindexation n'a été lancée. Sa progression s'affiche dans le Suivi. | Aucune réindexation n'est lancée |
| idem, traitement en pause (`resume_required`, `paused`) | Réindexation demandée : sa progression s'affiche dans le Suivi. | Le dernier traitement de ce document est en pause : la réindexation n'en lance pas un second. Reprenez-le pour poursuivre l'indexation depuis son dernier point de reprise. Bouton « Reprendre le traitement » (attente : « Reprise… »), puis « Reprise demandée : sa progression s'affiche dans le Suivi. » | Rien ne progressait sans reprise |
| idem, `pausing` (409 `job_pausing`) | idem | Message du service sous le bouton, tel quel : « Mise en pause en cours pour ce document : attendre qu'elle aboutisse, puis reprendre ce travail depuis le Suivi. » | Le service refuse la demande sans créer de traitement ; l'atelier n'ajoute aucun texte |
| idem, `cancelling` | idem | Réindexation demandée : sa progression s'affiche dans le Suivi. | Le service crée un traitement neuf, exécuté après l'annulation |
| idem, `resume_required` avec un autre état que `paused` | idem | Un traitement suspendu de ce document existe déjà (état {code}) : aucune nouvelle réindexation n'a été lancée. Consultez le Suivi pour le reprendre. | Repli : ce service ne renvoie que `paused` ; aucune reprise proposée qui pourrait être refusée ; le code reste lisible |

## Import d'un fichier identique dont le traitement est suspendu (1er octobre 2026)

`POST /documents/import` renvoie, pour un fichier identique déjà importé au même chemin dont le traitement est `paused`, `pausing` ou `cancelling`, ce traitement avec `job_state` et `resume_required`, sans en lancer un autre (`Database.import_original`). L'avis de la bibliothèque le dit (`src/lib/import-outcome.ts`, `tests/unit/import-outcome.test.ts`). Les phrases ci-dessous suivent l'avis « {n} PDF reçus par le service[ ; {k} fichiers non PDF ignorés]. » ; « Ce fichier » quand un seul PDF est importé, « Un fichier » parmi plusieurs, « {n} fichiers étaient… leurs traitements… » au pluriel.

| Emplacement | Texte avant | Texte après | Motif |
|---|---|---|---|
| `library-panel.tsx`, avis d'import sans traitement suspendu | {n} PDF reçus par le service[ ; {k} fichiers non PDF ignorés]. Leur extraction et leur indexation s'affichent dans le Suivi. | *inchangé* | — |
| idem, autres fichiers de l'import | Leur extraction et leur indexation s'affichent dans le Suivi. | L'extraction et l'indexation de l'autre fichier / des {m} autres fichiers s'affichent dans le Suivi. | Seuls ces fichiers progressent |
| idem, `paused` | idem | Ce fichier était déjà importé à l'identique et son traitement est en pause : l'import n'en lance pas un second. Reprenez-le pour poursuivre son indexation depuis son dernier point de reprise. Bouton « Reprendre le traitement » ou « Reprendre les {n} traitements » (attente : « Reprise… »), puis « Reprise demandée : sa progression s'affiche dans le Suivi. » ou « Reprises demandées : leur progression s'affiche dans le Suivi. » | Rien ne progressait sans reprise |
| idem, `pausing` | idem | Ce fichier était déjà importé à l'identique et son traitement est en cours de mise en pause : l'import n'en lance pas un second. Une fois la pause effective, reprenez-le depuis le Suivi. | La reprise est refusée tant que la pause n'est pas effective (409 `job_not_resumable`) |
| idem, `cancelling` | idem | Ce fichier était déjà importé à l'identique et son traitement est en cours d'annulation : l'import n'en lance pas un second. Une fois l'annulation terminée, importez-le de nouveau pour lancer un nouveau traitement ; le Suivi indique quand elle l'est. | Un traitement annulé n'est plus renvoyé : le réimport en crée un nouveau |
| idem, autre état | idem | Ce fichier était déjà importé à l'identique et son traitement est suspendu (état {code}) : l'import n'en lance pas un second. Consultez le Suivi pour le reprendre. | Repli ; aucune action proposée qui pourrait échouer |

## Compléments du 2 octobre 2026

Les commandes propres à Windows/Linux sont inventoriées dans leur section ci-dessus. Les nouveaux messages ci-dessous ont été relus dans le code ; les résultats des tests et les captures restent des preuves distinctes.

| Emplacement | Texte ou famille de textes | Rôle et condition |
|---|---|---|
| `library-panel.tsx`, boîte fermée sans fichier | Aucun fichier n'a été transmis par la boîte de choix. Si vous en aviez choisi un, faites-le glisser depuis votre gestionnaire de fichiers et déposez-le sur la bibliothèque. | Décrit l'absence de fichier reçu sans affirmer que l'utilisateur en a choisi un ; propose le dépôt réellement disponible |
| idem, dépôt de PDF | Déposez les PDF pour les importer dans la bibliothèque. | Action pendant le survol, pas promesse d'import déjà accepté |
| idem, import déjà actif | Un import est déjà en cours : attendez sa fin pour déposer d'autres PDF. | Explique le refus temporaire d'un second dépôt |
| `generation.ts`, mode CPU | Réponses calculées sur le processeur | Ne concerne que le modèle de réponse ; le détail renvoie à la rubrique « calcul » de `doctor` |
| idem, modèle entièrement résident sur GPU | Réponses calculées sur le GPU | N'est affirmé qu'après observation de la résidence complète ; la recherche et l'import restent sur CPU |
| idem, résidence partielle | Réponses calculées en partie sur le processeur | Distingue le GPU retenu et la répartition CPU/GPU réellement observée |
| idem, GPU retenu mais modèle sur CPU | GPU retenu, réponses calculées sur le processeur | Un choix de mode ne prouve pas une résidence GPU |
| idem, échec puis repli | GPU en échec : réponses calculées sur le processeur | Repli de l'instance après échec ; diagnostic et action au prochain démarrage, pas nouveau téléchargement implicite |

Preuves historiques : les [journaux des 30 septembre et 1er octobre](../../../RAG_Local_Agents/journal/README.md) identifient les recettes R15/R16/R20 et leurs captures. Le [journal du 2 octobre](../../../RAG_Local_Agents/journal/2026-10-02.md) distingue la recette d'import avec l'API réelle, la boîte native du Chromium snap en échec et le dépôt réussi. Les tests `status`, `generation`, `launcher`, `windows-texts` et `import-outcome` couvrent les formulations et conditions ; leur réussite ne prouve pas un GPU Windows ni toutes les largeurs de rendu. Le 2 octobre, R15-1 a vérifié le nouveau libellé sur l'export courant aux deux tailles desktop, avec readiness interceptée explicitement (test UI isolé). Six scénarios séparés utilisent l'API réelle : clavier, panneaux, dépôt/cancel, lecture-recherche-passage et périmètres page/bloc. Le journal porte les commandes et preuves, sans étendre cette recette aux autres états.

## Revue éditoriale complète et corrections R15-2 — 2 octobre 2026

La revue de source couvre les 54 fichiers TS/TSX et les `content` des trois CSS de `src/`, soit 57 empreintes. Elle complète les tables historiques, sans les effacer. La [preuve de lecture](../../../.runtime/qa/r15-editorial-20261002T191600Z/frontend-source-review.json) contient 16 constats FE01–FE16 et six omissions IN01–IN06 ; elle ne constitue pas une recette de rendu. Son champ HEAD initial a été associé à tort à l'heure du relevé : l'[erratum séparé](../../../.runtime/qa/r15-editorial-20261002T191600Z/frontend-source-review-erratum.json) conserve cette preuve et établit 57/57 empreintes identiques à `ee2341aa78c549a115cac375ec417cf7fe8d5a18`. Il ne reconstitue pas l'instant historique de lecture de chaque fichier.

État de préparation au 02/10/2026 à 20:16 UTC : corrections implémentées localement, [244 tests unitaires](../../../.runtime/qa/r15-editorial-20261002T191600Z/r15-2/green-unit.xml) réussis ; reproductions rouges et reprises séparées dans le [dossier de preuve](../../../.runtime/qa/r15-editorial-20261002T191600Z/r15-2/README.md). Le [contrôle de types](../../../.runtime/qa/r15-editorial-20261002T191600Z/r15-2/typecheck.json) passait après le renforcement du garde de version active : TypeScript 5.9.3, Node 24.16.0, `tsc --noEmit`, caches SD isolés. Aucun build ni navigateur exécuté à cet instant ; la compilation du fichier E2E ne l'exécutait pas. Depuis, build et recette ont été réalisés : rejeu final du 02/10 à 22:59 UTC, onze scénarios réussis et rendu relu indépendamment. Le [PLAN canonique](../../../RAG_Local_Agents/PLAN.md) et le [journal](../../../RAG_Local_Agents/journal/2026-10-02.md) portent les preuves, les substitutions UI et les limites de cette validation, sans clôture globale D06.

Avant toute recette Playwright, la cible et le stockage QA isolés doivent être vérifiés, et `RAG_E2E_BASE_URL` ainsi que `RAG_E2E_CONTROL_TOKEN_FILE` fournis explicitement pour cette même instance. Le seul flag `RAG_E2E_READONLY_ALLOWED` ne garantit pas l'isolation : `tests/global-setup.ts` effectue un POST réel `/api/v1/admin/session-links` avant les `skip`, échange le lien contre la session et écrit l'état d'authentification local. Sans ces paramètres explicites, les valeurs par défaut désignent le port 8785 et le jeton principal. Les blocages de mutation de `readOnlyApi` concernent ensuite la page, hors POST synthétiques explicitement interceptés ; « GET-only » décrit le corps du scénario après authentification, pas toute sa préparation. Ces POST et scénarios étaient non exécutés au relevé de préparation de 20:16 UTC ; les recettes ultérieures sur instances QA propres sont consignées dans le journal lié ci-dessus.

Cet inventaire porte désormais les formulations et conditions courantes. Les rapports figés et leurs errata conservent les états observés lors de chaque contrôle ; ils ne sont pas un second inventaire concurrent.

### Corrections de formulations et de retours utilisateur

| Constat / emplacement | Texte livré ou règle de présentation | Motif et borne |
|---|---|---|
| FE05, `jobs-view.ts` / `jobs-panel.tsx` | Aucune reprise d'indexation mise en file. Vérifiez les états dans le Suivi. / 1 reprise d'indexation mise en file ; son état s'affiche dans le Suivi. / {n} reprises d'indexation mises en file ; leur état s'affiche dans le Suivi. | Le nombre vient de `response.resumed`, pas du compteur avant clic ; mise en file acceptée, pas preuve de redémarrage du moteur |
| FE15, Suivi d'un partiel non publié | terminée, publication à décider · Extraction partielle terminée, non publiée : seul le texte extrait deviendra interrogeable si vous la publiez. Consultez les limites signalées avant de décider. | Ni validation qualité ni limite réservée aux pages manquantes ; le bouton explicite de publication et son périmètre sont conservés |
| FE15, Suivi d'un partiel publié | Extraction partielle publiée : pour ce document, les recherches et les réponses utilisent seulement le texte extrait disponible. Consultez les limites signalées. | Des régions ou du texte peuvent manquer même si toutes les pages sont traitées |
| FE06, recherche vide sans index incomplet | La recherche n'a retrouvé aucun passage dans ce périmètre. Une recherche sans résultat ne prouve pas l'absence de l'information : reformulez ou élargissez le périmètre. | Le retrieval vide ne certifie pas l'absence dans le document ou dans l'index ; la branche « Index incomplet pour ce périmètre » reste distincte |
| FE07, accueil | Importez des PDF, retrouvez des passages et posez vos questions. Ouvrez les sources citées pour vérifier la page et le texte utilisés. | Une abstention, clarification ou erreur ne fournit pas nécessairement de citation |
| FE07, aucune question posée | Posez une question sur le périmètre actif. Si la réponse cite des sources, ouvrez-les pour vérifier la page et le texte utilisés. | Invitation conditionnelle ; pas de garantie de source pour chaque réponse |
| FE08, aucun document ouvert | Ouvrez un document depuis la bibliothèque ou importez un PDF. Une source consultable s'ouvre ici à la page concernée ; le passage est surligné lorsque sa position est connue. | Une source à précision page reste consultable sans surlignage précis |
| FE09, lecteur | « Analyser » définit le périmètre de la prochaine recherche ou question, sans lancer de traitement. | Les actions page/section/bloc continuent de choisir le périmètre seulement ; aucun démarrage automatique |
| FE09, sélection présente | Le bouton « Analyser la sélection » définit le périmètre de la prochaine recherche ou question, sans lancer de traitement. | La sélection observée ne devient pas implicitement le périmètre avant le clic |
| FE11, réindexation désactivée, document en pause | Ce traitement est en pause : reprenez l'indexation dans le Suivi. | Une pause manuelle ne se termine pas en attendant |
| FE11, document annulé / retiré / état inconnu | Le traitement de ce document a été annulé ; importez de nouveau le fichier pour demander une nouvelle indexation. / Ce document a été retiré de la bibliothèque. / La réindexation n'est pas proposée pour l'état actuel de ce document. Consultez le Suivi. | Texte seulement ; les états autorisés à la réindexation restent `ready`, `ready_partial`, `error` |
| FE12, légende de page | Lecture de la page… / Page blanche / Texte natif / Texte OCR / Texte natif et régions OCR / Texte extrait disponible / Texte extrait non vérifié / Aucun texte extrait | Les blocs textuels conservés sans couche sélectionnable ne prouvent pas une origine OCR. Les seules boîtes/spans admissibles restent dans `ocrOverlays` ; aucune géométrie n'est inventée. Une erreur de lecture des blocs n'est pas une absence de texte |
| FE13, échec d'ouverture par réseau ou HTTP | Ouverture de l'atelier impossible · Vérification de la session impossible · Vérifier de nouveau | Une réponse HTTP d'erreur prouve que le service a répondu ; son message reste intact. Les écrans d'expiration/fermeture ne changent pas |
| FE14, échec de copie | Copie impossible : sélectionnez la commande voulue et copiez-la manuellement. | Retour visible `role="alert"`, sans supposer permission, navigateur ou cause ; la commande n'est jamais exécutée |
| FE10, avertissements de réponse | Texte du serveur inchangé ; un avertissement identique dans `warning` puis `done` n'est montré qu'une fois. | Identité sur tous les champs JSON indépendamment de l'ordre des clés ; code, message, référence ou détails différents restent distincts. Le périmètre et le contrat SSE ne changent pas |

### Traductions d'extraction sans message fourni par le serveur (IN01)

`groupedWarningTexts` regroupe les répétitions du même code avec les pages (indices API + 1) et le nombre de zones. Un message serveur présent reste prioritaire et inchangé. Les 27 entrées frontend ci-dessous sont inventoriées, y compris les nouvelles limites ; elles ne transforment pas un code en cause plus précise que le pipeline. FE01–FE04 et FE16 portent les corrections de provenance, de repli et de faute native.

| Code | Intitulé | Conséquence affichée |
|---|---|---|
| `GRAPHIC_INTERPRETATION_UNAVAILABLE` | Schémas ou images non interprétés | leur contenu n'est ni recherché ni cité ; le texte de ces pages l'est. Consultez la figure dans le lecteur. |
| `PAGE_WITHOUT_EXTRACTED_TEXT` | Pages sans texte extrait | aucun texte n'y a été trouvé (page blanche, logo seul ou image non lue). |
| `DOCUMENT_WITHOUT_TEXT` | Document sans texte extrait | aucune page n'apporte de texte recherchable. |
| `DOCLING_CONVERSION_FAILED` | Pages non converties | leur texte n'a pas pu être extrait ; réindexez le document ou consultez le diagnostic du poste. |
| `PAGE_GROUP_RETRIED_BY_PAGE` | Pages retraitées une à une | un groupe de pages a échoué et a été repris page par page. |
| `NATIVE_QUALITY_FAILED` | Couche texte native peu fiable | le texte intégré au PDF ne passait pas le contrôle de qualité. |
| `NATIVE_ESCALATED_TO_STRUCTURED` | Pages relues par l'analyse de mise en page | leur couche texte native ne passait pas le contrôle de qualité. |
| `STRUCTURED_TEXT_LOSS` | Texte écarté par l'analyse de mise en page | une partie du texte intégré au PDF manquait après l'analyse ; si la relecture directe n'a pas pu le reprendre, ce texte n'est ni recherché ni cité. |
| `STRUCTURED_FELL_BACK_TO_NATIVE` | Pages reprises depuis le texte intégré au PDF | une partie du texte intégré au PDF manquait après l'analyse ; la couche texte native a été utilisée pour cette page. L'ordre de lecture des colonnes ou tableaux peut différer ; vérifiez les passages dans le lecteur. |
| `OCR_WORD_LOW_CONFIDENCE` | Mots lus par OCR avec une faible confiance | vérifiez les valeurs dans le lecteur avant de les utiliser. |
| `OCR_CELL_LOW_CONFIDENCE` | Cellules de tableau lues par OCR avec une faible confiance | vérifiez les valeurs dans le lecteur avant de les utiliser. |
| `OCR_PRINTED_CELL_UNRESOLVED` | Cellules de tableau non lues | leur contenu manque dans l'index ; consultez le tableau dans le lecteur. |
| `OCR_NO_RECOGNIZED_CELLS` | Aucun texte reconnu par l'OCR | la zone numérisée n'apporte pas de texte recherchable. |
| `OCR_ORIENTATION_UNRESOLVED` | Orientation OCR non déterminée | la lecture OCR n'a pas été lancée dans les zones dont l'orientation reste indéterminée ; consultez la page originale dans le lecteur. |
| `TABLE_CONTENT_COVERAGE_UNCERTAIN` | Tableaux réduits à leurs intitulés de lignes | l'analyse de mise en page n'a reconnu qu'une colonne d'intitulés à gauche d'un tableau plus large ; les valeurs des autres colonnes peuvent manquer à la recherche et aux citations. Consultez le tableau dans le lecteur. |
| `TABLE_WITHOUT_RELIABLE_CELLS` | Tableaux sans cellules reconnues | l'analyse de mise en page a repéré un tableau sans en reconnaître les cellules ; son contenu peut manquer à la recherche et aux citations. Consultez le tableau dans le lecteur. |
| `OCR_REGION_ISOLATION_LIMIT` | Zones numérisées non isolées | une partie de la page n'a pas été soumise à l'OCR. |
| `ITEM_WITHOUT_PROVENANCE` | Éléments sans provenance vérifiable | leur texte n'est pas disponible pour la recherche et les citations. Consultez la page originale dans le lecteur. |
| `INVALID_SOURCE_CHARSPAN` | Positions de texte incohérentes | certains passages ont été écartés parce que leurs positions dans le texte sont incohérentes ; ils ne sont ni recherchés ni cités. Consultez la page originale dans le lecteur. |
| `PDF_RENDER_LIMIT` | Rendu d'extraction limité | le budget de pixels a limité le rendu et certaines zones n'ont pas été lues. Les recherches utilisent uniquement le texte extrait disponible. Consultez la page originale dans le lecteur. |
| `OCR_RENDER_LIMIT` | Rendu OCR limité | une région dépasse le plafond de pixels réservé à l'OCR ; sa lecture n'a pas été effectuée. Les recherches utilisent uniquement le texte extrait disponible. Consultez la page originale dans le lecteur. |
| `INGESTION_NATIVE_FAULT` | Arrêt du composant d'extraction | cette extraction ne peut pas être publiée ni réutilisée après une erreur native. Consultez le diagnostic du poste pour corriger la cause, puis réindexez le document. |
| `EXTRACTION_QUARANTINED` | Extraction mise en quarantaine | ses preuves sont conservées mais ne peuvent pas être réutilisées après une erreur native. Consultez le diagnostic du poste pour corriger la cause, puis réindexez le document. |
| `GEOMETRY_FRAME_MISMATCH` | Repère de page incohérent | les positions données par l'analyse de mise en page ne correspondent pas aux dimensions de la page ; des passages s'ouvrent sans surlignage précis et une cellule de tableau lue par OCR peut manquer. Vérifiez le passage dans le lecteur. |
| `GEOMETRY_OUTSIDE_PAGE` | Éléments placés hors de la page | des positions données par l'analyse de mise en page sortent du cadre de la page ; ces passages s'ouvrent sans surlignage précis et une cellule de tableau lue par OCR peut manquer. Vérifiez le passage dans le lecteur. |
| `UNKNOWN_COORDINATE_ORIGIN` | Origine des coordonnées inconnue | l'analyse de mise en page n'a pas indiqué comment placer ses éléments sur la page ; des passages s'ouvrent sans surlignage précis et une cellule de tableau lue par OCR peut manquer. Vérifiez le passage dans le lecteur. |
| `PREFLIGHT_TEXT_MAPPING_UNCERTAIN` | Caractères incertains dans le texte intégré au PDF | des mots coupés en fin de ligne ou des caractères non reconnus y ont été repérés ; ces mots peuvent être mal indexés et échapper à la recherche. Vérifiez le passage dans le lecteur. |

La présentation ajoute « page {n} » / « pages {n, …} », puis « et {k} autres » après huit pages. Le suffixe « ({n} zones) » n'est ajouté que si le code apparaît plusieurs fois (`count > 1`) et que ce nombre diffère du nombre de pages distinctes associées (`count !== pages.size`) ; une occurrence par page ne reçoit donc pas ce suffixe. Sans traduction ni message : « Limite signalée par le service, sans description (code {code}). » ; sans code : « Limite signalée par le service, sans description. ». Ces replis remplacent dans le produit le texte historique de la table des modules `lib` ; le code reste visible pour le diagnostic, jamais l'objet brut.

### Familles présentes mais omises de l'inventaire antérieur (IN02–IN06)

| Famille / emplacement | Textes ou conditions courants | Borne |
|---|---|---|
| Suivi, `jobsSummary` | {n} extraction(s) partielle(s) à publier · {n} échec(s) · {n} en cours ou en attente · {n} en pause · {n} annulé(s) · {n} terminé(s) | Résumé ordonné par besoin d'attention ; les libellés ne disent pas que les moteurs sont actifs |
| Suivi, traitement remplacé | remplacé par un traitement plus récent | Pas de décision de publication pour un ancien traitement supplanté |
| Suivi, reprise groupée | Reprendre l'indexation en pause / Reprendre les {n} indexations en pause · Reprise… | Une reprise manuelle explicite ; notice calculée après réponse, inventoriée plus haut |
| Suivi, priorités | Priorité aux questions : les indexations en cours s'arrêtent à leur prochain point de reprise et restent en pause jusqu'à leur reprise. / Priorité aux imports : les nouveaux traitements démarrent ; ceux qui sont en pause se relancent avec « Reprendre les indexations en pause ». | Action de priorité existante, pas reprise implicite des traitements suspendus |
| `documentStatus` | Extraction partielle à publier / Traitement annulé | Publication absente ou annulation ; ne pas traiter ces documents comme indexés |
| `panel-state.ts`, `coverageSentence` | Aucun document dans ce périmètre / Aucun document interrogeable / 1 document interrogeable / {n} documents interrogeables, puis « {n} exclu(s) : {k} en cours de traitement / indexation(s) en pause / extraction(s) partielle(s) à publier / traitement(s) annulé(s) / en erreur / état(s) non reconnu(s) » | Distingue les motifs d'exclusion de recherche de la lecture possible de l'original |
| `ocrPagesSentence` | 1 page lue par OCR / {n} pages lues par OCR | Accords du compteur ; pas preuve d'OCR pour chaque bloc de la page |
| Bibliothèque vide | Importez des fichiers avec « Importer des PDF », tout un dossier avec « Importer un dossier », ou déposez des PDF sur ce panneau depuis votre gestionnaire de fichiers. Les fichiers originaux sont conservés tels quels. | Ajoute le dépôt disponible au texte historique |
| Lecteur / Analyse | Lecture de l'original / Périmètre actif | Les anciens sur-titres « Original et provenance » et « Réponses avec sources » de la table historique ne sont plus affichés |
| Import pendant `cancelling`, `import-outcome.ts` | Avis ordinaire de PDF reçus puis progression de l'extraction/indexation dans le Suivi | Le contrat courant crée une nouvelle entrée en file ; la table du 1er octobre décrivait l'ancien comportement. `paused` reste repris manuellement ; `pausing` attend la pause effective |
| Garde de session, vérification | Atelier documentaire · Ouverture de l'atelier · Vérification de la session… | Pas de confirmation d'ouverture avant la réponse de session |
| Session requise | L'atelier s'ouvre avec un lien à usage unique délivré sur ce poste. {Dans PowerShell sous Windows / Dans un terminal / Dans PowerShell sous Windows ou dans un terminal sous Linux}, depuis le dossier du projet, lancez {la commande ci-dessous / la commande de votre système ci-dessous} : elle ouvre l'atelier dans un nouvel onglet. | Commande propre au poste ; le lien privé n'est pas inventorié |
| Session expirée | La session s'est fermée après une période sans activité ou a atteint sa durée maximale. Rouvrez l'atelier avec {la commande ci-dessous / la commande de votre système ci-dessous} ; documents, index et conversations enregistrés restent intacts. | Aucun transfert ni suppression implicite |
| Session fermée | La session de ce navigateur est fermée. Pour reprendre le travail, rouvrez l'atelier avec {la commande ci-dessous / la commande de votre système ci-dessous}. | Les autres sessions ne sont pas déclarées fermées |
| Lien d'ouverture expiré ou déjà utilisé | Chaque lien d'ouverture ne sert qu'une fois et expire après quelques minutes. Demandez-en un nouveau avec {la commande ci-dessous / la commande de votre système ci-dessous}. | La session et le jeton ne sont pas exposés |
| Réouverture / copie | Copier la commande / Copier la commande Windows / Copier la commande Linux / Commande copiée · Commande copiée dans le presse-papiers. · Si la session a été ouverte dans un autre onglet de ce navigateur, vérifiez de nouveau. · Vérifier de nouveau | Annonce de copie seulement après réussite ; retour d'échec ajouté plus haut |
| `generation.ts`, GPU non encore observé | Génération prévue sur le GPU · Le service a retenu le GPU de ce poste pour le modèle de réponse, qui n'a pas encore été vu chargé ; sa répartition entre GPU et processeur est relevée à chaque question. La recherche et l'import des documents restent calculés sur le processeur. | Choix de mode, pas résidence prouvée |
| idem, résidence indéterminée | Génération prévue sur le GPU · Le service a retenu le GPU de ce poste pour le modèle de réponse, mais la répartition du modèle entre GPU et processeur n'a pas pu être déterminée lors de la dernière vérification. La commande {doctor} donne l'état du GPU dans sa rubrique « calcul ». | Inconnue explicite |
| idem, CPU | Le modèle de réponse est exécuté sur le processeur de ce poste ; la commande {doctor} en donne la raison dans sa rubrique « calcul ». | Le détail accompagne « Réponses calculées sur le processeur » |
| idem, GPU complet | Le modèle de réponse était chargé entièrement sur le GPU de ce poste lors de la dernière vérification, faite avant chaque question et après chaque réponse. La recherche et l'import des documents restent calculés sur le processeur. La commande {doctor} détaille le GPU dans sa rubrique « calcul ». | Dernière observation, pas promesse permanente |
| idem, résidence partielle | Le service a retenu le GPU, mais lors de la dernière vérification le modèle de réponse était chargé à {gpu} % sur le GPU et à {cpu} % sur le processeur, selon la mémoire GPU libre à son chargement. La commande {doctor} détaille cette répartition dans sa rubrique « calcul ». | Répartition annoncée par l'API |
| idem, GPU retenu mais modèle CPU | Le service a retenu le GPU, mais lors de la dernière vérification le modèle de réponse était chargé entièrement sur le processeur. La commande {doctor} en donne la marche à suivre dans sa rubrique « calcul ». | Ne confond pas mode retenu et résidence |
| idem, échec GPU puis repli | Le chargement du modèle de réponse sur le GPU a échoué : l'atelier répond sur le processeur jusqu'à son prochain redémarrage. La commande {doctor} en donne la cause et la marche à suivre pour réessayer le GPU. | Détail et avis de bandeau identiques ; pas de téléchargement ou bascule implicite |
| `context-band.tsx`, explication du mode | Explication du matériel de génération | Bouton qui montre le détail, pas action de configuration |

Les parties entre accolades sont les seules valeurs variables de ces familles. Les commandes suivent la section W018 ; questions, réponses, extraits, titres, noms, chemins et messages fournis par le serveur restent hors réécriture. Les tests unitaires ne qualifient ni le GPU Windows ni ces états dans un corpus réel.

## E03 — aide sur la publication, complément du 3 octobre 2026

Ce complément remplace uniquement l'« avis de publication » historique de la
section Lecteur. Le texte courant reste dans
[`pdf-viewer.tsx`](../src/components/pdf-viewer.tsx), paragraphe `viewer-notice`
sous `!provenanceReady` : les fonctions dépendent de la publication de
l'extraction, pas de la seule fin de l'indexation. L'aide renvoie au Suivi et
précise qu'une extraction partielle peut demander un accord, sans prétendre
que tous les résultats partiels imposent cette décision.

Le contrat de `publication.ts` et `Indexer.publish` est inchangé. La ligne de
texte seule est corrigée ; les conditions de disponibilité des passages,
du sommaire et de l'analyse ne changent pas. Sept tests ciblés et 281 unités
passent, ainsi que le typage, le lint et le build isolé. La recette V5 termine
avec une sortie 0 : notice lisible aux deux tailles 1366×768 et 1920×1080
avant publication ; notice absente et analyse activée dans un troisième
contexte publié. Les trois captures nouvelles ont été examinées par ROOT et
le vérificateur indépendant. Session et API sont doublées dans des contextes
indépendants : ni transition native de publication ni dessin PDF qualifié. Le
[plan canonique](../../../RAG_Local_Agents/PLAN.md) porte l'état de l'action E03,
le journal ses commandes et preuves. Aucun état global R15/D06 n'est clos.

## Limites

- Les recettes historiques ont examiné les largeurs indiquées dans leurs rapports, notamment 1366×768 et 1920×1080. Les autres largeurs et les états non représentés dans ces captures ne sont pas déclarés validés ; longueur des libellés, retours à la ligne et troncatures restent à vérifier sur le build concerné.
- Les messages rédigés par le service (`services/api`) ne sont pas réécrits ici ; plusieurs sont précis (« Référence non retrouvée dans les passages de ce périmètre. »), d'autres restent techniques (« Entrée invalide. »). Leur reprise relève du backend.
- Le libellé « Service local pas encore prêt » ne prétend pas identifier la cause ni garantir une préparation en cours ; les composants concernés restent dans l'info-bulle et le bandeau de contexte.
