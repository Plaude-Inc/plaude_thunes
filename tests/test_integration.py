"""
Tests for ThunesPayerService in plaude_thunes/services/integration.py.

ThunesPayerService takes a ThunesHTTPClient and calls:
    - http_client.get_payer_details(payer_id)
    - http_client.get_credit_party_information(payer_id, credit_party_identifier, transaction_type)
directly on the raw HTTP client.
"""

from unittest.mock import MagicMock

from plaude_thunes.services.integration import ThunesPayerService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_http():
    """Return a MagicMock standing in for ThunesHTTPClient."""
    return MagicMock()


def _payer_response(name="Test Bank", b2b=None, b2c=None):
    return {
        "data": {
            "name": name,
            "transaction_types": {
                "B2B": b2b
                or {"credit_party_identifiers_accepted": [["bank_account_number"]]},
                "B2C": b2c or {},
            },
        }
    }


def _cpi_response(transaction_type, holder_name="Acme Ltd"):
    if transaction_type == "B2B":
        return {
            "data": {"receiving_business": {"bank_account_holder_name": holder_name}}
        }
    return {"data": {"beneficiary": {"bank_account_holder_name": holder_name}}}


def _identifier():
    return {"bank_account_number": "0123456789", "swift_bic_code": "TESTBICX"}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestThunesPayerServiceSuccess:
    def test_b2b_returns_true_with_result(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = _cpi_response(
            "B2B", "Acme Ltd"
        )

        ok, result = ThunesPayerService(http).process_account(
            transaction_type="B2B",
            payer_id="1234",
            country="NGA",
            currency="USD",
            credit_party_identifier=_identifier(),
        )

        assert ok is True
        assert result["bank_name"] == "Test Bank"
        assert result["account_holder_name"] == "Acme Ltd"

    def test_b2c_returns_true_with_result(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = _cpi_response(
            "B2C", "Jane Doe"
        )

        ok, result = ThunesPayerService(http).process_account(
            transaction_type="B2C",
            payer_id="5678",
            country="GBR",
            currency="GBP",
            credit_party_identifier={"msisdn": "+447911123456"},
        )

        assert ok is True
        assert result["account_holder_name"] == "Jane Doe"

    def test_result_echoes_all_input_fields(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = _cpi_response("B2B")
        identifier = _identifier()

        _, result = ThunesPayerService(http).process_account(
            transaction_type="B2B",
            payer_id="1234",
            country="NGA",
            currency="USD",
            credit_party_identifier=identifier,
        )

        assert result["payer_id"] == "1234"
        assert result["country"] == "NGA"
        assert result["currency"] == "USD"
        assert result["credit_party_identifier"] == identifier

    def test_b2b_and_b2c_objects_extracted_from_payer(self):
        http = _make_http()
        b2b_cfg = {"credit_party_identifiers_accepted": [["bank_account_number"]]}
        b2c_cfg = {"required_fields": ["msisdn"]}
        http.get_payer_details.return_value = _payer_response(b2b=b2b_cfg, b2c=b2c_cfg)
        http.get_credit_party_information.return_value = _cpi_response("B2B")

        _, result = ThunesPayerService(http).process_account(
            "B2B", "1234", "NGA", "USD", _identifier()
        )

        assert result["b2b"] == b2b_cfg
        assert result["b2c"] == b2c_cfg


# ---------------------------------------------------------------------------
# Invalid transaction type
# ---------------------------------------------------------------------------


class TestThunesPayerServiceTransactionType:
    def test_returns_false_for_invalid_transaction_type(self):
        http = _make_http()

        ok, result = ThunesPayerService(http).process_account(
            "WIRE", "1234", "NGA", "USD", _identifier()
        )

        assert ok is False
        assert result == "Invalid transaction type"
        http.get_payer_details.assert_not_called()

    def test_lowercase_transaction_type_is_accepted(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = _cpi_response("B2B")

        ok, _ = ThunesPayerService(http).process_account(
            "b2b", "1234", "NGA", "USD", _identifier()
        )

        assert ok is True


# ---------------------------------------------------------------------------
# Payer not found
# ---------------------------------------------------------------------------


class TestThunesPayerServicePayerNotFound:
    def test_returns_false_when_payer_response_is_none(self):
        http = _make_http()
        http.get_payer_details.return_value = None

        ok, result = ThunesPayerService(http).process_account(
            "B2B", "999", "NGA", "USD", _identifier()
        )

        assert ok is False
        assert result == "Payer not found"

    def test_returns_false_when_payer_response_has_no_data_key(self):
        http = _make_http()
        http.get_payer_details.return_value = {}  # missing "data"

        ok, result = ThunesPayerService(http).process_account(
            "B2B", "999", "NGA", "USD", _identifier()
        )

        assert ok is False
        assert result == "Payer not found"

    def test_cpi_not_called_when_payer_not_found(self):
        http = _make_http()
        http.get_payer_details.return_value = None

        ThunesPayerService(http).process_account(
            "B2B", "999", "NGA", "USD", _identifier()
        )

        http.get_credit_party_information.assert_not_called()


# ---------------------------------------------------------------------------
# CPI unavailable (now fatal)
# ---------------------------------------------------------------------------


class TestThunesPayerServiceCPIUnavailable:
    def test_account_holder_name_is_none_when_cpi_data_is_empty(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = {"data": {}}

        ok, result = ThunesPayerService(http).process_account(
            "B2B", "1234", "NGA", "USD", _identifier()
        )

        assert ok is True
        assert result["account_holder_name"] is None


# ---------------------------------------------------------------------------
# Correct entity key per transaction type
# ---------------------------------------------------------------------------


class TestThunesPayerServiceEntityKey:
    def test_b2b_reads_receiving_business(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = {
            "data": {
                "receiving_business": {"bank_account_holder_name": "Corp A"},
                "beneficiary": {"bank_account_holder_name": "Should Not Be Used"},
            }
        }

        _, result = ThunesPayerService(http).process_account(
            "B2B", "1234", "NGA", "USD", _identifier()
        )

        assert result["account_holder_name"] == "Corp A"

    def test_b2c_reads_beneficiary(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = {
            "data": {
                "receiving_business": {
                    "bank_account_holder_name": "Should Not Be Used"
                },
                "beneficiary": {"bank_account_holder_name": "Jane Doe"},
            }
        }

        _, result = ThunesPayerService(http).process_account(
            "B2C", "5678", "GBR", "GBP", {"msisdn": "+44123"}
        )

        assert result["account_holder_name"] == "Jane Doe"


# ---------------------------------------------------------------------------
# Correct HTTP calls made
# ---------------------------------------------------------------------------


class TestThunesPayerServiceHTTPCalls:
    def test_calls_get_payer_details_with_payer_id(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = _cpi_response("B2B")

        ThunesPayerService(http).process_account(
            "B2B", "p-42", "NGA", "USD", _identifier()
        )

        http.get_payer_details.assert_called_once_with("p-42")

    def test_calls_get_credit_party_information_with_correct_args(self):
        http = _make_http()
        http.get_payer_details.return_value = _payer_response()
        http.get_credit_party_information.return_value = _cpi_response("B2C")
        identifier = {"msisdn": "+447911123456"}

        ThunesPayerService(http).process_account(
            "B2C", "p-42", "GBR", "GBP", identifier
        )

        http.get_credit_party_information.assert_called_once_with(
            payer_id="p-42",
            credit_party_identifier=identifier,
            transaction_type="B2C",
        )
