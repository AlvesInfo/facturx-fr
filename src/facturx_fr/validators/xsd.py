"""Validation XSD des factures électroniques.

FR: Valide un XML de facture contre le schéma XSD Factur-X approprié.
    Utilise lxml directement avec les XSD bundlés dans le package facturx
    pour retourner TOUTES les erreurs (contrairement à xml_check_xsd()
    qui lève une exception au premier échec).
EN: Validates an invoice XML against the appropriate Factur-X XSD schema.
"""

import importlib.resources

from lxml import etree

# Mapping profil → chemin relatif du XSD dans le package facturx
_PROFILE_TO_XSD = {
    "minimum": "xsd/facturx-minimum/Factur-X_1.08_MINIMUM.xsd",
    "basicwl": "xsd/facturx-basicwl/Factur-X_1.08_BASICWL.xsd",
    "basic": "xsd/facturx-basic/Factur-X_1.08_BASIC.xsd",
    "en16931": "xsd/facturx-en16931/Factur-X_1.08_EN16931.xsd",
    "extended": "xsd/facturx-extended/Factur-X_1.08_EXTENDED.xsd",
}

_SUPPORTED_FLAVORS = {"factur-x"}


def validate_xsd(
    xml_bytes: bytes,
    flavor: str = "factur-x",
    profile: str = "autodetect",
) -> list[str]:
    """Valide un XML de facture contre le schéma XSD approprié.

    FR: Retourne une liste d'erreurs (vide si le XML est valide).
        Contrairement à facturx.xml_check_xsd(), cette fonction retourne
        TOUTES les erreurs de validation, pas seulement la première.
    EN: Returns a list of errors (empty if the XML is valid).

    Args:
        xml_bytes: Le contenu XML à valider.
        flavor: Le format de facture (seul "factur-x" est supporté pour l'instant).
        profile: Le profil Factur-X ("minimum", "basicwl", "basic", "en16931",
            "extended") ou "autodetect" pour détecter automatiquement depuis le XML.

    Returns:
        Liste des messages d'erreur (vide si valide).

    Raises:
        ValueError: Si le flavor n'est pas supporté ou si le profil est inconnu.
    """
    # 1. Vérifier le flavor
    if flavor not in _SUPPORTED_FLAVORS:
        msg = (
            f"Flavor non supporté : {flavor!r}. "
            f"Flavors disponibles : {', '.join(sorted(_SUPPORTED_FLAVORS))}"
        )
        raise ValueError(msg)

    # 2. Parser le XML
    try:
        xml_doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        return [f"Erreur de syntaxe XML : {exc}"]

    # 3. Résoudre le profil
    resolved_profile = _resolve_profile(xml_doc, profile)

    # 4. Charger le XSD et valider
    xsd_path = _PROFILE_TO_XSD[resolved_profile]
    schema = _load_xsd(xsd_path)

    if schema.validate(xml_doc):
        return []

    return [f"Ligne {error.line}: {error.message}" for error in schema.error_log]


def _resolve_profile(xml_doc: etree._Element, profile: str) -> str:
    """Résout le profil XSD à utiliser.

    Si profile est "autodetect", détecte le profil depuis le XML via
    facturx.get_level(). Sinon, normalise et vérifie le profil donné.

    Raises:
        ValueError: Si le profil est inconnu.
    """
    if profile == "autodetect":
        from facturx import get_level

        resolved = get_level(xml_doc, flavor="factur-x")
    else:
        resolved = profile.lower()

    if resolved not in _PROFILE_TO_XSD:
        msg = (
            f"Profil inconnu : {profile!r}. "
            f"Profils disponibles : {', '.join(sorted(_PROFILE_TO_XSD))}"
        )
        raise ValueError(msg)

    return resolved


def _load_xsd(xsd_relative_path: str) -> etree.XMLSchema:
    """Charge un schéma XSD depuis les fichiers bundlés du package facturx."""
    xsd_source = importlib.resources.files("facturx").joinpath(xsd_relative_path)
    with xsd_source.open() as f:
        xsd_doc = etree.parse(f)
    return etree.XMLSchema(xsd_doc)
