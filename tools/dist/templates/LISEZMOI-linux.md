# Atelier documentaire : kit hors ligne Linux {{version}}

**Rôle :** guide de ce kit : le vérifier, l'extraire, l'installer, puis trouver les procédures · **Propriétaire :** fabricant du kit (`tools/dist/kit_guide.py`) · **Statut :** Généré · **Référence :** kit `{{kit_id}}`, commit `{{commit}}` · **Mis à jour :** {{built_date}} UTC · **Source de vérité :** `{{manifest_file}}` et documents de `docs/` de ce kit · **Remplace :** —

Ce guide est produit à la fabrication du kit, à partir de son manifeste. Il existe en deux exemplaires identiques : `{{guide_file}}` à la racine du kit et `{{kit_id}}.{{guide_file}}` à côté de l'archive. Les liens vers `docs/` s'ouvrent une fois le kit extrait.

## Ce kit

| Élément | Valeur |
|---|---|
| Version | {{version}}, commit `{{commit_short}}` |
| Plateforme | Linux {{arch}} |
| Modèles livrés | {{models}} |
| Génération des réponses | {{gpu}} |
| Taille du kit extrait | {{kit_size}} |
| Place à prévoir pour l'installation | {{install_shared_size}} au moins avec les emplacements par défaut, qui placent programme et données sur le même volume ; si les données vont sur un autre volume : {{install_size}} pour le programme et {{data_reserve}} libres pour les données |
| Système de référence | {{reference_os}} |
| Installation | {{qualification}} |
| Avis de tiers | `{{notices_file}}` ; usage {{notices_usage}} |

## Avant de commencer

- Poste Linux {{arch}}, glibc {{glibc_min}} ou plus récente, noyau {{kernel_min}} ou plus récent, {{memory_gib_min}} Gio de mémoire au moins{{glibcxx}}.
- Compte utilisateur ordinaire : l'installation n'emploie ni `sudo` ni droit d'administration et n'installe aucun paquet du système.
- Outils du système : {{tools}}. `{{installer}}` prend `sha256sum` et `find` dans `/usr/bin` ou `/bin`, jamais ailleurs dans le PATH ; si l'un manque des deux, il le nomme et s'arrête avant de lancer Python (code 1) : le faire installer par l'administrateur du poste.
- Bibliothèques du système : si l'une manque, l'installateur s'arrête avant toute écriture et la nomme. L'administrateur du poste l'installe ; le paquet indiqué est celui du système de fabrication ({{observed_on}}), à identifier sur un autre système.

{{libraries}}
{{optional_libraries}}
- Place : l'archive occupe un peu plus que le kit ({{kit_size}} et les en-têtes tar), le kit extrait {{kit_size}}, l'installation {{install_shared_size}} au moins avec les emplacements par défaut. Prévoir la somme si les trois partagent un volume.
- Transport : {{transport}}Extraire le kit sur un système de fichiers Linux local, ext4 par exemple : FAT32 et exFAT n'ont pas de liens symboliques, et le kit en contient {{symlinks}}.

## Vérifier et extraire l'archive

Dans le dossier de l'archive, contrôler les deux empreintes (archive et guide) ; `sha256sum` doit répondre « OK » pour chacune. Extraire ensuite vers un dossier d'un volume local, puis entrer dans le kit :

```sh
sha256sum -c {{kit_id}}.tar.sha256
tar -xf {{kit_id}}.tar -C <dossier>
cd <dossier>/{{kit_id}}
```

Une empreinte différente signale une archive altérée ou incomplète : la copier à nouveau, sans l'extraire.

Modèle de menace : la vérification du kit protège contre l'altération ACCIDENTELLE (copie ou transport incomplets, fichiers ajoutés par erreur, déduplication ou fermes de liens, droits perdus). Elle ne protège pas contre une personne qui peut écrire dans le kit : `{{installer}}` lui-même s'exécute sans vérification préalable, et son intégrité repose sur l'empreinte de l'archive (`<kit_id>.tar.sha256`) contrôlée avant extraction. Pour ce kit, il s'agit de `{{kit_id}}.tar.sha256`, contrôlé par la commande ci-dessus.

## Installer

```sh
./{{installer}}
```

L'installateur vérifie le poste et le kit, affiche un récapitulatif (version, modèles, emplacements, place, ports, intégration au bureau) et demande confirmation avant toute écriture. Emplacements par défaut, sous `$XDG_DATA_HOME` s'il désigne un chemin absolu, sinon sous `~/.local/share` : programme dans `{{default_program}}`, données dans `{{default_data}}`. Pour un autre volume, ou pour contrôler le poste sans rien écrire :

```sh
./{{installer}} --emplacement <dossier>
./{{installer}} verifier
```

