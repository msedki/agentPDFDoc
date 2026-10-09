"""Guide `LISEZMOI.md` du kit hors ligne Linux (KIT4-16), généré à la fabrication.

Le guide est rendu depuis le modèle versionné `tools/dist/templates/LISEZMOI-linux.md`, le manifeste du kit et les
constantes de l'installateur (`tools/dist/linux_install.py`) : aucune valeur du kit n'est écrite ici. Chaque procédure
renvoie à la section canonique d'un document de `docs/` livré dans le kit, retrouvée par son titre ; le lien porte l'ancre
que GitHub et `tools/docs/check_docs.py` calculent pour ce titre. Une section absente arrête le rendu : le guide ne publie
jamais un lien sans cible.

Le modèle décrit aussi des comportements de l'installateur qui ne sont pas des constantes : modules ajoutés et entrées du
dossier de l'interpréteur qu'`installer.sh` refuse, refus de type (lien, dossier, fichier spécial) et de droits, outils pris
dans des dossiers fixes du système, action d'un refus dans un kit ou dans un programme installé, ce qui s'exécute avant d'être
haché, et le modèle de menace, écrit tel quel comme dans l'en-tête d'`install.sh` (la vérification protège de l'altération
accidentelle, pas d'une personne qui peut écrire dans le kit ; `installer.sh` ne repose que sur l'empreinte de l'archive).
`tests/unit/test_dist_kit_guide.py` les confronte à `install.sh` et à `linux_install.py` réels.

Bibliothèque standard seule au chargement : le module est livré dans `tools/dist`. `tools.docs.check_docs` (ancres) et
`tools.dist.linux_install` (constantes) ne sont importés qu'au rendu, exécuté par le fabricant dans le dépôt.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from typing import Any

TEMPLATE = "tools/dist/templates/LISEZMOI-linux.md"
# Noms des fichiers du kit que le guide cite, fournis par le fabricant (linux_kit) : une seule source.
FILE_KEYS = ("guide", "manifest", "sums", "links", "executables", "notices", "installer")
PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
GIB = 1024**3
# Sections canoniques du kit Linux (KIT4-15) : clé du modèle → document livré et titre, sans son numéro. `reparation` : procédure
# de la section 10.4 du dépannage, que citent les refus d'`installer.sh` dans un programme installé et `linux_install.py`.
SECTIONS = {
    "deploiement": ("docs/deploiement/DEPLOIEMENT.md", "Kit hors ligne Linux"),
    "lanceur": ("docs/exploitation/EXPLOITATION.md", "Lanceur atelier et menu"),
    "depannage": ("docs/exploitation/DEPANNAGE.md", "Installateur et lanceur Linux"),
    "reparation": ("docs/exploitation/DEPANNAGE.md", "Réparer un programme installé avec le seul kit de sa version"),
    "sauvegarde": ("docs/exploitation/SAUVEGARDE-RESTAURATION.md", "Sauvegarder"),
}
# Constantes de l'installateur reprises par le guide (emplacements, noms, codes de sortie, réserve de place des données que
# le précontrôle ajoute quand programme et données partagent un volume, actions du lanceur, lanceur de la destination et
# dossier de la commande de l'utilisateur, paquets où une mise à jour refuse un module ajouté).
INSTALLER_CONSTANTS = ("USER_COMMAND", "MENU_NAME", "DEFAULT_FOLDER", "PROGRAM_FOLDER", "DATA_FOLDER", "EXIT_CODES",
                       "DATA_MIN_FREE_BYTES", "LAUNCHER_ACTIONS", "LAUNCHER", "DEFAULT_LOCATIONS", "PRE_COPY_PACKAGES")
# Fichiers qu'une mise à jour refuse dans chaque dossier de PRE_COPY_PACKAGES s'ils sont absents de SHA256SUMS, au sens du
# shell : bytecode sans source, module compilé (chargé avant le .py du même nom), `__init__` d'un dossier de paquet (trouvé
# avant le module du même nom). Ce sont ceux de linux_install.added_compiled_modules, confrontée à cette liste par les tests.
UPDATE_REFUSED_FORMS = ("*.pyc", "*.so", "*/__init__.py", "*/__init__.pyc", "*/__init__.so", "*/__init__.*.so")
# Action du lanceur présentée dans sa propre rubrique (« Changer de modèle »), hors de la liste des premiers pas.
MODEL_ACTION = "modele"
NUMBERING = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
# Taille maximale d'un fichier sur FAT32 : 4 Gio (Microsoft Learn, « File System Functionality Comparison », Limits) ;
# l'archive, plus grande que le kit, la dépasse dès que le kit l'atteint.
FAT32_FILE_MAX = 4 * GIB


class GuideError(ValueError):
    """Rendu impossible : section canonique absente, constante de l'installateur absente ou modèle incomplet."""


