# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today, getdate,get_datetime, cint, nowdate
from datetime import datetime
 

from healthcare.healthcare.utils import validate_nursing_tasks



class TherapyPlan(Document):
    def validate(self):
        self.set_totals()
        self.set_status()
        self.release_sessions()   # ? function call

    def release_sessions(self):
        # ? Check sessions and release booked slots if completed
        for row in self.therapy_plan_details:
            # Without these guards a row with no practitioner (or an empty 0/0 row)
            # raises on every save, which rolls back the sessions_completed update
            # that triggered the save in the first place.
            if not row.healthcare_practitioner:
                continue

            if row.no_of_sessions and row.no_of_sessions == row.sessions_completed:
                # Fetch practitioner doc
                practitioner = frappe.get_doc("Healthcare Practitioner", row.healthcare_practitioner)

                # Loop through timings child table
                for slot in practitioner.get("time_slots"):   # ?? confirm child table fieldname
                    if (
                        slot.day == row.day
                        and str(slot.from_time) == str(row.start_time)
                        and str(slot.to_time) == str(row.end_time)
                    ):
                        slot.booked = 0   # ? Uncheck booked
                        practitioner.save(ignore_permissions=True)
                        frappe.msgprint(
                            f"Slot released for {row.healthcare_practitioner} on {row.day} "
                            f"({row.start_time} - {row.end_time})"
                        )
                        break

    def on_submit(self):
        validate_nursing_tasks(self)

    def set_status(self):
        if not self.total_sessions_completed:
            self.status = "Not Started"
        else:
            if self.total_sessions_completed < self.total_sessions:
                self.status = "In Progress"
            elif self.total_sessions_completed == self.total_sessions:
                self.status = "Completed"

    def set_totals(self):
        total_sessions = 0
        total_sessions_completed = 0
        for entry in self.therapy_plan_details:
            if entry.no_of_sessions:
                total_sessions += entry.no_of_sessions
            if entry.sessions_completed:
                total_sessions_completed += entry.sessions_completed

        self.db_set("total_sessions", total_sessions)
        self.db_set("total_sessions_completed", total_sessions_completed)

    @frappe.whitelist()
    def get_from_dates(doctype, txt, searchfield, start, page_len, filters):
        practitioner = filters.get("healthcare_practitioner")

        if not practitioner:
            return []

        return frappe.db.sql("""
            SELECT hct.from_date
            FROM `tabHealthcare Schedule Time Slot` hct
            WHERE hct.parent = %s
              AND hct.from_date LIKE %s
            ORDER BY hct.from_date DESC
        """, (practitioner, "%%%s%%" % txt))

    @frappe.whitelist()
    def set_therapy_details_from_template(self):
        # Add therapy types in the child table
        self.set("therapy_plan_details", [])
        therapy_plan_template = frappe.get_doc("Therapy Plan Template", self.therapy_plan_template)

        for data in therapy_plan_template.therapy_types:
            self.append(
                "therapy_plan_details",
                {"therapy_type": data.therapy_type, "no_of_sessions": data.no_of_sessions},
            )
        return self


def _parse_date_flexible(value):
    """Try multiple date formats to parse the child date."""
    if not value:
        return None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    try:
        return getdate(value)
    except Exception:
        return None

@frappe.whitelist()
def auto_create_therapy_sessions():
    """DEBUG - show date values in popups instead of logs"""
    current_date = getdate(today())
    frappe.msgprint(f"<b>Today's date (system):</b> {current_date}")

    therapy_plans = frappe.get_all(
        "Therapy Plan",
        fields=["name", "patient"],
        filters={"docstatus": 0}
    )

    msg = []
    for plan in therapy_plans:
        plan_doc = frappe.get_doc("Therapy Plan", plan.name)

        for row in plan_doc.therapy_plan_details:
            parsed = _parse_date_flexible(row.date)
            frappe.msgprint(f"<b>Plan:</b> {plan_doc.name}  <b>Raw:</b> {row.date} ? <b>Parsed:</b> {parsed}")

            if parsed == current_date:
                frappe.msgprint(f"<span style='color:green;'> Match found for plan {plan_doc.name}</span>")

    if not msg:
        frappe.msgprint("No Therapy Plan records found.")
    else:
        frappe.msgprint("<br>".join(msg))

    return "Date comparison test completed"


@frappe.whitelist()
def get_practitioner_slots(practitioner, day=None):
    filters = {"parent": practitioner, "booked": 0}
    if day:
        filters["day"] = day

    timings = frappe.get_all(
        "Healthcare Schedule Time Slot",
        filters=filters,
        fields=["name", "day", "from_time", "to_time", "booked"]
    )
    return timings



