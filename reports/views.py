import csv
from datetime import datetime

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from transactions.forms import style

from .pdf import render_pdf
from .services import build_report, resolve_report_range


class ReportForm(forms.Form):
    KIND = [("month", "Monthly"), ("semester", "Semester"), ("custom", "Custom range")]
    kind = forms.ChoiceField(choices=KIND, initial="month", label="Report type")
    month = forms.CharField(required=False, label="Month", widget=forms.TextInput(attrs={"type": "month"}))
    start = forms.DateField(required=False, label="From", widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, label="To", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)

    def clean_month(self):
        raw = self.cleaned_data.get("month")
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m").date()
        except ValueError as exc:
            raise forms.ValidationError("Use the format YYYY-MM.") from exc

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("kind") == "custom":
            start, end = cleaned.get("start"), cleaned.get("end")
            if not start or not end:
                raise forms.ValidationError("Choose both dates for a custom report.")
            if end < start:
                self.add_error("end", "'To' must be on or after 'From'.")
            elif (end - start).days > 400:
                self.add_error("end", "Custom reports are limited to about a year.")
        return cleaned


def _report_from_request(request):
    form = ReportForm(request.GET or None)
    if form.is_bound and form.is_valid():
        d = form.cleaned_data
        rng = resolve_report_range(request.user, d["kind"], d.get("month"), d.get("start"), d.get("end"))
    else:
        rng = resolve_report_range(request.user, "month")
    return form, build_report(request.user, rng)


@login_required
@require_GET
def report_view(request):
    form, report = _report_from_request(request)
    return render(request, "reports/report.html", {"form": form, "r": report, "query": request.GET.urlencode()})


def _safe_cell(value):
    """Prevent CSV/formula injection when the file is opened in Excel."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


@login_required
@require_GET
def export_csv(request):
    _, report = _report_from_request(request)
    rng = report["range"]
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"student-finance-{rng.start:%Y%m%d}-{rng.end:%Y%m%d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # BOM so Excel opens UTF-8 correctly
    writer = csv.writer(response)
    writer.writerow(["Type", "Date", "Category/Source", "Description", "Reference", "Amount (KSh)"])
    for i in report["incomes"]:
        writer.writerow(["Income", i.date.isoformat(), _safe_cell(i.source.name), _safe_cell(i.description), _safe_cell(i.reference), f"{i.amount:.2f}"])
    for e in report["expenses"]:
        writer.writerow(["Expense", e.date.isoformat(), _safe_cell(e.category.name), _safe_cell(e.description), _safe_cell(e.reference), f"{e.amount:.2f}"])
    t = report["totals"]
    writer.writerow([])
    writer.writerow(["Total income", "", "", "", "", f"{t['income']:.2f}"])
    writer.writerow(["Total expenses", "", "", "", "", f"{t['expenses']:.2f}"])
    writer.writerow(["Net", "", "", "", "", f"{t['net']:.2f}"])
    return response


@login_required
@require_GET
def export_pdf(request):
    _, report = _report_from_request(request)
    rng = report["range"]
    pdf = render_pdf(request.user, report)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="student-finance-{rng.start:%Y%m%d}-{rng.end:%Y%m%d}.pdf"'
    return response
