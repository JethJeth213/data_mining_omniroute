// API Configuration
const API_BASE_URL = 'http://127.0.0.1:5000/api';
// Current page tracking
let currentPage = 'dashboard';

console.log("🔍 DEBUG: Intercepting fetch calls");
const originalFetch = window.fetch;
window.fetch = function(url, options) {
    if (url.includes('/users') && options?.method === 'POST') {
        console.log("🔍 FETCH INTERCEPTED:");
        console.log("  URL:", url);
        console.log("  Data being sent:", options.body);
        try {
            const data = JSON.parse(options.body);
            console.log("  Parsed data:", data);
            console.log("  Role being sent:", data.role);
        } catch (e) {
            console.log("  Could not parse JSON");
        }
    }
    return originalFetch.apply(this, arguments);
};

// Pagination state
let currentDispatchPage = 1;
let currentVehiclePage = 1;
let totalDispatchPages = 1;
let totalVehiclePages = 1;
let availableVehicles = [];
let availableDrivers = [];
let selectedVehicles = []; 
let zonesList = [];
let selectedDrivers = []; 
let isLoadingDashboard = false;
let lastDashboardLoad = 0;
const DASHBOARD_LOAD_DELAY = 10000;

// DOM Elements
let contentArea;

// ============ AUTHENTICATION ============
async function checkAuthentication() {
    try {
        const response = await fetch(`${API_BASE_URL}/check-auth`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (!data.authenticated) {
            window.location.href = '/login';
            return false;
        }
        
        if (data.user) {
            const userNameSpan = document.getElementById('userName');
            const userRoleSpan = document.getElementById('userRole');
            if (userNameSpan) userNameSpan.textContent = data.user.full_name || data.user.username;
            if (userRoleSpan) userRoleSpan.textContent = data.user.role;
            
            if (data.user.role === 'driver') {
                const userManagementLink = document.querySelector('[data-page="users"]');
                if (userManagementLink) userManagementLink.style.display = 'none';
            }
        }
        
        return true;
    } catch (error) {
        console.error('Auth check failed:', error);
        window.location.href = '/login';
        return false;
    }
}

async function logout() {
    try {
        await fetch(`${API_BASE_URL}/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        sessionStorage.removeItem('user');
        window.location.href = '/login';
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = '/login';
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    const isAuthenticated = await checkAuthentication();
    if (!isAuthenticated) return;
    
    contentArea = document.getElementById('contentArea');
    setupNavigation();
    loadPage('dashboard');
    
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
});

function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            if (page) {
                loadPage(page);
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
                document.getElementById('pageTitle').innerText = item.querySelector('span').innerText;
            }
        });
    });
}

async function loadPage(page) {
    currentPage = page;
    showLoading();
    
    switch(page) {
        case 'dashboard':
            await loadDashboard();
            break;
        case 'forecast':
            await loadForecastPage();
            break;
        case 'dispatch':
            await loadDispatchPage();
            break;
        case 'vehicles':
            await loadVehiclesPage();
            break;
        case 'users':
            await loadUsersPage();
            break;
    }
    
    hideLoading();
}

// ============ DASHBOARD ============
async function loadDashboard() {
    if (isLoadingDashboard) {
        console.log("⚠️ Dashboard already loading, skipping...");
        return;
    }
    
    const now = Date.now();
    if (now - lastDashboardLoad < DASHBOARD_LOAD_DELAY) {
        console.log(`⏸️ Dashboard loaded ${Math.round((now - lastDashboardLoad)/1000)}s ago, skipping...`);
        return;
    }
    
    isLoadingDashboard = true;
    lastDashboardLoad = now;
    
    try {
        const pageTitle = document.getElementById('pageTitle');
        if (pageTitle) pageTitle.innerText = 'Dashboard';
        
        if (!contentArea) contentArea = document.getElementById('contentArea');
        
        contentArea.innerHTML = `
            <div class="loading-placeholder">
                <div class="loading-spinner-small"></div>
                <p>Loading dashboard...</p>
            </div>
        `;
        
        let statsData = { stats: {} };
        let zonesData = { zones: [] };
        let enrouteData = { assignments: [] };
        let peaksData = { success: false, zones: [], summary: {} };
        
        try {
            const statsResponse = await fetch(`${API_BASE_URL}/dashboard/stats`);
            if (statsResponse.ok) statsData = await statsResponse.json();
        } catch (error) { console.error("Stats fetch error:", error); }
        
        try {
            const zonesResponse = await fetch(`${API_BASE_URL}/zones`);
            if (zonesResponse.ok) zonesData = await zonesResponse.json();
        } catch (error) { console.error("Zones fetch error:", error); }
        
        try {
            const enrouteResponse = await fetch(`${API_BASE_URL}/dispatch/assignments?status=enroute`);
            if (enrouteResponse.ok) enrouteData = await enrouteResponse.json();
        } catch (error) { console.error("Enroute fetch error:", error); }
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 15000);
            const peaksResponse = await fetch(`${API_BASE_URL}/next-peaks`, { signal: controller.signal });
            clearTimeout(timeoutId);
            if (peaksResponse.ok) peaksData = await peaksResponse.json();
        } catch (error) { console.error("Peaks fetch error:", error); }
        
        let activeUsers = 0;
        if (statsData.stats?.users_by_role) {
            activeUsers = statsData.stats.users_by_role.reduce((sum, role) => sum + role.count, 0);
        }
        
        contentArea.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">🚚</div>
                    <div class="stat-value">${statsData.stats?.total_vehicles || 0}</div>
                    <div class="stat-label">Total Vehicles</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">👥</div>
                    <div class="stat-value">${activeUsers}</div>
                    <div class="stat-label">Active Users</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">📦</div>
                    <div class="stat-value">${statsData.stats?.today_assignments || 0}</div>
                    <div class="stat-label">Today's Dispatches</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">🚛</div>
                    <div class="stat-value">${statsData.stats?.active_drivers_today || 0}</div>
                    <div class="stat-label">Active Drivers</div>
                </div>
            </div>
            
            ${renderPeakDetectionSection(peaksData)}
            
            <div class="data-table">
                <div class="table-header">
                    <h3>🚚 En Route Dispatches</h3>
                    <span class="badge-count">${enrouteData.assignments?.length || 0} active</span>
                </div>
                <div class="scrollable-table-container" style="max-height: 300px; overflow-y: auto;">
                    ${renderEnrouteTable(enrouteData.assignments || [])}
                </div>
            </div>
            
            <div class="data-table" style="margin-top: 30px;">
                <div class="table-header">
                    <h3>📍 Delivery Zones</h3>
                </div>
                <div style="overflow-x: auto;">
                    ${renderZonesTable(zonesData.zones || [])}
                </div>
            </div>
        `;
        
        setTimeout(() => {
            loadAcknowledgedRisksAndFilter();
            setupRiskAcknowledgmentButtons();
        }, 100);
        
    } catch (error) {
        console.error('Dashboard error:', error);
        if (contentArea) {
            contentArea.innerHTML = `
                <div class="error" style="padding: 40px; text-align: center;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 48px; color: #dc2626; margin-bottom: 15px;"></i>
                    <h3>Failed to load dashboard</h3>
                    <p>Make sure the backend server is running on port 5000</p>
                    <button onclick="loadDashboard()" class="btn-primary" style="margin-top: 15px;">Retry</button>
                </div>
            `;
        }
    } finally {
        isLoadingDashboard = false;
    }
}

function renderPeakDetectionSection(peaksData) {
    if (!peaksData.success || !peaksData.zones || peaksData.zones.length === 0) {
        return `
            <div class="data-table" style="margin-bottom: 20px; background: linear-gradient(135deg, #f0fdf4, #dcfce7);">
                <div class="table-header">
                    <h3>🔍 Peak Detection (Next 7 Days)</h3>
                </div>
                <div style="padding: 30px; text-align: center;">
                    <i class="fas fa-check-circle" style="font-size: 36px; color: #16a34a; margin-bottom: 10px; display: block;"></i>
                    <p style="color: #166534;">No peak demand predicted in the next 7 days. Normal operations expected.</p>
                </div>
            </div>
        `;
    }
    
    const summary = peaksData.summary;
    
    return `
        <div class="data-table" style="margin-bottom: 20px; border-left: 4px solid ${summary.total_peak_risk > 0 ? '#dc2626' : '#ea580c'};">
            <div class="table-header">
                <h3>⚠️ Peak Detection & Alerts (Next 7 Days)</h3>
                <div style="display: flex; gap: 10px;">
                    ${summary.total_peak_risk > 0 ? `<span class="badge-count" style="background: #dc2626; color: white;">${summary.total_peak_risk} Peak Risk</span>` : ''}
                    ${summary.total_high_demand > 0 ? `<span class="badge-count" style="background: #ea580c; color: white;">${summary.total_high_demand} High Demand</span>` : ''}
                </div>
            </div>
            <div style="padding: 0 20px 20px 20px;" id="peaksListContainer">
                ${peaksData.zones.map(zone => {
                    const peak = zone.nearest_peak;
                    const isPeakRisk = peak.demand_level === 'Peak Risk';
                    const cardColor = isPeakRisk ? '#fee2e2' : '#fff3e0';
                    const borderColor = isPeakRisk ? '#dc2626' : '#ea580c';
                    const icon = isPeakRisk ? '⚠️' : '📈';
                    const riskKey = `${zone.zone_id}|${peak.datetime}`;
                    
                    let urgencyIcon = '';
                    if (peak.hours_from_now < 2) {
                        urgencyIcon = '<span style="background: #dc2626; color: white; padding: 2px 8px; border-radius: 20px; font-size: 11px; margin-left: 8px;">URGENT</span>';
                    } else if (peak.hours_from_now < 6) {
                        urgencyIcon = '<span style="background: #f97316; color: white; padding: 2px 8px; border-radius: 20px; font-size: 11px; margin-left: 8px;">SOON</span>';
                    }
                    
                    return `
                        <div class="peak-card" data-risk-key="${riskKey}" data-zone="${zone.zone_id}" data-datetime="${peak.datetime}" style="
                            background: ${cardColor};
                            border-radius: 12px;
                            padding: 16px;
                            margin-bottom: 12px;
                            border-left: 4px solid ${borderColor};
                        ">
                            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <span style="font-size: 24px;">${icon}</span>
                                    <strong style="font-size: 16px;">${zone.zone_id} - ${zone.zone_name || ''}</strong>
                                    <span class="status-badge" style="background: ${borderColor}20; color: ${borderColor}; font-weight: bold;">
                                        ${peak.demand_level}
                                    </span>
                                    ${urgencyIcon}
                                </div>
                                <div style="display: flex; gap: 8px;">
                                    <button class="btn-primary btn-sm" onclick="prepareDispatchFromPeak('${zone.zone_id}', '${peak.datetime}')">
                                        Prepare Dispatch →
                                    </button>
                                    <button class="btn-secondary btn-sm acknowledge-risk-btn" data-zone="${zone.zone_id}" data-datetime="${peak.datetime}">
                                        ✓ Acknowledge Risk
                                    </button>
                                </div>
                            </div>
                            
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; font-size: 14px;">
                                <div>
                                    <strong>⏰ ${peak.date_desc}</strong><br>
                                    ${peak.datetime_display}<br>
                                    <span style="color: #666;">(in ${peak.time_desc})</span>
                                </div>
                                <div>
                                    <strong>📦 Predicted Deliveries</strong><br>
                                    <span style="font-size: 18px; font-weight: bold;">${peak.predicted_deliveries}</span>
                                </div>
                                <div>
                                    <strong>🚚 Vehicle Recommendation</strong><br>
                                    🏍️ ${peak.vehicle_breakdown.motorcycles} MC 
                                    ${peak.vehicle_breakdown.vans > 0 ? `| 🚐 ${peak.vehicle_breakdown.vans} Vans` : ''}
                                    ${peak.vehicle_breakdown.trucks > 0 ? `| 🚚 ${peak.vehicle_breakdown.trucks} Truck` : ''}
                                </div>
                            </div>
                            
                            ${zone.all_peaks_this_week && zone.all_peaks_this_week.length > 1 ? `
                            <div style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed rgba(0,0,0,0.1);">
                                <details>
                                    <summary style="cursor: pointer; font-size: 12px; color: #666;">📋 +${zone.all_peaks_this_week.length - 1} more peak periods this week</summary>
                                    <div style="margin-top: 8px; font-size: 12px; color: #555;">
                                        ${zone.all_peaks_this_week.slice(1).map(p => `
                                            <div style="padding: 5px 0;">• ${new Date(p.datetime).toLocaleString()} - ${p.predicted_deliveries} deliveries (${p.demand_level})</div>
                                        `).join('')}
                                    </div>
                                </details>
                            </div>
                            ` : ''}
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

async function loadAcknowledgedRisksAndFilter() {
    try {
        const response = await fetch(`${API_BASE_URL}/get-acknowledged-risks`, {
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success && data.acknowledged_risks) {
            document.querySelectorAll('.peak-card').forEach(card => {
                const riskKey = card.dataset.riskKey;
                if (riskKey && data.acknowledged_risks.includes(riskKey)) {
                    card.style.display = 'none';
                }
            });
        }
    } catch (error) {
        console.error('Error loading acknowledged risks:', error);
    }
}

window.acknowledgeRisk = async function(zoneId, datetime, cardElement) {
    try {
        const response = await fetch(`${API_BASE_URL}/acknowledge-risk`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ zone_id: zoneId, datetime: datetime })
        });
        
        const data = await response.json();
        if (data.success) {
            if (cardElement) {
                cardElement.style.display = 'none';
            }
            alert('Risk acknowledged and removed from dashboard');
        } else {
            alert('Error: ' + (data.error || 'Could not acknowledge risk'));
        }
    } catch (error) {
        console.error('Error acknowledging risk:', error);
        alert('Error acknowledging risk');
    }
};

function setupRiskAcknowledgmentButtons() {
    document.querySelectorAll('.acknowledge-risk-btn').forEach(btn => {
        btn.removeEventListener('click', handleAcknowledgeClick);
        btn.addEventListener('click', handleAcknowledgeClick);
    });
}

function handleAcknowledgeClick(event) {
    event.stopPropagation();
    const btn = event.currentTarget;
    const zoneId = btn.dataset.zone;
    const datetime = btn.dataset.datetime;
    const card = btn.closest('.peak-card');
    
    if (confirm('Acknowledge this risk? It will be removed from your dashboard.')) {
        window.acknowledgeRisk(zoneId, datetime, card);
    }
}

window.prepareDispatchFromPeak = function(zoneId, datetime) {
    sessionStorage.setItem('prefill_zone', zoneId);
    sessionStorage.setItem('prefill_datetime', datetime);
    const forecastLink = document.querySelector('[data-page="forecast"]');
    if (forecastLink) forecastLink.click();
};

function renderZonesTable(zones) {
    if (!zones || zones.length === 0) {
        return '<div style="padding: 40px; text-align: center;">No zones configured</div>';
    }
    
    return `
        <table style="width:100%; border-collapse: collapse;">
            <thead>
                <tr><th>Zone</th><th>Name</th><th>Base Vehicles</th><th>Normal Threshold</th><th>High Threshold</th></tr>
            </thead>
            <tbody>
                ${zones.map(zone => `
                    <tr>
                        <td><strong>${zone.zone_id}</strong></td>
                        <td>${zone.zone_name}</small></td>
                        <td>${zone.base_vehicles}</small></td>
                        <td>${zone.threshold_normal}</small></td>
                        <td>${zone.threshold_high}</small></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function renderEnrouteTable(assignments) {
    if (!assignments || assignments.length === 0) {
        return `<div style="padding: 40px; text-align: center; color: #666;">No en route dispatches at this time.</div>`;
    }
    
    return `
        <table style="width:100%; border-collapse: collapse;">
            <thead>
                <tr style="position: sticky; top: 0; background: #f8f9fa;">
                    <th>Zone</th>
                    <th>Date/Time</th>
                    <th>Deliveries</th>
                    <th>Assigned Vehicles</th>
                    <th>Assigned Drivers</th>
                </tr>
            </thead>
            <tbody>
                ${assignments.map(ass => `
                    <tr>
                        <td><strong>${ass.zone_id}</strong><br><small>${ass.zone_name || ''}</small></td>
                        <td><small>${new Date(ass.dispatch_datetime).toLocaleString()}</small></td>
                        <td><strong>${ass.predicted_deliveries || '-'}</strong></td>
                        <td><small>${ass.assigned_vehicles || '-'}</small></td>
                        <td><small>${ass.assigned_drivers || '-'}</small></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// ============ DEMAND FORECAST PAGE ============
async function loadForecastPage() {
    const zonesResponse = await fetch(`${API_BASE_URL}/zones`);
    const zonesData = await zonesResponse.json();
    
    const now = new Date();
    now.setHours(now.getHours() + 1);
    now.setMinutes(0);
    let defaultDateTime = now.toISOString().slice(0, 16);
    
    const prefillZone = sessionStorage.getItem('prefill_zone');
    const prefillDatetime = sessionStorage.getItem('prefill_datetime');
    
    if (prefillDatetime) {
        defaultDateTime = prefillDatetime.replace(' ', 'T').slice(0, 16);
    }
    
    contentArea.innerHTML = `
        <div style="display: flex; gap: 30px; flex-wrap: wrap;">
            <div class="control-panel" style="flex: 1; min-width: 320px;">
                <h3>🎯 Demand Prediction</h3>
                <p>Select zone and time for demand forecast</p>
                
                <div class="form-group">
                    <label>📍 Delivery Zone</label>
                    <select id="zoneSelect" class="form-control">
                        <option value="">Select a zone...</option>
                        ${(zonesData.zones || []).map(zone => `
                            <option value="${zone.zone_id}" ${prefillZone === zone.zone_id ? 'selected' : ''}>
                                ${zone.zone_id} - ${zone.zone_name}
                            </option>
                        `).join('')}
                    </select>
                </div>
                
                <div class="form-group">
                    <label>⏰ Date & Time</label>
                    <input type="datetime-local" id="dateTimeSelect" class="form-control" value="${defaultDateTime}">
                </div>
                
                <div class="quick-select">
                    <label>Quick Select:</label>
                    <div class="quick-buttons">
                        <button class="quick-btn" data-hours="1">+1 Hour</button>
                        <button class="quick-btn" data-hours="3">+3 Hours</button>
                        <button class="quick-btn" data-hours="6">+6 Hours</button>
                        <button class="quick-btn" data-hours="12">+12 Hours</button>
                        <button class="quick-btn" data-hours="24">+24 Hours</button>
                    </div>
                </div>
                
                <button id="predictBtn" class="predict-btn">🔮 Predict Demand</button>
            </div>
            
            <div id="resultsPanel" class="results-panel" style="flex: 1; min-width: 320px; display: none;">
                <h3>📈 Prediction Results</h3>
                <div id="predictionResults"></div>
            </div>
        </div>
    `;
    
    sessionStorage.removeItem('prefill_zone');
    sessionStorage.removeItem('prefill_datetime');
    setupForecastPage();
}

function setupForecastPage() {
    document.querySelectorAll('.quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const hours = parseInt(btn.dataset.hours);
            const datetimeInput = document.getElementById('dateTimeSelect');
            let date = new Date(datetimeInput.value);
            if (isNaN(date.getTime())) date = new Date();
            date.setHours(date.getHours() + hours);
            datetimeInput.value = date.toISOString().slice(0, 16);
        });
    });
    
    document.getElementById('predictBtn').addEventListener('click', async () => {
        const zoneId = document.getElementById('zoneSelect').value;
        const datetime = document.getElementById('dateTimeSelect').value;
        
        if (!zoneId) {
            alert('Please select a zone');
            return;
        }
        
        showLoading();
        
        try {
            const response = await fetch(`${API_BASE_URL}/predict`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    zone_id: zoneId,
                    datetime: datetime.replace('T', ' ') + ':00'
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                displayPrediction(data.prediction);
            } else {
                alert('Error: ' + (data.error || 'Prediction failed'));
            }
        } catch (error) {
            alert('Error connecting to server');
        } finally {
            hideLoading();
        }
    });
}

