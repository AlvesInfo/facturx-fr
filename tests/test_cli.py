"""Tests des points d'entrée CLI (stubs en cours de développement)."""

import pytest

from facturx_fr import cli


@pytest.mark.parametrize(
    ("entry_point", "command"),
    [(cli.generate, "facturx-generate"), (cli.validate, "facturx-validate")],
    ids=["generate", "validate"],
)
def test_cli_stub_exits_with_error(
    entry_point, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Chaque commande annonce qu'elle est en développement et sort en code 1."""
    with pytest.raises(SystemExit) as exc_info:
        entry_point()
    assert exc_info.value.code == 1
    assert command in capsys.readouterr().err
