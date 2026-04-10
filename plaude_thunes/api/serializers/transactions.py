"""
Transaction and credit-party DRF serializers for plaude_thunes.

Key serializers:
    FilenameMaxLengthValidator      - Django validator for upload filename length
    CreditPartyIdentifierSerializer - All Thunes credit-party identifier fields
    CreditPartySerializer           - payer_id + transaction_type + nested identifier
    CheckAccountSerializer          - Full account-check input (override .create())
    BaseBeneficiarySerializer       - Common beneficiary fields
    BusinessBeneficiarySerializer   - Adds registered_name for B2B
    QuotationSerializer             - Input for creating a quotation
"""

import os
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from plaude_thunes.api.serializers.base import BaseThunesSerializer

# ---------------------------------------------------------------------------
# Default choices — override in subclasses or via Django model enums
# ---------------------------------------------------------------------------
DEFAULT_ACCOUNT_TYPE_CHOICES = ["CHECKING", "SAVINGS", "DEPOSIT", "OTHERS"]

# Representative ID type choices — downstream app should override this if
# it uses a RepresentativeIDType model/enum.
DEFAULT_REP_ID_TYPE_CHOICES = [
    "PASSPORT",
    "NATIONAL_ID",
    "DRIVERS_LICENSE",
    "RESIDENCE_PERMIT",
    "TAX_ID",
    "OTHER",
]


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


class FilenameMaxLengthValidator:
    """
    Django-compatible validator that checks the filename length (excluding extension).

    Designed for use with DRF FileField / ImageField::

        document = serializers.FileField(
            validators=[FilenameMaxLengthValidator(max_length=50)]
        )

    Also works with Django form FileField.

    Args:
        max_length: Maximum allowed length of the base filename (default: 50).
        message: Optional custom error message template.
    """

    message = (
        "Filename must not exceed %(max_length)s characters (excluding extension)."
    )
    code = "filename_too_long"

    def __init__(self, max_length: int = 50, message: str = None):
        self.max_length = max_length
        if message is not None:
            self.message = message

    def __call__(self, value):
        filename = value.name
        name_without_ext = os.path.splitext(filename)[0]
        if len(name_without_ext) > self.max_length:
            raise DjangoValidationError(
                self.message,
                code=self.code,
                params={"max_length": self.max_length, "length": len(name_without_ext)},
            )

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and self.max_length == other.max_length
            and self.message == other.message
            and self.code == other.code
        )


# ---------------------------------------------------------------------------
# Credit party
# ---------------------------------------------------------------------------


class CreditPartyIdentifierSerializer(BaseThunesSerializer):
    """
    Validates a set of Thunes credit-party identifier fields.

    All fields are optional; at least one must be provided (enforced by the
    parent CreditPartySerializer / CheckAccountSerializer).

    Extensibility:
        - Subclass and add extra fields for non-standard identifiers.
        - Override account_type.choices to use your project's AccountType enum.

    This is the SDK-level version of the host app's ``CreditPartyIdentifierSerializer``.
    """

    msisdn = serializers.CharField(write_only=True, required=False)
    bank_account_number = serializers.CharField(write_only=True, required=False)
    iban = serializers.CharField(write_only=True, required=False)
    sort_code = serializers.CharField(write_only=True, required=False)
    aba_routing_number = serializers.CharField(write_only=True, required=False)
    account_number = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)
    routing_code = serializers.CharField(write_only=True, required=False)
    account_type = serializers.ChoiceField(
        choices=DEFAULT_ACCOUNT_TYPE_CHOICES,
        write_only=True,
        required=False,
    )
    swift_bic_code = serializers.CharField(write_only=True, required=False)
    clabe = serializers.CharField(write_only=True, required=False)
    cbu = serializers.CharField(write_only=True, required=False)
    cbu_alias = serializers.CharField(write_only=True, required=False)
    bik_code = serializers.CharField(write_only=True, required=False)
    ifs_code = serializers.CharField(write_only=True, required=False)
    bsb_number = serializers.CharField(write_only=True, required=False)
    branch_number = serializers.CharField(write_only=True, required=False)
    entity_tt_id = serializers.CharField(write_only=True, required=False)
    card_number = serializers.CharField(write_only=True, required=False)
    qr_code = serializers.CharField(write_only=True, required=False)

    def to_representation(self, instance):
        """Strip None/empty values from output."""
        data = super().to_representation(instance)
        return {k: v for k, v in data.items() if v}


