# core/management/commands/initialize_tfidf.py

from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db.utils import OperationalError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
import pickle # <--- ADD THIS IMPORT
import os # <--- ADD THIS IMPORT
from django.conf import settings # <--- ADD THIS IMPORT

# Import the global variables from core.apps (where they are declared as None)
# Note: These are for reference, the actual persistence is via pickle files.
from core.apps import tfidf_vectorizer, tfidf_matrix # This is where the global vars live


# Define paths for the pickled model files
# It's good practice to store these in a dedicated directory, e.g., 'data/' or 'models/'
# relative to your project's BASE_DIR.
# Ensure this directory exists or create it.
MODEL_DIR = os.path.join(settings.BASE_DIR, 'data') # Or 'models'
TFIDF_VECTORIZER_PATH = os.path.join(MODEL_DIR, 'tfidf_vectorizer.pkl')
TFIDF_MATRIX_PATH = os.path.join(MODEL_DIR, 'tfidf_matrix.pkl')


class Command(BaseCommand):
    help = 'Initializes the global TF-IDF model by loading app names from the database and saving it to disk.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting TF-IDF Model Initialization ---"))

        # Ensure the model directory exists
        os.makedirs(MODEL_DIR, exist_ok=True)

        try:
            # Dynamically get the App model to avoid circular imports at module level
            App = apps.get_model('core', 'App')

            # Fetch app names, ensuring consistent order for the TF-IDF matrix
            app_names = [app.name for app in App.objects.all().order_by('pk')] # Added .order_by('pk') for consistency

            if app_names:
                self.stdout.write("Training TF-IDF vectorizer and building matrix...")
                vectorizer = TfidfVectorizer().fit(app_names)
                matrix = vectorizer.transform(app_names)

                # --- CRITICAL CHANGE: Save the trained model and matrix to disk ---
                with open(TFIDF_VECTORIZER_PATH, 'wb') as f:
                    pickle.dump(vectorizer, f)
                with open(TFIDF_MATRIX_PATH, 'wb') as f:
                    pickle.dump(matrix, f)

                self.stdout.write(self.style.SUCCESS(f"TF-IDF model initialized and saved to {MODEL_DIR} successfully."))
            else:
                # If no app names, ensure no old model files are left behind
                if os.path.exists(TFIDF_VECTORIZER_PATH):
                    os.remove(TFIDF_VECTORIZER_PATH)
                if os.path.exists(TFIDF_MATRIX_PATH):
                    os.remove(TFIDF_MATRIX_PATH)
                self.stdout.write(self.style.WARNING("No app names found in the database. TF-IDF model not initialized and old files removed."))

        except OperationalError as e:
            raise CommandError(
                self.style.ERROR(f"Database error during TF-IDF initialization: {e}\n"
                                 "Please ensure migrations are applied (python manage.py migrate) "
                                 "and the database is accessible before running this command.")
            )
        except Exception as e:
            raise CommandError(self.style.ERROR(f"An unexpected error occurred during TF-IDF initialization: {e}"))