"""Utilitaires pour la manipulation XML."""


def prettify_xml(xml_bytes: bytes) -> bytes:
    """Formate un XML avec indentation pour la lisibilité.

    Args:
        xml_bytes: Le contenu XML brut.

    Returns:
        Le contenu XML indenté.
    """
    from lxml import etree

    root = etree.fromstring(xml_bytes)
    etree.indent(root)
    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8")
