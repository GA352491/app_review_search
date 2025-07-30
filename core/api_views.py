# core/api_views.py

from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.pagination import PageNumberPagination  # Keep this import
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import App, Review
from .serializers import AppSerializer, ReviewSerializer, ReviewCreateSerializer, UserSerializer
from .views import SupervisorRequiredMixin  # Reusing the mixin for supervisor permissions
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from django.db.models import Case, When # <--- ADD THIS IMPORT

# Initialize TF-IDF Vectorizer globally for efficiency (same as in core/views.py)
app_names = [app.name for app in App.objects.all()]
if app_names:
    tfidf_vectorizer = TfidfVectorizer().fit(app_names)
    tfidf_matrix = tfidf_vectorizer.transform(app_names)
else:
    tfidf_vectorizer = None
    tfidf_matrix = None


class AppListAPIView(generics.ListAPIView):
    """
    API endpoint for listing and searching apps with pagination.
    """
    serializer_class = AppSerializer
    permission_classes = [AllowAny]
    pagination_class = PageNumberPagination  # Ensure pagination is active for this view

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        print(f"\n--- API DEBUG: Search Query: '{query}' ---")
        results_list = []

        if query and len(query) >= 1:
            # 1. Prioritize exact match (case-insensitive)
            exact_match_app = App.objects.filter(name__iexact=query).first()
            if exact_match_app:
                results_list.append(exact_match_app)
                print(f"API DEBUG 2: Exact match found: {exact_match_app.name} (ID: {exact_match_app.id})")
            else:
                print("API DEBUG 2: No exact match found.")

            # 2. Perform TF-IDF similarity search
            tfidf_results_found = False # Flag to track if TF-IDF found anything
            if tfidf_vectorizer and tfidf_matrix is not None:
                print("API DEBUG 3: TF-IDF vectorizer and matrix are initialized.")
                try:
                    query_vec = tfidf_vectorizer.transform([query])
                    cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                    all_apps = list(App.objects.all())
                    print(f"API DEBUG 4: Total apps for TF-IDF: {len(all_apps)}")

                    similar_apps_with_scores = []
                    for i, sim in enumerate(cosine_similarities):
                        if i < len(all_apps):
                            app_candidate = all_apps[i]
                            if sim > 0.001: # Main search threshold
                                if exact_match_app and app_candidate.id == exact_match_app.id:
                                    continue
                                similar_apps_with_scores.append((app_candidate, sim))

                    similar_apps_with_scores.sort(key=lambda x: x[1], reverse=True)

                    print(f"API DEBUG 5: Top 5 similar apps (excluding exact):")
                    for j, (app_obj, sim_score) in enumerate(similar_apps_with_scores[:5]):
                        print(f"  {j+1}. {app_obj.name} (ID: {app_obj.id}) - Similarity: {sim_score:.4f}")

                    if similar_apps_with_scores: # If TF-IDF found any results
                        tfidf_results_found = True
                        for app_obj, _ in similar_apps_with_scores[:50 - len(results_list)]:
                            results_list.append(app_obj)
                    print(f"API DEBUG 6: After TF-IDF, results_list size: {len(results_list)}")

                except Exception as e:
                    print(f"API DEBUG ERROR: Error during TF-IDF processing: {e}")
            else:
                print("API DEBUG 3: TF-IDF vectorizer or matrix NOT initialized.")

            # --- CRITICAL CHANGE: Always consider icontains if TF-IDF didn't find enough or failed ---
            if not tfidf_results_found or (not exact_match_app and not tfidf_results_found):
                print("API DEBUG: TF-IDF found no results or not initialized. Falling back to icontains.")
                fallback_results = App.objects.filter(name__icontains=query).order_by('name')
                for app_obj in fallback_results:
                    if app_obj not in results_list:
                        results_list.append(app_obj)

        else:
            print("API DEBUG 1: Query is empty or too short.")


        unique_ids = []
        ordered_ids = []
        for app_obj in results_list:
            if app_obj.id not in unique_ids:
                unique_ids.append(app_obj.id)
                ordered_ids.append(app_obj.id)

        print(f"API DEBUG 7: Unique IDs collected in desired order: {ordered_ids}")

        preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)])
        queryset = App.objects.filter(id__in=ordered_ids).order_by(preserved)

        print(f"API DEBUG 8: Final QuerySet count: {queryset.count()}")
        return queryset


