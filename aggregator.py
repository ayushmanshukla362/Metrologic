def aggregate_panel_results(panels_data):
    """
    panels_data: {'front': dict, 'back': dict, 'side': dict}
    """
    consolidated = {
        "mrp": None,
        "net_quantity": None,
        "commodity_name": None,
        "manufacturer": None,
        "mfg_date": None
    }
    
    for panel_name, fields in panels_data.items():
        for key, field_obj in fields.items():
            if field_obj and field_obj.get("value"):
                # Conflict Check: Agar 2 panels par alag MRP mila
                if consolidated[key] and consolidated[key]["value"] != field_obj["value"]:
                    consolidated[key]["confidence"] = 0.50  # Conflict drops confidence to trigger REVIEW
                    consolidated[key]["conflict_detected"] = True
                elif not consolidated[key]:
                    consolidated[key] = field_obj

    return consolidated