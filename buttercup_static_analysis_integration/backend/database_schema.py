"""
Database schema additions for Static Analysis integration.

Add this to: orchestrator/src/buttercup/orchestrator/ui/database.py
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

# ============================================================================
# NEW TABLE: StaticAnalysisFinding
# ============================================================================

class StaticAnalysisFinding(Base):
    """Static analysis finding from analyzer bot.
    
    Similar to POV table but for static analysis results.
    Each finding represents a potential bug or code quality issue.
    """
    __tablename__ = "static_analysis_findings"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Task association
    task_id = Column(String, nullable=False, index=True)
    
    # Tool information
    tool_name = Column(String, nullable=False, index=True)  # 'clang-tidy', 'cppcheck', etc.
    
    # Location information
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=False)
    column = Column(Integer, nullable=False)
    
    # Finding details
    severity = Column(String, nullable=False, index=True)  # 'error', 'warning', 'info'
    message = Column(Text, nullable=False)
    rule_id = Column(String, nullable=False, index=True)  # e.g., 'bugprone-use-after-move'
    code_snippet = Column(Text, nullable=True)
    
    # Deduplication (similar to crash dedup_token)
    dedup_token = Column(String, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Foreign key relationship
    task = relationship("Task", back_populates="static_findings")
    
    def __repr__(self):
        return f"<StaticAnalysisFinding(id={self.id}, tool={self.tool_name}, severity={self.severity}, rule={self.rule_id})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
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


# ============================================================================
# UPDATE: Task model to add static_findings relationship
# ============================================================================

# Add this to your existing Task class:
"""
class Task(Base):
    # ... existing fields ...
    
    # Add this relationship:
    static_findings = relationship("StaticAnalysisFinding", back_populates="task")
"""


# ============================================================================
# HELPER FUNCTION: Generate dedup token for static analysis findings
# ============================================================================

def generate_static_analysis_dedup_token(file_path: str, line_number: int, rule_id: str) -> str:
    """Generate a deduplication token for static analysis findings.
    
    Similar to crash dedup tokens, this allows clustering of similar findings.
    
    Args:
        file_path: Path to the file
        line_number: Line number of the finding
        rule_id: Rule/check ID (e.g., 'bugprone-use-after-move')
    
    Returns:
        Dedup token string
    """
    import hashlib
    from pathlib import Path
    
    # Use just the filename (not full path) to handle different repo locations
    filename = Path(file_path).name
    
    # Create a consistent string for hashing
    dedup_string = f"{filename}:{line_number}:{rule_id}"
    
    # Generate hash
    token = hashlib.sha256(dedup_string.encode()).hexdigest()[:16]
    
    return f"static-{token}"


# ============================================================================
# MIGRATION SCRIPT
# ============================================================================

"""
To apply this schema to your database:

1. If using Alembic migrations:
   ```bash
   cd orchestrator
   alembic revision --autogenerate -m "Add static analysis findings table"
   alembic upgrade head
   ```

2. Or manually in Python:
   ```python
   from buttercup.orchestrator.ui.database import Base, engine
   Base.metadata.create_all(engine)
   ```

3. Or using SQL directly:
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
"""
