from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.train_model import DemandForecaster
from database.queries import DatabaseQueries
from utils.feature_engineer import prepare_features
from utils.recommendations import generate_actionable_message, get_demand_label, get_vehicle_recommendation

app = Flask(__name__)
CORS(app)

# Get the path to the frontend folder
frontend_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')

@app.route('/')
def serve_frontend():
    """Serve the main dashboard HTML file"""
    try:
        return send_from_directory(frontend_folder, 'index.html')
    except Exception as e:
        return f"Error loading frontend: {e}", 500

@app.route('/style.css')
def serve_css():
    """Serve the CSS file"""
    return send_from_directory(frontend_folder, 'style.css')

@app.route('/script.js')
def serve_js():
    """Serve the JavaScript file"""
    return send_from_directory(frontend_folder, 'script.js')

# Initialize forecaster and load models
forecaster = DemandForecaster()

try:
    forecaster.load_models()
    models_loaded = True
    print("✅ Models loaded successfully!")
except:
    models_loaded = False
    print("❌ Models not found. Please run train_model.py first.")

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'models_loaded': models_loaded,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/zones', methods=['GET'])
def get_zones():
    """Get all available zones"""
    zones = ['ZONE_A', 'ZONE_B', 'ZONE_C', 'ZONE_D', 'ZONE_E']
    return jsonify({'zones': zones})

@app.route('/api/zone_config', methods=['GET'])
def get_zone_config():
    """Get configuration for a specific zone"""
    zone_id = request.args.get('zone_id')
    
    config = DatabaseQueries.get_zone_config(zone_id)
    
    if config:
        return jsonify(config)
    else:
        return jsonify({'error': 'Zone not found'}), 404

@app.route('/api/predict', methods=['POST'])
def predict():
    """Make prediction for a specific zone and time"""
    
    if not models_loaded:
        return jsonify({'error': 'Models not loaded. Please train models first.'}), 500
    
    data = request.json
    zone_id = data.get('zone_id')
    prediction_datetime_str = data.get('datetime')
    
    if not zone_id or not prediction_datetime_str:
        return jsonify({'error': 'Missing zone_id or datetime'}), 400
    
    try:
        prediction_datetime = datetime.strptime(prediction_datetime_str, '%Y-%m-%d %H:%M:%S')
    except:
        try:
            prediction_datetime = datetime.strptime(prediction_datetime_str, '%Y-%m-%d %H')
        except:
            return jsonify({'error': 'Invalid datetime format. Use YYYY-MM-DD HH:MM:SS'}), 400
    
    # Get historical data for feature engineering
    start_date = prediction_datetime - timedelta(days=30)
    end_date = prediction_datetime
    
    historical_data = DatabaseQueries.get_delivery_data(
        zone_id=zone_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if len(historical_data) < 24:
        return jsonify({
            'error': 'Insufficient historical data for this zone',
            'message': f'Only {len(historical_data)} records found. Need at least 24 hours of data.'
        }), 400
    
    # Prepare features for prediction
    df = pd.DataFrame(historical_data)
    
    # Create a row for prediction time
    prediction_row = pd.DataFrame([{
        'delivery_timestamp': prediction_datetime,
        'delivery_count': 0
    }])
    
    # Combine historical and prediction row
    combined_df = pd.concat([df, prediction_row], ignore_index=True)
    
    # Engineer features
    combined_df, feature_columns = prepare_features(combined_df)
    
    # Get features for prediction row
    X_pred = combined_df[feature_columns].iloc[-1:].fillna(0)
    
    # Scale features
    X_pred_scaled = forecaster.scaler.transform(X_pred)
    
    # Make predictions
    predicted_count = forecaster.regression_model.predict(X_pred_scaled)[0]
    predicted_class = forecaster.classification_model.predict(X_pred_scaled)[0]
    
    # Ensure non-negative
    predicted_count = max(0, predicted_count)
    
    # Get zone configuration
    zone_config = DatabaseQueries.get_zone_config(zone_id)
    if not zone_config:
        zone_config = {
            'zone_id': zone_id,
            'base_vehicles': 3,
            'threshold_normal': 15,
            'threshold_high': 25
        }
    
    # Generate recommendation
    action = generate_actionable_message(
        zone_id, predicted_count, prediction_datetime, zone_config
    )
    
    # Save prediction to log
    DatabaseQueries.save_prediction(
        zone_id, prediction_datetime, predicted_count, 
        action['demand_level'], action['recommendation']
    )
    
    # Confidence interval
    confidence_interval = [max(0, predicted_count - 5), predicted_count + 5]
    
    return jsonify({
        'success': True,
        'prediction': {
            'zone_id': zone_id,
            'datetime': action['predicted_hour'],
            'predicted_deliveries': action['predicted_count'],
            'demand_level': action['demand_level'],
            'confidence_interval': confidence_interval,
            'recommendation': action['recommendation'],
            'vehicle_breakdown': action['vehicle_breakdown'],
            'full_message': action['message']
        }
    })

@app.route('/api/historical_stats', methods=['GET'])
def get_historical_stats():
    """Get historical statistics for a zone"""
    zone_id = request.args.get('zone_id')
    days = int(request.args.get('days', 30))
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    data = DatabaseQueries.get_delivery_data(
        zone_id=zone_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if not data:
        return jsonify({'error': 'No historical data found'}), 404
    
    df = pd.DataFrame(data)
    
    stats = {
        'total_deliveries': int(df['delivery_count'].sum()),
        'avg_daily_deliveries': float(df.groupby(df['delivery_timestamp'].dt.date)['delivery_count'].sum().mean()),
        'avg_hourly_deliveries': float(df['delivery_count'].mean()),
        'max_hourly': int(df['delivery_count'].max()),
        'peak_hours': df.groupby(df['delivery_timestamp'].dt.hour)['delivery_count'].mean().nlargest(3).to_dict()
    }
    
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)