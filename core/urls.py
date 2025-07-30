# core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('search/', views.AppSearchResultsView.as_view(), name='search_apps'),
    path('app/<int:app_id>/', views.app_detail, name='app_detail'),
    path('search_suggestions/', views.search_suggestions, name='search_suggestions'),
    path('app/<int:app_id>/submit_review/', views.submit_review, name='submit_review'),

    path('search_suggestions/', views.search_suggestions, name='search_suggestions'),
    path('supervisor/dashboard/', views.SupervisorDashboardView.as_view(), name='supervisor_dashboard'),
    path('supervisor/review/<int:review_id>/action/', views.ApproveRejectReviewView.as_view(),
         name='approve_reject_review'),

]