class CreditPartySerializer(BaseThunesSerializer):
    """
    Validates input for credit-party validation / information endpoints.

    Fields:
        payer_id (str): Thunes payer ID (required)
        transaction_type (str): "B2B" or "B2C" (required)
        credit_party_identifier: Nested CreditPartyIdentifierSerializer (required,
            at least one identifier field must be non-empty)

    This is the SDK-level version of the host app's ``CreditPartySerializer``.
    Uses a strongly-typed nested serializer rather than a raw DictField so
    each identifier field receives proper type validation.
    """

    payer_id = serializers.CharField(write_only=True, required=True)
    transaction_type = serializers.ChoiceField(
        choices=["B2B", "B2C"], write_only=True, required=True
    )
    credit_party_identifier = CreditPartyIdentifierSerializer(
        write_only=True, required=True
    )

    def validate(self, attrs):
        identifier_data = attrs.get("credit_party_identifier", {})
        non_empty = {k: v for k, v in identifier_data.items() if v}
        if not non_empty:
            raise serializers.ValidationError(
                {
                    "credit_party_identifier": "At least one identifier field must be provided."
                }
            )
        attrs["credit_party_identifier"] = non_empty
        return attrs


# ---------------------------------------------------------------------------
# Account check serializer
# ---------------------------------------------------------------------------


class CheckAccountSerializer(BaseThunesSerializer):
    """
    Validates the full input for the "check account / create beneficiary" flow.

    This is the SDK-level version of the host app's ``CheckAccountSerializer``.

    The SDK validates format, transaction type, and payer existence (via Thunes API).
    The ``.create()`` method is intentionally left as a no-op — downstream apps
    must override it to create their ``Beneficiary`` and ``ThunesPayer`` models::

        class AppCheckAccountSerializer(CheckAccountSerializer):
            def validate(self, attrs):
                attrs = super().validate(attrs)
                # Resolve Django Country/Currency objects
                from ky.models import Country, Currency
                attrs["country"] = Country.objects.get(id=attrs["country"])
                attrs["currency"] = Currency.objects.get(code=attrs["currency"])
                return attrs

            def create(self, validated_data):
                from remit.helpers import ThunesAccountService
                success, result = ThunesAccountService.process_account(
                    user=self.context["user"], **validated_data
                )
                if not success:
                    raise serializers.ValidationError({"detail": result})
                return success, result

    Fields:
        transaction_type (str): "B2B" or "B2C"
        payer_id (str): Thunes payer ID
        credit_party_identifier: Nested identifier fields
        currency (str): Destination currency code
        country (str/int): Country identifier (resolved in app's override)
    """

    transaction_type = serializers.ChoiceField(
        choices=["B2B", "B2C"], write_only=True, required=True
    )
    payer_id = serializers.CharField(write_only=True, required=True)
    credit_party_identifier = CreditPartyIdentifierSerializer(
        write_only=True, required=True
    )
    currency = serializers.CharField(write_only=True, required=True)
    country = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if "user" not in self.context:
            raise serializers.ValidationError(
                {"user": "'user' must be provided in serializer context."}
            )
        identifier_data = attrs.get("credit_party_identifier", {})
        non_empty = {k: v for k, v in identifier_data.items() if v}
        if not non_empty:
            raise serializers.ValidationError(
                {"credit_party_identifier": "This field is required."}
            )
        attrs["credit_party_identifier"] = non_empty

        # Validate payer existence via Thunes API
        payer_id = attrs["payer_id"]
        thunes_client = self.context.get("thunes_client")
        if thunes_client:
            payer = thunes_client.payers.get_details(payer_id)
            if not payer:
                raise serializers.ValidationError({"payer_id": "Payer does not exist."})

        return attrs

    def create(self, validated_data):
        """
        Override in your Django app to create Beneficiary + ThunesPayer.

        The SDK leaves this abstract because it has no access to Django models.
        """
        raise NotImplementedError(
            "CheckAccountSerializer.create() must be overridden in your Django app."
        )


