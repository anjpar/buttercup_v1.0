# Static Analyzer Bot Implementation

A static analysis bot for Buttercup that uses your teammate's concurrency library to efficiently run multiple static analysis tools in parallel.

## Quick Start

### 1. Test Locally

```bash
# Run the test script (creates a sample repo with bugs)
python test_analyzer.py
```

This will:
- Create a temporary repository with intentional bugs
- Run all configured analyzers
- Show detailed findings

### 2. Analyze a Real Repository

```bash
# Analyze your DVCP vulnerable branch
python analyzer_bot.py /path/to/dvcp-safe-and-vulnerable test-dvcp-1
```

### 3. Analyze Your lwIP Port

```bash
# Analyze the lwIP code you've been fuzzing
python analyzer_bot.py /path/to/lwip-buttercup test-lwip-1
```

## Architecture

```
StaticAnalyzerBot
├── Discovers source files (.c, .cpp, .h, etc.)
├── For each tool (ClangTidy, CppCheck, CustomSecurity):
│   ├── Creates TaskManager with tool-specific concurrency
│   ├── Filters applicable files
│   └── Runs analysis tasks in parallel
└── Deduplicates and aggregates findings
```

### Key Features

1. **Concurrent Analysis**: Uses TaskManager to run multiple files in parallel
2. **Multiple Tools**: Integrates clang-tidy, cppcheck, and custom checkers
3. **Error Isolation**: One file error doesn't stop the whole analysis
4. **Deduplication**: Removes duplicate findings across tools
5. **Configurable Concurrency**: Each tool has appropriate limits

## Tools Included

### 1. clang-tidy
- **Purpose**: Comprehensive C/C++ static analysis
- **Checks**: bugprone, cert, clang-analyzer, cppcoreguidelines, performance
- **Concurrency**: 5 files at a time (CPU intensive)
- **Timeout**: 120 seconds per file

### 2. cppcheck
- **Purpose**: Additional C/C++ static analysis
- **Checks**: All enabled
- **Concurrency**: 10 files at a time
- **Timeout**: 60 seconds per file

### 3. Custom Security Checker
- **Purpose**: Pattern-based security vulnerability detection
- **Checks**: Dangerous functions (strcpy, sprintf, gets, etc.), unsafe patterns
- **Concurrency**: 20 files at a time (very fast)
- **Timeout**: 10 seconds per file

## Directory Structure

```
static_analyzer_implementation/
├── analyzer_bot.py           # Main bot orchestrator
├── test_analyzer.py          # Test script with sample code
├── requirements.txt          # Python dependencies (minimal)
├── tools/
│   ├── __init__.py
│   ├── base_tool.py          # Abstract base class
│   ├── clang_tidy.py         # clang-tidy integration
│   ├── cppcheck.py           # cppcheck integration
│   └── custom_security.py    # Custom vulnerability checker
└── concurrency/              # Your teammate's library
    ├── __init__.py
    ├── manager.py            # TaskManager
    └── result.py             # TaskResult
```

## How Concurrency Library is Used

### Per-Tool TaskManagers

Each static analysis tool gets its own TaskManager:

```python
# clang-tidy: Heavy CPU usage, limit to 5 concurrent
clang_manager = TaskManager(max_concurrent=5, timeout=120.0)

# cppcheck: Moderate, can handle 10
cpp_manager = TaskManager(max_concurrent=10, timeout=60.0)

# Custom checker: Lightweight, run 20 at once
custom_manager = TaskManager(max_concurrent=20, timeout=10.0)
```

### File-Level Parallelism

Each file is analyzed as a separate async task:

```python
for file_path in applicable_files:
    manager.add_task(tool.analyze_file(file_path, repo_path))

results = await manager.run_async()
```

### Benefits

1. **Efficient Resource Usage**: CPU-heavy tools run with lower concurrency
2. **Fast Lightweight Tools**: Pattern matchers run with high concurrency
3. **Error Isolation**: One file timeout doesn't affect others
4. **Easy Scaling**: Just change max_concurrent parameter

## Adding New Tools

### Example: Add Semaphore

```python
# In tools/semaphore.py
from .base_tool import StaticAnalysisTool, Finding

class SemaphoreTool(StaticAnalysisTool):
    def __init__(self):
        super().__init__(name="semaphore", max_concurrent=10, timeout=60.0)
    
    def is_applicable(self, file_path: Path) -> bool:
        return file_path.suffix in ['.c', '.cpp']
    
    async def analyze_file(self, file_path: Path, repo_path: Path) -> List[Finding]:
        # Run semaphore and parse output
        # ...
        return findings
```

Then add to `analyzer_bot.py`:

```python
from tools import SemaphoreTool

self.tools = [
    ClangTidyTool(...),
    CppCheckTool(...),
    CustomSecurityChecker(),
    SemaphoreTool(),  # NEW!
]
```

## Integration with Buttercup

### Database Schema

Add to your Buttercup database:

