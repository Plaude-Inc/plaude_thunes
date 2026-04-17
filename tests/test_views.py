"""
Tests for plaude_thunes DRF views:
    - GetPayersView
    - GetPayerDetailsView
    - GetPayerRequiredFieldsView
    - GetRepDocumentIdTypesView
    - GetPurposeOfRemittanceView
    - GetDocumentTypesView
    - CreditPartyValidationView
    - CreditPartyInformationView
"""

import json
from unittest.mock import MagicMock

from rest_framework.test import APIRequestFactory

from plaude_thunes.api.views.payers import (
    GetPayerDetailsView,
    GetPayerRequiredFieldsView,
    GetPayersView,
    GetRepDocumentIdTypesView,
)
from plaude_thunes.api.views.transactions import (
    CreditPartyInformationView,
    CreditPartyValidationView,
    GetDocumentTypesView,
    GetPurposeOfRemittanceView,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**attrs):
    """Return a MagicMock ThunesClient with sub-service mocks pre-attached."""
    client = MagicMock()
    client.payers = MagicMock()
    client.transactions = MagicMock()
    client.credit_party = MagicMock()
    for k, v in attrs.items():
        setattr(client, k, v)
    return client


def _view_with_client(view_class, mock_client):
    """Return a concrete view subclass that injects *mock_client*."""

    class ConcreteView(view_class):
        thunes_client = mock_client

    return ConcreteView.as_view()


factory = APIRequestFactory()


# ---------------------------------------------------------------------------
# GetPayersView
# ---------------------------------------------------------------------------


