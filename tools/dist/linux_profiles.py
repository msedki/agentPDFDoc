"""Profils d'une installation Linux (R26-KIT-01), exécuté par l'environnement isolé d'un programme installé (PyYAML).

`paths` : emplacements d'écriture d'un profil (données, stockage Qdrant, section `runtime`), résolus comme le runtime les
résout depuis la racine du programme.
`guard` : refus d'un profil rangé dans le programme ou qui y écrirait (garde de `rag.sh` dans une installation).
`derive` : profil d'un autre modèle livré (W032) sur les mêmes données, ports et stockage qu'un profil existant. Seules
les clés qui diffèrent entre les profils livrés des modèles (section `llm`, tokenizer, estimation de chargement) sont
remplacées ; toutes les autres valeurs du profil existant sont conservées, y compris celles d'un profil restauré. Un
profil déjà présent et identique au résultat est réutilisé ; différent, il est refusé sans être touché. `--check`
contrôle sans écrire.
`ports` : reprise des ports d'un profil (API, Qdrant, Ollama) quand ils sont libres, par exemple sur un profil restauré.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

PROGRAM = Path(__file__).resolve().parents[2]
if str(PROGRAM) not in sys.path:
    # Lancé avec -I : le dossier du script n'est pas dans sys.path, la racine du programme y est ajoutée explicitement.
    sys.path.insert(0, str(PROGRAM))

WRITE_KEYS = ("host_lock_path", "backups_dir", "restore_storage_dir", "huggingface_cache_dir")
# Sections qui portent chemins et ports : une différence entre profils livrés à cet endroit n'est pas une clé de modèle.
PROTECTED = ("app", "qdrant", "runtime", "sqlite", "security")


def load(path: Path) -> dict[str, Any]:
    import yaml

    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} n'est pas un profil")
    return value


def write_locations(profile: dict[str, Any], program: Path) -> dict[str, str]:
    """Emplacements où l'exécution écrit, résolus depuis la racine du programme comme dans supervisor et artifacts."""
    from services.runtime.artifacts import RUNTIME_LOCATIONS

    data = (program / profile["app"]["data_dir"]).resolve()
    storage = (profile.get("qdrant") or {}).get("storage_dir")
    runtime = profile.get("runtime") or {}
    locations = {"app.data_dir": str(data), "qdrant.storage": str((program / storage).resolve() if storage else data / "qdrant")}
    for key in WRITE_KEYS:
        locations[f"runtime.{key}"] = str((program / (runtime.get(key) or RUNTIME_LOCATIONS[key])).resolve())
    return locations


def ports_of(profile: dict[str, Any]) -> dict[str, int]:
    return {"app": int(profile["app"]["port"]), "qdrant": int(str(profile["qdrant"]["url"]).rsplit(":", 1)[1].rstrip("/")),
            "ollama": int(str(profile["llm"]["base_url"]).rsplit(":", 1)[1].rstrip("/"))}


def paths(profile_path: Path, program: Path) -> dict[str, Any]:
    profile = load(profile_path)
    llm = profile.get("llm") or {}
    return {"status": "read", "profile": str(profile_path), "model": llm.get("model"), "source_model": llm.get("source_model"),
            "locations": write_locations(profile, program), "ports": ports_of(profile)}


def inside(path: Path, folder: Path) -> bool:
    real, base = Path(os.path.realpath(path)), Path(os.path.realpath(folder))
    return real == base or real.is_relative_to(base)


def guard(profile_path: Path, program: Path) -> dict[str, Any]:
    if inside(profile_path, program):
        raise ValueError(f"Profil {profile_path} rangé dans le dossier du programme (profil livré) : ses données seraient écrites dans le "
                         "dossier du programme. Indiquer le profil de l'utilisateur, hors du programme, ou passer par le lanceur atelier.")
    within = [f"{key} {value}" for key, value in write_locations(load(profile_path), program).items() if inside(Path(value), program)]
    if within:
        raise ValueError(f"Le profil {profile_path} écrirait dans le dossier du programme ({'; '.join(within)}) : y indiquer des "
                         "chemins absolus hors du programme (rag.sh init-profile --target <racine des données> les écrit).")
    return {"status": "ok", "profile": str(profile_path)}


def flatten(value: Any, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], Any]:
    if isinstance(value, dict):
        items: dict[tuple[str, ...], Any] = {}
        for key, item in value.items():
            items.update(flatten(item, (*prefix, str(key))))
        return items
    return {prefix: value}


