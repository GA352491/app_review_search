# core/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from .models import App, Review
from .forms import UserRegisterForm, ReviewForm
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from django.db.models import Case, When # <--- ADD THIS IMPORT

# --- NEW IMPORTS FOR CLASS-BASED VIEWS AND MIXINS ---
from django.views.generic import ListView, View
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import \
    reverse_lazy  # Useful if you were redirecting from class views using reverse_lazy, though redirect() is also fine.

# Initialize TF-IDF Vectorizer globally for efficiency
app_names = [app.name for app in App.objects.all()]
if app_names:
    tfidf_vectorizer = TfidfVectorizer().fit(app_names)
    tfidf_matrix = tfidf_vectorizer.transform(app_names)
else:
    tfidf_vectorizer = None
    tfidf_matrix = None


def home_view(request):
    return render(request, 'core/home.html')


# def search_apps(request):
#     query = request.GET.get('q', '').strip()
#     results = []
#
#     if query:
#         if tfidf_vectorizer and tfidf_matrix is not None:  # Corrected variable name here (tfidf_matrix)
#             query_vec = tfidf_vectorizer.transform([query])
#             cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()
#             related_docs_indices = cosine_similarities.argsort()[:-50:-1]
#
#             all_apps = list(App.objects.all())
#             for i in related_docs_indices:
#                 if cosine_similarities[i] > 0.1:
#                     results.append(all_apps[i])
#         else:
#             results = App.objects.filter(name__icontains=query)[:50]
#
#     context = {
#         'query': query,
#         'results': results,
#     }
#     return render(request, 'core/search_results.html', context)
class AppSearchResultsView(ListView):
    """
    Displays search results for apps with pagination.
    Uses TF-IDF for similarity search or falls back to 'icontains'.
    """
    model = App
    template_name = 'core/search_results.html'
    context_object_name = 'results' # The variable name used in the template
    paginate_by = 10 # Set the number of results per page (e.g., 10 or 20)

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        print(f"\n--- DEBUG: Search Query: '{query}' ---")
        results_list = []

        if query and len(query) >= 1:
            # 1. Prioritize exact match (case-insensitive)
            exact_match_app = App.objects.filter(name__iexact=query).first()
            if exact_match_app:
                results_list.append(exact_match_app)
                print(f"DEBUG 2: Exact match found: {exact_match_app.name} (ID: {exact_match_app.id})")
            else:
                print("DEBUG 2: No exact match found.")

            # 2. Perform TF-IDF similarity search
            tfidf_results_found = False  # Flag to track if TF-IDF found anything
            if tfidf_vectorizer and tfidf_matrix is not None:
                print("DEBUG 3: TF-IDF vectorizer and matrix are initialized.")
                try:
                    query_vec = tfidf_vectorizer.transform([query])
                    cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                    all_apps = list(App.objects.all())
                    print(f"DEBUG 4: Total apps for TF-IDF: {len(all_apps)}")

                    similar_apps_with_scores = []
                    for i, sim in enumerate(cosine_similarities):
                        if i < len(all_apps):
                            app_candidate = all_apps[i]
                            if sim > 0.001:  # Main search threshold
                                if exact_match_app and app_candidate.id == exact_match_app.id:
                                    continue
                                similar_apps_with_scores.append((app_candidate, sim))

                    similar_apps_with_scores.sort(key=lambda x: x[1], reverse=True)

                    print(f"DEBUG 5: Top 5 similar apps (excluding exact):")
                    for j, (app_obj, sim_score) in enumerate(similar_apps_with_scores[:5]):
                        print(f"  {j + 1}. {app_obj.name} (ID: {app_obj.id}) - Similarity: {sim_score:.4f}")

                    if similar_apps_with_scores:  # If TF-IDF found any results
                        tfidf_results_found = True
                        for app_obj, _ in similar_apps_with_scores[:50 - len(results_list)]:
                            results_list.append(app_obj)
                    print(f"DEBUG 6: After TF-IDF, results_list size: {len(results_list)}")

                except Exception as e:
                    print(f"DEBUG ERROR: Error during TF-IDF processing: {e}")
            else:
                print("DEBUG 3: TF-IDF vectorizer or matrix NOT initialized.")

            # --- CRITICAL CHANGE: Always consider icontains if TF-IDF didn't find enough or failed ---
            # This ensures that if TF-IDF yields no results (e.g., due to typo or very low score),
            # we still fall back to a basic contains search.
            if not tfidf_results_found or (not exact_match_app and not tfidf_results_found):
                print("DEBUG: TF-IDF found no results or not initialized. Falling back to icontains.")
                fallback_results = App.objects.filter(name__icontains=query).order_by('name')
                for app_obj in fallback_results:
                    if app_obj not in results_list:  # Avoid adding duplicates
                        results_list.append(app_obj)

        else:
            print("DEBUG 1: Query is empty or too short.")

        unique_ids = []
        ordered_ids = []
        for app_obj in results_list:
            if app_obj.id not in unique_ids:
                unique_ids.append(app_obj.id)
                ordered_ids.append(app_obj.id)

        print(f"DEBUG 7: Unique IDs collected in desired order: {ordered_ids}")

        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)])
        queryset = App.objects.filter(id__in=ordered_ids).order_by(preserved)

        print(f"DEBUG 8: Final QuerySet count: {queryset.count()}")
        return queryset






    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '').strip() # Pass the query to the template
        return context


