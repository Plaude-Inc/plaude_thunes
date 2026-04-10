"""
Low-level HTTP client for the Thunes gateway.

ThunesHTTPClient is a thin, framework-agnostic wrapper around `requests`.
It handles authentication headers, response parsing, and error mapping.
All higher-level logic (services, views) delegates HTTP work here.

Extension points:
    - Subclass and override `_build_headers()` to change auth strategy.
    - Subclass and override `_handle_response()` to change error mapping.
    - Provide middleware hooks (request_hook, response_hook) for logging/retries.
"""

import logging
from typing import Any, Callable, Dict, Optional

import requests

from plaude_thunes.config import ThunesConfig
from plaude_thunes.exceptions import (
    ThunesAPIError,
    ThunesAuthenticationError,
    ThunesNotFoundError,
    ThunesValidationError,
)

logger = logging.getLogger(__name__)


class ThunesHTTPClient:
    """
    Low-level HTTP client that communicates with the Thunes gateway.

    All public methods return parsed JSON dicts on success, or raise
    a ThunesAPIError subclass on failure.

    Args:
        config: ThunesConfig instance holding credentials and base URL.
        request_hook: Optional callable invoked before each request.
                      Signature: (method, url, kwargs) -> None
        response_hook: Optional callable invoked after each response.
                       Signature: (response) -> None
        session: Optional pre-configured requests.Session (useful for testing).
    """

    def __init__(
        self,
        config: ThunesConfig,
        request_hook: Optional[Callable] = None,
        response_hook: Optional[Callable] = None,
        session: Optional[requests.Session] = None,
    ):
        self.config = config
        self._request_hook = request_hook
        self._response_hook = response_hook
        self._session = session or requests.Session()

    # ------------------------------------------------------------------
    # Header / auth construction
    # ------------------------------------------------------------------

    def _build_headers(self, include_content_type: bool = True) -> Dict[str, str]:
        """Build default JSON request headers. Override for custom auth."""
        headers = {"Authorization": f"Api-Key {self.config.api_key}"}
        if include_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    # ------------------------------------------------------------------
    # Core request dispatch
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        extra_headers: Optional[Dict] = None,
        timeout: Optional[int] = None,
    ) -> Dict:
        """
        Execute an HTTP request against the Thunes API.

        Args:
            method: HTTP verb ("GET", "POST", etc.)
            path: URL path relative to api_base_url (e.g. "/payers/NGA/USD")
            json: JSON-serializable body for JSON requests.
            data: Form-encoded body (used for multipart uploads).
            files: File payload for multipart requests.
            extra_headers: Headers to merge with defaults.
            timeout: Per-request timeout override.

        Returns:
            Parsed JSON dict from the response body.

        Raises:
            ThunesAuthenticationError: On 401/403.
            ThunesValidationError: On 400.
            ThunesNotFoundError: On 404.
            ThunesAPIError: On any other non-2xx status.
        """
        url = f"{self.config.api_base_url.rstrip('/')}{path}"
        use_content_type = files is None  # multipart sets its own content-type
        headers = self._build_headers(include_content_type=use_content_type)
        if extra_headers:
            headers.update(extra_headers)

        request_kwargs: Dict[str, Any] = {
            "headers": headers,
            "timeout": timeout or self.config.timeout,
        }
        if json is not None:
            request_kwargs["json"] = json
        if data is not None:
            request_kwargs["data"] = data
        if files is not None:
            request_kwargs["files"] = files

        if self._request_hook:
            try:
                self._request_hook(method, url, request_kwargs)
            except Exception:
                logger.debug("request_hook raised an exception", exc_info=True)

        try:
            response = self._session.request(method, url, **request_kwargs)
        except requests.RequestException as exc:
            logger.error("Thunes HTTP request error: %s", exc)
            raise ThunesAPIError(f"Network error: {exc}") from exc

        if self._response_hook:
            try:
                self._response_hook(response)
            except Exception:
                logger.debug("response_hook raised an exception", exc_info=True)

        return self._handle_response(response)

    def _handle_response(self, response: requests.Response) -> Dict:
        """
        Parse response and map error codes to exceptions.

        Override this method to customise error mapping behaviour.
        """
        if response.status_code in (200, 201):
            return response.json()

        try:
            body = response.json()
        except Exception:
            body = response.text

        message = (
            body.get("detail", body.get("message", "Request failed"))
            if isinstance(body, dict)
            else str(body)
        )
        logger.error("Thunes API error %s: %s", response.status_code, message)

        if response.status_code in (401, 403):
            raise ThunesAuthenticationError(
                message, status_code=response.status_code, response_body=body
            )
        if response.status_code == 400:
            raise ThunesValidationError(message, status_code=400, response_body=body)
        if response.status_code == 404:
            raise ThunesNotFoundError(message, response_body=body)

        raise ThunesAPIError(
            message, status_code=response.status_code, response_body=body
        )

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def get(self, path: str, **kwargs) -> Dict:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Dict:
        return self._request("POST", path, **kwargs)

    # ------------------------------------------------------------------
    # Thunes-domain API calls
    # ------------------------------------------------------------------

    def get_purpose_of_remittance(self) -> Optional[Dict]:
        """Fetch purpose-of-remittance values from the Thunes API."""
        try:
            return self.get("/purpose-of-remittance")
        except ThunesAPIError as exc:
            logger.error("Failed to fetch purpose of remittance: %s", exc)
            return None

    def get_transaction_document_types(self) -> Optional[Dict]:
        """Fetch supported transaction document types."""
        try:
            return self.get("/transaction-document-types")
        except ThunesAPIError as exc:
            logger.error("Failed to fetch transaction document types: %s", exc)
            return None

    def get_payers_by_country_and_currency(
        self, country: str, currency: str
    ) -> Optional[Dict]:
        """
        Fetch payers available for a given country and currency.

        Args:
            country: 3-letter ISO country code (e.g. "NGA").
            currency: 3-letter currency code (e.g. "USD").
        """
        try:
            return self.get(f"/payers/{country}/{currency}")
        except ThunesAPIError as exc:
            logger.error("Failed to fetch payers for %s/%s: %s", country, currency, exc)
            return None

    def get_payer_details(self, payer_id: str) -> Optional[Dict]:
        """
        Fetch detailed info for a specific payer.

        Args:
            payer_id: Numeric or string Thunes payer ID.
        """
        try:
            return self.get(f"/payer/{payer_id}")
        except ThunesAPIError as exc:
            logger.error("Failed to fetch payer details for %s: %s", payer_id, exc)
            return None

    def credit_party_validation(
        self,
        payer_id: str,
        credit_party_identifier: Dict,
        transaction_type: str,
    ) -> Optional[Dict]:
        """
        Validate a credit party (beneficiary account) with Thunes.

        Args:
            payer_id: Thunes payer ID.
            credit_party_identifier: Dict of identifier fields (e.g. bank_account_number).
            transaction_type: "B2B" or "B2C".
        """
        try:
            return self.post(
                "/payers/credit-party-validation",
                json={
                    "payer_id": payer_id,
                    "transaction_type": transaction_type,
                    "credit_party_identifier": credit_party_identifier,
                },
            )
        except ThunesAPIError as exc:
            logger.error("Credit party validation failed: %s", exc)
            return None

    def get_credit_party_information(
        self,
        payer_id: str,
        credit_party_identifier: Dict,
        transaction_type: str,
    ) -> Optional[Dict]:
        """
        Retrieve full credit party information from Thunes.

        Args:
            payer_id: Thunes payer ID.
            credit_party_identifier: Dict of identifier fields.
            transaction_type: "B2B" or "B2C".
        """
        try:
            return self.post(
                "/payers/credit-party-information",
                json={
                    "payer_id": payer_id,
                    "transaction_type": transaction_type,
                    "credit_party_identifier": credit_party_identifier,
                },
            )
        except ThunesAPIError as exc:
            logger.error("Failed to get credit party information: %s", exc)
            return None

    def create_transaction_quotation(
        self,
        payer_id: str,
        transaction_type: str,
        amount: str,
        destination_currency: str,
    ) -> Optional[Dict]:
        """
        Create a transaction quotation (pre-transaction price lock).

        Args:
            payer_id: Thunes payer ID.
            transaction_type: "B2B" or "B2C".
            amount: Amount as a string (e.g. "1000.00").
            destination_currency: 3-letter destination currency code.
        """
        try:
            return self.post(
                "/quotation/create",
                json={
                    "payer_id": payer_id,
                    "transaction_type": transaction_type,
                    "amount": amount,
                    "destination_currency": destination_currency,
                },
            )
        except ThunesAPIError as exc:
            logger.error("Failed to create quotation: %s", exc)
            return None

    def create_transaction(self, data: Dict) -> Optional[Dict]:
        """
        Submit a transaction to Thunes.

        Args:
            data: Full transaction payload (payer_id, quotation_id, etc.)
        """
        try:
            return self.post("/transaction/create", json=data)
        except ThunesAPIError as exc:
            logger.error("Failed to create Thunes transaction: %s", exc)
            return None

    def upload_transaction_document(
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
            file: File-like object to upload.
            file_name: Optional explicit filename.
        """
        resolved_name = file_name or (
            file.name if hasattr(file, "name") else "attachment"
        )
        try:
            return self.post(
                f"/transaction/{transaction_id}/document",
                files={"document": (resolved_name, file)},
                data={"document_type": document_type},
            )
        except ThunesAPIError as exc:
            logger.error(
                "Failed to upload document for transaction %s: %s", transaction_id, exc
            )
            return None

    def confirm_transaction(self, transaction_id: str) -> Optional[Dict]:
        """
        Confirm a transaction after documents have been uploaded.

        Args:
            transaction_id: Thunes transaction ID.
        """
        try:
            return self.get(f"/transaction/{transaction_id}/confirm")
        except ThunesAPIError as exc:
            logger.error("Failed to confirm transaction %s: %s", transaction_id, exc)
            return None
