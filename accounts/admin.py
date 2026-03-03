
from django.contrib import admin
from .models import (
    Customer,
    Supplier,
    CustomerPayment,
    SupplierPayment,
    Expense,
    AccountTransaction,
)

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'total_amount', 'total_paid', 'remaining_amount')

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'phone', 'total_payable', 'total_paid', 'remaining_payable')


@admin.register(CustomerPayment)
class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ("customer", "amount", "payment_mode", "status", "created_at")
    list_filter = ("status", "payment_mode", "created_at")
    search_fields = ("customer__name", "reference_no")


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ("supplier", "amount", "payment_mode", "status", "created_at")
    list_filter = ("status", "payment_mode", "created_at")
    search_fields = ("supplier__company_name", "reference_no")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "amount", "expense_date", "created_at")
    list_filter = ("category", "expense_date")
    search_fields = ("title",)


@admin.register(AccountTransaction)
class AccountTransactionAdmin(admin.ModelAdmin):
    list_display = ("entry_type", "dr_cr", "amount", "reference_model", "reference_id", "created_at")
    list_filter = ("entry_type", "dr_cr", "created_at")
    search_fields = ("reference_id", "notes")
