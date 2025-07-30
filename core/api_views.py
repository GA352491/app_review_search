# core/api_views.py

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db.models import Case, When # Import Case, When
from .models import App,Review
# --- CRITICAL CHANGE: Import global TF-IDF variables from core.apps ---
# These variables will be populated by the 'initialize_tfidf' management command.
from core.apps import tfidf_vectorizer, tfidf_matrix

# --- Keep sklearn components imported here as they are used directly in this file ---
from sklearn.feature_extraction.text import TfidfVectorizer # Needed for query_vec = tfidf_vectorizer.transform([query])
from sklearn.metrics.pairwise import linear_kernel # Needed for cosine_similarities = linear_kernel(...)

# --- REMOVE THE GLOBAL TF-IDF INITIALIZATION FROM HERE ---
# The following block is removed because initialization now happens via a management command.
# app_names = [app.name for app in App.objects.all()]
# if app_names:
#     tfidf_vectorizer = TfidfVectorizer().fit(app_names)
#     tfidf_matrix = tfidf_vectorizer.transform(app_names)
# else:
#     tfidf_vectorizer = None
#     tfidf_matrix = None


class AppListAPIView(generics.ListAPIView):
    """
    API endpoint for listing and searching apps with pagination.
    """
    # Import AppSerializer here, as it's directly used by serializer_class
    from .serializers import AppSerializer
    serializer_class = AppSerializer
    permission_classes = [AllowAny]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        print(f"\n--- API DEBUG: Search Query: '{query}' ---")
        results_list = []

        if query and len(query) >= 1:
            # Import App model here, as it's used for database queries
            from .models import App
            # 1. Prioritize exact match (case-insensitive)
            exact_match_app = App.objects.filter(name__iexact=query).first()
            if exact_match_app:
                results_list.append(exact_match_app)
                print(f"API DEBUG 2: Exact match found: {exact_match_app.name} (ID: {exact_match_app.id})")
            else:
                print("API DEBUG 2: No exact match found.")

            # 2. Perform TF-IDF similarity search
            tfidf_results_found = False
            # --- CRITICAL CHANGE: Use imported global tfidf_vectorizer and tfidf_matrix ---
            if tfidf_vectorizer is not None and tfidf_matrix is not None:
                print("API DEBUG 3: TF-IDF vectorizer and matrix are initialized.")
                try:
                    query_vec = tfidf_vectorizer.transform([query])
                    cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                    # all_apps needs to be fetched again here for the current state of the DB
                    all_apps = list(App.objects.all())
                    print(f"API DEBUG 4: Total apps for TF-IDF: {len(all_apps)}")

                    similar_apps_with_scores = []
                    for i, sim in enumerate(cosine_similarities):
                        if i < len(all_apps):
                            app_candidate = all_apps[i]
                            if sim > 0.001:
                                if exact_match_app and app_candidate.id == exact_match_app.id:
                                    continue
                                similar_apps_with_scores.append((app_candidate, sim))

                    similar_apps_with_scores.sort(key=lambda x: x[1], reverse=True)

                    print(f"API DEBUG 5: Top 5 similar apps (excluding exact):")
                    for j, (app_obj, sim_score) in enumerate(similar_apps_with_scores[:5]):
                        print(f"  {j + 1}. {app_obj.name} (ID: {app_obj.id}) - Similarity: {sim_score:.4f}")

                    if similar_apps_with_scores:
                        tfidf_results_found = True
                        for app_obj, _ in similar_apps_with_scores[:50 - len(results_list)]:
                            results_list.append(app_obj)
                    print(f"API DEBUG 6: After TF-IDF, results_list size: {len(results_list)}")

                except Exception as e:
                    print(f"API DEBUG ERROR: Error during TF-IDF processing: {e}")
            else:
                print("API DEBUG 3: TF-IDF vectorizer or matrix NOT initialized.")

            if not tfidf_results_found or (not exact_match_app and not tfidf_results_found):
                print("API DEBUG: TF-IDF found no results or not initialized. Falling back to icontains.")
                # Import App model here for fallback
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
        # Import App model here for final queryset construction
        queryset = App.objects.filter(id__in=ordered_ids).order_by(preserved)

        print(f"API DEBUG 8: Final QuerySet count: {queryset.count()}")
        return queryset


