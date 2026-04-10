"""
Base view for all plaude_thunes DRF views.

Design:
    - authentication_classes = []  (no-auth by default; downstream overrides)
    - permission_classes = []      (allow-all by default; downstream overrides)
    - get_thunes_client() must be overridden or thunes_client must be set

Downstream apps must supply a ThunesClient — via class attribute or by
overriding get_thunes_client()::

    from plaude_thunes.api.views.payers import GetPayerRequiredFieldsView
    from rest_framework.permissions import IsAuthenticated
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from plaude_thunes import ThunesClient
    from django.conf import settings

    class SecuredPayerRequiredFieldsView(GetPayerRequiredFieldsView):
        authentication_classes = [JWTAuthentication]
        permission_classes = [IsAuthenticated]

        def get_thunes_client(self):
            return ThunesClient(
                api_key=settings.EXTERNAL_API_KEY,
                api_base_url=settings.EXTERNAL_API_BASE_URL,
            )
"""

import logging
from typing import Optional

from rest_framework.views import APIView

from plaude_thunes._client import ThunesClient

logger = logging.getLogger(__name__)


class BaseThunesAPIView(APIView):
    """
    Abstract base for all plaude_thunes DRF views.

    Class attributes (override in subclasses):
        authentication_classes: List of DRF authentication backends.
                                 Default: [] (no authentication enforced).
        permission_classes: List of DRF permission backends.
                             Default: [] (all requests allowed).
        thunes_client: Set to a pre-built ThunesClient instance for simple DI.

    Subclasses MUST either:
        1. Set the ``thunes_client`` class attribute to a configured ThunesClient, or
        2. Override ``get_thunes_client()`` to return one.

    Failing to do either will raise NotImplementedError at request time.
    """

    authentication_classes: list = []
    permission_classes: list = []

    # Set to a pre-built client instance for simple dependency injection
    thunes_client: Optional[ThunesClient] = None

    def get_thunes_client(self) -> ThunesClient:
        """
        Return the ThunesClient to use for this request.

        Override this method for dynamic client provisioning::

            class MyView(BaseThunesAPIView):
                def get_thunes_client(self):
                    return ThunesClient(
                        api_key=settings.EXTERNAL_API_KEY,
                        api_base_url=settings.EXTERNAL_API_BASE_URL,
                    )

        Raises:
            NotImplementedError: If neither ``thunes_client`` is set nor this
                method is overridden.
        """
        if self.thunes_client is not None:
            return self.thunes_client
        raise NotImplementedError(
            f"{self.__class__.__name__} must either set the 'thunes_client' class "
            "attribute or override get_thunes_client()."
        )
