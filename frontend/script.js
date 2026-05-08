// API Configuration
const API_BASE_URL = 'http://127.0.0.1:5000/api';
// Current page tracking
let currentPage = 'dashboard';

// Pagination state
let currentDispatchPage = 1;
let currentVehiclePage = 1;
let totalDispatchPages = 1;
let totalVehiclePages = 1;

// DOM Elements
let contentArea;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    contentArea = document.getElementById('contentArea');
    setupNavigation();
    loadPage('dashboard');
});

// Navigation setup
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

// Load page content
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
    try {
        const statsResponse = await fetch(`${API_BASE_URL}/dashboard/stats`);
        const statsData = await statsResponse.json();
        
        const zonesResponse = await fetch(`${API_BASE_URL}/zones`);
        const zonesData = await zonesResponse.json();
        
        const assignmentsResponse = await fetch(`${API_BASE_URL}/dispatch/assignments?status=enroute,assigned`);
        const assignmentsData = await assignmentsResponse.json();
        
        contentArea.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">🚚</div>
                    <div class="stat-value">${statsData.stats.total_vehicles || 0}</div>
                    <div class="stat-label">Total Vehicles</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">👥</div>
                    <div class="stat-value">${getUserCount(statsData.stats.users_by_role)}</div>
                    <div class="stat-label">Active Users</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">📦</div>
                    <div class="stat-value">${statsData.stats.today_assignments || 0}</div>
                    <div class="stat-label">Today's Dispatches</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">🚛</div>
                    <div class="stat-value">${statsData.stats.active_drivers_today || 0}</div>
                    <div class="stat-label">Active Drivers Today</div>
                </div>
            </div>
            
            <div class="data-table">
                <div class="table-header">
                    <h3>Active Dispatches</h3>
                </div>
                <table>
                    <thead>
                        <tr><th>Zone</th><th>Time</th><th>Predicted</th><th>Status</th><th>Assigned</th></tr>
                    </thead>
                    <tbody>
                        ${renderActiveDispatches(assignmentsData.assignments || [])}
                    </tbody>
                </table>
            </div>
            
            <div class="data-table" style="margin-top: 30px;">
                <div class="table-header">
                    <h3>Delivery Zones</h3>
                </div>
                <table>
                    <thead>
                        <tr><th>Zone</th><th>Name</th><th>Base Vehicles</th><th>Normal Threshold</th><th>High Threshold</th></tr>
                    </thead>
                    <tbody>
                        ${(zonesData.zones || []).map(zone => `
                            <tr>
                                <td><strong>${zone.zone_id}</strong></td>
                                <td>${zone.zone_name}</td>
                                <td>${zone.base_vehicles}</td>
                                <td>${zone.threshold_normal}</td>
                                <td>${zone.threshold_high}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (error) {
        console.error('Error loading dashboard:', error);
        contentArea.innerHTML = '<div class="error">Error loading dashboard data</div>';
    }
}

function getUserCount(usersByRole) {
    if (!usersByRole) return 0;
    return usersByRole.reduce((sum, role) => sum + role.count, 0);
}

function renderActiveDispatches(assignments) {
    if (!assignments.length) {
        return '<tr><td colspan="5">No active dispatches</td></tr>';
    }
    return assignments.map(ass => `
        <tr>
            <td>${ass.zone_id}</td>
            <td>${new Date(ass.dispatch_datetime).toLocaleString()}</td>
            <td>${ass.predicted_deliveries || '-'}</td>
            <td><span class="status-badge status-${ass.dispatch_status}">${ass.dispatch_status}</span></td>
            <td>${ass.assigned_vehicles || '-'}</td>
        </tr>
    `).join('');
}

// ============ DEMAND FORECAST PAGE ============
async function loadForecastPage() {
    const zonesResponse = await fetch(`${API_BASE_URL}/zones`);
    const zonesData = await zonesResponse.json();
    
    const now = new Date();
    now.setHours(now.getHours() + 1);
    now.setMinutes(0);
    const defaultDateTime = now.toISOString().slice(0, 16);
    
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
                            <option value="${zone.zone_id}">${zone.zone_id} - ${zone.zone_name}</option>
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
    
    resultsDiv.innerHTML = `
        <div class="metrics-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
            <div class="metric-card" style="padding: 20px; text-align: center; background: linear-gradient(135deg, #f5f7fa, #e9ecef); border-radius: 15px;">
                <div class="metric-label">Predicted Deliveries</div>
                <div class="metric-value" style="font-size: 32px; font-weight: 800;">${prediction.predicted_deliveries}</div>
                <div class="metric-sub">95% CI: ${prediction.confidence_interval[0]} - ${prediction.confidence_interval[1]}</div>
            </div>
            <div class="metric-card" style="padding: 20px; text-align: center; background: linear-gradient(135deg, #f5f7fa, #e9ecef); border-radius: 15px;">
                <div class="metric-label">Demand Level</div>
                <div class="metric-value" style="font-size: 32px; font-weight: 800; color: ${demandColor}">${prediction.demand_level}</div>
                <div class="metric-sub">${prediction.demand_level === 'Peak Risk' ? '⚠️ Prepare all resources' : 
                                         prediction.demand_level === 'High Demand' ? '📈 Increase capacity' : '✅ Normal operations'}</div>
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
        </div>
    `;
    
    resultsPanel.style.display = 'block';
    window.lastPrediction = prediction;
}

window.createDispatchFromPrediction = async function() {
    if (!window.lastPrediction) return;
    const pred = window.lastPrediction;
    
    showLoading();
    try {
        const response = await fetch(`${API_BASE_URL}/dispatch/assignments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                zone_id: pred.zone_id,
                dispatch_datetime: pred.datetime,
                predicted_deliveries: pred.predicted_deliveries,
                demand_level: pred.demand_level,
                assigned_vehicles: `${pred.vehicle_breakdown.motorcycles} MC, ${pred.vehicle_breakdown.vans} Vans, ${pred.vehicle_breakdown.trucks} Trucks`,
                dispatch_status: 'planned',
                notes: 'Auto-created from demand prediction',
                created_by: 1
            })
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Dispatch assignment created successfully!');
            loadPage('dispatch');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Error creating assignment');
    } finally {
        hideLoading();
    }
};

