"""Configuration de l'application Django pour la facturation électronique."""

from django.apps import AppConfig


class FacturxFrConfig(AppConfig):
    """Configuration de l'app Django facturx-fr."""

    name = "facturx_fr.contrib.django"
    label = "facturx_fr"
    verbose_name = "Facturation électronique"
    default_auto_field = "django.db.models.BigAutoField"
