import frappe
from frappe import _
from frappe.utils import flt
import calendar

# --- Naya Helper Function Month se Dates nikalne ke liye ---
def get_date_range(filters):
    if not filters: 
        filters = {"month": "January", "year": "2026"}
        
    month_name = filters.get("month", "January")
    year = int(filters.get("year", 2026))
    
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    # Selected month ka number nikalna (1 se 12)
    month_idx = months.index(month_name) + 1
    
    start_date = f"{year}-{month_idx:02d}-01"
    last_day = calendar.monthrange(year, month_idx)[1]
    end_date = f"{year}-{month_idx:02d}-{last_day:02d}"
    
    return start_date, end_date


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data, filters)
    report_summary = get_report_summary(data, filters)
    
    return columns, data, None, chart, report_summary

def get_columns():
    return [
        {"label": _("Practitioner"), "fieldname": "practitioner", "fieldtype": "Data", "width": 260},
        {"label": _("Day Session"), "fieldname": "day_session", "fieldtype": "Float", "width": 150},
        {"label": _("Week Session"), "fieldname": "week_session", "fieldtype": "Float", "width": 150},
        {"label": _("Month Session"), "fieldname": "month_session", "fieldtype": "Float", "width": 130},
        {"label": _("Consumption %"), "fieldname": "consumption", "fieldtype": "Data", "width": 180},
        {"label": _("Rem. Cons. on 100%"), "fieldname": "rem_100", "fieldtype": "Data", "width": 180},
        {"label": _("Rem. Cons. on 60%"), "fieldname": "rem_60", "fieldtype": "Data", "width": 180}
    ]