// ============ ENHANCED FLEET DISPATCH PAGE ============
async function loadDispatchPage() {
    const zonesResponse = await fetch(`${API_BASE_URL}/zones`);
    const zonesData = await zonesResponse.json();
    
    contentArea.innerHTML = `
        <div class="filter-bar">
            <div class="filter-group">
                <label>🔍 Search (Code/Driver/Vehicle)</label>
                <input type="text" id="dispatchSearch" placeholder="Search by vehicle code, driver, zone..." style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 8px; width: 220px;">
            </div>
            <div class="filter-group">
                <label>Zone</label>
                <select id="dispatchZoneFilter">
                    <option value="">All Zones</option>
                    ${(zonesData.zones || []).map(zone => `<option value="${zone.zone_id}">${zone.zone_id}</option>`).join('')}
                </select>
            </div>
            <div class="filter-group">
                <label>Status</label>
                <select id="dispatchStatusFilter">
                    <option value="">All Status</option>
                    <option value="planned">Planned</option>
                    <option value="assigned">Assigned</option>
                    <option value="enroute">En Route</option>
                    <option value="completed">Completed</option>
                </select>
            </div>
            <div class="filter-group">
                <label>Date</label>
                <input type="date" id="dispatchDateFilter">
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
            <div id="dispatchTableContainer">
                <div class="loading-placeholder"><div class="loading-spinner-small"></div><p>Loading...</p></div>
            </div>
        </div>
        <div id="dispatchPagination" style="display: flex; justify-content: center; gap: 10px; margin-top: 20px;"></div>
    `;
    
    document.getElementById('applyDispatchFilter').addEventListener('click', () => { currentDispatchPage = 1; refreshDispatchTable(); });
    document.getElementById('clearDispatchFilter').addEventListener('click', () => {
        document.getElementById('dispatchSearch').value = '';
        document.getElementById('dispatchZoneFilter').value = '';
        document.getElementById('dispatchStatusFilter').value = '';
        document.getElementById('dispatchDateFilter').value = '';
        currentDispatchPage = 1;
        refreshDispatchTable();
    });
    document.getElementById('newDispatchBtn').addEventListener('click', showNewDispatchModal);
    
    await refreshDispatchTable();
}

