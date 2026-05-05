frappe.query_reports["Therapy Plan Summary"] = {
    filters: [
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: [
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December"
            ],
            default: frappe.datetime.str_to_obj(frappe.datetime.get_today()).toLocaleString("default", { month: "long" }),
            reqd: 0
        },
	{
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            options: [
                "",
                "2025",
                "2026",
                "2027"
            ],
	default:"2026",

            reqd: 0
        },

        {
            fieldname: "patient",
            label: __("Patient"),
            fieldtype: "Link",
            options: "Patient",
            reqd: 0
        },
        {
            fieldname: "therapy_plan_template",
            label: __("Package Name"),
            fieldtype: "Link",
            options: "Therapy Plan Template",
            reqd: 0
        },
        {
            fieldname: "reference",
            label: __("Reference"),
            fieldtype: "Select",
            options: [
                "",
                "Referred from Clinic to Therapy"
            ],
            reqd: 0
        }
    ]
};
