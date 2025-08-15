from django.contrib import admin
from .models import Board, RawPayload, WorkItem, PR, Defect, MetricSnapshot, RemediationTicket, Team, TeamBoard

@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ("name", "source", "board_id", "client_id", "last_synced")
    search_fields = ("name", "board_id", "client_id")
    list_filter = ("source",)

@admin.register(RawPayload)
class RawPayloadAdmin(admin.ModelAdmin):
    list_display = ("source", "object_type", "external_id", "mapping_version", "fetched_at")
    search_fields = ("external_id",)
    list_filter = ("source", "object_type", "mapping_version")

@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "item_type", "story_points", "sprint_id", "status", "done_at")
    list_filter = ("source", "item_type", "status")
    search_fields = ("title", "source_id", "release_id", "client_id")

@admin.register(PR)
class PRAdmin(admin.ModelAdmin):
    list_display = ("pr_id", "source", "work_item", "opened_at", "merged_at", "author_id")
    search_fields = ("pr_id", "author_id")

@admin.register(Defect)
class DefectAdmin(admin.ModelAdmin):
    list_display = ("defect_id", "source", "work_item", "severity", "detected_at", "environment")
    list_filter = ("severity", "environment")
    search_fields = ("defect_id",)

@admin.register(MetricSnapshot)
class MetricSnapshotAdmin(admin.ModelAdmin):
    list_display = ("scope", "scope_id", "sprint_id", "date", "created_at")
    list_filter = ("scope",)
    date_hierarchy = "date"

@admin.register(RemediationTicket)
class RemediationTicketAdmin(admin.ModelAdmin):
    list_display = ("rule_code", "board", "work_item", "status", "created_at", "resolved_at")
    list_filter = ("status", "rule_code")
    search_fields = ("rule_code", "message")

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "updated_at")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)

@admin.register(TeamBoard)
class TeamBoardAdmin(admin.ModelAdmin):
    list_display = ("team", "board", "weight")
    search_fields = ("team__name", "board__name")