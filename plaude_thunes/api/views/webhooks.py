"""
Webhook view for receiving Thunes transaction status callbacks.

BaseThunesWebhookView provides:
    - Signature/credential validation via WebhookValidator
    - Event parsing
    - Extensible handle_event() hook for downstream business logic

Downstream apps subclass and implement handle_event()::

    from plaude_thunes.api.views.webhooks import BaseThunesWebhookView

    class MyThunesWebhookView(BaseThunesWebhookView):
        def handle_event(self, data: dict):
            transaction_id = data.get("id")
            status_class = data.get("status_class_message")
            # Update your Transaction model here
            Transaction.objects.filter(partner_reference=transaction_id).update(
                partner_status=data.get("status_message"),
                partner_status_class=status_class,
            )
"""

import logging

from django.http import JsonResponse
from rest_framework import status
from rest_framework.views import APIView

from plaude_thunes.exceptions import ThunesWebhookError
from plaude_thunes.security.webhook import WebhookValidator

logger = logging.getLogger(__name__)


class BaseThunesWebhookView(APIView):
    """
    Base DRF view for Thunes webhook callbacks.

    All requests must pass Basic Auth validation using the configured
    callback_key and callback_secret.

    Class attributes:
        authentication_classes: [] (webhook endpoint handles its own auth)
        permission_classes: [] (all requests pass to validation layer)
        callback_key: Set to the webhook callback key (required).
        callback_secret: Set to the webhook callback secret (required).

    Override hooks:
        get_webhook_validator() - swap out the validator implementation
        handle_event(data)       - implement your business logic here
        on_validation_error(exc) - customise the 401 response

    Full example::

        class MyWebhookView(BaseThunesWebhookView):
            def handle_event(self, data: dict):
                transaction_id = data["id"]
                try:
                    tx = Transaction.objects.get(partner_reference=transaction_id)
                    tx.partner_status = data.get("status_message")
                    tx.partner_status_class = data.get("status_class_message")
                    if data.get("status_class_message") == "COMPLETED":
                        tx.status = "Success"
                    tx.save()
                except Transaction.DoesNotExist:
                    logger.warning("Transaction %s not found", transaction_id)
    """

    authentication_classes: list = []
    permission_classes: list = []

    # Optional: set directly on the class (constructor injection preferred)
    callback_key: str = None
    callback_secret: str = None

    def get_webhook_validator(self) -> WebhookValidator:
        """
        Return a configured WebhookValidator.

        Uses ``self.callback_key`` and ``self.callback_secret`` class attributes.
        Override this method to provide credentials dynamically::

            class MyWebhookView(BaseThunesWebhookView):
                def get_webhook_validator(self):
                    return WebhookValidator(
                        callback_key=settings.THUNES_CALLBACK_KEY,
                        callback_secret=settings.THUNES_CALLBACK_SECRET,
                    )

        Raises:
            ThunesWebhookError: If callback_key or callback_secret are not set.
        """
        key = self.callback_key
        secret = self.callback_secret

        if not (key and secret):
            raise ThunesWebhookError(
                "Webhook validator cannot be created: set 'callback_key' and "
                "'callback_secret' as class attributes or override get_webhook_validator().",
                reason="missing_config",
            )

        return WebhookValidator(callback_key=key, callback_secret=secret)

    def on_validation_error(self, exc: ThunesWebhookError) -> JsonResponse:
        """
        Return an HTTP 401 response when webhook validation fails.

        Override to customise the error response format.
        """
        return JsonResponse(
            {"status": "error", "message": "Unauthorized"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    def handle_event(self, data: dict) -> None:
        """
        Process a validated webhook event.

        Called after signature validation succeeds. Subclasses MUST override
        this to implement their business logic (e.g. updating Transaction records).

        Args:
            data: Parsed JSON body of the webhook payload.
                  Common fields from Thunes:
                      - id: Transaction ID (use as partner_reference lookup)
                      - status_message: Human-readable status text
                      - status_class_message: Machine-readable class ("COMPLETED", etc.)

        Note:
            This base implementation is a no-op. The POST handler returns 200 OK
            regardless, so be sure to raise or log errors inside your override.
        """
        logger.info("Thunes webhook received (no handle_event override): %s", data)

    def post(self, request, *args, **kwargs) -> JsonResponse:
        """Handle an incoming Thunes webhook POST request."""
        # --- 1. Validate credentials ---
        try:
            validator = self.get_webhook_validator()
            validator.validate(request)
        except ThunesWebhookError as exc:
            logger.warning("Thunes webhook validation failed: %s", exc)
            return self.on_validation_error(exc)

        # --- 2. Parse body ---
        data = request.data
        if not data:
            return JsonResponse(
                {"status": "error", "message": "Empty webhook payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info("Thunes webhook received: transaction_id=%s", data.get("id"))

        # --- 3. Dispatch to subclass handler ---
        self.handle_event(data)

        return JsonResponse(
            {"status": "success", "message": "Webhook processed"},
            status=status.HTTP_200_OK,
        )
