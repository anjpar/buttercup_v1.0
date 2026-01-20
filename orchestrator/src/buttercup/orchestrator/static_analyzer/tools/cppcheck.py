"""cppcheck static analysis tool integration."""

import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List
import logging

from buttercup.orchestrator.static_analyzer.tools.base_tool import StaticAnalysisTool, Finding

logger = logging.getLogger(__name__)


class CppCheckTool(StaticAnalysisTool):
    """Integration with cppcheck static analyzer."""
    
    def __init__(self, enable: str = "all"):
        """Initialize cppcheck.
        
        Args:
            enable: Checks to enable ('all', 'warning', 'style', etc.)
        """
        super().__init__(name="cppcheck", max_concurrent=10, timeout=60.0)
        self.enable = enable
        logger.info(f"Initialized cppcheck with enable={enable}")
    
    def is_applicable(self, file_path: Path) -> bool:
        """Check if file is C/C++ source."""
        return file_path.suffix in ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx']
    
    async def analyze_file(self, file_path: Path, repo_path: Path) -> List[Finding]:
        """Run cppcheck on a single file.
        
        Args:
            file_path: File to analyze
            repo_path: Repository root
            
        Returns:
            List of findings
        """
        findings = []
        
        try:
            # Build cppcheck command with XML output
            cmd = [
                'cppcheck',
                f'--enable={self.enable}',
                '--xml',
                '--xml-version=2',
                '--quiet',
                '-I', str(repo_path / 'include'),
                '-I', str(repo_path),
                str(file_path),
            ]
            
            logger.debug(f"Running cppcheck on {file_path.name}")
            
            # Run cppcheck (outputs XML to stderr!)
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
            
            # Parse XML output from stderr
            xml_output = stderr.decode('utf-8', errors='ignore')
            findings = self._parse_xml_output(xml_output, file_path)
            
            if findings:
                logger.info(f"cppcheck found {len(findings)} issues in {file_path.name}")
            
        except asyncio.TimeoutError:
            logger.warning(f"cppcheck timeout on {file_path.name} after {self.timeout}s")
        except FileNotFoundError:
            logger.error(f"cppcheck not found in PATH")
        except Exception as e:
            logger.error(f"cppcheck error on {file_path.name}: {e}")
        
        return findings
    
    def _parse_xml_output(self, xml_output: str, file_path: Path) -> List[Finding]:
        """Parse cppcheck XML output into Finding objects."""
        findings = []
        
        try:
            # Parse XML
            root = ET.fromstring(xml_output)
            
            # Find all error elements
            for error in root.findall('.//error'):
                error_id = error.get('id', 'unknown')
                severity = error.get('severity', 'warning')
                message = error.get('msg', '')
                
                # Map cppcheck severity to our standard levels
                severity_map = {
                    'error': 'error',
                    'warning': 'warning',
                    'style': 'info',
                    'performance': 'warning',
                    'portability': 'info',
                    'information': 'info',
                }
                std_severity = severity_map.get(severity, 'info')
                
                # Get location information
                locations = error.findall('.//location')
                for location in locations:
                    loc_file = location.get('file', '')
                    
                    # Only report findings for our target file
                    if Path(loc_file).name == file_path.name:
                        line = int(location.get('line', 0))
                        column = int(location.get('column', 0))
                        
                        findings.append(Finding(
                            tool_name=self.name,
                            file_path=str(file_path),
                            line_number=line,
                            column=column,
                            severity=std_severity,
                            message=message.strip(),
                            rule_id=error_id,
                        ))
        
        except ET.ParseError as e:
            logger.error(f"Failed to parse cppcheck XML: {e}")
        except Exception as e:
            logger.error(f"Error parsing cppcheck output: {e}")
        
        return findings
