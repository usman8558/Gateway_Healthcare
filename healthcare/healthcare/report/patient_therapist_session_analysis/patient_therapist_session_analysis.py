# Copyright (c) 2026, VFG and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict
from datetime import datetime
from frappe.utils import getdate

def execute(filters=None):
    if not filters:
        filters = {}
    
    group_by = filters.get("group_by", "Practitioner-wise")
    
    columns = get_columns(group_by)
    data, total_sessions, unique_patients, unique_practitioners, chart_data = get_data(filters, group_by)
    
    # 1. Graphical Chart Generation
    chart = get_chart(chart_data, group_by)
    
    # 2. Top KPI Summary Cards (Number Cards above grid)
    report_summary = [
        {"value": total_sessions, "indicator": "Blue", "label": "Total Scheduled Sessions", "datatype": "Int"},
        {"value": len(unique_patients), "indicator": "Green", "label": "Total Unique Patients", "datatype": "Int"},
        {"value": len(unique_practitioners), "indicator": "Orange", "label": "Active Practitioners", "datatype": "Int"}
    ]
    
    # Return 5 parameters: columns, data, message (None), chart, report_summary
    return columns, data, None, chart, report_summary

def get_columns(group_by):
    if group_by == "Practitioner-wise":
        return [
            {"label": "Practitioner", "fieldname": "practitioner", "fieldtype": "Data", "width": 360},
            {"label": "Patient Name", "fieldname": "patient", "fieldtype": "Data", "width": 220},
            {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
            {"label": "Month", "fieldname": "month", "fieldtype": "Data", "width": 110},
            {"label": "Token Number", "fieldname": "token_no", "fieldtype": "Data", "width": 120},
            {"label": "Time", "fieldname": "from_time", "fieldtype": "Data", "width": 100},
            {"label": "Therapy Service", "fieldname": "therapy_type", "fieldtype": "Data", "width": 190}
        ]
    else:
        return [
            {"label": "Patient Name", "fieldname": "patient", "fieldtype": "Data", "width": 340},
            {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
            {"label": "Month", "fieldname": "month", "fieldtype": "Data", "width": 110},
            {"label": "Token Number", "fieldname": "token_no", "fieldtype": "Data", "width": 120},
            {"label": "Time", "fieldname": "from_time", "fieldtype": "Data", "width": 100},
            {"label": "Practitioner", "fieldname": "practitioner", "fieldtype": "Data", "width": 180},
            {"label": "Therapy Service", "fieldname": "therapy_type", "fieldtype": "Data", "width": 240}
        ]

def get_data(filters, group_by):
    conditions = []
    if filters.get("from_date"):
        conditions.append(f"date >= '{filters.get('from_date')}'")
    if filters.get("to_date"):
        conditions.append(f"date <= '{filters.get('to_date')}'")
    if filters.get("practitioner"):
        conditions.append(f"healthcare_practitioner = '{filters.get('practitioner')}'")
    if filters.get("patient"):
        conditions.append(f"patient = '{filters.get('patient')}'")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    records = frappe.db.sql(f"""
        SELECT 
            date,
            day,
            token_no,
            from_time,
            therapy_type,
            patient,
            COALESCE(patrictioner_name, healthcare_practitioner) as patrictioner_name
        FROM 
            `tabTherapy Automation`
        WHERE 
            {where_clause}
        ORDER BY 
            date ASC, token_no ASC
    """, as_dict=True)
    
    if not records:
        return [], 0, set(), set(), {}
        
    result = []
    unique_patients = set()
    unique_practitioners = set()
    chart_data = defaultdict(int)
    total_sessions = len(records)
    
    for r in records:
        unique_patients.add(r.patient)
        unique_practitioners.add(r.patrictioner_name)
        if group_by == "Practitioner-wise":
            chart_data[r.patrictioner_name] += 1
        else:
            chart_data[r.therapy_type] += 1
    
    if group_by == "Practitioner-wise":
        pract_map = defaultdict(lambda: defaultdict(list))
        for r in records:
            pract_map[r.patrictioner_name][r.patient].append(r)
            
        for pract_name, patients in pract_map.items():
            tot_pat = len(patients)
            tot_sess = sum(len(sess) for sess in patients.values())
            
            # Level 1: Colorful Gradient Header for Practitioner
            result.append({
                "practitioner": f"""<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 13px;">
                    👨‍⚕️ <b>{pract_name}</b> &nbsp;|&nbsp; 📊 {tot_sess} Sessions &nbsp;|&nbsp; 🧑‍🤝‍🧑 {tot_pat} Patients
                </div>"""
            })
            
            for pat_name, sessions in patients.items():
                # Level 2: Styled Soft Blue Header for Patient
                result.append({
                    "patient": f"""<div style="background-color: #edf2f7; color: #2d3748; padding: 4px 10px; border-radius: 4px; border-left: 4px solid #3182ce; font-weight: 600;">
                        👤 {pat_name} <span style="color: #718096; font-size: 11px; font-weight: normal;">({len(sessions)} Sessions)</span>
                    </div>"""
                })
                
                for s in sessions:
                    d_obj = getdate(s.date)
                    result.append({
                        "date": s.date,
                        "month": f'<span style="color: #4a5568; font-weight: 500;">📅 {d_obj.strftime("%B %Y")}</span>',
                        "token_no": f'<span style="background: #feebc8; color: #c05621; padding: 3px 10px; border-radius: 12px; font-weight: bold; font-size: 11px;">Token #{s.token_no}</span>',
                        "from_time": format_time_str(s.from_time),
                        "therapy_type": f'<span style="background: #e2e8f0; color: #2b6cb0; padding: 3px 10px; border-radius: 15px; font-weight: 600; font-size: 11px; border: 1px solid #cbd5e0;">💊 {s.therapy_type}</span>'
                    })
    else:
        pat_map = defaultdict(list)
        for r in records:
            pat_map[r.patient].append(r)
            
        for pat_name, sessions in pat_map.items():
            # Level 1: Styled Patient Header
            result.append({
                "patient": f"""<div style="background: linear-gradient(135deg, #3182ce 0%, #2b6cb0 100%); color: white; padding: 6px 12px; border-radius: 6px; font-weight: 600; font-size: 13px;">
                    👤 <b>{pat_name}</b> &nbsp;|&nbsp; 📊 Total {len(sessions)} Sessions
                </div>"""
            })
            
            for s in sessions:
                d_obj = getdate(s.date)
                result.append({
                    "date": s.date,
                    "month": f'<span style="color: #4a5568; font-weight: 500;">📅 {d_obj.strftime("%B %Y")}</span>',
                    "token_no": f'<span style="background: #feebc8; color: #c05621; padding: 3px 10px; border-radius: 12px; font-weight: bold; font-size: 11px;">Token #{s.token_no}</span>',
                    "from_time": format_time_str(s.from_time),
                    "practitioner": f'<span style="color: #2d3748; font-weight: 600;">👨‍⚕️ {s.patrictioner_name}</span>',
                    "therapy_type": f'<span style="background: #e2e8f0; color: #2b6cb0; padding: 3px 10px; border-radius: 15px; font-weight: 600; font-size: 11px; border: 1px solid #cbd5e0;">💊 {s.therapy_type}</span>'
                })
                
    return result, total_sessions, unique_patients, unique_practitioners, chart_data

def get_chart(chart_data, group_by):
    if not chart_data:
        return None
        
    labels = list(chart_data.keys())
    values = list(chart_data.values())
    
    chart_title = "Sessions per Practitioner" if group_by == "Practitioner-wise" else "Sessions by Therapy Service"
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": "Total Sessions",
                    "values": values
                }
            ]
        },
        "type": "bar",
        "colors": ['#667eea', '#48bb78', '#ed8936', '#f56565', '#9f7aea'],
        "title": chart_title
    }

def format_time_str(time_val):
    if not time_val:
        return ""
    try:
        time_str = str(time_val)
        t_obj = datetime.strptime(time_str[:5], "%H:%M")
        return f'<span style="color: #2d3748; font-weight: bold;">⏰ {t_obj.strftime("%I:%M %p")}</span>'
    except Exception:
        return str(time_val)