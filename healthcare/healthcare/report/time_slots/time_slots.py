import frappe

def execute(filters=None):
    if not filters:
        filters = {}

    practitioner = filters.get("practitioner")
    date = filters.get("date")

    columns = [
        {"label": "Healthcare Practitioner", "fieldname": "healthcare_practitioner", "fieldtype": "Link", "options": "Healthcare Practitioner", "width": 200},
        {"label": "Practitioner Name", "fieldname": "practitioner_name", "fieldtype": "Data", "width": 200},
        {"label": "Day", "fieldname": "day", "fieldtype": "Data", "width": 100},
        {"label": "From Time", "fieldname": "from_time", "fieldtype": "Time", "width": 100},
        {"label": "To Time", "fieldname": "to_time", "fieldtype": "Time", "width": 100},
        {"label": "Token No", "fieldname": "token_no", "fieldtype": "Int", "width": 100},
    ]

    data = frappe.db.sql("""
        SELECT
            hp.name AS healthcare_practitioner,
            hp.first_name AS practitioner_name,
            ts.day AS day,
            ts.from_time AS from_time,
            ts.to_time AS to_time,
            CAST(ts.token_no AS UNSIGNED) AS token_no
        FROM
            `tabHealthcare Practitioner` hp
        JOIN
            `tabHealthcare Schedule Time Slot` ts 
            ON ts.parent = hp.name
        WHERE
            ts.parenttype = 'Healthcare Practitioner'
            AND hp.name = %(practitioner)s
            AND ts.day = DAYNAME(%(date)s)
            AND NOT EXISTS (
                SELECT 1 
                FROM `tabTherapy Automation` ta
                WHERE 
                    ta.healthcare_practitioner = hp.name
                    AND ta.token_no = ts.token_no
                    AND ta.date = %(date)s
                    AND ta.booked = 1
            )
        ORDER BY
            CAST(ts.token_no AS UNSIGNED) ASC
    """, {"practitioner": practitioner, "date": date}, as_dict=True)

    return columns, data
