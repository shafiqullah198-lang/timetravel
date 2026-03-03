
from django.shortcuts import render, redirect, get_object_or_404
from .models import Booking, PublicPageContent
from accounts.models import Customer, Supplier, CompanySetting
from tickets.models import Ticket
from django.core.mail import send_mail
from .services.amadeus_service import AmadeusService
from django.http import JsonResponse
from django.conf import settings
from urllib.parse import quote_plus
import re

from amadeus import ResponseError
from tickets.services.amadeus_client import amadeus

CURATED_LOCATIONS = [
    {"name": "Islamabad International Airport", "iataCode": "ISB", "cityName": "Islamabad", "countryCode": "PK"},
    {"name": "Jinnah International Airport", "iataCode": "KHI", "cityName": "Karachi", "countryCode": "PK"},
    {"name": "Allama Iqbal International Airport", "iataCode": "LHE", "cityName": "Lahore", "countryCode": "PK"},
    {"name": "Bacha Khan International Airport", "iataCode": "PEW", "cityName": "Peshawar", "countryCode": "PK"},
    {"name": "Quetta International Airport", "iataCode": "UET", "cityName": "Quetta", "countryCode": "PK"},
    {"name": "Multan International Airport", "iataCode": "MUX", "cityName": "Multan", "countryCode": "PK"},
    {"name": "Sialkot International Airport", "iataCode": "SKT", "cityName": "Sialkot", "countryCode": "PK"},
    {"name": "King Abdulaziz International Airport", "iataCode": "JED", "cityName": "Jeddah", "countryCode": "SA"},
    {"name": "King Khalid International Airport", "iataCode": "RUH", "cityName": "Riyadh", "countryCode": "SA"},
    {"name": "King Fahd International Airport", "iataCode": "DMM", "cityName": "Dammam", "countryCode": "SA"},
    {"name": "Prince Mohammad Bin Abdulaziz International Airport", "iataCode": "MED", "cityName": "Madinah", "countryCode": "SA"},
    {"name": "Dubai International Airport", "iataCode": "DXB", "cityName": "Dubai", "countryCode": "AE"},
    {"name": "Abu Dhabi International Airport", "iataCode": "AUH", "cityName": "Abu Dhabi", "countryCode": "AE"},
    {"name": "Sharjah International Airport", "iataCode": "SHJ", "cityName": "Sharjah", "countryCode": "AE"},
    {"name": "Hamad International Airport", "iataCode": "DOH", "cityName": "Doha", "countryCode": "QA"},
]

COUNTRY_ALIASES = {
    "ksa": "SA",
    "saudi": "SA",
    "saudi arabia": "SA",
    "pakistan": "PK",
    "uae": "AE",
    "dubai": "AE",
    "qatar": "QA",
}

def homepage(request):
    return render(request, 'public_booking/home.html')


def _render_public_page(request, page_key, fallback_title, fallback_content):
    page = PublicPageContent.objects.filter(page_key=page_key, is_active=True).first()
    context = {
        "title": page.title if page and page.title else fallback_title,
        "content": page.content if page and page.content else fallback_content,
    }
    return render(request, "public_booking/content_page.html", context)


def test_amadeus(request):
    try:
        response = amadeus.reference_data.locations.get(
            keyword="Lahore",
            subType="AIRPORT"
        )
        return JsonResponse(response.data, safe=False)
    except ResponseError as error:
        return JsonResponse({"error": str(error)})


def airport_search(request):
    keyword = (request.GET.get("keyword") or "").strip()

    if not keyword:
        return JsonResponse(_default_curated_locations(), safe=False)

    try:
        response = amadeus.reference_data.locations.get(
            keyword=keyword,
            subType="CITY,AIRPORT"
        )
        api_data = response.data or []
        curated_data = _match_curated_locations(keyword)

        merged = []
        seen_iata = set()
        for item in curated_data + api_data:
            iata = item.get("iataCode")
            if not iata or iata in seen_iata:
                continue
            seen_iata.add(iata)
            merged.append(item)

        return JsonResponse(merged[:15], safe=False)

    except ResponseError as error:
        fallback = _match_curated_locations(keyword)
        if fallback:
            return JsonResponse(fallback[:15], safe=False)
        return JsonResponse({"error": str(error)})

# ---- Remaining Booking Flow Same As Phase 10 ----

def initiate_booking(request):
    if request.method == "POST":
        booking = Booking.objects.create(
            full_name=request.POST['full_name'],
            email=request.POST['email'],
            phone=request.POST['phone'],
            from_city=request.POST['from_city'],
            to_city=request.POST['to_city'],
            departure_date=request.POST['departure_date'],
            airline=request.POST['airline'],
            price=request.POST['price'],
        )
        return redirect(f"/payment/{booking.id}/")


