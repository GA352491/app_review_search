# core/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Case, When
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages

from django.views.generic import ListView, View
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse_lazy

# --- CRITICAL CHANGE: Import global TF-IDF variables from core.apps ---
# These variables will be populated when Django's AppConfig.ready() method runs.
from core.apps import tfidf_vectorizer, tfidf_matrix

# --- Keep sklearn components imported here as they are used directly in this file ---
# TfidfVectorizer is needed for query_vec = tfidf_vectorizer.transform([query])
from sklearn.feature_extraction.text import TfidfVectorizer
# linear_kernel is needed for cosine_similarities = linear_kernel(...)
from sklearn.metrics.pairwise import linear_kernel


# --- REMOVE THE GLOBAL TF-IDF INITIALIZATION FROM HERE ---
# The following block is removed because initialization now happens in core/apps.py
# app_names = [app.name for app in App.objects.all()]
# if app_names:
#     tfidf_vectorizer = TfidfVectorizer().fit(app_names)
#     tfidf_matrix = tfidf_vectorizer.transform(app_names)
# else:
#     tfidf_vectorizer = None
#     tfidf_matrix = None


def home_view(request):
    """
    Renders the home page of the application.
    """
    return render(request, 'core/home.html')


class AppSearchResultsView(ListView):
    """
    Displays search results for apps with pagination.
    Uses TF-IDF for similarity search or falls back to 'icontains'.
    """
    # Model is specified here, so App is implicitly available for basic ListView operations.
    # Import App model here for the class definition itself
    from .models import App
    model = App
    template_name = 'core/search_results.html'
    context_object_name = 'results'  # The variable name used in the template
    paginate_by = 10  # Set the number of results per page (e.g., 10 or 20)

    def get_queryset(self):
        """
        Determines the queryset for search results based on the user's query.
        Implements a hybrid search strategy: exact match, TF-IDF similarity, and icontains fallback.
        """
        query = self.request.GET.get('q', '').strip()
        print(f"\n--- DEBUG: Search Query: '{query}' ---")
        results_list = []  # List to collect App objects in the desired relevance order

        # Only proceed if a non-empty query is provided
        if query and len(query) >= 1:
            # Import App model here to ensure it's available for database queries within this method.
            # This helps prevent potential circular import issues if App was imported at the top level
            # and then referenced during early Django startup phases.
            from .models import App

            # 1. Prioritize Exact Match (Case-Insensitive)
            # This ensures that if the user types the full, exact name of an app, it's the top result.
            exact_match_app = App.objects.filter(name__iexact=query).first()
            if exact_match_app:
                results_list.append(exact_match_app)
                print(f"DEBUG 2: Exact match found: {exact_match_app.name} (ID: {exact_match_app.id})")
            else:
                print("DEBUG 2: No exact match found.")
            print(f"DEBUG 2a: results_list after exact match: {[app.name for app in results_list]}")


            # 2. Perform TF-IDF Similarity Search (Primary Intelligent Search)
            # This flag tracks if the TF-IDF search found any results above its threshold.
            tfidf_results_found = False
            # Check if the global TF-IDF vectorizer and matrix have been initialized
            # by the AppConfig.ready() method.
            if tfidf_vectorizer is not None and tfidf_matrix is not None:
                print("DEBUG 3: TF-IDF vectorizer and matrix are initialized.")
                try:
                    # Transform the user's query into a TF-IDF vector.
                    query_vec = tfidf_vectorizer.transform([query])
                    # Calculate the cosine similarity between the query vector and all app name vectors.
                    cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                    # Fetch all App objects again. Crucially, order them by 'pk' to ensure
                    # their order matches the order used when building the tfidf_matrix,
                    # allowing correct mapping of similarity scores to apps.
                    all_apps = list(App.objects.all().order_by('pk'))
                    print(f"DEBUG 4: Total apps for TF-IDF (ordered by PK): {len(all_apps)}")

                    similar_apps_with_scores = []  # To store (App object, similarity score) tuples
                    for i, sim in enumerate(cosine_similarities):
                        if i < len(all_apps):  # Defensive check for index bounds
                            app_candidate = all_apps[i]
                            # Apply a similarity threshold: only consider apps with a score > 0.001.
                            # This filters out very weak or irrelevant matches.
                            # This threshold can be tuned for desired precision/recall.
                            if sim > 0.001:  # Main search threshold
                                # Avoid adding the exact match again if it was already found and added.
                                if exact_match_app and app_candidate.id == exact_match_app.id:
                                    continue
                                similar_apps_with_scores.append((app_candidate, sim))

                    # Sort the collected similar apps by their similarity score in descending order (most relevant first).
                    similar_apps_with_scores.sort(key=lambda x: x[1], reverse=True)

                    print(f"DEBUG 5: Top 10 similar apps (excluding exact) with scores:")
                    if similar_apps_with_scores:
                        for j, (app_obj, sim_score) in enumerate(similar_apps_with_scores[:10]):
                            print(f"  {j + 1}. {app_obj.name} (ID: {app_obj.id}) - Similarity: {sim_score:.6f}") # More precision
                    else:
                        print("  No similar apps found by TF-IDF above threshold.")


                    if similar_apps_with_scores:
                        tfidf_results_found = True
                        # Add TF-IDF results to results_list
                        for app_obj, _ in similar_apps_with_scores[:50 - len(results_list)]:
                            results_list.append(app_obj)
                    print(f"DEBUG 6: After TF-IDF, results_list size: {len(results_list)}")
                    print(f"DEBUG 6a: results_list after TF-IDF: {[app.name for app in results_list]}")


                except Exception as e:
                    # Log any errors during TF-IDF processing (e.g., malformed query, data issues).
                    print(f"DEBUG ERROR: Error during TF-IDF processing: {e}")
            else:
                print("DEBUG 3: TF-IDF vectorizer or matrix NOT initialized.")

            # 3. Fallback to `icontains` (Robustness)
            # This is a crucial step for robustness. It's executed if:
            # - The TF-IDF search didn't yield any results above its threshold.
            # - OR, if there was no exact match AND TF-IDF also found no results (or wasn't initialized).
            # This ensures that even if TF-IDF struggles (e.g., due to a typo), a basic substring match is attempted.
            if not tfidf_results_found or (not exact_match_app and not tfidf_results_found):
                print("DEBUG: TF-IDF found no results or not initialized. Falling back to icontains.")
                # Import App model here for fallback query
                fallback_results = App.objects.filter(name__icontains=query).order_by('name')
                for app_obj in fallback_results:
                    if app_obj not in results_list:  # Avoid adding duplicates
                        results_list.append(app_obj)
            print(f"DEBUG 6b: results_list after fallback: {[app.name for app in results_list]}")


        else:
            # If the query is empty or too short (e.g., less than 1 character after strip)
            print("DEBUG 1: Query is empty or too short.")

        # 4. Prepare Final QuerySet with Preserved Order for Pagination
        # Collect unique IDs from the results_list, preserving their order.
        unique_ids = []
        ordered_ids = []  # This list will store IDs in the desired display order
        for app_obj in results_list:
            if app_obj.id not in unique_ids:  # Ensure no duplicate apps in the final list
                unique_ids.append(app_obj.id)
                ordered_ids.append(app_obj.id)  # Add ID to the ordered list

        print(f"DEBUG 7: Unique IDs collected in desired order: {ordered_ids}")

        # Use Django's Case and When expressions to order the queryset by the specific
        # sequence of IDs we determined based on exact match and TF-IDF relevance.
        # This is critical for pagination to maintain the relevance order across pages.
        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)])
        # Import App model here for final queryset construction
        queryset = App.objects.filter(id__in=ordered_ids).order_by(preserved)

        print(f"DEBUG 8: Final QuerySet count: {queryset.count()}")
        return queryset

    def get_context_data(self, **kwargs):
        """
        Adds the original search query to the template context.
        """
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '').strip()  # Pass the query to the template
        return context