class AppSuggestionsAPIView(generics.ListAPIView):
    """
    API endpoint for providing app name suggestions using TF-IDF similarity.
    """
    # Import AppSerializer here, as it's directly used by serializer_class
    from .serializers import AppSerializer
    serializer_class = AppSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        print(f"\n--- API DEBUG: Suggestion Query: '{query}' ---")

        if query:
            # Import App model here for database queries
            from .models import App
            if len(query) <= 4:
                print(f"API DEBUG: Using icontains for short suggestion query: '{query}'")
                return App.objects.filter(name__icontains=query).order_by('name')[:10]
            else:
                # --- CRITICAL CHANGE: Use imported global tfidf_vectorizer and tfidf_matrix ---
                if tfidf_vectorizer is not None and tfidf_matrix is not None:
                    print(f"API DEBUG: Using TF-IDF for long suggestion query: '{query}'")
                    try:
                        query_vec = tfidf_vectorizer.transform([query])
                        cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                        # all_apps needs to be fetched again here for the current state of the DB
                        all_apps = list(App.objects.all())

                        similar_apps_with_scores = []
                        for i, sim in enumerate(cosine_similarities):
                            if i < len(all_apps) and sim >= 0.001:
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

    # core/api_views.py

    from rest_framework import generics, status
    from rest_framework.response import Response
    from rest_framework.views import APIView
    from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
    from rest_framework.authtoken.views import ObtainAuthToken
    from rest_framework.authtoken.models import Token  # Keep Token import here for CustomAuthToken
    from rest_framework.pagination import PageNumberPagination
    from django.contrib.auth.models import User  # Keep User import here for RegisterUserAPIView
    from django.db.models import Q
    from django.shortcuts import get_object_or_404
    from django.db.models import Case, When  # Import Case, When

    # --- CRITICAL CHANGE: Import global TF-IDF variables from core.apps ---
    # These variables will be populated when Django's AppConfig.ready() method runs.
    from core.apps import tfidf_vectorizer, tfidf_matrix

    # --- Keep sklearn components imported here as they are used directly in this file ---
    from sklearn.feature_extraction.text import \
        TfidfVectorizer  # Needed for query_vec = tfidf_vectorizer.transform([query])
    from sklearn.metrics.pairwise import linear_kernel  # Needed for cosine_similarities = linear_kernel(...)

    # --- REMOVE THE GLOBAL TF-IDF INITIALIZATION FROM HERE ---
    # The following block is removed because initialization now happens in core/apps.py
    # app_names = [app.name for app in App.objects.all()]
    # if app_names:
    #     tfidf_vectorizer = TfidfVectorizer().fit(app_names)
    #     tfidf_matrix = tfidf_vectorizer.transform(app_names)
    # else:
    #     tfidf_vectorizer = None
    #     tfidf_matrix = None

    class AppListAPIView(generics.ListAPIView):
        """
        API endpoint for listing and searching apps with pagination.
        """
        # Import AppSerializer here, as it's directly used by serializer_class
        from .serializers import AppSerializer
        serializer_class = AppSerializer
        permission_classes = [AllowAny]
        pagination_class = PageNumberPagination

        def get_queryset(self):
            query = self.request.query_params.get('q', '').strip()
            print(f"\n--- API DEBUG: Search Query: '{query}' ---")
            results_list = []

            if query and len(query) >= 1:
                # Import App model here, as it's used for database queries within this method
                from .models import App
                # 1. Prioritize exact match (case-insensitive)
                exact_match_app = App.objects.filter(name__iexact=query).first()
                if exact_match_app:
                    results_list.append(exact_match_app)
                    print(f"API DEBUG 2: Exact match found: {exact_match_app.name} (ID: {exact_match_app.id})")
                else:
                    print("API DEBUG 2: No exact match found.")
                print(f"API DEBUG 2a: results_list after exact match: {[app.name for app in results_list]}")

                # 2. Perform TF-IDF similarity search
                tfidf_results_found = False
                # --- CRITICAL CHANGE: Use imported global tfidf_vectorizer and tfidf_matrix ---
                if tfidf_vectorizer is not None and tfidf_matrix is not None:
                    print("API DEBUG 3: TF-IDF vectorizer and matrix are initialized.")
                    try:
                        query_vec = tfidf_vectorizer.transform([query])
                        cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                        # Fetch all App objects again. Crucially, order them by 'pk' to ensure
                        # their order matches the order used when building the tfidf_matrix.
                        all_apps = list(App.objects.all().order_by('pk'))
                        print(f"API DEBUG 4: Total apps for TF-IDF: {len(all_apps)}")

                        similar_apps_with_scores = []
                        for i, sim in enumerate(cosine_similarities):
                            if i < len(all_apps):
                                app_candidate = all_apps[i]
                                if sim > 0.001:
                                    if exact_match_app and app_candidate.id == exact_match_app.id:
                                        continue
                                    similar_apps_with_scores.append((app_candidate, sim))

                        similar_apps_with_scores.sort(key=lambda x: x[1], reverse=True)

                        print(f"API DEBUG 5: Top 5 similar apps (excluding exact):")
                        if similar_apps_with_scores:
                            for j, (app_obj, sim_score) in enumerate(similar_apps_with_scores[:5]):
                                print(f"  {j + 1}. {app_obj.name} (ID: {app_obj.id}) - Similarity: {sim_score:.6f}")
                        else:
                            print("  No similar apps found by TF-IDF above threshold.")

                        if similar_apps_with_scores:
                            tfidf_results_found = True
                            for app_obj, _ in similar_apps_with_scores[:50 - len(results_list)]:
                                results_list.append(app_obj)
                        print(f"API DEBUG 6: After TF-IDF, results_list size: {len(results_list)}")
                        print(f"API DEBUG 6a: results_list after TF-IDF: {[app.name for app in results_list]}")


                    except Exception as e:
                        print(f"API DEBUG ERROR: Error during TF-IDF processing: {e}")
                else:
                    print("API DEBUG 3: TF-IDF vectorizer or matrix NOT initialized.")

                if not tfidf_results_found or (not exact_match_app and not tfidf_results_found):
                    print("API DEBUG: TF-IDF found no results or not initialized. Falling back to icontains.")
                    # Import App model here for fallback
                    fallback_results = App.objects.filter(name__icontains=query).order_by('name')
                    for app_obj in fallback_results:
                        if app_obj not in results_list:
                            results_list.append(app_obj)
                print(f"API DEBUG 6b: results_list after fallback: {[app.name for app in results_list]}")


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
            # Import App model here for final queryset construction
            queryset = App.objects.filter(id__in=ordered_ids).order_by(preserved)

            print(f"API DEBUG 8: Final QuerySet count: {queryset.count()}")
            return queryset

    class AppSuggestionsAPIView(generics.ListAPIView):
        """
        API endpoint for providing app name suggestions using TF-IDF similarity.
        """
        # Import AppSerializer here, as it's directly used by serializer_class
        from .serializers import AppSerializer
        serializer_class = AppSerializer
        permission_classes = [AllowAny]
        pagination_class = None

        def get_queryset(self):
            query = self.request.query_params.get('q', '').strip()
            print(f"\n--- API DEBUG: Suggestion Query: '{query}' ---")

            if query:
                # Import App model here for database queries
                from .models import App
                if len(query) <= 4:
                    print(f"API DEBUG: Using icontains for short suggestion query: '{query}'")
                    return App.objects.filter(name__icontains=query).order_by('name')[:10]
                else:
                    # --- CRITICAL CHANGE: Use imported global tfidf_vectorizer and tfidf_matrix ---
                    if tfidf_vectorizer is not None and tfidf_matrix is not None:
                        print(f"API DEBUG: Using TF-IDF for long suggestion query: '{query}'")
                        try:
                            query_vec = tfidf_vectorizer.transform([query])
                            cosine_similarities = linear_kernel(query_vec, tfidf_matrix).flatten()

                            # Fetch all App objects again, ordered by PK for consistency with TF-IDF matrix
                            all_apps = list(App.objects.all().order_by('pk'))

                            similar_apps_with_scores = []
                            for i, sim in enumerate(cosine_similarities):
                                if i < len(all_apps) and sim >= 0.001:
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
            queryset_or_list = self.get_queryset()
            if isinstance(queryset_or_list, list):
                suggestions = [app.name for app in queryset_or_list]
            else:
                suggestions = [app.name for app in queryset_or_list]
            return Response({'suggestions': suggestions})

    class AppDetailAPIView(generics.RetrieveAPIView):
        """
        API endpoint for retrieving a single app's details and its reviews.
        """
        # Import App model and AppSerializer here
        from .models import App
        from .serializers import AppSerializer
        queryset = App.objects.all()  # This queryset is fine at module level for RetrieveAPIView
        serializer_class = AppSerializer
        lookup_field = 'pk'
        permission_classes = [AllowAny]

        def retrieve(self, request, *args, **kwargs):
            instance = self.get_object()
            serializer = self.get_serializer(instance)

            # Import Review model and ReviewSerializer here
            from .models import Review
            from .serializers import ReviewSerializer
            # Get reviews for this app
            if request.user.is_authenticated:
                reviews = instance.reviews.filter(Q(is_approved=True) | Q(user=request.user)).order_by('-created_at')
            else:
                reviews = instance.reviews.filter(is_approved=True).order_by('-created_at')

            review_serializer = ReviewSerializer(reviews, many=True)

            data = serializer.data
            data['reviews'] = review_serializer.data
            return Response(data)

    class ReviewCreateAPIView(generics.CreateAPIView):
        """
        API endpoint for users to submit new reviews.
        Requires authentication.
        """
        # Import Review model and ReviewCreateSerializer here
        from .models import Review, App  # App is needed for get_object_or_404
        from .serializers import ReviewCreateSerializer
        queryset = Review.objects.all()  # This queryset is fine at module level for CreateAPIView
        serializer_class = ReviewCreateSerializer
        permission_classes = [IsAuthenticated]

        def perform_create(self, serializer):
            app_id = self.kwargs.get('app_id')
            app = get_object_or_404(App, id=app_id)
            serializer.save(app=app, user=self.request.user)

    class SupervisorReviewListAPIView(generics.ListAPIView):
        """
        API endpoint for supervisors to view pending reviews.
        Requires supervisor permissions.
        """
        # Import Review model and ReviewSerializer here
        from .models import Review
        from .serializers import ReviewSerializer
        queryset = Review.objects.filter(is_approved=False).order_by(
            '-created_at')  # This queryset is fine at module level
        serializer_class = ReviewSerializer
        permission_classes = [IsAuthenticated, IsAdminUser]
        pagination_class = PageNumberPagination

    class ApproveRejectReviewAPIView(APIView):
        """
        API endpoint for supervisors to approve or reject reviews.
        Requires supervisor permissions.
        """
        # Import Review model here
        from .models import Review
        permission_classes = [IsAuthenticated, IsAdminUser]

        def post(self, request, review_id, format=None):
            review = get_object_or_404(Review, id=review_id)
            action = request.data.get('action')
            print(action)
            if action == 'approve':
                review.is_approved = True
                review.save()
                return Response({"message": "Review approved successfully."}, status=status.HTTP_200_OK)
            elif action == 'reject':
                review.delete()
                return Response({"message": "Review rejected and removed."},
                                status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({"error": "Invalid action. Must be 'approve' or 'reject'."},
                                status=status.HTTP_400_BAD_REQUEST)

    class RegisterUserAPIView(generics.CreateAPIView):
        """
        API endpoint for user registration.
        """
        # Import User model and UserSerializer here
        from django.contrib.auth.models import User
        from rest_framework.authtoken.models import Token
        from .serializers import UserSerializer
        queryset = User.objects.all()  # This queryset is fine at module level
        serializer_class = UserSerializer
        permission_classes = [AllowAny]

        def perform_create(self, serializer):
            user = serializer.save()
            user.set_password(self.request.data.get('password'))
            user.save()
            Token.objects.create(user=user)

    class CustomAuthToken(ObtainAuthToken):
        """
        Custom login endpoint to return user details along with the token.
        """
        # Import Token here
        from rest_framework.authtoken.models import Token
        def post(self, request, *args, **kwargs):
            serializer = self.serializer_class(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user_id': user.pk,
                'username': user.username,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            })
    def list(self, request, *args, **kwargs):
        queryset_or_list = self.get_queryset()
        if isinstance(queryset_or_list, list):
            suggestions = [app.name for app in queryset_or_list]
        else:
            suggestions = [app.name for app in queryset_or_list]
        return Response({'suggestions': suggestions})


