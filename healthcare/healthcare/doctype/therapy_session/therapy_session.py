# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, get_link_to_form, get_time, getdate
from datetime import datetime, time, date, timedelta

from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
    get_income_account,
    get_receivable_account,
)
from healthcare.healthcare.doctype.nursing_task.nursing_task import NursingTask
from healthcare.healthcare.doctype.service_request.service_request import (
    update_service_request_status,
)
from healthcare.healthcare.utils import validate_nursing_tasks

@frappe.whitelist()
def get_available_slots(**kwargs):
    practitioner = kwargs.get("practitioner")
    date = kwargs.get("date")
    day = kwargs.get("day")

    if not practitioner or not date or not day:
        frappe.throw("Missing required parameters.")

    practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner)

    available = []

    for row in practitioner_doc.time_slots:
        if row.day == day:

            # Check if this token is booked for the selected date
            is_booked = frappe.db.exists(
                "Therapy Automation",
                {
                    "healthcare_practitioner": practitioner,
                    "date": date,        # FIXED
                    "token_no": row.token_no,
                    "booked": 1
                }
            )

            # If slot not booked ? add to available list
            if not is_booked:
                available.append({
                    "day": row.day,
                    "from_time": row.from_time,
                    "to_time": row.to_time,
                    "token_no": row.token_no
                })

    return available




#unbook slot 
@frappe.whitelist()
def unbook_slot(therapy_session):
    """Unbook practitioner slot linked to old therapy session"""
    doc = frappe.get_doc("Therapy Session", therapy_session)

    if not doc.practitioner or not doc.from_time or not doc.to_time or not doc.day:
        frappe.msgprint("No slot found to unbook for this session.")
        return False

    practitioner = frappe.get_doc("Healthcare Practitioner", doc.practitioner)

    # Loop through practitioner's time slots child table
    released = False
    for slot in practitioner.get("time_slots"):
        if (
            slot.day == doc.day
            and str(slot.from_time) == str(doc.from_time)
            and str(slot.to_time) == str(doc.to_time)
        ):
            slot.booked = 0   
            released = True

    if released:
        practitioner.save(ignore_permissions=True)

        # Also update Therapy Session status
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.msgprint(
            f"Slot released for {doc.practitioner} on {doc.day} "
            f"({doc.from_time} - {doc.to_time})"
        )
        return True
    else:
        frappe.msgprint("No matching slot found in practitioner's schedule.")
        return False


@frappe.whitelist()
def create_rescheduled_session(old_session, practitioner, appointment_date, day, from_time, to_time, token_no):

    old_doc = frappe.get_doc("Therapy Session", old_session)

    # ---------------------------------------------------
    # 1?? If old session is Draft ? Submit first
    # ---------------------------------------------------
    if old_doc.docstatus == 0:
        old_doc.submit()

    # ---------------------------------------------------
    # 2?? Cancel old session
    # ---------------------------------------------------
    if old_doc.docstatus == 1:
        old_doc.cancel()

    # ---------------------------------------------------
    # 3?? Uncheck BOOKED in OLD Therapy Automation
    # ---------------------------------------------------
    if old_doc.therapy_automation:
        old_ta = frappe.get_doc("Therapy Automation", old_doc.therapy_automation)
        old_ta.booked = 0
        old_ta.save(ignore_permissions=True)

    # ---------------------------------------------------
    # 4?? Create NEW Therapy Session (Draft)
    # ---------------------------------------------------
    new_doc = frappe.copy_doc(old_doc)
    
    new_doc.docstatus = 0  # Draft
    new_doc.status = "Pending"
    new_doc.practitioner = practitioner
    new_doc.appointment_date = appointment_date
    new_doc.day = day
    new_doc.from_time = from_time
    new_doc.to_time = to_time
    new_doc.token_no = token_no

    new_doc.save(ignore_permissions=True)

    # ---------------------------------------------------
    # 5?? Create NEW Therapy Automation with all fields
    # ---------------------------------------------------
    new_ta = frappe.get_doc({
        "doctype": "Therapy Automation",
        "therapy_plan": old_doc.therapy_plan,
        "patient": old_doc.patient,
        "therapy_type": old_doc.therapy_type,
        "healthcare_practitioner": practitioner,

        # Values coming from popup
        "date": appointment_date,
        "day": day,
        "from_time": from_time,
        "to_time": to_time,
        "token_no": token_no,

        # Link new session created above
        "therapy_session": new_doc.name,

        # Mark new slot as booked
        "booked": 1
    })

    new_ta.insert(ignore_permissions=True)

    # ---------------------------------------------------
    # 6?? Link new automation back to new session
    # ---------------------------------------------------
    new_doc.therapy_automation = new_ta.name
    new_doc.save(ignore_permissions=True)

    return new_doc.name




