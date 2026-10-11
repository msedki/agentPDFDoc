# Sources officielles et traçabilité — V2.1

**Rôle :** registre des sources consultées, versions, apports et limites · **Propriétaire :** traçabilité technique du chantier · **Statut :** Vivant · **Référence :** base publiée `5204d2e` et consultations R26/R27/R28 datées ci-dessous ; historique conservé · **Mis à jour :** 2026-10-11 00:09 (UTC) · **Source de vérité :** ce registre pour les consultations ; publications liées pour les faits externes, code et rapports pour les résultats locaux

## NF09 — diagnostic graphique ciblé du 10 octobre 2026

Sources primaires consultées avant la sonde X11/GTK, sans migration du
poste ni de la pile du projet. La preuve de comportement reste le reçu
local, distinct des contrats documentaires ; [journal](journal/2026-10-10.md#nf09--diagnostic-hôte-et-prérequis-x11-privé--0035-utc).

| ID | Source officielle / version | Apport et limite |
|---|---|---|
| NF09-S01 | [X.Org Xvfb](https://xorg.freedesktop.org/releases/X11R6.8.2/doc/Xvfb.1.html), manuel historique ; binaire local1.20.13 contrôlé | Affichage virtuel et options d'écran ; flags auth/nolisten et extensions vérifiés dans le binaire, capacité GLX établie uniquement par la sonde locale. |
| NF09-S02 | [Mutter/Cogl3.36.9 GLX](https://raw.githubusercontent.com/GNOME/mutter/3.36.9/cogl/cogl/winsys/cogl-winsys-glx.c), [GTK3.24.20 X11 GLContext](https://raw.githubusercontent.com/GNOME/gtk/3.24.20/gdk/x11/gdkglcontext-x11.c) | GLX et configurations de rendu requis, backend exact ; ne prouve pas que tout Shell/session fonctionne sur Xvfb. |
| NF09-S03 | GTK3/3.24 : [realize](https://docs.gtk.org/gdk3/method.GLContext.realize.html), [make_current](https://docs.gtk.org/gdk3/method.GLContext.make_current.html), [get_version](https://docs.gtk.org/gdk3/method.GLContext.get_version.html), disponibles depuis3.16 | Version lue après réalisation et contexte courant réellement établi ; application observée sur GTK3.24.20/GdkX11, aucune règle GTK4 appliquée. |
| NF09-S04 | [Khronos GLX1.4](https://registry.khronos.org/OpenGL/specs/gl/glx1.4.pdf),16/12/2005 §§3.3.1/3.3.7 ; [glGetString, source mainteneur](https://raw.githubusercontent.com/KhronosGroup/OpenGL-Refpages/main/gl4/glGetString.xml) | Version GLX négociée, contexte/display courant et chaînes réelles. Route XHTML échoue à l'outil avec400 content-type ; route brute officielle ouverte. Aucun rendu ni bureau qualifié par une chaîne seule. |
| NF09-S05 | [Mesa, variables](https://docs.mesa3d.org/envvars.html), documentation actuelle ; bibliothèques locales21.2.6 | Rendu logiciel demandé et cache local ; renderer effectivement lu comme llvmpipe dans la sonde. Aucune version GL forcée, erreur désactivée ou qualification CPU16Go extrapolée. |
| NF09-S06 | [GNOME, tests automatisés](https://blogs.gnome.org/shell-dev/2022/12/02/automated-testing-of-gnome-shell/),02/12/2022 | Dépendances d'une session complète et substitutions explicites en CI ; publication plus récente que3.36.9, aucun framework de mocks adopté pour la sonde locale. |
| NF09-S07 | [D-Bus daemon](https://dbus.freedesktop.org/doc/dbus-daemon.1.html), documentation mainteneur actuelle ; [archive officielle1.12.16](https://dbus.freedesktop.org/releases/dbus/dbus-1.12.16.tar.gz), Last-Modified11/06/2019 ; binaire1.12.16 installé | Configuration Unix EXTERNAL sans include/dossier de service. `dbus-sysdeps-unix.c:877/1135/1183–1188` fixe99 octets et refuse un chemin plus long : chemins locaux105/104, premier daemon refusé sur105 ; réussite précédente97. Garde QA108 insuffisante, marge locale90 appliquée aux sondes03–04. GitLab/cgit inaccessibles, archive200 lue sélectivement sans exécution ; signature non vérifiée, SHA et deux sources conservés dans `review/native-final/dbus-socket-primary-source/access-and-hashes.json`. Aucun service système ni session GNOME complète qualifié. |
| NF09-S08 | GNOME Shell3.36.9 : [LoginManager](https://raw.githubusercontent.com/GNOME/gnome-shell/3.36.9/js/misc/loginManager.js), [background](https://raw.githubusercontent.com/GNOME/gnome-shell/3.36.9/js/ui/background.js), [main](https://raw.githubusercontent.com/GNOME/gnome-shell/3.36.9/js/ui/main.js) | Connexion système avant les proxies, démarrage UI et appels automatiques GDM/polkit. LoginManager extrait du binaire installé est byte-identique au tag officiel (`native/gnome-x11-runtime-source/comparison.json`, `012384dc…`). Route web ROOT Cache miss conservée, acquisition directe/lecture indépendante officielle réussie. Bus hôte exclu pour cette QA ; cause g3 non déduite. |
| NF09-S09 | [GLib2.64.6 GDBusProxy](https://raw.githubusercontent.com/GNOME/glib/2.64.6/gio/gdbusproxy.c), [2.64.2](https://raw.githubusercontent.com/GNOME/glib/2.64.2/gio/gdbusproxy.c), [GJS1.64.5 Gio](https://raw.githubusercontent.com/GNOME/gjs/1.64.5/modules/core/overrides/Gio.js) | Proxies sans propriétaire possibles après ServiceUnknown/NameHasNoOwner ; transport joignable ne prouve pas UI fonctionnelle. Les deux fichiers GLib sont identiques (`e576e64b…`). Constantes GI2.64.2 distinctes des exports version de la bibliothèque effectivement chargée2.64.6 ; observation ROOT séparée, aucun comportement GUI extrapolé. |
| NF09-S10 | [GIO bus_get_sync](https://docs.gtk.org/gio/func.bus_get_sync.html), API2.0, documentation bibliothèque2.91.0/since2.26 ; [PyGObject GI](https://pygobject.gnome.org/guide/api/api.html), docs actuelles | API Python `Gio.bus_get_sync(SYSTEM,None)` confrontée à la vraie signature introspectée Python3.8.10/PyGObject3.36.0/GLib chargée2.64.6. `Gio.DBus.system` appartient à GJS, sa transposition au préparateur Python a réellement échoué avant Shell ; erreur commune préparation/relecture conservée. Préfixe import/assertions sans connexion vérifié ; reçu04 séparé confirmant le transport privé réel. Route tutoriel Gio inaccessible, aucune recette hôte ni comportement produit extrapolé. |
| NF09-S11 | GNOME Shell3.36.9 : [layout](https://raw.githubusercontent.com/GNOME/gnome-shell/3.36.9/js/ui/layout.js), [overview](https://raw.githubusercontent.com/GNOME/gnome-shell/3.36.9/js/ui/overview.js), [viewSelector](https://raw.githubusercontent.com/GNOME/gnome-shell/3.36.9/js/ui/viewSelector.js), [shellDBus](https://raw.githubusercontent.com/GNOME/gnome-shell/3.36.9/js/ui/shellDBus.js), [main](https://raw.githubusercontent.com/GNOME/gnome-shell/3.36.9/js/ui/main.js), consultés10/10/2026 | FocusApp/interface ne garantit pas menu peint ; startup/coverPane, grab et animation/page sont des états distincts. layout extrait du GResource réel diffère du tag sur les helpers monitor-index, clauses startup identiques. Avis `frontend/native-final/gnome-review/nf09-overview-startup-source-boundary-20261010.json` (`cafb0ff4…`). PNG réel sans menu et un warning grab non horodaté ; cause inconnue, observations futures non exécutées. Aucun succès atelier ni défaut produit déduit. |
| NF09-S12 | [psutil 7.2.2, exceptions ZombieProcess et NoSuchProcess](https://psutil.readthedocs.io/stable/#psutil.ZombieProcess), mainteneur, consultation du 10/10/2026 UTC ; version locale 7.2.2 et héritage introspectés. Complète R15S23/R15S26/R15S30 ci-dessous. | ZombieProcess hérite de NoSuchProcess : une capture large ne prouve donc pas une absence. Les oracles QA nouveaux doivent conserver présence/inconnue et refuser ZombieProcess/AccessDenied, avec contrôle frais du PID pour une absence. Cette règle motive les contre-témoins d’oracle OwnedTree V2 et du comparateur v3→v4 ; elle ne reconstitue pas l’état des onze Firefox historiques et ne clôt pas NF09. |

Trace ROOT des contrats et limites :
`root/nf09-x11-source-review-20261010.json` sous les preuves R27.
Préparation et résultat local liés dans
`native/xvfb-gtk-prerequisite-final-preparation.json` et la revue terminale
`review/native-final/xvfb-gtk-prerequisite-executed-review.json`.
Ces références n'établissent aucune cause historique de g3 ni de PASS NF09.
La limite « observations futures non exécutées » de NF09-S11 décrit le
diagnostic v2. La recette distincte v3 a ensuite observé startup/coverPane
puis overview/page et capturé le menu réel : gelc9ea94e8, avis UI774839a3,
terminalbbeb128b et contrôle frais7eed3bd9 sous les preuves R27. Ces faits
locaux ne reconstituent pas la cause du grab v2. Le helper privé de
nettoyage accepte les zombies dans `matching()`/`remaining()` ; sans état
live/zombie dans le snapshot v3, ce constat source ne prouve pas la cause
des onze identités restantes. Le rouge initial est conservé, sans nouveau
contrat externe ni modification du comportement livré.

## R28 — sources de l'étude DOCX/XLSX du 9 octobre 2026

Consultation le 09/10/2026 UTC ; [étude](reports/extension-office-2026-10-09.md)
et [PLAN](PLAN.md#r28--étude-de-lextension-docxxlsx-avant-implémentation).
Les publications établissent les contrats externes ; les benchmarks locaux
sous `.runtime/qa/r27-20261009/office-study/` établissent seulement les
comportements mesurés. Aucun résultat PDF publié, source mobile ou roue
disponible n'est converti en preuve d'intégration Office du projet.

| ID | Source officielle / version et date connue | Apport et limite |
|---|---|---|
| R28-S01 | [ECMA-376](https://ecma-international.org/publications-and-standards/standards/ecma-376/), édition5 : partie2 OPC2021, partie1/4 2016, partie3 2015 | Parties/relations et familles OOXML ; page de standard consultée, pas téléchargement/examen intégral de tous ses volumes. Aucun quota métier/RAM déduit du standard. |
| R28-S02 | [Microsoft WordprocessingML](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document), mise à jour12/01/2024 | Parties, paragraphes/runs et stories ; ne garantit pas pagination Word dans notre lecteur. |
| R28-S03 | [python-docx Document](https://python-docx.readthedocs.io/en/latest/api/document.html),1.2.0 ; [source v1.2.0](https://github.com/python-openxml/python-docx/blob/v1.2.0/src/docx/document.py) | API ordre/paragraphes/tables/propriétés/commentaires et omissions révisions/nested ; source téléchargée identique à l'installation. Micro-probe Strict négatif et six ancrages XML exacts locaux, pas un adaptateur complet. |
| R28-S04 | [Docling Word v2.131.0](https://github.com/docling-project/docling/blob/v2.131.0/docling/backend/msword_backend.py), [Excel même tag](https://github.com/docling-project/docling/blob/v2.131.0/docling/backend/msexcel_backend.py), [formats](https://docling-project.github.io/docling/usage/supported_formats/) ; Core2.99.0 installé | Backends exacts égaux à l'installation ; SimplePipeline Office et couvertures/limites confrontées aux sorties réelles. Import PyTorch observé sans modèle, pertes de provenance/littéraux/formules/types. Aucune généralisation de précision à tout corpus. |
| R28-S05 | [openpyxl API](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html), [modes optimisés](https://openpyxl.readthedocs.io/en/stable/optimized.html), [formules](https://openpyxl.readthedocs.io/en/stable/formula.html) : stable3.1.3 ; route `/en/3.1`3.1.4 ; code installé3.1.5 vérifié | read_only/data_only/fermeture, dimensions, tokenizer limité. Tables/fusions et sharedStrings vérifiés dans source3.1.5 ; read_only ne prouve pas RAM constante ni évaluation de formules. Probe cache.cell borné non scalable, cible streaming à qualifier. |
| R28-S06 | [Microsoft SpreadsheetML formules](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/working-with-formulas), mise à jour14/01/2025 | `<f>` formule et `<v>` valeur de dernier calcul distinctes ; refs feuille/classeur/noms. Présence du cache ne garantit ni fraîcheur ni exactitude ; absence conservée dans les probes. |
| R28-S07 | [lxml parsing](https://lxml.de/parsing.html), [defusedxml mainteneur](https://github.com/tiran/defusedxml), [OWASP File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) ; lxml6.1.3/defusedxml0.7.1 réels | Options XML/protection et contrôle upload ; micro-tests installés : entités non expansées ou refus explicite selon parser. Préflight DOCTYPE/entities/ZIP nécessaire ; aucune certification sécurité du produit Office absent. |
| R28-S08 | [Python3.12 zipfile](https://docs.python.org/3.12/library/zipfile.html), [tempfile](https://docs.python.org/3.12/library/tempfile.html) ; documentation3.12.15, CPython3.12.14 exécuté | Tailles/CRC/chemins et handles temporaires Windows ; préflight et cleanup bornés à prévoir. Documentation de famille ne vaut pas recette Windows. |
| R28-S09 | Publications PyPI [python-docx1.2.0](https://pypi.org/project/python-docx/1.2.0/), [openpyxl3.1.5](https://pypi.org/project/openpyxl/3.1.5/), [lxml6.1.3](https://pypi.org/project/lxml/6.1.3/), [defusedxml0.7.1](https://pypi.org/project/defusedxml/0.7.1/), [et-xmlfile2.0.0](https://pypi.org/project/et-xmlfile/2.0.0/), [typing-extensions4.16.0](https://pypi.org/project/typing-extensions/4.16.0/) | Douze roues du verrou confrontées à noms/hashes publiés, inventaire installé et avis. Rectification R28-RT-02 du 10/10/2026 : la sonde historique omettait les noms LICENCE. Textes MIT openpyxl/et-xmlfile et LICENCE.python réellement présents dans le cache livré du kit 22fd828 ; octets, METADATA, RECORD et SHA256SUMS concordants, hashes dans le [rapport Office](reports/office-integration-2026-10-10.md). Aucune installation Windows/x86 ou disponibilité de chaque cache offline prouvée. |
| R28-S10 | [PyPA tags](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/), [PEP600](https://peps.python.org/pep-0600/), [lxml installation](https://lxml.de/installation.html) ; roues CPython3.12 et ELF aarch64 local | manylinux/ABI ; glibc locale du module et minimum de la pile entière distingués. GNU/Linux sous prérequis, pas Linux universel/musl ni dépendance Jetson/GPU introduite par Office. |
| R28-S11 | Mainteneurs [Calamine](https://github.com/tafia/calamine), [Mammoth Python](https://github.com/mwilliamson/python-mammoth), [Mammoth JS](https://github.com/mwilliamson/mammoth.js), [docx-preview](https://github.com/VolodymyrBaydalka/docxjs), [SheetJS cellules](https://docs.sheetjs.com/docs/csf/cell/), [MarkItDown](https://github.com/microsoft/markitdown), [Tika3.2.3 formats](https://tika.apache.org/3.2.3/formats.html) | Comparaison documentaire des représentations, rendu, sécurité, runtime et intégration ; solutions non installées/non benchmarkées ici. Versions mobiles ne sont pas des dépendances retenues ni des gains mesurés. |
| R28-S12 | [LibreOffice paramètres](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html), documentation latest26.8 ; paquets locaux6.4.7 constatés | Headless/conversion et profil utilisateur ; aucun convertisseur exécuté, rendu/calcul/fidélité/offline multihôte NOT_RUN. Dérivé éventuel distinct, pas moteur requis. |
| R28-S13 | [SQLite ALTER TABLE §6/8](https://sqlite.org/lang_altertable.html), [FK](https://sqlite.org/foreignkeys.html), [JSON](https://sqlite.org/json1.html), [query planner](https://sqlite.org/queryplanner.html) ; SQLite3.53.1 exécuté, ALTER COLUMN introduit3.53.0 | Sonde schéma v3 mémoire et DROP NOT NULL réel ; reconstruction portable si version antérieure, FK avant transaction et colonnes explicites. Contrats PK/FK/index sparse proposés, aucune migration persistante. |
| R28-S14 | [Pydantic unions discriminées](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions-with-str-discriminators), [React HTML](https://react.dev/reference/react-dom/components/common#dangerously-setting-the-inner-html) ; Pydantic2.13.5/React19.3.0 installés | Modèles typés et rendu échappé pour locators/source ; une structure d'API ou un composant ne prouve pas provenance, lecteur ou chaîne RAG. |


## R28 — contrats utilisés pour l’implémentation du 10 octobre 2026

Consultés le 10/10/2026 UTC après l’étude ; versions du verrou conservées.
La preuve d’application est dans les tests, la revue et la recette Office,
liés depuis le PLAN. Une publication reste distincte d’une preuve d’exécution.

| ID | Source primaire | Apport et limite |
|---|---|---|
| R28-S15 | [Microsoft ST_Xstring](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/d34ae755-c53f-4a44-a363-c6dd3ee018a4), [CellValue](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.spreadsheet.cellvalue?view=openxml-3.0.1), [Extension](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.spreadsheet.extension?view=openxml-3.0.1) | Contrat OOXML : décodage unique des escapes, paires UTF-16 valides, chaîne vide mise en cache distincte d’un cache absent, extensions explicitement conservées ou signalées. APIs .NET citées pour le schéma, sans nouvelle dépendance .NET ; contre-exemples et reprises dans `xlsx-refine/summary.json`. |
| R28-S16 | [SQLite FTS5, BM25](https://www.sqlite.org/fts5.html#the_bm25_function), [Online Backup API](https://www.sqlite.org/backup.html) | Les statistiques du corpus interviennent dans BM25 : projection FTS5 indépendante du contenu exclu pour une plage stricte. Sauvegarde cohérente d’une base ouverte, y compris WAL, avant migration atomique. Les budgets locaux et preuves de rollback/restauration viennent du code et des tests, jamais de la publication. |
| R28-S17 | [Python3.12 zipfile](https://docs.python.org/3.12/library/zipfile.html), [defusedxml](https://github.com/tiran/defusedxml), [lxml parsing](https://lxml.de/parsing.html) | CRC, membres ZIP, validation XML sans DTD/entités/réseau ; quotas globaux du package et parties validées une seule fois. Versions exécutées conservées : CPython3.12.14, defusedxml0.7.1 et lxml6.1.3. Refus et ressources mesurés dans la suite OPC ; aucune qualification Windows déduite. |
| R28-S18 | [Pillow Image](https://pillow.readthedocs.io/en/stable/reference/Image.html) | Vérification raster et bombes de décompression ; seule une image interne enregistrée, hashée, à MIME et dimensions bornés peut être servie. Documentation stable mobile confrontée aux signatures exécutées et tests, sans mise à jour du paquet ; SVG/HTML/OLE ne sont jamais affichés par cette route. |
| R28-S19 | PSF, Python 3.12 : [Path.mkdir](https://docs.python.org/3.12/library/pathlib.html#pathlib.Path.mkdir), [mkstemp](https://docs.python.org/3.12/library/tempfile.html#tempfile.mkstemp), [os.replace](https://docs.python.org/3.12/library/os.html#os.replace), consultés le 10/10/2026 à 15:16 UTC ; documentation 3.12.15, runtime 3.12.14 | Modes masqués par l’umask, traitement distinct des parents ; création exclusive privée, descripteur non héritable et remplacement atomique sur le même système de fichiers. Le nettoyage incombe à l’appelant. R28-RT-01 crée les nouvelles racines et dossiers de contrôle en 0700, les jetons en 0600, sans chmod global ni changement Windows. Tests sur fichiers POSIX réels et revue indépendante ; la documentation ne prouve pas une recette du kit corrigé. |

| R28-S20 | [SQLite WAL §2/4/5](https://www.sqlite.org/wal.html), [Atomic Commit](https://www.sqlite.org/atomiccommit.html), mainteneur, consultés le 10/10/2026 UTC ; moteur installé réellement observé 3.53.1 | Une transaction WAL n’est publiée qu’avec son marqueur de commit ; le fichier WAL peut persister après un arrêt brutal. Le protocole C02 conserve les fichiers avant reprise et utilise une connexion SQLite normale, sans lecture immutable qui ignorerait le WAL. Le crash synchronisé pendant la transaction doit être observé avant de conclure ; cette source ne constitue ni preuve d’exécution, ni recette de panne électrique ou multihôte. |
| R28-S21 | [CPython 3.12, sqlite3 : gestionnaire de connexion](https://docs.python.org/3.12/library/sqlite3.html#how-to-use-the-connection-context-manager), [contextlib.closing](https://docs.python.org/3.12/library/contextlib.html#contextlib.closing), mainteneur, consultation du 10/10/2026 UTC ; documentation de branche 3.12 affichant 3.12.15, interpréteur exécuté 3.12.14 | Le gestionnaire d’une connexion SQLite règle la transaction mais ne ferme pas la connexion. La fermeture explicite, également en cas d’exception, motive les sept corrections du runner QA C05 et leurs témoins en mémoire. Ce contrat documentaire ne prouve ni ingestion, ni résultat de recette native ; aucun changement du service DB produit n’est déduit. |
| R28-S22 | [Node.js fs 24.16.0](https://nodejs.org/download/release/v24.16.0/docs/api/fs.html#fspromiseswritefilefile-data-options), [flags](https://nodejs.org/download/release/v24.16.0/docs/api/fs.html#file-system-flags), [Playwright APIRequestContext.storageState](https://playwright.dev/docs/api/class-apirequestcontext#api-request-context-storage-state), consultés le 10/10/2026 à 19:44–19:45 UTC ; Node24.16.0/Playwright1.63 exécutés | Sans path, Playwright retourne l'état sans fichier. Node crée par défaut en 0666 masqué par umask ; mode ne corrige pas une cible existante. wx refuse une entrée existante/lien POSIX ; close et temporaire propre restent à gérer. Limites NFS, flags et permissions Windows distinctes. Contrat pour R28-QA-01 : aucune correction source ni qualification déduite de ces documents. |
| R28-S23 | [Qdrant Named Vectors](https://qdrant.tech/documentation/manage-data/vectors/#named-vectors), [Scroll points](https://api.qdrant.tech/api-reference/points/scroll-points), mainteneur, consultés le 10/10/2026 à 20:16 UTC ; documentation courante, runtime verrouillé 1.19.1 | Les vecteurs nommés sont enregistrés sous leurs noms, avec configurations propres ; scroll peut inclure leurs valeurs. Motive la correction de l'oracle QA C10 qui attendait une liste brute. Le nom dense, la dimension 384, l'absence de sparse et les 14 points conservés viennent du code/configuration/réponse réels, pas de cette documentation. Aucune modification de collection ni migration vers un autre schéma n'en découle. |
| R28-S24 | [CPython3.12 `re`](https://docs.python.org/3.12/library/re.html), [Ollama tag0.35.0 Options/DefaultOptions](https://raw.githubusercontent.com/ollama/ollama/v0.35.0/api/types.go), [Modelfile mainteneur](https://docs.ollama.com/modelfile) ; consultation F du10/10/2026, diagnostic `12ce5024`/revue `868d888f` | Regex : frontières/classes applicables à Python3.12.14, documentation mineure3.12 actuelle3.12.15 ; aucune grammaire métier imposée. Génération : tag0.35.0 initialise Seed à−1 ; documentation courante Modelfile présente seed0, distinction conservée. Le gateway envoie temperature0.2/top_p0.9 ; seed effective/modelfile non observée. Paramètres de répétabilité ne prouvent pas une correction du faux refus ni une cause interne. |
| R28-S25 | [Unicode UAX15](https://www.unicode.org/reports/tr15/), §1.2/3 et stabilité, version courante18.0/rev58 du12/08/2026 ; [SQLite FTS5](https://sqlite.org/fts5.html), §4.3.1 unicode61 ; consultation ROOT du10/10/2026 UTC | Environnement du repo mesuré : Python3.12.14, UCD15.0.0, SQLite3.53.1. Définitions/stabilité et prudence NFKC utilisées comme référence, sans attribuer UCD18 au runtime ni réécrire les originaux. unicode61 sépare par défaut la ponctuation ; cette recherche textuelle ne remplace pas le matching exact des codes. Ces publications ne définissent pas la frontière métier entre un mot composé et une référence. |
| R28-S26 | [SQLite Online Backup](https://sqlite.org/backup.html), [format WAL](https://sqlite.org/fileformat2.html#wal_file_format), [PRAGMA wal_checkpoint](https://sqlite.org/pragma.html#pragma_wal_checkpoint), [CPython3.12 Connection.backup](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup), consultés le 10/10/2026 UTC par F et ROOT ; runtime réellement exécuté Python3.12.14/SQLite3.53.1 | Complément de S20 : sauvegarde logique SQLite en ligne, frames et marqueur de commit, checkpoint PASSIVE borné par les lecteurs. Un fichier DB seul ne suffit pas lorsque des commits restent dans le WAL. Motive le témoin C02 distinct validé `b80460f0` ; inventaire binaire et documentation ne remplacent pas la reprise logique exacte. Aucune qualification de panne électrique, de spill non validé, de grosse base ou d’autre plateforme. |
| R28-S27 | [SQLite ORDER BY](https://www.sqlite.org/lang_select.html#the_order_by_clause), [LIMIT](https://www.sqlite.org/lang_select.html#the_limit_clause), [FastAPI Annotated Query](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/), [React useEffect](https://react.dev/reference/react/useEffect) ; consultation F/ROOT du10/10/2026 UTC | C05 : tri total créé/id, pagination paramétrée bornée et nettoyage des requêtes/flux remplacés. Versions exécutées backend Python3.12.14/SQLite3.53.1/FastAPI0.142.1, frontend React19.3.0 verrouillé ; documentation courante confrontée aux signatures et tests locaux, pas une qualification de toutes versions. Sources/détail/SSE existants restent autoritaires ; clé URL opaque, mode historique inconnu et absence de génération à l’ouverture sont des choix du projet, contrôlés sur deux anciennes réponses/quatre citations dans la recette native `cc5384a8` ; [preuves et limites](reports/office-integration-2026-10-10.md#r28-c05-01--restauration-des-questions-enregistrées). Les publications ne prouvent ni le PASS navigateur ni une supériorité SOTA comparative. |

## R27 — sources des corrections du 9 octobre 2026

La baseline du 9 octobre fournit les observations initiales ; les rapports
`.runtime/qa/r27-20261009/` conservent les reproductions et contrôles des
corrections. Les sources ci-dessous établissent les mécanismes, sans certifier
une qualification du RAG ni le support d'une plateforme non exercée.

| ID | Source officielle et version confrontée | Apport et limite |
|---|---|---|
| R27-S01 | [Agent Skills, spécification](https://agentskills.io/specification), consultée le 09/10/2026 | `compatibility` est un champ facultatif de 1 à 500 caractères. Le validateur projet le prend en charge ; le `quick_validate.py` système le refuse avec son ancienne liste de clés. Cet échec d'outil est conservé, sans retirer un champ valide ni modifier l'outil global. La conformité de format ne prouve pas l'invocation native des skills. |
| R27-S02 | [Linux user namespaces](https://man7.org/linux/man-pages/man7/user_namespaces.7.html), [netdevice](https://man7.org/linux/man-pages/man7/netdevice.7.html), [capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html), consultés le 09/10/2026 ; noyau local 5.10.120-tegra | Mapper uniquement l'UID/GID du compte, configurer loopback dans le namespace enfant puis exécuter en UID non nul sans capacités permet une recette hors ligne avec la garde root intacte. Sonde réelle : UID1000, CapEff/Prm/Amb nuls, loopback disponible, réseau externe inaccessible. Aucun changement du réseau hôte. |
| R27-S03 | [OWASP, expiration manuelle des sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#manual-session-expiration), [TanStack Query v5, mutations consécutives](https://tanstack.com/query/latest/docs/framework/react/guides/mutations#consecutive-mutations), [React, réponses dans les effets](https://react.dev/reference/react/useEffect#fetching-data-with-effects), consultés le 09/10/2026 ; Query5.104.0, React19.3.0 installés | Une fermeture doit être confirmée par le serveur ; les callbacks tardifs doivent respecter l'identité de l'opération. Corrections B04/B06 et tests discriminants, sans changement de session backend ni nouvelle couche de state. |
| R27-S04 | [Python3.12, finally](https://docs.python.org/3.12/reference/compound_stmts.html#finally-clause), [notes d'exception](https://docs.python.org/3.12/library/exceptions.html#BaseException.add_note), [disk_usage](https://docs.python.org/3.12/library/shutil.html#shutil.disk_usage), [Path.resolve](https://docs.python.org/3.12/library/pathlib.html#pathlib.Path.resolve), [inspect.isawaitable](https://docs.python.org/3.12/library/inspect.html#inspect.isawaitable), [flock](https://man7.org/linux/man-pages/man2/flock.2.html), consultés le 09/10/2026 ; CPython3.12.14 installé, documentation3.12.15 | Conservation de l'erreur primaire et du diagnostic de reprise, mesure du volume réel de destination, comparaison des chemins physiques, distinction contention/autres errno et attente des callbacks async. Contrats applicables vérifiés par les tests ; aucune recette native déduite des doubles. |
| R27-S05 | [Starlette, limite de corps](https://starlette.dev/middleware/#requestbodylimitmiddleware), [parseur multipart](https://starlette.dev/requests/), [code1.7.0](https://raw.githubusercontent.com/Kludex/starlette/1.7.0/starlette/middleware/body_limit.py), [FastAPI, fonctions utilitaires](https://fastapi.tiangolo.com/async/#other-utility-functions), [Python3.12, to_thread et shield](https://docs.python.org/3.12/library/asyncio-task.html), consultés le 09/10/2026 ; code Starlette1.7 et CPython3.12.14 exécutés | Compter les fragments avant parsing, fermer les spools sur dépassement ; une fonction synchrone appelée depuis async doit être déportée explicitement. Annuler l'attente n'arrête pas son thread : la persistance admise est drainée et le signal d'annulation conservé. Tests ASGI/SQLite et sondes non auteur, sans extrapolation au corpus ou à D07. |
| R27-S06 | [Git, attribut whitespace](https://git-scm.com/docs/gitattributes#_checking_whitespace_errors), [Git, core.whitespace](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corewhitespace), consultés le 09/10/2026 ; Git2.25.1 exécuté | Reconnaître CR comme terminaison des documents historiques/générés CRLF, avec `trailing-space` et `space-before-tab` conservés dans l'attribut Markdown. Témoins Git : ligne CRLF valide acceptée ; espace avant CR, ligne vide finale et espace avant tabulation refusés. Aucun changement de configuration Git global ni conversion d'octets. |
| R27-S07 | [Pydantic2, strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/), [ConfigDict extra](https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.extra), consultés le 09/10/2026 ; Pydantic2.13.5 installé | Schéma commun strict et imbriqué ; clés inconnues et valeurs non finies refusées, relations effectives contrôlées. Sonde installée et 325 tests ciblés/44 chargements positifs établissent le contrat local ; retour du dictionnaire original, pas de model_dump ou défaut inséré. Une documentation de schéma ne prouve pas une recette native. |
| R27-S08 | [Ollama0.35.0 Duration.UnmarshalJSON](https://github.com/ollama/ollama/blob/v0.35.0/api/types.go#L1085), [envconfig.KeepAlive](https://github.com/ollama/ollama/blob/v0.35.0/envconfig/config.go#L118), consultés le 09/10/2026 | Secondes numériques, fractions incluses, admises par le contrat ; variable du superviseur sérialisée en durée Go décimale exacte sans exposant. Sondes rouge/vert de la fonction réelle, profil inchangé ; aucun nouveau modèle ou démarrage Ollama déduit. |
| R27-S09 | [CPython3.12.14, cmdline.rst : -B et PYTHONDONTWRITEBYTECODE](https://github.com/python/cpython/blob/v3.12.14/Doc/using/cmdline.rst), sections Miscellaneous options et Environment variables ; [documentation3.12](https://docs.python.org/3.12/using/cmdline.html#cmdoption-B), affichée3.12.15. Sections lues le09/10/2026 vers21:46–21:51UTC ; interpréteur réel3.12.14 | L’option-B et une variable non vide interdisent les `.pyc` créés par import ; les modes-I/-E ignorent les variables Python. Réglage interne fixe après whitelist, plutôt que confiance dans une variable héritée. La précompilation explicite compileall reste fonctionnelle, vérifiée séparément ; ces contrats ne prouvent pas l’inventaire immuable d’une installation, à rejouer sur kit C. |

## R26-S02 — arbitrages utilisateur sur la fiabilité 2B et D06.5

Réponses de l'utilisateur dans cette session, le 6 octobre 2026 entre 23:15
et 23:25 UTC, après explication des résultats de la campagne 2B DEV et de la
mesure D06.5 : « il faut que les citations soient avec crochets, donc trouver
l'origine et corriger » ; retrait de l'étiquette technique recopiée accepté ;
échec D06.5 conservé en réserve. Ces réponses autorisent une correction de la
présentation des preuves et de la consigne, mesurée sur le jeu DEV ; elles
n'autorisent ni réglage sur le jeu final, ni normalisation des variantes de
citation, ni nouvelle mesure D06.5.

## R26-KIT — kit hors ligne Linux (KIT01 à KIT26)

Consultation du 6 octobre 2026 (UTC) pour R26-KIT-00 et R26-KIT-01, avant la
rédaction du skill [linux-offline-kit](../.agents/skills/linux-offline-kit/SKILL.md).
Ces pages établissent des mécanismes et des contrats de version ; elles ne
prouvent pas qu'un kit fabriqué ici s'installe ailleurs.

| ID | Source officielle | Version | Apport | Limite |
|---|---|---|---|---|
| KIT01 | [uv, cache](https://docs.astral.sh/uv/concepts/cache/) | page courante | cache sur le même volume que l'environnement pour lier au lieu de copier ; usage concurrent sûr | relocalisation et hors ligne non traités |
| KIT02 | [uv, réglages](https://docs.astral.sh/uv/reference/settings/) | page courante | `link-mode` (`clone` par défaut sous Linux), `offline`, désactivation de la configuration | repli sur ext4 non décrit |
| KIT03 | [uv, variables d'environnement](https://docs.astral.sh/uv/reference/environment/) | page courante | `UV_LINK_MODE`, `UV_OFFLINE`, `UV_MANAGED_PYTHON`, `UV_NO_CONFIG` | correction de `sysconfig` non décrite ; effet de `UV_NO_CONFIG` vérifié localement (`uv lock --check --offline` identique) |
| KIT04 | [uv, versions de Python](https://docs.astral.sh/uv/concepts/python-versions/) | page courante | lien de version mineure (lien symbolique sous Unix) | relocalisation non traitée |
| KIT05 | [uv, stockage](https://docs.astral.sh/uv/reference/storage/) | page courante | déplacer un Python géré impose de recréer les environnements | — |
| KIT06 | [uv, synchronisation](https://docs.astral.sh/uv/concepts/projects/sync/) | page du 05/08/2026 | `--locked`, `--no-dev` | hors ligne non décrit |
| KIT07 | [python-build-standalone, particularités](https://gregoryszorc.com/docs/python-build-standalone/main/quirks.html), renvoyé par la documentation d'uv | non datée | chemins de construction figés dans `_sysconfigdata`, corrigés par uv à l'installation | version non indiquée |
| KIT08 | [Python 3.12, venv](https://docs.python.org/3.12/library/venv.html) | 3.12.15 | un environnement virtuel ne se déplace pas : il se recrée | — |
| KIT09 | [Python 3.12, sysconfig](https://docs.python.org/3.12/library/sysconfig.html) et `Lib/sysconfig.py` 3.12.14 livré (l. 650-677) | 3.12.15 / 3.12.14 | `_init_posix` reprend `prefix` du fichier `_sysconfigdata` | relocalisation établie par le code et un essai local, pas par la documentation |
| KIT10 | [Python 3.12, tarfile](https://docs.python.org/3.12/library/tarfile.html) | 3.12.15 | filtre `data` : liens absolus ou sortants, fichiers spéciaux, modes ; format PAX | — |
| KIT11 | [Python 3.12, os](https://docs.python.org/3.12/library/os.html) et [shutil](https://docs.python.org/3.12/library/shutil.html) | 3.12.15 | `symlink`, `readlink`, `copystat`, `rmtree.avoids_symlink_attacks`, `disk_usage` | l'atomicité du remplacement relève de rename(2) |
| KIT12 | [PEP 600](https://peps.python.org/pep-0600/) | Final | `manylinux_X_Y` signifie glibc X.Y ou plus récente | — |
| KIT13 | [binutils : readelf, objdump](https://sourceware.org/binutils/docs/binutils/) et [ld, VERSION](https://sourceware.org/binutils/docs/ld/VERSION.html) | binutils 2.34 sur le poste | lecture des versions de symboles requises, contrôle au chargement | version non indiquée sur les pages |
| KIT14 | [libstdc++, ABI](https://gcc.gnu.org/onlinedocs/libstdc++/manual/abi.html) | page courante | `GLIBCXX_3.4.26` correspond à GCC 9.1.0 | — |
| KIT15 | [ldd(1)](https://man7.org/linux/man-pages/man1/ldd.1.html), [rename(2)](https://man7.org/linux/man-pages/man2/rename.2.html) | man-pages 6.19 | ne pas lancer `ldd` sur un exécutable non vérifié ; remplacement atomique, `EXDEV` | — |
| KIT16 | [Desktop Entry](https://specifications.freedesktop.org/desktop-entry-spec/latest/) et [XDG Base Directory](https://specifications.freedesktop.org/basedir-spec/latest/) | 1.5 / 0.8 | clés requises, citation de `Exec` et `%%`, `XDG_DATA_HOME` | entrée de menu créée seulement sur demande explicite jusqu'à [W047](DECISIONS.md#w047-kit-linux-installé-en-espace-utilisateur-intégré-au-bureau-par-défaut) |
| KIT17 | [Desktop Entry, clés reconnues](https://specifications.freedesktop.org/desktop-entry/latest/recognized-keys.html), [actions supplémentaires](https://specifications.freedesktop.org/desktop-entry/latest/extra-actions.html), [nom de fichier](https://specifications.freedesktop.org/desktop-entry/latest/file-naming.html), [changements de 1.0 à 1.1](https://specifications.freedesktop.org/desktop-entry/latest/apes05.html) | 1.5, consultée le 07/10/2026 | `Icon` en chemin absolu employé tel quel, `TryExec`, `Actions` et groupes `[Desktop Action]`, identifiant d'entrée ; `Actions` existe depuis 1.1, d'où `Version=1.1` | `desktop-file-validate` 0.24 du poste refuse `Version=1.5` (observé le 07/10) |
| KIT18 | [GNOME, intégrer une application](https://developer.gnome.org/documentation/guidelines/maintainer/integrating.html) | page courante, 07/10/2026 | installation par utilisateur sous `$XDG_DATA_HOME/applications`, `desktop-file-validate` dans les tests, icône SVG | affichage sous GNOME 3.36 non observé |
| KIT19 | [XDG Base Directory](https://specifications.freedesktop.org/basedir/latest/) | 0.8, 07/10/2026 | `XDG_DATA_HOME` et `XDG_STATE_HOME` par défaut ; un chemin relatif est invalide et ignoré | aucun dossier de programmes défini : emplacement par défaut interprété (W047) |
| KIT20 | [uv, stockage](https://docs.astral.sh/uv/reference/storage/) | page courante, 07/10/2026 | outils sous `$XDG_DATA_HOME/uv/tools`, exécutables sous `~/.local/bin` : précédent pour un programme par utilisateur | précédent, pas une norme |
| KIT21 | [Python 3.12, argparse](https://docs.python.org/3.12/library/argparse.html), [io.IOBase.isatty](https://docs.python.org/3.12/library/io.html#io.IOBase.isatty), [os.geteuid](https://docs.python.org/3.12/library/os.html#os.geteuid) | 3.12, 07/10/2026 | aides, `epilog`, erreurs d'usage sur stderr avec le code 2 ; détection d'un terminal ; refus en root | — |
| KIT22 | [dpkg-query(1), Ubuntu 20.04](https://manpages.ubuntu.com/manpages/focal/man1/dpkg-query.1.html) | focal, 07/10/2026 | `-S` donne le paquet qui fournit une bibliothèque, nommé dans les refus | paquets relevés sur le poste de fabrication seulement |
| KIT23 | [SQLite, corruption](https://www.sqlite.org/howtocorrupt.html) | page courante, 07/10/2026 | verrous défectueux sur les systèmes de fichiers réseau : données refusées sur un volume réseau | — |
| KIT24 | [Ollama, FAQ](https://docs.ollama.com/faq) | page courante, 07/10/2026 | écoute par défaut sur 127.0.0.1:11434 : ports contrôlés avant écriture et triplet libre proposé | — |
| KIT25 | [Microsoft, comparaison des systèmes de fichiers](https://learn.microsoft.com/en-us/windows/win32/fileio/filesystem-functionality-comparison) | page courante, 07/10/2026 | FAT32 limité à 4 Gio par fichier, ni FAT32 ni exFAT n'ont de liens symboliques : kit à extraire sur un disque Linux local | transport seulement |
| KIT26 | [Python, module site](https://docs.python.org/3.12/library/site.html), [initialisation de sys.path](https://docs.python.org/3.12/library/sys_path_init.html), [options de la ligne de commande](https://docs.python.org/3.12/using/cmdline.html) et [sys.pycache_prefix](https://docs.python.org/3.12/library/sys.html#sys.pycache_prefix) | 3.12, 07/10/2026 | `-S` sans `site` ni fichier `.pth`, `-I` mode isolé, `-B`, `-X pycache_prefix` : ce qui s'exécute avant la vérification ciblée | portée réelle établie par les tests de l'installateur |

## R26-WEB — chargement de PDF.js hors bundle et contrôle de l'export

Consultation du 6 octobre 2026 (UTC) pour R26-UI-01 : cause de la fuite du
chemin du poste dans l'export et choix de correction.

| ID | Source | Version | Apport | Limite |
|---|---|---|---|---|
| WEB01 | [Next.js, chargement différé, commentaires magiques](https://nextjs.org/docs/app/guides/lazy-loading) et documentation Turbopack livrée avec le paquet | Next 16.3.7 | `webpackIgnore: true` laisse l'import tel quel avec webpack comme avec Turbopack | Turbopack (`next dev`) non essayé |
| WEB02 | `next/dist/compiled/webpack/bundle5.js` (`ImportMetaPlugin`, schéma `importMeta`) | webpack 5.98.0 livré par Next | preuve de la substitution `import.meta.url` → URL `file://` du poste ; `importMeta` booléen seulement | code minifié |
| WEB03 | [webpack, variables de module](https://webpack.js.org/api/module-variables/), [configuration de module](https://webpack.js.org/configuration/module/), [méthodes de module](https://webpack.js.org/api/module-methods/) | documentation courante | `import.meta.url` rend l'URL `file:` absolue du module ; `importMeta: false` ; `webpackIgnore` | décrit la dernière version, forme objet de `importMeta` à partir de 5.109.0 seulement |
| WEB04 | `pdfjs-dist` `build/pdf.mjs` (l. 9685-9699) et `package.json` | 6.3.289 | `createRequire(import.meta.url)` réservé à Node ; point d'entrée `build/pdf.mjs` | — |
| WEB05 | [PDF.js, exemple helloworld](https://github.com/mozilla/pdf.js/blob/master/examples/learning/helloworld.html) | branche master | chargement de `pdf.mjs` en module et réglage de `workerSrc` | branche master, pas le tag 6.3.289 |

## R26-S01 — demande et arbitrages utilisateur

Source primaire : demandes utilisateur de cette session, reçues le 6 octobre
2026 vers 17:48 et 18:20 UTC, et réponses aux questions d'arbitrage de 19:20
à 19:50 UTC. Elles autorisent la reprise de W038 limitée aux réserves Linux
et à la distribution interne Linux, la campagne 2B sur le jeu DEV, l'arrêt
coopératif de l'instance principale pendant les recettes et la méthode
Playwright du point (15). L'utilisateur juge excessive une mesure D06.5 de
trois à cinq heures. Ces réponses n'autorisent ni R19, ni purge, ni
apprentissage, ni réglage sur le jeu final. [Décision W040](DECISIONS.md#w040-reprise-r26--réserves-linux-et-distribution-interne-linux).

## W039-S01 — plafond Ollama et correctif autorisé

Consultation du 6 octobre 2026 (UTC), diagnostic puis correctif R25-LEN-01 :
[Modelfile, paramètres officiels Ollama](https://docs.ollama.com/modelfile#valid-parameters-and-values),
[API chat officielle](https://docs.ollama.com/api/chat) et
[types API du tag installé v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/api/types.go).
`num_predict` borne le nombre de tokens générés ; `/api/chat` expose la
raison de fin, les tokens d'entrée et ceux de sortie. Le code versionné
confirme ces champs. Ces sources établissent le contrat, pas la qualité
ou les performances de nos réponses. Aucune option illimitée retenue.

Source locale : `config/local16.yaml`, `config/local16-4b.yaml`,
`ContextBuilder.build`, `OllamaGateway.chat_options`, `QueryService.run`
et `analysis-panel.tsx`, base `497d901` et modifications locales datées.
L'utilisateur autorise le correctif proposé 768/1 536 tokens avec réserve
cohérente et avertissement unique, dans le respect de CLAUDE.md et des skills.
La [décision W039](DECISIONS.md#w039-plafonds-de-réponse-et-avertissement-de-longueur)
ne reprend pas la qualification intégrale mise en attente par W038.

## W038-S01 — arbitrage utilisateur de livraison

Source primaire : demande utilisateur de cette session, consignée le
2026-10-06 09:36 UTC. Choix explicite : livraison locale Linux avec réserves et
mise en attente de la qualification intégrale, à documenter. Cette source
autorise l'arbitrage de livraison, pas un PASS technique ni la suppression
d'une preuve ou de données. [Décision W038](DECISIONS.md#w038-livraison-locale-linux-avec-réserves-et-qualification-intégrale-en-attente).

Références locales relues sur la base `5fb5dc8` :
[DoD, règles et qualifications](DEFINITION_OF_DONE.md), W032/W036/W037,
`config/local16.yaml` et `config/models.lock.json` (défaut 2B/Q8_0),
journal du 6 octobre (refus OCR P02/2B, Q10 et précondition Granite).
Les trois SHA des sources Q10 sont identiques à ceux du lot publié ;
aucun nouveau résultat applicatif n'est ajouté. Ces documents relient
les preuves antérieures, ils ne remplacent pas les rapports d'exécution.
Pas de recherche externe : aucun contrat logiciel, modèle ou méthode
technique changé. La [synthèse de livraison](reports/livraison-locale-linux-2026-10-06.md)
est un état daté avec réserves, pas le rapport final V2.1.

## R23OCR-S11 — discriminant de segmentation par lignes

Consultation ROOT le 6 octobre 2026 à 05:23 puis 05:29 UTC, avant tout
nouvel OCR. [ImproveQuality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html),
sections Page segmentation method et Borders : le mode dépend de la forme
de la région ; une petite bordure peut être utile. Documentation courante,
date de publication non indiquée. Au tag Tesseract 5.4.0 utilisé ici,
[`publictypes.h`, `PageSegMode`](https://raw.githubusercontent.com/tesseract-ocr/tesseract/5.4.0/include/tesseract/publictypes.h)
définit le mode 13 comme reconnaissance d'une ligne sans certaines
heuristiques spécifiques. Cela établit le contrat, pas un gain de fidélité.

Hypothèse distincte formulée avant exécution : reconnaître les vrais groupes TSV d'une
seule région narrative P02, à densité native, mêmes poids/langues/seuils,
avec une bordure de dix pixels et PSM13. Le choix des groupes ne dépend
ni d'une valeur attendue ni de la confiance. Ce n'est pas le retry actuel,
qui conserve les cellules admissibles. Le raster doit d'abord correspondre
exactement à celui de l'extraction conservée ; les lignes du pilote isolé
ne peuvent le remplacer. L'essai du 6 octobre à 05:44 UTC refuse cette
méthode comme correction dans ce périmètre ; aucun pipeline ou modèle
nominal modifié. Le [journal de l'essai](journal/2026-10-06.md#r23-ocr-01--discriminant-des-lignes-réelles)
porte les résultats locaux, que les sources officielles ne préjugent pas.

## R15-Q10-S01 — couverture du texte complet d'une citation

Consultation ROOT du 6 octobre 2026, 05:57–05:59 UTC : CSSWG/W3C,
[CSSOM View §9, Range.getClientRects](https://drafts.csswg.org/cssom-view/#dom-range-getclientrects),
Editor's Draft du 12 juillet 2026. Les rectangles concernent le texte
sélectionné, avec transformations ; ils ne prouvent pas sa peinture.
[Playwright, environnements d'évaluation](https://playwright.dev/docs/evaluating#different-environments)
impose de passer les arguments au navigateur, sans fermeture sur les imports
du test ; contrat confronté aux types installés de Playwright 1.63.0.
[MDN, Range.getClientRects](https://developer.mozilla.org/en-US/docs/Web/API/Range/getClientRects)
(page du 7 mars 2024), corrobore ce mécanisme.
Dans PDF.js 6.3.289 installé, `TextLayer.#appendText` ajoute les spans réels
et un BR pour `hasEOL` ; ne pas inférer les sauts de ligne des bboxes.

Méthode de contrôle Q10 : réconcilier le texte complet de chaque région
avec la TextLayer native, normaliser seulement les blancs, refuser
ambiguïté ou contenu manquant et mesurer tous les fragments par Range.
Comparer aux overlays réellement affichés ; conserver séparément l'encre
du canvas original et les captures. Aucun taux du corpus global déduit
d'un seul PDF ni de citations répétées. Essai local effectué sans changement
produit ; [résultats et limites](journal/2026-10-06.md#r15-3-q10--couverture-des-passages-entiers),
distincts des contrats documentés par les éditeurs.

## R15-F05-S01 — stabilité du défilement PDF virtualisé

Consultations du 6 octobre 2026 à 04:03–04:05 UTC, avant validation du
correctif : [React 19.3, useLayoutEffect](https://react.dev/reference/react/useLayoutEffect),
[CSSWG, Scroll Anchoring §2.1 et §3](https://drafts.csswg.org/css-scroll-anchoring/#exclusion-api)
(Editor's Draft du 30/09/2026) et
[CSSOM View, défilement instantané](https://drafts.csswg.org/cssom-view/#scrolling)
(Editor's Draft du 12/07/2026). React installé : 19.3.0, inchangé.
Apport : synchronisation de la géométrie après commit avant peinture ;
exclusion de l'ancrage implicite sur le seul scroller dont l'application
compense les offsets. `instant` est déjà utilisé par le lecteur.
Référence locale du correctif : [pdf-navigation.ts](../apps/web/src/lib/pdf-navigation.ts)
et [pdf-viewer.tsx](../apps/web/src/components/pdf-viewer.tsx), base `133c259`
et modifications F05 datées du 06/10/2026. Viewport périmé exclu ; mêmes
dimensions provisoires pour les slots et offsets, puis viewport PDF.js
réel. Le test de clamp utilise les dimensions observées du second essai.
Limites : les drafts sont des travaux en cours, pas une qualification
des navigateurs ; ni ces textes ni les unités ne démontrent la chronologie
du premier échec. La validation réelle est portée par le
[journal F05](journal/2026-10-06.md#r15-3-f05--citation-page-14-déviée-vers-la-page-13).

## R23S04 — consigne et témoin éditorial 2B

Consultation locale du 6 octobre 2026, 03:28 UTC :
[context.py](../services/api/context.py), consigne publiée sur `ab6e0cc`
restaurée, SHA `24db2d77…`, et [ollama.py](../services/api/ollama.py),
options et contrôle d'identité inchangés. Question et quatre objets de
preuve du rapport historique `69c56b3f…`, jamais reconstruits ou retirés.
Le rapport natif `d761333a…` conserve la consigne candidate effectivement
essayée ; celle-ci n'est pas livrée. Apport : distinguer validation technique
et appui factuel d'une citation. Limite : un chat GPU, sans retrieval/E2E,
mesure de performance ou taux d'abstention ; aucun recours externe.
[Exécution et refus](journal/2026-10-06.md#r23--correction-ciblée-du-jugement-2b).

## R23S03 — référence locale de la calibration CPU 2B

Consultation du 6 octobre 2026, 03:03 UTC :
[calibration.py](../services/runtime/calibration.py), source inchangée à
la base `0fd0f17`, SHA `d2d40531…`. Le rapport natif fermé, son profil
initial et la revue indépendante sont identifiés au
[journal de la mesure CPU](journal/2026-10-06.md#r23--mesure-cpu-2b-bornée-admission-du-6-octobre-à-0253-utc).
Apport : mesure locale utilisée par W036, pas une estimation depuis la taille
du modèle. Limite : CPU Linux aarch64, pilote court ; aucune qualification
D07, Windows, GPU, croissance chaude exacte ou qualité de réponse.
Le [profil livré](../config/local16.yaml) est la source de vérité du paramètre
corrigé ; le rapport conserve le profil antérieur utilisé pour mesurer.

## Q07 — sélection OCR par le navigateur

Consultation du 5 octobre 2026 à 22:40 UTC : mainteneur Playwright,
[Mouse](https://playwright.dev/docs/api/class-mouse) et
[Locator.click](https://playwright.dev/docs/api/class-locator#locator-click).
La souris travaille en pixels CSS du viewport principal ; `down`, `move`
et `up` produisent les événements de souris, `clickCount` compte les clics.
Contrats confrontés aux types locaux Playwright 1.63.0. Ces actions ne
garantissent pas une sélection correcte : il faut lire la vraie sélection,
vérifier sa correspondance aux blocs OCR et l'aller-retour par l'API.
La géométrie vient des blocs extraits et du DOM rendu, jamais d'un texte
injecté ou d'une réponse interceptée. Ces sources ne prouvent ni extraction,
sélection native réussie ni critère DoD ; les essais restent séparés.

## D06.9 — coupure réseau et observation du flux réel

Consultations intégrateur du 5 octobre 2026, avant le relevé de 21:52 UTC : mainteneurs
Playwright, [BrowserContext.setOffline](https://playwright.dev/docs/api/class-browsercontext#browser-context-set-offline)
et [newCDPSession](https://playwright.dev/docs/api/class-browsercontext#browser-context-new-cdp-session) ;
Chrome DevTools, [Network.eventSourceMessageReceived](https://chromedevtools.github.io/devtools-protocol/tot/Network/#event-eventSourceMessageReceived)
et [schéma du mainteneur](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/json/browser_protocol.json) ;
WHATWG, [HTML — reconnexion et Last-Event-ID](https://html.spec.whatwg.org/multipage/server-sent-events.html#processing-model).

`setOffline` émule une indisponibilité réseau du contexte navigateur ; CDP
est limité à Chromium. L'événement observé fournit l'identité de requête,
le type, l'identifiant et le contenu du message reçu. Contrats confrontés
aux types réellement installés de Playwright 1.63.0, sans mise à jour.
Les pages et la branche `master` sont courantes, non des artefacts verrouillés.
La reprise automatique d'EventSource utilise `Last-Event-ID` ; le paramètre
`after` du bouton applicatif relève de `src/lib/stream.ts` et
`services/api/main.py:581–610`, relus séparément. Observer les vrais messages
ne prouve pas leur affichage : la recette doit contrôler le texte pendant
génération, la reprise sans second POST et l'annulation réelle. Aucun PASS
natif ni critère DoD déduit de ces références.

Complément consulté à 21:59 UTC : [CDP Page.stopLoading](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-stopLoading),
schéma officiel ci-dessus et types installés `protocol.d.ts:16268–16273`.
La commande arrête les navigations et chargements de ressources en cours.
Hypothèse ciblée après l'essai rouge : interrompre ainsi le vrai chargement
SSE, puis conserver le mode hors ligne jusqu'au bouton de reconnexion.
Le standard ne garantit pas le comportement observé d'EventSource après
cette commande : un nouvel essai reste nécessaire. La première recette a
reçu 252 deltas pendant `setOffline(true)` ; ce réglage seul n'a pas coupé
la connexion ouverte sur ce navigateur. Ce constat n'est ni un défaut
produit ni une propriété générale de toutes les versions de Chromium.

Complément Qdrant du 5 octobre à 22:14 UTC : mainteneur,
[liste des collections, API v1.19.x](https://api.qdrant.tech/api-reference/collections/get-collections).
`GET /collections` renvoie `result.collections[].name` ; `QdrantStore.request`
retourne ici le contenu de `result`. Version native 1.19.1, aucune migration.
Le résultat de la liste permet de distinguer absence confirmée et erreur
de lecture des détails ; une présence listée ne suffit pas à qualifier
l'accès aux détails. Correction envisagée : une seule nouvelle lecture
des détails si la liste confirme la collection, sinon conserver le blocage
réel et son motif. Cette référence ne démontre pas la cause transport du
premier échec de lecture ; ni suppression d'index ni reprise native acquise.

## Q05 — état de session Playwright isolé

Consultation du 5 octobre 2026 à 21:13 UTC : mainteneurs Playwright,
[authentification](https://playwright.dev/docs/auth) et
[BrowserContext.storageState](https://playwright.dev/docs/api/class-browsercontext#browser-context-storage-state).
Ces pages courantes non versionnées décrivent un état sauvegardé dans un fichier
et réutilisé par la configuration du navigateur ; ce fichier contient des
informations d'authentification et ne doit pas être publié. Contrat confronté
aux types installés de Playwright 1.63.0. Le résolveur local conserve le chemin
historique par défaut et permet un fichier privé propre à chaque recette.
La consultation ne prouve ni ouverture de session ni parcours réel ;
[exécutions et limites](journal/2026-10-05.md#q05--oracle-de-peinture-et-recette-canonique-isolée).

Complément du même jour à 21:32 UTC : CSSWG/W3C,
[CSSOM View, Range.getBoundingClientRect](https://drafts.csswg.org/cssom-view/#dom-range-getboundingclientrect)
et [Element.scrollBy](https://drafts.csswg.org/cssom-view/#dom-element-scrollby),
Editor's Draft affiché du 12 juillet 2026. Les rectangles d'un Range portent
sur le texte sélectionné, avec transformations, et sont des instantanés ;
le cadrage mesure donc le seul repère puis remesure après le défilement.
Ni visibilité d'encre ni absence d'occlusion ne découle de ces coordonnées :
les pixels et la capture réelle restent des preuves distinctes. Accès DOM
WHATWG refusé par l'outil ; aucune lecture réussie de cette page revendiquée.

## R23OCR-S09 — entrées et mesures du pilote LSTM

### Taux réinitialisé après remap — 6 octobre 2026

Consultation du 6 octobre, 01:32–01:38 UTC, version 5.4.0 à la même
révision immuable que ci-dessous. ROOT et relecteur ont vérifié les sources
officielles locales verrouillées, sans nouveau modèle ou apprentissage.

- [lstmtraining.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/lstmtraining.cpp), défaut ligne 39 et chargement/reset lignes 152–182 : défaut 0,001 ; le reset s'applique après continuation/remap. Un checkpoint existant est prioritaire et contournerait ce bloc ; le préfixe doit être neuf.
- [lstmrecognizer.h](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/lstm/lstmrecognizer.h), lignes 161–168, et [plumbing.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/lstm/plumbing.cpp), lignes 240–250 : `SetLearningRate` remplace aussi les taux par couche, consommés par `Update`. Le mode 192 est hérité du réseau dans cette continuation, pas réappliqué par le flag `net_mode`.

Lecture en ligne de `lstmtraining.cpp` réussie ; ouverture de l'en-tête
refusée par l'outil (`Cache miss`). Son contrat est établi sur la source
officielle locale épinglée, pas sur une lecture Web réussie prétendue.
Ces sources justifient l'essai du taux 0,001 ; elles ne démontrent pas,
à elles seules, son efficacité sur le pilote ou l'ingestion PDF.
Il affecte aussi les anciennes classes : les critères de non-régression
restent indispensables. [Choix borné](DECISIONS.md#essai-du-taux-mainteneur--6-octobre-2026).

### Diagnostic des signes sans dictionnaire — 6 octobre 2026

Sources officielles 5.4.0, révision
`1be261dc226d49bdcad0ab2fcb10f8395edc1225`, confrontées aux fichiers
locaux verrouillés avant le témoin. Deux relectures indépendantes et ROOT ;
pas de nouvelle méthode d'apprentissage ou de paramètre adopté.

| Source mainteneur | Contrat utile | Limite |
| --- | --- | --- |
| [lstmeval.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/lstmeval.cpp), lignes 43–69, et [lstmtester.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/unicharset/lstmtester.cpp), lignes 83–128 | Un modèle de reconnaissance et une liste LSTMF suffisent. `RunEvalSync` calcule les sorties et imprime les paires Truth/OCR à verbosité 2. | EXIT0 seul est insuffisant : `Deserialize failed` peut être renvoyé comme texte. Exiger les deux paires attendues et le résumé ; les entrées non encodables peuvent prolonger la boucle, d'où une deadline externe. |
| [lstmrecognizer.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/lstm/lstmrecognizer.cpp), lignes 55–65 et 530–536, avec `lstmtester.cpp` ci-dessus | Le reconnaisseur neuf conserve `dict_ = nullptr` ; ce chemin n'appelle pas `LoadDictionary`. Il décode donc sans DAWG. | Une différence avec l'OCR CLI ne prouverait pas une causalité lexicale exclusive : la préparation des lignes diffère aussi. |
| [lstmtrainer.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/unicharset/lstmtrainer.cpp), lignes 882–917, et [weightmatrix.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/lstm/weightmatrix.cpp), lignes 146–173 | L'évaluation fait un forward et prépare des erreurs en mémoire, sans `Backward`/`Update`. Les sorties nouvelles du remap sont initialisées à partir de la moyenne des poids anciens. | Ajouter les tokens ne leur transmet pas une reconnaissance préapprise. Le compteur learning mesure des mises à jour, pas le succès de chaque signe ; augmenter les itérations ne constitue pas une correction démontrée. |

La documentation [Training Tesseract 5](https://tesseract-ocr.github.io/tessdoc/tess5/TrainingTesseract-5.html)
confirme la distinction entre extension d'alphabet et apprentissage.
Le tutoriel historique 4.00, désormais déprécié pour Tesseract 5, n'est
pas repris comme procédure ni comme prescription d'un nombre d'itérations.
Le témoin utilise uniquement deux variantes heldout du pilote W035 ;
aucun jeu DEV/final RAG, aucun corpus privé. [Décision bornée](DECISIONS.md#diagnostic-sur-deux-lignes--6-octobre-2026).

### Diagnostic CLI et ordre des exemples — 5 octobre, 23:55 UTC

Après le passage fermé, lecture non-auteur puis ROOT des sources officielles
5.4.0 déjà provisionnées dans la QA d'outillage, révision
`1be261dc226d49bdcad0ab2fcb10f8395edc1225`. Aucun téléchargement, patch des
sources mainteneur, apprentissage ou rejeu natif pour cette lecture.

| Source mainteneur | Contrat vérifié | Apport et limite |
|---|---|---|
| [commandlineflags.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/common/commandlineflags.cpp), `ParseCommandLineFlags`, lignes 168–185 et 279–302 ; SHA-256 local `e514dc6a88d52eaab5ad9fc51e3b49718ca990f5cd87b6c632e8be5c9884d249` | Booléens sans valeur séparée : flag seul ou `=true`/`=false` ; le premier argument non-option termine le parsing | Explique pourquoi `true` séparé interrompt la commande avant les réglages suivants. Pas de garantie sur une commande encore non corrigée. |
| [lstmtraining.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/lstmtraining.cpp), défauts, reset, cache, boucle et export ; SHA-256 local `fac1b0572b23d20c234ce6ee6dcdefef6d04ffd7854e66d2ed0b62f96f9571e2` | Taux par défaut 0,001, cible 0,01, cache 6 000 Mio ; arrêt lorsque l'erreur TRAIN n'est plus supérieure à la cible | Le paramètre demandé n'est pas une preuve de son application. À erreur nulle, la cible demandée 0 arrêterait aussi ; corriger les flags seuls ne couvre pas l'ordre des familles. |
| [imagedata.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/ccstruct/imagedata.cpp), `LoadDocuments` et `GetPageRoundRobin` ; SHA-256 local `7a38cfba4560f0d8e932bc4a8c78d0b64e7a5f6fab46ee77b4dd61c99992a811`, avec [lstmtrainer.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/unicharset/lstmtrainer.cpp) et `TrainOnLine` du header associé | Chargement dans l'ordre de la liste, sélection par numéro d'échantillon modulo le nombre de documents ; compteurs remis à zéro | Une liste regroupée par famille n'expose pas les signes dans son préfixe. Le préchargement du cache ne prouve pas leur soumission à l'apprentissage. |

Métadonnées fermées confrontées à ce chemin : 1 600 entrées, liste
SHA-256 `eca7f02165f65d3d0622d174dbdd3fbabea755f6e43f63acb08ab191a5401c00`,
manifeste LSTMF `7d1d7fefc23229260c920816a5ffc9316f122c51e7ab42e828872b2aeaec2baa`.
Les 100 premières entrées sont françaises sans les signes ; premier signe
à l'entrée 321 et première famille produit à 641. Le compteur terminal
`0/100/100` et l'absence de skip bornent les exemples effectivement soumis,
pas les fichiers préchargés. Le compteur learning nul ne constitue pas une
preuve d'identité bit à bit de tous les poids.

Rectification du relevé antérieur de cache : « défaut remplacé explicitement »
décrivait le réglage écrit. Dans ce passage, l'interruption du parser le
laisse au défaut ; aucune consommation de 6 000 Mio n'est déduite.
Résultat, arrêt et preuves : [journal](journal/2026-10-05.md#fermeture-en-échec-et-diagnostic).
Correction nécessaire : [W035](DECISIONS.md#admission-du-passage-unique--5-octobre-2334-utc),
sans seuil abaissé, volume augmenté ou nouveau candidat qualifié.

Complément du 6 octobre, 00:17 UTC : mêmes sources locales épinglées,
`commandlineflags.cpp`, lignes 129–166 et 191–197, et `lstmtraining.cpp`,
lignes 78–105. L'aide imprime les valeurs courantes des flags puis termine
le processus ; malgré le libellé « default », les valeurs reflètent les
arguments déjà parsés. Une sortie modèle vide est refusée avant le test
d'écriture et le chargement du réseau. Ces contrats permettent un témoin
de parsing borné, pas une preuve d'apprentissage ou d'export.

Complément du 5 octobre 2026 à 19:48 UTC, avant la correction de rendu :
PSF, [queue](https://docs.python.org/3.12/library/queue.html) et
[threading](https://docs.python.org/3.12/library/threading.html), documentation
3.12.15 ; contrat de l'interpréteur local 3.12.14 confronté à
[queue.py](https://raw.githubusercontent.com/python/cpython/v3.12.14/Lib/queue.py)
(`put`, `get`, `join`) et
[threading.py](https://raw.githubusercontent.com/python/cpython/v3.12.14/Lib/threading.py)
(`Event`, `Thread.join`, `is_alive`, `daemon`). La borne `Queue.maxsize`
porte sur les éléments en file, pas sur ceux déjà pris par un travailleur.
La limite de deux lignes admises non terminées doit donc être contrôlée
séparément. `qsize`, `empty` et `full` ne sont pas des garanties de sécurité ;
`Queue.join` n'a pas de délai. Les attentes sont bornées par la deadline
existante, sans renouvellement. Après une jointure bornée, vérifier
`is_alive` ; un thread encore actif interdit toute réussite et tout BOX.
Un événement d'arrêt ne force pas l'interruption d'une opération active.

Le GIL ne permet pas de présumer un gain de calcul Python ; la concurrence
proposée vise les attentes de publication observées, sans attribuer leur
cause au matériel. Deux threads non-daemon, un collecteur canonique et
la fermeture avant le traitement natif doivent être testés et relus.
Aucune suppression de synchronisation, mise à jour de runtime ou
accélération acquise par ces contrats. Choix préparatoire :
[W035](DECISIONS.md#correction-préparatoire-du-rendu--choix-du-5-octobre-1948-utc) ;
preuves et exécution éventuelle restent dans le journal.

Complément du 5 octobre 2026 à 18:45 UTC, avant le diagnostic du rendu :
contrats précédents relus dans les publications officielles de la PSF et
des mainteneurs Pillow. La documentation
[time, Python 3.12](https://docs.python.org/3.12/library/time.html), courante
3.12.15, distingue durée monotone écoulée et temps CPU ; deux lectures
de `monotonic_ns` bornent un intervalle, sans en attribuer les attentes
à un composant matériel. Interpréteur local confirmé : 3.12.14.
[ImageFont](https://pillow.readthedocs.io/en/stable/reference/ImageFont.html),
documentation 12.3.0, et
[ImageFont.py au tag 12.3.0](https://raw.githubusercontent.com/python-pillow/Pillow/12.3.0/src/PIL/ImageFont.py),
sections `truetype` et `set_variation_by_axes`, confirment la création de
l'objet de fonte depuis un flux binaire et le réglage des axes. Version
locale confirmée par les métadonnées installées : 12.3.0, sans ouvrir de fonte.
Le témoin conserve BASIC, fonte, axes et appels existants ; il ajoute des
sondes, pas un cache. Leur surcoût reste dans les mesures. Les publications
ne prouvent ni le coût dominant, ni un gain, ni l'achèvement des 2 000
variantes. [Protocole et état d'exécution](journal/2026-10-05.md#r23-ocr-03--diagnostic-du-rendu-et-de-sa-publication).

Complément du 5 octobre 2026 à 16:41 UTC : contrats examinés avant une
correction de préparation, pas une performance acquise. PSF,
[concurrent.futures](https://docs.python.org/3.12/library/concurrent.futures.html),
[threading](https://docs.python.org/3.12/library/threading.html) et
[subprocess](https://docs.python.org/3.12/library/subprocess.html), documentation
courante 3.12.15 ; contrat de l'interpréteur installé 3.12.14 confronté au
code officiel [thread.py](https://raw.githubusercontent.com/python/cpython/v3.12.14/Lib/concurrent/futures/thread.py)
(`_python_exit`, `shutdown`) et
[threading.py](https://raw.githubusercontent.com/python/cpython/v3.12.14/Lib/threading.py)
(`Thread.join`). `shutdown(wait=False)` ne supprime pas l'attente des threads
à la sortie de l'interpréteur ; annuler les tâches en attente n'arrête pas
les tâches déjà actives. Un `join` borné doit être suivi d'`is_alive`.
Les threads daemon ne garantissent pas la fermeture des ressources ;
`preexec_fn` est exclu en présence de threads.

Projet Linux man-pages 6.19,
[PR_SET_PDEATHSIG, Description et Caveats](https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html),
relu le même jour : le parent concerné est le thread créateur du processus,
pas l'ensemble du processus Python. Il doit donc rester vivant tant que
son enfant n'est pas récolté. Ces contrats imposent une revue du cycle de
vie, de l'état partagé et de l'arrêt avant toute concurrence native.
Aucune mise à jour de Python, suppression de synchronisation ou autorisation
d'adoption OCR n'en découle. Hypothèse locale et essais, lorsqu'exécutés,
restent dans le journal ; les publications ne prouvent pas un gain sur ce poste.

Complément du 5 octobre 2026 à 15:40 UTC : PSF,
[IOBase.close, fileno et flush](https://docs.python.org/3.12/library/io.html#io.IOBase.close)
et [BufferedWriter](https://docs.python.org/3.12/library/io.html#io.BufferedWriter),
documentation courante 3.12.15, interpréteur local inchangé 3.12.14.
`flush` vide le tampon Python ; `close` vide puis ferme le flux. Le contrat
[os.fsync](https://docs.python.org/3.12/library/os.html#os.fsync), déjà enregistré
ci-dessous, reste distinct : sur Unix, synchronisation du descripteur après
vidage du tampon. L'instrumentation suivante conserve ces appels et leur
ordre, y compris pour un journal vide. Elle mesure la durée écoulée de chaque
appel Python, pas un temps disque pur ni une consommation CPU. Aucune
suppression, substitution ou mise à jour de runtime n'en découle ; protocole
local dans le [journal](journal/2026-10-05.md#r23-ocr-03--décomposition-de-la-fermeture-des-journaux).
Relevé local exécuté à 16:09 UTC, [résultat et limites](journal/2026-10-05.md#témoin-exécuté-une-fois-relevé-1612-utc) :
intervalles instrumentés, sans attribution à un temps matériel pur ou
au débit du pilote complet. La publication officielle décrit les contrats,
pas ces durées locales.

Complément du 5 octobre 2026 à 14:00 UTC : PSF,
[module time, Python 3.12](https://docs.python.org/3.12/library/time.html),
sections `monotonic_ns`, `perf_counter_ns` et `get_clock_info`, documentation
courante 3.12.15, interpréteur local 3.12.14. Les différences de deux lectures
de l'horloge monotone mesurent une durée écoulée ; `perf_counter` inclut les
attentes. Le diagnostic utilise `monotonic_ns` et conserve les caractéristiques
de l'horloge. Les mesures comprennent les attentes, contrôles et barrières
des opérations délimitées : ce ne sont pas des temps CPU ni une preuve de
débit global. Aucun remplacement d'interpréteur ou de moteur n'en découle.
Protocole local et limites : [journal du diagnostic](journal/2026-10-05.md#r23-ocr-03--instrumentation-des-coûts-et-diagnostic-borné).

Complément local à 15:09 UTC : instrumentation confrontée aux sources
parent/worker épinglées et aux nouveaux reçus natifs fermés ;
[mesures exécutées](journal/2026-10-05.md#diagnostic-exécuté-une-fois-relevé-1509-utc).
Le résultat du diagnostic ne constitue ni un apprentissage, ni une
qualification du pilote complet. Les valeurs et hashes ne sont pas
dupliqués ici ; ce registre conserve le contrat officiel de l'horloge.

Sources initiales consultées ROOT le 5 octobre 2026 avant le provisionnement
du pilote ; compléments causaux datés ci-dessous, après les premiers essais.
Les références mouvantes sont des contrats documentaires, pas des identités
d'artefacts ou des résultats locaux. Décision : [W035](DECISIONS.md#w035-pilote-isolé-dapprentissage-des-signes-scientifiques).

Complément de méthode du 5 octobre, consigné à 10:50 UTC après les questions
sur le volume, la qualité des exemples et le GPU. Skill
`official-source-review` appliqué, sans nouveau téléchargement ou changement
de moteur ; `project-documentation` pour la trace vivante.

| Source officielle relue | Fait documentaire | Application et limite |
|---|---|---|
| Mainteneurs Tesseract, [Training Tesseract 5](https://tesseract-ocr.github.io/tessdoc/tess5/TrainingTesseract-5.html), sections Introduction, Training Text Requirements, Hardware-Software Requirements et Understanding the Various Files Used During Training ; page courante, date de mise à jour non indiquée | La continuation peut utiliser peu de données ; les images doivent ressembler au domaine visé. La documentation distingue rendu, préparation `.lstmf` et apprentissage ; `.lstmf` associe image et transcription UTF-8. La voie décrite n'offre pas de support GPU. | Version exécutée : 5.4.0 épinglée ci-dessous. Les informations historiques de la page sur les OS ne qualifient pas Windows. Aucun minimum de 1 000 lignes ou preuve de généralisation n'est tiré de cette page ; le volume et la fonte unique sont des choix locaux du pilote. |
| Mainteneurs Tesseract, [README tesstrain](https://raw.githubusercontent.com/tesseract-ocr/tesstrain/405346a3a67d8e4e049341d1da6a4b752e0b8351/README.md), révision `405346a3a67d8e4e049341d1da6a4b752e0b8351`, sections Provide ground truth data et Train | Paires d'images de lignes TIFF/PNG et transcriptions `.gt.txt`, partage apprentissage/évaluation et étapes de préparation avant le train. | Le protocole local sépare les groupes avant leurs variantes ; la seule extension de fichier ne prouve pas leur contenu ou leur conversion native. Aucune commande `make training`, téléchargement ou installation de cette page exécuté. |

Résultat local de cette relecture : distinction explicite des opérations et
limites ajoutée à [W035](DECISIONS.md#portée-données-et-sens-de-lapprentissage--précision-du-5-octobre-1050-utc).
Ce complément ne réduit aucun seuil et ne qualifie pas le pilote.

| Source officielle et version | Apport utilisé | Limite |
|---|---|---|
| [tessdata_best README](https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/README.md) et [licence](https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/LICENSE), révision `e12c65a915945e4c28e237a9b52bc4a8f39a0cec` ; [Data Files](https://tesseract-ocr.github.io/tessdoc/Data-Files.html) | best contient des modèles LSTM flottants utilisables pour continuation ; OEM 1. Licence Apache-2.0, notices à préserver. | La description n'établit pas la nature du blob local : contrôle natif distinct consigné au journal. Aucun résultat P02. |
| [Noto Sans OFL](https://raw.githubusercontent.com/google/fonts/9710da1eacb3be272583c3224dcb70f9da6eadbb/ofl/notosans/OFL.txt), révision `9710da1eacb3be272583c3224dcb70f9da6eadbb` | Fonte sous OFL 1.1, texte de licence conservé ; les documents rendus ne deviennent pas des fichiers de fonte. | Usage interne uniquement ici, fonte non modifiée ; aucune licence inventée pour le code ou les textes du projet. Couverture réelle non déduite du nom Noto. |
| [generate_line_box.py](https://raw.githubusercontent.com/tesseract-ocr/tesstrain/405346a3a67d8e4e049341d1da6a4b752e0b8351/generate_line_box.py), révision `405346a3a67d8e4e049341d1da6a4b752e0b8351`, 1 462 octets | Une boîte pleine ligne par caractère et une ligne tabulation ; utilise Pillow et normalise le GT. | Le générateur exige préalablement NFC et absence d'espaces de bord ; aucune correction d'OCR. Le helper seul ne valide pas les LSTMF. |
| Pillow 12.3.0, [ImageFont](https://pillow.readthedocs.io/en/stable/reference/ImageFont.html), sections truetype/getbbox/get_variation_axes/set_variation_by_axes/Layout ; [ImageDraw.text](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html#PIL.ImageDraw.ImageDraw.text), lues ROOT à 02:57 UTC | Fonte chargée depuis ses octets, axes dans l'ordre effectivement retourné, BASIC explicite, bbox tenant compte des accents et ancre cohérente au dessin. | La documentation ne démontre ni l'absence de clipping ni les glyphes réels ; admission et rendu séparés requis. |
| Microsoft OpenType 1.9.1, [cmap](https://learn.microsoft.com/en-us/typography/opentype/spec/cmap), [table directory](https://learn.microsoft.com/en-us/typography/opentype/spec/otff#table-directory) et [maxp](https://learn.microsoft.com/en-us/typography/opentype/spec/maxp), sections pertinentes lues ROOT jusqu'à 02:57 UTC | Répertoire big-endian, numGlyphs, glyph 0 manquant ; formats Unicode 4/12 et calcul idRangeOffset/idDelta. | Lecteur borné pour la seule fonte épinglée ; pas un validateur général de fontes. L'identité du blob complet reste une garde séparée. |
| Tesseract 5.4.0, [lstmtraining.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/lstmtraining.cpp) et [lstmtrainer.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/unicharset/lstmtrainer.cpp) ; sections relues dans la source verrouillée locale | Caches distincts, défaut 6 000 Mio remplacé explicitement ; reprise d'un checkpoint existant prioritaire ; fichier courant terminal FULL et export du réseau courant. | Choix de préfixe neuf, deadline et contrôle des sorties indispensables. Le plafond 500 porte sur `training_iteration`, pas sur `learning_iteration`, la durée ou la convergence ; « best » est lié au TRAIN et n'est pas la règle de choix du pilote. |

Les neuf fichiers proposés totalisent 6 679 977 octets : best/fra ;
Latin.unicharset, radical-stroke.txt et licence langdata_lstm
`07930fd9f246622c26eb5de794d9212ceac432d3` ; fonte, OFL et METADATA.pb ; helper
et licence tesstrain. Tailles, Git blobs, SHA connus et URLs complètes dans
le reçu privé fermé, relié au [journal](journal/2026-10-05.md#r23-ocr-03--méthode-et-préparation-du-pilote-relevé-0258-utc).
Aucun de ces fichiers n'était provisionné au gel de cette méthode.

Complément sur le framing CLI : `TessTextRenderer::AddImageHandler`,
`TessBaseAPI::GetUTF8Text`, `ResultIterator::IterateAndAppendUTF8TextlineText`
et constructeur `LTRResultIterator`, sources locales Tesseract 5.4.0
verrouillées, relus ROOT avant tout OCR. La ligne puis le paragraphe ajoutent
chacun LF ; le premier rendu n'ajoute pas de séparateur de page. Le lecteur
du pilote borne donc le suffixe à deux LF et une éventuelle FF, sans `rstrip`
arbitraire ni changement des espaces/CR ; les fichiers stdout restent conservés.

Complément causal consulté le 5 octobre après les premiers essais natifs :

| Source officielle et section | Contrat utilisé | Limite |
|---|---|---|
| Tesseract 5.4.0, [unicharset_training_utils.cpp](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/unicharset/unicharset_training_utils.cpp), `SetupBasicProperties`, lignes 91–106 ; source locale verrouillée relue | `other_case` est initialisé à l'ID propre. Une casse opposée absente produit un message informatif, sans ajout de token ni branche d'échec. | N'autorise aucune omission nouvelle : seules les paires anciennes réellement vérifiées peuvent être distinguées des autres diagnostics, au seul `build-proto`. Les contrôles complets du proto et des lexiques restent nécessaires. |
| Pillow 12.3.0, [_imagingft.c](https://raw.githubusercontent.com/python-pillow/Pillow/12.3.0/src/_imagingft.c), `font_getvaraxes`, lignes 1269–1333, et `font_setvaraxes_impl`, lignes 1362–1407 | Les bornes/defaults exposés par `getvaraxes` sont des entiers après division du Fixed FreeType par 65536. Le setter accepte aussi les coordonnées flottantes. | Le résultat de cette API n'est pas la valeur Fixed exacte de la table de fonte ; les deux représentations sont contrôlées séparément. Le [journal natif](journal/2026-10-05.md#fonte-et-proto-v2-réellement-conformes-relevé-0353-utc) porte l'observation locale, pas cette source. |
| Microsoft OpenType 1.9.1, [fvar](https://learn.microsoft.com/en-us/typography/opentype/spec/fvar), header, `VariationAxisRecord` et sélection d'instance ; [types](https://learn.microsoft.com/en-us/typography/opentype/spec/otff#data-types) | Axes dans l'ordre des enregistrements, bornes/defaults en Fixed signé16.16 ; coordonnées par défaut pour l'instance normale. Tailles et offsets explicites. | Le document n'établit pas les valeurs du blob Noto téléchargé ; identité et table contrôlées localement, résultats au journal. |

Ces lectures corrigent les interprétations des contrôles préparatoires, pas
les critères de fidélité OCR. Les premiers refus et leurs conditions sont
conservés dans le journal ; aucun candidat n'est qualifié par ces sources.

Complément après le refus de préparation, sources officielles consultées
ROOT le 5 octobre ; relevé du registre à 05:38 UTC :

| Source officielle et version | Contrat du diagnostic I/O | Limite |
|---|---|---|
| PSF, [os.fsync, documentation Python 3.12](https://docs.python.org/3.12/library/os.html#os.fsync), page courante 3.12.15 ; interpréteur local 3.12.14 | Pour un flux Python tamponné, vider le tampon avant de synchroniser le descripteur. Sur Unix, l'appel utilise `fsync`. | Pas de mise à jour de Python ; aucune durée ni accélération locale déduite du contrat. |
| Projet Linux man-pages, [fsync(2), DESCRIPTION et ERRORS](https://man7.org/linux/man-pages/man2/fsync.2.html), 6.19, page datée du 08/02/2026 | Synchroniser chaque fichier ne garantit pas la persistance de son entrée de répertoire : une synchronisation distincte du répertoire est nécessaire. Depuis Linux 4.13, les erreurs de writeback sont rapportées aux descripteurs ouverts lors de l'écriture. Garder les descripteurs écrivains jusqu'à la barrière. | Le noyau local 5.10 appartient à cette plage ; cette documentation ne prouve ni le comportement matériel en coupure électrique, ni le coût des synchronisations du pilote. Le diagnostic compare des écritures contrôlées, sans qualifier l'apprentissage. |

Hypothèse locale : les écritures immédiatement synchronisées sérialisent une
partie de la préparation. Le diagnostic prépare les mêmes octets dans deux
bras neufs et mesure rendu, écriture et synchronisations séparément. Chaque
fichier et les répertoires restent synchronisés avant toute réussite du
diagnostic ; un résultat manquant ou une erreur ne devient pas une admission.
Aucun regroupement n'est adopté dans le pilote ; le [diagnostic exécuté](journal/2026-10-05.md#diagnostic-io-natif-terminé-relevé-0624-utc)
ne confirme pas de gain. [W035](DECISIONS.md#w035-pilote-isolé-dapprentissage-des-signes-scientifiques)
conserve ses budgets, données et critères. Les publications officielles
décrivent la durabilité, pas ce résultat local.

Complément de supervision consulté ROOT le 5 octobre à 09:14–09:18 UTC :
[PSF, `os.scandir`, `DirEntry.stat` et `os.walk`](https://docs.python.org/3.12/library/os.html#os.scandir),
documentation 3.12.15, interpréteur local 3.12.14. Sur Unix, `stat` effectue
un appel système puis garde son résultat dans l'entrée ; ne pas conserver
ce cache entre deux scans. Fermer explicitement les itérateurs et utiliser
les relevés sans suivi des liens. `os.walk` utilise déjà `scandir` depuis
Python 3.5 : le changement proposé évite des relevés et allocations
répétés, pas un remplacement de `listdir` supposé. Les mutations durant
l'itération ont un résultat non spécifié ; la racine et son inventaire
doivent rester inchangés dans le benchmark en lecture seule.

Hypothèse à mesurer : le parcours actuel de la QA contribue au temps
de préparation et aux écarts de supervision. Le benchmark compare les
comptes logiques et physiques séparément sur l'ancien arbre immuable ;
aucun contenu de fonte, poids ou texte n'est ouvert. Il ne prouve ni une
cadence continue, ni le respect des 900 secondes du pilote avec écrivains
actifs. La mesure de fermeture conserve les synchronisations, gardes et
ordres existants ; aucun regroupement de commandes n'est adopté.

Complément mémoire consulté ROOT le 5 octobre à 09:40–09:42 UTC après le
refus `BENCH_RSS_CAP` : [Linux man-pages 6.19, `getrusage(2)`, NOTES](https://man7.org/linux/man-pages/man2/getrusage.2.html)
indique que les mesures sont conservées à travers `execve`. Le pic
`ru_maxrss` peut donc inclure l'image précédente du même processus ; il
n'est pas assimilé à la seule exécution Python du benchmark.
[Documentation officielle Linux, `/proc`, section 1.1](https://docs.kernel.org/filesystems/proc.html)
décrit `VmHWM` et `VmRSS` dans `status` et précise leur caractère asynchrone
et approximatif sur SMP. La V2 garde le pic historique en information et
contrôle le même plafond sur les valeurs de l'image courante ; ni pic
continu exact ni isolation matérielle mémoire ne sont revendiqués.

## R23OCR-S10 — disparition d'un processus pendant la lecture procfs

Consultation ROOT du 5 octobre, après l'échec du pilote neuf à 11:13:21 UTC,
avant tout changement du lecteur. Skills `official-source-review` et
`agent-introspection-debugging` ; aucune relance ou mutation du protocole
gelé par cette recherche. Hôte observé : `5.10.120-tegra` (`db8a62`).

| Source officielle et version | Apport | Limite d'application |
|---|---|---|
| Mainteneurs Linux, [documentation 5.10 de `/proc`, §1.1](https://docs.kernel.org/5.10/filesystems/proc.html#process-specific-subdirectories) | Un descripteur ouvert sur un processus ensuite disparu ne vise pas le nouveau processus qui reprendrait son PID ; ses opérations peuvent échouer avec `ESRCH`. La lecture du statut n'est pas une réservation de l'identité. | Famille de noyau applicable à l'hôte ; ne vérifie pas toutes les modifications NVIDIA. La source ne localise pas l'exception passée ni le PID concerné. |
| Python Software Foundation, [exceptions système Python 3.12](https://docs.python.org/3.12/library/exceptions.html#ProcessLookupError), `FileNotFoundError` et `ProcessLookupError` | `ENOENT` correspond au fichier absent ; `ESRCH` au processus absent et à `ProcessLookupError`. Ce sont deux sous-classes distinctes de `OSError`. | Page courante titrée 3.12.15, dernière mise à jour indiquée 01/10/2026 ; interpréteur projet 3.12.14. Contrat de la famille 3.12, pas preuve d'une recette locale. |

Code local relu (`0aabce`) : `process_stat` du protocole épinglé
`7c830396…0132`, lignes 203–211, intercepte seulement `FileNotFoundError`.
`owned_cohort`, lignes 214–225, utilise ce lecteur pour les entrées de
`/proc`, avant de retenir la session possédée. Cela identifie un scénario
de course testable ; l'origine exacte du `ProcessLookupError` historique
reste inconnue faute de traceback. Une correction future doit borner la
gestion d'absence au lecteur proc, conserver le refus sur perte de leader,
naissance différente, PGID/SID incohérents, permissions, données invalides
et erreurs non reconnues. Aucun arrêt sur un PID réutilisé ni tolérance
globale de `OSError` n'est autorisé par ce constat.

Correction locale distincte du protocole ancien : copie isolée
`tools_protocol_v2.py`, SHA-256
`f5655f5548428f81ec77950f582af2e3363ccc241b333869d2b2e0ef2ffb2ed2`.
Seuls l'import `errno` et le handler entourant `read_text` changent ;
ENOENT/ESRCH donnent `None`, les autres erreurs sont propagées, parsing
hors de ce handler. Les refus du leader, du groupe et de session ainsi
que l'arrêt restent inchangés. Témoins exacts, interfaces substituées,
gel et raccordement : [journal du correctif](journal/2026-10-05.md#correction-bornée-du-lecteur-procfs-relevé-1208-utc).
Ces preuves pures ne localisent pas l'exception historique et ne prouvent
ni une préparation complète ni un apprentissage natif.

## R23OCR-S08 — procédure d'extension et sources d'outillage

Sources officielles lues ROOT le 5 octobre avant la création du skill
`tesseract-lstm-extension`. Pas de poids, outils ou données d'apprentissage
adoptés par ces lectures. Le préflight S07 reste une observation locale,
pas un build ; la phase d'outillage est distincte de l'apprentissage.

| Source officielle/version | Contrat utilisé | Limite |
|---|---|---|
| [Makefile tesstrain `405346a3…`](https://raw.githubusercontent.com/tesseract-ocr/tesstrain/405346a3a67d8e4e049341d1da6a4b752e0b8351/Makefile) | Ancien alphabet fusionné avant le nouveau ; continuation avec `old_traineddata`, préparation des lignes et exports. Téléchargements et nettoyages sont des cibles explicites à ne pas déclencher implicitement. | Pin découvert par l'étude, pas un checkout exécuté ou qualifié. Un split par fichiers ne garantit pas la séparation des variantes d'un même texte. |
| [Tesseract 5.4, fusion d'alphabets](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/merge_unicharsets.cpp) | Fusion dans l'ordre des arguments ; contrôler les anciens tokens/IDs et les ajouts. | Conserver l'ordre ne suffit pas à prouver le recoder ou la reconnaissance. |
| [Tesseract 5.4, chargement du réseau d'apprentissage](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/unicharset/lstmtrainer.cpp), `TryLoadingCheckpoint` | Rejet du modèle integer ; ancien charset/recoder chargés pour remapper les sorties lorsque l'alphabet change. | Le remapping ne constitue pas l'apprentissage des sorties nouvelles ; aucune convergence présumée. |
| [Tesseract 5.4, `combine_lang_model`](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/combine_lang_model.cpp) | Les trois listes lexicales illisibles peuvent produire un avertissement et une liste vide ; vérifier les composants réels et les lexiques après export. | EXIT0 seul ne prouve pas la conservation des ressources nominales. |
| [Tesseract 5.4, boucle et exports d'apprentissage](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/lstmtraining.cpp) | `max_iterations` borne le compteur `training_iteration` ; caches train/évaluateur distincts. Un export peut signaler un échec d'écriture sans retour final non nul. | `learning_iteration` peut être inférieur, les lignes parfaites faisant aussi progresser `training_iteration`. Deadline externe, mesures et contrôle des fichiers restent nécessaires ; pas de résultat d'entraînement ici. Précision de source relue le 5 octobre à 04:16 UTC. |
| [CMake 3.16, FindICU](https://cmake.org/cmake/help/v3.16/module/FindICU.html), lecture ROOT du 05/10/2026 | Variables `ICU_FOUND`, `ICU_VERSION`, en-têtes et bibliothèques par composant. Le CMake training épinglé ne demande pas `REQUIRED` : les cibles effectives sont contrôlées avant compilation. | Le guide est affiché en version documentaire 3.16.9 ; CMake local est 3.16.3. La configuration réelle reste à exécuter ; la documentation ne valide pas la résolution locale d'ICU. |

Archive source déjà en cache vérifiée ROOT (`859d1c`) : 1 900 009 octets,
SHA-256 `30ceffd9b86780f01cbf4eaf9b7fc59abddfcbaf5bbd52f9a633c6528cb183fd`,
identique au verrou du projet. Aucune extraction ou construction nouvelle
à ce contrôle ; cache et installation nominaux inchangés.

## Q05UMASK-S01 — portée du masque dans l'entrée QA

Lecture ROOT le 5 octobre 2026 de la [documentation PSF Python 3.12,
`os.umask`](https://docs.python.org/3.12/library/os.html#os.umask) : fixe le
masque du processus et retourne l'ancien. La version documentaire affichée
est 3.12.15, l'interpréteur local 3.12.14. Ce contrat ne change pas les
permissions d'un fichier déjà présent et ne prouve pas le masque d'un
lancement historique.

Source locale : entrée opératoire SHA `8276b631…` appelant directement
`cohort.flow`, sans l'initialisation de `cohort.main` (`5ea2e203…`). Writer
exact `37e1287e…` : création temporaire `open("w")`, publication par
`replace`, sans chmod. Lecteur strict inchangé : JSON ≤16 Mio et mode `0600`.
[Sources complètes, correctif et témoins](journal/2026-10-05.md#q05--correctif-dentrée-qa-et-témoins-causaux-relevé-0141-utc).
L'omission de composition est prouvée ; aucune correction produit,
transformation d'ancien runtime ou validation native n'en est déduite.

## R23OCR-S06 — alphabet français historique et mode OCR

Étude ciblée du 5 octobre 2026, sans installation ni OCR. Hypothèse : le
modèle français officiel du dépôt `tessdata`, distinct de fast/best, pourrait
couvrir les deux signes scientifiques manquants par sa voie historique.
Métadonnées consultées à 00:55:56–00:55:58 UTC, composants à
00:58:17–00:58:19 ; ROOT relit les reçus et le lecteur, puis les sources
primaires et la version locale. Le [README épinglé](https://raw.githubusercontent.com/tesseract-ocr/tessdata/ced78752cc61322fb554c280d13360b35b8684e4/README.md)
déclare les voies historique et LSTM et la licence Apache-2.0 ; il ne prouve
pas la reconnaissance des signes.

| Source ou composant | Fait vérifié | Limite |
|---|---|---|
| [`tessdata/fra`](https://raw.githubusercontent.com/tesseract-ocr/tessdata/ced78752cc61322fb554c280d13360b35b8684e4/fra.traineddata), révision `ced78752cc61322fb554c280d13360b35b8684e4` | Taille annoncée 14 213 351 octets ; blob Git annoncé `250c7749ba301ce50c3317631c6a61b03b6410ce`. Composant 0 absent ; composant 1 : 143 entrées, 9 560 octets, plage 196–9755 ; composant 21 : 141 entrées, 8 105 octets, plage 14203943–14212047. `±` et `·` absents dans les deux alphabets, y compris leurs octets UTF-8 complets. | Quatre plages HTTP 206 exactes, 17 861 octets sur un plafond de 64 Kio ; aucun poids ni modèle complet. Le blob annoncé n'est pas rehaché. Cette seule piste française est écartée, pas tous les artefacts possibles. |
| [Tesseract 5.4.0, `TessdataType` et disponibilité des composants](https://raw.githubusercontent.com/tesseract-ocr/tesseract/5.4.0/src/ccutil/tessdatamanager.h), [initialisation du mode](https://raw.githubusercontent.com/tesseract-ocr/tesseract/5.4.0/src/ccmain/tessedit.cpp) | Composant 1 : alphabet historique ; 21 : alphabet LSTM. Le mode par défaut choisit selon la présence de 17 et de 1+3, puis les configurations peuvent le modifier. Un OEM explicite est réappliqué après ces configurations. | Une aide CLI, un composant présent ou une confiance élevée ne prouve pas une reconnaissance fidèle. Une langue partiellement chargée ne qualifie pas `fra+eng`. |
| [Docling 2.131.0, `_run_tesseract`](https://raw.githubusercontent.com/docling-project/docling/v2.131.0/docling/models/stages/ocr/tesseract_ocr_cli_model.py), fonction locale relue ; `services/ingestion/regional_grid.py:_run_literal_tsv` | Les deux chemins ne passent aucun `--oem`. Le binaire local expose réellement 0/1/2/3 via `--help-oem` (`64b9ad EXIT0`), sans OCR. | Changer de `tessdata` n'est donc pas nécessairement transparent pour le mode effectif. Ni essai historique, ni compatibilité Windows qualifiés. |

[Reçus, empreintes et décision de poursuite](journal/2026-10-05.md#r23-ocr-01--piste-française-historique-écartée-relevé-0104-utc).
L'inspection indépendante et le suivi restent distincts de la qualification
native. Aucun fichier installé, PDF gelé, seuil ou configuration nominale
n'est modifié par cette étude.

## R23OCR-S07 — extension d'alphabet LSTM, faisabilité à établir

Consultation ROOT le 5 octobre 2026 à 01:02 UTC de la
[documentation de formation Tesseract 5](https://tesseract-ocr.github.io/tessdoc/tess5/TrainingTesseract-5.html),
sections « Understanding the Various Files Used During Training » et
« LSTMTraining Command Line », et du [dépôt officiel tesstrain](https://github.com/tesseract-ocr/tesstrain).
Fait documentaire : la continuation peut modifier l'alphabet d'un modèle
non converti en entier ; `--old_traineddata` fournit alors l'ancien
alphabet/recoder. Les outils, données séparées et limites de calcul doivent
être établis avant essai. Les scripts historiques `tesstrain.sh` ne sont
plus la procédure recommandée ; aucun support GPU n'est annoncé pour cet
entraînement.

Préflight local clos à 01:11:51 UTC, relu ROOT à 01:18 : six outils absents
du seul préfixe inspecté, `BUILD_TRAINING_TOOLS=OFF` dans le cache nominal.
ICU 66.1 et Leptonica 1.87 disposent des en-têtes et liens requis ; les
modules pkg-config Pango/cairo/fontconfig interrogés ne sont pas trouvés.
Ces observations ne sont ni une configuration CMake réussie, ni une
compilation. [Reçu, empreintes et limites](journal/2026-10-05.md#r23-ocr-01--préflight-dextension-lstm-relevé-0118-utc).

| Source officielle relue ROOT le 5 octobre | Apport | Limite |
|---|---|---|
| [CMake des outils, Tesseract 5.4 épinglé](https://raw.githubusercontent.com/tesseract-ocr/tesseract/1be261dc226d49bdcad0ab2fcb10f8395edc1225/src/training/CMakeLists.txt) | Les cibles LSTM nécessitent ICU ; avec PkgConfig disponible, le bloc Pango du renderer est requis dès la configuration. Sélectionner seulement les cibles LSTM au build n'évite pas ce bloc. | L'absence de ces modules concerne la recherche effectuée, pas toutes les bibliothèques présentes sur le poste. |
| [CMake 3.16, désactivation d'un paquet optionnel](https://cmake.org/cmake/help/v3.16/variable/CMAKE_DISABLE_FIND_PACKAGE_PackageName.html) | `CMAKE_DISABLE_FIND_PACKAGE_PkgConfig=TRUE` sur un cache neuf désactive sa découverte non REQUIRED. Le code 5.4 devrait alors prendre FindICU et omettre Pango/text2image. | Déduction des sources seulement ; aucune configuration ni cible compilée. Le cache nominal ne doit pas être réutilisé ou modifié. |
| [README officiel tesstrain](https://raw.githubusercontent.com/tesseract-ocr/tesstrain/main/README.md) | Lignes TIFF/PNG et transcriptions UTF-8 séparées entre apprentissage et évaluation ; cibles explicites pour proto-modèle, entraînement et export. | Branche mobile consultée pour l'étude, pas un pin adopté. Les cibles peuvent télécharger des données ; aucune exécutée ici. |

**Statut : faisabilité seulement ; construction, entraînement et OCR NOT_RUN.**
Aucun modèle float téléchargé, outil construit ou entraînement lancé. Une
adoption nécessiterait une décision distincte, un skill adapté, des données
et licences d'entraînement séparées des fixtures gelées et une
requalification de l'extraction. Le coût et la convergence sont inconnus.
Cette étude ne donne ni poids corrigés ni résultat de qualité ; les modèles
nominaux restent ceux du verrou existant.

## R23OCR-S05 — couverture des alphabets alternatifs

Consultations C le 5 octobre 2026 : `best/fra` et `best/eng` à 00:01:55–00:01:58 UTC,
puis `fast/script/Latin` à 00:10:31–00:10:35. ROOT relit les deux reçus fermés
et le lecteur borné, puis les sections utiles du [README fast versionné](https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/README.md)
et de [Data-Files](https://tesseract-ocr.github.io/tessdoc/Data-Files.html), à 00:17–00:19 UTC.
La compatibilité d'un alphabet avec les deux signes scientifiques de P02 est
la question préalable ; aucune mesure de qualité OCR n'est exécutée.

| Artefact officiel | Révision de la source | Composant 21 inspecté | Résultat et limite |
|---|---|---|---|
| [`best/fra`](https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/fra.traineddata) | `e12c65a915945e4c28e237a9b52bc4a8f39a0cec` | 8 105 octets, plage inclusive 3963477–3971581 ; 141 caractères | `±` et `·` absents. SHA-256 `575fb5df…`, identique au composant fast installé ; ce n'est pas une équivalence des réseaux ou de leur qualité. |
| [`best/eng`](https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/eng.traineddata) | même révision best | 6 360 octets, plage inclusive 15393149–15399508 ; 112 caractères | `±` et `·` absents. SHA-256 `3a18fb4e…`, même limite de comparaison. |
| [`fast/script/Latin`](https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/script/Latin.traineddata) | `87416418657359cb625c412a48b6e1d6d41c29bd` | 18 023 octets, plage inclusive 89364021–89382043 ; 303 caractères | `·` présent, `±` absent. SHA-256 `0ce04ab5…`. Le README décrit un modèle d'écriture couvrant plusieurs langues latines, non la langue `lat`. Couverture insuffisante pour ce cas ; pas d'adoption. |

Lectures strictes HTTP 206 : `Content-Range`, longueur et absence de compression
contrôlés, plafond 64 Kio par artefact, sans repli sur une réponse intégrale.
Seuls l'en-tête et le composant 21 sont lus ; respectivement 8 301, 6 556 et
18 219 octets. Les tailles totales et blobs Git annoncés dans les métadonnées
officielles ne sont **pas** rehachés depuis ces lectures partielles. Aucun poids
du réseau, fichier modèle complet, inventaire installé ou OCR lu/exécuté ;
aucune installation ou modification de `fra+eng`. Le format du composant est
celui vérifié en R23OCR-S04. [Reçus, hashes complets et limites](journal/2026-10-05.md#inspection-bornée-des-alphabets-alternatifs).

Le résultat négatif borne la prochaine action : définir une voie dont
l'alphabet couvre les signes avant tout essai. Il ne justifie ni changement
de PDF gelé, correction lexicale des sorties, cascade de modèles ou nouveau
réglage de densité/PSM sur ces mêmes alphabets.

### Alternative ciblée best/script/Latin — 5 octobre, 23:04 UTC

Question : cet alphabet officiel couvre-t-il les signes manquants, avant
d'envisager le pilote W035 ? Une seule alternative supplémentaire, sans OCR,
installation ni recherche de modèles en série.

Les [métadonnées GitHub du mainteneur, révision best épinglée](https://api.github.com/repos/tesseract-ocr/tessdata_best/contents/script/Latin.traineddata?ref=e12c65a915945e4c28e237a9b52bc4a8f39a0cec)
ont été lues directement par ROOT (`f80a19`/`7823b2 EXIT0`) après deux routes
de lecture web indisponibles. Corps reçu : 1 112 octets, SHA-256
`1297ab31829ff778397778a8a7ba76448a81970a9345153f198730b4f80b2fdd`.
Elles annoncent un fichier de 101 402 885 octets, blob Git
`e78c193f637e0bcbeeb9ed2919f2e4ac68cb972d`, et la
[route raw officielle immuable](https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/script/Latin.traineddata).
Le [README de cette révision](https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/README.md)
décrit des modèles LSTM et une licence Apache 2.0 ; il ne prouve ni couverture
des signes ni reconnaissance sur les scans du projet.

Métadonnées consignées avant usage ; lecture unique fermée à 23:13 UTC,
`05469c`/`7bdec7 EXIT0`, `INSPECTED_COMPONENT21_ONLY`. Trois plages 206
exactes, 18 219 octets lus au total : en-têtes et alphabet seulement.
Composant 21 : 303 caractères, 18 023 octets, plage inclusive
101382045–101400067, SHA-256
`0ce04ab5919d3ae2a48769b4f8a17b25062a619495ccf00f3aa0f10384077994`.
« · » présent, « ± » absent des octets UTF-8 et des représentations.
Alphabet identique au composant fast/Latin examiné plus haut ; aucune
équivalence des réseaux ou de leur reconnaissance n'est déduite.

Le lecteur strict 206 épinglé est réutilisé sans modification, plafond
64 Kio et aucun repli intégral ; wrapper relu indépendamment avant admission
ROOT. La taille et le blob annoncés restent des métadonnées, non une identité
complète revalidée. Alternative écartée pour le signe requis, sans installation,
OCR ni apprentissage. Ce résultat ne prouve pas l'absence de tous les modèles
et ne rend pas indispensable le volume W035.
[Reçu, méthode et décision de suite](journal/2026-10-05.md#nécessité-de-correction-ocr--contrôle-ciblé-après-q07).

## R23OCR — reprise locale des petites lignes imprimées

Consultation ROOT du 4 octobre 2026, 23:29–23:36 UTC, avant l'essai et
l'adoption d'une voie différente du retry mono-glyphe. Question : peut-on
récupérer les deux extractions DEV partielles sans changer les PDF gelés,
le moteur, les langues ou le seuil de confiance ? Le skill d'ingestion
existant est adapté ; aucun second skill concurrent n'est créé.

| ID | Source officielle et contrat constaté | Apport et limite |
|---|---|---|
| R23OCR-S01 | Mainteneurs Tesseract, [ImproveQuality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html), sections Rescaling, Borders et Page segmentation method ; documentation courante non datée, binaire local verrouillé 5.4.0 | Densité et bordure peuvent influer sur la reconnaissance. PSM 3 segmente une page, 6 un bloc uniforme et 7 une ligne. Ces conseils justifient une hypothèse locale, pas les facteurs, plafonds ou gains du projet. Première expérience : crop borné et ×2, PSM de la baseline conservé. Aucun dictionnaire d'attendus ni substitution lexicale. |
| R23OCR-S02 | Projet Docling, [Tesseract CLI au tag v2.131.0](https://github.com/docling-project/docling/blob/v2.131.0/docling/models/stages/ocr/tesseract_ocr_cli_model.py), `_run_tesseract` et `__call__` ; mêmes fonctions et `backend/pypdfium2_backend.py:get_page_image` relues dans la version installée 2.131.0 | Les mots TSV, confiances et boîtes alimentent les cellules Docling ; le PSM est ajouté seulement s'il est configuré. Le rendu PDFium est fait à `scale * 1.5`, puis redimensionné aux dimensions arrondies du crop. Vérifier le hash du raster avant l'expérience ; aucune compatibilité Windows ou succès natif ne se déduit de la lecture. |
| R23OCR-S03 | Mainteneurs Pillow, [Image.resize](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize), documentation et installation 12.3.0 | Le filtre est un paramètre explicite ; BICUBIC est le défaut hors modes 1/P, LANCZOS est disponible. L'expérience doit nommer facteur, filtre et dimensions réellement arrondies. La disponibilité du filtre ne prouve ni amélioration OCR ni fidélité des signes et unités. |
| R23OCR-S04 | Tesseract 5.4.0, [TessdataType](https://raw.githubusercontent.com/tesseract-ocr/tesseract/5.4.0/src/ccutil/tessdatamanager.h), entrées 17–23 ; [LoadMemBuffer](https://raw.githubusercontent.com/tesseract-ocr/tesseract/5.4.0/src/ccutil/tessdatamanager.cpp), table d'offsets ; [LoadCharsets et DecodeLabel](https://raw.githubusercontent.com/tesseract-ocr/tesseract/5.4.0/src/lstm/lstmrecognizer.cpp). ROOT : sections ouvertes le 04/10 à 23:52–23:54 UTC ; diagnostic indépendant C précédent | Le composant 21 est l'alphabet LSTM effectivement chargé, lu avec le nombre d'entrées uint32 et les offsets int64. Son inspection locale en lecture seule vérifie d'abord tailles et Git blob SHA-1 des modèles officiels verrouillés. `±` et `·` sont absents des deux composants, y compris hors tokens. Limite d'alphabet, pas explication de la préférence particulière `+`/`-`, ni cause isolée de `0/O`. [Preuve et limites](journal/2026-10-04.md#r23-ocr-01--essais-bornés-et-alphabets-relevé-2356-utc). |

Hypothèse initiale, **NOT_RUN à sa rédaction** : reprendre une petite ligne
multiglyphe choisie par la baseline TSV réellement insuffisante, une seule
fois, avec budgets vérifiés avant allocation. Une réussite devra conserver
ses voisines, inverser toutes les transformations et respecter les attentes
littérales gelées. Les confiances seules ne prouvent pas cette fidélité.
L'action [R23-OCR-01](PLAN.md) et le journal portent les essais ; ce registre
ne remplace pas leurs résultats. Complément du relevé à 23:56 UTC : les essais
×2 et PSM7 ne qualifient pas P02 ; le contexte de rangée P03 est positif au
crop seulement. Les deux artefacts OCR existants ne couvrent pas les signes
scientifiques contrôlés. Aucun changement d'artefact acquis.

## R23S02 — identité du tag 2B et tokenizer versionné

Consultation ROOT le 4 octobre 2026, relevé à 19:17 UTC, après
reconfirmation du choix du modèle et du défaut `qwen3.5:2b`. Le tag exact
demandé n'est pas remplacé par le tag Q4_K_M historique de [R23S01](#r23s01--modèle-qwen-35-2b-et-quantification-explicite).

Le [manifeste officiel du registre Ollama](https://registry.ollama.ai/v2/library/qwen3.5/manifests/2b)
a été lu et haché : 1 088 octets, SHA-256
`0689d44085e06d165161a8a9a1731344278cfb5aade63a3c3dbdb48ab54b130a`.
Il désigne le moteur `llamacpp`, le format GGUF, une couche modèle de
2 012 012 448 octets et un projecteur séparé de 671 372 768 octets.
La [configuration officielle de cette identité](https://registry.ollama.ai/v2/library/qwen3.5/blobs/sha256:0f7af3a2d4145d7e4dbc9dbab778ac7a6aee7104fb93570c047726b5a816781f)
porte `Q8_0`, les renderer/parser `qwen3.5` et le prérequis `0.30.0`.
La [fiche du catalogue](https://ollama.com/library/qwen3.5:2b) distingue
aussi une distribution MLX : son identité n'est pas celle du runtime
Ollama 0.35.0 utilisé ici. Le tag reste mobile ; le futur provisionnement
doit refuser une identité différente du verrou, pas la suivre implicitement.

Contrôle complémentaire du code officiel Ollama 0.35.0 le 4 octobre :
[`PullModel`, `server/images.go`](https://github.com/ollama/ollama/blob/v0.35.0/server/images.go#L936)
conserve les octets reçus du registre (`pullModelManifest`, lignes 1194–1214)
et les écrit tels quels au stockage (ligne 1039). Il ne resérialise pas ici
les champs additionnels `runner` et `format`. Le digest est calculé à la
lecture du fichier dans
[`manifest/manifest.go`](https://github.com/ollama/ollama/blob/v0.35.0/manifest/manifest.go#L133).
Ce constat de code justifie le contrôle du SHA brut ; il ne remplace pas
le rapprochement HTTP et fichiers après un provisionnement réel.

Diagnostic réseau du provisionnement le 4 octobre : la documentation de
[`net`, Go 1.26.0, Name Resolution](https://pkg.go.dev/net@go1.26.0#hdr-Name_Resolution)
décrit `GODEBUG=netdns=cgo` pour utiliser le résolveur système lorsqu'il est
présent dans le binaire. Le
[`go.mod` d'Ollama 0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/go.mod)
déclare Go 1.26.0. Cette source justifie un essai borné au processus de
provisionnement, pas une modification DNS de la machine. Le premier pull
a échoué sur IPv6 ; les lectures HTTPS Python et curl IPv4 du même manifeste
ont réussi. La cause précise et l'effet du changement de résolveur restent
à vérifier ; ni proxy ni certificat désactivé.

Diagnostic des segments GGUF, sources officielles v0.35.0 relues le 4 octobre :
[`download.go`](https://github.com/ollama/ollama/blob/v0.35.0/server/download.go)
fixe 16 transferts et réessaie les segments bloqués ; la reprise lit les
sidecars et leurs offsets `Range`. Les variables d'inférence ne règlent pas
cette concurrence ([envconfig](https://github.com/ollama/ollama/blob/v0.35.0/envconfig/config.go)).
Le transport des ranges choisit une adresse résolue et ne configure pas de
proxy ([redirect.go](https://github.com/ollama/ollama/blob/v0.35.0/transfer/redirect.go)) ;
aucun sélecteur IPv4 officiel applicable identifié. Au redémarrage,
`Serve` appelle `PruneLayers` sauf `OLLAMA_NOPRUNE` ; les partiels âgés
de plus d'une heure peuvent être supprimés
([routes.go](https://github.com/ollama/ollama/blob/v0.35.0/server/routes.go),
[images.go](https://github.com/ollama/ollama/blob/v0.35.0/server/images.go)).
Une éventuelle reprise doit donc préserver le store et les partiels, sans
modifier le DNS global, le TLS ou détourner un paramètre d'inférence.
Ce constat ne prouve pas la cause des stalls ; aucun arrêt de téléchargement
ni ajout de `OLLAMA_NOPRUNE` effectué à ce relevé.

Le tokenizer candidat du producteur est
[Qwen/Qwen3.5-2B, révision `15852e8c16360a2fea060d615a32b45270f8a8fc`](https://huggingface.co/Qwen/Qwen3.5-2B/tree/15852e8c16360a2fea060d615a32b45270f8a8fc).
Ses six fichiers ont été lus depuis les URLs `resolve` versionnées, en
mémoire seulement, puis hachés :

| Fichier | Octets | SHA-256 |
| --- | ---: | --- |
| `tokenizer.json` | 12 807 982 | `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42` |
| `tokenizer_config.json` | 16 709 | `49e2b6e395f959f077f1e992b338919c0d4a9732fc6e613995e06557f843500c` |
| `chat_template.jinja` | 7 755 | `273d8e0e683b885071fb17e08d71e5f2a5ddfb5309756181681de4f5a1822d80` |
| `config.json` | 2 908 | `ed1c1723241f23f7f4e23430759cbd7dcfb4103cbdfe052bfe7626b57c2615b4` |
| `LICENSE` | 11 544 | `bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a` |
| `README.md` | 62 814 | `c0e83a849c776e6fa843d011f023132d942a0f0140d903205bf1c363adad2275` |

Les chemins officiels et les digests complets des couches figurent dans la
preuve privée `R23_OFFICIAL_2B_IDENTITY_OBSERVATIONS_20261004.json`, sous
QA R15 `evidence-review/modal-source249-ROOT-20261004/`, SHA-256
`0fedc1b54b5d3b2e90737f8eda9851d5ac02225c303e6d14c4c1820b23182ed9`.
Les accès directs du navigateur de recherche au registre et au fichier
`raw` Hugging Face ont échoué ; la lecture HTTPS des endpoints officiels
par la bibliothèque standard a réussi. Une erreur initiale d'échappement
du lecteur s'est produite avant tout accès réseau, puis a été corrigée.

Limites de cette consultation du 4 octobre à 19:17 UTC : les poids et le projecteur n'ont pas été téléchargés ni inspectés,
aucun artefact n'a été installé et aucun appel au modèle n'a été exécuté.
Le tokenizer documentaire ne prouve pas sa parité avec `prompt_eval_count`
d'Ollama. La séparation du projecteur ne prouve pas encore le comportement
texte seul sur cette version. Admission mémoire, latence, qualité, génération
SSE/citations et non-régression 4B restent à vérifier sur une cible isolée.

## R15S57 — lecture de pixels et drainage du harnais Q05

Consultation ROOT le 4 octobre 2026 ; relevé à 17:12 UTC. Contrat navigateur
actuel du WHATWG et APIs Playwright applicables à la version installée 1.63.0 :

| Source officielle | Apport retenu | Limite |
| --- | --- | --- |
| [HTML Standard, Canvas 2D et optimisation de lecture](https://html.spec.whatwg.org/multipage/canvas.html#concept-canvas-will-read-frequently) | `willReadFrequently` marque un contexte pour la lecture de pixels ; le contexte 2D reste lié au canvas. Une surface de lecture séparée évite de modifier le contexte utilisé par PDF.js. | Le standard ne prouve ni la cause du warning de la recette ni l'équivalence locale des pixels. Celle-ci exige un essai. |
| [Playwright, Route.fetch](https://playwright.dev/docs/api/class-route#route-fetch) | La requête est effectuée avant son `fulfill` ; timeout et absence de retries peuvent rester explicites. | Une requête engagée n'est pas nécessairement terminée au retour d'une autre opération Playwright. |
| [Playwright, BrowserContext.unrouteAll](https://playwright.dev/docs/api/class-browsercontext#browser-context-unroute-all), contrat de version déjà relié en [R15S56](#r15s56--fermeture-de-la-trace-et-du-contexte-de-test) | `wait` attend les handlers en cours mais retire les routes ; `ignoreErrors` masque leurs erreurs ultérieures. | Ces deux voies ne sont pas retenues : le confinement doit rester installé jusqu'à la fermeture, sans masquer les erreurs. |

Source Chromium tentée sur `chromium.googlesource.com`, fichier
`third_party/blink/renderer/modules/canvas/canvas2d/base_rendering_context_2d.cc`
de la branche `main` : accès en erreur, aucun fait de version déduit.
La référence WHATWG reste le contrat de canvas ; le test local fournit
seulement une observation sur le navigateur installé.

Essai ROOT isolé, sans application, API, authentification ou réseau :
`evidence-review/modal-source249-ROOT-20261004/readback-discriminator-20261004.mjs`,
Node 24.16.0 et Playwright 1.63.0, cache physique déjà provisionné.
Commandes `984c7d` puis terminal `2e2bcd EXIT0` : neuf lectures directes
produisent un warning du type Canvas2D recherché ; neuf copies ROI 1:1
dans une surface `OffscreenCanvas` de lecture produisent les mêmes SHA,
sans warning. Aucune requête ni erreur ; surface temporaire maximale de
23 493 pixels, libérée ; attribut du contexte source inchangé.
Cette preuve synthétique n'établit pas la cause du warning Q05 antérieur,
ne qualifie pas le PDF et ne remplace pas une nouvelle recette native.
Correction candidate confiée à C : lecture ROI bornée et drainage après
les dernières opérations, avec tests discriminants et revue non-auteur.

## R15S56 — fermeture de la trace et du contexte de test

Consultation ROOT le 4 octobre 2026 à 12:17–12:19 UTC, documentation
actuelle et code officiel du tag installé Playwright 1.63.0 :
[BrowserContext.close](https://playwright.dev/docs/api/class-browsercontext#browser-context-close),
[Tracing.stop](https://playwright.dev/docs/api/class-tracing#tracing-stop),
[client browserContext.ts](https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/packages/playwright-core/src/client/browserContext.ts)
(`close`, lignes 484–495 ; `unrouteAll`, 395–417) et
[client tracing.ts](https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/packages/playwright-core/src/client/tracing.ts)
(`stop`, 87–94).

Arrêter et exporter la trace ne ferme pas les pages. `close` ferme le
contexte, mais son client attend d'abord la libération du contexte de requêtes
et l'instrumentation : déplacer une annulation juste avant cet appel ne
supprime donc pas toute fenêtre intermédiaire. Retirer les routes avec
`unrouteAll` retire leur interception ; cette voie n'est pas retenue pour
une sonde dont elles assurent le confinement. Hypothèse ciblée : laisser les
GET autorisés passer pendant l'export de trace sur le parcours nominal,
en conservant le déblocage immédiat d'une DELETE tenue sur échec ou interruption.
Ces sources ne prouvent ni la cause des consoles observées ni le succès
de ce changement ; tests discriminants et recette restent requis.

## R15S55 — diagnostic final de la sonde modale

Sources officielles consultées par B le 4 octobre 2026 à 10:58–10:59 UTC,
puis relues par ROOT à 11:27 UTC ; version applicable Playwright 1.63.0.

| Référence officielle | Apport | Limite |
| --- | --- | --- |
| [Page.request/requestfailed](https://playwright.dev/docs/api/class-page#page-event-request-failed) et [Route.request](https://playwright.dev/docs/api/class-route#route-request) | Événements et route exposent une Request ; une réponse HTTP d'erreur n'est pas un échec de transport. | Une identité objet reconnue observe la tentative d'abort et l'événement ; elle ne démontre pas la cause exclusive de l'échec. |
| [ConsoleMessage](https://playwright.dev/docs/api/class-consolemessage) | L'API documentée n'expose pas d'identité Request. | La cooccurrence page/phase ne prouve pas la cause d'une console. |
| [Types officiels du tag v1.63.0](https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/packages/playwright-core/types/types.d.ts), confrontés par B aux types installés | Signatures applicables aux dépendances verrouillées. | Ni navigation ni transport réels exécutés lors de cette consultation. |

Sources internes : remise B `33a6aeda…`, diff et inverse exacts de la sonde,
13 tests purs PASS et rouge conservé ; avis indépendant A `01fb56e1…` /
`432bd3bf…`, lu et accepté ROOT. La projection ajoutée est bornée à 64 événements,
sans texte, URL ou contenu réseau ; les erreurs console restent fatales.
Le [journal](journal/2026-10-04.md#publication-documentaire-et-intégration-du-lot-frontend-relevé-1129-utc)
identifie les preuves privées. Ce complément préparatoire ne résout pas la
cause historique, ne qualifie pas F01 et n'autorise aucun démarrage.

## R15S54 — nouveaux 31 sur F01 et frontières de liaison modale

Sources internes relues ROOT puis A le 4 octobre 2026 jusqu'à 11:05 UTC ; aucune
nouvelle API externe ou montée de version. Les commandes, chemins et limites
sont au [journal des 31](journal/2026-10-04.md#recette-des-31-sur-f01-et-préparation-modale-relevé-0839-utc)
et à la [revue terminale et validation bornée F02](journal/2026-10-04.md#revue-c-terminale-et-validation-bornée-f02-relevé-1105-utc).

| Source examinée | Apport vérifié | Limite |
| --- | --- | --- |
| Préparation31 A `83ba7e2b…`, contrôleur `ee4fb5b3…`, revue B `fd289aea…` ; copie réelle, freeze `e093c06b…`, verrou988refs `ab2a21cd…` et revue postcopie C `869b4270…` | Deux deltas F01 exacts, 249 sources/13 ingestion, 697 copies et quatre liens autorisés ; réemploi explicite de l'export réel243/6 537 094 octets, pas de build pendant native31. | Les tests purs et la copie ne donnent pas un PASS natif ; copies et marqueurs nommés seulement. |
| Trois terminaux `bbd57a30…` / `15545290…` / `d7416718…`, retour réel ROOT `2701/d0aaa7 EXIT0` | 31 stricts parmi42 collectés, sept groupes/une tentative/retry0 ; primaire nul, restaurations et verrous PASS. | Onze génération/lifecycle NOT_RUN ; doubles éditoriaux/session/service distingués, pas31 intégrations complètes. |
| Avis final C `7a2aa737…`, metadata `4c625d36…`, reçu ROOT `356c176e…` ; contrôle physique ROOT `372815 EXIT0` | Arrêt nommé118 QA/quatre HOST, SQL QA neuf ready/complete/attempts1/query0, conservation bornée, 47 originales vues par C/72 inventoriées ; dix vues ROOT. 72 SHA/dimensions PNG et31 records terminaux recontrôlés ROOT. | Les absences gardent leur date ; aucun rajeunissement de clearance. Descendants inconnus non inventoriés ; pas de raw auth/log/trace ou payload SQL. C ne requalifie pas indépendamment toutes les primitives historiques qu'il a écrites. |
| Capture `canvas-budget-zoom-300.png` `7bb210ba…`, test `canvas-budget.spec.ts` et revue C | Test d'allocation/libération PASS ; capture page11/14, zoom300 et zone papier blanche visibles. | Ne prouve pas la peinture achevée ni les ancres Q05 ; pas de bug de peinture déduit d'une image isolée. |
| Préparation modale A `579624f2…`, source_rebind `06af588c…`, probe `a408c4fc…`, avis B `6430c122…` / metadata `10793185…` | 16 témoins Python/10 Node, inverses exacts et guards maintenus ; sonde entière inchangée, nouvel attendu ConfirmDialog explicite. | Source-only PREPARED_NOT_BOUND : pas de cible, owner, execution-lock, clearance, copie ou appel natif. B relit l'incrément A, pas son propre produit ni son ancien C3. |
| Complément A `53e3c920…`, entry `4c682163…`, verrou `3bf79fe3…` ; vrais corps C3 `qualification/assembled`, replay `verify_target:118–130`, first `lockcheck:77–86` et `FIX:33–37` | Trois frontières dérivées/inversées : attestation C exacte à six champs, 19 paths/SHA sous `visual/` et deux pins F01 du module first frais. 36 tests purs verts et trois refus historiques attendus conservés ; 888 actifs/254 différés, deux seuls records ROOT remplacés. | Tests avec transports déclarés doublés, pas un PASS natif. Locks historiques, vrais SHA/read, CSS et autres pins inchangés ; aucune capture déplacée ni faux alias C→B. |
| Revue non-auteur B `confirm-focus-modal-binding-review-B-20261004/REVIEW.md` `6c962b67…` / metadata `19db2c1b…`, acceptée ROOT `5a4700/f27da6` | Lecture complète et contrôles des 21 pièces privées, records/inverses/gate et XML ; avis favorable borné au nouveau complément A. | B est auteur du correctif produit et C3 historique : cet avis ne les requalifie pas indépendamment. Aucun appel natif, lecture DB/runtime ou image par B. |
| Preuve ROOT `modal-source249-ROOT-20261004/MODAL_F01_PREPARATION.md` `4e9d4f65…` ; terminal prepare `4695/73833f EXIT0`, contrôle physique `96935c` | Prepare réel : baseline `12d4a834…` et cible `72d0c798…` liées à l'arrêt31 ; 17 copies (7 MJS, 1 README, 9 métadonnées historiques) plus cible, 18 fichiers physiques 0600/nlink1. | Pas 17 fichiers de code ni copie de storageState. Cette phase seule n'a lancé ni up, auth, HTTP, import ou build ; la recette ultérieure est distincte. |
| Revue C postprepare `confirm-focus-modal-postprepare-C-20261004/REVIEW.md` `a3aea4cd…` / metadata `4a7393e3…`, acceptée ROOT `f9614c/31268b/4ae90f EXIT0` ; lancement ROOT `9a8763/session19964` | Copies/cible, état QA arrêté, 118 absences strictes fraîches et DB/source/export dans la portée C conformes. Recette lancée ; checkpoint rb-start à 09:27:11.078453, premier collecteur `266a77 EXIT0` après reach, reçu `a63faf7b…` et pointeur `c7f092…`. | Cette revue porte sur l'état avant up, pas sur le dernier arrêt après recette. Elle ne donne pas un PASS modal ; la clôture suivante est distincte. |
| Preuve ROOT `modal-source249-ROOT-20261004/MODAL_F01_NATIVE_FAILURE.md` `4879be0c…`, relue et rehashée A ; terminal `19964/b88958 EXIT2` à 09:29:07, résumé `9267a58f…` et terminal-source249 `559a65fa…` | FAILED avant rb-browser/modal-probe après trois clearances postcheckpoint. Diagnostic source ROOT `c53791/43dc9e`, log lu seulement ROOT `49c304` : `guards.mjs:9` dérive QA depuis `HERE/../../..` ; la copie sous `evidence-review/…/complement-binding-20261004/regression-browser/` place cette racine dans `Q/evidence-review`, donc le PROGRAM sous `Q/frontend-quality` est refusé en ligne 71 : `program_outside_qa`. ROOT confirme 14 absences exactes fraîches à 09:33:51.175706, dernier owner arrêté `71104a2a…` / runtime `dc8d70b8…` et conservation `365cb9e0…` identique. | Bug d'implantation du harnais QA, pas un défaut produit ou un échec de cas navigateur. Auth QA neuve exécutée, aucune capture ; A n'a lu que le rapport sanitizé, pas le log, l'auth, le runtime ou SQL. Revue C du nouvel arrêt encore attendue ; ancien stop31 désormais historique. |
| Incrément B `frontend-focus-fix/modal-f01-canonical-latest-stop-20261004/`, remise `fd1d1c77…`, verrou `284ff2bb…` ; avis non-auteur A `confirm-focus-modal-canonical-review-A-20261004/REVIEW.md` `be04df23…` / metadata `c0ff7e31…`, accepté ROOT `bd44a2/1dd06e` | Topologie canonique pour les guards inchangés et séparation entre qualification31 historique b1 et dernier arrêt711. Inverses/restaurations relus, 27 pièces privées, 918 actifs dont 888 records hérités exacts, 254 différés ; 37 Python/cinq Node purs PASS, rouges et montages séparés. | Les transports des tests sont explicitement doublés ; A relit le nouvel incrément B, pas sa propre base A ni le produit B. Les cibles héritées ne sont pas ouvertes ou rehashées par cette revue. Aucun PASS natif déduit. |
| Preuve ROOT `modal-source249-ROOT-20261004/MODAL_F01_CANONICAL_PREPARATION.json` `21ed1e78…`, observée à 10:26:08 UTC, lue entièrement et rehashée A ; prepare `19138/4ab472 EXIT0` | Baseline réelle `3d570e03…`, cible `72d0c798…`, 17 copies (7 MJS, 1 README, 9 métadonnées historiques) plus cible. Vrai options() de la copie `f1f29b` PASS collection-only. Lecteur ROOT `d24829` erroné sur Q700 corrigé par `5dafdb` : Q775 inchangée, seuls parents privés700 jusqu'à frontend-focus-fix, aucun guard natif modifié. | PREPARED_NOT_NATIVE_RUN : ni nouveau up/auth/HTTP/browser/build/import par ce prepare, aucune clearance ou recette nouvelle. Revue C postprepare EN_COURS au relevé ; arrêt711 non transformé en qualification modale. |
| Preuve ROOT `modal-source249-ROOT-20261004/MODAL_F01_CANONICAL_FAILED_OPERATOR_REVIEW.json` `80d4c9f8…`, revue à 10:55:04 UTC, lue entièrement et rehashée A ; recette `5924/e4f5ce EXIT2` close à 10:43:53, résumé `6e3add26…`, terminal `d6a5f6c7…` | Cinq clearances postreach réelles ; cinq cas RB stricts PASS/sans retry, skip ou flaky, résultats `bd28163e…`. Sonde `bedcfc7d…` FAILED à FINAL_VALIDATION/AssertionError malgré trois nominales et le scénario pending, primaire nul. ROOT voit cinq originales : titre entier aux trois tailles, focus nominal/pending et récupération visibles. 34 absences exactes ROOT à 10:53:56.202519, arrêt courant `5278b261…` / runtime `054e834b…` ; conservation avant/après `365cb9e0…` identique dans sa portée. | Deux consoles tardives non classées comme 400 simulées `45427d24…` et deux GET de cleanup abortés : ROOT infère `final_unexpected_console_error`, causalité inconnue. Aucun bug produit ou faux positif déduit, aucune qualification F01 ou globale. Revue C terminale encore en cours ; A lit le reçu, pas les PNG, auth, logs, runtime ou SQL. |
| Revue C `confirm-focus-modal-canonical-terminal-C-20261004/REVIEW.md` `4e6dcb55…` / metadata `1d5a9b74…`, close à 11:01:00.256850 UTC ; lue entièrement et rehashée A, acceptée ROOT à 11:04:24 (`244b9a/e66765`, physique `9c5033`) | Absences exactes des 34 QA et quatre HOST à 10:55:22.685472–10:55:22.688036 ; SQL QA neuf ready/complete/tentative1/query0 et conservation bornée close à 10:56:52.537077. Cinq mêmes PNG originales vues ROOT/C, titre entier aux trois tailles et RB5 strict PASS : ROOT valide F02 dans la seule portée du titre. | Modale et run toujours FAILED, F01 ouvert ; assertions clavier rapportées par le résultat réel, pas prouvées par les images seules. réponse HTTP 400 simulée à la DELETE, aucun retrait backend. A n'a lu que ces deux preuves closes ; ni mesure PID/SQL ni image par A, pas de qualification indépendante des primitives écrites par C. Aucun cache relu ou intégrité exhaustive revendiquée. |

Complément relu ROOT à 09:48 UTC : revue C du dernier arrêt
`confirm-focus-modal-failed-stop-C-20261004/REVIEW.md` `caa6d436…` /
metadata `142656fa…`, entièrement lus (`256032/444228`) et contrôlés
physiquement (`d2d1cf EXIT0`). Arrêt711/runtime dc8d, union14 exacte,
neuf jobs ready/complete/tentative1, zéro query et conservation bornée conformes.
Le premier lecteur C a hashé en mémoire un cache déclaré metadata-only avant
KeyError, sans digest retenu ou affiché ; le lecteur final reste stat-only pour
les trois caches, sans garantie d'intégrité exhaustive. Écart conservé dans
la revue, aucun FAILED transformé en PASS. Descriptor ROOT séparé format rb
`modal-source249-ROOT-20261004/LATEST_STOP_MODAL_F01_20261004.json`
`bb2fe63d…` : acceptation réelle de cette revue, aucune permission de prepare
ou de recette. La cible31 historique reste b1, le dernier arrêt est711.

Le vrai `options()` reproduit le refus sans natif (`2c2bdb EXIT0`). À profondeur
canonique, il accepte le même PROGRAM/pool et une sortie enfant existante
(`83fb76 EXIT0`), en collection-only sans exécuter la CLI ou lire l'auth.
L'essai de lecteur `ec7557` avec sortie égale à HERE reste refusé : containment
strict, aucun changement de garde. Ces observations ne qualifient pas le
futur placement corrigé ni les cinq cas navigateur.

Les références officielles déjà valides restent celles des skills web/E2E/Linux
et de R15S49/R15S53. Cette reprise ne modifie ni le contrat du dialogue natif,
ni les seuils de la DoD. Les preuves d'exécution ne sont pas remplacées par
les documents, les tests avec doubles ou l'acceptation d'une préparation.

## R15S53 — reprise qualité F01 et diagnostic préparatoire Q05

Sources internes relues le 4 octobre 2026 jusqu'à 07:19 UTC ; les exécutions
et chemins de preuves sont au [journal](journal/2026-10-04.md#qualité-isolée-du-correctif-f01-relevé-0710-utc).
Les avis préparatoires ne qualifient pas un service ou le navigateur.

| Source examinée | Apport vérifié | Limite |
| --- | --- | --- |
| Gels qualité C1 `25383639…` et C-v2 `b23eb515…`, contrôleur `d203d01a…` ; avis B `f9b23b32…` puis `2136ab16…` | C1 peut masquer le primaire lors de close ; le seul delta C-v2 préserve cet objet, distingue le secondaire et conserve un close seul fatal. Inverse entier, quality/gate byte-identiques ; neuf témoins verts sur le vrai delegate avec doubles. | C1 reste refusé, ses vingt tests ne sont pas rejoués ; les doubles ne qualifient aucun arrêt réel et ne localisent pas l'ancien refus OS. |
| Reçus C-v2 unités `379d92a7…`, lint `1af55fa6…`, build `2c6831a4…`, sorties ROOT `afb8d6`, `54242c`, `19f7bd` ; revue indépendante B `b2e738a7…`, metadata `87c8d885…` | Trois EXIT0 réels, 305 cas sans skip, 119 fichiers sans erreur/avertissement ; postchecks sans erreur et même baseline, typage A explicitement réemployé. B rehash les sources, l'export et les ensembles de conservation fermés ; ROOT lit et contrôle la remise. | Avis favorable borné à cette qualité isolée ; ni React DOM natif, ni recette31/RB5, ni DoD globale déduits. |
| Manifeste export `7168111f…`, export-check `1db79234…`, contrôle ROOT `52e0dd` | Ensemble physique exact de 243 fichiers, 6 537 094 octets ; 203 fichiers PDF.js et BUILD_ID liés aux SHA réels. Ressources : 23 échantillons, réserve minimum de 42 482 Mio. | Échantillons espacés d'environ deux secondes, pas pic continu ni qualification sur une machine physique de 16 Gio ; conservation pool/`.next` limitée aux marqueurs existants. |
| E2 `main:299–305`, quality `execute:155,196`, `argv_for:119–120` et `build-run.quality_reports:22` | Le pointeur de clearance doit porter le nom du stage à publication ; ce nom entre en collision avec le rapport ESLint. Publication sous dossier privé puis copie exacte ROOT vers un nom distinct admise par les contrats de lecture, SHA conservé. | Aucun changement des gardes, des heures, des assertions ou du gel ; fraîcheur maximale de 120 s toujours contrôlée avant opération. Le refus de nom initial reste distinct du lint réussi. |
| Diagnostic Q05 B-v2 `cd9eed67…`, verrou `9cb388ea…`, revue C `be4e90fd…` | Inverse B-v1 entier ; comparaison typée et récursive des constantes, rouge discriminant avec un FAIL puis 30 témoins PASS. Sources compilées pour contrôle d'identité, pas exécutées ; 34 anciens tests non rejoués. | Préparation acceptée seulement, aucune liaison ni GO natif neuf ; constantes flottantes comparées par valeur typée, pas par représentation binaire universelle. Sous-prédicat du refus Q05 toujours inconnu. |

Vérification officielle ROOT le 4 octobre à 06:27–06:28 UTC, avant acceptation
du diagnostic B-v2 : Python Software Foundation,
[objets traceback](https://docs.python.org/3.12/reference/datamodel.html#traceback-objects),
[sys.exc_info](https://docs.python.org/3.12/library/sys.html#sys.exc_info) et
[types.CodeType](https://docs.python.org/3.12/library/types.html#types.CodeType).
Sections utiles : `co_consts`, `tb_frame/tb_lineno/tb_next`, triplet
type/exception/traceback et construction des objets code. Documentation de la
branche3.12, interpréteur installé3.12.14 ; aucune montée de version effectuée.
Ces contrats encadrent une observation locale bornée, sans messages arbitraires,
locals/globals/env ou contenu d'authentification. Ils ne reconstituent aucune
cause historique et ne remplacent pas les preuves d'exécution.

## R15S52 — copie F01 et refus d'identité pendant les unités

Lectures internes ROOT le 4 octobre 2026, de 05:41 à 06:24 UTC ;
consultation officielle distincte à 06:08 ci-dessous. Chemins et résultats
au journal, sections de reprise F01 à 06:03 et de typage à 06:24.

| Source examinée | Apport | Limite |
| --- | --- | --- |
| Adaptateur qualité A `9fb94069…`, helpers stage/qualité/build figés, avis C `ee6f40bb…` | Deux records post-fix exacts, réemploi des 247 autres et des gardes HOST arrêté ; cinq phases distinctes avec conservation. | Tests purs avec doubles ; pas une preuve d'exécution. |
| Freeze réel `f76f2660…`, reçus stage et postcopie C `17e42870…` | Copie249/13, inodes distincts, profil CPU et quatre liens conformes, sans ancien export ou auth/data. | Aucun build ni rendu ; pool/`.next` limités aux marqueurs du helper. |
| Reçu unités `b0b61134…`, pile ROOT `7ef94c`, `pilot.py:173,195` | Le refus touche un candidat descendant avant insertion, et non la garde initiale du launcher. | Identité du candidat et cause non consignées ; XML52B non clos, aucun test qualifié. |
| Diagnostic indépendant C `da3d598e…`, metadata `e67ece1c…` | Absence stricte du seul launcher710062 et conservation JSON égale. | Descendants inconnus non inventoriés, aucun total de tests reconstitué. |
| Typage isolé, reçu `5b64ab40…` et terminal ROOT `48a9e8 EXIT0` ; lecture et réhash à 06:24 UTC | PASS réel sur la copie F01, log vide, postcheck sans erreur et snapshot égal au baseline ; cache TypeScript privé hors PROGRAM. | Pas un PASS unités/lint/build ; réemploi futur soumis aux mêmes liaisons exactes, sans reçu fabriqué. |
| `recovery31-v4/controller.py:129–295`, SHA `605fbcf3…`, et V3 `CandidateJournal` | Observation bornée d'un candidat à exécutable attendu vide ; seule absence fraîche exacte peut retourner None, sans appropriation ou signal de l'inconnu. | Son réemploi qualité doit encore être préparé et relu ; aucune causalité de l'échec passé ni réussite future déduite. |

L'alternative Node `--test-isolation=none`, seulement proposée par C à partir
des [CLI24.16 officielles](https://nodejs.org/download/release/v24.16.0/docs/api/cli.html#--test-isolationmode)
et du [modèle de tests24.16](https://nodejs.org/download/release/v24.16.0/docs/api/test.html#test-runner-execution-model),
n'est pas retenue à ce relevé. Ces liens décrivent une option, pas une cause
établie ni une recette exécutée. La préparation retenue conserve les argv et
les assertions actuels ; ancien FAILED et gardes restent intacts.
ROOT vérifie également ces deux sections officielles le 4 octobre 2026,
à 06:08 UTC, avec le skill `official-source-review` : mode `process` par
défaut, contexte partagé en mode `none` et interactions possibles entre
fichiers. L'aide du Node installé expose bien l'option (`b00136 EXIT0`) ;
aucun test n'est exécuté avec elle. Cette vérification justifie le maintien
du modèle d'exécution actuel, pas une hypothèse sur le candidat refusé.

## R15S51 — refus Q05 V2 et récupération native ciblée

Lectures internes ROOT du 4 octobre 2026, de 04:49 à 05:16 UTC. Sources
versionnées et preuves privées fermées ; aucune nouvelle API externe employée.

| Source | Apport constaté | Limite |
| --- | --- | --- |
| V2 `controller.py`, seul delta `Real.frozen_check` ; `delivery-v2.json` `a9a82863…` et revue C `b95e4676…` | Contrat 202 assets plus manifeste, inverse V1 exact, 95 tests purs et 72 pins ; vrai préflight ROOT PASS. | Tests synthétiques ; refus des extras dans l'export, pas inventaire public-only exhaustif. |
| Run Q05 V2, `summary.json` `54ab9eaf…`, cohorte `a99e36a4…`, record start `7ad6873c…` | FAILED avant auth, quatre natifs liés au seul up et onze tuples enregistrés. | Phase/classe seulement : sous-prédicat exact inconnu, aucune capture. |
| Cohorte `live/down`, diagnostic A `d720c861…` et métadonnées `2333cb0d…` | `live` levée laisse current=None ; le nettoyage exige la propriété partielle positive. | La phase d'entrée ne localise pas le refus dans la méthode ; pas de cause OS déduite. |
| `services/runtime/cli.py` dispatch down et `supervisor.py` stop ; sources du PROGRAM vérifiées | Arrêt coopératif par profil/data possédés et marqueur borné au control ; CLI ROOT retour0. | Ce contrôle n'autorise aucune instance étrangère, suppression ou signal direct. |
| Preuve ROOT `NATIVE_Q05_V2_FAILURE.md` `b436eb0d…`, revue C `7d29e8fb…`, métadonnées `38d6d2ae…` | Nouveau owner `c59e67…` réellement arrêté, 12 absences fraîches, DB/query et sources/export/marqueurs bornés conformes. | Original FAILED conservé ; inconnus non inventoriés, corps originals/extractions et caches complets non rehashés par C. |

Les chemins des preuves sont au journal ; ce registre ne recopie pas leur
suivi. Le descriptor `a747094a…` concerne désormais un arrêt antérieur,
pas l'état courant. Aucun résultat Q05, Windows ou DoD déduit de la récupération.

## R15S50 — manifeste PDF.js, assets et fichier de manifeste

Contrat interne relu par ROOT le 4 octobre 2026 après le préflight réel Q05,
jusqu'au relevé 04:36 UTC ; aucune recherche externe nécessaire pour ce schéma
produit par le dépôt. Sources : `apps/web/scripts/prepare-assets.mjs`,
`frontend-quality/run.py:105–127` (`export_check`), manifeste public du PROGRAM
source249 et revue terminale indépendante C `92f54665…`.

Le manifeste énumère 202 assets ; son propre fichier s'ajoute pour 203 fichiers
PDF.js physiques. Le wrapper Q05 V1 exige erronément 203 entrées. Refus réel
`EXPORT243_PDFJS203_REQUIRED`, avant toute action native : preuve ROOT
`Q05_PREFLIGHT_REFUSAL.md`, SHA `47a6bba1…`, liée au journal. V2 doit distinguer
les assets uniques du manifeste séparé sans diminuer les vérifications de SHA,
version, ensemble exporté ou taille. Aucun nouveau rendu n'est prouvé par ce
contrat ni par les anciens 72 tests purs.

## R15S49 — focus initial de la confirmation, défaut observé

Consultation ROOT le 4 octobre 2026, avant modification du composant :
recette C3 terminée à 04:11:42 UTC, résultat fermé lu et capture d'échec
examinée, puis sources officielles lues entre 04:14 et 04:16 UTC. La racine QA
privée et les résultats seront rattachés au journal de cette journée.

| Source et version examinée | Apport | Limite |
|---|---|---|
| C3 `regression-browser/run-root-modal-c3-20261004/modal-probe/result.json`, SHA `045b81cc…`, et `failure.png`, SHA `c3c28a6d…` ; `modal-probe-oracle-diagnosticC/probe.mjs`, `openConfirmation` | L'assertion réelle exige « Annuler » focalisé. Elle échoue à 1366×768 après visibilité du dialogue, avant Tab. Les cinq RB préalables ont franchi leur garde ; aucun DELETE n'a été intercepté ou transmis par la sonde | La cible de focus effectivement active n'est pas exposée dans ce résultat. Le titre est lisible sur la seule capture d'échec ; cela ne valide ni les trois largeurs ni le parcours pending. Échec conservé, pas de PASS modal |
| `apps/web/src/components/ui/confirm-dialog.tsx` et même composant du PROGRAM source249 : effet `showModal`, titre `tabIndex=-1`, branche pending | Le composant ne désigne aucune action pour le focus à l'ouverture nominale ; il focalise explicitement le titre seulement en attente | L'absence de désignation explique un choix laissé au navigateur, pas l'identité de l'élément actif dans l'essai. La correction et sa recette restent à exécuter |
| WHATWG, [HTML Living Standard, placement initial et dialog focusing steps](https://html.spec.whatwg.org/multipage/interactive-elements.html#dialog-focusing-steps), édition mise à jour le 03/10/2026 ; Mozilla, [dialog, accessibilité](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog#accessibility) | L'ouverture native applique les étapes de focus ; l'auteur doit choisir explicitement la cible adaptée à l'action. « Annuler » est la cible nominale retenue ici ; les actions désactivées gardent le titre comme cible statique | Standard courant et documentation, pas preuve de comportement du Chromium installé. Conserver le dialogue natif, la boucle clavier et le retour au déclencheur ; ajouter un témoin unitaire puis refaire le parcours sur un nouvel export qualifié |
| Meta/React, [useRef et transmission au DOM](https://react.dev/reference/react/useRef), documentation 19.3 ; [ref comme prop depuis React 19](https://react.dev/blog/2024/12/05/react-19#ref-as-a-prop), publication du 05/12/2024. ROOT : sections lues à 04:40–04:41 UTC, avant application du correctif | Ref objet assignée par React au nœud DOM, utilisable dans l'effet et non pendant le rendu. `Button` transmet `...props` ; son `ComponentProps<"button">` inclut la ref selon les types 19.3.0 installés, lignes 293/1459/2352/4279 | Le témoin avec `Button="button"` ne prouve pas à lui seul la transmission par le composant réel : typage et recette sur le nouvel export restent requis. Aucun forwardRef, changement de version ou dépendance nouveau |

## R15S48 — cible QA arrêtée et séparation des identités

Sources internes réellement lues pendant la reprise du 4 octobre 2026,
jusqu'au relevé 03:28 UTC, sous la racine QA privée du journal. Les primitives
versionnées PSF/psutil/Linux R15S24–R15S30 et les contrats navigateur déjà
consignés sont réutilisés ; aucun téléchargement ni contrat produit nouveau.

| Source et version examinée | Apport | Limite |
|---|---|---|
| Modale `modal-source249-host-stopped-deferred-pool-v2/controller.py`, SHA `7ef44632…`, verrou `3a46f94b…`, livraison `bca6dd4b…`, tests, delta et avis B | Deux seuls liens différés pnpm nommés exacts, inverse complet vers V1 ; préparation réelle source249 et arrêt31 lié, sans ancien état auth | Treize tests purs et prepare ne prouvent pas le précontrôle du run ; celui-ci a réellement refusé avant checkpoint |
| `rb5-modal-root-v3-composition-v2/controller.py`, SHA `9b0a52ec…`, `composition` ; `replay/controller.py:68–84`, `target_contract` | La composition ajoute le dernier owner aux interdits live ; le contrat rejette aussi ce même owner dans la métadonnée historique arrêtée. ROOT a observé le refus exact `new31_stopped_identity_required` sous le vrai contexte | Bug du dispositif QA, pas du produit. Correction C3 en cours ; aucune garde ou réussite native retirée/reconstituée |
| PSF, [`types.FunctionType`, documentation courante 3.12.15](https://docs.python.org/3.12/library/types.html#types.FunctionType) ; [`func_new_impl`, CPython au tag installé v3.12.14, lignes 669–758](https://raw.githubusercontent.com/python/cpython/v3.12.14/Objects/funcobject.c). B : première consultation 03:28 UTC ; ROOT : 03:32:35–03:32:45 UTC | Le constructeur reçoit code, dictionnaire de globals, defaults et closure ; nouvel objet de fonction avec le même code. Motive une copie locale de namespace pour le seul contrat metadata, sans réduire les globals du replay réel | Les signatures peuvent changer entre versions ; vérifier l'absence de closure/defaults du callee et les invariants du clone. L'événement d'audit n'est pas désactivé. Ce mécanisme reste à tester et relire ; aucune preuve native issue de la source |
| Baseline V2 `9dbbb294…` et cible `9523b7de…`, preuve ROOT `RUN_V2_PRECHECK_REFUSAL.md`, SHA `b076c024…` | Identité historique `d7f13…` égale au propriétaire arrêté initial ; run inexistant et clearances vides après le refus | Pas de nouveau stop, session, rendu ou recette navigateur ; les observations metadata ne sont pas un nouvel inventaire de processus |
| Q05 `paint300-source249-host-stopped/controller.py`, SHA `234bff07…`, README/SOURCES et livraison `0354035d…` ; revue C `490bc34f…`, avis ROOT `ac2a991d…` | Descriptor exact de futur dernier arrêt, six records/cleanup, quatre fenêtres après checkpoint, reprise des corps natifs et diagnostic inchangés ; 19 pièces et 55 pins contrôlés par ROOT | 72 verts sont des tests avec doubles explicites ; aucun dernier arrêt effectif, collector, auth ou PNG Q05 nouveau. Avis préparatoire sans GO |

Les dates, commandes et résultats sont au
[journal](journal/2026-10-04.md#préparation-modale-et-refus-précheckpoint-relevé-0328-utc).
Les anciennes sources et échecs restent conservés ; les documents ne valent
ni preuve d'exécution ni autorisation supplémentaire.

## R15S47 — préparation QA et continuité de l'hôte arrêté

Sources internes lues le 4 octobre 2026 entre 00:09 et 00:18 UTC, sous la
racine privée QA R15 ; aucun nouveau contrat externe ou téléchargement.
Les contrats PSF/psutil/Linux déjà consignés R15S24–R15S30 restent les références
des primitives. Cette lecture ne reconstitue ni l'état d'un ancien processus,
ni un résultat natif absent.

| Source et version examinée | Apport | Limite |
|---|---|---|
| `frontend-lifecycle/execution-source249C/artifact_policy.py`, SHA `652b9def…` ; variante D, SHA `8544bd8c…`, `PYTHON_PARENTS` et `sources` ; gel réel source249 et E05 | Liste C de six parents incompatible avec les sept parents des 86 Python du gel ; ajout fermé `tests/unit` dans D, inverses et refus conservés | Défaut du préparateur QA, pas une correction produit ou une validation des onze scénarios |
| D `prepare_source_dirs.py`, `controller.py`, tests et livraison `b2618f64…`, relus ROOT/A ; reçu réel `a69e65f0…` | Sept dossiers du miroir explicitement lié passent de 700 à 500 après vérifications ; aucun cache, build ou démarrage | Les pures sur fixtures et la lecture du code ne remplacent pas le contrôle postpréparation du miroir, effectué séparément par A |
| `frontend-focus-fix/modal-probe-oracle-diagnosticC/probe.mjs`, SHA `a408c4fc…`, diagnostic, tests, inverse et livraison `3e2738c3…`, relus ROOT/B | 26 oracles constants, projection fermée et primaire/cleanup distincts ; reconstruction complète du callee original `09686d5a…` | 38 tests sur doubles explicites, sans navigateur ; dernière assignation d'oracle, pas cause du FAILED historique |
| `host_clearance.py`, `collect` 41–65 ; `frontend-pilot/pilot.py`, `gate_proofs` 83–106 ; F04 D `clearance_check` 176–195 et `checkpoint` 542–546 | La porte historique lie corpus et HOST74 en fonctionnement ; elle ne peut attester HOST81cb arrêté. Motive une variante QA distincte avec corpus historique conservé et état actuel honnête | Aucune nouvelle clearance ou recette délivrée par cette analyse ; ne pas modifier les faits historiques ou fabriquer une disponibilité |
| Reçu d'arrêt ROOT `user-GPU-stop-result-20261004.json`, SHA `c7e89046…` ; preuve indépendante A `bfad6abc…` | Stop demandé, sortie 0 et quatre tuples strictement absents à leurs dates ; l'hôte doit rester arrêté | Preuve datée et bornée à quatre identités ; comptes/conservation lus par ROOT, sans deuxième SQL par A ; ni absence exhaustive future ni preuve DoD |
| E `host_stopped_gate.py:233`, remise `0df2470c…` et pins D/E ; métadonnées physiques de `frontend-pilot/pilot.py`, contrôlées ROOT puis B à 00:59:20 UTC | Le chargeur exige `600`, alors que le fichier et les pins hérités indiquent `664` avec le même SHA `feba91af…` ; explique le refus réel du premier collecteur avant import et Process | Les 61 pures et les avis préparatoires avaient manqué cette contradiction. Correctif E2 requis, sans chmod historique ni acceptation permissive de deux modes ; aucun scénario natif commencé |
| E2 `host_stopped_gate.py`, SHA `2fb59c2e…`, `test_guard_mode.py`, seal et remise `97981c81…`, relus ROOT/B/A | Seul mode GUARD changé en `664` strict ; vrai loader sur octets figés, onze témoins et inverses. Références E inchangées, correction sans chmod ancien | Preuves préparatoires distinctes de la première collecte réelle puis du parcours natif lancé par ROOT ; imports/génération ne se déduisent pas du code ou du vert pur |
| E2 `run-F04-host-stopped-guard-mode-20261004/summary.json`, SHA `6c2a4081…` et ses onze résultats ; `evidence-review/F04-E2-B-20261004/terminal.json`, SHA `f69fa52f…`, lus ROOT/A après le terminal | Onze résultats stricts et deux arrêts, absence datée des PID consignés, conservation des sources et des fichiers nommés ; correction QA réellement traversée | Trois exécutables historiques vides non reconstitués ; B ne relit ni SQLite ni les originaux/extractions de la QA. Les déclarations CLI et les comparaisons fermées ne sont pas une deuxième inspection SQL |
| `evidence-review/F04-E2-C-20261004/REVIEW.md`, SHA `e277dc28…`, dix PNG originaux et blocs synthétiques liés ; relecture ROOT de `lifecycle.spec.ts:207–260`, SHA `5fa69b8b…` | Carte corrompue propre au fichier ; citation enregistrée et spans recomputés ; deux captures de versions identiques expliquées par le véritable ordre des assertions | Spans de bloc entier, révision réemployée, pas de capture distincte de la nouvelle version. C a écrit le correctif de gate : indépendant du rendu natif, pas de son propre code |

Le complément du 4 octobre à 00:59 UTC confronte le callsite neuf à la
métadonnée physique et aux records hérités, pas à une supposition documentaire.
Le numéro de cette section est `R15S47` : `R15S36` reste réservé à sa référence
historique sur le binding et le contrat Node.js.

La lecture post-exécution s'étend jusqu'au relevé du 4 octobre à 01:57 UTC.
Les rapports de l'opérateur et des vérificateurs restent distincts ; les
dates et les commandes effectivement exécutées appartiennent au journal.

Les preuves et dates d'exécution sont au [journal du 4 octobre](journal/2026-10-04.md).
Le registre conserve les sources ; il ne remplace ni le suivi canonique, ni les
rapports privés, ni leurs garde-fous d'exploitation.

**Révision documentaire :** 29 septembre 2026, complétée par des sections datées ; relevé historique des ajouts au 2 octobre 2026 : sources de l'accélération GPU examinées le 1er octobre (W024, W025), puis sources et outils du chantier Linux consignés après l'audit D10/D11 (LNX21, LNX22, J8S01, J8S02, TOOL01 à TOOL03), et consultation actuelle des releases et avis de sécurité de trois dépendances Linux (D11S01–D11S08). Les décisions de ce dossier restent des choix de conception, non des résultats certifiés par les éditeurs. Les versions de production doivent être verrouillées séparément ; une documentation sur `main`/`master` ne constitue pas un verrou logiciel. Les consultations du 3 octobre (frontend, psutil, Linux, PSF, WHATWG, CSSWG et Node.js) figurent dans leurs sections datées ci-dessous.

## Références

### R23S01 — modèle Qwen 3.5 2B et quantification explicite

Ollama : [fiche du tag 2B Q4_K_M](https://ollama.com/library/qwen3.5:2b-q4_K_M),
[métadonnées de sa couche modèle](https://ollama.com/library/qwen3.5:2b-q4_K_M/blobs/7a3a8d553821)
et [fiche du tag court 2B](https://ollama.com/library/qwen3.5:2b).
Producteur Qwen : [fiche Qwen3.5-2B, Quickstart et entrée texte seule](https://huggingface.co/Qwen/Qwen3.5-2B).
Sections directement consultées par l'intégrateur le 03/10/2026, relevé à
10:05 UTC pour la demande d'ajout au plan ; pages courantes, dates de publication
exactes non établies. Contrat du runtime local : Ollama 0.35.0 dans le verrou,
compatibilité native avec ce nouvel artefact non exécutée.

Faits documentaires : le tag explicite 2B porte Q4_K_M ; le tag court porte
Q8_0 à cette consultation. La fiche Qwen indique un modèle multimodal et le
mode non-thinking par défaut du 2B. L'intégration RAG reste texte seule et
conserve `think=false` explicitement. Ni la taille de fichier publiée, ni les
benchmarks du producteur ne prouvent une consommation mémoire, une latence
ou une qualité sur ce projet. Un tag mobile ou un identifiant abrégé de page
ne remplace pas les digests complets à verrouiller lors de la préparation.

Observation locale distincte : `config/local16.yaml` et
`config/models.lock.json` n'identifient que la source 4B et sa variante texte ;
`services/runtime/cli.py` contrôle l'identité des modèles du profil et la
quantification via `_model_record`. Ces lectures soutiennent le statut
NOT_STARTED au relevé du 3 octobre de [R23](PLAN.md#r23--choix-du-modèle-de-génération-et-défaut-qwen-35-2b),
pas une impossibilité du 2B. Aucun modèle téléchargé, profil modifié ou essai
de génération effectué lors de cette inscription. Compatibilité tokenizer,
template, dérivation texte, identité, admission et qualité restent à tester.

### R15S46 — census du lanceur de géométrie

Référence locale fermée : pilote gelé `frontend-pilot/pilot.py`, fonctions
`command`, `remember_descendants` et `verified_owned`, et preuve Recorder
`primary_exception-c197e2452a4d46b58ecdb07280177ad9.json` du run
`strict-final`. Consultés le 3 octobre 2026 par ROOT et A après sa clôture ;
versions et empreintes exactes dans le
[journal du diagnostic](journal/2026-10-03.md#refus-du-lanceur-de-géométrie-relevé-2249-utc).
Le relevé situe le refus sur le lanceur du groupe de géométrie, mais ne
contient ni l'exécutable observé, ni le retour Popen, ni le statut zombie.
Il ne prouve donc pas une course de terminaison. Les contrats officiels
Popen et d'absence stricte restent ceux de R15S44 ; leur application aux
argv collectés exige ses propres contre-tests et sa recette native.

### R15S45 — schéma réel du reçu de démarrage QA

Référence locale, pas publication externe :
[émetteur du reçu d'instance](../tools/qualification/e2e_instance.py),
lignes 64–66, SHA `222a5654dd404573db401f5c1eedb2382519ee15494f6b7689500c0c55e69939`,
base publiée `45e8482`. Code relu directement par ROOT le 3 octobre 2026
vers 22:12 UTC ; métadonnées fermées du run `terminalA` lues par ROOT/A/B
après sa clôture à 22:05:53. L'émetteur écrit `status`, `root`, `profile`,
`origin`, `token_file` et `base_profile` ; il n'écrit pas `instance_id`.
Le chemin `token_file` est une métadonnée : aucune lecture du contenu du
fichier dans ces revues.

Le contrôleur C scellé `3ad5d233…`, fonction `strict_final` ligne 466,
demande pourtant `saved.instance_id`. Une `KeyError` est effectivement
levée après les 31 résultats stricts et l'arrêt ciblé réussis ; composition C
et attestation A `FAILED` conservées.
Le pin pidfd et le registre runtime fermé portent le même identifiant
`88bc104487584a8187627d42f155d5f6`, le profil `5959730d…` et les quatre
tuples PID/naissance/exécutable concordants. Ces records établissent la
liaison à contrôler ; ils n'autorisent ni un champ inventé dans `saved`,
ni l'appropriation d'une instance, ni la qualification rétroactive du run.
Références privées exactes et contrôles postérieurs dans le
[journal du terminal](journal/2026-10-03.md#recette31-terminale-et-défaillance-du-contrôle-de-schéma-relevé-2219-utc).

### R15S44 — terminaison du lanceur possédé et absence stricte

Python Software Foundation : [Popen.poll et wait, documentation 3.12](https://docs.python.org/3.12/library/subprocess.html#subprocess.Popen.poll),
[implémentation POSIX au tag v3.12.14](https://raw.githubusercontent.com/python/cpython/v3.12.14/Lib/subprocess.py).
Sections lues par A entre 21:18 et 21:20 UTC puis directement par ROOT
entre 21:20 et 21:21 UTC le 3 octobre 2026, avant tout correctif du refus
d'arrêt de la nouvelle recette31. Le guide courant est en 3.12.15 ;
l'interpréteur local reste 3.12.14. `subprocess.py` installé relu à
1973–2005, SHA `85d29b2bf0249f5436838298c9a60ee93508b1102e9ac43b001f8a7e7ae8f375`.

`poll()` vérifie la terminaison de l'enfant de son objet Popen et renseigne
returncode ; la voie POSIX utilise waitpid sur ce PID et WNOHANG. Le cas
ECHILD peut produire returncode 0 sans statut récupéré : ce seul code ne
prouve donc pas une identité ni une absence stricte. Une proposition de
correction doit rester liée au Popen original, puis exiger séparément un
constructeur frais levant NoSuchProcess de type exact pour le même PID et
`pid_exists(...) is False`, selon R15S26. Aucun signal, adoption ni décès
déduit d'un exécutable vide ou différent. Ces références ne reconstituent
pas l'état physique du launcherdown à 21:12:36 : la pile ne prouve que le
refus de sa comparaison d'exécutable. Cause fin de vie/zombie/exec encore
inconnue ; proposition, test reproduisant le callsite et revue restent requis.

### R15S43 — oracle de la carte du fichier en erreur

Microsoft/mainteneurs Playwright :
[filtrage par descendant](https://playwright.dev/docs/locators#filter-by-childdescendant)
et [assertions automatiques](https://playwright.dev/docs/test-assertions#auto-retrying-assertions).
Guides courants non versionnés lus par B à 20:23:48 UTC, puis sections
directement lues par ROOT à 20:25 UTC le 3 octobre 2026. Signatures
`Locator.filter`, `has`, `hasText` et `toHaveCount` confrontées aux types
locaux Playwright 1.63.0 ; fichier `playwright-core/types/types.d.ts` du
pool verrouillé, empreinte déjà consignée dans R15S42.

Le locator `has` est évalué depuis l'élément extérieur, pas depuis la page ;
il doit donc désigner un descendant relatif. La cardinalité et le texte
doivent être attendus par des assertions asynchrones, sans `.first()` qui
masquerait un doublon. Application à l'oracle F04 : carte du document
courant dans le Suivi, nom exact, carte unique, propre message non vide et
visible ; code d'erreur toujours contrôlé par l'API, sans imposer son
affichage absent du produit. Un test avec doubles ne prouve ni le DOM
réel ni le parcours natif ; ces contrôles restent à exécuter.

### R15S42 — isolement réseau et fermeture du contrôle de rendu

Consultation directe ROOT du 3 octobre 2026, entre 19:21 et 19:24 UTC,
avant exécution du navigateur E04/E05. Versions locales vérifiées :
Playwright et playwright-core 1.63.0, Node 24.16.0. Sources officielles :
[BrowserContext.routeWebSocket](https://playwright.dev/docs/api/class-browsercontext#browser-context-route-web-socket),
[WebSocketRoute.close et connectToServer](https://playwright.dev/docs/api/class-websocketroute),
[déclarations au tag v1.63.0](https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/packages/playwright-core/types/types.d.ts),
[HTTP server.close, Node v24.16.0](https://nodejs.org/download/release/v24.16.0/docs/api/http.html#serverclosecallback)
et [net.Server.close, même version](https://nodejs.org/download/release/v24.16.0/docs/api/net.html#serverclosecallback).

Les routes WebSocket doivent être posées avant les pages ; elles ne se
connectent pas au serveur sans appel explicite de connexion. La recette
les refuse, sans `connectToServer`, en plus des routes HTTP. Les guides
courants ne figent pas le paquet : signatures `routeWebSocket` et `close`
confrontées aux déclarations installées du pool, SHA
`2806f6d7810fba0306066d500cd716a6d1128d90af2c3cf71723e3ea0a8904c4`.
Pas d'identité globale annoncée entre le fichier installé et le tag distant.
`server.close` attend la fin des connexions ; son callback peut recevoir
une erreur. La fermeture et les drains sont donc bornés et leurs échecs
participent au verdict. Cette lecture ne prouve ni le navigateur futur,
ni une fermeture native, ni une modification du produit ou de ses dépendances.

### R15S41 — message de refus pour une sélection trop longue

FastAPI, code au tag installé 0.142.1 :
[RequestValidationError et errors()](https://raw.githubusercontent.com/fastapi/fastapi/0.142.1/fastapi/exceptions.py)
et [handler de validation](https://raw.githubusercontent.com/fastapi/fastapi/0.142.1/fastapi/exception_handlers.py).
Guide officiel courant : [remplacement du handler de validation](https://fastapi.tiangolo.com/tutorial/handling-errors/#override-request-validation-exceptions).
Pydantic, documentation au tag installé v2.13.5 :
[ErrorDetails et traduction](https://raw.githubusercontent.com/pydantic/pydantic/v2.13.5/docs/errors/errors.md)
et [erreur too_long](https://raw.githubusercontent.com/pydantic/pydantic/v2.13.5/docs/errors/validation_errors.md).
Sections ouvertes par B entre 18:14 et 18:20 UTC, puis directement par ROOT
entre 18:21 et 18:23 UTC le 3 octobre 2026. Versions installées et verrouillées
vérifiées : FastAPI 0.142.1, Pydantic 2.13.5, pydantic-core 2.46.5.
L'accès B à docs.pydantic.dev/2.13 a échoué ; le tag officiel est la source
effectivement lue, pas une consultation réussie de cette page.

FastAPI expose les erreurs de validation et autorise un handler personnalisé ;
son handler standard répond 422. Pydantic distingue type/loc des valeurs input,
msg et ctx ; une liste dépassant max_length produit too_long. Le chemin
imbriqué permet une traduction fermée, pas l'interprétation de tous les
value_error. L'exemple de traduction de l'éditeur ne justifie pas de renvoyer
les valeurs ou exceptions entrantes dans le texte affiché.

Application E05 proposée avant test : traduire uniquement le couple
body.scope.documentIds / too_long par une phrase fixe indiquant la limite
et l'action de réduction ; repli fixe pour les autres erreurs, sans input,
msg, ctx ni str(error). Conserver statut 422, code validation_error,
details.fields et request_id. La limite du schéma concerne les 1 000 éléments
de la liste, pas la capacité du corpus ni un nombre de documents uniques.
Test discriminant à exécuter sur ASGI isolé : 1 000/1 001 éléments, vraie
validation Pydantic, champ/type inconnus et absence des valeurs sensibles.
Aucun refus runtime observé à cette consultation ; résultats au journal.

### R15S40 — diagnostic fermé des assertions et rejets QA

Node.js : [événement unhandledRejection, version 24.16.0](https://nodejs.org/download/release/v24.16.0/docs/api/process.html#event-unhandledrejection)
et [retrait d'un listener, même version](https://nodejs.org/download/release/v24.16.0/docs/api/events.html#emitterremovelistenereventname-listener).
Microsoft / Playwright : [assertions](https://playwright.dev/docs/test-assertions)
et [source documentaire au tag installé v1.63.0](https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/docs/src/test-assertions-js.md).
Sections directement consultées par ROOT le 3 octobre 2026, entre 17:15 et
17:17 UTC ; la page Playwright courante est distinguée du tag installé.
Cette consultation complète celle de R15S39 ; elle ne précède pas l'essai V2.

Node émet l'événement lorsqu'un rejet n'a pas reçu de gestionnaire dans un tour
de boucle. Le retrait vise le callback enregistré ; il ne retire pas les
listeners étrangers ni un événement déjà en cours. L'écouteur temporaire QA
compte tout rejet observé comme fatal et est retiré après fermeture et drainage.
Ces mécanismes ne prouvent ni l'absence de callbacks futurs ni l'arrêt des PID.
Les assertions Playwright sur locators sont asynchrones et doivent être attendues ;
le tag documente un délai par défaut de cinq secondes. Aucun délai ni critère
de réussite n'est changé pour la reprise diagnostique E03.

Observation locale distincte : V2 a conservé `primary=Error` sans sa frame
initiale, avec zéro scénario achevé. Un nouveau helper privé doit consigner
une phase constante avant chaque oracle et des métadonnées fermées, sans lire
de trace, payload API ou fichier d'authentification. Cette préparation ne permet
pas de déduire quel oracle a échoué, ni d'attribuer un défaut au produit.

### R15S39 — contrôle final après fermeture de la sonde QA

Mainteneurs Node.js : [setImmediate, documentation 24.16.0](https://nodejs.org/download/release/v24.16.0/docs/api/timers.html#setimmediatecallback-args)
et [source documentaire au tag v24.16.0](https://raw.githubusercontent.com/nodejs/node/v24.16.0/doc/api/timers.md).
Microsoft : [BrowserContext.close](https://playwright.dev/docs/api/class-browsercontext#browser-context-close).
Sources directement ouvertes par ROOT le 3 octobre 2026 ; consignation canonique
à 15:19 UTC. Node installé : 24.16.0 ; contrat Playwright 1.63.0 conservé et
signatures installées déjà référencées dans R15S38. L'accès initial à
latest-v24.x a échoué ; la page versionnée a ensuite été consultée.

setImmediate programme un callback après les callbacks I/O du tour
d'événements. La fermeture Playwright ferme les pages et peut interrompre
des opérations ; elle n'est pas une preuve d'absence de PID. Le contrôle QA
ajoute un tour Node entre deux drainages après les deux fermetures, puis
revérifie les invariants fatals. Cela ne garantit pas l'absence de callbacks
futurs arbitraires : l'enveloppe doit encore vérifier les identités et l'arrêt.

Preuve locale distincte : C reproduit une requête DELETE tardive bloquée mais encore
qualifiée PASS par l'ancien `execute` de la sonde modale. Correctif ROOT privé : un seul bloc
après fermeture ; 33 contrôles conservés et 13 nouveaux, soit 46 PASS après 11 FAIL contre
V2. Revue C favorable limitée à cette préparation. Aucun DELETE backend,
navigateur ou comportement produit réel démontré par ces doubles. Le
nouvel assemblage, ses préconditions et son rendu restent à qualifier ; voir
le [journal](journal/2026-10-03.md#contrôles-qa-après-fermeture-et-compositions-relevé-1519-utc).

### R15S38 — observations console et fermeture du contexte Playwright

Microsoft / mainteneurs Playwright : [ConsoleMessage, location et type](https://playwright.dev/docs/api/class-consolemessage#console-message-location),
[Route.fetch](https://playwright.dev/docs/api/class-route#route-fetch),
[BrowserContext.close](https://playwright.dev/docs/api/class-browsercontext#browser-context-close)
et [types officiels au tag v1.63.0](https://raw.githubusercontent.com/microsoft/playwright/v1.63.0/packages/playwright-core/types/types.d.ts).
Consultation directe ROOT le 03/10/2026, relevé à13:28 UTC ; pages courantes
distinguées du tag installé1.63.0. Sections utiles du tag : ConsoleMessage
location/type/timestamp, BrowserContext.close/isClosed ; aucune installation.

Le type et la localisation d'un événement peuvent être observés séparément
de son texte et de ses arguments. La fermeture du contexte ferme ses pages ;
isClosed indique une fermeture commencée ou accomplie, pas une absence de PID.
Ces contrats permettent une instrumentation confidentielle, mais ne donnent
ni la cause d'un avertissement passé, ni celle d'une erreur de transport.

Observation locale distincte : Q05/run1315 fournit deux captures candidates,
puis un verdict caller FAILED : warning1 et transportErrors3/guardErrors3.
Le code exige zéro violation avant de rendre le candidat ; ces trois erreurs
ont donc été comptées entre ce contrôle et l'observation finale, fenêtre qui
inclut vérification des captures et fermeture. Leur phase précise reste
inconnue. Aucun texte console, corps, cookie, trace ou journal privé n'est lu.
La préparation suivante doit conserver les refus, ajouter des phases et
métadonnées fermées, puis vérifier sa cause avant toute correction de verdict.
Ni un PNG lisible ni close résolu ne valide la recette ou l'arrêt natif.

### R15S37 — naissance psutil et comparaison temporelle QA

Mainteneurs psutil : [create_time et boot_time, code release-7.2.2](https://github.com/giampaolo/psutil/blob/release-7.2.2/psutil/_pslinux.py),
[source brute officielle](https://raw.githubusercontent.com/giampaolo/psutil/release-7.2.2/psutil/_pslinux.py).
Fonctions directement consultées par ROOT le 03/10/2026 à12:25 UTC ;
version locale7.2.2. La page GitHub initiale ne rendait pas les fonctions
recherchées ; leur code a été lu via la source brute, pas déduit du seul titre.
create_time convertit les ticks starttime, puis ajoute boot_time lu dans btime.
Ce calcul ne fournit pas une mesure identique au time.time préalable du lanceur.

Preuve locale distincte : trois enfants Python créés par ROOT, EXIT0 et
strictement absents, donnent naissance psutil inférieure au temps préalable
d'environ0,5s (reçu43912d83). Le comparateur QA peut donc refuser son propre
enfant neuf. Le started_at historique1155 n'étant pas conservé, son refus
initial reste sans attribution exacte. Une correction doit établir
l'ownership depuis la cohorte exacte du seul start, sans marge temporelle,
appropriation ni retrait des contrôles naissance/exécutable/profil/source.

### R15S36 — chemin binding et contrat de Node.js

Mainteneurs Node.js : [path.dirname, documentation de la version 24.16.0](https://nodejs.org/download/release/v24.16.0/docs/api/path.html#pathdirnamepath).
Section directement consultée par ROOT le 03/10/2026 à 11:29 UTC, après
la reproduction locale et avant l'usage natif de la sonde corrigée.
La version installée est également 24.16.0. Le contrat attend une chaîne ;
une autre valeur provoque une TypeError. La page générale consultée à
11:28 décrit 26.10.0 ; elle n'est pas retenue comme contrat installé.
L'accès initial à la page latest-v24.x a échoué et n'est pas présenté
comme une consultation réussie.

Preuve locale distincte : la préparation V1 remplace le chemin binding
par les métadonnées JSON homonymes. Le contrôle suivant transmet cet objet
à la garde conservée, qui appelle dirname sur le chemin attendu. Le vrai
execute et les gardes V1, avec fichiers synthétiques et navigateur doublé,
produisent la TypeError d'empreinte c589de27… enregistrée dans RB1032,
avant tout appel du double launch. ROOT reproduit séparément la même
empreinte avec dirname et un objet synthétique sous Node24.16.0 à11:18.
Ce rapprochement de source et d'essai ne reconstitue pas une stack native
historique absente. La dérivation privée V2 sépare bindingPath et objet,
sans coercition, fallback ni nouvelle autorisation ; les gardes restent
inchangées. Tests purs, revue indépendante et future recette native sont
des preuves distinctes de cette publication.

### R15S35 — encodage marshal et prévention des caches de recette

Python Software Foundation : [implémentation marshal, CPython v3.12.14](https://github.com/python/cpython/blob/v3.12.14/Python/marshal.c)
et [avertissements de marshal, documentation 3.12](https://docs.python.org/3.12/library/marshal.html).
Consultation directe complémentaire par ROOT le 03/10/2026, entre 10:29 et
10:32 UTC ; version locale 3.12.14, page documentaire courante 3.12.15.
La fonction `w_ref` du code tagué dépend notamment des références vivantes :
un encodage brut ne constitue pas une représentation canonique indépendante
du contexte. La documentation interdit de traiter des données non fiables
comme une entrée sûre à désérialiser.

Preuve locale distincte : le script privé `execution-artifacts-v2/marshal_proof.py`
(SHA `5867d67a…`) compile quatre fois les mêmes octets sans exécuter le code.
Le résultat fermé `marshal-proof-final.json` (`4d6f2b5a…`) constate le même
bytecode mais deux encodages bruts. Aucun cache historique n'est lu, exécuté
ou désérialisé ; ce témoin n'identifie pas le contenu des caches de0914.
La comparaison brute envisagée est abandonnée au profit de la prévention
dans six parents sources d'un miroir neuf, en conservant le refus de tous
les caches PROGRAM. [R15S34](#r15s34--artefacts-natifs-du-miroir-de-recette)
reste la référence pour SourceFileLoader et le marqueur Qdrant ; cette
consultation complémentaire ne prétend pas précéder le travail préparatoire
de A, déjà consigné dans ses sources datées. Ni les publications, ni les
tests purs ne valident les onze parcours natifs.

### R15S34 — artefacts natifs du miroir de recette

Python Software Foundation : [py_compile, branche documentaire 3.12](https://docs.python.org/3.12/library/py_compile.html) et [SourceLoader, sérialisation et écriture des caches, CPython v3.12.14](https://github.com/python/cpython/blob/v3.12.14/Lib/importlib/_bootstrap_external.py). Qdrant : [indicateur de démarrage, v1.19.1](https://github.com/qdrant/qdrant/blob/v1.19.1/src/startup.rs) et [appel au démarrage, même tag](https://github.com/qdrant/qdrant/blob/v1.19.1/src/main.rs). Publications directement consultées par l'intégrateur le 03/10/2026 à 09:20–09:22 UTC, avant toute correction F04. Versions locales confirmées séparément : Python3.12.14 et verrou Qdrant1.19.1 ; la page Python courante décrit3.12.15, le code tagué fait foi pour le détail installé.

SourceLoader peut écrire un cache après compilation ; le format timestamp associe magie, indicateur, date/taille de source et code sérialisé. Le nom est dérivé de la source et du tag d'interpréteur. Ces propriétés permettent de vérifier un cache contre une source gelée ; elles n'autorisent ni l'exécution d'un cache inconnu ni une exclusion globale de tous les fichiers pyc. Qdrant écrit un indicateur vide, par défaut `.qdrant-initialized` relativement au répertoire courant, ou à la cible QDRANT_INIT_FILE_PATH. Cet indicateur ne démontre pas à lui seul la santé ou l'arrêt du service.

Observation distincte : PROGRAM0857 contient après0914 cet indicateur vide et28 caches de services, alors que ses697 copies restent exactes. Le contrôleur QA refuse ces extras. Le superviseur local reconstruit l'environnement des enfants et ne transmet pas PYTHONDONTWRITEBYTECODE ; aucun réglage global ou produit n'est modifié. Une correction QA doit vérifier des chemins et contenus précisément dérivés des sources gelées, refuser les autres artefacts et être testée puis relue ; ces publications ne constituent pas une validation des onze parcours.

### R15S33 — ciblage strict du titre dans le test RB03

Microsoft/mainteneurs Playwright : [Locators — Strictness](https://playwright.dev/docs/locators#strictness), [CSS locator](https://playwright.dev/docs/other-locators#css-locator) et [CSS ou XPath](https://playwright.dev/docs/locators#locate-by-css-or-xpath). Sections directement relues par l'intégrateur le 03/10/2026 à 08:50–08:51 UTC, documentation courante ; cible installée 1.63.0 inchangée, types locaux déjà identifiés dans R15S19.

Une action visant un élément échoue si son locator en résout plusieurs. Les opérations de comptage peuvent en résoudre plusieurs ; first/nth contournent la stricte unicité et ne conviennent pas à cette correction. Le mainteneur recommande les rôles ou contrats visibles plutôt que des chaînes CSS fragiles ; les sélecteurs CSS sont néanmoins supportés. Ici le court sélecteur enfant du titre est relié à la structure réellement lue de PdfViewer, pas à un index arbitraire ni à une suppression d'assertion.

Observation locale distincte : RB0828 échoue au clic de `regression.spec.mjs:245` sur `.viewer-title h2`, deux éléments résolus en mode strict ; `pdf-viewer.tsx:274` rend le titre dans un div direct et DocumentTools, dont le dialogue masqué possède un second h2. Échap et retour du focus avaient déjà passé. Cette source établit le contrat du locator, pas un succès navigateur : nouveau gel QA, témoin discriminant, revue indépendante et rejeu sont requis. Aucun produit, dépendance, build ou ancien résultat modifié par cette consultation.

| ID | Source officielle | Usage et statut documentaire |
|---|---|---|
| S01 | [Ollama — FAQ](https://docs.ollama.com/faq) | Référence conservée de la baseline : variables, rétention, concurrence et cloud ; vérifier la version de runtime au provisionnement |
| S02 | [Ollama — API chat](https://docs.ollama.com/api/chat) | Reconsultée pour cette V2.1 : flux, options et compteurs ; disponibilité des champs à contrôler au runtime |
| S03 | [Qwen3.5-4B — fiche officielle](https://huggingface.co/Qwen/Qwen3.5-4B) ; [distribution Ollama](https://ollama.com/library/qwen3.5) | Fiche Qwen reconsultée ; artefact Ollama exact, digest et Q4_K_M à contrôler, pas de RAM déduite du téléchargement |
| S04 | [multilingual-e5-small — fiche officielle](https://huggingface.co/intfloat/multilingual-e5-small/blob/main/README.md) | Référence E5 conservée : 384D, limites, préfixes/pooling ; artefact ONNX INT8 à produire ou vérifier |
| S05 | [ONNX Runtime — threading](https://onnxruntime.ai/docs/performance/tune-performance/threading.html) | Référence des threads et du spinning ; vérifier les options de la session réellement créée |
| S06 | [Docling — dépôt officiel](https://github.com/docling-project/docling) | Référence du composant, releases/licences à verrouiller |
| S07 | [Docling — options de pipeline](https://github.com/docling-project/docling/blob/main/docling/datamodel/pipeline_options.py) | Référence générale ; ne pas déduire la compatibilité de la seule branche courante |
| S08 | [Qdrant — configuration officielle](https://github.com/qdrant/qdrant/blob/master/config/config.yaml) ; [API création collection](https://api.qdrant.tech/api-reference/collections/create-collection) | Configuration serveur reconsultée : placement mémoire et dépréciations. Le schéma API de la version installée reste à tester séparément |
| S09 | [Next.js — static exports](https://nextjs.org/docs/app/guides/static-exports) | Référence du mode export ; les fonctionnalités serveur restent hors du profil statique |
| S10 | [Mozilla PDF.js — exemples](https://mozilla.github.io/pdf.js/examples/) | Référence du rendu/viewport ; alignement des sélections et surlignages à tester dans l'application |
| S11 | [SQLite — FTS5](https://sqlite.org/fts5.html) | BM25, tokenizers, triggers et tables externes ; SQL local réellement testé dans ce dossier |
| S12 | [OpenAI Codex — AGENTS.md](https://developers.openai.com/codex/guides/agents-md) | Référence des instructions de dépôt, conservée ; ce dossier ne sélectionne pas un modèle Codex via Markdown |
| S13 | [PyMuPDF — README](https://github.com/pymupdf/PyMuPDF/blob/main/README.md) | Référence de la décision historique de ne pas introduire cette dépendance nominale ; inventorier toutes les licences livrées |
| S14 | [Docling — options avancées](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md) | Reconsultée : voie native sans modèles layout/OCR/table, threads du parseur distincts, artefacts locaux |
| S15 | [Docling — pipeline options v2.131.0](https://github.com/docling-project/docling/blob/v2.131.0/docling/datamodel/pipeline_options.py) | Code versionné reconsulté : OcrMode et voies régionales ; ce tag de référence n'est pas déclaré testé comme installation complète |
| S16 | [Granite 97M Multilingual R2 — candidat de l'audit](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2) ; [publication IBM citée par l'audit](https://huggingface.co/blog/ibm-granite/granite-embedding-multilingual-r2) | Accès non reconfirmé pendant cette V2.1. Vérifier avant essai ; aucun score ni artefact CPU ne sont présentés comme vérifiés ici |

## Ce qui relève du projet

Les tailles de fragments, top-k, RRF k=60, budgets de tokens, enveloppes mémoire, politiques d'ordonnancement, métriques de recette et choix des composants sont des décisions explicites. Les sources documentent des mécanismes ; elles ne qualifient pas leur combinaison sur le PC utilisateur.

Les calculs 25 000 × 384 × 4, le contre-exemple RRF et les exemples d'offsets Unicode sont des contrôles de référence reproductibles du dossier, pas des benchmarks éditeurs ni des tests du sélecteur applicatif futur.

Une source inaccessible est notée comme telle. Ne pas la remplacer par une information supposée. Les dates et chiffres comparatifs de l'audit non reconfirmés ne sont pas nécessaires à la réalisation de la baseline E5 ; ils ne sont donc pas recopiés comme faits certifiés.

## Procédure de verrouillage

Identifier la version installée ; consulter son schéma officiel ou son code à cette version ; écrire un test de contrat minimal ; enregistrer commande, version, source et résultat ; produire le manifeste réel. Ne jamais inventer une signature, un digest, une option CLI ou un résultat de performance pour rendre un fichier complet.

Les autres dépendances de la stack conservent leurs sources officielles dans les lockfiles et le registre de licences produits au provisionnement. Aucun jeu de poids, fichier de police ou fichier privé n'est distribué avec ce dossier.


## Sources sur les compétences et leur rédaction — vérification V2.1

Consultation : **29 septembre 2026**. Les pages ci-dessous ont été ouvertes pour cette extension. Leur contenu documentaire ne prouve ni l'installation de compétences ni leur comportement dans un client utilisateur.

| ID | Source officielle | Constat utilisé / statut |
|---|---|---|
| S17 | [Agent Skills — Specification](https://agentskills.io/specification) | Format `SKILL.md`, métadonnées, structure et chargement ciblé vérifiés ; notre procédure reste propre au projet |
| S18 | [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | Principes de descriptions précises, instructions brèves et essais d'usage consultés |
| S19 | [OpenAI — catalogue plugins](https://github.com/openai/plugins) | Catalogue officiel d'exemples ; ne pas supposer que ces plugins sont installés |
| S20 | [OpenAI — ancien catalogue skills](https://github.com/openai/skills) | README consulté : dépôt marqué déprécié et renvoi vers le catalogue plugins ; pas de prescription d'un ancien installateur |
| S21 | [OpenAI — Package your plugin](https://developers.openai.com/plugins/build/plugins) | Documentation d'empaquetage officielle consultée via sa redirection ; aucune installation native effectuée par ce pack |
| S22 | [OpenAI — Build skills](https://developers.openai.com/plugins/build/skills) | Référence officielle actuelle pour structurer une compétence ; exigences du client à vérifier lors de son intégration |
| S23 | [Anthropic — exemples skills](https://github.com/anthropics/skills) | Dépôt officiel consulté ; exemples à tester et licences par artefact ; les skills projet ne sont pas copiés de ce dépôt |

Les URLs directes historiques `developers.openai.com/codex/skills` et `developers.openai.com/codex/guides/agents-md` n'ont pas été relues avec succès lors de cette extension (erreur d'accès). Même limite pour `code.claude.com/docs/en/skills`. Les routes officielles effectivement accessibles sont listées ci-dessus ; ne pas transformer ces échecs en preuve que les fonctionnalités n'existent pas. La référence S12 reste historique, non reconfirmée ici.

Le registre s'enrichit au fil des études selon [RECHERCHE_ET_SKILLS.md](RECHERCHE_ET_SKILLS.md). Il faut enregistrer la date de consultation et la version réelle avant chaque nouvelle décision dépendante, au lieu de présenter cette bibliographie initiale comme une vérification perpétuelle.

## Sources locales de l'inspection des 29 et 30 septembre 2026

L'inspection locale complète le brief sans revisiter ses liens web. Les versions installées sont observées sur le poste, sans nouvelle décision de stack. Les documents privés n'ont pas été transmis à un service externe par les outils d'inspection.

| ID | Source, version et date connues | Apport | Limite |
|---|---|---|---|
| OBS01 | [machine.json](reports/preuves-inspection-2026-09-30/machine.json), Windows CIM/registre, 30/09/2026 00:02:31 UTC | CPU, RAM, SSD, volumes, pagination, WSL et ports réellement observés | Photographie instantanée ; aucun benchmark ou diagnostic SMART détaillé |
| OBS02 | [environnement.json](reports/preuves-inspection-2026-09-30/environnement.json), commandes locales et métadonnées Python, session 29/30 septembre UTC | Versions exécutées, présence PATH, paquets d'un interpréteur et langues OCR | Ni inventaire de toutes les venv ni test de compatibilité applicative |
| OBS03 | [corpus-inspection.json](reports/preuves-inspection-2026-09-30/corpus-inspection.json), SHA-256 et PyMuPDF 1.28.2, 30/09/2026 | Cinq originaux identifiés, 182 pages inspectées structurellement, 24 échantillons visuels, DOCX ZIP/XML | Aucun OCR ; orientation non échantillonnée et qualité extraction métier inconnues |
| OBS04 | [integrite-pack.json](reports/preuves-inspection-2026-09-30/integrite-pack.json), ZIP et manifestes conservés, session 29/30 septembre UTC | Identité des copies du pack, puis distinction des deux mises à jour documentaires locales | Cohérence interne, pas authentification de l'auteur ni validation de runtime |
| OBS05 | [Rapport d'inspection](reports/INSPECTION_DOSSIER_MACHINE_2026-09-30.md), [journal](journal/2026-09-30.md) et brief v1.0 du 29/09/2026 | Interprétation des écarts entre matériel, corpus, logiciels et exigences | Appréciation de faisabilité conditionnelle ; D01–D09 non exécutés |

## Sources Windows et artefacts effectivement examinés — 30/09/2026 UTC

Les versions ci-dessous sont résolues à partir des métadonnées publiques du mainteneur, puis les fichiers ont été vérifiés selon config/artifacts.lock.json. Une URL de documentation explique le contrat ; seuls les rapports locaux prouvent son exécution.

| ID | Source officielle et portée | Observation et limite |
|---|---|---|
| WIN01 | https://docs.ollama.com/windows ; release ollama/ollama v0.35.0, API GitHub consultée30/09 | ZIP Windows amd641461196158octets, SHA256 verrouillé ; modèle encore en téléchargement à01:07UTC, pas d’inférence déclarée |
| WIN02 | https://github.com/qdrant/qdrant/releases/expanded_assets/v1.19.1 ; src/main.rs du tag | Serveur Windows x86-64 officiel et options config/telemetry ; binaire vérifié, démarrage applicatif à venir |
| WIN03 | https://docs.astral.sh/uv/getting-started/installation/ ; https://docs.astral.sh/uv/guides/install-python/ ; release astral-sh/uv0.12.21 | uv et Python3.12.14 isolés, bootstrap offline exécuté ; installation fraîche complète encore à tester |
| WIN04 | https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw ; https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent ; https://learn.microsoft.com/en-us/windows/console/attachconsole | Job kill-on-close, console dédiée et signal ciblé. Test Job enfant/descendant réel PASS ; arrêt réel des services encore à tester |
| MOD01 | https://huggingface.co/intfloat/multilingual-e5-small/tree/main/onnx ; API HF commit614241f622f53c4eeff9890bdc4f31cfecc418b3 | Export INT8 officiel118346824octets, tokenizer et SHA vérifiés ; smoke CPU2x384 PASS, aucune qualité de retrieval acquise |
| MOD02 | https://huggingface.co/Qwen/Qwen3.5-4B/tree/main ; commit851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a | Tokenizer/template/config/licence officiels verrouillés ; comptage local144tokens. Parité template Ollama à qualifier |
| MOD03 | API HF docling-project/docling-layout-heron commit8f39ad3c0b4c58e9c2d2c84a38465abf757272d8 ; docling-project/docling-models tagv2.3.0 commitfc0f2d45e2218ea24bce5045f58a389aed16dc23 | Seuls Heron et TableFormer accurate téléchargés, hashes vérifiés. Contrats lus dans Docling2.131 installé ; OCR/structuré encore en correction |
| OCR01 | https://github.com/tesseract-ocr/tessdata_fast ; commit87416418657359cb625c412a48b6e1d6d41c29bd | fra/eng/osd et licence téléchargés avec SHA blobGit puis SHA256 local ; exeWindows existant copié dans projet, provenance du paquet original non authentifiée indépendamment |
| FIX01 | https://docs.reportlab.com/reportlab/userguide/ch2_graphics/ ; metadata officielle PyPI reportlab5.0.1 | API PDF synthétiques lue ; dépendance dev verrouillée. Les fixtures générées ne sont pas le corpus métier |

Les ouvertures web ONNXquantization et certains chapitres ReportLab ont échoué ; aucun contrat non lu n’en est déduit. Les fichiers/source officiels téléchargés ou installés peuvent établir le contrat de leur version, sans certifier leur statut actuel de sécurité.

## Compléments examinés à 02:00 UTC

Les lignes précédentes décrivent l'état à 01:07 UTC. Depuis : services natifs démarrés et arrêtés exit0, modèle Qwen provisionné puis pilote court réel. Preuves : reports/runtime-first-up.json, runtime-first-down.json, cpu-pilot-short-4threads.json. Aucun PASS de performance finale déduit.

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| WIN05 | [Qdrant snapshot_api.rs v1.19.1](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/api/snapshot_api.rs), ouverte et raw lue le30/09 | Routes création, téléchargement et upload/recovery, priorité snapshot et checksum ; restauration vide exécutée, cas collection peuplée encore à vérifier. Pages actuelles qdrant.tech/api inaccessibles au navigateur, non données comme lues |
| WIN06 | [Ollama api/types.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/api/types.go), [adaptateur llama-server versionné](https://github.com/ollama/ollama/blob/v0.35.0/llm/llama_server.go), binaire verrouillé `llama-server --help` | num_thread/num_batch reconnus ; cache256 Mio/checkpoints2 confirmés par log réel. [common/arg.cpp actuel](https://github.com/ggml-org/llama.cpp/blob/master/common/arg.cpp) consulté comme source actuelle distincte, pas identité du build livré |
| OCR02 | [Tesseract5.4.0 config TSV](https://github.com/tesseract-ocr/tesseract/blob/1be261dc226d49bdcad0ab2fcb10f8395edc1225/tessdata/configs/tsv), commit réel derrière tag | Fichier22octets, SHA25659d079bb75d8b3d7c839a3564580cb559e362c93a9d70f234e421c0c3e767e04 ; première URL objet de tag404 conservée, URL commit téléchargée/vérifiée |
| OCR03 | [Installation officielle Tesseract, Windows](https://tesseract-ocr.github.io/tessdoc/Installation.html), [mainteneur du build UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki), consultés30/09 | L'amont renvoie au build maintenu par UB ; présence de ce canal ne prouve pas encore la provenance de l'installation locale copiée |
| WIN07 | [Microsoft CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), section dwShareMode, ouverte le30/09/2026 à02:28 UTC | Partage lecture/écriture/suppression et renommage ; conflit réellement reproduit par handle sans FILE_SHARE_DELETE. Lecture et écriture atomiques concurrentes corrigées, 2/2 tests Win32 PASS ; aucune modification de permissions système |

## Compléments examinés à 03:55 UTC

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| WIN08 | [Microsoft Maximum Path Length Limitation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation), ouverte30/09, page datée16/07/2024 | MAX_PATH260, chemins étendus absolus et conditions de support ; mécanisme Windows, pas garantie Qdrant. Essai étendu réel FAIL conservé ; aucun réglage global appliqué |
| QDR01 | [Qdrant config v1.19.1](https://github.com/qdrant/qdrant/blob/v1.19.1/config/config.yaml), source raw réellement téléchargée/lue dans .runtime/references/qdrant-snapshot-paths | `storage_path`, `snapshots_path`, `temp_path` existent à cette version. Seuls les deux premiers sont configurés ici ; `temp_path` n'est pas prétendu utilisé. Sources snapshots segment/shard du tag aussi reçues ; ouverture navigateur snapshot.rs échoue, raw versionnée lue |
| QDR02 | [Qdrant memory tiers](https://qdrant.tech/documentation/ops-configuration/memory-tiers/), documentation actuelle ouverte30/09, applicable1.19 | on_disk historique déprécié, tiers froid/cache et mmap ; preuve locale11points dans rapports backend. Index HNSW pas construit à11points, aucune qualification25k déduite |
| MOD04 | [IBM Granite fiche au commit](https://huggingface.co/ibm-granite/granite-embedding-97m-multilingual-r2/raw/835ad14087e140460703cf0fae09f97d469d65c2/README.md), API HF/JSON de configuration au même commit, réponses HTTP officielles reçues30/09 | CLS/L2/384, prefixes vides, ONNX AVX2 officiel/sha/tailles et licence Apache2 déclarée. Lock comparatif distinct ; documentation éditeur ne prouve pas qualité ni débit CPU local. Aucun LICENSE dans les siblings : ne pas inventer un fichier fourni |
| MOD05 | [Ollama ps](https://docs.ollama.com/api/ps), [tags](https://docs.ollama.com/api/tags), ouvertes30/09 par l'agent API | Digest réel vérifié avant /api/chat, CPU/context et quantification contrôlés ;19 tests gateway isolés PASS, pas une génération réelle |

Les fichiers de preuve sous reports et les skills projet portent les exécutions et limites. Les sources actuelles ne remplacent pas le contrat d'une version verrouillée ; les téléchargements du candidat IBM et son inférence sont des étapes distinctes.

## Compléments examinés entre 08:50 et 09:45 UTC

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| OLL01 | [Ollama llm/llama_server.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/llm/llama_server.go), raw téléchargé 30/09 ≈ 08:57 UTC | `NewLlamaServerRunner` (l. 867-895) passe `--mmproj` sur le GGUF lui-même pour les architectures listées (dont `qwen35`) dès que des tenseurs `v.*` existent ; aucune option ne le désactive. `hasMTPDraft` active le décodage spéculatif si des tenseurs `mtp.` existent. Fonde W006 ; code source, pas mesure. |
| OLL02 | [Ollama server/sched.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/server/sched.go) | `disableMmapDefaultReason` : mmap désactivé par défaut sur CPU ; une option `use_mmap` explicite est respectée. Mesure W007 : sans effet sur le GGUF dérivé (correctif de compatibilité). |
| OLL03 | [Ollama parser/parser.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/parser/parser.go) | Commandes Modelfile acceptées : `FROM`, `PARAMETER`, `LICENSE`, `RENDERER`, `PARSER`, `REQUIRES`, `DRAFT`… ; base de l'import `ollama create` du modèle texte. |
| OLL04 | [Ollama server/model_recommendations.go v0.35.0](https://github.com/ollama/ollama/blob/v0.35.0/server/model_recommendations.go) et [envconfig/config.go](https://github.com/ollama/ollama/blob/v0.35.0/envconfig/config.go) | `refresh` retourne avant toute requête HTTP vers `ollama.com/api/experimental/model-recommendations` si `OLLAMA_NO_CLOUD` est actif ; observation des sockets conforme (reports/ollama-recommendations-netwatch-20260930T0909.json). |
| QDR03 | [Qdrant config v1.19.1, section service](https://github.com/qdrant/qdrant/blob/v1.19.1/config/config.yaml) et [src/actix/auth.rs](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/auth.rs) | `service.api_key` : toute requête doit porter l'en-tête `api-key` ; liste blanche de chemins sans authentification définie dans `auth.rs`. Réponse au défaut D08.3 (Host étranger accepté, reports/host-origin-live-20260930T0930.json) ; intégré le 30/09 (W010), voir QDR04. |
| GIT01 | [Git — gitattributes](https://git-scm.com/docs/gitattributes), ouverte 30/09 ≈ 09:45 UTC | « Unsetting the text attribute on a path tells Git not to attempt any end-of-line conversion upon checkin or checkout » : `* -text` fonde W005 (octets hashés préservés malgré `core.autocrlf=true`). |
| UI01 | Référence de forme locale `D:\enhacements\decodair` (dépôt de l'utilisateur, commit `afbf8e305` observé 30/09) | Principes de shell, charte, composants et format du README ; ni métier ni branding repris. Analyse en cours (R16). |
| DOC01 | [Docling backend pypdfium2 v2.131 installé](https://github.com/docling-project/docling/blob/main/docling/backend/pypdfium2_backend.py) (`.venv/Lib/site-packages/docling/backend/pypdfium2_backend.py`, `_rect_to_display_frame`, `get_text_cells`, `get_size`) ; branche principale relue le 30/09 ≈ 14:30 UTC | Les rectangles PDFium sont tournés avec la taille de la CropBox sans retrait de son origine ; fonde la translation de W009. Code source, pas mesure ; revérifier à chaque mise à jour de Docling. |
| QDR04 | [Qdrant v1.19.1 `src/settings.rs`](https://github.com/qdrant/qdrant/blob/v1.19.1/src/settings.rs), [`src/actix/mod.rs`](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/mod.rs), [`src/actix/auth.rs`](https://github.com/qdrant/qdrant/blob/v1.19.1/src/actix/auth.rs), [`src/common/auth/mod.rs`](https://github.com/qdrant/qdrant/blob/v1.19.1/src/common/auth/mod.rs) ; fichiers bruts du tag téléchargés le 30/09 à 16:15 UTC dans `.runtime/references/qdrant-auth/` | Surcharge de configuration par variables `QDRANT__…` (séparateur `__`) ; liste blanche sans clé `/`, `/healthz`, `/readyz`, `/livez` (et l'interface web si son dossier existe, absent ici) ; clé lue dans `api-key` ou `Authorization: Bearer`, absence → 401. Vérifié en réel sur le binaire verrouillé (W010). |
| WIN09 | [Microsoft SetConsoleCtrlHandler](https://learn.microsoft.com/en-us/windows/console/setconsolectrlhandler), page datée 12/07/2018, ouverte le 30/09 à 16:32 UTC | « This attribute of ignoring or processing CTRL+C is inherited by child processes. » Explique l'arrêt console inopérant des enfants d'un lanceur qui ignore CTRL+C ; correction et essais dans le journal du 30/09 (16:30–16:37). |
| SEC01 | OWASP Cheat Sheet Series : [Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [HTTP Headers](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html), [REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html), [Authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) ; pages téléchargées le 30/09 à 16:48 UTC sous `.runtime/references/owasp/` | Entropie d'identifiant ≥ 64 bits, préfixe `__Host-` (Secure, Path=/, sans Domain), délais d'inactivité et absolu selon la criticité, renouvellement à l'ouverture, déconnexion visible ; jeton synchroniseur, en-têtes personnalisés, Fetch Metadata et SameSite en défense en profondeur. Appliqué par W011 ; recommandations génériques, les durées retenues sont un choix du projet. |
| SEC02 | Dépôt de référence `D:\enhacements\decodair` (lecture seule le 30/09), fichiers cités dans [security-reference-decodair-2026-09-30.md](reports/security-reference-decodair-2026-09-30.md) | Mécanismes de session, CSRF, révocation et en-têtes d'une application multi-utilisateur ; transposés selon W011. Ce n'est pas une source officielle : chaque choix repris est vérifié contre SEC01. |
| EVA01–EVA31 | Dossier [evaluation-methodology-sources-2026-09-30.md](reports/evaluation-methodology-sources-2026-09-30.md) §1 (sources primaires : trec_eval/NIST, Manning et al. chap. 8, Robertson et Zaragoza 2009, Cormack et al. 2009, RAGAS, ARES, TREC 2024 RAG, ALCE, Liu et al. 2023, SQuAD 2.0, BEIR, Promptagator, InPars, Wilson/NIST e-Handbook, Smucker et al. 2007, travaux OCR) ; consultées le 30/09 entre 17:38 et 17:59 UTC | Définitions des métriques, biais des questions synthétiques, statistiques pour petits effectifs, limites des juges LLM ; base de W013. Les sources non ouvertes ou lues en partie sont listées au §5 du dossier ; aucune ne porte sur le français ni sur des documents ferroviaires. |
| UX01–UX10 | Rapport [ui-recette-2026-09-30.md](reports/ui-recette-2026-09-30.md) §Méthode : WCAG 2.2 (recommandation W3C du 12/12/2024) et pages Understanding 4.1.3, 3.2.4, 2.5.8, 1.4.11 (cette dernière consultée le 01/10/2026) ; WAI-ARIA APG, motif Button ; WAI-ARIA 1.2 (06/06/2023), rôles progressbar et status ; GOV.UK Design System, composants Tag et Error message ; Nielsen Norman Group, 10 heuristiques (mise à jour du 30/01/2024) ; consultées le 30/09/2026 | Grille de recette de l'interface (états, bascules, barres d'avancement, messages sans code, cohérence des libellés). Pages GOV.UK et APG non datées ; NN/g n'est pas un organisme normatif ; contrastes calculés à partir des jetons par les tests unitaires, sans outil d'audit automatique ni lecteur d'écran |
| QDR05 | [Qdrant v1.19.1, schéma OpenAPI `docs/redoc/master/openapi.json` du tag](https://raw.githubusercontent.com/qdrant/qdrant/v1.19.1/docs/redoc/master/openapi.json), téléchargé le 01/10 à 10:34 UTC (github.com injoignable, raw.githubusercontent.com joignable), SHA-256 `eb3e5d71…a4ce0a`, copie hors Git sous `.runtime/references/qdrant-openapi/` | `VectorParams.on_disk`, `HnswConfigDiff.on_disk` et `on_disk_payload` dépréciés au profit de `memory` (`cold`, `cached`, `pinned`), valeurs par défaut et équivalences ; base de W017. Schéma d'API : la tenue réelle du binaire a été vérifiée séparément (collection de sondage, autocontrôle) |

## Sources Linux aarch64 examinées le 1er octobre 2026 (W018, lot J0)

Consultation le 01/10/2026 entre 15:30 et 16:05 UTC pour le skill [linux-rag-runtime](../.agents/skills/linux-rag-runtime/SKILL.md). Pages ouvertes par l'outil de lecture web, ou téléchargées par `curl` (HTTP 200) puis lues en texte lorsque cet outil a échoué : domaine man7.org refusé, aucune réponse pour pytorch.org, tessdoc et qdrant.tech. Copies de travail hors dépôt, non versionnées. Les observations du poste sont faites en lecture seule.

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| LNX01 | Python 3.12 (pages 3.12.15) : [subprocess](https://docs.python.org/3.12/library/subprocess.html), [os](https://docs.python.org/3.12/library/os.html), [signal](https://docs.python.org/3.12/library/signal.html), [fcntl](https://docs.python.org/3.12/library/fcntl.html), [tarfile](https://docs.python.org/3.12/library/tarfile.html) | `start_new_session` (setsid) et `process_group` (3.11) remplacent `preexec_fn`, « NOT SAFE » en présence de threads ; `terminate()` envoie SIGTERM ; `close_fds` vrai et descripteurs non héritables depuis 3.4 ; `env` doit fournir toutes les variables utiles ; `os.killpg`, `os.pidfd_open` (Linux ≥ 5.3), `signal.pidfd_send_signal` (Linux ≥ 5.1), `os.waitid` avec `WNOWAIT` ; gestionnaires de signaux dans le seul thread principal ; `fcntl.lockf` enveloppe les verrous `fcntl()` ; `LOCK_NB` lève `OSError` EACCES ou EAGAIN ; filtre tarfile `data`, mode flux `r|`. Documentation, pas mesure sur CPython 3.12.14 |
| LNX02 | man-pages 6.19 : [setsid(2)](https://man7.org/linux/man-pages/man2/setsid.2.html), [PR_SET_PDEATHSIG(2const)](https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html) (08/02/2026), [PR_SET_CHILD_SUBREAPER(2const)](https://man7.org/linux/man-pages/man2/PR_SET_CHILD_SUBREAPER.2const.html), [kill(2)](https://man7.org/linux/man-pages/man2/kill.2.html), [wait(2)](https://man7.org/linux/man-pages/man2/wait.2.html), [setsid(2)](https://man7.org/linux/man-pages/man2/setsid.2.html) | Signal envoyé à la fin du thread créateur, pas du processus ; effacé au fork, conservé à l'execve sauf binaire setuid ou à capacités ; aucun signal si le parent est déjà mort ; un subreaper adopte les orphelins ; un zombie garde son PID jusqu'au wait ; pid < -1 vise un groupe. Noyau local 5.10 : `setpriv --pdeathsig TERM` vérifié (valeur 15 relue après execve direct, 0 après un fork intermédiaire) |
| LNX03 | man-pages 6.19 : [flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html), [fcntl_locking(2)](https://man7.org/linux/man-pages/man2/fcntl_locking.2.html), [ld.so(8)](https://man7.org/linux/man-pages/man8/ld.so.8.html) (03/08/2026) | flock lié à la description de fichier ouverte, hérité au fork, conservé à l'execve ; deux `open()` du même processus se bloquent mutuellement ; verrous d'enregistrement liés au processus et perdus à la fermeture de n'importe quel descripteur du fichier ; sémantique différente sur SMB et NFS ; un élément vide de `LD_LIBRARY_PATH` désigne le répertoire courant. Fonde le refus de `lockf` et l'exclusion du `LD_LIBRARY_PATH` hérité (`/usr/local/cuda-11.4/lib64:` sur ce poste) |
| LNX04 | util-linux : [setpriv(1)](https://man7.org/linux/man-pages/man1/setpriv.1.html), [unshare(1)](https://man7.org/linux/man-pages/man1/unshare.1.html) (pages de la version 2.43 en développement ; 2.34 installée) ; man-pages [user_namespaces(7)](https://man7.org/linux/man-pages/man7/user_namespaces.7.html), [network_namespaces(7)](https://man7.org/linux/man-pages/man7/network_namespaces.7.html) | Espaces de noms utilisateur créables sans privilège depuis Linux 3.8. Constat local : `/proc/sys/kernel/unprivileged_userns_clone` absent, `user.max_user_namespaces` = 249101, `unshare -rn` fonctionne, seule `lo` (éteinte), sortie ENETUNREACH, UID 0 dans l'espace et fichiers appartenant à l'utilisateur sur l'hôte. Pas de `--map-current-user` en 2.34 ; vérifier `--help` local avant d'utiliser une option de 2.43 |
| LNX05 | uv (documentation courante ; uv 0.12.21 installé) : [résolution](https://docs.astral.sh/uv/concepts/resolution/), [dépendances](https://docs.astral.sh/uv/concepts/projects/dependencies/), [PyTorch](https://docs.astral.sh/uv/guides/integration/pytorch/), [variables](https://docs.astral.sh/uv/reference/environment/), [réglages](https://docs.astral.sh/uv/reference/settings/), [cache](https://docs.astral.sh/uv/concepts/cache/) | `environments` disjoints restreignent la résolution ; `required-environments` exige une roue par plateforme listée ; sources par marqueur et index `explicit` ; roues PyPI Linux ciblant CUDA 13.0 depuis PyTorch 2.11.0 ; `UV_PYTHON_INSTALL_DIR`, `UV_MANAGED_PYTHON` (0.6.8), `UV_OFFLINE`, `python-downloads = "never"` ; cache et environnement sur le même système de fichiers, sinon copie. Documentation non figée à 0.12.21 |
| LNX06 | [PyTorch Get Started](https://pytorch.org/get-started/locally/) ; `uv.lock` | Commande Linux CPU : index `https://download.pytorch.org/whl/cpu` ; glibc ≥ 2.28 exigée ; version stable affichée : 2.14.1. Verrou : `torch-2.14.0+cpu-cp312-cp312-manylinux_2_28_aarch64` (download-r2.pytorch.org). Installation sur ce poste en cours, non qualifiée |
| LNX07 | [Qdrant Installation](https://qdrant.tech/documentation/installation/) (page courante) ; API GitHub, release v1.19.1 du 04/09/2026 | AArch64 pris en charge ; stockage POSIX en accès bloc, ni NFS ni S3, SSD ou NVMe recommandé pour les vecteurs déchargés sur disque. Asset `qdrant-aarch64-unknown-linux-musl.tar.gz` : 30 277 893 octets, empreinte identique au verrou. Binaire pas encore téléchargé sur ce poste ; page non versionnée |
| LNX08 | [Ollama Linux](https://docs.ollama.com/linux), [FAQ](https://docs.ollama.com/faq) ; API GitHub, release v0.35.0 ; sources brutes v0.35.0 [`ml/path.go`](https://github.com/ollama/ollama/blob/v0.35.0/ml/path.go) (SHA-256 `8949f6a8…a4c3`), [`cmd/cmd.go`](https://github.com/ollama/ollama/blob/v0.35.0/cmd/cmd.go), [`envconfig/config.go`](https://github.com/ollama/ollama/blob/v0.35.0/envconfig/config.go) | Installation manuelle par `tar x -C /usr` avec sudo, non suivie ici ; la page ne mentionne pas Jetson ; liaison 127.0.0.1:11434 par défaut, `OLLAMA_MODELS`, `OLLAMA_NO_CLOUD`. Assets : arm64 1 550 231 393 octets (empreinte = verrou), `-jetpack5` 297 201 571, `-jetpack6` 269 692 742. Bibliothèques cherchées dans `<exe>/../lib/ollama`, puis `<exe>/lib/ollama`, puis `build/` et `dist/` relatifs à l'exécutable et au répertoire courant. `ollama serve` crée `$HOME/.ollama/id_ed25519` et lit `$HOME/.ollama/server.json`. Archive en cours de téléchargement ; compatibilité avec la glibc 2.31 non établie |
| LNX09 | [Go `os.UserHomeDir`](https://pkg.go.dev/os#UserHomeDir) ; `go.mod` d'Ollama v0.35.0 (go 1.26.0) | Sous Unix, rend `$HOME` ; si la variable manque, rend une valeur par défaut ou une erreur. Fonde l'obligation de transmettre `HOME` aux enfants |
| LNX10 | [tessdoc Compiling](https://tesseract-ocr.github.io/tessdoc/Compiling.html) ; `CMakeLists.txt` de Tesseract 5.4.0 ; `CMakeLists.txt`, `cmake/LeptonicaFunc.cmake` et README de Leptonica 1.87.0, lus dans les archives verrouillées (SHA-256 `30ceffd9…83fd` et `c7336339…b6a7` revérifiés) | CMake ≥ 3.10, Leptonica ≥ 1.74, `Leptonica_DIR` ; options `BUILD_TRAINING_TOOLS`, `DISABLE_ARCHIVE`, `DISABLE_CURL`, `GRAPHICS_DISABLED`, `OPENMP_BUILD` (OFF par défaut) ; NEON activé pour aarch64. Leptonica : options `ENABLE_*` et `STRICT_CONF` ; le README annonce des bibliothèques partagées par défaut ; installation sans root par préfixe. Compilation non exécutée |
| LNX11 | [python-zstandard 0.25.0, décompression](https://python-zstandard.readthedocs.io/en/latest/decompressor.html) ; métadonnées PyPI de `zstandard` 0.25.0 | `stream_reader` avec `read_across_frames=False` par défaut s'arrête en fin de trame ; `max_window_size` borne la fenêtre ; roue `cp312 manylinux2014_aarch64` disponible. En-tête de la première trame de l'archive Ollama : fenêtre de 8 Mio. Ajouté au verrou pour Linux le 01/10 (W018) |
| LNX12 | [Jetson Linux R35.4.1, Platform Power and Performance](https://docs.nvidia.com/jetson/archives/r35.4.1/DeveloperGuide/text/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html) | AGX Orin 64 Go : `MODE_30W` (ID 2, mode par défaut), 8 CPU en ligne, 1 728 MHz ; changement par `sudo nvpmodel -m`. Constat : `nvpmodel -q` = MODE_30W, CPU 0-7 en ligne sur 0-11 présents |
| LNX13 | Documentation du noyau (version courante 7.3-rc5) : [/proc, MemAvailable](https://docs.kernel.org/filesystems/proc.html), [zram](https://docs.kernel.org/admin-guide/blockdev/zram.html) | MemAvailable estime la mémoire disponible sans swap ; zram stocke les pages compressées en mémoire. Constat : 8 périphériques zram de 3,9 Gio, `lzo-rle`. Documentation plus récente que le noyau local 5.10 |
| LNX14 | [psutil](https://psutil.readthedocs.io/en/stable/) (documentation stable, version non indiquée ; version verrouillée 7.2.2) | `memory_full_info()` fournit USS, PSS et swap en parcourant tout l'espace d'adressage : plus lent que `memory_info()`, droits supérieurs parfois nécessaires |
| LNX15 | Playwright : [intro](https://playwright.dev/docs/intro), [notes de version](https://playwright.dev/docs/release-notes), [navigateurs](https://playwright.dev/docs/browsers) | Configuration requise : Debian 12/13, Ubuntu 22.04/24.04/26.04 (x86-64 et arm64). Notes de la 1.63 : « Ubuntu 20.04 is not supported anymore », Chrome for Testing sous Linux arm64. `PLAYWRIGHT_BROWSERS_PATH` documenté ; `install-deps` passe par le gestionnaire de paquets. Lancement sur ce poste non essayé |

Vérification indépendante le 01/10 entre 16:20 et 16:40 UTC : six de ces sources rouvertes et confrontées au skill ; corrections reportées (trames zstd, bibliothèques `cuda_v12` de l'archive Ollama générique, critère `ldd`, erreur de `flock`, ordre de recherche des bibliothèques d'Ollama, `envconfig/config.go` pour `server.json`).

Les limites « en cours », « pas encore téléchargé », « non qualifiée », « compilation non exécutée » et « lancement non essayé » de LNX06, LNX07, LNX08, LNX10 et LNX15 décrivent l'état au moment de la consultation (01/10, 15:30–16:05 UTC). Exécutions ultérieures, consignées aux journaux du [1er octobre](journal/2026-10-01.md) et du [2 octobre](journal/2026-10-02.md) : environnement Python synchronisé et torch `2.14.0+cpu` importé (16:05) ; `ollama --version` sous la glibc 2.31 (16:38) ; Leptonica et Tesseract compilés (lots J2/J3 puis J2b/J3b, 16:13–17:41) ; Qdrant et Ollama démarrés par la chaîne réelle `provision --only ollama`, `pull-model`, `up`, `status`, `doctor`, `down` (17:41) ; navigateur de Playwright installé et lancé (02/10, 01:44–01:46 UTC, TOOL02).

## Sources des corrections documentaires du 1er octobre 2026 (lot J6)

Pages ouvertes le 01/10/2026, sans version publiée sauf mention.

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| AGT01 | Claude Code, [How Claude remembers your project](https://code.claude.com/docs/en/memory) : sections « Organize rules with `.claude/rules/` », « How CLAUDE.md files load », « AGENTS.md » | `.claude/rules/` est le mécanisme de règles de projet (absent de ce dépôt) ; les `CLAUDE.md` de sous-dossiers se chargent quand un fichier du dossier est lu ; `AGENTS.md` n'est lu par défaut qu'en l'absence de `CLAUDE.md`. Comportement dépendant de la version du client |
| AGT02 | Claude Code, [Extend Claude with skills](https://code.claude.com/docs/en/skills) : section « Where skills live » | Skills de projet découverts sous `.claude/skills/<nom>/SKILL.md`, y compris dans des sous-dossiers ; les skills de `.agents/skills/` ne sont donc pas découverts nativement et se lisent par leur chemin |
| AGT03 | OpenAI, [Build skills](https://learn.chatgpt.com/docs/build-skills) (redirection 308 depuis `developers.openai.com/codex/skills`) | « For repositories, Codex scans `.agents/skills` in every directory from your current working directory up to the repository root » |
| PY01 | Python 3.12 : [datetime](https://docs.python.org/3.12/library/datetime.html), [tomllib](https://docs.python.org/3.12/library/tomllib.html) | `datetime.UTC` et `tomllib` : « Added in version 3.11 » ; fonde le prérequis Python 3.11 de `verify_pack.py` et `check_docs.py` |

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| LNX16 | astral-sh/uv, release [0.12.21](https://github.com/astral-sh/uv/releases/tag/0.12.21) : fichiers `.sha256` publiés à côté des archives, et champ `digest` de l'API GitHub des releases | `uv-aarch64-unknown-linux-gnu.tar.gz` : SHA-256 `030b69227b40af8c1981b7301793dc66e71ed3c796ea8688209dd268bd91ec51` (fichier `.sha256` et API concordants, archive téléchargée et vérifiée le 01/10 à 14:53 UTC) ; `uv-x86_64-unknown-linux-gnu.tar.gz` : `23f02075b652bb1df64178cfae41b5caf160822e720e2663568f3f5d63bc52c0` (fichier `.sha256` relu le 01/10 vers 17:05 UTC, archive non téléchargée sur ce poste aarch64). Valeurs reprises par `bootstrap.sh` ; l'archive Windows reste celle de `bootstrap.ps1` |

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| LNX17 | ollama/ollama v0.35.0, [`server/routes.go`](https://github.com/ollama/ollama/blob/v0.35.0/server/routes.go) (lu le 01/10/2026) | `signal.Notify` sur SIGINT et SIGTERM, même traitement : fermeture du serveur HTTP puis déchargement des runners ; confirmé par quatre essais réels sur ce poste (code 0, groupe vide). Fonde l'arrêt Linux par SIGTERM (complément W018) |
| LNX18 | Sources verrouillées Tesseract 5.4.0 (`CMakeLists.txt` l.90 `FAST_FLOAT`, `src/arch/simddetect.cpp`, `src/ccutil/tesstypes.h`) et Leptonica 1.87.0 (`CMakeLists.txt` l.42–45, `src/utils1.c`), lues dans les archives du groupe `tesseract-source` le 01/10/2026 | Options de compilation retenues et absence d'horodatage compilé hors MSVC ; documentation de `-ffile-prefix-map` : LNX19 ; la reproductibilité mesurée (même SHA-256 depuis deux emplacements) reste la seule preuve d'exécution |
| LNX19 | GCC : manuel [8.1.0 « Overall Options »](https://gcc.gnu.org/onlinedocs/gcc-8.1.0/gcc/Overall-Options.html), manuels 7.5.0 [« Overall Options »](https://gcc.gnu.org/onlinedocs/gcc-7.5.0/gcc/Overall-Options.html) et [« Option Summary »](https://gcc.gnu.org/onlinedocs/gcc-7.5.0/gcc/Option-Summary.html), [changements de GCC 8](https://gcc.gnu.org/gcc-8/changes.html) ; Clang : [notes de version 10.0.0](https://releases.llvm.org/10.0.0/tools/clang/docs/ReleaseNotes.html), [référence de ligne de commande 9.0.0](https://releases.llvm.org/9.0.0/tools/clang/docs/ClangCommandLineReference.html) (lus le 01/10/2026) | `-ffile-prefix-map=old=new` documentée à partir du manuel de GCC 8.1.0 (« equivalent to specifying all the individual -f*-prefix-map options … reproducible builds that are location independent »), absente des manuels 7.5.0 ; annoncée par Clang 10.0.0 (« equivalent to specifying both -fdebug-prefix-map and -fmacro-prefix-map »), absente de la référence 9.0.0. Fonde le minimum GCC 8 ou Clang 10 de `provisioning.build_tools` et `missing_build_prerequisites`. Limite : les changements de GCC 8 ne citent pas l'option, le minimum se déduit du premier manuel qui la documente ; Clang n'a pas été exécuté sur ce poste |
| LNX20 | Documentation du noyau Linux (version 7.3.0-rc5), [The /proc Filesystem](https://docs.kernel.org/filesystems/proc.html#mount-options), section 4.1 « Mount options » (lue le 01/10/2026 à 21:45 UTC) | « hidepid=off or hidepid=0 means classic mode - everybody may access all /proc/<pid>/ directories (default) » ; avec `hidepid=noaccess` ou `hidepid=1`, « Sensitive files like cmdline, sched*, status are now protected against other users » ; `hidepid=invisible` ou `hidepid=2` y ajoute l'invisibilité des dossiers `/proc/<pid>/` des autres comptes. Fonde le risque résiduel et la parade hors projet de W023. Constat local : `/proc` monté `rw,relatime`, sans `hidepid` (`/proc/mounts`, noyau 5.10.120-tegra). Limite : documentation plus récente que le noyau local ; remonter `/proc` exige des droits d'administrateur, non essayé |

## Sources de l'accélération GPU examinées le 1er octobre 2026 (W024, W025, lot J11)

Consultation du 01/10/2026 pour l'étude J11, en trois recherches : Ollama et NVIDIA (A, avec un clone du tag `v0.35.0` d'Ollama, commit `cc4069396f3a`), bibliothèques Python (B, entre 20:25 et 20:45 UTC) et essai réel sur ce Jetson (C). La revue adversariale de la conception a rouvert le même jour les pages GPU, FAQ et Windows d'Ollama, CUDA for Tegra, la compatibilité de version mineure de NVIDIA et la page JetPack 5.1.2. Copies de travail hors dépôt, non versionnées. Les observations du poste et les résultats d'essai n'appartiennent pas à ce registre : ceux de la recherche C restent dans ses copies de travail, hors dépôt ; ceux de l'essai J11.8 du 02/10 sont résumés dans la [section 5.1 d'ARCHITECTURE.md](../docs/architecture/ARCHITECTURE.md#51-accélération-gpu-de-la-génération), avec leurs preuves hors Git sous `.runtime/qa/j11-gpu-2026-10-02/`. Une source signalée « hors liste » n'appartient pas à la liste des sources autorisées pour l'étude (revue de la conception, constat M4) : elle éclaire un mécanisme sans fonder seule une décision. Les choix qui en découlent sont consignés dans [W025](DECISIONS.md#w025-accélération-gpu--arbitrages-de-réalisation-w024).

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| GPU01 | ollama/ollama, release [v0.35.0](https://github.com/ollama/ollama/releases/tag/v0.35.0) du 28/09/2026 : actifs et `digest` de l'API GitHub des releases, `sha256sum.txt` de la release | `ollama-linux-arm64-jetpack5.tar.zst` : 297 201 571 octets, SHA-256 `f7f1a7e8…0f5b`, identique dans l'API, dans `sha256sum.txt` et pour le fichier téléchargé ; `-jetpack6` : 269 692 742 octets, `609be1fb…2753` ; `ollama-windows-amd64.zip` : 1 461 196 158 octets ; ROCm et MLX en archives séparées. Valeurs du groupe `ollama-gpu` de `config/artifacts.lock.json`. Limites : notes de version muettes sur les GPU ; `-jetpack6` ni téléchargé ni essayé |
| GPU02 | [`scripts/install.sh`](https://github.com/ollama/ollama/blob/v0.35.0/scripts/install.sh) au tag v0.35.0 (SHA-256 `25f64b81…`, identique à l'actif de la release), l. 110-118, 159-187 et 264-269 | Complément choisi d'après `/etc/nv_tegra_release` (R36 : `jetpack6`, R35 : `jetpack5`) et extrait dans le même préfixe que l'archive de base ; aucun pilote installé sur Jetson. Limite : installation système avec sudo, reproduite ici en espace utilisateur sous `.runtime/bin` |
| GPU03 | Construction au tag v0.35.0 : `Dockerfile`, `scripts/build_linux.sh`, `scripts/build_windows.ps1`, `llama/server/CMakePresets.json` ; inventaire du zip Windows de la release par lecture de son répertoire central | Compléments construits sur `l4t-jetpack` r35.4.1 (architectures 72 et 87) et r36.4.0 (87) ; runtimes CUDA 12.8 et 13.0 dans l'archive générique, `cuda_v12` Linux compilé sans l'architecture 87 ; zip Windows avec `cuda_v12`, `cuda_v13` et `vulkan`. Limites : décrit la construction ; présence de Vulkan dans l'archive linux-amd64 non inventoriée ; version CUDA de r36.4.0 inconnue |
| GPU04 | Découverte au tag v0.35.0 : `discover/gpu.go` (l. 38-72), `discover/runner.go` (l. 89-97 et 382-436), `discover/types.go` (l. 19-64), `discover/cuda_compat.go` | Correspondance de la version de Jetson Linux à JetPack par ` R(\d+) ` ; délai de garde de 30 s par passe de découverte, 90 s sous Windows ; iGPU CUDA admis par défaut, autres iGPU écartés (« dropping integrated GPU ») ; format de la ligne « inference compute » ; contrôle du pilote (550, ou 570 sous la capacité 7) limité à `cuda_v12`. Limite : code non documenté et journal non contractuel, à revérifier à chaque montée de version |
| GPU05 | Ordonnancement et exécution au tag v0.35.0 : `server/sched.go` (l. 276-281, 645-676, 1163-1180, 1417-1420), `server/routes.go` (l. 2189-2211, 3218-3230), `llm/llama_server.go` (l. 404-413), `api/types.go`, `envconfig/config.go`, `ml/device.go` | `num_gpu` absent : placement automatique par llama-server ; `0` : CPU seul, sans GPU fourni au runner ; une requête sans `num_gpu` ne recharge pas un runner chargé sur CPU ; aucun repli CPU après un échec de chargement (HTTP 500) ; découverte journalisée avant `Serve` ; mmap désactivé sous Windows avec CUDA. Limite : `OLLAMA_GPU_OVERHEAD` reste sans effet sur le placement de llama-server, en écart avec sa description |
| GPU06 | [Ollama, Hardware support](https://docs.ollama.com/gpu) (`docs/gpu.mdx`), page non datée | NVIDIA : capacité de calcul 5.0 ou plus, pilote 550 ou plus récent, 570 pour une capacité de 5.0 à 6.2 ; `CUDA_VISIBLE_DEVICES=-1` force le CPU ; ROCm v7 ; Vulkan. Limite : Jetson absent de la page |
| GPU07 | Ollama : [FAQ](https://docs.ollama.com/faq), [`/api/ps`](https://docs.ollama.com/api/ps), [Windows](https://docs.ollama.com/windows), [Linux](https://docs.ollama.com/linux), [Troubleshooting](https://docs.ollama.com/troubleshooting), pages non datées ; `docs/docker.mdx` au tag v0.35.0 | Occupation du modèle par `size_vram` et colonne PROCESSOR (« 48%/52% CPU/GPU ») ; pilote Windows 551.61 ou plus récent ; archives ROCm et MLX à extraire au même emplacement (« Standalone CLI ») ; variable `JETSON_JETPACK`. Limites : la FAQ annonce un contexte par défaut de 4096, alors que le code le fait dépendre de la mémoire GPU (neutralisé par `OLLAMA_CONTEXT_LENGTH`) ; Troubleshooting décrit `OLLAMA_LLM_LIBRARY` autrement que le code ; aucune page ne définit `num_gpu` |
| GPU08 | llama.cpp, tag [b11081](https://github.com/ggml-org/llama.cpp/tree/b11081), fixé par `LLAMA_CPP_VERSION` d'Ollama : `ggml/src/ggml-cuda/ggml-cuda.cu` (l. 4893-5019), `common/arg.cpp` (l. 2785-2801), `common/common.h` | Sur un GPU intégré, la mémoire libre est lue dans `MemAvailable` ; `-ngl` automatique et `--fit` actifs par défaut. Limites : hors liste (revue M4) ; correctif `llama/compat` d'Ollama non relu en entier ; comportement corroboré par le journal d'Ollama de l'essai d'étude du 01/10, hors dépôt (`CUDA0: Orin (62800 MiB, 48222 MiB free)`), non par une documentation |
| GPU09 | NVIDIA, [CUDA for Tegra](https://docs.nvidia.com/cuda/cuda-for-tegra-appnote/index.html), version 13.4 mise à jour le 13/09/2026 : §3, §3.3, §6 et §8 (tableaux 6 à 9) | CPU et iGPU partagent la DRAM ; `cudaMemGetInfo` ne compte pas le swap ; estimation de la mémoire de l'iGPU à partir de `MemTotal`, `NvMapMemUsed` et `SwapFree` ; JetPack 5.x limité à CUDA 12.2 par le paquet de mise à niveau, installé avec sudo. Limites : page non propre à CUDA 11.4 ; sous R35.4.1, `NvMapMemUsed` est absent de `/proc/meminfo` et le debugfs nvmap réservé à root (constat local), la formule n'est donc pas calculable sur ce poste |
| GPU10 | NVIDIA, [CUDA Minor Version Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) et [Forward Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/forward-compatibility.html), mises à jour le 09/09/2026 | CUDA 13.x : pilote 580 ou plus récent ; CUDA 12.x : pilote 525 ou plus récent. La plage « 525 à 580 » relevée par la recherche A est celle de la compatibilité de version mineure : un pilote plus récent reste compatible (revue B1). Explique l'échec de `cuda_v12` et `cuda_v13` avec un pilote CUDA 11.4. Limite : renvoie à GPU09 pour Tegra |
| GPU11 | NVIDIA, [JetPack 5.1.2](https://developer.nvidia.com/embedded/jetpack-sdk-512), [archive JetPack](https://developer.nvidia.com/embedded/jetpack-archive), [CUDA GPUs](https://developer.nvidia.com/cuda-gpus), pages non datées | JetPack 5.1.2 : Jetson Linux 35.4.1, CUDA 11.4.19, Ubuntu 20.04 ; R35 correspond à JetPack 5, R36 à JetPack 6, R38 et R39 à JetPack 7 ; AGX Orin, Orin NX et Orin Nano en capacité 8.7. Limite : Xavier et Thor absents de l'extrait relevé |
| GPU12 | onnxruntime : [CUDA Execution Provider](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html), [Install](https://onnxruntime.ai/docs/install/), [Build EPs](https://onnxruntime.ai/docs/build/eps.html) (section NVIDIA Jetson), [`OperatorKernels.md` au tag v1.30.0](https://github.com/microsoft/onnxruntime/blob/v1.30.0/docs/OperatorKernels.md) ; PyPI [`onnxruntime-gpu` 1.30.0](https://pypi.org/pypi/onnxruntime-gpu/1.30.0/json), publié par Microsoft | Paquets GPU 1.27 à 1.30 en CUDA 13.0 sur PyPI, paquets CUDA 12.8 séparés ; roue aarch64 en manylinux_2_34 ; compilation obligatoire sur Jetson (CUDA 11.8 ou plus, gcc postérieur à 9.4) ; aucun noyau CUDA pour `DynamicQuantizeLinear`, `MatMulInteger` CUDA en int8 × int8 seulement : le graphe E5 INT8 du projet n'en profiterait pas. Limites : la page Install annonce encore CUDA 12.x par défaut, contredite par les métadonnées PyPI ; registre de noyaux, pas une mesure |
| GPU13 | PyTorch : [`RELEASE.md`](https://github.com/pytorch/pytorch/blob/main/RELEASE.md) (commit `1a54030` du 18/09/2026), [index des roues](https://download.pytorch.org/whl/torch/) ; NVIDIA : [PyTorch pour Jetson](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html) et sa matrice de compatibilité, mises à jour le 29/09/2026, dossier `jp/v512/pytorch/` | torch 2.14 : CUDA 12.6, 13.0 ou 13.2 (variantes cu126, cu130, cu132) ; JetPack 5.1.x : seule roue `torch-2.1.0a0+41361538.nv23.06-cp38` ; aucune roue NVIDIA après 24.09. Limites : version de Python déduite du nom de la roue ; exécution des roues aarch64 génériques sur le GPU d'un Jetson non établie |
| GPU14 | Docling, [`docs/usage/gpu.md` au tag v2.131.0](https://github.com/docling-project/docling/blob/v2.131.0/docs/usage/gpu.md) et code installé (`accelerator_options.py`, `accelerator_utils.py`) | Périphériques AUTO, CPU et CUDA ; `decide_device('cuda')` lève une erreur sans GPU, contrairement à sa docstring (essayé sur ce poste) ; pour l'OCR, seul RapidOCR profite du GPU, Tesseract en ligne de commande reste sur CPU. Limite : mesures de l'éditeur sur RTX et L40S, pas sur ce poste |
| GPU15 | uv, [guide PyTorch](https://docs.astral.sh/uv/guides/integration/pytorch/), documentation courante | Extras exclusifs (`conflicts`) et sources par marqueur ; `--torch-backend` réservé à `uv pip`. Fonde l'analyse du verrou à extras exclusifs qu'exigerait une voie GPU pour Docling, écartée par W025 (P1). Limites : hors liste (revue M4) ; documentation non figée à uv 0.12.21 ; essai de `uv lock` fait dans une copie de travail |

## Sources et outils du chantier Linux consignés après l'audit D10/D11 (2 octobre 2026)

Entrées établies le 2 octobre 2026 d'après les journaux, les preuves conservées et les empreintes recalculées ce jour-là ; aucune page n'a été rouverte pour les écrire. La date de consultation est celle du journal, ou bornée par le commit qui cite la source quand le journal ne la donne pas. Les outils TOOL01 à TOOL03 servent au développement et à la recette ; aucun n'entre dans le produit livré.

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| LNX21 | API GitHub des releases : Qdrant v1.19.1, actif `qdrant-x86_64-unknown-linux-musl.tar.gz` (32 315 868 octets, SHA-256 `70a40529…17c9`) ; Ollama v0.35.0, actif `ollama-linux-amd64.tar.zst` (1 427 765 407 octets, `1c114a6b…e525`) ; consultée le 01/10/2026 vers 16:36 UTC | Empreintes reprises dans `config/artifacts.lock.json` (complément W018 du 01/10 à 16:37 UTC). Archives téléchargées sur ce poste aarch64, empreintes conformes au verrou, extraites par le code du projet en plateforme simulée (ronde 4, 01/10, 19:03–20:06 UTC). Limites : aucune exécution sous Linux x86-64 ; plancher glibc de `bin/ollama` amd64 non établi |
| LNX22 | PyPI : métadonnées des 126 paquets alors verrouillés (versions de `uv.lock`), consultées le 01/10/2026 entre 15:03 et 15:09 UTC pour aarch64, puis vers 16:36 UTC pour x86-64 | Toutes les versions existent en roues manylinux aarch64 compatibles avec la glibc 2.31, sauf `pywin32` (propre à Windows) et `antlr4` (source en pur Python) ; même constat pour x86-64, `torch 2.14.0+cpu` compris ; la roue PyPI de torch 2.14.0 pour aarch64 tire CUDA 13, d'où la source `pytorch-cpu` (LNX05, LNX06). Fonde la justification de W018. Limite : le journal ne précise ni l'interface de PyPI interrogée ni la liste des roues retenues |
| J8S01 | ONNX Runtime v1.30.0 : [`docs/Privacy.md`, « Disabling Telemetry »](https://github.com/microsoft/onnxruntime/blob/v1.30.0/docs/Privacy.md#disabling-telemetry) ; [`onnxruntime/core/platform/telemetry_environment.h`](https://github.com/microsoft/onnxruntime/blob/v1.30.0/onnxruntime/core/platform/telemetry_environment.h), `IsTelemetryDisabledByEnvironment` ; version installée 1.30.0 (`uv.lock`) ; date de consultation non consignée, au plus tard le 02/10/2026 à 09:34 UTC (commit `419b526`, qui les cite) | Contrat tel que le reprennent le README (section 8) et ARCHITECTURE.md (section 2) : `ORT_DISABLE_TELEMETRY` est lue une fois, au chargement d'ONNX Runtime ; elle agit sous Linux et reste sans effet sous Windows, où la télémétrie passe par ETW. Observé sous Linux : rejeu R4 du 02/10 en session hors ligne, aucune requête DNS de télémétrie. Non observé sous Windows. Fonde la correction D08.2 du commit `419b526`, consignée a posteriori dans [W028](DECISIONS.md#w028-corrections-j8-à-effet-de-comportement--sondes-de-port-posix-et-télémétrie-donnx-runtime) |
| J8S02 | Python, [`socket.create_server` et exemple TIME_WAIT](https://docs.python.org/3.12/library/socket.html#socket.create_server), [`loop.create_server`/reuse_address](https://docs.python.org/3.12/library/asyncio-eventloop.html#asyncio.loop.create_server) (branche 3.12.15, code local Python 3.12.14 relu) ; Linux man-pages, [`socket(7)`/SO_REUSEADDR et NOTES](https://man7.org/linux/man-pages/man7/socket.7.html) (6.19, page du 05/06/2026) ; Microsoft, [Using SO_REUSEADDR and SO_EXCLUSIVEADDRUSE](https://learn.microsoft.com/en-us/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse) (mise à jour du 14/06/2022). Ouverts le 02/10/2026 entre 17:34 et 17:36 UTC | Sous POSIX, réutilisation d'une adresse TCP en TIME_WAIT ; sous Linux un écouteur actif reste bloquant et l'ancien serveur doit lui aussi avoir posé l'option. Sous Windows, SO_REUSEADDR peut lier un port déjà tenu : ne pas la poser dans une sonde de disponibilité. Sources consultées après le correctif `419b526`, pas à sa date ; elles confortent son contrat et les essais J8/R1 sans reconstituer une justification historique. Ne prouvent ni les options internes de Go/Qdrant, ni la sécurité complète des écouteurs Windows. Aucun changement de code ou d'option Windows. |
| TOOL01 | PowerShell 7.4.15 `linux-arm64` : release officielle du dépôt `PowerShell/PowerShell` et son `hashes.sha256` ; paquet NuGet officiel `Microsoft.PowerShell.Native` 7.4.0 ; fichiers `.csproj` des tags 7.4.x ; consultés entre le 01/10/2026 à 23:48 et le 02/10 à 00:05 UTC | Outil de développement, hors produit : archive `powershell-7.4.15-linux-arm64.tar.gz` de SHA-256 `922d392d382aa217c62e7ef9bcaf688c8158e295874bdfb9d6305ea6fe5d7f04`, identique à `hashes.sha256` de la release (contrôle du 02/10 vers 00:05 UTC, refait le 02/10 à 14:18 UTC), extraite hors dépôt dans la copie de travail de la session, sur la carte microSD. 7.6.6 et 7.4.20 refusés au démarrage (`libpsl-native.so` exige GLIBC_2.33) ; d'après les `.csproj`, la série 7.4 emploie `Microsoft.PowerShell.Native` 7.4.0 (GLIBC_2.17) jusqu'à 7.4.15. Sert `test_powershell_syntax.py`. Limite : PowerShell 7.4, pas Windows PowerShell 5.1 ; la syntaxe et quelques exécutions ciblées sont vérifiées, pas le comportement sous Windows |
| TOOL02 | Playwright 1.63.0 (`@playwright/test`, [`apps/web/package.json`](../apps/web/package.json)) : `playwright install --only-shell`, précédé de `--dry-run`, avec `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu22.04-arm64`, le 02/10/2026 entre 01:44 et 01:46 UTC | Chrome Headless Shell 153.0.8010.12 `linux-arm64` (révision Playwright 1243), téléchargé depuis `cdn.playwright.dev`, et ffmpeg (révision 1011), rangés dans `~/.cache/ms-playwright`, déplacé sur la carte microSD par un lien le 02/10. SHA-256 du binaire `chrome-headless-shell` relevé le 02/10 à 14:18 UTC : `f5d89353cc9ef8dc1541268bbee1f05ee40a31ce3d9799b3a274e5147f6a8cdb`, sans somme officielle à comparer. Limites : Ubuntu 20.04 n'est plus pris en charge par Playwright 1.63 (LNX15) ; la variable d'override n'est documentée par aucune source de ce registre, son effet a été lu dans `calculatePlatform` de `playwright-core` 1.63.0 installé ; l'acceptation de cette méthode comme preuve D06 reste à décider |
| TOOL03 | pnpm 10.34.1 par Corepack 0.35.0 : `corepack install` exécuté une fois avec réseau dans `apps/web` le 01/10/2026 ; version et empreinte SHA-512 fixées par `packageManager` ([`apps/web/package.json`](../apps/web/package.json)) | La vérification de cette empreinte par Corepack au téléchargement n'est ni sourcée dans ce registre ni consignée. Effet de bord du 01/10 (13:20–13:45 UTC) : `pnpm -v`, lancé par un agent alors que `packageManager` n'existait pas encore, a fait télécharger pnpm 12.8.1 par Corepack dans `~/.cache/node/corepack` (52 Mo), sans contrôle consigné ; le projet ne l'emploie pas. Les deux versions restent dans ce cache le 02/10 |

## Sources du diagnostic de l'import sous Chromium snap (2 octobre 2026)

Pages ouvertes le 02/10/2026 entre 16:12 et 16:16 UTC ; fichier du snap lu sur ce poste à la même heure. Elles expliquent l'échec de la boîte de choix constaté le même jour (journal, entrée de 15:51–16:16), sans engager le produit, qui ne règle pas les options du navigateur.

| ID | Source officielle/version | Contrat et limite |
|---|---|---|
| IMP01 | Launchpad, paquet Ubuntu `chromium-browser`, [bug #1851250](https://bugs.launchpad.net/bugs/1851250) « [snap] chromium-browser snap cannot upload files outside ~ », commentaires 14 (Alberto Mardegan, 15/12/2021) et 17 (Olivier Tilloy, mainteneur du snap, 16/12/2021) | Chromium n'emploie la boîte de choix par portail que si la propriété `version` de `org.freedesktop.portal.FileChooser` vaut au moins 3 ; elle vaut 2 sous Focal (20.04), où « the XDG desktop portal isn't new enough ». Mesure sur ce poste : `xdg-desktop-portal` 1.6.0, propriété `version` à 2. Le bug traite l'accès aux fichiers hors du dossier personnel ; la perte d'un fichier choisi dans `~/Downloads` relève de nos essais, pas de ce bug |
| IMP02 | Lanceur du snap Chromium 153.0.8010.47, révision 3535 (`/snap/chromium/3535/bin/chromium.launcher`, publié par Canonical), lignes 126 et 139–142 | Ligne 126 : `CHROMIUM_FLAGS="--gtk-version=3 $CHROMIUM_FLAGS"`, commentée « Use GTK3. LP:2106312, LP:2106342. » ; lignes 139–142 : lecture de `~/.chromium-browser.init` après cette ligne. Une option `--gtk-version=4` placée après celle du lanceur l'emporte (essai sur écran virtuel du 02/10 : boîte GTK 4, fichier transmis) |
| IMP03 | Launchpad, [bug #2106312](https://bugs.launchpad.net/bugs/2106312) « Download file doesn't work anymore » (signalé le 05/04/2025, Chromium 135, Fix Released) et [bug #2106342](https://bugs.launchpad.net/bugs/2106342) « Selected text became unreadable colors » (06/04/2025, même cause) | Motif de l'option GTK 3 du lanceur : sous GNOME jusqu'à Ubuntu 24.04, la boîte d'enregistrement ne sauvait aucun fichier, sans message, et le texte sélectionné devenait illisible. Dans la révision 3535, le lanceur impose GTK 3 quelle que soit la version d'Ubuntu (ligne 126). Non vérifié sur Chromium 153 en GTK 4 : risque à évaluer avant d'imposer `--gtk-version=4` |

## Sources de la reprise W029 et du maintien documentaire (2 octobre 2026)

Pages officielles ouvertes pendant cette reprise, sans transmission de code ni de PDF privés. Les méthodes éditoriales ne certifient pas le produit ; les conseils OCR restent des hypothèses jusqu'à leur test sur les fixtures immuables.

| ID | Source officielle/version, consultation | Apport et limite |
|---|---|---|
| W029S01 | Tesseract, [ImproveQuality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html), sections Borders, Page segmentation method et Tables recognition ; documentation courante ouverte le 02/10/2026 vers 16:42 UTC, section Rescaling relue vers 17:25 UTC ; exécutable local 5.4.0 | Une petite région de texte nécessite une bordure raisonnable et un mode de segmentation adapté ; la reconnaissance des tableaux nécessite une analyse de leur disposition. La section Rescaling permet d'étudier un agrandissement du raster lorsque sa densité est insuffisante. Motive les diagnostics de cellules DA-P03 et du scan à 90°. Ne fournit ni facteur de reprise obligatoire, ni seuil de hauteur de glyphe ; ceux-ci restent des choix locaux à tester. Ne démontre ni exactitude, ni confiance suffisante, ni couverture d'une page du projet. |
| W029S02 | Code installé de Docling 2.131.0 : `docling/document_converter.py` (`NativePdfFormatOption`, `convert`, `page_range`) et `docling/pipeline/native_pdf_pipeline.py` ; adaptateur local `services/ingestion/docling_adapter.py` ; lu le 02/10/2026 | Le convertisseur natif existant extrait les cellules PDF avec leur géométrie, sans modèle de disposition ni rendu d'image demandé par l'adaptateur. Base du repli sur une couche native fiable après `PDF_RENDER_LIMIT`. Ne fournit ni analyse des tableaux, ni ordre sémantique garanti pour des colonnes ; le refus de rendu reste une limite déclarée. |
| DOCS01 | Daniele Procida, [Diátaxis](https://diataxis.fr/), présentation des quatre besoins documentaires ; site du mainteneur, ouvert le 02/10/2026 entre 16:45 et 16:48 UTC, sans version publiée sur la page | Séparer référence, explication et procédures en fonction du lecteur. Adapté à l'organisation existante, sans imposer une migration des chemins canoniques ni confondre cette classification avec le statut vivant/stabilisé. |
| DOCS02 | Google, [Highlights — Developer documentation style guide](https://developers.google.com/style/highlights), sections Tone and content, Language and grammar, Formatting ; page datée du 02/04/2025 UTC, ouverte le 02/10/2026 entre 16:45 et 16:48 UTC | Formulations directes, conditions avant actions, liens explicites, dates non ambiguës et visuels utiles. Sert au skill `project-documentation` ; les conventions orthographiques américaines ne sont pas reprises dans les documents français. |

## Consultation actuelle des releases et avis de trois dépendances Linux (D11.2, 2 octobre 2026)

Sources ouvertes le 02/10/2026 entre 18:52 et 18:59 UTC, après la livraison W029 ; cette consultation ne reconstitue pas celles du portage ou de W025. Périmètre : `torch 2.14.0+cpu`, `python-zstandard 0.25.0` et complément Ollama `0.35.0-jetpack5` du poste aarch64. Métadonnées installées, verrou et manifestes confrontés en lecture seule ; aucun téléchargement de roue/archive, aucune migration, installation ou modification du runtime, aucun essai de vulnérabilité. Rapport détaillé hors Git : `.runtime/qa/w029-corpus-20261002T184300Z/source-review.json`. Une consultation de registre sans avis trouvé n'est pas une preuve d'absence de vulnérabilité.

| ID | Source officielle/version, section et dates connues | Applicabilité et limite |
|---|---|---|
| D11S01 | PyTorch, [index CPU](https://download.pytorch.org/whl/cpu/torch/), entrées CP312 aarch64 et x86-64 `2.14.0+cpu`, publiées le 02/09/2026 ; métadonnée de la roue aarch64 et `torch/version.py` installés | Version constatée `2.14.0+cpu`, tag `cp312-cp312-manylinux_2_28_aarch64`, CUDA absent dans `version.py`. SHA-256 de la métadonnée installée `6e6cbfdc…4f6` identique à celui de l'index ; empreintes des deux roues de l'index identiques à `uv.lock` (`da8140c3…0f8d` et `a09987c9…c260`). Le `git_version` de la roue est `08187d9e0fba026dc8217405802ab5381dc88d90`, distinct du commit du tag de release ; ne pas les assimiler. Roues non retéléchargées ni rehachées pendant cette revue ; aucune exécution x86-64. |
| D11S02 | PyTorch, [registre des avis](https://github.com/pytorch/pytorch/security/advisories) et cinq fiches ouvertes : [GHSA-63cw-57p8-fm3p](https://github.com/pytorch/pytorch/security/advisories/GHSA-63cw-57p8-fm3p) (26/01/2026), [GHSA-53q9-r3pm-6pq6](https://github.com/pytorch/pytorch/security/advisories/GHSA-53q9-r3pm-6pq6) (17/04/2025), [GHSA-2rj9-7h5r-q4h8](https://github.com/pytorch/pytorch/security/advisories/GHSA-2rj9-7h5r-q4h8) et [GHSA-g6v3-crfc-cggj](https://github.com/pytorch/pytorch/security/advisories/GHSA-g6v3-crfc-cggj) (29/09/2025), [GHSA-hw6r-g8gj-2987](https://github.com/pytorch/pytorch/security/advisories/GHSA-hw6r-g8gj-2987) (30/08/2023), sections Affected/Patched versions et Description | Les quatre avis runtime indiquent respectivement des corrections en `2.10.0`, `2.6.0`, `2.9.0` et `2.1.0` : la version publique `2.14.0` est hors de leurs plages affectées. Le cinquième concerne une action CI de PyTorch, pas la roue d'inférence installée. La variante CPU ne constitue pas une exemption aux défauts de désérialisation. Comparaison documentaire de versions, pas audit binaire ni preuve d'absence d'autres défauts. |
| D11S03 | PyTorch, [release 2.14.0](https://github.com/pytorch/pytorch/releases/tag/v2.14.0) du 02/09/2026, sections Backwards Incompatible Changes, Deprecations, Security ; [release 2.14.1](https://github.com/pytorch/pytorch/releases/tag/v2.14.1) du 30/09/2026, dernière release d'après [l'API officielle](https://api.github.com/repos/pytorch/pytorch/releases/latest) ; [politique au commit déclaré par la roue](https://github.com/pytorch/pytorch/blob/08187d9e0fba026dc8217405802ab5381dc88d90/SECURITY.md) et [sérialisation 2.14](https://docs.pytorch.org/docs/2.14/notes/serialization.html#weights-only-security) | 2.14 retire notamment `torch.cholesky`, `torch.qr` et l'argument `use_cuda` des profilers, et rend visibles les avertissements TorchScript ; ces changements ne sont pas une migration effectuée ici. 2.14.1 corrige des problèmes annoncés MPS/CUDA 13.2, non directement ceux de la roue CPU ; ses roues CPU CP312 existent dans l'index, mais n'ont pas été essayées. Le mainteneur n'applique les correctifs de sécurité qu'à la release courante. `weights_only=True` réduit le risque sans garantir l'absence de DoS/corruption ; Docling installé l'emploie pour ses checkpoints TableFormer. Ne pas recommander une montée de version sans contrat, retour arrière, empreintes et non-régression mesurée. |
| D11S04 | indygreg/python-zstandard, [release 0.25.0](https://github.com/indygreg/python-zstandard/releases/tag/0.25.0) du 14/09/2025, dernière release d'après [l'API](https://api.github.com/repos/indygreg/python-zstandard/releases/latest) ; [changelog immuable](https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/docs/news.rst), sections 0.25.0/0.24.0 ; [métadonnées PyPI 0.25.0](https://pypi.org/pypi/zstandard/0.25.0/json) | Version installée `0.25.0`, backend `cext`, libzstd `1.5.7`, roue CP312 manylinux2014 aarch64 non retirée ; SHA publié `6dffecc3…52ea` identique à `uv.lock`, pas rehachage de la roue. 0.25.0 modifie le build setuptools, corrige les noms qualifiés des types C utilisés par le pickling et accepte une libzstd externe `>=1.5.6`. Le changement manylinux_2_28 des roues Python 3.14 ne décrit pas la roue CP312 en place. |
| D11S05 | [Politique python-zstandard](https://github.com/indygreg/python-zstandard/security/policy) et [registre de ses avis](https://github.com/indygreg/python-zstandard/security/advisories) ; [avis de Zstandard upstream](https://github.com/facebook/zstd/security/advisories) ; [release Zstandard 1.5.7](https://github.com/facebook/zstd/releases/tag/v1.5.7) du 19/02/2025 ; [décompression python-zstandard 0.25.0](https://python-zstandard.readthedocs.io/en/0.25.0/decompressor.html), `stream_reader` | Les deux registres affichent aucun avis publié ; aucune absence de vulnérabilité n'en découle. La politique python-zstandard ne supporte que sa dernière release, actuellement installée. Le dépôt demande explicitement `read_across_frames=True` et `closefd=False` (`services/runtime/artifacts.py`) : conserver ce contrat lors d'une éventuelle migration, avec contrôle des fenêtres, archives invalides, membres et empreintes. Ces tests n'ont pas été rejoués dans cette recherche. Le libellé de documentation `max_window_size` en KiB diverge du passage direct au setter C versionné : ne pas redimensionner la constante sur ce seul libellé. |
| D11S06 | Ollama, [API de la release 0.35.0](https://api.github.com/repos/ollama/ollama/releases/tags/v0.35.0) du 28/09/2026 ; [install.sh](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/scripts/install.sh) et [Dockerfile](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/Dockerfile) au commit immuable du tag ; [API latest](https://api.github.com/repos/ollama/ollama/releases/latest) et [API 0.35.1](https://api.github.com/repos/ollama/ollama/releases/tags/v0.35.1) du 29/09/2026 | Actif `jetpack5` : 297 201 571 octets, SHA `f7f1a7e8…0f5b`, identique au verrou et au manifeste local ; quatre fichiers et trois liens présents, tailles conformes au manifeste, sans rehachage complet. Le complément est construit avec `r35.4.1` et choisi pour R35 ; aucune installation de pilote n'est déduite de cette compatibilité. 0.35.1 est annoncée par l'API actuelle, avec évolution des modèles de décision et du moteur ; aucun avis de sécurité propre à `jetpack5` dans ces notes. La page HTML du tag 0.35.1 diffère du corps et des dates de l'API consultée : divergence conservée au rapport, pas contrat de migration établi. |
| D11S07 | Ollama, [registre des avis](https://github.com/ollama/ollama/security/advisories) et [politique immuable 0.35.0](https://github.com/ollama/ollama/blob/cc4069396f3ad2c370c53eed2e4a42ac13adab84/SECURITY.md) ; NVIDIA, [Product Security](https://www.nvidia.com/en-us/security/) puis [index officiels au commit 08d1a287…](https://github.com/NVIDIA/product-security/tree/08d1a287ef3f1fc250f3bdaca913a1d4cff6f5b3), bulletins CUDA Toolkit 5334, 5373, 5446, 5456, 5469, 5517, 5548, 5564, 5577, 5594, 5643, 5661 et [5755](https://github.com/NVIDIA/product-security/blob/08d1a287ef3f1fc250f3bdaca913a1d4cff6f5b3/2026/5755/5755.md), sections Details/Security Updates | Ollama affiche aucun avis publié ; sa politique recommande de protéger les instances et de maintenir la version. Les bulletins CUDA lus concernent cuobjdump, nvdisasm, Nsight, nvJPEG/nvJPEG2000 et nvTIFF, absents des quatre fichiers du complément installé (`libggml-cuda`, `libcublas`, `libcublasLt`, `libcudart`). Aucune applicabilité directe de ces avis à ces quatre fichiers n'est établie ; cela ne certifie pas ces bibliothèques ni tout le pilote hôte. L'index web dynamique incomplet a été complété par le dépôt PSIRT officiel, sans substitution tierce. |
| D11S08 | NVIDIA, [bulletin Jetson/IGX 5716 du 14/10/2025](https://github.com/NVIDIA/product-security/blob/08d1a287ef3f1fc250f3bdaca913a1d4cff6f5b3/2025/5716/5716.md), sections Details/Security Updates ; [bulletin 5797 du 31/03/2026](https://github.com/NVIDIA/product-security/blob/08d1a287ef3f1fc250f3bdaca913a1d4cff6f5b3/2026/5797/5797.md), mêmes sections ; `/etc/nv_tegra_release` relu lors de cette consultation | **Risque hôte distinct :** L4T constatée `35.4.1` est dans les plages Orin de 5716 (`<=35.6.2`, corrigé en `35.6.3`) : CVE-2025-33177, allocations NvMap/DoS local ; CVE-2025-33182, UEFI/authentification et altération du Device Tree. 5797 inclut L4T 35 antérieure à `35.6.4` : CVE-2026-24148 (initialisation/identité machine), CVE-2026-24154 (initrd, arguments, accès physique) et CVE-2026-24153 (nvluks). Applicabilité documentaire de version, conditions locales d'exploitation non testées. Ce n'est ni un défaut démontré des quatre bibliothèques Ollama ni une qualification de sécurité de l'OS ; le repli CPU ne corrige pas ces risques hôte. Mise à jour OS/pilote hors mandat et sans élévation autorisée : action à arbitrer, aucune modification engagée et aucune clôture globale D11. |

## Complément actuel CPython webbrowser et W023 (D11.1, 2 octobre 2026)

Consultation officielle du 02/10/2026 entre 20:02:53 et 20:11:25 UTC, puis relecture des deux sources par l'intégrateur vers 20:13 UTC. Elle complète le registre sans reconstituer la recherche du 01/10. CPython installé : 3.12.14. Rapport de contrat et comparaisons d'octets hors Git : `.runtime/qa/r15-editorial-20261002T191600Z/webbrowser-source/sources.json` ; inspection de signature et liaison de `new=2`, sans appel de navigateur, création de session ou requête à l'API projet. Deux routes officielles en échec ont été conservées ; alternatives officielles accessibles, aucune substitution tierce.

| ID | Source officielle/version, section | Apport et limite |
|---|---|---|
| WB01 | Python Software Foundation, [webbrowser — Python 3.12](https://docs.python.org/3.12/library/webbrowser.html), introduction Unix/BROWSER, `open` et contrôleurs ; documentation courante 3.12.15, mise à jour du 01/10/2026 à 15:25 UTC | `new=2` demande un onglet si possible ; le booléen ne certifie ni chargement de l'atelier ni consommation de sa session. Sans affichage graphique, un navigateur texte peut bloquer jusqu'à sa fermeture. Documentation courante distincte de la version locale ; aucune observation du navigateur natif déduite. |
| WB02 | Mainteneurs CPython, [module au tag v3.12.14](https://github.com/python/cpython/blob/v3.12.14/Lib/webbrowser.py) et [source immuable du commit 2abcf904b8dac8c999d2b3aac76681abb333798a](https://raw.githubusercontent.com/python/cpython/2abcf904b8dac8c999d2b3aac76681abb333798a/Lib/webbrowser.py), `open`, contrôleurs et sélection Unix | Les deux fichiers officiels sont identiques aux 24 207 octets du module installé, SHA-256 `8a7d3cea5e22f227b2fbfcdb21be2ffc3f1c940d2ea26d2da479e1efeec49388`. Signature `open(url, new=0, autoraise=True)` compatible avec `webbrowser.open(url, new=2)` du CLI. Plusieurs contrôleurs passent l'URL dans les arguments de processus ; `DISPLAY`, `WAYLAND_DISPLAY`, `TERM`, `BROWSER` et les exécutables disponibles influent sur la sélection. Contrat source seulement : ni droits effectifs de lecture de `/proc`, ni audit hooks, ni rendu/session qualifiés. |

## Préparation de la recette frontend isolée (R15-2, 2 octobre 2026)

Sources ouvertes le 02/10/2026 entre 20:49 et 20:51 UTC. Périmètre : enveloppe du build existant, export statique et séparation des écritures QA. Aucune migration de framework, installation ou qualification navigateur déduite. Le préflight reste une préparation : `.runtime/qa/r15-editorial-20261002T191600Z/build-preflight.json`.

| ID | Source officielle/version, section et date | Apport et limite |
|---|---|---|
| R15S01 | util-linux, [manuel flock au commit d4319b91c9d7d69e7b954fc66819214f81501312](https://raw.githubusercontent.com/util-linux/util-linux/d4319b91c9d7d69e7b954fc66819214f81501312/sys-utils/flock.1), synopsis, `-n`, `-o`, `-E` et statut de sortie ; commit du tag `v2.34`, tag daté du 14/06/2019, manuel daté juillet 2014 | Version locale `2.34` et aide concordantes. `-n` refuse d'attendre ; `-o` garde le verrou dans l'enveloppe sans le transmettre au build ; `-E 75` distingue le conflit. Sonde sur le verrou commun à 20:50 UTC : sortie 75, commande témoin non lancée. L'API GitHub refusée par le navigateur a répondu par HTTPS officiel ; aucun contournement ou déverrouillage. Aucun build effectué. |
| R15S02 | Vercel, [export statique au tag Next.js v16.3.7](https://raw.githubusercontent.com/vercel/next.js/v16.3.7/docs/01-app/02-guides/static-exports.mdx), configuration et déploiement ; [guide courant](https://nextjs.org/docs/app/guides/static-exports), mis à jour le 25/08/2026, version affichée `16.3.8` | Next installé `16.3.7` distingué du guide courant. Le contrat `output: export` et le dossier `out` concordent avec les sources installées et `next.config.mjs`. `build-monitored.py` calcule son dossier depuis son fichier réel ; déplacer uniquement les preuves ne déplace pas ses écritures. La copie physique QA doit encore réussir le vrai build et servir le rendu vérifié ; aucun succès déduit de cette concordance. |

## Oracle de conservation plein texte (D03, 2 octobre 2026)

Documentation officielle consultée le 02/10/2026 ; date de publication de la page non établie. Python local `3.12.14`, SQLite lié `3.53.1`, constatés par interrogation du module. Cette consultation vise le pilote QA, pas une modification du schéma applicatif. Source consignée avant la sonde locale, exécutée à 21:34:54 UTC : `.runtime/qa/r15-editorial-20261002T191600Z/fts-source-probe/result.json`.

| ID | Source officielle et section | Apport et limite |
|---|---|---|
| D03S01 | SQLite, [FTS5](https://www.sqlite.org/fts5.html), §4.4.3 tables à contenu externe et §8 `fts5vocab` | Le comptage sans recherche dans une table à contenu externe ne prouve pas l'absence de postings. Contrat local PASS sur base synthétique : table `temp` en mémoire visant l'index `main`, lecture des rowids par `instance`, base principale ouverte `mode=ro`, octets inchangés et écriture refusée. Témoin négatif : suppression synthétique sans trigger, comptage externe nul mais posting orphelin détecté. Le chemin officiel de source au tag `version-3.53.1` n'a pas pu être ouvert par le navigateur ; aucune concordance d'octets avec ce tag ni qualification native D03 n'est affirmée. Aucun terme ou contenu privé envoyé à une source externe. |

## Contrôles de qualité frontend (R15, 2 octobre 2026)

Consultations officielles du 02/10/2026 vers 22:15–22:24 UTC, avant toute adoption d'un linter ; contrat de l'annonceur installé relu à 22:33. Analyse privée `frontend-pilot/lint-analysis/LINT_REVIEW.md` sous QA R15, SHA `c3cd217d0ea271088de9b617ec65efce8c4651c171a26d6e2c87b188bdf1e19d`. Next/React/TypeScript installés : `16.3.7`/`19.3.0`/`5.9.3`. Aucun paquet, plugin, règle ou installation qualifié par cette seule lecture.

| ID | Source officielle/version et section | Apport et limite |
|---|---|---|
| R15S03 | Vercel, [configuration ESLint](https://nextjs.org/docs/app/api-reference/config/eslint), guide courant `16.3.8`, mis à jour le 25/08/2026 ; [paquet au tag v16.3.7](https://raw.githubusercontent.com/vercel/next.js/v16.3.7/packages/eslint-config-next/package.json), exports et peers | CLI ESLint et configuration flat distincts du typage/build ; configs Core Web Vitals et TypeScript composables. Next 16 n'a plus `next lint`. Peers directs : ESLint ≥9, TypeScript ≥3.3.1 ; ils ne prouvent pas la compatibilité du graphe transitif réellement résolu. Aucun changement de Next/React/TS demandé. |
| R15S04 | Équipe ESLint/OpenJS, [support des versions](https://eslint.org/version-support/), tableau Current Release Lines, publication non datée | La ligne 10 est maintenue ; la ligne 9 est EOL depuis le 06/08/2026. Ne pas choisir une version abandonnée pour obtenir un résultat vert. Analyse de la version exacte et des plugins encore à réaliser ; aucun support commercial supposé. |
| R15S05 | Équipe ESLint, [migration vers v10](https://eslint.org/docs/latest/use/migrate-to-10.0.0), engines, recherche de configuration, API supprimées | Node 24.16.0 satisfait le prérequis Node de v10 ; recherche de config par fichier et suppressions d'API de plugins à contrôler. C'est un prérequis, pas une recette de compatibilité de Next ou de ses plugins. |
| R15S06 | Source officielle installée `apps/web/node_modules/next/dist/client/components/app-router-announcer.js`, Next `16.3.7`, lignes 13–33 ; SHA `70aac21e21d9acbfa4086f98742e44aa6e601ee018b6db643e421bd5ec870615` | L'annonceur `role=alert` est dans un shadow root ouvert, ajouté à `document.body`, hors du `main` de session. Les deux échecs réels QA R15 retrouvent ce nœud avec l'alerte applicative ; cibler `main` corrige le sélecteur sans retirer l'accessibilité ou l'assertion. Cette concordance explique le test rouge, sans valider son rejeu ni qualifier le produit global. |
| R15S07 | Métadonnées officielles npm relues le 02/10 vers 22:51 UTC : [eslint 10.12.0](https://registry.npmjs.org/eslint/10.12.0), [@eslint/js 10.0.1](https://registry.npmjs.org/@eslint%2Fjs/10.0.1), [plugin Next 16.3.7](https://registry.npmjs.org/@next%2Feslint-plugin-next/16.3.7), engines/peers/dépendances | Versions résolues une fois, à verrouiller avant adoption. ESLint et JS acceptent Node 24 ; JS déclare ESLint ^10. Le plugin Next n'a pas de déclaration peer ESLint : son absence ne prouve pas sa compatibilité. Le navigateur a refusé son URL de registre ; la lecture HTTPS officielle par Node a réussi. Pas d'installation ni d'exécution déduite. |
| R15S08 | Métadonnées officielles npm, même consultation : [react 7.37.5](https://registry.npmjs.org/eslint-plugin-react/7.37.5), [import 2.32.0](https://registry.npmjs.org/eslint-plugin-import/2.32.0), [jsx-a11y 6.10.2](https://registry.npmjs.org/eslint-plugin-jsx-a11y/6.10.2), peers ; [guide Next](https://nextjs.org/docs/app/api-reference/config/eslint), « Using the plugin directly » | Les trois plugins ne déclarent pas ESLint 10 ; le peer large d'eslint-config-next ne suffit donc pas à qualifier leur combinaison. Le guide décrit une composition par plugin Next direct. Voie retenue pour l'essai à venir, avec JS/TS/hooks maintenus ; elle n'inclut pas les règles propres à ces trois plugins incompatibles et ne doit pas être présentée comme le preset Next complet. Accessibilité et rendu restent à tester séparément. |
| R15S09 | [typescript-eslint, démarrage/configuration](https://typescript-eslint.io/getting-started/), `defineConfig`, recommandé ; [métadonnées 8.71.0](https://registry.npmjs.org/typescript-eslint/8.71.0) ; [React, plugin Hooks](https://react.dev/reference/eslint-plugin-react-hooks), règles recommandées ; [métadonnées Hooks 7.1.1](https://registry.npmjs.org/eslint-plugin-react-hooks/7.1.1) | TS déclare ESLint ^10 et TypeScript ≥4.8.4 <6.1, compatible au niveau des peers avec TS local 5.9.3 ; Hooks déclare ESLint ^10 et Node ≥18. Le preset Hooks inclut dépendances, pureté, refs et diagnostics de compilateur, même sans compiler l'application. Ces contrats doivent encore être exercés sur le code ; aucun diagnostic ignoré pour obtenir un vert. |
| R15S10 | [ESLint, configuration flat](https://eslint.org/docs/latest/use/configure/configuration-files), fichiers, `languageOptions`, plugins, `extends`, `globalIgnores` ; consultation 02/10 vers 22:52 UTC | Les règles s'appliquent aux extensions explicitement incluses ; les exclusions globales portent sur les sorties générées, pas sur les sources/tests/scripts. Avec `--config`, les globs sont relatifs au cwd ; une configuration privée d'essai peut donc exercer le vrai code sans modifier ses dépendances partagées. Lecture de contrat, pas lint exécuté. |
| R15S11 | [ESLint, variables globales prédéfinies](https://eslint.org/docs/latest/use/configure/language-options#predefined-global-variables) ; [globals 17.13.0, métadonnées officielles](https://registry.npmjs.org/globals/17.13.0), consultés vers 22:52 UTC | Jeux Node et navigateur distincts via `languageOptions.globals`. Node ≥18 déclaré, compatible avec Node 24.16.0. Les tests Playwright peuvent contenir du code Node et des callbacks navigateur ; ce périmètre ne doit pas être confondu avec celui des sources applicatives. Aucun lint exécuté par la lecture. |
| R15S12 | PSF, [os.link/os.unlink, Python 3.12](https://docs.python.org/3.12/library/os.html#os.link), documentation courante 3.12.15, consultée vers 22:55 UTC ; signatures installées 3.12.14 relevées dans `frontend-pilot/test-only-v4/delivery-v4.json` | Un lien dur donne un second nom au fichier ; retirer l'ancien nom après identité/hash vérifiés conserve les octets à l'emplacement d'archive privé. Contrat utilisé pour l'auth QA connue du passage rouge, jamais pour un stockage utilisateur. Les tests purs utilisent des octets synthétiques ; aucune archive réelle ni preuve forensique d'origine autonome déduite de cette source. |
| R15S13 | Vercel, [index du plugin Next au tag v16.3.7](https://raw.githubusercontent.com/vercel/next.js/v16.3.7/packages/eslint-plugin-next/src/index.ts), `recommended`, `core-web-vitals` et règles ; Meta, [README du plugin Hooks](https://raw.githubusercontent.com/facebook/react/main/packages/eslint-plugin-react-hooks/README.md), config flat/recommandée ; relus vers 22:54–22:55 UTC | Next exporte bien les deux presets dont les règles sont composées ; le preset Core Web Vitals reprend les recommandations. Le README Hooks sur branche mobile n'identifie pas à lui seul les octets 7.1.1 : exports/règles installés à contrôler avant lint. Pas de règle désactivée ni de compatibilité d'exécution déduite de cette lecture. |
| R15S14 | Meta, [état ajusté lors d'un changement de prop](https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes), [useCallback](https://react.dev/reference/react/useCallback), [useEffect](https://react.dev/reference/react/useEffect) et [useEffectEvent](https://react.dev/reference/react/useEffectEvent), React 19.3, relus vers 23:03 UTC | Pour un reset partiel, état précédent et garde explicite permettent de corriger le même composant avant commit sans effet en cascade ; sinon dériver la valeur ou utiliser une clé. DOM, tâches PDF et listeners restent dans effets/événements, avec nettoyage. Callback mémoïsé à dépendances exactes pour éviter de relancer le rendu PDF après chaque mesure de hauteur ; pas de ref lue au rendu. Effect Event réservé à une vraie notification d'effet, pas un moyen de cacher ses dépendances ni un callback à transmettre aux enfants. Ces contrats guident la correction des diagnostics du lint, sans constituer une preuve navigateur. |
| R15S15 | Meta, [useImperativeHandle](https://react.dev/reference/react/useImperativeHandle), [callbacks de ref DOM](https://react.dev/reference/react-dom/components/common#ref-callback), [useSyncExternalStore](https://react.dev/reference/react/useSyncExternalStore), React 19.3 ; consultation du sous-agent 23:15 UTC, contrats relus par l'intégrateur ensuite | Handle impératif construit par React avec dépendances complètes, pas mutation du prop au rendu. Ref DOM stable avec nettoyage symétrique au commit ; StrictMode exerce un cycle supplémentaire. Snapshot serveur identique pendant l'hydratation ; accès navigateur seulement après ce snapshot. Signatures React/@types 19.3 installées confrontées ; cette lecture ne prouve ni focus/portails ni session réelle. |
| R15S16 | Équipe ESLint, [API Node](https://eslint.org/docs/latest/integrate/nodejs-api), constructeur, `lintText`, `isPathIgnored`, relus avant les témoins privés | `cwd` et `overrideConfigFile` explicites ; `filePath` sélectionne les règles. Un fichier ignoré peut produire un tableau vide ou un avertissement : ce résultat ne valide pas un témoin positif. `fix:false`, aucun cache/fichier applicatif réécrit. Les témoins synthétiques doivent refuser syntaxe/règles attendues et accepter les cas valides séparément ; ils ne constituent pas une recette produit. |
| R15S17 | Équipe pnpm, [install, branche 10.x](https://pnpm.io/10.x/cli/install), `--frozen-lockfile`, `--lockfile-only`, `--ignore-scripts` ; [réglages 10.x](https://pnpm.io/10.x/settings), consultés le 02/10/2026 vers 23:48 UTC ; source distribuée de pnpm `10.34.1`, `validateModules`, `checkCompatibility`, `readModulesManifest`, SHA `a2383215978f913ac3d4afe6a435b15035ff6e7891663a858a40d79eb8d59b0f` | Le verrou seul n'installe pas les dépendances ; le mode frozen refuse sa mise à jour. Le refus non-TTY observé intervient avant `removeContentsOfDir` dans la version installée : ne pas désactiver cette protection pour recréer le pool partagé. Installer le même manifeste/verrou dans un nouveau dossier physique privé, puis remplacer uniquement le lien local `node_modules` après contrôles, en conservant son ancienne cible pour reprise. La page courante 10.x mentionne aussi des changements de `10.34.2`, non appliqués à `10.34.1` ; aucune cause précise du désaccord de layout ni compatibilité exécutée déduite de la consultation. |
| R15S18 | Meta, [règle set-state-in-effect](https://react.dev/reference/eslint-plugin-react-hooks/lints/set-state-in-effect) et [réponses réseau dans useEffect](https://react.dev/reference/react/useEffect#fetching-data-with-effects), React 19.3 : sous-agent à 00:09 UTC le 03/10/2026, intégrateur à 00:10–00:11 UTC ; source distribuée Hooks 7.1.1, `getSetStateCall` à 46429, SHA `d401e94560ab2660e40fe59a3408828b96d78e9929a22358386aa51acbe32e2b` | Chargement initial fourni par l'état initial ; la mise en attente d'une relance appartient à l'événement utilisateur. La mise à jour depuis la réponse réelle reste dans son callback, sans temporisation artificielle. Deux variantes await ont passé le témoin d'absence de setter synchrone mais sont restées rouges au lint : source du plugin et observation d'exécution distinctes, pas motif pour désactiver une règle. Complément au contrat React déjà consigné R15S14 ; limites de nettoyage/réponses concurrentes et comportement navigateur restent à vérifier, aucune preuve produit déduite de la documentation. |
| R15S19 | Microsoft/mainteneurs Playwright, [Route](https://playwright.dev/docs/api/class-route) (`abort`, `continue`, `fetch`, `fulfill`), [configuration](https://playwright.dev/docs/test-configuration), [Locator](https://playwright.dev/docs/api/class-locator) (`getByRole`, visibilité/attente) ; consultation du sous-agent achevée avant le relevé exact 00:36:03 UTC du 03/10/2026, intégrateur à 00:36–00:38 UTC. Types locaux `playwright-core@1.63.0/types/types.d.ts`, SHA `2806f6d7810fba0306066d500cd716a6d1128d90af2c3cf71723e3ea0a8904c4` | `continue` envoie directement au réseau sans les autres handlers ; une route de contexte unique vérifie origine et méthode avant chaque substitution. `fetch` obtient la vraie réponse sans la rendre au navigateur ; les interceptions restent des états UI déclarés, pas une intégration réelle. Configuration explicite, worker unique et zéro retry ; assertions sur rendu observable, sans attente de visibilité déduite de `isVisible`. Documentation courante non versionnée confrontée aux types installés ; aucun navigateur ou parcours qualifié par cette consultation. |
| R15S20 | Microsoft/mainteneurs Playwright, [APIRequest.newContext](https://playwright.dev/docs/api/class-apirequest#api-request-new-context) et [APIRequestContext.storageState](https://playwright.dev/docs/api/class-apirequestcontext#api-request-context-storage-state). Sous-agent : première ouverture 03/10/2026 à 01:14:27 UTC, lecture achevée avant 01:15:57 ; intégrateur : relecture achevée à 01:35:48. Types installés Playwright 1.63.0, SHA `2806f6d7810fba0306066d500cd716a6d1128d90af2c3cf71723e3ea0a8904c4`, signatures à 19270, 19409 et 20326 | Un contexte API autonome possède ses cookies séparés ; `maxRedirects: 0` empêche le suivi automatique. `storageState()` sans chemin retourne la valeur sans écrire : le harnais peut créer un fichier neuf privé et exclusif, lié à l'instance réellement vérifiée, sans reprendre une authentification historique. Contrat courant confronté aux types verrouillés et au `global-setup.ts` du projet ; ne prouve aucune session réellement ouverte. Les requêtes administratives restent limitées à la QA autorisée après vérification native, pas au HOST. |
| R15S21 | W3C, [APG — Dialog (Modal)](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), sections Keyboard Interaction et Note ; WHATWG, [HTML Living Standard — Sequential focus navigation](https://html.spec.whatwg.org/multipage/interaction.html#sequential-focus-navigation), §§ 6.6.5–6.6.6. Consultation de l'intégrateur le 03/10/2026 à 02:08–02:12:23 UTC, après le rouge réel RB03 ; publications courantes non versionnées | Le patron APG demande une boucle Tab/Shift+Tab entre les contrôles du dialogue et privilégie l'action non destructive à l'ouverture d'une confirmation irréversible. L'algorithme HTML peut transférer le focus aux contrôles du navigateur lorsqu'il n'existe plus de candidat suivant : `showModal()` seul ne prouve donc pas cette boucle applicative. Conserver le dialogue natif et son arrière-plan inerte ; compléter seulement le passage aux bornes. Le rouge RB03 prouve `contains(activeElement) = false`, pas la destination du focus ni l'activation du contenu derrière. Ces sources ne remplacent pas le test clavier et l'examen du rendu réel dans le navigateur installé. |
| R15S22 | Microsoft/mainteneurs Playwright, [Page.route](https://playwright.dev/docs/api/class-page#page-route), [BrowserContext.route](https://playwright.dev/docs/api/class-browsercontext#browser-context-route), [Route.fetch](https://playwright.dev/docs/api/class-route#route-fetch), [Browser.newContext](https://playwright.dev/docs/api/class-browser#browser-new-context), [Tracing.start](https://playwright.dev/docs/api/class-tracing#tracing-start). Sous-agent : 03/10/2026 vers 02:42–02:49:25 UTC ; intégrateur : sections pertinentes relues avant 02:52:33 UTC. Types installés Playwright1.63.0 SHA `2806f6d7810fba0306066d500cd716a6d1128d90af2c3cf71723e3ea0a8904c4` | Une route n'intercepte que la première URL d'une redirection ; les Service Workers doivent être bloqués pour contrôler les requêtes. La sonde utilise un dispatch de contexte unique : GET de même origine obtenu par `fetch` avec zéro redirection/retry, réponse native rendue sans modification, refus des3xx. Une seule DELETE UI exacte peut être retenue puis recevoir une erreur simulée, sans requête au backend : état frontend substitué, pas suppression métier. Le contexte reçoit seulement l'auth QA liée à l'instance vérifiée. Une trace de contexte contient opérations/réseau, pas assertions : garder un rapport d'assertions distinct et le ZIP privé, sans inférer une qualification de la consultation. |
| R15S22-W | Microsoft/mainteneurs Playwright, [BrowserContext.routeWebSocket](https://playwright.dev/docs/api/class-browsercontext#browser-context-route-web-socket), [WebSocketRoute.close](https://playwright.dev/docs/api/class-websocketroute#web-socket-route-close) et `connectToServer` ; intégrateur : 03/10/2026 à03:19:18–40 UTC. API depuis1.48, confrontée aux types1.63.0 ci-dessus | Installer la route avant la création des pages ; la route ne se connecte pas au serveur tant que `connectToServer()` n'est pas appelé. Le refus de la sonde ne doit jamais l'appeler. La documentation décrit le mécanisme, pas une absence de WebSocket réellement observée dans une recette. |
| R15S23 | Mainteneurs psutil, [documentation7.2.2 : exe](https://psutil.readthedocs.io/stable/#psutil.Process.exe), [status](https://psutil.readthedocs.io/stable/#psutil.Process.status), [ZombieProcess](https://psutil.readthedocs.io/stable/#psutil.ZombieProcess) ; intégrateur : consultation03/10/2026 à03:22, puis03:28–03:31 UTC. Implémentation installée7.2.2 de `Process.exe`, `_pslinux.Process._readlink` et `status` relue séparément | `exe()` peut être vide lorsque l'exécutable est indéterminable ; ce vide n'établit ni décès ni changement réel. `ZombieProcess` hérite de `NoSuchProcess`. L'implémentation Linux locale vérifie l'état zombie avant le fallback vide ; le garde QA historique intercepte déjà `NoSuchProcess`. L'hypothèse « zombie résolu en répertoire courant » n'est donc pas un défaut démontré. Le refus `owned_identity_executable_changed` du run0301 ne donne ni PID ni paire d'exécutables : instrumenter un nouvel essai sans supprimer le contrôle naissance/exécutable, conserver l'échec ancien. Ces sources ne reconstituent pas l'événement manquant. |
| R15S25 | Python Software Foundation, [select — Polling Objects](https://docs.python.org/3.12/library/select.html#poll-objects), documentation courante 3.12.15, sections register/unregister/poll et masques. Consultation intégrateur du 03/10/2026 vers 04:52 UTC ; consultation de l'auteur V2 consignée séparément dans son snapshot privé avant implémentation | `poll` retourne des couples descripteur/masque et son timeout est en millisecondes ; POLLERR et POLLNVAL ne prouvent pas une terminaison. Une exception levée par le handler interrompt l'attente : préserver sa propagation. Applicable à la QA Linux CPython 3.12.14 installée, sans qualification Windows ni mise à jour. La sonde locale et la recette restent des preuves distinctes de cette référence. |
| R15S24 | Projet Linux man-pages, mainteneur Michael Kerrisk : [pidfd_open(2), NOTES et poll](https://man7.org/linux/man-pages/man2/pidfd_open.2.html), [proc_pid_exe(5)](https://man7.org/linux/man-pages/man5/proc_pid_exe.5.html), pages 6.19 datées du 08/02/2026. Python Software Foundation : [os.pidfd_open](https://docs.python.org/3.12/library/os.html#os.pidfd_open), [signaux et exceptions](https://docs.python.org/3.12/library/signal.html#note-on-signal-handlers-and-exceptions), documentation courante 3.12.15. Intégrateur : sections consultées le 03/10/2026 à 04:35 UTC ; contrat local CPython 3.12.14 `(pid, flags=0)`, `select.poll`, noyau `5.10.120-tegra` vérifiés séparément | Un pidfd sans `PIDFD_THREAD`, ouvert après vérification de l'identité, devient lisible quand le groupe de threads est terminé ; POLLHUP indique la collecte. Cette observation permet d'attendre une fin naturelle, sans signal, ni assimiler un exécutable vide à un décès. Acquisition encadrée par les contrôles de naissance/exécutable ; erreur, timeout ou identité inconnue ne donnent aucune adoption. `/proc/pid/exe` peut aussi devenir indisponible après la fin du thread principal : possibilité documentée, pas cause démontrée du run0415. Python peut lever une exception de signal à une instruction quelconque ; le handler QA actuel traduit SIGTERM en KeyboardInterrupt sans enregistrer le signal, donc le déclencheur initial reste inconnu. La correction proposée conserve les gardes et l'interruption, ajoute une attente de terminaison bornée et un diagnostic privé ; ni test réel ni qualification déduits des sources. Documentation 3.12.15 confrontée à l'API installée, pas une mise à jour de Python ou du noyau. |
| R15S26 | Mainteneur psutil : [documentation 7.2.2, pid_exists](https://psutil.readthedocs.io/stable/#psutil.pid_exists), [exceptions](https://psutil.readthedocs.io/stable/#exceptions), [code POSIX au tag release-7.2.2](https://github.com/giampaolo/psutil/blob/release-7.2.2/psutil/_psposix.py#L26), [code Linux au même tag](https://github.com/giampaolo/psutil/blob/release-7.2.2/psutil/_pslinux.py#L1417) ; projet Linux man-pages, [kill(2), DESCRIPTION](https://man7.org/linux/man-pages/man2/kill.2.html). Consultation intégrateur le 03/10/2026 à 05:37–05:38 UTC ; consultations des axes A/C datées séparément dans leurs rapports privés | `pid_exists` ne vérifie pas la naissance et exclut les TID Linux ; le backend POSIX utilise `kill(pid, 0)`, sans livraison de signal. Une future branche de capture peut constater une absence seulement après `NoSuchProcess` de type exact, pour le même PID, puis `pid_exists(...) is False`. Zombie, erreur d'accès, processus présent ou PID réutilisé restent refusés pour un exécutable attendu inconnu. Le garde d'origine intercepte les sous-classes de `NoSuchProcess` : un refus doit donc rester un `ValueError`, pas propager `ZombieProcess` qui serait ignoré. Ces sources ne prouvent ni le PID ni l'état du candidat perdu dans la recette 0510 ; l'incrément et ses tests restent à livrer. |
| R15S27 | Python Software Foundation : [contextvars, ContextVar et Token](https://docs.python.org/3.12/library/contextvars.html#contextvars.ContextVar), documentation courante 3.12.15. Consultation intégrateur du 03/10/2026 à 06:01 UTC, sections création/get/set/reset et gestion des contextes | Déclarer la variable au niveau module, pas dans une closure : les contextes conservent des références fortes. `set` fournit le token de restauration ; `reset` rétablit l'état antérieur, à conserver dans finally. Applicable au harnais privé CPython 3.12.14, sans mise à jour. Consultation actuelle du draft V3, après sa première implémentation mais avant le delta et sa qualification : création déplacée au niveau module, tests d'isolation/restauration et revue requis. Aucune fuite ni cause du refus 0510 déduite de cette recommandation. |
| R15S28 | WHATWG : [HTML Living Standard, focus delegate](https://html.spec.whatwg.org/multipage/interaction.html#focus-delegate), [tabindex](https://html.spec.whatwg.org/multipage/interaction.html#attr-tabindex), [dialog focusing steps](https://html.spec.whatwg.org/multipage/interactive-elements.html#dialog-focusing-steps). Consultation intégrateur le 03/10/2026 à 06:15–06:16 UTC, édition mise à jour le 02/10/2026 | Sans autofocus, le dialogue recherche normalement un descendant dans l'ordre séquentiel. Un titre `tabIndex=-1` reste focalisable par programme mais normalement hors de cet ordre ; sa présence ne démontre pas qu'il capte le focus initial. Des préférences du navigateur peuvent modifier ce comportement. Revue du code de la confirmation et des assertions, sans modification produit ni assouplissement : RB03 vérifie la boucle et le retour, seule la sonde dédiée exige Annuler initialement. Le rendu réel du navigateur installé reste à examiner ; ni standard ni doubles unitaires ne le qualifient. |
| R15S29 | Python Software Foundation : [sys.exception](https://docs.python.org/3.12/library/sys.html#sys.exception), [time.monotonic](https://docs.python.org/3.12/library/time.html#time.monotonic), [time.sleep](https://docs.python.org/3.12/library/time.html#time.sleep), contrat relu aussi au tag installé [v3.12.14/sys.rst](https://github.com/python/cpython/blob/v3.12.14/Doc/library/sys.rst) et [time.rst](https://github.com/python/cpython/blob/v3.12.14/Doc/library/time.rst) ; mainteneur psutil [create_time, 7.2.2](https://psutil.readthedocs.io/stable/#psutil.Process.create_time). Consultation intégrateur le 03/10/2026 à 06:41–06:43 UTC avant tout incrément suivant | `sys.exception()` donne l'objet du handler actif le plus interne, sinon None : capturer le primaire avant d'entrer dans le handler secondaire. Une attente doit utiliser une différence d'horloge monotone, pas l'heure UTC ; sleep peut dépasser la durée demandée et propage un handler qui lève. `create_time` est mis en cache par objet et utilise l'horloge système : recréer Process pour chaque observation, ne pas confondre naissance et délai. Proposition privée seulement : attente naturelle bornée sans signal/adoption, acceptation uniquement après absence exacte, refus des contradictions. Aucun fait passé reconstitué ni durée garantie par ces contrats ; tests et revue requis avant exécution. |
| R15S30 | Mainteneur psutil : [status et constantes, documentation stable 7.2.2](https://psutil.readthedocs.io/stable/#psutil.Process.status), [implémentation Linux au tag release-7.2.2](https://github.com/giampaolo/psutil/blob/release-7.2.2/psutil/_pslinux.py#L2036). Intégrateur : sections lues le 03/10/2026 à 07:12–07:13 UTC, pendant la relecture du draft V4 ; l'URL `latest` redirige vers le site de développement et n'est pas utilisée comme contrat installé | Le statut est une chaîne issue des constantes ; Linux le lit dans `/proc` et peut retourner une valeur inconnue. Un constructeur réussi et une naissance cohérente ne prouvent pas un processus vivant non zombie. Le draft privé lit donc un statut frais et refuse zombie, dead, valeur inconnue et erreur non vérifiable. Une erreur NoSuchProcess sur une méthode n'est pas l'absence stricte finale : un nouveau constructeur doit la constater séparément. Ces sources ne reconstituent pas l'état OS du candidat 0612 et ne qualifient pas le draft ; tests et revue restent nécessaires. |
| R15S31 | Mozilla : [RenderTask.promise/cancel, PDF.js v6.3.289](https://github.com/mozilla/pdf.js/blob/v6.3.289/src/display/api.js#L3057), [CanvasGraphics.beginDrawing au même tag](https://github.com/mozilla/pdf.js/blob/v6.3.289/src/display/canvas.js#L579). WHATWG : [canvas, manipulation des pixels](https://html.spec.whatwg.org/multipage/canvas.html#dom-context-2d-getimagedata). Microsoft/mainteneurs Playwright : [Locator.evaluate](https://playwright.dev/docs/api/class-locator#locator-evaluate), [screenshot](https://playwright.dev/docs/api/class-locator#locator-screenshot), [expect.poll](https://playwright.dev/docs/test-assertions#expectpoll). Intégrateur : sections lues le 03/10/2026 à 07:12–07:13 UTC ; consultation antérieure de B datée dans son rapport privé ; PDF.js installé 6.3.289 et types Playwright 1.63.0 déjà verrouillés | PDF.js expose une promesse de fin de rendu ; l'annulation la rejette. Le fond peut être rempli de blanc avant le contenu : dimensions et couche texte ne prouvent pas une peinture achevée. `getImageData` lit le bitmap, en coordonnées de celui-ci ; hors bitmap, pixels transparents, et refus SecurityError si origine non conforme. Une capture peut masquer un élément couvert ou ne montrer que la partie défilée ; evaluate n'a plus de limite de temps une fois le locator résolu. Préparation proposée : lire des zones natives visibles, bornées, identifiées et revoir leurs captures, sans dessiner ni modifier le produit. Seuils locaux et stabilité de pixels ne valent ni norme éditeur ni preuve de fin de RenderTask. Aucun parcours réel validé par ces consultations. |
| R15S32 | CSSWG/W3C : [CSSOM getComputedStyle](https://drafts.csswg.org/cssom/#dom-window-getcomputedstyle), Editor's Draft du 31/08/2026, et [CSSOM View elementFromPoint](https://drafts.csswg.org/cssom-view/#dom-document-elementfrompoint). Python Software Foundation : [UUID.__str__, tag installé CPython v3.12.14](https://github.com/python/cpython/blob/v3.12.14/Lib/uuid.py#L259). Intégrateur : sections directement lues le 03/10/2026 à 08:06–08:07 UTC, après le draft privé Q05 V1, avant sa correction V2 et toute qualification native | getComputedStyle expose des valeurs résolues en lecture seule, pas une preuve exhaustive de composition ; elementFromPoint peut ignorer un élément peint avec pointer-events:none. Les contrôles de couverture restent bornés et la lecture humaine des PNG obligatoire. UUID.__str__ produit une forme hexadécimale minuscule hyphénée 8-4-4-4-12, distincte de UUID.hex. Contrat réel vérifié séparément dans services/api/db.py:17–18,218,234 et indexing.py:154–160 : documents/versions/générations via uid(), révision possible via uuid5. Le draft de sonde confondait ces IDs avec l'instance runtime 32hex ; refus nominal à corriger et tester, sans changement produit. Les drafts CSS restent des travaux en cours, pas une qualification du navigateur installé. |
