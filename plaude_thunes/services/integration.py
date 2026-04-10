"""
High-level integration service for plaude_thunes.

ThunesPayerService orchestrates payer lookup and credit party information
retrieval to validate a beneficiary account and return all data needed to
create a downstream Beneficiary record.

The downstream app supplies a ThunesHTTPClient — typically obtained from a
configured ThunesClient instance::

    from plaude_thunes import ThunesClient, ThunesPayerService

    client = ThunesClient(api_key="...", api_base_url="...")
    service = ThunesPayerService(http_client=client.http)
    ok, result = service.process_account(
        transaction_type="B2B",
        payer_id="1234",
        country="NGA",
        currency="USD",
        credit_party_identifier={"bank_account_number": "0123456789"},
    )
"""

import logging
from typing import Any, Dict

from plaude_thunes.clients.thunes_client import ThunesHTTPClient

logger = logging.getLogger(__name__)


class ThunesPayerService:
    """
    Orchestrates payer lookup and credit party information retrieval using
    the existing PayerService and CreditPartyService.

    Args:
        http_client: A ``ThunesHTTPClient`` instance. Obtained from a configured
                     ``ThunesClient`` via ``client.http``.

    Returns from ``process_account``:
        ``(True, result_dict)`` on success, ``(False, error_message)`` on failure.

    Result dict keys:
        - ``bank_name``               - Payer/bank name from Thunes
        - ``account_holder_name``     - Name on the account (or None if unavailable)
        - ``b2b``                     - B2B transaction-type config from the payer
        - ``b2c``                     - B2C transaction-type config from the payer
        - ``payer_id``                - Echo of the input payer_id
        - ``country``                 - Echo of the input country
        - ``currency``                - Echo of the input currency
        - ``credit_party_identifier`` - Echo of the input identifier dict
    """

    def __init__(self, http_client: ThunesHTTPClient):
        self._client = http_client

    def process_account(
        self,
        transaction_type: str,
        payer_id: str,
        country: str,
        currency: str,
        credit_party_identifier: Dict[str, Any],
    ) -> Dict[str, Any]:

        transaction_type = transaction_type.upper()
        if transaction_type not in {"B2B", "B2C"}:
            return False, "Invalid transaction type"

        payer_response = self._client.get_payer_details(payer_id)

        if not payer_response or "data" not in payer_response:
            logger.warning("Payer '%s' not found", payer_id)
            return False, "Payer not found"

        payer_data = payer_response["data"]
        bank_name = payer_data.get("name")

        payer_transaction_types = payer_data.get("transaction_types", {})
        b2b_object = payer_transaction_types.get("B2B")
        b2c_object = payer_transaction_types.get("B2C")

        bank_account_holder_name = None

        cpi_response = self._client.get_credit_party_information(
            payer_id=payer_id,
            credit_party_identifier=credit_party_identifier,
            transaction_type=transaction_type,
        )

        if cpi_response and "data" in cpi_response:
            cpi_data = cpi_response["data"]

            entity_data = (
                cpi_data.get("receiving_business", {})
                if transaction_type == "B2B"
                else cpi_data.get("beneficiary", {})
            )

            bank_account_holder_name = entity_data.get("bank_account_holder_name")
        else:
            logger.warning("Credit party info lookup failed for %s", payer_id)
            return False, "Credit party information not found"

        return True, {
            "bank_name": bank_name,
            "account_holder_name": bank_account_holder_name,
            "b2b": b2b_object,
            "b2c": b2c_object,
            "payer_id": payer_id,
            "country": country,
            "currency": currency,
            "credit_party_identifier": credit_party_identifier,
        }
