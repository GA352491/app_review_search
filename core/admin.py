# core/admin.py

from django.contrib import admin
from .models import App, Review

@admin.register(App)
class AppAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'rating', 'installs')
    search_fields = ('name', 'category')
    list_filter = ('category', 'content_rating')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('app', 'user', 'review_title', 'is_approved', 'created_at', 'sentiment')
    list_filter = ('is_approved', 'sentiment', 'created_at')
    search_fields = ('app__name', 'user__username', 'review_title', 'translated_review')
    raw_id_fields = ('app', 'user') # For better performance with many objects
    actions = ['approve_reviews', 'reject_reviews']

    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} reviews successfully approved.')
    approve_reviews.short_description = "Approve selected reviews"

    def reject_reviews(self, request, queryset):
        deleted_count, _ = queryset.delete()
        self.message_user(request, f'{deleted_count} reviews successfully rejected and deleted.')
    reject_reviews.short_description = "Reject and delete selected reviews"