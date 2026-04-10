"""
Payer-related DRF serializers for plaude_thunes.
"""

from rest_framework import serializers

from plaude_thunes.api.serializers.base import BaseThunesSerializer


class PayerRequiredFieldsSerializer(BaseThunesSerializer):
    """
    Validates input for the GetPayerRequiredFieldsView.

    Fields:
        payer_id (str): Thunes payer ID (required)
        transaction_type (str): "B2B" or "B2C" (required)
        data_type (str): "beneficiary" or "transaction" (required)

    This is the SDK-level version of ``ThunesPayerRequiredFieldsSerializer``
    from the host application. It validates format only — payer existence
    is checked by the view via the Thunes API.

    Downstream apps can extend this to add payer-existence DB validation::

        class AppPayerRequiredFieldsSerializer(PayerRequiredFieldsSerializer):
            def validate_payer_id(self, value):
                from myapp.models import KnownPayer
                if not KnownPayer.objects.filter(payer_id=value).exists():
                    raise serializers.ValidationError("Unknown payer")
                return value
    """

    payer_id = serializers.CharField(write_only=True, required=True)
    transaction_type = serializers.ChoiceField(
        choices=["B2B", "B2C"],
        write_only=True,
        required=True,
    )
    data_type = serializers.ChoiceField(
        choices=["beneficiary", "transaction"],
        write_only=True,
        required=True,
    )