async function refreshDispatchTable() {
    const search = document.getElementById('dispatchSearch')?.value || '';
    const zone = document.getElementById('dispatchZoneFilter')?.value || '';
    const status = document.getElementById('dispatchStatusFilter')?.value || '';
    const date = document.getElementById('dispatchDateFilter')?.value || '';
    
    let url = `${API_BASE_URL}/dispatch/assignments/enhanced?page=${currentDispatchPage}&per_page=15`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (zone) url += `&zone_id=${zone}`;
    if (status) url += `&status=${status}`;
    if (date) url += `&date=${date}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        const container = document.getElementById('dispatchTableContainer');
        if (!container) return;
        
        totalDispatchPages = data.pagination?.total_pages || 1;
        
        container.innerHTML = `
            <table style="width:100%; border-collapse: collapse;">
                <thead>
                    <tr><th>ID</th><th>Zone</th><th>Date/Time</th><th>Predicted</th><th>Actual</th><th>Demand Level</th><th>Assigned Vehicles</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>
                    ${(data.assignments || []).map(ass => `
                        <tr>
                            <td>${ass.assignment_id}</td>
                            <td><strong>${ass.zone_id}</strong><br><small>${ass.zone_name || ''}</small></td>
                            <td>${new Date(ass.dispatch_datetime).toLocaleString()}</td>
                            <td>${ass.predicted_deliveries || '-'}</td>
                            <td>${ass.actual_deliveries || '-'}</td>
                            <td><span class="status-badge" style="background:${getDemandColor(ass.demand_level)}20; color:${getDemandColor(ass.demand_level)}">${ass.demand_level || '-'}</span></td>
                            <td>${ass.assigned_vehicles || '-'}</td>
                            <td><span class="status-badge status-${ass.dispatch_status}">${ass.dispatch_status}</span></td>
                            <td><button class="btn-secondary btn-sm" onclick="editDispatch(${ass.assignment_id})">Edit</button><button class="btn-danger btn-sm" onclick="deleteDispatch(${ass.assignment_id})">Delete</button></td>
                        </tr>
                    `).join('')}
                    ${(data.assignments || []).length === 0 ? '<tr><td colspan="9">No dispatch assignments found</td></tr>' : ''}
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

window.editDispatch = async function(id) {
    const response = await fetch(`${API_BASE_URL}/dispatch/assignments`);
    const data = await response.json();
    const assignment = data.assignments.find(a => a.assignment_id === id);
    if (assignment) {
        showEditDispatchModal(assignment);
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

function showNewDispatchModal() {
    showModal('Create Dispatch Assignment', `
        <div class="form-group"><label>Zone ID</label><input type="text" id="dispatchZoneId" placeholder="e.g., ZONE_A"></div>
        <div class="form-group"><label>Date & Time</label><input type="datetime-local" id="dispatchDateTime"></div>
        <div class="form-group"><label>Predicted Deliveries</label><input type="number" id="dispatchPredicted" placeholder="0"></div>
        <div class="form-group"><label>Demand Level</label><select id="dispatchDemandLevel"><option>Normal Demand</option><option>High Demand</option><option>Peak Risk</option></select></div>
        <div class="form-group"><label>Assigned Vehicles</label><input type="text" id="dispatchVehicles" placeholder="e.g., 3 MC, 1 Van"></div>
        <div class="form-group"><label>Assigned Driver ID</label><input type="number" id="dispatchDriver" placeholder="Driver user ID"></div>
        <div class="form-group"><label>Vehicle ID</label><input type="number" id="dispatchVehicle" placeholder="Vehicle ID"></div>
        <div class="form-group"><label>Status</label><select id="dispatchStatus"><option>planned</option><option>assigned</option><option>enroute</option><option>completed</option></select></div>
        <div class="form-group"><label>Notes</label><textarea id="dispatchNotes" rows="3"></textarea></div>
        <div class="form-actions"><button onclick="closeModal()" class="btn-secondary">Cancel</button><button onclick="saveFullDispatch()" class="btn-primary">Save</button></div>
    `);
}

window.saveFullDispatch = async function() {
    const data = {
        zone_id: document.getElementById('dispatchZoneId').value,
        dispatch_datetime: document.getElementById('dispatchDateTime').value.replace('T', ' ') + ':00',
        predicted_deliveries: parseInt(document.getElementById('dispatchPredicted').value) || null,
        demand_level: document.getElementById('dispatchDemandLevel').value,
        assigned_vehicles: document.getElementById('dispatchVehicles').value,
        assigned_drivers: document.getElementById('dispatchDriver')?.value || null,
        vehicle_id: document.getElementById('dispatchVehicle')?.value || null,
        dispatch_status: document.getElementById('dispatchStatus').value,
        notes: document.getElementById('dispatchNotes').value,
        created_by: 1
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/dispatch/assignments/full`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) { closeModal(); refreshDispatchTable(); }
        else alert('Error: ' + result.error);
    } catch (error) { alert('Error saving dispatch'); }
};

function showEditDispatchModal(assignment) {
    showModal('Edit Dispatch Assignment', `
        <div class="form-group"><label>Zone ID</label><input type="text" id="dispatchZoneId" value="${assignment.zone_id || ''}"></div>
        <div class="form-group"><label>Date & Time</label><input type="datetime-local" id="dispatchDateTime" value="${assignment.dispatch_datetime ? assignment.dispatch_datetime.slice(0, 16) : ''}"></div>
        <div class="form-group"><label>Predicted Deliveries</label><input type="number" id="dispatchPredicted" value="${assignment.predicted_deliveries || ''}"></div>
        <div class="form-group"><label>Actual Deliveries</label><input type="number" id="dispatchActual" value="${assignment.actual_deliveries || ''}"></div>
        <div class="form-group"><label>Demand Level</label><select id="dispatchDemandLevel"><option ${assignment.demand_level === 'Normal Demand' ? 'selected' : ''}>Normal Demand</option><option ${assignment.demand_level === 'High Demand' ? 'selected' : ''}>High Demand</option><option ${assignment.demand_level === 'Peak Risk' ? 'selected' : ''}>Peak Risk</option></select></div>
        <div class="form-group"><label>Assigned Vehicles</label><input type="text" id="dispatchVehicles" value="${assignment.assigned_vehicles || ''}"></div>
        <div class="form-group"><label>Status</label><select id="dispatchStatus"><option ${assignment.dispatch_status === 'planned' ? 'selected' : ''}>planned</option><option ${assignment.dispatch_status === 'assigned' ? 'selected' : ''}>assigned</option><option ${assignment.dispatch_status === 'enroute' ? 'selected' : ''}>enroute</option><option ${assignment.dispatch_status === 'completed' ? 'selected' : ''}>completed</option></select></div>
        <div class="form-group"><label>Notes</label><textarea id="dispatchNotes" rows="3">${assignment.notes || ''}</textarea></div>
        <div class="form-actions"><button onclick="closeModal()" class="btn-secondary">Cancel</button><button onclick="updateDispatch(${assignment.assignment_id})" class="btn-primary">Update</button></div>
    `);
}

window.updateDispatch = async function(id) {
    const data = {
        zone_id: document.getElementById('dispatchZoneId').value,
        dispatch_datetime: document.getElementById('dispatchDateTime').value.replace('T', ' ') + ':00',
        predicted_deliveries: parseInt(document.getElementById('dispatchPredicted').value) || null,
        actual_deliveries: parseInt(document.getElementById('dispatchActual')?.value) || null,
        demand_level: document.getElementById('dispatchDemandLevel').value,
        assigned_vehicles: document.getElementById('dispatchVehicles').value,
        dispatch_status: document.getElementById('dispatchStatus').value,
        notes: document.getElementById('dispatchNotes').value
    };
    if (data.dispatch_status === 'completed') data.completed_at = new Date().toISOString().slice(0, 19).replace('T', ' ');
    
    try {
        const response = await fetch(`${API_BASE_URL}/dispatch/assignments/${id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) { closeModal(); refreshDispatchTable(); }
        else alert('Error: ' + result.error);
    } catch (error) { alert('Error updating dispatch'); }
};

// ============ ENHANCED VEHICLE MANAGEMENT PAGE ============
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
    
    let url = `${API_BASE_URL}/vehicles/enhanced?page=${currentVehiclePage}&per_page=15`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (zone) url += `&zone_id=${zone}`;
    if (status) url += `&status=${status}`;
    if (type) url += `&vehicle_type=${type}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        const container = document.getElementById('vehiclesTableContainer');
        if (!container) return;
        
        totalVehiclePages = data.pagination?.total_pages || 1;
        
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
        
        const paginationDiv = document.getElementById('vehiclePagination');
        if (paginationDiv && totalVehiclePages > 1) {
            paginationDiv.innerHTML = `
                <button class="btn-secondary" onclick="changeVehiclePage(${currentVehiclePage - 1})" ${currentVehiclePage === 1 ? 'disabled' : ''}>Previous</button>
                <span style="padding: 8px 16px;">Page ${currentVehiclePage} of ${totalVehiclePages}</span>
                <button class="btn-secondary" onclick="changeVehiclePage(${currentVehiclePage + 1})" ${currentVehiclePage === totalVehiclePages ? 'disabled' : ''}>Next</button>
            `;
        }
    } catch (error) {
        console.error('Error loading vehicles:', error);
    }
}

function changeVehiclePage(page) {
    if (page >= 1 && page <= totalVehiclePages) {
        currentVehiclePage = page;
        refreshVehiclesTable();
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
    await refreshUsersTable();
    
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
                <div class="loading-placeholder"><div class="loading-spinner-small"></div><p>Loading...</p></div>
            </div>
        </div>
    `;
    
    document.getElementById('applyUserFilter').addEventListener('click', refreshUsersTable);
    document.getElementById('clearUserFilter').addEventListener('click', () => {
        document.getElementById('userRoleFilter').value = '';
        refreshUsersTable();
    });
    document.getElementById('newUserBtn').addEventListener('click', showNewUserModal);
}

async function refreshUsersTable() {
    const role = document.getElementById('userRoleFilter')?.value || '';
    let url = `${API_BASE_URL}/users`;
    if (role) url += `?role=${role}`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        const container = document.getElementById('usersTableContainer');
        if (!container) return;
        
        container.innerHTML = `
            <table style="width:100%; border-collapse: collapse;">
                <thead>
                    <tr><th>Username</th><th>Full Name</th><th>Email</th><th>Role</th><th>Zone Access</th><th>Status</th><th>Last Login</th><th>Actions</th></tr>
                </thead>
                <tbody>
                    ${(data.users || []).map(user => `
                        <tr>
                            <td><strong>${user.username}</strong></td>
                            <td>${user.full_name || '-'}</td>
                            <td>${user.email}</td>
                            <td><span class="status-badge" style="background:#667eea20; color:#667eea">${user.role}</span></td>
                            <td>${user.role === 'driver' ? (user.zone_access || '-') : '-'}</td>
                            <td>${user.is_active ? '<span class="status-badge status-available">Active</span>' : '<span class="status-badge status-repair">Inactive</span>'}</td>
                            <td>${user.last_login ? new Date(user.last_login).toLocaleString() : '-'}</td>
                            <td><button class="btn-secondary btn-sm" onclick="editUser(${user.user_id})">Edit</button><button class="btn-danger btn-sm" onclick="deleteUser(${user.user_id})">Delete</button></td>
                        </tr>
                    `).join('')}
                    ${(data.users || []).length === 0 ? '<tr><td colspan="8">No users found<\/td></tr>' : ''}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function showNewUserModal() {
    showModal('Add New User', `
        <div class="form-group"><label>Username *</label><input type="text" id="userUsername" placeholder="e.g., johndoe"></div>
        <div class="form-group"><label>Password *</label><input type="password" id="userPassword" placeholder="••••••••"></div>
        <div class="form-group"><label>Full Name</label><input type="text" id="userFullName" placeholder="John Doe"></div>
        <div class="form-group"><label>Email *</label><input type="email" id="userEmail" placeholder="john@example.com"></div>
        <div class="form-group"><label>Role</label><select id="userRole"><option value="dispatcher">Dispatcher</option><option value="admin">Admin</option><option value="manager">Manager</option><option value="driver">Driver</option></select></div>
        <div class="form-group driver-zone" style="display:none;"><label>Zone Access (comma-separated)</label><input type="text" id="userZoneAccess" placeholder="ZONE_A,ZONE_B"><small style="color:#666;">Only for drivers</small></div>
        <div class="form-group"><label>Status</label><select id="userStatus"><option value="1">Active</option><option value="0">Inactive</option></select></div>
        <div class="form-actions"><button onclick="closeModal()" class="btn-secondary">Cancel</button><button onclick="saveUser()" class="btn-primary">Save</button></div>
    `);
    
    document.getElementById('userRole').addEventListener('change', (e) => {
        const zoneDiv = document.querySelector('.driver-zone');
        if (zoneDiv) zoneDiv.style.display = e.target.value === 'driver' ? 'block' : 'none';
    });
}

window.saveUser = async function() {
    const password = document.getElementById('userPassword').value;
    if (!password) { alert('Password is required'); return; }
    
    const role = document.getElementById('userRole').value;
    const data = {
        username: document.getElementById('userUsername').value,
        password: password,
        full_name: document.getElementById('userFullName').value,
        email: document.getElementById('userEmail').value,
        role: role,
        zone_access: role === 'driver' ? document.getElementById('userZoneAccess').value : null,
        is_active: parseInt(document.getElementById('userStatus').value)
    };
    if (!data.username || !data.email) { alert('Username and email are required'); return; }
    
    try {
        const response = await fetch(`${API_BASE_URL}/users`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) { closeModal(); refreshUsersTable(); }
        else alert('Error: ' + result.error);
    } catch (error) { alert('Error saving user'); }
};

window.editUser = async function(id) {
    const response = await fetch(`${API_BASE_URL}/users`);
    const data = await response.json();
    const user = data.users.find(u => u.user_id === id);
    if (user) {
        showModal('Edit User', `
            <div class="form-group"><label>Username</label><input type="text" id="userUsername" value="${user.username}" readonly style="background:#f0f2f5"></div>
            <div class="form-group"><label>New Password (leave blank to keep current)</label><input type="password" id="userPassword" placeholder="••••••••"></div>
            <div class="form-group"><label>Full Name</label><input type="text" id="userFullName" value="${user.full_name || ''}"></div>
            <div class="form-group"><label>Email</label><input type="email" id="userEmail" value="${user.email}"></div>
            <div class="form-group"><label>Role</label><select id="userRole"><option ${user.role === 'dispatcher' ? 'selected' : ''}>dispatcher</option><option ${user.role === 'admin' ? 'selected' : ''}>admin</option><option ${user.role === 'manager' ? 'selected' : ''}>manager</option><option ${user.role === 'driver' ? 'selected' : ''}>driver</option></select></div>
            <div class="form-group driver-zone" style="${user.role === 'driver' ? 'block' : 'none'}"><label>Zone Access</label><input type="text" id="userZoneAccess" value="${user.zone_access || ''}"></div>
            <div class="form-group"><label>Status</label><select id="userStatus"><option value="1" ${user.is_active ? 'selected' : ''}>Active</option><option value="0" ${!user.is_active ? 'selected' : ''}>Inactive</option></select></div>
            <div class="form-actions"><button onclick="closeModal()" class="btn-secondary">Cancel</button><button onclick="updateUser(${user.user_id})" class="btn-primary">Update</button></div>
        `);
        
        document.getElementById('userRole').addEventListener('change', (e) => {
            const zoneDiv = document.querySelector('.driver-zone');
            if (zoneDiv) zoneDiv.style.display = e.target.value === 'driver' ? 'block' : 'none';
        });
    }
};

window.updateUser = async function(id) {
    const role = document.getElementById('userRole').value;
    const data = {
        full_name: document.getElementById('userFullName').value,
        email: document.getElementById('userEmail').value,
        role: role,
        zone_access: role === 'driver' ? document.getElementById('userZoneAccess').value : null,
        is_active: parseInt(document.getElementById('userStatus').value)
    };
    const password = document.getElementById('userPassword').value;
    if (password) data.password = password;
    
    try {
        const response = await fetch(`${API_BASE_URL}/users/${id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) { closeModal(); refreshUsersTable(); }
        else alert('Error: ' + result.error);
    } catch (error) { alert('Error updating user'); }
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