"""Verdict de `doctor` par rubrique (DIST-05) : vert, orange ou rouge, avec un message et l'action possible.

Lit seulement le résultat de `doctor` : aucun service, fichier ni processus n'est interrogé ici. Rubriques et ton des
messages suivent le parcours d'installation de l'analyse de distribution (section 7.1, étapes 7 à 10). Rouge : l'atelier
ne peut pas fonctionner ; orange : il fonctionne, ou fonctionnera après une action ordinaire (démarrer, libérer de la
mémoire) ; vert : rien à faire. Le verdict ne remplace pas un contrôle réel (import, recherche, réponse).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from . import platforms
from .accelerator import REASON_TEXTS, describe_device, device_variant, is_nvidia, reason_text

GREEN, ORANGE, RED = "vert", "orange", "rouge"
SEVERITY = {GREEN: 0, ORANGE: 1, RED: 2}

PROGRAM_FILES = {"python312": "Python 3.12", "dependencies_locked": "verrous des dépendances", "static_export": "interface compilée",
                 "embedding_files": "modèle d'embedding", "llm_tokenizer": "tokenizer du modèle de réponse",
                 "ocr_tsv_config": "configuration TSV de Tesseract", "tesseract_binary": "Tesseract"}
READINESS_LABELS = {"sqlite": "base SQLite", "embedding": "modèle d'embedding", "llm_tokenizer": "tokenizer du modèle de réponse",
                    "qdrant": "index Qdrant", "ollama": "modèle de réponse dans Ollama", "governor": "gouverneur de ressources"}
ADMISSION_OWNERS = {"generation": "Génération", "ingestion": "Extraction"}


def mib(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ") + " Mio"


def on_this_host(windows: str, posix: str) -> str:
    """Action propre au lanceur du poste : texte de rag.ps1 inchangé sous Windows (W001), rag.sh sous Linux (W018).

    Le poste Linux n'a pas de kit d'installation : la reprise des fichiers du programme y passe par `provision`.
    """
    return windows if platforms.WINDOWS else posix


def run(command: str) -> str:
    return platforms.launcher_command(command)


REPROVISION = "Relancez {} ; les données de l'utilisateur ne sont pas touchées."


def rubric(name: str, level: str, message: str, action: str | None = None) -> dict[str, Any]:
    return {"rubric": name, "level": level, "message": message, **({"action": action} if action else {})}


def program_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    missing = [label for key, label in PROGRAM_FILES.items() if checks.get(key) is not True]
    missing += [f"langue OCR {name}" for name, present in sorted(checks.get("ocr_languages", {}).items()) if not present]
    if "error" in checks.get("native_binaries", {}):
        missing.append(f"binaires Qdrant et Ollama ({checks['native_binaries']['error']})")
    if missing:
        return rubric("programme", RED, "Fichiers du programme absents ou incomplets : " + ", ".join(missing) + ".",
                      on_this_host("Réinstallez l'atelier depuis le kit ; les données de l'utilisateur ne sont pas touchées.",
                                   REPROVISION.format(run("provision"))))
    return rubric("programme", GREEN, "Fichiers du programme présents.")


def model_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    lock = checks.get("model_lock", {})
    if lock.get("status") == "invalid_lock":
        return rubric("modèle", RED, f"Verrou des modèles illisible : {lock.get('reason', 'raison inconnue')}.",
                      on_this_host("Réinstallez l'atelier depuis le kit.",
                                   "Rétablissez config/models.lock.json de la version installée, puis relancez " + run("doctor") + "."))
    if lock.get("profile_models_locked") is False:
        return rubric("modèle", RED, "Le modèle déclaré par le profil ne figure pas dans config/models.lock.json.",
                      "Rétablissez le profil généré à l'installation ou réinstallez l'atelier.")
    models = lock.get("models", {})
    absent = sorted(name for name, model in models.items() if model.get("status") == "absent")
    altered = {name: model for name, model in sorted(models.items()) if model.get("status") == "nonconform"}
    if absent:
        return rubric("modèle", RED, "Modèle absent du stockage local : " + ", ".join(absent) + ".",
                      on_this_host(r"Lancez .\rag.ps1 pull-model -Offline ; s'il échoue, réinstallez l'atelier depuis le kit.",
                                   f"Lancez {run('pull-model --offline')} ; s'il échoue, lancez {run('pull-model')}, qui télécharge le modèle verrouillé."))
    if altered:
        detail = "; ".join(f"{name} ({', '.join(sorted({issue.get('issue', '?') for issue in model.get('issues', [])}))})"
                           for name, model in altered.items())
        return rubric("modèle", RED, f"Modèle différent du verrou : {detail}.",
                      on_this_host("Réinstallez l'atelier depuis le kit pour retrouver les fichiers vérifiés.",
                                   f"Relancez {run('pull-model')} pour retrouver les fichiers vérifiés."))
    if lock.get("status") != "conform":
        return rubric("modèle", RED, f"Conformité du modèle non établie (état {lock.get('status', 'inconnu')}).",
                      on_this_host(r"Relancez .\rag.ps1 doctor ; si l'état persiste, réinstallez l'atelier.",
                                   f"Relancez {run('doctor')} ; si l'état persiste, relancez {run('provision')}."))
    return rubric("modèle", GREEN, "Modèle vérifié contre le verrou : " + ", ".join(sorted(models)) + ".")


def profile_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    storage = checks.get("qdrant_storage", {})
    if storage.get("status") != "valid":
        return rubric("profil", RED, f"Stockage de l'index refusé : {storage.get('reason', 'raison inconnue')}.",
                      "Indiquez dans le profil un dossier court et vide pour qdrant.storage_dir, puis relancez.")
    application = checks.get("profile_application", {}).get("status")
    if application == "restart_required":
        return rubric("profil", ORANGE, "Le profil a changé depuis le démarrage de l'atelier : l'instance applique encore l'ancien.",
                      f"Redémarrez : {run('down')} puis {run('up')}.")
    return rubric("profil", GREEN, "Profil valide" + (", appliqué par l'instance démarrée." if application == "applied" else "."))


def ports_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    taken = []
    for name, port in sorted(checks.get("ports", {}).items()):
        if port.get("state") in {"foreign", "occupied_unknown_owner"}:
            owners = ", ".join(f"{label} (PID {pid})" for pid, label in zip(port.get("listener_pids", []), port.get("listener_names", []), strict=False))
            taken.append(f"{port.get('port')} ({name}) occupé par " + (owners or "un processus non identifié"))
    if taken:
        return rubric("ports", RED, "Port déjà utilisé : " + " ; ".join(taken) + ". Rien n'a été arrêté.",
                      "Fermez le programme concerné, ou indiquez d'autres ports dans le profil (app.port, qdrant.url, llm.base_url), puis relancez.")
    return rubric("ports", GREEN, "Ports libres ou tenus par l'atelier.")


def library_state(result: dict[str, Any]) -> str:
    body = result.get("services", {}).get("api_ready", {}).get("body")
    empty = isinstance(body, dict) and body.get("qdrant_collection") == "absent_empty_library"
    return "index vide, prêt à importer" if empty else "index disponible"


def services_rubric(result: dict[str, Any]) -> dict[str, Any]:
    state = result.get("runtime", {}).get("status", "stopped")
    if state in {"stopped", "failed"}:
        return rubric("services", ORANGE, "Atelier arrêté.", f"Démarrez-le : {run('up')}, ou ouvrez-le par {run('open')}.")
    if state == "stale":
        return rubric("services", ORANGE, "État d'exécution périmé : le superviseur s'est arrêté sans le mettre à jour.",
                      f"Relancez l'atelier : {run('up')}.")
    if state in {"starting", "stopping"}:
        return rubric("services", ORANGE, "Atelier en cours de " + ("démarrage." if state == "starting" else "arrêt."),
                      f"Relancez {run('doctor')} dans une minute.")
    ready = result.get("services", {}).get("api_ready", {})
    body = ready.get("body") if isinstance(ready.get("body"), dict) else {}
    if ready.get("http_status") != 200:
        blocked = [READINESS_LABELS.get(key, key) for key, value in body.get("checks", {}).items() if not value]
        detail = ", ".join(blocked) if blocked else "API injoignable"
        if body.get("qdrant_collection") == "absent_with_published_generations":
            detail += " ; collection Qdrant absente alors que des documents sont publiés"
        return rubric("services", RED, f"Atelier démarré mais pas prêt : {detail}.",
                      f"Consultez les journaux ({run('logs')}). Une collection perdue ne se recrée pas sur place : restaurez une "
                      "sauvegarde dans une racine neuve ("
                      + on_this_host(r".\rag.ps1 restore -Path <sauvegarde> -Target <racine neuve>",
                                     run("restore --path <sauvegarde> --target <racine neuve>")) + ").")
    return rubric("services", GREEN, f"Services démarrés et prêts ({library_state(result)}).")


def index_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    consistency = checks.get("index_consistency", {})
    state = consistency.get("status")
    if state == "consistent":
        active = consistency.get("active_generations", 0)
        return rubric("index", GREEN, "Index cohérent : " + (f"{active} document(s) indexé(s), autant de points Qdrant que de fragments SQLite."
                                                             if active else "aucun document indexé."))
    if state == "inconsistent":
        return rubric("index", RED, f"Index incohérent pour {len(consistency.get('mismatches', []))} document(s) : points Qdrant et fragments SQLite diffèrent.",
                      "Réindexez les documents concernés depuis l'atelier ; si l'écart persiste, restaurez une sauvegarde dans une racine neuve.")
    reason = "atelier arrêté" if state == "api_unavailable" else f"état {state or 'inconnu'}"
    return rubric("index", ORANGE, f"Cohérence de l'index non vérifiée ({reason}).", f"Démarrez l'atelier puis relancez {run('doctor')}.")


def memory_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    refused = [(ADMISSION_OWNERS[owner], value) for owner, value in checks.get("cold_admission", {}).items()
               if owner in ADMISSION_OWNERS and isinstance(value, dict) and not value.get("admissible_now")]
    if refused:
        detail = " ; ".join(f"{label} non admise maintenant : {mib(value['available_mib'])} disponibles, {mib(value['required_available_mib'])} requis"
                            for label, value in refused)
        return rubric("mémoire", ORANGE, detail + ". L'atelier fonctionne ; les traitements attendent que la mémoire se libère.",
                      "Fermez des applications avant de poser une question ou d'importer des documents.")
    return rubric("mémoire", GREEN, "Mémoire suffisante pour l'extraction et la génération.")


def generation_text(accelerator: dict[str, Any]) -> str:
    """Mode de génération d'une instance en une proposition (selftest, status) : « génération sur GPU, Orin (…) » ou
    « génération sur CPU, aucun GPU utilisable découvert par Ollama »."""
    reason = str(accelerator.get("reason") or "")
    if accelerator.get("mode") == "gpu":
        device = accelerator.get("device") or {}
        text = "génération sur GPU, " + describe_device(device, accelerator.get("variant") or device_variant(device))
        return text + (f" ; {REASON_TEXTS[reason]}" if reason == "gpu_trial" else "")
    return f"génération sur CPU, {reason_text(accelerator)}"


# --- Rubrique « calcul » (D01.4, W024, W025) ---------------------------------------------------------------------------

PROPOSAL_SUFFIX = "Proposition : accélération GPU disponible, voir la rubrique calcul."
# États dont la proposition n'ouvre aucun accès au GPU par une action dans l'atelier (pilote à mettre à jour par
# l'administrateur, GPU de bibliothèques mêlées, kit sans bibliothèques CUDA) : elle reste dans la rubrique, le résumé
# ne l'annonce pas.
INFORMATIVE_PROPOSALS = frozenset({"nvidia_not_retained", "gpu_mixed_libraries", "cuda_libraries_absent"})
UNQUALIFIED = "sur une voie non qualifiée par un essai réel"
UNKNOWN_SHARE = "répartition du modèle entre GPU et CPU non déterminée par Ollama"
CUDA_NOT_RETAINED = "CUDA ne l'a pas retenu, à cause du pilote ou de la capacité de calcul du GPU"


def _first(devices: list[dict[str, Any]], cuda: bool) -> dict[str, Any] | None:
    return next((item for item in devices if (item.get("library") == "CUDA") is cuda), None)


def _gpu(device: dict[str, Any] | None, variant: str | None = None) -> str:
    """« Orin (CUDA, GPU intégré, bibliothèques cuda_jetpack5) » : toujours hors parenthèses dans un message."""
    return describe_device(device, variant or device_variant(device)) if device else "GPU"


def _jetson(host: dict[str, Any]) -> str:
    """« Jetson Linux R35, JetPack 5 » (notation de la conception J11, sans parenthèses imbriquées dans les messages)."""
    jetpack = host.get("jetpack")
    return f"Jetson Linux R{host.get('l4t_major')}" + (f", JetPack {jetpack.removeprefix('jetpack')}" if jetpack else "")


def _restart() -> str:
    """« ./rag.sh down puis ./rag.sh up », à placer entre parenthèses après « redémarrez »."""
    return f"{run('down')} puis {run('up')}"


def _down_up() -> str:
    """« ./rag.sh down et ./rag.sh up », après une première commande (« lancez …, puis … »)."""
    return f"{run('down')} et {run('up')}"


def _provision_gpu() -> str:
    return on_this_host(r".\rag.ps1 provision -Only ollama-gpu", run("provision --only ollama-gpu"))


def _complement_sizes(check: dict[str, Any]) -> str:
    """« 283 Mio à télécharger, 825 Mio une fois extraits », tailles lues dans le verrou ; vide sans complément."""
    complement = check.get("complement") or {}
    if not complement.get("size"):
        return ""
    sizes = f"{mib(complement['size'] / 1048576)} à télécharger"
    if complement.get("extracted_size"):
        sizes += f", {mib(complement['extracted_size'] / 1048576)} une fois extraits"
    return f" ({sizes})"


def _complement_qualified(check: dict[str, Any]) -> bool:
    """Voie du complément de ce poste qualifiée par un essai réel (QUALIFIED_GPU_PATHS) : seul cas où le mode auto
    calculera sur le GPU une fois le complément extrait. Sans cette information, rien n'est promis."""
    return bool((check.get("complement") or {}).get("qualified"))


