# Buttercup Static Analysis Integration Guide

Complete step-by-step guide to integrate static analysis into your Buttercup deployment.

## Overview

This integration adds a new "Static Analysis" tab to your Buttercup UI, similar to your crash triage dashboard. It includes:

1. **Backend**: Database schema + API endpoints
2. **Frontend**: New UI tab with cluster and list views
3. **Bot Integration**: Updated analyzer bot that submits to Buttercup API

---

## Step 1: Update Database Schema

### Option A: Using Alembic (Recommended)

```bash
cd /datadrive/repos/buttercup/orchestrator

# Create migration
alembic revision --autogenerate -m "Add static analysis findings table"

# Review the migration file in alembic/versions/

# Apply migration
alembic upgrade head
```

### Option B: Manual SQL (if not using Alembic)

```bash
# Connect to your database
sqlite3 /path/to/buttercup.db  # or your PostgreSQL connection

# Run this SQL:
```

```sql
CREATE TABLE static_analysis_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR NOT NULL,
    tool_name VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    line_number INTEGER NOT NULL,
    column INTEGER NOT NULL,
    severity VARCHAR NOT NULL,
    message TEXT NOT NULL,
    rule_id VARCHAR NOT NULL,
    code_snippet TEXT,
    dedup_token VARCHAR,
    created_at DATETIME
);

CREATE INDEX idx_saf_task_id ON static_analysis_findings(task_id);
CREATE INDEX idx_saf_tool_name ON static_analysis_findings(tool_name);
CREATE INDEX idx_saf_severity ON static_analysis_findings(severity);
CREATE INDEX idx_saf_rule_id ON static_analysis_findings(rule_id);
CREATE INDEX idx_saf_dedup_token ON static_analysis_findings(dedup_token);
CREATE INDEX idx_saf_created_at ON static_analysis_findings(created_at);
```

### Update database.py

```bash
cd /datadrive/repos/buttercup
nano orchestrator/src/buttercup/orchestrator/ui/database.py
```

Add the class definition from `backend/database_schema.py`:

```python
# At the end of database.py, add:

class StaticAnalysisFinding(Base):
    """Static analysis finding from analyzer bot."""
    __tablename__ = "static_analysis_findings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=False)
    column = Column(Integer, nullable=False)
    severity = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    rule_id = Column(String, nullable=False, index=True)
    code_snippet = Column(Text, nullable=True)
    dedup_token = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    task = relationship("Task", back_populates="static_findings")
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'tool_name': self.tool_name,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'column': self.column,
            'severity': self.severity,
            'message': self.message,
            'rule_id': self.rule_id,
            'code_snippet': self.code_snippet,
            'dedup_token': self.dedup_token,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

def generate_static_analysis_dedup_token(file_path: str, line_number: int, rule_id: str) -> str:
    """Generate deduplication token for static analysis findings."""
    import hashlib
    from pathlib import Path
    
    filename = Path(file_path).name
    dedup_string = f"{filename}:{line_number}:{rule_id}"
    token = hashlib.sha256(dedup_string.encode()).hexdigest()[:16]
    return f"static-{token}"

# Also update the Task class to add:
# static_findings = relationship("StaticAnalysisFinding", back_populates="task")
```

---

## Step 2: Add API Endpoints

```bash
cd /datadrive/repos/buttercup
nano orchestrator/src/buttercup/orchestrator/ui/competition_api/main.py
```

Add the endpoints from `backend/api_endpoints.py`. Insert them after your existing POV endpoints:

```python
# Add all four endpoints:
# 1. get_static_findings()
# 2. get_static_clusters()
# 3. get_static_analysis_summary()
# 4. submit_static_analysis_results()
```

**Important**: Make sure to import the necessary dependencies at the top:

```python
from collections import defaultdict
from buttercup.orchestrator.ui.database import (
    StaticAnalysisFinding,
    generate_static_analysis_dedup_token
)
```

---

## Step 3: Update Frontend

### 3.1 Update HTML

```bash
cd /datadrive/repos/buttercup
nano orchestrator/src/buttercup/orchestrator/ui/static/index.html
```

Add the new tab button in the tab bar (copy from `frontend/html_updates.html`):

```html
<!-- After the "POVs & Crash Analysis" tab button: -->
<div class="tab-button" onclick="switchTab('static-analysis')">
    <span>🔍</span>
    <span>Static Analysis</span>
</div>
```

