"""One authorized native build with sampled host/process resources; no browser.

Node (W018) : l'exécutable désigné par la variable RAG_WEB_NODE ; à défaut, sous Windows seulement,
D:/node/node-v22.17.0-win-x64/node.exe s'il existe (repli historique du poste Windows de qualification,
propre à ce poste) ; à défaut, le node du PATH. pnpm passe par le Corepack livré avec ce Node (dist/pnpm.js), à la version fixée
par le champ packageManager de package.json. Le build s'exécute sans réseau (COREPACK_ENABLE_NETWORK=0) :
avant d'écrire la moindre preuve, le script vérifie que Corepack lance cette version depuis son cache,
et sinon s'arrête en donnant la commande `corepack install` à exécuter une fois avec réseau.
La version de ce Node (`node --version`, lancé comme la sonde pnpm) est lue avant toute preuve, puis consignée
dans le premier relevé de ressources et dans le résumé JSON (`node_version`) ; si elle manque, le message d'arrêt
nomme la provenance de ce Node (RAG_WEB_NODE, repli Windows du poste de qualification ou PATH) et l'action à mener.
Preuves (journal, relevés de ressources, manifeste de l'export) dans reports/, suivi par Git, ou dans le dossier donné
par --evidence-dir, créé après les sondes, pour garder hors de Git les preuves d'une campagne.
Lancer avec l'interpréteur du projet (Python 3.12).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NamedTuple

import psutil

# Repli historique du poste Windows de qualification (Node 22.17.0) : employé seulement sans RAG_WEB_NODE.
WINDOWS_NODE = Path("D:/node/node-v22.17.0-win-x64/node.exe")
NODE_VARIABLE = "RAG_WEB_NODE"
PACKAGE_MANAGER = re.compile(r"pnpm@(\d+\.\d+\.\d+)(?:\+sha\d+\.[0-9a-f]+)?")
# Forme de `node --version` : v<majeure>.<mineure>.<correctif>, suffixe de préversion admis (v24.0.0-rc.1).
NODE_VERSION = re.compile(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?")
# Délai de chaque sonde lancée avant le build (node --version, pnpm --version).
PROBE_TIMEOUT_SECONDS = 120
# Provenance du Node retenu : RAG_WEB_NODE, repli WINDOWS_NODE ou PATH.
NodeOrigin = Literal["variable", "windows_fallback", "path"]


class Toolchain(NamedTuple):
    """Node retenu, pnpm.js de son Corepack et provenance de ce Node, que cite l'échec de la sonde Node."""
    node: Path
    corepack: Path
    origin: NodeOrigin


def resolve_toolchain(environ: Mapping[str, str] = os.environ, platform: str = sys.platform,
                      which: Callable[[str], str | None] = shutil.which) -> Toolchain:
    """Exécutable node, pnpm.js de son Corepack et provenance du node, ou SystemExit qui dit quoi fournir.

    Ordre : RAG_WEB_NODE s'il est renseigné (sans repli s'il désigne un fichier absent) ; sous Windows,
    WINDOWS_NODE s'il existe ; le node du PATH.
    """
    declared = environ.get(NODE_VARIABLE)
    origin: NodeOrigin
    if declared:
        node, origin = Path(declared).resolve(), "variable"
        if not node.is_file():
            raise SystemExit(f"{NODE_VARIABLE} désigne {declared}, introuvable : corriger la variable ou la retirer")
    elif platform == "win32" and WINDOWS_NODE.is_file():
        node, origin = WINDOWS_NODE, "windows_fallback"
    else:
        found = which("node")
        if not found:
            raise SystemExit(f"node introuvable : renseigner {NODE_VARIABLE} ou placer node dans le PATH")
        node, origin = Path(found).resolve(), "path"
    # Corepack est livré à côté de node.exe sous Windows, dans lib/node_modules sous Linux.
    layouts = (node.parent / "node_modules/corepack/dist/pnpm.js",
               node.parent.parent / "lib/node_modules/corepack/dist/pnpm.js")
    corepack = next((path for path in layouts if path.is_file()), None)
    if not node.is_file() or corepack is None:
        raise SystemExit(f"Node ou Corepack absent : {node} ; pnpm.js cherché dans {', '.join(map(str, layouts))}")
    return Toolchain(node, corepack, origin)


def no_window() -> int:
    """Indicateur de création de processus : aucune console ouverte sous Windows."""
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def pinned_pnpm(web: Path) -> str:
    """Version de pnpm fixée par le champ packageManager de package.json."""
    declared = json.loads((web / "package.json").read_text(encoding="utf-8")).get("packageManager")
    match = PACKAGE_MANAGER.fullmatch(declared) if isinstance(declared, str) else None
    if match is None:
        raise SystemExit(f"{web / 'package.json'} : packageManager attendu sous la forme pnpm@<version>+sha512.<empreinte>, lu {declared!r}")
    return match.group(1)