def _trial_steps(check: dict[str, Any]) -> str:
    """Essai du GPU d'un Jetson sur une voie non qualifiée : complément, profil en gpu (s'il ne l'est pas), redémarrage,
    puis contrôle réel."""
    profile = "" if check.get("requested") == "gpu" else "indiquez llm.accelerator: gpu dans le profil, "
    return (f"lancez {_provision_gpu()}{_complement_sizes(check)}, {profile}puis {_down_up()}, et vérifiez la réponse "
            f"avec {run('selftest')}")


def _complement_proposal(check: dict[str, Any], qualified_text: str) -> str:
    """Proposition d'extraire le complément du poste : calcul sur GPU sur une voie qualifiée, essai ailleurs."""
    if _complement_qualified(check):
        return f"{qualified_text} : {_provision_gpu()}{_complement_sizes(check)}, puis {_down_up()}."
    return f"Pour essayer le GPU de ce Jetson, {UNQUALIFIED} : {_trial_steps(check)}."


def _hour(utc: Any) -> str:
    try:
        moment = datetime.fromisoformat(str(utc))
    except ValueError:
        return str(utc or "heure inconnue")
    return (moment.astimezone(UTC) if moment.tzinfo else moment).strftime("%d/%m/%Y %H:%M:%S UTC")


