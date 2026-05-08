from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from database.db_config import db_config
import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import bcrypt

app = Flask(__name__)
CORS(app)

# ============ SERVE FRONTEND FILES ============
@app.route('/')
def serve_index():
    return send_from_directory('../frontend', 'index.html')

@app.route('/<path:path>')
def serve_frontend(path):
    try:
        return send_from_directory('../frontend', path)
    except:
        # If file doesn't exist, return index.html (for SPA routing)
        return send_from_directory('../frontend', 'index.html')

# ============ DATABASE CONNECTION ============
def get_db_connection():
    """Get database connection using db_config"""
    return db_config.get_connection()

# ============ LOAD MODELS ============
try:
    reg_model = joblib.load('backend/models/regression_model.pkl')
    cls_model = joblib.load('backend/models/classification_model.pkl')
    scaler = joblib.load('backend/models/scaler.pkl')
    with open('backend/models/feature_columns.txt', 'r') as f:
        feature_columns = f.read().strip().split(',')
    models_loaded = True
    print("✅ Models loaded successfully")
except Exception as e:
    print(f"⚠️ Models not loaded: {e}")
    models_loaded = False
    feature_columns = []

# ============ HEALTH CHECK ============
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'models_loaded': models_loaded})

# ============ PREDICTION API ============
@app.route('/api/predict', methods=['POST'])
def predict():
    if not models_loaded:
        return jsonify({'success': False, 'error': 'Models not loaded'})
    
    data = request.json
    zone_id = data.get('zone_id')
    datetime_str = data.get('datetime')
    
    # Get zone config
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM zones WHERE zone_id = %s", (zone_id,))
    zone_config = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not zone_config:
        return jsonify({'success': False, 'error': 'Zone not found'})
    
    # Prepare features
    pred_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
    
    # Get recent data for lags
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT delivery_count, delivery_timestamp 
        FROM delivery_records 
        WHERE zone_id = %s AND delivery_timestamp < %s 
        ORDER BY delivery_timestamp DESC LIMIT 25
    """, (zone_id, datetime_str))
    recent = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Build feature vector
    features = {}
    
    # Time features
    features['hour'] = pred_datetime.hour
    features['hour_sin'] = np.sin(2 * np.pi * pred_datetime.hour / 24)
    features['hour_cos'] = np.cos(2 * np.pi * pred_datetime.hour / 24)
    features['day_of_week'] = pred_datetime.weekday()
    features['dow_sin'] = np.sin(2 * np.pi * pred_datetime.weekday() / 7)
    features['dow_cos'] = np.cos(2 * np.pi * pred_datetime.weekday() / 7)
    features['month'] = pred_datetime.month
    features['is_weekend'] = 1 if pred_datetime.weekday() >= 5 else 0
    features['is_morning_rush'] = 1 if 7 <= pred_datetime.hour <= 9 else 0
    features['is_evening_rush'] = 1 if 17 <= pred_datetime.hour <= 19 else 0
    features['is_lunch_hour'] = 1 if 12 <= pred_datetime.hour <= 13 else 0
    
    # Lag features
    recent_counts = [r['delivery_count'] for r in recent]
    for lag in [1, 2, 3, 6, 12, 24]:
        if len(recent_counts) >= lag:
            features[f'lag_{lag}h'] = recent_counts[lag-1]
        else:
            features[f'lag_{lag}h'] = 0
    
    # Rolling features
    for window in [3, 6, 12, 24]:
        if len(recent_counts) >= window:
            window_data = recent_counts[:window]
            features[f'rolling_mean_{window}h'] = np.mean(window_data)
            features[f'rolling_std_{window}h'] = np.std(window_data)
        else:
            features[f'rolling_mean_{window}h'] = 0
            features[f'rolling_std_{window}h'] = 0
    
    # Create feature array
    X = np.array([[features.get(col, 0) for col in feature_columns]])
    X_scaled = scaler.transform(X)
    
    # Predict
    pred_count = reg_model.predict(X_scaled)[0]
    pred_count = max(0, int(round(pred_count)))
    
    # Demand level
    if pred_count <= zone_config['threshold_normal']:
        demand_level = "Normal Demand"
    elif pred_count <= zone_config['threshold_high']:
        demand_level = "High Demand"
    else:
        demand_level = "Peak Risk"
    
    # Vehicle recommendation
    base = zone_config['base_vehicles']
    if pred_count <= 10:
        motorcycles = base
        vans = 0
        trucks = 0
        recommendation = f"Normal operations: {motorcycles} motorcycles"
    elif pred_count <= 20:
        motorcycles = base
        vans = 1
        trucks = 0
        recommendation = f"Increase capacity: {motorcycles} motorcycles + {vans} van"
    elif pred_count <= 35:
        motorcycles = base
        vans = 2
        trucks = 0
        recommendation = f"High demand period: {motorcycles} motorcycles + {vans} vans"
    else:
        motorcycles = base
        vans = 3
        trucks = 1
        recommendation = f"PEAK ALERT: {motorcycles} motorcycles + {vans} vans + {trucks} truck"
    
    # Save prediction
    conn = get_db_connection()
    if conn is not None:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions_log (zone_id, predicted_hour, predicted_count, demand_level, recommendation)
            VALUES (%s, %s, %s, %s, %s)
        """, (zone_id, datetime_str, pred_count, demand_level, recommendation))
        conn.commit()
        cursor.close()
        conn.close()
    
    return jsonify({
        'success': True,
        'prediction': {
            'zone_id': zone_id,
            'datetime': datetime_str,
            'predicted_deliveries': pred_count,
            'demand_level': demand_level,
            'recommendation': recommendation,
            'vehicle_breakdown': {
                'motorcycles': motorcycles,
                'vans': vans,
                'trucks': trucks
            },
            'confidence_interval': [max(0, pred_count - 5), pred_count + 5],
            'full_message': f"Zone: {zone_id}\nTime: {datetime_str}\nPredicted: {pred_count} deliveries\nDemand: {demand_level}\nRecommendation: {recommendation}"
        }
    })

