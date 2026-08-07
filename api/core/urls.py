from django.urls import path

from . import views

urlpatterns = [
    path("config/", views.config, name="config"),
    path("uploads/", views.upload, name="upload"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path("notifications/read/", views.mark_notifications_read, name="notifications-read"),
    path(
        "notifications/preferences/",
        views.notification_preferences,
        name="notification-preferences",
    ),
]
