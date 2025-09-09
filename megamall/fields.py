# megamall/fields.py
from bson import ObjectId
from rest_framework import serializers

class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        # Convert ObjectId to string for JSON serialization
        if isinstance(value, ObjectId):
            return str(value)
        return value

    def to_internal_value(self, data):
        # Convert string back to ObjectId for database operations
        try:
            return ObjectId(data)
        except:
            raise serializers.ValidationError("Invalid ObjectId")