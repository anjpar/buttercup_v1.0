# Buttercup Static Analysis Bot - Implementation Guide

## Overview

Your teammate's `concurrency` library is a task management framework for running async operations in parallel. To integrate static analysis into Buttercup, we'll create a new **Static Analysis Bot** that uses this library to efficiently run multiple static analysis tools concurrently across the codebase.

---

## Architecture Design

### Current Buttercup Bot Architecture
Based on your crash triage work, Buttercup has these bot types:
1. **Fuzzer Bot** - Runs fuzzers, finds crashes
2. **Tracer Bot** - Analyzes crashes, generates stack traces and dedup tokens

### New Bot: Static Analysis Bot
```
┌─────────────────┐
│  Scheduler      │ Assigns static analysis task
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Static Analysis │ Orchestrates analysis
│     Bot         │
└────────┬────────┘
         │
         ├─────────────────────────────────┐
         │                                 │
         ▼                                 ▼
┌─────────────────┐              ┌─────────────────┐
│ TaskManager #1  │              │ TaskManager #2  │
│ (Concurrency)   │              │ (Concurrency)   │
└────────┬────────┘              └────────┬────────┘
         │                                 │
         ├──────┬──────┬──────┐           ├──────┬──────┐
         ▼      ▼      ▼      ▼           ▼      ▼      ▼
      Tool1  Tool2  Tool3  Tool4       File1  File2  File3
     (clang  (cpp   (sema  (custom)
     -tidy) check) phore)
```

### Key Design Decisions

1. **Per-Tool TaskManagers**: Each static analysis tool gets its own TaskManager with appropriate concurrency limits
2. **File-Level Parallelism**: Each file in the codebase is analyzed as a separate task
3. **Result Aggregation**: All findings are collected, deduplicated, and stored in the database
4. **Integration Points**: Similar to fuzzer bot, but produces "findings" instead of "POVs"

---

## Implementation Plan

### Phase 1: Create Static Analysis Bot Structure

#### 1.1 Create Bot Directory
```bash
# In your Buttercup repository
mkdir -p static_analyzer/src/buttercup/static_analyzer
```

#### 1.2 File Structure
```
static_analyzer/
├── src/
│   └── buttercup/
│       └── static_analyzer/
│           ├── __init__.py
│           ├── analyzer_bot.py          # Main bot logic
│           ├── tools/
│           │   ├── __init__.py
│           │   ├── base_tool.py         # Abstract base class for tools
│           │   ├── clang_tidy.py        # clang-tidy integration
│           │   ├── cppcheck.py          # cppcheck integration
│           │   ├── semaphore.py         # semaphore integration
│           │   └── custom_checker.py    # Your custom checkers
│           ├── concurrency/             # Your teammate's library
│           │   ├── __init__.py
│           │   ├── manager.py
│           │   └── result.py
│           └── result_processor.py      # Dedup & aggregate results
├── Dockerfile
└── requirements.txt
```

---

### Phase 2: Implement Core Components

#### 2.1 Base Tool Interface (`tools/base_tool.py`)

```python
"""Base class for static analysis tools."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Finding:
    """Represents a single static analysis finding."""
    tool_name: str
    file_path: str
    line_number: int
    column: int
    severity: str  # 'error', 'warning', 'info'
    message: str
    rule_id: str
    code_snippet: str | None = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'tool_name': self.tool_name,
            'file_path': str(self.file_path),
            'line_number': self.line_number,
            'column': self.column,
            'severity': self.severity,
            'message': self.message,
            'rule_id': self.rule_id,
            'code_snippet': self.code_snippet,
        }


class StaticAnalysisTool(ABC):
    """Abstract base class for static analysis tools."""
    
    def __init__(self, name: str, max_concurrent: int = 10, timeout: float = 60.0):
        """Initialize the tool.
        
        Args:
            name: Tool name (e.g., 'clang-tidy')
            max_concurrent: Max concurrent file analyses
            timeout: Timeout per file in seconds
        """
        self.name = name
        self.max_concurrent = max_concurrent
        self.timeout = timeout
    
    @abstractmethod
    async def analyze_file(self, file_path: Path, repo_path: Path) -> List[Finding]:
        """Analyze a single file and return findings.
        
        Args:
            file_path: Path to the file to analyze
            repo_path: Root path of the repository
            
        Returns:
            List of Finding objects
        """
        pass
    
    @abstractmethod
    def is_applicable(self, file_path: Path) -> bool:
        """Check if this tool can analyze the given file.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if tool can analyze this file type
        """
        pass
```

