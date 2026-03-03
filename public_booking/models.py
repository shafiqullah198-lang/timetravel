
from django.db import models
import uuid

class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    )

    pnr = models.CharField(max_length=20, unique=True, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    from_city = models.CharField(max_length=100)
    to_city = models.CharField(max_length=100)
    departure_date = models.DateField()
    airline = models.CharField(max_length=100)
    fare_type = models.CharField(max_length=30, blank=True)
    departure_time = models.CharField(max_length=10, blank=True)
    arrival_time = models.CharField(max_length=10, blank=True)
    stop_label = models.CharField(max_length=30, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    passport_number = models.CharField(max_length=30, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pnr:
            self.pnr = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - {self.pnr}"


class SidebarMenuItem(models.Model):
    title = models.CharField(max_length=120)
    url_name = models.CharField(max_length=120, blank=True, help_text="Django URL name, e.g. partner")
    custom_url = models.CharField(max_length=255, blank=True, help_text="Optional direct URL path, e.g. /flights/")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Sidebar Menu Item"
        verbose_name_plural = "Sidebar Menu Items"

    def __str__(self):
        return self.title


class PublicPageContent(models.Model):
    PAGE_ABOUT = "about"
    PAGE_VISA = "visa"
    PAGE_UMRAH = "umrah"
    PAGE_HOLIDAY = "holiday"

    PAGE_CHOICES = (
        (PAGE_ABOUT, "About Us"),
        (PAGE_VISA, "Visa Services"),
        (PAGE_UMRAH, "Umrah Packages"),
        (PAGE_HOLIDAY, "Holiday Packages"),
    )

    page_key = models.CharField(max_length=32, choices=PAGE_CHOICES, unique=True)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page_key"]
        verbose_name = "Public Page Content"
        verbose_name_plural = "Public Page Content"

    def __str__(self):
        return self.get_page_key_display()
