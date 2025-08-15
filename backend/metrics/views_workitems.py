from __future__ import annotations
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q

from .models import WorkItem
from .serializers import WorkItemListSerializer, WorkItemDetailSerializer
from .filters import WorkItemFilter

class WorkItemSearchView(generics.ListAPIView):
    """
    GET /api/workitems/search?board=1&status=Ready%20for%20QA&blocked=true&ordering=-done_at&limit=50&offset=0
    Supports:
      - Filters (see WorkItemFilter)
      - SearchFilter on: title, source_id, dev_owner
      - Ordering on: created_at, updated_at, done_at, story_points, dev_started_at, qa_started_at
    """
    serializer_class = WorkItemListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = WorkItemFilter
    search_fields = ["title","source_id","dev_owner"]
    ordering_fields = ["created_at","updated_at","done_at","story_points","dev_started_at","qa_started_at","ready_for_qa_at"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        qs = (WorkItem.objects
              .select_related("board")
              .defer("description","meta")  # keep list light
              .order_by("-updated_at"))
        # Optional: restrict by role/board visibility here.
        return qs

class WorkItemDetailView(generics.RetrieveAPIView):
    """
    GET /api/workitems/<int:id>
    """
    serializer_class = WorkItemDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = WorkItem.objects.select_related("board")

class WorkItemByKeyView(generics.GenericAPIView):
    """
    GET /api/workitems/by-key?source=jira&source_id=APP-123
    """
    serializer_class = WorkItemDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        source = request.query_params.get("source")
        source_id = request.query_params.get("source_id")
        if not source or not source_id:
            return Response({"error":"source and source_id are required"}, status=status.HTTP_400_BAD_REQUEST)
        wi = get_object_or_404(WorkItem, source__iexact=source, source_id=source_id)
        return Response(self.get_serializer(wi).data)

class WorkItemFacetView(generics.GenericAPIView):
    """
    GET /api/workitems/facets?board=1&blocked=false
    Returns lightweight counts for filter UIs:
      { statuses: [{value,count}], item_types: [...], assignees: [...], sprints: [...], has_pr: {true: X, false: Y} }
    Takes same filter params as /search and applies them BEFORE facet counts (except the facet dimension itself).
    """
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = WorkItemFilter

    def get_queryset(self):
        return WorkItem.objects.all()

    def get(self, request):
        base = self.filter_queryset(self.get_queryset())

        # status counts
        status_counts = (base.values("status")
                              .exclude(status__isnull=True)
                              .exclude(status__exact="")
                              .annotate(count=Count("id"))
                              .order_by("-count","status"))
        # item_type counts
        type_counts = (base.values("item_type")
                            .exclude(item_type__isnull=True)
                            .exclude(item_type__exact="")
                            .annotate(count=Count("id"))
                            .order_by("-count","item_type"))
        # assignee counts (flatten list field)
        assignee_counts = (base.filter(assignees__isnull=False)
                               .values("assignees")
                               .annotate(count=Count("id"))
                               .order_by("-count","assignees"))
        # sprint counts
        sprint_counts = (base.values("sprint_id")
                              .exclude(sprint_id__isnull=True)
                              .exclude(sprint_id__exact="")
                              .annotate(count=Count("id"))
                              .order_by("-count","sprint_id"))
        # has_pr counts
        with_pr = base.exclude(linked_prs__isnull=True).exclude(linked_prs=[])
        no_pr   = base.filter(Q(linked_prs__isnull=True) | Q(linked_prs=[]))

        data = {
            "statuses": [{"value": r["status"], "count": r["count"]} for r in status_counts[:50]],
            "item_types": [{"value": r["item_type"], "count": r["count"]} for r in type_counts[:50]],
            "assignees": [{"value": r["assignees"], "count": r["count"]} for r in assignee_counts[:50]],
            "sprints": [{"value": r["sprint_id"], "count": r["count"]} for r in sprint_counts[:50]],
            "has_pr": {"true": with_pr.count(), "false": no_pr.count()},
            "total": base.count()
        }
        return Response(data)
