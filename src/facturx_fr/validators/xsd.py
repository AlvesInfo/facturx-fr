"""Validation XSD des factures électroniques."""


def validate_xsd(xml_bytes: bytes, flavor: str = "factur-x") -> list[str]:
    """Valide un XML de facture contre le schéma XSD approprié.

    FR: Retourne une liste d'erreurs (vide si le XML est valide).
    EN: Returns a list of errors (empty if the XML is valid).

    Args:
        xml_bytes: Le contenu XML à valider.
        flavor: Le format de facture ("factur-x", "ubl", "cii").

    Returns:
        Liste des messages d'erreur.
    """
    raise NotImplementedError("Validation XSD en cours de développement")