# NEW CLASS: Separate API view for suggestions
class AppSuggestionsAPIView(generics.ListAPIView):
    """
    API endpoint for providing app name suggestions using TF-IDF similarity.
    """
    serializer_class = AppSerializer # Still needs a serializer, but we'll return names directly
    permission_classes = [AllowAny]
    pagination_class = None # IMPORTANT: No pagination for suggestions

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()

        if query:
            if len(query) <= 4: # Example: Use icontains for queries shorter than 4 characters
                print(f"API DEBUG: Using icontains for short suggestion query: '{query}'")
                return App.objects.filter(name__icontains=query).order_by('name')[:10]
            else: # Use TF-IDF for longer queries
                if tfidf_vectorizer and tfidf_matrix is not None:
                    print(f"API DEBUG: Using TF-IDF for long suggestion query: '{query}'")
                    try:
                        query_vec = tfidf_vectorizer.transform([query])
                        cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()
                        all_apps = list(App.objects.all())
                        similar_apps_with_scores = []
                        for i, sim in enumerate(cosine_similarities):
                            if i < len(all_apps) and sim >= 0.001: # Keep a small threshold
                                similar_apps_with_scores.append((all_apps[i], sim))
                        similar_apps_with_scores.sort(key=lambda x: x[1], reverse=True)
                        return [app_obj for app_obj, _ in similar_apps_with_scores[:10]]
                    except Exception as e:
                        print(f"API DEBUG ERROR: Error during TF-IDF suggestions, falling back: {e}")
                        return App.objects.filter(name__icontains=query).order_by('name')[:10]
                else:
                    print("API DEBUG: TF-IDF not initialized for suggestions. Falling back to icontains.")
                    return App.objects.filter(name__icontains=query).order_by('name')[:10]
        return App.objects.none()

    def list(self, request, *args, **kwargs):
        # Override list method to return only the list of suggestion names
        # get_queryset now returns a list of App objects, so we extract names
        queryset_or_list = self.get_queryset()
        if isinstance(queryset_or_list, list): # If TF-IDF returned a list of objects
            suggestions = [app.name for app in queryset_or_list]
        else: # If fallback to queryset was used
            suggestions = [app.name for app in queryset_or_list]
        return Response({'suggestions': suggestions})



class AppDetailAPIView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving a single app's details and its reviews.
    """
    queryset = App.objects.all()
    serializer_class = AppSerializer
    lookup_field = 'pk'  # Use 'pk' (id) for lookup
    permission_classes = [AllowAny]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Get reviews for this app
        if request.user.is_authenticated:
            # Show approved reviews + user's own pending reviews
            reviews = instance.reviews.filter(Q(is_approved=True) | Q(user=request.user)).order_by('-created_at')
        else:
            # Only show approved reviews for unauthenticated users
            reviews = instance.reviews.filter(is_approved=True).order_by('-created_at')

        review_serializer = ReviewSerializer(reviews, many=True)

        # Combine app data and review data in one response
        data = serializer.data
        data['reviews'] = review_serializer.data
        return Response(data)


class ReviewCreateAPIView(generics.CreateAPIView):
    """
    API endpoint for users to submit new reviews.
    Requires authentication.
    """
    queryset = Review.objects.all()
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticated]  # Only authenticated users can create reviews

    def perform_create(self, serializer):
        app_id = self.kwargs.get('app_id')  # Get app_id from URL kwargs
        app = get_object_or_404(App, id=app_id)
        # Set the app and user for the review before saving
        serializer.save(app=app, user=self.request.user)


# core/api_views.py

# ... (existing imports) ...

class SupervisorReviewListAPIView(generics.ListAPIView):  # <--- REMOVED SupervisorRequiredMixin
    """
    API endpoint for supervisors to view pending reviews.
    Requires supervisor permissions.
    """
    queryset = Review.objects.filter(is_approved=False).order_by('-created_at')
    serializer_class = ReviewSerializer
    # Use IsAdminUser permission directly for API
    permission_classes = [IsAuthenticated, IsAdminUser]  # <--- CHANGED PERMISSION
    pagination_class = PageNumberPagination


# ... (rest of your api_views.py file) ...


class ApproveRejectReviewAPIView(APIView):
    """
    API endpoint for supervisors to approve or reject reviews.
    Requires supervisor permissions.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]  # SupervisorRequiredMixin handles the specific permission

    def post(self, request, review_id, format=None):
        review = get_object_or_404(Review, id=review_id)
        action = request.data.get('action')  # Get action from request body (JSON)
        print(action)
        if action == 'approve':
            review.is_approved = True
            review.save()
            return Response({"message": "Review approved successfully."}, status=status.HTTP_200_OK)
        elif action == 'reject':
            review.delete()
            return Response({"message": "Review rejected and removed."},
                            status=status.HTTP_204_NO_CONTENT)  # 204 No Content for successful deletion
        else:
            return Response({"error": "Invalid action. Must be 'approve' or 'reject'."},
                            status=status.HTTP_400_BAD_REQUEST)


# User Authentication and Registration APIs
class RegisterUserAPIView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]  # Allow anyone to register

    def perform_create(self, serializer):
        user = serializer.save()
        user.set_password(self.request.data.get('password'))  # Hash the password
        user.save()
        # Optionally create a token immediately for the new user
        Token.objects.create(user=user)


class CustomAuthToken(ObtainAuthToken):
    """
    Custom login endpoint to return user details along with the token.
    """

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'is_staff': user.is_staff,  # Useful for Vue.js to check supervisor status
            'is_superuser': user.is_superuser,
        })
