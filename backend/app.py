from flask import Flask, request, jsonify, send_from_directory, session
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
import subprocess
import threading
from functools import wraps
from datetime import datetime, timedelta
import time

app = Flask(__name__)
app.secret_key = 'omniroute-dm-secret-key-2024-change-this-in-production'
CORS(app, supports_credentials=True, origins=['http://127.0.0.1:5000', 'http://localhost:5000'])

# ============ AUTHENTICATION DECORATOR ============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Authentication required', 'redirect': '/login'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============ SERVE FRONTEND FILES ============
@app.route('/')
def serve_index():
    if 'user_id' not in session:
        return send_from_directory('../frontend', 'login.html')
    return send_from_directory('../frontend', 'index.html')

@app.route('/login')
def serve_login():
    return send_from_directory('../frontend', 'login.html')

@app.route('/<path:path>')
def serve_frontend(path):
    try:
        return send_from_directory('../frontend', path)
    except:
        if 'user_id' not in session:
            return send_from_directory('../frontend', 'login.html')
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

# ============ AUTHENTICATION API ============
@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user and start session"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, username, email, full_name, role, zone_access, is_active, password_hash FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'error': 'Invalid username or password'})
    
    # Check password
    if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        conn.close()
        return jsonify({'success': False, 'error': 'Invalid username or password'})
    
    if not user['is_active']:
        conn.close()
        return jsonify({'success': False, 'error': 'Account is disabled'})
    
    # Start session
    session['user_id'] = user['user_id']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    session['role'] = user['role']
    session['zone_access'] = user['zone_access']
    
    # Update last login
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_login = NOW() WHERE user_id = %s", (user['user_id'],))
    conn.commit()
    cursor.close()
    conn.close()
    
    return jsonify({
        'success': True,
        'user': {
            'user_id': user['user_id'],
            'username': user['username'],
            'full_name': user['full_name'],
            'role': user['role'],
            'zone_access': user['zone_access']
        }
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout user and clear session"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """Check if user is logged in"""
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'user_id': session['user_id'],
                'username': session['username'],
                'full_name': session.get('full_name'),
                'role': session.get('role'),
                'zone_access': session.get('zone_access')
            }
        })
    else:
        return jsonify({'authenticated': False})

# ============ HEALTH CHECK ============
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'models_loaded': models_loaded})

# ============ PREDICTION API ============
@app.route('/api/predict', methods=['POST'])
@login_required
def predict():
    if not models_loaded:
        return jsonify({'success': False, 'error': 'Models not loaded'})
    
    data = request.json
    zone_id = data.get('zone_id')
    datetime_str = data.get('datetime')
    
    if not zone_id or not datetime_str:
        return jsonify({'success': False, 'error': 'Missing zone_id or datetime'})
    
    # ========== ADD BUSINESS HOURS CHECK ==========
    pred_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
    hour = pred_datetime.hour
    
    # Check if outside business hours (6 AM - 10 PM)
    if hour < 6 or hour > 22:
        return jsonify({
            'success': True,
            'prediction': {
                'zone_id': zone_id,
                'datetime': datetime_str,
                'predicted_deliveries': 0,
                'demand_level': 'No Operations',
                'recommendation': 'No deliveries scheduled during this time. Please select a time between 6 AM and 10 PM.',
                'vehicle_breakdown': {
                    'motorcycles': 0,
                    'vans': 0,
                    'trucks': 0
                },
                'confidence_interval': [0, 0],
                'full_message': f"Zone: {zone_id}\nTime: {datetime_str}\nNo operations at this hour. Select time between 6 AM - 10 PM."
            }
        })
    # =============================================
    
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
    
    # Time features (use pred_datetime which is already defined)
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
    try:
        X = np.array([[features.get(col, 0) for col in feature_columns]])
        X_scaled = scaler.transform(X)
    except Exception as e:
        print(f"Feature error: {e}")
        return jsonify({'success': False, 'error': f'Feature processing error: {str(e)}'})
    
    # Predict
    try:
        pred_count = reg_model.predict(X_scaled)[0]
        pred_count = max(0, int(round(pred_count)))
    except Exception as e:
        print(f"Prediction error: {e}")
        return jsonify({'success': False, 'error': f'Model prediction error: {str(e)}'})
    
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
    
    # Save prediction (optional - don't fail if this errors)
    try:
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
    except Exception as e:
        print(f"Warning: Could not save prediction to log: {e}")
        # Continue anyway - don't fail the request
    
    # ========== FINAL RETURN (ALWAYS HAPPENS FOR BUSINESS HOURS) ==========
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

_peak_cache = None
_peak_cache_time = 0
PEAK_CACHE_DURATION = 120  # Cache for 2 minutes

# ============ NEXT PEAK PREDICTION API (7 DAYS) ============
@app.route('/api/next-peaks', methods=['GET'])
@login_required
def next_peaks():
    global _peak_cache, _peak_cache_time
    
    # Return cached result if still fresh
    current_time = time.time()
    if _peak_cache is not None and (current_time - _peak_cache_time) < PEAK_CACHE_DURATION:
        print(f"⚡ Returning cached peaks (age: {current_time - _peak_cache_time:.1f}s)")
        return jsonify(_peak_cache)
    
    print("🔍 Computing new peak detection (this may take a few seconds)...")
    
    if not models_loaded:
        return jsonify({'success': False, 'error': 'Models not loaded'})
    
    # Get all zones in ONE query
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM zones")
    zones = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not zones:
        return jsonify({'success': False, 'error': 'No zones found'})
    
    # Load feature columns once
    global feature_columns
    if feature_columns is None:
        try:
            with open('backend/models/feature_columns.txt', 'r') as f:
                feature_columns = f.read().strip().split(',')
        except:
            feature_columns = []
    
    now = datetime.now()
    next_peaks_list = []
    
    # For each zone, only check the next 48 hours (not 7 days) for speed
    for zone in zones:
        zone_id = zone['zone_id']
        zone_name = zone['zone_name']
        zone_peaks = []
        
        # Get recent records for this zone ONCE
        conn2 = get_db_connection()
        if conn2 is None:
            continue
        
        cursor2 = conn2.cursor(dictionary=True)
        try:
            cursor2.execute("""
                SELECT delivery_count, delivery_timestamp 
                FROM delivery_records 
                WHERE zone_id = %s 
                ORDER BY delivery_timestamp DESC LIMIT 50
            """, (zone_id,))
            all_recent = cursor2.fetchall()
        except Exception as e:
            print(f"Error fetching records for {zone_id}: {e}")
            all_recent = []
        finally:
            cursor2.close()
            conn2.close()
        
        # Only check next 48 hours, and only every 3 hours (reduces work)
        for hours_ahead in range(2, 49, 3):  # Start from 2 hours ahead, every 3 hours
            check_time = now + timedelta(hours=hours_ahead)
            hour = check_time.hour
            
            # Skip non-business hours
            if hour < 6 or hour > 22:
                continue
            
            # Get recent records BEFORE check_time
            recent = [r for r in all_recent 
                     if r['delivery_timestamp'] < check_time][:25]
            
            # Build features
            features = {}
            features['hour'] = check_time.hour
            features['hour_sin'] = np.sin(2 * np.pi * check_time.hour / 24)
            features['hour_cos'] = np.cos(2 * np.pi * check_time.hour / 24)
            features['day_of_week'] = check_time.weekday()
            features['dow_sin'] = np.sin(2 * np.pi * check_time.weekday() / 7)
            features['dow_cos'] = np.cos(2 * np.pi * check_time.weekday() / 7)
            features['month'] = check_time.month
            features['is_weekend'] = 1 if check_time.weekday() >= 5 else 0
            features['is_morning_rush'] = 1 if 7 <= check_time.hour <= 9 else 0
            features['is_evening_rush'] = 1 if 17 <= check_time.hour <= 19 else 0
            features['is_lunch_hour'] = 1 if 12 <= check_time.hour <= 13 else 0
            
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
                    features[f'rolling_mean_{window}h'] = float(np.mean(window_data))
                    features[f'rolling_std_{window}h'] = float(np.std(window_data))
                else:
                    features[f'rolling_mean_{window}h'] = 0
                    features[f'rolling_std_{window}h'] = 0
            
            # Predict
            try:
                feature_values = [features.get(col, 0) for col in feature_columns]
                X = np.array([feature_values])
                X_scaled = scaler.transform(X)
                pred_count = reg_model.predict(X_scaled)[0]
                pred_count = max(0, int(round(pred_count)))
            except Exception as e:
                continue
            
            # Check if this is a peak
            if pred_count <= zone['threshold_normal']:
                continue  # Skip normal demand
            
            if pred_count <= zone['threshold_high']:
                demand_level = "High Demand"
            else:
                demand_level = "Peak Risk"
            
            # Calculate time description
            hours_from_now = hours_ahead
            if hours_from_now < 24:
                date_desc = "Today"
                if hours_from_now == 1:
                    time_desc = "1 hour"
                else:
                    time_desc = f"{hours_from_now} hours"
            elif hours_from_now < 48:
                date_desc = "Tomorrow"
                remaining = hours_from_now - 24
                time_desc = f"{remaining} hours" if remaining != 1 else "1 hour"
            else:
                days = hours_from_now // 24
                date_desc = f"In {days} days"
                time_desc = f"{hours_from_now % 24} hours"
            
            # Format display time
            hour_12 = check_time.hour if check_time.hour <= 12 else check_time.hour - 12
            if hour_12 == 0:
                hour_12 = 12
            ampm = "AM" if check_time.hour < 12 else "PM"
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            # Vehicle recommendation
            base = zone['base_vehicles']
            if pred_count <= 10:
                motorcycles, vans, trucks = base, 0, 0
            elif pred_count <= 20:
                motorcycles, vans, trucks = base, 1, 0
            elif pred_count <= 35:
                motorcycles, vans, trucks = base, 2, 0
            else:
                motorcycles, vans, trucks = base, 3, 1
            
            zone_peaks.append({
                'datetime': check_time.strftime('%Y-%m-%d %H:%M:%S'),
                'datetime_display': f"{weekday_names[check_time.weekday()]} at {hour_12}:00 {ampm}",
                'date_desc': date_desc,
                'time_desc': time_desc,
                'hours_from_now': hours_from_now,
                'predicted_deliveries': pred_count,
                'demand_level': demand_level,
                'vehicle_breakdown': {
                    'motorcycles': motorcycles,
                    'vans': vans,
                    'trucks': trucks
                },
                'recommendation': f"{motorcycles} MC" + (f" + {vans} Vans" if vans > 0 else "") + (f" + {trucks} Truck" if trucks > 0 else "")
            })
        
        if zone_peaks:
            zone_peaks.sort(key=lambda x: x['hours_from_now'])
            next_peaks_list.append({
                'zone_id': zone_id,
                'zone_name': zone_name,
                'nearest_peak': zone_peaks[0],
                'all_peaks_this_week': zone_peaks[:3]  # Only show top 3
            })
    
    next_peaks_list.sort(key=lambda x: x['nearest_peak']['hours_from_now'])
    
    total_peaks = sum(1 for zone in next_peaks_list if zone['nearest_peak']['demand_level'] == 'Peak Risk')
    total_high = sum(1 for zone in next_peaks_list if zone['nearest_peak']['demand_level'] == 'High Demand')
    
    result = {
        'success': True,
        'zones': next_peaks_list,
        'summary': {
            'total_zones_with_peaks': len(next_peaks_list),
            'total_peak_risk': total_peaks,
            'total_high_demand': total_high
        }
    }
    
    # Cache the result
    _peak_cache = result
    _peak_cache_time = current_time
    
    print(f"✅ Peak detection complete. Found {len(next_peaks_list)} zones with peaks.")
    return jsonify(result)

# ============ HELPER FUNCTION FOR PEAK DETECTION ============
def build_prediction_features(pred_datetime, recent_records):
    """Build feature vector for prediction at a specific datetime"""
    
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
    
    # Business hours features
    features['is_business_hour'] = 1 if 6 <= pred_datetime.hour <= 22 else 0
    features['is_overnight'] = 1 if pred_datetime.hour >= 22 or pred_datetime.hour <= 5 else 0
    
    # Lag features
    recent_counts = [r['delivery_count'] for r in recent_records]
    
    for lag in [1, 2, 3, 6, 12, 24]:
        if len(recent_counts) >= lag:
            features[f'lag_{lag}h'] = recent_counts[lag-1]
        else:
            features[f'lag_{lag}h'] = 0
    
    # Rolling features
    for window in [3, 6, 12, 24]:
        if len(recent_counts) >= window:
            window_data = recent_counts[:window]
            features[f'rolling_mean_{window}h'] = float(np.mean(window_data))
            features[f'rolling_std_{window}h'] = float(np.std(window_data))
        else:
            features[f'rolling_mean_{window}h'] = 0
            features[f'rolling_std_{window}h'] = 0
    
    return features

@app.route('/api/retrain-model', methods=['POST'])
@login_required
def retrain_model():
    """Retrain the ML model with latest delivery records"""
    
    def retrain_in_background():
        try:
            print("🔄 Starting model retraining with latest data...")
            result = subprocess.run(
                ['python', 'train_standalone.py'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            if result.returncode == 0:
                print("✅ Model retrained successfully!")
                # Reload models
                global reg_model, cls_model, scaler, models_loaded, feature_columns
                try:
                    reg_model = joblib.load('backend/models/regression_model.pkl')
                    cls_model = joblib.load('backend/models/classification_model.pkl')
                    scaler = joblib.load('backend/models/scaler.pkl')
                    with open('backend/models/feature_columns.txt', 'r') as f:
                        feature_columns = f.read().strip().split(',')
                    models_loaded = True
                    print("✅ Models reloaded successfully!")
                except Exception as e:
                    print(f"⚠️ Error reloading models: {e}")
            else:
                print(f"❌ Retraining failed: {result.stderr}")
        except Exception as e:
            print(f"❌ Retraining error: {e}")
    
    # Run retraining in background thread to not block the API
    thread = threading.Thread(target=retrain_in_background)
    thread.start()
    
    return jsonify({'success': True, 'message': 'Model retraining started in background'})

@app.route('/api/delivery-records/count', methods=['GET'])
@login_required
def get_delivery_records_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM delivery_records")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({'count': result[0] if result else 0})

# ============ VEHICLE MANAGEMENT API ============
@app.route('/api/vehicles', methods=['GET'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def add_user():
    """Create a new user - HARDCODED ROLE = 'driver'"""
    data = request.json
    
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'})
    
    # Get data from request
    username = data.get('username', '').strip()
    password = data.get('password', '')
    email = data.get('email', '').strip().lower()
    full_name = data.get('full_name', '').strip() if data.get('full_name') else None
    zone_access = data.get('zone_access', '').strip() if data.get('zone_access') else 'ZONE_A,ZONE_B,ZONE_C,ZONE_D,ZONE_E'
    is_active = data.get('is_active', 1)
    
    # ========== HARDCODE ROLE ==========
    role = 'driver'  # ← EVERY USER BECOMES A DRIVER
    # ==================================
    
    # ========== DEBUG PRINT ==========
    print("\n" + "=" * 60)
    print("📝 ADD USER - HARDCODED MODE")
    print("=" * 60)
    print(f"   Username: {username}")
    print(f"   Email: {email}")
    print(f"   Role (HARDCODED): '{role}'")
    print(f"   Zone Access: {zone_access}")
    print("=" * 60 + "\n")
    # ==================================
    
    # Validation
    if not username:
        return jsonify({'success': False, 'error': 'Username is required'})
    if not password:
        return jsonify({'success': False, 'error': 'Password is required'})
    if len(password) < 4:
        return jsonify({'success': False, 'error': 'Password must be at least 4 characters'})
    if not email:
        return jsonify({'success': False, 'error': 'Email is required'})
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    # Check if username exists
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': f'Username "{username}" already exists'})
    
    # Check if email exists
    cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': f'Email "{email}" already exists'})
    
    # Hash password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, email, full_name, role, zone_access, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            username,
            password_hash,
            email,
            full_name,
            role,  # ← HARDCODED 'driver'
            zone_access,
            is_active
        ))
        
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        print(f"✅ USER CREATED: {username} with ROLE: {role}")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'role': role,
            'message': f'User {username} created with role: {role}'
        })
        
    except Exception as e:
        print(f"❌ Error: {e}")
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})
    

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
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
@login_required
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
@login_required
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
        if ',' in status:
            status_list = status.split(',')
            placeholders = ','.join(['%s'] * len(status_list))
            query += f" AND da.dispatch_status IN ({placeholders})"
            params.extend(status_list)
        else:
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
@login_required
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
              data.get('created_by', session.get('user_id', 1))))
        
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
@login_required
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
        
        # Check if status is being changed to 'completed'
        is_completing = data.get('dispatch_status') == 'completed'
        
        if updates:
            params.append(assignment_id)
            cursor.execute(f"UPDATE dispatch_assignments SET {', '.join(updates)} WHERE assignment_id = %s", params)
            
            # If marking as completed, create delivery record
            if is_completing:
                # Use a NEW dictionary cursor for fetching
                dict_cursor = conn.cursor(dictionary=True)
                dict_cursor.execute("""
                    SELECT zone_id, dispatch_datetime, actual_deliveries, predicted_deliveries, 
                           assigned_vehicles, assigned_drivers
                    FROM dispatch_assignments 
                    WHERE assignment_id = %s
                """, (assignment_id,))
                dispatch = dict_cursor.fetchone()
                dict_cursor.close()
                
                if dispatch:
                    # Use actual_deliveries if provided, otherwise use predicted_deliveries
                    delivery_count = dispatch['actual_deliveries'] if dispatch['actual_deliveries'] else dispatch['predicted_deliveries']
                    
                    # Determine vehicle type from assigned vehicles
                    vehicle_type = 'motorcycle'  # default
                    if dispatch['assigned_vehicles']:
                        if 'van' in dispatch['assigned_vehicles'].lower():
                            vehicle_type = 'van'
                        elif 'truck' in dispatch['assigned_vehicles'].lower():
                            vehicle_type = 'truck'
                    
                    # Insert into delivery_records
                    cursor.execute("""
                        INSERT INTO delivery_records 
                        (zone_id, delivery_timestamp, delivery_count, vehicle_type, distance_km)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        dispatch['zone_id'],
                        dispatch['dispatch_datetime'],
                        delivery_count,
                        vehicle_type,
                        round(5 + (delivery_count * 0.1), 2)
                    ))
                    
                    print(f"✅ Created delivery record for dispatch {assignment_id}")
            
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dispatch/assignments/<int:assignment_id>', methods=['DELETE'])
@login_required
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
@login_required
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