def _usage(check: dict[str, Any]) -> dict[str, Any] | None:
    """Occupation du modèle du profil dans /api/ps ; None s'il n'est pas chargé ou si Ollama n'a pas répondu."""
    return next((item for item in check.get("usage") or [] if item.get("model") == check.get("model")), None)


def _shares(processor: str) -> tuple[str, str] | None:
    """Parts « CPU » et « GPU » de la colonne PROCESSOR (« 48%/52% CPU/GPU ») : ("48", "52") ; None pour « Unknown »,
    qu'Ollama affiche quand size_vram dépasse size, et pour toute autre forme."""
    match = re.fullmatch(r"(\d+)%/(\d+)% CPU/GPU", processor or "")
    return (match[1], match[2]) if match else None


def _loaded(check: dict[str, Any]) -> str:
    usage = _usage(check)
    if usage is None:
        return ("le modèle n'est pas encore chargé" if check.get("usage") is not None
                else "chargement du modèle non vérifié (Ollama n'a pas répondu à /api/ps)")
    processor = usage.get("processor", "")
    if processor in ("100% GPU", "100% CPU"):
        return f"modèle chargé à 100 % sur le {processor.rsplit(' ', 1)[-1]}"
    shares = _shares(processor)
    return f"modèle chargé à {shares[1]} % sur le GPU et {shares[0]} % sur le CPU" if shares else UNKNOWN_SHARE


