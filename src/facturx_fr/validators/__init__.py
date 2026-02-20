"""Validation XSD et schématrons pour les factures électroniques.

FR: Point d'entrée principal pour la validation de factures.
    validate_xml() combine XSD + schématrons EN16931.
    validate_xsd() effectue uniquement la validation XSD.
    validate_schematron() effectue uniquement la validation schématron.
EN: Main entry point for invoice validation.
"""

import logging

from facturx_fr.validators.schematron import validate_schematron
from facturx_fr.validators.xsd import validate_xsd

logger = logging.getLogger(__name__)

# Profils pour lesquels le schématron est applicable
# (Minimum et BasicWL n'ont pas de lignes de détail → pas de schématron)
_SCHEMATRON_PROFILES = {"basic", "en16931", "extended"}


def validate_xml(
    xml_bytes: bytes,
    flavor: str = "factur-x",
    profile: str = "autodetect",
) -> list[str]:
    """Point d'entrée principal — XSD puis schématrons EN16931.

    FR: Valide un XML de facture contre le XSD puis les schématrons EN16931
        (si saxonche est installé et le profil le supporte). Si le XSD échoue,
        les erreurs schématron ne sont pas ajoutées (faux positifs probables).
    EN: Validates an invoice XML against XSD then EN16931 schematrons.

    Args:
        xml_bytes: Le contenu XML à valider.
        flavor: Le format de facture ("factur-x").
        profile: Le profil ("en16931", "extended", etc.) ou "autodetect".

    Returns:
        Liste des messages d'erreur (vide si valide).
    """
    # 1. Validation XSD
    xsd_errors = validate_xsd(xml_bytes, flavor=flavor, profile=profile)
    if xsd_errors:
        return xsd_errors

    # 2. Validation schématron (seulement si XSD OK et profil supporté)
    resolved_profile = profile.lower() if profile != "autodetect" else _resolve_profile(xml_bytes)
    if resolved_profile not in _SCHEMATRON_PROFILES:
        return []

    # Mapper vers le profil schématron (basic et extended utilisent EN16931)
    schematron_profile = "EN16931"

    try:
        schematron_errors = validate_schematron(
            xml_bytes, flavor="autodetect", profile=schematron_profile
        )
    except ImportError:
        logger.debug(
            "saxonche non installé — validation schématron ignorée. "
            "Installez avec : pip install facturx-fr[schematron]"
        )
        return []

    return schematron_errors


def _resolve_profile(xml_bytes: bytes) -> str:
    """Résout le profil depuis le XML (pour l'auto-détection)."""
    try:
        from lxml import etree

        from facturx import get_level

        doc = etree.fromstring(xml_bytes)
        return get_level(doc, flavor="factur-x").lower()
    except Exception:
        return ""


__all__ = ["validate_schematron", "validate_xml", "validate_xsd"]
