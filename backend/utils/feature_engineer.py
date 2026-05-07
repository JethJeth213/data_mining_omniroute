import pandas as pd
import numpy as np
from datetime import datetime

def create_time_features(df):
    """Create time-based features from timestamp"""
    
    if 'delivery_timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['delivery_timestamp'])
    else:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Basic time features
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['month'] = df['timestamp'].dt.month
    df['day_of_month'] = df['timestamp'].dt.day
    df['week_of_year'] = df['timestamp'].dt.isocalendar().week
    
    # Cyclical encoding for hour
    df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    
    # Cyclical encoding for day of week
    df['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
    
    # Boolean features
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['is_morning_rush'] = ((df['hour'] >= 7) & (df['hour'] <= 9)).astype(int)
    df['is_evening_rush'] = ((df['hour'] >= 17) & (df['hour'] <= 19)).astype(int)
    df['is_lunch_hour'] = ((df['hour'] >= 12) & (df['hour'] <= 13)).astype(int)
    
    return df

def create_lag_features(df, target_col, lags=[1, 2, 3, 6, 12, 24]):
    """Create lag features for time series"""
    df_sorted = df.sort_values('timestamp').copy()
    
    for lag in lags:
        df_sorted[f'lag_{lag}h'] = df_sorted[target_col].shift(lag)
    
    return df_sorted

def create_rolling_features(df, target_col, windows=[3, 6, 12, 24]):
    """Create rolling average features"""
    df_sorted = df.sort_values('timestamp').copy()
    
    for window in windows:
        df_sorted[f'rolling_mean_{window}h'] = df_sorted[target_col].rolling(window=window, min_periods=1).mean()
        df_sorted[f'rolling_std_{window}h'] = df_sorted[target_col].rolling(window=window, min_periods=1).std()
    
    return df_sorted

def prepare_features(df):
    """Complete feature engineering pipeline"""
    
    # Create time features
    df = create_time_features(df)
    
    # Create lag features
    df = create_lag_features(df, 'delivery_count')
    
    # Create rolling features
    df = create_rolling_features(df, 'delivery_count')
    
    # Handle NaN values
    df = df.fillna(0)
    
    # Select features for model (MUST match training)
    feature_columns = [
        'hour', 'hour_sin', 'hour_cos',
        'day_of_week', 'dow_sin', 'dow_cos',
        'month', 'is_weekend', 'is_morning_rush',
        'is_evening_rush', 'is_lunch_hour',
        'lag_1h', 'lag_2h', 'lag_3h', 'lag_6h', 'lag_12h', 'lag_24h',
        'rolling_mean_3h', 'rolling_mean_6h', 'rolling_mean_12h', 'rolling_mean_24h',
        'rolling_std_3h', 'rolling_std_6h', 'rolling_std_12h', 'rolling_std_24h'
    ]
    
    return df, feature_columns