def _discovered(check: dict[str, Any]) -> list[dict[str, Any]]:
    discovery = check.get("discovery") or {}
    return list(discovery.get("devices") or []) if discovery.get("status") == "gpu" else []


def _gpu_hint(check: dict[str, Any]) -> bool:
    """Indice d'un GPU NVIDIA sur le poste (Jetson Linux, pilote, nœud de périphérique, nvcuda.dll)."""
    host = check.get("host") or {}
    return bool(host.get("l4t_major") is not None or host.get("nvidia_kernel_driver") or host.get("windows_nvcuda")
                or any(node.get("exists") for node in (host.get("gpu_nodes") or {}).values()))


def _program_path(path: str) -> str:
    """Chemin relatif à la racine du programme, avec le séparateur du poste."""
    return on_this_host(path.replace("/", "\\"), path)


def _discovery_log(check: dict[str, Any]) -> str:
    """Journal où la découverte retenue a été lue : celui de l'instance (commande logs) ou celui de provision."""
    discovery = check.get("discovery") or {}
    if discovery.get("source") == "provision" and discovery.get("log"):
        return f"le journal d'Ollama du provisionnement ({_program_path(str(discovery['log']))})"
    return f"le journal d'Ollama ({run('logs')})"


def _superseded(check: dict[str, Any]) -> str:
    """Phrase sur une découverte plus récente mais illisible, écartée au profit de la précédente, lisible."""
    later = (check.get("discovery") or {}).get("superseded")
    if not isinstance(later, dict):
        return ""
    if later.get("source") == "provision":
        failure = f"a échoué : {later['error']}" if later.get("error") else "n'a pas pu être lue"
        text = f" La sonde de découverte du provisionnement du {_hour(later.get('utc'))} {failure}."
    else:
        text = f" La découverte de la dernière instance, du {_hour(later.get('utc'))}, est illisible."
    return text + " La découverte précédente, lisible, reste retenue."


