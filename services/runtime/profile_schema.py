"""Validation stricte partagée ; le dictionnaire YAML reste l'identité du profil.

Les défauts de ces modèles servent à contrôler les relations des valeurs absentes,
pas à enrichir le profil remis aux consommateurs. Les chemins restent des chaînes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveNumber = Annotated[float, Field(gt=0)]
NonNegativeNumber = Annotated[float, Field(ge=0)]
Ratio = Annotated[float, Field(ge=0, le=1)]
Port = Annotated[int, Field(ge=1, le=65535)]


class Section(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class App(Section):
    host: str = "127.0.0.1"
    port: Port = 8785
    asgi_workers: PositiveInt = 1
    data_dir: str = ".runtime/data"
    offline: bool = True
    telemetry: bool = False
    log_document_text: bool = False


class OutputBudgets(Section):
    factual: PositiveInt = 384
    ordinary: PositiveInt = 768
    analysis: PositiveInt = 768
    compare: PositiveInt = 768


class Llm(Section):
    base_url: str
    provider: str = "ollama"
    model: str = ""
    source_model: str = ""
    model_manifest: str = ""
    source_model_manifest: str = ""
    required_quantization: str = ""
    num_ctx: PositiveInt = 8192
    num_predict: PositiveInt = 768
    temperature: NonNegativeNumber = 0.2
    top_p: Ratio = 0.9
    think: bool = False
    accelerator: str = "auto"
    num_gpu: NonNegativeInt = 0
    threads_max: PositiveInt = 4
    # Duration.UnmarshalJSON d'Ollama 0.35.0 admet durée texte et secondes numériques.
    keep_alive: str | int | float = "10m"
    prompt_cache_mib: NonNegativeInt = 256
    context_checkpoints_max: NonNegativeInt = 2
    connect_timeout_seconds: PositiveNumber = 5
    idle_read_timeout_seconds: PositiveNumber = 300
    max_active_generations: PositiveInt = 1
    max_pending_generations: NonNegativeInt = 2
    output_tokens_by_mode: OutputBudgets = Field(default_factory=OutputBudgets)
    tokenizer_model_id: str = ""
    tokenizer_dir: str = ""


class EmbeddingQualification(Section):
    baseline_required: bool = True
    candidate_model_id: str = ""
    max_candidates: NonNegativeInt = 1
    verify_official_artifact_before_use: bool = True
    if_candidate_unverifiable: str = "retain_baseline_and_report"
    simultaneous_models: bool = False


class Embedding(Section):
    model_id: str = "intfloat/multilingual-e5-small"
    local_dir: str = ".runtime/models/e5-small-int8"
    backend: str = "onnxruntime"
    provider: str = "CPUExecutionProvider"
    weights_precision: str = "int8"
    dimensions: PositiveInt = 384
    query_prefix: str = "query: "
    passage_prefix: str = "passage: "
    normalize_l2: bool = True
    max_model_tokens: PositiveInt = 512
    batch_size: PositiveInt = 8
    intra_op_threads: NonNegativeInt = 2
    inter_op_threads: NonNegativeInt = 1
    allow_spinning: bool = False
    qualification: EmbeddingQualification = Field(default_factory=EmbeddingQualification)
    onnx_file: str = "model.onnx"


class Pdf(Section):
    parser: str = "docling_router"
    device: str = "cpu"
    worker_processes: PositiveInt = 1
    threads_max: PositiveInt = 2
    table_mode: str = "accurate_when_structured"
    ocr_engine: str = "tesseract_cli"
    ocr_languages: list[str] = Field(default_factory=lambda: ["fra", "eng"])
    ocr_policy: str = "selective_regions"
    enable_remote_services: bool = False
    generate_page_images: bool = False
    picture_description: bool = False
    # Le pilote e2e_instance accepte aussi une limite fractionnaire en Mio.
    max_file_mib: PositiveNumber = 200
    max_document_pages: PositiveInt = 2000
    max_page_render_pixels: PositiveInt = 8_000_000
    max_ocr_region_pixels: PositiveInt = 13_000_000
    suspect_text_min_alnum_chars: NonNegativeInt = 40
    suspect_text_max_replacement_ratio: Ratio = 0.02
    routes: list[str] = Field(default_factory=lambda: ["native", "structured", "regional_ocr"])
    native_parser_threads: PositiveInt = 2
    model_inference_threads: PositiveInt = 2
    checkpoint_window_pages_initial: PositiveInt = 4
    coverage_unit: str = "region"
    native_route_requires_quality_gate: bool = True
    ocr_mode_requested: str = "pdf_aware_layout_regions"
    parser_api_contract_check_required: bool = True
    artifacts_path: str = ".runtime/models/docling"
    tesseract_cmd: str = "tesseract"
    tessdata_dir: str = ".runtime/models/tessdata"
    pdf_backend: str = "pypdfium2"
    ocr_intrinsic_aspect: bool = True
    ocr_cell_ink_crop: bool = True
    ocr_min_word_confidence: Ratio = 0.8


class Office(Section):
    max_members: PositiveInt = 10_000
    max_total_bytes: PositiveInt = 268_435_456
    max_part_bytes: PositiveInt = 67_108_864
    max_compression_ratio: PositiveInt = 1_000
    max_xml_depth: PositiveInt = 128
    max_elements: PositiveInt = 2_000_000
    max_blocks: PositiveInt = 100_000
    max_cells: PositiveInt = 100_000
    max_shared_strings: PositiveInt = 100_000
    max_units: PositiveInt = 10_000
    max_text_chars: PositiveInt = 20_000_000
    max_cell_chars: PositiveInt = 100_000
    max_block_chars: PositiveInt = 8_000


class Chunking(Section):
    tokenizer: str = "embedding"
    target_tokens: PositiveInt = 320
    max_prefixed_tokens: PositiveInt = 448
    overlap_max_tokens: NonNegativeInt = 48
    respect_section_boundaries: bool = True
    parent_expand_max_llm_tokens: PositiveInt = 900


class EvidenceBudgets(Section):
    factual: PositiveInt = 1536
    ordinary: PositiveInt = 2560
    analysis: PositiveInt = 4864
    compare: PositiveInt = 4864


class Retrieval(Section):
    dense_top_k: NonNegativeInt = 24
    lexical_top_k: NonNegativeInt = 24
    rrf_k: NonNegativeInt = 60
    final_max_fragments: PositiveInt = 6
    hnsw_ef: PositiveInt = 64
    reranker: bool = False
    max_evidence_llm_tokens: PositiveInt = 5120
    max_history_llm_tokens: NonNegativeInt = 512
    max_instructions_question_llm_tokens: PositiveInt = 1024
    context_safety_tokens: NonNegativeInt = 256
    constrained_max_fragments: PositiveInt = 8
    exact_identifier_final_coverage_required: bool = True
    context_coverage_check_required: bool = True
    evidence_tokens_by_mode: EvidenceBudgets = Field(default_factory=EvidenceBudgets)
    history_is_evidence: bool = False


class Qdrant(Section):
    url: str
    collection: str = "pdf_chunks_e5small_v1"
    storage_dir: str = ""
    distance: str = "Cosine"
    vector_dimensions: PositiveInt = 384
    upsert_batch_size: PositiveInt = 64
    wait_for_upserts: bool = True
    vector_storage_initial: str = "mapped"
    hnsw_storage_initial: str = "ram_or_cached"
    collection_api_contract_check_required: bool = True
    model_identity_in_collection_name_required: bool = True


class Sqlite(Section):
    path: str = ".runtime/data/app.sqlite3"
    journal_mode: str = "WAL"
    foreign_keys: bool = True
    busy_timeout_ms: PositiveInt = 5000
    cache_size_kib: PositiveInt = 32768
    fts_tokenizer: str = "unicode61 remove_diacritics 2"


class Scheduling(Section):
    initial_mode: str = "interactive"
    pause_policy: str = "cooperative_checkpoint"
    kill_on_interactive_request: bool = False
    auto_resume_ingestion: bool = False
    watchdog_no_progress_seconds_initial: PositiveNumber = 300
    watchdog_window_seconds_initial: PositiveNumber = 900
    record_checkpoint_and_reload_costs: bool = True


class Resources(Section):
    application_target_max_mib: PositiveNumber = 10240
    host_available_min_mib: NonNegativeNumber = 1536
    admit_heavy_min_available_mib: NonNegativeNumber = 3072
    sampling_interval_seconds: PositiveNumber = 1
    unload_llm_before_ingestion: bool = True
    initial_llm_load_peak_estimate_mib: NonNegativeNumber = 3968
    warm_llm_additional_peak_estimate_mib: NonNegativeNumber = 512
    embedding_load_peak_estimate_mib: NonNegativeNumber = 768
    generation_admission_wait_seconds: NonNegativeNumber = 0
    initial_parser_peak_estimate_mib: NonNegativeNumber = 2304
    scheduling: Scheduling = Field(default_factory=Scheduling)


class Security(Section):
    environment: Literal["development", "production"] = "development"
    session_idle_minutes: PositiveInt = 120
    session_absolute_hours: PositiveInt = 12
    launch_link_ttl_seconds: Annotated[int, Field(gt=0, le=3600)] = 300
    tls_cert_file: str | None = None
    tls_key_file: str | None = None


class Ui(Section):
    pdf_max_high_resolution_canvases: PositiveInt = 5
    pdf_max_device_pixel_ratio: PositiveNumber = 2
    default_scope: str = "document_if_open_else_library"
    citation_navigation_preserves_scope: bool = True
    assets_local_only: bool = True
    pdf_max_total_raster_pixels: PositiveInt = 24_000_000
    include_thumbnails_in_raster_budget: bool = True
    selection_offset_unit: str = "unicode_code_point"
    selection_requires_text_hash: bool = True


class EvaluationTargets(Section):
    retrieval_p95_seconds: PositiveNumber = 3
    warm_ttft_p95_seconds: PositiveNumber = 45
    warm_answer_400_tokens_p95_seconds: PositiveNumber = 180
    recall_at_10_min: Ratio = 0.9
    supported_claim_ratio_min: Ratio = 0.95
    no_answer_correct_ratio_min: Ratio = 0.9
    citation_integrity_ratio: Ratio = 1.0
    scope_leakage_count: NonNegativeInt = 0
    evidence_coverage_at_context_min: Ratio = 0.9
    answer_correctness_on_answerable_min: Ratio = 0.85
    qualification_questions: PositiveInt = 200
    development_questions: NonNegativeInt = 100
    heldout_questions: NonNegativeInt = 100
    heldout_unanswerable_questions: NonNegativeInt = 20


class Runtime(Section):
    host_lock_path: str = ".runtime/control/host-heavy.lock"
    backups_dir: str = ".runtime/backups"
    restore_storage_dir: str = ".runtime/restore"
    huggingface_cache_dir: str = ".runtime/cache/huggingface"


class Profile(Section):
    schema_version: Annotated[int, Field(ge=1, le=2)]
    profile: str = "local16"
    baseline: str = ""
    app: App = Field(default_factory=App)
    llm: Llm
    embedding: Embedding = Field(default_factory=Embedding)
    pdf: Pdf = Field(default_factory=Pdf)
    office: Office = Field(default_factory=Office)
    chunking: Chunking = Field(default_factory=Chunking)
    retrieval: Retrieval = Field(default_factory=Retrieval)
    qdrant: Qdrant
    sqlite: Sqlite = Field(default_factory=Sqlite)
    resources: Resources = Field(default_factory=Resources)
    security: Security = Field(default_factory=Security)
    ui: Ui = Field(default_factory=Ui)
    evaluation_targets: EvaluationTargets = Field(default_factory=EvaluationTargets)
    runtime: Runtime = Field(default_factory=Runtime)


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


class ProfileValidationError(ValueError):
    """Erreur sans valeurs d'entrée ; chemins de clés utilisables par les deux frontières."""

    def __init__(self, message: str, keys: list[str]):
        super().__init__(message)
        self.keys = keys