function displayPrediction(prediction) {
    const resultsPanel = document.getElementById('resultsPanel');
    const resultsDiv = document.getElementById('predictionResults');
    
    const demandColor = prediction.demand_level === 'Peak Risk' ? '#dc2626' : 
                       prediction.demand_level === 'High Demand' ? '#ea580c' : '#16a34a';
    
    const adjustmentNote = prediction.adjusted ? 
        `<div style="background: #fff3e0; padding: 10px; border-radius: 8px; margin-bottom: 15px;">
            <small>⚠️ This is an ADJUSTED forecast (+${prediction.adjustment_applied} deliveries). Original prediction was ${prediction.original_prediction} deliveries.</small>
         </div>` : '';
    
    resultsDiv.innerHTML = `
        ${adjustmentNote}
        <div class="metrics-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
            <div class="metric-card" style="padding: 20px; text-align: center; background: linear-gradient(135deg, #f5f7fa, #e9ecef); border-radius: 15px;">
                <div class="metric-label">Forecasted Deliveries</div>
                <div class="metric-value" style="font-size: 32px; font-weight: 800;">${prediction.predicted_deliveries}</div>
                <div class="metric-sub">95% CI: ${prediction.confidence_interval[0]} - ${prediction.confidence_interval[1]}</div>
            </div>
            <div class="metric-card" style="padding: 20px; text-align: center; background: linear-gradient(135deg, #f5f7fa, #e9ecef); border-radius: 15px;">
                <div class="metric-label">Demand Level</div>
                <div class="metric-value" style="font-size: 32px; font-weight: 800; color: ${demandColor}">${prediction.demand_level}</div>
                <div class="metric-sub">${prediction.demand_level.includes('Peak') ? '⚠️ Prepare all resources' : 
                                         prediction.demand_level.includes('High') ? '📈 Increase capacity' : '✅ Normal operations'}</div>
            </div>
            <div class="metric-card" style="padding: 20px; text-align: center; background: linear-gradient(135deg, #f5f7fa, #e9ecef); border-radius: 15px;">
                <div class="metric-label">Zone</div>
                <div class="metric-value" style="font-size: 32px; font-weight: 800;">${prediction.zone_id}</div>
                <div class="metric-sub">${new Date(prediction.datetime).toLocaleString()}</div>
            </div>
        </div>
        
        <div class="recommendation-card" style="background: #f0f4ff; border-radius: 15px; padding: 20px; border-left: 4px solid #667eea;">
            <div class="rec-header">🚚 Dispatch Recommendation</div>
            <div class="rec-content">${prediction.recommendation}</div>
            <div class="vehicle-breakdown" style="display: flex; gap: 15px; margin-top: 15px;">
                <div class="vehicle-item" style="background: white; padding: 8px 15px; border-radius: 10px;">🏍️ ${prediction.vehicle_breakdown.motorcycles} Motorcycles</div>
                <div class="vehicle-item" style="background: white; padding: 8px 15px; border-radius: 10px;">🚐 ${prediction.vehicle_breakdown.vans} Vans</div>
                <div class="vehicle-item" style="background: white; padding: 8px 15px; border-radius: 10px;">🚚 ${prediction.vehicle_breakdown.trucks} Trucks</div>
            </div>
        </div>
        
        <div class="action-buttons" style="display: flex; gap: 10px; margin-top: 20px;">
            <button onclick="createDispatchFromPrediction()" class="btn-primary">Create Dispatch Assignment</button>
            <button onclick="getAdjustedForecast()" class="btn-warning" style="background: #ea580c; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer;">
                +2 Risk (Adjust Forecast ↑)
            </button>
        </div>
    `;
    
    resultsPanel.style.display = 'block';
    window.lastPrediction = prediction;
}

