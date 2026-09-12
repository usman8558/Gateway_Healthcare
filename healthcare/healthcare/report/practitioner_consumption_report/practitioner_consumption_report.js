frappe.query_reports["Practitioner Consumption Report"] = {
    filters: [
        {
            fieldname: "view",
            label: __("View"),
            fieldtype: "Select",
            options: "Monthly\nQuarterly\nYearly",
            default: "Monthly",
            reqd: 1,
            on_change: function() {
                // Dynamically Hide/Show dependent filters
                let view = frappe.query_report.get_filter_value('view');
                if (view === 'Monthly') {
                    frappe.query_report.toggle_filter_display('month', false);
                    frappe.query_report.toggle_filter_display('quarter', true);
                } else if (view === 'Quarterly') {
                    frappe.query_report.toggle_filter_display('month', true);
                    frappe.query_report.toggle_filter_display('quarter', false);
                } else {
                    // Yearly
                    frappe.query_report.toggle_filter_display('month', true);
                    frappe.query_report.toggle_filter_display('quarter', true);
                }
                frappe.query_report.refresh();
            }
        },
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: "January\nFebruary\nMarch\nApril\nMay\nJune\nJuly\nAugust\nSeptember\nOctober\nNovember\nDecember",
            default: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][frappe.datetime.str_to_obj(frappe.datetime.nowdate()).getMonth()]
        },
        {
            fieldname: "quarter",
            label: __("Quarter"),
            fieldtype: "Select",
            options: "Q1\nQ2\nQ3\nQ4",
            default: "Q1",
            hidden: 1
        },
        {
            fieldname: "year",
            label: __("Year"),
            fieldtype: "Select",
            options: "2024\n2025\n2026\n2027\n2028\n2029\n2030",
            default: frappe.datetime.str_to_obj(frappe.datetime.nowdate()).getFullYear().toString(),
            reqd: 1
        }
    ],
    
    onload: function(report) {
        // Ensure filters are correctly displayed when the report first loads
        let view = report.get_filter_value('view');
        if (view === 'Monthly') {
            report.toggle_filter_display('quarter', true);
        }
    },

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (!data) return value;

        // Apply % formatting to Capacity Used
        if (column.fieldname === "capacity_used") {
            let bold_format = data.capacity_used > 100 ? "font-weight: bold; color: #dc3545;" : "font-weight: 500;";
            return `<span style="${bold_format}">${data.capacity_used}%</span>`;
        }

        // Apply Beautiful UI Badges for Status
        if (column.fieldname === "status") {
            let status = data.status;
            let bg_color = "#6c757d"; // Default Gray
            let text_color = "#ffffff";

            if (status === "Excellent") { bg_color = "#28a745"; } // Green
            else if (status === "Good") { bg_color = "#007bff"; } // Blue
            else if (status === "Moderate") { bg_color = "#fd7e14"; } // Orange
            else if (status === "Overloaded") { bg_color = "#dc3545"; } // Red
            
            return `<div style="
                background-color: ${bg_color}; 
                color: ${text_color}; 
                padding: 4px 12px; 
                border-radius: 12px; 
                font-weight: 600; 
                font-size: 11px; 
                text-align: center; 
                display: inline-block; 
                min-width: 85px; 
                box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
                letter-spacing: 0.5px;">
                ${status.toUpperCase()}
            </div>`;
        }

        return value;
    }
};