"""
Credit party validation and information service for plaude_thunes.

Wraps the two Thunes credit-party API endpoints:
    - POST /payers/credit-party-validation
    - POST /payers/credit-party-information
"""

import logging
from typing import Dict, Optional

from plaude_thunes.clients.thunes_client import ThunesHTTPClient

logger = logging.getLogger(__name__)


class CreditPartyService:
    """
    Service for Thunes credit party (beneficiary account) operations.

    Args:
        http_client: ThunesHTTPClient instance.

    Example::

        result = client.credit_party.validate(
            payer_id="1234",
            credit_party_identifier={"bank_account_number": "0123456789"},
            transaction_type="B2B",
        )
    """

    def __init__(self, http_client: ThunesHTTPClient):
        self._http = http_client

    def validate(
        self,
        payer_id: str,
        credit_party_identifier: Dict,
        transaction_type: str,
    ) -> Optional[Dict]:
        """
        Validate a credit party account with Thunes.

        Args:
            payer_id: Thunes payer ID.
            credit_party_identifier: Dict of identifier fields
                (e.g. {"bank_account_number": "0123456789"}).
            transaction_type: "B2B" or "B2C".

        Returns:
            Validation result dict (contains account_status, id), or None on error.
        """
        response = self._http.credit_party_validation(
            payer_id=payer_id,
            credit_party_identifier=credit_party_identifier,
            transaction_type=transaction_type,
        )
        if response:
            return response.get("data")
        return None

    def get_information(
        self,
        payer_id: str,
        credit_party_identifier: Dict,
        transaction_type: str,
    ) -> Optional[Dict]:
        """
        Retrieve full credit party (account holder) information from Thunes.

        Args:
            payer_id: Thunes payer ID.
            credit_party_identifier: Dict of identifier fields.
            transaction_type: "B2B" or "B2C".

        Returns:
            Credit party info dict, or None on error.
        """
        response = self._http.get_credit_party_information(
            payer_id=payer_id,
            credit_party_identifier=credit_party_identifier,
            transaction_type=transaction_type,
        )
        if response:
            return response.get("data")
        return None

    def get_account_holder_name(
        self,
        payer_id: str,
        credit_party_identifier: Dict,
        transaction_type: str,
    ) -> Optional[str]:
        """
        Convenience method: return only the bank_account_holder_name.

        Args:
            payer_id: Thunes payer ID.
            credit_party_identifier: Dict of identifier fields.
            transaction_type: "B2B" or "B2C".

        Returns:
            Account holder name string, or None if not found.
        """
        info = self.get_information(payer_id, credit_party_identifier, transaction_type)
        if not info:
            return None

        nested = info
        if transaction_type == "B2B":
            entity_data = nested.get("receiving_business", {})
        else:
            entity_data = nested.get("beneficiary", {})

        return entity_data.get("bank_account_holder_name")