#### 2.2 Example Tool: clang-tidy (`tools/clang_tidy.py`)

```python
"""clang-tidy static analysis tool integration."""

import asyncio
import re
from pathlib import Path
from typing import List

from .base_tool import StaticAnalysisTool, Finding


class ClangTidyTool(StaticAnalysisTool):
    """Integration with clang-tidy static analyzer."""
    
    def __init__(self, checks: str = "bugprone-*,cert-*,clang-analyzer-*"):
        """Initialize clang-tidy.
        
        Args:
            checks: Comma-separated list of checks to enable
        """
        super().__init__(name="clang-tidy", max_concurrent=5, timeout=120.0)
        self.checks = checks
    
    def is_applicable(self, file_path: Path) -> bool:
        """Check if file is C/C++ source."""
        return file_path.suffix in ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp']
    
    async def analyze_file(self, file_path: Path, repo_path: Path) -> List[Finding]:
        """Run clang-tidy on a single file."""
        findings = []
        
        try:
            # Build clang-tidy command
            cmd = [
                'clang-tidy',
                f'--checks={self.checks}',
                '--format-style=file',
                str(file_path),
                '--',
                '-I', str(repo_path / 'include'),  # Adjust as needed
            ]
            
            # Run clang-tidy
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout
            )
            
            # Parse output
            output = stdout.decode('utf-8', errors='ignore')
            findings = self._parse_output(output, file_path)
            
        except asyncio.TimeoutError:
            print(f"clang-tidy timeout on {file_path}")
        except Exception as e:
            print(f"clang-tidy error on {file_path}: {e}")
        
        return findings
    
    def _parse_output(self, output: str, file_path: Path) -> List[Finding]:
        """Parse clang-tidy output into Finding objects."""
        findings = []
        
        # clang-tidy format: file:line:column: severity: message [rule-id]
        pattern = r'(.+?):(\d+):(\d+):\s+(error|warning|note):\s+(.+?)\s+\[([^\]]+)\]'
        
        for match in re.finditer(pattern, output):
            _, line, col, severity, message, rule_id = match.groups()
            
            findings.append(Finding(
                tool_name=self.name,
                file_path=str(file_path),
                line_number=int(line),
                column=int(col),
                severity=severity,
                message=message.strip(),
                rule_id=rule_id.strip(),
            ))
        
        return findings
```

#### 2.3 Main Analyzer Bot (`analyzer_bot.py`)

