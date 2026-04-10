"""
URL patterns for plaude_thunes.

Include these in your Django project's urlconf::

    # urls.py
    from django.urls import path, include

    urlpatterns = [
        path("api/", include("plaude_thunes.urls")),
        ...
    ]

This produces endpoints like:
    GET  /api/thunes/payers/<country>/<currency>/
    GET  /api/thunes/payers/<payer_id>/
    GET  /api/thunes/payers/<payer_id>/<transaction_type>/<data_type>/required-fields
    GET  /api/thunes/utils/rep-document-id-types/
    GET  /api/thunes/purpose-of-remittance/
    GET  /api/thunes/document-types/
    POST /api/thunes/credit-party/validate/
    POST /api/thunes/credit-party/information/
    POST /api/thunes/webhook/

Downstream apps can override individual view classes before including these URLs::

    # myapp/urls.py
    from plaude_thunes import urls as thunes_urls
    from myapp.views import SecuredPayerRequiredFieldsView

    # Swap in the secured view:
    thunes_urls.urlpatterns[2] = path(
        "thunes/payers/<str:payer_id>/<str:transaction_type>/<str:data_type>/required-fields",
        SecuredPayerRequiredFieldsView.as_view(),
        name="thunes-payer-required-fields",
    )

    urlpatterns = [
        path("api/", include(thunes_urls)),
        ...
    ]
"""

from django.urls import path

from plaude_thunes.api.views.payers import (
    GetPayerDetailsView,
    GetPayerRequiredFieldsView,
    GetPayersView,
    GetRepDocumentIdTypesView,
)
from plaude_thunes.api.views.transactions import (
    CreditPartyInformationView,
    CreditPartyValidationView,
    GetDocumentTypesView,
    GetPurposeOfRemittanceView,
)
from plaude_thunes.api.views.webhooks import BaseThunesWebhookView

app_name = "plaude_thunes"

urlpatterns = [
    # --- Payer endpoints ---
    path(
        "thunes/payers/<str:country_iso_code>/<str:currency>/",
        GetPayersView.as_view(),
        name="thunes-payers-by-country-currency",
    ),
    path(
        "thunes/payers/<str:payer_id>/",
        GetPayerDetailsView.as_view(),
        name="thunes-payer-details",
    ),
    path(
        "thunes/payers/<str:payer_id>/<str:transaction_type>/<str:data_type>/required-fields",
        GetPayerRequiredFieldsView.as_view(),
        name="thunes-payer-required-fields",
    ),
    # --- Utility endpoints ---
    path(
        "thunes/utils/rep-document-id-types/",
        GetRepDocumentIdTypesView.as_view(),
        name="thunes-rep-document-id-types",
    ),
    path(
        "thunes/purpose-of-remittance/",
        GetPurposeOfRemittanceView.as_view(),
        name="thunes-purpose-of-remittance",
    ),
    path(
        "thunes/document-types/",
        GetDocumentTypesView.as_view(),
        name="thunes-document-types",
    ),
    # --- Credit party endpoints ---
    path(
        "thunes/credit-party/validate/",
        CreditPartyValidationView.as_view(),
        name="thunes-credit-party-validate",
    ),
    path(
        "thunes/credit-party/information/",
        CreditPartyInformationView.as_view(),
        name="thunes-credit-party-information",
    ),
    # --- Webhook ---
    path(
        "thunes/webhook/",
        BaseThunesWebhookView.as_view(),
        name="thunes-webhook",
    ),
]
