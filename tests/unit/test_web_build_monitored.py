"""apps/web/scripts/build-monitored.py : résolution de Node selon la plateforme (W018), sondes de Node et de pnpm
avant toute preuve, version de Node consignée dans la preuve du build."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "apps" / "web" / "scripts" / "build-monitored.py"


@pytest.fixture()
def script(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("build_monitored", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Le chemin historique du poste Windows n'existe pas dans le test, sauf si le cas le crée.
    monkeypatch.setattr(module, "WINDOWS_NODE", tmp_path / "absent" / "node.exe")
    return module


def posix_node(root: Path) -> tuple[Path, Path]:
    node = root / "bin" / "node"
    pnpm = root / "lib" / "node_modules" / "corepack" / "dist" / "pnpm.js"
    for path in (node, pnpm):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return node, pnpm


def windows_node(root: Path) -> tuple[Path, Path]:
    node = root / "node.exe"
    pnpm = root / "node_modules" / "corepack" / "dist" / "pnpm.js"
    for path in (node, pnpm):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return node, pnpm


def test_linux_uses_node_from_path_and_its_corepack(script, tmp_path):
    node, pnpm = posix_node(tmp_path / "nvm")
    assert script.resolve_toolchain({}, "linux", lambda name: str(node) if name == "node" else None) == (node.resolve(), pnpm, "path")


def test_documented_variable_wins_over_path(script, tmp_path):
    chosen, pnpm = posix_node(tmp_path / "choisi")
    other, _ = posix_node(tmp_path / "autre")
    environ = {script.NODE_VARIABLE: str(chosen)}
    assert script.resolve_toolchain(environ, "linux", lambda name: str(other)) == (chosen.resolve(), pnpm, "variable")


def test_windows_variable_wins_over_the_historical_node(script, monkeypatch, tmp_path):
    historical, _ = windows_node(tmp_path / "node-v22.17.0-win-x64")
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    chosen, pnpm = windows_node(tmp_path / "choisi")
    other, _ = windows_node(tmp_path / "path")
    assert script.resolve_toolchain({script.NODE_VARIABLE: str(chosen)}, "win32", lambda name: str(other)) == (chosen.resolve(), pnpm, "variable")


def test_windows_without_variable_keeps_the_historical_node_before_path(script, monkeypatch, tmp_path):
    historical, pnpm = windows_node(tmp_path / "node-v22.17.0-win-x64")
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    other, _ = windows_node(tmp_path / "path")
    assert script.resolve_toolchain({}, "win32", lambda name: str(other)) == (historical, pnpm, "windows_fallback")
    # Une variable vide ne désigne rien : le repli historique s'applique.
    assert script.resolve_toolchain({script.NODE_VARIABLE: ""}, "win32", lambda name: str(other)) == (historical, pnpm, "windows_fallback")


def test_the_historical_node_is_never_used_outside_windows(script, monkeypatch, tmp_path):
    historical, _ = windows_node(tmp_path / "node-v22.17.0-win-x64")
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    node, pnpm = posix_node(tmp_path / "nvm")
    assert script.resolve_toolchain({}, "linux", lambda name: str(node)) == (node.resolve(), pnpm, "path")


def test_a_variable_naming_a_missing_node_is_refused_without_fallback(script, monkeypatch, tmp_path):
    historical, _ = windows_node(tmp_path / "node-v22.17.0-win-x64")
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    with pytest.raises(SystemExit, match="RAG_WEB_NODE"):
        script.resolve_toolchain({script.NODE_VARIABLE: str(tmp_path / "absent" / "node.exe")}, "win32", lambda name: None)


def test_windows_without_historical_node_falls_back_to_path(script, tmp_path):
    node, pnpm = windows_node(tmp_path / "nodejs")
    assert script.resolve_toolchain({}, "win32", lambda name: str(node)) == (node.resolve(), pnpm, "path")


def test_missing_node_or_corepack_is_refused_with_the_action(script, tmp_path):
    with pytest.raises(SystemExit, match="RAG_WEB_NODE"):
        script.resolve_toolchain({}, "linux", lambda name: None)
    bare = tmp_path / "nu" / "bin" / "node"
    bare.parent.mkdir(parents=True)
    bare.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="Corepack absent"):
        script.resolve_toolchain({}, "linux", lambda name: str(bare))


# --- pnpm hors ligne (COREPACK_ENABLE_NETWORK=0) : vérification préalable, avant toute preuve écrite ---

PINNED = "pnpm@10.34.1+sha512." + "b" * 128


def web_with(root: Path, package_manager) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    package = {"name": "web"} if package_manager is None else {"name": "web", "packageManager": package_manager}
    (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
    return root


def fake_run(code: int, stdout: str = "", stderr: str = ""):
    calls = []

    def run(argv, **options):
        calls.append((argv, options))
        return subprocess.CompletedProcess(argv, code, stdout, stderr)
    return run, calls


def test_pinned_version_is_read_from_package_manager(script, tmp_path):
    assert script.pinned_pnpm(web_with(tmp_path / "ok", PINNED)) == "10.34.1"
    assert script.pinned_pnpm(web_with(tmp_path / "nohash", "pnpm@10.34.1")) == "10.34.1"
    for name, value in (("absent", None), ("yarn", "yarn@4.5.0"), ("range", "pnpm@^10")):
        with pytest.raises(SystemExit, match="packageManager attendu"):
            script.pinned_pnpm(web_with(tmp_path / name, value))


def test_cached_pnpm_passes_offline_with_the_build_environment(script, tmp_path):
    web = web_with(tmp_path / "web", PINNED)
    run, calls = fake_run(0, "10.34.1\n")
    environment = {"COREPACK_ENABLE_NETWORK": "0", "PATH": "/bin"}
    node, pnpm = Path("/n/node"), Path("/n/dist/pnpm.js")
    assert script.check_offline_pnpm(node, pnpm, web, environment, "linux", run) == "10.34.1"
    argv, options = calls[0]
    # str() du chemin : barres obliques inverses quand la suite tourne sous Windows.
    assert argv == [str(node), str(pnpm), "--version"]
    assert options["cwd"] == web and options["env"]["COREPACK_ENABLE_NETWORK"] == "0" and options["timeout"] == 120


def test_missing_cache_stops_with_the_single_install_command(script, tmp_path):
    web = web_with(tmp_path / "web", PINNED)
    offline = "Network access disabled by the environment; can't reach https://registry.npmjs.org/pnpm/-/pnpm-10.34.1.tgz"
    run, _ = fake_run(1, "", "! Corepack is about to download https://registry.npmjs.org/pnpm/-/pnpm-10.34.1.tgz\n" + offline + "\n")
    node, pnpm = Path("D:/node/node-v22.17.0-win-x64/node.exe"), Path("D:/node/node-v22.17.0-win-x64/node_modules/corepack/dist/pnpm.js")
    with pytest.raises(SystemExit) as windows:
        script.check_offline_pnpm(node, pnpm, web, {}, "win32", run)
    message = str(windows.value)
    assert f"(code 1) : {offline}\n" in message
    assert "rien n'a été écrit dans reports/" in message
    assert f'    Set-Location -LiteralPath "{web}"; & "{node}" "{pnpm.with_name("corepack.js")}" install\n' in message
    assert "%LOCALAPPDATA%\\node\\corepack" in message
    with pytest.raises(SystemExit) as linux:
        script.check_offline_pnpm(Path("/n/bin/node"), Path("/n/lib/node_modules/corepack/dist/pnpm.js"), web, {}, "linux", run)
    node, corepack = Path("/n/bin/node"), Path("/n/lib/node_modules/corepack/dist/corepack.js")
    assert f'    cd "{web}" && "{node}" "{corepack}" install\n' in str(linux.value)


def test_wrong_version_or_silent_corepack_is_refused(script, tmp_path):
    web = web_with(tmp_path / "web", PINNED)
    run, _ = fake_run(0, "9.15.0\n")
    with pytest.raises(SystemExit, match=r"\(code 0\) : version 9\.15\.0 au lieu de 10\.34\.1"):
        script.check_offline_pnpm(Path("node"), Path("pnpm.js"), web, {}, "linux", run)

    def timeout(argv, **options):
        raise subprocess.TimeoutExpired(argv, options["timeout"])
    with pytest.raises(SystemExit, match="par Corepack : aucune réponse de Corepack en 120 s"):
        script.check_offline_pnpm(Path("node"), Path("pnpm.js"), web, {}, "linux", timeout)


def local_corepack():
    node = shutil.which("node")
    if not node:
        return None
    node_path = Path(node).resolve()
    for candidate in (node_path.parent / "node_modules/corepack/dist/pnpm.js", node_path.parent.parent / "lib/node_modules/corepack/dist/pnpm.js"):
        if candidate.is_file():
            return node_path, candidate
    return None


@pytest.mark.skipif(local_corepack() is None, reason="node et Corepack absents de ce poste")
def test_build_without_cached_pnpm_writes_no_evidence(tmp_path):
    """Script réel, Corepack réel, cache vide : arrêt avant le build, aucune preuve écrite, commande donnée."""
    web = tmp_path / "web"
    (web / "scripts").mkdir(parents=True)
    (web / "reports").mkdir()
    shutil.copy2(SCRIPT, web / "scripts" / SCRIPT.name)
    shutil.copy2(SCRIPT.parents[1] / "package.json", web / "package.json")
    node, _ = local_corepack()
    environment = {**os.environ, "COREPACK_HOME": str(tmp_path / "corepack-vide"), "RAG_WEB_NODE": str(node)}
    result = subprocess.run([sys.executable, str(web / "scripts" / SCRIPT.name), "--tag", "cache-vide"], env=environment,
                            capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert result.returncode == 1
    assert "Network access disabled by the environment" in result.stderr
    assert "corepack.js\" install" in result.stderr
    assert list((web / "reports").iterdir()) == []


# --- Version de Node consignée dans la preuve du build ---

def test_node_version_probe_runs_like_the_pnpm_probe(script, tmp_path):
    """`node --version` avec le même dossier, le même environnement, le même délai et les mêmes options."""
    web = web_with(tmp_path / "web", PINNED)
    environment = {"COREPACK_ENABLE_NETWORK": "0", "PATH": "/n/bin"}
    pnpm_run, pnpm_calls = fake_run(0, "10.34.1\n")
    node_run, node_calls = fake_run(0, "v24.16.0\n")
    node = Path("/n/bin/node")
    script.check_offline_pnpm(node, Path("/n/dist/pnpm.js"), web, environment, "linux", pnpm_run)
    assert script.probe_node_version(node, web, environment, node_run, origin="path") == "v24.16.0"
    argv, options = node_calls[0]
    assert argv == [str(node), "--version"]
    assert options == pnpm_calls[0][1]
    assert options["timeout"] == 120 and options["env"] == environment and options["env"] is not environment


@pytest.mark.parametrize("version", ["v22.13.0", "v24.16.0", "v24.0.0-rc.1"])
def test_node_release_versions_are_accepted(script, tmp_path, version):
    run, _ = fake_run(0, version + "\r\n")
    assert script.probe_node_version(Path("node"), tmp_path, {}, run, origin="path") == version


def test_node_version_failure_stops_before_any_evidence(script, tmp_path):
    def refused(code, stdout="", stderr=""):
        run, _ = fake_run(code, stdout, stderr)
        return run

    def timeout(argv, **options):
        raise subprocess.TimeoutExpired(argv, options["timeout"])

    def unlaunchable(argv, **options):
        raise OSError(8, "Exec format error")

    cases = (
        (refused(1, "", "node: bad option\n"), r"\(code 1\) : node: bad option"),
        (refused(0, "Python 3.12.14\n"), r"\(code 0\) : sortie 'Python 3\.12\.14' au lieu de v<majeure>\.<mineure>\.<correctif>"),
        (refused(0, ""), r"\(code 0\) : sortie '' au lieu de v<majeure>\.<mineure>\.<correctif>"),
        (timeout, r" : aucune réponse en 120 s"),
        (unlaunchable, r" : lancement impossible \(\[Errno 8\] Exec format error\)"),
    )
    for run, reason in cases:
        with pytest.raises(SystemExit, match=reason) as stopped:
            script.probe_node_version(Path("/n/bin/node"), tmp_path, {}, run, origin="path")
        message = str(stopped.value)
        assert message.startswith(f"{Path('/n/bin/node')} --version n'a pas donné la version de Node")
        assert "rien n'a été écrit dans reports/" in message
        assert "RAG_WEB_NODE" in message


def test_build_evidence_records_the_node_version(monkeypatch, tmp_path, capsys):
    """main() réel sur une copie du script : version de Node dans le premier relevé et dans le résumé JSON."""
    web = tmp_path / "web"
    (web / "scripts").mkdir(parents=True)
    reports = web / "reports"
    reports.mkdir()
    copy = web / "scripts" / SCRIPT.name
    shutil.copy2(SCRIPT, copy)
    spec = importlib.util.spec_from_file_location("build_monitored_copy", copy)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Build factice : l'interpréteur courant tient le rôle de node et écrit un export minimal.
    fake_pnpm = tmp_path / "fake-pnpm.py"
    fake_pnpm.write_text(
        "import pathlib, sys, time\n"
        "assert sys.argv[1:] == ['build']\n"
        "time.sleep(0.3)\n"
        "out = pathlib.Path('out')\n"
        "out.mkdir()\n"
        "(out / 'index.html').write_text('<!doctype html>', encoding='utf-8')\n",
        encoding="utf-8")
    node = Path(sys.executable)
    probes = []

    def node_probe(probed, probed_web, environment, *rest, origin):
        assert list(reports.iterdir()) == [], "la version de Node est lue avant toute preuve"
        assert origin == "variable", "la sonde reçoit la provenance rendue par resolve_toolchain"
        probes.append(("node", probed, probed_web, dict(environment)))
        return "v24.16.0"

    def pnpm_probe(probed, corepack, probed_web, environment, *rest):
        probes.append(("pnpm", probed, probed_web, dict(environment)))
        return "10.34.1"

    monkeypatch.setattr(module, "resolve_toolchain", lambda: module.Toolchain(node, fake_pnpm, "variable"))
    monkeypatch.setattr(module, "probe_node_version", node_probe)
    monkeypatch.setattr(module, "check_offline_pnpm", pnpm_probe)
    monkeypatch.setattr(sys, "argv", [str(copy), "--tag", "version-node"])
    assert module.main() == 0
    # Même exécutable, même dossier et même environnement que la sonde pnpm et le build.
    assert [entry[0] for entry in probes] == ["node", "pnpm"]
    assert probes[0][1:] == probes[1][1:]
    assert probes[0][3]["COREPACK_ENABLE_NETWORK"] == "0"
    assert probes[0][3]["PATH"].startswith(str(node.parent) + os.pathsep)
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["exit_code"] == 0 and summary["node"] == str(node)
    assert summary["node_version"] == "v24.16.0" and summary["pnpm"] == "10.34.1"
    lines = [json.loads(line) for line in (reports / "build-version-node-resources.jsonl").read_text(encoding="utf-8").splitlines()]
    assert lines[0]["phase"] == "before" and lines[0]["node_version"] == "v24.16.0"
    assert lines[-1]["phase"] == "after" and lines[-1]["exit_code"] == 0
    assert json.loads((reports / "export-manifest-version-node.json").read_text(encoding="utf-8"))["files"] == 1


# --- Provenance du Node retenu, citée par l'échec de la sonde Node ---

ADVICE = {
    "variable": "Ce Node est désigné par RAG_WEB_NODE : corriger la variable ou la retirer, puis relancer ce build.",
    "windows_fallback": ("Ce Node est le repli Windows propre au poste de qualification, employé faute de RAG_WEB_NODE : "
                         "désigner un exécutable Node valide par RAG_WEB_NODE, prioritaire sur ce repli, puis relancer ce build."),
    "path": ("Ce Node est celui du PATH, employé faute de RAG_WEB_NODE : désigner un exécutable Node valide par RAG_WEB_NODE, "
             "prioritaire sur le PATH, ou corriger le node du PATH, puis relancer ce build."),
}


@pytest.mark.parametrize("origin", sorted(ADVICE))
def test_node_probe_failure_names_where_the_node_comes_from(script, tmp_path, origin):
    run, _ = fake_run(1, "", "node: bad option\n")
    with pytest.raises(SystemExit) as stopped:
        script.probe_node_version(Path("/n/bin/node"), tmp_path, {}, run, origin=origin)
    message = str(stopped.value)
    assert message.endswith("\n" + ADVICE[origin])
    # Une seule provenance citée : pas de conseil sur le PATH pour un Node que le PATH n'a pas fourni.
    assert [text for key, text in ADVICE.items() if key != origin and text in message] == []
    if origin != "path":
        assert "node du PATH" not in message


def test_the_origin_given_to_the_probe_is_the_one_that_chose_the_node(script, monkeypatch, tmp_path):
    """Chaque branche de resolve_toolchain rend la provenance dont le message d'échec donne l'action."""
    historical, _ = windows_node(tmp_path / "node-v22.17.0-win-x64")
    chosen, _ = windows_node(tmp_path / "choisi")
    found, _ = windows_node(tmp_path / "path")
    assert script.resolve_toolchain({script.NODE_VARIABLE: str(chosen)}, "win32", lambda name: str(found)).origin == "variable"
    assert script.resolve_toolchain({}, "win32", lambda name: str(found)).origin == "path"
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    assert script.resolve_toolchain({}, "win32", lambda name: str(found)).origin == "windows_fallback"
    assert script.resolve_toolchain({}, "linux", lambda name: str(found)).origin == "path"


# --- Sous Windows, aucune sonde n'ouvre de console (CREATE_NO_WINDOW) ---

def test_windows_probes_pass_create_no_window(script, monkeypatch, tmp_path):
    """Plateforme win32 simulée : la sonde Node, comme celle de pnpm, reçoit CREATE_NO_WINDOW.

    Sous Linux, subprocess n'a pas cet attribut et no_window() vaut 0 : sans cette simulation, l'égalité des
    options des deux sondes ne prouverait rien sur Windows. La valeur posée est celle de Windows (0x08000000).
    """
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(script, "sys", SimpleNamespace(platform="win32"))
    assert script.no_window() == 0x08000000
    web = web_with(tmp_path / "web", PINNED)
    node_run, node_calls = fake_run(0, "v22.17.0\r\n")
    pnpm_run, pnpm_calls = fake_run(0, "10.34.1\r\n")
    node = Path("D:/node/node-v22.17.0-win-x64/node.exe")
    assert script.probe_node_version(node, web, {}, node_run, origin="windows_fallback") == "v22.17.0"
    assert script.check_offline_pnpm(node, node.parent / "node_modules/corepack/dist/pnpm.js", web, {}, "win32", pnpm_run) == "10.34.1"
    assert node_calls[0][1]["creationflags"] == 0x08000000
    assert pnpm_calls[0][1]["creationflags"] == 0x08000000
