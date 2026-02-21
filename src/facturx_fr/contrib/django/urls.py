"""Configuration des URLs Django pour la facturation électronique."""

from django.urls import path

from facturx_fr.contrib.django.views import (
    CheckStatusView,
    DownloadPDFView,
    DownloadXMLView,
    GenerateXMLView,
    SubmitToPDPView,
)

app_name = "facturx_fr"

urlpatterns = [
    path(
        "<int:invoice_id>/generate-xml/",
        GenerateXMLView.as_view(),
        name="generate-xml",
    ),
    path(
        "<int:invoice_id>/submit/",
        SubmitToPDPView.as_view(),
        name="submit",
    ),
    path(
        "<int:invoice_id>/download-xml/",
        DownloadXMLView.as_view(),
        name="download-xml",
    ),
    path(
        "<int:invoice_id>/download-pdf/",
        DownloadPDFView.as_view(),
        name="download-pdf",
    ),
    path(
        "<int:invoice_id>/check-status/",
        CheckStatusView.as_view(),
        name="check-status",
    ),
]
