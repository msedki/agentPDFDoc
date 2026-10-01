import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .errors import ApiError
from .security import scheme_for

# Clés du profil dont le code ne met en œuvre qu'une valeur (constat C6 de l'inspection du 1er octobre 2026) :
# lues au chargement, toute autre valeur est refusée au démarrage au lieu d'être ignorée en silence.
# Une clé absente garde la valeur mise en œuvre.
FIXED_PROFILE_VALUES: dict[tuple[str, ...], object] = {
    ("app", "log_document_text"): False,
    ("llm", "provider"): "ollama",
    ("llm", "max_active_generations"): 1,
    ("embedding", "backend"): "onnxruntime",
    ("embedding", "provider"): "CPUExecutionProvider",
    ("embedding", "weights_precision"): "int8",
    ("embedding", "dimensions"): 384,
    ("embedding", "query_prefix"): "query: ",
    ("embedding", "passage_prefix"): "passage: ",
    ("embedding", "normalize_l2"): True,
    # Bornes et réglage de la session E5 codés dans embedding.py, fichier haché par l'identité du sélecteur
    # (`selector_sha256` des évaluations) : contrôlés ici pour ne pas changer cette identité.
    ("embedding", "max_model_tokens"): 512,
    ("embedding", "allow_spinning"): False,
    ("chunking", "max_prefixed_tokens"): 448,
    ("chunking", "tokenizer"): "embedding",
    ("chunking", "respect_section_boundaries"): True,
    ("retrieval", "reranker"): False,
    ("retrieval", "history_is_evidence"): False,
    ("retrieval", "exact_identifier_final_coverage_required"): True,
    ("retrieval", "context_coverage_check_required"): True,
    ("qdrant", "distance"): "Cosine",
    ("qdrant", "vector_dimensions"): 384,
    ("qdrant", "wait_for_upserts"): True,
    ("qdrant", "collection_api_contract_check_required"): True,
    ("qdrant", "model_identity_in_collection_name_required"): True,
    ("sqlite", "journal_mode"): "WAL",
    ("sqlite", "foreign_keys"): True,
    ("sqlite", "fts_tokenizer"): "unicode61 remove_diacritics 2",
    ("resources", "scheduling", "pause_policy"): "cooperative_checkpoint",
    ("resources", "scheduling", "kill_on_interactive_request"): False,
}

_MISSING = object()


def unsupported_profile_values(config: dict) -> list[str]:
    """Clés de `FIXED_PROFILE_VALUES` présentes avec une autre valeur que celle mise en œuvre (types compris)."""
    refused = []
    for path, expected in FIXED_PROFILE_VALUES.items():
        node: object = config
        for name in path:
            node = node.get(name, _MISSING) if isinstance(node, dict) else _MISSING
        if node is not _MISSING and (type(node) is not type(expected) or node != expected):
            refused.append(".".join(path))
    return refused


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
        refused = unsupported_profile_values(config)
        if refused:
            raise ApiError("invalid_profile", "Valeurs du profil non prises en charge par cette version : " + ", ".join(refused)
                           + ". Rétablir les valeurs du profil livré (config/local16.yaml).", 400, {"keys": refused})
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
