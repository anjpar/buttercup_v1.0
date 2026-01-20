/**
 * JavaScript for Static Analysis UI
 * 
 * Add this to: orchestrator/src/buttercup/orchestrator/ui/static/script.js
 */

// ============================================================================
// Global state for static analysis
// ============================================================================

let staticAnalysisData = {
    clusters: [],
    findings: [],
    stats: {},
    currentView: 'cluster'  // 'cluster' or 'list'
};

// ============================================================================
// Load static analysis data
// ============================================================================

async function loadStaticAnalysis() {
    const taskFilter = document.getElementById('static-task-filter')?.value || '';
    const severityFilter = document.getElementById('static-severity-filter')?.value || '';
    const toolFilter = document.getElementById('static-tool-filter')?.value || '';
    
    try {
        // Build query string
        const params = new URLSearchParams();
        if (taskFilter) params.append('task_id', taskFilter);
        if (severityFilter) params.append('severity', severityFilter);
        if (toolFilter) params.append('tool_name', toolFilter);
        
        // Fetch clusters (for cluster view)
        const clustersUrl = `/v1/dashboard/static_clusters?${params.toString()}`;
        const clustersResponse = await fetch(clustersUrl);
        const clustersData = await clustersResponse.json();
        
        // Fetch all findings (for list view)
        const findingsUrl = `/v1/dashboard/static_findings?${params.toString()}`;
        const findingsResponse = await fetch(findingsUrl);
        const findingsData = await findingsResponse.json();
        
        // Update global state
        staticAnalysisData.clusters = clustersData.clusters || [];
        staticAnalysisData.findings = findingsData.findings || [];
        staticAnalysisData.stats = clustersData.stats || {};
        
        // Update UI
        displayStaticStats();
        
        if (staticAnalysisData.currentView === 'cluster') {
            displayStaticClusters();
        } else {
            displayStaticFindings();
        }
        
    } catch (error) {
        console.error('Error loading static analysis:', error);
        showError('Failed to load static analysis results');
    }
}

// ============================================================================
// Display statistics cards
// ============================================================================

function displayStaticStats() {
    const container = document.getElementById('static-stats-cards');
    const stats = staticAnalysisData.stats;
    
    const html = `
        <div class="stat-card">
            <div class="stat-number">${stats.total_findings || 0}</div>
            <div class="stat-label">Total Findings</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">${stats.unique_issues || 0}</div>
            <div class="stat-label">Unique Issues</div>
        </div>
        <div class="stat-card error">
            <div class="stat-number">${stats.by_severity?.error || 0}</div>
            <div class="stat-label">Errors</div>
        </div>
        <div class="stat-card warning">
            <div class="stat-number">${stats.by_severity?.warning || 0}</div>
            <div class="stat-label">Warnings</div>
        </div>
        <div class="stat-card info">
            <div class="stat-number">${stats.by_severity?.info || 0}</div>
            <div class="stat-label">Info</div>
        </div>
    `;
    
    container.innerHTML = html;
}

// ============================================================================
// Display clusters (grouped view)
// ============================================================================

