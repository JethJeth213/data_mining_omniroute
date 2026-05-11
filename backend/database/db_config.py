import mysql.connector
from mysql.connector import Error

class DatabaseConfig:
    def __init__(self):
        self.config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'omniroute_dm',  # ← FIXED: changed from 'omniroute_db'
            'port': 3307
        }
    
    def get_connection(self):
        try:
            print(f"🔌 Attempting connection to {self.config['host']}:{self.config['port']}...")
            connection = mysql.connector.connect(**self.config)
            print("✅ Database connected!")
            return connection
        except Exception as e:
            print(f"❌ DATABASE ERROR: {e}")
            return None

db_config = DatabaseConfig()