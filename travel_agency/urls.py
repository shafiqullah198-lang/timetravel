
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', include('dashboard.urls')),
    path('', include('public_booking.urls')),
    path('accounts/', include('accounts.urls')),
    path("tickets/", include("tickets.urls")),
    path("auth/", include("users.urls")),

]

