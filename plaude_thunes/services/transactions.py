"""
Transaction-related service logic for plaude_thunes.

TransactionService covers the full Thunes transaction lifecycle:
    1. Fetch purpose-of-remittance choices
    2. Fetch document type choices
    3. Create a quotation
    4. Create the transaction
    5. Upload supporting documents
    6. Confirm the transaction

It also provides helper methods for extracting B2B/B2C transaction data
from a generic data dict (ported from remit/helpers.py).
"""

import logging
from typing import Dict, List, Optional, Tuple

from plaude_thunes.clients.thunes_client import ThunesHTTPClient
from plaude_thunes.utils.helpers import flatten_list, to_human_readable

logger = logging.getLogger(__name__)

#: Fallback purpose-of-remittance choices used when the API is unavailable.
FALLBACK_PURPOSE_CHOICES: List[Tuple[str, str]] = [
    ("", "Select purpose of payment"),
    ("FAMILY_SUPPORT", "Family Support"),
    ("EDUCATION", "Education"),
    ("MEDICAL_TREATMENT", "Medical Treatment"),
    ("BUSINESS_PAYMENT", "Business Payment"),
    ("OTHER", "Other"),
]


class TransactionService:
    """
    High-level service for Thunes transaction operations.

    Args:
        http_client: ThunesHTTPClient instance.

    Example::

        choices = client.transactions.get_purpose_of_remittance_choices()
        quotation = client.transactions.create_quotation(
            payer_id="123", transaction_type="B2B",
            amount="500.00", destination_currency="USD"
        )
    """

    def __init__(self, http_client: ThunesHTTPClient):
        self._http = http_client

    # ------------------------------------------------------------------
    # Reference data helpers
    # ------------------------------------------------------------------

    def get_purpose_of_remittance_choices(self) -> List[Tuple[str, str]]:
        """
        Fetch purpose-of-remittance values and return as (value, label) tuples.

        Falls back to a hardcoded list if the API is unavailable.

        Returns:
            List of (value, label) tuples suitable for Django form choices.
        """
        try:
            response = self._http.get_purpose_of_remittance()
            if response and response.get("status") == "success" and "data" in response:
                choices = [("", "Select purpose of payment")]
                for item in response["data"]:
                    purpose = item.get("purpose")
                    if purpose:
                        choices.append((purpose, purpose.replace("_", " ").title()))
                return choices

            logger.warning(
                "Thunes API returned unexpected structure for purpose of remittance"
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Error fetching purpose of remittance from Thunes: %s", exc)

        return FALLBACK_PURPOSE_CHOICES

    def get_document_type_choices(self) -> List[Tuple[str, str]]:
        """
        Fetch supported transaction document types and return as (value, label) tuples.

        Returns:
            List of (document_type, human_readable_label) tuples, or [] on error.
        """
        try:
            response = self._http.get_transaction_document_types()
            if response:
                return [
                    (doc_type, to_human_readable(doc_type))
                    for item in response.get("data", [])
                    if (doc_type := item.get("document_type"))
                ]
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("Error fetching document types from Thunes: %s", exc)

        return []

    # ------------------------------------------------------------------
    # Transaction lifecycle
    # ------------------------------------------------------------------

    def create_quotation(
        self,
        payer_id: str,
        transaction_type: str,
        amount: str,
        destination_currency: str,
    ) -> Optional[Dict]:
        """
        Create a Thunes transaction quotation (price lock).

        Args:
            payer_id: Thunes payer ID.
            transaction_type: "B2B" or "B2C".
            amount: Amount as string (e.g. "1000.00").
            destination_currency: 3-letter destination currency code.

        Returns:
            Quotation data dict, or None on failure.
        """
        response = self._http.create_transaction_quotation(
            payer_id=payer_id,
            transaction_type=transaction_type,
            amount=amount,
            destination_currency=destination_currency,
        )
        if response:
            return response.get("data")
        return None

    def create_transaction(self, data: Dict) -> Optional[Dict]:
        """
        Submit a fully built transaction to Thunes.

        Args:
            data: Transaction payload. Must include payer_id, quotation_id,
                  transaction_type, and beneficiary fields.

        Returns:
            Created transaction data dict, or None on failure.
        """
        response = self._http.create_transaction(data)
        if response:
            return response.get("data")
        return None

    def upload_document(
        self,
        transaction_id: str,
        document_type: str,
        file,
        file_name: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Upload a supporting document for a transaction.

        Args:
            transaction_id: Thunes transaction ID.
            document_type: Document type string (e.g. "INVOICE").
            file: File-like object.
            file_name: Optional filename override.

        Returns:
            Upload result dict, or None on failure.
        """
        response = self._http.upload_transaction_document(
            transaction_id=transaction_id,
            document_type=document_type,
            file=file,
            file_name=file_name,
        )
        if response:
            return response.get("data")
        return None

    def confirm_transaction(self, transaction_id: str) -> Optional[Dict]:
        """
        Confirm a Thunes transaction after all documents are uploaded.

        Args:
            transaction_id: Thunes transaction ID.

        Returns:
            Confirmation result dict, or None on failure.
        """
        response = self._http.confirm_transaction(transaction_id)
        if response:
            return response.get("data")
        return None

    # ------------------------------------------------------------------
    # Payload builders (ported from remit/helpers.py)
    # ------------------------------------------------------------------

    @staticmethod
    def build_b2b_credit_party_identifier(
        beneficiary_data: Dict,
        b2b_config: Dict,
    ) -> Dict:
        """
        Extract B2B credit party identifiers and receiving business fields
        from a beneficiary data dict, filtered by the payer's B2B requirements.

        This is the logic ported from ``remit.helpers.get_b2b_beneficiary_data()``.
        Framework-agnostic: works with any dict representation of a beneficiary.

        Args:
            beneficiary_data: Dict with beneficiary field values. Expected keys
                vary by payer but may include: business_name, country_iso3,
                tax_number, state_province_region, bank_account_number,
                swift_bic, account_type, etc.
            b2b_config: The B2B sub-dict from ThunesPayer.B2B (or equivalent),
                containing required_receiving_entity_fields and
                credit_party_identifiers_accepted.

        Returns:
            Dict with two keys:
                - "receiving_business": dict of required entity fields
                - "credit_party_identifier": dict of identifier fields
        """
        required_entity_fields = flatten_list(
            b2b_config.get("required_receiving_entity_fields", [])
        )
        accepted_cp_fields = flatten_list(
            b2b_config.get("credit_party_identifiers_accepted", [])
        )

        # Mapping: Thunes field name → beneficiary_data key (or None to use field name as-is)
        entity_field_map = {
            "registered_name": "business_name",
            "country_iso_code": "country_iso3",
            "tax_id": "tax_number",
            "province_state": "state_province_region",
            "representative_id_country_iso_code": "representative_id_country_iso3",
        }
        cp_field_map = {
            "swift_bic_code": "swift_bic",
            "account_type": None,  # present as-is, uppercased
        }

        receiving_business = {}
        for field in required_entity_fields:
            mapped_key = entity_field_map.get(field, field)
            value = beneficiary_data.get(mapped_key)
            if value:
                receiving_business[field] = value

        credit_party_identifier = {}
        for field in accepted_cp_fields:
            if field == "account_type":
                value = beneficiary_data.get("account_type")
                if value:
                    credit_party_identifier[field] = str(value).upper()
            else:
                mapped_key = cp_field_map.get(field, field)
                value = beneficiary_data.get(mapped_key or field)
                if value:
                    credit_party_identifier[field] = value

        return {
            "receiving_business": receiving_business,
            "credit_party_identifier": credit_party_identifier,
        }

    @staticmethod
    def build_b2c_payload(beneficiary_data: Dict) -> Dict:
        """
        Build the B2C beneficiary payload for a Thunes transaction.

        Ported from ``remit.helpers.get_b2c_beneficiary_data()``.

        Args:
            beneficiary_data: Dict with keys: business_name (or firstname/lastname),
                country_iso3, address, postal_code, city, state_province_region.

        Returns:
            Dict with a "beneficiary" key containing the Thunes B2C beneficiary payload.
        """
        return {
            "beneficiary": {
                "firstname": beneficiary_data.get("firstname")
                or beneficiary_data.get("business_name", ""),
                "lastname": beneficiary_data.get("lastname")
                or beneficiary_data.get("business_name", ""),
                "country_iso_code": beneficiary_data.get("country_iso3", ""),
                "address": beneficiary_data.get("address", ""),
                "postal_code": beneficiary_data.get("postal_code", ""),
                "city": beneficiary_data.get("city", ""),
                "province_state": beneficiary_data.get("state_province_region", ""),
            }
        }
