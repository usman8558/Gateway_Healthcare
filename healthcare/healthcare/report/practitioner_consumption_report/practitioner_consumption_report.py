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
    chart = get_chart_data(data)
    report_summary = get_report_summary(data)
    
    return columns, data, None, chart, report_summary

def get_columns():
    return [
        {"label": _("Practitioner"), "fieldname": "practitioner", "fieldtype": "Data", "width": 250},
        {"label": _("Sessions"), "fieldname": "sessions", "fieldtype": "Int", "width": 120},
        {"label": _("Capacity Used"), "fieldname": "capacity_used", "fieldtype": "Float", "width": 150},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 150}
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
        if quarter == "Q1": 
            start_date, end_date = f"{year}-01-01", f"{year}-03-31"
        elif quarter == "Q2": 
            start_date, end_date = f"{year}-04-01", f"{year}-06-30"
        elif quarter == "Q3": 
            start_date, end_date = f"{year}-07-01", f"{year}-09-30"
        else: 
            start_date, end_date = f"{year}-10-01", f"{year}-12-31"
            
    else: # Yearly
        start_date, end_date = f"{year}-01-01", f"{year}-12-31"
        
    return start_date, end_date

def get_data(filters, start_date, end_date):
    view = filters.get("view", "Monthly")
    
    # Base configuration per your Excel metrics (100% Capacity)
    base_monthly_capacity = 260 
    
    if view == "Monthly":
        total_expected_capacity = base_monthly_capacity
    elif view == "Quarterly":
        total_expected_capacity = base_monthly_capacity * 3
    else:
        total_expected_capacity = base_monthly_capacity * 12

    practitioners = frappe.get_all(
        "Healthcare Practitioner", 
        filters={"type": ["in", ["Therapist", "Both"]]},
        fields=["name", "practitioner_name"] 
    )

    data = []
    
    for p in practitioners:
        # ?? NAYA LOGIC: Therapy Session Doctype se Submited records uthana
        sessions_count = frappe.db.count("Therapy Session", {
            "practitioner": p.name,  # Check agar aapki custom app me field ka naam 'healthcare_practitioner' hai, to ise change karlena
            "docstatus": 1,          # Sirf Submitted sessions count honge
            "start_date": ["between", [start_date, end_date]]
        })
        
        # Calculate Capacity Used %
        if total_expected_capacity > 0:
            capacity_used_perc = (sessions_count / total_expected_capacity) * 100
        else:
            capacity_used_perc = 0
            
        # Determine Status dynamically
        if capacity_used_perc > 100:
            status = "Overloaded"
        elif capacity_used_perc >= 80:
            status = "Excellent"
        elif capacity_used_perc >= 60:
            status = "Good"
        elif capacity_used_perc >= 40:
            status = "Moderate"
        else:
            status = "Low"

        data.append({
            "practitioner": p.practitioner_name or p.name,
            "sessions": sessions_count,
            "capacity_used": flt(capacity_used_perc, 2),
            "status": status,
            "expected_capacity": total_expected_capacity 
        })
        
    # Sort data by capacity used descending for better readability
    data.sort(key=lambda x: x["capacity_used"], reverse=True)
    return data

def get_chart_data(data):
    if not data:
        return None

    labels = []
    values = []
    colors = []

    for row in data:
        labels.append(row["practitioner"])
        values.append(row["capacity_used"])
        
        # Match bar colors to the UI status badges
        if row["status"] == "Overloaded": colors.append("#dc3545")
        elif row["status"] == "Excellent": colors.append("#28a745")
        elif row["status"] == "Good": colors.append("#007bff")
        elif row["status"] == "Moderate": colors.append("#fd7e14")
        else: colors.append("#6c757d")

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Capacity Used %"), 
                    "values": values
                }
            ]
        },
        "type": "bar",
        "colors": colors
    }

def get_report_summary(data):
    if not data:
        return []
        
    total_practitioners = len(data)
    total_sessions = sum(row["sessions"] for row in data)
    
    avg_capacity = sum(row["capacity_used"] for row in data) / total_practitioners if total_practitioners > 0 else 0
    highest_util = max(row["capacity_used"] for row in data) if data else 0
    lowest_util = min(row["capacity_used"] for row in data) if data else 0
    avg_sessions_per_prac = total_sessions / total_practitioners if total_practitioners > 0 else 0

    return [
        {"value": total_practitioners, "label": _("Total Practitioners"), "indicator": "Blue", "datatype": "Int"},
        {"value": total_sessions, "label": _("Total Sessions"), "indicator": "Blue", "datatype": "Int"},
        {"value": flt(avg_capacity, 2), "label": _("Average Capacity Used"), "indicator": "Green" if avg_capacity >= 60 else "Orange", "datatype": "Float"},
        {"value": flt(highest_util, 2), "label": _("Highest Utilization"), "indicator": "Green", "datatype": "Float"},
        {"value": flt(lowest_util, 2), "label": _("Lowest Utilization"), "indicator": "Red", "datatype": "Float"},
        {"value": flt(avg_sessions_per_prac, 0), "label": _("Avg Sessions/Practitioner"), "indicator": "Blue", "datatype": "Int"},
    ]