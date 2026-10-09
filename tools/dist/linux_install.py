"""Installation de l'atelier depuis un kit Linux hors ligne : install (commande par défaut), update, rollback, uninstall,
repair, status, verifier, modele et les actions du lanceur `atelier`.

Exécuté par `installer.sh` avec le CPython du kit (`-B -I -S`), bibliothèque standard seule. Aucun droit administrateur :
refus en root, ni sudo, ni service, ni modification du PATH ou des fichiers de session. Écritures limitées à la
destination des versions, à la racine des données et, sauf `--sans-menu`, à l'intégration au bureau du compte : entrée de
menu sous `$XDG_DATA_HOME/applications`, commande `~/.local/bin/atelier`, et registre des installations sous
`$XDG_STATE_HOME/atelier-documentaire` (XDG Base Directory 0.8) ; avec `--sans-menu`, rien n'est écrit hors des dossiers
choisis, registre compris. Emplacements par défaut : `$XDG_DATA_HOME/atelier-documentaire/{programme,donnees}`, ou
`--emplacement <dossier>` pour un autre volume.

Chaque version s'installe dans `<destination>/<kit_id>` ; les données restent dans la racine choisie. La version
courante est désignée par `<destination>/installation.json` ; le lanceur `<destination>/atelier`, l'icône, l'entrée de
menu et la commande de l'utilisateur en sont dérivés. Bascule : tous les fichiers sont préparés (temporaire, fsync), puis
le `rename(2)` du pointeur valide la bascule ; un échec ensuite laisse le pointeur juste, et `repair` régénère le reste.

Ordre d'une installation : précontrôles sans écriture, vérification ciblée du kit (SHA256SUMS contre le manifeste, listes
déclarées, fichiers soumis à ldd, fichiers du kit exécutés ou lus avant la copie), contrôles système (bibliothèques,
libstdc++, ldd, Jetson), récapitulatif confirmé (terminal, ou `--oui`), verrou de l'installateur, copie vérifiée (chaque
fichier haché pendant la copie ; un écart retire la copie et rien n'est désigné), réécriture du préfixe de CPython,
`bootstrap.sh --offline --no-dev`, précompilation, profils, `doctor` (rouge : arrêt), bascule, puis démarrage, contrôle
réel et ouverture. Une mise à jour vérifie les fichiers du nouveau kit qu'elle exécute avant la copie, valide les profils
dérivés et la place de la sauvegarde, puis sauvegarde et vérifie les données de la version en place avant toute copie.

Portée de la vérification. Modèle de menace : la vérification du kit protège contre l'altération ACCIDENTELLE (copie ou
transport incomplets, fichiers ajoutés par erreur, déduplication ou fermes de liens, droits perdus). Elle ne protège pas
contre une personne qui peut écrire dans le kit : `installer.sh` lui-même s'exécute sans vérification préalable, et son
intégrité repose sur l'empreinte de l'archive (`<kit_id>.tar.sha256`) contrôlée avant extraction.

Avant de lancer Python, `installer.sh` lit `kit-manifest.json` et SHA256SUMS, puis vérifie par `sha256sum` (pris dans
/usr/bin ou /bin) l'interpréteur du kit, les trois scripts de l'installateur (`linux_install.py`, `linux_kit.py`,
`build_kit.py`) et SYMLINKS, qu'il ne lit qu'ensuite. Chaque fichier vérifié doit être présent, lisible et un fichier ordinaire,
et aucun dossier de son chemin un lien, sauf déclaré dans SYMLINKS : un lien vers une copie identique ferait hacher la cible,
puis lire par le chargeur dynamique ($ORIGIN) et par Python (préfixe, modules voisins) l'arbre de cette cible. `installer.sh`
refuse les fichiers absents de SHA256SUMS parmi les modules de l'installateur (`tools.py`, `tools.pyc`, `tools*.so` à la
racine ; `tools/__init__.py`, `tools/dist.py`, `tools/dist/__init__.py` ; tout `.pyc` ou `.so` de `tools/` et `tools/dist/` ;
tout `__init__` d'un dossier de paquet de `tools/` ou `tools/dist/`). Dans le dossier de l'interpréteur (`<CPython>`), parcouru
par `find` (pris dans /usr/bin ou /bin), un lien doit figurer dans SYMLINKS, un fichier ordinaire dans SHA256SUMS, et aucun
autre fichier n'est admis (tube, socket, périphérique) ; un dossier ajouté n'y est refusé que par son contenu. Sont ainsi
refusés une bibliothèque que le chargeur dynamique prendrait avant celle du système (DT_RPATH `$ORIGIN/../lib` du binaire et
ses sous-dossiers de capacités matérielles, ld.so(8)), un fichier de démarrage (`._pth`, `pyvenv.cfg`, `pybuilddir.txt`,
`lib/python312.zip`, effectifs malgré `-I -S`), un module ou un dossier de paquet ajouté à la bibliothèque standard, un
fichier listé absent, sans droit de lecture pour son propriétaire, ou remplacé par un lien, un dossier ou un fichier spécial,
et un lien listé absent ou devenu fichier ou dossier. Seul y est admis hors des listes le bytecode des dossiers `__pycache__`
qu'écrit `compileall` dans un programme installé, que Python ne lit pas (`-X pycache_prefix=/dev/null`) ; les bibliothèques
listées (`lib*.so*` sous `<CPython>/lib`, sous-dossiers compris) sont hachées avant le lancement. `installer.sh` ne garde du
PATH que ses éléments absolus : un élément vide ou « . » y désignerait le dossier courant, souvent le kit. Seuls
`installer.sh` lui-même et les fichiers listés de la bibliothèque standard, s'ils ont été modifiés, s'exécutent avant d'être
hachés (à la copie) ; `installer.sh` lit aussi `kit-manifest.json`, SHA256SUMS, SYMLINKS et, dans un programme installé, le
pointeur `installation.json` avant toute vérification Python. Un refus nomme le fichier et l'action : recopier un kit depuis
son archive ; dans un programme installé (pointeur `installation.json` dans le dossier parent), retirer le fichier ajouté par
erreur, sinon, selon ce que le pointeur dit de cette version, réinstaller la version courante (dépannage, section 10.4) ou la
mettre à jour depuis le kit d'une autre version, et retirer une version précédente, abandonnée ou non désignée par
l'installateur de la version courante. `installer.sh --controle-seul` fait ces contrôles sans lancer Python ; `status` les
rejoue pour chaque version désignée et relaie un refus.
Lancé comme script, l'installateur prend sa racine dans le chemin reçu, sans résoudre les liens, et charge `build_kit.py` et
`linux_kit.py` par leur chemin (load_verified_modules) : ce sont ceux qu'`installer.sh` a hachés ; aucun import par nom ne
consulte le kit, dont la racine n'entre pas dans `sys.path`, et aucun bytecode de `__pycache__` n'est lu. La vérification
ciblée en Python compare ensuite SHA256SUMS au manifeste, SYMLINKS et EXECUTABLES à SHA256SUMS, et hache les fichiers soumis
à ldd ; chaque fichier est haché pendant la copie, qui est retirée au moindre écart.
Une mise à jour exécute en outre, avant la copie, `linux_profiles.py derive --check` du nouveau kit par l'environnement de la
version en place : ses sources (PRE_COPY_FILES) et les profils livrés sont vérifiés avant ; le script charge ses modules
`services.runtime` par leur chemin, sous la racine du chemin reçu, sans lire de bytecode ; un `.pyc`, un `.so` ou un dossier
de paquet ajouté dans `services/` ou `services/runtime/` est refusé. SHA256SUMS et le manifeste ne sont ancrés que par
l'empreinte de l'archive, contrôlée avant l'extraction : un kit refait avec ses listes n'est pas détecté.

Graphie des chemins : le pointeur garde la destination telle qu'elle a été tapée (un dossier atteint par un lien), alors
qu'`installer.sh` transmet le chemin physique d'un programme installé ; toute destination reçue est ramenée à celle du pointeur
(pointer_destination), et dossiers de version et marques de propriété se comparent par leur chemin réel (same_path).

Profil principal : celui du modèle par défaut du kit (`default_model`, qwen3.5:4b depuis W045) pour une installation
neuve, sauf `--model`. Une mise à jour garde le profil principal en place sans le convertir ; s'il diffère du modèle par
défaut du nouveau kit, le rapport le signale avec les commandes pour employer ce modèle. `atelier modele <modèle>` (ou
`update --model`) change durablement le modèle principal, sans modifier aucun fichier de profil.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import inspect
import json
import os
import platform
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, TextIO

# Racine du kit ou du programme par le chemin reçu, liens non résolus (R4S-01) : load_verified_modules charge build_kit.py et
# linux_kit.py par le même chemin que celui qu'installer.sh a haché, jamais à côté de la cible d'un lien.
HERE = Path(os.path.abspath(__file__)).parents[2]
# Modules du kit que l'installateur exécute avant sa vérification ciblée, vérifiés par sha256sum dans installer.sh, dans
# l'ordre de leur chargement (linux_kit importe build_kit).
VERIFIED_MODULES = ("build_kit", "linux_kit")


def load_verified_modules(root: Path, main: ModuleType) -> None:
    """Chargement des modules de l'installateur par leur chemin, quand il est lancé comme script (installer.sh, lanceur
    `atelier`), selon la recette « Importing a source file directly » d'importlib (Python 3.12). Les paquets `tools` et
    `tools.dist` sont créés sans dossier (`__path__` vide) : aucun import par nom ne consulte les fichiers du kit, si bien
    qu'un module, un bytecode ou un dossier de paquet ajouté à côté des scripts vérifiés (par exemple
    `tools/dist/linux_kit/__init__.py`, trouvé avant `linux_kit.py` par une recherche par nom) n'est jamais importé, et la
    racine du kit n'entre pas dans sys.path."""
    import importlib.util
    import types

    tools, dist = types.ModuleType("tools"), types.ModuleType("tools.dist")
    for package in (tools, dist):
        package.__path__ = []
        sys.modules[package.__name__] = package
    tools.__dict__["dist"] = dist
    # linux_kit importe tools.dist.linux_install dans des fonctions du fabricant : c'est le module en cours d'exécution.
    sys.modules["tools.dist.linux_install"] = main
    for name in VERIFIED_MODULES:
        spec = importlib.util.spec_from_file_location(f"tools.dist.{name}", root / "tools/dist" / f"{name}.py")
        if spec is None or spec.loader is None:
            raise ImportError(f"tools/dist/{name}.py introuvable dans {root}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        setattr(dist, name, module)


if not __package__:
    # Lancé comme script (python -B -I -S … linux_install.py) : jamais de recherche par nom dans le kit.
    load_verified_modules(HERE, sys.modules[__name__])

from tools.dist import linux_kit  # noqa: E402

# --- Constantes lues par kit_guide.py ---------------------------------------------------------------------------------------
# Source unique des noms, emplacements, commandes, codes de sortie et libellés que le guide LISEZMOI.md du kit reprend
# (tools/dist/kit_guide.py les lit ici) et que linux_kit emploie (icône). Une modification ici change le guide à la
# fabrication suivante ; ne pas les recopier ailleurs.

LAUNCHER = "atelier"                      # lanceur de la destination : <destination>/atelier
USER_COMMAND = "atelier"                  # commande de l'utilisateur : ~/.local/bin/atelier
MENU_NAME = "Atelier documentaire"        # nom de l'entrée de menu
DEFAULT_FOLDER = "atelier-documentaire"   # dossier de l'atelier sous $XDG_DATA_HOME ou sous --emplacement
PROGRAM_FOLDER = "programme"              # destination des versions : <dossier de l'atelier>/programme
DATA_FOLDER = "donnees"                   # racine des données : <dossier de l'atelier>/donnees
INSTALLER_NAME = "installer.sh"
GUIDE_NAME = "LISEZMOI.md"
DESKTOP = "atelier-documentaire.desktop"
ICON = "atelier-documentaire.svg"         # icône publiée à côté du lanceur, désignée par un chemin absolu (clé Icon)
ICON_SOURCE = "tools/dist/assets/atelier-documentaire.svg"  # icône versionnée, générée par tools/dist/make_icon.py
# Règle XDG Base Directory 0.8 : une variable vide, absente ou relative est ignorée.
XDG_RULE = ("$XDG_DATA_HOME et $XDG_STATE_HOME ne sont retenus que s'ils désignent un chemin absolu ; sinon $HOME/.local/share "
            "et $HOME/.local/state.")
DEFAULT_LOCATIONS = {
    "programme": f"${{XDG_DATA_HOME:-$HOME/.local/share}}/{DEFAULT_FOLDER}/{PROGRAM_FOLDER}",
    "donnees": f"${{XDG_DATA_HOME:-$HOME/.local/share}}/{DEFAULT_FOLDER}/{DATA_FOLDER}",
    "menu": f"${{XDG_DATA_HOME:-$HOME/.local/share}}/applications/{DESKTOP}",
    "commande": f"$HOME/.local/bin/{USER_COMMAND}",
    "registre": f"${{XDG_STATE_HOME:-$HOME/.local/state}}/{DEFAULT_FOLDER}/installations.json",
}
INSTALLER_COMMANDS = {
    "install": "installer ce kit (commande par défaut ; propose la mise à jour si une installation existe déjà)",
    "update": "installer ce kit à côté de la version en place, après une sauvegarde vérifiée des données",
    "rollback": "revenir à la version précédente",
    "uninstall": "retirer une version, les anciennes versions (--anciennes) ou tout le programme (--tout) ; données conservées",
    "repair": "régénérer le lanceur, l'icône, l'entrée de menu et la commande atelier ; --menu ou --sans-menu change ce choix",
    "status": "état de l'installation : versions, données, instance, sauvegardes et problèmes relevés",
    "verifier": "contrôler le poste et le kit sans rien écrire",
    "modele": "changer durablement le modèle principal de l'installation",
}
LAUNCHER_ACTIONS = {
    "ouvrir": "démarrer l'atelier si nécessaire et l'ouvrir dans le navigateur (action par défaut)",
    "arreter": "arrêter l'atelier ; documents, index et sauvegardes sont conservés",
    "diagnostic": "vérifier l'atelier et indiquer les corrections possibles",
    "etat": "indiquer si l'atelier est démarré, et avec quel modèle",
    "sauvegarder": "sauvegarder les données dans la racine des données (atelier démarré)",
    "journaux": "afficher les chemins des journaux des services",
    "modele": "changer durablement le modèle principal : atelier modele <modèle>",
}
# Actions de l'entrée de menu (groupes [Desktop Action …]) ; une action « modele-<modèle> » s'ajoute par autre modèle installé.
MENU_ACTIONS = {"arreter": "Arrêter l'atelier", "diagnostic": "Diagnostic de l'atelier", "sauvegarder": "Sauvegarder l'atelier"}
EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_REFUSED, EXIT_SYSTEM, EXIT_PARTIAL, EXIT_INTERRUPTED = 0, 1, 2, 3, 4, 5, 130
EXIT_CODES = {
    EXIT_OK: "réussite",
    EXIT_ERROR: ("autre erreur, ou refus d'installer.sh avant le lancement de Python (compte root, système ou architecture, glibc, "
                 "outil absent de /usr/bin et /bin, manifeste introuvable ou illisible, fichier du kit ou du programme absent, altéré, "
                 "ajouté, remplacé par un lien, un dossier ou un fichier spécial, sans droit de lecture ou d'exécution, dossier de "
                 "l'interpréteur illisible) ; pour status : aucune installation trouvée ou problème relevé"),
    EXIT_USAGE: "usage : commande ou option invalide",
    EXIT_REFUSED: "refus ou annulation avant toute écriture",
    EXIT_SYSTEM: "contrôles du système refusés (bibliothèques, libstdc++, ldd)",
    EXIT_PARTIAL: "échec après le début des écritures : le message dit ce qui a été retiré ou reste désigné",
    EXIT_INTERRUPTED: "interruption",
}
# Libellés à l'écran des étapes ; le rapport JSON garde les identifiants.
STEP_LABELS = {
    "precontroles": "Contrôles du poste et des emplacements", "kit": "Intégrité du kit", "systeme": "Bibliothèques du système",
    "sauvegarde": "Sauvegarde des données de la version en place", "copie": "Copie du programme", "python": "Interpréteur Python",
    "environnement": "Environnement Python isolé", "precompilation": "Précompilation", "profil": "Profils",
    "doctor": "Diagnostic avant démarrage", "bascule": "Activation de la version", "integration": "Intégration au bureau",
    "demarrage": "Démarrage", "verdict": "Diagnostic après démarrage", "controle": "Contrôle réel", "ouverture": "Ouverture",
    "modele": "Modèle principal", "instance": "Instance en marche", "arret": "Arrêt", "donnees": "Données",
    "restauration": "Restauration", "ports": "Ports", "stockage": "Stockage Qdrant", "pointeur": "Pointeur de version",
    "programme": "Programme", "registre": "Registre des installations", "interrompue": "Installation interrompue",
}
# Libellés du bloc de fin d'opération (installation, mise à jour, retour arrière, désinstallation).
END_LABELS = {
    "program": "Programme", "data": "Données", "profile": "Profil principal", "models": "Modèles", "open": "Ouvrir",
    "stop": "Arrêter", "diagnose": "Diagnostiquer", "save": "Sauvegarder", "model": "Changer de modèle", "guide": "Guide",
    "report": "Rapport", "rollback": "Revenir à", "remove": "Retirer", "active_data": "Données actives",
    "old_data": "Ancienne racine conservée, non supprimée", "ports": "Ports", "backups": "Sauvegardes",
    "storage": "Index Qdrant hors de la racine des données", "kept": "Pointeur et rapports", "desktop": "Bureau",
    "update": "Mettre à jour",
}
# Entrées que Qdrant 1.19.1 lit dans son dossier de démarrage, celui de son stockage sous Linux : config/config,
# config/development, config/local et ./static (relevé du runtime, docstring de supervisor.qdrant_working_directory).
QDRANT_READS = ("config", "static")
# Délai laissé aux processus d'une instance arrêtée par la désinstallation pour se terminer : supervisor.stop rend dès que
# l'état écrit dit « stopped », et le superviseur peut alors être encore en train de se terminer.
PROCESS_EXIT_WAIT_S = 10.0
# Réserve de place exigée par une sauvegarde (services/runtime/backup.py) : seuil de la racine des données.
DATA_MIN_FREE_BYTES = 2 * linux_kit.GIB
# Ports de la restauration (services/runtime/backup.py), jamais proposés pour une installation.
RESTORE_PORTS = (8795, 6343, 11445)
PORT_RULE = ("chaque port par défaut occupé est remplacé par le premier port libre au-dessus, distinct des deux autres, entre "
             "1024 et 65535, hors 8795, 6343 et 11445 (ports de la restauration)")
# Attente maximale de `up` (services/runtime/supervisor.py) : seule durée annoncée avant une mesure de recette.
STARTUP_WAIT_MAX_S = 150
# Cible matérielle du projet (D07) : un poste de 16 Go montre environ 15 Gio au noyau.
TARGET_MEMORY_LABEL = "poste de 16 Go"

# --- Constantes internes -----------------------------------------------------------------------------------------------------

POINTER = "installation.json"
REGISTRY = "installations.json"
REGISTRY_FORMAT = "atelier-installations-v1"
LOCK = ".atelier-installateur.lock"
POINTER_FORMAT = "atelier-installation-v1"
DEFAULT_COMMAND = "install"
RED = "rouge"
RUNNING = {"starting", "running", "stopping"}
# Systèmes de fichiers sans liens symboliques ni bit x fiables, ou distants (verrous flock sur volume local seulement).
REFUSED_FILESYSTEMS = {"vfat", "msdos", "exfat", "ntfs", "ntfs3", "fuseblk", "nfs", "nfs4", "cifs", "smb3", "smbfs", "fuse.sshfs", "9p"}
# Volumes non persistants ou images en lecture seule : documents, index et sauvegardes perdus au redémarrage.
VOLATILE_FILESYSTEMS = {"tmpfs", "ramfs", "overlay", "squashfs"}
# Volumes amovibles sans liens ni droits d'exécution : un kit qui y est extrait perd ses liens et ses bits x.
NON_LINUX_FILESYSTEMS = {"vfat", "msdos", "exfat", "ntfs", "ntfs3", "fuseblk"}
# Volumes locaux proposés quand la place manque (jamais réseau, mémoire, pseudo-système ni lecture seule).
LOCAL_FILESYSTEMS = {"ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "jfs", "zfs", "reiserfs"}
# Données d'exécution qui ne doivent jamais exister dans un dossier programme (profil livré employé à tort).
RUNTIME_DATA = (".runtime/data", ".runtime/control", ".runtime/q", ".runtime/qa", "backups")
# Variables héritées sans effet voulu sur l'installation : chemins Python, réglages uv (cache, index, liens, Python).
DROPPED_PREFIXES = ("UV_",)
DROPPED = {"LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "PYTHONNOUSERSITE", "RAG_DATA_DIR"}
KIT_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+_-]*")
PYTHON_EXECUTABLE = re.compile(r"\.runtime/python/([0-9A-Za-z._-]+)/bin/python3\.\d+")
PYTHON_KEY = re.compile(r"[0-9A-Za-z._-]+")
# Nom d'un dossier de version : kit_id du fabricant (<version>+<commit12>-linux-<arch>-<gpu>-<modèles>).
KIT_FOLDER = re.compile(r"[0-9][0-9A-Za-z.]*\+[0-9a-f]{12}-linux-[a-z0-9_]+-[a-z0-9]+-[a-z0-9]+")
LAUNCHER_MARKER = "# Lanceur de l'atelier documentaire"
# Desktop Menu Specification 1.1 (« File locations », <DefaultAppDirs>, « Install Locations ») : le menu des applications
# rassemble les entrées des dossiers applications des données XDG, dont $XDG_DATA_HOME/applications pour l'utilisateur.
MENU_ELSEWHERE = ("--menu <dossier> écrirait l'entrée ailleurs, mais une entrée hors de $XDG_DATA_HOME/applications et des dossiers "
                  "applications de $XDG_DATA_DIRS n'apparaît pas dans le menu des applications")
# Marqueur d'une installation ou d'une reprise en cours, dans la racine des données : retiré après la bascule (fsync du
# dossier) ou par le nettoyage d'un échec ; laissé par un arrêt brutal (SIGKILL, coupure) avant la bascule, il permet à la
# même commande de reprendre exactement. `run` identifie l'exécution (repris dans l'événement de bascule de l'historique du
# pointeur) ; `bascule` est écrit juste avant le rename(2) du pointeur : un marqueur qui l'a atteint n'est jamais repris.
INSTALL_MARKER = "installation-en-cours.json"
MARKER_FORMAT = "atelier-installation-en-cours-v2"
MARKER_KINDS = {"install", "reprise"}
# Fichiers du kit exécutés avant la copie (mise à jour : `linux_profiles.py derive --check` par l'environnement de la version
# en place) et modules qu'ils peuvent importer depuis la racine du kit ; vérifiés avec les profils livrés (model_profiles).
PRE_COPY_FILES = ("tools/dist/linux_profiles.py", "services/__init__.py", "services/runtime/__init__.py",
                  "services/runtime/artifacts.py", "services/runtime/accelerator.py", "services/runtime/platforms.py")
# Paquets de ces modules dans le nouveau kit : un module compilé (.so, chargé avant le .py du même nom), un bytecode sans
# source (.pyc) ou un dossier de paquet (<nom>/__init__.*, trouvé avant <nom>.py) absent de SHA256SUMS y est refusé avant la
# dérivation, qui charge pourtant ses modules par leur chemin (linux_profiles.load_runtime_modules).
PRE_COPY_PACKAGES = ("services", "services/runtime")
PACKAGE_INIT = re.compile(r"__init__(?:\.py|\.pyc|\.so|\..+\.so)")
# Préfixe du bytecode (-X pycache_prefix, Python 3.12) du code exécuté avant sa copie : /dev/null n'est pas un dossier, aucun
# fichier ne peut exister dessous, donc aucun .pyc de __pycache__ n'est lu à la place des sources vérifiées.
NO_BYTECODE = "/dev/null"
COMMAND_MARKER = "Écrit par l'installateur de l'atelier documentaire pour "
# Premier argument d'installer.sh qui fait tous ses contrôles en lecture seule, puis s'arrête avant de lancer Python (code 0, ou
# son refus et le code 1) : status les rejoue pour chaque version désignée (U6-04). Un installateur antérieur, qui ne le connaît
# pas, n'est pas rejoué.
INSTALLER_CHECK_ONLY = "--controle-seul"
# PATH du contrôle rejoué : celui qu'installer.sh se donne sans PATH absolu ; ses outils de contrôle sont pris dans /usr/bin et
# /bin quoi qu'il arrive.
INSTALLER_CHECK_PATH = "/usr/bin:/bin"
PAUSE_ACTIONS = {"diagnostic", "etat", "sauvegarder", "journaux"}
INSTALL_STEPS = ["precontroles", "kit", "systeme", "copie", "environnement", "precompilation", "profil", "doctor", "bascule"]
UPDATE_STEPS = ["precontroles", "kit", "systeme", "sauvegarde", "copie", "environnement", "precompilation", "profil", "doctor", "bascule"]
START_STEPS = ["demarrage", "controle", "ouverture"]
TIMED_STEPS = {"copie", "environnement", "precompilation", "sauvegarde", "demarrage", "controle", "restauration"}
STATE_TEXT = {"starting": "en cours de démarrage", "running": "démarré", "stopping": "arrêt en cours", "stopped": "arrêté"}
INTERRUPTED = {
    "install": "Installation interrompue avant toute écriture : rien n'a été écrit ; relancer la même commande.",
    "update": "Mise à jour interrompue avant toute écriture : rien n'a été installé ; relancer la même commande.",
    "rollback": "Retour arrière interrompu avant toute modification ; relancer la même commande.",
    "uninstall": "Désinstallation interrompue avant toute suppression ; relancer la même commande.",
    "repair": "Réparation interrompue : relancer la même commande.",
    "verifier": "Vérification interrompue : rien n'a été écrit.",
    "status": "Lecture de l'état interrompue : rien n'a été modifié.",
    "modele": "Changement de modèle interrompu : relancer la même commande.",
    "run": "Commande interrompue : l'atelier peut continuer à démarrer ou à s'arrêter ; « atelier etat » l'indique.",
}
UNKNOWN_PROFILE = "un profil inconnu de l'installation"
ROOT_REFUSAL = ("Ne pas lancer l'installateur ni le lanceur avec sudo ni en root : l'atelier s'installe et s'exécute pour votre "
                "compte. Relancer sans sudo ; rien n'a été modifié.")


class InstallError(RuntimeError):
    """Refus ou échec, avec l'état laissé, la correction attendue et le code de sortie (EXIT_CODES)."""

    def __init__(self, message: str, code: int = EXIT_ERROR):
        super().__init__(message)
        self.code = code


class SwitchIncomplete(InstallError):
    """Pointeur basculé, lanceur ou entrée de menu non régénéré : `repair` les reprend depuis le pointeur."""

    def __init__(self, message: str):
        super().__init__(message, EXIT_PARTIAL)


class PrecheckRefusal(InstallError):
    """Précontrôles refusés ; `volumes` : volumes locaux qui ont la place, proposés quand elle manque."""

    def __init__(self, message: str, volumes: list[dict[str, Any]] | None = None):
        super().__init__(message, EXIT_REFUSED)
        self.volumes = volumes or []


class Interrupted(KeyboardInterrupt):
    """Ctrl+C : message de l'état laissé, affiché à la place d'une trace Python (code 130)."""


@dataclass
class Completed:
    returncode: int
    stdout: str
    stderr: str = ""


def child_environment() -> dict[str, str]:
    """Environnement des commandes lancées : celui de l'utilisateur, sans LD_LIBRARY_PATH, chemins Python ni réglages uv
    hérités ; le profil fixe les données (RAG_DATA_DIR réservé aux enfants du superviseur), uv sans fichier de
    configuration de l'utilisateur (UV_NO_CONFIG), Python en UTF-8."""
    environment = {key: value for key, value in os.environ.items() if key not in DROPPED and not key.startswith(DROPPED_PREFIXES)}
    environment["PYTHONUTF8"] = "1"
    environment["UV_NO_CONFIG"] = "1"
    return environment


class SystemRunner:
    def run(self, argv: list[str], *, cwd: Path | None = None, timeout: float | None = None) -> Completed:
        try:
            completed = subprocess.run(argv, cwd=cwd, env=child_environment(), capture_output=True, text=True, encoding="utf-8",
                                       errors="replace", timeout=timeout, stdin=subprocess.DEVNULL, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            return Completed(127, "", str(error))
        return Completed(completed.returncode, completed.stdout, completed.stderr)


def ldconfig_path() -> str | None:
    return shutil.which("ldconfig", path="/sbin:/usr/sbin:/usr/bin:/bin")


def ldconfig_cache() -> dict[str, str]:
    """Bibliothèques connues du chargeur (`ldconfig -p`, lecture seule) : SONAME → chemin ; vide sans ldconfig."""
    ldconfig = ldconfig_path()
    if not ldconfig:
        return {}
    completed = subprocess.run([ldconfig, "-p"], capture_output=True, text=True, errors="replace", check=False, timeout=60,
                               env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    found: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        match = re.match(r"\s+(\S+) \(([^)]*)\) => (\S+)", line)
        if match:
            found.setdefault(match.group(1), match.group(3))
    return found


def unescape_mount(text: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), text)


class SystemProbe:
    """Lectures du poste, sans écriture."""

    def machine(self) -> str:
        return platform.machine()

    def glibc(self) -> str | None:
        return linux_kit.host_glibc()

    def kernel(self) -> str:
        return platform.release()

    def memory_total_gib(self) -> float | None:
        try:
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1024**2
        except (OSError, ValueError, IndexError):
            return None
        return None

    def free_bytes(self, path: Path) -> int:
        return shutil.disk_usage(existing_ancestor(path)).free

    def device(self, path: Path) -> str:
        """Périphérique du volume (majeur:mineur, comme /proc/self/mountinfo) ; POSIX seulement (os.major, os.minor)."""
        if sys.platform == "win32":
            raise InstallError("Installateur Linux seulement", EXIT_REFUSED)
        identity = os.stat(existing_ancestor(path)).st_dev
        return f"{os.major(identity)}:{os.minor(identity)}"

    def mounts(self) -> list[dict[str, Any]]:
        """Montages lus dans /proc/self/mountinfo : point, racine montée, type, noexec, lecture seule, périphérique."""
        found = []
        try:
            lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        for line in lines:
            fields = line.split(" ")
            try:
                tail = fields[fields.index("-") + 1:]
                options = fields[5].split(",")
                found.append({"mount": unescape_mount(fields[4]), "root": unescape_mount(fields[3]), "fstype": tail[0],
                              "noexec": "noexec" in options, "readonly": "ro" in options, "device": fields[2]})
            except (ValueError, IndexError):
                continue
        return found

    def filesystem(self, path: Path) -> dict[str, Any]:
        """Type du système de fichiers (mountinfo, point de montage le plus long) et option noexec (statvfs)."""
        real = os.path.realpath(existing_ancestor(path))
        best, fstype = "", "inconnu"
        for entry in self.mounts():
            point = entry["mount"]
            if (real == point or real.startswith(point.rstrip("/") + "/")) and len(point) >= len(best):
                best, fstype = point, entry["fstype"]
        noexec = False
        if sys.platform != "win32":
            noexec = bool(os.statvfs(existing_ancestor(path)).f_flag & getattr(os, "ST_NOEXEC", 8))
        return {"mount": best, "fstype": fstype, "noexec": noexec}

    def writable(self, path: Path) -> bool:
        return Path(path).is_dir() and os.access(path, os.W_OK | os.X_OK)

    def tree_bytes(self, path: Path) -> int:
        """Taille des fichiers d'un dossier, liens non suivis ; 0 s'il est absent."""
        total = 0
        for root, _, files in os.walk(path, followlinks=False):
            for name in files:
                try:
                    total += os.lstat(os.path.join(root, name)).st_size
                except OSError:
                    continue
        return total

    def os_release(self) -> dict[str, str]:
        return linux_kit.os_release()

    def setpriv(self) -> str | None:
        return shutil.which("setpriv", path="/usr/bin:/bin")

    def ldd(self, binary: Path) -> Completed:
        ldd = shutil.which("ldd", path="/usr/bin:/bin")
        if not ldd:
            return Completed(127, "", "ldd introuvable dans /usr/bin ou /bin")
        environment = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}
        completed = subprocess.run([ldd, str(binary)], env=environment, capture_output=True, text=True, errors="replace", check=False,
                                   timeout=60)
        return Completed(completed.returncode, completed.stdout, completed.stderr)

    def shared_libraries(self) -> set[str] | None:
        """Bibliothèques du cache du chargeur ; None si ldconfig est introuvable (rien n'est alors comparable)."""
        return set(ldconfig_cache()) if ldconfig_path() else None

    def glibcxx_max(self) -> str | None:
        """Version GLIBCXX la plus haute définie par le libstdc++.so.6 du chargeur (chaînes de sa table de versions)."""
        path = ldconfig_cache().get("libstdc++.so.6")
        if not path:
            return None
        try:
            versions = {int(item) for item in re.findall(rb"GLIBCXX_3\.4\.(\d+)", Path(path).read_bytes())}
        except OSError:
            return None
        return f"3.4.{max(versions)}" if versions else None

    def l4t_major(self) -> int | None:
        release = linux_kit.l4t_release()
        return release.get("major") if release else None

    def port_free(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True

    def program_processes(self, program: Path) -> list[tuple[int, str]]:
        """Processus du compte dont l'exécutable est dans `program` (/proc/<pid>/exe), hors du processus courant : une
        instance lancée depuis ce programme, quel que soit son profil (R3S-03). Les processus d'un autre compte, ceux qui
        disparaissent pendant la lecture et ceux dont l'exécutable est illisible sont ignorés. Linux seulement."""
        if sys.platform == "win32" or not os.path.isdir("/proc"):
            return []
        found = []
        for name in os.listdir("/proc"):
            if not name.isdigit() or int(name) == os.getpid():
                continue
            try:
                if os.stat(f"/proc/{name}").st_uid != os.getuid():
                    continue
                executable = os.readlink(f"/proc/{name}/exe").removesuffix(" (deleted)")
            except OSError:
                continue
            if inside(Path(executable), program):
                found.append((int(name), executable))
        return sorted(found)

    def installer_refusal(self, program: Path) -> str | None:
        """Refus que `<program>/installer.sh` opposerait à toute commande (U6-04) : ses contrôles rejoués en lecture seule
        (INSTALLER_CHECK_ONLY, arrêt avant le lancement de Python), par /bin/sh avec PATH=/usr/bin:/bin. None s'il les passe, s'il
        est absent ou s'il ne connaît pas ce mode (installateur antérieur). Linux seulement."""
        script = program / INSTALLER_NAME
        if sys.platform == "win32" or not script.is_file():
            return None
        try:
            if INSTALLER_CHECK_ONLY not in script.read_text(encoding="utf-8", errors="replace"):
                return None
            completed = subprocess.run(["/bin/sh", str(script), INSTALLER_CHECK_ONLY], cwd="/", env={"PATH": INSTALLER_CHECK_PATH},
                                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            return f"contrôles d'{INSTALLER_NAME} impossibles à rejouer ({error})"
        if completed.returncode == 0:
            return None
        return " ".join((completed.stderr or completed.stdout).split()) or f"code de sortie {completed.returncode}"


def existing_ancestor(path: Path) -> Path:
    path = path.absolute()
    while not path.exists():
        path = path.parent
    return path


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def stamp(moment: dt.datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")


def inside(path: Path, folder: Path) -> bool:
    """Vrai si `path` est `folder` ou dessous, chemins réels comparés (liens résolus)."""
    real, base = Path(os.path.realpath(path)), Path(os.path.realpath(folder))
    return real == base or real.is_relative_to(base)


def same_path(first: Path | str, second: Path | str) -> bool:
    """Même emplacement, chemins réels comparés (liens résolus). Le pointeur garde les chemins tels qu'ils ont été tapés (un
    dossier atteint par un lien, comme un volume relié), alors qu'installer.sh transmet le chemin physique du programme qui le
    lance (--kit "$(pwd -P)") et que son refus cite la destination physique (U6-01, R5S-01) : dossiers de version, destinations
    et marques de propriété se comparent ainsi, jamais par leur graphie."""
    return os.path.realpath(first) == os.path.realpath(second)


def owned_by(owner: str | None, destination: Path) -> bool:
    """Marque de propriété (X-Atelier-Destination d'une entrée de menu, marqueur de la commande atelier) écrite pour cette
    destination, sous l'une ou l'autre graphie."""
    return owner is not None and same_path(owner, destination)


def control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    linux_kit.write_atomic(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        value = json.loads(text)
    except ValueError:
        lines = text.splitlines()
        try:
            value = json.loads(lines[-1]) if lines else {}
        except ValueError:
            value = {}
    return value if isinstance(value, dict) else {}


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as reader:
        for block in iter(lambda: reader.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def model_slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", model).strip("-")


def action_slug(model: str) -> str:
    """Identifiant d'action de l'entrée de menu (format des noms de clé : A-Za-z0-9-)."""
    return re.sub(r"[^A-Za-z0-9-]+", "-", model).strip("-")


def model_label(model: str) -> str:
    """Libellé court d'un modèle (« qwen3.5:2b » → « 2B ») ; le modèle tel quel s'il n'a pas de taille."""
    match = re.search(r":(\d+(?:\.\d+)?)b$", model, flags=re.I)
    return f"{match.group(1)}B" if match else model


def make_user_dir(path: Path) -> None:
    """Dossier créé pour l'utilisateur seul (0700, XDG Base Directory 0.8) ; un dossier existant garde ses droits."""
    missing = []
    current = path.absolute()
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        current = current.parent
    for folder in reversed(missing):
        try:
            folder.mkdir(mode=0o700)
        except FileExistsError:
            continue


# --- Nombres et libellés en français ------------------------------------------------------------------------------------------

def fr_number(value: float, decimals: int = 1) -> str:
    """Nombre au format français : virgule décimale, espace fine insécable entre les milliers."""
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def fr_gib(size: int | float) -> str:
    return f"{fr_number(size / linux_kit.GIB, 1)} Gio"


def fr_size(size: int | float) -> str:
    return f"{fr_number(size / linux_kit.GIB, 2)} Gio"


def fr_seconds(seconds: float) -> str:
    if seconds < 60:
        return f"{fr_number(seconds, 0)} s"
    return f"{int(seconds // 60)} min {int(seconds % 60):02d} s"


def fr_utc(text: str | None) -> str | None:
    if not text:
        return None
    try:
        moment = dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.UTC)
    except ValueError:
        return None
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def quoted(*words: str) -> str:
    return shlex.join(words)


def desktop_quote(value: str) -> str:
    """Argument de la clé Exec (Desktop Entry) : `%` doublé, guillemets, puis `"`, `` ` ``, `$` et `\\` précédés d'une barre
    oblique inverse ; la règle d'échappement des chaînes (barre oblique inverse doublée) s'applique ensuite."""
    if control_characters(value):
        raise InstallError(f"Chemin à caractère de contrôle refusé dans une entrée de menu : {value!r}", EXIT_REFUSED)
    quoted_value = '"' + re.sub(r'(["`$\\\\])', r"\\\1", value.replace("%", "%%")) + '"'
    return quoted_value.replace("\\", "\\\\")


def desktop_escape(value: str) -> str:
    """Valeur de type string d'une entrée de menu : barre oblique inverse doublée ; caractères de contrôle refusés."""
    if control_characters(value):
        raise InstallError(f"Chemin à caractère de contrôle refusé dans une entrée de menu : {value!r}", EXIT_REFUSED)
    return value.replace("\\", "\\\\")


def desktop_unescape(value: str) -> str:
    replacements = {"s": " ", "n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
    return re.sub(r"\\(.)", lambda match: replacements.get(match.group(1), match.group(0)), value)


# --- Contexte, rapport et étapes ------------------------------------------------------------------------------------------

def tty(stream: Any) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def read_terminal_line() -> str:
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line.rstrip("\n")


@dataclass
class Context:
    kit: Path
    runner: Any = field(default_factory=SystemRunner)
    probe: Any = field(default_factory=SystemProbe)
    out: TextIO = field(default_factory=lambda: sys.stdout)
    err: TextIO = field(default_factory=lambda: sys.stderr)
    clock: Any = utc_now
    monotonic: Callable[[], float] = time.monotonic
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)
    stdin_tty: bool = field(default_factory=lambda: tty(sys.stdin))
    stdout_tty: bool = field(default_factory=lambda: tty(sys.stdout))
    ask: Callable[[], str] = read_terminal_line
    # Fixé par main : terminal en entrée et en sortie, sans --non-interactif.
    interactive: bool = False

    def say(self, status: str, step: str, detail: str = "", duration: float | None = None) -> None:
        line = f"[{status}] {STEP_LABELS.get(step, step)}" + (f" : {detail}" if detail else "")
        if duration is not None and duration >= 1:
            line += f" ({fr_seconds(duration)})"
        print(line, file=self.out, flush=True)

    def warn(self, text: str) -> None:
        print(f"[orange] {text}", file=self.out, flush=True)

    def question(self, prompt: str) -> str:
        print(prompt, end="", file=self.out, flush=True)
        try:
            answer = self.ask()
        except EOFError:
            answer = ""
        return answer.strip()


class Report:
    def __init__(self, ctx: Context, kind: str, **fields: Any):
        self.ctx = ctx
        self.data: dict[str, Any] = {"format": f"atelier-{kind}-linux-v1", "started_utc": ctx.clock().isoformat(), **fields, "steps": []}
        self.path: Path | None = None
        self.started = ctx.monotonic()
        self.mark = self.started

    def restart(self) -> None:
        self.mark = self.ctx.monotonic()

    def step(self, name: str, status: str, detail: str = "", *, screen: str | None = None) -> None:
        now = self.ctx.monotonic()
        duration = round(max(0.0, now - self.mark), 3)
        self.mark = now
        self.data["steps"].append({"step": name, "status": status, "detail": detail, "at_utc": self.ctx.clock().isoformat(),
                                   "duration_s": float(duration)})
        self.ctx.say(status, name, detail if screen is None else screen, duration if name in TIMED_STEPS else None)

    def save(self) -> None:
        if self.path:
            self.data["finished_utc"] = self.ctx.clock().isoformat()
            self.data["duration_s"] = float(round(max(0.0, self.ctx.monotonic() - self.started), 3))
            write_json_atomic(self.path, self.data)


class Plan:
    """Étapes d'une installation ou d'une mise à jour, annoncées avant leur début avec leur rang."""

    def __init__(self, ctx: Context, report: Report, steps: list[str]):
        self.ctx, self.report, self.steps = ctx, report, steps

    def begin(self, step: str, detail: str = "") -> None:
        index = self.steps.index(step) + 1
        print(f"Étape {index}/{len(self.steps)} — {STEP_LABELS[step]}" + (f" ({detail})" if detail else "") + "…", file=self.ctx.out,
              flush=True)
        self.report.restart()


class Progress:
    """Progression d'une opération sur les fichiers : sur un terminal, ligne réécrite au plus une fois par seconde ; sinon une
    ligne par palier de 10 %."""

    def __init__(self, ctx: Context, label: str, total: int):
        self.ctx, self.label, self.total = ctx, label, total
        self.last_time: float | None = None
        self.last_decile = 0
        self.shown = False

    def __call__(self, done: int, total: int | None = None) -> None:
        total = int(total or self.total or 0)
        if total <= 0:
            return
        done = min(int(done), total)
        text = f"{self.label} : {int(done * 100 / total)} % ({fr_size(done)} sur {fr_size(total)})"
        if self.ctx.stdout_tty:
            now = self.ctx.monotonic()
            if self.last_time is not None and now - self.last_time < 1 and done < total:
                return
            self.last_time = now
            print(f"\r{text}", end="", file=self.ctx.out, flush=True)
            self.shown = True
        else:
            decile = done * 10 // total
            if decile > self.last_decile:
                self.last_decile = decile
                print(text, file=self.ctx.out, flush=True)

    def close(self) -> None:
        """Fin de la ligne réécrite. Appelée aussi pendant un nettoyage (Ctrl+C, terminal fermé) : un terminal disparu
        (OSError, EIO) ne remplace jamais l'interruption ni l'échec en cours."""
        if self.shown:
            try:
                print("", file=self.ctx.out, flush=True)
            except (OSError, ValueError):
                pass


# --- Emplacements XDG, registre et commandes affichées -----------------------------------------------------------------------

def home(environ: Mapping[str, str]) -> Path:
    value = environ.get("HOME", "")
    if not value or not os.path.isabs(value):
        raise InstallError("HOME absent ou relatif : emplacements par défaut inconnus. Indiquer le dossier de l'atelier avec "
                           "--emplacement <dossier> (ou --destination et --data-root), et --sans-menu ; rien n'a été écrit.", EXIT_REFUSED)
    return Path(value)


def xdg_home(environ: Mapping[str, str], variable: str, fallback: str) -> Path:
    """Dossier XDG de l'utilisateur : la variable si elle est absolue, sinon $HOME/<fallback> (une valeur relative est ignorée)."""
    value = environ.get(variable, "")
    if value and os.path.isabs(value):
        return Path(value)
    return home(environ) / fallback


def data_home(environ: Mapping[str, str]) -> Path:
    return xdg_home(environ, "XDG_DATA_HOME", ".local/share")


def default_base(environ: Mapping[str, str]) -> Path:
    return data_home(environ) / DEFAULT_FOLDER


def default_programs_text(environ: Mapping[str, str]) -> str:
    """Destination des versions par défaut, résolue pour ce compte (U4-06) ; l'expression XDG si HOME est inutilisable."""
    try:
        return str(default_base(environ) / PROGRAM_FOLDER)
    except InstallError:
        return DEFAULT_LOCATIONS["programme"]


def applications_dir(environ: Mapping[str, str]) -> Path:
    return data_home(environ) / "applications"


def user_bin(environ: Mapping[str, str]) -> Path:
    return home(environ) / ".local/bin"


def registry_file(environ: Mapping[str, str]) -> Path | None:
    try:
        return xdg_home(environ, "XDG_STATE_HOME", ".local/state") / DEFAULT_FOLDER / REGISTRY
    except InstallError:
        return None


def registry_read(environ: Mapping[str, str]) -> list[str]:
    path = registry_file(environ)
    if path is None or not path.is_file():
        return []
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return []
    if data.get("format") != REGISTRY_FORMAT:
        return []
    return [item for item in data.get("destinations") or [] if isinstance(item, str) and os.path.isabs(item)]


def registry_record(ctx: Context, destination: Path) -> None:
    """Après chaque bascule : la destination figure au registre tant que son pointeur désigne une version et que
    l'intégration au bureau est active. Avec `--sans-menu`, rien n'est écrit hors des dossiers choisis : le registre n'est
    ni créé ni complété, et une entrée antérieure de cette destination en est retirée. Un échec n'est qu'un avertissement :
    le pointeur reste la seule source de vérité."""
    path = registry_file(ctx.environ)
    try:
        pointer = read_pointer(destination)
    except (OSError, ValueError, InstallError):
        pointer = None
    keep = bool(pointer and (pointer.get("current") or pointer.get("previous")) and integration_enabled(pointer))
    if path is None:
        if keep:
            ctx.warn(f"registre des installations non écrit (HOME absent) : les commandes retrouvent l'installation avec --destination {destination}")
        return
    try:
        listed = registry_read(ctx.environ)
        same = [item for item in listed if same_path(item, destination)]
        if (same == [str(destination)]) if keep else not same:
            return
        entries = [item for item in listed if not same_path(item, destination)] + ([str(destination)] if keep else [])
        make_user_dir(path.parent)
        write_json_atomic(path, {"format": REGISTRY_FORMAT, "destinations": entries})
    except (OSError, ValueError, InstallError) as error:
        ctx.warn(f"registre des installations {path} non mis à jour ({error}) : les commandes retrouvent l'installation avec "
                 f"--destination {destination}")


def known_destinations(ctx: Context) -> list[Path]:
    """Installations connues : registre, puis destination par défaut si un pointeur s'y trouve."""
    candidates = [Path(item) for item in registry_read(ctx.environ)]
    try:
        candidates.append(default_base(ctx.environ) / PROGRAM_FOLDER)
    except InstallError:
        pass
    found: list[Path] = []
    for path in candidates:
        if any(same_path(path, other) for other in found):
            continue
        try:
            pointer = read_pointer(path)
        except (OSError, ValueError, InstallError):
            continue
        if pointer and (pointer.get("current") or pointer.get("previous")):
            found.append(path)
    return found


def installation_of(program: Path) -> Path | None:
    """Destination dont le pointeur désigne `program` (version courante ou précédente), sous la graphie du pointeur
    (pointer_destination) ; None pour un kit."""
    if not (program / linux_kit.MANIFEST).is_file():
        return None
    destination = program.parent
    try:
        pointer = read_pointer(destination)
    except (OSError, ValueError, InstallError):
        return None
    for entry in ((pointer or {}).get("current"), (pointer or {}).get("previous")):
        if entry and same_path(entry["program"], program):
            return pointer_destination(destination)
    return None


def pointer_destination(destination: Path) -> Path:
    """Destination telle que son pointeur la porte (chemin tapé à l'installation, lien compris : dossier de la version courante,
    puis de la précédente, puis clé `destination`) quand `destination` désigne le même dossier réel ; `destination` sinon.
    Toute destination reçue (--destination, programme qui lance l'installateur, lanceur) y est ramenée : pointeur, lanceur,
    entrée de menu, commande atelier et registre gardent la graphie de l'installation (U6-01)."""
    pointer = safe_pointer(destination)
    if not pointer:
        return destination
    # Pointeur lu sans autre contrôle que son format : une entrée sans chemin de programme ne propose aucune graphie.
    candidates = [Path(entry["program"]).parent for entry in (pointer.get("current"), pointer.get("previous"))
                  if isinstance(entry, dict) and isinstance(entry.get("program"), str)]
    if isinstance(pointer.get("destination"), str):
        candidates.append(Path(pointer["destination"]))
    for candidate in candidates:
        if candidate.is_absolute() and same_path(candidate, destination):
            return candidate
    return destination


def installer_command(base: Path | str, *words: str) -> str:
    """Commande exacte de l'installateur d'un kit ou d'un programme installé, en chemin absolu."""
    return quoted(str(Path(base) / INSTALLER_NAME), *words)


def launcher_command(pointer: dict[str, Any] | None, destination: Path, *words: str) -> str:
    """Commande du lanceur : `atelier …` si la commande de l'utilisateur est installée, sinon le chemin complet du lanceur."""
    if (pointer or {}).get("user_command"):
        return quoted(USER_COMMAND, *words)
    return quoted(str(destination / LAUNCHER), *words)


def choose(ctx: Context, title: str, options: list[str]) -> int | None:
    """Choix numéroté au terminal ; None si l'utilisateur abandonne."""
    print(title, file=ctx.out)
    for index, option in enumerate(options, 1):
        print(f"  {index}. {option}", file=ctx.out)
    answer = ctx.question("Numéro (Entrée : abandonner) : ")
    if answer.isdigit() and 1 <= int(answer) <= len(options):
        return int(answer) - 1
    return None


def describe_destination(path: Path) -> str:
    try:
        current = (read_pointer(path) or {}).get("current")
    except (OSError, ValueError, InstallError):
        current = None
    return f"{path} (version {current['kit_id']})" if current else f"{path} (aucune version courante)"


def refuse_undesignated_version(ctx: Context, command: str) -> None:
    """Installateur lancé depuis un dossier de version que le pointeur de sa destination ne désigne plus (ni courante ni
    précédente) : il ne se rabat jamais sur le registre ni sur l'emplacement par défaut, qui désigneraient une autre
    installation ; refus qui nomme sa destination et la commande de sa version courante."""
    if not (ctx.kit / linux_kit.MANIFEST).is_file() or not (ctx.kit.parent / POINTER).is_file() or installation_of(ctx.kit):
        return
    destination = ctx.kit.parent
    pointer = safe_pointer(destination) or {}
    entry = pointer.get("current") or pointer.get("previous")
    word = command if command in {"rollback", "status", "uninstall", "repair", "modele"} else "status"
    action = f"employer « {installer_command(Path(entry['program']), word)} », ou indiquer --destination" if entry else "indiquer --destination"
    raise InstallError(f"{ctx.kit} est un dossier de version de {destination} que son pointeur ne désigne pas : {action} ; rien n'a été "
                       "modifié.", EXIT_REFUSED)


def resolve_destination(ctx: Context, args: argparse.Namespace) -> Path:
    """Destination des versions : --destination, sinon celle du programme qui lance l'installateur, sinon le registre ou
    l'emplacement par défaut ; plusieurs installations : choix au terminal, refus sinon. Un dossier de version que sa
    destination ne désigne plus est refusé (refuse_undesignated_version). La destination rendue a la graphie du pointeur,
    quelle que soit celle reçue (chemin logique ou physique : pointer_destination)."""
    if getattr(args, "destination", None):
        return pointer_destination(Path(args.destination).absolute())
    own = installation_of(ctx.kit)
    if own:
        return own
    refuse_undesignated_version(ctx, str(getattr(args, "command", "") or ""))
    found = known_destinations(ctx)
    if len(found) == 1:
        return found[0]
    if not found:
        registry = registry_file(ctx.environ)
        raise InstallError(f"Aucune installation de l'atelier trouvée (registre {registry or 'inaccessible'}, emplacement par défaut "
                           f"{default_programs_text(ctx.environ)}) : indiquer --destination <dossier des versions>, ou installer avec "
                           f"{INSTALLER_NAME}.", EXIT_REFUSED)
    if ctx.interactive:
        index = choose(ctx, "Plusieurs installations de l'atelier existent :", [describe_destination(path) for path in found])
        if index is not None:
            return found[index]
    raise InstallError("Plusieurs installations de l'atelier existent : " + " ; ".join(describe_destination(path) for path in found)
                       + ". Indiquer celle visée avec --destination <dossier>.", EXIT_REFUSED)


# --- Verrou de l'installateur ---------------------------------------------------------------------------------------------

@contextmanager
def installer_lock(destination: Path) -> Iterator[None]:
    """Une opération d'installation à la fois par destination (flock non bloquant, libéré à la fermeture)."""
    if sys.platform == "win32":
        raise InstallError("Installateur Linux seulement", EXIT_REFUSED)
    import fcntl

    make_user_dir(destination)
    with (destination / LOCK).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise InstallError(f"Une autre opération d'installation est en cours sur {destination} ; attendre sa fin, puis relancer.",
                               EXIT_REFUSED) from error
        yield


def lock_is_free(destination: Path) -> bool:
    if sys.platform == "win32" or not (destination / LOCK).exists():
        return True
    import fcntl

    with (destination / LOCK).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(handle, fcntl.LOCK_UN)
    return True


def refuse_if_locked(destination: Path) -> None:
    if not lock_is_free(destination):
        raise InstallError(f"Une autre opération d'installation est en cours sur {destination} ; attendre sa fin, puis relancer.",
                           EXIT_REFUSED)


# --- Commandes du programme installé ------------------------------------------------------------------------------------

def rag(ctx: Context, program: Path, command: str, *arguments: str, timeout: float = 1800) -> dict[str, Any]:
    """`rag.sh <commande>` du programme ; résultat JSON, avec le code de sortie dans `_returncode`."""
    completed = ctx.runner.run([str(program / "rag.sh"), command, *arguments], cwd=program, timeout=timeout)
    result = parse_json(completed.stdout)
    result["_returncode"] = completed.returncode
    if not result.get("message") and completed.returncode:
        result["message"] = (completed.stderr or completed.stdout).strip()[-600:]
    return result


def venv_python(program: Path) -> Path:
    return program / ".venv/bin/python"


def profiles_tool(ctx: Context, python: Path, scripts: Path, *arguments: str, cwd: Path) -> dict[str, Any]:
    """`linux_profiles.py` de `scripts`, exécuté par `python` (environnement isolé d'un programme : PyYAML). Le code d'un autre
    dossier que celui de l'environnement (nouveau kit d'une mise à jour, dont seules les sources de PRE_COPY_FILES sont
    vérifiées) est lancé sans lire aucun bytecode ; un programme installé garde le sien (compileall)."""
    foreign = not Path(python).absolute().is_relative_to(Path(scripts).absolute())
    options = ["-B", "-I", *(["-X", f"pycache_prefix={NO_BYTECODE}"] if foreign else [])]
    completed = ctx.runner.run([str(python), *options, str(scripts / "tools/dist/linux_profiles.py"), *arguments], cwd=cwd, timeout=120)
    result = parse_json(completed.stdout)
    if completed.returncode and not result.get("message"):
        result["message"] = (completed.stderr or completed.stdout).strip()[-400:]
    result.setdefault("status", "failed")
    return result


def profile_info(ctx: Context, program: Path, profile: Path) -> dict[str, Any]:
    """Modèle, ports et emplacements d'écriture d'un profil, lus par l'environnement du programme."""
    result = profiles_tool(ctx, venv_python(program), program, "paths", "--profile", str(profile), cwd=program)
    if result["status"] != "read":
        raise InstallError(f"Profil {profile} illisible par {program} : {result.get('message')}")
    return result


def derive_profiles(ctx: Context, report: Report | None, *, python: Path, scripts: Path, program: Path, like: str,
                    data_root: Path, models: list[str], check: bool = False) -> dict[str, str]:
    """Profils d'autres modèles livrés sur les données de `like` ; rend {modèle: profil} créé, réutilisé ou contrôlé."""
    made: dict[str, str] = {}
    for model in models:
        output = data_root / f"profile-{model_slug(model)}.yaml"
        result = profiles_tool(ctx, python, scripts, "derive", "--like", like, "--model", model, "--program", str(program),
                               "--output", str(output), *(["--check"] if check else []), cwd=program)
        if result["status"] not in {"created", "reused", "checked"}:
            raise InstallError(f"Profil {model} non dérivable : {result.get('message')}")
        made[model] = str(output)
        if report and not check:
            report.step("profil", "ok", f"{output} ({model}, mêmes données ; {'réutilisé' if result['status'] == 'reused' else 'créé'})")
    return made


# --- Pointeur, lanceur, icône, entrée de menu et commande de l'utilisateur ----------------------------------------------------

def read_pointer(destination: Path) -> dict[str, Any] | None:
    path = destination / POINTER
    if not path.exists():
        return None
    pointer = read_json(path)
    if pointer.get("format") != POINTER_FORMAT:
        raise InstallError(f"{path} n'est pas un pointeur d'installation de l'atelier", EXIT_REFUSED)
    return pointer


def designated(destination: Path) -> dict[str, Any] | None:
    """Version que le pointeur désigne réellement, relue sur disque ; None si absent ou illisible."""
    try:
        return (read_pointer(destination) or {}).get("current")
    except (OSError, ValueError, InstallError):
        return None


def launcher_text(entry: dict[str, Any], destination: Path) -> str:
    program = Path(entry["program"])
    python = program / entry["python"]
    return ("#!/bin/sh\n"
            f"{LAUNCHER_MARKER}, version {entry['kit_id']}.\n"
            "# Écrit par l'installateur à chaque bascule de version (installer.sh repair le régénère) : ne pas modifier.\n"
            "# Actions : ouvrir (défaut), arreter, diagnostic, etat, sauvegarder, journaux, modele <modèle> ; options --modele "
            "<modèle>, --no-browser, --attendre, --aide.\n"
            "set -eu\nunset LD_LIBRARY_PATH\n"
            f"exec {shlex.quote(str(python))} -B -I -S -X utf8 {shlex.quote(str(program / 'tools/dist/linux_install.py'))} "
            f"--kit {shlex.quote(str(program))} run --destination {shlex.quote(str(destination))} \"$@\"\n")


def desktop_text(destination: Path, current: dict[str, Any], *, icon: bool) -> str:
    """Entrée de menu (Desktop Entry 1.1 : Actions et Keywords) : chaque Exec porte --attendre, pour que la fenêtre du
    terminal garde un échec, un diagnostic ou un état lisible."""
    launcher = desktop_quote(str(destination / LAUNCHER))
    others = [model for model in current.get("profiles") or {} if model != current.get("model")]
    actions = [*MENU_ACTIONS, *(f"modele-{action_slug(model)}" for model in others)]
    lines = ["[Desktop Entry]", "Type=Application", "Version=1.1", f"Name={MENU_NAME}", "GenericName=Atelier de documents PDF",
             "Comment=Démarre l'atelier si nécessaire et l'ouvre dans le navigateur",
             "Keywords=recherche;questions;réponses;citations;sources;OCR;",
             *([f"Icon={desktop_escape(str(destination / ICON))}"] if icon else []),
             f"TryExec={desktop_escape(str(destination / LAUNCHER))}", f"Exec={launcher} ouvrir --attendre", "Terminal=true",
             "Categories=Office;", f"Actions={';'.join(actions)};", f"X-Atelier-Destination={desktop_escape(str(destination))}"]
    for action, name in MENU_ACTIONS.items():
        lines += ["", f"[Desktop Action {action}]", f"Name={name}", f"Exec={launcher} {action} --attendre"]
    for model in others:
        lines += ["", f"[Desktop Action modele-{action_slug(model)}]", f"Name=Ouvrir avec le modèle {model_label(model)}",
                  f"Exec={launcher} ouvrir --modele {desktop_quote(model)} --attendre"]
    return "\n".join(lines) + "\n"


def desktop_owner(path: Path) -> str | None:
    """Destination inscrite dans une entrée de menu écrite par l'installateur (X-Atelier-Destination) ; None sinon."""
    if path.is_symlink() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in text.splitlines():
        if line.startswith("X-Atelier-Destination="):
            return desktop_unescape(line.split("=", 1)[1])
    return None


def user_command_text(destination: Path) -> str:
    """Commande `atelier` de l'utilisateur : court script POSIX qui passe la main au lanceur de la destination, ou explique
    l'absence d'un volume démonté (le lanceur n'est pas un lien : un lien vers un volume absent échouerait sans message)."""
    if control_characters(str(destination)):
        raise InstallError(f"Chemin à caractère de contrôle refusé : {str(destination)!r}", EXIT_REFUSED)
    missing = f"Programme de l'atelier introuvable ({destination}) : volume non monté ? Monter le volume, puis relancer."
    return ("#!/bin/sh\n"
            f"# {COMMAND_MARKER}{destination}\n"
            "# Retirée avec la dernière version ou par installer.sh repair --sans-menu ; ne pas modifier.\n"
            f"launcher={shlex.quote(str(destination / LAUNCHER))}\n"
            'if [ ! -x "$launcher" ]; then\n'
            f"    printf '%s\\n' {shlex.quote(missing)} >&2\n"
            "    exit 1\n"
            "fi\n"
            'exec "$launcher" "$@"\n')


def command_owner(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[:3]
    except (OSError, UnicodeDecodeError):
        return None
    prefix = f"# {COMMAND_MARKER}"
    return next((line[len(prefix):] for line in lines if line.startswith(prefix)), None)


def menu_unsupported(destination: Path) -> str | None:
    """Raison pour laquelle aucune entrée de menu n'est écrite pour cette destination, ou None. Un guillemet droit s'écrit
    `\\\\"` dans Exec selon la Desktop Entry Specification (règle des chaînes, puis guillemets) et GLib 2.64 le lit ainsi, mais
    desktop-file-validate 0.24 refuse cette forme : l'entrée n'est pas écrite plutôt que de l'être invalide pour cet outil."""
    if '"' in str(destination):
        return (f"destination {destination} : un chemin qui contient un guillemet droit (\") ne s'écrit pas dans une entrée de menu "
                "validée par desktop-file-validate — choisir un dossier sans guillemet, ou installer avec --sans-menu")
    return None


def free_or_ours(path: Path, owner: Callable[[Path], str | None], destination: Path) -> bool:
    """Fichier absent, ou écrit par l'installateur pour cette destination : seul cas où il est écrit ou retiré."""
    return (not path.exists() and not path.is_symlink()) or owned_by(owner(path), destination)


def integration_enabled(pointer: dict[str, Any]) -> bool:
    return pointer.get("menu") is not False


def derived_files(destination: Path, pointer: dict[str, Any]) -> tuple[list[tuple[Path, bytes, int]], list[Path]]:
    """Fichiers dérivés du pointeur (lanceur, icône, entrée de menu, commande) et fichiers étrangers laissés intacts."""
    current = pointer.get("current")
    if not current:
        return [], []
    files = [(destination / LAUNCHER, launcher_text(current, destination).encode("utf-8"), 0o755)]
    icon_source = Path(current["program"]) / ICON_SOURCE
    icon = icon_source.is_file()
    if icon:
        files.append((destination / ICON, icon_source.read_bytes(), 0o644))
    skipped: list[Path] = []
    if integration_enabled(pointer) and pointer.get("menu_entry") and not menu_unsupported(destination):
        entry = Path(pointer["menu_entry"])
        if free_or_ours(entry, desktop_owner, destination):
            files.append((entry, desktop_text(destination, current, icon=icon).encode("utf-8"), 0o644))
        else:
            skipped.append(entry)
    if integration_enabled(pointer) and pointer.get("user_command"):
        command = Path(pointer["user_command"])
        if free_or_ours(command, command_owner, destination):
            files.append((command, user_command_text(destination).encode("utf-8"), 0o755))
        else:
            skipped.append(command)
    return files, skipped


def remove_derived(destination: Path, pointer: dict[str, Any], *, only: list[str] | None = None) -> None:
    """Lanceur, icône, et entrée de menu et commande s'ils appartiennent à cette destination ; jamais un fichier étranger."""
    (destination / LAUNCHER).unlink(missing_ok=True)
    (destination / ICON).unlink(missing_ok=True)
    for key, owner in (("menu_entry", desktop_owner), ("user_command", command_owner)):
        value = pointer.get(key)
        if value and (only is None or key in only) and owned_by(owner(Path(value)), destination):
            Path(value).unlink(missing_ok=True)


def stage(path: Path, data: bytes, mode: int) -> Path:
    """Fichier temporaire complet et synchronisé à côté de `path`, prêt pour rename(2)."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as writer:
            writer.write(data)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(temporary, mode)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def fsync_directory(folder: Path) -> None:
    """Rend durables les créations, renommages et suppressions d'entrées de `folder` (fsync(2) du dossier)."""
    directory = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def publish(temporary: Path, path: Path) -> None:
    os.replace(temporary, path)
    fsync_directory(path.parent)


def warn_skipped(warn: Callable[[str], None] | None, skipped: list[Path], destination: Path) -> None:
    for path in skipped:
        if warn:
            warn(f"{path} existe et n'appartient pas à cette installation : laissé intact ; le lanceur reste {destination / LAUNCHER}")


def refresh_derived(destination: Path, pointer: dict[str, Any], *, warn: Callable[[str], None] | None = None) -> None:
    """Fichiers dérivés du pointeur : préparés puis publiés ; retirés sans version courante."""
    files, skipped = derived_files(destination, pointer)
    staged: list[tuple[Path, Path]] = []
    try:
        for path, data, mode in files:
            make_user_dir(path.parent)
            staged.append((stage(path, data, mode), path))
        for temporary, path in staged:
            publish(temporary, path)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    warn_skipped(warn, skipped, destination)
    if not pointer.get("current"):
        remove_derived(destination, pointer)


def switch(destination: Path, pointer: dict[str, Any] | None, current: dict[str, Any] | None, previous: dict[str, Any] | None,
           event: dict[str, Any], *, menu: Path | None = None, integration: dict[str, Any] | None = None,
           warn: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Bascule transactionnelle : pointeur et fichiers dérivés préparés d'abord ; le rename(2) du pointeur est le point de
    validation. Avant lui, rien ne change ; après lui, un échec lève SwitchIncomplete (le pointeur est juste, `repair`
    régénère le reste). Une entrée de menu ou une commande abandonnée par un changement de choix est retirée si elle nous
    appartient."""
    new = dict(pointer or {"format": POINTER_FORMAT, "destination": str(destination), "history": []})
    new["current"], new["previous"] = current, previous
    new["history"] = [*new.get("history", []), event]
    if integration is not None:
        new.update(integration)
    if menu is not None:
        new["menu_entry"], new["menu"] = str(menu / DESKTOP), True
    old = pointer or {}
    abandoned = [key for key in ("menu_entry", "user_command")
                 if old.get(key) and (old.get(key) != new.get(key) or not integration_enabled(new))]
    derived, skipped = derived_files(destination, new)
    files = [(destination / POINTER, (json.dumps(new, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), 0o644), *derived]
    staged: list[tuple[Path, Path]] = []
    try:
        for path, data, mode in files:
            make_user_dir(path.parent)
            staged.append((stage(path, data, mode), path))
        publish(*staged[0])
    except BaseException:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
        raise
    try:
        for temporary, path in staged[1:]:
            publish(temporary, path)
        if abandoned:
            for key in abandoned:
                owner = desktop_owner if key == "menu_entry" else command_owner
                if owned_by(owner(Path(old[key])), destination):
                    Path(old[key]).unlink(missing_ok=True)
        if not current:
            remove_derived(destination, new)
    except BaseException as error:
        for temporary, _ in staged[1:]:
            temporary.unlink(missing_ok=True)
        version = (current or {}).get("kit_id", "aucune")
        repair = (installer_command(current["program"], "repair") if current else
                  installer_command(previous["program"], "repair") if previous else
                  f"<dossier du kit>/{quoted(INSTALLER_NAME, 'repair', '--destination', str(destination))}")
        raise SwitchIncomplete(f"La version {version} est la version courante (pointeur {destination / POINTER} basculé), mais le lanceur "
                               f"ou l'entrée de menu n'a pas été régénéré ({error}) : « {repair} » le reprend depuis le "
                               "pointeur.") from error
    warn_skipped(warn, skipped, destination)
    return new


def mark_started(destination: Path, program: Path, *, holding_lock: bool = False) -> None:
    """Consigne qu'une version a démarré sur les données (son retour arrière passera par la restauration). Le lanceur ne
    l'écrit que si aucune opération d'installation ne tient le verrou ; sinon l'exécutable du superviseur, lu par `status`,
    en garde la trace."""
    if not holding_lock and not lock_is_free(destination):
        return
    pointer = read_pointer(destination)
    if pointer and pointer.get("current") and same_path(pointer["current"]["program"], program) and not pointer["current"].get("started_on_data"):
        pointer["current"]["started_on_data"] = True
        write_json_atomic(destination / POINTER, pointer)


def integration_for(ctx: Context, destination: Path, *, sans_menu: bool, menu_dir: Path | None) -> tuple[dict[str, Any], list[str]]:
    """Choix d'intégration au bureau : entrée de menu (dossier XDG des applications, ou --menu) et commande ~/.local/bin/atelier,
    sauf --sans-menu. Une commande étrangère du même nom est laissée intacte (avertissement)."""
    if sans_menu:
        return {"menu": False, "menu_entry": None, "user_command": None}, []
    notes: list[str] = []
    try:
        folder = menu_dir.absolute() if menu_dir else applications_dir(ctx.environ)
    except InstallError as error:
        raise InstallError("HOME absent ou relatif : entrée de menu et commande atelier impossibles. Ajouter --sans-menu, ou indiquer "
                           "le dossier de l'entrée avec --menu <dossier> ; rien n'a été écrit.", EXIT_REFUSED) from error
    command: Path | None = None
    try:
        candidate = user_bin(ctx.environ) / USER_COMMAND
    except InstallError:
        candidate = None
        notes.append(f"HOME absent : commande {USER_COMMAND} non créée ; lancer l'atelier par {destination / LAUNCHER}")
    if candidate is not None:
        if candidate.is_dir() and not candidate.is_symlink():
            notes.append(f"{candidate} est un dossier : commande {USER_COMMAND} non créée ; lancer l'atelier par {destination / LAUNCHER}")
        elif free_or_ours(candidate, command_owner, destination):
            command = candidate
        else:
            notes.append(f"{candidate} existe et n'appartient pas à cette installation : laissé intact ; lancer l'atelier par "
                         f"{destination / LAUNCHER}")
    return {"menu": True, "menu_entry": str(folder / DESKTOP), "user_command": str(command) if command else None}, notes


def session_note(ctx: Context, integration: dict[str, Any], destination: Path, bin_existed: bool) -> str | None:
    """`atelier` n'est trouvé que si ~/.local/bin est dans le PATH. L'installateur ne le modifie jamais : un dossier créé
    maintenant n'y entre qu'à une nouvelle session, et seulement si le profil de session l'y ajoute (/etc/skel/.profile
    d'Ubuntu le fait s'il existe) ; un dossier présent mais absent du PATH n'y est pas ajouté par le profil."""
    command = integration.get("user_command")
    if not command:
        return None
    folder = str(Path(command).parent)
    if bin_existed and folder in (ctx.environ.get("PATH") or "").split(":"):
        return None
    launcher = destination / LAUNCHER
    if not bin_existed:
        return (f"{folder} vient d'être créé : « {USER_COMMAND} » ne sera trouvé qu'à une nouvelle session, et seulement si le profil "
                f"de session ajoute ce dossier au PATH (cas du ~/.profile par défaut d'Ubuntu) ; d'ici là, ou sinon : {launcher}")
    return (f"{folder} n'est pas dans le PATH de cette session : employer le chemin complet {launcher} ; une nouvelle session ne "
            "l'y ajoutera que si le profil de session le prévoit (cas du ~/.profile par défaut d'Ubuntu)")


# --- Manifeste et précontrôles ---------------------------------------------------------------------------------------------

def read_manifest(kit: Path) -> dict[str, Any]:
    """Manifeste du kit, avec les champs qui deviennent des chemins validés avant tout usage."""
    try:
        manifest = read_json(kit / linux_kit.MANIFEST)
        sums = linux_kit.read_sums(kit)
    except (OSError, ValueError) as error:
        raise InstallError(f"kit-manifest.json ou SHA256SUMS illisible dans {kit} : {error} ; ré-extraire l'archive.", EXIT_REFUSED) from error
    if manifest.get("format") != linux_kit.KIT_FORMAT or not str(manifest.get("platform", "")).startswith("linux-"):
        raise InstallError(f"{kit} n'est pas un kit Linux de l'atelier (format {manifest.get('format')})", EXIT_REFUSED)
    problems = []
    kit_id = str(manifest.get("kit_id", ""))
    if not KIT_ID.fullmatch(kit_id) or kit_id in {".", ".."}:
        problems.append(f"kit_id {kit_id!r}")
    python = manifest.get("python") or {}
    executable, key = str(python.get("executable", "")), str(python.get("key", ""))
    match = PYTHON_EXECUTABLE.fullmatch(executable)
    if not match or match.group(1) in {".", ".."} or executable not in sums:
        problems.append(f"python.executable {executable!r}")
    # La clé devient un chemin (compileall, préfixe réécrit) : même composant que l'exécutable, jamais « . » ni « .. ».
    if not PYTHON_KEY.fullmatch(key) or key in {".", ".."} or not match or match.group(1) != key:
        problems.append(f"python.key {key!r}")
    for item in manifest.get("neutralizations") or []:
        if str(item.get("path")) not in sums or not str(item.get("path")).startswith(".runtime/"):
            problems.append(f"neutralizations {item.get('path')!r}")
    for relative in (manifest.get("target") or {}).get("ldd_checks") or []:
        if relative not in sums:
            problems.append(f"ldd_checks {relative!r}")
    if problems:
        raise InstallError(f"kit-manifest.json non conforme ({', '.join(problems)}) : recopier le kit ; rien n'a été installé.", EXIT_REFUSED)
    return manifest


def ordered_models(manifest: dict[str, Any]) -> list[str]:
    default = manifest.get("default_model")
    models = list(manifest.get("model_profiles") or {})
    return sorted(models, key=lambda model: (model != default, models.index(model)))


def writable_target(path: Path) -> bool:
    ancestor = existing_ancestor(path)
    return ancestor.is_dir() and os.access(ancestor, os.W_OK | os.X_OK)


def check_ports(ctx: Context, ports: str) -> list[str]:
    parts = ports.split(",")
    action = "indiquer trois autres ports avec --ports a,b,c"
    if len(parts) != 3 or not all(part.strip().isdigit() for part in parts):
        return [f"--ports {ports} : trois ports API,Qdrant,Ollama attendus — {action}"]
    values = [int(part) for part in parts]
    if len(set(values)) != 3 or not all(1024 <= value <= 65535 for value in values):
        return [f"--ports {ports} : trois ports distincts entre 1024 et 65535 attendus — {action}"]
    return [f"--ports : port {value} occupé sur 127.0.0.1 — {action}" for value in values if not ctx.probe.port_free(value)]


def free_triplet(defaults: dict[str, int], is_free: Callable[[int], bool]) -> dict[str, int]:
    """Règle fixe (PORT_RULE) : un port par défaut libre est gardé ; un port occupé est remplacé par le premier port libre
    au-dessus, distinct des autres, entre 1024 et 65535, hors ports de la restauration."""
    chosen: dict[str, int] = {}
    for name in ("app", "qdrant", "ollama"):
        port = defaults[name]
        taken = set(chosen.values()) | {value for key, value in defaults.items() if key != name and key not in chosen}
        while not (1024 <= port <= 65535) or port in RESTORE_PORTS or port in taken or not is_free(port):
            port += 1
            if port > 65535:
                raise InstallError(f"Aucun port libre au-dessus de {defaults[name]} pour {name} : indiquer trois ports avec --ports a,b,c.",
                                   EXIT_REFUSED)
        chosen[name] = port
    return chosen


def choose_ports(ctx: Context, manifest: dict[str, Any], model: str, ports: str | None) -> tuple[str | None, dict[str, int] | None, list[str]]:
    """Ports du profil principal. Sans --ports : ports du profil livré lus au manifeste (`profile_ports`), contrôlés avant toute
    écriture ; occupés, un triplet libre est retenu. Un manifeste sans ce champ garde le contrôle par init-profile."""
    if ports:
        values = [part.strip() for part in ports.split(",")]
        return ports, (dict(zip(("app", "qdrant", "ollama"), map(int, values), strict=True)) if len(values) == 3 and all(v.isdigit() for v in values) else None), []
    defaults = ((manifest.get("profile_ports") or {}).get(model) or {})
    if not all(isinstance(defaults.get(name), int) for name in ("app", "qdrant", "ollama")):
        return None, None, []
    defaults = {name: int(defaults[name]) for name in ("app", "qdrant", "ollama")}
    busy = [defaults[name] for name in ("app", "qdrant", "ollama") if not ctx.probe.port_free(defaults[name])]
    if not busy:
        return None, defaults, []
    chosen = free_triplet(defaults, ctx.probe.port_free)
    return ",".join(str(chosen[name]) for name in ("app", "qdrant", "ollama")), chosen, [f"port {port} occupé" for port in busy]


def session_mount(point: str) -> bool:
    return point.startswith(("/media/", "/run/media/"))


def volume_candidates(ctx: Context, needed: int) -> list[dict[str, Any]]:
    """Volumes locaux montés qui ont la place : type local, ni noexec ni lecture seule, racine du système de fichiers,
    point de montage accessible en écriture au compte."""
    seen: set[str] = set()
    found: list[dict[str, Any]] = []
    for entry in ctx.probe.mounts():
        if entry.get("root", "/") != "/" or entry.get("fstype") not in LOCAL_FILESYSTEMS or entry.get("noexec") or entry.get("readonly"):
            continue
        point = Path(entry["mount"])
        device = str(entry.get("device") or point)
        if device in seen or not ctx.probe.writable(point):
            continue
        free = ctx.probe.free_bytes(point)
        if free is None or free < needed:
            continue
        seen.add(device)
        found.append({"mount": str(point), "free": free, "session": session_mount(str(point))})
    return sorted(found, key=lambda item: -item["free"])


def suggestion(ctx: Context, args: argparse.Namespace | None, *, add: list[str], drop: tuple[str, ...] = (),
               drop_flags: tuple[str, ...] = ()) -> str:
    """Commande exacte à relancer : arguments de l'utilisateur, sans les options écartées (`drop` : options à valeur,
    `drop_flags` : options sans valeur), plus les ajouts."""
    words = list(getattr(args, "user_argv", None) or [])
    kept: list[str] = []
    skip = False
    for word in words:
        if skip:
            skip = False
            continue
        name = word.split("=", 1)[0]
        if name in drop:
            skip = "=" not in word
            continue
        if word in drop_flags:
            continue
        kept.append(word)
    return installer_command(ctx.kit, *kept, *add)


def install_suggestion(ctx: Context, args: argparse.Namespace, *, add: list[str], drop: tuple[str, ...] = (),
                       drop_flags: tuple[str, ...] = ()) -> str:
    """Commande `install` exacte à relancer depuis ce kit ; la commande est écrite même si l'utilisateur l'avait omise."""
    if getattr(args, "implicit", False):
        args = argparse.Namespace(**{**vars(args), "user_argv": ["install", *(getattr(args, "user_argv", None) or [])]})
    return suggestion(ctx, args, add=add, drop=drop, drop_flags=drop_flags)


def other_data_root(ctx: Context, args: argparse.Namespace) -> str:
    """Commande d'une installation neuve sur une autre racine des données ; le dossier reste à choisir (hors shlex)."""
    return install_suggestion(ctx, args, add=["--data-root"], drop=("--data-root",), drop_flags=("--reprendre-donnees",)) + " <autre dossier>"


def space_refusal(ctx: Context, args: argparse.Namespace | None, free: int, needed: int, ancestor: Path, shared: bool, *,
                  elsewhere_hint: str | None = None) -> tuple[str, list[dict[str, Any]]]:
    """Place insuffisante pour une installation neuve sans emplacement explicite : volumes locaux qui ont la place, chacun
    avec sa commande exacte ; `elsewhere_hint` (aucune installation retrouvée) est écrit avant eux, pour qu'une installation
    faite ailleurs soit mise à jour au lieu d'une installation neuve sur des données vides."""
    detail = "programme" + (f" et réserve de {fr_gib(DATA_MIN_FREE_BYTES)} des données" if shared else "")
    cause = f"espace insuffisant sous {ancestor} : {fr_gib(free)} libres, {fr_gib(needed)} nécessaires ({detail})"
    volumes = volume_candidates(ctx, needed)
    hint = f"\n      {elsewhere_hint}" if elsewhere_hint else ""
    if not volumes:
        return cause + " — libérer de la place, ou installer sur un volume local qui a la place : --emplacement <dossier>" + hint, []
    lines = [cause + " — " + (f"{elsewhere_hint} ; sinon, " if elsewhere_hint else "") + "volumes locaux qui ont la place :"]
    for volume in volumes:
        note = " (volume monté par la session : il devra être monté pour ouvrir l'atelier)" if volume["session"] else ""
        lines.append(f"      {volume['mount']} — {fr_gib(volume['free'])} libres{note}")
        lines.append("        commande : " + suggestion(ctx, args, add=["--emplacement", f"{volume['mount'].rstrip('/')}/{DEFAULT_FOLDER}"],
                                                         drop=("--emplacement", "--destination", "--data-root")))
    return "\n".join(lines), volumes


def update_space_refusal(ctx: Context, destination: Path, free: int, needed: int, ancestor: Path) -> str:
    """Place insuffisante pour une mise à jour : elle se fait dans la destination en place, jamais ailleurs (une installation
    neuve sur un autre volume aurait des données vides). Seules des commandes de l'installateur en place sont proposées."""
    pointer = safe_pointer(destination) or {}
    current, previous = pointer.get("current"), pointer.get("previous")
    cause = (f"espace insuffisant sous {ancestor}, volume de l'installation : {fr_gib(free)} libres, {fr_gib(needed)} nécessaires au "
             "programme")
    if not current:
        return cause + " — libérer de la place sur ce volume, puis relancer"
    program = Path(current["program"])
    designated_ids = {entry["kit_id"] for entry in (current, previous) if entry}
    others = [kit_id for kit_id in versions_present(destination) if kit_id not in designated_ids]
    options = []
    if others:
        size = sum(ctx.probe.tree_bytes(destination / kit_id) for kit_id in others)
        options.append(f"versions non désignées ({', '.join(others)}, {fr_gib(size)}) : « {installer_command(program, 'uninstall', '--anciennes')} »")
    if previous:
        size = ctx.probe.tree_bytes(Path(previous["program"]))
        consequence = "" if previous.get("rolled_back") else " ; le retour arrière vers elle ne sera plus possible"
        options.append(f"version précédente {previous['kit_id']} ({fr_gib(size)}) : « {installer_command(program, 'uninstall')} »{consequence}")
    options.append(f"anciennes sauvegardes, listées par « {installer_command(program, 'status')} »")
    return cause + " — libérer de la place sur ce volume : " + " ; ".join(options) + " ; puis relancer la mise à jour"


def safe_pointer(destination: Path) -> dict[str, Any] | None:
    try:
        return read_pointer(destination)
    except (OSError, ValueError, InstallError):
        return None


def orphans(destination: Path, pointer: dict[str, Any] | None) -> list[str]:
    """Dossiers de version laissés par une copie interrompue (arrêt brutal) : nom d'un kit_id, ni lien ni dossier désigné,
    sans kit-manifest.json (copié en dernier par linux_kit.install_copy) ni donnée d'exécution."""
    if not destination.is_dir():
        return []
    designated_programs = {os.path.realpath(entry["program"]) for entry in ((pointer or {}).get("current"), (pointer or {}).get("previous"))
                           if entry}
    found = []
    for path in sorted(destination.iterdir()):
        if path.is_symlink() or not path.is_dir() or not KIT_FOLDER.fullmatch(path.name):
            continue
        if (path / linux_kit.MANIFEST).is_file() or os.path.realpath(path) in designated_programs:
            continue
        if any((path / name).exists() or (path / name).is_symlink() for name in RUNTIME_DATA):
            continue
        found.append(path.name)
    return found


def removal_command(ctx: Context, destination: Path, pointer: dict[str, Any] | None, kit_id: str) -> str:
    """Commande absolue qui retire une version non désignée ou un dossier incomplet."""
    current = (pointer or {}).get("current")
    if current:
        return installer_command(Path(current["program"]), "uninstall", "--kit-id", kit_id)
    return installer_command(ctx.kit, "uninstall", "--destination", str(destination), "--kit-id", kit_id)


def present_version(ctx: Context, destination: Path, kit_id: str) -> str:
    """Refus d'une version déjà présente dans la destination, selon ce que le pointeur en dit : jamais de commande qui retire
    une version désignée (courante, ou précédente encore utile au retour arrière)."""
    target = destination / kit_id
    pointer = safe_pointer(destination)
    current, previous = (pointer or {}).get("current"), (pointer or {}).get("previous")
    if target.is_symlink() or not target.is_dir():
        return f"{target} existe et n'est pas un dossier de version — le déplacer, puis relancer"
    if current and current["kit_id"] == kit_id:
        return f"version {kit_id} déjà courante dans {destination} — rien à installer : « {installer_command(Path(current['program']), 'status')} »"
    if previous and previous["kit_id"] == kit_id and not previous.get("rolled_back"):
        rollback = installer_command(Path(current["program"]), "rollback") if current else None
        return (f"version {kit_id} : version précédente de {destination}" + (f" — pour y revenir, « {rollback} »" if rollback else ""))
    command = removal_command(ctx, destination, pointer, kit_id)
    if previous and previous["kit_id"] == kit_id:
        return (f"version {kit_id} déjà présente, abandonnée par un retour arrière — la retirer (« {command} » ; données conservées), "
                "puis relancer")
    if kit_id in orphans(destination, pointer):
        return f"dossier incomplet {target} (copie interrompue, sans kit-manifest.json) — le retirer : « {command} », puis relancer"
    return f"version {kit_id} déjà présente dans {target}, non désignée : jamais remplacée — la retirer (« {command} »), puis relancer"


def launcher_owned(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        return any(line.startswith(LAUNCHER_MARKER) for line in path.read_text(encoding="utf-8").splitlines()[:3])
    except (OSError, UnicodeDecodeError):
        return False


def foreign_files(kit: Path, destination: Path) -> list[Path]:
    """Lanceur ou icône présents dans une destination sans version courante, que l'installation remplacerait : un lanceur
    sans le marqueur de l'atelier, ou une icône différente de celle du kit (ICON_SOURCE). Une icône n'est jamais écrite par
    un kit qui n'en livre pas."""
    found = []
    launcher, icon, source = destination / LAUNCHER, destination / ICON, kit / ICON_SOURCE
    if (launcher.is_file() or launcher.is_symlink()) and not launcher.is_dir() and not launcher_owned(launcher):
        found.append(launcher)
    if (icon.is_file() or icon.is_symlink()) and not icon.is_dir() and source.is_file():
        try:
            same = not icon.is_symlink() and icon.read_bytes() == source.read_bytes()
        except OSError:
            same = False
        if not same:
            found.append(icon)
    return found


def precheck(ctx: Context, manifest: dict[str, Any], destination: Path, data_root: Path, *, qdrant_storage: Path | None = None,
             program: Path | None = None, menu_entry: Path | None = None, menu_explicit: bool = False, model: str | None = None,
             ports: str | None = None, data_checks: bool = True, args: argparse.Namespace | None = None, relocatable: bool = False,
             replaced: Path | None = None, user_command: Path | None = None, command_fix: str | None = None,
             elsewhere_hint: str | None = None) -> dict[str, Any]:
    """Contrôles du poste, des emplacements et des options, sans écriture ; tous les refus sont rendus ensemble, un par ligne
    « cause — action ». `relocatable` : installation neuve sans emplacement explicite, à qui d'autres volumes sont proposés
    quand la place manque ; `program` : version en place d'une mise à jour ; `replaced` : dossier incomplet d'une
    installation interrompue, retiré avant la copie ; `user_command` : commande atelier que la bascule écrira
    (`command_fix` : autre correction que --sans-menu) ; `elsewhere_hint` : installation existante non retrouvée, dite avant
    les volumes proposés."""
    probe, kit = ctx.probe, ctx.kit
    target = manifest["target"]
    failures: list[str] = []
    passed: list[str] = []
    volumes: list[dict[str, Any]] = []
    machine = probe.machine()
    if machine == target["arch"]:
        passed.append(f"architecture {machine}")
    else:
        failures.append(f"ce kit vise {target['arch']}, ce poste est en {machine} — employer le kit de l'architecture de ce poste")
    glibc = probe.glibc()
    if glibc is None:
        failures.append("glibc introuvable (musl ou bibliothèque C non reconnue) — employer un système Linux à glibc")
    elif target.get("glibc_min") and linux_kit.version_tuple(glibc) < linux_kit.version_tuple(target["glibc_min"]):
        failures.append(f"glibc {glibc} trop ancienne : {target['glibc_min']} ou plus récente exigée — employer un système plus récent")
    else:
        passed.append(f"glibc {glibc}")
    kernel = probe.kernel()
    if linux_kit.version_tuple(kernel)[:2] < linux_kit.version_tuple(target.get("kernel_min", linux_kit.KERNEL_MIN))[:2]:
        failures.append(f"noyau {kernel} : {target.get('kernel_min')} ou plus récent exigé (pidfd) — employer un noyau plus récent")
    memory = probe.memory_total_gib()
    minimum = target.get("memory_gib_min") or (manifest.get("requirements") or {}).get("memory_gib_min") or linux_kit.MEMORY_MIN_GIB
    if memory is not None and memory < minimum:
        failures.append(f"ce poste a {fr_number(memory)} Gio ; l'atelier exige {fr_number(minimum, 0)} Gio visibles ({TARGET_MEMORY_LABEL}) — "
                        "employer un poste qui a cette mémoire")
    if not probe.setpriv():
        failures.append("setpriv (util-linux) absent de /usr/bin et /bin : l'arrêt des services à la mort du superviseur ne serait pas "
                        "garanti — le faire installer par l'administrateur du poste (util-linux)")
    required = (manifest.get("gpu") or {}).get("requires_l4t_major")
    if required and probe.l4t_major() != required:
        failures.append(f"kit {manifest['gpu'].get('variant')} réservé à Jetson Linux R{required} (ce poste : "
                        f"{'R' + str(probe.l4t_major()) if probe.l4t_major() else 'pas de Jetson Linux'}) — employer un kit --gpu none")
    places = [("destination", destination), ("racine des données", data_root)]
    if menu_entry is not None:
        places.append(("--menu" if menu_explicit else "dossier des entrées de menu", menu_entry.parent))
    for name, path in places:
        if control_characters(str(path)):
            failures.append(f"{name} {str(path)!r} : caractère de contrôle refusé — choisir un chemin sans caractère de contrôle")
        elif not path.is_absolute():
            failures.append(f"{name} : chemin absolu attendu ({path}) — indiquer un chemin absolu")
        elif inside(path, kit) or (program is not None and inside(path, program)):
            failures.append(f"{name} {path} dans le kit ou le programme — choisir un dossier hors du kit")
        elif not writable_target(path):
            failures.append(f"{name} {path} : dossier non accessible en écriture pour ce compte ({existing_ancestor(path)}) — choisir un "
                            "dossier de ce compte")
    if inside(data_root, destination) or inside(destination, data_root):
        failures.append(f"racine des données {data_root} et destination {destination} imbriquées — choisir deux dossiers distincts")
    for name in (POINTER, LAUNCHER, ICON):
        if (destination / name).is_dir():
            failures.append(f"{destination / name} est un dossier — rien ne le remplace : le déplacer")
    if program is None and designated(destination) is None:
        for path in foreign_files(kit, destination):
            failures.append(f"{path} existe et n'appartient pas à l'atelier — le déplacer, ou choisir un autre dossier (--destination ou "
                            "--emplacement)")
    if menu_entry is not None and menu_unsupported(destination):
        failures.append(menu_unsupported(destination))  # type: ignore[arg-type]
    if menu_entry is not None and not control_characters(str(menu_entry)):
        if menu_entry.is_dir() or (menu_entry.parent.exists() and not menu_entry.parent.is_dir()):
            failures.append(f"--menu {menu_entry.parent} : dossier attendu — indiquer un dossier")
        elif not free_or_ours(menu_entry, desktop_owner, destination):
            failures.append(f"entrée de menu {menu_entry} déjà présente, d'une autre application ou d'une autre installation — la laisser "
                            f"en place et installer avec --sans-menu (lanceur {destination / LAUNCHER}) ; {MENU_ELSEWHERE}")
    if qdrant_storage is not None and (not qdrant_storage.is_absolute() or inside(qdrant_storage, destination)):
        failures.append(f"stockage Qdrant {qdrant_storage} : chemin absolu hors de la destination attendu — indiquer un autre dossier")
    elif qdrant_storage is not None:
        # Mêmes règles que la racine des données : l'index y est écrit et doit survivre au redémarrage, donc au retrait du kit
        # (R3S-02). Qdrant démarre depuis ce dossier (supervisor.qdrant_working_directory) : il y lirait config/ et servirait
        # static/ s'ils existaient ; le runtime n'y crée que storage, snapshots, son verrou et son indicateur de démarrage.
        read_by_qdrant = [f"{name}/" for name in QDRANT_READS if (qdrant_storage / name).exists() or (qdrant_storage / name).is_symlink()]
        if control_characters(str(qdrant_storage)):
            failures.append(f"stockage Qdrant {str(qdrant_storage)!r} : caractère de contrôle refusé — choisir un chemin sans caractère de "
                            "contrôle (--qdrant-storage)")
        elif inside(qdrant_storage, kit) or (program is not None and inside(qdrant_storage, program)):
            failures.append(f"stockage Qdrant {qdrant_storage} dans le kit ou le programme — choisir un dossier hors du kit "
                            "(--qdrant-storage)")
        elif not writable_target(qdrant_storage):
            failures.append(f"stockage Qdrant {qdrant_storage} : dossier non accessible en écriture pour ce compte "
                            f"({existing_ancestor(qdrant_storage)}) — choisir un dossier de ce compte (--qdrant-storage)")
        elif read_by_qdrant:
            failures.append(f"stockage Qdrant {qdrant_storage} : contient {' et '.join(read_by_qdrant)}, que Qdrant lirait en démarrant "
                            "depuis ce dossier (configuration config/, pages static/) — choisir un dossier absent, vide ou réservé à "
                            "l'index (--qdrant-storage)")
        else:
            storage_fs = probe.filesystem(qdrant_storage)
            if storage_fs["fstype"] in VOLATILE_FILESYSTEMS:
                failures.append(f"stockage Qdrant {qdrant_storage} sur un volume non persistant ({storage_fs['fstype']}) monté sur "
                                f"{storage_fs['mount']} : l'index serait perdu au redémarrage — choisir un dossier sur un disque local "
                                "(--qdrant-storage)")
            elif storage_fs["fstype"] in REFUSED_FILESYSTEMS:
                failures.append(f"stockage Qdrant {qdrant_storage} sur {storage_fs['fstype']} ({storage_fs['mount']}) : Qdrant exige un "
                                "système de fichiers POSIX local (ni réseau, ni FAT, ni NTFS) — choisir un dossier sur un disque local "
                                "(--qdrant-storage)")
    if user_command is not None and not control_characters(str(user_command)) and not writable_target(user_command.parent):
        # La commande est écrite à la bascule, après la copie et la préparation : ses droits se contrôlent ici sans rien écrire.
        # Dossier absent (~/.local/bin) : les droits à corriger sont ceux du premier dossier existant, où il sera créé (U4-05).
        folder = user_command.parent
        blocked = existing_ancestor(folder)
        where = f"{folder}" if blocked == folder.absolute() else f"{blocked} ({folder} à y créer)"
        failures.append(f"commande {USER_COMMAND} : {where} non accessible en écriture pour ce compte — corriger ses droits "
                        f"(« chmod u+w {shlex.quote(str(blocked))} »), " + (command_fix or "ou installer avec --sans-menu"))
    if model is not None and model not in (manifest.get("model_profiles") or {}):
        failures.append(f"Modèle {model} absent de ce kit ({', '.join(ordered_models(manifest))}) — choisir un modèle livré")
    if ports is not None:
        failures += check_ports(ctx, ports)
    target_dir = destination / manifest["kit_id"]
    if (target_dir.exists() or target_dir.is_symlink()) and not (replaced is not None and same_path(target_dir, replaced)):
        failures.append(present_version(ctx, destination, manifest["kit_id"]))
    needed = int(manifest["requirements"]["install_bytes_min"])
    shared = data_checks and probe.device(destination) == probe.device(data_root)
    needed_total = needed + (DATA_MIN_FREE_BYTES if shared else 0)
    free = probe.free_bytes(destination)
    if free < needed_total and relocatable:
        text, volumes = space_refusal(ctx, args, free, needed_total, existing_ancestor(destination), shared, elsewhere_hint=elsewhere_hint)
        failures.append(text)
    elif free < needed_total and program is not None:
        failures.append(update_space_refusal(ctx, destination, free, needed_total, existing_ancestor(destination)))
    elif free < needed_total:
        detail = "programme" + (f" et réserve de {fr_gib(DATA_MIN_FREE_BYTES)} des données" if shared else "")
        failures.append(f"espace insuffisant sous {existing_ancestor(destination)} : {fr_gib(free)} libres, {fr_gib(needed_total)} "
                        f"nécessaires ({detail}) — libérer de la place, ou choisir des emplacements sur un volume local qui a la place "
                        "(--destination et --data-root, ou --emplacement)")
    else:
        passed.append(f"{fr_gib(free)} libres")
    filesystem = probe.filesystem(destination)
    if filesystem["fstype"] in VOLATILE_FILESYSTEMS:
        failures.append(f"destination sur un volume non persistant ({filesystem['fstype']}) monté sur {filesystem['mount']} : le programme "
                        "disparaîtrait au redémarrage — choisir un disque Linux local (ext4)")
    elif filesystem["fstype"] in REFUSED_FILESYSTEMS or filesystem["noexec"]:
        failures.append(f"destination sur {filesystem['fstype']}{' monté noexec' if filesystem['noexec'] else ''} ({filesystem['mount']}) : "
                        "liens symboliques et exécutables exigés, volume local seulement — choisir un disque Linux local (ext4)")
    data_free = None
    if data_checks:
        data_fs = probe.filesystem(data_root)
        if data_fs["fstype"] in VOLATILE_FILESYSTEMS:
            failures.append(f"racine des données sur un volume non persistant ({data_fs['fstype']}) monté sur {data_fs['mount']} : documents, "
                            "index et sauvegardes seraient perdus au redémarrage — choisir une racine des données sur un disque local "
                            "(--data-root ou --emplacement)")
        elif data_fs["fstype"] in REFUSED_FILESYSTEMS:
            failures.append(f"racine des données sur {data_fs['fstype']} ({data_fs['mount']}) : SQLite et les verrous de l'atelier exigent "
                            "un disque local — choisir une racine des données sur un volume local (--data-root ou --emplacement)")
        if not shared:
            data_free = probe.free_bytes(data_root)
            if data_free < DATA_MIN_FREE_BYTES:
                failures.append(f"racine des données {data_root} : {fr_gib(data_free)} libres, {fr_gib(DATA_MIN_FREE_BYTES)} au moins "
                                "exigés (réserve des sauvegardes) — choisir une racine des données sur un volume qui a la place "
                                "(--data-root)")
    if failures:
        raise PrecheckRefusal("Précontrôles refusés, rien n'a été écrit :\n" + "\n".join(f"  - {item}" for item in failures), volumes)
    return {"passed": passed, "free": free, "needed": needed_total, "shared": shared, "data_free": data_free}


def kit_volume_hint(ctx: Context) -> str:
    filesystem = ctx.probe.filesystem(ctx.kit)
    if filesystem["fstype"] in NON_LINUX_FILESYSTEMS:
        return (f" Le kit est sur un volume {filesystem['fstype']} ({filesystem['mount']}) : ce système de fichiers ne garde ni les liens "
                "symboliques ni les droits d'exécution ; extraire l'archive sur un disque Linux local (ext4, par exemple).")
    return ""


def ldd_targets(manifest: dict[str, Any]) -> list[str]:
    """Fichiers du kit soumis à ldd : `target.ldd_checks`, sinon Tesseract. Liste unique de la vérification ciblée et des
    contrôles système : ldd ne vise jamais un fichier non vérifié juste avant (ldd(1))."""
    target = manifest.get("target") or {}
    return list(target.get("ldd_checks") or [target.get("tesseract") or linux_kit.TESSERACT_BINARY])


def pre_copy_files(manifest: dict[str, Any]) -> list[str]:
    """Fichiers du kit exécutés ou lus avant la copie : script de dérivation des profils et ses imports possibles
    (PRE_COPY_FILES), profils livrés des modèles (model_profiles)."""
    profiles = [str(path) for path in (manifest.get("model_profiles") or {}).values()]
    return sorted({*PRE_COPY_FILES, *profiles})


def added_compiled_modules(kit: Path, expected: dict[str, str]) -> list[str]:
    """Fichiers absents de SHA256SUMS qu'une recherche par nom trouverait à la place d'un module vérifié, dans les paquets que
    la dérivation contrôlée lit dans le nouveau kit (PRE_COPY_PACKAGES) : module compilé (.so), bytecode sans source (.pyc),
    ou `__init__` d'un dossier de paquet, trouvé avant le module du même nom (PEP 420)."""
    found = []
    for package in PRE_COPY_PACKAGES:
        folder = kit / package
        names = sorted(os.listdir(folder)) if folder.is_dir() and not folder.is_symlink() else []
        for name in names:
            relative = f"{package}/{name}"
            if name.endswith((".so", ".pyc")) and relative not in expected:
                found.append(relative)
            elif (folder / name).is_dir():
                found += [f"{relative}/{init}" for init in sorted(os.listdir(folder / name))
                          if PACKAGE_INIT.fullmatch(init) and f"{relative}/{init}" not in expected]
    return found


def verify_targeted(ctx: Context, manifest: dict[str, Any], report: Report, *, pre_copy: bool = False) -> None:
    """Vérification ciblée en Python, après les contrôles d'`installer.sh` : SHA256SUMS contre le manifeste, listes déclarées
    contre SHA256SUMS, fichiers soumis à ldd (ldd_targets) et, pour une mise à jour (`pre_copy`), fichiers exécutés ou lus
    avant la copie (pre_copy_files). Les autres fichiers sont hachés pendant la copie, qui est retirée au moindre écart :
    aucun fichier du kit non vérifié n'est désigné, et le kit n'est lu qu'une fois. S'exécutent avant d'être hachés
    `installer.sh` lui-même et les fichiers listés de la bibliothèque standard du CPython du kit, chargés avant cette
    fonction ; modèle de menace et portée exacte : en-tête du module."""
    kit = ctx.kit
    problems: list[str] = []
    try:
        if manifest.get("sha256sums_sha256") != linux_kit.stream_hash(kit / linux_kit.SUMS):
            problems.append("SHA256SUMS différent du manifeste")
        expected = linux_kit.read_sums(kit)
        links, _ = linux_kit.declared(kit, expected)
    except (linux_kit.KitError, OSError, ValueError) as error:
        problems.append(str(error))
        expected, links = {}, {}
    for relative in ldd_targets(manifest):
        path = kit / relative
        if path.is_symlink() or not path.is_file() or linux_kit.stream_hash(path) != expected.get(relative):
            problems.append(f"{relative} altéré ou absent")
    for relative in pre_copy_files(manifest) if pre_copy else []:
        path = kit / relative
        if relative not in expected:
            # Module d'un paquet absent du commit : il ne doit pas apparaître dans le kit, où il serait importé sans contrôle.
            if path.exists() or path.is_symlink():
                problems.append(f"{relative} ajouté, absent de SHA256SUMS")
        elif path.is_symlink() or not path.is_file() or linux_kit.stream_hash(path) != expected[relative]:
            problems.append(f"{relative} altéré ou absent")
    for relative in added_compiled_modules(kit, expected) if pre_copy else []:
        problems.append(f"{relative} ajouté, absent de SHA256SUMS : fichier étranger parmi les modules que la dérivation lit avant la copie")
    if problems:
        raise InstallError(f"Kit non conforme ({' ; '.join(problems)}) : ré-extraire l'archive après avoir contrôlé son empreinte "
                           f"(sha256sum -c) ; rien n'a été installé." + kit_volume_hint(ctx), EXIT_REFUSED)
    known = set(expected) | set(links) | {linux_kit.SUMS, linux_kit.MANIFEST}
    added = sorted(path.relative_to(kit).as_posix() for path, _ in linux_kit.walk_tree(kit) if path.relative_to(kit).as_posix() not in known)
    if added:
        shown = ", ".join(added[:5]) + (f" et {len(added) - 5} autres" if len(added) > 5 else "")
        report.step("kit", "info", f"Fichiers ajoutés dans le dossier du kit, ignorés (non copiés) : {shown}")
    checks = len(ldd_targets(manifest))
    early = f" et {len([item for item in pre_copy_files(manifest) if item in expected])} fichiers lus avant la copie" if pre_copy else ""
    report.step("kit", "ok", f"SHA256SUMS, SYMLINKS, EXECUTABLES, {checks} fichiers soumis à ldd{early} conformes ; autres fichiers "
                             "vérifiés pendant la copie",
                screen=f"empreintes de contrôle, {checks} fichiers soumis à ldd{early} conformes ; les autres fichiers sont vérifiés "
                       "pendant la copie")


def component_of(manifest: dict[str, Any], soname: str, labels: set[str]) -> str:
    record = ((manifest.get("target") or {}).get("system_packages") or {}).get(soname) or {}
    if isinstance(record, dict) and record.get("component"):
        return str(record["component"])
    users = " ".join((manifest.get("target") or {}).get("system_libraries_required_by", {}).get(soname, [])) + " " + " ".join(labels)
    text = users.lower()
    if "tesseract" in text:
        return "OCR Tesseract"
    if "cv2" in text or "opencv" in text:
        return "OpenCV (OCR et tableaux)"
    if "cuda_jetpack" in text:
        return "GPU Jetson"
    return "bibliothèque C/C++"


def same_build_os(manifest: dict[str, Any], release: dict[str, str]) -> bool:
    built = (manifest.get("build_host") or {}).get("os_release") or {}
    return bool(built.get("ID") and built.get("VERSION_ID") and built.get("ID") == release.get("ID")
                and built.get("VERSION_ID") == release.get("VERSION_ID"))


def package_hint(manifest: dict[str, Any], soname: str, matches: bool) -> str:
    record = ((manifest.get("target") or {}).get("system_packages") or {}).get(soname) or {}
    package = record.get("package") if isinstance(record, dict) else None
    if package and matches:
        return f"paquet du système de fabrication ({record.get('observed_on') or 'non relevé'}) : {package}"
    return "paquet à identifier pour ce système"


def ldd_label(relative: str, target: dict[str, Any]) -> str:
    if relative == target.get("tesseract", linux_kit.TESSERACT_BINARY):
        return "Tesseract"
    return relative.rsplit("/", 1)[-1]


def system_check(ctx: Context, manifest: dict[str, Any], report: Report) -> None:
    """Bibliothèques, libstdc++ et ldd du poste cible, sur les seuls fichiers vérifiés et sans écriture ; refus en liste, une
    ligne par bibliothèque avec son composant et le paquet du système de fabrication quand le système est le même."""
    target, probe = manifest["target"], ctx.probe
    failures: list[str] = []
    missing: dict[str, set[str]] = {}
    available = probe.shared_libraries()
    if available is None:
        failures.append("ldconfig introuvable dans /sbin, /usr/sbin, /usr/bin et /bin : les bibliothèques du système ne peuvent pas être "
                        "comparées au kit — le faire installer par l'administrateur du poste (paquet libc-bin sous Debian et Ubuntu)")
    else:
        for name in target.get("system_libraries") or []:
            if name not in available:
                missing.setdefault(name, set())
        for name, reason in (target.get("optional_system_libraries") or {}).items():
            if name not in available:
                report.step("systeme", "orange", f"bibliothèque facultative absente : {name} ({reason}) ; installation poursuivie")
    if target.get("glibcxx_min"):
        have = probe.glibcxx_max()
        if have is None:
            failures.append(f"libstdc++.so.6 introuvable : GLIBCXX {target['glibcxx_min']} exigé — faire installer libstdc++ par "
                            "l'administrateur du poste")
        elif linux_kit.version_tuple(have) < linux_kit.version_tuple(target["glibcxx_min"]):
            failures.append(f"libstdc++ du poste en GLIBCXX {have} : GLIBCXX {target['glibcxx_min']} exigé — faire installer une "
                            "libstdc++ plus récente par l'administrateur du poste")
    for relative in ldd_targets(manifest):
        label = ldd_label(relative, target)
        linked = probe.ldd(ctx.kit / relative)
        unresolved = [line.strip() for line in (linked.stdout + "\n" + linked.stderr).splitlines() if "not found" in line]
        for line in unresolved:
            match = re.match(r"(\S+) => not found", line)
            if match:
                missing.setdefault(match.group(1), set()).add(label)
            else:
                failures.append(f"bibliothèques système de {label} manquantes ou trop anciennes ({line}) — à faire installer par "
                                "l'administrateur du poste")
        if linked.returncode and not unresolved:
            failures.append(f"ldd en échec sur {label} ({linked.stderr.strip()[-300:]}) — à examiner avec l'administrateur du poste")
    matches = same_build_os(manifest, probe.os_release())
    lines = [f"{name} — {component_of(manifest, name, labels)} — {package_hint(manifest, name, matches)}" for name, labels in sorted(missing.items())]
    lines += failures
    if lines:
        raise InstallError("Contrôles du système refusés, rien n'a été écrit :\n" + "\n".join(f"  - {line}" for line in lines)
                           + "\nÀ faire installer par l'administrateur du poste ; l'installateur n'installe aucun paquet.", EXIT_SYSTEM)
    report.step("systeme", "ok", f"{len(target.get('system_libraries') or [])} bibliothèques, GLIBCXX, "
                                 f"{len(ldd_targets(manifest))} contrôles ldd")


# --- Étapes communes ------------------------------------------------------------------------------------------------------

def rewrite_python_prefix(program: Path, manifest: dict[str, Any]) -> int:
    """Jeton du préfixe de CPython remplacé par le préfixe réel du programme installé, comme uv à l'installation."""
    prefix = str((program / ".runtime/python" / manifest["python"]["key"]).resolve()).encode()
    rewritten = 0
    for item in manifest.get("neutralizations", []):
        if not item.get("rewrite_at_install"):
            continue
        path = program / item["path"]
        data = path.read_bytes()
        token = item["token"].encode()
        if data.count(token) != item["replacements"]:
            raise InstallError(f"{item['path']} : {data.count(token)} jetons pour {item['replacements']} attendus")
        linux_kit.write_atomic(path, data.replace(token, prefix), mode=0o644)
        rewritten += item["replacements"]
    return rewritten


def accepts(function: Callable[..., Any], name: str) -> bool:
    try:
        return name in inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False


def copy_verified(ctx: Context, manifest: dict[str, Any], program: Path) -> dict[str, Any]:
    """Copie du kit, chaque fichier haché pendant la copie ; progression affichée si la copie la fournit (`progress`). La copie
    est liée à la liste et au manifeste vérifiés avant la confirmation : SHA256SUMS doit garder l'empreinte contrôlée
    (`sums_sha256`), et le manifeste copié doit être celui qui a été lu ; un kit remplacé entre-temps n'est ni copié ni
    désigné."""
    progress = Progress(ctx, "Copie", int(manifest.get("bytes") or 0))
    copy = linux_kit.install_copy
    options: dict[str, Any] = {}
    if accepts(copy, "progress"):
        options["progress"] = progress
    if accepts(copy, "sums_sha256"):
        options["sums_sha256"] = manifest["sha256sums_sha256"]
    try:
        result = copy(ctx.kit, program, **options)
        try:
            copied = read_json(program / linux_kit.MANIFEST)
        except (OSError, ValueError):
            copied = None
        if copied != manifest:
            shutil.rmtree(program, ignore_errors=True)
            raise linux_kit.KitError(f"{linux_kit.MANIFEST} a changé depuis sa vérification : kit remplacé pendant l'installation, "
                                     "ré-extraire l'archive")
        return result
    except linux_kit.KitError as error:
        raise InstallError(f"Kit altéré ({error}) ; copie partielle retirée, rien n'a été désigné ; ré-extraire l'archive."
                           + kit_volume_hint(ctx), EXIT_PARTIAL) from error
    finally:
        progress.close()


def prepare_program(ctx: Context, plan: Plan, report: Report, manifest: dict[str, Any], program: Path) -> None:
    """Copie vérifiée, préfixe de CPython, environnement isolé hors ligne et précompilation."""
    plan.begin("copie", fr_size(int(manifest.get("bytes") or 0)))
    copy = copy_verified(ctx, manifest, program)
    report.step("copie", "ok", f"{copy['files']} fichiers et {copy['links']} liens dans {program}",
                screen=f"{fr_number(copy['files'], 0)} fichiers et {fr_number(copy['links'], 0)} liens copiés et vérifiés dans {program}")
    plan.begin("environnement")
    report.step("python", "ok", f"préfixe de CPython réécrit ({rewrite_python_prefix(program, manifest)} occurrences)",
                screen="interpréteur adapté à son emplacement")
    bootstrap = ctx.runner.run([str(program / "bootstrap.sh"), "--offline", "--no-dev"], cwd=program, timeout=3600)
    if bootstrap.returncode:
        raise InstallError(f"Environnement isolé non créé : {(bootstrap.stderr or bootstrap.stdout).strip()[-600:]}")
    report.step("environnement", "ok", "bootstrap.sh --offline --no-dev", screen="créé hors ligne depuis le cache du kit")
    plan.begin("precompilation")
    # Précompilation de ce qu'importera l'exploitation : le dossier programme ne reçoit plus de bytecode ensuite. Quelques
    # fichiers d'exemple des paquets ne compilent pas (syntaxe d'un autre Python) : code de sortie consigné, non bloquant.
    stdlib = program / ".runtime/python" / manifest["python"]["key"] / "lib/python3.12"
    compiled = ctx.runner.run([str(venv_python(program)), "-m", "compileall", "-q", "-j", "0", str(stdlib),
                               str(program / ".venv/lib/python3.12/site-packages"), str(program / "services"), str(program / "tools")],
                              cwd=program, timeout=3600)
    report.step("precompilation", "ok", f"compileall, code {compiled.returncode}", screen="terminée")


def doctor_gate(ctx: Context, report: Report, program: Path, profile: str) -> dict[str, Any]:
    doctor = rag(ctx, program, "doctor", "--profile", profile)
    verdict = doctor.get("verdict") or {}
    report.data["verdict_before_start"] = verdict
    red = [item for item in verdict.get("rubrics", []) if item.get("level") == RED]
    if doctor.get("_returncode") or not verdict:
        raise InstallError(f"Vérification impossible : {doctor.get('message')}")
    if red:
        raise InstallError("Vérification refusée : " + " ".join(f"{item.get('message')} {item.get('action') or ''}".strip() for item in red))
    report.step("doctor", "ok", str(verdict.get("summary", "")))
    return verdict


def start_and_check(ctx: Context, plan: Plan, report: Report, destination: Path, program: Path, profile: str, *, browser: bool) -> None:
    pointer = read_pointer(destination)
    diagnostic = launcher_command(pointer, destination, "diagnostic")
    plan.begin("demarrage", f"attente maximale du démarrage : {STARTUP_WAIT_MAX_S} s")
    up = rag(ctx, program, "up", "--profile", profile)
    if up.get("status") != "running":
        raise InstallError(f"Démarrage refusé : {up.get('message')} Le programme est installé et désigné ; « {diagnostic} » détaille l'état.")
    # up rend l'instance déjà en marche sur ces données si son profil est identique (supervisor.start) : elle doit être
    # celle de ce programme, jamais une instance d'une autre version.
    executable = (up.get("supervisor") or {}).get("executable")
    if not isinstance(executable, str) or not inside(Path(executable), program):
        # supervisor.stop agit sur le dossier de données du profil : le lanceur arrête l'instance, quel que soit son programme.
        raise InstallError(f"L'instance démarrée n'appartient pas au programme {program} (superviseur : {executable or 'inconnu'}) : une "
                           f"autre version tourne sur ces données ; l'arrêter (« {launcher_command(pointer, destination, 'arreter')} »), "
                           f"puis « {launcher_command(pointer, destination, 'ouvrir')} ».")
    mark_started(destination, program, holding_lock=True)
    report.data["started_on_data"] = True
    report.step("demarrage", "ok", str(up.get("instance_id", "")), screen="atelier démarré")
    doctor = rag(ctx, program, "doctor", "--profile", profile)
    verdict = doctor.get("verdict") or {}
    report.data["verdict"] = verdict
    for item in verdict.get("rubrics", []):
        ctx.say(item.get("level", "?"), item.get("rubric", ""), item.get("message", ""))
        if item.get("proposal"):
            print(f"      Proposition : {item['proposal']}", file=ctx.out)
    report.step("verdict", str(verdict.get("level", "?")), str(verdict.get("summary", "")))
    plan.begin("controle")
    control = rag(ctx, program, "selftest", "--profile", profile, timeout=3600)
    report.data["selftest"] = {key: value for key, value in control.items() if key != "_returncode"}
    for item in control.get("steps", []):
        ctx.say(item.get("status", "?"), item.get("step", ""), item.get("detail", ""))
    if control.get("level") == RED or control.get("_returncode"):
        raise InstallError(f"{control.get('summary') or control.get('message')} Le programme est installé et désigné ; « {diagnostic} » "
                           "et le rapport d'installation détaillent l'échec.")
    report.step("controle", str(control.get("level", "ok")), str(control.get("summary", "")))
    plan.begin("ouverture")
    opened = rag(ctx, program, "open", "--profile", profile, *([] if browser else ["--no-browser"]))
    if opened.get("_returncode"):
        report.step("ouverture", "orange", f"{opened.get('message')} ; « {launcher_command(pointer, destination, 'ouvrir', '--no-browser')} » "
                                           "affiche le lien")
    elif browser:
        report.step("ouverture", "ok", "atelier ouvert dans le navigateur par défaut")
    else:
        # Lien à usage unique : affiché au terminal, jamais écrit dans un rapport.
        print(f"Lien à usage unique, à ouvrir dans un navigateur de ce poste : {opened.get('url')}", file=ctx.out)
        report.step("ouverture", "ok", "lien à usage unique affiché")


def version_entry(manifest: dict[str, Any], program: Path, data_root: Path, profiles: dict[str, str], model: str, **extra: Any) -> dict[str, Any]:
    return {"kit_id": manifest["kit_id"], "program": str(program), "python": manifest["python"]["executable"],
            "data_root": str(data_root), "profile": profiles[model], "profiles": profiles, "model": model,
            "started_on_data": False, **extra}


def remove_new_program(destination: Path, program: Path, report: Report) -> bool:
    """Retire un dossier programme créé par cette exécution, jamais celui que le pointeur désigne (relu sur disque)."""
    current = designated(destination)
    if current and same_path(current["program"], program):
        return False
    if program.exists() and not program.is_symlink() and (program / linux_kit.MANIFEST).is_file():
        shutil.rmtree(program)
        report.data["new_program_removed"] = str(program)
    return True


def failure_message(destination: Path, program: Path, previous: dict[str, Any] | None) -> str | None:
    """État laissé après un échec, écrit après sa cause : version que le pointeur désigne vraiment, et la suite possible.
    `previous` : version en place d'une mise à jour, arrêtée avant la copie."""
    current = designated(destination)
    pointer = safe_pointer(destination)
    if current and same_path(current["program"], program):
        return (f"La version {current['kit_id']} est la version courante (bascule faite) ; « {launcher_command(pointer, destination, 'diagnostic')} » "
                "détaille son état" + (f", « {installer_command(program, 'rollback')} » revient à {previous['kit_id']}" if previous else "") + ".")
    if current and previous and same_path(current["program"], previous["program"]):
        return f"La version {current['kit_id']} reste la version courante ; la relancer par « {launcher_command(pointer, destination, 'ouvrir')} »."
    return None


def instance_left(ctx: Context, program: Path, profile: str, current: dict[str, Any], *, started_here: bool, running_before: bool,
                  pointer: dict[str, Any] | None, destination: Path) -> str:
    """Échec d'une mise à jour avant l'arrêt de la version en place : l'instance qu'elle a démarrée pour la sauvegarde est
    arrêtée ; celle que l'utilisateur avait démarrée reste en marche. Rend l'état laissé, écrit après la cause."""
    kept = f"La version {current['kit_id']} reste la version courante"
    if running_before:
        return f"{kept} ; son instance, déjà démarrée avant la mise à jour, reste démarrée."
    if not started_here:
        return f"{kept}."
    down = rag(ctx, program, "down", "--profile", profile)
    if not down.get("_returncode") and down.get("status") in {"stopped", "failed"}:
        return f"{kept} ; l'instance démarrée pour la sauvegarde a été arrêtée, comme avant la mise à jour."
    return (f"{kept} ; l'instance démarrée pour la sauvegarde est toujours en marche : « {launcher_command(pointer, destination, 'arreter')} » "
            "l'arrête.")


def as_partial(error: BaseException) -> InstallError:
    """Échec après le début des écritures : code 5, message d'origine conservé."""
    if isinstance(error, InstallError) and error.code == EXIT_PARTIAL:
        return error
    message = str(error) if isinstance(error, (InstallError, linux_kit.KitError)) else f"{type(error).__name__} : {error}"
    return InstallError(message, EXIT_PARTIAL)


def running_profile(ctx: Context, program: Path, profiles: dict[str, str], pointer: dict[str, Any] | None,
                    destination: Path) -> tuple[str | None, str | None]:
    """Profil de l'instance en marche sur ces données parmi les profils connus ; refus si elle tourne avec un autre, que le
    lanceur arrête (supervisor.stop agit sur le dossier de données du profil, pas sur son empreinte)."""
    foreign = False
    for model, profile in profiles.items():
        state = rag(ctx, program, "status", "--profile", profile)
        if state.get("status") in RUNNING:
            if state.get("profile_matches_current"):
                return model, profile
            foreign = True
    if foreign:
        raise InstallError("Une instance tourne sur ces données avec un profil que l'installation ne connaît pas : l'arrêter "
                           f"(« {launcher_command(pointer, destination, 'arreter')} ») avant la mise à jour ; rien n'a été installé.",
                           EXIT_REFUSED)
    return None, None


def model_of_state(state: dict[str, Any], profiles: dict[str, str], principal: str) -> str | None:
    """Modèle de l'instance en marche : profil dont l'empreinte est celle de l'instance (runtime.json), sinon le principal si
    l'état le désigne ; None pour un profil inconnu de l'installation."""
    digest = state.get("profile_sha256")
    if digest:
        for model, path in profiles.items():
            try:
                if file_sha256(path) == digest:
                    return model
            except OSError:
                continue
    return principal if state.get("profile_matches_current") else None


def confirm(ctx: Context, args: argparse.Namespace, title: str, lines: list[str], *, add: list[str] | None = None) -> None:
    """Récapitulatif, puis confirmation : `--oui`, ou « o » au terminal. Hors terminal et sans `--oui`, refus avant toute
    écriture avec la commande exacte à relancer."""
    text = f"{title} :\n" + "\n".join(f"  {line}" for line in lines)
    if getattr(args, "oui", False):
        print(text, file=ctx.out, flush=True)
        return
    if not ctx.interactive:
        command = suggestion(ctx, args, add=[*(add or []), "--oui"])
        print(text, file=ctx.err, flush=True)
        raise InstallError(f"Confirmation requise : hors terminal, rien n'est fait sans --oui. Après lecture du récapitulatif, relancer : "
                           f"{command} ; rien n'a été écrit.", EXIT_REFUSED)
    print(text, file=ctx.out, flush=True)
    if ctx.question("Continuer ? [o/N] ").lower() not in {"o", "oui"}:
        raise InstallError("Abandon demandé : rien n'a été écrit.", EXIT_REFUSED)


def end_block(ctx: Context, title: str, rows: list[tuple[str, str]], footer: str | None = None) -> None:
    print(title, file=ctx.out)
    for label, value in rows:
        print(f"  {label} : {value}", file=ctx.out)
    if footer:
        print(footer, file=ctx.out)
    ctx.out.flush()


def usage_rows(pointer: dict[str, Any], destination: Path, entry: dict[str, Any]) -> list[tuple[str, str]]:
    """Lignes communes des blocs de fin : programme, données, modèles et commandes du lanceur."""
    program = Path(entry["program"])
    def command(*words: str) -> str:
        return f"« {launcher_command(pointer, destination, *words)} »"

    models = [entry["model"], *(model for model in entry.get("profiles") or {} if model != entry["model"])]
    ways = []
    if integration_enabled(pointer) and pointer.get("menu_entry"):
        ways.append(f"menu des applications > {MENU_NAME}")
    ways.append(command("ouvrir"))
    if pointer.get("user_command"):
        ways.append(f"« {quoted(str(destination / LAUNCHER), 'ouvrir')} »")
    rows = [(END_LABELS["program"], str(program)), (END_LABELS["data"], entry["data_root"]), (END_LABELS["profile"], entry["profile"]),
            (END_LABELS["models"], ", ".join(f"{model} (principal)" if model == entry["model"] else model for model in models)),
            (END_LABELS["open"], ", ou ".join(ways)), (END_LABELS["stop"], command("arreter")),
            (END_LABELS["diagnose"], command("diagnostic")), (END_LABELS["save"], command("sauvegarder"))]
    for other in models[1:]:
        rows.append((END_LABELS["model"], f"{command('modele', other)} (durable) ou {command('ouvrir', '--modele', other)} (une ouverture)"))
    if (program / GUIDE_NAME).is_file():
        rows.append((END_LABELS["guide"], str(program / GUIDE_NAME)))
    return rows


# --- Sous-commandes : installation et reprise ----------------------------------------------------------------------------

def install_locations(ctx: Context, args: argparse.Namespace) -> tuple[Path, Path, bool]:
    """Destination et racine des données : options explicites, sinon --emplacement, sinon $XDG_DATA_HOME/atelier-documentaire.
    Le troisième élément dit si un volume proposé peut remplacer ces emplacements (aucun chemin explicite)."""
    base: Path | None = None
    if args.emplacement:
        base = Path(args.emplacement).absolute()
    elif not (args.destination and args.data_root):
        base = default_base(ctx.environ)
    destination = Path(args.destination).absolute() if args.destination else base / PROGRAM_FOLDER  # type: ignore[operator]
    data_root = Path(args.data_root).absolute() if args.data_root else base / DATA_FOLDER  # type: ignore[operator]
    # Une destination déjà munie d'un pointeur garde sa graphie, quelle que soit celle tapée (pointer_destination, U6-01).
    return pointer_destination(destination), data_root, not (args.destination or args.data_root)


def backups_in(folder: Path) -> list[Path]:
    """Sauvegardes d'un dossier de sauvegardes (manifest.json présent), de la plus ancienne à la plus récente."""
    return sorted(path for path in folder.iterdir() if (path / "manifest.json").is_file()) if folder.is_dir() else []


def latest_backup(data_root: Path) -> Path | None:
    found = backups_in(data_root / "backups")
    return found[-1] if found else None


def backup_date(path: Path) -> str:
    try:
        return fr_utc(read_json(path / "manifest.json").get("created_at_utc")) or "date inconnue"
    except (OSError, ValueError):
        return "date inconnue"


def data_user(ctx: Context, data_root: Path) -> tuple[Path, str] | None:
    """Destination et version désignée qui emploient cette racine des données."""
    for destination in known_destinations(ctx):
        try:
            pointer = read_pointer(destination) or {}
        except (OSError, ValueError, InstallError):
            continue
        for entry in (pointer.get("current"), pointer.get("previous")):
            if entry and inside(Path(entry["data_root"]), data_root) and inside(data_root, Path(entry["data_root"])):
                return destination, entry["kit_id"]
    return None


def data_in_use(ctx: Context, data_root: Path) -> str | None:
    """Destination dont une version désignée emploie cette racine des données, en texte."""
    user = data_user(ctx, data_root)
    return f"{user[0]} (version {user[1]})" if user else None


def install_summary(ctx: Context, manifest: dict[str, Any], destination: Path, data_root: Path, facts: dict[str, Any], model: str,
                    ports: dict[str, int] | None, port_notes: list[str], integration: dict[str, Any], start: bool) -> list[str]:
    models = ordered_models(manifest)
    lines = [f"Version : {manifest['kit_id']}",
             f"Modèle principal : {model}" + (" (défaut du kit)" if model == manifest.get("default_model") else "")
             + f" ; modèles livrés : {', '.join(models)}",
             f"Programme : {destination / manifest['kit_id']}", f"Données : {data_root}",
             f"Place : {fr_gib(facts['free'])} libres ; {fr_gib(facts['needed'])} nécessaires"]
    if ports:
        lines.append(f"Ports : {ports['app']} (API), {ports['qdrant']} (Qdrant), {ports['ollama']} (Ollama)"
                     + (f" ; {', '.join(port_notes)} : {PORT_RULE}" if port_notes else ""))
    else:
        lines.append("Ports : ceux du profil livré, contrôlés à la création du profil")
    if integration.get("menu"):
        lines.append(f"Bureau : entrée de menu {integration['menu_entry']}, icône {destination / ICON}"
                     + (f", commande {integration['user_command']}" if integration.get("user_command") else ", sans commande atelier"))
    else:
        lines.append("Bureau : aucune intégration (--sans-menu) ; lanceur " + str(destination / LAUNCHER))
    lines.append("Démarrage : " + ("après l'installation, puis ouverture dans le navigateur" if start else "non (--no-start)"))
    return lines


def choose_volume(ctx: Context, refusal: PrecheckRefusal) -> Path:
    """Choix numéroté d'un volume proposé, après le refus (et l'indice d'une installation faite ailleurs) ; un abandon
    s'arrête sans réimprimer le refus déjà affiché."""
    print(str(refusal), file=ctx.out)
    index = choose(ctx, "Volumes locaux qui ont la place :", [f"{item['mount']} — {fr_gib(item['free'])} libres" for item in refusal.volumes])
    if index is None:
        raise InstallError("Abandon demandé : rien n'a été écrit.", EXIT_REFUSED)
    return Path(refusal.volumes[index]["mount"]) / DEFAULT_FOLDER


def refuse_previous_version(manifest: dict[str, Any], destination: Path, pointer: dict[str, Any] | None) -> None:
    """Le kit de la version précédente encore utile au retour arrière ne propose ni mise à jour ni retrait : rollback."""
    current, previous = (pointer or {}).get("current"), (pointer or {}).get("previous")
    if current and previous and previous["kit_id"] == manifest["kit_id"] and not previous.get("rolled_back"):
        raise InstallError(f"La version {previous['kit_id']} est la version précédente de {destination} : pour y revenir, "
                           f"« {installer_command(Path(current['program']), 'rollback')} » ; rien n'a été modifié.", EXIT_REFUSED)


def elsewhere_text(ctx: Context) -> str:
    """Aucune installation retrouvée : la mise à jour d'une installation faite ailleurs (installateur de 78ec95c, par exemple),
    au lieu d'une installation neuve sur des données vides."""
    return ("aucune installation retrouvée (registre, emplacement par défaut) ; si l'atelier est déjà installé ailleurs, ne choisir "
            f"aucun volume : « {installer_command(ctx.kit, 'update', '--destination')} <dossier des versions> »")


def elsewhere_line(ctx: Context) -> str:
    """Ligne du récapitulatif d'une installation neuve, et de `verifier`, quand aucune installation n'est retrouvée."""
    return ("Installation existante : aucune trouvée (registre, emplacement par défaut) ; pour mettre à jour une installation faite à "
            f"un autre emplacement : « {installer_command(ctx.kit, 'update', '--destination')} <dossier des versions> »")


def install(ctx: Context, args: argparse.Namespace) -> int:
    manifest = read_manifest(ctx.kit)
    found: list[Path] = []
    implicit = getattr(args, "implicit", False) and not (args.destination or args.data_root or args.emplacement or args.reprendre_donnees)
    if implicit:
        own = installation_of(ctx.kit)
        if own:
            print(f"Ce dossier est un programme installé : voici l'état de l'installation. Pour une mise à jour, lancer "
                  f"{INSTALLER_NAME} depuis le dossier d'un kit plus récent.", file=ctx.out)
            return status_report(ctx, own, as_json=False)
        refuse_undesignated_version(ctx, "status")
        found = known_destinations(ctx)
        if found:
            destination = found[0] if len(found) == 1 else resolve_destination(ctx, args)
            pointer = read_pointer(destination)
            current = (pointer or {}).get("current")
            if current and current["kit_id"] == manifest["kit_id"]:
                print(f"La version {current['kit_id']} est déjà la version courante de {destination}.", file=ctx.out)
                return status_report(ctx, destination, as_json=False)
            refuse_previous_version(manifest, destination, pointer)
            if current:
                print(f"Installation existante trouvée dans {destination} (version {current['kit_id']}) : ce kit en propose la mise à jour.",
                      file=ctx.out)
                args.destination = destination
                return update(ctx, args)
    elif not (args.destination or args.data_root or args.reprendre_donnees):
        found = known_destinations(ctx)
    # Installation neuve à l'emplacement par défaut ou sur un autre volume, sans installation connue : elle peut doubler une
    # installation faite ailleurs que ni le registre ni l'emplacement par défaut ne désignent (U3-03).
    elsewhere = None if (found or args.destination or args.data_root or args.reprendre_donnees) else elsewhere_text(ctx)
    reprise = bool(args.reprendre_donnees)
    model = args.model or manifest["default_model"]
    start = not args.no_start
    report = Report(ctx, "reprise" if reprise else "install", kit=str(ctx.kit), kit_id=manifest["kit_id"])
    plan = Plan(ctx, report, INSTALL_STEPS + (START_STEPS if start else []))
    while True:
        destination, data_root, relocatable = install_locations(ctx, args)
        program = destination / manifest["kit_id"]
        integration, notes = integration_for(ctx, destination, sans_menu=args.sans_menu, menu_dir=Path(args.menu) if args.menu else None)
        interrupted = interrupted_install(ctx, data_root, destination, reprise=reprise, args=args)
        refuse_existing(ctx, args, destination, data_root, reprise=reprise, interrupted=interrupted)
        refuse_if_locked(destination)
        backup = reprise_checks(ctx, args, data_root) if reprise else None
        ports_value, ports, port_notes = (None, None, []) if reprise else choose_ports(ctx, manifest, model, args.ports)
        plan.begin("precontroles")
        try:
            facts = precheck(ctx, manifest, destination, data_root, qdrant_storage=args.qdrant_storage, menu_entry=(
                Path(integration["menu_entry"]) if integration.get("menu_entry") else None), menu_explicit=bool(args.menu),
                model=None if reprise else model, ports=args.ports, args=args, relocatable=relocatable,
                replaced=Path(interrupted["program"]) if interrupted else None,
                user_command=Path(integration["user_command"]) if integration.get("user_command") else None, elsewhere_hint=elsewhere)
        except PrecheckRefusal as refusal:
            if refusal.volumes and relocatable and ctx.interactive and not args.oui:
                args.emplacement = choose_volume(ctx, refusal)
                continue
            raise
        break
    report.data.update(destination=str(destination), data_root=str(data_root))
    report.step("precontroles", "ok", ", ".join(facts["passed"]) + (f" ; {', '.join(port_notes)} : ports retenus {ports_value}" if port_notes else ""))
    for note in notes:
        ctx.warn(note)
    plan.begin("kit")
    verify_targeted(ctx, manifest, report)
    plan.begin("systeme")
    system_check(ctx, manifest, report)
    lines = install_summary(ctx, manifest, destination, data_root, facts, model, ports, port_notes, integration, start)
    if reprise:
        lines[1] = "Modèle principal : celui du profil repris, s'il est livré par ce kit"
        lines[5] = "Ports : ceux du profil repris, contrôlés par le diagnostic avant la bascule"
        lines.insert(4, f"Reprise des données de {data_root} : aucune version installée ne peut les sauvegarder avant une éventuelle "
                        f"évolution de leur format ; dernière sauvegarde : {backup} ({backup_date(backup)})")  # type: ignore[arg-type]
    if interrupted:
        lines.append(interrupted_text(interrupted))
    if elsewhere:
        lines.append(elsewhere_line(ctx))
    confirm(ctx, args, "Récapitulatif de la reprise" if reprise else "Récapitulatif de l'installation", lines,
            add=["--ports", ports_value] if ports_value and not args.ports else None)
    return install_writes(ctx, args, manifest, plan, report, destination, data_root, program, model, ports_value, integration, reprise,
                          interrupted=interrupted)


def refuse_existing(ctx: Context, args: argparse.Namespace, destination: Path, data_root: Path, *, reprise: bool,
                    interrupted: dict[str, Any] | None = None) -> None:
    """Jamais de remplacement : une installation désignée ou un profil existant arrêtent l'installation, sauf le profil créé
    par une installation interrompue sans nettoyage (`interrupted`), qui sera retiré avant la copie."""
    pointer = read_pointer(destination)
    if pointer and pointer.get("current"):
        raise InstallError(f"Un atelier est déjà installé dans {destination} (version {pointer['current']['kit_id']}) : pour "
                           f"installer cette version à côté, « {installer_command(ctx.kit, 'update', '--destination', str(destination))} ». "
                           "Rien n'a été installé.", EXIT_REFUSED)
    if interrupted and str(data_root / "profile.yaml") in interrupted.get("created", {}):
        return
    if (data_root / "profile.yaml").exists() and not reprise:
        raise InstallError(kept_data_refusal(ctx, args, data_root), EXIT_REFUSED)


def kept_data_refusal(ctx: Context, args: argparse.Namespace, data_root: Path) -> str:
    """Racine des données déjà munie d'un profil, sans version courante dans la destination : la suite possible selon que
    ces données sont employées par une autre installation, reprenables (une sauvegarde existe) ou ni l'un ni l'autre."""
    other = other_data_root(ctx, args)
    user = data_user(ctx, data_root)
    if user:
        update = installer_command(ctx.kit, "update", "--destination", str(user[0]))
        return (f"La racine des données {data_root} est celle de l'installation {user[0]} (version {user[1]}) : pour y installer ce "
                f"kit, « {update} » ; pour une installation séparée, une autre racine des données : « {other} ». Rien n'a été installé.")
    backup = latest_backup(data_root)
    if backup is None:
        return (f"Données conservées dans {data_root} (profile.yaml), sans aucune sauvegarde dans {data_root / 'backups'} : elles ne sont "
                "jamais remplacées, et leur reprise sans sauvegarde n'est pas prise en charge. Pour installer l'atelier, choisir une "
                f"autre racine des données : « {other} » ; les données restent dans {data_root}. Rien n'a été installé.")
    reprise = install_suggestion(ctx, args, add=["--reprendre-donnees"])  # mêmes emplacements que la commande refusée
    return (f"Données conservées dans {data_root} (profile.yaml), qu'aucune version installée n'emploie : elles ne sont jamais "
            f"remplacées. Pour les reprendre (dernière sauvegarde : {backup}, {backup_date(backup)}) : « {reprise} » ; pour une "
            f"installation neuve, une autre racine des données : « {other} ». Rien n'a été installé.")


def reprise_checks(ctx: Context, args: argparse.Namespace, data_root: Path) -> Path:
    """Reprise de données conservées : profil présent, racine employée par aucune version désignée, et sauvegarde existante
    (une reprise sans aucune sauvegarde n'est pas prise en charge)."""
    if not (data_root / "profile.yaml").is_file():
        raise InstallError(f"Aucun profil à reprendre dans {data_root} (profile.yaml absent) : installer sans --reprendre-donnees.", EXIT_REFUSED)
    user = data_user(ctx, data_root)
    if user:
        update = installer_command(ctx.kit, "update", "--destination", str(user[0]))
        raise InstallError(f"La racine des données {data_root} est employée par l'installation {user[0]} (version {user[1]}) : pour y "
                           f"installer ce kit, « {update} », au lieu de la reprendre ; rien n'a été installé.", EXIT_REFUSED)
    backup = latest_backup(data_root)
    if backup is None:
        raise InstallError(f"Reprise refusée : aucune sauvegarde dans {data_root / 'backups'}. La reprise de données sans sauvegarde "
                           "n'est pas prise en charge : aucune version installée ne peut les sauvegarder avant une éventuelle évolution "
                           f"de leur format. Les données restent dans {data_root}. Pour installer l'atelier, choisir une autre racine "
                           f"des données : « {other_data_root(ctx, args)} ». Rien n'a été installé.", EXIT_REFUSED)
    return backup


def interrupted_install(ctx: Context, data_root: Path, destination: Path, *, reprise: bool = False,
                        args: argparse.Namespace | None = None) -> dict[str, Any] | None:
    """Installation ou reprise interrompue sans nettoyage (arrêt brutal : SIGKILL, coupure) que la même commande reprend
    exactement : marqueur de cette destination et du même genre que la commande, écrit par une exécution qui n'a pas atteint
    la bascule, version jamais désignée, racine des données employée par aucune version désignée, profils créés intacts
    (empreintes du marqueur) et dossier de version sans donnée d'exécution. None sinon.

    Refus avant écriture (code 3), qui nomme le marqueur : marqueur périmé (son exécution a atteint la bascule : la version a
    pu servir, ses profils sont ceux de l'utilisateur), ou marqueur d'une installation neuve pour une reprise (il compte
    profile.yaml parmi ce qu'elle a créé, qu'une reprise ne retire jamais)."""
    path = data_root / INSTALL_MARKER
    if path.is_symlink() or not path.is_file():
        return None
    try:
        marker = read_json(path)
    except (OSError, ValueError):
        return None
    created = marker.get("created")
    program = Path(str(marker.get("program") or ""))
    if (marker.get("format") != MARKER_FORMAT or not isinstance(marker.get("destination"), str)
            or not same_path(marker["destination"], destination) or not isinstance(created, dict)
            or not same_path(program.parent, destination) or not KIT_FOLDER.fullmatch(program.name) or marker.get("kind") not in MARKER_KINDS
            or not isinstance(marker.get("run"), str) or not marker["run"]):
        return None
    pointer = safe_pointer(destination) or {}
    if any(entry and os.path.realpath(entry["program"]) == os.path.realpath(program) for entry in (pointer.get("current"), pointer.get("previous"))):
        return None
    stale = stale_marker(marker, pointer, destination)
    if stale:
        raise InstallError(f"{path} est périmé : {stale}. Ce marqueur ne désigne rien à retirer : profils et données sont laissés intacts. "
                           f"Le supprimer (« rm -- {shlex.quote(str(path))} »), puis relancer la commande ; rien n'a été installé.",
                           EXIT_REFUSED)
    if reprise and (marker["kind"] != "reprise" or str(data_root / "profile.yaml") in created):
        command = install_suggestion(ctx, args, add=[], drop_flags=("--reprendre-donnees",)) if args else (
            f"<dossier du kit>/{quoted(INSTALLER_NAME, 'install', '--destination', str(destination), '--data-root', str(data_root))}")
        raise InstallError(f"{path} signale une installation neuve interrompue le {fr_utc(marker.get('started_utc')) or 'date inconnue'} "
                           f"(version {marker.get('kit_id')}), qui a créé profile.yaml : une reprise ne retire jamais ce profil. Pour "
                           f"reprendre cette installation interrompue, relancer sa commande, sans --reprendre-donnees : « {command} » ; "
                           "profils et données sont laissés intacts ; rien n'a été installé.", EXIT_REFUSED)
    if marker["kind"] != ("reprise" if reprise else "install") or data_in_use(ctx, data_root):
        return None
    for name, digest in created.items():
        profile = Path(name)
        if profile.parent != data_root or profile.is_symlink():
            return None
        if profile.exists() and (not profile.is_file() or file_sha256(profile) != digest):
            return None
    if program.is_symlink() or any((program / item).exists() or (program / item).is_symlink() for item in RUNTIME_DATA):
        return None
    return marker


def stale_marker(marker: dict[str, Any], pointer: dict[str, Any], destination: Path) -> str | None:
    """Raison pour laquelle l'exécution qui a écrit ce marqueur a atteint la bascule, ou None. L'historique du pointeur fait foi
    (événement portant son `run`) ; à défaut (pointeur supprimé ou recréé), le drapeau `bascule`, écrit juste avant le
    rename(2) du pointeur, suffit : la version a pu être activée et servir."""
    noun = "la reprise" if marker.get("kind") == "reprise" else "l'installation"
    author = f"{noun} qui l'a écrit (version {marker.get('kit_id')}, commencée le {fr_utc(marker.get('started_utc')) or 'date inconnue'})"
    for event in pointer.get("history") or []:
        if isinstance(event, dict) and event.get("run") == marker["run"]:
            return (f"{author} a activé cette version le {fr_utc(event.get('at_utc')) or 'date inconnue'} (historique de "
                    f"{destination / POINTER}), puis s'est arrêtée avant de le retirer")
    if marker.get("bascule"):
        return f"{author} s'est arrêtée au moment d'activer cette version, qui a pu servir depuis"
    return None


def interrupted_leftovers(marker: dict[str, Any]) -> tuple[list[str], str | None]:
    """Ce qu'une exécution interrompue a laissé et que sa reprise retire : chemins (profils qu'elle a créés, puis dossier de
    version), et leur description accordée (« dossier de version … retiré », « profils … et dossier … retirés ») ; None
    s'il ne reste rien. Lu avant toute suppression."""
    profiles = [Path(name) for name in marker["created"] if Path(name).exists()]
    program = Path(marker["program"])
    parts = []
    if profiles:
        names = ", ".join(path.name for path in profiles)
        parts.append(f"profils qu'elle a créés ({names})" if len(profiles) > 1 else f"profil qu'elle a créé ({names})")
    if program.exists():
        parts.append(f"dossier de version {program}")
    paths = [str(path) for path in profiles] + ([str(program)] if program.exists() else [])
    if not parts:
        return paths, None
    return paths, " et ".join(parts) + (" retirés" if len(profiles) > 1 or len(parts) > 1 else " retiré")


def interrupted_text(marker: dict[str, Any]) -> str:
    _, removed = interrupted_leftovers(marker)
    kind = "Reprise interrompue" if marker.get("kind") == "reprise" else "Installation interrompue"
    return (f"{kind} le {fr_utc(marker.get('started_utc')) or 'date inconnue'} (version {marker.get('kit_id')}), jamais activée : "
            + (f"{removed} avant la copie" if removed else "rien à retirer"))


def remove_marker(data_root: Path) -> None:
    """Retrait durable du marqueur : sans fsync du dossier des données, une coupure peut le faire réapparaître."""
    try:
        (data_root / INSTALL_MARKER).unlink()
    except FileNotFoundError:
        return
    fsync_directory(data_root)


def cleanup_interrupted(ctx: Context, report: Report, data_root: Path, destination: Path, marker: dict[str, Any]) -> None:
    """Retrait de ce qu'une installation interrompue a créé (marqueur revalidé sous le verrou) : ses profils, jamais
    désignés, et son dossier de version, supprimé sans suivre les liens."""
    program = Path(marker["program"])
    if program.exists() and not shutil.rmtree.avoids_symlink_attacks:
        raise InstallError("Suppression sûre impossible sur ce système (rmtree sans protection contre les liens) ; rien n'a été installé.",
                           EXIT_REFUSED)
    # Description et chemins établis avant les suppressions : la trace dit ce qui a été retiré.
    paths, removed = interrupted_leftovers(marker)
    for name in marker["created"]:
        Path(name).unlink(missing_ok=True)
    if program.exists():
        shutil.rmtree(program)
    remove_marker(data_root)
    report.data["interrupted_removed"] = paths
    when = f"commencée le {fr_utc(marker.get('started_utc')) or 'date inconnue'}, jamais activée"
    report.step("interrompue", "ok", f"{removed} ({when})" if removed else f"marqueur retiré, rien d'autre à retirer ({when})")


def removal_note(report: Report, profiles_removed: bool) -> str:
    """Suite d'un échec avant la bascule (code 5) : ce qui a été retiré, rien de désigné, rapport conservé."""
    parts = (["programme copié"] if report.data.get("new_program_removed") else []) + (["profils créés"] if profiles_removed else [])
    where = f" ; rapport : {report.path}" if report.path else ""
    if not parts:
        return f"Rapport : {report.path}." if report.path else ""
    removed = " et ".join(parts) + (" retirés" if len(parts) > 1 or not report.data.get("new_program_removed") else " retiré")
    return f"État laissé : {removed}, rien n'a été désigné{where} ; relancer la même commande après correction."


def install_writes(ctx: Context, args: argparse.Namespace, manifest: dict[str, Any], plan: Plan, report: Report, destination: Path,
                   data_root: Path, program: Path, model: str, ports_value: str | None, integration: dict[str, Any], reprise: bool,
                   *, interrupted: dict[str, Any] | None = None) -> int:
    created: list[str] = []
    data_created = not data_root.exists()
    bin_existed = bool(integration.get("user_command")) and Path(integration["user_command"]).parent.is_dir()
    marker = {"format": MARKER_FORMAT, "kind": "reprise" if reprise else "install", "run": os.urandom(16).hex(),
              "kit_id": manifest["kit_id"], "destination": str(destination), "program": str(program),
              "started_utc": ctx.clock().isoformat(), "report": None, "created": {}}

    def remember(paths: list[str]) -> None:
        """Profils créés par cette exécution, consignés au marqueur pour une reprise après un arrêt brutal."""
        marker["created"].update({path: file_sha256(path) for path in paths})
        write_json_atomic(data_root / INSTALL_MARKER, marker)

    with installer_lock(destination):
        pointer = read_pointer(destination)
        if pointer and pointer.get("current"):
            raise InstallError(f"Un atelier a été installé dans {destination} pendant la confirmation : relancer la commande ; rien n'a été "
                               "installé.", EXIT_REFUSED)
        if interrupted and interrupted_install(ctx, data_root, destination, reprise=reprise, args=args) != interrupted:
            raise InstallError("L'installation interrompue a changé pendant la confirmation : relancer la commande ; rien n'a été installé.",
                               EXIT_REFUSED)
        try:
            make_user_dir(data_root)
            report.path = data_root / f"{'reprise' if reprise else 'install'}-{stamp(ctx.clock())}.json"
            marker["report"] = str(report.path)
            if interrupted:
                cleanup_interrupted(ctx, report, data_root, destination, interrupted)
            remember([])
            prepare_program(ctx, plan, report, manifest, program)
            plan.begin("profil")
            profiles: dict[str, str] = {}
            if reprise:
                profile = str(data_root / "profile.yaml")
                info = profile_info(ctx, program, Path(profile))
                model = str(info.get("source_model") or info.get("model") or "")
                if model not in (manifest.get("model_profiles") or {}):
                    raise InstallError(f"Le profil repris emploie le modèle {model}, que ce kit ne livre pas ({', '.join(ordered_models(manifest))}) : "
                                       "employer un kit qui le livre.")
                profiles[model] = profile
                report.step("profil", "ok", f"{profile} repris ({model})")
            else:
                # Modèle toujours explicite : le profil principal ne dépend pas du défaut de rag.sh.
                arguments = ["--target", str(data_root), "--model", model]
                arguments += ["--qdrant-storage", str(args.qdrant_storage)] if args.qdrant_storage else []
                arguments += ["--ports", ports_value] if ports_value else []
                initialized = rag(ctx, program, "init-profile", *arguments)
                if initialized.get("status") != "created":
                    raise InstallError(f"Profil non créé : {initialized.get('message')}")
                profiles[model] = initialized["profile"]
                created.append(initialized["profile"])
                remember(created)
                report.step("profil", "ok", f"{initialized['profile']} ({model})")
            others = [name for name in manifest.get("model_profiles") or {} if name != model]
            before = {str(data_root / f"profile-{model_slug(name)}.yaml") for name in others if (data_root / f"profile-{model_slug(name)}.yaml").exists()}
            made = derive_profiles(ctx, report, python=venv_python(program), scripts=program, program=program, like=profiles[model],
                                   data_root=data_root, models=others)
            created += [path for path in made.values() if path not in before]
            remember(created)
            profiles.update(made)
            plan.begin("doctor")
            doctor_gate(ctx, report, program, profiles[model])
            plan.begin("bascule")
            entry = version_entry(manifest, program, data_root, dict(profiles), model, installed_utc=ctx.clock().isoformat())
            # Drapeau écrit (fsync) avant le rename(2) du pointeur : après un arrêt brutal entre la bascule et le retrait du
            # marqueur, celui-ci n'est jamais pris pour une installation jamais activée (interrupted_install).
            marker["bascule"] = True
            write_json_atomic(data_root / INSTALL_MARKER, marker)
            new = switch(destination, read_pointer(destination), entry, None,
                         {"event": "reprise" if reprise else "install", "kit_id": manifest["kit_id"], "at_utc": ctx.clock().isoformat(),
                          "report": str(report.path), "run": marker["run"]}, integration=integration, warn=ctx.warn)
            remove_marker(data_root)
            report.step("bascule", "ok", f"{destination / POINTER} et lanceur {destination / LAUNCHER}")
            if new.get("menu"):
                report.step("integration", "ok", f"entrée de menu {new.get('menu_entry')}"
                            + (f", commande {new['user_command']}" if new.get("user_command") else ", sans commande atelier"))
            registry_record(ctx, destination)
            if not args.no_start:
                start_and_check(ctx, plan, report, destination, program, profiles[model], browser=not args.no_browser)
            report.data.update(status="reprised" if reprise else "installed", program=str(program), profiles=profiles)
            pointer = read_pointer(destination) or new
            note = session_note(ctx, new, destination, bin_existed)
            rows = usage_rows(pointer, destination, pointer["current"])
            if not integration_enabled(pointer):
                rows.append((END_LABELS["update"], f"« <dossier du kit suivant>/{quoted(INSTALLER_NAME, 'update', '--destination', str(destination))} » "
                                                   "(installation non inscrite au registre : --sans-menu)"))
            end_block(ctx, f"{'Reprise' if reprise else 'Installation'} terminée : version {manifest['kit_id']}.",
                      rows + [(END_LABELS["report"], str(report.path))], footer=f"Commande {USER_COMMAND} : {note}." if note else None)
            return EXIT_OK
        except BaseException as error:
            report.data.update(status="failed", error=str(error))
            if remove_new_program(destination, program, report):
                # Cette version n'est pas désignée : les profils créés par cette exécution sont retirés avec elle.
                for path in created:
                    Path(path).unlink(missing_ok=True)
                remove_marker(data_root)
                if isinstance(error, KeyboardInterrupt):
                    report.path = None
                    if data_created:
                        try:
                            data_root.rmdir()
                        except OSError:
                            pass
                    raise Interrupted(f"{'Reprise' if reprise else 'Installation'} interrompue : copie partielle retirée, données "
                                      "inchangées ; relancer la même commande.") from None
                note = removal_note(report, bool(created))
                raise InstallError(f"{as_partial(error)}" + (f"\n{note}" if note else ""), EXIT_PARTIAL) from error
            remove_marker(data_root)
            if isinstance(error, KeyboardInterrupt):
                raise Interrupted(f"Installation interrompue après l'activation de la version {manifest['kit_id']} : "
                                  f"« {launcher_command(read_pointer(destination), destination, 'diagnostic')} » détaille son état.") from None
            state = failure_message(destination, program, None)
            raise InstallError(f"{as_partial(error)}" + (f"\n{state}" if state else ""), EXIT_PARTIAL) from error
        finally:
            report.save()


# --- Mise à jour --------------------------------------------------------------------------------------------------------

def backup_estimate(ctx: Context, program: Path, profile: Path, destination: Path, needed: int) -> dict[str, Any] | None:
    """Taille estimée de la sauvegarde de mise à jour (données et index), comparée à la place du volume des sauvegardes."""
    if not venv_python(program).exists():
        return None
    locations = profile_info(ctx, program, profile)["locations"]
    data_dir, storage = Path(locations["app.data_dir"]), Path(locations["qdrant.storage"])
    backups = Path(locations["runtime.backups_dir"])
    size = ctx.probe.tree_bytes(data_dir) + (0 if inside(storage, data_dir) else ctx.probe.tree_bytes(storage))
    shared = ctx.probe.device(backups) == ctx.probe.device(destination)
    required = size + DATA_MIN_FREE_BYTES + (needed if shared else 0)
    free = ctx.probe.free_bytes(backups)
    return {"size": size, "required": required, "free": free, "backups": str(backups), "shared": shared, "data_dir": str(data_dir),
            "storage": str(storage)}


def no_designated_version_text(ctx: Context, destination: Path, pointer: dict[str, Any] | None) -> str:
    """Mise à jour sans version courante : commandes exactes d'une reprise des données conservées et d'une installation neuve
    depuis ce kit ; la racine des données est celle de la version précédente si le pointeur en garde une."""
    command = installer_command(ctx.kit, "install", "--destination", str(destination))
    previous = (pointer or {}).get("previous")
    reprise = (installer_command(ctx.kit, "install", "--destination", str(destination), "--data-root", previous["data_root"],
                                 "--reprendre-donnees") if previous else f"{command} --data-root <données conservées> --reprendre-donnees")
    return (f"Aucune version installée n'est désignée dans {destination / POINTER} : pour reprendre des données conservées, "
            f"« {reprise} » ; pour une installation neuve, « {command} » ; rien n'a été installé.")


def update(ctx: Context, args: argparse.Namespace) -> int:
    manifest = read_manifest(ctx.kit)
    destination = resolve_destination(ctx, args)
    menu = Path(args.menu).absolute() if getattr(args, "menu", None) else None
    refuse_if_locked(destination)
    pointer = read_pointer(destination)
    if not pointer or not pointer.get("current"):
        raise InstallError(no_designated_version_text(ctx, destination, pointer), EXIT_REFUSED)
    current = pointer["current"]
    if current["kit_id"] == manifest["kit_id"]:
        raise InstallError(f"La version {manifest['kit_id']} est déjà la version courante : rien à mettre à jour.", EXIT_REFUSED)
    refuse_previous_version(manifest, destination, pointer)
    available = manifest.get("model_profiles") or {}
    model = getattr(args, "model", None) or current.get("model")
    if model not in available:
        if getattr(args, "model", None):
            raise InstallError(f"Modèle {model} absent de ce kit ({', '.join(ordered_models(manifest))}) ; rien n'a été installé.", EXIT_REFUSED)
        default = str(manifest.get("default_model"))
        # update --model vaut pour toute installation ; l'action « modele » n'existe que dans le lanceur des installations munies
        # de l'intégration au bureau (pointeur avec la clé menu), pas dans celui de l'installateur de 78ec95c.
        first = launcher_command(pointer, destination, "modele", default) if "menu" in pointer else None
        raise InstallError(f"Le modèle du profil en place ({current.get('model')}) n'est pas livré par ce kit ; rien n'a été installé. "
                           "Pour adopter le modèle livré pendant la mise à jour : "
                           f"« {installer_command(ctx.kit, 'update', '--destination', str(destination), '--model', default)} »"
                           + (f" ; ou d'abord dans la version en place : « {first} », puis relancer la mise à jour" if first else "")
                           + f" ; ou employer un kit qui livre {current.get('model')} (fabrication par défaut : --models 4b,2b).", EXIT_REFUSED)
    previous_program, profile = Path(current["program"]), current["profile"]
    data_root = Path(current["data_root"])
    program = destination / manifest["kit_id"]
    start = not args.no_start
    report = Report(ctx, "update", kit=str(ctx.kit), kit_id=manifest["kit_id"], destination=str(destination), data_root=str(data_root),
                    previous=current["kit_id"])
    plan = Plan(ctx, report, UPDATE_STEPS + (START_STEPS if start else []))
    plan.begin("precontroles")
    command = Path(pointer["user_command"]) if integration_enabled(pointer) and pointer.get("user_command") else None
    facts = precheck(ctx, manifest, destination, data_root, program=previous_program, menu_entry=(menu / DESKTOP) if menu else None,
                     menu_explicit=True, data_checks=False, args=args, user_command=command,
                     command_fix=f"ou retirer l'intégration au bureau (« {installer_command(previous_program, 'repair', '--sans-menu')} »)")
    report.step("precontroles", "ok", ", ".join(facts["passed"]))
    plan.begin("kit")
    # Fichiers du nouveau kit exécutés ou lus par la dérivation contrôlée (script, imports possibles, profils livrés) : vérifiés
    # avant elle, comme l'interpréteur et l'installateur le sont avant leur lancement.
    verify_targeted(ctx, manifest, report, pre_copy=True)
    # Profils des modèles nouveaux : dérivation contrôlée avant toute sauvegarde ni copie, par le code et les profils livrés
    # du nouveau kit, avec l'environnement de la version en place.
    missing = [name for name in available if name not in (current.get("profiles") or {})]
    try:
        derive_profiles(ctx, None, python=venv_python(previous_program), scripts=ctx.kit, program=ctx.kit, like=profile,
                        data_root=data_root, models=missing, check=True)
    except InstallError as error:
        raise InstallError(f"{error} ; rien n'a été installé.", EXIT_REFUSED) from error
    report.step("profil", "ok", f"dérivation contrôlée : {', '.join(missing)}" if missing else "aucun nouveau modèle dans ce kit")
    plan.begin("systeme")
    system_check(ctx, manifest, report)
    estimate = backup_estimate(ctx, previous_program, Path(profile), destination, int(manifest["requirements"]["install_bytes_min"]))
    if estimate and estimate["free"] < estimate["required"]:
        raise InstallError(f"Place insuffisante pour la sauvegarde de mise à jour : {fr_gib(estimate['size'])} estimés (données "
                           f"{estimate['data_dir']} et index {estimate['storage']}), plus la réserve de {fr_gib(DATA_MIN_FREE_BYTES)}"
                           + (" et le programme, sur le même volume" if estimate["shared"] else "")
                           + f" ; {fr_gib(estimate['free'])} libres sous {estimate['backups']}. Libérer de la place sur ce volume, par "
                           f"exemple en retirant d'anciennes sauvegardes (« {installer_command(previous_program, 'status')} » les liste) ; "
                           "rien n'a été installé.", EXIT_REFUSED)
    lines = [f"Mise à jour : {current['kit_id']} → {manifest['kit_id']} (dans {destination})",
             f"Modèle principal : {model}" + (f" (changé : {current.get('model')} auparavant)" if model != current.get("model") else " (conservé)"),
             f"Données : {data_root} (conservées ; sauvegardées et vérifiées avant la copie)",
             f"Place : {fr_gib(facts['free'])} libres ; {fr_gib(facts['needed'])} nécessaires au programme"
             + (f" ; sauvegarde estimée à {fr_gib(estimate['size'])}" if estimate else ""),
             "Version en place : arrêtée pendant la mise à jour, conservée ensuite pour le retour arrière",
             "Démarrage : " + ("après la mise à jour" if start else "non (--no-start)")]
    repair_menu = desktop_hint(pointer, program, menu)
    if repair_menu:
        lines.append(f"Bureau : {repair_menu}")
    confirm(ctx, args, "Récapitulatif de la mise à jour", lines)
    with installer_lock(destination):
        if read_pointer(destination) != pointer:
            raise InstallError("L'installation a changé pendant la confirmation : relancer la commande ; rien n'a été installé.", EXIT_REFUSED)
        report.path = data_root / f"update-{stamp(ctx.clock())}.json"
        stopped = copying = started_here = False
        active_model, source = None, profile
        new_profiles: list[str] = []
        try:
            plan.begin("sauvegarde")
            # Sauvegarde vérifiée des données avant toute copie : elle exige l'instance démarrée (up la retrouve), avec le
            # profil de l'instance déjà en marche s'il y en a une (par exemple le 2B).
            active_model, active_profile = running_profile(ctx, previous_program, current.get("profiles") or {current["model"]: profile},
                                                           pointer, destination)
            source = active_profile or profile
            if active_model:
                report.step("instance", "ok", f"instance en marche avec {source} (modèle {active_model}) : sauvegarde par cette instance")
            started = rag(ctx, previous_program, "up", "--profile", source)
            if started.get("status") != "running":
                raise InstallError(f"La version en place ne démarre pas ({started.get('message')}) ; sauvegarde impossible, rien n'a été installé.")
            started_here = active_model is None
            backup = rag(ctx, previous_program, "backup", "--profile", source, timeout=7200)
            if not backup.get("path"):
                raise InstallError(f"Sauvegarde refusée : {backup.get('message')} Rien n'a été installé.")
            verified = rag(ctx, previous_program, "verify", "--profile", source, "--path", str(backup["path"]), timeout=7200)
            if verified.get("state") != "verified":
                raise InstallError(f"Sauvegarde {backup['path']} non vérifiée : {verified.get('message')} Rien n'a été installé.")
            stopped_state = rag(ctx, previous_program, "down", "--profile", source)
            if stopped_state.get("status") not in {"stopped", "failed"}:
                raise InstallError(f"Arrêt de la version en place non confirmé (état {stopped_state.get('status')}) ; rien n'a été installé.")
            stopped = True
            report.data["backup"] = str(backup["path"])
            report.step("sauvegarde", "ok", f"{backup['path']} vérifiée ; version {current['kit_id']} arrêtée")
            copying = True
            prepare_program(ctx, plan, report, manifest, program)
            plan.begin("profil")
            profiles = {name: path for name, path in (current.get("profiles") or {}).items() if name in available}
            before = {path for path in (data_root / f"profile-{model_slug(name)}.yaml" for name in missing) if path.exists()}
            report.step("profil", "ok", f"{profile} repris")
            made = derive_profiles(ctx, report, python=venv_python(program), scripts=program, program=program, like=profile,
                                   data_root=data_root, models=missing)
            new_profiles = [path for path in made.values() if Path(path) not in before]
            profiles.update(made)
            principal = profiles[model]
            plan.begin("doctor")
            doctor_gate(ctx, report, program, principal)
            # Dernier contrôle avant la bascule : aucune instance ne doit avoir été relancée sur ces données depuis l'arrêt
            # (ses écritures seraient postérieures à la sauvegarde, et up de la nouvelle version la reprendrait).
            late = rag(ctx, program, "status", "--profile", principal)
            if late.get("status") in RUNNING:
                relaunched = (late.get("supervisor") or {}).get("executable") or "exécutable inconnu"
                raise InstallError(f"Une instance a été relancée pendant la mise à jour ({relaunched}) : ses écritures sont postérieures à la "
                                   f"sauvegarde {backup['path']}. Rien n'a été basculé ; l'arrêter (« "
                                   f"{launcher_command(pointer, destination, 'arreter')} »), puis relancer la mise à jour.")
            plan.begin("bascule")
            entry = version_entry(manifest, program, data_root, profiles, model, installed_utc=ctx.clock().isoformat(),
                                  backup=str(backup["path"]))
            new = switch(destination, pointer, entry, current, {"event": "update", "kit_id": manifest["kit_id"], "from": current["kit_id"],
                                                                "backup": str(backup["path"]), "at_utc": ctx.clock().isoformat(),
                                                                "report": str(report.path)}, menu=menu, warn=ctx.warn)
            report.step("bascule", "ok", f"{current['kit_id']} → {manifest['kit_id']}")
            registry_record(ctx, destination)
            principal_model_note(report, model, manifest.get("default_model"), new, destination)
            if start:
                start_and_check(ctx, plan, report, destination, program, principal, browser=not args.no_browser)
            report.data.update(status="updated", program=str(program))
            size = ctx.probe.tree_bytes(previous_program)
            rows = usage_rows(new, destination, entry)
            if repair_menu:
                rows.append((END_LABELS["desktop"], repair_menu))
            rows += [(f"{END_LABELS['rollback']} {current['kit_id']}", installer_command(program, "rollback")),
                     (f"{END_LABELS['remove']} {current['kit_id']} ({fr_gib(size)})",
                      f"{installer_command(program, 'uninstall', '--kit-id', current['kit_id'])} ; le retour arrière ne sera plus possible"),
                     (END_LABELS["report"], str(report.path))]
            end_block(ctx, f"Mise à jour terminée : version {manifest['kit_id']} ; version {current['kit_id']} conservée pour le retour arrière, "
                           f"sauvegarde {backup['path']}.", rows)
            return EXIT_OK
        except BaseException as error:
            report.data.update(status="failed", error=str(error))
            if remove_new_program(destination, program, report):
                for path in new_profiles:
                    Path(path).unlink(missing_ok=True)
            switched = designated(destination) is not None and same_path((designated(destination) or {})["program"], program)
            if isinstance(error, KeyboardInterrupt):
                if switched:
                    raise Interrupted(f"Mise à jour interrompue après l'activation de la version {manifest['kit_id']} : "
                                      f"« {installer_command(program, 'rollback')} » revient à {current['kit_id']}.") from None
                if stopped:
                    raise Interrupted(f"Mise à jour interrompue : copie partielle retirée ; la version {current['kit_id']} reste la version "
                                      f"courante, arrêtée (« {launcher_command(pointer, destination, 'ouvrir')} » la relance) ; sauvegarde "
                                      f"conservée : {report.data.get('backup')}.") from None
                running = (" ; l'instance démarrée pour la sauvegarde peut être en marche : "
                           f"« {launcher_command(pointer, destination, 'arreter')} » l'arrête") if started_here else ""
                raise Interrupted(f"Mise à jour interrompue avant la copie : la version {current['kit_id']} reste la version courante"
                                  f"{running} ; relancer la même commande.") from None
            # La cause d'abord (message de l'exception, affiché par main), puis l'état laissé.
            if stopped or switched:
                state = failure_message(destination, program, current)
            elif designated(destination) is not None:
                state = instance_left(ctx, previous_program, source, current, started_here=started_here,
                                      running_before=active_model is not None, pointer=pointer, destination=destination)
            else:
                state = None
            lines = [line for line in (state, f"Sauvegarde conservée : {report.data['backup']}." if report.data.get("backup") else None) if line]
            cause = str(error) if isinstance(error, (InstallError, linux_kit.KitError)) else f"{type(error).__name__} : {error}"
            code = EXIT_PARTIAL if copying else getattr(error, "code", EXIT_ERROR)
            raise InstallError("\n".join([cause, *lines]), code) from error
        finally:
            report.save()


def desktop_hint(pointer: dict[str, Any], program: Path, menu: Path | None) -> str | None:
    """Installation antérieure à l'intégration au bureau (installateur de 78ec95c : pointeur sans clé `menu`) : la mise à
    jour ne crée ni entrée ni commande sans le dire, et donne la commande qui les ajoute."""
    if "menu" in pointer or menu is not None:
        return None
    return (f"aucune entrée de menu ni commande {USER_COMMAND} (installation antérieure à l'intégration au bureau) ; "
            f"« {installer_command(program, 'repair', '--menu')} » les ajoute après la mise à jour")


def principal_model_note(report: Report, model: str, default: str | None, pointer: dict[str, Any], destination: Path) -> None:
    """Le profil principal d'une installation existante n'est jamais converti (W045) : un choix, pas une migration. Les
    commandes citées sont celles du lanceur réellement disponible (`atelier`, sinon son chemin complet)."""
    switch_commands = ([launcher_command(pointer, destination, "arreter"), launcher_command(pointer, destination, "ouvrir", "--modele", default)]
                       if default and model != default else None)
    persistent = launcher_command(pointer, destination, "modele", default) if switch_commands and default else None
    report.data["principal_model"] = {"model": model, "kit_default": default, "converted": False, "switch": switch_commands,
                                      "persistent": persistent}
    if switch_commands:
        report.step("modele", "info", f"Profil principal conservé : {model}, choix de cette installation, non converti. Le modèle par "
                                      f"défaut de cette version est {default} ; pour l'adopter durablement : « {persistent} » ; pour une "
                                      f"seule ouverture : « {switch_commands[0]} », puis « {switch_commands[1]} ».")


# --- Retour arrière -----------------------------------------------------------------------------------------------------

def new_version_started(ctx: Context, entry: dict[str, Any]) -> bool:
    """La version a-t-elle démarré sur les données ? Pointeur, puis état de l'instance (exécutable du superviseur)."""
    if entry.get("started_on_data"):
        return True
    program = Path(entry["program"])
    state = rag(ctx, program, "status", "--profile", entry["profile"])
    if state.get("_returncode"):
        return True  # état illisible : la restauration, plus sûre, est retenue
    executable = (state.get("supervisor") or {}).get("executable")
    return isinstance(executable, str) and inside(Path(executable), program)


def rollback(ctx: Context, args: argparse.Namespace) -> int:
    destination = resolve_destination(ctx, args)
    refuse_if_locked(destination)
    pointer = read_pointer(destination)
    if not pointer:
        raise InstallError(f"Aucune installation dans {destination} : aucun retour arrière possible.", EXIT_REFUSED)
    current, previous = pointer.get("current"), pointer.get("previous")
    if not current:
        raise InstallError(f"Aucune version courante dans {destination} : un retour arrière part d'une version courante. "
                           f"{reinstall_hint(destination, pointer)} Rien n'a été modifié.", EXIT_REFUSED)
    if not previous:
        raise InstallError(f"Aucune version précédente n'est désignée : la version {current['kit_id']} est la seule installée ; retour "
                           "arrière impossible.", EXIT_REFUSED)
    if previous.get("rolled_back"):
        removal = installer_command(Path(current["program"]), "uninstall", "--kit-id", previous["kit_id"])
        raise InstallError(f"Retour arrière déjà effectué : la version précédente {previous['kit_id']} est celle qu'il a abandonnée ; "
                           "aucun second retour arrière n'est proposé. Pour passer à une autre version : retirer la version abandonnée "
                           f"(« {removal} »), puis « <dossier du kit de la version voulue>/"
                           f"{quoted(INSTALLER_NAME, 'update', '--destination', str(destination))} ».", EXIT_REFUSED)
    old_program, new_program = Path(previous["program"]), Path(current["program"])
    if not (old_program / "rag.sh").is_file():
        raise InstallError(f"Version précédente absente ({old_program}) : retour arrière impossible.", EXIT_REFUSED)
    data_root = Path(current["data_root"])
    restore = new_version_started(ctx, current)
    target = None
    if restore:
        backup = current.get("backup")
        if not backup:
            raise InstallError("La nouvelle version a démarré sur les données et aucune sauvegarde n'est associée à sa mise à jour : "
                               "restauration impossible, rien n'a été basculé.", EXIT_REFUSED)
        target = (Path(args.restore_target) if args.restore_target else data_root.with_name(f"{data_root.name}-retour-{stamp(ctx.clock())}")).absolute()
        problem = restore_target_problem(ctx, target, explicit=bool(args.restore_target), relative=bool(args.restore_target) and not
                                         Path(args.restore_target).is_absolute())
        if problem:
            raise InstallError(f"{problem} ; rien n'a été modifié.", EXIT_REFUSED)
        confirm(ctx, args, "Récapitulatif du retour arrière", [
            f"Version rétablie : {previous['kit_id']} (version abandonnée : {current['kit_id']}, qui a démarré sur les données)",
            f"Sauvegarde restaurée : {backup} ({backup_date(Path(backup))})",
            f"Nouvelle racine des données : {target}",
            f"Ancienne racine conservée : {data_root} ; elle garde les écritures postérieures à la sauvegarde, qui ne sont pas "
            "restaurées",
            f"Ports : ceux de la version abandonnée s'ils sont libres, sinon {', '.join(map(str, RESTORE_PORTS))} (à changer ensuite)"])
    report = Report(ctx, "rollback", destination=str(destination), current=current["kit_id"], previous=previous["kit_id"])
    report.path = data_root / f"rollback-{stamp(ctx.clock())}.json"
    with installer_lock(destination):
        if read_pointer(destination) != pointer:
            raise InstallError("L'installation a changé pendant la confirmation : relancer la commande ; rien n'a été modifié.", EXIT_REFUSED)
        phase = "avant"
        try:
            state = rag(ctx, new_program, "status", "--profile", current["profile"])
            if state.get("status") in RUNNING:
                down = rag(ctx, new_program, "down", "--profile", current["profile"])
                if down.get("status") not in {"stopped", "failed"}:
                    raise InstallError(f"Arrêt de la version {current['kit_id']} non confirmé ; rien n'a été basculé.")
                report.step("arret", "ok", current["kit_id"])
            phase = "arretee"
            # Entrée de retour : la sauvegarde de sa propre mise à jour ne vaut plus pour elle.
            restored_entry = {key: value for key, value in previous.items()
                              if key not in {"backup", "rolled_back", "restored_from", "started_on_data"}}
            restored_entry["started_on_data"] = False
            ports_used = None
            if restore:
                phase = "restauration"
                update_entry, ports_used = restore_previous(ctx, report, current, old_program, data_root, target, destination, new_program)  # type: ignore[arg-type]
                restored_entry.update(update_entry)
            else:
                # Rebascule simple, sans confirmation : l'installation visée est nommée avant d'agir.
                print(f"Retour arrière de {destination} : version {previous['kit_id']} rétablie, version {current['kit_id']} abandonnée ; "
                      "elle n'a jamais démarré sur les données : rien n'est restauré.", file=ctx.out, flush=True)
                report.step("donnees", "ok", f"la version {current['kit_id']} n'a jamais démarré sur les données : profils conservés")
            new = switch(destination, pointer, restored_entry, {**current, "rolled_back": True},
                         {"event": "rollback", "from": current["kit_id"], "to": previous["kit_id"], "at_utc": ctx.clock().isoformat(),
                          "report": str(report.path)}, warn=ctx.warn)
            phase = "basculee"
            report.step("bascule", "ok", f"{current['kit_id']} → {previous['kit_id']}")
            registry_record(ctx, destination)
            report.data["status"] = "rolled_back"
            open_command = f"« {launcher_command(new, destination, 'ouvrir')} »"
            if restore:
                rows = [(END_LABELS["active_data"], f"{restored_entry['data_root']} (restaurées depuis {current.get('backup')})"),
                        (END_LABELS["old_data"], f"{data_root} — elle contient les écritures de la version abandonnée depuis la "
                                                 "sauvegarde"),
                        (END_LABELS["ports"], ports_used or "inchangés"), (END_LABELS["open"], open_command),
                        (END_LABELS["report"], str(report.path))]
            else:
                rows = [(END_LABELS["data"], f"{data_root} (inchangées)"), (END_LABELS["open"], open_command),
                        (END_LABELS["report"], str(report.path))]
            end_block(ctx, f"Retour arrière terminé : version {previous['kit_id']} courante ; version {current['kit_id']} conservée, "
                           f"retirable par « {installer_command(old_program, 'uninstall')} ».", rows)
            return EXIT_OK
        except BaseException as error:
            report.data.update(status="failed", error=str(error))
            if isinstance(error, KeyboardInterrupt):
                messages = {"avant": INTERRUPTED["rollback"],
                            "arretee": f"Retour arrière interrompu : la version {current['kit_id']} reste courante, arrêtée ; relancer la "
                                       "même commande.",
                            "restauration": f"Retour arrière interrompu pendant la restauration : la version {current['kit_id']} reste "
                                            f"courante, arrêtée ; la racine partielle {target} peut être retirée ; relancer la commande.",
                            "basculee": f"Retour arrière interrompu après la bascule : la version {previous['kit_id']} est courante."}
                raise Interrupted(messages[phase]) from None
            if phase in {"restauration", "basculee"}:
                raise as_partial(error) from error
            raise
        finally:
            report.save()


def restore_target_problem(ctx: Context, target: Path, *, explicit: bool, relative: bool) -> str | None:
    """Racine de restauration, qui devient la racine active du pointeur : règles de la racine des données (chemin absolu, sans
    caractère de contrôle, accessible en écriture, volume ni volatil ni réseau). « cause — action », ou None."""
    name = f"--restore-target {target}" if explicit else f"racine de restauration {target}"
    action = "choisir une racine neuve sur un disque local" + (" (--restore-target)" if not explicit else "")
    if relative:
        return f"--restore-target : chemin absolu attendu ({target}) — indiquer un chemin absolu"
    if control_characters(str(target)):
        return f"{name!r} : caractère de contrôle refusé — choisir un chemin sans caractère de contrôle"
    if not writable_target(target):
        return f"{name} : dossier non accessible en écriture pour ce compte ({existing_ancestor(target)}) — {action}"
    filesystem = ctx.probe.filesystem(target)
    if filesystem["fstype"] in VOLATILE_FILESYSTEMS:
        return (f"{name} sur un volume non persistant ({filesystem['fstype']}) monté sur {filesystem['mount']} : les données restaurées "
                f"seraient perdues au redémarrage — {action}")
    if filesystem["fstype"] in REFUSED_FILESYSTEMS:
        return (f"{name} sur {filesystem['fstype']} ({filesystem['mount']}) : SQLite et les verrous de l'atelier exigent un disque local "
                f"— {action}")
    return None


def restore_previous(ctx: Context, report: Report, current: dict[str, Any], old_program: Path, data_root: Path, target: Path,
                     destination: Path, new_program: Path) -> tuple[dict[str, Any], str]:
    """Restauration de la sauvegarde de la mise à jour par l'ancienne version, dans une racine neuve ; ports de l'utilisateur
    repris s'ils sont libres ; profils des autres modèles régénérés sur les données restaurées."""
    backup = current["backup"]
    if inside(target, old_program) or inside(target, new_program) or inside(target, destination):
        raise InstallError(f"Racine de restauration {target} dans un dossier programme : choisir une racine de données neuve.", EXIT_REFUSED)
    original = profile_info(ctx, new_program, Path(current["profile"])) if venv_python(new_program).exists() else None
    restored = rag(ctx, old_program, "restore", "--path", backup, "--target", str(target), timeout=7200)
    if restored.get("state") != "restored_storage_verified":
        raise InstallError(f"Restauration refusée : {restored.get('message') or restored.get('error')} ; rien n'a été basculé.")
    profile = target / "restored-profile.yaml"
    report.step("restauration", "ok", f"{backup} restaurée dans {target} par la version {Path(old_program).name}")
    used = f"{RESTORE_PORTS[0]} (API), {RESTORE_PORTS[1]} (Qdrant), {RESTORE_PORTS[2]} (Ollama), ports de la restauration"
    if original:
        ports = original["ports"]
        adopted = profiles_tool(ctx, venv_python(old_program), old_program, "ports", "--profile", str(profile), "--ports",
                                f"{ports['app']},{ports['qdrant']},{ports['ollama']}", cwd=old_program)
        if adopted["status"] == "adopted":
            used = f"{ports['app']} (API), {ports['qdrant']} (Qdrant), {ports['ollama']} (Ollama), ceux de l'utilisateur"
            report.step("ports", "ok", f"ports de l'utilisateur repris ({ports['app']}, {ports['qdrant']}, {ports['ollama']})")
        else:
            used += f" ; ports de l'utilisateur occupés ({', '.join(adopted.get('busy') or [])})"
            report.step("ports", "orange", f"ports de l'utilisateur occupés ({', '.join(adopted.get('busy') or [])}) : la restauration garde "
                                            "8795, 6343 et 11445 ; les changer dans le profil restauré une fois libres")
        storage = original["locations"].get("qdrant.storage")
        report.step("stockage", "ok", f"stockage Qdrant restauré dans {target / 'qdrant'} ; l'ancien stockage {storage} garde les "
                                      "données de la version abandonnée et n'est pas réutilisé")
    else:
        report.step("ports", "orange", "profil de la version abandonnée illisible : ports de la restauration (8795, 6343, 11445) conservés")
    info = profile_info(ctx, old_program, profile)
    model = info["source_model"] or info["model"]
    old_manifest = read_json(old_program / linux_kit.MANIFEST)
    others = [name for name in old_manifest.get("model_profiles") or {} if name != model]
    profiles = {model: str(profile), **derive_profiles(ctx, report, python=venv_python(old_program), scripts=old_program,
                                                       program=old_program, like=str(profile), data_root=target, models=others)}
    report.data["restored"] = {"backup": backup, "target": str(target)}
    return {"profile": str(profile), "profiles": profiles, "data_root": str(target), "model": model, "restored_from": backup}, used


# --- Désinstallation ------------------------------------------------------------------------------------------------------

def versions_present(destination: Path) -> list[str]:
    return sorted(path.name for path in destination.iterdir() if path.is_dir() and not path.is_symlink()
                  and (path / linux_kit.MANIFEST).is_file()) if destination.is_dir() else []


def uninstall_targets(destination: Path, pointer: dict[str, Any] | None, args: argparse.Namespace) -> tuple[list[str], list[str]]:
    """Versions à retirer, dans l'ordre (non désignées, précédente, courante), et avertissements."""
    current, previous = (pointer or {}).get("current"), (pointer or {}).get("previous")
    present = versions_present(destination)
    designated_ids = {entry["kit_id"] for entry in (current, previous) if entry}
    warnings: list[str] = []
    if args.tout:
        targets = [kit_id for kit_id in present if kit_id not in designated_ids]
        targets += [entry["kit_id"] for entry in (previous, current) if entry and entry["kit_id"] not in targets]
        return targets, warnings
    if args.anciennes:
        return [kit_id for kit_id in present if kit_id not in designated_ids], warnings
    if args.kit_id:
        if current and args.kit_id == current["kit_id"] and previous:
            program = Path(current["program"])
            if previous.get("rolled_back"):
                raise InstallError(f"Retirer d'abord la version abandonnée {previous['kit_id']} (« {installer_command(program, 'uninstall')} »), "
                                   f"puis {current['kit_id']} ; rien n'a été supprimé.", EXIT_REFUSED)
            raise InstallError(f"Revenir d'abord à {previous['kit_id']} (« {installer_command(program, 'rollback')} »), puis retirer "
                               f"{current['kit_id']} ; rien n'a été supprimé.", EXIT_REFUSED)
        if previous and args.kit_id == previous["kit_id"] and not previous.get("rolled_back"):
            warnings.append(f"version précédente {previous['kit_id']} : le retour arrière ne sera plus possible")
        return [args.kit_id], warnings
    if previous:
        warnings.append(f"version {'abandonnée par le retour arrière' if previous.get('rolled_back') else 'précédente'} "
                        f"{previous['kit_id']}" + ("" if previous.get("rolled_back") else " : le retour arrière ne sera plus possible"))
        return [previous["kit_id"]], warnings
    if current:
        return [current["kit_id"]], warnings
    others = [kit_id for kit_id in present]
    raise InstallError(f"Aucune version désignée dans {destination}" + (f" ; versions présentes : {', '.join(others)} : les retirer avec "
                       "--anciennes ou --kit-id <version>" if others else " : rien à retirer") + ".", EXIT_REFUSED)


def processes_text(found: list[tuple[int, str]]) -> str:
    shown = " ; ".join(f"PID {pid} : {executable}" for pid, executable in found[:5])
    return shown + (f" ; et {len(found) - 5} autres" if len(found) > 5 else "")


def refuse_unreadable_instance(ctx: Context, destination: Path, pointer: dict[str, Any] | None, kit_id: str,
                               extra_profiles: list[str]) -> None:
    """Avant la confirmation d'un retrait (R3S-03) : une version dont aucun profil lisible ne permet de lire l'état de
    l'instance (profil désigné absent, version non désignée sans --profile) n'est retirée que si aucun processus du compte ne
    tourne depuis son dossier ; sinon refus, code 3, rien n'est retiré. Une instance dont l'état se lit est arrêtée par
    remove_version."""
    program = destination / kit_id
    if program.is_symlink() or not program.is_dir():
        return
    entries = [entry for entry in ((pointer or {}).get("current"), (pointer or {}).get("previous"))
               if entry and same_path(entry["program"], program)]
    profiles = sorted({path for entry in entries for path in entry.get("profiles", {}).values()} | set(extra_profiles))
    missing = [profile for profile in profiles if not Path(profile).is_file()]
    if profiles and not missing:
        return
    running = ctx.probe.program_processes(program)
    if not running:
        return
    if missing:
        cause = f"profil{'s' if len(missing) > 1 else ''} {', '.join(missing)} absent{'s' if len(missing) > 1 else ''}"
    else:
        cause = "version non désignée par le pointeur, dont aucun profil n'est connu de l'installation"
    raise InstallError(f"État de l'instance de {kit_id} illisible ({cause}) : processus de ce programme en marche "
                       f"({processes_text(running)}) — les arrêter, puis relancer ; rien n'a été supprimé.", EXIT_REFUSED)


def remove_version(ctx: Context, destination: Path, kit_id: str, report: Report, extra_profiles: list[str], kept: dict[str, set[str]]) -> None:
    """Gardes, arrêt de l'instance de cette version, pointeur mis à jour d'abord, puis suppression protégée contre les liens."""
    program = destination / kit_id
    known = safe_pointer(destination) or {}
    designations = {key: known.get(key) for key in ("current", "previous")}
    gone = [entry for entry in designations.values() if entry and same_path(entry["program"], program)]
    if gone and not program.exists() and not program.is_symlink() and KIT_FOLDER.fullmatch(kit_id):
        # Dossier d'une version désignée disparu (supprimé à la main, volume perdu) : rien à supprimer ni à arrêter par lui ;
        # le pointeur est mis à jour, pour que la reprise des données (dépannage, section 10.4) reste possible.
        for entry in gone:
            kept["data"].add(entry["data_root"])
            kept["backups"].add(str(Path(entry["data_root"]) / "backups"))
        left = {key: None if entry in gone else entry for key, entry in designations.items()}
        switch(destination, known, left["current"], left["previous"], {"event": "uninstall", "kit_id": kit_id, "absent": True,
                                                                       "at_utc": ctx.clock().isoformat(), "report": str(report.path)},
               warn=ctx.warn)
        report.step("programme", "ok", f"{program} déjà absent : version retirée du pointeur, rien n'a été supprimé")
        return
    if program.is_symlink() or not program.is_dir():
        raise InstallError(f"{program} n'est pas un dossier d'installation (absent ou lien) ; rien n'a été supprimé.", EXIT_REFUSED)
    if Path(os.path.realpath(program)).parent != Path(os.path.realpath(destination)):
        raise InstallError(f"{program} n'est pas directement sous {destination} ; rien n'a été supprimé.", EXIT_REFUSED)
    if kit_id in orphans(destination, safe_pointer(destination)):
        # Copie interrompue par un arrêt brutal : ni manifeste, ni version désignée, ni donnée d'exécution (orphans).
        if not shutil.rmtree.avoids_symlink_attacks:
            raise InstallError("Suppression sûre impossible sur ce système (rmtree sans protection contre les liens) ; rien n'a été "
                               "supprimé.", EXIT_REFUSED)
        shutil.rmtree(program)
        report.step("programme", "ok", f"dossier incomplet {program} retiré, liens supprimés sans être suivis")
        return
    for marker in (linux_kit.MANIFEST, linux_kit.SUMS):
        path = program / marker
        if path.is_symlink() or not path.is_file():
            raise InstallError(f"{program} n'est pas une installation de l'atelier ({marker} absent) ; rien n'a été supprimé.", EXIT_REFUSED)
    if read_json(program / linux_kit.MANIFEST).get("kit_id") != kit_id:
        raise InstallError(f"{program} ne porte pas la version {kit_id} ; rien n'a été supprimé.", EXIT_REFUSED)
    residues = [name for name in RUNTIME_DATA if (program / name).exists() or (program / name).is_symlink()]
    if residues:
        raise InstallError(f"données d'exécution dans le dossier programme ({', '.join(residues)}) : un profil y a écrit. Les déplacer ou "
                           "les sauvegarder, puis relancer ; rien n'a été supprimé.", EXIT_REFUSED)
    pointer = read_pointer(destination)
    entries = [entry for entry in ((pointer or {}).get("current"), (pointer or {}).get("previous")) if entry and same_path(entry["program"], program)]
    for entry in entries:
        kept["data"].add(entry["data_root"])
    backups: set[str] = set()
    profiles = sorted({path for entry in entries for path in entry.get("profiles", {}).values()} | set(extra_profiles or []))
    stopped = False
    for profile in profiles:
        if not Path(profile).is_file():
            continue
        if inside(Path(profile), program):
            raise InstallError(f"Le profil {profile} est dans le dossier programme ; rien n'a été supprimé.", EXIT_REFUSED)
        if venv_python(program).exists():
            info = profile_info(ctx, program, Path(profile))
            within = [f"{key} {value}" for key, value in info["locations"].items() if inside(Path(value), program)]
            if within:
                raise InstallError(f"Le profil {profile} écrit dans le dossier programme ({'; '.join(within)}) ; rien n'a été supprimé.",
                                   EXIT_REFUSED)
            locations = info["locations"]
            if locations.get("runtime.backups_dir"):
                backups.add(locations["runtime.backups_dir"])
            storage = locations.get("qdrant.storage")
            if storage and not any(inside(Path(storage), Path(root)) for root in kept["data"]):
                kept["storage"].add(storage)
        state = rag(ctx, program, "status", "--profile", profile)
        if state.get("_returncode") or not state.get("status"):
            # État illisible : jamais pris pour un arrêt ; une instance de cette version garderait ports et verrou du stockage
            # sans plus aucun lanceur pour l'arrêter.
            reason = str(state.get("message") or "état sans statut").strip()
            raise InstallError(f"État de l'instance de {kit_id} illisible ({reason}) : l'arrêter (« "
                               f"{launcher_command(safe_pointer(destination), destination, 'arreter')} »), puis relancer ; rien n'a été "
                               "supprimé.", EXIT_REFUSED)
        executable = (state.get("supervisor") or {}).get("executable")
        if state.get("status") in RUNNING and executable and inside(Path(executable), program):
            down = rag(ctx, program, "down", "--profile", profile)
            if down.get("status") not in {"stopped", "failed"}:
                raise InstallError(f"Arrêt de l'atelier non confirmé (état {down.get('status')}) ; rien n'a été supprimé.")
            report.step("arret", "ok", f"instance de {kit_id} arrêtée")
            stopped = True
    # Aucun processus du compte ne doit tourner depuis ce dossier (R3S-03) : instance lancée avec un profil que l'installation
    # ne désigne pas, ou autre usage du programme. Après un arrêt, ses processus ont un court délai pour se terminer.
    leftover = ctx.probe.program_processes(program)
    deadline = time.monotonic() + PROCESS_EXIT_WAIT_S
    while leftover and stopped and time.monotonic() < deadline:
        time.sleep(0.2)
        leftover = ctx.probe.program_processes(program)
    if leftover:
        raise InstallError(f"Processus de {kit_id} encore en marche ({processes_text(leftover)}) : instance lancée avec un profil que "
                           "l'installation ne désigne pas, ou autre usage de ce programme — les arrêter, puis relancer ; rien n'a été "
                           "supprimé.", EXIT_REFUSED)
    # Sauvegardes : emplacement lu dans les profils, sinon celui que init-profile écrit (<données>/backups).
    kept["backups"] |= backups or {str(Path(entry["data_root"]) / "backups") for entry in entries}
    if not shutil.rmtree.avoids_symlink_attacks:
        raise InstallError("Suppression sûre impossible sur ce système (rmtree sans protection contre les liens) ; rien n'a été supprimé.",
                           EXIT_REFUSED)
    if pointer and entries:
        # Pointeur d'abord : il ne désigne jamais un dossier en cours de suppression.
        current = None if pointer.get("current") and same_path(pointer["current"]["program"], program) else pointer.get("current")
        previous = None if pointer.get("previous") and same_path(pointer["previous"]["program"], program) else pointer.get("previous")
        switch(destination, pointer, current, previous, {"event": "uninstall", "kit_id": kit_id, "at_utc": ctx.clock().isoformat(),
                                                         "report": str(report.path)}, warn=ctx.warn)
        report.step("pointeur", "ok", "version courante retirée, lanceur supprimé" if not current else "version courante inchangée")
    try:
        shutil.rmtree(program)
    except KeyboardInterrupt:
        raise Interrupted(f"Désinstallation interrompue pendant la suppression de {program} : cette version n'est plus désignée ; "
                          f"« {removal_command(ctx, destination, safe_pointer(destination), kit_id)} » retire ce dossier restant, puis "
                          "relancer la commande pour les versions suivantes.") from None
    report.step("programme", "ok", f"{program} retiré, liens supprimés sans être suivis")


def uninstall_again(ctx: Context, destination: Path, args: argparse.Namespace) -> str:
    """Même désinstallation, par l'installateur d'une version encore désignée (le programme lancé peut avoir été retiré)."""
    pointer = safe_pointer(destination) or {}
    entry = pointer.get("current") or pointer.get("previous")
    option = ["--tout"] if args.tout else ["--anciennes"] if args.anciennes else ["--kit-id", args.kit_id] if args.kit_id else []
    if entry and (Path(entry["program"]) / INSTALLER_NAME).is_file():
        return installer_command(Path(entry["program"]), "uninstall", *option)
    return installer_command(ctx.kit, "uninstall", "--destination", str(destination), *option)


def uninstall(ctx: Context, args: argparse.Namespace) -> int:
    destination = resolve_destination(ctx, args)
    if not destination.is_dir():
        raise InstallError(f"Destination absente : {destination} ; rien n'a été supprimé.", EXIT_REFUSED)
    refuse_if_locked(destination)
    pointer = read_pointer(destination)
    targets, warnings = uninstall_targets(destination, pointer, args)
    if not targets:
        print("Aucune ancienne version à retirer : seules la version courante et la version précédente sont présentes.", file=ctx.out)
        return EXIT_OK
    entries = [entry for entry in ((pointer or {}).get("current"), (pointer or {}).get("previous")) if entry]
    lines = [f"Installation : {destination}"]
    for kit_id in targets:
        folder = destination / kit_id
        if folder.exists() or folder.is_symlink():
            lines.append(f"Retirer : {kit_id} ({fr_gib(ctx.probe.tree_bytes(folder))})")
        else:
            # Dossier d'une version désignée disparu : seul le pointeur change (remove_version, U4-02).
            lines.append(f"Retirer du pointeur : {kit_id} (dossier {folder} déjà absent)")
    lines += [f"Attention : {warning}" for warning in warnings]
    if entries and all(entry["kit_id"] in targets for entry in entries):
        # Dernière version désignée : sans sauvegarde, ces données ne pourront plus être reprises (reprise_checks).
        for root in sorted({entry["data_root"] for entry in entries}):
            if latest_backup(Path(root)) is None:
                lines.append(f"Attention : aucune sauvegarde dans {Path(root) / 'backups'} ; une réinstallation sur ces données sera "
                             "refusée (reprise sans sauvegarde non prise en charge). Sauvegarder d'abord : "
                             f"« {launcher_command(pointer, destination, 'ouvrir')} », puis "
                             f"« {launcher_command(pointer, destination, 'sauvegarder')} »")
    lines += [f"Conservé : données {root}" for root in sorted({entry["data_root"] for entry in entries})]
    if args.tout:
        lines.append("Retiré aussi : lanceur, icône, entrée de menu, commande atelier et entrée du registre")
    for kit_id in targets:
        refuse_unreadable_instance(ctx, destination, pointer, kit_id, args.profile or [])
    confirm(ctx, args, "Récapitulatif de la désinstallation", lines)
    label = "tout" if args.tout else "anciennes" if args.anciennes else targets[0]
    report = Report(ctx, "uninstall", destination=str(destination), kit_ids=targets)
    report.path = destination / f"uninstall-{label}-{stamp(ctx.clock())}.json"
    kept: dict[str, set[str]] = {"data": set(), "backups": set(), "storage": set()}
    with installer_lock(destination):
        if read_pointer(destination) != pointer:
            raise InstallError("L'installation a changé pendant la confirmation : relancer la commande ; rien n'a été supprimé.", EXIT_REFUSED)
        removed: list[str] = []
        try:
            for kit_id in targets:
                remove_version(ctx, destination, kit_id, report, args.profile or [], kept)
                removed.append(kit_id)
            report.data["status"] = "uninstalled"
            registry_record(ctx, destination)
            rows = [(END_LABELS["data"], f"{root} ({fr_gib(ctx.probe.tree_bytes(Path(root)))})") for root in sorted(kept["data"])]
            rows += [(END_LABELS["backups"], path + ("" if backups_in(Path(path)) else " (aucune sauvegarde)")) for path in sorted(kept["backups"])]
            rows += [(END_LABELS["storage"], path) for path in sorted(kept["storage"])]
            rows.append((END_LABELS["kept"], f"{destination} ({POINTER}, {LOCK}, rapports uninstall-*.json)"))
            end_block(ctx, f"Désinstallation terminée : {', '.join(removed)} retirée{'s' if len(removed) > 1 else ''}. Conservés :", rows,
                      footer="Les supprimer reste une décision de l'utilisateur.")
            return EXIT_OK
        except BaseException as error:
            report.data.update(status="failed", error=str(error), removed=removed)
            if removed and isinstance(error, KeyboardInterrupt):
                rest = [kit_id for kit_id in targets if kit_id not in removed]
                detail = f" {error}" if isinstance(error, Interrupted) and str(error) else ""
                raise Interrupted(f"Désinstallation interrompue : versions déjà retirées : {', '.join(removed)} ; non retirées : "
                                  f"{', '.join(rest)} ; données conservées.{detail} Relancer « {uninstall_again(ctx, destination, args)} » "
                                  "pour la suite.") from None
            if removed and isinstance(error, Exception):
                raise as_partial(InstallError(f"{error} (déjà retirées : {', '.join(removed)})")) from error
            raise
        finally:
            report.save()


# --- Réparation, état, vérification -------------------------------------------------------------------------------------

def repair(ctx: Context, args: argparse.Namespace) -> int:
    """Fichiers dérivés régénérés depuis le pointeur, seule source de vérité de la version courante ; --menu et --sans-menu
    changent le choix d'intégration au bureau et le consignent."""
    destination = resolve_destination(ctx, args)
    # Lecture avant le verrou, qui crée la destination : une destination mal saisie ne laisse ni dossier ni verrou.
    if not destination.is_dir() or not read_pointer(destination):
        raise InstallError(f"Aucun pointeur {destination / POINTER} : rien à réparer ; rien n'a été écrit.", EXIT_REFUSED)
    with installer_lock(destination):
        pointer = read_pointer(destination)
        if not pointer:
            raise InstallError(f"Aucun pointeur {destination / POINTER} : rien à réparer.", EXIT_REFUSED)
        current = pointer.get("current")
        if current and not (Path(current["program"]) / linux_kit.MANIFEST).is_file():
            raise InstallError(f"Le pointeur désigne {current['program']}, absent : {absent_program_way(pointer)} ; rien n'a été écrit.",
                               EXIT_REFUSED)
        change: dict[str, Any] | None = None
        if args.sans_menu:
            change = {"menu": False, "menu_entry": None, "user_command": None}
        elif args.menu is not None:
            change, notes = integration_for(ctx, destination, sans_menu=False, menu_dir=Path(args.menu) if args.menu else None)
            if menu_unsupported(destination):
                raise InstallError(f"{menu_unsupported(destination)} ; rien n'a été modifié.", EXIT_REFUSED)
            entry = Path(change["menu_entry"])
            if not free_or_ours(entry, desktop_owner, destination):
                raise InstallError(f"Entrée de menu {entry} déjà présente, d'une autre application ou d'une autre installation : la laisser en "
                                   f"place ; {MENU_ELSEWHERE}. Rien n'a été modifié.", EXIT_REFUSED)
            for note in notes:
                ctx.warn(note)
        if change is not None:
            pointer = switch(destination, pointer, current, pointer.get("previous"),
                             {"event": "repair", "menu": change["menu"], "at_utc": ctx.clock().isoformat()}, integration=change, warn=ctx.warn)
            registry_record(ctx, destination)
        else:
            refresh_derived(destination, pointer, warn=ctx.warn)
        parts = [f"lanceur {'régénéré pour la version ' + current['kit_id'] if current else 'retiré (aucune version courante)'}"]
        if integration_enabled(pointer) and pointer.get("menu_entry"):
            parts.append(f"entrée de menu {pointer['menu_entry']}")
        if integration_enabled(pointer) and pointer.get("user_command"):
            parts.append(f"commande {pointer['user_command']}")
        if not integration_enabled(pointer):
            parts.append("aucune intégration au bureau (--sans-menu)")
        print("Réparation terminée : " + " ; ".join(parts) + ".", file=ctx.out)
        return EXIT_OK


def absent_program_way(pointer: dict[str, Any]) -> str:
    """Suite possible quand le dossier du programme courant a disparu : retour à la version précédente par son installateur,
    sinon réinstallation de cette version avec son kit (dépannage, section 10.4)."""
    previous = pointer.get("previous")
    if previous and not previous.get("rolled_back") and (Path(previous["program"]) / INSTALLER_NAME).is_file():
        return f"revenir à la version précédente : « {installer_command(Path(previous['program']), 'rollback')} »"
    return ("réinstaller cette version depuis son kit en reprenant les données : procédure de docs/exploitation/DEPANNAGE.md, "
            "section 10.4 (« Réparer un programme installé avec le seul kit de sa version »)")


def present_installer(ctx: Context, destination: Path, pointer: dict[str, Any] | None) -> tuple[Path, tuple[str, ...]]:
    """Installateur présent qui porte les commandes d'une installation (U4-02) : celui de la version courante, sinon celui de
    la version précédente encore utile au retour arrière, sinon celui qui s'exécute (kit ou programme), avec --destination."""
    for key in ("current", "previous"):
        entry = (pointer or {}).get(key)
        if entry and not entry.get("rolled_back") and (Path(entry["program"]) / INSTALLER_NAME).is_file():
            return Path(entry["program"]), ()
    return ctx.kit, ("--destination", str(destination))


def state_text(state: dict[str, Any], model: str | None, pointer: dict[str, Any] | None, destination: Path) -> str:
    status = state.get("status")
    if status == "running":
        return f"démarré (modèle {model})" if model else "démarré (profil non reconnu par l'installation)"
    if status == "failed":
        return f"arrêté sur erreur : « {launcher_command(pointer, destination, 'diagnostic')} » en détaille la cause"
    if status == "stale":
        return f"interrompu sans arrêt propre : relancer « {launcher_command(pointer, destination, 'ouvrir')} »"
    return STATE_TEXT.get(str(status), f"non reconnu ; « {launcher_command(pointer, destination, 'diagnostic')} » en détaille la cause")


def backups_of(ctx: Context, current: dict[str, Any], program: Path) -> tuple[Path, list[dict[str, Any]]]:
    folder = Path(current["data_root"]) / "backups"
    if venv_python(program).exists() and Path(current["profile"]).is_file():
        try:
            folder = Path(profile_info(ctx, program, Path(current["profile"]))["locations"].get("runtime.backups_dir") or folder)
        except InstallError:
            pass
    found = []
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if (path / "manifest.json").is_file():
                found.append({"path": str(path), "name": path.name, "date": backup_date(path), "size": ctx.probe.tree_bytes(path)})
    return folder, found


def status_report(ctx: Context, destination: Path, *, as_json: bool) -> int:
    pointer = read_pointer(destination)
    versions = versions_present(destination)
    incomplete = orphans(destination, pointer)
    result: dict[str, Any] = {"destination": str(destination), "versions": versions, "incomplete_versions": incomplete, "pointer": pointer,
                              "problems": []}
    problems = result["problems"]
    current, previous = (pointer or {}).get("current"), (pointer or {}).get("previous")
    text: list[str] = [f"Installation : {destination}"]
    if not pointer:
        problems.append(f"aucune installation dans {destination}")
    elif not current:
        problems.append(f"aucune version courante. {reinstall_hint(destination, pointer)}")
    base, extra = present_installer(ctx, destination, pointer)

    def command(*words: str) -> str:
        return installer_command(base, *words, *extra)

    # Contrôles d'installer.sh de chaque version désignée présente, rejoués en lecture seule (U6-04) : son refus, qui porte
    # l'action selon ce que le pointeur dit de cette version, est un problème ; le lanceur, qui ne passe pas par installer.sh,
    # fonctionnerait encore.
    for entry in (current, previous):
        if entry and (Path(entry["program"]) / linux_kit.MANIFEST).is_file():
            refusal = ctx.probe.installer_refusal(Path(entry["program"]))
            if refusal:
                problems.append(f"« {installer_command(Path(entry['program']))} » refuse toute commande, avant de lancer Python : {refusal}")
    if current:
        program = Path(current["program"])
        present = (program / linux_kit.MANIFEST).is_file()
        repair_command = command("repair")
        launcher = destination / LAUNCHER
        models = [current["model"], *(model for model in current.get("profiles") or {} if model != current["model"])]
        text += [f"Version courante : {current['kit_id']} (modèle principal {current['model']} ; modèles : {', '.join(models)})",
                 f"Programme : {program}", f"Données : {current['data_root']}"]
        if present and (not launcher.is_file() or f"version {current['kit_id']}." not in launcher.read_text(encoding="utf-8")):
            problems.append(f"lanceur absent ou d'une autre version : « {repair_command} » le régénère depuis le pointeur")
        if not present:
            # Lanceur, icône et intégration se régénèrent après le retour arrière ou la réinstallation : seule cette suite est dite.
            problems.append(f"programme courant absent : {program} — {absent_program_way(pointer or {})}")
        elif not Path(current["profile"]).is_file():
            problems.append(f"profil absent : {current['profile']}")
        else:
            state = rag(ctx, program, "status", "--profile", current["profile"])
            result["instance"] = {key: state.get(key) for key in ("status", "instance_id", "generation", "profile_matches_current")}
            model = model_of_state(state, current.get("profiles") or {}, current["model"]) if state.get("status") in RUNNING else None
            text.append(f"État de l'atelier : {state_text(state, model, pointer, destination)}")
        if present and (program / ICON_SOURCE).is_file() and not (destination / ICON).is_file():
            problems.append(f"icône absente ({destination / ICON}) : « {repair_command} » la régénère")
        if integration_enabled(pointer or {}):
            for key, owner, name in (("menu_entry", desktop_owner, "entrée de menu"), ("user_command", command_owner, "commande atelier")):
                value = (pointer or {}).get(key)
                if not value or not present:
                    continue
                if not Path(value).exists() and not Path(value).is_symlink():
                    problems.append(f"{name} absente ({value}) : « {repair_command} » la régénère")
                elif not owned_by(owner(Path(value)), destination):
                    problems.append(f"{name} {value} remplacée par un fichier étranger : le retirer, puis « {repair_command} »")
            parts = [f"entrée de menu {pointer.get('menu_entry')}" if pointer.get("menu_entry") else None,  # type: ignore[union-attr]
                     f"commande {pointer.get('user_command')}" if pointer.get("user_command") else None]  # type: ignore[union-attr]
            line = "Intégration au bureau : " + (" ; ".join(part for part in parts if part) or "aucune")
            if "menu" not in (pointer or {}):
                # Installateur de 78ec95c : ni entrée ni commande, et aucune mise à jour ne les crée sans repair --menu.
                line += (" (installation antérieure à l'intégration au bureau) ; « " + command("repair", "--menu")
                         + f" » ajoute l'entrée de menu et la commande {USER_COMMAND}")
            text.append(line)
        else:
            text.append("Intégration au bureau : désactivée (--sans-menu) ; « " + command("repair", "--menu") + " » la rétablit")
        if previous:
            if previous.get("rolled_back"):
                text.append(f"Version précédente : {previous['kit_id']}, abandonnée par un retour arrière")
                if previous.get("data_root") and previous["data_root"] != current["data_root"]:
                    text.append(f"Ancienne racine des données conservée : {previous['data_root']}")
            else:
                text.append(f"Version précédente : {previous['kit_id']} ; retour arrière : « {command('rollback')} »")
        folder, backups = backups_of(ctx, current, program)
        if backups:
            text.append(f"Sauvegardes ({folder}) :")
            for item in backups:
                needed = " — nécessaire au retour arrière" if current.get("backup") and os.path.realpath(current["backup"]) == os.path.realpath(item["path"]) else ""
                text.append(f"  {item['name']} — {item['date']} — {fr_gib(item['size'])}{needed}")
    designated_ids = {entry["kit_id"] for entry in (current, previous) if entry}
    for kit_id in versions:
        if kit_id not in designated_ids:
            removal = command("uninstall", "--anciennes") if current else removal_command(ctx, destination, pointer, kit_id)
            problems.append(f"version présente non désignée : {kit_id} ({fr_gib(ctx.probe.tree_bytes(destination / kit_id))}) — la retirer : "
                            f"« {removal} »")
    for kit_id in incomplete:
        problems.append(f"dossier incomplet {destination / kit_id} (copie interrompue, sans kit-manifest.json ; "
                        f"{fr_gib(ctx.probe.tree_bytes(destination / kit_id))}) — le retirer : « {removal_command(ctx, destination, pointer, kit_id)} »")
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2), file=ctx.out)
    else:
        text += (["Problèmes :", *(f"  - {item}" for item in problems)] if problems else ["Aucun problème relevé."])
        print("\n".join(text), file=ctx.out)
    return EXIT_OK if not problems else EXIT_ERROR


def status(ctx: Context, args: argparse.Namespace) -> int:
    if not args.destination and not installation_of(ctx.kit) and not known_destinations(ctx):
        registry = registry_file(ctx.environ)
        print(f"Aucune installation de l'atelier trouvée (registre {registry or 'inaccessible'} ; emplacement par défaut "
              f"{default_programs_text(ctx.environ)}). Si l'atelier est installé ailleurs : "
              f"« {installer_command(ctx.kit, 'status', '--destination')} <dossier des versions> » ; sinon, installer depuis le "
              f"dossier d'un kit : ./{INSTALLER_NAME}.", file=ctx.out)
        return EXIT_ERROR
    return status_report(ctx, resolve_destination(ctx, args), as_json=args.json)


def verify_only(ctx: Context, args: argparse.Namespace) -> int:
    """Ce que ferait l'installation avec les mêmes options, sans écriture ni verrou (U4-03) : sans emplacement explicite, la
    même résolution que `./installer.sh` (installation retrouvée : mise à jour annoncée, version précédente ou dossier de
    version non désigné refusés) ; installation désignée ou données conservées dans les emplacements visés : même refus
    qu'`install` (code 3) ; sinon précontrôles, vérification ciblée et contrôles système. Codes 0, 3 ou 4."""
    manifest = read_manifest(ctx.kit)
    # Les commandes citées par les refus sont celles de l'installation : `install` à la place de `verifier`.
    words = list(getattr(args, "user_argv", None) or [])
    if "verifier" in words:
        words[words.index("verifier")] = "install"
    install_args = argparse.Namespace(**{**vars(args), "user_argv": words, "implicit": False, "reprendre_donnees": False})
    implicit = not (args.destination or args.data_root or args.emplacement)
    found: list[Path] = []
    if implicit:
        refuse_undesignated_version(ctx, "status")
    if not (args.destination or args.data_root):
        found = known_destinations(ctx)
    if implicit and found:
        destination = found[0] if len(found) == 1 else resolve_destination(ctx, args)
        pointer = read_pointer(destination)
        current = (pointer or {}).get("current")
        if current and current["kit_id"] == manifest["kit_id"]:
            print(f"La version {current['kit_id']} est déjà la version courante de {destination} : rien à installer ; son état : "
                  f"« {installer_command(Path(current['program']), 'status')} ». Rien n'a été écrit.", file=ctx.out)
            return EXIT_OK
        refuse_previous_version(manifest, destination, pointer)
        if current:
            report = Report(ctx, "verifier", kit_id=manifest["kit_id"])
            verify_targeted(ctx, manifest, report, pre_copy=True)
            system_check(ctx, manifest, report)
            print(f"Installation existante trouvée dans {destination} (version {current['kit_id']}) : ./{INSTALLER_NAME}, lancé depuis ce "
                  f"kit, en proposera la mise à jour vers {manifest['kit_id']}. Kit et bibliothèques du système conformes ; la place, "
                  "la sauvegarde des données et les profils des modèles seront contrôlés par la mise à jour, avant toute écriture. Rien "
                  "n'a été écrit.", file=ctx.out)
            return EXIT_OK
    destination, data_root, relocatable = install_locations(ctx, args)
    model = args.model or manifest["default_model"]
    integration, notes = integration_for(ctx, destination, sans_menu=args.sans_menu, menu_dir=Path(args.menu) if args.menu else None)
    report = Report(ctx, "verifier", kit_id=manifest["kit_id"])
    interrupted = interrupted_install(ctx, data_root, destination, args=install_args)
    refuse_existing(ctx, install_args, destination, data_root, reprise=False, interrupted=interrupted)
    _, _, port_notes = choose_ports(ctx, manifest, model, args.ports)
    elsewhere = None if (found or args.destination or args.data_root) else elsewhere_line(ctx)
    facts = precheck(ctx, manifest, destination, data_root, qdrant_storage=args.qdrant_storage,
                     menu_entry=Path(integration["menu_entry"]) if integration.get("menu_entry") else None, menu_explicit=bool(args.menu),
                     model=model, ports=args.ports, args=args, relocatable=relocatable,
                     replaced=Path(interrupted["program"]) if interrupted else None,
                     user_command=Path(integration["user_command"]) if integration.get("user_command") else None,
                     elsewhere_hint=elsewhere_text(ctx) if elsewhere else None)
    report.step("precontroles", "ok", ", ".join(facts["passed"]) + (f" ; {', '.join(port_notes)} : un triplet libre sera proposé" if port_notes else ""))
    for note in notes:
        ctx.warn(note)
    verify_targeted(ctx, manifest, report)
    system_check(ctx, manifest, report)
    print(f"Poste et kit prêts pour l'installation dans {destination} (données : {data_root}) ; rien n'a été écrit."
          + (f"\n{elsewhere}" if elsewhere else ""), file=ctx.out)
    return EXIT_OK


# --- Modèle principal et lanceur --------------------------------------------------------------------------------------------

def change_model(ctx: Context, args: argparse.Namespace, destination: Path, model: str | None) -> int:
    """Modèle principal changé durablement (pointeur, lanceur, actions du menu), sous le verrou ; aucun profil modifié."""
    pointer = read_pointer(destination)
    current = (pointer or {}).get("current")
    if not current:
        raise InstallError(f"Aucune version courante dans {destination} : rien à changer.", EXIT_REFUSED)
    profiles = dict(current.get("profiles") or {})
    if not model:
        # Texte à remplacer écrit tel quel (shlex le mettrait entre apostrophes).
        raise InstallError(f"Indiquer le modèle : « {launcher_command(pointer, destination, 'modele')} <modèle> » ; installés : "
                           f"{', '.join(profiles)}.", EXIT_USAGE)
    if model == current["model"]:
        print(f"{model} est déjà le modèle principal : rien à changer.", file=ctx.out)
        return EXIT_OK
    program = Path(current["program"])
    delivered = read_json(program / linux_kit.MANIFEST).get("model_profiles") or {}
    if model not in profiles and model not in delivered:
        raise InstallError(f"Modèle {model} non livré par la version {current['kit_id']} ({', '.join(delivered)}) ; rien n'a été changé.",
                           EXIT_REFUSED)
    refuse_if_locked(destination)
    state = rag(ctx, program, "status", "--profile", current["profile"])
    running = state.get("status") in RUNNING
    active = model_of_state(state, profiles, current["model"]) if running else None
    if running and active != model:
        text = (f"L'atelier tourne avec {active or UNKNOWN_PROFILE} : l'arrêter d'abord (« "
                f"{launcher_command(pointer, destination, 'arreter')} »), puis relancer « {launcher_command(pointer, destination, 'modele', model)} » ; "
                "un traitement en cours serait interrompu. Rien n'a été changé.")
        if getattr(args, "oui", False) or not ctx.interactive:
            raise InstallError(text, EXIT_REFUSED)
        print(text.replace(" Rien n'a été changé.", ""), file=ctx.out)
        if ctx.question("Arrêter l'atelier maintenant, puis changer de modèle ? [o/N] ").lower() not in {"o", "oui"}:
            raise InstallError("Abandon demandé : rien n'a été changé.", EXIT_REFUSED)
    with installer_lock(destination):
        if read_pointer(destination) != pointer:
            raise InstallError("L'installation a changé entre-temps : relancer la commande ; rien n'a été changé.", EXIT_REFUSED)
        report = Report(ctx, "modele", destination=str(destination), kit_id=current["kit_id"], model_from=current["model"], model_to=model)
        report.path = Path(current["data_root"]) / f"modele-{stamp(ctx.clock())}.json"
        created: list[str] = []
        stopped = False
        try:
            if running and active != model:
                down = rag(ctx, program, "down", "--profile", current["profile"])
                if down.get("status") not in {"stopped", "failed"}:
                    raise InstallError(f"Arrêt de l'atelier non confirmé (état {down.get('status')}) ; rien n'a été changé.")
                stopped = True
                report.step("arret", "ok", "atelier arrêté avant le changement de modèle")
            if model not in profiles:
                target = Path(current["data_root"]) / f"profile-{model_slug(model)}.yaml"
                existed = target.exists()
                made = derive_profiles(ctx, report, python=venv_python(program), scripts=program, program=program, like=current["profile"],
                                       data_root=Path(current["data_root"]), models=[model])
                created += [] if existed else [made[model]]
                profiles.update(made)
            doctor = rag(ctx, program, "doctor", "--profile", profiles[model])
            verdict = doctor.get("verdict") or {}
            for item in verdict.get("rubrics", []):
                if item.get("rubric") in {"modèle", "mémoire"}:
                    ctx.say(item.get("level", "?"), item.get("rubric", ""), item.get("message", ""))
            red = [item for item in verdict.get("rubrics", []) if item.get("level") == RED]
            if doctor.get("_returncode") or not verdict or red:
                details = " ".join(f"{item.get('message')} {item.get('action') or ''}".strip() for item in red) or str(doctor.get("message"))
                raise InstallError(f"Changement refusé par le diagnostic du profil {profiles[model]} : {details} Rien n'a été changé.", EXIT_REFUSED)
            entry = {**current, "model": model, "profile": profiles[model], "profiles": profiles}
            new = switch(destination, pointer, entry, (pointer or {}).get("previous"),
                         {"event": "modele", "from": current["model"], "to": model, "at_utc": ctx.clock().isoformat(), "report": str(report.path)},
                         warn=ctx.warn)
            report.step("modele", "ok", f"{current['model']} → {model} ; profils inchangés")
            registry_record(ctx, destination)
            report.data["status"] = "changed"
            print(f"Modèle principal : {model}. « {launcher_command(new, destination, 'ouvrir')} » l'emploie désormais ; pour revenir : "
                  f"« {launcher_command(new, destination, 'modele', current['model'])} ». Aucun profil n'a été modifié.", file=ctx.out)
            return EXIT_OK
        except BaseException as error:
            report.data.update(status="failed", error=str(error))
            # Relecture du pointeur sur disque : un profil créé que la bascule a déjà désigné n'est jamais retiré.
            now = designated(destination) or {}
            switched = now.get("model") == model and now.get("profile") == profiles.get(model)
            kept = set((now.get("profiles") or {}).values())
            for path in created:
                if path not in kept:
                    Path(path).unlink(missing_ok=True)
            if isinstance(error, KeyboardInterrupt):
                if switched:
                    raise Interrupted(f"Changement de modèle interrompu après la bascule : {model} est le modèle principal ; "
                                      f"« {launcher_command(safe_pointer(destination), destination, 'modele', current['model'])} » "
                                      "revient en arrière.") from None
                raise Interrupted(f"Changement de modèle interrompu avant la bascule : {current['model']} reste le modèle principal"
                                  + (", atelier arrêté" if stopped else "") + " ; relancer la même commande.") from None
            raise
        finally:
            report.save()


def installer_model(ctx: Context, args: argparse.Namespace) -> int:
    return change_model(ctx, args, resolve_destination(ctx, args), args.tag)


def reinstall_hint(destination: Path, pointer: dict[str, Any] | None) -> str:
    """Suite possible sans version courante : commandes complètes, la seule inconnue étant le dossier du kit à employer."""
    previous = (pointer or {}).get("previous")
    kit = "<dossier du kit>/"
    if previous:
        removal = installer_command(Path(previous["program"]), "uninstall", "--kit-id", previous["kit_id"])
        reprise = quoted(INSTALLER_NAME, "install", "--destination", str(destination), "--data-root", previous["data_root"], "--reprendre-donnees")
        return (f"La version {previous['kit_id']} y reste sans être désignée : la retirer (« {removal} »), puis reprendre les données "
                f"conservées depuis le dossier d'un kit (« {kit}{reprise} »).")
    return (f"Réinstaller depuis le dossier d'un kit (« {kit}{quoted(INSTALLER_NAME, 'install', '--destination', str(destination))} », "
            "avec --reprendre-donnees pour reprendre des données conservées).")


def no_current_text(destination: Path, pointer: dict[str, Any] | None) -> str:
    return f"Aucune version courante dans {destination}. {reinstall_hint(destination, pointer)}"


def run(ctx: Context, args: argparse.Namespace) -> int:
    """Actions du lanceur `atelier`, toujours avec un profil de la racine des données."""
    destination = pointer_destination(Path(args.destination).absolute())
    pointer = read_pointer(destination)
    current = (pointer or {}).get("current")
    if not current:
        raise InstallError(no_current_text(destination, pointer), EXIT_REFUSED)
    program = Path(current["program"])
    if Path(os.path.realpath(program)) != Path(os.path.realpath(ctx.kit)):
        raise InstallError(f"Lanceur périmé : il vise {ctx.kit}, la version courante est {program} ; « {installer_command(program, 'repair')} » "
                           "le régénère.", EXIT_REFUSED)
    action = args.action

    def command(*words: str) -> str:
        return launcher_command(pointer, destination, *words)

    if action == "modele":
        return change_model(ctx, args, destination, args.valeur)
    if args.valeur:
        raise InstallError(f"Argument inattendu : {args.valeur} ; « {command('--aide')} » liste les actions.", EXIT_USAGE)
    profiles = current.get("profiles") or {}
    if args.modele and args.modele not in profiles:
        raise InstallError(f"Modèle {args.modele} non installé ; installés : {', '.join(profiles)}.", EXIT_REFUSED)
    if action in {"ouvrir", "sauvegarder"} and not lock_is_free(destination):
        raise InstallError(f"Une opération d'installation est en cours sur {destination} (installation, mise à jour, retour arrière ou "
                           f"désinstallation) : « {command(action)} » est refusé jusqu'à sa fin, pour ne pas relancer ni sauvegarder "
                           "une version en cours de remplacement.", EXIT_REFUSED)
    if action == "arreter":
        result = rag(ctx, program, "down", "--profile", profiles.get(args.modele) or current["profile"], timeout=7200)
        if result.get("_returncode"):
            raise InstallError(str(result.get("message")))
        print("Atelier arrêté. Les documents, l'index et les sauvegardes sont conservés.", file=ctx.out)
        return EXIT_OK
    if action == "journaux":
        result = rag(ctx, program, "logs", "--profile", current["profile"])
        if result.get("_returncode"):
            raise InstallError(str(result.get("message")))
        logs = {name: path for name, path in result.items() if not name.startswith("_") and isinstance(path, str)}
        if not logs:
            print("Aucun journal : l'atelier n'a pas encore démarré sur ces données.", file=ctx.out)
        else:
            print("Journaux des services de la dernière instance :", file=ctx.out)
            for name, path in sorted(logs.items()):
                print(f"  {name} : {path}", file=ctx.out)
        return EXIT_OK
    state = rag(ctx, program, "status", "--profile", current["profile"])
    if state.get("_returncode"):
        raise InstallError(str(state.get("message")))
    running = state.get("status") in RUNNING
    active = model_of_state(state, profiles, current["model"]) if running else None
    if running and args.modele and active != args.modele:
        raise InstallError(f"L'atelier tourne avec {active or UNKNOWN_PROFILE}. Pour passer à {args.modele} : « "
                           f"{command('arreter')} », puis « {command('ouvrir', '--modele', args.modele)} » ; un traitement en cours serait "
                           "interrompu.", EXIT_REFUSED)
    if action == "etat":
        generation = state.get("generation")
        print(f"État : {state_text(state, active, pointer, destination)}." + (f" {generation}" if generation else ""), file=ctx.out)
        return EXIT_OK
    if running and active is None:
        raise InstallError(f"Une instance tourne sur ces données avec un profil que l'installation ne connaît pas : l'arrêter (« "
                           f"{command('arreter')} »), puis « {command(action)} ».", EXIT_REFUSED)
    if action == "sauvegarder" and not running:
        # La sauvegarde passe par l'instance (services/runtime/backup.py) : l'état étant connu ici, le refus cite le lanceur.
        raise InstallError(f"L'atelier est arrêté : l'ouvrir (« {command('ouvrir')} »), puis « {command('sauvegarder')} ».", EXIT_REFUSED)
    model = args.modele or active or current["model"]
    profile = profiles[model]
    if action == "ouvrir":
        if running:
            print(f"Atelier déjà démarré avec {model} ; " + ("affichage du lien à usage unique…" if args.no_browser
                                                              else "ouverture dans le navigateur…"), file=ctx.out, flush=True)
        else:
            print(f"Démarrage de l'atelier si nécessaire (attente maximale du démarrage : {STARTUP_WAIT_MAX_S} s)…", file=ctx.out, flush=True)
        up = rag(ctx, program, "up", "--profile", profile)
        if up.get("status") != "running":
            raise InstallError(f"{up.get('message')} ; « {command('diagnostic')} » détaille l'état.")
        mark_started(destination, program)
        opened = rag(ctx, program, "open", "--profile", profile, *(["--no-browser"] if args.no_browser else []))
        if opened.get("_returncode"):
            raise InstallError(f"{opened.get('message')} ; « {command('ouvrir', '--no-browser')} » affiche le lien à coller dans un navigateur")
        print(f"Lien à usage unique : {opened['url']}" if args.no_browser else "Atelier ouvert dans le navigateur par défaut.", file=ctx.out)
        stop = f"menu {MENU_NAME} > {MENU_ACTIONS['arreter']}, ou « {command('arreter')} »" if (
            integration_enabled(pointer or {}) and (pointer or {}).get("menu_entry")) else f"« {command('arreter')} »"
        print(f"L'atelier reste démarré après la fermeture du navigateur ; pour l'arrêter : {stop}.", file=ctx.out)
        return EXIT_OK
    rag_command = {"diagnostic": "doctor", "sauvegarder": "backup"}[action]
    result = rag(ctx, program, rag_command, "--profile", profile, timeout=7200)
    if result.get("_returncode"):
        raise InstallError(str(result.get("message")))
    if action == "diagnostic":
        verdict = result.get("verdict") or {}
        print(verdict.get("summary", ""), file=ctx.out)
        for item in verdict.get("rubrics", []):
            print(f"[{item.get('level')}] {item.get('rubric')} : {item.get('message')}", file=ctx.out)
            for key, label in (("action", ""), ("proposal", "Proposition : ")):
                if item.get(key):
                    print(f"        {label}{item[key]}", file=ctx.out)
    else:
        print(f"Sauvegarde écrite dans {result.get('path')}.", file=ctx.out)
    return EXIT_OK


# --- Analyse de la ligne de commande -------------------------------------------------------------------------------------------

ARGPARSE_MESSAGES = (
    (re.compile(r"the following arguments are required: (.+)"), r"arguments obligatoires absents : \1"),
    (re.compile(r"unrecognized arguments: (.+)"), r"arguments non reconnus : \1"),
    (re.compile(r"argument (\S+): invalid choice: (.+) \(choose from (.+)\)"), r"argument \1 : choix invalide \2 (valeurs admises : \3)"),
    (re.compile(r"argument (\S+): expected one argument"), r"argument \1 : une valeur est attendue"),
    (re.compile(r"argument (\S+): expected at most one argument"), r"argument \1 : une seule valeur est admise"),
    (re.compile(r"argument (\S+): not allowed with argument (\S+)"), r"argument \1 : incompatible avec \2"),
    (re.compile(r"argument (\S+): invalid (\S+) value: (.+)"), r"argument \1 : valeur invalide \3"),
    (re.compile(r"argument (\S+): ignored explicit argument (.+)"), r"argument \1 : valeur non admise \2"),
    (re.compile(r"ambiguous option: (\S+) could match (.+)"), r"option ambiguë : \1 peut désigner \2"),
    (re.compile(r"argument (\S+): (.+)"), r"argument \1 : \2"),
)


class FrenchFormatter(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage: str | None, actions: Any, groups: Any, prefix: str | None = None) -> None:
        super().add_usage(usage, actions, groups, "Usage : " if prefix is None else prefix)


class FrenchParser(argparse.ArgumentParser):
    """Analyseur aux messages en français : aide par -h ou --aide, erreurs sur la sortie d'erreur avec renvoi à l'aide et
    code 2 (comportement documenté d'ArgumentParser.error)."""

    def __init__(self, *args: Any, streams: tuple[TextIO, TextIO] | None = None, **kwargs: Any):
        kwargs.setdefault("formatter_class", FrenchFormatter)
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self.streams = streams
        # argparse écrit « <titre>: » ; l'espace finale donne la ponctuation française « Options : ».
        self._positionals.title = "Arguments "
        self._optionals.title = "Options "
        self.add_argument("-h", "--aide", "--help", action="help", help="afficher cette aide")

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        out, err = self.streams or (sys.stdout, sys.stderr)
        (err if file is sys.stderr else out).write(message)

    def print_help(self, file: Any = None) -> None:
        self._print_message(self.format_help(), None)

    def error(self, message: str) -> Any:  # type: ignore[override]
        for pattern, replacement in ARGPARSE_MESSAGES:
            if pattern.search(message):
                message = pattern.sub(replacement, message, count=1)
                break
        unknown = re.match(r"argument action : choix invalide '?([^' ]*)'? \(valeurs admises", message)
        if unknown:
            message = f"action inconnue : {unknown.group(1)} (actions : {', '.join(LAUNCHER_ACTIONS)})"
        _, err = self.streams or (sys.stdout, sys.stderr)
        err.write(f"{self.prog} : {message}\nAide : {self.prog} --aide\n")
        raise SystemExit(EXIT_USAGE)


class TopParser(FrenchParser):
    """Sans commande, `install` est retenu (`implicit`), y compris avec les options d'installation seules."""

    def parse_known_args(self, args: Any = None, namespace: Any = None) -> Any:  # type: ignore[override]
        argv = list(sys.argv[1:] if args is None else args)
        argv, implicit, user_argv = with_default_command(argv)
        word = argv[command_index(argv)] if not implicit else DEFAULT_COMMAND
        if word not in COMMANDS and word not in HELP_FLAGS:
            # Commande inconnue : liste des commandes publiques, sans la commande interne du lanceur (run) ni le jeton
            # « argument command » d'argparse, dont la forme varie selon la version de Python.
            self.error(f"commande inconnue : {word} (commandes : {', '.join(INSTALLER_COMMANDS)})")
        namespace, rest = super().parse_known_args(argv, namespace)
        namespace.implicit = implicit
        namespace.user_argv = user_argv
        return namespace, rest


GLOBAL_VALUE_OPTIONS = {"--kit"}
GLOBAL_FLAGS = {"--oui", "--non-interactif"}
HELP_FLAGS = {"-h", "--aide", "--help"}


def command_index(argv: list[str]) -> int:
    """Rang du premier mot qui n'est pas une option globale (--kit <kit>, --oui, --non-interactif)."""
    index = 0
    while index < len(argv):
        word = argv[index]
        if word in GLOBAL_VALUE_OPTIONS:
            index += 2
        elif word in GLOBAL_FLAGS or word.split("=", 1)[0] in GLOBAL_VALUE_OPTIONS:
            index += 1
        else:
            break
    return index


def with_default_command(argv: list[str]) -> tuple[list[str], bool, list[str]]:
    """Insère `install` si aucune commande n'est donnée ; rend aussi les arguments de l'utilisateur (sans --kit)."""
    user: list[str] = []
    skip = False
    for word in argv:
        if skip:
            skip = False
            continue
        if word in GLOBAL_VALUE_OPTIONS:
            skip = True
            continue
        if word.split("=", 1)[0] in GLOBAL_VALUE_OPTIONS:
            continue
        user.append(word)
    index = command_index(argv)
    if index < len(argv) and (not argv[index].startswith("-") or argv[index] in HELP_FLAGS):
        return argv, False, user
    return [*argv[:index], DEFAULT_COMMAND, *argv[index:]], True, user


def installer_description() -> str:
    width = max(len(name) for name in INSTALLER_COMMANDS)
    commands = "\n".join(f"  {name.ljust(width)}  {text}" for name, text in INSTALLER_COMMANDS.items())
    return ("Installe l'atelier documentaire depuis ce kit hors ligne, pour votre compte, sans droit d'administration. Sans commande, "
            "installe aux emplacements par défaut, ou propose la mise à jour si une installation existe déjà. Une installation, une "
            "mise à jour, une désinstallation et un retour arrière avec restauration affichent un récapitulatif et demandent "
            "confirmation (--oui hors terminal).\n\n"
            f"Commandes :\n{commands}")


def exit_code_label(text: str) -> str:
    """Libellé court d'un code de sortie (aide de l'installateur) : avant le premier « ; » ou « : », sans parenthèse."""
    return re.sub(r" \([^)]*\)", "", text.split(" ;")[0].split(" :")[0])


def installer_epilog() -> str:
    codes = " ; ".join(f"{code} {exit_code_label(text)}" for code, text in EXIT_CODES.items())
    examples = ((f"./{INSTALLER_NAME}", "installer aux emplacements par défaut"),
                (f"./{INSTALLER_NAME} --emplacement <dossier>", "installer sur un autre volume (programme et données)"),
                (f"./{INSTALLER_NAME} status", "état de l'installation et commandes utiles"))
    width = max(len(command) for command, _ in examples)
    return ("Exemples :\n" + "".join(f"  {command.ljust(width)}  {text}\n" for command, text in examples) + "\n"
            f"Emplacements par défaut : {DEFAULT_LOCATIONS['programme']} et {DEFAULT_LOCATIONS['donnees']} ({XDG_RULE.rstrip('.')}).\n"
            f"Codes de sortie : {codes}.\n"
            f"Guide du kit : {GUIDE_NAME}. Aide d'une commande : ./{INSTALLER_NAME} <commande> --aide.")


def launcher_description(installed: list[str] | None) -> str:
    width = max(len(name) for name in LAUNCHER_ACTIONS)
    actions = "\n".join(f"  {name.ljust(width)}  {text}" for name, text in LAUNCHER_ACTIONS.items())
    models = ""
    if installed:
        models = (f"\n\nModèles installés : {installed[0]} (principal)" + "".join(f", {model}" for model in installed[1:])
                  + f". « {USER_COMMAND} ouvrir --modele <modèle> » le temps d'une ouverture ; « {USER_COMMAND} modele <modèle> » "
                  "durablement.")
    return f"Lanceur de l'atelier documentaire installé.\n\nActions :\n{actions}{models}"


# Valeurs à remplacer dans les aides (métavariables), écrites comme dans les documents.
FOLDER, MODEL = "<dossier>", "<modèle>"


def build_parser(*, manifest: dict[str, Any] | None = None, installed: list[str] | None = None,
                 streams: tuple[TextIO, TextIO] | None = None) -> TopParser:
    default = (manifest or {}).get("default_model")
    delivered = ordered_models(manifest) if manifest else []
    model_help = (f"modèle du profil principal : {default} par défaut ; {'livrés' if len(delivered) > 1 else 'livré'} par ce kit : "
                  f"{', '.join(delivered)}" if default else "modèle du profil principal (défaut : celui du kit)")
    top = TopParser(prog=INSTALLER_NAME, usage=f"{INSTALLER_NAME} [commande] [options]", description=installer_description(),
                    epilog=installer_epilog(), streams=streams)
    top.add_argument("--kit", type=Path, default=HERE, help=argparse.SUPPRESS)
    top.add_argument("--oui", action="store_true", help="accepter le récapitulatif sans question (exigé hors terminal par les opérations "
                                                        "qui en affichent un)")
    top.add_argument("--non-interactif", action="store_true", help="ne poser aucune question (implicite hors terminal)")
    sub = top.add_subparsers(dest="command", parser_class=FrenchParser, help=argparse.SUPPRESS)

    def command(name: str, *, confirms: bool = True, asks: bool = True, oui: str | None = None) -> FrenchParser:
        """Sous-commande ; `confirms` : elle écrit après un récapitulatif (--oui affiché, ou décrit par `oui`) ; `asks` : elle peut
        poser une question (--non-interactif affiché). Les options restent acceptées partout, masquées où elles sont sans effet."""
        parser = sub.add_parser(name, prog=f"{INSTALLER_NAME} {name}", description=INSTALLER_COMMANDS[name], streams=streams)
        parser.add_argument("--oui", action="store_true", default=argparse.SUPPRESS,
                            help=(oui or "accepter le récapitulatif sans question") if confirms else argparse.SUPPRESS)
        parser.add_argument("--non-interactif", action="store_true", default=argparse.SUPPRESS,
                            help=("ne poser aucune question" if confirms else "ne pas proposer de choix numéroté quand plusieurs "
                                  "installations existent") if asks else argparse.SUPPRESS)
        return parser

    def destination_option(parser: FrenchParser) -> None:
        parser.add_argument("--destination", type=Path, metavar=FOLDER, help="dossier des versions de l'installation visée (défaut : "
                                                                              "installation retrouvée par le registre ou l'emplacement par défaut)")

    menu_default = DEFAULT_LOCATIONS["menu"].rsplit("/", 1)[0]
    for name in ("install", "verifier"):
        parser = command(name, confirms=name == "install", asks=name == "install")
        parser.add_argument("--emplacement", type=Path, metavar=FOLDER, help=f"dossier de l'atelier sur un autre volume : "
                                                                              f"<dossier>/{PROGRAM_FOLDER} et <dossier>/{DATA_FOLDER}")
        parser.add_argument("--destination", type=Path, metavar=FOLDER, help=f"dossier des versions du programme (défaut : "
                                                                              f"{DEFAULT_LOCATIONS['programme']})")
        parser.add_argument("--data-root", type=Path, metavar=FOLDER, help=f"racine des données, hors de la destination (défaut : "
                                                                            f"{DEFAULT_LOCATIONS['donnees']})")
        parser.add_argument("--qdrant-storage", type=Path, metavar=FOLDER, help="stockage de l'index Qdrant, hors de la destination, sur "
                                                                                 "un disque local (défaut : <données>/q)")
        parser.add_argument("--ports", metavar="<API,Qdrant,Ollama>", help="ports de l'API, de Qdrant et d'Ollama (défaut : ceux du profil "
                                                                           "livré, ou un triplet libre s'ils sont occupés)")
        parser.add_argument("--model", "--modele", dest="model", metavar=MODEL, help=model_help + " (--modele : même option, comme "
                                                                                             "dans le lanceur atelier)")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--menu", type=Path, metavar=FOLDER, help=f"dossier de l'entrée de menu (défaut : {menu_default}) ; une "
                                                                      "entrée écrite ailleurs n'apparaît pas dans le menu des applications")
        group.add_argument("--sans-menu", action="store_true", help=f"ni entrée de menu, ni commande {USER_COMMAND} dans ~/.local/bin, ni "
                                                                    "inscription au registre des installations")
        if name == "install":
            parser.add_argument("--reprendre-donnees", action="store_true", help="reprendre la racine des données conservée par un "
                                                                                 "retrait complet (sauvegarde existante exigée)")
            parser.add_argument("--no-start", action="store_true", help="ne pas démarrer l'atelier après l'installation")
            parser.add_argument("--no-browser", action="store_true", help="afficher le lien à usage unique au lieu d'ouvrir le navigateur")
    parser = command("update")
    destination_option(parser)
    parser.add_argument("--model", "--modele", dest="model", metavar=MODEL, help="modèle principal après la mise à jour (défaut : "
                                                                                 "celui de l'installation ; --modele : même option)")
    parser.add_argument("--menu", type=Path, metavar=FOLDER, help=f"dossier de l'entrée de menu, si elle doit changer ; hors de "
                                                                  f"{menu_default}, l'entrée n'apparaît pas dans le menu des applications")
    parser.add_argument("--no-start", action="store_true", help="ne pas démarrer l'atelier après la mise à jour")
    parser.add_argument("--no-browser", action="store_true", help="afficher le lien à usage unique au lieu d'ouvrir le navigateur")
    parser = command("rollback")
    destination_option(parser)
    parser.add_argument("--restore-target", type=Path, metavar=FOLDER, help="racine neuve de restauration, sur un disque local, si la "
                                                                             "nouvelle version a démarré sur les données")
    parser = command("uninstall")
    destination_option(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--kit-id", metavar="<kit_id>", help=f"identifiant de version donné par {INSTALLER_NAME} status (défaut : la "
                                                            "version précédente, sinon la version courante)")
    group.add_argument("--anciennes", action="store_true", help="retirer les versions ni courantes ni précédentes")
    group.add_argument("--tout", action="store_true", help="retirer toutes les versions, le lanceur et l'intégration au bureau ; données "
                                                           "conservées")
    parser.add_argument("--profile", action="append", metavar="<fichier>", help="profil supplémentaire à contrôler avant le retrait "
                                                                               "(répétable)")
    parser = command("repair", confirms=False)
    destination_option(parser)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--menu", nargs="?", const="", metavar=FOLDER, help=f"rétablir l'entrée de menu et la commande atelier (dossier "
                                                                            f"facultatif ; hors de {menu_default}, l'entrée n'apparaît pas dans "
                                                                            "le menu des applications)")
    group.add_argument("--sans-menu", action="store_true", help="retirer l'entrée de menu et la commande atelier ; ce choix est inscrit "
                                                                "au pointeur et l'entrée de l'installation est retirée du registre")
    parser = command("status", confirms=False)
    destination_option(parser)
    parser.add_argument("--json", action="store_true", help="état en JSON (structure du rapport d'état)")
    parser = command("modele", oui="ne rien demander ; refuse si l'atelier tourne avec un autre modèle")
    destination_option(parser)
    parser.add_argument("tag", metavar=MODEL, help="modèle installé à employer durablement")
    launch = sub.add_parser("run", prog=USER_COMMAND, usage=f"{USER_COMMAND} [action] [options]", description=launcher_description(installed),
                            streams=streams)
    launch.add_argument("--destination", type=Path, required=True, help=argparse.SUPPRESS)
    launch.add_argument("action", nargs="?", default="ouvrir", choices=list(LAUNCHER_ACTIONS), metavar="action", help=argparse.SUPPRESS)
    launch.add_argument("valeur", nargs="?", metavar=MODEL, help=argparse.SUPPRESS)
    launch.add_argument("--modele", metavar=MODEL, help="modèle installé à employer le temps de cette ouverture"
                        + (f" ({', '.join(installed)})" if installed else ""))
    launch.add_argument("--no-browser", action="store_true", help="afficher le lien à usage unique au lieu d'ouvrir le navigateur")
    launch.add_argument("--attendre", action="store_true", help="au terminal, attendre la touche Entrée après un échec, un diagnostic, "
                                                                "un état, une sauvegarde ou l'affichage des journaux (entrée de menu)")
    launch.add_argument("--oui", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    launch.add_argument("--non-interactif", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return top


def prescan(argv: list[str], option: str) -> str | None:
    for index, word in enumerate(argv):
        if word == option and index + 1 < len(argv):
            return argv[index + 1]
        if word.startswith(option + "="):
            return word.split("=", 1)[1]
    return None


def parser(kit: Path | None = None, *, streams: tuple[TextIO, TextIO] | None = None, argv: list[str] | None = None) -> TopParser:
    """Analyseur de l'installateur et du lanceur ; l'aide lit le manifeste du kit et, pour le lanceur, les modèles installés."""
    kit = kit or HERE
    try:
        manifest = read_json(kit / linux_kit.MANIFEST)
    except (OSError, ValueError):
        manifest = None
    installed = None
    destination = prescan(argv or [], "--destination")
    if destination:
        try:
            current = (read_pointer(Path(destination)) or {}).get("current") or {}
            installed = [current["model"], *(model for model in current.get("profiles") or {} if model != current["model"])] if current else None
        except (OSError, ValueError, InstallError, KeyError):
            installed = None
    return build_parser(manifest=manifest, installed=installed, streams=streams)


COMMANDS = {"install": install, "update": update, "rollback": rollback, "uninstall": uninstall, "repair": repair, "status": status,
            "verifier": verify_only, "modele": installer_model, "run": run}


def pause(ctx: Context) -> None:
    print("Appuyez sur Entrée pour fermer cette fenêtre.", file=ctx.out, flush=True)
    try:
        ctx.ask()
    except (EOFError, KeyboardInterrupt):
        pass


def interrupt_on_signal(signum: int, frame: Any) -> None:
    """SIGHUP (fenêtre du terminal fermée) et SIGTERM (fin de session) suivent le chemin de Ctrl+C : copie partielle et
    profils créés retirés, message de l'état laissé, code 130."""
    raise KeyboardInterrupt


@contextmanager
def termination_signals() -> Iterator[None]:
    """Gestionnaires de SIGHUP et SIGTERM pendant une commande, rétablis ensuite (fil principal seulement, POSIX)."""
    if sys.platform == "win32":
        yield
        return
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = {number: signal.signal(number, interrupt_on_signal) for number in (signal.SIGHUP, signal.SIGTERM)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def interrupted_text_of(command: str, args: argparse.Namespace) -> str:
    """Message d'une interruption sans état particulier ; pour le lanceur, la commande d'état est celle de l'installation."""
    text = INTERRUPTED.get(command, "Commande interrompue.")
    if command == "run":
        destination = Path(args.destination).absolute()
        text = text.replace("« atelier etat »", f"« {launcher_command(safe_pointer(destination), destination, 'etat')} »")
    return text


def report_error(ctx: Context, text: str) -> None:
    """Message sur la sortie d'erreur ; un terminal fermé (SIGHUP) ne transforme pas le nettoyage fait en trace Python."""
    try:
        print(text, file=ctx.err, flush=True)
    except (OSError, ValueError):
        pass


def main(argv: list[str] | None = None, ctx: Context | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    streams = (ctx.out, ctx.err) if ctx else (sys.stdout, sys.stderr)
    kit = ctx.kit if ctx else Path(prescan(argv, "--kit") or HERE)
    try:
        args = parser(kit, streams=streams, argv=argv).parse_args(argv)
    except SystemExit as exit_:
        return exit_.code if isinstance(exit_.code, int) else EXIT_USAGE
    ctx = ctx or Context(kit=args.kit.resolve())
    ctx.interactive = bool(ctx.stdin_tty and ctx.stdout_tty and not args.non_interactif)
    command = args.command
    with termination_signals():
        try:
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                raise InstallError(ROOT_REFUSAL, EXIT_REFUSED)
            code = COMMANDS[command](ctx, args)
        except KeyboardInterrupt as error:
            report_error(ctx, str(error) if isinstance(error, Interrupted) and str(error) else interrupted_text_of(command, args))
            code = EXIT_INTERRUPTED
        except (InstallError, linux_kit.KitError) as error:
            report_error(ctx, f"Arrêt : {error}")
            code = getattr(error, "code", EXIT_ERROR)
        except Exception as error:  # noqa: BLE001 - message lisible au lieu d'une trace ; le rapport garde le détail
            report_error(ctx, f"Arrêt : {type(error).__name__} : {error}")
            code = EXIT_ERROR
    if command == "run" and getattr(args, "attendre", False) and ctx.stdin_tty and (code != EXIT_OK or args.action in PAUSE_ACTIONS):
        pause(ctx)
    return code


if __name__ == "__main__":
    sys.exit(main())
