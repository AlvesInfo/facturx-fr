"""Sérialiseurs légers pour la facturation électronique.

FR: Fonctions de sérialisation Django → dict JSON-safe,
    sans dépendance à Django REST Framework.
EN: Lightweight serialization functions from Django models to
    JSON-safe dicts, without DRF dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from facturx_fr.contrib.django.models import Invoice, InvoiceLine


def invoice_line_to_dict(line: InvoiceLine) -> dict:
    """Sérialise une ligne de facture en dict JSON-safe."""
    return {
        "id": line.pk,
        "line_number": line.line_number,
        "description": line.description,
        "quantity": str(line.quantity),
        "unit_price": str(line.unit_price),
        "vat_rate": str(line.vat_rate),
        "vat_category": line.vat_category,
        "line_total_excl_tax": str(line.line_total_excl_tax),
        "line_vat_amount": str(line.line_vat_amount),
        "line_total_incl_tax": str(line.line_total_incl_tax),
    }


def invoice_to_dict(invoice: Invoice) -> dict:
    """Sérialise un modèle Django Invoice en dict JSON-safe."""
    return {
        "id": invoice.pk,
        "number": invoice.number,
        "issue_date": invoice.issue_date.isoformat(),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "type_code": invoice.type_code,
        "currency": invoice.currency,
        "operation_category": invoice.operation_category,
        "status": invoice.status,
        "pdp_invoice_id": invoice.pdp_invoice_id,
        "seller": {
            "name": invoice.seller_name,
            "siren": invoice.seller_siren,
            "vat_number": invoice.seller_vat_number,
            "street": invoice.seller_street,
            "city": invoice.seller_city,
            "postal_code": invoice.seller_postal_code,
            "country_code": invoice.seller_country_code,
        },
        "buyer": {
            "name": invoice.buyer_name,
            "siren": invoice.buyer_siren,
            "vat_number": invoice.buyer_vat_number,
            "street": invoice.buyer_street,
            "city": invoice.buyer_city,
            "postal_code": invoice.buyer_postal_code,
            "country_code": invoice.buyer_country_code,
        },
        "payment": {
            "iban": invoice.payment_iban,
            "bic": invoice.payment_bic,
        },
        "lines": [
            invoice_line_to_dict(line)
            for line in invoice.lines.all()
        ],
        "has_xml": bool(invoice.xml_file),
        "has_pdf": bool(invoice.pdf_file),
        "created_at": invoice.created_at.isoformat(),
        "updated_at": invoice.updated_at.isoformat(),
    }