# ============ VEHICLE MANAGEMENT API ============
@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    zone_id = request.args.get('zone_id')
    status = request.args.get('status')
    
    query = "SELECT * FROM vehicles WHERE 1=1"
    params = []
    
    if zone_id:
        query += " AND assigned_zone = %s"
        params.append(zone_id)
    if status:
        query += " AND status = %s"
        params.append(status)
    
    query += " ORDER BY vehicle_id"
    cursor.execute(query, params)
    vehicles = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'vehicles': vehicles})

@app.route('/api/vehicles', methods=['POST'])
def add_vehicle():
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO vehicles (vehicle_code, vehicle_type, plate_number, capacity_kg, 
                                 capacity_cubic_m, fuel_type, status, assigned_zone)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (data['vehicle_code'], data['vehicle_type'], data.get('plate_number'),
              data.get('capacity_kg', 0), data.get('capacity_cubic_m', 0),
              data.get('fuel_type', 'gasoline'), data.get('status', 'available'),
              data.get('assigned_zone')))
        
        conn.commit()
        vehicle_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'vehicle_id': vehicle_id})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vehicles/<int:vehicle_id>', methods=['PUT'])
def update_vehicle(vehicle_id):
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        updates = []
        params = []
        
        for field in ['vehicle_code', 'vehicle_type', 'plate_number', 'capacity_kg', 
                      'capacity_cubic_m', 'fuel_type', 'status', 'assigned_zone']:
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])
        
        if updates:
            params.append(vehicle_id)
            cursor.execute(f"UPDATE vehicles SET {', '.join(updates)} WHERE vehicle_id = %s", params)
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vehicles/<int:vehicle_id>', methods=['DELETE'])
def delete_vehicle(vehicle_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM vehicles WHERE vehicle_id = %s", (vehicle_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

# ============ USER MANAGEMENT API ============
@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    role = request.args.get('role')
    
    query = "SELECT user_id, username, email, full_name, role, zone_access, is_active, last_login, created_at FROM users"
    params = []
    
    if role:
        query += " WHERE role = %s"
        params.append(role)
    
    query += " ORDER BY user_id"
    cursor.execute(query, params)
    users = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'users': users})

@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    # Hash password
    password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, full_name, role, zone_access, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data['username'], password_hash, data['email'], data.get('full_name'),
              data.get('role', 'dispatcher'), data.get('zone_access'), data.get('is_active', 1)))
        
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'user_id': user_id})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        updates = []
        params = []
        
        for field in ['email', 'full_name', 'role', 'zone_access', 'is_active']:
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])
        
        if 'password' in data and data['password']:
            password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
            updates.append("password_hash = %s")
            params.append(password_hash)
        
        if updates:
            params.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = %s", params)
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

# ============ DISPATCH MANAGEMENT API ============
@app.route('/api/dispatch/assignments', methods=['GET'])
def get_dispatch_assignments():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    zone_id = request.args.get('zone_id')
    status = request.args.get('status')
    date = request.args.get('date')
    
    query = """
        SELECT da.*, z.zone_name 
        FROM dispatch_assignments da
        LEFT JOIN zones z ON da.zone_id = z.zone_id
        WHERE 1=1
    """
    params = []
    
    if zone_id:
        query += " AND da.zone_id = %s"
        params.append(zone_id)
    if status:
        query += " AND da.dispatch_status = %s"
        params.append(status)
    if date:
        query += " AND DATE(da.dispatch_datetime) = %s"
        params.append(date)
    
    query += " ORDER BY da.dispatch_datetime DESC"
    
    cursor.execute(query, params)
    assignments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'assignments': assignments})

