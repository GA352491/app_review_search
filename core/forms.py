# core/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Review

class UserRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email'] # You can add more fields if needed

class ReviewForm(forms.ModelForm):
    rating = forms.IntegerField(min_value=1, max_value=5, widget=forms.NumberInput(attrs={'placeholder': '1-5 Stars'}))
    review_title = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={'placeholder': 'Optional title for your review'}))
    translated_review = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Write your review here...'}), label="Your Review")

    class Meta:
        model = Review
        fields = ['rating', 'review_title', 'translated_review']