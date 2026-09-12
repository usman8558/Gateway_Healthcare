import frappe
from frappe import _
from frappe.utils import flt
import calendar
from datetime import date

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    start_date, end_date = get_date_range(filters)
    data = get_data(filters, start_date, end_date)
    
    return columns, data, None, None, None

def get_columns():
    return [
        {"label": _("Practitioner / Metric"), "fieldname": "practitioner", "fieldtype": "Data", "width": 200},
        
        # 100% Columns
        {"label": _("100% Days"), "fieldname": "d_100", "fieldtype": "Float", "width": 90},
        {"label": _("100% Week"), "fieldname": "w_100", "fieldtype": "Float", "width": 90},
        {"label": _("100% Period"), "fieldname": "m_100", "fieldtype": "Float", "width": 100},
        
        # 80% Columns
        {"label": _("80% Days"), "fieldname": "d_80", "fieldtype": "Float", "width": 90},
        {"label": _("80% Week"), "fieldname": "w_80", "fieldtype": "Float", "width": 90},
        {"label": _("80% Period"), "fieldname": "m_80", "fieldtype": "Float", "width": 100},
        
        # 60% Columns
        {"label": _("60% Days"), "fieldname": "d_60", "fieldtype": "Float", "width": 90},
        {"label": _("60% Week"), "fieldname": "w_60", "fieldtype": "Float", "width": 90},
        {"label": _("60% Period"), "fieldname": "m_60", "fieldtype": "Float", "width": 100},
        
        # Actual Utilization Columns
        {"label": _("Act. Days"), "fieldname": "d_act", "fieldtype": "Float", "width": 90},
        {"label": _("Act. Week"), "fieldname": "w_act", "fieldtype": "Float", "width": 90},
        {"label": _("Act. Period"), "fieldname": "m_act", "fieldtype": "Float", "width": 100},
        
        # Status / Visuals
        {"label": _("Util. %"), "fieldname": "util_perc", "fieldtype": "Float", "width": 90},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110}
    ]

def get_date_range(filters):
    view = filters.get("view", "Monthly")
    year = int(filters.get("year", date.today().year))
    
    if view == "Monthly":
        month_name = filters.get("month", date.today().strftime("%B"))
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        month_idx = months.index(month_name) + 1
        start_date = f"{year}-{month_idx:02d}-01"
        last_day = calendar.monthrange(year, month_idx)[1]
        end_date = f"{year}-{month_idx:02d}-{last_day:02d}"
    elif view == "Quarterly":
        quarter = filters.get("quarter", "Q1")
        if quarter == "Q1": start_date, end_date = f"{year}-01-01", f"{year}-03-31"
        elif quarter == "Q2": start_date, end_date = f"{year}-04-01", f"{year}-06-30"
        elif quarter == "Q3": start_date, end_date = f"{year}-07-01", f"{year}-09-30"
        else: start_date, end_date = f"{year}-10-01", f"{year}-12-31"
    else:
        start_date, end_date = f"{year}-01-01", f"{year}-12-31"
        
    return start_date, end_date

