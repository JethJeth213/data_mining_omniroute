# 🚚 OmniRoute-DM - Demand Forecasting System

A data mining system that predicts delivery demand and recommends vehicle dispatch for logistics companies.

## 📋 Overview

OmniRoute-DM uses machine learning to answer two critical questions:
- **How many deliveries will occur in the next hour?** (Regression)
- **Is that hour normal, high-demand, or at peak risk?** (Classification)

The system helps dispatchers prepare the right number of vehicles before demand spikes.

---

## 💻 Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.8+ | Run the ML models |
| MySQL | 8.0+ | Store delivery data |
| MySQL Workbench | Any | Database management |
| Git | Any | Clone the repository |

---

## 🚀 Quick Setup (10-15 minutes)

### Step 1: Clone the Repository

```bash
git clone [your-repo-url]
cd data_mining_omniroute/data_mining_omniroute

Step 2: Install Python Packages

pip install -r requirements.txt

This installs: Flask, pandas, scikit-learn, xgboost, MySQL connector, and other dependencies.

💡 Tip: If the command fails, try python -m pip install -r requirements.txt

Step 3: Setup MySQL Database
3.1 Start MySQL
Windows: Search for "MySQL Workbench" and open it

Mac: Open Terminal → mysql -u root -p

3.2 Import the Database Schema
Option A (Recommended):

Open MySQL Workbench

File → Open SQL Script → Select database_schema.sql

Click the lightning bolt ⚡ to execute

Option B (Command Line):

bash
mysql -u root -p < database_schema.sql
3.3 Configure Database Password
Open backend/database/db_config.py and update the password:

python
'password': 'YOUR_MYSQL_PASSWORD',  # ← Change this to your actual password
🔑 Common passwords: Try 'root', '' (empty), or 'password'

Step 4: Generate Data (Required)
You need to generate the delivery data:

bash
python data/generate_delivery_data.py
This creates 21,000+ synthetic delivery records in your database.

Expected output:

text
============================================================
OmniRoute-DM Data Generator
============================================================

Generating synthetic delivery data...
  Processing zone: ZONE_A
  Processing zone: ZONE_B
  ...
✅ Generated 21840 delivery records
✅ Successfully inserted 21840 records into MySQL database
⚠️ Note: The ML models (.pkl files) are already in the repo, so you SKIP the training step!

Step 5: Start the Web Application
bash
python backend/app.py
Expected output:

text
✅ Models loaded successfully!
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.21:5000
🟢 Keep this terminal open! The server needs to stay running.

Step 6: Open the Dashboard
Open your web browser and go to:

text
http://127.0.0.1:5000
🎮 How to Use the Dashboard
Making a Prediction
Select a Zone

Zone A - Downtown (busiest)

Zone B - North District

Zone C - South District

Zone D - East Commercial

Zone E - West Residential (quietest)

Pick a Date & Time

Any date between January 1 - June 30, 2024

Try different hours to compare demand

Click "Predict Demand"

Review the Results

📦 Predicted deliveries

🚦 Demand level (Normal/High/Peak)

🚚 Vehicle recommendation

📊 Confidence interval

Understanding the Results
Demand Level	Deliveries	What It Means	Recommended Action
Normal	0-15	Regular operations	Standard fleet
High	15-25	Increased demand	Add 1-2 vans
Peak	25+	Critical demand	Deploy all vehicles
Zone Reference
Zone	Area Type	Peak Hours	Base Vehicles
ZONE_A	Downtown	12-2 PM, 5-7 PM	5 motorcycles
ZONE_B	North District	11-1 PM, 5-6 PM	3 motorcycles
ZONE_C	South District	12-2 PM, 5-7 PM	3 motorcycles
ZONE_D	East Commercial	11-2 PM, 5-7 PM	4 motorcycles
ZONE_E	West Residential	5-8 PM	2 motorcycles
🔧 Troubleshooting
❌ "pip install" fails
bash
# Upgrade pip first
python -m pip install --upgrade pip

# Then retry
pip install -r requirements.txt
❌ "Access denied for user 'root'"
Check your MySQL password in db_config.py

Try these common passwords: 'root', '' (empty), 'password'

Or reset MySQL password

❌ "Table 'omniroute_dm.xxx' doesn't exist"
Re-run the database_schema.sql script in MySQL Workbench

Make sure you're using the correct database: USE omniroute_dm;

❌ "Module not found"
bash
# Reinstall all packages
pip install --force-reinstall -r requirements.txt
❌ Port 5000 already in use
Change the port in backend/app.py (last line):

python
app.run(debug=True, host='0.0.0.0', port=5001)
Then access: http://127.0.0.1:5001

❌ No data in database
bash
# Generate data
python data/generate_delivery_data.py
❌ Predictions not showing
Make sure you:

Generated data: python data/generate_delivery_data.py

MySQL is running

Password is correct in db_config.py

Date is between Jan 1 - June 30, 2024

📁 Project Structure
text
data_mining_omniroute/
├── backend/
│   ├── app.py                    # Main Flask server (RUN THIS)
│   ├── models/
│   │   ├── regression_model.pkl  # ✅ Already trained (in repo)
│   │   ├── classification_model.pkl # ✅ Already trained
│   │   └── scaler.pkl            # ✅ Already saved
│   ├── database/
│   │   ├── db_config.py          # ⚙️ Edit password here
│   │   └── queries.py
│   └── utils/
│       ├── feature_engineer.py
│       └── recommendations.py
├── data/
│   └── generate_delivery_data.py # Run this to create data
├── frontend/
│   ├── index.html                # Dashboard
│   ├── style.css
│   └── script.js
├── database_schema.sql           # Database setup (run this first)
├── requirements.txt              # Python dependencies
└── README.md                     # This file
✅ Quick Checklist
Before running, make sure you:

Python installed ✅

MySQL installed ✅

MySQL Workbench installed ✅

Ran pip install -r requirements.txt ✅

Imported database_schema.sql in MySQL ✅

Updated password in db_config.py ✅

Ran python data/generate_delivery_data.py ✅

Ran python backend/app.py ✅

Opened http://127.0.0.1:5000 ✅

🧪 Test Scenarios to Try
Scenario 1: Compare Peak vs Off-Peak
Peak: Zone A, Monday 5:00 PM → Should show High/Peak demand

Off-peak: Zone E, Sunday 3:00 AM → Should show Normal demand

Scenario 2: Compare Different Zones
Downtown (ZONE_A) → Highest predicted deliveries

Residential (ZONE_E) → Lowest predicted deliveries

Scenario 3: Historical Patterns
Lunch hour (12:00 PM) → Higher demand

Late night (2:00 AM) → Lower demand

📊 Database Tables
Table	Purpose
delivery_records	Historical delivery data (generated by you)
zones	Zone configurations
predictions_log	All predictions made through the dashboard
Useful SQL Queries
sql
-- Check how many records you have
SELECT COUNT(*) FROM delivery_records;

-- See recent predictions
SELECT * FROM predictions_log ORDER BY created_at DESC LIMIT 10;

-- Check zone configurations
SELECT * FROM zones;
💡 Important Notes
You don't need to retrain the models - The .pkl files are already in the repo

You MUST generate the data - Run python data/generate_delivery_data.py

Use dates between Jan 1 - June 30, 2024 for predictions

Keep the Flask terminal open while using the dashboard

📞 Getting Help
If you get stuck:

Check the error message carefully

Make sure MySQL is running

Verify your password in db_config.py

Try restarting: python backend/app.py

Ask the team for help