def model_keys(shipped: dict[str, dict[str, Any]]) -> list[tuple[str, ...]]:
    """Clés dont la valeur (ou la présence) diffère entre les profils livrés des modèles : ce qui dépend du modèle."""
    flat = [flatten(profile) for profile in shipped.values()]
    keys = sorted(set().union(*flat))
    differing = [key for key in keys if len({json.dumps(item.get(key, "<absent>"), sort_keys=True) for item in flat}) > 1]
    protected = [".".join(key) for key in differing if key[0] in PROTECTED]
    if protected:
        raise ValueError(f"Les profils livrés diffèrent hors des réglages du modèle ({', '.join(protected)}) : dérivation refusée")
    return differing


def assign(target: dict[str, Any], key: tuple[str, ...], value: Any, present: bool) -> None:
    node = target
    for part in key[:-1]:
        node = node.setdefault(part, {})
    if present:
        node[key[-1]] = copy.deepcopy(value)
    else:
        node.pop(key[-1], None)


def derived_profile(like: Path, model: str, program: Path) -> tuple[dict[str, Any], list[str]]:
    manifest = json.loads((program / "kit-manifest.json").read_text(encoding="utf-8"))
    available = manifest.get("model_profiles") or {}
    if model not in available:
        raise ValueError(f"Modèle {model} absent de ce kit ({', '.join(available)})")
    shipped = {name: load(program / relative) for name, relative in available.items()}
    keys = model_keys(shipped)
    result = copy.deepcopy(load(like))
    flat = flatten(shipped[model])
    for key in keys:
        assign(result, key, flat.get(key), key in flat)
    return result, [".".join(key) for key in keys]


def derive(like: Path, model: str, program: Path, output: Path, *, check: bool = False) -> dict[str, Any]:
    import yaml

    profile, keys = derived_profile(like, model, program)
    if output.exists():
        if load(output) != profile:
            raise ValueError(f"Profil {output} déjà présent et différent du profil {model} dérivé de {like.name} : il n'est jamais "
                             "remplacé ; le renommer ou le retirer s'il n'est plus employé, puis relancer")
        return {"status": "reused", "profile": str(output), "model": model, "replaced_keys": keys}
    if check:
        return {"status": "checked", "profile": str(output), "model": model, "replaced_keys": keys}
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(f"# Profil généré par l'installateur : {like.name} avec les réglages du modèle {model} (W032).\n")
        yaml.safe_dump(profile, stream, allow_unicode=True, sort_keys=False)
    try:
        os.link(temporary, output)  # échoue si le profil est apparu entre-temps : jamais de remplacement
    finally:
        temporary.unlink()
    return {"status": "created", "profile": str(output), "model": model, "replaced_keys": keys}


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def adopt_ports(profile_path: Path, wanted: dict[str, int]) -> dict[str, Any]:
    """Ports voulus écrits dans le profil s'ils sont tous libres ; sinon profil inchangé et ports occupés nommés."""
    import yaml

    busy = sorted(f"{name} {port}" for name, port in wanted.items() if not port_free(port))
    if busy:
        return {"status": "kept", "profile": str(profile_path), "busy": busy}
    profile = load(profile_path)
    profile["app"]["port"] = wanted["app"]
    profile["qdrant"]["url"] = f"http://127.0.0.1:{wanted['qdrant']}"
    profile["llm"]["base_url"] = f"http://127.0.0.1:{wanted['ollama']}"
    temporary = profile_path.with_name(f".{profile_path.name}.{os.getpid()}.tmp")
    temporary.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(temporary, profile_path)
    return {"status": "adopted", "profile": str(profile_path), "ports": wanted}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("paths", "guard"):
        sub.add_parser(name).add_argument("--profile", type=Path, required=True)
    make = sub.add_parser("derive")
    make.add_argument("--like", type=Path, required=True)
    make.add_argument("--model", required=True)
    make.add_argument("--program", type=Path, required=True, help="racine dont kit-manifest.json et les profils livrés font foi")
    make.add_argument("--output", type=Path, required=True)
    make.add_argument("--check", action="store_true")
    adopt = sub.add_parser("ports")
    adopt.add_argument("--profile", type=Path, required=True)
    adopt.add_argument("--ports", required=True, help="API,Qdrant,Ollama")
    args = parser.parse_args()
    try:
        if args.command == "paths":
            result = paths(args.profile, PROGRAM)
        elif args.command == "guard":
            result = guard(args.profile.absolute(), PROGRAM)
        elif args.command == "derive":
            result = derive(args.like, args.model, args.program, args.output, check=args.check)
        else:
            values = [int(item) for item in args.ports.split(",")]
            result = adopt_ports(args.profile, dict(zip(("app", "qdrant", "ollama"), values, strict=True)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        if args.command == "guard":
            print(str(error), file=sys.stderr)
            return 1
        result = {"status": "failed", "message": str(error)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in {"read", "ok", "created", "reused", "checked", "adopted", "kept"} else 1


if __name__ == "__main__":
    sys.exit(main())
