
from django.contrib import admin
from .models import Booking, SidebarMenuItem, PublicPageContent

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'pnr', 'airline', 'fare_type', 'passport_number', 'price', 'status', 'created_at')
    search_fields = ('full_name', 'pnr', 'passport_number', 'phone', 'email', 'airline')


@admin.register(SidebarMenuItem)
class SidebarMenuItemAdmin(admin.ModelAdmin):
    list_display = ("title", "url_name", "custom_url", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    search_fields = ("title", "url_name", "custom_url")


@admin.register(PublicPageContent)
class PublicPageContentAdmin(admin.ModelAdmin):
    list_display = ("page_key", "title", "is_active", "updated_at")
    list_filter = ("page_key", "is_active")
    search_fields = ("title", "content")
