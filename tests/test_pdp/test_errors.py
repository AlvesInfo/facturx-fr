"""Tests pour la hiérarchie d'exceptions PDP."""

import pytest

from facturx_fr.pdp.errors import (
    PDPAuthenticationError,
    PDPConnectionError,
    PDPError,
    PDPNotFoundError,
    PDPValidationError,
)


class TestPDPErrorHierarchy:
    """Vérifie que toutes les exceptions héritent de PDPError."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            PDPAuthenticationError,
            PDPValidationError,
            PDPNotFoundError,
            PDPConnectionError,
        ],
    )
    def test_subclass_of_pdp_error(self, exc_class: type) -> None:
        assert issubclass(exc_class, PDPError)

    @pytest.mark.parametrize(
        "exc_class",
        [
            PDPAuthenticationError,
            PDPValidationError,
            PDPNotFoundError,
            PDPConnectionError,
        ],
    )
    def test_catchable_as_base(self, exc_class: type) -> None:
        with pytest.raises(PDPError):
            raise exc_class("test")

    def test_pdp_error_is_exception(self) -> None:
        assert issubclass(PDPError, Exception)


class TestPDPValidationError:
    """Vérifie le stockage des détails de validation."""

    def test_with_error_list(self) -> None:
        errors = ["Champ manquant : SIREN", "Taux TVA invalide"]
        exc = PDPValidationError("Validation échouée", errors=errors)
        assert str(exc) == "Validation échouée"
        assert exc.errors == errors

    def test_without_error_list(self) -> None:
        exc = PDPValidationError("Validation échouée")
        assert exc.errors == []

    def test_with_none_error_list(self) -> None:
        exc = PDPValidationError("Validation échouée", errors=None)
        assert exc.errors == []