def get_available_tokens(practitioner, day, date, patient=None, exclude_booked=True):
    """
    Get available tokens for practitioner on specific day and date
    Optionally exclude tokens already booked by the same patient
    """
    try:
        prac = frappe.get_doc('Healthcare Practitioner', practitioner)
        if not prac or not hasattr(prac, 'time_slots'):
            return []
        
        # Get all tokens for the day from practitioner's time slots
        day_tokens = []
        for slot in prac.time_slots:
            slot_day = (slot.get('day') or '').strip().lower()
            if slot_day == day.strip().lower():
                day_tokens.append({
                    'token_no': slot.get('token_no'),
                    'from_time': slot.get('from_time'),
                    'to_time': slot.get('to_time'),
                    'booked_in_slots': slot.get('booked', 0)
                })
        
        if not day_tokens:
            return []
        
        # Filter out tokens booked in practitioner's slots
        if exclude_booked:
            day_tokens = [token for token in day_tokens if not token.get('booked_in_slots')]
        
        # Get tokens already booked in Therapy Automation for this practitioner-date-day
        booked_tokens = frappe.get_all('Therapy Automation',
            filters={
                'healthcare_practitioner': practitioner,
                'date': date,
                'day': day,
                'booked': 1,
                'docstatus': 0  # Only active records
            },
            fields=['token_no']
        )
        
        booked_token_nos = [str(b['token_no']) for b in booked_tokens if b.get('token_no')]
        
        # If patient is provided, also get tokens booked by this patient on the same date
        if patient:
            patient_booked_tokens = frappe.get_all('Therapy Automation',
                filters={
                    'patient': patient,
                    'date': date,
                    'booked': 1,
                    'docstatus': 0
                },
                fields=['token_no']
            )
            
            patient_booked_token_nos = [str(b['token_no']) for b in patient_booked_tokens if b.get('token_no')]
            booked_token_nos.extend(patient_booked_token_nos)
        
        # Filter out already booked tokens
        available_tokens = []
        for token in day_tokens:
            token_no_str = str(token.get('token_no'))
            if token_no_str not in booked_token_nos:
                available_tokens.append(token)
        
        # Sort tokens numerically if they are numbers
        try:
            available_tokens.sort(key=lambda x: int(x['token_no']) if x['token_no'].isdigit() else x['token_no'])
        except:
            available_tokens.sort(key=lambda x: x['token_no'])
        
        return available_tokens
        
    except Exception as e:
        frappe.log_error(f"Error in get_available_tokens: {str(e)}")
        return []

@frappe.whitelist()
def validate_token_availability(practitioner, day, token_no, date, patient=None):
    """
    Validate if a token is available for the given practitioner, day and date
    Now checks Therapy Automation records instead of just time slots
    Also checks patient's existing bookings
    """
    if not practitioner or not day or not token_no or not date:
        return {"available": False, "message": "Missing required parameters"}
    
    try:
        # First check if token exists in practitioner's time slots
        prac = frappe.get_doc('Healthcare Practitioner', practitioner)
        if not prac:
            return {"available": False, "message": "Practitioner not found"}
        
        token_found = False
        token_booked_in_slots = False
        
        if hasattr(prac, 'time_slots'):
            for slot in prac.time_slots:
                slot_day = (slot.get('day') or '').strip().lower()
                if slot_day == day.strip().lower() and str(slot.get('token_no')) == str(token_no):
                    token_found = True
                    if slot.get('booked'):
                        token_booked_in_slots = True
                    break
        
        if not token_found:
            return {"available": False, "message": f"Token {token_no} not found for {day}"}
        
        if token_booked_in_slots:
            return {"available": False, "message": f"Token {token_no} is booked in practitioner's time slots for {day}"}
        
        # Check 1: If token is already booked for the same practitioner, date, day and token
        existing_practitioner_booking = frappe.db.get_value('Therapy Automation', {
            'healthcare_practitioner': practitioner,
            'date': date,
            'day': day,
            'token_no': token_no,
            'booked': 1
        }, 'name')
        
        if existing_practitioner_booking:
            return {"available": False, "message": f"Token {token_no} is already booked for {day} on {date} with this practitioner"}
        
        # Check 2: If patient is provided, check if patient already has a booking for same date and token
        if patient:
            existing_patient_booking = frappe.db.get_value('Therapy Automation', {
                'patient': patient,
                'date': date,
                'token_no': token_no,
                'booked': 1,
                'docstatus': 0  # Only check submitted/active records
            }, 'name')
            
            if existing_patient_booking:
                return {"available": False, "message": f"Patient already has a booking for token {token_no} on {date}"}
        
        return {"available": True, "message": "Token is available"}
    
    except Exception as e:
        frappe.log_error(f"Error in validate_token_availability: {str(e)}")
        return {"available": False, "message": "Error validating token availability"}


@frappe.whitelist()
def get_first_token(practitioner, day, date, patient=None):
    """
    Get first available token (checking Therapy Automation records)
    Now also considers patient's existing bookings
    """
    available_tokens = get_available_tokens(practitioner, day, date, patient=patient, exclude_booked=True)
    
    if available_tokens:
        return available_tokens[0].get('token_no')
    return ""




