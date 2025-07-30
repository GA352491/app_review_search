# core/api_urls.py

from django.urls import path
from .api_views import (
    AppListAPIView, AppDetailAPIView, ReviewCreateAPIView,
    SupervisorReviewListAPIView, ApproveRejectReviewAPIView,
    RegisterUserAPIView, CustomAuthToken,
    AppSuggestionsAPIView # <--- ADD THIS IMPORT
)

urlpatterns = [
    # App Search & Details
    path('apps/', AppListAPIView.as_view(), name='api_app_list'),
    path('apps/<int:pk>/', AppDetailAPIView.as_view(), name='api_app_detail'),

    # Suggestions (now a separate view)
    path('apps/suggestions/', AppSuggestionsAPIView.as_view(), name='api_app_suggestions'), # <--- UPDATED

    # Review Submission
    path('apps/<int:app_id>/reviews/submit/', ReviewCreateAPIView.as_view(), name='api_submit_review'),

    # Supervisor Dashboard & Actions
    path('supervisor/reviews/pending/', SupervisorReviewListAPIView.as_view(), name='api_supervisor_pending_reviews'),
    path('supervisor/reviews/<int:review_id>/action/', ApproveRejectReviewAPIView.as_view(), name='api_approve_reject_review'),

    # User Authentication
    path('register/', RegisterUserAPIView.as_view(), name='api_register'),
    path('login/', CustomAuthToken.as_view(), name='api_login'),
]