class AppDetailAPIView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving a single app's details and its reviews.
    """
    # Import App model and AppSerializer here
    from .models import App
    from .serializers import AppSerializer
    queryset = App.objects.all()
    serializer_class = AppSerializer
    lookup_field = 'pk'
    permission_classes = [AllowAny]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        # Import Review model and ReviewSerializer here
        from .models import Review
        from .serializers import ReviewSerializer
        # Get reviews for this app
        if request.user.is_authenticated:
            reviews = instance.reviews.filter(Q(is_approved=True) | Q(user=request.user)).order_by('-created_at')
        else:
            reviews = instance.reviews.filter(is_approved=True).order_by('-created_at')

        review_serializer = ReviewSerializer(reviews, many=True)

        data = serializer.data
        data['reviews'] = review_serializer.data
        return Response(data)


class ReviewCreateAPIView(generics.CreateAPIView):
    """
    API endpoint for users to submit new reviews.
    Requires authentication.
    """
    # Import Review model and ReviewCreateSerializer here
    from .models import Review, App # App is needed for get_object_or_404
    from .serializers import ReviewCreateSerializer
    queryset = Review.objects.all()
    serializer_class = ReviewCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        app_id = self.kwargs.get('app_id')
        app = get_object_or_404(App, id=app_id)
        serializer.save(app=app, user=self.request.user)


class SupervisorReviewListAPIView(generics.ListAPIView):
    """
    API endpoint for supervisors to view pending reviews.
    Requires supervisor permissions.
    """
    # Import Review model and ReviewSerializer here
    from .models import Review
    from .serializers import ReviewSerializer
    queryset = Review.objects.filter(is_approved=False).order_by('-created_at')
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = PageNumberPagination


class ApproveRejectReviewAPIView(APIView):
    """
    API endpoint for supervisors to approve or reject reviews.
    Requires supervisor permissions.
    """
    # Import Review model here
    from .models import Review
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, review_id, format=None):
        review = get_object_or_404(Review, id=review_id)
        action = request.data.get('action')
        print(action)
        if action == 'approve':
            review.is_approved = True
            review.save()
            return Response({"message": "Review approved successfully."}, status=status.HTTP_200_OK)
        elif action == 'reject':
            review.delete()
            return Response({"message": "Review rejected and removed."},
                            status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({"error": "Invalid action. Must be 'approve' or 'reject'."},
                            status=status.HTTP_400_BAD_REQUEST)


class RegisterUserAPIView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    """
    # Import User model and UserSerializer here
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from .serializers import UserSerializer
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        user.set_password(self.request.data.get('password'))
        user.save()
        Token.objects.create(user=user)


class CustomAuthToken(ObtainAuthToken):
    """
    Custom login endpoint to return user details along with the token.
    """
    # Import Token here
    from rest_framework.authtoken.models import Token
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        })