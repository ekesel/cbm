from __future__ import annotations
import django_filters as df
from django.utils.dateparse import parse_datetime
from .models import WorkItem

class WorkItemFilter(df.FilterSet):
    # Basic exact filters
    board = df.NumberFilter(field_name="board_id")
    client_id = df.CharFilter(field_name="client_id", lookup_expr="iexact")
    source = df.CharFilter(field_name="source", lookup_expr="iexact")
    source_id = df.CharFilter(field_name="source_id", lookup_expr="iexact")
    item_type = df.CharFilter(field_name="item_type", lookup_expr="iexact")
    status = df.CharFilter(field_name="status", lookup_expr="iexact")
    sprint_id = df.CharFilter(field_name="sprint_id", lookup_expr="iexact")
    assignee = df.CharFilter(field_name="assignees", method="filter_assignee")
    dev_owner = df.CharFilter(field_name="dev_owner", lookup_expr="iexact")
    closed = df.BooleanFilter(field_name="closed")

    # Story point bounds
    points_min = df.NumberFilter(field_name="story_points", lookup_expr="gte")
    points_max = df.NumberFilter(field_name="story_points", lookup_expr="lte")
    has_points = df.BooleanFilter(method="filter_has_points")

    # Timestamps (range)
    created_from = df.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to   = df.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    done_from    = df.IsoDateTimeFilter(field_name="done_at", lookup_expr="gte")
    done_to      = df.IsoDateTimeFilter(field_name="done_at", lookup_expr="lte")

    # Flags
    blocked = df.BooleanFilter(method="filter_blocked")
    has_pr  = df.BooleanFilter(method="filter_has_pr")

    # Text search (title/description) – supplemental to DRF SearchFilter
    q = df.CharFilter(method="filter_q")

    class Meta:
        model = WorkItem
        fields = []

    def filter_assignee(self, qs, name, value):
        return qs.filter(assignees__icontains=value)

    def filter_has_points(self, qs, name, value: bool):
        if value is True:  return qs.exclude(story_points__isnull=True)
        if value is False: return qs.filter(story_points__isnull=True)
        return qs

    def filter_blocked(self, qs, name, value: bool):
        if value is True:  return qs.filter(blocked_flag=True)
        if value is False: return qs.filter(blocked_flag=False)
        return qs

    def filter_has_pr(self, qs, name, value: bool):
        if value is True:  return qs.exclude(linked_prs__isnull=True).exclude(linked_prs=[])
        if value is False: return qs.filter(linked_prs__isnull=True) | qs.filter(linked_prs=[])
        return qs

    def filter_q(self, qs, name, value):
        if not value: return qs
        return qs.filter(title__icontains=value) | qs.filter(description__icontains=value)