Then add the tab content section (copy the entire section from `frontend/html_updates.html`).

### 3.2 Update JavaScript

```bash
nano orchestrator/src/buttercup/orchestrator/ui/static/script.js
```

Append all the JavaScript functions from `frontend/javascript_updates.js`.

Also update your existing `switchTab()` function to include the new tab:

```javascript
function switchTab(tabName) {
    // ... existing tab handling ...
    
    if (tabName === 'static-analysis') {
        loadStaticAnalysis();
    }
}
```

### 3.3 Update CSS

```bash
nano orchestrator/src/buttercup/orchestrator/ui/static/styles.css
```

Append all the CSS from `frontend/css_updates.css` to the end of the file.

---

## Step 4: Update Analyzer Bot

### 4.1 Copy Updated Bot

```bash
cd /datadrive/repos/buttercup/sca_implement/static_analyzer_implementation

# Backup original
cp analyzer_bot.py analyzer_bot.py.backup

# Add the submission functions
nano analyzer_bot.py
```

Add the `submit_to_buttercup()` method from `backend/analyzer_bot_updated.py` to the `StaticAnalyzerBot` class.

Update the `main()` function to support API submission.

### 4.2 Install aiohttp (for API submissions)

```bash
pip install aiohttp
```

Or add to your requirements.txt:

```bash
echo "aiohttp>=3.9.0" >> requirements.txt
pip install -r requirements.txt
```

---

## Step 5: Deploy and Test

### 5.1 Redeploy Buttercup

```bash
cd /datadrive/repos/buttercup

# If using Kubernetes:
make undeploy
make deploy

# Verify UI is running
kubectl port-forward -n crs svc/buttercup-ui 1323:1323

# Or if running locally:
# Restart your UI server
```

### 5.2 Run Test Analysis

```bash
cd /datadrive/repos/buttercup/sca_implement/static_analyzer_implementation

# Run analyzer with API submission
python3 analyzer_bot.py /datadrive/repos/dvcp-safe-and-vulnerable test-integration-1

# Check that it submits successfully
# You should see: "✓ Results submitted to http://localhost:1323"
```

### 5.3 Verify in UI

1. Open browser: http://localhost:1323
2. Click on "🔍 Static Analysis" tab
3. You should see:
   - Statistics cards showing findings
   - Cluster view with grouped issues
   - Ability to toggle to list view
   - Click on findings to see details

---

## Step 6: Create Kubernetes Deployment (Optional)

If you want to run the analyzer bot as a Kubernetes deployment:

### 6.1 Create Dockerfile

```bash
cd /datadrive/repos/buttercup
mkdir -p static_analyzer
nano static_analyzer/Dockerfile
```

```dockerfile
FROM python:3.11-slim

# Install static analysis tools
RUN apt-get update && apt-get install -y \
    clang-tidy \
    cppcheck \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy analyzer code
COPY static_analyzer_implementation/ /app/

# Install Python dependencies
RUN pip install --no-cache-dir aiohttp

ENV PYTHONPATH=/app

# Entry point
CMD ["python3", "analyzer_bot.py"]
```

### 6.2 Create Kubernetes Deployment

```bash
nano deployment/k8s/templates/static-analyzer-deployment.yaml
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: buttercup-static-analyzer
  namespace: {{ .Values.namespace }}
spec:
  replicas: {{ .Values.staticAnalyzer.replicas | default 1 }}
  selector:
    matchLabels:
      app: static-analyzer
  template:
    metadata:
      labels:
        app: static-analyzer
    spec:
      containers:
      - name: static-analyzer
        image: {{ .Values.staticAnalyzer.image }}
        env:
        - name: BUTTERCUP_API_URL
          value: "http://buttercup-ui:1323"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: buttercup-secrets
              key: DATABASE_URL
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        volumeMounts:
        - name: repos
          mountPath: /repos
      volumes:
      - name: repos
        persistentVolumeClaim:
          claimName: buttercup-repos
```

### 6.3 Build and Deploy

```bash
# Build image
cd /datadrive/repos/buttercup
docker build -t buttercup-static-analyzer:latest -f static_analyzer/Dockerfile .

# Deploy
kubectl apply -f deployment/k8s/templates/static-analyzer-deployment.yaml
```

---

## Usage Examples

### Example 1: Manual Analysis

```bash
# Analyze a repository
python3 analyzer_bot.py /path/to/repo task-manual-1

# Results automatically submitted to UI
```

