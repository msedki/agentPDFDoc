from dataclasses import dataclass, field
from pathlib import Path
import os
from urllib.parse import urlparse

from .errors import ApiError


@dataclass
class Settings:
    root: Path
    profile: dict = field(default_factory=dict)

    @classmethod
    def load(cls, profile_path=None):
        import yaml

        root = Path(__file__).resolve().parents[2]
        path = Path(profile_path or os.environ.get("RAG_PROFILE", root / "config/local16.yaml"))
        if not path.exists() and profile_path is None:
            path = root / "RAG_Local_Agents/config/local16.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or config.get("schema_version") not in {1, 2}:
            raise ApiError("invalid_profile", "Profil de configuration invalide.")
        settings = cls(root, config)
        for domain, field_name in (("qdrant", "url"), ("llm", "base_url")):
            parsed = urlparse(settings.value(domain, field_name, ""))
            if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
                raise ApiError("invalid_profile", "Les services doivent rester sur loopback.")
        if config.get("llm", {}).get("num_gpu", 0) != 0:
            raise ApiError("invalid_profile", "Le profil exige un calcul CPU.")
        return settings

    def value(self, section, key, default=None):
        return self.profile.get(section, {}).get(key, default)

    def path(self, value):
        path = Path(value)
        return path.resolve() if path.is_absolute() else (self.root / path).resolve()

    @property
    def data_dir(self):
        return self.path(os.environ.get("RAG_DATA_DIR", self.value("app", "data_dir", ".runtime")))

    @property
    def db_path(self):
        override = os.environ.get("RAG_DB_PATH")
        return self.path(override) if override else self.data_dir / "app.sqlite3"

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.value('app', 'port', 8765)}"

    @property
    def embedding_dir(self):
        return self.path(self.value("embedding", "local_dir", ".runtime/models/e5-small-int8"))

    @property
    def llm_tokenizer_dir(self):
        return self.path(self.value("llm", "tokenizer_dir", ".runtime/models/qwen3.5-4b-tokenizer"))
