from bson import ObjectId
from rest_framework import serializers

class ObjectIdField(serializers.Field):
    """
    Custom DRF field to handle MongoDB ObjectId serialization.
    Converts ObjectId <-> str.
    """

    def to_representation(self, value):
        # Convert ObjectId -> str for JSON
        if isinstance(value, ObjectId):
            return str(value)
        return value

    def to_internal_value(self, data):
        # Convert str -> ObjectId when saving
        try:
            return ObjectId(str(data))
        except Exception:
            raise serializers.ValidationError("Invalid ObjectId")