Une installation existante n'est retrouvée que par le registre des installations, que l'installateur tient à jour sauf avec `--sans-menu`, ou à l'emplacement par défaut. Si l'atelier est déjà installé ailleurs, par exemple par l'installateur d'une version antérieure avec des chemins en argument, `./{{installer}}` seul préparerait une seconde installation, avec une racine des données vide ; son récapitulatif l'indique par la ligne « Installation existante : aucune trouvée » (`./{{installer}} verifier` l'affiche aussi, sans rien écrire) : répondre non, puis mettre à jour l'installation existante en désignant son dossier des versions, celui qui contient le lanceur `{{launcher}}` :

```sh
./{{installer}} update --destination <dossier des versions>
```

Si la place manque sur le volume par défaut, l'installateur propose d'autres volumes avant ce récapitulatif, en rappelant qu'aucune installation n'a été retrouvée : dans ce cas, n'en choisir aucun et lancer la mise à jour ci-dessus.

Options, rapports et emplacements : [Déploiement, kit hors ligne Linux]({{link_deploiement}}).

## Premiers pas

L'entrée « {{menu_name}} » du menu des applications ouvre l'atelier dans le navigateur. Depuis un terminal, la commande `{{user_command}}` fait de même et porte les autres actions :

```sh
{{launcher_commands}}
```

L'atelier reste actif après la fermeture du navigateur, jusqu'à `{{user_command}} arreter`. Actions et menu : [Lanceur atelier et menu]({{link_lanceur}}).

Si la commande `{{user_command}}` n'est pas trouvée, employer le lanceur par son chemin complet, suivi de l'action : `{{default_program}}/{{launcher}} ouvrir` avec les emplacements par défaut, `<dossier des versions>/{{launcher}} ouvrir` sinon ; la fin de l'installation cite ce chemin. C'est le cas dans la session en cours quand `{{user_bin}}` vient d'être créé (il n'entre dans le PATH qu'à une nouvelle session, et seulement si le profil de session l'y ajoute), quand ce dossier n'est pas dans le PATH, et après une installation avec `--sans-menu`, qui ne crée ni entrée de menu ni commande `{{user_command}}`.

## Changer de modèle

{{switch_model}}

## Mettre à jour, revenir en arrière, désinstaller

Si une version plus ancienne est déjà installée, `update` lancé depuis le dossier de ce kit installe cette version à côté d'elle, après une sauvegarde vérifiée des données ; `rollback` revient à la version précédente. Depuis le dossier de ce kit :

```sh
./{{installer}} update
./{{installer}} rollback
./{{installer}} status
./{{installer}} repair
./{{installer}} uninstall
```

`uninstall` retire le dossier d'une version : les données, les sauvegardes et les rapports restent ; les supprimer est une décision de l'utilisateur. Avant de retirer la dernière version, sauvegarder les données (`{{user_command}} ouvrir`, puis `{{user_command}} sauvegarder`) : une réinstallation sur des données sans sauvegarde est refusée, et seule une autre racine des données est alors possible ; le récapitulatif de `uninstall` le rappelle. Conditions et retour arrière : [Déploiement, kit hors ligne Linux]({{link_deploiement}}).

## Sauvegarder

`{{user_command}} sauvegarder` écrit une sauvegarde dans la racine des données, l'atelier démarré (`{{user_command}} ouvrir` d'abord). La copier sur un autre support la protège d'une panne du poste : [Sauvegarde et restauration]({{link_sauvegarde}}).

## Codes de sortie de l'installateur

| Code | Signification |
|---|---|
{{exit_codes}}

## En cas de problème

`{{user_command}} diagnostic` nomme chaque contrôle en échec et l'action possible. Chaque installation ou mise à jour laisse un rapport JSON dans la racine des données. Messages et conduite à tenir : [Installateur et lanceur Linux]({{link_depannage}}).

## Ce dossier

`{{installer}}` est le seul point d'entrée du kit : ne lancer ni `rag.sh` ni `bootstrap.sh` depuis ce dossier, et n'y rien ajouter ni modifier : un fichier modifié ou manquant arrête l'installation ; un fichier ajouté est ignoré par l'installateur, qui le signale sans le copier, sauf un fichier de la liste ci-dessous ou du dossier `<CPython>`, que Python ou le chargeur dynamique liraient avant toute vérification : l'opération s'arrête alors avant de l'employer, avec un message qui le nomme ; `build_kit verify` et l'archivage, côté fabrication, le refusent. Fichiers refusés, chemins relatifs au dossier du kit (`*` : n'importe quel nom, au sens du shell ; `<CPython>` : dossier de l'interpréteur du kit, `python.executable` de `{{manifest_file}}` sans `/bin/python3.12`) :

