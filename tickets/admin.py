
from django.contrib import admin
from .models import Ticket

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "airline",
        "pnr",
        "customer",
        "supplier",
        "selling_price",
        "cost_price",
        "profit",
        "customer_payment_status",
        "supplier_payment_status",
        "source_channel",
    )
    list_filter = ("payment_mode", "customer_payment_status", "supplier_payment_status", "source_channel")
    search_fields = ("pnr", "ticket_number", "customer__name", "supplier__company_name")
