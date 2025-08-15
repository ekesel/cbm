from rest_framework import serializers
from .models import MappingVersion, BoardCredential
from .models import NotificationChannel

class MappingVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MappingVersion
        fields = ["id", "version", "description", "config", "active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class BoardCredentialSerializer(serializers.ModelSerializer):
    # write-only token field; not returned on GET
    token_plain = serializers.CharField(write_only=True, required=False, allow_blank=True)

    has_token = serializers.SerializerMethodField()

    class Meta:
        model = BoardCredential
        fields = [
            "id", "board", "api_base_url", "auth_type", "username", "extra",
            "has_token", "token_plain", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "has_token", "created_at", "updated_at"]

    def get_has_token(self, obj):
        return bool(obj.token_encrypted)

    def create(self, validated_data):
        token = validated_data.pop("token_plain", "")
        cred = BoardCredential.objects.create(**validated_data)
        if token:
            cred.set_token(token)
            cred.save(update_fields=["token_encrypted"])
        return cred

    def update(self, instance, validated_data):
        token = validated_data.pop("token_plain", "")
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if token:
            instance.set_token(token)
        instance.save()
        return instance


class NotificationChannelSerializer(serializers.ModelSerializer):
    webhook_plain = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_webhook = serializers.SerializerMethodField()

    class Meta:
        model = NotificationChannel
        fields = ["id","board","channel_type","name","is_active","rules","min_severity","extra",
                  "webhook_plain","has_webhook","created_at","updated_at"]
        read_only_fields = ["id","has_webhook","created_at","updated_at"]

    def get_has_webhook(self, obj): return bool(obj.webhook_encrypted)

    def create(self, validated):
        w = validated.pop("webhook_plain", "")
        inst = NotificationChannel.objects.create(**validated)
        if w: inst.set_webhook(w); inst.save(update_fields=["webhook_encrypted"])
        return inst

    def update(self, inst, validated):
        w = validated.pop("webhook_plain", "")
        for k,v in validated.items(): setattr(inst, k, v)
        if w: inst.set_webhook(w)
        inst.save()
        return inst