def _legacy_proposal(check: dict[str, Any]) -> str | None:
    """Proposition d'un profil antérieur (llm.num_gpu: 0, W025 P5), d'après ce que donnerait llm.accelerator: auto."""
    preview = check.get("if_auto") or {}
    replace = "remplacez llm.num_gpu: 0 par llm.accelerator: {} dans le profil"
    libraries = check.get("libraries") or {}
    if libraries.get("required") and not libraries.get("provisioned"):
        present = f"Un GPU NVIDIA Jetson est présent ({_jetson(check.get('host') or {})})"
        complement = f"lancez {_provision_gpu()}{_complement_sizes(check)}, puis {_down_up()}"
        if _complement_qualified(check):
            return f"{present} : {replace.format('auto')}, {complement}."
        return (f"{present}, {UNQUALIFIED} : pour l'essayer, {replace.format('gpu')}, {complement}, et vérifiez la "
                f"réponse avec {run('selftest')}.")
    if preview.get("mode") == "gpu":
        return (f"Un GPU utilisable est présent : {_gpu(preview.get('device'), preview.get('variant'))}. Remplacez "
                f"llm.num_gpu: 0 par llm.accelerator: auto dans le profil, puis redémarrez ({_restart()}).")
    if preview.get("reason") == "gpu_path_not_qualified":
        return (f"GPU NVIDIA détecté sur une voie non qualifiée : {_gpu(preview.get('device'), preview.get('variant'))}. "
                f"Pour l'essayer, {replace.format('gpu')}, redémarrez ({_restart()}) puis lancez {run('selftest')}.")
    return None


def _requested_unavailable(check: dict[str, Any]) -> tuple[str, str]:
    """Message et action de `gpu_requested_unavailable` : GPU demandé par le profil, aucun GPU utilisable."""
    devices = _discovered(check)
    reason = check.get("reason")
    libraries = check.get("libraries") or {}
    missing = bool(libraries.get("required") and not libraries.get("provisioned"))
    if missing:
        detail = (f"les bibliothèques GPU d'Ollama pour ce Jetson ({_jetson(check.get('host') or {})}) ne sont pas "
                  "installées")
    elif reason == "gpu_library_not_retained":
        other = _first(devices, False)
        if is_nvidia(other):
            detail = f"le GPU NVIDIA détecté, {_gpu(other)}, n'est vu par Ollama que par Vulkan : {CUDA_NOT_RETAINED}"
        else:
            detail = f"le seul GPU détecté, {_gpu(other)}, n'emploie pas CUDA, seule bibliothèque retenue par l'atelier"
    elif reason == "gpu_mixed_libraries":
        detail = (f"un GPU NVIDIA, {_gpu(_first(devices, True))}, côtoie un GPU d'une autre bibliothèque, "
                  f"{_gpu(_first(devices, False))}, et Ollama choisirait lui-même entre les deux")
    else:
        detail = "Ollama n'a découvert aucun GPU utilisable"
    message = f"Calcul sur CPU : le profil demande le GPU (llm.accelerator: gpu), mais {detail}."
    if missing:
        action = (f"Lancez {_provision_gpu()}{_complement_sizes(check)}, puis {_down_up()} ; sinon, indiquez "
                  "llm.accelerator: auto ou cpu dans le profil.")
    else:
        action = (f"Consultez le journal d'Ollama ({run('logs')}) ; pour retirer cet avertissement, indiquez "
                  f"llm.accelerator: auto ou cpu dans le profil, puis redémarrez ({_restart()}).")
    return message, action


def _discovery_pending(check: dict[str, Any]) -> str:
    """Découverte à venir : au prochain démarrage (up), ou au redémarrage d'une instance en marche (down puis up)."""
    if check.get("running"):
        cause = ("l'instance en marche a démarré avant l'accélération GPU" if check.get("instance_predates_accelerator")
                 else "les bibliothèques GPU d'Ollama ont changé depuis le démarrage de l'instance en marche")
        return (f"Calcul sur CPU : {cause}. Le mode de calcul, GPU ou CPU, sera choisi à son redémarrage "
                f"({_restart()}).")
    if check.get("discovery_stale"):
        return ("Les bibliothèques GPU d'Ollama ont changé depuis la dernière découverte des GPU : elle sera refaite au "
                f"prochain démarrage, qui choisira le mode de calcul, GPU ou CPU ({run('up')}).")
    return ("Découverte des GPU par Ollama au prochain démarrage : le mode de calcul (GPU ou CPU) sera choisi à ce "
            f"moment ({run('up')}).")