def app_detail(request, app_id):
    """
    Displays the details of a single app and its associated reviews.
    Shows approved reviews to all users, and also pending reviews by the current user.
    """
    # Import models here to ensure they are available within the function scope.
    from .models import App, Review
    app = get_object_or_404(App, id=app_id)
    if request.user.is_authenticated:
        # If user is authenticated, show approved reviews + their own pending reviews
        reviews = app.reviews.filter(Q(is_approved=True) | Q(user=request.user)).order_by('-created_at')
    else:
        # If user is not authenticated, only show approved reviews
        reviews = app.reviews.filter(is_approved=True).order_by('-created_at')
    context = {
        'app': app,
        'reviews': reviews,
    }
    return render(request, 'core/app_detail.html', context)


def search_suggestions(request):
    """
    Provides real-time search suggestions using a hybrid approach (icontains for short queries, TF-IDF for longer).
    Returns suggestions as a JSON response.
    """
    query = request.GET.get('q', '').strip()
    suggestions = []
    print(f"\n--- DEBUG: Traditional Web Suggestion Query: '{query}' ---")

    # Only provide suggestions if query is not empty and has at least 3 characters
    if query and len(query) >= 3:
        # Import App model here for database queries
        from .models import App
        # Hybrid Logic: Use icontains for very short queries (3-4 characters)
        if len(query) <= 4:
            print(f"DEBUG: Using icontains for short suggestion query: '{query}'")
            # Efficiently get only the 'name' field for the top 10 matches
            matching_apps = App.objects.filter(name__icontains=query).values_list('name', flat=True)[:10]
            suggestions = list(matching_apps)
        else:  # Hybrid: Use TF-IDF for longer queries (5+ characters)
            # Check if TF-IDF model is initialized by the AppConfig.ready() method
            if tfidf_vectorizer is not None and tfidf_matrix is not None:
                print(f"DEBUG: Using TF-IDF for long suggestion query: '{query}'")
                try:
                    query_vec = tfidf_vectorizer.transform([query])
                    cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                    # Fetch all App objects again, ordered by PK for consistency with TF-IDF matrix
                    all_apps = list(App.objects.all().order_by('pk'))

                    similar_apps_with_scores = []
                    for i, sim in enumerate(cosine_similarities):
                        if i < len(all_apps):
                            app_candidate = all_apps[i]
                            if sim >= 0.1:  # Use a specific threshold for suggestions (can be tuned)
                                similar_apps_with_scores.append((app_candidate, sim))

                    similar_apps_with_scores.sort(key=lambda x: x[1], reverse=True)

                    top_suggestions_apps = [app_obj for app_obj, _ in similar_apps_with_scores[:10]]
                    suggestions = [app.name for app in top_suggestions_apps]
                    print(f"DEBUG: TF-IDF Web Suggestions found: {suggestions}")
                    for app_obj, sim_score in similar_apps_with_scores[:10]:
                        print(f"  - {app_obj.name} (Score: {sim_score:.4f})")

                except Exception as e:
                    print(f"DEBUG ERROR: Error during TF-IDF web suggestions, falling back: {e}")
                    matching_apps = App.objects.filter(name__icontains=query).values_list('name', flat=True)[:10]
                    suggestions = list(matching_apps)
            else:
                print("DEBUG: TF-IDF not initialized for web suggestions. Falling back to icontains.")
                matching_apps = App.objects.filter(name__icontains=query).values_list('name', flat=True)[:10]
                suggestions = list(matching_apps)

    return JsonResponse({'suggestions': suggestions})


