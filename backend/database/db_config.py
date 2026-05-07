import mysql.connector
from mysql.connector import Error
import os

class DatabaseConfig:
    def __init__(self):
        self.config = {
            'host': 'localhost',
            'user': 'root',  # Your MySQL username
            'password': 'root',  # Your MySQL password
            'database': 'omniroute_dm',
            'port': 3306
        }
    
    def get_connection(self):
        try:
            connection = mysql.connector.connect(**self.config)
            return connection
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            return None

db_config = DatabaseConfig()