"""
Updated analyzer_bot.py with Buttercup API submission.

This replaces the TODO section in the original analyzer_bot.py
"""

import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Any
import logging

# Add this function to the StaticAnalyzerBot class:

async def submit_to_buttercup(self, results: Dict[str, Any], api_url: str = "http://localhost:1323") -> bool:
    """Submit analysis results to Buttercup API.
    
    Args:
        results: Analysis results from analyze()
        api_url: Buttercup API base URL
        
    Returns:
        True if submission succeeded
    """
    logger.info(f"Submitting {len(results['findings'])} findings to Buttercup API...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Prepare submission data
            submission_data = {
                'task_id': self.task_id,
                'findings': results['findings'],
            }
            
            # Submit to API
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
    
    except aiohttp.ClientError as e:
        logger.error(f"✗ Network error submitting to Buttercup: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error submitting to Buttercup: {e}")
        return False


# Update the main() function:

async def main():
    """Entry point for the static analyzer bot."""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: analyzer_bot.py <repo_path> <task_id> [--api-url <url>] [--no-submit]")
        print("\nExamples:")
        print("  python analyzer_bot.py /path/to/repo task-123")
        print("  python analyzer_bot.py /path/to/repo task-123 --api-url http://buttercup-ui:1323")
        print("  python analyzer_bot.py /path/to/repo task-123 --no-submit  # Skip API submission")
        sys.exit(1)
    
    repo_path = Path(sys.argv[1])
    task_id = sys.argv[2]
    
    # Parse optional arguments
    api_url = "http://localhost:1323"
    submit_results = True
    
    for i, arg in enumerate(sys.argv[3:], start=3):
        if arg == "--api-url" and i + 1 < len(sys.argv):
            api_url = sys.argv[i + 1]
        elif arg == "--no-submit":
            submit_results = False
    
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
        if submit_results:
            print("\n" + "="*60)
            print("SUBMITTING TO BUTTERCUP")
            print("="*60)
            success = await bot.submit_to_buttercup(results, api_url)
            
            if success:
                print(f"\n✓ Results submitted to {api_url}")
                print(f"  View in UI: {api_url}")
            else:
                print(f"\n✗ Failed to submit results")
                print(f"  Results saved locally, can retry submission")
                sys.exit(1)
        else:
            print("\n(Skipping API submission as requested)")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
