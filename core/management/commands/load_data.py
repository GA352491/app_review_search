# app_review_search/core/management/commands/load_data.py

import csv
import os
from django.core.management.base import BaseCommand
from core.models import App, Review

class Command(BaseCommand):
    help = 'Loads data from googlestore.csv and googleplaystore_user_reviews.csv into the database.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting data loading...'))

        # Define file paths relative to the project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        google_store_csv_path = os.path.join(project_root, 'googleplaystore.csv')
        user_reviews_csv_path = os.path.join(project_root, 'googleplaystore_user_reviews.csv')

        self.stdout.write(f"Looking for googlestore.csv at: {google_store_csv_path}")
        self.stdout.write(f"Looking for googleplaystore_user_reviews.csv at: {user_reviews_csv_path}")

        # Clear existing data (optional, for development)
        self.stdout.write('Clearing existing App and Review data...')
        Review.objects.all().delete()
        App.objects.all().delete()
        self.stdout.write('Existing data cleared.')

        # Load Apps from googlestore.csv
        try:
            with open(google_store_csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                apps_to_create = []
                for row in reader:
                    # Clean and validate data as needed
                    try:
                        app_name = row.get('App')
                        if not app_name:
                            continue # Skip rows with no app name

                        # Handle 'Varies with device' or non-numeric values for 'Reviews' and 'Installs'
                        reviews_count = row.get('Reviews', '0').replace('M', '000000').replace('k', '000').replace(',', '')
                        installs_count = row.get('Installs', '0+').replace('+', '').replace(',', '')

                        try:
                            reviews_count = int(float(reviews_count)) # Convert to float first, then int
                        except ValueError:
                            reviews_count = 0

                        try:
                            installs_count = int(float(installs_count))
                        except ValueError:
                            installs_count = 0

                        # Handle 'Rating'
                        try:
                            rating = float(row.get('Rating', '0'))
                        except ValueError:
                            rating = 0.0

                        apps_to_create.append(
                            App(
                                name=app_name,
                                category=row.get('Category', ''),
                                rating=rating,
                                reviews_count=reviews_count,
                                size=row.get('Size', ''),
                                installs=installs_count,
                                type=row.get('Type', ''),
                                price=row.get('Price', ''),
                                content_rating=row.get('Content Rating', ''),
                                genres=row.get('Genres', ''),
                                last_updated=row.get('Last Updated', ''),
                                current_ver=row.get('Current Ver', ''),
                                android_ver=row.get('Android Ver', '')
                            )
                        )
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing app row: {row}. Error: {e}"))
                App.objects.bulk_create(apps_to_create, ignore_conflicts=True) # ignore_conflicts added
                self.stdout.write(self.style.SUCCESS(f'Successfully loaded {len(apps_to_create)} apps.'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Error: googlestore.csv not found at {google_store_csv_path}'))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error loading googlestore.csv: {e}'))
            return

        # Load Reviews from googleplaystore_user_reviews.csv
        app_name_to_id = {app.name: app.id for app in App.objects.all()}
        try:
            with open(user_reviews_csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                reviews_to_create = []
                for row in reader:
                    try:
                        app_name = row.get('App')
                        translated_review = row.get('Translated_Review')
                        sentiment = row.get('Sentiment')
                        sentiment_polarity = row.get('Sentiment_Polarity')
                        sentiment_subjectivity = row.get('Sentiment_Subjectivity')

                        app_id = app_name_to_id.get(app_name)
                        if app_id and translated_review: # Only add reviews if app exists and review text is present
                            reviews_to_create.append(
                                Review(
                                    app_id=app_id,
                                    translated_review=translated_review,
                                    sentiment=sentiment,
                                    sentiment_polarity=float(sentiment_polarity) if sentiment_polarity else 0.0,
                                    sentiment_subjectivity=float(sentiment_subjectivity) if sentiment_subjectivity else 0.0
                                )
                            )
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error processing review row: {row}. Error: {e}"))
                Review.objects.bulk_create(reviews_to_create, ignore_conflicts=True)
                self.stdout.write(self.style.SUCCESS(f'Successfully loaded {len(reviews_to_create)} reviews.'))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'Error: googleplaystore_user_reviews.csv not found at {user_reviews_csv_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error loading googleplaystore_user_reviews.csv: {e}'))

        self.stdout.write(self.style.SUCCESS('Data loading complete.'))