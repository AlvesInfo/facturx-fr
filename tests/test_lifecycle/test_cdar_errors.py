"""Tests des erreurs de parsing CDAR sur des éléments obligatoires manquants."""

import pytest

from facturx_fr.lifecycle.cdar import NS_RAM, NS_RSM, CDARParser

_HEADER = (
    b'<?xml version="1.0"?>'
    b"<rsm:CrossDomainAcknowledgementAndResponse"
    b' xmlns:rsm="' + NS_RSM.encode() + b'"'
    b' xmlns:ram="' + NS_RAM.encode() + b'">'
)
_FOOTER = b"</rsm:CrossDomainAcknowledgementAndResponse>"


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b"<rsm:ExchangedDocument/>", "ram:ID"),
        (b"<rsm:ExchangedDocument><ram:ID/></rsm:ExchangedDocument>", "ram:ID"),
        (
            b"<rsm:ExchangedDocument><ram:ID>MSG-1</ram:ID></rsm:ExchangedDocument>",
            "ram:StatusCode",
        ),
    ],
    ids=["id_missing", "id_empty", "status_code_missing"],
)
def test_parse_missing_mandatory_text(body: bytes, expected: str) -> None:
    """Un élément texte obligatoire absent ou vide lève ValueError."""
    parser = CDARParser()
    with pytest.raises(ValueError, match=f"obligatoire manquant : {expected}"):
        parser.parse(_HEADER + body + _FOOTER)
