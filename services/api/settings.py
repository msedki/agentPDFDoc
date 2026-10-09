import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from services.runtime.accelerator import (
    LLM_SECTION_MESSAGE,
    REASON_TEXTS,
    AcceleratorProfileError,
    profile_accelerator,
)
from services.runtime.profile_schema import FIXED_PROFILE_VALUES as FIXED_PROFILE_VALUES
from services.runtime.profile_schema import ProfileValidationError, read_profile_document, validate_profile
from services.runtime.profile_schema import unsupported_profile_values as unsupported_profile_values

from .errors import ApiError
from .security import scheme_for

# Raisons de resolve_mode propres à chaque mode (W025) : une raison transmise qui contredit le mode est ignorée.
GPU_REASONS = frozenset({"gpu_discovered", "gpu_trial"})



@dataclass
class Settings:
    root: Path
    profile: dict = field(default_factory=dict)

    @classmethod
    def load(cls, profile_path=None):
        root = Path(__file__).resolve().parents[2]
        path = Path(profile_path or os.environ.get("RAG_PROFILE", root / "config/local16.yaml"))
        if not path.exists() and profile_path is None:
            path = root / "RAG_Local_Agents/config/local16.yaml"
        try:
            config = read_profile_document(path)
        except ProfileValidationError as error:
            raise ApiError("invalid_profile", str(error), 400, {"keys": error.keys}) from error
        if type(config.get("schema_version")) is not int or config.get("schema_version") not in {1, 2}:
            raise ApiError("invalid_profile", "Profil de configuration invalide.", 400, {"keys": ["schema_version"]})
        settings = cls(root, config)
        # Sections lues dès le chargement : présentes, elles doivent être des tables (relecture J11.9 : une section llm
        # en liste levait AttributeError dans `value`). Absentes, la règle de boucle locale ci-dessous les refuse.
        for section, message in (("qdrant", "La section qdrant du profil n'est pas une table."),
                                 ("llm", LLM_SECTION_MESSAGE)):
            if section in config and not isinstance(config[section], dict):
                raise ApiError("invalid_profile", message, 400, {"keys": [section]})
        for domain, field_name in (("qdrant", "url"), ("llm", "base_url")):
            value = settings.value(domain, field_name, "")
            try:
                parsed = urlparse(value) if isinstance(value, str) else None
                local = (parsed is not None and parsed.scheme == "http"
                         and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                         and parsed.username is None and parsed.password is None
                         and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment)
            except ValueError:
                local = False
            if not local:
                raise ApiError("invalid_profile", "Les services doivent rester sur loopback.")
        try:
            profile_accelerator(config)
        except AcceleratorProfileError as error:
            # Mêmes messages que le superviseur (services/runtime/accelerator.py).
            raise ApiError("invalid_profile", str(error), 400, {"keys": list(error.keys)}) from error
        try:
            validate_profile(config, consumer="api")
        except ProfileValidationError as error:
            raise ApiError("invalid_profile", str(error), 400, {"keys": error.keys}) from error
        return settings

    def value(self, section, key, default=None):
        return self.profile.get(section, {}).get(key, default)

    def path(self, value):
        path = Path(value)
        return path.resolve() if path.is_absolute() else (self.root / path).resolve()

    @property
    def llm_accelerator(self):
        """Accélération demandée par le profil et mode de génération décidé par le superviseur au démarrage (W025).

        Le superviseur transmet sa décision à l'API seule (`RAG_LLM_ACCELERATOR`, `RAG_LLM_ACCELERATOR_REASON`). Le GPU
        n'est retenu que si le profil le permet (auto ou gpu) et que la décision vaut `gpu` ; sans décision (API lancée
        hors superviseur, tests), la génération reste sur CPU comme avant W024, avec une raison nulle.
        """
        requested = profile_accelerator({**self.profile, "llm": self.profile.get("llm") or {}})
        if requested["requested"] == "cpu":
            legacy = requested["requested_source"] == "legacy_num_gpu"
            return {**requested, "mode": "cpu", "reason": "legacy_profile_cpu" if legacy else "imposed_by_profile"}
        decided = os.environ.get("RAG_LLM_ACCELERATOR")
        mode = "gpu" if decided == "gpu" else "cpu"
        reason = os.environ.get("RAG_LLM_ACCELERATOR_REASON")
        if decided not in ("gpu", "cpu") or reason not in REASON_TEXTS or (reason in GPU_REASONS) != (mode == "gpu"):
            reason = None
        return {**requested, "mode": mode, "reason": reason}

    @property
    def data_dir(self):
        return self.path(os.environ.get("RAG_DATA_DIR", self.value("app", "data_dir", ".runtime")))

    @property
    def db_path(self):
        override = os.environ.get("RAG_DB_PATH")
        return self.path(override) if override else self.data_dir / "app.sqlite3"

    @property
    def qdrant_headers(self):
        """En-tête `api-key` de l'instance : variable du superviseur, sinon fichier de contrôle de la racine."""
        key = os.environ.get("RAG_QDRANT_API_KEY")
        if not key:
            path = self.data_dir / "control" / "qdrant-api-key"
            key = path.read_text(encoding="ascii").strip() if path.exists() else ""
        return {"api-key": key} if key else {}

    @property
    def origin(self):
        """Origine servie par l'API locale : HTTPS en production (W011), HTTP en développement."""
        return f"{scheme_for(self.value('security', 'environment', 'development'))}://127.0.0.1:{self.value('app', 'port', 8785)}"

    @property
    def origin_certificate(self):
        """Certificat du profil qu'un client de l'API locale vérifie en production ; None en développement (HTTP)."""
        security = self.profile.get("security") or {}
        if security.get("environment") == "production" and security.get("tls_cert_file"):
            return self.path(security["tls_cert_file"])
        return None

    @property
    def embedding_dir(self):
        return self.path(self.value("embedding", "local_dir", ".runtime/models/e5-small-int8"))

    @property
    def llm_tokenizer_dir(self):
        return self.path(self.value("llm", "tokenizer_dir", ".runtime/models/qwen3.5-4b-tokenizer"))