### Example 2: Automated Analysis (in Buttercup workflow)

```bash
# Create a task that runs both fuzzing and static analysis
# This can be integrated into your task submission workflow
```

### Example 3: Filter Results in UI

1. Open UI: http://localhost:1323
2. Go to Static Analysis tab
3. Use filters:
   - Filter by task
   - Filter by severity (errors only)
   - Filter by tool (clang-tidy only)
4. Toggle between cluster and list views

### Example 4: Export Results

You can add an export button to download findings as JSON/CSV:

```javascript
// Add to script.js
function exportStaticFindings() {
    const data = staticAnalysisData.findings;
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'static_analysis_results.json';
    a.click();
}
```

---

## Troubleshooting

### Issue: "Table does not exist"

**Solution**: Make sure you ran the database migration:

```bash
cd orchestrator
alembic upgrade head
```

### Issue: "API endpoint not found"

**Solution**: Verify the endpoints are added to main.py and UI is restarted:

```bash
# Check logs
kubectl logs -n crs -l app=ui --tail=50

# Look for route registration messages
```

### Issue: "Results not showing in UI"

**Solution**: Check browser console for JavaScript errors:

1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for errors in `loadStaticAnalysis()`

Also verify the API is returning data:

```bash
# Test API directly
curl http://localhost:1323/v1/dashboard/static_findings | jq
```

### Issue: "Bot submission fails"

**Solution**: Check that UI is accessible from bot:

```bash
# Test connectivity
curl http://localhost:1323/v1/dashboard/tasks

# Check bot logs for error details
```

---

## Testing Checklist

- [ ] Database table created
- [ ] API endpoints responding
- [ ] UI tab visible
- [ ] Statistics cards showing
- [ ] Cluster view working
- [ ] List view working
- [ ] Finding detail modal opens
- [ ] Filters working (task, severity, tool)
- [ ] Bot can submit results
- [ ] Results appear in UI
- [ ] No JavaScript errors in console
- [ ] Mobile responsive (optional)

---

## Performance Considerations

### Database Indexes

The schema includes indexes on frequently queried columns:
- `task_id`, `tool_name`, `severity`, `rule_id`, `dedup_token`, `created_at`

### API Pagination

For large result sets, consider adding pagination:

```python
@app.get("/v1/dashboard/static_findings")
def get_static_findings(
    limit: int = 100,
    offset: int = 0,
    ...
):
    query = query.limit(limit).offset(offset)
```

### Frontend Optimization

For thousands of findings, consider:
- Virtual scrolling
- Lazy loading clusters
- Server-side filtering

---

## Next Steps

### Enhancement Ideas

1. **AI Analysis Integration**
   - Similar to your crash triage, add GPT-4 analysis of findings
   - Generate fix suggestions
   - Prioritize issues by exploitability

2. **Cross-Reference with Fuzzing**
   - Show static warnings at crash locations
   - Highlight if static analysis predicted a crash

3. **Trend Analysis**
   - Track findings over time
   - Show if code quality is improving

4. **Automatic Fixes**
   - Generate patches for simple issues
   - Create pull requests automatically

5. **Integration with CI/CD**
   - Run static analysis on every commit
   - Block PRs with critical findings

---

## Files Modified

Summary of all files you need to modify:

```
buttercup/
├── orchestrator/src/buttercup/orchestrator/
│   ├── ui/
│   │   ├── database.py                    [ADD: StaticAnalysisFinding class]
│   │   └── competition_api/
│   │       └── main.py                    [ADD: 4 new endpoints]
│   └── static/
│       ├── index.html                     [ADD: New tab + content]
│       ├── script.js                      [ADD: JS functions]
│       └── styles.css                     [ADD: CSS styles]
└── static_analyzer_implementation/
    └── analyzer_bot.py                     [UPDATE: Add submission]
```

---

## Support

If you encounter issues:

1. Check the logs:
   ```bash
   kubectl logs -n crs -l app=ui --tail=100
   ```

2. Verify database:
   ```bash
   # Check table exists
   sqlite3 buttercup.db ".tables"
   
   # Check for data
   sqlite3 buttercup.db "SELECT COUNT(*) FROM static_analysis_findings;"
   ```

3. Test API:
   ```bash
   curl http://localhost:1323/v1/dashboard/static_findings
   ```

---

**Status**: Ready for Integration ✅  
**Estimated Time**: 1-2 hours  
**Difficulty**: Medium (similar to crash triage integration)