# ---------------------------------------------------------------------------
# Beneficiary serializers
# ---------------------------------------------------------------------------


class BaseBeneficiarySerializer(CreditPartyIdentifierSerializer):
    """
    Common beneficiary fields extending CreditPartyIdentifierSerializer.

    Includes representative fields (for B2B compliance) and address fields.
    Downstream apps subclass this and override `validate()` to resolve
    Country model objects from the ``country_iso_code`` / ``representative_id_country_iso_code`` fields.

    This is the SDK-level version of the host app's ``BaseBeneficiarySerializer``.
    """

    tax_id = serializers.CharField(write_only=True, required=False)
    address = serializers.CharField(write_only=True, required=False)
    city = serializers.CharField(write_only=True, required=False)
    province_state = serializers.CharField(write_only=True, required=False)
    postal_code = serializers.CharField(write_only=True, required=False)
    registration_number = serializers.CharField(write_only=True, required=False)
    country_iso_code = serializers.CharField(write_only=True, required=False)
    account_holder_name = serializers.CharField(write_only=True, required=False)
    trading_name = serializers.CharField(write_only=True, required=False)
    date_of_incorporation = serializers.CharField(write_only=True, required=False)
    phone_number = serializers.CharField(write_only=True, required=False)

    # Representative fields (required for B2B with certain payers)
    representative_firstname = serializers.CharField(write_only=True, required=False)
    representative_lastname = serializers.CharField(write_only=True, required=False)
    representative_lastname2 = serializers.CharField(write_only=True, required=False)
    representative_middlename = serializers.CharField(write_only=True, required=False)
    representative_nativename = serializers.CharField(write_only=True, required=False)
    representative_id_type = serializers.ChoiceField(
        choices=DEFAULT_REP_ID_TYPE_CHOICES,
        write_only=True,
        required=False,
    )
    representative_id_country_iso_code = serializers.CharField(
        write_only=True, required=False
    )
    representative_id_number = serializers.CharField(write_only=True, required=False)
    representative_id_delivery_date = serializers.CharField(
        write_only=True, required=False
    )
    representative_id_expiration_date = serializers.CharField(
        write_only=True, required=False
    )

    def validate(self, attrs):
        """
        Base validation: override in downstream app to resolve Country objects.

        The SDK cannot resolve Country objects (no access to Django models).
        In the host app::

            class AppBeneficiarySerializer(BaseBeneficiarySerializer):
                def validate(self, attrs):
                    attrs = super().validate(attrs)
                    if "country_iso_code" in attrs:
                        attrs["country"] = Country.objects.get(iso3=attrs["country_iso_code"])
                    return attrs
        """
        return attrs


class BusinessBeneficiarySerializer(BaseBeneficiarySerializer):
    """
    B2B beneficiary serializer.

    Adds ``registered_name`` as a required field.

    This is the SDK-level version of the host app's ``BusinessBeneficiarySerializer``.
    """

    registered_name = serializers.CharField(write_only=True, required=True)


# ---------------------------------------------------------------------------
# Quotation serializer
# ---------------------------------------------------------------------------


class QuotationSerializer(BaseThunesSerializer):
    """
    Validates input for creating a transaction quotation.

    Fields:
        payer_id (str): Thunes payer ID
        transaction_type (str): "B2B" or "B2C"
        amount (str): Amount as string (e.g. "1000.00")
        destination_currency (str): 3-letter currency code
    """

    payer_id = serializers.CharField(required=True)
    transaction_type = serializers.ChoiceField(choices=["B2B", "B2C"], required=True)
    amount = serializers.CharField(required=True)
    destination_currency = serializers.CharField(
        required=True, max_length=3, min_length=3
    )

    def validate_amount(self, value: str) -> str:
        try:
            decimal_value = Decimal(value)
            if decimal_value <= 0:
                raise serializers.ValidationError("Amount must be positive.")
        except (InvalidOperation, TypeError):
            raise serializers.ValidationError("Amount must be a valid decimal number.")
        return value
