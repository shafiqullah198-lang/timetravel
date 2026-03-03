from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from users.utils import role_required
from accounts.models import Customer, Supplier
from .models import Ticket


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def ticket_list(request):
    query = (request.GET.get("q") or "").strip()
    tickets = Ticket.objects.select_related("customer", "supplier").order_by("-created_at")

    if query:
        tickets = tickets.filter(
            Q(customer__name__icontains=query) | Q(pnr__icontains=query)
        )

    tickets = tickets[:300]
    return render(request, "tickets/ticket_list.html", {"tickets": tickets, "q": query})


@login_required(login_url="/auth/login/")
@role_required("admin", "staff", "operations")
def ticket_create(request):
    customers = Customer.objects.all().order_by("name")
    suppliers = Supplier.objects.all().order_by("company_name")

    if request.method == "POST":
        def parse_decimal(field_name, default="0"):
            raw = (request.POST.get(field_name) or default).strip().replace(",", "")
            try:
                return Decimal(raw)
            except (InvalidOperation, ValueError):
                raise ValueError(field_name)

        customer_name = (request.POST.get("customer_name") or "").strip()
        supplier_name = (request.POST.get("supplier_name") or "").strip()

        if not customer_name or not supplier_name:
            messages.error(request, "Customer and Supplier are required.")
            return render(
                request,
                "tickets/ticket_create.html",
                {"customers": customers, "suppliers": suppliers, "form_data": request.POST},
            )

        customer = Customer.objects.filter(name__iexact=customer_name).first()
        if not customer:
            customer = Customer.objects.create(name=customer_name, phone="N/A")

        supplier = Supplier.objects.filter(company_name__iexact=supplier_name).first()
        if not supplier:
            supplier = Supplier.objects.create(company_name=supplier_name, phone="N/A")

        try:
            cost_price = parse_decimal("cost_price")
            selling_price = parse_decimal("selling_price")
            customer_paid = parse_decimal("customer_paid", "0")
            supplier_paid = parse_decimal("supplier_paid", "0")
        except ValueError:
            messages.error(request, "Please enter valid numeric values for price and payment fields.")
            return render(
                request,
                "tickets/ticket_create.html",
                {"customers": customers, "suppliers": suppliers, "form_data": request.POST},
            )

        ticket = Ticket(
            customer=customer,
            supplier=supplier,
            airline=request.POST.get("airline"),
            pnr=request.POST.get("pnr"),
            ticket_number=request.POST.get("ticket_number"),
            travel_from=request.POST.get("travel_from"),
            travel_to=request.POST.get("travel_to"),
            travel_date=request.POST.get("travel_date") or None,
            cost_price=cost_price,
            selling_price=selling_price,
            payment_mode=request.POST.get("payment_mode") or "credit",
            customer_paid=customer_paid,
            supplier_paid=supplier_paid,
            source_channel="erp",
        )
        ticket.save()
        messages.success(request, "Ticket created and ERP balances updated.")
        return redirect("ticket_list")

    return render(
        request,
        "tickets/ticket_create.html",
        {"customers": customers, "suppliers": suppliers, "form_data": {}},
    )
