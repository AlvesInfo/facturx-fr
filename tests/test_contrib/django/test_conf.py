"""Tests de la configuration Django facturx-fr."""

import pytest
from django.test import override_settings

from facturx_fr.contrib.django.conf import get_pdp_instance, get_setting


class TestGetSetting:
    """Tests de get_setting()."""

    def test_default_values(self):
        """Vérifie que les valeurs par défaut sont retournées."""
        assert get_setting("PDP_CLASS") is None
        assert get_setting("PDP_API_KEY") == ""
        assert get_setting("PDP_ENVIRONMENT") == "sandbox"
        assert get_setting("PDP_BASE_URL") is None
        assert get_setting("DEFAULT_PROFILE") == "EN16931"
        assert get_setting("DEFAULT_CURRENCY") == "EUR"

    @override_settings(FACTURX_FR={"PDP_ENVIRONMENT": "production"})
    def test_override_setting(self):
        """Vérifie qu'un paramètre utilisateur surcharge le défaut."""
        assert get_setting("PDP_ENVIRONMENT") == "production"
        # Les autres restent par défaut
        assert get_setting("DEFAULT_CURRENCY") == "EUR"

    @override_settings(FACTURX_FR={"PDP_API_KEY": "my-secret-key"})
    def test_override_api_key(self):
        """Vérifie la surcharge de la clé API."""
        assert get_setting("PDP_API_KEY") == "my-secret-key"

    def test_unknown_setting_raises(self):
        """Vérifie qu'un paramètre inconnu lève KeyError."""
        with pytest.raises(KeyError, match="inconnu"):
            get_setting("NONEXISTENT_SETTING")


class TestGetPDPInstance:
    """Tests de get_pdp_instance()."""

    def test_no_pdp_class_raises(self):
        """Vérifie que l'absence de PDP_CLASS lève ValueError."""
        with pytest.raises(ValueError, match="PDP_CLASS"):
            get_pdp_instance()

    @override_settings(
        FACTURX_FR={
            "PDP_CLASS": "facturx_fr.pdp.connectors.memory.MemoryPDP",
        }
    )
    def test_instantiate_memory_pdp(self):
        """Vérifie l'instanciation dynamique du MemoryPDP."""
        from facturx_fr.pdp.connectors.memory import MemoryPDP

        pdp = get_pdp_instance()
        assert isinstance(pdp, MemoryPDP)

    @override_settings(
        FACTURX_FR={
            "PDP_CLASS": "nonexistent.module.FakePDP",
        }
    )
    def test_invalid_pdp_class_raises(self):
        """Vérifie qu'une classe PDP invalide lève une erreur."""
        with pytest.raises(ImportError):
            get_pdp_instance()