window.getAdjustedForecast = async function() {
    if (!window.lastPrediction) {
        alert('Please make a prediction first');
        return;
    }
    
    const pred = window.lastPrediction;
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/predict-adjusted`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                zone_id: pred.zone_id,
                datetime: pred.datetime,
                adjustment: 2
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayPrediction(data.prediction);
            alert(`⚠️ Risk-adjusted forecast: +2 deliveries added.\nNew total: ${data.prediction.predicted_deliveries} deliveries`);
        } else {
            alert('Error: ' + (data.error || 'Could not get adjusted forecast'));
        }
    } catch (error) {
        console.error('Error getting adjusted forecast:', error);
        alert('Error connecting to server');
    } finally {
        hideLoading();
    }
};

window.createDispatchFromPrediction = async function() {
    if (!window.lastPrediction) return;
    const pred = window.lastPrediction;
    
    showLoading();
    try {
        const vehiclesResponse = await fetch(`${API_BASE_URL}/vehicles?status=available`);
        const vehiclesData = await vehiclesResponse.json();
        
        const neededMotorcycles = pred.vehicle_breakdown.motorcycles;
        const neededVans = pred.vehicle_breakdown.vans;
        const neededTrucks = pred.vehicle_breakdown.trucks;
        
        const availableMotorcycles = (vehiclesData.vehicles || []).filter(v => v.vehicle_type === 'motorcycle' && v.status === 'available').length;
        const availableVans = (vehiclesData.vehicles || []).filter(v => v.vehicle_type === 'van' && v.status === 'available').length;
        const availableTrucks = (vehiclesData.vehicles || []).filter(v => v.vehicle_type === 'truck' && v.status === 'available').length;
        
        if (availableMotorcycles < neededMotorcycles || availableVans < neededVans || availableTrucks < neededTrucks) {
            alert(`⚠️ Insufficient available vehicles!\nNeed: ${neededMotorcycles} MC, ${neededVans} Vans, ${neededTrucks} Trucks\nAvailable: ${availableMotorcycles} MC, ${availableVans} Vans, ${availableTrucks} Trucks\n\nPlease assign vehicles manually in Fleet Dispatch.`);
            loadPage('dispatch');
            hideLoading();
            return;
        }
        
        const response = await fetch(`${API_BASE_URL}/dispatch/assignments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                zone_id: pred.zone_id,
                dispatch_datetime: pred.datetime,
                predicted_deliveries: pred.predicted_deliveries,
                demand_level: pred.demand_level,
                assigned_vehicles: `${pred.vehicle_breakdown.motorcycles} MC, ${pred.vehicle_breakdown.vans} Vans, ${pred.vehicle_breakdown.trucks} Trucks`,
                dispatch_status: 'planned',
                notes: `Auto-created from demand prediction${pred.adjusted ? ' (ADJUSTED +2 RISK FORECAST)' : ''}`,
                created_by: 1
            })
        });
        
        const data = await response.json();
        if (data.success) {
            alert(`Dispatch assignment created successfully!\nVehicles will be automatically marked as ASSIGNED when dispatch starts.\n\nNote: Go to Fleet Dispatch > Start to mark vehicles as assigned.`);
            loadPage('dispatch');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creating assignment');
    } finally {
        hideLoading();
    }
};

// ============ FLEET DISPATCH PAGE ============
async function loadDispatchPage() {
    const zonesResponse = await fetch(`${API_BASE_URL}/zones`);
    const zonesData = await zonesResponse.json();
    zonesList = zonesData.zones || [];
    
    await refreshDispatchTable();
    
    contentArea.innerHTML = `
        <div class="filter-bar">
            <div class="filter-group">
                <label>Zone</label>
                <select id="dispatchZoneFilter" class="form-control" style="min-width: 180px;">
                    <option value="">All Zones</option>
                    ${(zonesList).map(zone => `
                        <option value="${zone.zone_id}">${zone.zone_id} - ${zone.zone_name}</option>
                    `).join('')}
                </select>
            </div>
            <div class="filter-group">
                <label>Status</label>
                <select id="dispatchStatusFilter" class="form-control">
                    <option value="">All Status</option>
                    <option value="planned">Planned</option>
                    <option value="assigned">Assigned</option>
                    <option value="enroute">En Route</option>
                    <option value="completed">Completed</option>
                    <option value="cancelled">Cancelled</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Date</label>
                <input type="date" id="dispatchDateFilter" class="form-control">
            </div>
            <div class="filter-group">
                <button id="applyDispatchFilter" class="btn-secondary">Apply Filter</button>
                <button id="clearDispatchFilter" class="btn-secondary">Clear</button>
            </div>
            <div style="flex:1"></div>
            <button id="newDispatchBtn" class="btn-primary">+ New Dispatch</button>
        </div>
        
        <div class="data-table">
            <div class="table-header">
                <h3>Dispatch Assignments</h3>
            </div>
            <div id="dispatchTableContainer"></div>
        </div>
        <div id="dispatchPagination" style="display: flex; justify-content: center; gap: 10px; margin-top: 20px;"></div>
    `;
    
    document.getElementById('applyDispatchFilter').addEventListener('click', () => { currentDispatchPage = 1; refreshDispatchTable(); });
    document.getElementById('clearDispatchFilter').addEventListener('click', () => {
        document.getElementById('dispatchZoneFilter').value = '';
        document.getElementById('dispatchStatusFilter').value = '';
        document.getElementById('dispatchDateFilter').value = '';
        currentDispatchPage = 1;
        refreshDispatchTable();
    });
    document.getElementById('newDispatchBtn').addEventListener('click', showNewDispatchModal);
}