@app.route('/api/dispatch/assignments/<int:assignment_id>/complete-with-delivery', methods=['POST'])
@login_required
def complete_dispatch_with_delivery(assignment_id):
    """Complete a dispatch and free up vehicles/drivers"""
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    try:
        actual_deliveries = data.get('actual_deliveries')
        vehicle_type = data.get('vehicle_type', 'motorcycle')
        distance_km = data.get('distance_km')
        
        dict_cursor = conn.cursor(dictionary=True)
        regular_cursor = conn.cursor()
        
        # Get dispatch details
        dict_cursor.execute("""
            SELECT da.zone_id, da.dispatch_datetime, da.predicted_deliveries, 
                   da.assigned_vehicles, da.assigned_drivers, da.dispatch_status
            FROM dispatch_assignments da
            WHERE da.assignment_id = %s
        """, (assignment_id,))
        dispatch = dict_cursor.fetchone()
        
        if not dispatch:
            return jsonify({'success': False, 'error': 'Dispatch not found'})
        
        # Only allow completion if status is enroute
        if dispatch['dispatch_status'] != 'enroute':
            return jsonify({'success': False, 'error': f'Dispatch must be enroute to complete. Current status: {dispatch["dispatch_status"]}'})
        
        delivery_count = actual_deliveries if actual_deliveries else dispatch['predicted_deliveries']
        
        if not distance_km:
            distance_km = round(2 + (delivery_count * 0.3), 2)
        
        # Update dispatch to completed
        regular_cursor.execute("""
            UPDATE dispatch_assignments 
            SET dispatch_status = 'completed', 
                actual_deliveries = %s,
                completed_at = NOW()
            WHERE assignment_id = %s
        """, (delivery_count, assignment_id))
        
        # Insert into delivery_records
        regular_cursor.execute("""
            INSERT INTO delivery_records 
            (zone_id, delivery_timestamp, delivery_count, vehicle_type, distance_km)
            VALUES (%s, %s, %s, %s, %s)
        """, (dispatch['zone_id'], dispatch['dispatch_datetime'], delivery_count, vehicle_type, distance_km))
        
        record_id = regular_cursor.lastrowid
        
        # FREE UP VEHICLES (only if they were assigned/enroute)
        if dispatch['assigned_vehicles']:
            import re
            vehicle_codes = re.findall(r'([A-Z]+-[0-9]+)', dispatch['assigned_vehicles'])
            
            for vehicle_code in vehicle_codes:
                regular_cursor.execute("""
                    UPDATE vehicles 
                    SET status = 'available', 
                        driver_id = NULL,
                        updated_at = NOW()
                    WHERE vehicle_code = %s AND status = 'assigned'
                """, (vehicle_code,))
                print(f"   ✅ Vehicle {vehicle_code} freed up")
        
        # FREE UP DRIVERS
        if dispatch['assigned_drivers']:
            driver_names = [name.strip() for name in dispatch['assigned_drivers'].split(',')]
            
            for driver_name in driver_names:
                dict_cursor.execute("""
                    SELECT user_id FROM users 
                    WHERE full_name = %s OR username = %s
                """, (driver_name, driver_name))
                driver = dict_cursor.fetchone()
                
                if driver:
                    regular_cursor.execute("""
                        UPDATE driver_assignments 
                        SET status = 'completed'
                        WHERE driver_id = %s 
                        AND shift_date = CURDATE()
                        AND status = 'active'
                    """, (driver['user_id'],))
                    print(f"   ✅ Driver {driver_name} freed up")
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Dispatch completed, vehicles and drivers freed up',
            'delivery_record_id': record_id
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/dispatch/assignments/<int:assignment_id>/enroute', methods=['PUT'])
@login_required
def mark_dispatch_enroute(assignment_id):
    """Mark dispatch as enroute and assign vehicles/drivers"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    try:
        dict_cursor = conn.cursor(dictionary=True)
        regular_cursor = conn.cursor()
        
        # Get dispatch details
        dict_cursor.execute("""
            SELECT zone_id, assigned_vehicles, assigned_drivers, dispatch_status
            FROM dispatch_assignments 
            WHERE assignment_id = %s
        """, (assignment_id,))
        dispatch = dict_cursor.fetchone()
        
        if not dispatch:
            return jsonify({'success': False, 'error': 'Dispatch not found'})
        
        if dispatch['dispatch_status'] != 'assigned':
            return jsonify({'success': False, 'error': f'Dispatch must be assigned first. Current status: {dispatch["dispatch_status"]}'})
        
        # Update dispatch status to enroute
        regular_cursor.execute("""
            UPDATE dispatch_assignments 
            SET dispatch_status = 'enroute'
            WHERE assignment_id = %s
        """, (assignment_id,))
        
        # Mark vehicles as assigned
        if dispatch['assigned_vehicles']:
            import re
            vehicle_codes = re.findall(r'([A-Z]+-[0-9]+)', dispatch['assigned_vehicles'])
            
            for vehicle_code in vehicle_codes:
                regular_cursor.execute("""
                    UPDATE vehicles 
                    SET status = 'assigned', 
                        updated_at = NOW()
                    WHERE vehicle_code = %s AND status = 'available'
                """, (vehicle_code,))
                print(f"   ✅ Vehicle {vehicle_code} marked as assigned")
        
        # Mark drivers as active
        if dispatch['assigned_drivers']:
            driver_names = [name.strip() for name in dispatch['assigned_drivers'].split(',')]
            
            for driver_name in driver_names:
                dict_cursor.execute("""
                    SELECT user_id FROM users 
                    WHERE full_name = %s OR username = %s
                """, (driver_name, driver_name))
                driver = dict_cursor.fetchone()
                
                if driver:
                    regular_cursor.execute("""
                        UPDATE driver_assignments 
                        SET status = 'active'
                        WHERE driver_id = %s 
                        AND shift_date = CURDATE()
                        AND status = 'scheduled'
                    """, (driver['user_id'],))
                    print(f"   ✅ Driver {driver_name} marked as active")
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Dispatch is now enroute, vehicles and drivers assigned'
        })
        
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/driver/assignments', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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

@app.route('/api/delivery-records', methods=['POST'])
@login_required
def add_delivery_record():
    """Manually add a delivery record (for historical data)"""
    data = request.json
    conn = get_db_connection()
    if conn is None:
        return jsonify({'success': False, 'error': 'Database connection failed'})
    
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO delivery_records 
            (zone_id, delivery_timestamp, delivery_count, vehicle_type, distance_km)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            data['zone_id'],
            data['delivery_timestamp'],
            data['delivery_count'],
            data.get('vehicle_type', 'motorcycle'),
            data.get('distance_km', 5.0)
        ))
        
        conn.commit()
        record_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'record_id': record_id})
    except Exception as e:
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dispatch/assignments/full', methods=['POST'])
@login_required
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
              data.get('created_by', session.get('user_id', 1))))
        
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def get_dispatch_statuses():
    """Get distinct dispatch statuses for filters"""
    return jsonify({
        'success': True, 
        'dispatch_statuses': ['planned', 'assigned', 'enroute', 'completed', 'cancelled']
    })

# ============ RUN APP ============
if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')