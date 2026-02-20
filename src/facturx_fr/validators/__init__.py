"""Validation XSD et schématrons pour les factures électroniques.

FR: Point d'entrée principal pour la validation de factures.
    validate_xml() combine XSD + (futur) schématrons.
    validate_xsd() effectue uniquement la validation XSD.
EN: Main entry point for invoice validation.
"""

from facturx_fr.validators.xsd import validate_xsd


def validate_xml(
    xml_bytes: bytes,
    flavor: str = "factur-x",
    profile: str = "autodetect",
) -> list[str]:
    """Point d'entrée principal — XSD + (futur) schématrons.

    FR: Valide un XML de facture contre le XSD puis (à terme)
        les schématrons FR (BR-FR-CTC). Retourne une liste d'erreurs.
    EN: Validates an invoice XML against XSD and (future) FR schematrons.

    Args:
        xml_bytes: Le contenu XML à valider.
        flavor: Le format de facture ("factur-x").
        profile: Le profil ("en16931", "extended", etc.) ou "autodetect".

    Returns:
        Liste des messages d'erreur (vide si valide).
    """
    return validate_xsd(xml_bytes, flavor=flavor, profile=profile)


__all__ = ["validate_xml", "validate_xsd"]