def app_detail(request, app_id):
    app = get_object_or_404(App, id=app_id)
    if request.user.is_authenticated:
        reviews = app.reviews.filter(Q(is_approved=True) | Q(user=request.user)).order_by('-created_at')
    else:
        reviews = app.reviews.filter(is_approved=True).order_by('-created_at')
    context = {
        'app': app,
        'reviews': reviews,
    }
    return render(request, 'core/app_detail.html', context)


def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    suggestions = []
    print(f"\n--- DEBUG: Traditional Web Suggestion Query: '{query}' ---")

    if query and len(query) >= 3: # Still require minimum 3 characters for suggestions
        if len(query) <= 4: # Hybrid: Use icontains for queries shorter than 4 characters
            print(f"DEBUG: Using icontains for short suggestion query: '{query}'")
            matching_apps = App.objects.filter(name__icontains=query).values_list('name', flat=True)[:10]
            suggestions = list(matching_apps)
        else: # Hybrid: Use TF-IDF for longer queries
            if tfidf_vectorizer and tfidf_matrix is not None:
                print(f"DEBUG: Using TF-IDF for long suggestion query: '{query}'")
                try:
                    query_vec = tfidf_vectorizer.transform([query])
                    cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                    all_apps = list(App.objects.all())

                    similar_apps_with_scores = []
                    for i, sim in enumerate(cosine_similarities):
                        if i < len(all_apps):
                            app_candidate = all_apps[i]
                            # Use a very low threshold for suggestions to catch more results
                            if sim >= 0.1: # You can tune this threshold
                                similar_apps_with_scores.append((app_candidate, sim))

                    similar_apps_with_scores.sort(key=lambda x: x[1], reverse=True)

                    top_suggestions_apps = [app_obj for app_obj, _ in similar_apps_with_scores[:10]]
                    suggestions = [app.name for app in top_suggestions_apps]
                    print(f"DEBUG: TF-IDF Web Suggestions found: {suggestions}")
                    for app_obj, sim_score in similar_apps_with_scores[:10]:
                        print(f"  - {app_obj.name} (Score: {sim_score:.4f})")

                except Exception as e:
                    print(f"DEBUG ERROR: Error during TF-IDF web suggestions, falling back: {e}")
                    # Fallback to icontains if TF-IDF processing fails for some reason
                    matching_apps = App.objects.filter(name__icontains=query).values_list('name', flat=True)[:10]
                    suggestions = list(matching_apps)
            else:
                print("DEBUG: TF-IDF not initialized for web suggestions. Falling back to icontains.")
                # Fallback to icontains if TF-IDF vectorizer/matrix are not available
                matching_apps = App.objects.filter(name__icontains=query).values_list('name', flat=True)[:10]
                suggestions = list(matching_apps)

    return JsonResponse({'suggestions': suggestions})


# User Registration View
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Account created for {user.username}!')
            return redirect('home')
    else:
        form = UserRegisterForm()
    return render(request, 'core/register.html', {'form': form})


# Submit Review View
@login_required
def submit_review(request, app_id):
    app = get_object_or_404(App, id=app_id)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.app = app
            review.user = request.user
            review.is_approved = False  # New reviews are pending approval
            review.save()
            messages.success(request, 'Your review has been submitted for approval!')
            return redirect('app_detail', app_id=app.id)
    else:
        form = ReviewForm()
    context = {
        'form': form,
        'app': app,
    }
    return render(request, 'core/submit_review.html', context)


# =========================================================
# SUPERVISOR RELATED VIEWS START HERE
# =========================================================

class SupervisorRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure that only authenticated staff users (or superusers)
    can access the view.
    """

    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)

    def handle_no_permission(self):
        """
        Redirects to login page if not authenticated, or shows 403 if authenticated but not authorized.
        """
        if not self.request.user.is_authenticated:
            # Redirect to login with 'next' parameter so they return here after login
            return redirect(f'/login/?next={self.request.path}')
        # If authenticated but not staff/superuser, raise 403 forbidden
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to access the supervisor dashboard.")


class SupervisorDashboardView(SupervisorRequiredMixin, ListView):
    """
    Displays a list of reviews that are pending approval.
    """
    model = Review
    template_name = 'core/supervisor_dashboard.html'
    context_object_name = 'pending_reviews'  # The variable name used in the template
    ordering = ['-created_at']  # Order by newest reviews first
    paginate_by = 10  # <--- ADD THIS LINE: Display 10 reviews per page (adjust as needed)

    def get_queryset(self):
        # Retrieve only reviews that have not yet been approved
        return Review.objects.filter(is_approved=False).order_by('-created_at')


class ApproveRejectReviewView(SupervisorRequiredMixin, View):
    """
    Handles the approval or rejection of a specific review.
    """

    def post(self, request, review_id):
        # Get the review object, or return 404 if not found
        review = get_object_or_404(Review, id=review_id)
        action = request.POST.get('action')  # Get the action (e.g., 'approve' or 'reject') from the form

        if action == 'approve':
            review.is_approved = True  # Set the review as approved
            review.save()
            messages.success(request,
                             f'Review by {review.user.username if review.user else "Anonymous"} for {review.app.name} has been approved.')
        elif action == 'reject':
            review.delete()  # Delete the review if rejected.
            # Alternatively, you could add a 'status' field (e.g., 'pending', 'approved', 'rejected')
            # and set review.status = 'rejected' here instead of deleting.
            messages.info(request,
                          f'Review by {review.user.username if review.user else "Anonymous"} for {review.app.name} has been rejected and removed.')
        else:
            messages.error(request, 'Invalid action for review.')

        # Redirect back to the supervisor dashboard after processing the action
        return redirect('supervisor_dashboard')

# =========================================================
# SUPERVISOR RELATED VIEWS END HERE
# =========================================================
