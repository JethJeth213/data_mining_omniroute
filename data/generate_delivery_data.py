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
    
    # Define holiday dates for 2026 (Philippine holidays)
    holidays_2026 = [
        '2026-01-01',  # New Year's Day
        '2026-04-09',  # Araw ng Kagitingan
        '2026-05-01',  # Labor Day
        '2026-06-12',  # Independence Day
        '2026-08-21',  # Ninoy Aquino Day
        '2026-08-31',  # National Heroes Day (last Monday of August)
        '2026-11-30',  # Bonifacio Day
        '2026-12-25',  # Christmas Day
        '2026-12-30',  # Rizal Day
        '2026-04-01',  # Maundy Thursday (example - actual dates vary)
        '2026-04-02',  # Good Friday (example - actual dates vary)
        '2026-04-03',  # Black Saturday (example - actual dates vary)
    ]
    
    print(f"Generating data from {start_date} to {end_date}")
    print(f"Total hours to generate: {len(date_range)}")
    
    for zone in zones:
        print(f"  Processing zone: {zone}")
        for timestamp in date_range:
            hour = timestamp.hour
            day_of_week = timestamp.dayofweek
            is_weekend = 1 if day_of_week >= 5 else 0
            is_holiday = 1 if timestamp.strftime('%Y-%m-%d') in holidays_2026 else 0
            
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
            
            # Month-based adjustment (seasonal patterns)
            month = timestamp.month
            if month in [12, 1, 2]:  # Holiday season
                base_demand *= 1.2
            elif month in [6, 7, 8]:  # Rainy season (slightly lower)
                base_demand *= 0.9
            
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

def save_to_csv(df, filename='delivery_data_2026.csv'):
    """Save dataframe to CSV"""
    df.to_csv(filename, index=False)
    print(f"\n✅ CSV saved to: {filename}")
    return os.path.abspath(filename)

def insert_to_mysql(df):
    """Insert data into MySQL database"""
    try:
        conn = mysql.connector.connect(
            host='localhost',
            port=3306,
            user='root',
            password='root',  # Your MySQL password
            database='omniroute_dm'
        )
        cursor = conn.cursor()
        
        # Optional: Clear existing data first
        confirm = input("\nDo you want to clear existing delivery_records before inserting? (y/n): ")
        if confirm.lower() == 'y':
            cursor.execute("TRUNCATE TABLE delivery_records")
            print("✅ Cleared existing delivery records")
        
        print("\nInserting data into MySQL...")
        inserted = 0
        batch_size = 1000
        batch_data = []
        
        for _, row in df.iterrows():
            batch_data.append((
                row['zone_id'], 
                row['delivery_timestamp'], 
                row['delivery_count'], 
                row['vehicle_type'], 
                row['distance_km']
            ))
            inserted += 1
            
            if len(batch_data) >= batch_size:
                cursor.executemany("""
                    INSERT INTO delivery_records 
                    (zone_id, delivery_timestamp, delivery_count, vehicle_type, distance_km)
                    VALUES (%s, %s, %s, %s, %s)
                """, batch_data)
                conn.commit()
                print(f"  Inserted {inserted} records...")
                batch_data = []
        
        # Insert remaining records
        if batch_data:
            cursor.executemany("""
                INSERT INTO delivery_records 
                (zone_id, delivery_timestamp, delivery_count, vehicle_type, distance_km)
                VALUES (%s, %s, %s, %s, %s)
            """, batch_data)
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

def generate_sample_verification(df):
    """Print verification statistics"""
    print("\n" + "=" * 60)
    print("DATA VERIFICATION")
    print("=" * 60)
    
    # Date range
    print(f"\n📅 Date Range: {df['delivery_timestamp'].min()} to {df['delivery_timestamp'].max()}")
    
    # Records per zone
    print("\n📍 Records per zone:")
    zone_counts = df['zone_id'].value_counts()
    for zone, count in zone_counts.items():
        print(f"   {zone}: {count:,} records")
    
    # Delivery statistics
    print("\n📊 Delivery Statistics:")
    print(f"   Total Deliveries: {df['delivery_count'].sum():,}")
    print(f"   Average per hour: {df['delivery_count'].mean():.1f}")
    print(f"   Max per hour: {df['delivery_count'].max()}")
    print(f"   Min per hour: {df['delivery_count'].min()}")
    
    # Peak hours
    print("\n⏰ Peak Hours (all zones):")
    df['hour'] = df['delivery_timestamp'].dt.hour
    peak_hours = df.groupby('hour')['delivery_count'].mean().sort_values(ascending=False).head(5)
    for hour, avg in peak_hours.items():
        print(f"   {hour}:00 - {avg:.1f} avg deliveries")
    
    # Vehicle type distribution
    print("\n🚗 Vehicle Type Distribution:")
    vehicle_counts = df['vehicle_type'].value_counts()
    for vtype, count in vehicle_counts.items():
        print(f"   {vtype}: {count:,} records ({count/len(df)*100:.1f}%)")

if __name__ == "__main__":
    print("=" * 60)
    print("OmniRoute-DM Data Generator (2026 Data)")
    print("=" * 60)
    
    zones = ['ZONE_A', 'ZONE_B', 'ZONE_C', 'ZONE_D', 'ZONE_E']
    
    # Generate data from January 1, 2026 to May 8, 2026 (today)
    # This gives approximately 5 months of hourly data
    start_date = '2026-01-01'
    end_date = '2026-05-08'  # Today's date
    
    print(f"\n📅 Generating data from {start_date} to {end_date}")
    print(f"   (5 months of historical data)")
    
    # Generate synthetic delivery data
    print("\n🔄 Generating synthetic delivery data...")
    df = generate_delivery_data(start_date, end_date, zones)
    
    print(f"\n✅ Generated {len(df):,} delivery records")
    
    # Sample data preview
    print("\n📋 Sample data (first 10 rows):")
    print(df.head(10))
    
    print("\n📈 Data summary:")
    print(df.describe())
    
    # Generate verification stats
    generate_sample_verification(df)
    
    # Save to CSV
    csv_path = save_to_csv(df)
    
    # Insert to MySQL
    success = insert_to_mysql(df)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ DATA GENERATION COMPLETE!")
        print("=" * 60)
        print(f"\n📁 CSV saved to: {csv_path}")
        print(f"💾 Database: omniroute_dm")
        print(f"📊 Records inserted: {len(df):,}")
        print(f"\n📅 Data covers: {start_date} to {end_date}")
        print(f"   (Approximately 5 months of hourly data)")
        print(f"\n🚀 Next steps:")
        print("   1. Run: python train_standalone.py")
        print("   2. Run: python backend/app.py")
        print("   3. Open index.html in browser")
    else:
        print("\n⚠️ CSV file saved but MySQL insertion failed.")
        print(f"📁 CSV location: {csv_path}")
        print("💡 You can still use the CSV file for training by modifying train_model.py")