```python
class StaticAnalysisFinding(Base):
    __tablename__ = "static_analysis_findings"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=False)
    column = Column(Integer, nullable=False)
    severity = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    rule_id = Column(String, nullable=False)
    dedup_token = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### API Endpoint

```python
@app.get("/v1/dashboard/static_findings")
def get_static_findings(task_id: str | None = None):
    # Query StaticAnalysisFinding table
    # Group by dedup_token for clustering
    # Return findings with stats
    ...
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: buttercup-static-analyzer
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: static-analyzer
        image: buttercup-static-analyzer:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: buttercup-secrets
              key: DATABASE_URL
```

## Performance Tuning

### Concurrency Guidelines

| Tool | Type | Recommended max_concurrent |
|------|------|---------------------------|
| clang-tidy | CPU-heavy | 5-10 |
| cppcheck | Moderate | 10-20 |
| Custom checkers | Lightweight | 20-50 |
| Semaphore | API-based | 5-10 (rate limits) |

### Timeout Guidelines

- Simple tools: 10-30 seconds
- Complex analysis: 60-120 seconds
- Large files: Increase timeout proportionally

### Scaling

```bash
# Scale analyzer pods
kubectl -n crs scale deployment buttercup-static-analyzer --replicas=5

# Each pod can analyze different repos concurrently
```

## Example Output

```
============================================================
Running clang-tidy...
============================================================
Analyzing 15 files with clang-tidy
clang-tidy complete:
  - Files analyzed: 15/15
  - Findings: 23
  - Errors: 0
  - Time: 45.32s

============================================================
Running cppcheck...
============================================================
Analyzing 15 files with cppcheck
cppcheck complete:
  - Files analyzed: 15/15
  - Findings: 18
  - Errors: 0
  - Time: 12.45s

============================================================
Running custom-security...
============================================================
Analyzing 15 files with custom-security
custom-security complete:
  - Files analyzed: 15/15
  - Findings: 31
  - Errors: 0
  - Time: 0.87s

============================================================
Analysis Complete!
============================================================
Total time: 58.64s
Total findings: 72 (unique: 48)
Severity breakdown:
  - Errors: 5
  - Warnings: 28
  - Info: 15
```

## Testing

### Unit Test Example

```python
import pytest
from pathlib import Path
from tools.clang_tidy import ClangTidyTool

@pytest.mark.asyncio
async def test_clang_tidy():
    tool = ClangTidyTool()
    
    # Create test file
    test_file = Path("/tmp/test.c")
    test_file.write_text("int main() { int x; return 0; }")
    
    findings = await tool.analyze_file(test_file, Path("/tmp"))
    
    assert isinstance(findings, list)
```

### Integration Test

```bash
# Test with your DVCP repo
git clone https://github.com/anjpar/dvcp-safe-and-vulnerable.git /tmp/dvcp
cd /tmp/dvcp
git checkout vulnerable

# Run analyzer
python /path/to/analyzer_bot.py /tmp/dvcp test-integration-1
```

## Comparison: Fuzzing vs Static Analysis

| Aspect | Fuzzing (Current) | Static Analysis (New) |
|--------|------------------|----------------------|
| Execution | Runtime | Compile-time |
| Coverage | Paths executed | All code paths |
| Speed | Minutes-Hours | Seconds-Minutes |
| Findings | Real crashes | Potential bugs |
| False Positives | Very low | Medium |
| Tool | Fuzzer Bot | Static Analyzer Bot |
| Output Table | `povs` | `static_analysis_findings` |
| Clustering | Stack trace | File+Line+Rule |

## Next Steps for Buttercup Integration

1. **Test locally** ✅ (you can do this now!)
2. **Create Dockerfile** for static analyzer bot
3. **Add database table** for findings
4. **Create API endpoints** for UI
5. **Build UI tab** for static analysis results
6. **Deploy to Kubernetes** in your cluster
7. **Combine with fuzzing** - cross-reference static warnings with crash locations

## FAQ

**Q: Why not just run clang-tidy directly?**
A: The bot provides:
- Parallel execution across files
- Multiple tools orchestration
- Result deduplication
- Integration with Buttercup
- Error handling and timeouts

**Q: Can I use this outside Buttercup?**
A: Yes! The analyzer_bot.py is standalone and can be used on any codebase.

**Q: How does this compare to your fuzzing work?**
A: Complementary! Static analysis finds potential bugs without execution. Fuzzing finds real crashes. Together they're more powerful.

**Q: What about false positives?**
A: Static analysis can have false positives. The UI should allow filtering/suppression. Consider adding AI analysis (like your crash triage) to help triage findings.

## Resources

- Your concurrency library: `concurrency/README.md`
- Buttercup fuzzer bot: Similar pattern for reference
- Crash triage system: Can reuse UI clustering patterns
- clang-tidy docs: https://clang.llvm.org/extra/clang-tidy/
- cppcheck docs: http://cppcheck.net/

---

**Status**: Ready for local testing ✅  
**Next**: Run `python test_analyzer.py` to see it in action!
