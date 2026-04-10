"""
Base serializer helpers for plaude_thunes.
"""

from rest_framework import serializers


class BaseThunesSerializer(serializers.Serializer):
    """
    Marker base class for all plaude_thunes serializers.

    Provides a common ancestor for isinstance checks and future shared behaviour.
    Downstream apps can extend individual serializers without modifying SDK code.
    """
