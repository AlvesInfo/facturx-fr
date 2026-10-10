"""URLs de l'API HTTP stateless (génération / validation).

FR: À monter dans un projet Django sans ajouter l'app à INSTALLED_APPS
    (aucun modèle n'est utilisé) :

        path("facturx/", include("facturx_fr.contrib.django.api_urls")),

EN: Mount in any Django project; no INSTALLED_APPS entry needed.
"""

from django.urls import path

from facturx_fr.contrib.django.api_views import (
    GenerateFacturXView,
    GenerateXMLView,
    HealthView,
    ValidateXMLView,
)

app_name = "facturx_fr_api"

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("generate/", GenerateFacturXView.as_view(), name="generate"),
    path("generate-xml/", GenerateXMLView.as_view(), name="generate-xml"),
    path("validate/", ValidateXMLView.as_view(), name="validate"),
]