function displayStaticClusters() {
    const container = document.getElementById('static-clusters-container');
    const clusters = staticAnalysisData.clusters;
    
    if (!clusters || clusters.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No static analysis results found</p>
                <p class="hint">Run static analysis on a task to see results here</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    
    clusters.forEach(cluster => {
        const severityClass = cluster.severity;
        const severityIcon = getSeverityIcon(cluster.severity);
        const fileName = cluster.file_paths[0].split('/').pop();
        
        html += `
            <div class="cluster-card ${severityClass}">
                <div class="cluster-header" onclick="toggleCluster('static-cluster-${cluster.cluster_id}')">
                    <div class="cluster-title">
                        ${severityIcon}
                        <span class="severity-badge ${severityClass}">${cluster.severity.toUpperCase()}</span>
                        <strong>${cluster.rule_id}</strong>
                        <span class="finding-count">${cluster.count} finding(s)</span>
                    </div>
                    <div class="cluster-meta">
                        <span>📄 ${fileName}:${cluster.line_number}</span>
                        <span>🔧 ${cluster.tool_names.join(', ')}</span>
                    </div>
                </div>
                
                <div class="cluster-body">
                    <div class="finding-message">${escapeHtml(cluster.message)}</div>
                    
                    <div class="cluster-details" id="static-cluster-${cluster.cluster_id}" style="display: none;">
                        <div class="detail-section">
                            <h4>📁 Affected Files</h4>
                            <ul>
                                ${cluster.file_paths.map(path => 
                                    `<li><code>${escapeHtml(path)}</code></li>`
                                ).join('')}
                            </ul>
                        </div>
                        
                        <div class="detail-section">
                            <h4>🔍 Individual Findings (${cluster.findings.length})</h4>
                            <table class="findings-table">
                                <thead>
                                    <tr>
                                        <th>Tool</th>
                                        <th>File</th>
                                        <th>Line</th>
                                        <th>Message</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${cluster.findings.map(f => `
                                        <tr onclick="showStaticFindingDetail(${f.id})">
                                            <td><span class="tool-badge">${f.tool_name}</span></td>
                                            <td><code>${f.file_path.split('/').pop()}</code></td>
                                            <td>${f.line_number}</td>
                                            <td>${escapeHtml(f.message.substring(0, 100))}${f.message.length > 100 ? '...' : ''}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    
                    <button class="view-details-btn" onclick="toggleCluster('static-cluster-${cluster.cluster_id}')">
                        View Details
                    </button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// ============================================================================
// Display all findings (list view)
// ============================================================================

function displayStaticFindings() {
    const container = document.getElementById('static-findings-list');
    const findings = staticAnalysisData.findings;
    
    if (!findings || findings.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No findings to display</p></div>';
        return;
    }
    
    // Group by file
    const byFile = {};
    findings.forEach(finding => {
        const fileName = finding.file_path.split('/').pop();
        if (!byFile[fileName]) {
            byFile[fileName] = [];
        }
        byFile[fileName].push(finding);
    });
    
    let html = '';
    
    Object.keys(byFile).sort().forEach(fileName => {
        const fileFindings = byFile[fileName];
        const errorCount = fileFindings.filter(f => f.severity === 'error').length;
        const warningCount = fileFindings.filter(f => f.severity === 'warning').length;
        const infoCount = fileFindings.filter(f => f.severity === 'info').length;
        
        html += `
            <div class="file-group">
                <div class="file-header" onclick="toggleFileGroup('${fileName}')">
                    <h3>📄 ${fileName}</h3>
                    <div class="file-stats">
                        ${errorCount > 0 ? `<span class="error">${errorCount} errors</span>` : ''}
                        ${warningCount > 0 ? `<span class="warning">${warningCount} warnings</span>` : ''}
                        ${infoCount > 0 ? `<span class="info">${infoCount} info</span>` : ''}
                    </div>
                </div>
                
                <div id="file-${fileName}" class="file-findings">
                    <table class="findings-table">
                        <thead>
                            <tr>
                                <th>Severity</th>
                                <th>Line</th>
                                <th>Tool</th>
                                <th>Rule</th>
                                <th>Message</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${fileFindings.map(f => `
                                <tr class="${f.severity}" onclick="showStaticFindingDetail(${f.id})">
                                    <td>
                                        ${getSeverityIcon(f.severity)}
                                        <span class="severity-badge ${f.severity}">${f.severity}</span>
                                    </td>
                                    <td><code>${f.line_number}</code></td>
                                    <td><span class="tool-badge">${f.tool_name}</span></td>
                                    <td><code>${f.rule_id}</code></td>
                                    <td>${escapeHtml(f.message)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// ============================================================================
// Show detailed view of a finding
// ============================================================================

function showStaticFindingDetail(findingId) {
    const finding = staticAnalysisData.findings.find(f => f.id === findingId);
    if (!finding) return;
    
    const severityIcon = getSeverityIcon(finding.severity);
    
    const html = `
        <div class="finding-detail">
            <h2>
                ${severityIcon}
                <span class="severity-badge ${finding.severity}">${finding.severity.toUpperCase()}</span>
                ${finding.rule_id}
            </h2>
            
            <div class="detail-grid">
                <div class="detail-item">
                    <strong>Tool:</strong>
                    <span class="tool-badge">${finding.tool_name}</span>
                </div>
                
                <div class="detail-item">
                    <strong>File:</strong>
                    <code>${finding.file_path}</code>
                </div>
                
                <div class="detail-item">
                    <strong>Location:</strong>
                    <code>Line ${finding.line_number}, Column ${finding.column}</code>
                </div>
                
                <div class="detail-item">
                    <strong>Found:</strong>
                    ${new Date(finding.created_at).toLocaleString()}
                </div>
            </div>
            
            <div class="message-section">
                <h3>Message</h3>
                <p>${escapeHtml(finding.message)}</p>
            </div>
            
            ${finding.code_snippet ? `
                <div class="code-section">
                    <h3>Code Snippet</h3>
                    <pre><code>${escapeHtml(finding.code_snippet)}</code></pre>
                </div>
            ` : ''}
            
            <div class="actions">
                <button onclick="copyToClipboard('${finding.file_path}:${finding.line_number}')">
                    📋 Copy Location
                </button>
                <button onclick="closeStaticFindingModal()">Close</button>
            </div>
        </div>
    `;
    
    document.getElementById('static-finding-detail').innerHTML = html;
    document.getElementById('static-finding-modal').style.display = 'block';
}

function closeStaticFindingModal() {
    document.getElementById('static-finding-modal').style.display = 'none';
}

// ============================================================================
// View toggle functions
// ============================================================================

function showStaticClusterView() {
    staticAnalysisData.currentView = 'cluster';
    document.getElementById('static-cluster-view').style.display = 'block';
    document.getElementById('static-list-view').style.display = 'none';
    document.getElementById('static-cluster-view-btn').classList.add('active');
    document.getElementById('static-list-view-btn').classList.remove('active');
    displayStaticClusters();
}

function showStaticListView() {
    staticAnalysisData.currentView = 'list';
    document.getElementById('static-cluster-view').style.display = 'none';
    document.getElementById('static-list-view').style.display = 'block';
    document.getElementById('static-cluster-view-btn').classList.remove('active');
    document.getElementById('static-list-view-btn').classList.add('active');
    displayStaticFindings();
}

// ============================================================================
// Helper functions
// ============================================================================

function getSeverityIcon(severity) {
    const icons = {
        'error': '🔴',
        'warning': '⚠️',
        'info': 'ℹ️'
    };
    return icons[severity] || '•';
}

function toggleCluster(clusterId) {
    const element = document.getElementById(clusterId);
    if (element) {
        element.style.display = element.style.display === 'none' ? 'block' : 'none';
    }
}

function toggleFileGroup(fileName) {
    const element = document.getElementById(`file-${fileName}`);
    if (element) {
        element.style.display = element.style.display === 'none' ? 'block' : 'none';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!');
    });
}

function showNotification(message) {
    // Simple notification - can be enhanced
    alert(message);
}

function showError(message) {
    console.error(message);
    // Show error in UI
}

// ============================================================================
// Initialize on page load
// ============================================================================

// Add this to your existing window.onload or initialization function:
/*
window.addEventListener('load', () => {
    loadStaticAnalysis();
});
*/
