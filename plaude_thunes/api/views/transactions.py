"""
Transaction and credit-party DRF views for plaude_thunes.

Views:
    GetPurposeOfRemittanceView  - List purpose-of-remittance choices
    GetDocumentTypesView        - List supported transaction document types
    CreditPartyValidationView   - Validate a credit party (beneficiary account)
    CreditPartyInformationView  - Retrieve credit party account holder info
"""

import logging

from django.http import JsonResponse
from rest_framework import status

from plaude_thunes.api.serializers.transactions import CreditPartySerializer
from plaude_thunes.api.views.base import BaseThunesAPIView

logger = logging.getLogger(__name__)


class GetPurposeOfRemittanceView(BaseThunesAPIView):
    """
    GET /thunes/purpose-of-remittance/

    Return available purpose-of-remittance choices.
    Falls back to a hardcoded list if the Thunes API is unavailable.
    """

    def get(self, request, *args, **kwargs):
        client = self.get_thunes_client()
        choices = client.transactions.get_purpose_of_remittance_choices()

        data = [{"id": i, "purpose": v} for i, (v, _) in enumerate(choices) if v]
        return JsonResponse(
            {
                "status": "success",
                "message": "Purpose of remittance choices retrieved",
                "data": data,
            },
            status=status.HTTP_200_OK,
        )


class GetDocumentTypesView(BaseThunesAPIView):
    """
    GET /thunes/document-types/

    Return supported transaction document types.
    """

    def get(self, request, *args, **kwargs):
        client = self.get_thunes_client()
        choices = client.transactions.get_document_types()
        
        return JsonResponse(
            {
                "status": "success",
                "message": "Document types retrieved",
                "data": choices,
            },
            status=status.HTTP_200_OK,
        )


class CreditPartyValidationView(BaseThunesAPIView):
    """
    POST /thunes/credit-party/validate/

    Validate a beneficiary account (credit party) via Thunes.

    Request body:
        payer_id (str): Thunes payer ID
        transaction_type (str): "B2B" or "B2C"
        credit_party_identifier (dict): Identifier fields

    Extend with auth/permissions as needed.
    """

    def post(self, request, *args, **kwargs):
        serializer = CreditPartySerializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = self.get_thunes_client()
        result = client.credit_party.validate(
            payer_id=serializer.validated_data["payer_id"],
            credit_party_identifier=serializer.validated_data[
                "credit_party_identifier"
            ],
            transaction_type=serializer.validated_data["transaction_type"],
        )

        if result is None:
            result = {"account_status": "UNAVAILABLE", "id": None}

        return JsonResponse(
            {
                "status": "success",
                "message": "Credit party validation completed",
                "data": result,
            },
            status=status.HTTP_200_OK,
        )


class CreditPartyInformationView(BaseThunesAPIView):
    """
    POST /thunes/credit-party/information/

    Retrieve full account holder information for a credit party.

    Request body:
        payer_id (str): Thunes payer ID
        transaction_type (str): "B2B" or "B2C"
        credit_party_identifier (dict): Identifier fields
    """

    def post(self, request, *args, **kwargs):
        serializer = CreditPartySerializer(data=request.data)
        if not serializer.is_valid():
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Validation failed",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = self.get_thunes_client()
        result = client.credit_party.get_information(
            payer_id=serializer.validated_data["payer_id"],
            credit_party_identifier=serializer.validated_data[
                "credit_party_identifier"
            ],
            transaction_type=serializer.validated_data["transaction_type"],
        )

        return JsonResponse(
            {
                "status": "success",
                "message": "Credit party information retrieved",
                "data": result or {},
            },
            status=status.HTTP_200_OK,
        )