@app.route('/api/dispatch/assignments', methods=['POST'])
def create_dispatch_assignment():
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO dispatch_assignments 
            (zone_id, dispatch_datetime, predicted_deliveries, actual_deliveries, 
             demand_level, assigned_vehicles, assigned_drivers, dispatch_status, 
             notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (data['zone_id'], data['dispatch_datetime'], data.get('predicted_deliveries'),
              data.get('actual_deliveries'), data.get('demand_level'), 
              data.get('assigned_vehicles'), data.get('assigned_drivers'),
              data.get('dispatch_status', 'planned'), data.get('notes'), 
              data.get('created_by', 1)))
        
        conn.commit()
        assignment_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'assignment_id': assignment_id})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dispatch/assignments/<int:assignment_id>', methods=['PUT'])
def update_dispatch_assignment(assignment_id):
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        updates = []
        params = []
        
        for field in ['dispatch_datetime', 'predicted_deliveries', 'actual_deliveries', 
                      'demand_level', 'assigned_vehicles', 'assigned_drivers', 
                      'dispatch_status', 'notes']:
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])
        
        if 'completed_at' in data and data['completed_at']:
            updates.append("completed_at = %s")
            params.append(data['completed_at'])
        
        if updates:
            params.append(assignment_id)
            cursor.execute(f"UPDATE dispatch_assignments SET {', '.join(updates)} WHERE assignment_id = %s", params)
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dispatch/assignments/<int:assignment_id>', methods=['DELETE'])
def delete_dispatch_assignment(assignment_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM dispatch_assignments WHERE assignment_id = %s", (assignment_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

# ============ DRIVER ASSIGNMENT API ============
@app.route('/api/driver/assignments', methods=['GET'])
def get_driver_assignments():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    date = request.args.get('date')
    driver_id = request.args.get('driver_id')
    
    query = """
        SELECT da.*, u.full_name as driver_name, v.vehicle_code, z.zone_name
        FROM driver_assignments da
        LEFT JOIN users u ON da.driver_id = u.user_id
        LEFT JOIN vehicles v ON da.vehicle_id = v.vehicle_id
        LEFT JOIN zones z ON da.zone_id = z.zone_id
        WHERE 1=1
    """
    params = []
    
    if date:
        query += " AND da.shift_date = %s"
        params.append(date)
    if driver_id:
        query += " AND da.driver_id = %s"
        params.append(driver_id)
    
    query += " ORDER BY da.shift_date DESC, da.shift_start"
    
    cursor.execute(query, params)
    assignments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'assignments': assignments})

@app.route('/api/driver/assignments', methods=['POST'])
def create_driver_assignment():
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO driver_assignments 
            (driver_id, vehicle_id, shift_date, shift_start, shift_end, zone_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data['driver_id'], data['vehicle_id'], data['shift_date'], 
              data['shift_start'], data['shift_end'], data.get('zone_id'), 
              data.get('status', 'scheduled')))
        
        conn.commit()
        assignment_id = cursor.lastrowid
        
        # Update vehicle status
        cursor.execute("UPDATE vehicles SET status = 'assigned', driver_id = %s WHERE vehicle_id = %s", 
                      (data['driver_id'], data['vehicle_id']))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'assignment_id': assignment_id})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

# ============ ZONES API ============
@app.route('/api/zones', methods=['GET'])
def get_zones():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM zones ORDER BY zone_id")
    zones = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'zones': zones})

