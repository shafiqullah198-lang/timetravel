from decimal import Decimal
from django.db import models, transaction
from accounts.models import (
    Customer,
    Supplier,
    CustomerLedger,
    SupplierLedger,
    CustomerPayment,
    SupplierPayment,
    AccountTransaction,
)

class Ticket(models.Model):
    PAYMENT_MODES = (
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('check', 'Check'),
        ('online', 'Online'),
        ('credit', 'Credit/Udar'),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    airline = models.CharField(max_length=100)
    pnr = models.CharField(max_length=50)
    ticket_number = models.CharField(max_length=50, blank=True, null=True)
    travel_from = models.CharField(max_length=100, blank=True, null=True)
    travel_to = models.CharField(max_length=100, blank=True, null=True)
    travel_date = models.DateField(blank=True, null=True)
    
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='credit')
    customer_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    customer_payment_status = models.CharField(
        max_length=20,
        choices=(("paid", "Paid"), ("partial", "Partial"), ("unpaid", "Unpaid")),
        default="unpaid",
    )
    supplier_payment_status = models.CharField(
        max_length=20,
        choices=(("paid", "Paid"), ("partial", "Partial"), ("unpaid", "Unpaid")),
        default="unpaid",
    )
    source_channel = models.CharField(
        max_length=20,
        choices=(("erp", "ERP"), ("public", "Public Website")),
        default="erp",
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new = self.pk is None

            self.profit = self.selling_price - self.cost_price

            self.customer_payment_status = self._get_payment_status(self.customer_paid, self.selling_price)
            self.supplier_payment_status = self._get_payment_status(self.supplier_paid, self.cost_price)
            super().save(*args, **kwargs)

            if is_new:
                # Customer Ledger (Debit = Sale)
                CustomerLedger.objects.create(
                    customer=self.customer,
                    description=f"Ticket Sale ({self.pnr}) - {self.route}",
                    debit=self.selling_price,
                    payment_mode=self.payment_mode,
                    reference_id=self.pnr
                )
                
                # If customer paid something upfront
                if self.customer_paid > 0:
                    payment = CustomerPayment.objects.create(
                        customer=self.customer,
                        amount=self.customer_paid,
                        payment_mode=self._map_payment_mode(self.payment_mode),
                        reference_no=self.pnr,
                        notes="Initial payment from ticket booking",
                        status="approved",
                    )
                    CustomerLedger.objects.create(
                        customer=self.customer,
                        description=f"Initial Payment ({self.pnr})",
                        credit=self.customer_paid,
                        payment_mode=self.payment_mode,
                        reference_id=self.pnr
                    )
                    AccountTransaction.objects.create(
                        entry_type="customer_payment",
                        dr_cr="debit",
                        amount=self.customer_paid,
                        notes=f"Customer payment ({self.pnr})",
                        reference_model="CustomerPayment",
                        reference_id=str(payment.id),
                    )

                # Supplier Ledger (Credit = Purchase)
                SupplierLedger.objects.create(
                    supplier=self.supplier,
                    description=f"Ticket Purchase ({self.pnr}) - {self.route}",
                    credit=self.cost_price,
                    payment_mode='system',
                    reference_id=self.pnr
                )
                
                # If we paid supplier upfront
                if self.supplier_paid > 0:
                    supplier_payment = SupplierPayment.objects.create(
                        supplier=self.supplier,
                        amount=self.supplier_paid,
                        payment_mode="bank",
                        reference_no=self.pnr,
                        notes="Initial supplier payment from ticket booking",
                        status="approved",
                    )
                    SupplierLedger.objects.create(
                        supplier=self.supplier,
                        description=f"Initial Payment to Supplier ({self.pnr})",
                        debit=self.supplier_paid,
                        payment_mode='system',
                        reference_id=self.pnr
                    )

                    AccountTransaction.objects.create(
                        entry_type="supplier_payment",
                        dr_cr="credit",
                        amount=self.supplier_paid,
                        notes=f"Supplier payment ({self.pnr})",
                        reference_model="SupplierPayment",
                        reference_id=str(supplier_payment.id),
                    )

                AccountTransaction.objects.create(
                    entry_type="sale",
                    dr_cr="debit",
                    amount=self.selling_price,
                    notes=f"Ticket sale {self.pnr}",
                    reference_model="Ticket",
                    reference_id=str(self.id),
                )
                AccountTransaction.objects.create(
                    entry_type="supplier_purchase",
                    dr_cr="credit",
                    amount=self.cost_price,
                    notes=f"Supplier payable {self.pnr}",
                    reference_model="Ticket",
                    reference_id=str(self.id),
                )

                self.customer.recalculate_balances()
                self.supplier.recalculate_balances()

    @staticmethod
    def _get_payment_status(paid, total):
        paid_val = paid or Decimal("0")
        total_val = total or Decimal("0")
        if paid_val <= 0:
            return "unpaid"
        if paid_val < total_val:
            return "partial"
        return "paid"

    @staticmethod
    def _map_payment_mode(payment_mode):
        mapping = {
            "cash": "cash",
            "bank": "bank",
            "check": "bank",
            "online": "online",
            "credit": "online",
        }
        return mapping.get(payment_mode, "cash")

    @property
    def route(self):
        return f"{self.travel_from} -> {self.travel_to}" if self.travel_from and self.travel_to else "N/A"

    def __str__(self):
        return f"{self.pnr} - {self.customer.name}"
