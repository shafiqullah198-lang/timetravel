from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from users.utils import role_required
from .analytics import (
    today_sales,
    today_profit,
    monthly_sales,
    monthly_profit,
    total_customer_udar,
    overdue_customer_count,
    partial_customer_count,
    total_supplier_payable,
    overdue_supplier_count,
    total_paid_to_suppliers,
    sales_bar_data,
    monthly_profit_line_data,
    customer_payment_status_pie_data,
    supplier_payable_vs_paid_data,
)


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def dashboard_home(request):
    context = {
        "today_sales": today_sales(),
        "today_profit": today_profit(),
        "monthly_sales": monthly_sales(),
        "monthly_profit": monthly_profit(),
        "total_udar": total_customer_udar(),
        "overdue_customers": overdue_customer_count(),
        "partial_customers": partial_customer_count(),
        "total_supplier_payable": total_supplier_payable(),
        "overdue_suppliers": overdue_supplier_count(),
        "supplier_paid_total": total_paid_to_suppliers(),
    }
    return render(request, "dashboard/home.html", context)


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def dashboard_charts_api(request):
    payload = {
        "daily_sales": sales_bar_data(days=10),
        "monthly_profit": monthly_profit_line_data(months=6),
        "customer_status": customer_payment_status_pie_data(),
        "supplier_status": supplier_payable_vs_paid_data(),
    }
    return JsonResponse(payload)