- par `{{installer}}`, quelle que soit la commande, avant de lancer Python (code 1), modules et paquets qui prendraient la place de ceux de l'installateur : `tools.py`, `tools.pyc`, `tools.so`, `tools.*.so`, `tools/__init__.py`, `tools/dist.py`, `tools/dist/__init__.py`, `tools/*.pyc`, `tools/*.so`, `tools/dist/*.pyc`, `tools/dist/*.so`, `tools/*/__init__.py`, `tools/*/__init__.pyc`, `tools/*/__init__.so`, `tools/*/__init__.*.so`, `tools/dist/*/__init__.py`, `tools/dist/*/__init__.pyc`, `tools/dist/*/__init__.so`, `tools/dist/*/__init__.*.so` ;
- par `{{installer}}` aussi, fichiers que l'interpréteur lit à son démarrage et qui changeraient ses chemins de modules : `<CPython>/bin/*._pth`, `<CPython>/bin/pyvenv.cfg`, `<CPython>/pyvenv.cfg`, `<CPython>/bin/pybuilddir.txt`, `<CPython>/lib/python3*.zip` ;
- par une mise à jour, avant d'exécuter la dérivation des profils du nouveau kit (code 3) : {{update_refusals}}.

`{{installer}}` refuse aussi, quelle que soit la commande et avant de lancer Python (code 1), tout fichier, lien ou fichier spécial ajouté sous `<CPython>`, absent de `{{sums_file}}` et de `{{links_file}}` : une bibliothèque que le chargeur dynamique prendrait avant celles du système, par exemple `<CPython>/lib/librt.so.1` ou `<CPython>/lib/tls/librt.so.1` ; un module ou un dossier de paquet que Python importerait à la place d'un module de la bibliothèque standard, par exemple `<CPython>/lib/python3.12/tarfile/__init__.py` ; tout autre fichier, même anodin, comme `<CPython>/lib/python3.12/NOTES.txt`. Seul y est admis le bytecode des dossiers `__pycache__` (`<CPython>/lib/python3.12/__pycache__/*.pyc`), que `compileall` écrit dans un programme installé et que Python, lancé par `{{installer}}`, ne lit pas.

`{{installer}}` refuse de même, avant de lancer Python (code 1), ce que laissent une copie incomplète, une copie par liens, une déduplication, une copie qui a suivi les liens ou des droits perdus :

- l'interpréteur, un script de l'installateur (`tools/dist/linux_install.py`, `tools/dist/linux_kit.py`, `tools/dist/build_kit.py`), `{{links_file}}`, ou un module ou un fichier de démarrage des deux premiers points ci-dessus inscrit dans `{{sums_file}}`, remplacé par un lien, un dossier ou un fichier spécial, ou dont un dossier du chemin est devenu un lien absent de `{{links_file}}` ;
- sous `<CPython>`, un fichier inscrit dans `{{sums_file}}` absent, sans droit de lecture pour son propriétaire ou devenu lien, dossier ou fichier spécial, un dossier de fichiers inscrits devenu lien absent de `{{links_file}}`, et un lien inscrit dans `{{links_file}}` absent ou devenu fichier ou dossier ;
- l'interpréteur sans droit d'exécution, et tout fichier du premier point sans droit de lecture.

Les refus d'`{{installer}}` décrits ci-dessus nomment le chemin en cause et l'action à mener : dans un kit, le recopier depuis son archive (rubrique « Vérifier et extraire l'archive ») ; dans un programme installé (dossier d'une version, à côté du pointeur `installation.json`), retirer le fichier s'il a été ajouté par erreur ; sinon, pour la version courante, la réinstaller depuis le dossier de son kit ([Réparer un programme installé avec le seul kit de sa version]({{link_reparation}})) ou mettre à jour l'installation depuis le kit d'une autre version, et pour une version précédente, abandonnée ou non désignée, la retirer par la commande que cite le refus, sans la réinstaller. Pour un fichier sans droit de lecture, le refus propose aussi de rétablir ces droits par `chmod -R u+rX`.

Seuls `{{installer}}` lui-même et les fichiers listés de la bibliothèque standard du kit, s'ils ont été modifiés, s'exécutent avant d'être hachés (à la copie) ; `{{installer}}` lit aussi `{{manifest_file}}`, `{{sums_file}}` et `{{links_file}}` avant toute vérification Python. Portée de cette vérification : rubrique « Vérifier et extraire l'archive » ; détail : tableau « Ce qui s'exécute avant la vérification » de [Déploiement, kit hors ligne Linux]({{link_deploiement}}).

Fichiers de contrôle : `{{sums_file}}`, `{{links_file}}`, `{{executables_file}}` et `{{manifest_file}}`. Certains documents de `docs/` renvoient à `RAG_Local_Agents/`, `tests/`, `apps/web/src` ou aux scripts Windows : ces chemins désignent le dépôt du projet, qui n'est pas livré avec ce kit.