```python
"""Static Analysis Bot - orchestrates static analysis tools."""

import asyncio
from pathlib import Path
from typing import List, Dict, Any
import logging

from buttercup.static_analyzer.concurrency import TaskManager, TaskResult
from buttercup.static_analyzer.tools.base_tool import StaticAnalysisTool, Finding
from buttercup.static_analyzer.tools.clang_tidy import ClangTidyTool
from buttercup.static_analyzer.tools.cppcheck import CppCheckTool
# Import other tools as needed


logger = logging.getLogger(__name__)


class StaticAnalyzerBot:
    """Bot that runs static analysis tools on a repository."""
    
    def __init__(self, repo_path: Path, task_id: str):
        """Initialize the analyzer bot.
        
        Args:
            repo_path: Path to the repository to analyze
            task_id: Buttercup task ID for tracking
        """
        self.repo_path = Path(repo_path)
        self.task_id = task_id
        self.tools: List[StaticAnalysisTool] = []
        
        # Initialize tools
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize all available static analysis tools."""
        self.tools = [
            ClangTidyTool(checks="bugprone-*,cert-*,clang-analyzer-*,cppcoreguidelines-*"),
            CppCheckTool(enable="all"),
            # Add more tools here
        ]
        logger.info(f"Initialized {len(self.tools)} static analysis tools")
    
    def _discover_files(self) -> List[Path]:
        """Discover all source files in the repository."""
        source_extensions = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx'}
        files = []
        
        for ext in source_extensions:
            files.extend(self.repo_path.rglob(f'*{ext}'))
        
        logger.info(f"Discovered {len(files)} source files")
        return files
    
    async def analyze(self) -> Dict[str, Any]:
        """Run all static analysis tools on the repository.
        
        Returns:
            Dictionary with analysis results and statistics
        """
        start_time = asyncio.get_event_loop().time()
        
        # Discover files
        files = self._discover_files()
        
        if not files:
            logger.warning("No source files found")
            return {
                'task_id': self.task_id,
                'status': 'no_files',
                'findings': [],
                'stats': {}
            }
        
        # Analyze files with each tool
        all_findings = []
        tool_stats = {}
        
        for tool in self.tools:
            logger.info(f"Running {tool.name} on {len(files)} files...")
            
            # Filter files applicable to this tool
            applicable_files = [f for f in files if tool.is_applicable(f)]
            
            if not applicable_files:
                logger.info(f"No applicable files for {tool.name}")
                continue
            
            # Create TaskManager for this tool
            manager = TaskManager(
                max_concurrent=tool.max_concurrent,
                timeout=tool.timeout
            )
            
            # Add analysis tasks
            for file_path in applicable_files:
                manager.add_task(tool.analyze_file(file_path, self.repo_path))
            
            # Run all tasks for this tool
            results = await manager.run_async()
            
            # Collect findings
            tool_findings = []
            success_count = 0
            error_count = 0
            
            for result in results:
                if result.success:
                    success_count += 1
                    tool_findings.extend(result.value)
                else:
                    error_count += 1
                    logger.error(f"{tool.name} error: {result.error}")
            
            all_findings.extend(tool_findings)
            
            tool_stats[tool.name] = {
                'files_analyzed': len(applicable_files),
                'successful': success_count,
                'errors': error_count,
                'findings': len(tool_findings),
            }
            
            logger.info(f"{tool.name}: {len(tool_findings)} findings from {success_count}/{len(applicable_files)} files")
        
        # Deduplicate findings
        unique_findings = self._deduplicate_findings(all_findings)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        
        return {
            'task_id': self.task_id,
            'status': 'success',
            'findings': [f.to_dict() for f in unique_findings],
            'stats': {
                'total_files': len(files),
                'total_findings': len(all_findings),
                'unique_findings': len(unique_findings),
                'tools': tool_stats,
                'elapsed_seconds': elapsed,
            }
        }
    
    def _deduplicate_findings(self, findings: List[Finding]) -> List[Finding]:
        """Remove duplicate findings based on file, line, and rule_id."""
        seen = set()
        unique = []
        
        for finding in findings:
            # Create dedup key
            key = (finding.file_path, finding.line_number, finding.rule_id)
            
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        
        logger.info(f"Deduplicated {len(findings)} -> {len(unique)} findings")
        return unique


async def main():
    """Entry point for the static analyzer bot."""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: analyzer_bot.py <repo_path> <task_id>")
        sys.exit(1)
    
    repo_path = Path(sys.argv[1])
    task_id = sys.argv[2]
    
    bot = StaticAnalyzerBot(repo_path, task_id)
    results = await bot.analyze()
    
    # Submit results to Buttercup
    # TODO: Implement submission logic similar to fuzzer_bot.py
    print(f"Analysis complete: {results['stats']}")
    print(f"Found {results['stats']['unique_findings']} unique issues")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### Phase 3: Database Schema Updates

Add a new table for static analysis findings (similar to POV table):

```python
# In orchestrator/src/buttercup/orchestrator/ui/database.py