@frappe.whitelist()
def get_time_slots_for_token(practitioner, day, token_no):
    """
    Get from_time and to_time for a specific token
    """
    if not practitioner or not day or not token_no:
        return {}
    
    try:
        prac = frappe.get_doc('Healthcare Practitioner', practitioner)
        if not prac:
            return {}
        
        if hasattr(prac, 'time_slots'):
            for slot in prac.time_slots:
                slot_day = (slot.get('day') or '').strip().lower()
                if (slot_day == day.strip().lower() and 
                    str(slot.get('token_no')) == str(token_no)):
                    return {
                        'from_time': slot.get('from_time'),
                        'to_time': slot.get('to_time')
                    }
        
        return {}
    
    except Exception as e:
        frappe.log_error(f"Error in get_time_slots_for_token: {str(e)}")
        return {}




@frappe.whitelist()
def unbook_practitioner_slot(practitioner, from_time, to_time, appointment_date=None):
    """
    Unbook a practitioner's time slot
    """
    try:
        # Find the slot to unbook
        filters = {
            "parent": practitioner,
            "from_time": from_time,
            "to_time": to_time,
            "booked": 1
        }
        
        if appointment_date:
            # If you have date-specific slots
            filters["appointment_date"] = appointment_date
        
        slot_name = frappe.db.get_value("Healthcare Schedule Time Slot", filters, "name")
        
        if slot_name:
            frappe.db.set_value("Healthcare Schedule Time Slot", slot_name, "booked", 0)
            frappe.db.commit()
            return {"success": True, "message": "Slot unbooked successfully"}
        else:
            return {"success": False, "message": "Slot not found"}
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Unbook Practitioner Slot Error")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def make_therapy_session(therapy_plan, patient, therapy_type, company, appointment=None):
    therapy_type_doc = frappe.get_doc("Therapy Type", therapy_type)

    therapy_session = frappe.new_doc("Therapy Session")
    therapy_session.therapy_plan = therapy_plan
    therapy_session.company = company
    therapy_session.patient = patient
    therapy_session.therapy_type = therapy_type_doc.name
    therapy_session.duration = therapy_type_doc.default_duration
    therapy_session.rate = therapy_type_doc.rate

    therapy_plan_doc = frappe.get_doc("Therapy Plan", therapy_plan)
    for d in therapy_plan_doc.therapy_plan_details:
        if d.therapy_type == therapy_type:   # same row selected
            therapy_session.from_time = d.start_time
            therapy_session.to_time = d.end_time
            therapy_session.day = d.day
            therapy_session.practitioner=d.healthcare_practitioner
            break

    if not therapy_session.exercises and therapy_type_doc.exercises:
        for exercise in therapy_type_doc.exercises:
            therapy_session.append(
                "exercises",
                (frappe.copy_doc(exercise)).as_dict(),
            )

    therapy_session.appointment = appointment

    if frappe.flags.in_test:
        therapy_session.start_date = today()

    return therapy_session.as_dict()


@frappe.whitelist()
def create_events_for_today():
    # Get all therapy plans where end_date is today
    today_date = today()
    therapy_plans = frappe.get_all(
        "Therapy Plan",
        filters={"end_date": today_date},
        fields=["name", "therapy_plan_template", "patient_name", "start_date", "end_date"]
    )

    if not therapy_plans:
        return "No therapy plans ending today."

    created_events = []
    for tp in therapy_plans:
        subject = f"{tp.therapy_plan_template} - {tp.patient_name} | {tp.start_date} to {tp.end_date}"

        # Assuming you want start and end on same day for now
        starts_on_dt = get_datetime(tp.start_date)
        ends_on_dt = get_datetime(tp.end_date)

        event = frappe.get_doc({
            "doctype": "Event",
            "subject": subject,
            "starts_on": starts_on_dt,
            "ends_on": ends_on_dt,
            "google_calendar": "demotboss8@gmail.com",
            "google_calendar_id": "03cd4dc270832a8f48dd3215ef41c94634347672f80626ed256f852186ac1b2e@group.calendar.google.com"
        })
        event.insert(ignore_permissions=True)
        created_events.append(event.name)

    return f"Created {len(created_events)} events: {', '.join(created_events)}"

@frappe.whitelist()
def make_sales_invoice(reference_name, patient, company, therapy_plan_template):
    from erpnext.stock.get_item_details import get_item_details

    si = frappe.new_doc("Sales Invoice")
    si.company = company
    si.patient = patient
    si.customer = frappe.db.get_value("Patient", patient, "customer")

    item = frappe.db.get_value("Therapy Plan Template", therapy_plan_template, "linked_item")
    price_list, price_list_currency = frappe.db.get_values(
        "Price List", {"selling": 1}, ["name", "currency"]
    )[0]
    args = {
        "doctype": "Sales Invoice",
        "item_code": item,
        "company": company,
        "customer": si.customer,
        "selling_price_list": price_list,
        "price_list_currency": price_list_currency,
        "plc_conversion_rate": 1.0,
        "conversion_rate": 1.0,
    }

    item_line = si.append("items", {})
    item_details = get_item_details(args)
    item_line.item_code = item
    item_line.qty = 1
    item_line.rate = item_details.price_list_rate
    item_line.amount = flt(item_line.rate) * flt(item_line.qty)
    item_line.reference_dt = "Therapy Plan"
    item_line.reference_dn = reference_name
    item_line.description = item_details.description

    si.set_missing_values(for_validate=True)
    return si
