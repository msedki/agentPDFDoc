"""One generative model and mandatory source checks at live entry points.

Historical profile readers remain available for stopping/exporting an old
instance. Loading an API or starting generation is a separate operation.
"""

from .profile_schema import ProfileValidationError

GENERATION_MODEL = "qwen3-4b-enhanced:q4km"
GENERATION_PROFILE = "config/enhanced-4b.yaml"
REQUIRED_GENERATION_VALUES = {
    "schema_version": 2,
    "llm.provider": "ollama",
    "llm.model": GENERATION_MODEL,
    "llm.source_model": GENERATION_MODEL,
    "llm.required_family": "qwen3",
    "llm.required_parameter_size": "4.0B",
    "llm.required_quantization": "Q4_K_M",
    "llm.think": False,
    "enhanced.preserve_evidence": True,
    "enhanced.answer_contract": True,
    "enhanced.explicit_pdf_lists": True,
    "enhanced.property_coverage_selection": True,
    "retrieval.history_is_evidence": False,
}


def require_generation_profile(config: dict) -> None:
    """Validate configuration before any model/service launch, without repair.

    Native manifest/digest and Ollama model identity verification remain required;
    a matching tag here alone does not qualify model bytes or answer quality.
    """
    invalid = []
    for path, expected in REQUIRED_GENERATION_VALUES.items():
        value: object = config
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if type(value) is not type(expected) or value != expected:
            invalid.append(path)
    if invalid:
        raise ProfileValidationError(
            "La génération exige le profil renforcé Qwen3-4B Q4_K_M et ses contrôles de preuves. "
            "Utiliser config/enhanced-4b.yaml ; le profil historique reste lisible pour arrêter ou sauvegarder son instance.",
            invalid)