def corepack_install_command(node: Path, corepack: Path, web: Path, platform: str = sys.platform) -> str:
    """Commande unique à exécuter avec réseau : `corepack install` du même Node, dans le dossier du projet."""
    corepack_js = corepack.with_name("corepack.js")
    if platform == "win32":
        return f'Set-Location -LiteralPath "{web}"; & "{node}" "{corepack_js}" install'
    return f'cd "{web}" && "{node}" "{corepack_js}" install'


def probe_options(web: Path, environment: Mapping[str, str]) -> dict:
    """Options communes des sondes lancées avant le build : dossier du projet, environnement du build, délai borné."""
    return {"cwd": web, "env": dict(environment), "capture_output": True, "text": True, "encoding": "utf-8",
            "errors": "replace", "timeout": PROBE_TIMEOUT_SECONDS, "creationflags": no_window()}


def node_origin_advice(origin: NodeOrigin) -> str:
    """Provenance du Node retenu et action qui la corrige, pour l'échec de la sonde Node."""
    if origin == "variable":
        return f"Ce Node est désigné par {NODE_VARIABLE} : corriger la variable ou la retirer, puis relancer ce build."
    if origin == "windows_fallback":
        return (f"Ce Node est le repli Windows propre au poste de qualification, employé faute de {NODE_VARIABLE} : "
                f"désigner un exécutable Node valide par {NODE_VARIABLE}, prioritaire sur ce repli, puis relancer ce build.")
    return (f"Ce Node est celui du PATH, employé faute de {NODE_VARIABLE} : désigner un exécutable Node valide par "
            f"{NODE_VARIABLE}, prioritaire sur le PATH, ou corriger le node du PATH, puis relancer ce build.")


def probe_node_version(node: Path, web: Path, environment: Mapping[str, str],
                       run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run, *, origin: NodeOrigin,
                       evidence: str = "reports/") -> str:
    """Version de Node rendue par `node --version`, ou SystemExit avant toute preuve écrite.

    `origin` est la provenance rendue par resolve_toolchain : le message d'arrêt donne l'action qui lui correspond.
    `evidence` est le dossier des preuves que cite ce message.
    """
    code: int | None = None
    try:
        result = run([str(node), "--version"], **probe_options(web, environment))
    except subprocess.TimeoutExpired:
        reason = f"aucune réponse en {PROBE_TIMEOUT_SECONDS} s"
    except OSError as error:
        reason = f"lancement impossible ({error})"
    else:
        code, found = result.returncode, result.stdout.strip()
        if code == 0 and NODE_VERSION.fullmatch(found):
            return found
        lines = (result.stderr or result.stdout).strip().splitlines()
        reason = (f"sortie {found!r} au lieu de v<majeure>.<mineure>.<correctif>" if code == 0
                  else (lines[-1] if lines else "aucune sortie"))
    raise SystemExit(
        f"{node} --version n'a pas donné la version de Node{f' (code {code})' if code is not None else ''} : {reason}\n"
        f"La preuve du build consigne cette version ; rien n'a été écrit dans {evidence}.\n"
        + node_origin_advice(origin)
    )


