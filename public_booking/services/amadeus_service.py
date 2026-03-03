from tickets.services.amadeus_client import amadeus
from datetime import datetime


class AmadeusService:

    def format_duration(self, raw_duration):
        """
        Convert PT5H30M → 5h 30m
        Convert PT45M → 45m
        Convert PT2H → 2h
        """
        duration = raw_duration.replace("PT", "")

        hours = ""
        minutes = ""

        if "H" in duration:
            hours = duration.split("H")[0] + "h "
            duration = duration.split("H")[1]

        if "M" in duration:
            minutes = duration.replace("M", "m")

        return (hours + minutes).strip()

    def search_flights(self, origin, destination, departure_date):
        flights_data = []

        if not origin or not destination or not departure_date:
            return flights_data

        response = amadeus.shopping.flight_offers_search.get(
    originLocationCode=origin,
    destinationLocationCode=destination,
    departureDate=departure_date,
    adults=1,
    currencyCode="PKR"   # 🔥 THIS LINE ADDED
)

        carriers = response.result.get("dictionaries", {}).get("carriers", {})

        for offer in response.data:
            itinerary = offer["itineraries"][0]
            segments = itinerary.get("segments", [])
            if not segments:
                continue

            first_segment = segments[0]
            last_segment = segments[-1]
            departure_at = first_segment["departure"]["at"]
            arrival_at = last_segment["arrival"]["at"]

            raw_duration = itinerary["duration"]
            duration = self.format_duration(raw_duration)

            airline_code = first_segment["carrierCode"]
            airline_name = carriers.get(airline_code, airline_code)
            flight_number = first_segment.get("number", "")
            stops = max(0, len(segments) - 1)
            stop_label = "Nonstop" if stops == 0 else f"{stops} Stop" if stops == 1 else f"{stops} Stops"
            arrival_plus_days = 0

            try:
                dep_date = datetime.strptime(departure_at[:10], "%Y-%m-%d").date()
                arr_date = datetime.strptime(arrival_at[:10], "%Y-%m-%d").date()
                arrival_plus_days = max(0, (arr_date - dep_date).days)
            except (TypeError, ValueError):
                arrival_plus_days = 0

            price_value = round(float(offer["price"]["total"]))
            currency = offer["price"]["currency"]

            # Format price with comma
            formatted_price = f"{price_value:,}"

            logo_url = f"https://content.airhex.com/content/logos/airlines_{airline_code}_200_200_s.png"

            flights_data.append({
                "departure_time": departure_at[11:16],
                "arrival_time": arrival_at[11:16],
                "from_airport": first_segment.get("departure", {}).get("iataCode", origin),
                "to_airport": last_segment.get("arrival", {}).get("iataCode", destination),
                "airline": airline_name,
                "airline_code": airline_code,
                "flight_number": f"{airline_code}-{flight_number}" if flight_number else airline_code,
                "duration": duration,
                "stops": stops,
                "stop_label": stop_label,
                "arrival_plus_days": arrival_plus_days,
                "meal_text": "Meal",
                "price": formatted_price,
                "currency": currency,
                "logo": logo_url
            })

        return flights_data