# ============ DASHBOARD STATS API ============
@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    stats = {}
    
    # Vehicle stats
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM vehicles 
        GROUP BY status
    """)
    stats['vehicles_by_status'] = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as total FROM vehicles")
    result = cursor.fetchone()
    stats['total_vehicles'] = result['total'] if result else 0
    
    # User stats
    cursor.execute("""
        SELECT role, COUNT(*) as count 
        FROM users 
        WHERE is_active = 1 
        GROUP BY role
    """)
    stats['users_by_role'] = cursor.fetchall()
    
    # Dispatch stats
    cursor.execute("""
        SELECT dispatch_status, COUNT(*) as count 
        FROM dispatch_assignments 
        GROUP BY dispatch_status
    """)
    stats['dispatch_by_status'] = cursor.fetchall()
    
    # Today's assignments
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM dispatch_assignments 
        WHERE DATE(dispatch_datetime) = CURDATE()
    """)
    result = cursor.fetchone()
    stats['today_assignments'] = result['count'] if result else 0
    
    # Active driver assignments
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM driver_assignments 
        WHERE shift_date = CURDATE() AND status = 'active'
    """)
    result = cursor.fetchone()
    stats['active_drivers_today'] = result['count'] if result else 0
    
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'stats': stats})

# ============ HISTORICAL STATS API ============
@app.route('/api/historical_stats', methods=['GET'])
def historical_stats():
    zone_id = request.args.get('zone_id')
    days = int(request.args.get('days', 30))
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_deliveries,
            AVG(delivery_count) as avg_hourly_deliveries,
            MAX(delivery_count) as max_hourly,
            AVG(daily_count) as avg_daily_deliveries
        FROM (
            SELECT 
                DATE(delivery_timestamp) as date,
                SUM(delivery_count) as daily_count,
                delivery_count
            FROM delivery_records
            WHERE zone_id = %s AND delivery_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY date, delivery_timestamp
        ) as daily
    """, (zone_id, days))
    
    result = cursor.fetchone()
    
    # Get peak hours
    cursor.execute("""
        SELECT HOUR(delivery_timestamp) as hour, AVG(delivery_count) as avg_count
        FROM delivery_records
        WHERE zone_id = %s AND delivery_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY HOUR(delivery_timestamp)
        ORDER BY avg_count DESC
        LIMIT 3
    """, (zone_id, days))
    
    peak_hours = {str(row['hour']): row['avg_count'] for row in cursor.fetchall()}
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'total_deliveries': result['total_deliveries'] or 0,
        'avg_hourly_deliveries': result['avg_hourly_deliveries'] or 0,
        'max_hourly': result['max_hourly'] or 0,
        'avg_daily_deliveries': result['avg_daily_deliveries'] or 0,
        'peak_hours': peak_hours
    })

# ============ ENHANCED DISPATCH MANAGEMENT API ============
@app.route('/api/dispatch/assignments/enhanced', methods=['GET'])
def get_dispatch_assignments_enhanced():
    """Get dispatch assignments with search and pagination"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    # Get pagination and search parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 15))
    search = request.args.get('search', '')
    zone_id = request.args.get('zone_id', '')
    status = request.args.get('status', '')
    
    offset = (page - 1) * per_page
    
    # Build query with search
    query = """
        SELECT da.*, z.zone_name, 
               v.vehicle_code, v.vehicle_type,
               u.full_name as driver_name
        FROM dispatch_assignments da
        LEFT JOIN zones z ON da.zone_id = z.zone_id
        LEFT JOIN vehicles v ON FIND_IN_SET(v.vehicle_code, REPLACE(da.assigned_vehicles, ' MC', '')) > 0
        LEFT JOIN users u ON da.assigned_drivers = u.user_id
        WHERE 1=1
    """
    count_query = "SELECT COUNT(*) as total FROM dispatch_assignments da WHERE 1=1"
    params = []
    
    if search:
        search_term = f"%{search}%"
        query += " AND (da.assignment_id LIKE %s OR da.zone_id LIKE %s OR da.assigned_vehicles LIKE %s)"
        count_query += " AND (assignment_id LIKE %s OR zone_id LIKE %s OR assigned_vehicles LIKE %s)"
        params.extend([search_term, search_term, search_term])
    
    if zone_id:
        query += " AND da.zone_id = %s"
        count_query += " AND zone_id = %s"
        params.append(zone_id)
    
    if status:
        query += " AND da.dispatch_status = %s"
        count_query += " AND dispatch_status = %s"
        params.append(status)
    
    # Get total count
    cursor.execute(count_query, params)
    total = cursor.fetchone()['total']
    
    # Get paginated results
    query += " ORDER BY da.dispatch_datetime DESC LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
    
    cursor.execute(query, params)
    assignments = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'success': True, 
        'assignments': assignments,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page
        }
    })

@app.route('/api/dispatch/assignments/full', methods=['POST'])
def create_full_dispatch():
    """Create dispatch assignment with driver and vehicle association"""
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        # Insert dispatch assignment
        cursor.execute("""
            INSERT INTO dispatch_assignments 
            (zone_id, dispatch_datetime, predicted_deliveries, actual_deliveries, 
             demand_level, assigned_vehicles, assigned_drivers, dispatch_status, 
             notes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (data['zone_id'], data['dispatch_datetime'], data.get('predicted_deliveries'),
              data.get('actual_deliveries'), data.get('demand_level'), 
              data['assigned_vehicles'], data.get('assigned_drivers'),
              data.get('dispatch_status', 'planned'), data.get('notes'), 
              data.get('created_by', 1)))
        
        assignment_id = cursor.lastrowid
        
        # Update vehicle status if vehicle is assigned
        if data.get('vehicle_id'):
            cursor.execute("UPDATE vehicles SET status = 'assigned' WHERE vehicle_id = %s", 
                          (data['vehicle_id'],))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'assignment_id': assignment_id})
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

