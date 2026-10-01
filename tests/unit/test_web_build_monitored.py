"""Résolution de Node par apps/web/scripts/build-monitored.py selon la plateforme (W018)."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

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
    assert script.resolve_toolchain({}, "linux", lambda name: str(node) if name == "node" else None) == (node.resolve(), pnpm)


def test_documented_variable_wins_over_path(script, tmp_path):
    chosen, pnpm = posix_node(tmp_path / "choisi")
    other, _ = posix_node(tmp_path / "autre")
    environ = {script.NODE_VARIABLE: str(chosen)}
    assert script.resolve_toolchain(environ, "linux", lambda name: str(other)) == (chosen.resolve(), pnpm)


def test_windows_variable_wins_over_the_historical_node(script, monkeypatch, tmp_path):
    historical, _ = windows_node(tmp_path / "node-v22.17.0-win-x64")
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    chosen, pnpm = windows_node(tmp_path / "choisi")
    other, _ = windows_node(tmp_path / "path")
    assert script.resolve_toolchain({script.NODE_VARIABLE: str(chosen)}, "win32", lambda name: str(other)) == (chosen.resolve(), pnpm)


def test_windows_without_variable_keeps_the_historical_node_before_path(script, monkeypatch, tmp_path):
    historical, pnpm = windows_node(tmp_path / "node-v22.17.0-win-x64")
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    other, _ = windows_node(tmp_path / "path")
    assert script.resolve_toolchain({}, "win32", lambda name: str(other)) == (historical, pnpm)
    # Une variable vide ne désigne rien : le repli historique s'applique.
    assert script.resolve_toolchain({script.NODE_VARIABLE: ""}, "win32", lambda name: str(other)) == (historical, pnpm)


def test_the_historical_node_is_never_used_outside_windows(script, monkeypatch, tmp_path):
    historical, _ = windows_node(tmp_path / "node-v22.17.0-win-x64")
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    node, pnpm = posix_node(tmp_path / "nvm")
    assert script.resolve_toolchain({}, "linux", lambda name: str(node)) == (node.resolve(), pnpm)


def test_a_variable_naming_a_missing_node_is_refused_without_fallback(script, monkeypatch, tmp_path):
    historical, _ = windows_node(tmp_path / "node-v22.17.0-win-x64")
    monkeypatch.setattr(script, "WINDOWS_NODE", historical)
    with pytest.raises(SystemExit, match="RAG_WEB_NODE"):
        script.resolve_toolchain({script.NODE_VARIABLE: str(tmp_path / "absent" / "node.exe")}, "win32", lambda name: None)


def test_windows_without_historical_node_falls_back_to_path(script, tmp_path):
    node, pnpm = windows_node(tmp_path / "nodejs")
    assert script.resolve_toolchain({}, "win32", lambda name: str(node)) == (node.resolve(), pnpm)


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
    assert script.check_offline_pnpm(Path("/n/node"), Path("/n/dist/pnpm.js"), web, environment, "linux", run) == "10.34.1"
    argv, options = calls[0]
    assert argv == ["/n/node", "/n/dist/pnpm.js", "--version"]
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
    assert f'    cd "{web}" && "/n/bin/node" "/n/lib/node_modules/corepack/dist/corepack.js" install\n' in str(linux.value)


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
