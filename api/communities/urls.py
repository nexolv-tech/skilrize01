from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("communities", views.CommunityViewSet, basename="community")
router.register("threads", views.ThreadViewSet, basename="thread")
router.register("events", views.EventViewSet, basename="event")
router.register("resources", views.ResourceViewSet, basename="resource")
router.register("conversations", views.ConversationViewSet, basename="conversation")

urlpatterns = [
    # These come first on purpose. The router's detail route matches any
    # non-slash segment, so `conversations/start/` would otherwise resolve to
    # the read-only detail view and answer 405 to a POST.
    path("conversations/start/", views.start_conversation, name="conversation-start"),
    path("", include(router.urls)),
    path("communities/<int:pk>/chat/", views.community_chat, name="community-chat"),
    path("replies/<int:pk>/", views.remove_reply, name="reply-remove"),
    path("feed/", views.activity_feed, name="activity-feed"),
    path("reports/", views.report_content, name="report-create"),
    path("moderation/queue/", views.moderation_queue, name="moderation-queue"),
    path("moderation/reports/<int:pk>/resolve/", views.resolve_report, name="report-resolve"),
]
