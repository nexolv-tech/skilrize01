from django.contrib import admin
from django.urls import include, path

from core.views import health, serve_signed_file

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", health, name="health"),
    # User-uploaded content is served only from this signed, short-lived route —
    # never from a public media directory.
    path("files/<str:token>/", serve_signed_file, name="signed-file"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("marketplace.urls")),
    path("api/v1/", include("contracts.urls")),
    path("api/v1/", include("gigs.urls")),
]