def heading_key(text: str) -> str:
    """Titre comparable : sans numéro, sans balises de code, espaces réduits, casse ignorée."""
    return " ".join(NUMBERING.sub("", text.replace("`", "").strip()).split()).casefold()


def document_anchors(text: str) -> dict[str, str]:
    """Titre comparable → ancre, comme `check_docs.anchors` (doublons suffixés -1, -2…), premier titre retenu."""
    from tools.docs.check_docs import HEADING, slug, split_code

    prose, _ = split_code(text)
    seen: dict[str, int] = {}
    found: dict[str, str] = {}
    for _, line in prose:
        match = HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        found.setdefault(heading_key(match.group(2)), base if count == 0 else f"{base}-{count}")
    return found


def section_links(documents: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Lien de chaque section canonique (`docs/…md#ancre`) et sections absentes, nommées par document et titre."""
    links: dict[str, str] = {}
    missing: list[str] = []
    for key, (path, title) in SECTIONS.items():
        anchor = document_anchors(documents[path]).get(heading_key(title)) if path in documents else None
        if anchor is None:
            missing.append(f"{path} « {title} »")
        else:
            links[key] = f"{path}#{anchor}"
    return links, missing


def installer_constants(installer: Any = None) -> dict[str, Any]:
    """Constantes publiques de l'installateur ; `installer` : module ou objet qui les porte (linux_install par défaut)."""
    if installer is None:
        from tools.dist import linux_install as installer
    absent = [name for name in INSTALLER_CONSTANTS if not hasattr(installer, name)]
    if absent:
        raise GuideError(f"constantes absentes de tools/dist/linux_install.py : {', '.join(absent)}")
    return {name: getattr(installer, name) for name in INSTALLER_CONSTANTS}


def gib(value: int) -> str:
    """Taille en Gio arrondie au dixième supérieur, virgule décimale."""
    return f"{math.ceil(value * 10 / GIB) / 10:.1f}".replace(".", ",") + " Gio"


def models_text(manifest: dict[str, Any]) -> str:
    default = manifest["default_model"]
    labels = sorted(manifest.get("model_profiles") or {default: ""}, key=lambda label: (label != default, label))
    return ", ".join(f"`{label}`" + (" (par défaut)" if label == default else "") for label in labels)


def switch_model_text(manifest: dict[str, Any], command: str, actions: dict[str, str], lanceur: str) -> str:
    """Rubrique « Changer de modèle » : changement durable si le lanceur a l'action `modele` (`actions` : LAUNCHER_ACTIONS de
    l'installateur), puis ouverture avec un autre modèle ; mêmes commandes que le bloc de fin de l'installateur
    (`usage_rows`). `lanceur` : lien de la section canonique du lanceur."""
    default = manifest["default_model"]
    others = sorted(label for label in manifest.get("model_profiles") or {} if label != default)
    if not others:
        return f"Ce kit ne livre que le modèle `{default}`."
    lines = [f"Le modèle par défaut est `{default}`."]
    if MODEL_ACTION in actions:
        lines[0] += " Pour qu'un autre modèle livré devienne durablement le modèle principal de l'installation :"
        lines += ["", "```sh", *(f"{command} modele {label}" for label in others), "```", "",
                  f"Aucun fichier de profil n'est modifié ; `{command} modele {default}` rétablit le modèle par défaut. Si l'atelier "
                  "tourne avec un autre modèle, la commande refuse le changement ; dans un terminal, elle propose de l'arrêter d'abord.",
                  "", "Pour une seule ouverture avec un autre modèle, arrêter d'abord l'atelier :"]
    else:
        lines[0] += " Pour ouvrir l'atelier avec un autre modèle livré, l'arrêter d'abord :"
    lines += ["", "```sh", f"{command} arreter", *(f"{command} ouvrir --modele {label}" for label in others), "```", "",
              f"L'option vaut pour l'ouverture où elle figure : sans elle, `{command} ouvrir` reprend l'atelier déjà démarré, ou à "
              f"défaut le modèle principal de l'installation. Actions et options du lanceur : [Lanceur atelier et menu]({lanceur})."]
    return "\n".join(lines)


def launcher_commands(command: str, actions: dict[str, str]) -> str:
    """Commandes des premiers pas : une ligne par action du lanceur (LAUNCHER_ACTIONS), sauf le changement de modèle."""
    return "\n".join(f"{command} {action}" for action in actions if action != MODEL_ACTION)


def user_bin(locations: dict[str, str]) -> str:
    """Dossier de la commande de l'utilisateur (DEFAULT_LOCATIONS de l'installateur), `$HOME` écrit `~`."""
    folder = locations["commande"].rsplit("/", 1)[0]
    return "~" + folder[len("$HOME"):] if folder.startswith("$HOME") else folder


def update_refusals(packages: tuple[str, ...]) -> str:
    """Fichiers ajoutés qu'une mise à jour refuse avant la dérivation des profils du nouveau kit (UPDATE_REFUSED_FORMS)."""
    return ", ".join(f"`{package}/{form}`" for package in packages for form in UPDATE_REFUSED_FORMS)


def gpu_text(gpu: dict[str, Any], command: str) -> str:
    """Calcul de la génération selon les bibliothèques GPU d'Ollama livrées (`gpu` du manifeste)."""
    libraries = gpu.get("ollama_libraries") or []
    if not libraries:
        return "sur CPU ; aucune bibliothèque GPU d'Ollama n'est livrée"
    where = f", pour Jetson Linux R{gpu['requires_l4t_major']}" if gpu.get("requires_l4t_major") else ""
    names = ", ".join(f"`{name}`" for name in libraries)
    return (f"bibliothèques GPU d'Ollama livrées ({names}){where} ; l'emploi du GPU est décidé au démarrage et `{command} diagnostic` "
            "l'indique, sinon la génération se fait sur CPU")


def tools_text(target: dict[str, Any]) -> str:
    projects: dict[str, list[str]] = {}
    for item in target.get("tools") or []:
        projects.setdefault(item["project"], []).append(f"`{item['name']}`")
    return " ; ".join(f"{project} ({', '.join(names)})" for project, names in projects.items()) or "aucun déclaré"


def libraries_text(target: dict[str, Any]) -> str:
    packages = target.get("system_packages") or {}
    users = target.get("system_libraries_required_by") or {}
    rows = ["| Bibliothèque | Composant | Paquet du système de fabrication |", "|---|---|---|"]
    for name in target.get("system_libraries") or []:
        record = packages.get(name) or {}
        component = record.get("component") or ", ".join(users.get(name, [])[:1]) or "kit"
        package = f"`{record['package']}`" if record.get("package") else "à identifier"
        rows.append(f"| `{name}` | {component} | {package} |")
    return "\n".join(rows) if len(rows) > 2 else "Aucune bibliothèque du système n'est requise."


def optional_libraries_text(target: dict[str, Any]) -> str:
    optional = target.get("optional_system_libraries") or {}
    if not optional:
        return ""
    items = " ; ".join(f"`{name}`, {reason}" for name, reason in optional.items())
    return f"\n- Facultatives, signalées sans bloquer l'installation : {items}.\n"


def qualification_text(target: dict[str, Any]) -> str:
    if target.get("installation_qualified"):
        return f"qualifiée par une recette réelle : {target.get('installation_qualification_proof')}"
    return "aucune installation réelle de ce kit n'est encore qualifiée ; le système de référence est celui de la fabrication"


def render(manifest: dict[str, Any], *, template: str, documents: dict[str, str], files: dict[str, str],
           installer: Any = None) -> str:
    """Guide du kit. `documents` : textes des documents de `docs/` livrés ; `files` : noms des fichiers du kit que le guide
    cite (FILE_KEYS), tels que le fabricant les écrit ; `installer` : module des constantes (linux_install par défaut)."""
    links, missing = section_links(documents)
    if missing:
        raise GuideError("sections canoniques absentes des documents du kit : " + ", ".join(missing))
    absent = [key for key in FILE_KEYS if not files.get(key)]
    if absent:
        raise GuideError(f"noms de fichiers du kit non fournis : {', '.join(absent)}")
    constants = installer_constants(installer)
    target = manifest["target"]
    command = constants["USER_COMMAND"]
    requirements = manifest["requirements"]
    built = dt.datetime.fromisoformat(manifest["built_utc"]).astimezone(dt.UTC).date().isoformat()
    folder = f"~/.local/share/{constants['DEFAULT_FOLDER']}"
    kit_bytes = int(requirements["kit_bytes"])
    install_bytes, data_reserve = int(requirements["install_bytes_min"]), int(constants["DATA_MIN_FREE_BYTES"])
    values = {
        "version": manifest["version"], "kit_id": manifest["kit_id"], "commit": manifest["commit"], "commit_short": manifest["commit"][:12],
        "built_date": built, "arch": target["arch"], "models": models_text(manifest),
        "gpu": gpu_text(manifest["gpu"], command), "kit_size": gib(kit_bytes),
        "install_size": gib(install_bytes), "install_shared_size": gib(install_bytes + data_reserve), "data_reserve": gib(data_reserve),
        "reference_os": target.get("reference_os") or "non déclaré",
        "qualification": qualification_text(target), "notices_file": files["notices"],
        "notices_usage": manifest["notices"]["usage"], "glibc_min": target["glibc_min"], "kernel_min": target["kernel_min"],
        "memory_gib_min": str(requirements["memory_gib_min"]),
        "glibcxx": f", libstdc++ fournissant GLIBCXX_{target['glibcxx_min']}" if target.get("glibcxx_min") else "",
        "tools": tools_text(target), "observed_on": next((item.get("observed_on") for item in (target.get("system_packages") or {}).values()
                                                         if item.get("observed_on")), "non relevé"),
        "libraries": libraries_text(target), "optional_libraries": optional_libraries_text(target),
        "transport": ("l'archive dépasse 4 Gio, taille maximale d'un fichier sur FAT32 : la transporter sur un support exFAT, NTFS "
                      "ou ext4. " if kit_bytes >= FAT32_FILE_MAX else ""),
        "symlinks": str(manifest["symlinks"]), "installer": files["installer"],
        "default_program": f"{folder}/{constants['PROGRAM_FOLDER']}", "default_data": f"{folder}/{constants['DATA_FOLDER']}",
        "menu_name": constants["MENU_NAME"], "user_command": command, "launcher": constants["LAUNCHER"],
        "launcher_commands": launcher_commands(command, constants["LAUNCHER_ACTIONS"]),
        "user_bin": user_bin(constants["DEFAULT_LOCATIONS"]), "update_refusals": update_refusals(tuple(constants["PRE_COPY_PACKAGES"])),
        "switch_model": switch_model_text(manifest, command, constants["LAUNCHER_ACTIONS"], links["lanceur"]),
        "exit_codes": "\n".join(f"| {code} | {meaning} |" for code, meaning in sorted(constants["EXIT_CODES"].items())),
        "guide_file": files["guide"], "manifest_file": files["manifest"], "sums_file": files["sums"], "links_file": files["links"],
        "executables_file": files["executables"],
        **{f"link_{key}": link for key, link in links.items()},
    }
    unknown = sorted({match.group(1) for match in PLACEHOLDER.finditer(template)} - set(values))
    if unknown:
        raise GuideError(f"emplacements sans valeur dans {TEMPLATE} : {', '.join(unknown)}")
    rendered = PLACEHOLDER.sub(lambda match: str(values[match.group(1)]), template)
    if "{{" in rendered or "}}" in rendered:
        raise GuideError(f"emplacement mal formé dans {TEMPLATE}")
    return rendered


def commands(guide: str) -> list[str]:
    """Lignes des blocs `sh` du guide : chaque commande que le lecteur peut taper."""
    found, active = [], False
    for line in guide.splitlines():
        if line.startswith("```"):
            active = line.strip() == "```sh"
            continue
        if active and line.strip():
            found.append(line.strip())
    return found
