# core/apps.py

from django.apps import AppConfig
from django.db.utils import OperationalError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# --- CRITICAL CHANGE: Declare global variables here, and initialize them within ready() ---
# They will be populated when Django's AppConfig.ready() method runs.
tfidf_vectorizer = None
tfidf_matrix = None


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """
        This method is called once when Django starts up, after all apps are loaded
        and the database connection is established.
        """
        # Import models here to avoid circular imports, as models might not be ready yet
        from .models import App

        global tfidf_vectorizer, tfidf_matrix # Declare intent to modify global variables

        print("\n--- Initializing TF-IDF model via AppConfig.ready() ---")
        try:
            app_names = [app.name for app in App.objects.all()]

            if app_names:
                tfidf_vectorizer = TfidfVectorizer().fit(app_names)
                tfidf_matrix = tfidf_vectorizer.transform(app_names)
                print("TF-IDF model initialized successfully.")
            else:
                tfidf_vectorizer = None
                tfidf_matrix = None
                print("No app names found for TF-IDF initialization.")
        except OperationalError as e:
            # This handles cases where `ready()` might be called during initial `makemigrations`
            # or `migrate` before tables are fully created.
            print(f"WARNING: Database tables not ready for TF-IDF initialization: {e}")
            tfidf_vectorizer = None
            tfidf_matrix = None
        except Exception as e:
            print(f"ERROR: Failed to initialize TF-IDF model: {e}")
            tfidf_vectorizer = None
            tfidf_matrix = None