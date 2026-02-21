"""Modèles Django pour la facturation électronique.

FR: Modèles Django mappés sur les modèles Pydantic de la lib. Design plat
    (seller_*/buyer_* directement sur le modèle Invoice) pour simplifier
    l'admin et les requêtes.
EN: Django models mapped to the library's Pydantic models. Flat design
    (seller_*/buyer_* directly on the Invoice model).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models, transaction

from facturx_fr.models.enums import (
    InvoiceTypeCode,
    OperationCategory,
    VATCategory,
)
from facturx_fr.models.invoice import Invoice as PydanticInvoice
from facturx_fr.models.invoice import InvoiceLine as PydanticInvoiceLine
from facturx_fr.models.party import Address, Party
from facturx_fr.models.payment import BankAccount, PaymentMeans, PaymentMeansCode


class InvoiceStatusChoices(models.TextChoices):
    """Statuts de facture : brouillon + 14 statuts PDP."""

    DRAFT = "draft", "Brouillon"
    DEPOSEE = "200", "Déposée"
    EMISE = "201", "Émise"
    RECUE = "202", "Reçue"
    MISE_A_DISPOSITION = "203", "Mise à disposition"
    PRISE_EN_CHARGE = "204", "Prise en charge"
    APPROUVEE = "205", "Approuvée"
    PARTIELLEMENT_APPROUVEE = "206", "Partiellement approuvée"
    EN_LITIGE = "207", "En litige"
    SUSPENDUE = "208", "Suspendue"
    REJETEE_EMISSION = "209", "Rejetée à l'émission"
    REFUSEE = "210", "Refusée"
    PAIEMENT_TRANSMIS = "211", "Paiement transmis"
    REJETEE_RECEPTION = "212", "Rejetée à la réception"
    ENCAISSEE = "213", "Encaissée"
    COMPLETEE = "214", "Complétée"


class Invoice(models.Model):
    """Facture électronique.

    FR: Modèle Django avec design plat (seller_*/buyer_*). Convertible
        vers/depuis le modèle Pydantic de la lib pour la génération
        XML et la soumission PDP.
    EN: Django model with flat design. Convertible to/from the library's
        Pydantic model for XML generation and PDP submission.
    """

    # --- Identification ---
    number = models.CharField(
        "numéro de facture", max_length=50, unique=True
    )
    issue_date = models.DateField("date d'émission")
    due_date = models.DateField("date d'échéance", blank=True, null=True)
    type_code = models.CharField(
        "type de document", max_length=3, db_default="380"
    )
    currency = models.CharField("devise", max_length=3, db_default="EUR")
    operation_category = models.CharField(
        "catégorie de l'opération",
        max_length=10,
        choices=[
            (OperationCategory.DELIVERY, "Livraison de biens"),
            (OperationCategory.SERVICE, "Prestation de services"),
            (OperationCategory.MIXED, "Mixte"),
        ],
    )

    # --- Vendeur ---
    seller_name = models.CharField("raison sociale vendeur", max_length=200)
    seller_siren = models.CharField("SIREN vendeur", max_length=9)
    seller_vat_number = models.CharField(
        "n° TVA vendeur", max_length=20, blank=True, default=""
    )
    seller_street = models.CharField("adresse vendeur", max_length=200)
    seller_city = models.CharField("ville vendeur", max_length=100)
    seller_postal_code = models.CharField("code postal vendeur", max_length=10)
    seller_country_code = models.CharField(
        "pays vendeur", max_length=2, db_default="FR"
    )

    # --- Acheteur ---
    buyer_name = models.CharField("raison sociale acheteur", max_length=200)
    buyer_siren = models.CharField("SIREN acheteur", max_length=9)
    buyer_vat_number = models.CharField(
        "n° TVA acheteur", max_length=20, blank=True, default=""
    )
    buyer_street = models.CharField("adresse acheteur", max_length=200)
    buyer_city = models.CharField("ville acheteur", max_length=100)
    buyer_postal_code = models.CharField("code postal acheteur", max_length=10)
    buyer_country_code = models.CharField(
        "pays acheteur", max_length=2, db_default="FR"
    )

    # --- Paiement ---
    payment_iban = models.CharField(
        "IBAN", max_length=34, blank=True, default=""
    )
    payment_bic = models.CharField(
        "BIC", max_length=11, blank=True, default=""
    )

    # --- Statut PDP ---
    status = models.CharField(
        "statut",
        max_length=10,
        choices=InvoiceStatusChoices.choices,
        db_default="draft",
    )
    pdp_invoice_id = models.CharField(
        "identifiant PDP", max_length=100, blank=True, default=""
    )

    # --- Fichiers ---
    xml_file = models.FileField(
        "fichier XML", upload_to="facturx/xml/", blank=True
    )
    pdf_file = models.FileField(
        "fichier PDF", upload_to="facturx/pdf/", blank=True
    )

    # --- Métadonnées ---
    created_at = models.DateTimeField("date de création", auto_now_add=True)
    updated_at = models.DateTimeField("date de modification", auto_now=True)

    class Meta:
        verbose_name = "facture"
        verbose_name_plural = "factures"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(seller_siren__regex=r"^\d{9}$"),
                name="valid_seller_siren",
            ),
            models.CheckConstraint(
                condition=models.Q(buyer_siren__regex=r"^\d{9}$"),
                name="valid_buyer_siren",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "issue_date"],
                name="idx_status_issue_date",
            ),
            models.Index(
                fields=["seller_siren"],
                name="idx_seller_siren",
            ),
            models.Index(
                fields=["buyer_siren"],
                name="idx_buyer_siren",
            ),
        ]

    def __str__(self) -> str:
        return f"Facture {self.number}"

    def to_pydantic(self) -> PydanticInvoice:
        """Convertit le modèle Django en modèle Pydantic.

        FR: Construit un objet Invoice Pydantic à partir des champs Django,
            incluant les lignes associées.
        EN: Builds a Pydantic Invoice from Django fields, including lines.
        """
        # Construction du moyen de paiement si IBAN renseigné
        payment_means = None
        if self.payment_iban:
            payment_means = PaymentMeans(
                code=PaymentMeansCode.SEPA_CREDIT_TRANSFER,
                bank_account=BankAccount(
                    iban=self.payment_iban,
                    bic=self.payment_bic or None,
                ),
            )

        pydantic_lines = [line.to_pydantic() for line in self.lines.all()]

        return PydanticInvoice(
            number=self.number,
            issue_date=self.issue_date,
            due_date=self.due_date,
            type_code=InvoiceTypeCode(self.type_code),
            currency=self.currency,
            operation_category=OperationCategory(self.operation_category),
            seller=Party(
                name=self.seller_name,
                siren=self.seller_siren,
                vat_number=self.seller_vat_number or None,
                address=Address(
                    street=self.seller_street,
                    city=self.seller_city,
                    postal_code=self.seller_postal_code,
                    country_code=self.seller_country_code,
                ),
            ),
            buyer=Party(
                name=self.buyer_name,
                siren=self.buyer_siren,
                vat_number=self.buyer_vat_number or None,
                address=Address(
                    street=self.buyer_street,
                    city=self.buyer_city,
                    postal_code=self.buyer_postal_code,
                    country_code=self.buyer_country_code,
                ),
            ),
            lines=pydantic_lines,
            payment_means=payment_means,
        )

    @classmethod
    def from_pydantic(cls, invoice: PydanticInvoice) -> Invoice:
        """Crée une instance Django (non sauvée) depuis un modèle Pydantic.

        FR: Convertit un objet Invoice Pydantic en instance Django. Ne sauvegarde
            pas en base — appeler .save() ou utiliser create_with_lines().
        EN: Converts a Pydantic Invoice to a Django instance. Does not save.
        """
        # Extraction IBAN/BIC si disponible
        payment_iban = ""
        payment_bic = ""
        if invoice.payment_means and invoice.payment_means.bank_account:
            payment_iban = invoice.payment_means.bank_account.iban
            payment_bic = invoice.payment_means.bank_account.bic or ""

        return cls(
            number=invoice.number,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            type_code=str(invoice.type_code),
            currency=invoice.currency,
            operation_category=str(invoice.operation_category),
            seller_name=invoice.seller.name,
            seller_siren=invoice.seller.siren or "",
            seller_vat_number=invoice.seller.vat_number or "",
            seller_street=invoice.seller.address.street,
            seller_city=invoice.seller.address.city,
            seller_postal_code=invoice.seller.address.postal_code,
            seller_country_code=invoice.seller.address.country_code,
            buyer_name=invoice.buyer.name,
            buyer_siren=invoice.buyer.siren or "",
            buyer_vat_number=invoice.buyer.vat_number or "",
            buyer_street=invoice.buyer.address.street,
            buyer_city=invoice.buyer.address.city,
            buyer_postal_code=invoice.buyer.address.postal_code,
            buyer_country_code=invoice.buyer.address.country_code,
            payment_iban=payment_iban,
            payment_bic=payment_bic,
        )

    @classmethod
    @transaction.atomic
    def create_with_lines(cls, invoice: PydanticInvoice) -> Invoice:
        """Crée une facture avec ses lignes en une transaction.

        FR: Crée l'Invoice Django + toutes les InvoiceLines depuis
            le modèle Pydantic, en une seule transaction atomique.
        EN: Creates the Django Invoice + all InvoiceLines from the
            Pydantic model in a single atomic transaction.
        """
        django_invoice = cls.from_pydantic(invoice)
        django_invoice.save()

        for idx, line in enumerate(invoice.lines, start=1):
            InvoiceLine.objects.create(
                invoice=django_invoice,
                line_number=line.line_number or idx,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                vat_rate=line.vat_rate,
                vat_category=str(line.vat_category),
            )

        return django_invoice


class InvoiceLine(models.Model):
    """Ligne de facture.

    FR: Représente un poste de facturation avec quantité, prix unitaire et TVA.
    EN: Represents an invoice item with quantity, unit price and VAT.
    """

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="facture",
    )
    line_number = models.PositiveIntegerField("numéro de ligne")
    description = models.CharField("désignation", max_length=500)
    quantity = models.DecimalField(
        "quantité", max_digits=12, decimal_places=4
    )
    unit_price = models.DecimalField(
        "prix unitaire HT", max_digits=12, decimal_places=4
    )
    vat_rate = models.DecimalField(
        "taux de TVA (%)", max_digits=5, decimal_places=2, db_default="20.00"
    )
    vat_category = models.CharField(
        "catégorie TVA", max_length=3, db_default="S"
    )

    class Meta:
        verbose_name = "ligne de facture"
        verbose_name_plural = "lignes de facture"
        ordering = ["line_number"]

    def __str__(self) -> str:
        return f"Ligne {self.line_number} — {self.description}"

    @property
    def line_total_excl_tax(self) -> Decimal:
        """Montant total HT de la ligne."""
        return self.quantity * self.unit_price

    @property
    def line_vat_amount(self) -> Decimal:
        """Montant de TVA de la ligne."""
        return (self.line_total_excl_tax * self.vat_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )

    @property
    def line_total_incl_tax(self) -> Decimal:
        """Montant total TTC de la ligne."""
        return self.line_total_excl_tax + self.line_vat_amount

    def to_pydantic(self) -> PydanticInvoiceLine:
        """Convertit la ligne Django en ligne Pydantic."""
        return PydanticInvoiceLine(
            line_number=self.line_number,
            description=self.description,
            quantity=self.quantity,
            unit_price=self.unit_price,
            vat_rate=self.vat_rate,
            vat_category=VATCategory(self.vat_category),
        )

    @classmethod
    def from_pydantic(
        cls, line: PydanticInvoiceLine, invoice: Invoice, idx: int = 1
    ) -> InvoiceLine:
        """Crée une instance Django (non sauvée) depuis une ligne Pydantic."""
        return cls(
            invoice=invoice,
            line_number=line.line_number or idx,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            vat_rate=line.vat_rate,
            vat_category=str(line.vat_category),
        )
