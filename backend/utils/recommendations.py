def get_demand_label(predicted_count, zone_config):
    """Classify demand level based on zone thresholds"""
    
    normal_threshold = zone_config.get('threshold_normal', 15)
    high_threshold = zone_config.get('threshold_high', 25)
    
    if predicted_count <= normal_threshold:
        return "Normal Demand"
    elif predicted_count <= high_threshold:
        return "High Demand"
    else:
        return "Peak Risk"

def get_vehicle_recommendation(predicted_count, zone_config):
    """Generate vehicle dispatch recommendation"""
    
    base_vehicles = zone_config.get('base_vehicles', 3)
    
    # Base recommendation
    if predicted_count <= 10:
        motorcycles = base_vehicles
        vans = 0
        trucks = 0
        recommendation = f"Normal operations: {motorcycles} motorcycles"
        
    elif predicted_count <= 20:
        motorcycles = base_vehicles
        vans = 1
        trucks = 0
        recommendation = f"Increase capacity: {motorcycles} motorcycles + {vans} van"
        
    elif predicted_count <= 35:
        motorcycles = base_vehicles
        vans = 2
        trucks = 0
        recommendation = f"High demand period: {motorcycles} motorcycles + {vans} vans"
        
    else:
        motorcycles = base_vehicles
        vans = 3
        trucks = 1
        recommendation = f"PEAK ALERT: {motorcycles} motorcycles + {vans} vans + {trucks} truck"
    
    return recommendation, motorcycles, vans, trucks

def generate_actionable_message(zone_id, predicted_count, predicted_hour, zone_config):
    """Generate complete actionable message for dispatcher"""
    
    demand_label = get_demand_label(predicted_count, zone_config)
    recommendation, motorcycles, vans, trucks = get_vehicle_recommendation(predicted_count, zone_config)
    
    # Time description
    hour = predicted_hour.hour if hasattr(predicted_hour, 'hour') else predicted_hour
    
    if 5 <= hour < 12:
        time_desc = "morning"
    elif 12 <= hour < 17:
        time_desc = "afternoon"
    elif 17 <= hour < 22:
        time_desc = "evening"
    else:
        time_desc = "night"
    
    message = f"""
    📊 OmniRoute-DM Prediction for {zone_id}
    
    ⏰ {predicted_hour.strftime('%Y-%m-%d %H:00')} ({time_desc} shift)
    📦 Predicted Deliveries: {predicted_count}
    🚦 Demand Level: {demand_label}
    
    🚚 Dispatch Recommendation:
    {recommendation}
    
    💡 Note: This is a demand forecast only. Adjust based on real-time conditions.
    """
    
    return {
        'zone_id': zone_id,
        'predicted_hour': predicted_hour.strftime('%Y-%m-%d %H:00:00'),
        'predicted_count': int(predicted_count),
        'demand_level': demand_label,
        'recommendation': recommendation,
        'vehicle_breakdown': {
            'motorcycles': motorcycles,
            'vans': vans,
            'trucks': trucks
        },
        'message': message
    }