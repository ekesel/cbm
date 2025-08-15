from rest_framework import serializers
from metrics.models import Board
from .models import WorkItem, PR, RemediationTicket

class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ["id", "source", "board_id", "name", "client_id", "meta", "last_synced"]
        read_only_fields = ["id", "last_synced"]

class DateRangeSerializer(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    tz = serializers.CharField(required=False, default="UTC", allow_blank=True)

class LeaderboardParamsSerializer(DateRangeSerializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=50)
    sort = serializers.ChoiceField(
        required=False,
        choices=("done_points_30d","done_points_7d","done_count_30d","done_count_7d","reviews_30d","reviews_7d"),
        default="done_points_30d"
    )
    
class UserMetricParamsSerializer(serializers.Serializer):
    board_id = serializers.IntegerField(required=True)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    tz = serializers.CharField(required=False, default="UTC", allow_blank=True)

class UserWIPParamsSerializer(serializers.Serializer):
    board_id = serializers.IntegerField(required=True)
    

class PRSerializer(serializers.ModelSerializer):
    class Meta:
        model = PR
        fields = ["pr_id","source","title","branch","opened_at","first_reviewed_at","merged_at","author_id","reviewer_ids","meta"]

class RemediationTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemediationTicket
        fields = ["id","rule_code","status","message","meta","created_at","updated_at","resolved_at"]

class WorkItemListSerializer(serializers.ModelSerializer):
    has_pr = serializers.SerializerMethodField()
    lead_time_sec = serializers.SerializerMethodField()

    class Meta:
        model = WorkItem
        fields = [
            "id","board","client_id","source","source_id","title","item_type","status",
            "story_points","assignees","dev_owner","sprint_id","closed",
            "created_at","started_at","dev_started_at","dev_done_at","ready_for_qa_at",
            "qa_started_at","qa_verified_at","signed_off_at","ready_for_uat_at","deployed_uat_at","done_at",
            "blocked_flag","blocked_reason","blocked_since",
            "has_pr","lead_time_sec",
        ]

    def get_has_pr(self, obj): return bool(obj.linked_prs)

    def get_lead_time_sec(self, obj):
        if obj.created_at and obj.done_at:
            return (obj.done_at - obj.created_at).total_seconds()
        return None

class WorkItemDetailSerializer(WorkItemListSerializer):
    linked_prs_full = serializers.SerializerMethodField()
    remediation_tickets = serializers.SerializerMethodField()

    class Meta(WorkItemListSerializer.Meta):
        fields = WorkItemListSerializer.Meta.fields + [
            "description","meta","linked_prs","linked_prs_full","remediation_tickets"
        ]

    def get_linked_prs_full(self, obj):
        prs = PR.objects.filter(work_item=obj).order_by("-opened_at")
        return PRSerializer(prs, many=True).data

    def get_remediation_tickets(self, obj):
        rts = RemediationTicket.objects.filter(work_item=obj).order_by("-created_at")
        return RemediationTicketSerializer(rts, many=True).data