def get_data(filters, start_date, end_date):
    view = filters.get("view", "Monthly")
    
    # Capacity Multiplier based on View
    multiplier = 1
    if view == "Quarterly": multiplier = 3
    elif view == "Yearly": multiplier = 12

    practitioners = frappe.get_all("Healthcare Practitioner", 
        filters={"type": ["in", ["Therapist", "Both"]]},
        fields=["name", "first_name", "practitioner_name"]
    )

    data = []
    
    # Base configuration per practitioner based on EXACT 13/65 formulas
    b_d100, b_w100, b_m100 = 13, 65, 260 * multiplier
    b_d80, b_w80, b_m80 = 10.4, 52, 208 * multiplier   # Week was 52 per formula
    b_d60, b_w60, b_m60 = 7.8, 39, 156 * multiplier    # Week was 39 per formula
    
    # Totals Variables
    t_d100 = t_w100 = t_m100 = 0
    t_d80 = t_w80 = t_m80 = 0
    t_d60 = t_w60 = t_m60 = 0
    t_d_act = t_w_act = t_m_act = 0

    for p in practitioners:
        m_act = frappe.db.count("Therapy Session", {
            "practitioner": p.name,
            "docstatus": 1,
            "start_date": ["between", [start_date, end_date]]
        })
        
        # Excel Image Formula mapping for Actuals: Period/5 = Week, Week/4 = Days
        # If Quarter/Year, the daily/weekly averages should divide by proper scale.
        m_act_monthly_avg = m_act / multiplier 
        w_act = m_act_monthly_avg / 5.0
        d_act = w_act / 4.0
        
        util_perc = (m_act / b_m100) * 100 if b_m100 > 0 else 0
        
        if util_perc > 100: status = "Overloaded"
        elif util_perc >= 80: status = "Excellent"
        elif util_perc >= 60: status = "Good"
        elif util_perc >= 40: status = "Moderate"
        else: status = "Low"

        t_d100 += b_d100; t_w100 += b_w100; t_m100 += b_m100
        t_d80 += b_d80; t_w80 += b_w80; t_m80 += b_m80
        t_d60 += b_d60; t_w60 += b_w60; t_m60 += b_m60
        t_d_act += d_act; t_w_act += w_act; t_m_act += m_act

        data.append({
            "practitioner": p.first_name or p.practitioner_name,
            "d_100": b_d100, "w_100": b_w100, "m_100": b_m100,
            "d_80": b_d80, "w_80": b_w80, "m_80": b_m80,
            "d_60": b_d60, "w_60": b_w60, "m_60": b_m60,
            "d_act": flt(d_act, 2), "w_act": flt(w_act, 2), "m_act": m_act,
            "util_perc": flt(util_perc, 2), "status": status
        })

    data.sort(key=lambda x: x["practitioner"])

    # 1. Main Totals Row
    data.append({
        "practitioner": "Total Sessions",
        "d_100": t_d100, "w_100": t_w100, "m_100": t_m100,
        "d_80": flt(t_d80, 2), "w_80": flt(t_w80, 2), "m_80": t_m80,
        "d_60": flt(t_d60, 2), "w_60": flt(t_w60, 2), "m_60": t_m60,
        "d_act": flt(t_d_act, 2), "w_act": flt(t_w_act, 2), "m_act": t_m_act,
        "util_perc": "", "status": "", "is_total_row": 1
    })

    # ==========================================================
    # --- REVENUE AND CAPACITY SECTION INJECTION ---
    # ==========================================================
    
    therapy_sales = frappe.db.sql("""
        SELECT SUM(grand_total) 
        FROM `tabSales Invoice` 
        WHERE docstatus = 1 
          AND posting_date BETWEEN %s AND %s 
          AND type = 'Therapy'
    """, (start_date, end_date))[0][0] or 0.0

    avg_rev = (flt(therapy_sales) / t_m_act) if t_m_act > 0 else 0
    avg_sess_pat = 837 / 17

    data.append({"practitioner": "", "is_blank": 1})
    data.append({"practitioner": "CAPACITY & REVENUE SUMMARY", "is_section_header": 1})

    # Average Revenue / Session
    data.append({
        "practitioner": "Average Revenue / Session",
        "m_100": avg_rev, "m_80": avg_rev, "m_60": avg_rev, "m_act": avg_rev,
        "is_summary": 1, "is_currency": 1
    })

    # Total Revenue
    data.append({
        "practitioner": "Total Revenue",
        "m_100": avg_rev * t_m100, "m_80": avg_rev * t_m80, "m_60": avg_rev * t_m60, "m_act": therapy_sales,
        "is_summary": 1, "is_currency": 1
    })

    # Average Session / Patient
    data.append({
        "practitioner": "Avg. Session / Patient",
        "m_100": avg_sess_pat, "m_80": avg_sess_pat, "m_60": avg_sess_pat, "m_act": avg_sess_pat,
        "is_summary": 1
    })

    # Estimated Patients
    data.append({
        "practitioner": "Estimated Patients",
        "m_100": t_m100 / avg_sess_pat if avg_sess_pat else 0,
        "m_80": t_m80 / avg_sess_pat if avg_sess_pat else 0,
        "m_60": t_m60 / avg_sess_pat if avg_sess_pat else 0,
        "m_act": t_m_act / avg_sess_pat if avg_sess_pat else 0,
        "is_summary": 1
    })

    return data