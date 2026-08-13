from django.urls import path

from . import views

urlpatterns = [
    path("integrations/providers/", views.providers_status, name="integrations-providers"),
    path("integrations/<str:provider>/authorize/", views.authorize, name="integrations-authorize"),
    path("integrations/<str:provider>/connect/", views.connect, name="integrations-connect"),
    path(
        "integrations/<str:provider>/disconnect/",
        views.disconnect,
        name="integrations-disconnect",
    ),
    path(
        "contracts/<int:contract_id>/meetings/", views.contract_meetings, name="contract-meetings"
    ),
    path("meetings/<int:meeting_id>/cancel/", views.cancel_meeting, name="meeting-cancel"),
    path(
        "contracts/<int:contract_id>/activity-sources/",
        views.contract_activity_sources,
        name="contract-activity-sources",
    ),
    path(
        "activity-sources/<int:source_id>/sync/",
        views.sync_activity_source_now,
        name="activity-source-sync",
    ),
]