class TherapySession(Document):
    def validate(self):
        self.set_exercises_from_therapy_type()
        self.validate_duplicate()
        self.set_total_counts()
        self.unbooked_slot()
        # self.create_event()

    def after_insert(self):
        if self.service_request:
            update_service_request_status(
                self.service_request, self.doctype, self.name, "completed-Request Status"
            )

        self.create_nursing_tasks(post_event=False)

    def on_update(self):
        if self.appointment:
            frappe.db.set_value("Patient Appointment", self.appointment, "status", "Closed")

    def on_cancel(self):
        if self.appointment:
            frappe.db.set_value("Patient Appointment", self.appointment, "status", "Open")
        if self.service_request:
            frappe.db.set_value("Service Request", self.service_request, "status", "active-Request Status")

        self.update_sessions_count_in_therapy_plan(on_cancel=True)

    def validate_duplicate(self):
      # Convert start_date string to date object
      start_date_obj = getdate(self.start_date)
      
      end_time = datetime.combine(
          start_date_obj, get_time(self.start_time)
      ) + timedelta(minutes=flt(self.duration))

      overlaps = frappe.db.sql(
          """
      select
          name
      from
          `tabTherapy Session`
      where
          start_date=%s and name!=%s and docstatus!=2
          and (practitioner=%s or patient=%s) and
          ((start_time<%s and start_time + INTERVAL duration MINUTE>%s) or
          (start_time>%s and start_time<%s) or
          (start_time=%s))
      """,
          (
              self.start_date,
              self.name,
              self.practitioner,
              self.patient,
              self.start_time,
              end_time.time(),
              self.start_time,
              end_time.time(),
              self.start_time,
          ),
      )

      # if overlaps:
      #     overlapping_details = _("Therapy Session overlaps with {0}").format(
      #         get_link_to_form("Therapy Session", overlaps[0][0])
      #     )
      #     frappe.throw(overlapping_details, title=_("Therapy Sessions Overlapping"))

    def on_submit(self):
        validate_nursing_tasks(self)
        self.update_sessions_count_in_therapy_plan()
        self.completed_session_released()

        if self.service_request:
            frappe.db.set_value(
                "Service Request", self.service_request, "status", "completed-Request Status"
            )
    def create_event(self):
      if self.status == "Pending":
          therapy_type = self.therapy_type or ""
          patient = self.patient_name or ""
          time_range = f"{self.from_time}-{self.to_time}"
          subject = f"{therapy_type}-{patient} | {time_range}"

          if self.start_date and self.from_time and self.to_time:
              # Use Frappe's get_datetime for proper datetime conversion
              starts_on = f"{self.start_date} {self.from_time}"
              ends_on = f"{self.start_date} {self.to_time}"
              
              # Convert to datetime objects if needed
              starts_on_dt = frappe.utils.get_datetime(starts_on)
              ends_on_dt = frappe.utils.get_datetime(ends_on)


              # ---------- Create Event ----------
              event = frappe.get_doc({
                  "doctype": "Event",
                  "subject": subject,
                  "starts_on": starts_on_dt,
                  "ends_on": ends_on_dt,
                  "google_calendar": self.doctor_name,
                  "google_calendar_id":"19f2e10d8709e15b209f0e4e6ec67ac781bc2714e3c0ffeb1571d3f31a3cf28e@group.calendar.google.com"
              })
              event.insert(ignore_permissions=True)

    def unbooked_slot(self):
        """When therapy session is completed, uncheck booked in Therapy Automation"""
        if self.status == "Completed" and self.therapy_automation:
            try:
                ta = frappe.get_doc("Therapy Automation", self.therapy_automation)

                if ta.booked:  # only update if it's checked
                    ta.booked = 0
                    ta.save(ignore_permissions=True)
                    frappe.db.commit()

                    frappe.logger().info(
                        f"Therapy Automation {ta.name}: booked unchecked because session {self.name} completed"
                    )

            except Exception as e:
                frappe.logger().error(f"Error updating booked in Therapy Automation: {e}")


    def completed_session_released(self):
        if not self.status:
            self.status = "Completed"
            frappe.db.set_value("Therapy Session", self.name, "status", "Completed")

        if self.therapy_plan:
            try:
                therapy_plan = frappe.get_doc("Therapy Plan", self.therapy_plan)

                for row in therapy_plan.get("therapy_plan_details"):
                    if (
                        row.day == self.day
                        and str(row.start_time) == str(self.from_time)
                        and str(row.end_time) == str(self.to_time)
                    ):
                        if row.no_of_sessions == row.sessions_completed:
                            if self.practitioner:
                                practitioner = frappe.get_doc("Healthcare Practitioner", self.practitioner)
                                for slot in practitioner.get("time_slots"):
                                    if (
                                        slot.day == row.day
                                        and str(slot.from_time) == str(row.start_time)
                                        and str(slot.to_time) == str(row.end_time)
                                    ):
                                        slot.booked = 0  # ? Release slot
                                practitioner.save(ignore_permissions=True)

                                frappe.msgprint(
                                    f"Slot released for {self.practitioner} on {row.day} "
                                    f"({row.start_time} - {row.end_time})"
                                )
            except Exception as e:
                frappe.log_error(f"Error releasing slot for {self.name}: {e}", "Therapy Session on_submit")



    def create_nursing_tasks(self, post_event=True):
        template = frappe.db.get_value("Therapy Type", self.therapy_type, "nursing_checklist_template")
        if template:
            NursingTask.create_nursing_tasks_from_template(
                template,
                self,
                start_time=frappe.utils.get_datetime(f"{self.start_date} {self.start_time}"),
                post_event=post_event,
            )

    def update_sessions_count_in_therapy_plan(self, on_cancel=False):
        therapy_plan = frappe.get_doc("Therapy Plan", self.therapy_plan)
        for entry in therapy_plan.therapy_plan_details:
            if entry.therapy_type == self.therapy_type:
                if on_cancel:
                    entry.sessions_completed -= 1
                else:
                    entry.sessions_completed += 1
        therapy_plan.save()

    def set_total_counts(self):
        target_total = 0
        counts_completed = 0
        for entry in self.exercises:
            if entry.counts_target:
                target_total += entry.counts_target
            if entry.counts_completed:
                counts_completed += entry.counts_completed

        self.db_set("total_counts_targeted", target_total)
        self.db_set("total_counts_completed", counts_completed)

    def set_exercises_from_therapy_type(self):
        if self.therapy_type and not self.exercises:
            therapy_type_doc = frappe.get_cached_doc("Therapy Type", self.therapy_type)
            if therapy_type_doc.exercises:
                for exercise in therapy_type_doc.exercises:
                    self.append(
                        "exercises",
                        (frappe.copy_doc(exercise)).as_dict(),
                    )

    def before_insert(self):
        if self.service_request:
            therapy_session = frappe.db.exists(
                "Therapy Session",
                {"service_request": self.service_request, "docstatus": ["!=", 2]},
            )
            if therapy_session:
                frappe.throw(
                    _("Therapy Session {0} already created from service request {1}").format(
                        frappe.bold(get_link_to_form("Therapy Session", therapy_session)),
                        frappe.bold(get_link_to_form("Service Request", self.service_request)),
                    ),
                    title=_("Already Exist"),
                )


