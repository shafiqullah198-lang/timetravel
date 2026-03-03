from amadeus import Client
from django.conf import settings

amadeus = Client(
    client_id=settings.AMADEUS_CLIENT_ID,
    client_secret=settings.AMADEUS_CLIENT_SECRET
)
