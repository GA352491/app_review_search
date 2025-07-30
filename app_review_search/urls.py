# app_review_project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views  # Import Django's built-in auth views
from core import views as core_views  # Import your core views for register/submit_review
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),

    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),  # Redirect to home after logout
    path('register/', core_views.register, name='register'),  # Custom registration view
    path('api/', include('core.api_urls')),  # <--- ADD THIS LINE FOR YOUR API ENDPOINTS
    # DRF Spectacular API Documentation URLs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),  # Your API schema in YAML/JSON
    # Optional: If you want to customize the URL name for the schema
    # path('api/schema.json', SpectacularAPIView.as_view(), name='schema-json'),

    # Swagger UI (interactive API documentation)
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Redoc UI (another popular API documentation UI)
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

]
