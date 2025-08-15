# users/serializers.py
from rest_framework import serializers
from .models import User, Roles

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "client_id"]
        read_only_fields = ["id", "username", "email", "role", "client_id"]