async function refreshDispatchTable() {
    const zone = document.getElementById('dispatchZoneFilter')?.value || '';
    const status = document.getElementById('dispatchStatusFilter')?.value || '';
    const date = document.getElementById('dispatchDateFilter')?.value || '';
    
    let url = `${API_BASE_URL}/dispatch/assignments`;
    const params = new URLSearchParams();
    if (zone) params.append('zone_id', zone);
    if (status) params.append('status', status);
    if (date) params.append('date', date);
    params.append('page', currentDispatchPage);
    params.append('per_page', 15);
    if (params.toString()) url += '?' + params.toString();
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        const container = document.getElementById('dispatchTableContainer');
        if (!container) return;
        
        totalDispatchPages = data.pagination?.total_pages || 1;
        
        container.innerHTML = `
            <table style="width:100%; border-collapse: collapse;">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Zone</th>
                        <th>Date/Time</th>
                        <th>Deliveries</th>
                        <th>Actual</th>
                        <th>Demand Level</th>
                        <th>Assigned Vehicles</th>
                        <th>Assigned Drivers</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${(data.assignments || []).map(ass => {
                        let actionButtons = '';
                        
                        if (ass.dispatch_status === 'planned') {
                            actionButtons = `
                                <button class="btn-primary btn-sm" onclick="quickStartDispatch(${ass.assignment_id})">▶ Start</button>
                                <button class="btn-secondary btn-sm" onclick="editDispatch(${ass.assignment_id})">Edit</button>
                                <button class="btn-danger btn-sm" onclick="deleteDispatch(${ass.assignment_id})">Delete</button>
                            `;
                        } else if (ass.dispatch_status === 'assigned') {
                            actionButtons = `
                                <button class="btn-primary btn-sm" onclick="markAsEnroute(${ass.assignment_id})">🚚 Start Route</button>
                                <button class="btn-secondary btn-sm" onclick="editDispatch(${ass.assignment_id})">Edit</button>
                                <button class="btn-danger btn-sm" onclick="deleteDispatch(${ass.assignment_id})">Delete</button>
                            `;
                        } else if (ass.dispatch_status === 'enroute') {
                            actionButtons = `
                                <button class="btn-success btn-sm" onclick="completeDispatchWithDelivery(${ass.assignment_id}, '${ass.zone_id}', '${ass.dispatch_datetime}', ${ass.predicted_deliveries || 0}, '${(ass.assigned_vehicles || '').replace(/'/g, "\\'")}', '${(ass.assigned_drivers || '').replace(/'/g, "\\'")}')" style="background: #16a34a;">✅ Complete</button>
                                <button class="btn-secondary btn-sm" onclick="editDispatch(${ass.assignment_id})">Edit</button>
                                <button class="btn-danger btn-sm" onclick="deleteDispatch(${ass.assignment_id})">Delete</button>
                            `;
                        } else {
                            actionButtons = `
                                <button class="btn-secondary btn-sm" onclick="editDispatch(${ass.assignment_id})">Edit</button>
                                <button class="btn-danger btn-sm" onclick="deleteDispatch(${ass.assignment_id})">Delete</button>
                            `;
                        }
                        
                        return `
                            <tr>
                                <td>${ass.assignment_id}</td>
                                <td><strong>${ass.zone_id}</strong><br><small>${ass.zone_name || ''}</small></td>
                                <td><small>${new Date(ass.dispatch_datetime).toLocaleString()}</small></td>
                                <td><strong>${ass.predicted_deliveries || '-'}</strong></td>
                                <td>${ass.actual_deliveries || '-'}</td>
                                <td><span class="status-badge" style="background:${getDemandColor(ass.demand_level)}20; color:${getDemandColor(ass.demand_level)}">${ass.demand_level || '-'}</span></td>
                                <td><small>${ass.assigned_vehicles || '-'}</small></td>
                                <td><small>${ass.assigned_drivers || '-'}</small></td>
                                <td><span class="status-badge status-${ass.dispatch_status}">${ass.dispatch_status}</span></td>
                                <td>${actionButtons}</td>
                            </tr>
                        `;
                    }).join('')}
                    ${(data.assignments || []).length === 0 ? '<tr><td colspan="10">No dispatch assignments found</td></tr>' : ''}
                </tbody>
            </table>
        `;
        
        const paginationDiv = document.getElementById('dispatchPagination');
        if (paginationDiv && totalDispatchPages > 1) {
            paginationDiv.innerHTML = `
                <button class="btn-secondary" onclick="changeDispatchPage(${currentDispatchPage - 1})" ${currentDispatchPage === 1 ? 'disabled' : ''}>Previous</button>
                <span style="padding: 8px 16px;">Page ${currentDispatchPage} of ${totalDispatchPages}</span>
                <button class="btn-secondary" onclick="changeDispatchPage(${currentDispatchPage + 1})" ${currentDispatchPage === totalDispatchPages ? 'disabled' : ''}>Next</button>
            `;
        }
    } catch (error) {
        console.error('Error loading dispatch:', error);
        const container = document.getElementById('dispatchTableContainer');
        if (container) container.innerHTML = '<div class="error">Error loading data</div>';
    }
}

function changeDispatchPage(page) {
    if (page >= 1 && page <= totalDispatchPages) {
        currentDispatchPage = page;
        refreshDispatchTable();
    }
}

function getDemandColor(demandLevel) {
    if (demandLevel === 'Peak Risk') return '#dc2626';
    if (demandLevel === 'High Demand') return '#ea580c';
    return '#16a34a';
}

// ============ DISPATCH ACTIONS ============
window.quickStartDispatch = async function(id) {
    if (!confirm('Start this dispatch? This will assign vehicles and mark as enroute.')) {
        return;
    }
    
    showLoading();
    try {
        const checkResponse = await fetch(`${API_BASE_URL}/dispatch/assignments`);
        const checkData = await checkResponse.json();
        const dispatch = checkData.assignments.find(a => a.assignment_id === id);
        
        if (!dispatch) {
            alert('Dispatch not found');
            hideLoading();
            return;
        }
        
        if (dispatch.dispatch_status === 'planned') {
            let assignResponse = await fetch(`${API_BASE_URL}/dispatch/assignments/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ dispatch_status: 'assigned' })
            });
            
            let assignData = await assignResponse.json();
            if (!assignData.success) {
                alert('Error assigning: ' + assignData.error);
                hideLoading();
                return;
            }
        }
        
        const enrouteResponse = await fetch(`${API_BASE_URL}/dispatch/assignments/${id}/enroute`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        });
        
        const enrouteData = await enrouteResponse.json();
        
        if (enrouteData.success) {
            alert('✅ Dispatch started! Now ENROUTE.');
            refreshDispatchTable();
            if (currentPage === 'dashboard') loadDashboard();
        } else {
            alert('Error: ' + enrouteData.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error starting dispatch: ' + error.message);
    } finally {
        hideLoading();
    }
};

window.markAsEnroute = async function(id) {
    if (!confirm('Start the route? This will mark the dispatch as ENROUTE.')) {
        return;
    }
    
    showLoading();
    try {
        const response = await fetch(`${API_BASE_URL}/dispatch/assignments/${id}/enroute`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.success) {
            alert('✅ Dispatch is now ENROUTE!');
            refreshDispatchTable();
            if (currentPage === 'dashboard') loadDashboard();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error starting dispatch');
    } finally {
        hideLoading();
    }
};

window.completeDispatchWithDelivery = async function(id, zoneId, datetime, predictedDeliveries, assignedVehicles, assignedDrivers) {
    showModal('Complete Dispatch & Record Delivery', `
        <div style="background: #e8f5e9; padding: 10px; border-radius: 8px; margin-bottom: 15px;">
            <small style="color: #2e7d32;">⚠️ This data will be used to train the ML model for future predictions</small>
        </div>
        
        <div style="background: #fff3e0; padding: 10px; border-radius: 8px; margin-bottom: 15px;">
            <small style="color: #e65100;">🚚 Upon completion, the following will be set to AVAILABLE:</small>
            <div style="margin-top: 8px;">
                <small><strong>Vehicles:</strong> ${assignedVehicles || 'None'}</small><br>
                <small><strong>Drivers:</strong> ${assignedDrivers || 'None'}</small>
            </div>
        </div>
        
        <div class="form-group">
            <label>Actual Number of Deliveries *</label>
            <input type="number" id="actualDeliveries" class="form-control" 
                   placeholder="Enter actual delivery count" value="${predictedDeliveries}" required>
            <small class="form-text text-muted">This will be added to historical data for ML training</small>
        </div>
        
        <div class="form-group">
            <label>Vehicle Type Used</label>
            <select id="vehicleType" class="form-control">
                <option value="motorcycle">🏍️ Motorcycle</option>
                <option value="van">🚐 Van</option>
                <option value="truck">🚚 Truck</option>
                <option value="ebike">🛵 E-Bike</option>
            </select>
        </div>
        
        <div class="form-group">
            <label>Distance Traveled (km)</label>
            <input type="number" id="distanceKm" class="form-control" step="0.1" 
                   placeholder="Auto-calculated if left empty">
        </div>
        
        <div class="form-actions" style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
            <button onclick="closeModal()" class="btn-secondary" style="padding: 10px 20px;">Cancel</button>
            <button onclick="saveCompletedDelivery(${id})" class="btn-primary" style="padding: 10px 20px; background: #16a34a;">Complete & Free Resources</button>
        </div>
    `);
};

window.saveCompletedDelivery = async function(assignmentId) {
    console.log("🔵 saveCompletedDelivery called for assignment:", assignmentId);
    
    const actualDeliveriesInput = document.getElementById('actualDeliveries');
    const vehicleTypeSelect = document.getElementById('vehicleType');
    const distanceKmInput = document.getElementById('distanceKm');
    
    if (!actualDeliveriesInput) {
        console.error("Could not find actualDeliveries input field");
        alert('Error: Form fields not found. Please try again.');
        return;
    }
    
    const actualDeliveries = actualDeliveriesInput.value;
    const vehicleType = vehicleTypeSelect ? vehicleTypeSelect.value : 'motorcycle';
    const distanceKm = distanceKmInput ? distanceKmInput.value : null;
    
    if (!actualDeliveries || actualDeliveries < 0) {
        alert('Please enter valid number of deliveries');
        return;
    }
    
    console.log("📤 Sending completion data:", {
        assignment_id: assignmentId,
        actual_deliveries: parseInt(actualDeliveries),
        vehicle_type: vehicleType,
        distance_km: distanceKm ? parseFloat(distanceKm) : null
    });
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/dispatch/assignments/${assignmentId}/complete-with-delivery`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                actual_deliveries: parseInt(actualDeliveries),
                vehicle_type: vehicleType,
                distance_km: distanceKm ? parseFloat(distanceKm) : null
            })
        });
        
        const data = await response.json();
        console.log("📥 Server response:", data);
        
        if (data.success) {
            alert(`✅ Dispatch completed successfully!\n\nDelivery record #${data.delivery_record_id} created.\nVehicles and drivers have been freed up.`);
            closeModal();
            refreshDispatchTable();
            if (currentPage === 'dashboard') {
                loadDashboard();
            }
        } else {
            alert('Error: ' + (data.error || 'Failed to complete dispatch'));
        }
    } catch (error) {
        console.error('❌ Error completing dispatch:', error);
        alert('Error completing dispatch: ' + error.message);
    } finally {
        hideLoading();
    }
};

