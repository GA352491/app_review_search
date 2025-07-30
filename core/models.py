# core/models.py

from django.db import models
from django.contrib.auth.models import User

class App(models.Model):
    name = models.CharField(max_length=255, unique=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    reviews_count = models.IntegerField(default=0)
    size = models.CharField(max_length=50, null=True, blank=True)
    installs = models.BigIntegerField(default=0)
    type = models.CharField(max_length=50, null=True, blank=True)
    price = models.CharField(max_length=50, null=True, blank=True)
    content_rating = models.CharField(max_length=100, null=True, blank=True)
    genres = models.CharField(max_length=255, null=True, blank=True)
    last_updated = models.CharField(max_length=50, null=True, blank=True)
    current_ver = models.CharField(max_length=50, null=True, blank=True)
    android_ver = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.name

class Review(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # Reviewer
    review_title = models.CharField(max_length=255, null=True, blank=True)
    translated_review = models.TextField(null=True, blank=True)
    sentiment = models.CharField(max_length=50, null=True, blank=True)
    sentiment_polarity = models.FloatField(null=True, blank=True)
    sentiment_subjectivity = models.FloatField(null=True, blank=True)
    rating = models.IntegerField(null=True, blank=True) # User's star rating
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Review for {self.app.name} by {self.user.username if self.user else 'Anonymous'}"