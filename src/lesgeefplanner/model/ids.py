"""Id-generatie, los van model/__init__.py om circulaire imports te vermijden."""
import uuid


def nieuw_id() -> str:
    """Genereert een nieuw, uniek object-id. Wordt nooit hergebruikt of herberekend."""
    return uuid.uuid4().hex
