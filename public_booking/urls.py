
from django.urls import path
from .views import homepage, search_results, initiate_booking, payment_page, confirm_payment, get_flights_for_date, airport_search
from . import views
urlpatterns = [
    path('', homepage, name='public_home'),
    path('about/', views.about_us, name='about_us'),
    path('results/', search_results, name='search_results'),
    path('api/flights-by-date/', get_flights_for_date, name='get_flights_for_date'),
    path('airport-search/', airport_search, name='airport_search'),
    path('booking-request/', views.booking_request, name='booking_request'),
    path('initiate-booking/', initiate_booking, name='initiate_booking'),
    path('payment/<int:booking_id>/', payment_page, name='payment_page'),
    path('confirm-payment/<int:booking_id>/', confirm_payment, name='confirm_payment'),
    path('flights/', views.flights, name='flights'),
    path('visas/', views.visas, name='visas'),
    path('holidays/', views.holidays, name='holidays'),
    path('umrah-packages/', views.umrah_packages, name='umrah_packages'),
    path('partner/', views.partner, name='partner'),
]
