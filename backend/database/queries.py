from .db_config import db_config

class DatabaseQueries:
    @staticmethod
    def get_delivery_data(zone_id=None, start_date=None, end_date=None):
        """Fetch delivery records with optional filters"""
        connection = db_config.get_connection()
        if not connection:
            return []
        
        cursor = connection.cursor(dictionary=True)
        
        query = """
            SELECT delivery_id, zone_id, delivery_timestamp, delivery_count, 
                   vehicle_type, distance_km
            FROM delivery_records
            WHERE 1=1
        """
        params = []
        
        if zone_id:
            query += " AND zone_id = %s"
            params.append(zone_id)
        
        if start_date:
            query += " AND delivery_timestamp >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND delivery_timestamp <= %s"
            params.append(end_date)
        
        query += " ORDER BY delivery_timestamp"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return results
    
    @staticmethod
    def get_zone_config(zone_id):
        """Get zone configuration"""
        connection = db_config.get_connection()
        if not connection:
            return None
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM zones WHERE zone_id = %s", (zone_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return result
    
    @staticmethod
    def save_prediction(zone_id, predicted_hour, predicted_count, demand_level, recommendation):
        """Save prediction to log"""
        connection = db_config.get_connection()
        if not connection:
            return
        
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO predictions_log 
            (zone_id, predicted_hour, predicted_count, demand_level, recommendation)
            VALUES (%s, %s, %s, %s, %s)
        """, (zone_id, predicted_hour, predicted_count, demand_level, recommendation))
        
        connection.commit()
        cursor.close()
        connection.close()