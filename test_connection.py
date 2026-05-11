import mysql.connector

try:
    conn = mysql.connector.connect(
        host='127.0.0.1',
        user='root',
        password='',  # Try empty first
        port=3307,
        database='omniroute_dm'
    )
    print("✅ SUCCESS! Connected to database!")
    conn.close()
except mysql.connector.Error as err:
    print(f"❌ Failed: {err}")