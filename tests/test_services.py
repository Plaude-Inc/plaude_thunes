"""
Tests for plaude_thunes services:
    - PayerService
    - TransactionService
    - CreditPartyService
"""

from unittest.mock import MagicMock

from plaude_thunes.services.credit_party import CreditPartyService
from plaude_thunes.services.payers import PayerService
from plaude_thunes.services.transactions import TransactionService

# ---------------------------------------------------------------------------
# PayerService
# ---------------------------------------------------------------------------


class TestPayerService:
    def _mock_http(self):
        return MagicMock()

    def test_get_by_country_and_currency_returns_data_list(self):
        http = self._mock_http()
        http.get_payers_by_country_and_currency.return_value = {
            "status": "success",
            "data": [{"id": 1, "name": "Test Bank"}],
        }
        svc = PayerService(http)
        result = svc.get_by_country_and_currency("NGA", "USD")
        assert result == [{"id": 1, "name": "Test Bank"}]
        http.get_payers_by_country_and_currency.assert_called_once_with("NGA", "USD")

    def test_get_by_country_returns_none_on_api_failure(self):
        http = self._mock_http()
        http.get_payers_by_country_and_currency.return_value = None
        svc = PayerService(http)
        assert svc.get_by_country_and_currency("NGA", "USD") is None

    def test_get_details_returns_data(self):
        http = self._mock_http()
        http.get_payer_details.return_value = {"data": {"id": "123", "name": "Payer X"}}
        svc = PayerService(http)
        result = svc.get_details("123")
        assert result == {"id": "123", "name": "Payer X"}

    def test_get_required_fields_beneficiary(self):
        payer_response = {
            "data": {
                "transaction_types": {
                    "B2B": {
                        "credit_party_identifiers_accepted": [
                            ["bank_account_number", "swift_bic_code"]
                        ],
                        "required_receiving_entity_fields": [
                            ["registered_name", "country_iso_code"]
                        ],
                    }
                }
            }
        }
        http = self._mock_http()
        http.get_payer_details.return_value = payer_response
        svc = PayerService(http)
        result = svc.get_required_fields("123", "B2B", "beneficiary")
        assert "credit_party_identifiers_accepted" in result
        assert "required_receiving_entity_fields" in result
        # Nested list should not be flattened
        assert "bank_account_number" in result["credit_party_identifiers_accepted"][0]
        assert "registered_name" in result["required_receiving_entity_fields"][0]

    def test_get_required_fields_transaction(self):
        payer_response = {
            "data": {
                "transaction_types": {
                    "B2C": {
                        "purpose_of_remittance_values_accepted": [
                            ["FAMILY_SUPPORT", "EDUCATION"]
                        ],
                        "required_documents": [["INVOICE"]],
                    }
                }
            }
        }
        http = self._mock_http()
        http.get_payer_details.return_value = payer_response
        svc = PayerService(http)
        result = svc.get_required_fields("456", "B2C", "transaction")
        assert "purpose_of_remittance_values_accepted" in result
        assert "required_documents" in result
        # Nested list should be not be flattened
        assert "FAMILY_SUPPORT" in result["purpose_of_remittance_values_accepted"][0]
        assert "INVOICE" in result["required_documents"][0]

    def test_get_required_fields_returns_empty_on_api_failure(self):
        http = self._mock_http()
        http.get_payer_details.return_value = None
        svc = PayerService(http)
        assert svc.get_required_fields("999", "B2B", "beneficiary") == {}


# ---------------------------------------------------------------------------
# TransactionService
# ---------------------------------------------------------------------------


