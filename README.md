 
Create a full stack Django application with the following features.
 
It should be a search application like google that enables people to search for an app and see all the reviews.
 
The search should be based on algorithm for text similarity. Upon typing the first 3 characters the user should get suggestions. Upon hitting enter the user should get a list of results. Each result would have data from googlestore.csv. Upon click it should show the list of reviews from the googleplaystore_user_reviews.csv.
 
The user should be able to create a new review and send it for approval to his supervisor
 
A second user(i.e. supervisor) should be able to login and see all the reviews for approval and have the ability to approve this.
 
Please find attached a dataset downloaded from Kaggle that has details from the google play store apps.
 

# App Review Search Application (Backend)

This is the backend component of a full-stack web application that allows users to search for mobile applications, view their details, submit reviews, and provides a supervisor dashboard for review moderation. The search functionality leverages a hybrid approach combining exact matching, TF-IDF (Term Frequency-Inverse Document Frequency) for semantic similarity, and substring matching for robustness.

## Features

User Authentication:** Register, Login, Logout ( endpoints).
* **App Search API:**
    * Search apps by name.
    * Hybrid search algorithm:
        * Prioritizes exact matches.
        * Uses TF-IDF for semantic similarity for more relevant results.
        * Falls back to `icontains` (substring match) for robustness if TF-IDF yields no results or for short queries.
* **Search Suggestions API (Autosuggest):** Provides real-time suggestions as the user types.
* **App Details API:** Retrieve detailed information about each app, including its category, rating, installs, and reviews.
* **Review Submission API:** Authenticated users can submit reviews for apps.
* **Review Moderation API (Supervisor Dashboard):**
    * API endpoints for staff/superusers to view pending reviews.
    * API endpoints to approve or reject reviews.
* **Pagination:** Search results and pending reviews are paginated.
* **RESTful API:** A comprehensive API for interacting with app and review data.

## Technologies Used

### Backend (Django)

* **Python:** 3.9+ (Python 3.13 used in development environment)
* **Django:** Web framework
* **Django REST Framework (DRF):** For building the RESTful API
* **Scikit-learn:** For TF-IDF vectorization and cosine similarity calculation
* **Pillow:** For image processing (if app icons were handled, otherwise a common dependency)
* **`django-cors-headers`:** For handling Cross-Origin Resource Sharing
* **`rest_framework.authtoken`:** For API token authentication

### Database

* **SQLite:** Default for development (configured as `db.sqlite3`). Can be easily switched to PostgreSQL, MySQL, etc., for production.

## Setup and Running the Application

Follow these steps to get the backend application up and running on your local machine.

### Prerequisites

* **Python 3.9+** (ensure `python` command points to a compatible version or use `python3`).
* **pip** (Python package installer).
* **Git** (for cloning the repository).

### 1. Clone the Repository

Navigate to the directory where you want to store your project and clone the repository:

```bash
git clone <your-repository-url>
cd <your-repository-name> # e.g., cd app_review_search
````

### 2\. Backend Setup (Django)

Navigate into the Django project directory (where `manage.py` is located):

```bash
cd app_review_search # Or whatever your Django project folder is named
```

#### a. Create and Activate Virtual Environment

It's highly recommended to use a virtual environment to manage dependencies:

```bash
python -m venv .venv
source .venv/bin/activate # On Windows: .venv\Scripts\activate
```

#### b. Install Python Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt # Make sure you have a requirements.txt file in your Django project root
# If you don't have requirements.txt, you'll need to install them manually:
# pip install Django djangorestframework scikit-learn numpy scipy django-cors-headers Pillow
```

#### c. Database Migrations

Apply the database migrations to create the necessary tables:

```bash
python manage.py migrate
```

#### d. Create a Superuser

Create a superuser account to access the Django admin panel and for testing supervisor functionalities:

```bash
python manage.py createsuperuser
```

Follow the prompts to set a username, email, and password.

#### e. Load Sample Data

Load the app and review data from the provided CSV files into your database. Ensure `googlestore.csv` and `googleplaystore_user_reviews.csv` are in your Django project's root directory (same as `manage.py`).

