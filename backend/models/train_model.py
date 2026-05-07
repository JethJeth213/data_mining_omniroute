import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, classification_report, accuracy_score
import joblib
import warnings
warnings.filterwarnings('ignore')

class DemandForecaster:
    def __init__(self):
        self.regression_model = None
        self.classification_model = None
        self.scaler = StandardScaler()
        self.feature_columns = None
        
    def load_data_from_db(self, zone_id=None):
        """Load data from database"""
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='root',  # Change if you have a password
                database='omniroute_dm'
            )
            
            query = "SELECT zone_id, delivery_timestamp, delivery_count FROM delivery_records"
            if zone_id:
                query += f" WHERE zone_id = '{zone_id}'"
            
            df = pd.read_sql(query, conn)
            conn.close()
            
            print(f"✅ Loaded {len(df)} records from database")
            return df
            
        except Exception as e:
            print(f"⚠️ Could not load from database: {e}")
            return None
    
    def load_data_from_csv(self, csv_path='data/delivery_data.csv'):
        """Load data from CSV as backup"""
        try:
            # Try multiple possible locations
            possible_paths = [
                csv_path,
                '../data/delivery_data.csv',
                'data/delivery_data.csv',
                'delivery_data.csv'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    df = pd.read_csv(path)
                    print(f"✅ Loaded {len(df)} records from CSV: {path}")
                    return df
            
            print("❌ No CSV file found")
            return None
            
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            return None
    
    def create_time_features(self, df):
        """Create time-based features"""
        df['timestamp'] = pd.to_datetime(df['delivery_timestamp'])
        
        df['hour'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['month'] = df['timestamp'].dt.month
        df['day_of_month'] = df['timestamp'].dt.day
        
        # Cyclical encoding
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        
        # Boolean features
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        df['is_morning_rush'] = ((df['hour'] >= 7) & (df['hour'] <= 9)).astype(int)
        df['is_evening_rush'] = ((df['hour'] >= 17) & (df['hour'] <= 19)).astype(int)
        df['is_lunch_hour'] = ((df['hour'] >= 12) & (df['hour'] <= 13)).astype(int)
        
        return df
    
    def create_lag_features(self, df):
        """Create lag features per zone"""
        zones = df['zone_id'].unique()
        all_dfs = []
        
        for zone in zones:
            zone_df = df[df['zone_id'] == zone].copy()
            zone_df = zone_df.sort_values('timestamp')
            
            # Create lags
            for lag in [1, 2, 3, 6, 12, 24]:
                zone_df[f'lag_{lag}h'] = zone_df['delivery_count'].shift(lag)
            
            # Create rolling averages
            for window in [3, 6, 12, 24]:
                zone_df[f'rolling_mean_{window}h'] = zone_df['delivery_count'].rolling(window=window, min_periods=1).mean()
            
            all_dfs.append(zone_df)
        
        return pd.concat(all_dfs, ignore_index=True)
    
    def prepare_training_data(self, df):
        """Prepare features and targets"""
        
        print("\nEngineering features...")
        df = self.create_time_features(df)
        df = self.create_lag_features(df)
        
        # Define feature columns
        self.feature_columns = [
            'hour', 'hour_sin', 'hour_cos',
            'day_of_week', 'dow_sin', 'dow_cos',
            'month', 'is_weekend', 'is_morning_rush',
            'is_evening_rush', 'is_lunch_hour',
            'lag_1h', 'lag_2h', 'lag_3h', 'lag_6h', 'lag_12h', 'lag_24h',
            'rolling_mean_3h', 'rolling_mean_6h', 'rolling_mean_12h', 'rolling_mean_24h'
        ]
        
        # Fill NaN values
        df = df.fillna(0)
        
        # Prepare features
        X = df[self.feature_columns]
        
        # Target for regression
        y_reg = df['delivery_count']
        
        # Target for classification (based on percentiles)
        q33 = y_reg.quantile(0.33)
        q66 = y_reg.quantile(0.66)
        
        y_cls = np.where(y_reg <= q33, 0,  # Normal
                        np.where(y_reg <= q66, 1,  # High
                                2))  # Peak
        
        print(f"Features shape: {X.shape}")
        print(f"Classification distribution: Normal={sum(y_cls==0)}, High={sum(y_cls==1)}, Peak={sum(y_cls==2)}")
        
        return X, y_reg, y_cls
    
    def train_models(self, X, y_reg, y_cls):
        """Train both models"""
        
        # Split data
        X_train, X_test, y_reg_train, y_reg_test, y_cls_train, y_cls_test = train_test_split(
            X, y_reg, y_cls, test_size=0.2, random_state=42, stratify=y_cls
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train Regression Model
        print("\n" + "="*50)
        print("Training Regression Model...")
        print("="*50)
        
        self.regression_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.regression_model.fit(X_train_scaled, y_reg_train)
        
        # Evaluate Regression
        y_reg_pred = self.regression_model.predict(X_test_scaled)
        
        mae = mean_absolute_error(y_reg_test, y_reg_pred)
        rmse = np.sqrt(mean_squared_error(y_reg_test, y_reg_pred))
        r2 = r2_score(y_reg_test, y_reg_pred)
        
        print(f"\nRegression Results:")
        print(f"  MAE: {mae:.2f} deliveries")
        print(f"  RMSE: {rmse:.2f} deliveries")
        print(f"  R² Score: {r2:.4f}")
        
        # Train Classification Model
        print("\n" + "="*50)
        print("Training Classification Model...")
        print("="*50)
        
        self.classification_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        self.classification_model.fit(X_train_scaled, y_cls_train)
        
        # Evaluate Classification
        y_cls_pred = self.classification_model.predict(X_test_scaled)
        
        accuracy = accuracy_score(y_cls_test, y_cls_pred)
        print(f"\nClassification Results:")
        print(f"  Accuracy: {accuracy:.4f}")
        print("\n  Detailed Report:")
        print(classification_report(y_cls_test, y_cls_pred, 
                                   target_names=['Normal', 'High', 'Peak']))
        
        return X_test_scaled, y_reg_test, y_cls_test
    
    def save_models(self):
        """Save models to disk"""
        model_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Save models
        joblib.dump(self.regression_model, os.path.join(model_dir, 'regression_model.pkl'))
        joblib.dump(self.classification_model, os.path.join(model_dir, 'classification_model.pkl'))
        joblib.dump(self.scaler, os.path.join(model_dir, 'scaler.pkl'))
        
        # Save feature columns
        with open(os.path.join(model_dir, 'feature_columns.txt'), 'w') as f:
            f.write(','.join(self.feature_columns))
        
        print(f"\n✅ Models saved to: {model_dir}")
        print(f"   - regression_model.pkl")
        print(f"   - classification_model.pkl")
        print(f"   - scaler.pkl")
        
        # Verify files were created
        for filename in ['regression_model.pkl', 'classification_model.pkl', 'scaler.pkl']:
            filepath = os.path.join(model_dir, filename)
            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                print(f"   ✓ {filename} ({size:,} bytes)")
            else:
                print(f"   ✗ {filename} NOT CREATED!")
    
    def load_models(self):
        """Load trained models"""
        model_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.regression_model = joblib.load(os.path.join(model_dir, 'regression_model.pkl'))
        self.classification_model = joblib.load(os.path.join(model_dir, 'classification_model.pkl'))
        self.scaler = joblib.load(os.path.join(model_dir, 'scaler.pkl'))
        
        # Load feature columns
        with open(os.path.join(model_dir, 'feature_columns.txt'), 'r') as f:
            self.feature_columns = f.read().split(',')
        
        print("✅ Models loaded successfully!")

if __name__ == "__main__":
    print("=" * 60)
    print("OmniRoute-DM Model Training Pipeline")
    print("=" * 60)
    
    forecaster = DemandForecaster()
    
    # Try to load from database first
    print("\n[1/4] Loading data...")
    df = forecaster.load_data_from_db()
    
    # If no database, try CSV
    if df is None or len(df) == 0:
        print("Attempting to load from CSV...")
        df = forecaster.load_data_from_csv()
    
    if df is None or len(df) == 0:
        print("\n❌ No data found!")
        print("\nPlease run first:")
        print("  python data/generate_delivery_data.py")
        sys.exit(1)
    
    print(f"\n[2/4] Preparing features for {len(df)} records...")
    X, y_reg, y_cls = forecaster.prepare_training_data(df)
    
    print(f"\n[3/4] Training models...")
    forecaster.train_models(X, y_reg, y_cls)
    
    print(f"\n[4/4] Saving models...")
    forecaster.save_models()
    
    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE!")
    print("=" * 60)
    print("\nNext step: python backend/app.py")