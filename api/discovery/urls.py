from django.urls import path

from . import views

urlpatterns = [
    # Search
    path("search/gigs/", views.search_gigs, name="search-gigs"),
    path("search/projects/", views.search_projects, name="search-projects"),
    path("gigs/<int:gig_id>/click/", views.record_click, name="gig-click"),
    # Work showcase
    path("showcase/", views.showcase, name="showcase"),
    path(
        "showcase/contracts/<int:contract_id>/",
        views.showcase_consent,
        name="showcase-consent",
    ),
    # Promoted placement
    path("promotions/", views.promotions, name="promotions"),
    path("promotions/<int:pk>/pause/", views.pause_promotion, name="promotion-pause"),
    # Reputation
    path("sellers/<slug:handle>/reputation/", views.seller_reputation, name="seller-reputation"),
]