def get_data(filters):
    start_date, end_date = get_date_range(filters)

    data = []
    
    practitioners = frappe.get_all("Healthcare Practitioner", 
        filters={"type": ["in", ["Therapist", "Both"]]},
        fields=["name", "first_name"]
    )

    # --- SECTION 1: 100% ---
    p100 = {"practitioner": "100 Percent Consumption", "day_session": 0, "week_session": 0, "month_session": 0, "consumption": "100%", "indent": 0, "bold": 1}
    for p in practitioners:
        p100["day_session"] += 14; p100["week_session"] += 70; p100["month_session"] += 280
        data.append({"practitioner": p.first_name, "day_session": 14, "week_session": 70, "month_session": 280, "consumption": "", "indent": 1})
    data.insert(0, p100)
    

    # --- SECTION 2: 60% ---
    p60 = {"practitioner": "60 Percent Consumption", "day_session": 0, "week_session": 0, "month_session": 0, "consumption": "60%", "indent": 0, "bold": 1}
    section2_start_index = len(data)
    for p in practitioners:
        m60 = 280 * 0.60; d60 = m60 / 20; w60 = d60 * 5
        p60["day_session"] += d60; p60["week_session"] += w60; p60["month_session"] += m60
        data.append({"practitioner": p.first_name, "day_session": d60, "week_session": w60, "month_session": m60, "consumption": "", "indent": 1})
    data.insert(section2_start_index, p60)

    # --- SECTION 3: ACTUAL ---
    p_act = {"practitioner": "Actual Consumption", "day_session": 0, "week_session": 0, "month_session": 0, "indent": 0, "bold": 1}
    section3_rows = []

    for p in practitioners:
        actual_count = frappe.db.sql("""
            SELECT COUNT(*) FROM `tabTherapy Automation` 
            WHERE healthcare_practitioner = %s AND booked = 1 AND date BETWEEN %s AND %s
        """, (p.name, start_date, end_date))[0][0] or 0
        
        m_act = flt(actual_count); w_act = m_act / 5; d_act = w_act / 5
        section3_rows.append({
            "practitioner": p.first_name, "day_session": d_act, "week_session": w_act, "month_session": m_act, "consumption": "", "indent": 1
        })
        p_act["day_session"] += d_act; p_act["week_session"] += w_act; p_act["month_session"] += m_act

    # --- PERCENTAGES CALCULATION ---
    if p100["month_session"] > 0:
        total_cons_perc = (p_act["month_session"] / p100["month_session"]) * 100
    else: 
        total_cons_perc = 0
        
    rem_100_val = 100 - total_cons_perc
    rem_60_val = 60 - total_cons_perc
        
    p_act["consumption"] = f"{flt(total_cons_perc, 2)}%"
    p_act["rem_100"] = f"{flt(rem_100_val, 2)}%"
    p_act["rem_60"] = f"{flt(rem_60_val, 2)}%"
    data.append(p_act); data.extend(section3_rows)

    # ==========================================================
    # --- SECTION 4: CAPACITY AND REVENUE TABLE ---
    # ==========================================================
    
    data.append({"practitioner": "", "indent": 0}) 
    data.append({"practitioner": "CAPACITY AND REVENUE TABLE", "indent": 0, "bold": 1})
    
    data.append({
        "practitioner": "HEADER_ROW_MARKER", 
        "day_session": f"Current {flt(total_cons_perc, 2)}%", 
        "week_session": "60% Utilization", 
        "month_session": "100% Utilization",
        "consumption": "",            
        "indent": 1, "is_header": 1
    })

    def add_cap_row(metric, curr, u60, u100):
        data.append({
            "practitioner": metric,
            "day_session": curr,      
            "week_session": u60,      
            "month_session": u100,    
            "consumption": "",        
            "indent": 1,
            "is_capacity_row": 1
        })
    
    total_therapists = len(practitioners)

    total_therapy_sessions = frappe.db.count("Therapy Session", filters={
        "start_date": ["between", [start_date, end_date]],
        "docstatus": 1 
    })

    month_cap_curr = total_therapy_sessions  
    month_cap_60 = 1512                      
    month_cap_100 = 2520                     

    day_session_curr = month_cap_curr / 20 if month_cap_curr > 0 else 0
    day_session_60 = month_cap_60 / 20
    day_session_100 = month_cap_100 / 20

    week_session_curr = day_session_curr * 5
    week_session_60 = day_session_60 * 5
    week_session_100 = day_session_100 * 5

    if month_cap_100 > 0:
        util_curr = (month_cap_curr / month_cap_100) * 100
        util_60 = (month_cap_60 / month_cap_100) * 100
        util_100 = (month_cap_100 / month_cap_100) * 100
    else:
        util_curr = 0; util_60 = 0; util_100 = 0

    total_sess_curr = month_cap_curr * (util_curr / 100)
    total_sess_60 = month_cap_60 * (util_60 / 100)
    total_sess_100 = month_cap_100 * (util_100 / 100)

    # ----------------------------------------------------------
    # 8. Average Revenue / Session 
    # ----------------------------------------------------------
    
    therapy_sales = frappe.db.sql("""
        SELECT SUM(grand_total) 
        FROM `tabSales Invoice` 
        WHERE docstatus = 1 
          AND posting_date BETWEEN %s AND %s 
          AND type = 'Therapy'
    """, (start_date, end_date))[0][0] or 0.0

    total_therapy_sales = flt(therapy_sales)

    # Teeno ko month_cap_curr se divide karna hai, isliye condition bhi month_cap_curr ki check hogi
    avg_rev_curr = (total_therapy_sales / month_cap_curr) if month_cap_curr > 0 else 0
    avg_rev_60 = (total_therapy_sales / month_cap_curr) if month_cap_curr > 0 else 0
    avg_rev_100 = (total_therapy_sales / month_cap_curr) if month_cap_curr > 0 else 0

    # ----------------------------------------------------------
    # 9. Total Revenue  
    # ----------------------------------------------------------
    tot_rev_curr = (avg_rev_curr * month_cap_curr) if month_cap_curr > 0 else 0
    tot_rev_60 = (avg_rev_60 * month_cap_60) if month_cap_60 > 0 else 0
    tot_rev_100 = (avg_rev_100 * month_cap_100) if month_cap_100 > 0 else 0

    avg_sess_patient = 837 / 17

    est_patient_curr = (month_cap_curr / avg_sess_patient) if avg_sess_patient > 0 else 0
    est_patient_60 = (month_cap_60 / avg_sess_patient) if avg_sess_patient > 0 else 0
    est_patient_100 = (month_cap_100 / avg_sess_patient) if avg_sess_patient > 0 else 0

    # ROW APPENDING
    add_cap_row("Therapists", total_therapists, total_therapists, total_therapists)
    add_cap_row("Monthly Capacity", month_cap_curr, month_cap_60, month_cap_100)
    add_cap_row("Session / Day (Total)", day_session_curr, day_session_60, day_session_100)
    add_cap_row("Session / Week (Total)", week_session_curr, week_session_60, week_session_100)
    add_cap_row("Utilization %", util_curr, util_60, util_100)
    add_cap_row("Total Sessions", total_sess_curr, total_sess_60, total_sess_100)
    add_cap_row("Average Revenue / Session", avg_rev_curr, avg_rev_60, avg_rev_100)
    add_cap_row("Total Revenue", tot_rev_curr, tot_rev_60, tot_rev_100)
    add_cap_row("Average Session / Patient", avg_sess_patient, avg_sess_patient, avg_sess_patient)
    add_cap_row("Estimated Patient", est_patient_curr, est_patient_60, est_patient_100)

    return data


