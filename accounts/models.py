from decimal import Decimal
from django.db import models

class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    cnic_passport = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def recalculate_balances(self, save=True):
        total_sold = self.ticket_set.aggregate(total=models.Sum("selling_price"))["total"] or Decimal("0")
        total_paid = self.customerpayment_set.filter(status="approved").aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0")

        self.total_amount = total_sold
        self.total_paid = total_paid
        self.remaining_amount = max(Decimal("0"), total_sold - total_paid)
        if save:
            self.save(update_fields=["total_amount", "total_paid", "remaining_amount"])

    def __str__(self):
        return self.name

class Supplier(models.Model):
    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    bank_details = models.TextField(blank=True, null=True)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def recalculate_balances(self, save=True):
        total_purchased = self.ticket_set.aggregate(total=models.Sum("cost_price"))["total"] or Decimal("0")
        total_paid = self.supplierpayment_set.filter(status="approved").aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0")

        self.total_payable = total_purchased
        self.total_paid = total_paid
        self.remaining_payable = max(Decimal("0"), total_purchased - total_paid)
        if save:
            self.save(update_fields=["total_payable", "total_paid", "remaining_payable"])

    def __str__(self):
        return self.company_name

class CustomerLedger(models.Model):
    PAYMENT_MODES = (
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('check', 'Check'),
        ('online', 'Online'),
        ('system', 'System Auto'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='system')
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.name} - {self.description}"

class SupplierLedger(models.Model):
    PAYMENT_MODES = (
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('check', 'Check'),
        ('online', 'Online'),
        ('system', 'System Auto'),
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='system')
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supplier.company_name} - {self.description}"

class CompanySetting(models.Model):
    default_margin = models.DecimalField(max_digits=10, decimal_places=2, default=3000)

    def __str__(self):
        return "Company Settings"


class CustomerPayment(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )
    PAYMENT_MODES = (
        ("cash", "Cash"),
        ("bank", "Bank Transfer"),
        ("card", "Card"),
        ("jazzcash", "JazzCash"),
        ("easypaisa", "Easypaisa"),
        ("online", "Online"),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default="cash")
    reference_no = models.CharField(max_length=120, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="approved")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.name} - {self.amount}"


class SupplierPayment(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )
    PAYMENT_MODES = (
        ("cash", "Cash"),
        ("bank", "Bank Transfer"),
        ("card", "Card"),
        ("online", "Online"),
    )

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default="bank")
    reference_no = models.CharField(max_length=120, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="approved")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supplier.company_name} - {self.amount}"


class Expense(models.Model):
    CATEGORY_CHOICES = (
        ("salary", "Salary"),
        ("rent", "Rent"),
        ("utility", "Utility"),
        ("marketing", "Marketing"),
        ("operations", "Operations"),
        ("other", "Other"),
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.amount}"


class AccountTransaction(models.Model):
    ENTRY_TYPES = (
        ("sale", "Sale"),
        ("customer_payment", "Customer Payment"),
        ("supplier_purchase", "Supplier Purchase"),
        ("supplier_payment", "Supplier Payment"),
        ("expense", "Expense"),
        ("adjustment", "Adjustment"),
    )
    DR_CR = (
        ("debit", "Debit"),
        ("credit", "Credit"),
    )

    entry_type = models.CharField(max_length=30, choices=ENTRY_TYPES)
    dr_cr = models.CharField(max_length=10, choices=DR_CR)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True, null=True)
    reference_model = models.CharField(max_length=80, blank=True, null=True)
    reference_id = models.CharField(max_length=80, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entry_type} - {self.amount}"
