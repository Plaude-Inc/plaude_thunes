"""
Payer-related DRF views for plaude_thunes.

Views:
    GetPayersView               - List payers by country and currency
    GetPayerDetailsView         - Get full payer details by ID
    GetPayerRequiredFieldsView  - Get required fields for a payer/transaction/data-type
    GetRepDocumentIdTypesView   - List valid representative document ID types
"""

import logging
from enum import Enum

from django.http import JsonResponse
from rest_framework import status

from plaude_thunes.api.views.base import BaseThunesAPIView
from plaude_thunes.utils.helpers import get_special_payer

logger = logging.getLogger(__name__)


class GetPayersView(BaseThunesAPIView):
    """
    GET /thunes/payers/<country_iso_code>/<currency>/

    Return the list of payers available for a given country/currency pair.

    URL kwargs:
        country (str): 3-letter ISO country code (e.g. "NGA")
        currency (str): 3-letter currency code (e.g. "USD")

    Extend this view to add authentication/permissions::

        class MyGetPayersView(GetPayersView):
            authentication_classes = [JWTAuthentication]
            permission_classes = [IsAuthenticated]
    """

    def get(self, request, country: str, currency: str, *args, **kwargs):
        client = self.get_thunes_client()
        special_payer = get_special_payer(country, currency)
        if special_payer:
            payers = [special_payer]
        else:
            payers_data_response = client.payers.get_by_country_and_currency(
                country, currency
            )
            if payers_data_response is None:
                return JsonResponse(
                    {"status": "error", "message": "Failed to fetch payers"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            payers = [
                {"id": payer.get("id", ""), "name": payer.get("name", "")}
                for payer in payers_data_response
            ]

        return JsonResponse(
            {
                "status": "success",
                "message": "Payers retrieved successfully",
                "data": payers,
            },
            status=status.HTTP_200_OK,
        )


class GetPayerDetailsView(BaseThunesAPIView):
    """
    GET /thunes/payers/<payer_id>/

    Return full details for a single Thunes payer.

    URL kwargs:
        payer_id (str): Thunes payer ID
    """

    def get(self, request, payer_id: str, *args, **kwargs):
        client = self.get_thunes_client()
        payer = client.payers.get_details(payer_id)

        if payer is None:
            return JsonResponse(
                {"status": "error", "message": f"Payer '{payer_id}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return JsonResponse(
            {
                "status": "success",
                "message": "Payer details retrieved successfully",
                "data": payer,
            },
            status=status.HTTP_200_OK,
        )


class GetPayerRequiredFieldsView(BaseThunesAPIView):
    """
    GET /thunes/payers/<payer_id>/<transaction_type>/<data_type>/required-fields

    Return the required fields for a payer given transaction type and data type.

    This view replicates ``GetThunesPayerRequiredFieldsView`` from the host app.

    URL kwargs:
        payer_id (str): Thunes payer ID
        transaction_type (str): "B2B" or "B2C"
        data_type (str): "beneficiary" or "transaction"

    Downstream apps typically add authentication and permission classes::

        class SecuredPayerFieldsView(GetPayerRequiredFieldsView):
            authentication_classes = [JWTAuthentication]
            permission_classes = [IsAuthenticated]
    """

    def get(
        self,
        request,
        payer_id: str,
        transaction_type: str,
        data_type: str,
        *args,
        **kwargs,
    ):
        if data_type not in ("beneficiary", "transaction"):
            return JsonResponse(
                {
                    "status": "error",
                    "message": "data_type must be 'beneficiary' or 'transaction'",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = self.get_thunes_client()
        required_fields = client.payers.get_required_fields(
            payer_id=payer_id,
            transaction_type=transaction_type,
            data_type=data_type,
        )

        if not required_fields:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "No required fields found for the given parameters",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return JsonResponse(
            {
                "status": "success",
                "message": f"Required fields for {data_type} retrieved successfully",
                "data": required_fields,
            },
            status=status.HTTP_200_OK,
        )


class RepresentativeIDType(Enum):
    PASSPORT = "Passport"
    NATIONAL_ID = "National Identification Card"
    DRIVING_LICENSE = "Driving License"
    SOCIAL_SECURITY = "Social Security Card/Number"
    TAX_ID = "Tax Payer Identification Card/Number"
    SENIOR_CITIZEN_ID = "Senior Citizen Identification Card"
    BIRTH_CERTIFICATE = "Birth Certificate"
    VILLAGE_ELDER_ID = "Village Elder Identification Card"
    RESIDENT_CARD = "Permanent Residency Identification Card"
    ALIEN_REGISTRATION = "Alien Registration Certificate/Card"
    PAN_CARD = "PAN Card"
    VOTERS_ID = "Voter's Identification Card"
    HEALTH_CARD = "Health Insurance Card/Number"
    EMPLOYER_ID = "Employer Identification Card"
    OTHER = "Other"


class GetRepDocumentIdTypesView(BaseThunesAPIView):
    """
    GET /thunes/utils/rep-document-id-types/

    Return the list of valid representative document ID types.

    This view replicates ``GetThunesRepDocumentIdTypesView`` from the host app.
    It reads from the ``RepresentativeIDType`` enum — if that model is available
    via Django, it reads it; otherwise it returns an empty list.

    Override ``get_id_types()`` to provide types from a different source::

        class MyRepDocView(GetRepDocumentIdTypesView):
            def get_id_types(self):
                return [{"name": "Passport", "value": "PASSPORT"}]
    """

    def get(self, request, *args, **kwargs):
        respresentative_id_types = [
            {"name": e.value, "value": e.name} for e in RepresentativeIDType
        ]
        return JsonResponse(
            {
                "status": "success",
                "message": "Representative Document ID Types retrieved successfully",
                "data": respresentative_id_types,
            },
            status=status.HTTP_200_OK,
        )