def check_offline_pnpm(node: Path, corepack: Path, web: Path, environment: Mapping[str, str],
                       platform: str = sys.platform, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
                       *, evidence: str = "reports/") -> str:
    """Version de pnpm lancée sans réseau par Corepack, ou SystemExit qui donne la commande à exécuter.

    `evidence` est le dossier des preuves que cite le message d'arrêt.
    """
    expected = pinned_pnpm(web)
    code: int | None = None
    try:
        result = run([str(node), str(corepack), "--version"], **probe_options(web, environment))
    except subprocess.TimeoutExpired:
        reason = f"aucune réponse de Corepack en {PROBE_TIMEOUT_SECONDS} s"
    else:
        code, found = result.returncode, result.stdout.strip()
        if code == 0 and found == expected:
            return found
        lines = (result.stderr or result.stdout).strip().splitlines()
        reason = f"version {found or 'non communiquée'} au lieu de {expected}" if code == 0 else (lines[-1] if lines else "aucune sortie")
    raise SystemExit(
        f"pnpm {expected}, fixé par packageManager dans {web / 'package.json'}, n'a pas pu être lancé sans réseau par Corepack"
        f"{f' (code {code})' if code is not None else ''} : {reason}\n"
        f"Le build s'exécute hors ligne (COREPACK_ENABLE_NETWORK=0) ; rien n'a été écrit dans {evidence}.\n"
        "Exécuter une fois, avec accès réseau :\n"
        f"    {corepack_install_command(node, corepack, web, platform)}\n"
        f"Corepack télécharge alors pnpm {expected}, vérifie son empreinte et le garde dans son cache (COREPACK_HOME, par défaut "
        "%LOCALAPPDATA%\\node\\corepack sous Windows, ~/.cache/node/corepack ailleurs) ; relancer ensuite ce build."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--evidence-dir", type=Path,
                        help="dossier des preuves du build, créé après les sondes de Node et de pnpm s'il manque ; "
                             "par défaut apps/web/reports/, suivi par Git")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]{1,90}", args.tag):
        parser.error("Use a unique simple evidence tag")
    web = Path(__file__).resolve().parents[1]
    if args.evidence_dir is None:
        evidence, shown = web / "reports", "reports/"
    else:
        evidence = args.evidence_dir.resolve()
        shown = str(evidence)
        # Le manifeste parcourt out/ et le build le régénère : des preuves placées dessous s'y mêleraient.
        if evidence.is_relative_to(web / "out"):
            parser.error(f"--evidence-dir {evidence} : dossier dans out/, que le build régénère ; choisir un dossier hors de "
                         f"{web / 'out'}")
        # Refus avant les sondes : mkdir, après elles, échouerait sur un fichier (le dossier lui-même ou un parent).
        existing = next((path for path in (evidence, *evidence.parents) if path.exists()), None)
        if existing is not None and not existing.is_dir():
            parser.error(f"--evidence-dir {evidence} : {existing} existe et n'est pas un dossier ; choisir un dossier existant "
                         "ou à créer")
    node, corepack, origin = resolve_toolchain()
    log = evidence / f"build-{args.tag}.log"
    resources = evidence / f"build-{args.tag}-resources.jsonl"
    manifest = evidence / f"export-manifest-{args.tag}.json"
    if any(path.exists() for path in (log, resources, manifest)):
        raise SystemExit("Preserve the existing evidence; choose a new tag")
    environment = os.environ.copy()
    environment.update(NEXT_TELEMETRY_DISABLED="1", COREPACK_ENABLE_NETWORK="0", NODE_OPTIONS="--max-old-space-size=2048", FORCE_COLOR="0")
    environment.pop("NO_COLOR", None)
    environment["PATH"] = str(node.parent) + os.pathsep + environment.get("PATH", "")
    # Avant toute preuve : la version de Node consignée, puis pnpm, dont l'absence du cache de Corepack
    # ferait échouer le build hors ligne.
    node_version = probe_node_version(node, web, environment, origin=origin, evidence=shown)
    pnpm_version = check_offline_pnpm(node, corepack, web, environment, evidence=shown)
    evidence.mkdir(parents=True, exist_ok=True)
    psutil.cpu_percent(interval=0.2)

    def sample(phase, process=None):
        children = []
        if process:
            try:
                candidates = [process] + process.children(recursive=True)
            except psutil.Error:
                candidates = []
            for child in candidates:
                try:
                    with child.oneshot():
                        memory = child.memory_info()
                        children.append({"id": child.pid, "parent_id": child.ppid(), "name": child.name(), "rss_mib": round(memory.rss / 1048576, 1), "private_mib": round(memory.private / 1048576, 1) if hasattr(memory, "private") else None})
                except psutil.Error:
                    pass
        return {"timestamp_utc": datetime.now(UTC).isoformat(), "phase": phase, "host_available_mib": round(psutil.virtual_memory().available / 1048576, 1), "host_cpu_percent": psutil.cpu_percent(interval=None), "disk_free_bytes": psutil.disk_usage(str(web)).free, "owned_build_tree": children, "method": "Host/per-process snapshots about every 2 seconds; no summed RSS, continuous peak or 30-minute qualification claim"}

    started = time.monotonic()
    with resources.open("x", encoding="utf-8") as samples, log.open("xb") as output:
        def record(value):
            samples.write(json.dumps(value, ensure_ascii=True) + "\n")
            samples.flush()
        record({**sample("before"), "node_version": node_version})
        build = subprocess.Popen([str(node), str(corepack), "build"], cwd=web, env=environment, stdout=output, stderr=subprocess.STDOUT, creationflags=no_window())
        owned = psutil.Process(build.pid)
        while build.poll() is None:
            record(sample("during", owned))
            time.sleep(2)
        code = build.wait()
        record({**sample("after"), "exit_code": code, "elapsed_seconds": round(time.monotonic() - started, 2)})
    if code == 0:
        entries = []
        for path in sorted((web / "out").rglob("*")):
            if path.is_file():
                entries.append({"path": path.relative_to(web / "out").as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest.write_text(json.dumps({"status": "BUILD_EXIT_0_STATIC_EXPORT", "files": len(entries), "total_bytes": sum(entry["bytes"] for entry in entries), "entries": entries}, indent=2), encoding="utf-8")
    print(json.dumps({"exit_code": code, "elapsed_seconds": round(time.monotonic() - started, 2), "node": str(node), "node_version": node_version, "pnpm_js": str(corepack), "pnpm": pnpm_version, "log": str(log), "resources": str(resources), "manifest": str(manifest) if code == 0 else None}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
