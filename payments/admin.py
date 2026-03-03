
from django.contrib import admin
from .models import CustomerPayment, SupplierPayment

admin.site.register(CustomerPayment)
admin.site.register(SupplierPayment)
