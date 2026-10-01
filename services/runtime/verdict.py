"""Verdict de `doctor` par rubrique (DIST-05) : vert, orange ou rouge, avec un message et l'action possible.

Lit seulement le résultat de `doctor` : aucun service, fichier ni processus n'est interrogé ici. Rubriques et ton des
messages suivent le parcours d'installation de l'analyse de distribution (section 7.1, étapes 7 à 10). Rouge : l'atelier
ne peut pas fonctionner ; orange : il fonctionne, ou fonctionnera après une action ordinaire (démarrer, libérer de la
mémoire) ; vert : rien à faire. Le verdict ne remplace pas un contrôle réel (import, recherche, réponse).
"""

from __future__ import annotations

from typing import Any

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


def rubric(name: str, level: str, message: str, action: str | None = None) -> dict[str, Any]:
    return {"rubric": name, "level": level, "message": message, **({"action": action} if action else {})}


def program_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    missing = [label for key, label in PROGRAM_FILES.items() if checks.get(key) is not True]
    missing += [f"langue OCR {name}" for name, present in sorted(checks.get("ocr_languages", {}).items()) if not present]
    if "error" in checks.get("native_binaries", {}):
        missing.append(f"binaires Qdrant et Ollama ({checks['native_binaries']['error']})")
    if missing:
        return rubric("programme", RED, "Fichiers du programme absents ou incomplets : " + ", ".join(missing) + ".",
                      "Réinstallez l'atelier depuis le kit ; les données de l'utilisateur ne sont pas touchées.")
    return rubric("programme", GREEN, "Fichiers du programme présents.")


def model_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    lock = checks.get("model_lock", {})
    if lock.get("status") == "invalid_lock":
        return rubric("modèle", RED, f"Verrou des modèles illisible : {lock.get('reason', 'raison inconnue')}.",
                      "Réinstallez l'atelier depuis le kit.")
    if lock.get("profile_models_locked") is False:
        return rubric("modèle", RED, "Le modèle déclaré par le profil ne figure pas dans config/models.lock.json.",
                      "Rétablissez le profil généré à l'installation ou réinstallez l'atelier.")
    models = lock.get("models", {})
    absent = sorted(name for name, model in models.items() if model.get("status") == "absent")
    altered = {name: model for name, model in sorted(models.items()) if model.get("status") == "nonconform"}
    if absent:
        return rubric("modèle", RED, "Modèle absent du stockage local : " + ", ".join(absent) + ".",
                      r"Lancez .\rag.ps1 pull-model -Offline ; s'il échoue, réinstallez l'atelier depuis le kit.")
    if altered:
        detail = "; ".join(f"{name} ({', '.join(sorted({issue.get('issue', '?') for issue in model.get('issues', [])}))})"
                           for name, model in altered.items())
        return rubric("modèle", RED, f"Modèle différent du verrou : {detail}.",
                      "Réinstallez l'atelier depuis le kit pour retrouver les fichiers vérifiés.")
    if lock.get("status") != "conform":
        return rubric("modèle", RED, f"Conformité du modèle non établie (état {lock.get('status', 'inconnu')}).",
                      r"Relancez .\rag.ps1 doctor ; si l'état persiste, réinstallez l'atelier.")
    return rubric("modèle", GREEN, "Modèle vérifié contre le verrou : " + ", ".join(sorted(models)) + ".")


def profile_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    storage = checks.get("qdrant_storage", {})
    if storage.get("status") != "valid":
        return rubric("profil", RED, f"Stockage de l'index refusé : {storage.get('reason', 'raison inconnue')}.",
                      "Indiquez dans le profil un dossier court et vide pour qdrant.storage_dir, puis relancez.")
    application = checks.get("profile_application", {}).get("status")
    if application == "restart_required":
        return rubric("profil", ORANGE, "Le profil a changé depuis le démarrage de l'atelier : l'instance applique encore l'ancien.",
                      r"Redémarrez : .\rag.ps1 down puis .\rag.ps1 up.")
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
        return rubric("services", ORANGE, "Atelier arrêté.", r"Démarrez-le : .\rag.ps1 up, ou ouvrez-le par .\rag.ps1 open.")
    if state == "stale":
        return rubric("services", ORANGE, "État d'exécution périmé : le superviseur s'est arrêté sans le mettre à jour.",
                      r"Relancez l'atelier : .\rag.ps1 up.")
    if state in {"starting", "stopping"}:
        return rubric("services", ORANGE, "Atelier en cours de " + ("démarrage." if state == "starting" else "arrêt."),
                      r"Relancez .\rag.ps1 doctor dans une minute.")
    ready = result.get("services", {}).get("api_ready", {})
    body = ready.get("body") if isinstance(ready.get("body"), dict) else {}
    if ready.get("http_status") != 200:
        blocked = [READINESS_LABELS.get(key, key) for key, value in body.get("checks", {}).items() if not value]
        detail = ", ".join(blocked) if blocked else "API injoignable"
        if body.get("qdrant_collection") == "absent_with_published_generations":
            detail += " ; collection Qdrant absente alors que des documents sont publiés"
        return rubric("services", RED, f"Atelier démarré mais pas prêt : {detail}.",
                      r"Consultez les journaux (.\rag.ps1 logs). Une collection perdue ne se recrée pas sur place : restaurez une "
                      r"sauvegarde dans une racine neuve (.\rag.ps1 restore -Path <sauvegarde> -Target <racine neuve>).")
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
    return rubric("index", ORANGE, f"Cohérence de l'index non vérifiée ({reason}).", r"Démarrez l'atelier puis relancez .\rag.ps1 doctor.")


def memory_rubric(checks: dict[str, Any]) -> dict[str, Any]:
    refused = [(ADMISSION_OWNERS[owner], value) for owner, value in checks.get("cold_admission", {}).items()
               if owner in ADMISSION_OWNERS and isinstance(value, dict) and not value.get("admissible_now")]
    if refused:
        detail = " ; ".join(f"{label} non admise maintenant : {mib(value['available_mib'])} disponibles, {mib(value['required_available_mib'])} requis"
                            for label, value in refused)
        return rubric("mémoire", ORANGE, detail + ". L'atelier fonctionne ; les traitements attendent que la mémoire se libère.",
                      "Fermez des applications avant de poser une question ou d'importer des documents.")
    return rubric("mémoire", GREEN, "Mémoire suffisante pour l'extraction et la génération.")


def doctor_verdict(result: dict[str, Any]) -> dict[str, Any]:
    checks = result.get("checks", {})
    rubrics = [program_rubric(checks), model_rubric(checks), profile_rubric(checks), ports_rubric(checks),
               services_rubric(result), index_rubric(checks), memory_rubric(checks)]
    level = max((item["level"] for item in rubrics), key=SEVERITY.__getitem__)
    if level == GREEN:
        summary = f"Tout est prêt : services démarrés, {library_state(result)}, modèle vérifié."
    else:
        pending = [item["rubric"] for item in rubrics if item["level"] != GREEN]
        summary = ("Atelier inutilisable en l'état" if level == RED else "Atelier utilisable, avec réserve") + " : " + ", ".join(pending) + "."
    return {"level": level, "summary": summary, "rubrics": rubrics,
            "limit": "Verdict tiré des contrôles de doctor ; il ne prouve ni import, ni recherche, ni réponse réels."}
