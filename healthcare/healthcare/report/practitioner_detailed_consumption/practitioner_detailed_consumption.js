frappe.query_reports["Practitioner Detailed Consumption"] = {
    filters: [
        {
            fieldname: "view", 
            label: __("View"), 
            fieldtype: "Select", 
            options: "Monthly\nQuarterly\nYearly", 
            default: "Monthly",
            on_change: function() {
                let view = frappe.query_report.get_filter_value('view');
                frappe.query_report.toggle_filter_display('month', view !== 'Monthly');
                frappe.query_report.toggle_filter_display('quarter', view !== 'Quarterly');
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
        let view = report.get_filter_value('view');
        if (view === 'Monthly') {
            report.toggle_filter_display('quarter', true);
            report.toggle_filter_display('month', false);
        }
    },

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;
        let c = column.fieldname;

        // --- SECTION INJECTIONS FORMATTING ---
        
        if (data.is_blank) {
            column.custom_style = {"background-color": "#ffffff", "border": "none"};
            return "";
        }

        if (data.is_section_header) {
            column.custom_style = {"background-color": "#e3f2fd", "color": "#0d47a1", "font-weight": "bold", "font-size": "13px"};
            if (c === "practitioner") return `<strong>${value}</strong>`;
            return "";
        }

        if (data.is_summary) {
            let target_cols = ['m_100', 'm_80', 'm_60', 'm_act'];
            
            // Only show values in the Month/Period columns for summary rows
            if (!target_cols.includes(c) && c !== 'practitioner') {
                return ""; // Hide Days/Weeks blocks for Revenue rows
            }
            
            if (c === 'practitioner') {
                column.custom_style = {"font-weight": "600", "color": "#333"};
                return value;
            }

            if (target_cols.includes(c)) {
                let raw_val = data[c] ? parseFloat(data[c]) : 0;
                
                // Color mapping to keep vertical alignment looking great
                if (c === 'm_100') column.custom_style = { "background-color": "#f8f9fa", "color": "#495057", "font-weight": "600" };
                else if (c === 'm_80') column.custom_style = { "background-color": "#fffdf2", "color": "#856404", "font-weight": "600" };
                else if (c === 'm_60') column.custom_style = { "background-color": "#fff5f5", "color": "#c53030", "font-weight": "600" };
                else if (c === 'm_act') column.custom_style = { "background-color": "#f0fdf4", "color": "#166534", "font-weight": "bold" };

                if (data.is_currency) {
                    return format_currency(raw_val);
                } else {
                    return raw_val.toFixed(2);
                }
            }
        }

        // --- NORMAL ROWS FORMATTING ---
        
        if (data.is_total_row) {
            column.custom_style = {"font-weight": "bold", "background-color": "#e2e8f0", "color": "#1a202c"};
            return value;
        }

        if (['d_100', 'w_100', 'm_100'].includes(c)) column.custom_style = { "background-color": "#f8f9fa", "color": "#495057" };
        else if (['d_80', 'w_80', 'm_80'].includes(c)) column.custom_style = { "background-color": "#fffdf2", "color": "#856404" };
        else if (['d_60', 'w_60', 'm_60'].includes(c)) column.custom_style = { "background-color": "#fff5f5", "color": "#c53030" };
        else if (['d_act', 'w_act', 'm_act'].includes(c)) column.custom_style = { "background-color": "#f0fdf4", "color": "#166534", "font-weight": "500" };
        else if (c === 'util_perc') return `<span style="font-weight: bold;">${parseFloat(data.util_perc).toFixed(1)}%</span>`;
        else if (c === 'status' && data.status) {
            let bg = "#6c757d"; 
            if (data.status === "Excellent") bg = "#28a745"; 
            else if (data.status === "Good") bg = "#007bff"; 
            else if (data.status === "Moderate") bg = "#fd7e14"; 
            else if (data.status === "Overloaded") bg = "#dc3545"; 
            return `<div style="background-color: ${bg}; color: white; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px; text-align: center;">${data.status.toUpperCase()}</div>`;
        }

        if (typeof value === "string" && value.includes(".")) {
            let parsed = parseFloat(value);
            if (!isNaN(parsed)) value = parsed.toString();
        }

        return value;
    }
};