def booking_request(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        passport_number = request.POST.get("passport_number", "").strip()
        passport_expiry = request.POST.get("passport_expiry") or None
        nationality = request.POST.get("nationality", "").strip()
        date_of_birth = request.POST.get("date_of_birth") or None

        from_city = request.POST.get("from_city", "").strip()
        to_city = request.POST.get("to_city", "").strip()
        departure_date = request.POST.get("departure_date", "").strip()
        airline = request.POST.get("airline", "").strip()
        fare_type = request.POST.get("fare_type", "").strip()
        departure_time = request.POST.get("departure_time", "").strip()
        arrival_time = request.POST.get("arrival_time", "").strip()
        stop_label = request.POST.get("stop_label", "").strip()
        price = request.POST.get("price", "0").replace(",", "").strip() or "0"

        booking = Booking.objects.create(
            full_name=full_name,
            email=email,
            phone=phone,
            from_city=from_city,
            to_city=to_city,
            departure_date=departure_date,
            airline=airline,
            fare_type=fare_type,
            departure_time=departure_time,
            arrival_time=arrival_time,
            stop_label=stop_label,
            price=price,
            passport_number=passport_number,
            passport_expiry=passport_expiry,
            nationality=nationality,
            date_of_birth=date_of_birth,
            status="pending",
        )

        admin_message = (
            "New Flight Booking Request\n"
            "-------------------------\n"
            f"PNR: {booking.pnr}\n"
            "Customer Details\n"
            f"Name: {full_name or '-'}\n"
            f"Phone: {phone or '-'}\n"
            f"Email: {email or '-'}\n"
            f"Passport Number: {passport_number or '-'}\n"
            f"Passport Expiry: {passport_expiry or '-'}\n"
            f"Nationality: {nationality or '-'}\n"
            f"Date of Birth: {date_of_birth or '-'}\n"
            "\n"
            "Flight Details\n"
            f"Route: {from_city or '-'} -> {to_city or '-'}\n"
            f"Departure Date: {departure_date or '-'}\n"
            f"Airline: {airline or '-'}\n"
            f"Departure: {departure_time or '-'}\n"
            f"Arrival: {arrival_time or '-'}\n"
            f"Stops: {stop_label or '-'}\n"
            f"Fare Type: {fare_type or '-'}\n"
            f"Price: PKR {booking.price}\n"
        )

        send_mail(
            subject=f"New Booking Request - {booking.pnr}",
            message=admin_message,
            from_email="noreply@travel.com",
            recipient_list=["98shahidkhan@gmail.com"],
            fail_silently=True,
        )

        raw_wa_number = str(getattr(settings, "ADMIN_WHATSAPP_NUMBER", "923402125530"))
        wa_number = re.sub(r"\D", "", raw_wa_number)
        wa_url = f"https://wa.me/{wa_number}?text={quote_plus(admin_message)}"

        return render(
            request,
            "public_booking/booking_request.html",
            {
                "success": True,
                "wa_url": wa_url,
                "booking": booking,
            },
        )

    context = {
        "from_city": request.GET.get("from_city", ""),
        "to_city": request.GET.get("to_city", ""),
        "departure_date": request.GET.get("departure_date", ""),
        "airline": request.GET.get("airline", ""),
        "fare_type": request.GET.get("fare_type", ""),
        "price": request.GET.get("price", "0"),
        "departure_time": request.GET.get("departure_time", ""),
        "arrival_time": request.GET.get("arrival_time", ""),
        "stop_label": request.GET.get("stop_label", ""),
    }
    return render(request, "public_booking/booking_request.html", context)

def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'public_booking/payment.html', {'booking': booking})

def confirm_payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    booking.status = 'paid'
    booking.save()

    customer, _ = Customer.objects.get_or_create(
        name=booking.full_name,
        phone=booking.phone
    )

    supplier = Supplier.objects.first()
    if supplier is None:
        supplier = Supplier.objects.create(
            company_name="Default Supplier",
            contact_person="Operations Team",
            phone="0000000000",
            email="ops@example.com",
        )

    margin_setting = CompanySetting.objects.first()
    margin = margin_setting.default_margin if margin_setting else 3000

    cost_price = max(0, float(booking.price) - float(margin))

    Ticket.objects.create(
        customer=customer,
        supplier=supplier,
        airline=booking.airline,
        pnr=booking.pnr,
        ticket_number=booking.pnr,
        travel_from=booking.from_city,
        travel_to=booking.to_city,
        travel_date=booking.departure_date,
        cost_price=cost_price,
        selling_price=booking.price,
        customer_paid=booking.price,
        supplier_paid=0,
        payment_mode="online",
        source_channel="public",
    )

    send_mail(
        subject="Booking Confirmation",
        message=f"Your booking {booking.pnr} is confirmed.",
        from_email="noreply@travel.com",
        recipient_list=[booking.email],
        fail_silently=True,
    )

    return redirect('/dashboard/')