def calcul_rubric(check: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Rubrique « calcul » et proposition éventuelle, d'après `checks["accelerator"]` (état établi par doctor).

    Une proposition n'est jamais une réserve : elle ne change pas le niveau. Les commandes citées sont celles du lanceur
    du poste (rag.ps1 ou rag.sh). Une découverte plus récente mais illisible, écartée, est signalée à la fin du message.
    """
    item, proposal = _calcul_state(check)
    note = _superseded(check)
    return ({**item, "message": item["message"] + note} if note else item), proposal


def _calcul_state(check: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    state = check.get("state")
    device, variant = check.get("device"), check.get("variant")
    devices = _discovered(check)
    host = check.get("host") or {}
    logs = run("logs")
    version = check.get("ollama_version") or "0.35.0"
    proposal: str | None = None
    if state == "cpu_imposed":
        message = "Calcul sur CPU, imposé par le profil (llm.accelerator: cpu)."
        present = _first(devices, True) or (devices[0] if devices else None)
        if present:
            message += f" GPU présent, laissé inutilisé : {_gpu(present)}."
        return rubric("calcul", GREEN, message), None
    if state == "cpu_legacy":
        return (rubric("calcul", GREEN, "Calcul sur CPU : le profil est antérieur à l'accélération GPU (llm.num_gpu: 0)."),
                _legacy_proposal(check))
    if state == "cpu_no_gpu":
        message = "Calcul sur CPU : Ollama n'a découvert aucun GPU utilisable."
        dropped = [item for item in (check.get("discovery") or {}).get("dropped") or []
                   if item.get("reason") == "integrated_gpu"]
        if dropped:
            message += " GPU intégré ignoré par Ollama : " + " ; ".join(
                f"{item.get('description') or item.get('name')} ({item.get('library')})" for item in dropped) + "."
        return rubric("calcul", GREEN, message), None
    if state == "gpu_libraries_missing":
        message = (f"Calcul sur CPU : GPU NVIDIA Jetson présent ({_jetson(host)}), mais les bibliothèques GPU "
                   "d'Ollama pour cette version ne sont pas installées.")
        proposal = (_complement_proposal(check, "Pour calculer les réponses sur le GPU") + " Pour rester sur CPU sans "
                    "cette proposition, indiquez llm.accelerator: cpu dans le profil.")
        return rubric("calcul", GREEN, message), proposal
    if state == "jetson_unsupported":
        return rubric("calcul", GREEN, f"Calcul sur CPU : Jetson Linux R{host.get('l4t_major')} n'a pas de bibliothèques "
                      f"GPU publiées pour Ollama {version} (seuls JetPack 5 et JetPack 6 en ont), et Ollama n'a découvert "
                      "aucun GPU utilisable."), None
    if state == "nvidia_not_retained":
        # Bornes basses seulement (revue B1) : un pilote plus récent reste compatible.
        proposal = (f"Ollama {version} exige une capacité de calcul 5.0 ou plus et un pilote NVIDIA 550 ou plus récent "
                    "(570 ou plus récent pour une capacité de 5.0 à 6.2) : vérifiez la version du pilote, dont la mise à "
                    f"jour relève de l'administrateur du poste, puis le journal d'Ollama ({logs}).")
        vulkan = next((item for item in devices if item.get("library") != "CUDA" and is_nvidia(item)), None)
        if vulkan:
            # Vulkan, actif par défaut dans Ollama 0.35.0, voit encore un GPU NVIDIA que CUDA a écarté.
            return rubric("calcul", GREEN, f"Calcul sur CPU : {_gpu(vulkan)} n'est vu par Ollama que par Vulkan ; "
                          f"{CUDA_NOT_RETAINED}."), proposal
        return rubric("calcul", GREEN, "Calcul sur CPU : un pilote NVIDIA est installé, mais Ollama n'a retenu aucun "
                      "GPU."), proposal
    if state == "cuda_libraries_absent":
        # Kit construit avec --without-gpu (ou fichiers retirés) : la cause est l'installation, pas le pilote.
        message = ("Calcul sur CPU : un pilote NVIDIA est installé, mais l'installation d'Ollama de ce poste ne contient "
                   "pas les bibliothèques CUDA vérifiées " + on_this_host("(kit construit sans GPU, ou fichiers retirés depuis)",
                                                             "(fichiers absents ou modifiés)")
                   + " : Ollama ne peut retenir aucun GPU NVIDIA.")
        proposal = on_this_host("Pour essayer ce GPU, réinstallez l'atelier depuis un kit complet, construit sans "
                                r"l'option --without-gpu, puis suivez la proposition de .\rag.ps1 doctor.",
                                f"Pour rétablir ces bibliothèques, relancez {run('provision --only ollama')}, puis "
                                f"{_down_up()}.")
        return rubric("calcul", GREEN, message), proposal
    if state == "gpu_not_retained":
        return rubric("calcul", GREEN, f"Calcul sur CPU : {_gpu(_first(devices, False))} détecté par Ollama, non retenu "
                      "par l'atelier, qui n'emploie que les GPU NVIDIA (CUDA)."), None
    if state == "gpu_mixed_libraries":
        cuda, other = _gpu(_first(devices, True)), _gpu(_first(devices, False))
        message = (f"Calcul sur CPU : Ollama a détecté ensemble {cuda} et {other} ; il choisirait lui-même la "
                   "bibliothèque employée, l'atelier reste donc sur CPU.")
        proposal = (f"Le GPU NVIDIA, {cuda}, serait utilisable seul, mais l'atelier ne réserve pas Ollama à CUDA faute "
                    "d'un essai réel de cette configuration. Conservez ce diagnostic pour décider d'un essai sur ce "
                    "poste, ou indiquez llm.accelerator: cpu dans le profil pour ne plus voir cette proposition.")
        return rubric("calcul", GREEN, message), proposal
    if state == "gpu_path_not_qualified":
        message = (f"Calcul sur CPU : GPU NVIDIA détecté, {_gpu(device, variant)}, {UNQUALIFIED} sur ce type de "
                   "poste.")
        proposal = (f"GPU NVIDIA détecté, voie non qualifiée : pour l'essayer, indiquez llm.accelerator: gpu dans le "
                    f"profil, redémarrez ({_restart()}) puis lancez {run('selftest')}.")
        return rubric("calcul", GREEN, message), proposal
    if state == "gpu_requested_unavailable":
        message, action = _requested_unavailable(check)
        return rubric("calcul", ORANGE, message, action), None
    if state == "gpu_libraries_unverified":
        group = ((check.get("libraries") or {}).get("variants") or {}).get(variant or "", {}).get("group")
        provision = run(f"provision --only {group}" if group else "provision")
        mismatch = ("ces bibliothèques ne correspondent pas" if variant
                    else "ses bibliothèques, dans un dossier inconnu, ne correspondent pas")
        return rubric("calcul", ORANGE, f"Calcul sur CPU : Ollama a trouvé un GPU, {_gpu(device, variant)}, mais "
                      f"{mismatch} au manifeste vérifié.",
                      on_this_host("Réinstallez l'atelier depuis le kit pour rétablir les fichiers vérifiés d'Ollama, "
                                   f"puis redémarrez ({_restart()}).",
                                   f"Relancez {provision} pour rétablir les fichiers vérifiés d'Ollama, puis "
                                   f"{_down_up()}.")), None
    if state == "gpu_rejected_by_ollama":
        return rubric("calcul", ORANGE, f"Calcul sur CPU : les bibliothèques GPU d'Ollama pour ce Jetson "
                      f"({_jetson(host)}) sont installées, mais Ollama n'a retenu aucun GPU.",
                      f"Consultez {_discovery_log(check)} : il indique pourquoi le GPU a été écarté. Pour ne plus "
                      "voir cet avertissement, indiquez llm.accelerator: cpu dans le profil."), None
    trial = check.get("reason") == "gpu_trial"
    if state == "gpu_pending":
        upcoming = check.get("next_start") if check.get("running") else None
        if upcoming:
            # Instance démarrée avant le complément GPU : elle calcule sur CPU jusqu'à son redémarrage.
            return rubric("calcul", GREEN, "Génération sur GPU au prochain démarrage de l'atelier "
                          f"({_restart()}) : {_gpu(upcoming.get('device'), upcoming.get('variant'))} ; l'instance en "
                          "marche calcule encore sur CPU."), None
        return rubric("calcul", GREEN, f"Génération sur GPU attendue au prochain démarrage : {_gpu(device, variant)}"
                      + (" ; essai sur un poste non qualifié (llm.accelerator: gpu)." if trial else ".")), None
    if state == "gpu_trial":
        return rubric("calcul", GREEN, f"Génération sur GPU, essai sur un poste non qualifié : {_gpu(device, variant)} ; "
                      f"{_loaded(check)}."), None
    if state == "gpu_ready":
        return rubric("calcul", GREEN, f"Génération sur GPU : {_gpu(device, variant)} ; {_loaded(check)}."), None
    if state == "gpu_in_use":
        return rubric("calcul", GREEN, f"Génération sur GPU : {_gpu(device, variant)}, modèle chargé à 100 % sur le "
                      "GPU."), None
    if state == "gpu_partial":
        shares = _shares((_usage(check) or {}).get("processor", ""))
        if shares is None:
            return rubric("calcul", GREEN, f"Génération sur GPU : {_gpu(device, variant)} ; {UNKNOWN_SHARE}."), None
        return rubric("calcul", GREEN, f"Génération sur GPU et CPU : {_gpu(device, variant)}, modèle chargé à "
                      f"{shares[1]} % sur le GPU et {shares[0]} % sur le CPU, selon la mémoire GPU libre au "
                      "chargement."), None
    if state == "gpu_mode_on_cpu":
        # Revue B2 : un runner chargé sur CPU sert les requêtes sans num_gpu (needsReload) ; un déchargement suffit.
        return rubric("calcul", ORANGE, f"GPU retenu, {_gpu(device, variant)}, mais le modèle est chargé entièrement "
                      "sur le CPU.",
                      f"Attendez la fin du maintien en mémoire du modèle (llm.keep_alive : {check.get('keep_alive')}) : "
                      "la question suivante le rechargera sur le GPU, sans redémarrage. S'il revient sur le CPU, "
                      f"libérez de la mémoire et consultez le journal d'Ollama ({logs})."), None
    if state == "gpu_fallback":
        fallback = check.get("fallback") or {}
        return rubric("calcul", ORANGE, f"Le chargement du modèle sur le GPU a échoué ({_hour(fallback.get('utc'))}) : "
                      "l'atelier répond sur CPU jusqu'au prochain redémarrage. Message d'Ollama (HTTP "
                      f"{fallback.get('http_status')}) : « {fallback.get('error') or 'vide'} ».",
                      f"Consultez le journal d'Ollama ({logs}), puis redémarrez ({_restart()}) pour réessayer le GPU ; "
                      "pour ne plus l'essayer, indiquez llm.accelerator: cpu dans le profil."), None
    if state == "anomaly_gpu_in_cpu_mode":
        processor = next((item.get("processor") for item in check.get("usage") or [] if item.get("size_vram")), None)
        split = f" ({processor})" if _shares(processor or "") or processor == "100% GPU" else ""
        return rubric("calcul", ORANGE, f"Anomalie : le modèle est chargé sur le GPU{split} alors que l'atelier "
                      "calcule sur CPU.",
                      f"Redémarrez l'atelier ({_restart()}) ; si l'anomalie persiste, conservez le journal d'Ollama "
                      f"({logs}). Aucune mesure de recette D07 n'est valable dans cet état."), None
    libraries = check.get("libraries") or {}
    missing = libraries.get("required") and not libraries.get("provisioned") and check.get("requested") != "cpu"
    if state == "discovery_unreadable":
        discovery = check.get("discovery") or {}
        proposal = _complement_proposal(check, "Pour calculer les réponses sur le GPU de ce Jetson") if missing else None
        if discovery.get("source") == "provision" and discovery.get("log"):
            # Sonde ou service de pull-model de provision : son journal et son erreur, pas ceux de l'instance.
            error = f" ; erreur consignée : {discovery['error']}." if discovery.get("error") else "."
            message = ("Calcul sur CPU : la découverte des GPU n'a pas pu être lue dans le journal d'Ollama du "
                       "provisionnement" + error)
            action = (f"Consultez ce journal ({_program_path(str(discovery['log']))}) ; la découverte sera relevée au "
                      f"prochain démarrage ({run('up')}), l'atelier fonctionne sur CPU d'ici là.")
        else:
            message = "Calcul sur CPU : la découverte des GPU par Ollama n'a pas pu être lue dans son journal."
            action = f"Consultez le journal d'Ollama ({logs}) ; l'atelier fonctionne sur CPU."
        if _gpu_hint(check):
            return rubric("calcul", ORANGE, message, action), proposal
        return rubric("calcul", GREEN, message), proposal
    if state == "discovery_pending":
        return rubric("calcul", GREEN, _discovery_pending(check)), None
    return rubric("calcul", ORANGE, f"Mode de calcul non établi ({check.get('error') or state or 'état inconnu'}).",
                  f"Relancez {run('doctor')} ; si l'état persiste, consultez le journal d'Ollama ({logs})."), None


def doctor_verdict(result: dict[str, Any]) -> dict[str, Any]:
    checks = result.get("checks", {})
    rubrics = [program_rubric(checks), model_rubric(checks), profile_rubric(checks), ports_rubric(checks),
               services_rubric(result), index_rubric(checks), memory_rubric(checks)]
    proposals: list[dict[str, str]] = []
    # Rubrique « calcul » en dernière position ; absente d'un résultat de doctor antérieur à W024. Le résumé renvoie à la
    # rubrique : elle porte aussi sa proposition.
    if isinstance(checks.get("accelerator"), dict):
        calcul, proposal = calcul_rubric(checks["accelerator"])
        rubrics.append({**calcul, "proposal": proposal} if proposal else calcul)
        # Seule une proposition qui mène au GPU par une action dans l'atelier est annoncée par le résumé.
        if proposal and checks["accelerator"].get("state") not in INFORMATIVE_PROPOSALS:
            proposals.append({"rubric": "calcul", "text": proposal})
    level = max((item["level"] for item in rubrics), key=SEVERITY.__getitem__)
    if level == GREEN:
        summary = f"Tout est prêt : services démarrés, {library_state(result)}, modèle vérifié."
    else:
        pending = [item["rubric"] for item in rubrics if item["level"] != GREEN]
        summary = ("Atelier inutilisable en l'état" if level == RED else "Atelier utilisable, avec réserve") + " : " + ", ".join(pending) + "."
    # Une proposition ne change jamais le niveau ; elle est signalée dans le résumé vert ou orange.
    if proposals and level != RED:
        summary += " " + PROPOSAL_SUFFIX
    return {"level": level, "summary": summary, "rubrics": rubrics, "proposals": proposals,
            "limit": "Verdict tiré des contrôles de doctor ; il ne prouve ni import, ni recherche, ni réponse réels."}
