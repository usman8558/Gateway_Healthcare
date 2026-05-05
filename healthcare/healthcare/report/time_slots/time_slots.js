// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt
frappe.query_reports["Time Slots"] = {
    "filters": [
        {
            "fieldname": "practitioner",
            "label": __("Healthcare Practitioner"),
            "fieldtype": "Link",
            "options": "Healthcare Practitioner",
            "reqd": 1
        },
        {
            "fieldname": "date",
            "label": __("Date"),
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.get_today()
        }
    ]
};
