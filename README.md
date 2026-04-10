# plaude-thunes

A reusable Python SDK for integrating with the Thunes payment API. Designed for Django + DRF projects with a clean, layered architecture and no magic — all configuration is supplied explicitly at construction time.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Package Structure](#package-structure)
- [Configuration](#configuration)
- [ThunesClient](#thunesclient)
- [Services](#services)
  - [PayerService](#payerservice)
  - [TransactionService](#transactionservice)
  - [CreditPartyService](#creditpartyservice)
- [DRF Views](#drf-views)
  - [Wiring Views into Your App](#wiring-views-into-your-app)
  - [Available Views](#available-views)
  - [URL Patterns](#url-patterns)
- [Serializers](#serializers)
- [Webhook Handling](#webhook-handling)
- [Exceptions](#exceptions)
- [Utilities](#utilities)
- [Testing](#testing)
- [Design Principles](#design-principles)

---

## Installation

```bash
pip install plaude-thunes
```

Or editable local install:

```bash
pip install -e /path/to/plaude-thunes
```

Add `rest_framework` to `INSTALLED_APPS` in your Django settings if not already present.

---

## Quick Start

```python
from plaude_thunes import ThunesClient

client = ThunesClient(
    api_key="your_api_key",
    api_base_url="https://api.example.com/thunes",
    callback_key="webhook_key",
    callback_secret="webhook_secret",
    environment="production",  # or "sandbox"
)

# List payers for a country/currency
payers = client.payers.get_by_country_and_currency("NGA", "USD")

# Validate a credit party (beneficiary account)
result = client.credit_party.validate(
    payer_id="1234",
    credit_party_identifier={"bank_account_number": "0123456789"},
    transaction_type="B2C",
)

# Create a quotation
quotation = client.transactions.create_quotation(
    payer_id="1234",
    transaction_type="B2C",
    amount="500.00",
    destination_currency="NGN",
)
```

boto3-style factory:

```python
import plaude_thunes

client = plaude_thunes.client(
    "thunes",
    api_key="your_api_key",
    api_base_url="https://api.example.com/thunes",
)
```

---

## Package Structure

```
plaude-thunes/
├── README.md
├── pyproject.toml
├── __init__.py              # ThunesClient re-export + boto3-style factory
├── client.py                # ThunesClient — main entry point
├── config.py                # ThunesConfig — holds all credentials/settings
├── exceptions.py            # Exception hierarchy
├── urls.py                  # Django URL patterns
├── clients/
│   └── thunes_client.py     # ThunesHTTPClient — low-level HTTP layer
├── services/
│   ├── payers.py            # PayerService
│   ├── transactions.py      # TransactionService
│   └── credit_party.py      # CreditPartyService
├── api/
│   ├── views/
│   │   ├── base.py          # BaseThunesAPIView
│   │   ├── payers.py        # Payer views
│   │   ├── transactions.py  # Transaction / credit-party views
│   │   └── webhooks.py      # BaseThunesWebhookView
│   └── serializers/
│       ├── base.py          # BaseThunesSerializer
│       ├── payers.py        # PayerRequiredFieldsSerializer
│       └── transactions.py  # All transaction serializers
├── security/
│   └── webhook.py           # WebhookValidator
├── utils/
│   └── helpers.py           # Utility functions + SPECIAL_PAYERS + IDENTIFIER_CONFIG
└── tests/
    ├── conftest.py
    ├── settings.py
    ├── test_client.py
    ├── test_config.py
    ├── test_services.py
    ├── test_utils.py
    └── test_webhook.py
```

---

## Configuration

`ThunesConfig` holds all SDK settings. All values are passed at construction time — the SDK never reads environment variables or Django settings automatically.

```python
from plaude_thunes.config import ThunesConfig

config = ThunesConfig(
    api_key="your_api_key",          # Required
    api_base_url="https://...",       # Required
    callback_key="webhook_key",       # Optional — required for webhook validation
    callback_secret="webhook_secret", # Optional — required for webhook validation
    environment="production",         # "sandbox" or "production" (default: "production")
    timeout=30,                       # HTTP timeout in seconds (default: 30)
)

config.validate()       # Raises ValueError if api_key or api_base_url is missing
config.is_sandbox       # True if environment == "sandbox"
```

In a Django app, read settings explicitly before passing:

```python
from django.conf import settings
from plaude_thunes import ThunesClient

def get_thunes_client():
    return ThunesClient(
        api_key=settings.EXTERNAL_API_KEY,
        api_base_url=settings.EXTERNAL_API_BASE_URL,
        callback_key=settings.THUNES_CALLBACK_KEY,
        callback_secret=settings.THUNES_CALLBACK_SECRET,
    )
```

---

## ThunesClient

The top-level entry point. Composes config, HTTP client, and all domain services.

```python
from plaude_thunes import ThunesClient

client = ThunesClient(
    api_key="key",
    api_base_url="https://api.example.com/thunes",
    callback_key="cbkey",           # For webhook validation
    callback_secret="cbsecret",
    environment="sandbox",
    timeout=60,
    request_hook=lambda method, url, kwargs: print(f"{method} {url}"),
    response_hook=lambda response: print(response.status_code),
)

client.config            # ThunesConfig instance
client.http              # ThunesHTTPClient (raw HTTP — use for custom calls)
client.payers            # PayerService
client.transactions      # TransactionService
client.credit_party      # CreditPartyService
client.webhook_validator # WebhookValidator (None if no callback credentials)
```

### Hooks

`request_hook` and `response_hook` fire on every HTTP call — useful for logging, tracing, or metrics:

```python
import logging
logger = logging.getLogger(__name__)

client = ThunesClient(
    api_key="...",
    api_base_url="...",
    request_hook=lambda method, url, kwargs: logger.debug("OUT %s %s", method, url),
    response_hook=lambda resp: logger.debug("IN  %s %s", resp.status_code, resp.url),
)
```

---

## Services

### PayerService

`client.payers`

#### `get_by_country_and_currency(country_iso_code, currency)`

Returns a list of payers available for a given country and currency.

```python
payers = client.payers.get_by_country_and_currency("NGA", "USD")
# [{"id": 123, "name": "GTBank Nigeria", ...}, ...]
```

#### `get_details(payer_id)`

Returns full details for a single payer. Returns `None` if not found.

```python
payer = client.payers.get_details("1234")
# {"id": 1234, "name": "GTBank Nigeria", "country": {...}, ...}
```

#### `get_required_fields(payer_id, transaction_type, data_type)`

Returns the fields a payer requires for a given transaction type and data type. Handles flattening of Thunes' nested response format automatically.

```python
# data_type is "beneficiary" or "transaction"
fields = client.payers.get_required_fields("1234", "B2C", "beneficiary")
# {
#   "credit_party_identifiers_accepted": ["bank_account_number", "swift_bic_code"],
#   "required_receiving_entity_fields": ["registered_name", "country_iso_code"]
# }

fields = client.payers.get_required_fields("1234", "B2C", "transaction")
# {
#   "purpose_of_remittance_values_accepted": ["FAMILY_SUPPORT", "EDUCATION"],
#   "required_documents": ["NATIONAL_ID"]
# }
```

---

### TransactionService

`client.transactions`

#### `get_purpose_of_remittance_choices()`

Returns a list of `(value, label)` tuples for use in form/serializer choices. Falls back to hardcoded defaults if the Thunes API is unavailable.

```python
choices = client.transactions.get_purpose_of_remittance_choices()
# [("FAMILY_SUPPORT", "Family Support"), ("EDUCATION", "Education"), ...]
```

#### `get_document_type_choices()`

Returns supported transaction document types as `(value, label)` tuples.

```python
choices = client.transactions.get_document_type_choices()
# [("PASSPORT", "Passport"), ("NATIONAL_ID", "National ID"), ...]
```

#### `create_quotation(payer_id, transaction_type, amount, destination_currency)`

Creates a transaction quotation. Returns the quotation dict from Thunes.

```python
quotation = client.transactions.create_quotation(
    payer_id="1234",
    transaction_type="B2C",
    amount="1000.00",
    destination_currency="NGN",
)
```

#### `create_transaction(data)`

Creates a transaction. `data` is the full transaction payload dict.

```python
transaction = client.transactions.create_transaction(data={...})
```

#### `upload_document(transaction_id, document_type, file, file_name)`

Uploads a supporting document for a transaction.

```python
with open("passport.pdf", "rb") as f:
    result = client.transactions.upload_document(
        transaction_id="tx-001",
        document_type="PASSPORT",
        file=f,
        file_name="passport.pdf",
    )
```

#### `confirm_transaction(transaction_id)`

Confirms a transaction after document upload.

```python
result = client.transactions.confirm_transaction("tx-001")
```

#### `build_b2b_credit_party_identifier(beneficiary_data, b2b_config)` (static)

Builds the `credit_party_identifier` and `receiving_business` dict for a B2B transaction payload.

```python
from plaude_thunes.services.transactions import TransactionService

payload = TransactionService.build_b2b_credit_party_identifier(
    beneficiary_data={...},
    b2b_config={...},
)
# {"receiving_business": {...}, "credit_party_identifier": {...}}
```

#### `build_b2c_payload(beneficiary_data)` (static)

Builds the `beneficiary` dict for a B2C transaction payload.

```python
payload = TransactionService.build_b2c_payload(beneficiary_data={...})
# {"beneficiary": {...}}
```

---

### CreditPartyService

`client.credit_party`

#### `validate(payer_id, credit_party_identifier, transaction_type)`

Validates that a credit party (beneficiary account) exists and is active.

```python
result = client.credit_party.validate(
    payer_id="1234",
    credit_party_identifier={"bank_account_number": "0123456789", "sort_code": "123456"},
    transaction_type="B2C",
)
# {"account_status": "ACTIVE", "id": "..."}
```

#### `get_information(payer_id, credit_party_identifier, transaction_type)`

Returns full account holder information.

```python
info = client.credit_party.get_information(
    payer_id="1234",
    credit_party_identifier={"bank_account_number": "0123456789"},
    transaction_type="B2C",
)
```

#### `get_account_holder_name(payer_id, credit_party_identifier, transaction_type)`

Convenience method — returns just the account holder's name as a string, or `None`.

```python
name = client.credit_party.get_account_holder_name(
    payer_id="1234",
    credit_party_identifier={"bank_account_number": "0123456789"},
    transaction_type="B2C",
)
# "John Doe"
```

---

## DRF Views

### Wiring Views into Your App

All SDK views inherit from `BaseThunesAPIView`, which has empty `authentication_classes` and `permission_classes` by default. Your app subclasses them to add auth, permissions, and a `ThunesClient`.

**Every view subclass MUST either:**
1. Set the `thunes_client` class attribute, or
2. Override `get_thunes_client()` to return a configured `ThunesClient`

Failing to do either raises `NotImplementedError` at request time.

```python
# yourapp/views.py
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from plaude_thunes import ThunesClient
from plaude_thunes.api.views.payers import GetPayersView, GetPayerRequiredFieldsView
from plaude_thunes.api.views.transactions import (
    CreditPartyValidationView,
    CreditPartyInformationView,
)


def _client():
    return ThunesClient(
        api_key=settings.EXTERNAL_API_KEY,
        api_base_url=settings.EXTERNAL_API_BASE_URL,
    )


class SecuredGetPayersView(GetPayersView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_thunes_client(self):
        return _client()


class SecuredGetPayerRequiredFieldsView(GetPayerRequiredFieldsView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_thunes_client(self):
        return _client()


class SecuredCreditPartyValidationView(CreditPartyValidationView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_thunes_client(self):
        return _client()
```

```python
# yourapp/urls.py
from django.urls import path
from .views import (
    SecuredGetPayersView,
    SecuredGetPayerRequiredFieldsView,
    SecuredCreditPartyValidationView,
)

urlpatterns = [
    path(
        "thunes/payers/<str:country_iso_code>/<str:currency>/",
        SecuredGetPayersView.as_view(),
    ),
    path(
        "thunes/payers/<str:payer_id>/<str:transaction_type>/<str:data_type>/required-fields",
        SecuredGetPayerRequiredFieldsView.as_view(),
    ),
    path(
        "thunes/credit-party/validate/",
        SecuredCreditPartyValidationView.as_view(),
    ),
]
```

Alternatively, include the SDK's built-in URL patterns directly (no auth):

```python
from django.urls import include, path

urlpatterns = [
    path("api/", include("plaude_thunes.urls")),
]
```

---

### Available Views

#### `GetPayersView`
`GET /thunes/payers/<country_iso_code>/<currency>/`

Returns all payers available for the given country and currency.

---

#### `GetPayerDetailsView`
`GET /thunes/payers/<payer_id>/`

Returns details for a single payer. Returns `404` if not found.

---

#### `GetPayerRequiredFieldsView`
`GET /thunes/payers/<payer_id>/<transaction_type>/<data_type>/required-fields`

- `transaction_type`: `B2B` or `B2C`
- `data_type`: `beneficiary` or `transaction`

---

#### `GetRepDocumentIdTypesView`
`GET /thunes/utils/rep-document-id-types/`

Returns available representative ID types. Override `get_id_types()` to supply values from your own model:

```python
from plaude_thunes.api.views.payers import GetRepDocumentIdTypesView

class AppRepDocumentIdTypesView(GetRepDocumentIdTypesView):
    def get_id_types(self):
        from myapp.models import RepresentativeIDType
        return list(RepresentativeIDType.objects.values_list("code", flat=True))
```

---

#### `GetPurposeOfRemittanceView`
`GET /thunes/purpose-of-remittance/`

Returns purpose-of-remittance choices. Falls back to hardcoded defaults if the Thunes API is unavailable.

---

#### `GetDocumentTypesView`
`GET /thunes/document-types/`

Returns available transaction document type choices.

---

#### `CreditPartyValidationView`
`POST /thunes/credit-party/validate/`

**Request body:**
```json
{
  "payer_id": "1234",
  "transaction_type": "B2C",
  "credit_party_identifier": {
    "bank_account_number": "0123456789",
    "sort_code": "123456"
  }
}
```

---

#### `CreditPartyInformationView`
`POST /thunes/credit-party/information/`

Same request body shape as validation. Returns full account holder information.

---

### URL Patterns

| Method | URL | View | Name |
|--------|-----|------|------|
| GET | `thunes/payers/<country_iso_code>/<currency>/` | `GetPayersView` | `thunes-payers-by-country-currency` |
| GET | `thunes/payers/<payer_id>/` | `GetPayerDetailsView` | `thunes-payer-details` |
| GET | `thunes/payers/<payer_id>/<transaction_type>/<data_type>/required-fields` | `GetPayerRequiredFieldsView` | `thunes-payer-required-fields` |
| GET | `thunes/utils/rep-document-id-types/` | `GetRepDocumentIdTypesView` | `thunes-rep-document-id-types` |
| GET | `thunes/purpose-of-remittance/` | `GetPurposeOfRemittanceView` | `thunes-purpose-of-remittance` |
| GET | `thunes/document-types/` | `GetDocumentTypesView` | `thunes-document-types` |
| POST | `thunes/credit-party/validate/` | `CreditPartyValidationView` | `thunes-credit-party-validate` |
| POST | `thunes/credit-party/information/` | `CreditPartyInformationView` | `thunes-credit-party-information` |
| POST | `thunes/webhook/` | `BaseThunesWebhookView` | `thunes-webhook` |

---

## Serializers

All serializers live in `plaude_thunes.api.serializers` and extend `BaseThunesSerializer`.

### `FilenameMaxLengthValidator`

A Django-compatible validator for file upload filenames. Checks the base name length (excluding extension).

```python
from plaude_thunes.api.serializers import FilenameMaxLengthValidator

document = serializers.FileField(
    validators=[FilenameMaxLengthValidator(max_length=50)]
)
```

### `CreditPartyIdentifierSerializer`

Validates Thunes credit-party identifier fields. All 20 fields are optional — the parent serializer enforces that at least one is provided.

Supported fields: `msisdn`, `bank_account_number`, `iban`, `sort_code`, `aba_routing_number`, `account_number`, `email`, `routing_code`, `account_type`, `swift_bic_code`, `clabe`, `cbu`, `cbu_alias`, `bik_code`, `ifs_code`, `bsb_number`, `branch_number`, `entity_tt_id`, `card_number`, `qr_code`.

### `CreditPartySerializer`

Validates input for credit-party endpoints. Requires `payer_id`, `transaction_type` (`B2B`/`B2C`), and a nested `credit_party_identifier` with at least one non-empty field.

### `CheckAccountSerializer`

Full account-check input serializer. The SDK validates format and payer existence via the Thunes API. **`create()` must be overridden in your app** — the SDK has no access to your Django models.

```python
from plaude_thunes.api.serializers import CheckAccountSerializer
from rest_framework import serializers

class AppCheckAccountSerializer(CheckAccountSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        from myapp.models import Country, Currency
        attrs["country"] = Country.objects.get(id=attrs["country"])
        attrs["currency"] = Currency.objects.get(code=attrs["currency"])
        return attrs

    def create(self, validated_data):
        from myapp.helpers import ThunesAccountService
        success, result = ThunesAccountService.process_account(
            user=self.context["user"], **validated_data
        )
        if not success:
            raise serializers.ValidationError({"detail": result})
        return success, result
```

Pass `thunes_client` and `user` in context for payer existence validation:

```python
serializer = AppCheckAccountSerializer(
    data=request.data,
    context={
        "user": request.user,
        "thunes_client": ThunesClient(api_key=..., api_base_url=...),
    }
)
```

### `BaseBeneficiarySerializer`

Extends `CreditPartyIdentifierSerializer` with address, representative, and business fields. Override `validate()` to resolve Country model objects:

```python
from plaude_thunes.api.serializers import BaseBeneficiarySerializer

class AppBeneficiarySerializer(BaseBeneficiarySerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("country_iso_code"):
            attrs["country"] = Country.objects.get(iso3=attrs["country_iso_code"])
        return attrs
```

### `BusinessBeneficiarySerializer`

Extends `BaseBeneficiarySerializer` with a required `registered_name` field (B2B).

### `QuotationSerializer`

Validates quotation input. Enforces that `amount` is a positive decimal string and `destination_currency` is exactly 3 characters.

```python
from plaude_thunes.api.serializers import QuotationSerializer

serializer = QuotationSerializer(data={
    "payer_id": "1234",
    "transaction_type": "B2C",
    "amount": "500.00",
    "destination_currency": "NGN",
})
serializer.is_valid(raise_exception=True)
```

---

## Webhook Handling

Subclass `BaseThunesWebhookView`, set `callback_key`/`callback_secret`, and implement `handle_event()`.

```python
# yourapp/webhooks.py
from django.conf import settings
from plaude_thunes.api.views.webhooks import BaseThunesWebhookView
from myapp.models import Transaction, Status
import logging

logger = logging.getLogger(__name__)


class ThunesWebhookView(BaseThunesWebhookView):
    callback_key = settings.THUNES_CALLBACK_KEY
    callback_secret = settings.THUNES_CALLBACK_SECRET

    def handle_event(self, data: dict):
        transaction_id = data.get("id")
        status_message = data.get("status_message")
        status_class_message = data.get("status_class_message")

        try:
            transaction = Transaction.objects.get(partner_reference=transaction_id)
        except Transaction.DoesNotExist:
            logger.warning("Thunes webhook: transaction %s not found", transaction_id)
            return

        transaction.partner_status = status_message
        transaction.partner_status_class = status_class_message
        if status_class_message == "COMPLETED":
            transaction.status = Status.Success.value
        transaction.save()
```

```python
# yourapp/urls.py
from django.urls import path
from .webhooks import ThunesWebhookView

urlpatterns = [
    path("api/thunes/webhook", ThunesWebhookView.as_view(), name="thunes-webhook"),
]
```

Override `get_webhook_validator()` for dynamic credentials:

```python
from plaude_thunes.security.webhook import WebhookValidator

class ThunesWebhookView(BaseThunesWebhookView):
    def get_webhook_validator(self):
        return WebhookValidator(
            callback_key=settings.THUNES_CALLBACK_KEY,
            callback_secret=settings.THUNES_CALLBACK_SECRET,
        )

    def handle_event(self, data: dict):
        ...
```

Override `on_validation_error()` to customise the 401 response:

```python
from django.http import JsonResponse

class ThunesWebhookView(BaseThunesWebhookView):
    def on_validation_error(self, exc):
        return JsonResponse({"error": "Webhook auth failed", "reason": exc.reason}, status=401)
```

### `WebhookValidator` (direct use)

```python
from plaude_thunes.security.webhook import WebhookValidator

validator = WebhookValidator(callback_key="key", callback_secret="secret")
validator.is_valid(request)             # bool
validator.validate(request)             # raises ThunesWebhookError on failure
validator.extract_credentials(request)  # returns (key, secret) or None
```

---

## Exceptions

```
ThunesSDKError
├── ThunesAPIError(message, status_code, response_body)
│   ├── ThunesAuthenticationError   — 401 / 403 from gateway
│   ├── ThunesValidationError(errors)  — 400 with field-level errors
│   └── ThunesNotFoundError         — 404 resource not found
├── ThunesWebhookError(message, reason)  — webhook validation failure
└── ThunesConfigError               — missing/invalid SDK configuration
```

```python
from plaude_thunes.exceptions import (
    ThunesAPIError,
    ThunesAuthenticationError,
    ThunesValidationError,
    ThunesNotFoundError,
    ThunesWebhookError,
)

try:
    payer = client.payers.get_details("bad-id")
except ThunesNotFoundError:
    print("Payer not found")
except ThunesAuthenticationError:
    print("Invalid API credentials")
except ThunesValidationError as e:
    print("Validation failed:", e.errors)
except ThunesAPIError as e:
    print(f"Thunes API error {e.status_code}: {e.message}")
```

---

## Utilities

### `SPECIAL_PAYERS`

Hardcoded payer overrides for country/currency pairs where Thunes requires a specific payer ID.

```python
from plaude_thunes.utils.helpers import get_special_payer

get_special_payer("CHN", "USD")  # {"id": 6248, ...}
get_special_payer("IND", "USD")  # {"id": 6484, ...}
get_special_payer("HKG", "USD")  # {"id": 6241, ...}
get_special_payer("GBR", "GBP")  # None
```

| Country | Currency | Payer ID |
|---------|----------|----------|
| CHN | USD | 6248 |
| IND | USD | 6484 |
| HKG | USD | 6241 |

### `IDENTIFIER_CONFIG`

Maps identifier field names to human-readable labels. Useful for building dynamic forms.

```python
from plaude_thunes.utils.helpers import IDENTIFIER_CONFIG

IDENTIFIER_CONFIG.get("swift_bic_code")  # "SWIFT/BIC"
IDENTIFIER_CONFIG.get("msisdn")          # "Mobile Number"
```

### Helper functions

```python
from plaude_thunes.utils.helpers import title_case, to_human_readable, flatten_list

title_case("bank_account_number")   # "Bank Account Number"
title_case("swift_bic")             # "SWIFT/BIC"
to_human_readable("FAMILY_SUPPORT") # "Family Support"
flatten_list([[1, 2], [3, [4, 5]]]) # [1, 2, 3, 4, 5]
```

---

## Testing

```bash
pip install -e ".[dev,django]"
pytest
```

The `tests/` directory lives at the project root alongside the source files. pytest is configured in `pyproject.toml`:

- `testpaths = ["tests"]` — only runs files inside `tests/`
- `pythonpath = ["."]` — project root on `sys.path` so `plaude_thunes.*` imports resolve
- `DJANGO_SETTINGS_MODULE = "tests.settings"` — minimal Django config in `tests/settings.py`

Tests use `responses` to mock all HTTP calls — no real Thunes API calls are made.

```python
# Example: testing a view subclass
import responses as responses_lib
from rest_framework.test import APIRequestFactory
from plaude_thunes import ThunesClient
from plaude_thunes.api.views.payers import GetPayersView

class MyGetPayersView(GetPayersView):
    def get_thunes_client(self):
        return ThunesClient(api_key="test", api_base_url="https://test.example.com/thunes")

@responses_lib.activate
def test_get_payers():
    responses_lib.add(
        responses_lib.GET,
        "https://test.example.com/thunes/payer/NGA/USD",
        json=[{"id": 1, "name": "Test Bank"}],
        status=200,
    )
    factory = APIRequestFactory()
    request = factory.get("/")
    response = MyGetPayersView.as_view()(request, country_iso_code="NGA", currency="USD")
    assert response.status_code == 200
```

---

## Design Principles

- **Explicit over implicit** — credentials are always passed at construction time, never read from environment variables or Django settings automatically.
- **No model coupling** — the SDK has no Django ORM dependency. Serializers that need model objects provide abstract hooks (`validate()`, `create()`) for the app to implement.
- **Extensible views** — all views ship with empty auth/permissions. Add your own stack by subclassing and setting `authentication_classes` / `permission_classes`.
- **Single responsibility** — HTTP, services, serializers, and views are separate layers.
- **Testable** — domain services are injected with the HTTP client, making them independently testable with mocks.