// ============ VEHICLE MANAGEMENT PAGE ============
async function loadVehiclesPage() {
    const zonesResponse = await fetch(`${API_BASE_URL}/zones`);
    const zonesData = await zonesResponse.json();
    
    contentArea.innerHTML = `
        <div class="filter-bar">
            <div class="filter-group">
                <label>🔍 Search (Code/Plate)</label>
                <input type="text" id="vehicleSearch" placeholder="Search by code or plate..." style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 8px; width: 200px;">
            </div>
            <div class="filter-group">
                <label>Zone</label>
                <select id="vehicleZoneFilter">
                    <option value="">All Zones</option>
                    ${(zonesData.zones || []).map(zone => `<option value="${zone.zone_id}">${zone.zone_id}</option>`).join('')}
                </select>
            </div>
            <div class="filter-group">
                <label>Status</label>
                <select id="vehicleStatusFilter">
                    <option value="">All Status</option>
                    <option value="available">Available</option>
                    <option value="assigned">Assigned</option>
                    <option value="maintenance">Maintenance</option>
                    <option value="repair">Repair</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Type</label>
                <select id="vehicleTypeFilter">
                    <option value="">All Types</option>
                    <option value="motorcycle">Motorcycle</option>
                    <option value="van">Van</option>
                    <option value="truck">Truck</option>
                    <option value="ebike">E-Bike</option>
                </select>
            </div>
            <div class="filter-group">
                <button id="applyVehicleFilter" class="btn-secondary">Apply Filter</button>
                <button id="clearVehicleFilter" class="btn-secondary">Clear</button>
            </div>
            <div style="flex:1"></div>
            <button id="newVehicleBtn" class="btn-primary">+ Add Vehicle</button>
        </div>
        
        <div class="data-table">
            <div class="table-header">
                <h3>Vehicle Fleet</h3>
            </div>
            <div id="vehiclesTableContainer">
                <div class="loading-placeholder"><div class="loading-spinner-small"></div><p>Loading...</p></div>
            </div>
        </div>
        <div id="vehiclePagination" style="display: flex; justify-content: center; gap: 10px; margin-top: 20px;"></div>
    `;
    
    document.getElementById('applyVehicleFilter').addEventListener('click', () => { currentVehiclePage = 1; refreshVehiclesTable(); });
    document.getElementById('clearVehicleFilter').addEventListener('click', () => {
        document.getElementById('vehicleSearch').value = '';
        document.getElementById('vehicleZoneFilter').value = '';
        document.getElementById('vehicleStatusFilter').value = '';
        document.getElementById('vehicleTypeFilter').value = '';
        currentVehiclePage = 1;
        refreshVehiclesTable();
    });
    document.getElementById('newVehicleBtn').addEventListener('click', showNewVehicleModal);
    
    await refreshVehiclesTable();
}

async function refreshVehiclesTable() {
    const search = document.getElementById('vehicleSearch')?.value || '';
    const zone = document.getElementById('vehicleZoneFilter')?.value || '';
    const status = document.getElementById('vehicleStatusFilter')?.value || '';
    const type = document.getElementById('vehicleTypeFilter')?.value || '';
    
    let url = `${API_BASE_URL}/vehicles`;
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (zone) params.append('zone_id', zone);
    if (status) params.append('status', status);
    if (type) params.append('vehicle_type', type);
    if (params.toString()) url += '?' + params.toString();
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        const container = document.getElementById('vehiclesTableContainer');
        if (!container) return;
        
        container.innerHTML = `
            <table style="width:100%; border-collapse: collapse;">
                <thead><tr><th>Code</th><th>Type</th><th>Plate Number</th><th>Capacity (kg)</th><th>Fuel Type</th><th>Zone</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>
                    ${(data.vehicles || []).map(vehicle => `
                        <tr>
                            <td><strong>${vehicle.vehicle_code}</strong></td>
                            <td>${getVehicleIcon(vehicle.vehicle_type)} ${vehicle.vehicle_type}</td>
                            <td>${vehicle.plate_number || '-'}</td>
                            <td>${vehicle.capacity_kg || 0}</td>
                            <td>${vehicle.fuel_type || '-'}</td>
                            <td>${vehicle.assigned_zone || '-'}</td>
                            <td><span class="status-badge status-${vehicle.status}">${vehicle.status}</span></td>
                            <td><button class="btn-secondary btn-sm" onclick="editVehicle(${vehicle.vehicle_id})">Edit</button><button class="btn-danger btn-sm" onclick="deleteVehicle(${vehicle.vehicle_id})">Delete</button></td>
                        </tr>
                    `).join('')}
                    ${(data.vehicles || []).length === 0 ? '<tr><td colspan="8">No vehicles found</td></tr>' : ''}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Error loading vehicles:', error);
    }
}

function getVehicleIcon(type) {
    const icons = { 'motorcycle': '🏍️', 'van': '🚐', 'truck': '🚚', 'ebike': '🛵', 'cargo_bike': '🚲' };
    return icons[type] || '🚗';
}

function showNewVehicleModal() {
    showModal('Add New Vehicle', `
        <div class="form-group"><label>Vehicle Code *</label><input type="text" id="vehicleCode" placeholder="e.g., MC-001"></div>
        <div class="form-group"><label>Vehicle Type *</label><select id="vehicleType"><option value="motorcycle">Motorcycle</option><option value="van">Van</option><option value="truck">Truck</option><option value="ebike">E-Bike</option></select></div>
        <div class="form-group"><label>Plate Number</label><input type="text" id="vehiclePlate" placeholder="ABC-1234"></div>
        <div class="form-group"><label>Capacity (kg)</label><input type="number" id="vehicleCapacityKg" value="0"></div>
        <div class="form-group"><label>Fuel Type</label><select id="vehicleFuelType"><option value="gasoline">Gasoline</option><option value="diesel">Diesel</option><option value="electric">Electric</option></select></div>
        <div class="form-group"><label>Assigned Zone</label><input type="text" id="vehicleZone" placeholder="ZONE_A"></div>
        <div class="form-group"><label>Status</label><select id="vehicleStatus"><option value="available">Available</option><option value="assigned">Assigned</option><option value="maintenance">Maintenance</option></select></div>
        <div class="form-actions"><button onclick="closeModal()" class="btn-secondary">Cancel</button><button onclick="saveVehicle()" class="btn-primary">Save</button></div>
    `);
}

window.saveVehicle = async function() {
    const data = {
        vehicle_code: document.getElementById('vehicleCode').value,
        vehicle_type: document.getElementById('vehicleType').value,
        plate_number: document.getElementById('vehiclePlate').value,
        capacity_kg: parseInt(document.getElementById('vehicleCapacityKg').value) || 0,
        fuel_type: document.getElementById('vehicleFuelType').value,
        assigned_zone: document.getElementById('vehicleZone').value || null,
        status: document.getElementById('vehicleStatus').value
    };
    if (!data.vehicle_code || !data.vehicle_type) { alert('Vehicle code and type are required'); return; }
    
    try {
        const response = await fetch(`${API_BASE_URL}/vehicles`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) { closeModal(); refreshVehiclesTable(); }
        else alert('Error: ' + result.error);
    } catch (error) { alert('Error saving vehicle'); }
};

window.editVehicle = async function(id) {
    const response = await fetch(`${API_BASE_URL}/vehicles`);
    const data = await response.json();
    const vehicle = data.vehicles.find(v => v.vehicle_id === id);
    if (vehicle) {
        showModal('Edit Vehicle', `
            <div class="form-group"><label>Vehicle Code</label><input type="text" id="vehicleCode" value="${vehicle.vehicle_code}"></div>
            <div class="form-group"><label>Vehicle Type</label><select id="vehicleType"><option ${vehicle.vehicle_type === 'motorcycle' ? 'selected' : ''}>motorcycle</option><option ${vehicle.vehicle_type === 'van' ? 'selected' : ''}>van</option><option ${vehicle.vehicle_type === 'truck' ? 'selected' : ''}>truck</option></select></div>
            <div class="form-group"><label>Plate Number</label><input type="text" id="vehiclePlate" value="${vehicle.plate_number || ''}"></div>
            <div class="form-group"><label>Capacity (kg)</label><input type="number" id="vehicleCapacityKg" value="${vehicle.capacity_kg || 0}"></div>
            <div class="form-group"><label>Fuel Type</label><select id="vehicleFuelType"><option ${vehicle.fuel_type === 'gasoline' ? 'selected' : ''}>gasoline</option><option ${vehicle.fuel_type === 'diesel' ? 'selected' : ''}>diesel</option><option ${vehicle.fuel_type === 'electric' ? 'selected' : ''}>electric</option></select></div>
            <div class="form-group"><label>Assigned Zone</label><input type="text" id="vehicleZone" value="${vehicle.assigned_zone || ''}"></div>
            <div class="form-group"><label>Status</label><select id="vehicleStatus"><option ${vehicle.status === 'available' ? 'selected' : ''}>available</option><option ${vehicle.status === 'assigned' ? 'selected' : ''}>assigned</option><option ${vehicle.status === 'maintenance' ? 'selected' : ''}>maintenance</option></select></div>
            <div class="form-actions"><button onclick="closeModal()" class="btn-secondary">Cancel</button><button onclick="updateVehicle(${vehicle.vehicle_id})" class="btn-primary">Update</button></div>
        `);
    }
};

window.updateVehicle = async function(id) {
    const data = {
        vehicle_code: document.getElementById('vehicleCode').value,
        vehicle_type: document.getElementById('vehicleType').value,
        plate_number: document.getElementById('vehiclePlate').value,
        capacity_kg: parseInt(document.getElementById('vehicleCapacityKg').value) || 0,
        fuel_type: document.getElementById('vehicleFuelType').value,
        assigned_zone: document.getElementById('vehicleZone').value || null,
        status: document.getElementById('vehicleStatus').value
    };
    try {
        const response = await fetch(`${API_BASE_URL}/vehicles/${id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) { closeModal(); refreshVehiclesTable(); }
        else alert('Error: ' + result.error);
    } catch (error) { alert('Error updating vehicle'); }
};

