from django.urls import path

from . import views

urlpatterns = [
    # Bootstrap
    path("csrf/", views.csrf, name="csrf"),
    # Registration and sign-in
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("login/2fa/", views.login_two_factor, name="login-2fa"),
    path("login/device/", views.login_device_verify, name="login-device-verify"),
    path("refresh/", views.refresh, name="refresh"),
    path("logout/", views.logout, name="logout"),
    # The signed-in user
    path("me/", views.me, name="me"),
    path("me/avatar/", views.upload_avatar, name="avatar"),
    path("me/seller/", views.update_seller_profile, name="seller-profile"),
    path("me/buyer/", views.update_buyer_profile, name="buyer-profile"),
    path("users/<slug:handle>/", views.public_profile, name="public-profile"),
    # Verification
    path("email/verify/", views.request_email_verification, name="email-verify-request"),
    path("email/confirm/", views.confirm_email, name="email-verify-confirm"),
    path("phone/", views.set_phone, name="phone-set"),
    path("phone/verify/", views.verify_phone, name="phone-verify"),
    path("identity/", views.submit_identity, name="identity-submit"),
    path("universities/lookup/", views.lookup_university, name="university-lookup"),
    # Passwords
    path("password/reset/", views.request_password_reset, name="password-reset-request"),
    path("password/reset/confirm/", views.confirm_password_reset, name="password-reset-confirm"),
    path("password/change/", views.change_password, name="password-change"),
    # Sessions
    path("sessions/", views.sessions, name="sessions"),
    path("sessions/<uuid:family>/", views.revoke_session, name="session-revoke"),
    path("sessions/revoke-all/", views.revoke_all_sessions, name="sessions-revoke-all"),
    # Two-factor
    path("2fa/setup/", views.two_factor_setup, name="2fa-setup"),
    path("2fa/confirm/", views.two_factor_confirm, name="2fa-confirm"),
    path("2fa/disable/", views.two_factor_disable, name="2fa-disable"),
]
