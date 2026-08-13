from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("challenges", views.ChallengeViewSet, basename="challenge")

urlpatterns = [
    # Before the router: its detail pattern matches any non-slash segment and
    # would otherwise swallow this as if "mine" were a slug.
    path("challenges/mine/", views.my_participations, name="challenges-mine"),
    path("", include(router.urls)),
]
