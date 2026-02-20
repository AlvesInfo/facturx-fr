"""Tests pour la hiérarchie d'exceptions e-reporting."""

import pytest

from facturx_fr.ereporting.errors import (
    EReportingEmptyDeclarationError,
    EReportingError,
    EReportingValidationError,
)


class TestEReportingError:
    """Tests de l'exception de base."""

    def test_is_exception(self) -> None:
        assert issubclass(EReportingError, Exception)

    def test_can_raise_and_catch(self) -> None:
        with pytest.raises(EReportingError):
            raise EReportingError("erreur de base")

    def test_message(self) -> None:
        err = EReportingError("test message")
        assert str(err) == "test message"


class TestEReportingValidationError:
    """Tests de l'exception de validation."""

    def test_inherits_from_ereporting_error(self) -> None:
        assert issubclass(EReportingValidationError, EReportingError)

    def test_catchable_as_base(self) -> None:
        with pytest.raises(EReportingError):
            raise EReportingValidationError("validation échouée")

    def test_catchable_as_validation(self) -> None:
        with pytest.raises(EReportingValidationError):
            raise EReportingValidationError("validation échouée")

    def test_errors_list(self) -> None:
        errors = ["champ manquant", "SIREN invalide"]
        err = EReportingValidationError("invalide", errors=errors)
        assert err.errors == errors

    def test_errors_default_empty(self) -> None:
        err = EReportingValidationError("invalide")
        assert err.errors == []

    def test_message(self) -> None:
        err = EReportingValidationError("données invalides")
        assert str(err) == "données invalides"


class TestEReportingEmptyDeclarationError:
    """Tests de l'exception déclaration vide."""

    def test_inherits_from_ereporting_error(self) -> None:
        assert issubclass(EReportingEmptyDeclarationError, EReportingError)

    def test_catchable_as_base(self) -> None:
        with pytest.raises(EReportingError):
            raise EReportingEmptyDeclarationError("déclaration vide")

    def test_catchable_as_empty(self) -> None:
        with pytest.raises(EReportingEmptyDeclarationError):
            raise EReportingEmptyDeclarationError("déclaration vide")

    def test_message(self) -> None:
        err = EReportingEmptyDeclarationError("pas d'opérations")
        assert str(err) == "pas d'opérations"
