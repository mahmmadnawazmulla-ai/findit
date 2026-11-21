from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("report/lost/", views.report_item, {"kind": "lost"}, name="report_lost"),
    path("report/found/", views.report_item, {"kind": "found"}, name="report_found"),
    path("browse/", views.browse, name="browse"),
    path("item/<str:kind>/<int:pk>/", views.item_detail, name="item_detail"),
    path("item/<str:kind>/<int:pk>/delete/", views.delete_item, name="delete_item"),
    path("item/<str:kind>/<int:pk>/recovered/", views.mark_recovered, name="mark_recovered"),
    path("item/<str:kind>/<int:pk>/qr.svg", views.qr_code, name="qr_code"),
    path("my-reports/", views.my_reports, name="my_reports"),
    path("claim/<int:pk>/", views.claim_create, name="claim_create"),
    path("my-claims/", views.my_claims, name="my_claims"),
    path("notifications/", views.notifications, name="notifications"),
    # Admin module (staff only)
    path("manage/", views.manage_dashboard, name="manage_dashboard"),
    path("manage/reports/", views.manage_reports, name="manage_reports"),
    path("manage/reports/<str:kind>/<int:pk>/<str:action>/", views.manage_report_action, name="manage_report_action"),
    path("manage/claims/", views.manage_claims, name="manage_claims"),
    path("manage/claims/<int:pk>/", views.manage_claim_detail, name="manage_claim_detail"),
    path("manage/users/", views.manage_users, name="manage_users"),
    path("manage/categories/", views.manage_categories, name="manage_categories"),
    path("manage/recovered/", views.manage_recovered, name="manage_recovered"),
]