def flights(request):
    return redirect("public_home")

def visas(request):
    return _render_public_page(
        request,
        PublicPageContent.PAGE_VISA,
        "Visa Services",
        "Update your visa services details from Django admin.",
    )

def holidays(request):
    return _render_public_page(
        request,
        PublicPageContent.PAGE_HOLIDAY,
        "Holiday Packages",
        "Update your holiday packages details from Django admin.",
    )

def partner(request):
    return redirect("umrah_packages")


def umrah_packages(request):
    return _render_public_page(
        request,
        PublicPageContent.PAGE_UMRAH,
        "Umrah Packages",
        "Update your Umrah packages details from Django admin.",
    )


def about_us(request):
    return _render_public_page(
        request,
        PublicPageContent.PAGE_ABOUT,
        "About Us",
        "Share your organization story, mission, and services from Django admin.",
    )

from datetime import datetime, timedelta
from django.core.cache import cache


def _parse_price_to_int(raw_price):
    cleaned = re.sub(r"[^\d.]", "", str(raw_price or "0"))
    if not cleaned:
        return 0
    try:
        return int(round(float(cleaned)))
    except (TypeError, ValueError):
        return 0


def _normalize_flights(flights, travel_date):
    """
    Normalize pricing fields and merge duplicate schedule entries,
    keeping the cheapest offer for the same airline/timing bucket.
    """
    deduped = {}

    for flight in flights or []:
        flight_copy = dict(flight)
        base = _parse_price_to_int(flight_copy.get("base_price") or flight_copy.get("price"))

        flight_copy["base_price"] = base
        flight_copy["price"] = f"{base:,}"
        flight_copy["nil_price"] = base
        flight_copy["standard_price"] = base + 1800
        flight_copy["value_price"] = base + 3500
        flight_copy["save_price"] = max(0, flight_copy["value_price"] - flight_copy["base_price"])
        flight_copy["date"] = travel_date
        flight_copy["stops"] = int(flight_copy.get("stops") or 0)
        flight_copy["stop_label"] = flight_copy.get("stop_label") or (
            "Nonstop" if flight_copy["stops"] == 0 else f"{flight_copy['stops']} Stop" if flight_copy["stops"] == 1 else f"{flight_copy['stops']} Stops"
        )
        flight_copy["meal_text"] = flight_copy.get("meal_text") or "Meal"
        flight_copy["arrival_plus_days"] = int(flight_copy.get("arrival_plus_days") or 0)
        flight_copy["airline_code"] = flight_copy.get("airline_code") or ""
        flight_copy["flight_number"] = flight_copy.get("flight_number") or flight_copy.get("airline", "")

        key = (
            str(flight_copy.get("airline", "")).strip().lower(),
            str(flight_copy.get("departure_time", "")).strip(),
            str(flight_copy.get("arrival_time", "")).strip(),
            str(flight_copy.get("duration", "")).strip(),
        )

        existing = deduped.get(key)
        if existing is None or flight_copy["base_price"] < existing["base_price"]:
            deduped[key] = flight_copy

    return sorted(deduped.values(), key=lambda item: item.get("base_price", 0))


def _match_curated_locations(keyword):
    q = (keyword or "").strip().lower()
    if not q:
        return []

    country_alias = COUNTRY_ALIASES.get(q)
    matches = []

    for loc in CURATED_LOCATIONS:
        haystack = f"{loc['name']} {loc['cityName']} {loc['iataCode']} {loc['countryCode']}".lower()
        if q in haystack or (country_alias and loc["countryCode"] == country_alias):
            matches.append({
                "name": loc["name"],
                "iataCode": loc["iataCode"],
                "address": {
                    "cityName": loc["cityName"],
                    "countryCode": loc["countryCode"],
                },
            })

    return matches


def _default_curated_locations(limit=8):
    rows = []
    for loc in CURATED_LOCATIONS[:limit]:
        rows.append({
            "name": loc["name"],
            "iataCode": loc["iataCode"],
            "address": {
                "cityName": loc["cityName"],
                "countryCode": loc["countryCode"],
            },
        })
    return rows