# ============ ENHANCED VEHICLE MANAGEMENT API ============
@app.route('/api/vehicles/enhanced', methods=['GET'])
def get_vehicles_enhanced():
    """Get vehicles with search and pagination"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 15))
    search = request.args.get('search', '')
    zone_id = request.args.get('zone_id', '')
    status = request.args.get('status', '')
    vehicle_type = request.args.get('vehicle_type', '')
    
    offset = (page - 1) * per_page
    
    query = "SELECT * FROM vehicles WHERE 1=1"
    count_query = "SELECT COUNT(*) as total FROM vehicles WHERE 1=1"
    params = []
    
    if search:
        search_term = f"%{search}%"
        query += " AND (vehicle_code LIKE %s OR plate_number LIKE %s)"
        count_query += " AND (vehicle_code LIKE %s OR plate_number LIKE %s)"
        params.extend([search_term, search_term])
    
    if zone_id:
        query += " AND assigned_zone = %s"
        count_query += " AND assigned_zone = %s"
        params.append(zone_id)
    
    if status:
        query += " AND status = %s"
        count_query += " AND status = %s"
        params.append(status)
    
    if vehicle_type:
        query += " AND vehicle_type = %s"
        count_query += " AND vehicle_type = %s"
        params.append(vehicle_type)
    
    cursor.execute(count_query, params)
    total = cursor.fetchone()['total']
    
    query += " ORDER BY vehicle_id LIMIT %s OFFSET %s"
    params.extend([per_page, offset])
    
    cursor.execute(query, params)
    vehicles = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'vehicles': vehicles,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page
        }
    })

# ============ DRIVER MANAGEMENT API ============
@app.route('/api/drivers', methods=['GET'])
def get_drivers():
    """Get all users with role = 'driver'"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    
    # Get only drivers
    cursor.execute("""
        SELECT user_id, username, email, full_name, role, zone_access, is_active, 
               last_login, created_at
        FROM users 
        WHERE role = 'driver'
        ORDER BY full_name
    """)
    drivers = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'drivers': drivers})

@app.route('/api/drivers', methods=['POST'])
def add_driver():
    """Add a new driver (user with role='driver')"""
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, full_name, role, zone_access, is_active)
            VALUES (%s, %s, %s, %s, 'driver', %s, %s)
        """, (data['username'], password_hash, data['email'], data.get('full_name'),
              data.get('zone_access'), data.get('is_active', 1)))
        
        conn.commit()
        driver_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'driver_id': driver_id})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/drivers/<int:driver_id>', methods=['PUT'])
def update_driver(driver_id):
    """Update driver information"""
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        updates = []
        params = []
        
        for field in ['email', 'full_name', 'zone_access', 'is_active']:
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])
        
        if 'password' in data and data['password']:
            password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
            updates.append("password_hash = %s")
            params.append(password_hash)
        
        if updates:
            params.append(driver_id)
            cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = %s AND role = 'driver'", params)
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/drivers/<int:driver_id>', methods=['DELETE'])
def delete_driver(driver_id):
    """Delete a driver"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM users WHERE user_id = %s AND role = 'driver'", (driver_id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

# ============ VEHICLE TYPES & STATUS API ============
@app.route('/api/vehicle-types', methods=['GET'])
def get_vehicle_types():
    """Get distinct vehicle types for filters"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT vehicle_type FROM vehicles WHERE vehicle_type IS NOT NULL")
    types = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'vehicle_types': types})

@app.route('/api/vehicle-statuses', methods=['GET'])
def get_vehicle_statuses():
    """Get distinct vehicle statuses for filters"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT status FROM vehicles WHERE status IS NOT NULL")
    statuses = [row[0] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return jsonify({'success': True, 'vehicle_statuses': statuses})

# ============ DISPATCH STATUS API ============
@app.route('/api/dispatch-statuses', methods=['GET'])
def get_dispatch_statuses():
    """Get distinct dispatch statuses for filters"""
    return jsonify({
        'success': True, 
        'dispatch_statuses': ['planned', 'assigned', 'enroute', 'completed', 'cancelled']
    })

# ============ RUN APP ============
if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')