window.deleteVehicle = async function(id) {
    if (confirm('Are you sure you want to delete this vehicle?')) {
        try {
            const response = await fetch(`${API_BASE_URL}/vehicles/${id}`, { method: 'DELETE' });
            const result = await response.json();
            if (result.success) refreshVehiclesTable();
            else alert('Error deleting vehicle');
        } catch (error) { alert('Error deleting vehicle'); }
    }
};

// ============ USER MANAGEMENT PAGE ============
async function loadUsersPage() {
    contentArea.innerHTML = `
        <div class="filter-bar">
            <div class="filter-group">
                <label>Role</label>
                <select id="userRoleFilter">
                    <option value="">All Roles</option>
                    <option value="admin">Admin</option>
                    <option value="dispatcher">Dispatcher</option>
                    <option value="manager">Manager</option>
                    <option value="driver">Driver</option>
                </select>
            </div>
            <div class="filter-group">
                <button id="applyUserFilter" class="btn-secondary">Apply Filter</button>
                <button id="clearUserFilter" class="btn-secondary">Clear</button>
            </div>
            <div style="flex:1"></div>
            <button id="newUserBtn" class="btn-primary">+ Add User</button>
        </div>
        
        <div class="data-table">
            <div class="table-header">
                <h3>System Users</h3>
            </div>
            <div id="usersTableContainer">
                <div class="loading-placeholder"><div class="loading-spinner-small"></div><p>Loading users...</p></div>
            </div>
        </div>
    `;
    
    document.getElementById('applyUserFilter').addEventListener('click', () => refreshUsersTable());
    document.getElementById('clearUserFilter').addEventListener('click', () => {
        document.getElementById('userRoleFilter').value = '';
        refreshUsersTable();
    });
    document.getElementById('newUserBtn').addEventListener('click', showNewUserModal);
    
    await refreshUsersTable();
}

async function refreshUsersTable() {
    const role = document.getElementById('userRoleFilter')?.value || '';
    let url = `${API_BASE_URL}/users`;
    if (role) url += `?role=${role}`;
    
    const container = document.getElementById('usersTableContainer');
    if (!container) return;
    
    container.innerHTML = '<div class="loading-placeholder"><div class="loading-spinner-small"></div><p>Loading users...</p></div>';
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        if (!data.success) {
            container.innerHTML = `<div class="error">Error: ${data.error || 'Failed to load users'}</div>`;
            return;
        }
        
        if (!data.users || data.users.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #666;">
                    <i class="fas fa-users" style="font-size: 48px; margin-bottom: 10px; display: block;"></i>
                    No users found.
                    <br><small>Click "+ Add User" to create a new user.</small>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `
            <table style="width:100%; border-collapse: collapse;">
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Full Name</th>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Zone Access</th>
                        <th>Status</th>
                        <th>Last Login</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.users.map(user => `
                        <tr>
                            <td><strong>${escapeHtml(user.username)}</strong></td>
                            <td>${escapeHtml(user.full_name || '-')}</td>
                            <td>${escapeHtml(user.email)}</td>
                            <td><span class="status-badge" style="background:#667eea20; color:#667eea">${user.role}</span></td>
                            <td>${user.role === 'driver' ? (escapeHtml(user.zone_access) || 'All Zones') : '-'}</td>
                            <td>${user.is_active ? '<span class="status-badge status-available">Active</span>' : '<span class="status-badge status-repair">Inactive</span>'}</td>
                            <td>${user.last_login ? new Date(user.last_login).toLocaleString() : '-'}</td>
                            <td>
                                <button class="btn-secondary btn-sm" onclick="editUser(${user.user_id})">Edit</button>
                                <button class="btn-danger btn-sm" onclick="deleteUser(${user.user_id})">Delete</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Error loading users:', error);
        container.innerHTML = `<div class="error">Error loading users. Make sure the backend is running.</div>`;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showNewUserModal() {
    showModal('Add New User', `
        <div class="form-group">
            <label>Username *</label>
            <input type="text" id="userUsername" class="form-control" placeholder="e.g., johndoe">
        </div>
        <div class="form-group">
            <label>Password *</label>
            <input type="password" id="userPassword" class="form-control" placeholder="••••••••">
        </div>
        <div class="form-group">
            <label>Full Name</label>
            <input type="text" id="userFullName" class="form-control" placeholder="John Doe">
        </div>
        <div class="form-group">
            <label>Email *</label>
            <input type="email" id="userEmail" class="form-control" placeholder="john@example.com">
        </div>
        
        <div class="form-group">
            <label>Role</label>
            <div style="display: flex; gap: 20px; flex-wrap: wrap; padding: 10px 0;">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                    <input type="radio" name="userRole" value="dispatcher" checked> Dispatcher
                </label>
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                    <input type="radio" name="userRole" value="admin"> Admin
                </label>
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                    <input type="radio" name="userRole" value="manager"> Manager
                </label>
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                    <input type="radio" name="userRole" value="driver"> Driver
                </label>
            </div>
        </div>
        
        <div class="form-group">
            <label>Status</label>
            <select id="userStatus" class="form-control">
                <option value="1">Active</option>
                <option value="0">Inactive</option>
            </select>
        </div>
        <div class="form-actions">
            <button onclick="closeModal()" class="btn-secondary">Cancel</button>
            <button onclick="saveUser()" class="btn-primary">Create User</button>
        </div>
    `);
}

window.saveUser = async function() {
    await new Promise(resolve => setTimeout(resolve, 100));
    
    const username = document.getElementById('userUsername')?.value || '';
    const password = document.getElementById('userPassword')?.value || '';
    const fullName = document.getElementById('userFullName')?.value || '';
    const email = document.getElementById('userEmail')?.value || '';
    const isActive = parseInt(document.getElementById('userStatus')?.value || '1');
    
    const selectedRole = document.querySelector('input[name="userRole"]:checked');
    let role = 'dispatcher';
    if (selectedRole) {
        role = selectedRole.value;
    }
    
    if (!username) { alert('Username is required'); return; }
    if (!password) { alert('Password is required'); return; }
    if (password.length < 4) { alert('Password must be at least 4 characters'); return; }
    if (!email) { alert('Email is required'); return; }
    
    const data = {
        username: username,
        password: password,
        full_name: fullName || null,
        email: email,
        role: role,
        zone_access: null,
        is_active: isActive
    };
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ User "${username}" created successfully!\nRole: ${result.role || role}`);
            closeModal();
            refreshUsersTable();
        } else {
            alert('Error: ' + (result.error || 'Failed to create user'));
        }
    } catch (error) {
        console.error('❌ Error:', error);
        alert('Error saving user: ' + error.message);
    } finally {
        hideLoading();
    }
};

window.editUser = async function(id) {
    const response = await fetch(`${API_BASE_URL}/users`);
    const data = await response.json();
    const user = data.users.find(u => u.user_id === id);
    
    if (!user) return;
    
    const roleOptions = ['dispatcher', 'admin', 'manager', 'driver'];
    const roleLabels = {
        'dispatcher': 'Dispatcher',
        'admin': 'Admin',
        'manager': 'Manager',
        'driver': 'Driver'
    };
    
    showModal('Edit User', `
        <div class="form-group">
            <label>Username</label>
            <input type="text" id="userUsername" class="form-control" value="${escapeHtml(user.username)}" disabled style="background: #f0f2f5;">
            <small class="form-text text-muted">Username cannot be changed</small>
        </div>
        <div class="form-group">
            <label>Password (leave blank to keep current)</label>
            <input type="password" id="userPassword" class="form-control" placeholder="••••••••">
        </div>
        <div class="form-group">
            <label>Full Name</label>
            <input type="text" id="userFullName" class="form-control" value="${escapeHtml(user.full_name || '')}">
        </div>
        <div class="form-group">
            <label>Email *</label>
            <input type="email" id="userEmail" class="form-control" value="${escapeHtml(user.email)}">
        </div>
        
        <div class="form-group">
            <label>Role</label>
            <div style="display: flex; gap: 20px; flex-wrap: wrap; padding: 10px 0;">
                ${roleOptions.map(role => `
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                        <input type="radio" name="userRole" value="${role}" ${user.role === role ? 'checked' : ''}> 
                        ${roleLabels[role]}
                    </label>
                `).join('')}
            </div>
        </div>
        
        <div class="form-group">
            <label>Status</label>
            <select id="userStatus" class="form-control">
                <option value="1" ${user.is_active === 1 ? 'selected' : ''}>Active</option>
                <option value="0" ${user.is_active === 0 ? 'selected' : ''}>Inactive</option>
            </select>
        </div>
        <div class="form-actions">
            <button onclick="closeModal()" class="btn-secondary">Cancel</button>
            <button onclick="updateUser(${user.user_id})" class="btn-primary">Update User</button>
        </div>
    `);
};

window.updateUser = async function(id) {
    const fullName = document.getElementById('userFullName')?.value || '';
    const email = document.getElementById('userEmail')?.value || '';
    const password = document.getElementById('userPassword')?.value || '';
    const isActive = parseInt(document.getElementById('userStatus')?.value || '1');
    
    const selectedRole = document.querySelector('input[name="userRole"]:checked');
    let role = 'dispatcher';
    if (selectedRole) {
        role = selectedRole.value;
    }
    
    if (!email) { alert('Email is required'); return; }
    
    const data = {
        full_name: fullName || null,
        email: email,
        role: role,
        zone_access: null,
        is_active: isActive
    };
    
    if (password && password.length >= 4) {
        data.password = password;
    } else if (password && password.length < 4) {
        alert('Password must be at least 4 characters if changing');
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/users/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ User updated successfully!\nRole: ${role}`);
            closeModal();
            refreshUsersTable();
        } else {
            alert('Error: ' + (result.error || 'Failed to update user'));
        }
    } catch (error) {
        console.error('❌ Error:', error);
        alert('Error updating user: ' + error.message);
    } finally {
        hideLoading();
    }
};

