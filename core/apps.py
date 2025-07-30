# core/apps.py

from django.apps import AppConfig
from django.db.utils import OperationalError
import pickle # <--- ADD THIS IMPORT
import os # <--- ADD THIS IMPORT
from django.conf import settings # <--- ADD THIS IMPORT

# Declare global variables, but initialize them to None.
# These will be populated by loading from pickle files in ready().
# core/apps.py

# ... (existing imports) ...

# Declare global variables, but initialize them to None.
tfidf_vectorizer = None
tfidf_matrix = None

# Define paths for the pickled model files (must match paths in management command)
# Ensure settings.BASE_DIR is correctly imported and used
from django.conf import settings
import os

MODEL_DIR = os.path.join(settings.BASE_DIR, 'data')
TFIDF_VECTORIZER_PATH = os.path.join(MODEL_DIR, 'tfidf_vectorizer.pkl')
TFIDF_MATRIX_PATH = os.path.join(MODEL_DIR, 'tfidf_matrix.pkl')


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        global tfidf_vectorizer, tfidf_matrix

        print(f"\n--- AppConfig.ready() called. Checking for TF-IDF model files... ---")
        print(f"Expected MODEL_DIR: {MODEL_DIR}")
        print(f"Expected TFIDF_VECTORIZER_PATH: {TFIDF_VECTORIZER_PATH}")
        print(f"Expected TFIDF_MATRIX_PATH: {TFIDF_MATRIX_PATH}")
        print(f"Does MODEL_DIR exist? {os.path.exists(MODEL_DIR)}")
        print(f"Does TFIDF_VECTORIZER_PATH exist? {os.path.exists(TFIDF_VECTORIZER_PATH)}")
        print(f"Does TFIDF_MATRIX_PATH exist? {os.path.exists(TFIDF_MATRIX_PATH)}")


        try:
            if os.path.exists(TFIDF_VECTORIZER_PATH) and os.path.exists(TFIDF_MATRIX_PATH):
                with open(TFIDF_VECTORIZER_PATH, 'rb') as f:
                    tfidf_vectorizer = pickle.load(f)
                with open(TFIDF_MATRIX_PATH, 'rb') as f:
                    tfidf_matrix = pickle.load(f)
                print(f"TF-IDF model loaded successfully from {MODEL_DIR}.")
            else:
                print(f"WARNING: TF-IDF model files NOT FOUND in {MODEL_DIR}. Please run 'python manage.py initialize_tfidf' to create them.")
                tfidf_vectorizer = None
                tfidf_matrix = None
        except Exception as e:
            print(f"ERROR: Failed to load TF-IDF model from disk: {e}")
            tfidf_vectorizer = None
            tfidf_matrix = None