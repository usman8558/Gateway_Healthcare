import frappe
import calendar
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data, chart = get_data(filters)
    return columns, data, chart


def get_columns():
    return [
        # New columns added at the start
        {"label": "Start Date", "fieldname": "start_date", "fieldtype": "Date", "width": 110},
        {"label": "End Date", "fieldname": "end_date", "fieldtype": "Date", "width": 110},
        
        {"label": "Patient", "fieldname": "patient", "fieldtype": "Link", "options": "Patient", "width": 150},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": "Package Name", "fieldname": "therapy_plan_template", "fieldtype": "Data", "width": 150},
        {"label": "Therapy Type(s)", "fieldname": "therapy_type", "fieldtype": "Data", "width": 200},
        {"label": "Practitioner(s)", "fieldname": "patrictioner_name", "fieldtype": "Data", "width": 200},
        {"label": "Total Sessions", "fieldname": "total_sessions", "fieldtype": "Int", "width": 120},
        {"label": "Completed Sessions", "fieldname": "completed_sessions", "fieldtype": "Int", "width": 150},
        {"label": "Remaining Sessions", "fieldname": "remaining_sessions", "fieldtype": "Int", "width": 150},
        {"label": "Invoice No", "fieldname": "invoice_no", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
        {"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
        {"label": "Paid Amount", "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
        {"label": "Outstanding Amount", "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 150},
        {"label": "Reference", "fieldname": "reference", "fieldtype": "Data", "width": 220},
    ]


def get_data(filters):
    data = []
    conditions = []
    values = {}

    # -------- Month Filter --------
    if filters.get("month"):
        month_number = list(calendar.month_name).index(filters["month"])
        conditions.append("MONTH(tp.posting_date) = %(month)s")
        values["month"] = month_number

    # -------- Year Filter --------
    if filters.get("year"):
        conditions.append("YEAR(tp.posting_date) = %(year)s")
        values["year"] = int(filters["year"])

    if filters.get("patient"):
        conditions.append("tp.patient = %(patient)s")
        values["patient"] = filters["patient"]

    if filters.get("therapy_plan_template"):
        conditions.append("tp.therapy_plan_template = %(therapy_plan_template)s")
        values["therapy_plan_template"] = filters["therapy_plan_template"]

    condition_query = " AND ".join(conditions)
    if condition_query:
        condition_query = " AND " + condition_query

    therapy_plans = frappe.db.sql(f"""
        SELECT
            tp.name,
            tp.patient,
            tp.posting_date,
            tp.start_date,
            tp.end_date,
            tp.therapy_plan_template,
            tp.total_sessions,
            tp.total_sessions_completed,
            tp.sales_invoice
        FROM `tabTherapy Plan` tp
        WHERE tp.docstatus = 0
        {condition_query}
    """, values, as_dict=True)

    package_summary = {}

    for tp in therapy_plans:
        # Fetching Therapy Details
        details = frappe.db.sql("""
            SELECT therapy_type, patrictioner_name
            FROM `tabTherapy Plan Detail`
            WHERE parent = %s
        """, tp.name, as_dict=True)

        therapy_types = ", ".join(sorted({d.therapy_type for d in details if d.therapy_type}))
        practitioners = ", ".join(sorted({d.patrictioner_name for d in details if d.patrictioner_name}))

        grand_total = outstanding_amount = paid_amount = 0
        reference = ""

        # Invoice logic
        if tp.sales_invoice:
            invoice = frappe.db.get_value(
                "Sales Invoice",
                tp.sales_invoice,
                ["grand_total", "outstanding_amount"],
                as_dict=True
            ) or {}

            grand_total = invoice.get("grand_total", 0)
            outstanding_amount = invoice.get("outstanding_amount", 0)

            paid_amount = frappe.db.sql("""
                SELECT SUM(allocated_amount)
                FROM `tabPayment Entry Reference`
                WHERE reference_doctype = 'Sales Invoice'
                AND reference_name = %s
            """, tp.sales_invoice)[0][0] or 0

        # Reference logic
        if tp.patient:
            types = frappe.db.sql("""
                SELECT DISTINCT type
                FROM `tabSales Invoice`
                WHERE patient = %s
                AND type IN ('Clinic', 'Therapy')
                AND docstatus = 1
            """, tp.patient, as_dict=True)

            if {"Clinic", "Therapy"} <= {t.type for t in types}:
                reference = "Referred from Clinic to Therapy"

        if filters.get("reference") and reference != filters.get("reference"):
            continue

        # Chart Data Build
        pkg = tp.therapy_plan_template or "Unknown"
        package_summary.setdefault(pkg, {"total": 0, "completed": 0})
        package_summary[pkg]["total"] += flt(tp.total_sessions)
        package_summary[pkg]["completed"] += flt(tp.total_sessions_completed)

        # Mapping data to dictionary
        data.append({
            "start_date": tp.start_date,
            "end_date": tp.end_date,
            "patient": tp.patient,
            "posting_date": tp.posting_date,
            "therapy_plan_template": tp.therapy_plan_template,
            "therapy_type": therapy_types,
            "patrictioner_name": practitioners,
            "total_sessions": tp.total_sessions,
            "completed_sessions": tp.total_sessions_completed,
            "remaining_sessions": flt(tp.total_sessions) - flt(tp.total_sessions_completed),
            "invoice_no": tp.sales_invoice,
            "grand_total": grand_total,
            "paid_amount": paid_amount,
            "outstanding_amount": outstanding_amount,
            "reference": reference,
        })

    # Chart Config
    chart = {
        "data": {
            "labels": list(package_summary.keys()),
            "datasets": [
                {
                    "name": "Total Sessions",
                    "values": [v["total"] for v in package_summary.values()]
                },
                {
                    "name": "Completed Sessions",
                    "values": [v["completed"] for v in package_summary.values()]
                }
            ]
        },
        "type": "bar",
        "height": 300
    }

    return data, chart