def _resolve_location_to_iata(location_text):
    if not location_text:
        return None, None

    value = location_text.strip()
    if not value:
        return None, None

    if len(value) == 3 and value.isalpha():
        code = value.upper()
        return code, code

    curated = _match_curated_locations(value)
    if curated:
        item = curated[0]
        code = item.get("iataCode")
        address = item.get("address", {})
        city_name = address.get("cityName") or item.get("name") or value
        country_code = address.get("countryCode")
        label = f"{city_name}, {country_code} ({code})" if country_code else f"{city_name} ({code})"
        return code, label

    bracket_match = re.search(r"\(([A-Za-z]{3})\)$", value)
    if bracket_match:
        code = bracket_match.group(1).upper()
        return code, value

    try:
        response = amadeus.reference_data.locations.get(
            keyword=value,
            subType="CITY,AIRPORT"
        )
        data = response.data or []
        if not data:
            return None, None

        item = data[0]
        code = item.get("iataCode")
        if not code:
            return None, None

        address = item.get("address", {})
        city_name = address.get("cityName") or item.get("name") or value
        country_code = address.get("countryCode")
        label = f"{city_name}, {country_code} ({code})" if country_code else f"{city_name} ({code})"
        return code, label
    except Exception:
        return None, None


def search_results(request):

    origin_input = request.GET.get('from_city')
    destination_input = request.GET.get('to_city')
    origin_code = request.GET.get('from_code')
    destination_code = request.GET.get('to_code')
    departure_date = request.GET.get('departure_date')

    if not origin_input or not destination_input or not departure_date:
        return redirect('/')

    if origin_code:
        origin = origin_code.strip().upper()
        from_city_display = origin_input
    else:
        origin, from_city_display = _resolve_location_to_iata(origin_input)

    if destination_code:
        destination = destination_code.strip().upper()
        to_city_display = destination_input
    else:
        destination, to_city_display = _resolve_location_to_iata(destination_input)

    if not origin or not destination:
        return redirect('/')

    if not from_city_display:
        from_city_display = f"{origin_input} ({origin})"
    if not to_city_display:
        to_city_display = f"{destination_input} ({destination})"

    service = AmadeusService()

    # ===============================
    # MAIN SEARCH (CACHED)
    # ===============================

    cache_key = f"search_{origin}_{destination}_{departure_date}"
    flights = cache.get(cache_key)

    if flights is None:
        try:
            flights = service.search_flights(origin, destination, departure_date)
            cache.set(cache_key, flights, 60 * 5)
            print(f"✈️ Initial search: Fetched {len(flights)} flights for {origin}->{destination} on {departure_date}")
        except Exception as e:
            print(f"❌ API Error: {e}")
            flights = []

    flights = _normalize_flights(flights, departure_date)

    # ===============================
    # DATE SLIDER
    # ===============================

    base_price = 0
    if flights:
        base_price = min([f["base_price"] for f in flights if f["base_price"] > 0])

    try:
        base_date = datetime.strptime(departure_date, "%Y-%m-%d")
    except:
        base_date = datetime.today()

    date_prices = []

    for i in range(-2, 3):
        d = base_date + timedelta(days=i)

        variation = abs(i) * 900
        simulated_price = base_price + variation

        date_prices.append({
            "date": d.strftime("%Y-%m-%d"),
            "day": d.strftime("%a, %d %b"),
            "price": simulated_price,
        })

    # Mark cheapest
    valid_prices = [d["price"] for d in date_prices if d["price"] > 0]

    if valid_prices:
        min_price = min(valid_prices)
        for d in date_prices:
            d["is_cheapest"] = d["price"] == min_price
    else:
        for d in date_prices:
            d["is_cheapest"] = False

    return render(request, "public_booking/results.html", {
        "flights": flights,
        "departure_date": departure_date,
        "date_prices": date_prices,
        "from_city": from_city_display,
        "to_city": to_city_display,
        "from_city_code": origin,
        "to_city_code": destination
    })


def get_flights_for_date(request):
    """
    AJAX endpoint to fetch flights for a selected date
    """
    from_city = request.GET.get('from_city')
    to_city = request.GET.get('to_city')
    selected_date = request.GET.get('date')

    if not from_city or not to_city or not selected_date:
        return JsonResponse({"error": "Missing parameters: from_city, to_city, date required"}, status=400)

    resolved_from, _ = _resolve_location_to_iata(from_city)
    resolved_to, _ = _resolve_location_to_iata(to_city)

    if resolved_from:
        from_city = resolved_from
    if resolved_to:
        to_city = resolved_to

    service = AmadeusService()
    cache_key = f"search_{from_city}_{to_city}_{selected_date}"
    
    flights = cache.get(cache_key)

    if flights is None:
        try:
            flights = service.search_flights(from_city, to_city, selected_date)
            cache.set(cache_key, flights, 60 * 5)
            print(f"✈️ Fetched {len(flights)} flights for {from_city}->{to_city} on {selected_date}")
        except Exception as e:
            print(f"❌ API Error: {e}")
            flights = []

    flights = _normalize_flights(flights, selected_date)

    return JsonResponse({
        "flights": flights,
        "from_city": from_city,
        "to_city": to_city,
        "date": selected_date,
        "count": len(flights)
    })
