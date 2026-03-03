from django.urls import reverse, NoReverseMatch
from .models import SidebarMenuItem


def sidebar_menu_items(request):
    items = []

    db_items = SidebarMenuItem.objects.filter(is_active=True).order_by("sort_order", "id")
    for item in db_items:
        href = "#"
        if item.custom_url:
            href = item.custom_url
        elif item.url_name:
            try:
                href = reverse(item.url_name)
            except NoReverseMatch:
                href = "#"

        items.append({
            "title": item.title,
            "href": href,
        })

    normalized_items = []
    for item in items:
        title = (item.get("title") or "").strip()
        href = item.get("href") or "#"
        key = title.lower()

        if key == "partner with us":
            title = "Umrah Packages"
            href = reverse("umrah_packages")
        elif key in {"flights", "flight"}:
            href = reverse("public_home")
        elif key in {"visas", "visa"}:
            href = reverse("visas")
        elif key in {"holiday packages", "holidays", "holiday"}:
            href = reverse("holidays")

        normalized_items.append({
            "title": title,
            "href": href,
        })

    items = normalized_items

    if not items:
        items = [
            {"title": "Umrah Packages", "href": reverse("umrah_packages")},
            {"title": "Flights", "href": reverse("public_home")},
            {"title": "Visas", "href": reverse("visas")},
            {"title": "Holiday Packages", "href": reverse("holidays")},
        ]

    return {"sidebar_menu_items": items}
