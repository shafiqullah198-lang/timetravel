from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from users.utils import role_required
from tickets.models import Ticket
from .models import (
    Customer,
    Supplier,
    CustomerLedger,
    SupplierLedger,
    CustomerPayment,
    SupplierPayment,
    Expense,
    AccountTransaction,
)

def _pdf_escape(text):
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _truncate(text, width):
    value = str(text)
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "."


def _build_pdf_bytes(title, headers, rows, widths, preface_lines=None):
    lines = [
        title,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    if preface_lines:
        lines.extend(preface_lines)
        lines.append("")
    header = " | ".join(_truncate(h, w).ljust(w) for h, w in zip(headers, widths))
    sep = "-+-".join("-" * w for w in widths)
    lines.extend([header, sep])

    for row in rows:
        line = " | ".join(_truncate(v, w).ljust(w) for v, w in zip(row, widths))
        lines.append(line)

    page_height = 842
    start_y = 800
    line_height = 14
    max_lines_per_page = 50
    line_pages = [lines[i : i + max_lines_per_page] for i in range(0, len(lines), max_lines_per_page)] or [[]]

    objects = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    font_id = 3 + (len(line_pages) * 2)
    page_ids = []

    for index, page_lines in enumerate(line_pages):
        page_id = 3 + (index * 2)
        content_id = page_id + 1
        page_ids.append(page_id)

        stream_lines = [b"BT", b"/F1 10 Tf", f"50 {start_y} Td".encode("ascii"), f"{line_height} TL".encode("ascii")]
        for line in page_lines:
            stream_lines.append(f"({_pdf_escape(line)}) Tj".encode("latin-1", "ignore"))
            stream_lines.append(b"T*")
        stream_lines.append(b"ET")
        content_stream = b"\n".join(stream_lines)

        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 {page_height}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        objects[content_id] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content_stream), content_stream)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    objects[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"

    max_id = max(objects.keys())
    out = bytearray()
    out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max_id + 1)

    for obj_id in range(1, max_id + 1):
        offsets[obj_id] = len(out)
        out.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        out.extend(objects[obj_id])
        out.extend(b"\nendobj\n")

    xref_start = len(out)
    out.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for obj_id in range(1, max_id + 1):
        out.extend(f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii"))

    out.extend(
        (
            "trailer\n"
            f"<< /Size {max_id + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("ascii")
    )
    return bytes(out)


def _month_bounds_from_text(month_text):
    ref = timezone.localdate().replace(day=1)
    if month_text:
        try:
            ref = datetime.strptime(month_text, "%Y-%m").date().replace(day=1)
        except ValueError:
            pass

    if ref.month == 12:
        next_month = ref.replace(year=ref.year + 1, month=1, day=1)
    else:
        next_month = ref.replace(month=ref.month + 1, day=1)
    return ref, next_month


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def customer_ledger_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    entries = CustomerLedger.objects.filter(customer=customer).order_by("-created_at")
    return render(request, "accounts/customer_ledger.html", {"customer": customer, "entries": entries})


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def supplier_ledger_view(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    entries = SupplierLedger.objects.filter(supplier=supplier).order_by("-created_at")
    return render(request, "accounts/supplier_ledger.html", {"supplier": supplier, "entries": entries})


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def customer_udar_list(request):
    query = (request.GET.get("q") or "").strip()
    customers = Customer.objects.filter(remaining_amount__gt=0)
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    customers = customers.order_by("-remaining_amount")
    summary = customers.aggregate(
        total_udar=Sum("remaining_amount"),
        total_partial=Sum("total_paid"),
    )
    return render(
        request,
        "accounts/customer_udar.html",
        {
            "customers": customers,
            "total_udar": summary["total_udar"] or 0,
            "total_partial": summary["total_partial"] or 0,
            "q": query,
        },
    )


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def supplier_payable_list(request):
    query = (request.GET.get("q") or "").strip()
    suppliers = Supplier.objects.filter(remaining_payable__gt=0)
    if query:
        suppliers = suppliers.filter(Q(company_name__icontains=query) | Q(phone__icontains=query))
    suppliers = suppliers.order_by("-remaining_payable")
    summary = suppliers.aggregate(
        total_payable=Sum("remaining_payable"),
        total_paid=Sum("total_paid"),
    )
    return render(
        request,
        "accounts/supplier_payable.html",
        {
            "suppliers": suppliers,
            "total_payable": summary["total_payable"] or 0,
            "total_paid": summary["total_paid"] or 0,
            "q": query,
        },
    )


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant")
def expense_list_create(request):
    selected_month = (request.GET.get("month") or request.POST.get("month") or "").strip()
    month_start, next_month = _month_bounds_from_text(selected_month)
    selected_month = month_start.strftime("%Y-%m")

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        category = (request.POST.get("category") or "other").strip()
        amount_raw = (request.POST.get("amount") or "").strip()
        expense_date_raw = (request.POST.get("expense_date") or "").strip()
        notes = (request.POST.get("notes") or "").strip()

        if not title or not amount_raw or not expense_date_raw:
            messages.error(request, "Title, amount, and expense date are required.")
            return redirect(f"{reverse('expense_page')}?month={selected_month}")

        try:
            amount = Decimal(amount_raw.replace(",", ""))
            if amount <= Decimal("0"):
                raise ValueError
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a valid amount greater than zero.")
            return redirect(f"{reverse('expense_page')}?month={selected_month}")

        try:
            expense_date = datetime.strptime(expense_date_raw, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Enter a valid expense date.")
            return redirect(f"{reverse('expense_page')}?month={selected_month}")

        expense = Expense.objects.create(
            title=title,
            category=category,
            amount=amount,
            expense_date=expense_date,
            notes=notes or None,
        )
        AccountTransaction.objects.create(
            entry_type="expense",
            dr_cr="credit",
            amount=expense.amount,
            notes=expense.title,
            reference_model="Expense",
            reference_id=str(expense.id),
        )
        messages.success(request, "Expense added successfully.")
        return redirect(f"{reverse('expense_page')}?month={selected_month}")

    today = timezone.localdate()
    expenses = Expense.objects.filter(
        expense_date__gte=month_start,
        expense_date__lt=next_month,
    ).order_by("-expense_date", "-created_at")

    daily_sales = Ticket.objects.filter(created_at__date=today).aggregate(
        total=Sum("selling_price")
    )["total"] or 0
    daily_expense = Expense.objects.filter(expense_date=today).aggregate(
        total=Sum("amount")
    )["total"] or 0
    monthly_sales = Ticket.objects.filter(
        created_at__date__gte=month_start,
        created_at__date__lt=next_month,
    ).aggregate(total=Sum("selling_price"))["total"] or 0
    monthly_expense = expenses.aggregate(total=Sum("amount"))["total"] or 0

    context = {
        "expenses": expenses,
        "selected_month": selected_month,
        "today": today,
        "daily_sales": daily_sales,
        "daily_expense": daily_expense,
        "daily_cutoff": daily_sales - daily_expense,
        "monthly_sales": monthly_sales,
        "monthly_expense": monthly_expense,
        "monthly_cutoff": monthly_sales - monthly_expense,
    }
    return render(request, "accounts/expense_page.html", context)


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant")
def monthly_incoming_pdf(request):
    month_start, next_month = _month_bounds_from_text((request.GET.get("month") or "").strip())
    selected_month = month_start.strftime("%Y-%m")

    incoming = CustomerPayment.objects.filter(
        status="approved",
        created_at__date__gte=month_start,
        created_at__date__lt=next_month,
    ).select_related("customer").order_by("-created_at")

    rows = []
    for item in incoming:
        rows.append([
            item.created_at.strftime("%Y-%m-%d"),
            item.customer.name,
            item.payment_mode,
            item.reference_no or "-",
            f"{item.amount:.2f}",
        ])

    if not rows:
        rows.append(["N/A", "-", "-", "-", "0.00"])

    total_incoming = incoming.aggregate(total=Sum("amount"))["total"] or 0
    pdf_bytes = _build_pdf_bytes(
        title=f"Incoming Money Flow - {selected_month}",
        preface_lines=[
            f"Month: {month_start.strftime('%B %Y')}",
            f"Total Incoming: PKR {total_incoming}",
        ],
        headers=["Date", "Customer", "Mode", "Reference", "Amount"],
        rows=rows,
        widths=[12, 20, 10, 14, 12],
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="incoming_cash_flow_{selected_month}.pdf"'
    return response


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant")
def monthly_outgoing_pdf(request):
    month_start, next_month = _month_bounds_from_text((request.GET.get("month") or "").strip())
    selected_month = month_start.strftime("%Y-%m")

    supplier_payments = SupplierPayment.objects.filter(
        status="approved",
        created_at__date__gte=month_start,
        created_at__date__lt=next_month,
    ).select_related("supplier")

    expenses = Expense.objects.filter(
        expense_date__gte=month_start,
        expense_date__lt=next_month,
    )

    entries = []
    for payment in supplier_payments:
        entries.append({
            "date": payment.created_at.date(),
            "type": "Supplier Payment",
            "party": payment.supplier.company_name,
            "ref": payment.reference_no or "-",
            "amount": payment.amount,
        })

    for expense in expenses:
        entries.append({
            "date": expense.expense_date,
            "type": f"Expense ({expense.category})",
            "party": expense.title,
            "ref": "-",
            "amount": expense.amount,
        })

    entries.sort(key=lambda x: x["date"], reverse=True)

    rows = []
    for item in entries:
        rows.append([
            item["date"].strftime("%Y-%m-%d"),
            item["type"],
            item["party"],
            item["ref"],
            f"{item['amount']:.2f}",
        ])

    if not rows:
        rows.append(["N/A", "-", "-", "-", "0.00"])

    total_supplier_paid = supplier_payments.aggregate(total=Sum("amount"))["total"] or 0
    total_expense = expenses.aggregate(total=Sum("amount"))["total"] or 0
    total_outgoing = total_supplier_paid + total_expense

    pdf_bytes = _build_pdf_bytes(
        title=f"Outgoing Money Flow - {selected_month}",
        preface_lines=[
            f"Month: {month_start.strftime('%B %Y')}",
            f"Supplier Payments: PKR {total_supplier_paid}",
            f"Operational Expenses: PKR {total_expense}",
            f"Total Outgoing: PKR {total_outgoing}",
        ],
        headers=["Date", "Type", "Payee", "Reference", "Amount"],
        rows=rows,
        widths=[12, 18, 18, 14, 12],
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="outgoing_cash_flow_{selected_month}.pdf"'
    return response


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def customer_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        cnic_passport = (request.POST.get("cnic_passport") or "").strip()
        email = (request.POST.get("email") or "").strip()

        if not name or not phone:
            messages.error(request, "Customer name and phone are required.")
            return render(request, "accounts/customer_create.html", {"form_data": request.POST})

        Customer.objects.create(
            name=name,
            phone=phone,
            cnic_passport=cnic_passport or None,
            email=email or None,
        )
        messages.success(request, "Customer added successfully.")
        return redirect("customer_udar")

    return render(request, "accounts/customer_create.html")


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def supplier_create(request):
    if request.method == "POST":
        company_name = (request.POST.get("company_name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        contact_person = (request.POST.get("contact_person") or "").strip()
        email = (request.POST.get("email") or "").strip()
        bank_details = (request.POST.get("bank_details") or "").strip()

        if not company_name or not phone:
            messages.error(request, "Supplier company name and phone are required.")
            return render(request, "accounts/supplier_create.html", {"form_data": request.POST})

        Supplier.objects.create(
            company_name=company_name,
            phone=phone,
            contact_person=contact_person or None,
            email=email or None,
            bank_details=bank_details or None,
        )
        messages.success(request, "Supplier added successfully.")
        return redirect("supplier_payable")

    return render(request, "accounts/supplier_create.html")


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def customer_debt_pdf(request, pk):
    from tickets.models import Ticket

    customer = get_object_or_404(Customer, pk=pk)
    customer.recalculate_balances()

    tickets = Ticket.objects.filter(customer=customer).order_by("-created_at")
    rows = []
    for ticket in tickets:
        route = f"{ticket.travel_from or 'N/A'}->{ticket.travel_to or 'N/A'}"
        due = (ticket.selling_price or 0) - (ticket.customer_paid or 0)
        rows.append(
            [
                ticket.travel_date.strftime("%Y-%m-%d") if ticket.travel_date else "N/A",
                ticket.pnr or "N/A",
                ticket.ticket_number or "N/A",
                ticket.airline or "N/A",
                route,
                f"{ticket.selling_price:.2f}",
                f"{ticket.customer_paid:.2f}",
                f"{due:.2f}",
            ]
        )

    if not rows:
        rows.append(["N/A", "-", "-", "-", "No tickets found", "-", "-", "-"])

    pdf_bytes = _build_pdf_bytes(
        title=f"Customer Debt Statement - {customer.name}",
        preface_lines=[
            f"Customer: {customer.name}",
            f"Phone: {customer.phone or 'N/A'}",
            f"Email: {customer.email or 'N/A'}",
            f"Total Sale: PKR {customer.total_amount}",
            f"Total Paid: PKR {customer.total_paid}",
            f"Outstanding Udar: PKR {customer.remaining_amount}",
        ],
        headers=["Date", "PNR", "Ticket #", "Airline", "Route", "Sale", "Paid", "Due"],
        rows=rows,
        widths=[10, 8, 9, 8, 10, 8, 8, 8],
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="customer_debt_{customer.id}.pdf"'
    return response


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def send_customer_reminder(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.recalculate_balances()

    if customer.remaining_amount <= 0:
        messages.info(request, f"{customer.name} has no outstanding udar.")
        return redirect("customer_udar")

    phone = "".join(ch for ch in (customer.phone or "") if ch.isdigit())
    if phone.startswith("00"):
        phone = phone[2:]
    if not phone:
        messages.error(request, f"{customer.name} has no valid phone number.")
        return redirect("customer_udar")

    debt_pdf_url = request.build_absolute_uri(reverse("customer_debt_pdf", args=[customer.id]))
    message = (
        f"Assalam o Alaikum {customer.name}, your outstanding udar is PKR {customer.remaining_amount}. "
        f"Please review your statement PDF: {debt_pdf_url}"
    )
    whatsapp_url = f"https://wa.me/{phone}?text={quote(message)}"
    return redirect(whatsapp_url)


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def supplier_record_pdf(request, pk):
    from tickets.models import Ticket

    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.recalculate_balances()

    tickets = Ticket.objects.filter(supplier=supplier).order_by("-created_at")
    rows = []
    for ticket in tickets:
        route = f"{ticket.travel_from or 'N/A'}->{ticket.travel_to or 'N/A'}"
        due = (ticket.cost_price or 0) - (ticket.supplier_paid or 0)
        rows.append(
            [
                ticket.travel_date.strftime("%Y-%m-%d") if ticket.travel_date else "N/A",
                ticket.pnr or "N/A",
                ticket.ticket_number or "N/A",
                ticket.airline or "N/A",
                route,
                f"{ticket.cost_price:.2f}",
                f"{ticket.supplier_paid:.2f}",
                f"{due:.2f}",
            ]
        )

    if not rows:
        rows.append(["N/A", "-", "-", "-", "No tickets found", "-", "-", "-"])

    pdf_bytes = _build_pdf_bytes(
        title=f"Supplier Statement - {supplier.company_name}",
        preface_lines=[
            f"Supplier: {supplier.company_name}",
            f"Phone: {supplier.phone or 'N/A'}",
            f"Email: {supplier.email or 'N/A'}",
            f"Contact Person: {supplier.contact_person or 'N/A'}",
            f"Total Payable: PKR {supplier.total_payable}",
            f"Total Paid: PKR {supplier.total_paid}",
            f"Remaining: PKR {supplier.remaining_payable}",
        ],
        headers=["Date", "PNR", "Ticket #", "Airline", "Route", "Cost", "Paid", "Due"],
        rows=rows,
        widths=[10, 8, 9, 8, 10, 8, 8, 8],
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="supplier_record_{supplier.id}.pdf"'
    return response


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant", "staff", "operations")
def send_supplier_record(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.recalculate_balances()

    if supplier.remaining_payable <= 0:
        messages.info(request, f"{supplier.company_name} has no remaining payable.")
        return redirect("supplier_payable")

    phone = "".join(ch for ch in (supplier.phone or "") if ch.isdigit())
    if phone.startswith("00"):
        phone = phone[2:]
    if not phone:
        messages.error(request, f"{supplier.company_name} has no valid phone number.")
        return redirect("supplier_payable")

    statement_pdf_url = request.build_absolute_uri(reverse("supplier_record_pdf", args=[supplier.id]))
    message = (
        f"Assalam o Alaikum {supplier.company_name}, remaining payable is PKR {supplier.remaining_payable}. "
        f"Please review your statement PDF: {statement_pdf_url}"
    )
    whatsapp_url = f"https://wa.me/{phone}?text={quote(message)}"
    return redirect(whatsapp_url)


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant")
def add_customer_payment(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        amount = request.POST.get("amount")
        payment_mode = request.POST.get("payment_mode", "cash")
        reference_no = request.POST.get("reference_no")
        notes = request.POST.get("notes")

        CustomerPayment.objects.create(
            customer=customer,
            amount=amount or 0,
            payment_mode=payment_mode,
            reference_no=reference_no,
            notes=notes,
            status="approved",
        )
        messages.success(request, "Customer payment recorded successfully.")
    return redirect("customer_ledger", pk=customer.id)


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant")
def add_supplier_payment(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        amount = request.POST.get("amount")
        payment_mode = request.POST.get("payment_mode", "bank")
        reference_no = request.POST.get("reference_no")
        notes = request.POST.get("notes")

        SupplierPayment.objects.create(
            supplier=supplier,
            amount=amount or 0,
            payment_mode=payment_mode,
            reference_no=reference_no,
            notes=notes,
            status="approved",
        )
        messages.success(request, "Supplier payment recorded successfully.")
    return redirect("supplier_ledger", pk=supplier.id)


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant")
def export_customer_ledger_pdf(request):
    rows = [
        [customer.name, customer.total_amount, customer.total_paid, customer.remaining_amount]
        for customer in Customer.objects.all().order_by("name")
    ]
    pdf_bytes = _build_pdf_bytes(
        title="Customer Ledger Report",
        headers=["Customer", "Total Amount", "Total Paid", "Remaining"],
        rows=rows,
        widths=[24, 14, 14, 14],
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="customer_ledger_report.pdf"'
    return response


@login_required(login_url="/auth/login/")
@role_required("admin", "accountant")
def export_supplier_ledger_pdf(request):
    rows = [
        [supplier.company_name, supplier.total_payable, supplier.total_paid, supplier.remaining_payable]
        for supplier in Supplier.objects.all().order_by("company_name")
    ]
    pdf_bytes = _build_pdf_bytes(
        title="Supplier Ledger Report",
        headers=["Supplier", "Total Payable", "Total Paid", "Remaining"],
        rows=rows,
        widths=[24, 14, 14, 14],
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="supplier_ledger_report.pdf"'
    return response