```bash
python manage.py load_data # Or whatever your data loading command is named
```

#### f. Initialize TF-IDF Model

This step trains the TF-IDF model on your loaded app names and saves it to disk. This needs to be run once after data loading, and re-run if app names in the database change.

```bash
python manage.py initialize_tfidf
```

### 3\. Running the Backend Application

1.  Ensure your **Django backend** is running in one terminal:

    ```bash
    cd app_review_search
    source .venv/bin/activate
    python manage.py runserver
    ```

    *(You should see "TF-IDF model loaded successfully from data/" during startup.)*

The backend API will be accessible at `http://127.0.0.1:8000/api/` (or your configured host/port).

## Application Flow Explanation

### Backend (Django)

The Django backend serves as the API for the application, handling data storage, business logic, authentication, and search processing.

  * **Models (`core/models.py`):** Defines the `App` and `Review` data structures, including relationships.
  * **Serializers (`core/serializers.py`):** Converts Django model instances into JSON format for the API and vice-versa.
  * **Views (`core/views.py`):** Handles traditional web page rendering (e.g., home, search results, app detail, registration, review submission, supervisor dashboard).
      * The `AppSearchResultsView` and `search_suggestions` functions implement the hybrid search logic for the server-rendered views.
  * **API Views (`core/api_views.py`):** Provides RESTful endpoints for the frontend.
      * `AppListAPIView`: For fetching and searching apps via API.
      * `AppSuggestionsAPIView`: For providing search suggestions via API.
      * `AppDetailAPIView`: For retrieving single app details and its reviews.
      * `ReviewCreateAPIView`: For submitting new reviews.
      * `SupervisorReviewListAPIView`, `ApproveRejectReviewAPIView`: For review moderation by supervisors.
      * `RegisterUserAPIView`, `CustomAuthToken`: For user registration and login (API token generation).
  * **TF-IDF Model Initialization (`core/apps.py` & `core/management/commands/initialize_tfidf.py`):**
      * The `initialize_tfidf` management command is responsible for fetching all app names from the database, training the `TfidfVectorizer`, building the `tfidf_matrix`, and then **persisting (pickling)** these two objects to `.pkl` files in the `data/` directory.
      * The `CoreConfig.ready()` method (in `core/apps.py`) is executed once when the Django server starts. Its role is to **load** these pickled TF-IDF model files from disk into global variables (`tfidf_vectorizer`, `tfidf_matrix`), making them available to all parts of the application without re-training on every request.

### Search Mechanism (Hybrid Approach)

The search functionality is a core part of the application, designed for both relevance and robustness:

1.  **Exact Match Priority:** When a user submits a query, the system first checks for an exact, case-insensitive match with any app name. If found, this app is prioritized at the very top of the results.
2.  **TF-IDF Similarity Search:** For more nuanced queries, TF-IDF is used.
      * The user's query is transformed into a TF-IDF vector.
      * Cosine similarity is calculated between the query vector and the TF-IDF vectors of all app names in the pre-built `tfidf_matrix`.
      * Apps with a similarity score above a certain threshold (e.g., `0.001` for main search, `0.1` for suggestions) are considered relevant.
      * These results are sorted by their similarity score (highest first) and added to the results list.
3.  **`icontains` Fallback:** If the TF-IDF search doesn't yield enough results (or any at all), or for very short queries (e.g., 3-4 characters), a simple `icontains` (case-insensitive substring match) query is performed. This acts as a robust fallback to ensure some results are returned even for typos or less semantically rich queries.
4.  **Result Aggregation and Ordering:** The results from exact match, TF-IDF, and `icontains` are combined, ensuring no duplicates, and then ordered according to this priority before being paginated.

### Review Moderation Flow

1.  **User Submits Review:** An authenticated user submits a review for an app. The `is_approved` field for this new review is set to `False`.
2.  **Supervisor Dashboard:** Staff or superuser accounts can log in and access the supervisor dashboard (via API or traditional view). This fetches only reviews where `is_approved` is `False`.
3.  **Approve/Reject:** From the dashboard, supervisors can choose to "Approve" a review (setting `is_approved` to `True`) or "Reject" it (deleting the review).
  