from django.urls import path
from .views import (
    register_view,
    login_view,
    verify_email_view,
    forgot_password_view,
    reset_password_view,
    admin_forgot_password_view,
    admin_reset_password_view,
    profile_me_view,
    profile_admin_view,
    resume_score_view,
    resume_history_view,
    download_ats_pdf_view,
    google_auth_view,
    google_callback_view,
    github_auth_view,
    github_callback_view,
    db_test_view,
)

urlpatterns = [
    # DB Test
    path("db-test", db_test_view, name="db_test"),

    # Auth routes (/api/auth/*)
    path("auth/register", register_view, name="register"),
    path("auth/login", login_view, name="login"),
    path("auth/verify-email", verify_email_view, name="verify_email"),
    path("auth/forgot-password", forgot_password_view, name="forgot_password"),
    path("auth/reset-password", reset_password_view, name="reset_password"),

    # OAuth
    path("auth/google", google_auth_view, name="google_auth"),
    path("auth/google/callback", google_callback_view, name="google_callback"),
    path("auth/github", github_auth_view, name="github_auth"),
    path("auth/github/callback", github_callback_view, name="github_callback"),

    # Admin Auth (/api/admin/auth/*)
    path("admin/auth/forgot-password", admin_forgot_password_view, name="admin_forgot_password"),
    path("admin/auth/reset-password", admin_reset_password_view, name="admin_reset_password"),

    # Profile routes (/api/profile/*)
    path("profile/me", profile_me_view, name="profile_me"),
    path("profile/admin", profile_admin_view, name="profile_admin"),

    # Resume routes (/api/resume/*)
    path("resume/score", resume_score_view, name="resume_score"),
    path("resume/history", resume_history_view, name="resume_history"),
    path("resume/report/<int:report_id>/pdf", download_ats_pdf_view, name="download_ats_pdf"),
]
