"""
Shared utility functions and constants for plaude_thunes.

These helpers are framework-agnostic and carry no Django/DRF dependencies.
"""

from typing import Any, Dict, List, Tuple, Union


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def title_case(key: str) -> str:
    """
    Convert a snake_case field name to a human-readable title.

    Special-cases SWIFT/BIC.

    Args:
        key: A snake_case string (e.g. "bank_account_number").

    Returns:
        Human-readable string (e.g. "Bank Account Number").

    Example::

        title_case("swift_bic")          # → "SWIFT/BIC"
        title_case("bank_account_number") # → "Bank Account Number"
    """
    if key == "swift_bic":
        return "SWIFT/BIC"
    return key.replace("_", " ").title()


def to_human_readable(value: str) -> str:
    """
    Convert a SCREAMING_SNAKE_CASE document type to a readable label.

    Args:
        value: e.g. "PROOF_OF_ADDRESS"

    Returns:
        e.g. "Proof Of Address"
    """
    return value.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Data structure helpers
# ---------------------------------------------------------------------------

def flatten_list(nested: List) -> List:
    """
    Flatten a potentially nested list, removing duplicates while preserving order.

    Thunes API responses sometimes return doubly-nested lists for
    required_documents and credit_party_identifiers_accepted.

    Args:
        nested: A list that may contain sublists.

    Returns:
        Flat deduplicated list.

    Example::

        flatten_list([["A", "B"], "C", ["A", "D"]]) → ["A", "B", "C", "D"]
    """
    flat: List = []
    for item in nested:
        if isinstance(item, list):
            for sub in flatten_list(item):
                if sub not in flat:
                    flat.append(sub)
        else:
            if item not in flat:
                flat.append(item)
    return flat


# ---------------------------------------------------------------------------
# Thunes domain constants
# ---------------------------------------------------------------------------

#: Human-readable labels for Thunes credit party identifier fields.
#: Used when rendering beneficiary forms and receipts.
IDENTIFIER_CONFIG: Dict[str, str] = {
    "msisdn": "Mobile Number",
    "bank_account_number": "Bank Account Number",
    "iban": "IBAN",
    "sort_code": "Sort Code",
    "aba_routing_number": "ABA Routing Number",
    "routing_code": "Routing Code",
    "account_number": "Account Number",
    "account_type": "Account Type",
    "email": "Email",
    "swift_bic": "SWIFT/BIC",
    "clabe": "CLABE",
    "cbu": "CBU",
    "cbu_alias": "CBU Alias",
    "bik_code": "BIK Code",
    "ifs_code": "IFS Code",
    "bsb_number": "BSB Number",
    "branch_number": "Branch Number",
    "entity_tt_id": "Entity TT ID",
    "card_number": "Card Number",
    "qr_code": "QR Code",
}

#: Hardcoded payer overrides for countries/currencies that require a specific Thunes payer.
#: Key: (country_iso3, currency_code), Value: {"id": ..., "name": ...}
SPECIAL_PAYERS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("CHN", "USD"): {
        "id": 6248,
        "name": "All Banks China USD (via SWIFT Wire Transfer)",
    },
    ("IND", "USD"): {
        "id": 6484,
        "name": "All Banks India USD (via SWIFT Wire Transfer)",
    },
    ("HKG", "USD"): {
        "id": 6241,
        "name": "All Banks Hong Kong USD (via SWIFT Wire Transfer)",
    },
}


def get_special_payer(country_iso3: str, currency: str) -> Union[Dict, None]:
    """
    Look up a special payer override for a country/currency combination.

    Args:
        country_iso3: 3-letter ISO country code (e.g. "CHN").
        currency: 3-letter currency code (e.g. "USD").

    Returns:
        Dict with "id" and "name" keys, or None if no override exists.
    """
    return SPECIAL_PAYERS.get((country_iso3.upper(), currency.upper()))