window.deleteUser = async function(id) {
    if (confirm('Are you sure you want to delete this user?')) {
        try {
            const response = await fetch(`${API_BASE_URL}/users/${id}`, { method: 'DELETE' });
            const result = await response.json();
            if (result.success) refreshUsersTable();
            else alert('Error deleting user');
        } catch (error) { alert('Error deleting user'); }
    }
};

// ============ MODAL FUNCTIONS ============
function showModal(title, bodyHtml) {
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    modalTitle.innerText = title;
    modalBody.innerHTML = bodyHtml;
    modal.style.display = 'flex';
}

window.closeModal = function() { document.getElementById('modal').style.display = 'none'; };

document.addEventListener('click', (e) => {
    const modal = document.getElementById('modal');
    if (e.target === modal) closeModal();
});

// ============ DISPATCH MODAL FUNCTIONS ============
function showNewDispatchModal() {
    fetchVehiclesAndDrivers().then(() => {
        showModal('Create Dispatch Assignment', `
            <div class="form-group">
                <label>Zone ID *</label>
                <select id="dispatchZoneId" class="form-control" style="width: 100%;" onchange="updateDemandLevel()">
                    <option value="">Select a zone...</option>
                    ${(zonesList || []).map(zone => `
                        <option value="${zone.zone_id}">${zone.zone_id} - ${zone.zone_name}</option>
                    `).join('')}
                </select>
            </div>
            
            <div class="form-group">
                <label>Date & Time *</label>
                <input type="datetime-local" id="dispatchDateTime" class="form-control">
            </div>
            
            <div class="form-group">
                <label>Number of Deliveries *</label>
                <input type="number" id="deliveryCount" class="form-control" placeholder="Enter number of deliveries" onchange="updateDemandLevel()">
            </div>
            
            <div class="form-group">
                <label>Demand Level (Auto-calculated)</label>
                <input type="text" id="demandLevelDisplay" class="form-control" readonly style="background: #f0f2f5; font-weight: bold;">
            </div>
            
            <div class="form-group">
                <label>Vehicles & Drivers Assignment *</label>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                    <div style="display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;">
                        <select id="vehicleSelect" class="form-control" style="flex: 1; min-width: 150px;">
                            <option value="">Select a vehicle...</option>
                            ${availableVehicles.filter(v => v.status === 'available').map(vehicle => `
                                <option value="${vehicle.vehicle_id}">${vehicle.vehicle_code} - ${vehicle.vehicle_type} (${vehicle.plate_number || 'No plate'})</option>
                            `).join('')}
                        </select>
                        <select id="driverSelect" class="form-control" style="flex: 1; min-width: 150px;">
                            <option value="">Select a driver...</option>
                            ${availableDrivers.map(driver => `
                                <option value="${driver.user_id}">${driver.full_name || driver.username} (${driver.role})</option>
                            `).join('')}
                        </select>
                        <button type="button" class="btn-primary" onclick="addVehicleDriverPair()" style="white-space: nowrap;">+ Add Pair</button>
                    </div>
                    <small class="form-text text-muted">Assign a vehicle with a specific driver. You can add multiple vehicle-driver pairs.</small>
                </div>
                <div id="selectedPairsList" style="margin-top: 10px; max-height: 200px; overflow-y: auto; border: 1px solid #ddd; border-radius: 8px; padding: 10px; background: #f8f9fa;">
                    <div style="color: #666; text-align: center;">No vehicle-driver pairs added yet</div>
                </div>
            </div>
            
            <div class="form-group">
                <label>Notes</label>
                <textarea id="dispatchNotes" class="form-control" rows="3" placeholder="Optional notes..."></textarea>
            </div>
            
            <div class="form-actions">
                <button onclick="closeModal()" class="btn-secondary">Cancel</button>
                <button onclick="saveDispatch()" class="btn-primary">Create Dispatch</button>
            </div>
        `);
        
        const now = new Date();
        now.setHours(now.getHours() + 1);
        now.setMinutes(0);
        document.getElementById('dispatchDateTime').value = now.toISOString().slice(0, 16);
        
        selectedVehicles = [];
        selectedDrivers = [];
        updateSelectedPairsList();
    });
}

async function fetchVehiclesAndDrivers() {
    try {
        const vehiclesResponse = await fetch(`${API_BASE_URL}/vehicles`);
        const vehiclesData = await vehiclesResponse.json();
        availableVehicles = vehiclesData.vehicles || [];
        
        const driversResponse = await fetch(`${API_BASE_URL}/users?role=driver`);
        const driversData = await driversResponse.json();
        availableDrivers = driversData.users || [];
        
        if (!zonesList || zonesList.length === 0) {
            const zonesResponse = await fetch(`${API_BASE_URL}/zones`);
            const zonesData = await zonesResponse.json();
            zonesList = zonesData.zones || [];
        }
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

window.addVehicleDriverPair = function() {
    const vehicleSelect = document.getElementById('vehicleSelect');
    const driverSelect = document.getElementById('driverSelect');
    const vehicleId = vehicleSelect.value;
    const driverId = driverSelect.value;
    
    if (!vehicleId) { alert('Please select a vehicle first'); return; }
    if (!driverId) { alert('Please select a driver first'); return; }
    
    const vehicle = availableVehicles.find(v => v.vehicle_id == vehicleId);
    const driver = availableDrivers.find(d => d.user_id == driverId);
    
    if (!vehicle || !driver) return;
    
    if (selectedVehicles.some(v => v.vehicle_id == vehicleId)) {
        alert(`Vehicle ${vehicle.vehicle_code} already assigned.`);
        return;
    }
    
    if (vehicle.status !== 'available') {
        alert(`Vehicle ${vehicle.vehicle_code} is ${vehicle.status}. Cannot assign.`);
        return;
    }
    
    if (selectedDrivers.some(d => d.driver_id == driverId)) {
        alert(`Driver ${driver.full_name || driver.username} is already assigned.`);
        return;
    }
    
    selectedVehicles.push({
        vehicle_id: vehicle.vehicle_id,
        vehicle_code: vehicle.vehicle_code,
        vehicle_type: vehicle.vehicle_type,
        plate_number: vehicle.plate_number,
        driver_id: driverId,
        driver_name: driver.full_name || driver.username
    });
    
    selectedDrivers.push({
        driver_id: driverId,
        driver_name: driver.full_name || driver.username,
        vehicle_id: vehicle.vehicle_id,
        vehicle_code: vehicle.vehicle_code
    });
    
    updateSelectedPairsList();
    vehicleSelect.value = '';
    driverSelect.value = '';
};

function updateSelectedPairsList() {
    const container = document.getElementById('selectedPairsList');
    if (!container) return;
    
    if (selectedVehicles.length === 0) {
        container.innerHTML = '<div style="color: #666; text-align: center;">No vehicle-driver pairs added yet</div>';
        return;
    }
    
    container.innerHTML = selectedVehicles.map(pair => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px; margin-bottom: 8px; background: white; border-radius: 8px; border: 1px solid #e0e0e0;">
            <div style="flex: 1;">
                <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;">
                    <div>
                        <strong>🚗 ${pair.vehicle_code}</strong><br>
                        <small>${pair.vehicle_type} | ${pair.plate_number || 'No plate'}</small>
                    </div>
                    <div>
                        <i class="fas fa-arrow-right"></i>
                    </div>
                    <div>
                        <strong>👤 ${pair.driver_name}</strong><br>
                        <small>Driver</small>
                    </div>
                </div>
            </div>
            <button class="btn-danger btn-sm" onclick="removeVehicleDriverPair(${pair.vehicle_id}, ${pair.driver_id})">Remove</button>
        </div>
    `).join('');
}

window.removeVehicleDriverPair = function(vehicleId, driverId) {
    selectedVehicles = selectedVehicles.filter(v => v.vehicle_id != vehicleId);
    selectedDrivers = selectedDrivers.filter(d => d.driver_id != driverId);
    updateSelectedPairsList();
};

window.updateDemandLevel = function() {
    const deliveryCount = parseInt(document.getElementById('deliveryCount')?.value) || 0;
    const zoneId = document.getElementById('dispatchZoneId')?.value;
    const demandDisplay = document.getElementById('demandLevelDisplay');
    
    if (!demandDisplay) return;
    
    const zone = zonesList.find(z => z.zone_id === zoneId);
    if (!zone) {
        demandDisplay.value = 'Select zone first';
        demandDisplay.style.color = '#666';
        return;
    }
    
    let demandLevel = '';
    let color = '';
    
    if (deliveryCount <= zone.threshold_normal) {
        demandLevel = 'Normal Demand';
        color = '#16a34a';
    } else if (deliveryCount <= zone.threshold_high) {
        demandLevel = 'High Demand';
        color = '#ea580c';
    } else {
        demandLevel = 'Peak Risk';
        color = '#dc2626';
    }
    
    demandDisplay.value = demandLevel;
    demandDisplay.style.color = color;
    demandDisplay.style.fontWeight = 'bold';
};

window.saveDispatch = async function() {
    const zoneId = document.getElementById('dispatchZoneId').value;
    const datetime = document.getElementById('dispatchDateTime').value;
    const deliveryCount = document.getElementById('deliveryCount').value;
    const notes = document.getElementById('dispatchNotes').value;
    
    if (!zoneId) { alert('Please select a zone'); return; }
    if (!datetime) { alert('Please select date and time'); return; }
    if (!deliveryCount) { alert('Please enter number of deliveries'); return; }
    if (selectedVehicles.length === 0) { alert('Please add at least one vehicle-driver pair'); return; }
    
    const zone = zonesList.find(z => z.zone_id === zoneId);
    let demandLevel = '';
    if (deliveryCount <= zone.threshold_normal) {
        demandLevel = 'Normal Demand';
    } else if (deliveryCount <= zone.threshold_high) {
        demandLevel = 'High Demand';
    } else {
        demandLevel = 'Peak Risk';
    }
    
    const assignedVehiclesStr = selectedVehicles.map(v => `${v.vehicle_code} (${v.vehicle_type})`).join(', ');
    const assignedDriversStr = selectedDrivers.map(d => d.driver_name).join(', ');
    
    const data = {
        zone_id: zoneId,
        dispatch_datetime: datetime.replace('T', ' ') + ':00',
        predicted_deliveries: parseInt(deliveryCount),
        actual_deliveries: null,
        demand_level: demandLevel,
        assigned_vehicles: assignedVehiclesStr,
        assigned_drivers: assignedDriversStr,
        dispatch_status: 'planned',
        notes: notes,
        created_by: 1
    };
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/dispatch/assignments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            const shiftDate = datetime.split('T')[0];
            const shiftTime = datetime.split('T')[1];
            const endTime = new Date(new Date(datetime).getTime() + 8*60*60*1000).toISOString().slice(11, 16);
            
            for (const pair of selectedVehicles) {
                await fetch(`${API_BASE_URL}/vehicles/${pair.vehicle_id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ 
                        status: 'assigned', 
                        driver_id: pair.driver_id,
                        assigned_zone: zoneId
                    })
                });
                
                await fetch(`${API_BASE_URL}/driver/assignments`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        driver_id: parseInt(pair.driver_id),
                        vehicle_id: pair.vehicle_id,
                        shift_date: shiftDate,
                        shift_start: shiftTime,
                        shift_end: endTime,
                        zone_id: zoneId,
                        status: 'scheduled'
                    })
                });
            }
            
            alert(`Dispatch assignment created successfully!\nAssigned: ${selectedVehicles.length} vehicle(s) with ${selectedDrivers.length} driver(s)`);
            closeModal();
            refreshCurrentPage();
        } else {
            alert('Error: ' + (result.error || 'Failed to create dispatch'));
        }
    } catch (error) {
        console.error('Error creating dispatch:', error);
        alert('Error creating dispatch assignment');
    } finally {
        hideLoading();
    }
};

