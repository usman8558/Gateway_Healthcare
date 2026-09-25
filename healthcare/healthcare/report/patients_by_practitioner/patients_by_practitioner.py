# Copyright (c) 2026, VFG and contributors
# For license information, please see license.txt

from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns()
	rows = get_therapy_session_rows(filters)
	data = get_data(rows)
	chart = get_chart(data)
	report_summary = get_report_summary(data)

	return columns, data, None, chart, report_summary


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be after To Date"))


def get_columns():
	return [
		{
			"label": _("Practitioner"),
			"fieldname": "practitioner",
			"fieldtype": "Link",
			"options": "Healthcare Practitioner",
			"width": 220,
		},
		{
			"label": _("Practitioner Name"),
			"fieldname": "practitioner_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Patient Count"),
			"fieldname": "patient_count",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Patient Names"),
			"fieldname": "patient_names",
			"fieldtype": "Small Text",
			"width": 560,
		},
		{
			"label": _("Session Count"),
			"fieldname": "session_count",
			"fieldtype": "Int",
			"width": 140,
		},
	]


def get_therapy_session_rows(filters):
	conditions = [
		"ts.docstatus < 2",
		"ts.practitioner IS NOT NULL",
		"ts.practitioner != ''",
		"ts.patient IS NOT NULL",
		"ts.patient != ''",
	]
	values = {}

	if filters.get("company"):
		conditions.append("ts.company = %(company)s")
		values["company"] = filters.company

	if filters.get("from_date"):
		conditions.append("ts.start_date >= %(from_date)s")
		values["from_date"] = filters.from_date

	if filters.get("to_date"):
		conditions.append("ts.start_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	if filters.get("practitioner"):
		conditions.append("ts.practitioner = %(practitioner)s")
		values["practitioner"] = filters.practitioner

	if filters.get("patient"):
		conditions.append("ts.patient = %(patient)s")
		values["patient"] = filters.patient

	if filters.get("therapy_type"):
		conditions.append("ts.therapy_type = %(therapy_type)s")
		values["therapy_type"] = filters.therapy_type

	if filters.get("status"):
		conditions.append("ts.status = %(status)s")
		values["status"] = filters.status

	return frappe.db.sql(
		f"""
		SELECT
			ts.practitioner,
			COALESCE(NULLIF(ts.doctor_name, ''), hp.practitioner_name, ts.practitioner) AS practitioner_name,
			ts.patient,
			COALESCE(NULLIF(ts.patient_name, ''), p.patient_name, ts.patient) AS patient_name
		FROM `tabTherapy Session` ts
		LEFT JOIN `tabHealthcare Practitioner` hp ON hp.name = ts.practitioner
		LEFT JOIN `tabPatient` p ON p.name = ts.patient
		WHERE {" AND ".join(conditions)}
		ORDER BY practitioner_name, patient_name
		""",
		values,
		as_dict=True,
	)


def get_data(rows):
	practitioner_map = OrderedDict()

	for row in rows:
		practitioner = row.practitioner
		if practitioner not in practitioner_map:
			practitioner_map[practitioner] = {
				"practitioner": practitioner,
				"practitioner_name": row.practitioner_name,
				"patients": OrderedDict(),
				"session_count": 0,
			}

		practitioner_entry = practitioner_map[practitioner]
		practitioner_entry["session_count"] += 1

		if row.patient not in practitioner_entry["patients"]:
			practitioner_entry["patients"][row.patient] = row.patient_name

	data = []
	for practitioner_entry in practitioner_map.values():
		patient_names = sorted(practitioner_entry["patients"].values())
		data.append(
			{
				"practitioner": practitioner_entry["practitioner"],
				"practitioner_name": practitioner_entry["practitioner_name"],
				"patient_count": len(patient_names),
				"patient_names": ", ".join(patient_names),
				"session_count": practitioner_entry["session_count"],
			}
		)

	data.sort(key=lambda row: (-row["patient_count"], row["practitioner_name"] or ""))
	return data


def get_chart(data):
	if not data:
		return None

	top_rows = data[:10]

	return {
		"data": {
			"labels": [row["practitioner_name"] or row["practitioner"] for row in top_rows],
			"datasets": [
				{
					"name": _("Patients"),
					"values": [row["patient_count"] for row in top_rows],
				}
			],
		},
		"type": "bar",
	}


def get_report_summary(data):
	total_patients = sum(row["patient_count"] for row in data)
	total_sessions = sum(row["session_count"] for row in data)

	return [
		{
			"value": len(data),
			"indicator": "Blue",
			"label": _("Practitioners"),
			"datatype": "Int",
		},
		{
			"value": total_patients,
			"indicator": "Green",
			"label": _("Assigned Patients"),
			"datatype": "Int",
		},
		{
			"value": total_sessions,
			"indicator": "Orange",
			"label": _("Therapy Sessions"),
			"datatype": "Int",
		},
	]
