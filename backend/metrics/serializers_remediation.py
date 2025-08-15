from __future__ import annotations
from rest_framework import serializers
from .models import RemediationTicket, RemediationStatus

class RemediationTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemediationTicket
        fields = [
            "id", "board", "work_item", "rule_code", "status", "message", "meta",
            "owner", "acknowledged_at", "snoozed_until",
            "created_at", "updated_at", "resolved_at"
        ]
        read_only_fields = ["id","created_at","updated_at","resolved_at"]

class RemediationTicketUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        required=False,
        choices=[RemediationStatus.OPEN, RemediationStatus.IN_PROGRESS, RemediationStatus.DONE]
    )
    owner = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    message = serializers.CharField(required=False, allow_blank=True)   # replace message
    append_note = serializers.CharField(required=False, allow_blank=True)  # add note to meta["notes"]
    snoozed_until = serializers.DateTimeField(required=False, allow_null=True)

class RemediationTicketBulkActionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    action = serializers.ChoiceField(choices=["ack","resolve","assign","snooze","note","reopen"])
    owner = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)
    snoozed_until = serializers.DateTimeField(required=False, allow_null=True)

class ComplianceQuerySerializer(serializers.Serializer):
    board_id = serializers.IntegerField()
    start = serializers.DateField(required=False)   # optional window for “opened within”
    end = serializers.DateField(required=False)
