"""clang-tidy static analysis tool integration."""

import asyncio
import re
from pathlib import Path
from typing import List
import logging

from .base_tool import StaticAnalysisTool, Finding


logger = logging.getLogger(__name__)


class ClangTidyTool(StaticAnalysisTool):
    """Integration with clang-tidy static analyzer."""
    
    def __init__(self, checks: str = "bugprone-*,cert-*,clang-analyzer-*,cppcoreguidelines-*"):
        """Initialize clang-tidy.
        
        Args:
            checks: Comma-separated list of checks to enable
        """
        super().__init__(name="clang-tidy", max_concurrent=5, timeout=120.0)
        self.checks = checks
        logger.info(f"Initialized clang-tidy with checks: {checks}")
    
    def is_applicable(self, file_path: Path) -> bool:
        """Check if file is C/C++ source."""
        return file_path.suffix in ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx']
    
    async def analyze_file(self, file_path: Path, repo_path: Path) -> List[Finding]:
        """Run clang-tidy on a single file.
        
        Args:
            file_path: File to analyze
            repo_path: Repository root
            
        Returns:
            List of findings
        """
        findings = []
        
        try:
            # Build clang-tidy command
            cmd = [
                'clang-tidy',
                f'--checks={self.checks}',
                '--format-style=file',
                '--quiet',  # Reduce output
                str(file_path),
                '--',
                '-I', str(repo_path / 'include'),
                '-I', str(repo_path),
            ]
            
            logger.debug(f"Running clang-tidy on {file_path.name}")
            
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
            
            # Parse output (clang-tidy writes to stdout)
            output = stdout.decode('utf-8', errors='ignore')
            findings = self._parse_output(output, file_path)
            
            if findings:
                logger.info(f"clang-tidy found {len(findings)} issues in {file_path.name}")
            
        except asyncio.TimeoutError:
            logger.warning(f"clang-tidy timeout on {file_path.name} after {self.timeout}s")
        except FileNotFoundError:
            logger.error(f"clang-tidy not found in PATH")
        except Exception as e:
            logger.error(f"clang-tidy error on {file_path.name}: {e}")
        
        return findings
    
    def _parse_output(self, output: str, file_path: Path) -> List[Finding]:
        """Parse clang-tidy output into Finding objects.
        
        clang-tidy format: 
        file:line:column: severity: message [rule-id]
        """
        findings = []
        
        # Pattern for main diagnostic line
        pattern = r'(.+?):(\d+):(\d+):\s+(error|warning|note):\s+(.+?)\s+\[([^\]]+)\]'
        
        for match in re.finditer(pattern, output):
            file, line, col, severity, message, rule_id = match.groups()
            
            # Only create findings for the target file (clang-tidy can report issues in headers)
            if Path(file).name == file_path.name:
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
