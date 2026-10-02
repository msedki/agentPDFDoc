"""Accélération GPU de la génération par Ollama (W024, W025) : profil, compléments de bibliothèques, découverte, mode.

Seule la génération passe sur GPU (W025 P1). Le mode d'une instance est décidé une fois, au démarrage, d'après la
découverte qu'Ollama 0.35.0 journalise avant de servir HTTP (`server/routes.go` : `GPUDevices`, `LogDetails`, puis
`Serve`). Seul CUDA est retenu (P3) et le GPU n'est employé d'office que sur un couple (plateforme, bibliothèques)
qualifié par un essai réel (P4) ; un GPU intégré à mémoire unifiée (Jetson) l'est en plus seulement sur un poste de
plus de 16 Gio de mémoire totale. Le format du journal n'est pas un contrat d'Ollama : il se revérifie à chaque montée
de version, et une découverte illisible laisse l'instance sur CPU.

Le module ne dépend que de la bibliothèque standard et de `platforms` : le runtime et l'API l'importent sans dépendance
de plus. Seule la sonde de provisionnement (`probe_discovery`) charge le superviseur, au moment de l'appel.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .platforms import entries_for_platform, platform_id

ROOT = Path(__file__).resolve().parents[2]
# Groupe du verrou qui porte les compléments officiels JetPack d'Ollama (extraits par-dessus l'archive de base).
GPU_GROUP = "ollama-gpu"
GPU_LIBRARIES_RETAINED = frozenset({"CUDA"})
# Couples qualifiés par un essai réel (W025 P4) : Jetson AGX Orin, JetPack 5, complément officiel, essai du 01/10/2026.
QUALIFIED_GPU_PATHS = frozenset({("linux-aarch64", "cuda_jetpack5")})
ACCELERATOR_VALUES = ("auto", "cpu", "gpu")
# Correspondance d'Ollama (discover/gpu.go v0.35.0) : R35 donne jetpack5, R36 jetpack6, toute autre version rien.
JETPACK_BY_L4T = {35: "jetpack5", 36: "jetpack6"}
TEGRA_RELEASE = Path("/etc/nv_tegra_release")
NVIDIA_DRIVER_VERSION = Path("/proc/driver/nvidia/version")
MEMINFO = Path("/proc/meminfo")
# GPU intégré à mémoire unifiée (type « iGPU » de la découverte d'Ollama, cas des Jetson) : qualifié en auto seulement
# au-delà de la taille de l'hôte de référence de D-01 (16 Gio). L'essai réel du 02/10/2026 suggère que la mémoire prise
# par le GPU n'apparaît qu'en partie dans MemAvailable (hypothèse H-GPU-2, non mesurable sans root) : la réserve
# d'admission n'y est pas fiable.
UNIFIED_MEMORY_MIN_MIB = 16384
# Nœuds d'un GPU NVIDIA dédié (nvidia0) ou intégré Jetson (nvhost-gpu, nvgpu) ; le compte doit pouvoir les ouvrir.
GPU_DEVICE_NODES = ("/dev/nvidia0", "/dev/nvhost-gpu", "/dev/nvgpu/igpu0/ctrl")
# Découverte confirmée par `provision`, relative à la racine du programme ; jamais livrée dans le kit (poste de fabrication).
DISCOVERY_MANIFEST = Path(".runtime/manifests/ollama-discovery.json")
# Même port de boucle locale que le service de provisionnement de pull-model, jamais employé en même temps.
PROBE_PORT = 11444

VALUE_MESSAGE = ("llm.accelerator accepte auto (GPU utilisé s'il est détecté sur un poste qualifié, CPU sinon), "
                 "cpu (calcul CPU imposé) ou gpu (essai du GPU sur un poste non qualifié).")
BOTH_KEYS_MESSAGE = "llm.num_gpu est remplacé par llm.accelerator : retirez llm.num_gpu du profil."
LLM_SECTION_MESSAGE = "La section llm du profil est absente ou n'est pas une table."
LEGACY_NUM_GPU_MESSAGE = ("llm.num_gpu n'accepte que 0 (profil antérieur à l'accélération GPU) ; pour utiliser le GPU, "
                          "remplacez-le par llm.accelerator: auto, ou gpu pour l'essayer sur un poste non qualifié.")

# Textes courts des raisons de resolve_mode, placés après « génération sur CPU, » ou « génération sur GPU, … ; »
# (selftest, status, provision) : une paire de parenthèses au plus, jamais entre parenthèses.
REASON_TEXTS = {
    "imposed_by_profile": "imposée par le profil (llm.accelerator: cpu)",
    "legacy_profile_cpu": "profil antérieur à l'accélération GPU (llm.num_gpu: 0)",
    "discovery_unreadable": "découverte des GPU illisible dans le journal d'Ollama",
    "no_gpu_discovered": "aucun GPU utilisable découvert par Ollama",
    "gpu_library_not_retained": "GPU non NVIDIA écarté, seul CUDA est employé",
    "gpu_mixed_libraries": "GPU NVIDIA et GPU d'une autre bibliothèque présents ensemble, Ollama choisirait lui-même",
    "gpu_libraries_unverified": "bibliothèques GPU d'Ollama différentes du manifeste vérifié",
    "gpu_path_not_qualified": "GPU NVIDIA détecté, voie non qualifiée par un essai réel sur ce type de poste",
    "gpu_unified_memory_not_qualified": ("GPU intégré à mémoire partagée avec le CPU, qualifié seulement au-delà de "
                                         f"{UNIFIED_MEMORY_MIN_MIB // 1024} Gio de mémoire totale"),
    "gpu_trial": "essai demandé par le profil (llm.accelerator: gpu) sur une voie ou un poste non qualifiés",
    "gpu_discovered": "GPU découvert, bibliothèques vérifiées, voie qualifiée",
}

DISCOVERY_START = 'msg="discovering available GPUs..."'
_INFERENCE_COMPUTE = 'msg="inference compute"'
# Écartés par Ollama : iGPU hors CUDA (discover/runner.go) et cibles ROCm sans rocBLAS (discover/amd.go).
_DROPPED = {'msg="dropping integrated GPU': "integrated_gpu", 'msg="dropping ROCm device': "rocm_target_unsupported"}
# Paires clé=valeur du gestionnaire texte de slog : valeur entre guillemets (échappements de strconv.Quote) ou nue.
_PAIR = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S*)')
_L4T = re.compile(rb" R(\d+) ")
DEVICE_FIELDS = ("id", "library", "compute", "name", "description", "libdirs", "driver", "pci_id", "type", "total",
                 "available")
DROPPED_FIELDS = ("id", "library", "compute", "name", "description", "pci_id")


class AcceleratorProfileError(ValueError):
    """Profil refusé ; `keys` nomme les clés du profil en cause (détail `keys` de l'erreur `invalid_profile` de l'API)."""

    def __init__(self, message: str, keys: tuple[str, ...]):
        super().__init__(message)
        self.keys = keys


def profile_accelerator(config: dict) -> dict[str, str]:
    """Accélération demandée par le profil : `llm.accelerator`, sinon la forme antérieure `llm.num_gpu: 0`, sinon auto."""
    llm = config.get("llm") if isinstance(config, dict) else None
    if not isinstance(llm, dict):
        raise AcceleratorProfileError(LLM_SECTION_MESSAGE, ("llm",))
    if "accelerator" in llm and "num_gpu" in llm:
        raise AcceleratorProfileError(BOTH_KEYS_MESSAGE, ("llm.accelerator", "llm.num_gpu"))
    if "accelerator" in llm:
        value = llm["accelerator"]
        if not isinstance(value, str) or value not in ACCELERATOR_VALUES:
            raise AcceleratorProfileError(VALUE_MESSAGE, ("llm.accelerator",))
        return {"requested": value, "requested_source": "profile"}
    if "num_gpu" in llm:
        value = llm["num_gpu"]
        # YAML `false` vaut 0 pour Python : seul l'entier 0 est la forme antérieure.
        if type(value) is not int or value != 0:
            raise AcceleratorProfileError(LEGACY_NUM_GPU_MESSAGE, ("llm.num_gpu",))
        return {"requested": "cpu", "requested_source": "legacy_num_gpu"}
    return {"requested": "auto", "requested_source": "default"}


def l4t_major(path: Path = TEGRA_RELEASE) -> int | None:
    """Version majeure de Jetson Linux, lue comme Ollama (expression « R(\\d+) » entourée d'espaces) ; None sinon."""
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(4096)
    except OSError:
        return None
    match = _L4T.search(data)
    return int(match.group(1)) if match else None


def _first_line(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            return stream.readline(512).strip() or None
    except OSError:
        return None


def read_memory_total_mib(path: Path | None = None) -> int | None:
    """Mémoire physique totale du poste en Mio, d'après le champ MemTotal de /proc/meminfo (en kB, soit des Kio).

    None si le fichier est absent ou illisible, ou si le champ manque ou a une autre forme : la mémoire reste inconnue.
    """
    try:
        with Path(path or MEMINFO).open("r", encoding="ascii", errors="replace") as stream:
            for line in stream:
                name, _, value = line.partition(":")
                if name == "MemTotal":
                    fields = value.split()
                    if len(fields) == 2 and fields[1] == "kB" and fields[0].isdigit():
                        return int(fields[0]) // 1024
                    return None
    except OSError:
        return None
    return None


def unified_memory_qualified(memory_total_mib: object) -> bool:
    """Mémoire totale suffisante pour employer d'office un GPU intégré à mémoire unifiée : plus de 16 Gio.

    Une mémoire inconnue, ou une valeur qui n'est pas un entier (runtime.json altéré), ne qualifie jamais le poste.
    """
    return (isinstance(memory_total_mib, int) and not isinstance(memory_total_mib, bool)
            and memory_total_mib > UNIFIED_MEMORY_MIN_MIB)


def _node_state(node: str) -> dict[str, bool]:
    try:
        return {"exists": os.path.exists(node), "access": os.access(node, os.R_OK | os.W_OK)}
    except (OSError, ValueError):
        return {"exists": False, "access": False}


def host_signals() -> dict[str, Any]:
    """Indices matériels du poste, sans jamais lever : seule la découverte d'Ollama fait foi pour le mode.

    Sous Windows, seul `nvcuda.dll` est cherché ; sous Linux, la version de Jetson Linux, le pilote noyau NVIDIA,
    l'accès aux nœuds GPU et la mémoire totale (`memory_total_mib`, qui décide d'un GPU intégré ; None ailleurs).
    """
    signals: dict[str, Any] = {"platform": None, "l4t_major": None, "jetpack": None, "nvidia_kernel_driver": None,
                               "gpu_nodes": {}, "windows_nvcuda": None, "memory_total_mib": None}
    try:
        current = platform_id()
    except Exception:  # indices facultatifs : le poste reste décrit sans eux
        return signals
    signals["platform"] = current
    if current.startswith("linux-"):
        major = l4t_major(TEGRA_RELEASE)
        signals["l4t_major"] = major
        # Ollama ne cherche une variante JetPack que sous Linux arm64.
        signals["jetpack"] = JETPACK_BY_L4T.get(major) if current == "linux-aarch64" and major is not None else None
        signals["nvidia_kernel_driver"] = _first_line(NVIDIA_DRIVER_VERSION)
        signals["gpu_nodes"] = {node: _node_state(node) for node in GPU_DEVICE_NODES}
        signals["memory_total_mib"] = read_memory_total_mib(MEMINFO)
    elif current.startswith("windows-"):
        try:
            system_root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
            signals["windows_nvcuda"] = (system_root / "System32" / "nvcuda.dll").is_file()
        except OSError:
            signals["windows_nvcuda"] = None
    return signals


def jetson_label(signals: dict[str, Any]) -> str | None:
    """« Jetson Linux R35 (JetPack 5) », « Jetson Linux R38 » ou None hors Jetson."""
    major = signals.get("l4t_major")
    if major is None:
        return None
    jetpack = signals.get("jetpack")
    return f"Jetson Linux R{major}" + (f" (JetPack {jetpack.removeprefix('jetpack')})" if jetpack else "")


def no_complement_message(signals: dict[str, Any]) -> str:
    host = jetson_label(signals) or "hors Jetson"
    return (f"Aucun complément GPU d'Ollama ne correspond à ce poste ({signals.get('platform') or platform_id()}, "
            f"{host}) : rien à télécharger.")


def entries_for_host(entries: list[dict[str, Any]], signals: dict[str, Any] | None = None,
                     current: str | None = None) -> list[dict[str, Any]]:
    """Entrées d'un groupe du verrou valables sur ce poste : règle de plateforme, puis champ `host` éventuel.

    `host` (par exemple `{"l4t_major": 35}`) exige l'égalité de chaque indice de `host_signals` ; une entrée sans ce
    champ vaut sur toute sa plateforme. Les indices ne sont relevés que si une entrée de la plateforme les demande :
    un poste sans complément GPU (Windows compris) ne lit aucun fichier de plus.
    """
    current = current or (signals or {}).get("platform") or None
    candidates = entries_for_platform(entries, current)
    if not any("host" in entry for entry in candidates):
        return candidates
    observed = signals if signals is not None else host_signals()

    def matches(entry: dict[str, Any]) -> bool:
        required = entry.get("host")
        if required is None:
            return True
        return isinstance(required, dict) and all(key in observed and observed[key] == value
                                                  for key, value in required.items())

    return [entry for entry in candidates if matches(entry)]


def _unquote(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        try:
            return str(json.loads(raw))
        except ValueError:
            return re.sub(r"\\(.)", r"\1", raw[1:-1])
    return raw


def _pairs(line: str) -> dict[str, str]:
    return {key: _unquote(raw) for key, raw in _PAIR.findall(line)}


def parse_discovery(text: str) -> dict[str, Any]:
    """Découverte du dernier démarrage d'Ollama, lue dans son journal.

    Seul le dernier bloc compte : celui qui suit la dernière ligne « discovering available GPUs... » (le journal d'une
    instance est ouvert en ajout). Une ligne « inference compute » par périphérique retenu, ou `id=cpu` sans GPU
    (`discover/types.go`) ; les GPU écartés par Ollama sont rendus dans `dropped`. Une dernière ligne sans fin de ligne
    est ignorée (journal en cours d'écriture). Sans ligne « inference compute » complète dans ce bloc : `unreadable`.
    `libdirs` devient une liste (`["ollama", "cuda_jetpack5"]`).
    """
    lines = text.split("\n")
    if not text.endswith("\n"):
        lines = lines[:-1]
    start = max((index for index, line in enumerate(lines) if DISCOVERY_START in line), default=None)
    unreadable: dict[str, Any] = {"status": "unreadable", "devices": [], "dropped": []}
    if start is None:
        return unreadable
    devices: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    cpu = False
    for line in lines[start + 1:]:
        if _INFERENCE_COMPUTE in line:
            values = _pairs(line)
            # « available » est le dernier champ : sa présence atteste une ligne entière.
            if not {"id", "library", "available"} <= values.keys():
                continue
            if values["id"] == "cpu":
                cpu = True
                continue
            device: dict[str, Any] = {key: values.get(key, "") for key in DEVICE_FIELDS}
            device["libdirs"] = [part for part in values.get("libdirs", "").split(",") if part]
            devices.append(device)
            continue
        for marker, reason in _DROPPED.items():
            if marker in line:
                values = _pairs(line)
                item = {"reason": reason, **{key: values.get(key, "") for key in DROPPED_FIELDS}}
                if reason == "rocm_target_unsupported":
                    item.update(library="ROCm", name=values.get("device", ""), gfx_target=values.get("gfx_target", ""))
                dropped.append(item)
                break
    # Ollama journalise soit des GPU, soit la ligne CPU (LogDetails) : les deux ensemble ne sont pas interprétés.
    if devices and not cpu:
        return {"status": "gpu", "devices": devices, "dropped": dropped}
    if cpu and not devices:
        return {"status": "cpu_only", "devices": [], "dropped": dropped}
    return {**unreadable, "dropped": dropped}


def read_discovery(log_path: Path, limit: int = 1 << 20) -> dict[str, Any]:
    """`parse_discovery` sur les `limit` derniers octets du journal (UTF-8, caractères invalides remplacés).

    Journal absent ou illisible : `unreadable`. Quand le journal dépasse la limite, la première ligne lue, coupée, est
    ignorée.
    """
    try:
        with Path(log_path).open("rb") as stream:
            size = stream.seek(0, os.SEEK_END)
            stream.seek(max(0, size - limit))
            data = stream.read(limit)
    except OSError:
        return {"status": "unreadable", "devices": [], "dropped": []}
    if size > limit:
        data = data.split(b"\n", 1)[1] if b"\n" in data else b""
    return parse_discovery(data.decode("utf-8", errors="replace"))


def device_variant(device: dict[str, Any] | None) -> str | None:
    """Dossier de bibliothèques d'Ollama employé par le périphérique (`cuda_jetpack5`, `cuda_v13`…), None sinon."""
    if not device:
        return None
    return next((name for name in device.get("libdirs") or [] if name != "ollama"), None)


def _variant_of(recorded: str) -> str | None:
    """Sous-dossier de `lib/ollama` d'un chemin du manifeste (séparateurs Windows ou POSIX) ; None hors sous-dossier."""
    parts = recorded.replace("\\", "/").split("/")
    for index in range(len(parts) - 3):
        if parts[index] == "lib" and parts[index + 1] == "ollama":
            return parts[index + 2]
    return None


def ollama_version(lock: dict[str, Any], current: str | None = None) -> str:
    """Version d'Ollama verrouillée pour cette plateforme (entrée unique du groupe `ollama`)."""
    entries = entries_for_platform(lock["groups"]["ollama"], current)
    if len(entries) != 1:
        raise FileNotFoundError(f"Verrou d'artefacts : une entrée ollama attendue pour {current or platform_id()}, "
                                f"{len(entries)} trouvée(s)")
    return str(entries[0]["version"])


def verified_libraries(lock: dict[str, Any], manifest: dict[str, Any], signals: dict[str, Any] | None = None,
                       current: str | None = None, *, root: Path | None = None) -> dict[str, Any]:
    """Bibliothèques GPU d'Ollama présentes sur disque telles que le manifeste local de leur extraction les décrit.

    Seuls comptent les enregistrements `ollama` et `ollama-gpu` issus des entrées du verrou de ce poste (même URL).
    Chaque fichier d'un sous-dossier de `lib/ollama` est comparé par sa taille, sans rehachage ; chaque lien interne
    par sa cible. `required` : un complément officiel existe pour ce poste ; `provisioned` : il a été extrait.
    """
    root = root or ROOT
    current = current or (signals or {}).get("platform") or platform_id()
    groups = lock.get("groups", {})
    base = entries_for_platform(groups.get("ollama", []), current)
    complements = entries_for_host(groups.get(GPU_GROUP, []), signals, current)
    variants: dict[str, dict[str, Any]] = {}

    def variant(name: str, group: str) -> dict[str, Any]:
        return variants.setdefault(name, {"group": group, "files": 0, "links": 0, "sizes_ok": True, "links_ok": True})

    recorded_urls = set()
    for group, entries in (("ollama", base), (GPU_GROUP, complements)):
        urls = {entry.get("url") for entry in entries}
        for record in manifest.get(group, []):
            if record.get("url") not in urls:
                continue
            recorded_urls.add(record["url"])
            for item in record.get("extracted_files", []):
                name = _variant_of(str(item.get("path", "")))
                if name is None:
                    continue
                state = variant(name, group)
                state["files"] += 1
                path = root / item["path"]
                if not path.is_file() or "size" not in item or path.stat().st_size != item["size"]:
                    state["sizes_ok"] = False
            for link in record.get("extracted_links", []):
                name = _variant_of(str(link.get("path", "")))
                if name is None:
                    continue
                state = variant(name, group)
                state["links"] += 1
                path = root / link["path"]
                if not path.is_symlink() or os.readlink(path) != link.get("target"):
                    state["links_ok"] = False
    names = [entry["url"].rsplit("/", 1)[-1] for entry in complements]
    return {"entry": names[0] if names else None, "required": bool(complements),
            "provisioned": bool(complements) and all(entry["url"] in recorded_urls for entry in complements),
            "variants": variants}


def variant_verified(libraries: dict[str, Any], variant: str | None) -> bool:
    state = (libraries.get("variants") or {}).get(variant) if variant else None
    return bool(state and state["files"] and state["sizes_ok"] and state["links_ok"])


def libraries_signature(libraries: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Ce qu'Ollama peut charger : complément extrait ou non, et dossiers de bibliothèques vérifiés sur disque.

    Une découverte consignée avec une autre signature que celle d'aujourd'hui (complément extrait ou retiré depuis,
    fichiers altérés) ne dit plus ce que découvrira le prochain démarrage.
    """
    return (bool(libraries.get("provisioned")),
            tuple(sorted(name for name in libraries.get("variants") or {} if variant_verified(libraries, name))))


def cuda_libraries_removed(libraries: dict[str, Any]) -> bool:
    """Dossiers CUDA d'Ollama consignés au manifeste mais absents ou altérés sur disque, aucun n'étant vérifié.

    Cas d'un kit Windows construit avec --without-gpu : le manifeste de l'archive de base garde cuda_v12 et cuda_v13,
    dont les fichiers ne sont pas livrés.
    """
    cuda = [name for name, state in (libraries.get("variants") or {}).items()
            if name.startswith("cuda") and state.get("files")]
    return bool(cuda) and not any(variant_verified(libraries, name) for name in cuda)


_READ_HOST_MEMORY = object()


def resolve_mode(requested: dict[str, Any], discovery: dict[str, Any], libraries: dict[str, Any],
                 platform: str | None = None, *, memory_total_mib: object = _READ_HOST_MEMORY) -> dict[str, Any]:
    """Mode de génération d'une instance (W025), règles appliquées dans l'ordre.

    CPU imposé par le profil ; découverte illisible ; aucun GPU ; aucun GPU CUDA ; CUDA avec un GPU d'une autre
    bibliothèque (Ollama choisirait lui-même, `sched.go`) ; bibliothèques non vérifiées ; voie non qualifiée (CPU en
    auto, essai GPU en `gpu`) ; GPU intégré à mémoire unifiée sur un poste de 16 Gio ou moins, ou de mémoire inconnue
    (CPU en auto, essai GPU en `gpu`) ; sinon GPU. `device` est le GPU concerné par la décision (CUDA de préférence),
    même en mode CPU ; `qualified` dit si sa voie figure dans QUALIFIED_GPU_PATHS, quelle que soit la mémoire.

    `memory_total_mib` vient de `host_signals` ; sans valeur transmise (superviseur, calibration), la mémoire totale
    est lue sur le poste, et seulement pour un GPU intégré sur une voie qualifiée. Un GPU dédié n'a aucune condition
    de mémoire.
    """
    platform = platform or platform_id()
    status = discovery.get("status")
    devices = list(discovery.get("devices") or []) if status == "gpu" else []
    retained = [device for device in devices if device.get("library") in GPU_LIBRARIES_RETAINED]
    device = (retained or devices or [None])[0]
    variant = device_variant(device)
    paths = {(platform, device_variant(item)) for item in retained}
    qualified = bool(retained) and paths <= QUALIFIED_GPU_PATHS

    def decision(mode: str, reason: str) -> dict[str, Any]:
        return {"mode": mode, "reason": reason, "device": device, "variant": variant, "qualified": qualified}

    if requested.get("requested") == "cpu":
        legacy = requested.get("requested_source") == "legacy_num_gpu"
        return decision("cpu", "legacy_profile_cpu" if legacy else "imposed_by_profile")
    if status not in ("gpu", "cpu_only"):
        return decision("cpu", "discovery_unreadable")
    if not devices:
        return decision("cpu", "no_gpu_discovered")
    if not retained:
        return decision("cpu", "gpu_library_not_retained")
    if len(retained) != len(devices):
        return decision("cpu", "gpu_mixed_libraries")
    if not all(variant_verified(libraries, device_variant(item)) for item in retained):
        return decision("cpu", "gpu_libraries_unverified")
    if not qualified:
        if requested.get("requested") == "gpu":
            return decision("gpu", "gpu_trial")
        return decision("cpu", "gpu_path_not_qualified")
    if any(item.get("type") == "iGPU" for item in retained):
        memory = read_memory_total_mib() if memory_total_mib is _READ_HOST_MEMORY else memory_total_mib
        if not unified_memory_qualified(memory):
            if requested.get("requested") == "gpu":
                return decision("gpu", "gpu_trial")
            return decision("cpu", "gpu_unified_memory_not_qualified")
    return decision("gpu", "gpu_discovered")


def is_nvidia(device: dict[str, Any] | None) -> bool:
    """GPU NVIDIA d'après sa description ou son nom : un GPU que CUDA écarte reste visible par Vulkan sous ce nom."""
    if not device:
        return False
    return "nvidia" in f"{device.get('description') or ''} {device.get('name') or ''}".lower()


def reason_text(decision: dict[str, Any]) -> str:
    """Texte court de la raison d'une décision (REASON_TEXTS), précisé pour un GPU NVIDIA vu seulement par Vulkan."""
    reason = decision.get("reason")
    if reason == "gpu_library_not_retained" and is_nvidia(decision.get("device")):
        return "GPU NVIDIA vu seulement par Vulkan, CUDA ne l'a pas retenu : pilote ou capacité de calcul"
    return REASON_TEXTS.get(str(reason), str(reason)) if reason else "raison non consignée"


def describe_device(device: dict[str, Any], variant: str | None = None) -> str:
    """« Orin (CUDA, GPU intégré, bibliothèques cuda_jetpack5) »."""
    kind = {"iGPU": "GPU intégré", "discrete": "GPU dédié"}.get(str(device.get("type", "")))
    details = [str(device.get("library") or "bibliothèque inconnue"), *([kind] if kind else []),
               *([f"bibliothèques {variant}"] if variant else [])]
    return f"{device.get('description') or device.get('name') or 'GPU'} ({', '.join(details)})"


def processor_label(size: int, size_vram: int) -> str:
    """Colonne PROCESSOR de `ollama ps` (cmd/cmd.go v0.35.0) à partir de `size` et `size_vram` de `/api/ps`."""
    if size_vram == 0:
        return "100% CPU"
    if size_vram == size:
        return "100% GPU"
    if size_vram > size or size == 0:
        return "Unknown"
    # Même calcul que Go ; math.Round arrondit la demie en s'éloignant de zéro, round() de Python l'arrondirait au pair.
    share = (size - size_vram) / size * 100
    cpu = math.floor(share)
    if share - cpu >= 0.5:
        cpu += 1
    return f"{cpu}%/{100 - cpu}% CPU/GPU"


def discovery_record(discovery: dict[str, Any], *, source: str, method: str, log: str, version: str,
                     signals: dict[str, Any], utc: str | None = None,
                     libraries: dict[str, Any] | None = None) -> dict[str, Any]:
    """Contenu de `.runtime/manifests/ollama-discovery.json` ; `log` est relatif à la racine du programme.

    `libraries` (verified_libraries au moment de la découverte) permet à doctor d'écarter une découverte faite avec
    d'autres bibliothèques GPU que celles d'aujourd'hui.
    """
    return {"schema_version": 1, "source": source, "method": method, "utc": utc or datetime.now(UTC).isoformat(),
            "version": version, "platform": signals.get("platform"), "l4t_major": signals.get("l4t_major"),
            "jetpack": signals.get("jetpack"), "log": log, "status": discovery["status"],
            "devices": discovery["devices"], "dropped": discovery["dropped"],
            **({"libraries": libraries} if libraries is not None else {})}


def probe_discovery(profile: dict, profile_path: Path, directory: Path, log_path: Path, *, version: str,
                    port: int = PROBE_PORT, timeout: float = 150) -> dict[str, Any]:
    """Sonde de provisionnement : `ollama serve` sur la boucle locale, le temps de lire sa découverte, puis arrêt.

    Mêmes environnement (`environment()`, inchangé), exécutable vérifié et répertoire courant que l'instance ; port
    contrôlé libre comme pour pull-model. Chemins absolus exigés (B5) : un dossier de données relatif serait résolu
    depuis le répertoire courant d'Ollama (`bin/`) et y laisserait `HOME/.ollama`. Le délai couvre plusieurs passes de
    découverte (90 s chacune au plus sous Windows, `discover/runner.go`).
    """
    from .supervisor import (
        ProcessJob,
        environment,
        native_paths,
        ollama_working_directory,
        port_probe,
        send_owned_console_interrupt,
        wait_http,
    )

    for label, value in (("profil", profile_path), ("dossier du service", directory), ("journal", log_path)):
        if not Path(value).is_absolute():
            raise ValueError(f"Sonde de découverte : chemin absolu exigé pour le {label} ({value})")
    base_url = f"http://127.0.0.1:{port}"
    probe_profile = {**profile, "llm": {**profile["llm"], "base_url": base_url}}
    with port_probe() as probe:
        probe.bind(("127.0.0.1", port))
    binary = native_paths(("ollama",))["ollama"]
    env = environment(probe_profile, Path(directory), Path(profile_path))
    with ProcessJob() as job:
        child = job.launch([str(binary), "serve"], cwd=ollama_working_directory(binary), env=env, log_path=Path(log_path))
        try:
            wait_http(base_url + "/api/version", child, version, timeout=timeout)
        finally:
            try:
                send_owned_console_interrupt(child, "ollama")
                child.wait(30)
            except TimeoutError:
                print("Sonde de découverte : arrêt forcé ciblé du Job, aucune inférence active.", flush=True)
            except Exception as exc:  # arrêt coopératif impossible (assistant console_signal hors délai sous Windows…)
                # La fermeture du Job arrête Ollama ; la découverte, journalisée avant HTTP, reste lisible.
                print(f"Sonde de découverte : arrêt coopératif d'Ollama impossible, {type(exc).__name__} ; arrêt forcé "
                      "ciblé du Job, aucune inférence active.", flush=True)
    return read_discovery(Path(log_path))