def read_profile_document(path: Path) -> dict:
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise ProfileValidationError("Document YAML du profil invalide.", []) from None
    if not isinstance(config, dict):
        raise ProfileValidationError("Le profil doit être une table YAML.", [])
    return config


def refuse_relation(message: str, *keys: str) -> None:
    raise ProfileValidationError(message, list(keys))


def validate_profile(config: dict, *, consumer: Literal["api", "runtime"]) -> dict:
    """Refuse types, clés et relations invalides, puis rend l'objet original sans normalisation."""
    refused = unsupported_profile_values(config)
    if refused:
        raise ProfileValidationError(
            "Valeurs du profil non prises en charge par cette version : " + ", ".join(refused)
            + ". Rétablir les valeurs du profil livré (config/local16.yaml).", refused)
    try:
        profile = Profile.model_validate(config)
    except ValidationError as error:
        errors = error.errors(include_input=False, include_url=False, include_context=False)
        keys = list(dict.fromkeys(".".join(map(str, item["loc"])) for item in errors))
        types = ", ".join(f'{".".join(map(str, item["loc"]))}: {item["type"]}' for item in errors)
        raise ProfileValidationError("Profil de configuration invalide : " + types + ".", keys) from None
    if consumer == "runtime":
        if profile.schema_version != 2:
            refuse_relation("Profil version2 requis", "schema_version")
        # Indexations directes de supervisor, cli/provisioning et backup : pas de défaut à cet endroit.
        required = (("app", "host"), ("app", "data_dir"), ("app", "port"),
                    ("llm", "num_ctx"), ("llm", "model"), ("llm", "tokenizer_dir"),
                    ("embedding", "local_dir"), ("embedding", "onnx_file"),
                    ("pdf", "artifacts_path"), ("pdf", "tessdata_dir"), ("pdf", "tesseract_cmd"),
                    ("pdf", "ocr_languages"))
        missing = [f"{section}.{key}" for section, key in required
                   if key not in config.get(section, {}) or config[section][key] == ""]
        if "sqlite" not in config:
            missing.append("sqlite")
        if missing:
            raise ProfileValidationError("Clés requises par le runtime absentes : " + ", ".join(missing) + ".", missing)
    if profile.office.max_part_bytes > profile.office.max_total_bytes:
        refuse_relation("Une partie Office dépasse le budget total du conteneur.",
                        "office.max_part_bytes", "office.max_total_bytes")
    chunk = profile.chunking
    if chunk.target_tokens > chunk.max_prefixed_tokens:
        refuse_relation("La cible des fragments dépasse leur budget préfixé.",
                        "chunking.target_tokens", "chunking.max_prefixed_tokens")
    if chunk.overlap_max_tokens >= chunk.target_tokens:
        refuse_relation("Le chevauchement doit rester inférieur à la cible des fragments.",
                        "chunking.overlap_max_tokens", "chunking.target_tokens")
    llm, retrieval = profile.llm, profile.retrieval
    if (retrieval.max_evidence_llm_tokens + retrieval.max_history_llm_tokens
            + retrieval.max_instructions_question_llm_tokens + llm.num_predict
            + retrieval.context_safety_tokens > llm.num_ctx):
        refuse_relation("Les budgets de preuve, historique, instructions, sortie et marge dépassent le contexte.",
                        "llm.num_ctx", "llm.num_predict", "retrieval.max_evidence_llm_tokens",
                        "retrieval.max_history_llm_tokens", "retrieval.max_instructions_question_llm_tokens",
                        "retrieval.context_safety_tokens")
    for section, budgets, maximum, key in (
        ("llm", llm.output_tokens_by_mode, llm.num_predict, "num_predict"),
        ("retrieval", retrieval.evidence_tokens_by_mode, retrieval.max_evidence_llm_tokens, "max_evidence_llm_tokens"),
    ):
        # ContextBuilder demande 384/768 tokens pour les sorties absentes, avant Ollama.chat_options.
        # Ses budgets de preuve absents sont en revanche clampés par max_evidence_llm_tokens.
        modes = type(budgets).model_fields if section == "llm" else budgets.model_fields_set
        for mode in modes:
            if getattr(budgets, mode) > maximum:
                refuse_relation("Un budget de mode dépasse son plafond.", f"{section}.output_tokens_by_mode.{mode}"
                                if section == "llm" else f"{section}.evidence_tokens_by_mode.{mode}", f"{section}.{key}")
    security = profile.security
    if security.session_idle_minutes * 60 > security.session_absolute_hours * 3600:
        refuse_relation("L'inactivité ne peut dépasser la durée absolue de session.",
                        "security.session_idle_minutes", "security.session_absolute_hours")
    if security.environment == "production" and not (security.tls_cert_file and security.tls_key_file):
        refuse_relation("Production : certificat et clé TLS du profil requis.",
                        "security.tls_cert_file", "security.tls_key_file")
    ports = {"app.port": profile.app.port}
    for key, value in (("llm.base_url", llm.base_url), ("qdrant.url", profile.qdrant.url)):
        try:
            explicit_port = urlsplit(value).port
        except ValueError:
            refuse_relation("Port de service invalide.", key)
        port = explicit_port if explicit_port is not None else 80
        if port <= 0:
            refuse_relation("Port de service invalide.", key)
        ports[key] = port
    if len(set(ports.values())) != len(ports):
        duplicates = [key for key, port in ports.items() if list(ports.values()).count(port) > 1]
        raise ProfileValidationError("Les ports de l'API, de Qdrant et d'Ollama doivent être distincts.", duplicates)
    return config