# =================================================================
# FUNCTIONS: CHART AUR REPORT SUMMARY KE LIYE
# =================================================================

def get_chart_data(data, filters):
    if not data: return None
    
    consumed_capacity = 0
    total_capacity = 0
    
    for row in data:
        if row.get("practitioner") == "Monthly Capacity":
            consumed_capacity = flt(row.get("day_session"))
            total_capacity = flt(row.get("month_session"))
            break
            
    remaining_capacity = total_capacity - consumed_capacity if total_capacity > consumed_capacity else 0

    return {
        "data": {
            "labels": [_("Consumed"), _("Remaining")],
            "datasets": [{"name": _("Sessions"), "values": [consumed_capacity, remaining_capacity]}],
        },
        "type": "donut",
        "colors": ["#28a745", "#dc3545"], 
    }

def get_report_summary(data, filters):
    if not data: return None

    # Selected Month ki Dates yahan bhi mangwa li
    start_date, end_date = get_date_range(filters)

    therapists = 0; sessions = 0; utilization = 0; revenue = 0
    for row in data:
        prac = row.get("practitioner")
        if prac == "Therapists": therapists = flt(row.get("day_session"))
        elif prac == "Monthly Capacity": sessions = flt(row.get("day_session"))
        elif prac == "Utilization %": utilization = flt(row.get("day_session"), 2) 
        elif prac == "Total Revenue": revenue = flt(row.get("day_session"))

    # =====================================================
    # NAYA AUR SIMPLE LOGIC: SIRF CHECKBOX KO CHECK KAREGA
    # =====================================================
    
    # Active Patients (Left checkbox = 0) - Jo report ke end_date tak ban chuke they
    active_patients = frappe.db.sql("""
        SELECT COUNT(DISTINCT patient) 
        FROM `tabTherapy Plan` 
        WHERE docstatus < 2 
        AND `left` = 0
        AND start_date <= %s 
    """, (end_date,))[0][0] or 0

    # Left Patients (Left checkbox = 1) - Jo report ke end_date tak chhor chuke they
    left_patients = frappe.db.sql("""
        SELECT COUNT(DISTINCT patient) 
        FROM `tabTherapy Plan` 
        WHERE docstatus < 2 
        AND `left` = 1
        AND start_date <= %s 
    """, (end_date,))[0][0] or 0


    return [
        {
            "value": active_patients,
            "label": _("Active Patients"),
            "indicator": "Green",
            "datatype": "Int",
        },
        {
            "value": left_patients,
            "label": _("Left Patients"),
            "indicator": "Red",
            "datatype": "Int",
        },
        {
            "value": therapists,
            "label": _("Active Therapists"),
            "indicator": "Blue",
            "datatype": "Int",
        },
        {
            "value": sessions,
            "label": _("Total Sessions"),
            "indicator": "Green" if sessions > 0 else "Red",
            "datatype": "Int",
        },
        {
            "value": utilization,
            "label": _("Utilization %"),
            "indicator": "Green" if utilization >= 60 else "Orange",
            "datatype": "Float",
        },
        {
            "value": revenue,
            "label": _("Total Revenue"),
            "indicator": "Green",
            "datatype": "Currency",
            "currency": "PKR" 
        }
    ]