@frappe.whitelist()
def create_therapy_session(source_name, target_doc=None):
    def set_missing_values(source, target):
        therapy_type = frappe.get_doc("Therapy Type", source.therapy_type)
        target.exercises = therapy_type.exercises

    doc = get_mapped_doc(
        "Patient Appointment",
        source_name,
        {
            "Patient Appointment": {
                "doctype": "Therapy Session",
                "field_map": [
                    ["appointment", "name"],
                    ["patient", "patient"],
                    ["patient_age", "patient_age"],
                    ["gender", "patient_sex"],
                    ["therapy_type", "therapy_type"],
                    ["therapy_plan", "therapy_plan"],
                    ["practitioner", "practitioner"],
                    ["department", "department"],
                    ["start_date", "appointment_date"],
                    ["start_time", "appointment_time"],
                    ["service_unit", "service_unit"],
                    ["company", "company"],
                    ["invoiced", "invoiced"],
                ],
            }
        },
        target_doc,
        set_missing_values,
    )

    return doc

@frappe.whitelist()
def get_session_details(session_name):
    session = frappe.get_doc("Therapy Session", session_name)

    # Fetch patient DOB
    dob = frappe.db.get_value("Patient", session.patient, "dob")

    # Calculate age
    age = ""
    if dob:
        today = date.today()
        age = today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )

    return {
        "patient_name": session.patient,
        "creator": session.owner,
        "age": age
    }