# User Registration View
def register(request):
    """
    Handles user registration.
    """
    # Import forms and auth functions here to ensure availability
    from .forms import UserRegisterForm
    from django.contrib.auth import login
    from django.contrib import messages
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Log the user in immediately after registration
            messages.success(request, f'Account created for {user.username}!')
            return redirect('home')
    else:
        form = UserRegisterForm()
    return render(request, 'core/register.html', {'form': form})


# Submit Review View
@login_required  # Requires user to be logged in to submit a review
def submit_review(request, app_id):
    """
    Allows authenticated users to submit a review for a specific app.
    Reviews are initially set to pending approval.
    """
    # Import models and forms here
    from .models import App, Review
    from .forms import ReviewForm
    from django.contrib import messages
    app = get_object_or_404(App, id=app_id)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)  # Don't save to DB yet
            review.app = app  # Associate with the app
            review.user = request.user  # Associate with the current user
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
        """
        Checks if the request user is authenticated AND is either staff or superuser.
        """
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser)

    def handle_no_permission(self):
        """
        Redirects to login page if not authenticated, or raises 403 if authenticated but not authorized.
        """
        if not self.request.user.is_authenticated:
            # If user is not logged in, redirect them to the login page
            # with a 'next' parameter so they return to the original page after login.
            return redirect(f'/login/?next={self.request.path}')
        # If authenticated but not staff/superuser, raise PermissionDenied (results in a 403 Forbidden).
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have permission to access the supervisor dashboard.")


class SupervisorDashboardView(SupervisorRequiredMixin, ListView):
    """
    Displays a list of reviews that are pending approval for supervisors.
    """
    # Model is specified here, so Review is implicitly available for basic ListView operations.
    from .models import Review # Import Review model here for the class definition itself
    model = Review
    template_name = 'core/supervisor_dashboard.html'
    context_object_name = 'pending_reviews'  # The variable name used in the template
    ordering = ['-created_at']  # Order by newest reviews first
    paginate_by = 10  # Display 10 reviews per page (adjust as needed)

    def get_queryset(self):
        """
        Retrieves only reviews that have not yet been approved.
        """
        # Import Review model here
        from .models import Review
        return Review.objects.filter(is_approved=False).order_by('-created_at')


class ApproveRejectReviewView(SupervisorRequiredMixin, View):
    """
    Handles the approval or rejection of a specific review via POST request.
    Only accessible by supervisors.
    """

    def post(self, request, review_id):
        # Import Review model here
        from .models import Review
        from django.contrib import messages
        # Get the review object, or return 404 if not found
        review = get_object_or_404(Review, id=review_id)
        # Get the action (e.g., 'approve' or 'reject') from the form data
        action = request.POST.get('action')

        if action == 'approve':
            review.is_approved = True  # Set the review as approved
            review.save()
            messages.success(request,
                             f'Review by {review.user.username if review.user else "Anonymous"} for {review.app.name} has been approved.')
        elif action == 'reject':
            review.delete()  # Delete the review if rejected.
            # Alternative: You could add a 'status' field (e.g., 'pending', 'approved', 'rejected')
            # and set review.status = 'rejected' here instead of deleting, if you want to keep rejected reviews.
            messages.info(request,
                          f'Review by {review.user.username if review.user else "Anonymous"} for {review.app.name} has been rejected and removed.')
        else:
            messages.error(request, 'Invalid action for review.')

        # Redirect back to the supervisor dashboard after processing the action
        return redirect('supervisor_dashboard')

# =========================================================
# SUPERVISOR RELATED VIEWS END HERE
# =========================================================