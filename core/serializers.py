# core/serializers.py

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import App, Review

class AppSerializer(serializers.ModelSerializer):
    class Meta:
        model = App
        fields = '__all__' # Include all fields from the App model

class ReviewSerializer(serializers.ModelSerializer):
    # Display username instead of user ID
    user_username = serializers.CharField(source='user.username', read_only=True)
    # Display app name instead of app ID
    app_name = serializers.CharField(source='app.name', read_only=True)

    class Meta:
        model = Review
        # Include all fields, plus the custom ones for display
        fields = [
            'id', 'app', 'app_name', 'user', 'user_username', 'review_title',
            'translated_review', 'sentiment', 'sentiment_polarity',
            'sentiment_subjectivity', 'rating', 'created_at', 'is_approved'
        ]
        # Make app and user read-only when retrieving, as they are FKs
        read_only_fields = ['app', 'user', 'is_approved', 'created_at']

class ReviewCreateSerializer(serializers.ModelSerializer):
    """
    Serializer specifically for creating new reviews.
    It will automatically set `is_approved` to False.
    """
    class Meta:
        model = Review
        fields = ['review_title', 'translated_review', 'rating'] # Fields allowed for user input

    def create(self, validated_data):
        # The app and user will be set in the view based on URL and authenticated user
        review = Review.objects.create(
            is_approved=False, # New reviews are always pending approval
            **validated_data
        )
        return review

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email'] # Basic user details