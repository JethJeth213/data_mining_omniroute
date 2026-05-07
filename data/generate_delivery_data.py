import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import mysql.connector
import os

def generate_delivery_data(start_date, end_date, zones):
    """Generate synthetic delivery data with realistic patterns"""
    
    # Use 'h' (lowercase) instead of 'H' for hourly frequency
    date_range = pd.date_range(start=start_date, end=end_date, freq='h')
    records = []
    
    # Define holiday dates (Philippine holidays example)
    holidays = ['2024-01-01', '2024-04-09', '2024-05-01', '2024-06-12', 
                '2024-08-21', '2024-11-30', '2024-12-25', '2024-12-30']
    
    print(f"Generating data for {len(date_range)} hours...")
    
    for zone in zones:
        print(f"  Processing zone: {zone}")
        for timestamp in date_range:
            hour = timestamp.hour
            day_of_week = timestamp.dayofweek
            is_weekend = 1 if day_of_week >= 5 else 0
            is_holiday = 1 if timestamp.strftime('%Y-%m-%d') in holidays else 0
            
            # Base demand by zone and hour pattern
            if zone == 'ZONE_A':  # Downtown
                base_demand = 25 if 9 <= hour <= 18 else 8
                peak_hours = [12, 13, 18, 19]
            elif zone == 'ZONE_B':  # North
                base_demand = 18 if 8 <= hour <= 20 else 5
                peak_hours = [11, 12, 17, 18]
            elif zone == 'ZONE_C':  # South
                base_demand = 15 if 9 <= hour <= 19 else 4
                peak_hours = [12, 13, 18]
            elif zone == 'ZONE_D':  # East Commercial
                base_demand = 20 if 9 <= hour <= 20 else 6
                peak_hours = [11, 12, 18, 19]
            else:  # West Residential
                base_demand = 12 if 10 <= hour <= 19 else 3
                peak_hours = [17, 18, 19]
            
            # Adjust for peak hours
            if hour in peak_hours:
                base_demand *= 1.5
            
            # Weekend adjustment
            if is_weekend:
                if zone == 'ZONE_A':
                    base_demand *= 0.7
                else:
                    base_demand *= 0.8
            
            # Holiday adjustment (increased demand)
            if is_holiday:
                base_demand *= 1.3
            
            # Add random noise
            noise = np.random.normal(0, base_demand * 0.15)
            delivery_count = max(0, int(base_demand + noise))
            
            records.append({
                'zone_id': zone,
                'delivery_timestamp': timestamp,
                'delivery_count': delivery_count,
                'vehicle_type': random.choice(['motorcycle', 'van', 'truck']),
                'distance_km': round(random.uniform(1, 15), 2)
            })
    
    return pd.DataFrame(records)

def save_to_csv(df, filename='delivery_data.csv'):
    """Save dataframe to CSV"""
    df.to_csv(filename, index=False)
    print(f"\n✅ CSV saved to: {filename}")
    return os.path.abspath(filename)

def insert_to_mysql(df):
    """Insert data into MySQL database"""
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='root',  # Change if you have a password
            database='omniroute_dm'
        )
        cursor = conn.cursor()
        
        print("\nInserting data into MySQL...")
        inserted = 0
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO delivery_records 
                (zone_id, delivery_timestamp, delivery_count, vehicle_type, distance_km)
                VALUES (%s, %s, %s, %s, %s)
            """, (row['zone_id'], row['delivery_timestamp'], row['delivery_count'], 
                  row['vehicle_type'], row['distance_km']))
            inserted += 1
            if inserted % 1000 == 0:
                print(f"  Inserted {inserted} records...")
        
        conn.commit()
        print(f"✅ Successfully inserted {inserted} records into MySQL database")
        
        cursor.close()
        conn.close()
        return True
        
    except mysql.connector.Error as e:
        print(f"❌ MySQL Error: {e}")
        print("\nMake sure:")
        print("  1. MySQL is running")
        print("  2. Database 'omniroute_dm' exists")
        print("  3. Table 'delivery_records' exists")
        print("  4. Run the SQL setup script first")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("OmniRoute-DM Data Generator")
    print("=" * 60)
    
    zones = ['ZONE_A', 'ZONE_B', 'ZONE_C', 'ZONE_D', 'ZONE_E']
    
    # Generate 6 months of hourly data
    print("\nGenerating synthetic delivery data...")
    df = generate_delivery_data('2024-01-01', '2024-06-30', zones)
    
    print(f"\n✅ Generated {len(df)} delivery records")
    print(f"\nSample data:")
    print(df.head(10))
    print(f"\nData summary:")
    print(df.describe())
    
    # Save to CSV
    csv_path = save_to_csv(df)
    
    # Insert to MySQL
    success = insert_to_mysql(df)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ DATA GENERATION COMPLETE!")
        print("=" * 60)
        print(f"\nNext steps:")
        print("1. Run: python backend/models/train_model.py")
        print("2. Run: python backend/app.py")
    else:
        print("\n⚠️ CSV file saved but MySQL insertion failed.")
        print(f"CSV location: {csv_path}")
        print("You can still use the CSV file for training by modifying train_model.py")