class StaticAnalysisFinding(Base):
    """Static analysis finding from analyzer bot."""
    __tablename__ = "static_analysis_findings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=False)
    column = Column(Integer, nullable=False)
    severity = Column(String, nullable=False)  # 'error', 'warning', 'info'
    message = Column(Text, nullable=False)
    rule_id = Column(String, nullable=False)
    code_snippet = Column(Text, nullable=True)
    
    # Deduplication token (similar to crash dedup)
    dedup_token = Column(String, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Foreign key
    task = relationship("Task", back_populates="static_findings")


# Update Task model to add relationship
class Task(Base):
    # ... existing fields ...
    static_findings = relationship("StaticAnalysisFinding", back_populates="task")
```

---

### Phase 4: API Endpoints

Add endpoints to expose static analysis results:

```python
# In orchestrator/src/buttercup/orchestrator/ui/competition_api/main.py

@app.get("/v1/dashboard/static_findings")
def get_static_findings(
    task_id: str | None = None,
    tool_name: str | None = None,
    severity: str | None = None,
    database_manager: DatabaseManager = Depends(get_database_manager)
) -> dict[str, Any]:
    """Get static analysis findings with optional filtering."""
    session = database_manager.get_session()
    
    query = session.query(StaticAnalysisFinding)
    
    if task_id:
        query = query.filter(StaticAnalysisFinding.task_id == task_id)
    if tool_name:
        query = query.filter(StaticAnalysisFinding.tool_name == tool_name)
    if severity:
        query = query.filter(StaticAnalysisFinding.severity == severity)
    
    findings = query.order_by(
        StaticAnalysisFinding.severity.desc(),
        StaticAnalysisFinding.created_at.desc()
    ).all()
    
    return {
        "findings": [
            {
                "id": f.id,
                "task_id": f.task_id,
                "tool_name": f.tool_name,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "severity": f.severity,
                "message": f.message,
                "rule_id": f.rule_id,
            }
            for f in findings
        ],
        "total": len(findings),
    }


@app.get("/v1/dashboard/static_clusters")
def get_static_clusters(
    task_id: str | None = None,
    database_manager: DatabaseManager = Depends(get_database_manager)
) -> dict[str, Any]:
    """Get clustered static analysis findings (similar to crash clusters)."""
    session = database_manager.get_session()
    
    # Group by dedup_token
    # Similar logic to crash clustering
    # ...
```

---

### Phase 5: Frontend Integration

Add a new "Static Analysis" tab to the UI:

```javascript
// In orchestrator/src/buttercup/orchestrator/ui/static/script.js

async function loadStaticFindings(taskId = null) {
    let url = '/v1/dashboard/static_findings';
    if (taskId) {
        url += `?task_id=${taskId}`;
    }
    
    const response = await fetch(url);
    const data = await response.json();
    
    displayStaticFindings(data.findings);
}

function displayStaticFindings(findings) {
    const container = document.getElementById('static-findings-container');
    
    // Group by severity
    const grouped = {
        error: findings.filter(f => f.severity === 'error'),
        warning: findings.filter(f => f.severity === 'warning'),
        info: findings.filter(f => f.severity === 'info'),
    };
    
    let html = `
        <div class="stats-cards">
            <div class="stat-card error">
                <h3>${grouped.error.length}</h3>
                <p>Errors</p>
            </div>
            <div class="stat-card warning">
                <h3>${grouped.warning.length}</h3>
                <p>Warnings</p>
            </div>
            <div class="stat-card info">
                <h3>${grouped.info.length}</h3>
                <p>Info</p>
            </div>
        </div>
    `;
    
    // Display findings grouped by file
    // ...
    
    container.innerHTML = html;
}
```

---

### Phase 6: Kubernetes Deployment

#### 6.1 Dockerfile

```dockerfile
# static_analyzer/Dockerfile
FROM python:3.11-slim

# Install static analysis tools
RUN apt-get update && apt-get install -y \
    clang-tidy \
    cppcheck \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ /app/

ENV PYTHONPATH=/app

CMD ["python", "-m", "buttercup.static_analyzer.analyzer_bot"]
```

#### 6.2 Kubernetes Deployment

```yaml
# deployment/k8s/templates/static-analyzer-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: buttercup-static-analyzer
  namespace: {{ .Values.namespace }}
spec:
  replicas: {{ .Values.staticAnalyzer.replicas }}
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
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: buttercup-secrets
              key: DATABASE_URL
        - name: MAX_CONCURRENT_FILES
          value: "10"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

---

## Usage Examples

### Example 1: Analyze a Repository

```python
from buttercup.static_analyzer.analyzer_bot import StaticAnalyzerBot
from pathlib import Path

# Create bot
bot = StaticAnalyzerBot(
    repo_path=Path("/path/to/repo"),
    task_id="task-123"
)

# Run analysis
results = await bot.analyze()

print(f"Found {results['stats']['unique_findings']} issues")
for tool_name, stats in results['stats']['tools'].items():
    print(f"{tool_name}: {stats['findings']} findings")
```

### Example 2: Add a Custom Tool

```python
# In tools/custom_checker.py
from .base_tool import StaticAnalysisTool, Finding

class CustomSecurityChecker(StaticAnalysisTool):
    def __init__(self):
        super().__init__(name="custom-security", max_concurrent=20)
    
    def is_applicable(self, file_path: Path) -> bool:
        return file_path.suffix in ['.c', '.cpp']
    
    async def analyze_file(self, file_path: Path, repo_path: Path) -> List[Finding]:
        findings = []
        
        # Read file
        content = file_path.read_text()
        
        # Check for dangerous functions
        dangerous = ['strcpy', 'strcat', 'sprintf', 'gets']
        for line_num, line in enumerate(content.splitlines(), 1):
            for func in dangerous:
                if func in line:
                    findings.append(Finding(
                        tool_name=self.name,
                        file_path=str(file_path),
                        line_number=line_num,
                        column=line.find(func),
                        severity='warning',
                        message=f'Dangerous function {func} detected',
                        rule_id='SEC-001',
                    ))
        
        return findings
```

---

## Key Benefits of Using Concurrency Library

1. **Efficient Parallelism**: Analyze multiple files simultaneously with configurable concurrency
2. **Error Isolation**: One file failure doesn't affect others
3. **Tool Isolation**: Each tool gets its own TaskManager with appropriate limits
4. **Timeout Handling**: Automatic timeout for stuck analyses
5. **Result Tracking**: Easy to track success/failure rates per tool

---

## Testing Plan

### Unit Tests
```python
import pytest
from pathlib import Path
from buttercup.static_analyzer.tools.clang_tidy import ClangTidyTool

@pytest.mark.asyncio
async def test_clang_tidy_basic():
    tool = ClangTidyTool()
    
    # Create test file
    test_file = Path("/tmp/test.c")
    test_file.write_text("""
    int main() {
        int x = 0;
        return 0;
    }
    """)
    
    findings = await tool.analyze_file(test_file, Path("/tmp"))
    
    assert isinstance(findings, list)
```

### Integration Tests
```bash
# Test with DVCP repository
curl -X POST http://localhost:1323/webhook/trigger_static_analysis \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "static-test-1",
    "repo_url": "https://github.com/anjpar/dvcp-safe-and-vulnerable.git",
    "repo_ref": "vulnerable"
  }'
```

---

## Performance Considerations

### Concurrency Tuning
- **clang-tidy**: Heavy CPU usage, max_concurrent=5
- **cppcheck**: Moderate CPU, max_concurrent=10
- **Custom checkers**: Lightweight, max_concurrent=20

### Scaling
```bash
# Scale static analyzer pods
kubectl -n crs scale deployment buttercup-static-analyzer --replicas=3

# Each pod can analyze different repositories concurrently
```

---

## Next Steps

1. **Implement Phase 1-2**: Create bot structure and core components
2. **Test locally**: Run on DVCP repo to validate
3. **Add more tools**: Integrate semaphore, custom checkers
4. **Frontend work**: Build static analysis UI tab
5. **Deploy to K8s**: Add to your cluster
6. **Demo**: Show manager the findings dashboard

---

## Comparison: Fuzzing vs Static Analysis

| Aspect | Fuzzing | Static Analysis |
|--------|---------|----------------|
| Bot Type | Fuzzer Bot | Static Analyzer Bot |
| Output | POVs (crashes) | Findings (warnings/errors) |
| Database Table | `povs` | `static_analysis_findings` |
| Dedup | Stack trace hash | file+line+rule_id |
| UI Tab | "POVs & Crash Analysis" | "Static Analysis" |
| Clustering | By dedup_token | By dedup_token |
| AI Analysis | GPT-4o security analysis | Optional: GPT-4o code review |

---

## Questions to Answer

1. **Which tools to prioritize?** Start with clang-tidy, cppcheck, then add custom
2. **How to handle false positives?** Add filtering/suppression config
3. **Integration with fuzzing?** Can cross-reference static warnings with crash locations
4. **AI enhancement?** Could use GPT-4o to explain/triage findings (similar to crash analysis)

---

## Additional Resources

- Your teammate's concurrency library: Use TaskManager for parallel execution
- Buttercup fuzzer bot: Similar pattern for task submission/result storage
- Crash triage implementation: Reuse UI patterns for clustering/analysis

---

**Status**: Design Complete ✅  
**Next**: Implement Phase 1 and test locally
