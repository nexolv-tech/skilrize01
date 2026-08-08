from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("crm/contacts", views.ContactViewSet, basename="crm-contact")
router.register("crm/deals", views.DealViewSet, basename="crm-deal")
router.register("crm/tasks", views.TaskViewSet, basename="crm-task")
router.register("agencies", views.AgencyViewSet, basename="agency")
router.register("workspaces", views.WorkspaceViewSet, basename="workspace")
router.register("retainers", views.RetainerPlanViewSet, basename="retainer")

urlpatterns = [
    # Specific routes before the router: its detail pattern matches any
    # non-slash segment and would otherwise swallow these.
    path("retainers/mine/", views.my_retainers, name="my-retainers"),
    path("crm/pipeline/", views.pipeline_summary, name="crm-pipeline"),
    path("", include(router.urls)),
    # Plans and subscriptions
    path("plans/", views.plans, name="plans"),
    path("subscription/", views.my_subscription, name="my-subscription"),
    path("subscription/subscribe/", views.subscribe, name="subscribe"),
    path("subscription/cancel/", views.cancel_subscription, name="cancel-subscription"),
    path("retainers/subscriptions/<int:pk>/cancel/", views.cancel_retainer, name="cancel-retainer"),
]