class TestTransactionService:
    def _mock_http(self):
        return MagicMock()

    def test_get_purpose_of_remittance_choices_success(self):
        http = self._mock_http()
        http.get_purpose_of_remittance.return_value = {
            "status": "success",
            "data": [
                {"purpose": "FAMILY_SUPPORT"},
                {"purpose": "EDUCATION"},
            ],
        }
        svc = TransactionService(http)
        choices = svc.get_purpose_of_remittance_choices()
        values = [v for v, _ in choices]
        assert "FAMILY_SUPPORT" in values
        assert "EDUCATION" in values

    def test_get_purpose_choices_falls_back_on_error(self):
        http = self._mock_http()
        http.get_purpose_of_remittance.return_value = None
        svc = TransactionService(http)
        choices = svc.get_purpose_of_remittance_choices()
        # Should return fallback list
        assert len(choices) > 0
        assert any(v == "FAMILY_SUPPORT" for v, _ in choices)

    def test_get_document_type_choices_success(self):
        http = self._mock_http()
        http.get_transaction_document_types.return_value = {
            "data": [
                {"document_type": "INVOICE"},
                {"document_type": "PROOF_OF_ADDRESS"},
            ]
        }
        svc = TransactionService(http)
        choices = svc.get_document_type_choices()
        assert ("INVOICE", "Invoice") in choices
        assert ("PROOF_OF_ADDRESS", "Proof Of Address") in choices

    def test_create_quotation_returns_data(self):
        http = self._mock_http()
        http.create_transaction_quotation.return_value = {"data": {"id": "q-001"}}
        svc = TransactionService(http)
        result = svc.create_quotation("payer1", "B2B", "500.00", "USD")
        assert result == {"id": "q-001"}

    def test_confirm_transaction_returns_data(self):
        http = self._mock_http()
        http.confirm_transaction.return_value = {"data": {"status": "CONFIRMED"}}
        svc = TransactionService(http)
        result = svc.confirm_transaction("tx-001")
        assert result["status"] == "CONFIRMED"

    def test_build_b2b_credit_party_identifier(self):
        b2b_config = {
            "required_receiving_entity_fields": [
                ["registered_name", "country_iso_code"]
            ],
            "credit_party_identifiers_accepted": [
                ["bank_account_number", "swift_bic_code"]
            ],
        }
        beneficiary_data = {
            "business_name": "Acme Corp",
            "country_iso3": "NGA",
            "bank_account_number": "0123456789",
            "swift_bic": "TESTBICX",
        }
        result = TransactionService.build_b2b_credit_party_identifier(
            beneficiary_data, b2b_config
        )
        assert result["receiving_business"]["registered_name"] == "Acme Corp"
        assert result["receiving_business"]["country_iso_code"] == "NGA"
        assert result["credit_party_identifier"]["bank_account_number"] == "0123456789"
        assert result["credit_party_identifier"]["swift_bic_code"] == "TESTBICX"

    def test_build_b2c_payload(self):
        beneficiary_data = {
            "business_name": "John Doe",
            "country_iso3": "GBR",
            "address": "123 Main St",
            "postal_code": "SW1A 1AA",
            "city": "London",
            "state_province_region": "England",
        }
        result = TransactionService.build_b2c_payload(beneficiary_data)
        assert result["beneficiary"]["firstname"] == "John Doe"
        assert result["beneficiary"]["country_iso_code"] == "GBR"
        assert result["beneficiary"]["city"] == "London"


# ---------------------------------------------------------------------------
# CreditPartyService
# ---------------------------------------------------------------------------


class TestCreditPartyService:
    def _mock_http(self):
        return MagicMock()

    def test_validate_returns_data(self):
        http = self._mock_http()
        http.credit_party_validation.return_value = {
            "data": {"account_status": "AVAILABLE", "id": "cp-123"}
        }
        svc = CreditPartyService(http)
        result = svc.validate("p1", {"bank_account_number": "123"}, "B2B")
        assert result["account_status"] == "AVAILABLE"

    def test_validate_returns_none_on_failure(self):
        http = self._mock_http()
        http.credit_party_validation.return_value = None
        svc = CreditPartyService(http)
        assert svc.validate("p1", {}, "B2B") is None

    def test_get_account_holder_name_b2b(self):
        http = self._mock_http()
        http.get_credit_party_information.return_value = {
            "data": {"receiving_business": {"bank_account_holder_name": "Acme Ltd"}}
        }
        svc = CreditPartyService(http)
        name = svc.get_account_holder_name("p1", {"bank_account_number": "123"}, "B2B")
        assert name == "Acme Ltd"

    def test_get_account_holder_name_b2c(self):
        http = self._mock_http()
        http.get_credit_party_information.return_value = {
            "data": {"beneficiary": {"bank_account_holder_name": "Jane Doe"}}
        }
        svc = CreditPartyService(http)
        name = svc.get_account_holder_name("p1", {"msisdn": "+447911123456"}, "B2C")
        assert name == "Jane Doe"

    def test_get_account_holder_name_returns_none_on_failure(self):
        http = self._mock_http()
        http.get_credit_party_information.return_value = None
        svc = CreditPartyService(http)
        assert svc.get_account_holder_name("p1", {}, "B2C") is None
