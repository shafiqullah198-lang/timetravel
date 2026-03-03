from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import (
    CustomerPayment,
    SupplierPayment,
    Expense,
    CustomerLedger,
    SupplierLedger,
    AccountTransaction,
)


def _payment_mode_for_ledger(payment_mode):
    return payment_mode if payment_mode in {"cash", "bank", "check", "online"} else "online"


@receiver(post_save, sender=CustomerPayment)
def customer_payment_saved(sender, instance, created, **kwargs):
    instance.customer.recalculate_balances()

    if created and instance.status == "approved":
        CustomerLedger.objects.create(
            customer=instance.customer,
            description="Customer payment received",
            credit=instance.amount,
            payment_mode=_payment_mode_for_ledger(instance.payment_mode),
            reference_id=instance.reference_no,
        )
        AccountTransaction.objects.create(
            entry_type="customer_payment",
            dr_cr="debit",
            amount=instance.amount,
            notes="Customer payment approved",
            reference_model="CustomerPayment",
            reference_id=str(instance.id),
        )


@receiver(post_delete, sender=CustomerPayment)
def customer_payment_deleted(sender, instance, **kwargs):
    instance.customer.recalculate_balances()


@receiver(post_save, sender=SupplierPayment)
def supplier_payment_saved(sender, instance, created, **kwargs):
    instance.supplier.recalculate_balances()

    if created and instance.status == "approved":
        SupplierLedger.objects.create(
            supplier=instance.supplier,
            description="Payment made to supplier",
            debit=instance.amount,
            payment_mode=_payment_mode_for_ledger(instance.payment_mode),
            reference_id=instance.reference_no,
        )
        AccountTransaction.objects.create(
            entry_type="supplier_payment",
            dr_cr="credit",
            amount=instance.amount,
            notes="Supplier payment approved",
            reference_model="SupplierPayment",
            reference_id=str(instance.id),
        )


@receiver(post_delete, sender=SupplierPayment)
def supplier_payment_deleted(sender, instance, **kwargs):
    instance.supplier.recalculate_balances()


@receiver(post_save, sender=Expense)
def expense_saved(sender, instance, created, **kwargs):
    if created:
        AccountTransaction.objects.create(
            entry_type="expense",
            dr_cr="credit",
            amount=instance.amount,
            notes=instance.title,
            reference_model="Expense",
            reference_id=str(instance.id),
        )
