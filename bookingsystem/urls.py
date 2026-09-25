from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from booking.views import CustomLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('booking.urls')),
    path('api/login/', CustomLoginView.as_view(), name='login'),
    path('api/login/refresh/', TokenRefreshView.as_view(), name='login_refresh'),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]