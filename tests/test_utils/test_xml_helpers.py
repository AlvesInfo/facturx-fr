"""Tests des utilitaires XML."""

from facturx_fr.utils.xml_helpers import prettify_xml


def test_prettify_xml_indents_and_declares_encoding() -> None:
    """Le XML compact est indenté et préfixé d'une déclaration XML UTF-8."""
    result = prettify_xml(b"<root><child>texte</child></root>")

    assert result.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
    assert b"\n  <child>texte</child>\n" in result
