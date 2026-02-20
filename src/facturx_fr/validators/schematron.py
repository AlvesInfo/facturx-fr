"""Validation par schématrons EN16931 (règles de gestion).

FR: Applique les règles de gestion EN16931 via les XSLT pré-compilés
    (ConnectingEurope/eInvoicing-EN16931). Utilise saxonche (Saxon C HE)
    pour le support XSLT 2.0, et lxml pour le parsing du résultat SVRL.
EN: Applies EN16931 business rules via pre-compiled XSLT schematrons.
    Uses saxonche (Saxon C HE) for XSLT 2.0 support.
"""

from __future__ import annotations

import importlib.resources
import logging
from typing import TYPE_CHECKING

from lxml import etree

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# --- Mapping namespace racine → flavor ---
_NS_TO_FLAVOR: dict[str, str] = {
    "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100": "cii",
    "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2": "ubl",
    "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2": "ubl",
}

# --- Mapping (profil, flavor) → chemin XSLT relatif au package en16931 ---
_PROFILE_FLAVOR_TO_XSLT: dict[tuple[str, str], str] = {
    ("en16931", "cii"): "EN16931-CII-validation.xslt",
    ("en16931", "ubl"): "EN16931-UBL-validation.xslt",
}

_SUPPORTED_PROFILES = {"en16931"}

# --- Namespace SVRL ---
_SVRL_NS = "http://purl.oclc.org/dsdl/svrl"


def _detect_flavor(xml_bytes: bytes) -> str:
    """Détecte le flavor (cii/ubl) depuis le namespace de l'élément racine.

    Raises:
        ValueError: Si le namespace n'est pas reconnu.
    """
    try:
        doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        msg = f"XML invalide : {exc}"
        raise ValueError(msg) from exc

    ns = etree.QName(doc.tag).namespace or ""
    flavor = _NS_TO_FLAVOR.get(ns)
    if not flavor:
        msg = (
            f"Namespace racine non reconnu : {ns!r}. "
            f"Namespaces supportés : {', '.join(sorted(_NS_TO_FLAVOR))}"
        )
        raise ValueError(msg)
    return flavor


def _get_xslt_path(profile: str, flavor: str) -> Path:
    """Résout le chemin du fichier XSLT bundlé pour un profil et flavor donnés.

    Raises:
        ValueError: Si la combinaison profil/flavor n'est pas supportée.
    """
    key = (profile.lower(), flavor)
    xslt_filename = _PROFILE_FLAVOR_TO_XSLT.get(key)
    if not xslt_filename:
        msg = (
            f"Pas de schématron disponible pour profil={profile!r}, flavor={flavor!r}. "
            f"Combinaisons supportées : {list(_PROFILE_FLAVOR_TO_XSLT)}"
        )
        raise ValueError(msg)

    xslt_resource = importlib.resources.files(
        "facturx_fr.validators.schemas.schematrons.en16931"
    ).joinpath(xslt_filename)

    # importlib.resources renvoie un Traversable ; as_file() donne un Path
    return xslt_resource  # type: ignore[return-value]


def _parse_svrl(svrl_str: str) -> list[str]:
    """Parse le XML SVRL et extrait les erreurs (failed-assert).

    Retourne une liste de messages formatés : [rule_id] texte (emplacement: xpath).
    """
    svrl_doc = etree.fromstring(svrl_str.encode("utf-8"))
    errors: list[str] = []

    for failed in svrl_doc.iter(f"{{{_SVRL_NS}}}failed-assert"):
        rule_id = failed.get("id", "")
        location = failed.get("location", "")
        text_el = failed.find(f"{{{_SVRL_NS}}}text")
        text = "".join(text_el.itertext()).strip() if text_el is not None else ""

        if rule_id and text:
            errors.append(f"[{rule_id}] {text} (emplacement: {location})")
        elif text:
            errors.append(f"{text} (emplacement: {location})")

    return errors


def validate_schematron(
    xml_bytes: bytes,
    flavor: str = "autodetect",
    profile: str = "EN16931",
) -> list[str]:
    """Valide un XML de facture contre les schématrons EN16931.

    FR: Applique les règles de gestion EN16931 via une transformation XSLT 2.0
        (saxonche). Détecte automatiquement le format (CII/UBL) si flavor="autodetect".
    EN: Validates an invoice XML against EN16931 schematron business rules.

    Args:
        xml_bytes: Le contenu XML à valider.
        flavor: Le format ("cii", "ubl") ou "autodetect" pour détecter automatiquement.
        profile: Le profil de validation ("EN16931").

    Returns:
        Liste des messages d'erreur (vide si valide).

    Raises:
        ImportError: Si saxonche n'est pas installé.
        ValueError: Si le profil ou flavor est invalide.
    """
    try:
        from saxonche import PySaxonProcessor
    except ImportError:
        msg = (
            "saxonche est requis pour la validation schématron. "
            "Installez-le avec : pip install facturx-fr[schematron]"
        )
        raise ImportError(msg)

    # Normaliser le profil
    profile_lower = profile.lower()
    if profile_lower not in _SUPPORTED_PROFILES:
        msg = (
            f"Profil non supporté : {profile!r}. "
            f"Profils disponibles : {', '.join(sorted(_SUPPORTED_PROFILES))}"
        )
        raise ValueError(msg)

    # Détecter le flavor si nécessaire
    if flavor == "autodetect":
        resolved_flavor = _detect_flavor(xml_bytes)
    else:
        resolved_flavor = flavor.lower()
        if resolved_flavor not in ("cii", "ubl"):
            msg = f"Flavor non supporté : {flavor!r}. Flavors disponibles : cii, ubl"
            raise ValueError(msg)

    # Résoudre le chemin XSLT
    xslt_resource = _get_xslt_path(profile_lower, resolved_flavor)

    # Appliquer la transformation XSLT via saxonche
    xml_str = xml_bytes.decode("utf-8")

    with importlib.resources.as_file(xslt_resource) as xslt_path:
        with PySaxonProcessor(license=False) as proc:
            xslt_proc = proc.new_xslt30_processor()
            executable = xslt_proc.compile_stylesheet(
                stylesheet_file=str(xslt_path)
            )
            node = proc.parse_xml(xml_text=xml_str)
            svrl_str = executable.transform_to_string(xdm_node=node)

    if not svrl_str:
        logger.warning("La transformation XSLT n'a produit aucun résultat SVRL")
        return []

    return _parse_svrl(svrl_str)
