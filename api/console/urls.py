from django.urls import path

from . import views

urlpatterns = [
    path("admin/overview/", views.overview, name="console-overview"),
    # Payments
    path("admin/payments/transfers/", views.transfers, name="console-transfers"),
    path(
        "admin/payments/transfers/<int:pk>/confirm/",
        views.transfer_confirm,
        name="console-transfer-confirm",
    ),
    path(
        "admin/payments/transfers/<int:pk>/not-received/",
        views.transfer_not_received,
        name="console-transfer-not-received",
    ),
    path("admin/payments/plans/", views.plan_payments, name="console-plan-payments"),
    path(
        "admin/payments/plans/<int:pk>/confirm/",
        views.plan_payment_confirm,
        name="console-plan-payment-confirm",
    ),
    path(
        "admin/payments/plans/<int:pk>/not-received/",
        views.plan_payment_not_received,
        name="console-plan-payment-not-received",
    ),
    path("admin/payments/payouts/", views.payouts, name="console-payouts"),
    path(
        "admin/payments/payouts/<int:pk>/bank-details/",
        views.payout_bank_details,
        name="console-payout-bank-details",
    ),
    path(
        "admin/payments/payouts/<int:pk>/mark-paid/",
        views.payout_mark_paid,
        name="console-payout-mark-paid",
    ),
    path(
        "admin/payments/payouts/<int:pk>/send-swich/",
        views.payout_send_swich,
        name="console-payout-send-swich",
    ),
    path("admin/payments/refunds/", views.refunds, name="console-refunds"),
    path(
        "admin/payments/refunds/<int:pk>/send-swich/",
        views.refund_send_swich,
        name="console-refund-send-swich",
    ),
    path(
        "admin/payments/refunds/<int:pk>/bank-details/",
        views.refund_bank_details,
        name="console-refund-bank-details",
    ),
    path(
        "admin/payments/refunds/<int:pk>/mark-sent/",
        views.refund_mark_sent,
        name="console-refund-mark-sent",
    ),
    # Identity
    path("admin/identity/", views.identity_queue, name="console-identity"),
    path(
        "admin/identity/<int:pk>/approve/", views.identity_approve, name="console-identity-approve"
    ),
    path("admin/identity/<int:pk>/reject/", views.identity_reject, name="console-identity-reject"),
    # Catalogue
    path("admin/gigs/", views.gigs, name="console-gigs"),
    path("admin/gigs/<int:pk>/remove/", views.gig_remove, name="console-gig-remove"),
    path("admin/gigs/<int:pk>/restore/", views.gig_restore, name="console-gig-restore"),
    path("admin/projects/", views.projects, name="console-projects"),
    path("admin/projects/<int:pk>/close/", views.project_close, name="console-project-close"),
    path("admin/categories/", views.categories, name="console-categories"),
    path("admin/categories/<int:pk>/", views.category_update, name="console-category-update"),
    # Orders
    path("admin/orders/", views.orders, name="console-orders"),
    path("admin/orders/<int:pk>/void/", views.order_void, name="console-order-void"),
    # Reports
    path("admin/reports/", views.reports, name="console-reports"),
    path("admin/reports/<int:pk>/resolve/", views.report_resolve, name="console-report-resolve"),
    # Users (the list, detail and suspension endpoints live in accounts)
    path("admin/users/<int:pk>/summary/", views.user_summary, name="console-user-summary"),
    path("admin/users/<int:pk>/role/", views.user_set_role, name="console-user-role"),
    path("admin/users/<int:pk>/sign-out/", views.user_sign_out, name="console-user-sign-out"),
    # Settings
    path("admin/settings/", views.platform_settings, name="console-settings"),
]
