from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("projects", views.ProjectViewSet, basename="project")
router.register("proposals", views.ProposalViewSet, basename="proposal")
router.register("invitations", views.InvitationViewSet, basename="invitation")

urlpatterns = [
    path("categories/", views.categories, name="categories"),
    path("skills/", views.skills, name="skills"),
    path("proposals/quota/", views.proposal_quota, name="proposal-quota"),
    path("projects/recommended/", views.recommended_projects, name="recommended-projects"),
    path("", include(router.urls)),
]
