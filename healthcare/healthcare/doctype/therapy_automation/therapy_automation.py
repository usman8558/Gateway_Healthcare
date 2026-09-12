import frappe
from frappe.model.document import Document
from frappe.utils import today, to_timedelta ,getdate, add_days
from datetime import datetime

@frappe.whitelist()
def create_previous_sessions():
    """Create therapy sessions for previous dates"""
    try:
        today_date = getdate(today())
        frappe.logger().info(f"Therapy Automation: Checking for previous sessions")
        
        # Get records with dates before today and no therapy session created
        records = frappe.get_all(
            "Therapy Automation",
            filters=[
                ["date", "<", today_date],
                ["therapy_session", "=", ""]  # Only get records without sessions
            ],
            fields=["name", "date", "therapy_plan", "therapy_plan_detail", "patient", "therapy_type",
                    "healthcare_practitioner", "from_time", "to_time", "therapy_session"]
        )

        if not records:
            msg = "No previous therapy sessions found to create."
            frappe.logger().info(f"Therapy Automation: {msg}")
            return msg

        created = []
        skipped = 0

        for r in records:
            try:
                # Get the session date from therapy automation
                session_date = r.date
                
                # Create therapy session with the date from therapy automation
                session = frappe.new_doc("Therapy Session")
                session.therapy_plan = r.therapy_plan
                session.therapy_plan_detail = r.therapy_plan_detail
                session.patient = r.patient
                session.therapy_type = r.therapy_type
                session.practitioner = r.healthcare_practitioner
                session.start_date = session_date  # Use the date from therapy automation
                
                # Handle time fields
                if r.from_time:
                    session.from_time = r.from_time
                if r.to_time:
                    session.to_time = r.to_time
                
                # Calculate duration if both times are available
                if r.from_time and r.to_time:
                    from_time = frappe.utils.to_timedelta(str(r.from_time))
                    to_time = frappe.utils.to_timedelta(str(r.to_time))
                    duration_minutes = int((to_time - from_time).total_seconds() / 60)
                    if duration_minutes < 0:
                        duration_minutes = 0
                    session.duration = duration_minutes
                
                session.status = "Pending"
                session.therapy_automation = r.name
                session.flags.ignore_permissions = True
                session.insert()

                # Save back to Therapy Automation
                frappe.db.set_value("Therapy Automation", r.name, "therapy_session", session.name)
                created.append(session.name)
                frappe.db.commit()  # Commit after each creation
                
            except Exception as e:
                frappe.logger().error(f"Therapy Automation: Error creating session for {r.name}: {str(e)}")
                skipped += 1
                frappe.db.rollback()
                continue

        result = f"Created {len(created)} previous Therapy Sessions: {', '.join(created)}. Skipped {skipped} records with errors." if created else f"No previous sessions created. {skipped} records had errors."
        frappe.logger().info(f"Therapy Automation: {result}")
        return result

    except Exception as e:
        error_msg = f"Therapy Automation Error: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.db.rollback()
        return error_msg




@frappe.whitelist()
def create_today_sessions():
    """Create therapy sessions for today"""
    try:
        today_date = frappe.utils.today()
        frappe.logger().info(f"Therapy Automation: Checking for sessions on {today_date}")
        
        records = frappe.get_all(
            "Therapy Automation",
            filters={"date": today_date},
            fields=["name", "therapy_plan", "therapy_plan_detail", "patient", "therapy_type",
                    "healthcare_practitioner", "from_time", "to_time", "therapy_session"]
        )

        if not records:
            msg = "No therapy sessions scheduled for today."
            frappe.logger().info(f"Therapy Automation: {msg}")
            return msg

        created = []
        skipped = 0

        for r in records:
            # Skip if already created
            if r.therapy_session:
                skipped += 1
                continue

            # Calculate duration
            from_time = frappe.utils.to_timedelta(str(r.from_time))
            to_time = frappe.utils.to_timedelta(str(r.to_time))
            duration_minutes = int((to_time - from_time).total_seconds() / 60)
            if duration_minutes < 0:
                duration_minutes = 0

            # Create therapy session
            session = frappe.new_doc("Therapy Session")
            session.therapy_plan = r.therapy_plan
            session.therapy_plan_detail = r.therapy_plan_detail
            session.patient = r.patient
            session.therapy_type = r.therapy_type
            session.practitioner = r.healthcare_practitioner
            session.from_time = r.from_time
            session.to_time = r.to_time
            session.duration = duration_minutes
            session.status = "Pending"
            session.therapy_automation=r.name
            session.flags.ignore_permissions = True
            session.insert()

            # Save back to Therapy Automation
            frappe.db.set_value("Therapy Automation", r.name, "therapy_session", session.name)
            created.append(session.name)
            frappe.db.commit()  # Commit after each creation

        result = f"Created {len(created)} Therapy Sessions: {', '.join(created)}. Skipped {skipped} already created." if created else f"No new sessions created. {skipped} already existed."
        frappe.logger().info(f"Therapy Automation: {result}")
        return result

    except Exception as e:
        error_msg = f"Therapy Automation Error: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.db.rollback()
        return error_msg

class TherapyAutomation(Document):
    pass