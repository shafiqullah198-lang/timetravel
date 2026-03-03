
from django.db import models, transaction
from accounts.models import Customer, Supplier, CustomerLedger, SupplierLedger

class CustomerPayment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="legacy_customer_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)

            self.customer.total_paid += self.amount
            self.customer.remaining_amount = self.customer.total_amount - self.customer.total_paid
            self.customer.save()

            CustomerLedger.objects.create(
                customer=self.customer,
                description="Customer Payment",
                credit=self.amount
            )


class SupplierPayment(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="legacy_supplier_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)

            self.supplier.total_paid += self.amount
            self.supplier.remaining_payable = self.supplier.total_payable - self.supplier.total_paid
            self.supplier.save()

            SupplierLedger.objects.create(
                supplier=self.supplier,
                description="Supplier Payment",
                debit=self.amount
            )
