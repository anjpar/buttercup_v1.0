"""Static Analysis Bot - orchestrates static analysis tools.

This bot uses the concurrency library to efficiently run multiple static
analysis tools across a codebase in parallel.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any
import logging
import sys

from buttercup.orchestrator.static_analyzer.concurrency import TaskManager, TaskResult
from buttercup.orchestrator.static_analyzer.tools.base_tool import StaticAnalysisTool, Finding
from buttercup.orchestrator.static_analyzer.tools.clang_tidy import ClangTidyTool
from buttercup.orchestrator.static_analyzer.tools.cppcheck import CppCheckTool
from buttercup.orchestrator.static_analyzer.tools.custom_security import CustomSecurityChecker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StaticAnalyzerBot:
    """Bot that runs static analysis tools on a repository.
    
    This bot discovers source files, runs multiple analysis tools in parallel,
    and aggregates the results with deduplication.
    """
    
    def __init__(self, repo_path: Path, task_id: str):
        """Initialize the analyzer bot.
        
        Args:
            repo_path: Path to the repository to analyze
            task_id: Buttercup task ID for tracking
        """
        self.repo_path = Path(repo_path).resolve()
        self.task_id = task_id
        self.tools: List[StaticAnalysisTool] = []
        
        # Validate repo path
        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        
        # Initialize tools
        self._initialize_tools()
        
        logger.info(f"Initialized StaticAnalyzerBot for task {task_id}")
        logger.info(f"Repository: {self.repo_path}")
    
    def _initialize_tools(self):
        """Initialize all available static analysis tools."""
        # Add tools here - only enabled ones will be used
        self.tools = [
            # ClangTidyTool with comprehensive checks
            ClangTidyTool(checks="bugprone-*,cert-*,clang-analyzer-*,cppcoreguidelines-*,performance-*"),
            
            # CppCheck with all checks enabled
            CppCheckTool(enable="all"),
            
            # Custom security checker
            CustomSecurityChecker(),
        ]
        
        logger.info(f"Initialized {len(self.tools)} static analysis tools:")
        for tool in self.tools:
            logger.info(f"  - {tool.name} (max_concurrent={tool.max_concurrent}, timeout={tool.timeout}s)")
    
    def _discover_files(self) -> List[Path]:
        """Discover all source files in the repository.
        
        Returns:
            List of source file paths
        """
        source_extensions = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx'}
        files = []
        
        logger.info(f"Discovering source files in {self.repo_path}...")
        
        for ext in source_extensions:
            discovered = list(self.repo_path.rglob(f'*{ext}'))
            files.extend(discovered)
            if discovered:
                logger.debug(f"Found {len(discovered)} {ext} files")
        
        # Filter out common directories to skip
        skip_dirs = {'.git', 'build', 'cmake-build', '.vscode', '__pycache__', 'node_modules'}
        filtered_files = [
            f for f in files
            if not any(skip_dir in f.parts for skip_dir in skip_dirs)
        ]
        
        if len(filtered_files) < len(files):
            logger.info(f"Filtered out {len(files) - len(filtered_files)} files in skip directories")
        
        logger.info(f"Discovered {len(filtered_files)} source files")
        return filtered_files
    
    async def analyze(self) -> Dict[str, Any]:
        """Run all static analysis tools on the repository.
        
        This method:
        1. Discovers source files
        2. For each tool:
           - Creates a TaskManager with tool-specific concurrency
           - Analyzes all applicable files in parallel
        3. Deduplicates findings
        4. Returns aggregated results
        
        Returns:
            Dictionary with analysis results and statistics
        """
        logger.info(f"Starting static analysis for task {self.task_id}")
        start_time = asyncio.get_event_loop().time()
        
        # Discover files
        files = self._discover_files()
        
        if not files:
            logger.warning("No source files found")
            return {
                'task_id': self.task_id,
                'status': 'no_files',
                'findings': [],
                'stats': {
                    'total_files': 0,
                    'elapsed_seconds': 0,
                }
            }
        
        # Analyze files with each tool
        all_findings: List[Finding] = []
        tool_stats = {}
        
        for tool in self.tools:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running {tool.name}...")
            logger.info(f"{'='*60}")
            
            # Filter files applicable to this tool
            applicable_files = [f for f in files if tool.is_applicable(f)]
            
            if not applicable_files:
                logger.info(f"No applicable files for {tool.name}")
                tool_stats[tool.name] = {
                    'files_analyzed': 0,
                    'successful': 0,
                    'errors': 0,
                    'findings': 0,
                }
                continue
            
            logger.info(f"Analyzing {len(applicable_files)} files with {tool.name}")
            
            # Create TaskManager for this tool with tool-specific concurrency
            manager = TaskManager(
                max_concurrent=tool.max_concurrent,
                timeout=tool.timeout
            )
            
            # Add analysis tasks for each file
            for file_path in applicable_files:
                manager.add_task(tool.analyze_file(file_path, self.repo_path))
            
            # Run all tasks for this tool concurrently
            tool_start = asyncio.get_event_loop().time()
            results: List[TaskResult] = await manager.run_async()
            tool_elapsed = asyncio.get_event_loop().time() - tool_start
            
            # Process results
            tool_findings = []
            success_count = 0
            error_count = 0
            
            for i, result in enumerate(results):
                if result.success:
                    success_count += 1
                    findings_for_file = result.value
                    tool_findings.extend(findings_for_file)
                else:
                    error_count += 1
                    logger.error(f"{tool.name} error on {applicable_files[i].name}: {result.error}")
            
            all_findings.extend(tool_findings)
            
            # Store statistics
            tool_stats[tool.name] = {
                'files_analyzed': len(applicable_files),
                'successful': success_count,
                'errors': error_count,
                'findings': len(tool_findings),
                'elapsed_seconds': round(tool_elapsed, 2),
            }
            
            logger.info(f"{tool.name} complete:")
            logger.info(f"  - Files analyzed: {success_count}/{len(applicable_files)}")
            logger.info(f"  - Findings: {len(tool_findings)}")
            logger.info(f"  - Errors: {error_count}")
            logger.info(f"  - Time: {tool_elapsed:.2f}s")
        
        # Deduplicate findings
        unique_findings = self._deduplicate_findings(all_findings)
        
        # Calculate totals
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Group findings by severity
        severity_counts = {
            'error': len([f for f in unique_findings if f.severity == 'error']),
            'warning': len([f for f in unique_findings if f.severity == 'warning']),
            'info': len([f for f in unique_findings if f.severity == 'info']),
        }
        
        results = {
            'task_id': self.task_id,
            'status': 'success',
            'findings': [f.to_dict() for f in unique_findings],
            'stats': {
                'total_files': len(files),
                'total_findings': len(all_findings),
                'unique_findings': len(unique_findings),
                'severity_counts': severity_counts,
                'tools': tool_stats,
                'elapsed_seconds': round(elapsed, 2),
            }
        }
        
        # Log summary
        logger.info(f"\n{'='*60}")
        logger.info(f"Analysis Complete!")
        logger.info(f"{'='*60}")
        logger.info(f"Total time: {elapsed:.2f}s")
        logger.info(f"Total findings: {len(all_findings)} (unique: {len(unique_findings)})")
        logger.info(f"Severity breakdown:")
        logger.info(f"  - Errors: {severity_counts['error']}")
        logger.info(f"  - Warnings: {severity_counts['warning']}")
        logger.info(f"  - Info: {severity_counts['info']}")
        
        return results
    
    async def submit_to_buttercup(self, results: Dict[str, Any], api_url: str = "http://localhost:1323") -> bool:
        """Submit analysis results to Buttercup API."""
        import aiohttp
        
        logger.info(f"Submitting {len(results['findings'])} findings to Buttercup API...")
        
        try:
            async with aiohttp.ClientSession() as session:
                submission_data = {
                    'task_id': self.task_id,
                    'findings': results['findings'],
                }
                
                async with session.post(
                    f"{api_url}/v1/submit/static_analysis",
                    json=submission_data,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        response_data = await response.json()
                        logger.info(f"✓ Submission successful!")
                        logger.info(f"  - Submitted: {response_data['submitted']}")
                        logger.info(f"  - Duplicates skipped: {response_data['duplicates_skipped']}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"✗ Submission failed: HTTP {response.status}")
                        logger.error(f"  Response: {error_text}")
                        return False
        
        except Exception as e:
            logger.error(f"✗ Error submitting to Buttercup: {e}")
            return False

    def _deduplicate_findings(self, findings: List[Finding]) -> List[Finding]:
        """Remove duplicate findings based on file, line, and rule_id.
        
        Args:
            findings: List of all findings
            
        Returns:
            List of unique findings
        """
        seen = set()
        unique = []
        
        for finding in findings:
            key = finding.dedup_key()
            
            if key not in seen:
                seen.add(key)
                unique.append(finding)
        
        logger.info(f"Deduplicated {len(findings)} -> {len(unique)} findings")
        return unique


async def main():
    """Entry point for the static analyzer bot."""
    if len(sys.argv) < 3:
        print("Usage: analyzer_bot.py <repo_path> <task_id>")
        print("\nExample:")
        print("  python analyzer_bot.py /path/to/repo task-123")
        sys.exit(1)
    
    repo_path = Path(sys.argv[1])
    task_id = sys.argv[2]
    
    # Create and run bot
    try:
        bot = StaticAnalyzerBot(repo_path, task_id)
        results = await bot.analyze()
        
        # Print results summary
        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)
        print(f"Task ID: {results['task_id']}")
        print(f"Status: {results['status']}")
        print(f"\nStatistics:")
        print(f"  Total files: {results['stats']['total_files']}")
        print(f"  Total findings: {results['stats']['total_findings']}")
        print(f"  Unique findings: {results['stats']['unique_findings']}")
        print(f"\nSeverity breakdown:")
        for severity, count in results['stats']['severity_counts'].items():
            print(f"  {severity}: {count}")
        print(f"\nTool performance:")
        for tool_name, stats in results['stats']['tools'].items():
            print(f"  {tool_name}:")
            print(f"    - Files: {stats['successful']}/{stats['files_analyzed']}")
            print(f"    - Findings: {stats['findings']}")
            print(f"    - Time: {stats['elapsed_seconds']}s")
        
        print(f"\nTotal time: {results['stats']['elapsed_seconds']}s")
        
        # Submit to Buttercup API
        print("\n" + "="*60)
        print("SUBMITTING TO BUTTERCUP")
        print("="*60)
        success = await bot.submit_to_buttercup(results)
        
        if success:
            print(f"\n✓ Results submitted to Buttercup!")
            print(f"  View in UI: http://localhost:1323")
        else:
            print(f"\n✗ Failed to submit results")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
