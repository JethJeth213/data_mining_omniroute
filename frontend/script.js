// API Configuration
const API_BASE_URL = 'http://localhost:5000/api';

// DOM Elements
const zoneSelect = document.getElementById('zoneSelect');
const dateTimeSelect = document.getElementById('dateTimeSelect');
const predictBtn = document.getElementById('predictBtn');
const resultsPanel = document.getElementById('resultsPanel');
const loadingOverlay = document.getElementById('loadingOverlay');
const statsSection = document.getElementById('statsSection');

// Set default datetime (next hour)
function setDefaultDateTime() {
    const now = new Date();
    now.setHours(now.getHours() + 1);
    now.setMinutes(0);
    now.setSeconds(0);
    
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    
    dateTimeSelect.value = `${year}-${month}-${day}T${hours}:00`;
}

// Quick select buttons
document.querySelectorAll('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const hours = parseInt(btn.dataset.hours);
        const currentDate = dateTimeSelect.value ? new Date(dateTimeSelect.value) : new Date();
        currentDate.setHours(currentDate.getHours() + hours);
        
        const year = currentDate.getFullYear();
        const month = String(currentDate.getMonth() + 1).padStart(2, '0');
        const day = String(currentDate.getDate()).padStart(2, '0');
        const hoursStr = String(currentDate.getHours()).padStart(2, '0');
        
        dateTimeSelect.value = `${year}-${month}-${day}T${hoursStr}:00`;
    });
});

// Zone selection change
zoneSelect.addEventListener('change', async () => {
    const zoneId = zoneSelect.value;
    if (zoneId) {
        await loadHistoricalStats(zoneId);
    } else {
        statsSection.style.display = 'none';
    }
});

// Load historical stats
async function loadHistoricalStats(zoneId) {
    try {
        const response = await fetch(`${API_BASE_URL}/historical_stats?zone_id=${zoneId}&days=30`);
        const data = await response.json();
        
        if (!data.error) {
            displayHistoricalStats(data);
            statsSection.style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Display historical stats
function displayHistoricalStats(stats) {
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.innerHTML = `
        <div class="stat-item">
            <div class="stat-label">Total Deliveries (30 days)</div>
            <div class="stat-value">${stats.total_deliveries.toLocaleString()}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Avg Daily Deliveries</div>
            <div class="stat-value">${Math.round(stats.avg_daily_deliveries)}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Avg Hourly Deliveries</div>
            <div class="stat-value">${stats.avg_hourly_deliveries.toFixed(1)}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Peak Hour Record</div>
            <div class="stat-value">${stats.max_hourly}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Peak Hours (avg)</div>
            <div class="stat-value">${Object.entries(stats.peak_hours).map(([hour, val]) => `${hour}:00 (${Math.round(val)})`).join(', ')}</div>
        </div>
    `;
}

// Make prediction
async function makePrediction() {
    const zoneId = zoneSelect.value;
    const datetime = dateTimeSelect.value;
    
    if (!zoneId) {
        alert('Please select a delivery zone');
        return;
    }
    
    if (!datetime) {
        alert('Please select a date and time');
        return;
    }
    
    // Convert datetime-local to proper format
    const formattedDateTime = datetime.replace('T', ' ') + ':00';
    
    // Show loading
    loadingOverlay.style.display = 'flex';
    
    try {
        const response = await fetch(`${API_BASE_URL}/predict`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                zone_id: zoneId,
                datetime: formattedDateTime
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayPrediction(data.prediction);
        } else {
            alert('Error: ' + (data.error || 'Failed to get prediction'));
        }
    } catch (error) {
        console.error('Prediction error:', error);
        alert('Error connecting to server. Make sure the backend is running.');
    } finally {
        loadingOverlay.style.display = 'none';
    }
}

// Display prediction results
function displayPrediction(prediction) {
    // Show results panel
    resultsPanel.style.display = 'block';
    
    // Update timestamp
    document.getElementById('predictionTimestamp').innerHTML = 
        `<strong>Predicted for:</strong> ${prediction.datetime}`;
    
    // Update metrics
    document.getElementById('predictedCount').innerHTML = prediction.predicted_deliveries;
    document.getElementById('confidenceInterval').innerHTML = 
        `95% CI: ${prediction.confidence_interval[0]} - ${prediction.confidence_interval[1]}`;
    
    // Update demand level with icon
    const demandLevelElem = document.getElementById('demandLevel');
    const demandIconElem = document.getElementById('demandLevelIcon');
    
    demandLevelElem.innerHTML = prediction.demand_level;
    
    if (prediction.demand_level === 'Peak Risk') {
        demandIconElem.innerHTML = '⚠️ EXTREME - Prepare all resources';
        demandLevelElem.style.color = '#f44336';
    } else if (prediction.demand_level === 'High Demand') {
        demandIconElem.innerHTML = '📈 Increase capacity needed';
        demandLevelElem.style.color = '#FF9800';
    } else {
        demandIconElem.innerHTML = '✅ Normal operations';
        demandLevelElem.style.color = '#4CAF50';
    }
    
    // Update zone name
    const zoneNames = {
        'ZONE_A': 'Zone A - Downtown',
        'ZONE_B': 'Zone B - North District',
        'ZONE_C': 'Zone C - South District',
        'ZONE_D': 'Zone D - East Commercial',
        'ZONE_E': 'Zone E - West Residential'
    };
    document.getElementById('zoneName').innerHTML = zoneNames[prediction.zone_id] || prediction.zone_id;
    
    // Update recommendation
    document.getElementById('recommendation').innerHTML = prediction.recommendation;
    
    // Update vehicle breakdown
    const vehicles = prediction.vehicle_breakdown;
    const vehicleBreakdownDiv = document.getElementById('vehicleBreakdown');
    vehicleBreakdownDiv.innerHTML = `
        <div class="vehicle-item vehicle-motorcycle">
            🏍️ ${vehicles.motorcycles} Motorcycles
        </div>
        <div class="vehicle-item vehicle-van">
            🚐 ${vehicles.vans} Vans
        </div>
        <div class="vehicle-item vehicle-truck">
            🚚 ${vehicles.trucks} Trucks
        </div>
    `;
    
    // Update full message
    document.getElementById('fullMessage').innerHTML = prediction.full_message.replace(/\n/g, '<br>');
    
    // Scroll to results
    resultsPanel.scrollIntoView({ behavior: 'smooth' });
}

// Event listeners
predictBtn.addEventListener('click', makePrediction);

// Initialize
setDefaultDateTime();

// Check API health on load
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        
        if (!data.models_loaded) {
            console.warn('Models not loaded. Please run train_model.py first.');
        }
    } catch (error) {
        console.error('Backend not running. Please start the Flask server.');
    }
}

checkHealth();

// Keyboard shortcut (Enter on zone or datetime)
zoneSelect.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') makePrediction();
});

dateTimeSelect.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') makePrediction();
});