from __future__ import annotations
import django_filters as df
from .models import RemediationTicket, RemediationStatus

class RemediationTicketFilter(df.FilterSet):
    board = df.NumberFilter(field_name="board_id")
    rule_code = df.CharFilter(field_name="rule_code", lookup_expr="iexact")
    status = df.CharFilter(field_name="status", lookup_expr="iexact")
    owner = df.CharFilter(field_name="owner", lookup_expr="iexact")
    work_item = df.NumberFilter(field_name="work_item_id")
    created_from = df.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_to   = df.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    updated_from = df.IsoDateTimeFilter(field_name="updated_at", lookup_expr="gte")
    updated_to   = df.IsoDateTimeFilter(field_name="updated_at", lookup_expr="lte")
    snoozed = df.BooleanFilter(method="filter_snoozed")

    class Meta:
        model = RemediationTicket
        fields = []

    def filter_snoozed(self, qs, name, value: bool):
        if value is True:  return qs.exclude(snoozed_until__isnull=True)
        if value is False: return qs.filter(snoozed_until__isnull=True)
        return qs
