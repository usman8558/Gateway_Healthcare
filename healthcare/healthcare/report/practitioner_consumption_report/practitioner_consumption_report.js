frappe.query_reports["Practitioner Consumption Report"] = {
    filters: [
        {
            fieldname: "month",
            label: __("Month"),
            fieldtype: "Select",
            options: "January\nFebruary\nMarch\nApril\nMay\nJune\nJuly\nAugust\nSeptember\nOctober\nNovember\nDecember",
            default: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][frappe.datetime.str_to_obj(frappe.datetime.nowdate()).getMonth()],
            reqd: 1
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
    treeview: true,
    name_field: "practitioner",
    
    formatter: function(value, row, column, data, default_formatter) {
        // ... (Aapka purana formatter ka code yahan aayega) ...
        // Default formatter se commas waghera lag jayenge
        value = default_formatter(value, row, column, data);
        
        // 🔥 NAYA SAFE PARSING: Commas ka masla khatam karne ke liye hum raw data use karenge
        let raw_value = data ? flt(data[column.fieldname]) : 0;

        // --- 1. UNIVERSAL BOLD ---
        if (data && (data.indent === 0 || data.bold)) {
            if (typeof value === "string" && !value.includes("<strong>")) {
                value = `<strong>${value}</strong>`;
            }
        }

        // --- 2. CAPACITY TABLE TITLE ROW ---
        if (data && data.practitioner === "CAPACITY AND REVENUE TABLE") {
            column.custom_style = {
                "background-color": "#e3f2fd", 
                "color": "#0d47a1",            
                "font-weight": "bold",
                "font-size": "13px"
            };
        }

        // --- 3. HEADER ROW INJECTION ---
        if (data && data.is_header) {
            column.custom_style = {"background-color": "#f8f9fa", "font-weight": "bold", "color": "#1a1a1a"};
            if (column.fieldname === "practitioner") return `<strong>Metric</strong>`;
            else if (data[column.fieldname]) return `<strong>${data[column.fieldname]}</strong>`; 
            return "";
        }

        // --- 4. CAPACITY TABLE DATA ROWS ---
        if (data && data.is_capacity_row) {
            
            // Utilization % formatting (raw_value use kiya)
            if (data.practitioner === "Utilization %" && column.fieldtype === "Float") {
                return `${raw_value.toFixed(2)}%`;
            }

            // Total Revenue Formatting (raw_value use kiya)
            if (data.practitioner === "Total Revenue" && column.fieldtype === "Float") {
                if (raw_value === 0) return ""; // Ab sirf tab blank hoga jab database se sach mein 0 aaye
                return `<span style="color:#28a745;"> ${format_currency(raw_value)}</span>`;
            }
        }

        // --- 5. ACTUAL CONSUMPTION BADGES ---
        if (data && data.practitioner === "Actual Consumption") {
            const target_cols = ["consumption", "rem_100", "rem_60"];
            
            if (target_cols.includes(column.fieldname)) {
                let badge_color = "#28a745"; 
                if (column.fieldname === "consumption") {
                    if (raw_value < 60) badge_color = "#dc3545"; 
                } else {
                    if (raw_value < 0) badge_color = "#007bff"; 
                }
                value = `<div style="background-color: ${badge_color}; color: white; padding: 4px 12px; border-radius: 15px; font-weight: bold; display: inline-block; min-width: 75px; text-align: center; font-size: 11px;">${value}</div>`;
            }
            column.custom_style = {"background-color": "#f0fdf4", "color": "#166534", "font-weight": "bold"};
        }

        return value;
    }
};