"""Custom security checker for common vulnerabilities."""

import asyncio
import re
from pathlib import Path
from typing import List, Dict, Tuple
import logging

from buttercup.orchestrator.static_analyzer.tools.base_tool import StaticAnalysisTool, Finding

logger = logging.getLogger(__name__)


class CustomSecurityChecker(StaticAnalysisTool):
    """Custom security checker for dangerous patterns."""
    
    # Dangerous functions and their secure alternatives
    DANGEROUS_FUNCTIONS = {
        'strcpy': ('strncpy', 'Buffer overflow risk'),
        'strcat': ('strncat', 'Buffer overflow risk'),
        'sprintf': ('snprintf', 'Buffer overflow risk'),
        'gets': ('fgets', 'Buffer overflow risk'),
        'scanf': ('fgets + sscanf', 'Format string vulnerability'),
        'vsprintf': ('vsnprintf', 'Buffer overflow risk'),
        'strncpy': (None, 'May not null-terminate, consider safer alternatives'),
        'strncat': (None, 'Potential off-by-one errors'),
    }
    
    # Dangerous patterns (regex, description)
    DANGEROUS_PATTERNS = [
        (r'\balloca\s*\(', 'alloca usage - stack overflow risk'),
        (r'\bmemcpy\s*\([^,]+,\s*[^,]+,\s*strlen', 'memcpy with strlen - off-by-one error'),
        (r'sizeof\s*\([^)]*\*[^)]*\)', 'sizeof on pointer - likely error'),
        (r'\[\s*0\s*\]', 'Zero-length array - undefined behavior'),
    ]
    
    def __init__(self):
        """Initialize custom security checker."""
        super().__init__(name="custom-security", max_concurrent=20, timeout=10.0)
        logger.info(f"Initialized custom security checker")
    
    def is_applicable(self, file_path: Path) -> bool:
        """Check if file is C/C++ source."""
        return file_path.suffix in ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx']
    
    async def analyze_file(self, file_path: Path, repo_path: Path) -> List[Finding]:
        """Analyze file for security issues.
        
        This is a simple pattern-matching checker. For production use,
        consider using a proper parser/AST.
        """
        findings = []
        
        try:
            # Read file content
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            lines = content.splitlines()
            
            # Check for dangerous functions
            for line_num, line in enumerate(lines, 1):
                # Skip comments (simple check)
                stripped = line.strip()
                if stripped.startswith('//') or stripped.startswith('/*'):
                    continue
                
                # Check dangerous functions
                for func_name, (safe_alt, risk) in self.DANGEROUS_FUNCTIONS.items():
                    if re.search(rf'\b{func_name}\s*\(', line):
                        column = line.find(func_name)
                        message = f"Dangerous function '{func_name}' detected: {risk}"
                        if safe_alt:
                            message += f". Consider using '{safe_alt}' instead"
                        
                        findings.append(Finding(
                            tool_name=self.name,
                            file_path=str(file_path),
                            line_number=line_num,
                            column=column,
                            severity='warning',
                            message=message,
                            rule_id=f'SEC-UNSAFE-FUNC-{func_name.upper()}',
                            code_snippet=line.strip()
                        ))
                
                # Check dangerous patterns
                for pattern, description in self.DANGEROUS_PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        findings.append(Finding(
                            tool_name=self.name,
                            file_path=str(file_path),
                            line_number=line_num,
                            column=match.start(),
                            severity='warning',
                            message=f'Dangerous pattern detected: {description}',
                            rule_id='SEC-PATTERN',
                            code_snippet=line.strip()
                        ))
            
            if findings:
                logger.info(f"Custom checker found {len(findings)} security issues in {file_path.name}")
        
        except Exception as e:
            logger.error(f"Custom checker error on {file_path.name}: {e}")
        
        # Simulate async I/O (in real implementation, could check online CVE databases)
        await asyncio.sleep(0)
        
        return findings