class TestGetPayersView:
    def test_returns_200_with_payers(self):
        client = _make_client()
        client.payers.get_by_country_and_currency.return_value = [
            {"id": 1, "name": "Test Bank"}
        ]

        request = factory.get("/thunes/payers/NGA/USD/")
        response = _view_with_client(GetPayersView, client)(
            request, country="NGA", currency="USD"
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "success"
        assert body["data"] == [{"id": 1, "name": "Test Bank"}]
        client.payers.get_by_country_and_currency.assert_called_once_with("NGA", "USD")

    def test_returns_502_when_client_returns_none(self):
        client = _make_client()
        client.payers.get_by_country_and_currency.return_value = None

        request = factory.get("/thunes/payers/NGA/USD/")
        response = _view_with_client(GetPayersView, client)(
            request, country="NGA", currency="USD"
        )

        assert response.status_code == 502
        body = json.loads(response.content)
        assert body["status"] == "error"

    def test_special_payer_returned_without_api_call(self):
        # CHN/USD has a known special payer override — the API must not be called
        client = _make_client()

        request = factory.get("/thunes/payers/CHN/USD/")
        response = _view_with_client(GetPayersView, client)(
            request, country="CHN", currency="USD"
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["data"] == [
            {"id": 6248, "name": "All Banks China USD (via SWIFT Wire Transfer)"}
        ]
        client.payers.get_by_country_and_currency.assert_not_called()

    def test_no_special_payer_for_unknown_country_calls_api(self):
        client = _make_client()
        client.payers.get_by_country_and_currency.return_value = [
            {"id": 99, "name": "Regular Bank"}
        ]

        request = factory.get("/thunes/payers/NGA/USD/")
        response = _view_with_client(GetPayersView, client)(
            request, country="NGA", currency="USD"
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == 99
        client.payers.get_by_country_and_currency.assert_called_once_with("NGA", "USD")


# ---------------------------------------------------------------------------
# GetPayerDetailsView
# ---------------------------------------------------------------------------


class TestGetPayerDetailsView:
    def test_returns_200_with_payer_data(self):
        payer = {"id": "123", "name": "Payer X"}
        client = _make_client()
        client.payers.get_details.return_value = payer

        request = factory.get("/thunes/payers/123/")
        response = _view_with_client(GetPayerDetailsView, client)(
            request, payer_id="123"
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "success"
        assert body["data"] == payer
        client.payers.get_details.assert_called_once_with("123")

    def test_returns_404_when_payer_not_found(self):
        client = _make_client()
        client.payers.get_details.return_value = None

        request = factory.get("/thunes/payers/999/")
        response = _view_with_client(GetPayerDetailsView, client)(
            request, payer_id="999"
        )

        assert response.status_code == 404
        body = json.loads(response.content)
        assert body["status"] == "error"
        assert "999" in body["message"]


# ---------------------------------------------------------------------------
# GetPayerRequiredFieldsView
# ---------------------------------------------------------------------------


class TestGetPayerRequiredFieldsView:
    def test_returns_200_with_required_fields(self):
        fields = {"credit_party_identifiers_accepted": [["bank_account_number"]]}
        client = _make_client()
        client.payers.get_required_fields.return_value = fields

        request = factory.get("/thunes/payers/123/B2B/beneficiary/required-fields")
        response = _view_with_client(GetPayerRequiredFieldsView, client)(
            request, payer_id="123", transaction_type="B2B", data_type="beneficiary"
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "success"
        assert body["data"] == fields
        client.payers.get_required_fields.assert_called_once_with(
            payer_id="123", transaction_type="B2B", data_type="beneficiary"
        )

    def test_returns_400_for_invalid_data_type(self):
        client = _make_client()

        request = factory.get("/thunes/payers/123/B2B/invalid/required-fields")
        response = _view_with_client(GetPayerRequiredFieldsView, client)(
            request, payer_id="123", transaction_type="B2B", data_type="invalid"
        )

        assert response.status_code == 400
        body = json.loads(response.content)
        assert body["status"] == "error"
        client.payers.get_required_fields.assert_not_called()

    def test_returns_404_when_no_required_fields(self):
        client = _make_client()
        client.payers.get_required_fields.return_value = {}

        request = factory.get("/thunes/payers/123/B2C/transaction/required-fields")
        response = _view_with_client(GetPayerRequiredFieldsView, client)(
            request, payer_id="123", transaction_type="B2C", data_type="transaction"
        )

        assert response.status_code == 404
        body = json.loads(response.content)
        assert body["status"] == "error"

    def test_accepts_transaction_data_type(self):
        fields = {"purpose_of_remittance_values_accepted": [["FAMILY_SUPPORT"]]}
        client = _make_client()
        client.payers.get_required_fields.return_value = fields

        request = factory.get("/thunes/payers/456/B2C/transaction/required-fields")
        response = _view_with_client(GetPayerRequiredFieldsView, client)(
            request, payer_id="456", transaction_type="B2C", data_type="transaction"
        )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GetRepDocumentIdTypesView
# ---------------------------------------------------------------------------


class TestGetRepDocumentIdTypesView:
    def test_returns_200_with_empty_list_when_no_model(self):
        """Falls back to [] when remit.models is not importable."""
        client = _make_client()

        request = factory.get("/thunes/utils/rep-document-id-types/")
        response = _view_with_client(GetRepDocumentIdTypesView, client)(request)

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "success"
        assert isinstance(body["data"], list)
        id_types = body["data"]
        assert all("name" in id_type and "value" in id_type for id_type in id_types)


# ---------------------------------------------------------------------------
# GetPurposeOfRemittanceView
# ---------------------------------------------------------------------------


class TestGetPurposeOfRemittanceView:
    def test_returns_200_with_choices(self):
        client = _make_client()
        client.transactions.get_purpose_of_remittance_choices.return_value = [
            ("FAMILY_SUPPORT", "Family Support"),
            ("EDUCATION", "Education"),
        ]

        request = factory.get("/thunes/purpose-of-remittance/")
        response = _view_with_client(GetPurposeOfRemittanceView, client)(request)

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "success"
        purposes = [item["purpose"] for item in body["data"]]
        assert "FAMILY_SUPPORT" in purposes
        assert "EDUCATION" in purposes

    def test_filters_out_empty_purpose_values(self):
        client = _make_client()
        client.transactions.get_purpose_of_remittance_choices.return_value = [
            ("FAMILY_SUPPORT", "Family Support"),
            ("", "Empty"),
        ]

        request = factory.get("/thunes/purpose-of-remittance/")
        response = _view_with_client(GetPurposeOfRemittanceView, client)(request)

        body = json.loads(response.content)
        purposes = [item["purpose"] for item in body["data"]]
        assert "" not in purposes
        assert "FAMILY_SUPPORT" in purposes


# ---------------------------------------------------------------------------
# GetDocumentTypesView
# ---------------------------------------------------------------------------


class TestGetDocumentTypesView:
    def test_returns_200_with_document_types(self):
        client = _make_client()
        client.transactions.get_document_types.return_value = [
            {"value": "INVOICE", "label": "Invoice"},
            {"value": "PROOF_OF_ADDRESS", "label": "Proof Of Address"},
        ]

        request = factory.get("/thunes/document-types/")
        response = _view_with_client(GetDocumentTypesView, client)(request)

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "success"
        values = [item["value"] for item in body["data"]]
        assert "INVOICE" in values
        assert "PROOF_OF_ADDRESS" in values

    def test_response_includes_label(self):
        client = _make_client()
        client.transactions.get_document_types.return_value = [
            {"value": "INVOICE", "label": "Invoice"},
        ]

        request = factory.get("/thunes/document-types/")
        response = _view_with_client(GetDocumentTypesView, client)(request)

        body = json.loads(response.content)
        assert body["data"][0]["label"] == "Invoice"


# ---------------------------------------------------------------------------
# CreditPartyValidationView
# ---------------------------------------------------------------------------


class TestCreditPartyValidationView:
    def _post(self, data, client):
        request = factory.post(
            "/thunes/credit-party/validate/",
            data=data,
            format="json",
        )
        return _view_with_client(CreditPartyValidationView, client)(request)

    def test_returns_200_on_valid_request(self):
        client = _make_client()
        client.credit_party.validate.return_value = {
            "account_status": "AVAILABLE",
            "id": "cp-001",
        }

        response = self._post(
            {
                "payer_id": "p1",
                "transaction_type": "B2B",
                "credit_party_identifier": {"bank_account_number": "123456"},
            },
            client,
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "success"
        assert body["data"]["account_status"] == "AVAILABLE"

    def test_returns_400_on_invalid_serializer(self):
        client = _make_client()

        response = self._post(
            {
                # missing required fields
                "transaction_type": "B2B",
            },
            client,
        )

        assert response.status_code == 400
        body = json.loads(response.content)
        assert body["status"] == "error"
        client.credit_party.validate.assert_not_called()

    def test_returns_400_when_credit_party_identifier_is_empty(self):
        client = _make_client()

        response = self._post(
            {
                "payer_id": "p1",
                "transaction_type": "B2B",
                "credit_party_identifier": {},
            },
            client,
        )

        assert response.status_code == 400

    def test_returns_unavailable_when_client_returns_none(self):
        client = _make_client()
        client.credit_party.validate.return_value = None

        response = self._post(
            {
                "payer_id": "p1",
                "transaction_type": "B2C",
                "credit_party_identifier": {"msisdn": "+447911123456"},
            },
            client,
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["data"]["account_status"] == "UNAVAILABLE"
        assert body["data"]["id"] is None


# ---------------------------------------------------------------------------
# CreditPartyInformationView
# ---------------------------------------------------------------------------


class TestCreditPartyInformationView:
    def _post(self, data, client):
        request = factory.post(
            "/thunes/credit-party/information/",
            data=data,
            format="json",
        )
        return _view_with_client(CreditPartyInformationView, client)(request)

    def test_returns_200_with_information(self):
        client = _make_client()
        client.credit_party.get_information.return_value = {
            "beneficiary": {"bank_account_holder_name": "Jane Doe"}
        }

        response = self._post(
            {
                "payer_id": "p1",
                "transaction_type": "B2C",
                "credit_party_identifier": {"msisdn": "+447911123456"},
            },
            client,
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["status"] == "success"
        assert body["data"]["beneficiary"]["bank_account_holder_name"] == "Jane Doe"

    def test_returns_400_on_invalid_serializer(self):
        client = _make_client()

        response = self._post(
            {
                # transaction_type missing
                "payer_id": "p1",
                "credit_party_identifier": {"bank_account_number": "123456"},
            },
            client,
        )

        assert response.status_code == 400
        client.credit_party.get_information.assert_not_called()

    def test_returns_empty_dict_when_client_returns_none(self):
        client = _make_client()
        client.credit_party.get_information.return_value = None

        response = self._post(
            {
                "payer_id": "p1",
                "transaction_type": "B2B",
                "credit_party_identifier": {"bank_account_number": "123456"},
            },
            client,
        )

        assert response.status_code == 200
        body = json.loads(response.content)
        assert body["data"] == {}
