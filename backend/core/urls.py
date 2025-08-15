"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from rest_framework.routers import DefaultRouter

from etl.views import MappingVersionViewSet, BoardCredentialViewSet
from core.views import HealthView, PingView
from etl.views import ETLTriggerView, RawStorageOpsView, ValidatorTriggerView, SLABlockedCheckTrigger, \
            NotificationChannelViewSet, RemediationNotifyTriggerView, MappingMatrixValidateView, SnapshotTriggerView, SLABlockedBackfillTrigger
from metrics.views import (
    BoardTimeseriesView, BoardWIPView, BoardReviewTimeseriesView, UserLeaderboardView, BoardViewSet
)
from metrics.views_team_metrics import (
    TeamSummaryView, TeamTimeseriesView
)

from metrics.views_user_metrics import (
    UserSelfSummaryView, UserSelfTimeseriesView, UserSelfWIPView,
    UserSummaryView, UserTimeseriesView, UserWIPView
)

from metrics.views_workitems import (
    WorkItemSearchView, WorkItemDetailView, WorkItemByKeyView, WorkItemFacetView
)
from etl.views_admin import (
    AdminRunETLView, AdminETLStatusView, AdminETLJobsListView, AdminETLJobDetailView, AdminETLCancelView
)

from metrics.views_remediation import (
    RemediationTicketListView, RemediationTicketDetailView, RemediationTicketUpdateView,
    RemediationTicketBulkActionView, ComplianceSummaryView
)



def health(request):
    return JsonResponse({"status": "ok"})


router = DefaultRouter()
router.register(r"admin/boards", BoardViewSet, basename="board")
router.register(r"admin/mappings", MappingVersionViewSet, basename="mappingversion")
router.register(r"admin/credentials", BoardCredentialViewSet, basename="boardcredential")
router.register(r"admin/notify/channels", NotificationChannelViewSet, basename="notifychannel")

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include(router.urls)),
    # Health (public)
    path("api/health/", HealthView.as_view(), name="health"),

    # Auth (JWT + profile)
    path("api/auth/", include("users.urls")),

    # Simple protected ping
    path("api/ping/", PingView.as_view(), name="ping"),
    path("api/admin/etl/run/", ETLTriggerView.as_view(), name="etl_trigger"),
    path("api/admin/raw-storage/run/", RawStorageOpsView.as_view(), name="raw_storage_ops"),
    path("api/admin/validator/run/", ValidatorTriggerView.as_view(), name="validator_trigger"),
    path("api/admin/remediation/notify/", RemediationNotifyTriggerView.as_view(), name="remediation_notify"),
    path("api/admin/mapping/validate/", MappingMatrixValidateView.as_view(), name="mapping_validate"),
    path("api/admin/snapshots/run/", SnapshotTriggerView.as_view(), name="snapshot_trigger"),
    path("api/metrics/boards/<int:board_id>/timeseries", BoardTimeseriesView.as_view(), name="metrics_board_timeseries"),
    path("api/metrics/boards/<int:board_id>/wip",        BoardWIPView.as_view(),       name="metrics_board_wip"),
    path("api/metrics/boards/<int:board_id>/review",     BoardReviewTimeseriesView.as_view(), name="metrics_board_review"),
    path("api/metrics/boards/<int:board_id>/users/leaderboard", UserLeaderboardView.as_view(), name="metrics_user_leaderboard"),
    path("api/admin/sla/blocked/check/", SLABlockedCheckTrigger.as_view(), name="sla_blocked_check"),
    path("api/admin/sla/blocked/backfill/", SLABlockedBackfillTrigger.as_view(), name="sla_blocked_backfill"),
    path("api/metrics/teams/<int:team_id>/timeseries", TeamTimeseriesView.as_view(), name="metrics_team_timeseries"),
    path("api/metrics/teams/<int:team_id>/summary",    TeamSummaryView.as_view(),    name="metrics_team_summary"),
    path("api/metrics/users/self/summary",    UserSelfSummaryView.as_view(),    name="user_metrics_self_summary"),
    path("api/metrics/users/self/timeseries", UserSelfTimeseriesView.as_view(), name="user_metrics_self_timeseries"),
    path("api/metrics/users/self/wip",        UserSelfWIPView.as_view(),        name="user_metrics_self_wip"),

    # arbitrary user (private; requires PROCESS/CTO/ADMIN unless querying self)
    path("api/metrics/users/<str:uid>/summary",    UserSummaryView.as_view(),    name="user_metrics_summary"),
    path("api/metrics/users/<str:uid>/timeseries", UserTimeseriesView.as_view(), name="user_metrics_timeseries"),
    path("api/metrics/users/<str:uid>/wip",        UserWIPView.as_view(),        name="user_metrics_wip"),
    
    path("api/workitems/search", WorkItemSearchView.as_view(), name="workitem_search"),
    path("api/workitems/by-key", WorkItemByKeyView.as_view(), name="workitem_by_key"),
    path("api/workitems/<int:pk>", WorkItemDetailView.as_view(), name="workitem_detail"),
    path("api/workitems/facets", WorkItemFacetView.as_view(), name="workitem_facets"),
    
    path("api/admin/etl/run",    AdminRunETLView.as_view(),        name="etl_run"),
    path("api/admin/etl/status", AdminETLStatusView.as_view(),     name="etl_status"),
    path("api/admin/etl/jobs",   AdminETLJobsListView.as_view(),   name="etl_jobs"),
    path("api/admin/etl/jobs/<int:job_id>", AdminETLJobDetailView.as_view(), name="etl_job_detail"),
    path("api/admin/etl/cancel", AdminETLCancelView.as_view(),     name="etl_cancel"),   # optional
    
    
    # Tickets
    path("api/remediation/tickets",          RemediationTicketListView.as_view(),   name="rt_list"),
    path("api/remediation/tickets/<int:pk>", RemediationTicketDetailView.as_view(), name="rt_detail"),
    path("api/remediation/tickets/<int:pk>/update", RemediationTicketUpdateView.as_view(), name="rt_update"),
    path("api/remediation/tickets/bulk",     RemediationTicketBulkActionView.as_view(),    name="rt_bulk"),

    # Compliance snapshot
    path("api/remediation/compliance",       ComplianceSummaryView.as_view(),       name="rt_compliance"),
]
