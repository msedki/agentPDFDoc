from typing import Any


def request_validation_message(fields: list[dict[str, Any]]) -> str:
    """Choisir une aide connue sans reprendre les valeurs ou messages de la requête."""
    if len(fields) == 1 and fields[0].get("loc") == ["body", "scope", "documentIds"] and fields[0].get("type") == "too_long":
        return "Le périmètre est limité à 1 000 documents sélectionnés. Réduisez la sélection, puis réessayez."
    return "Certains paramètres de la demande sont manquants ou incorrects. Vérifiez les champs renseignés, puis réessayez."


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details=None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details = details or {}
