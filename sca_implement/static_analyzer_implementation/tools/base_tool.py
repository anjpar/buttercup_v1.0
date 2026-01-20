"""Base class for static analysis tools."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
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
        return asdict(self)
    
    def dedup_key(self) -> tuple:
        """Generate deduplication key."""
        return (self.file_path, self.line_number, self.rule_id)


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
    
    def get_name(self) -> str:
        """Get tool name."""
        return self.name
    
    def get_concurrency_limit(self) -> int:
        """Get max concurrent tasks."""
        return self.max_concurrent
    
    def get_timeout(self) -> float:
        """Get timeout in seconds."""
        return self.timeout
