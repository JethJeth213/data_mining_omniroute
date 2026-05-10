import mysql.connector

try:
    conn = mysql.connector.connect(
        host='127.0.0.1',
        user='root',
        password='root',  # Try empty first
        port=3306,
        database='omniroute_dm2'
    )
    print("✅ SUCCESS! Connected to database!")
    conn.close()
except mysql.connector.Error as err:
    print(f"❌ Failed: {err}")