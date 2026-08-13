from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminContractViewSet, ContractViewSet

router = DefaultRouter()
router.register("contracts", ContractViewSet, basename="contract")
router.register("admin/contracts", AdminContractViewSet, basename="admin-contract")

urlpatterns = [path("", include(router.urls))]
