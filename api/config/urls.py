from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.views import health, serve_signed_file

# Titles on the interim console, so an operator can never mistake which
# environment they are about to change data in.
admin.site.site_header = f"SkilRize · {settings.ENVIRONMENT}"
admin.site.site_title = "SkilRize admin"
admin.site.index_title = "Operations"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("healthz", health, name="health"),
    # User-uploaded content is served only from this signed, short-lived route —
    # never from a public media directory.
    path("files/<str:token>/", serve_signed_file, name="signed-file"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("marketplace.urls")),
    path("api/v1/", include("contracts.urls")),
    path("api/v1/", include("gigs.urls")),
    path("api/v1/", include("communities.urls")),
    path("api/v1/", include("discovery.urls")),
    path("api/v1/", include("professional.urls")),
    path("api/v1/", include("challenges.urls")),
    path("api/v1/", include("integrations.urls")),
    path("api/v1/", include("payments.urls")),
]
