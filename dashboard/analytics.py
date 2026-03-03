from datetime import date, timedelta
from django.db.models import Sum, Count, Q
from django.utils import timezone
from tickets.models import Ticket
from accounts.models import Customer, Supplier, Expense


def _month_bounds(ref_date=None):
    ref = ref_date or timezone.localdate()
    start = ref.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month = start.replace(month=start.month + 1, day=1)
    return start, next_month


def today_sales():
    return Ticket.objects.filter(created_at__date=timezone.localdate()).aggregate(
        total=Sum("selling_price")
    )["total"] or 0


def today_profit():
    return Ticket.objects.filter(created_at__date=timezone.localdate()).aggregate(
        total=Sum("profit")
    )["total"] or 0


def monthly_sales():
    start, next_month = _month_bounds()
    return Ticket.objects.filter(
        created_at__date__gte=start,
        created_at__date__lt=next_month,
    ).aggregate(total=Sum("selling_price"))["total"] or 0


def monthly_profit():
    start, next_month = _month_bounds()
    gross = Ticket.objects.filter(
        created_at__date__gte=start,
        created_at__date__lt=next_month,
    ).aggregate(total=Sum("profit"))["total"] or 0
    expenses = Expense.objects.filter(
        expense_date__gte=start,
        expense_date__lt=next_month,
    ).aggregate(total=Sum("amount"))["total"] or 0
    return gross - expenses


def total_customer_udar():
    return Customer.objects.aggregate(total=Sum("remaining_amount"))["total"] or 0


def overdue_customer_count():
    return Customer.objects.filter(remaining_amount__gt=0).count()


def partial_customer_count():
    return Customer.objects.filter(total_paid__gt=0, remaining_amount__gt=0).count()


def total_supplier_payable():
    return Supplier.objects.aggregate(total=Sum("remaining_payable"))["total"] or 0


def overdue_supplier_count():
    return Supplier.objects.filter(remaining_payable__gt=0).count()


def total_paid_to_suppliers():
    return Supplier.objects.aggregate(total=Sum("total_paid"))["total"] or 0


def sales_bar_data(days=7):
    today = timezone.localdate()
    points = []
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        total = Ticket.objects.filter(created_at__date=day).aggregate(
            total=Sum("selling_price")
        )["total"] or 0
        points.append({"label": day.strftime("%d %b"), "value": float(total)})
    return points


def monthly_profit_line_data(months=6):
    today = timezone.localdate()
    series = []
    for i in range(months - 1, -1, -1):
        month_ref = (today.replace(day=1) - timedelta(days=i * 30))
        start, next_month = _month_bounds(month_ref)
        gross = Ticket.objects.filter(
            created_at__date__gte=start, created_at__date__lt=next_month
        ).aggregate(total=Sum("profit"))["total"] or 0
        costs = Expense.objects.filter(
            expense_date__gte=start, expense_date__lt=next_month
        ).aggregate(total=Sum("amount"))["total"] or 0
        series.append({"label": start.strftime("%b %Y"), "value": float(gross - costs)})
    return series


def customer_payment_status_pie_data():
    paid = Customer.objects.filter(remaining_amount=0).count()
    partial = Customer.objects.filter(total_paid__gt=0, remaining_amount__gt=0).count()
    unpaid = Customer.objects.filter(total_paid=0, remaining_amount__gt=0).count()
    return [
        {"label": "Paid", "value": paid},
        {"label": "Partial", "value": partial},
        {"label": "Unpaid", "value": unpaid},
    ]


def supplier_payable_vs_paid_data():
    totals = Supplier.objects.aggregate(
        payable=Sum("total_payable"),
        paid=Sum("total_paid"),
    )
    return [
        {"label": "Payable", "value": float(totals["payable"] or 0)},
        {"label": "Paid", "value": float(totals["paid"] or 0)},
    ]
