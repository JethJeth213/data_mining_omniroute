import pandas as pd
import numpy as np
import mysql.connector
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score, classification_report
import joblib
import warnings
import os
warnings.filterwarnings('ignore')

print("=" * 60)
print("OmniRoute-DM Standalone Training")
print("=" * 60)

# Step 1: Load data from MySQL
print("\n[1/5] Loading data from MySQL...")
try:
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='omniroute_dm'
    )
    
    df = pd.read_sql("SELECT zone_id, delivery_timestamp, delivery_count FROM delivery_records", conn)
    conn.close()
    print(f"✅ Loaded {len(df)} records")
except Exception as e:
    print(f"❌ Error loading data: {e}")
    exit(1)

# Step 2: Feature engineering
print("\n[2/5] Engineering features...")
df['timestamp'] = pd.to_datetime(df['delivery_timestamp'])
df['hour'] = df['timestamp'].dt.hour
df['day_of_week'] = df['timestamp'].dt.dayofweek
df['month'] = df['timestamp'].dt.month

# Cyclical features
df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

# Boolean features
df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
df['is_morning_rush'] = ((df['hour'] >= 7) & (df['hour'] <= 9)).astype(int)
df['is_evening_rush'] = ((df['hour'] >= 17) & (df['hour'] <= 19)).astype(int)
df['is_lunch_hour'] = ((df['hour'] >= 12) & (df['hour'] <= 13)).astype(int)

# Sort by zone and timestamp for lags
df = df.sort_values(['zone_id', 'timestamp'])

# Create lag features per zone
print("   Creating lag features...")
lags = [1, 2, 3, 6, 12, 24]
for lag in lags:
    df[f'lag_{lag}h'] = df.groupby('zone_id')['delivery_count'].shift(lag)

# Create rolling features
print("   Creating rolling features...")
windows = [3, 6, 12, 24]
for window in windows:
    df[f'rolling_mean_{window}h'] = df.groupby('zone_id')['delivery_count'].transform(
        lambda x: x.rolling(window, min_periods=1).mean()
    )
    df[f'rolling_std_{window}h'] = df.groupby('zone_id')['delivery_count'].transform(
        lambda x: x.rolling(window, min_periods=1).std()
    )

# Fill NaN
df = df.fillna(0)

# Feature columns
feature_columns = [
    'hour', 'hour_sin', 'hour_cos',
    'day_of_week', 'dow_sin', 'dow_cos',
    'month', 'is_weekend', 'is_morning_rush',
    'is_evening_rush', 'is_lunch_hour',
    'lag_1h', 'lag_2h', 'lag_3h', 'lag_6h', 'lag_12h', 'lag_24h',
    'rolling_mean_3h', 'rolling_mean_6h', 'rolling_mean_12h', 'rolling_mean_24h',
    'rolling_std_3h', 'rolling_std_6h', 'rolling_std_12h', 'rolling_std_24h'
]

X = df[feature_columns]
y_reg = df['delivery_count']

# Classification labels
q33 = y_reg.quantile(0.33)
q66 = y_reg.quantile(0.66)
y_cls = np.where(y_reg <= q33, 0, np.where(y_reg <= q66, 1, 2))

print(f"✅ Features shape: {X.shape}")
print(f"   Features: {len(feature_columns)}")

# Step 3: Split data
print("\n[3/5] Splitting data...")
X_train, X_test, y_reg_train, y_reg_test, y_cls_train, y_cls_test = train_test_split(
    X, y_reg, y_cls, test_size=0.2, random_state=42
)

# Step 4: Train models
print("\n[4/5] Training models...")

# Scale features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Regression
print("   Training regression model...")
reg_model = RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42, n_jobs=-1)
reg_model.fit(X_train_scaled, y_reg_train)

# Evaluate regression
y_reg_pred = reg_model.predict(X_test_scaled)
mae = mean_absolute_error(y_reg_test, y_reg_pred)
r2 = r2_score(y_reg_test, y_reg_pred)
print(f"   Regression - MAE: {mae:.2f}, R²: {r2:.4f}")

# Classification
print("   Training classification model...")
cls_model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
cls_model.fit(X_train_scaled, y_cls_train)

# Evaluate classification
y_cls_pred = cls_model.predict(X_test_scaled)
accuracy = accuracy_score(y_cls_test, y_cls_pred)
print(f"   Classification - Accuracy: {accuracy:.4f}")

# Step 5: Save models
print("\n[5/5] Saving models...")
os.makedirs('backend/models', exist_ok=True)
joblib.dump(reg_model, 'backend/models/regression_model.pkl')
joblib.dump(cls_model, 'backend/models/classification_model.pkl')
joblib.dump(scaler, 'backend/models/scaler.pkl')

# Save feature columns
with open('backend/models/feature_columns.txt', 'w') as f:
    f.write(','.join(feature_columns))

# Check file sizes
import os
for model_file in ['regression_model.pkl', 'classification_model.pkl', 'scaler.pkl']:
    path = f'backend/models/{model_file}'
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"   ✅ {model_file} ({size:,} bytes)")
    else:
        print(f"   ❌ {model_file} not saved")

print("\n" + "=" * 60)
print("✅ TRAINING COMPLETE!")
print("=" * 60)
print("\nNow run: python backend/app.py")