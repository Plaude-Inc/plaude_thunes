"""
Tests for plaude_thunes.utils.helpers
"""

from plaude_thunes.utils.helpers import (
    IDENTIFIER_CONFIG,
    flatten_list,
    get_special_payer,
    title_case,
    to_human_readable,
)


class TestTitleCase:
    def test_snake_case_to_title(self):
        assert title_case("bank_account_number") == "Bank Account Number"

    def test_swift_bic_special_case(self):
        assert title_case("swift_bic") == "SWIFT/BIC"

    def test_single_word(self):
        assert title_case("email") == "Email"


class TestToHumanReadable:
    def test_screaming_snake_case(self):
        assert to_human_readable("PROOF_OF_ADDRESS") == "Proof Of Address"

    def test_single_word(self):
        assert to_human_readable("INVOICE") == "Invoice"


class TestFlattenList:
    def test_already_flat(self):
        assert flatten_list(["A", "B", "C"]) == ["A", "B", "C"]

    def test_singly_nested(self):
        assert flatten_list([["A", "B"], "C"]) == ["A", "B", "C"]

    def test_doubly_nested(self):
        result = flatten_list([["A", ["B", "C"]], "D"])
        assert result == ["A", "B", "C", "D"]

    def test_deduplication(self):
        result = flatten_list([["A", "B"], ["A", "C"]])
        assert result.count("A") == 1
        assert "B" in result
        assert "C" in result

    def test_empty_list(self):
        assert flatten_list([]) == []


class TestSpecialPayers:
    def test_china_usd(self):
        payer = get_special_payer("CHN", "USD")
        assert payer is not None
        assert payer["id"] == 6248

    def test_india_usd(self):
        payer = get_special_payer("IND", "USD")
        assert payer is not None
        assert payer["id"] == 6484

    def test_case_insensitive(self):
        assert get_special_payer("chn", "usd") == get_special_payer("CHN", "USD")

    def test_unknown_returns_none(self):
        assert get_special_payer("ZZZ", "EUR") is None


class TestIdentifierConfig:
    def test_contains_expected_keys(self):
        assert "bank_account_number" in IDENTIFIER_CONFIG
        assert "swift_bic" in IDENTIFIER_CONFIG
        assert "msisdn" in IDENTIFIER_CONFIG
        assert "iban" in IDENTIFIER_CONFIG