@frappe.whitelist()
def create_progress_note(therapy_session, patient_name, diagnosis, age, table_rows):
    try:
        # Validate required fields
        if not diagnosis:
            frappe.throw("Diagnosis is required")
        if not age:
            frappe.throw("Age is required")

        # Parse table_rows if it's a JSON string
        if isinstance(table_rows, str):
            import json
            try:
                table_rows = json.loads(table_rows)
            except json.JSONDecodeError:
                frappe.throw("Invalid progress notes data")

        # Create Progress Note
        doc = frappe.new_doc("Progress Notes")
        doc.therapy_session = therapy_session
        doc.patient_name = patient_name
        doc.diagnosis = diagnosis
        doc.age = age

        # Insert child table rows
        if table_rows:
            for row in table_rows:
                child = doc.append("progress_notes_ct", {})
                child.date = row.get("date")
                child.target = row.get("target")
                child.activities = row.get("activities")
                child.behavior_observation = row.get("behavior_observation")
                child.user = row.get("user")

        doc.insert(ignore_permissions=True)
        doc.submit()

        # Submit the Therapy Session
        therapy_submitted = False
        therapy_message = ""
        
        therapy_doc = frappe.get_doc("Therapy Session", therapy_session)
        if therapy_doc.docstatus == 0:  # Draft state
            try:
                therapy_doc.status="Completed"
                therapy_doc.submit()
                therapy_submitted = True
                therapy_message = "Progress Note created and Therapy Session submitted successfully!"
            except Exception as e:
                therapy_message = f"Progress Note created but Therapy Session submission failed: {str(e)}"
        elif therapy_doc.docstatus == 1:  # Already submitted
            therapy_message = "Progress Note created successfully! (Therapy Session was already submitted)"
        else:  # Cancelled
            therapy_message = "Progress Note created! (Therapy Session is cancelled and cannot be submitted)"

        return {
            "progress_note": doc.name,
            "therapy_session_submitted": therapy_submitted,
            "message": therapy_message
        }

    except Exception as e:
        frappe.log_error(f"Error in create_progress_note: {str(e)}")
        frappe.throw("Failed to create progress note. Please try again.")





@frappe.whitelist()
def invoice_therapy_session(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.customer = frappe.db.get_value("Patient", source.patient, "customer")
        target.due_date = getdate()
        target.debit_to = get_receivable_account(source.company)
        item = target.append("items", {})
        item = get_therapy_item(source, item)
        target.set_missing_values(for_validate=True)

    doc = get_mapped_doc(
        "Therapy Session",
        source_name,
        {
            "Therapy Session": {
                "doctype": "Sales Invoice",
                "field_map": [
                    ["patient", "patient"],
                    ["referring_practitioner", "practitioner"],
                    ["company", "company"],
                    ["due_date", "start_date"],
                ],
            }
        },
        target_doc,
        set_missing_values,
    )

    return doc


def get_therapy_item(therapy, item):
    item.item_code = frappe.db.get_value("Therapy Type", therapy.therapy_type, "item")
    item.description = _("Therapy Session Charges: {0}").format(therapy.practitioner)
    item.income_account = get_income_account(therapy.practitioner, therapy.company)
    item.cost_center = frappe.get_cached_value("Company", therapy.company, "cost_center")
    item.rate = therapy.rate
    item.amount = therapy.rate
    item.qty = 1
    item.reference_dt = "Therapy Session"
    item.reference_dn = therapy.name
    return item
