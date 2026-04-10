"""
Payer-related service logic for plaude_thunes.

PayerService wraps the HTTP client to provide high-level payer operations,
including required-fields extraction logic (ported from internal_api/helpers.py).
"""

import logging
from typing import Dict, List, Optional

from plaude_thunes.clients.thunes_client import ThunesHTTPClient

logger = logging.getLogger(__name__)


class PayerService:
    """
    High-level service for Thunes payer operations.

    Args:
        http_client: ThunesHTTPClient (or compatible duck-typed object).

    Example::

        client = ThunesClient(api_key="...", api_base_url="...")
        payers = client.payers.get_by_country_and_currency("NGA", "USD")
    """

    def __init__(self, http_client: ThunesHTTPClient):
        self._http = http_client

    def get_by_country_and_currency(
        self, country: str, currency: str
    ) -> Optional[List[Dict]]:
        """
        Return the list of available payers for a country/currency pair.

        Args:
            country: 3-letter ISO country code (e.g. "NGA").
            currency: 3-letter currency code (e.g. "USD").

        Returns:
            List of payer dicts, or None on error.
        """
        response = self._http.get_payers_by_country_and_currency(country, currency)
        if response:
            return response.get("data")
        return None

    def get_details(self, payer_id: str) -> Optional[Dict]:
        """
        Return full payer details for a given payer ID.

        Args:
            payer_id: Thunes payer ID.

        Returns:
            Payer detail dict, or None if not found / on error.
        """
        response = self._http.get_payer_details(payer_id)
        if response:
            return response.get("data")
        return None

    def get_required_fields(
        self, payer_id: str, transaction_type: str, data_type: str
    ) -> Dict:
        """
        Retrieve required fields for a payer based on transaction and data type.

        This is the logic ported from ``internal_api/helpers.get_payer_required_fields()``.

        Args:
            payer_id: Thunes payer ID.
            transaction_type: "B2B" or "B2C".
            data_type: "beneficiary" or "transaction".

        Returns:
            Dict with keys relevant to data_type:
                - For "beneficiary":
                    {"credit_party_identifiers_accepted": [...],
                     "required_receiving_entity_fields": [...]}
                - For "transaction":
                    {"purpose_of_remittance_values_accepted": [...],
                     "required_documents": [...]}
            Returns empty dict if payer not found or data unavailable.
        """
        api_response = self._http.get_payer_details(payer_id)
        if api_response is None:
            return {}

        response_payload: Dict = {
            "beneficiary": {},
            "transaction": {},
        }

        payer_data = api_response.get("data", {})
        transaction_types = payer_data.get("transaction_types", {})
        type_data = transaction_types.get(transaction_type, {})

        if data_type == "beneficiary":
            identifiers = type_data.get("credit_party_identifiers_accepted", [])
            entity_fields = type_data.get("required_receiving_entity_fields", [])

            response_payload["beneficiary"]["credit_party_identifiers_accepted"] = (
                identifiers
            )
            response_payload["beneficiary"]["required_receiving_entity_fields"] = (
                entity_fields
            )
        elif data_type == "transaction":
            purpose_values = type_data.get("purpose_of_remittance_values_accepted", [])
            required_docs = type_data.get("required_documents", [])

            response_payload["transaction"]["purpose_of_remittance_values_accepted"] = (
                purpose_values
            )
            response_payload["transaction"]["required_documents"] = required_docs

        return response_payload.get(data_type, {})
