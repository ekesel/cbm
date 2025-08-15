from __future__ import annotations
from rest_framework import serializers

class RunETLSerializer(serializers.Serializer):
    board_id = serializers.IntegerField()
    stages = serializers.ListField(
        child=serializers.ChoiceField(choices=["fetch","normalize","validate","snapshot"]),
        required=False,
        allow_empty=True,
        default=["fetch","normalize","validate","snapshot"]
    )
    mapping_version = serializers.CharField(required=False, allow_blank=True, default="v1")
    date_for_snapshot = serializers.DateField(required=False)  # optional, only used if 'snapshot' in stages

class StatusQuerySerializer(serializers.Serializer):
    task_id = serializers.CharField()

class JobsListQuerySerializer(serializers.Serializer):
    board_id = serializers.IntegerField(required=False)
    stage = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=50)
    offset = serializers.IntegerField(required=False, min_value=0, default=0)

class CancelTaskSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    terminate = serializers.BooleanField(required=False, default=False)
