"""Configuration de la facturation électronique via settings Django.

FR: Helper pour accéder aux paramètres FACTURX_FR définis dans settings.py.
    Fournit des valeurs par défaut et un instanciateur dynamique de PDP.
EN: Helper for accessing FACTURX_FR settings defined in settings.py.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils.module_loading import import_string

from facturx_fr.pdp.base import BasePDP

logger = logging.getLogger(__name__)

DEFAULTS: dict[str, object] = {
    "PDP_CLASS": None,
    "PDP_API_KEY": "",
    "PDP_ENVIRONMENT": "sandbox",
    "PDP_BASE_URL": None,
    "DEFAULT_PROFILE": "EN16931",
    "DEFAULT_CURRENCY": "EUR",
}


def get_setting(name: str) -> object:
    """Retourne la valeur d'un paramètre FACTURX_FR.

    FR: Cherche dans settings.FACTURX_FR[name], puis dans les défauts.
    EN: Looks up settings.FACTURX_FR[name], then falls back to defaults.
    """
    if name not in DEFAULTS:
        msg = f"Paramètre FACTURX_FR inconnu : {name}"
        raise KeyError(msg)
    user_settings = getattr(settings, "FACTURX_FR", {})
    return user_settings.get(name, DEFAULTS[name])


def get_pdp_instance() -> BasePDP:
    """Instancie dynamiquement le connecteur PDP configuré.

    FR: Utilise PDP_CLASS, PDP_API_KEY, PDP_ENVIRONMENT et PDP_BASE_URL
        pour créer une instance du connecteur PDP.
    EN: Uses PDP_CLASS, PDP_API_KEY, PDP_ENVIRONMENT and PDP_BASE_URL
        to create a PDP connector instance.

    Raises:
        ValueError: Si PDP_CLASS n'est pas configuré.
    """
    pdp_class_path = get_setting("PDP_CLASS")
    if not pdp_class_path:
        msg = (
            "FACTURX_FR['PDP_CLASS'] n'est pas configuré. "
            "Spécifiez le chemin complet de la classe PDP."
        )
        raise ValueError(msg)

    pdp_class = import_string(pdp_class_path)
    return pdp_class(
        api_key=get_setting("PDP_API_KEY"),
        environment=get_setting("PDP_ENVIRONMENT"),
        base_url=get_setting("PDP_BASE_URL"),
    )