window.editDispatch = async function(id) {
    const response = await fetch(`${API_BASE_URL}/dispatch/assignments`);
    const data = await response.json();
    const assignment = data.assignments.find(a => a.assignment_id === id);
    
    if (!assignment) return;
    
    await fetchVehiclesAndDrivers();
    
    selectedVehicles = [];
    selectedDrivers = [];
    
    if (assignment.assigned_vehicles && assignment.assigned_drivers) {
        const vehiclePairs = assignment.assigned_vehicles.split(',');
        const driverNames = assignment.assigned_drivers.split(',');
        
        for (let i = 0; i < vehiclePairs.length; i++) {
            const vehicleCode = vehiclePairs[i].trim().split(' ')[0];
            const vehicle = availableVehicles.find(v => v.vehicle_code === vehicleCode);
            const driver = availableDrivers.find(d => (d.full_name || d.username) === driverNames[i]?.trim());
            
            if (vehicle && driver) {
                selectedVehicles.push({
                    vehicle_id: vehicle.vehicle_id,
                    vehicle_code: vehicle.vehicle_code,
                    vehicle_type: vehicle.vehicle_type,
                    plate_number: vehicle.plate_number,
                    driver_id: driver.user_id,
                    driver_name: driver.full_name || driver.username
                });
                
                selectedDrivers.push({
                    driver_id: driver.user_id,
                    driver_name: driver.full_name || driver.username,
                    vehicle_id: vehicle.vehicle_id,
                    vehicle_code: vehicle.vehicle_code
                });
            }
        }
    }
    
    showModal('Edit Dispatch Assignment', `
        <div class="form-group">
            <label>Zone ID</label>
            <select id="dispatchZoneId" class="form-control" onchange="updateDemandLevel()">
                ${(zonesList || []).map(zone => `
                    <option value="${zone.zone_id}" ${assignment.zone_id === zone.zone_id ? 'selected' : ''}>${zone.zone_id} - ${zone.zone_name}</option>
                `).join('')}
            </select>
        </div>
        
        <div class="form-group">
            <label>Date & Time</label>
            <input type="datetime-local" id="dispatchDateTime" class="form-control" value="${assignment.dispatch_datetime ? assignment.dispatch_datetime.slice(0, 16) : ''}">
        </div>
        
        <div class="form-group">
            <label>Number of Deliveries</label>
            <input type="number" id="deliveryCount" class="form-control" value="${assignment.predicted_deliveries || ''}" onchange="updateDemandLevel()">
        </div>
        
        <div class="form-group">
            <label>Demand Level (Auto-calculated)</label>
            <input type="text" id="demandLevelDisplay" class="form-control" readonly style="background: #f0f2f5;">
        </div>
        
        <div class="form-group">
            <label>Status</label>
            <select id="dispatchStatus" class="form-control">
                <option value="planned" ${assignment.dispatch_status === 'planned' ? 'selected' : ''}>Planned</option>
                <option value="assigned" ${assignment.dispatch_status === 'assigned' ? 'selected' : ''}>Assigned</option>
                <option value="enroute" ${assignment.dispatch_status === 'enroute' ? 'selected' : ''}>En Route</option>
                <option value="completed" ${assignment.dispatch_status === 'completed' ? 'selected' : ''}>Completed</option>
                <option value="cancelled" ${assignment.dispatch_status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
            </select>
        </div>
        
        <div class="form-group">
            <label>Vehicles & Drivers Assignment</label>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px;">
                <div style="display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;">
                    <select id="vehicleSelect" class="form-control" style="flex: 1; min-width: 150px;">
                        <option value="">Select a vehicle...</option>
                        ${availableVehicles.filter(v => v.status === 'available' || selectedVehicles.some(sv => sv.vehicle_id === v.vehicle_id)).map(vehicle => `
                            <option value="${vehicle.vehicle_id}">${vehicle.vehicle_code} - ${vehicle.vehicle_type} (${vehicle.status})</option>
                        `).join('')}
                    </select>
                    <select id="driverSelect" class="form-control" style="flex: 1; min-width: 150px;">
                        <option value="">Select a driver...</option>
                        ${availableDrivers.map(driver => `
                            <option value="${driver.user_id}">${driver.full_name || driver.username} (${driver.role})</option>
                        `).join('')}
                    </select>
                    <button type="button" class="btn-primary" onclick="addVehicleDriverPair()">+ Add Pair</button>
                </div>
                <small class="form-text text-muted">Add vehicle-driver pairs. Each pair represents one vehicle with its assigned driver.</small>
            </div>
            <div id="selectedPairsList" style="margin-top: 10px; max-height: 200px; overflow-y: auto; border: 1px solid #ddd; border-radius: 8px; padding: 10px; background: #f8f9fa;"></div>
        </div>
        
        <div class="form-group">
            <label>Notes</label>
            <textarea id="dispatchNotes" class="form-control" rows="3">${assignment.notes || ''}</textarea>
        </div>
        
        <div class="form-actions">
            <button onclick="closeModal()" class="btn-secondary">Cancel</button>
            <button onclick="updateDispatch(${assignment.assignment_id})" class="btn-primary">Update</button>
        </div>
    `);
    
    updateSelectedPairsList();
    updateDemandLevel();
};

window.updateDispatch = async function(id) {
    const zoneId = document.getElementById('dispatchZoneId').value;
    const datetime = document.getElementById('dispatchDateTime').value;
    const deliveryCount = document.getElementById('deliveryCount').value;
    const status = document.getElementById('dispatchStatus').value;
    const notes = document.getElementById('dispatchNotes').value;
    
    const zone = zonesList.find(z => z.zone_id === zoneId);
    let demandLevel = '';
    if (deliveryCount <= zone.threshold_normal) {
        demandLevel = 'Normal Demand';
    } else if (deliveryCount <= zone.threshold_high) {
        demandLevel = 'High Demand';
    } else {
        demandLevel = 'Peak Risk';
    }
    
    const assignedVehiclesStr = selectedVehicles.map(v => `${v.vehicle_code} (${v.vehicle_type})`).join(', ');
    const assignedDriversStr = selectedDrivers.map(d => d.driver_name).join(', ');
    
    const data = {
        zone_id: zoneId,
        dispatch_datetime: datetime.replace('T', ' ') + ':00',
        predicted_deliveries: parseInt(deliveryCount),
        demand_level: demandLevel,
        assigned_vehicles: assignedVehiclesStr,
        assigned_drivers: assignedDriversStr,
        dispatch_status: status,
        notes: notes
    };
    
    if (status === 'completed') {
        data.completed_at = new Date().toISOString().slice(0, 19).replace('T', ' ');
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/dispatch/assignments/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) {
            alert('Dispatch assignment updated successfully!');
            closeModal();
            refreshCurrentPage();
        } else {
            alert('Error: ' + result.error);
        }
    } catch (error) {
        alert('Error updating dispatch');
    }
};

window.deleteDispatch = async function(id) {
    if (confirm('Are you sure you want to delete this dispatch assignment?')) {
        try {
            const response = await fetch(`${API_BASE_URL}/dispatch/assignments/${id}`, { method: 'DELETE' });
            const data = await response.json();
            if (data.success) refreshDispatchTable();
            else alert('Error deleting assignment');
        } catch (error) {
            alert('Error deleting assignment');
        }
    }
};

// ============ LOADING FUNCTIONS ============
function showLoading() {
    let overlay = document.getElementById('loadingOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loadingOverlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `<div class="loading-spinner"></div><p>Loading...</p>`;
        document.body.appendChild(overlay);
    }
    overlay.style.display = 'flex';
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.style.display = 'none';
}

window.refreshCurrentPage = function() { loadPage(currentPage); };
window.refreshDispatchTable = refreshDispatchTable;
window.refreshVehiclesTable = refreshVehiclesTable;
window.refreshUsersTable = refreshUsersTable;