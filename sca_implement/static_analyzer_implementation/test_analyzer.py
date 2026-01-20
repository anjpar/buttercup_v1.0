#!/usr/bin/env python3
"""
Test script for the static analyzer bot.

This script creates a small test repository with intentional bugs
and runs the static analyzer on it.
"""

import asyncio
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from analyzer_bot import StaticAnalyzerBot


# Sample C code with intentional bugs
VULNERABLE_CODE = """
#include <stdio.h>
#include <string.h>

// Bug 1: Dangerous function strcpy
void copy_string(char *dest, const char *src) {
    strcpy(dest, src);  // Buffer overflow risk
}

// Bug 2: Dangerous function gets
void read_input() {
    char buffer[100];
    gets(buffer);  // Unsafe gets
}

// Bug 3: Dangerous sprintf
void format_message(char *buf, const char *user) {
    sprintf(buf, "Hello, %s!", user);  // No bounds checking
}

// Bug 4: Memory leak
int* allocate_array(int size) {
    int *arr = (int*)malloc(size * sizeof(int));
    if (arr == NULL) {
        return NULL;
    }
    // Bug: No free() called
    return arr;
}

// Bug 5: Potential null pointer dereference
void process_data(int *ptr) {
    *ptr = 42;  // No null check
}

// Bug 6: Uninitialized variable
int compute_value() {
    int result;
    return result * 2;  // result not initialized
}

int main() {
    char dest[10];
    copy_string(dest, "This is a very long string that will overflow");
    
    read_input();
    
    char msg[50];
    format_message(msg, "World");
    
    int *data = allocate_array(100);
    process_data(data);
    
    int val = compute_value();
    
    printf("Done\\n");
    return 0;
}
"""

SAFER_CODE = """
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

// Safe version with bounds checking
void copy_string_safe(char *dest, size_t dest_size, const char *src) {
    strncpy(dest, src, dest_size - 1);
    dest[dest_size - 1] = '\\0';
}

// Safe input reading
void read_input_safe() {
    char buffer[100];
    if (fgets(buffer, sizeof(buffer), stdin) != NULL) {
        printf("Read: %s", buffer);
    }
}

// Safe formatting
void format_message_safe(char *buf, size_t buf_size, const char *user) {
    snprintf(buf, buf_size, "Hello, %s!", user);
}

int main() {
    char dest[10];
    copy_string_safe(dest, sizeof(dest), "Safe");
    
    read_input_safe();
    
    char msg[50];
    format_message_safe(msg, sizeof(msg), "World");
    
    printf("Done\\n");
    return 0;
}
"""


async def create_test_repo(temp_dir: Path) -> Path:
    """Create a temporary test repository with vulnerable code."""
    print(f"Creating test repository in {temp_dir}...")
    
    # Create source files
    src_dir = temp_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    
    # Write vulnerable code
    vuln_file = src_dir / "vulnerable.c"
    vuln_file.write_text(VULNERABLE_CODE)
    print(f"  - Created {vuln_file.name} with intentional bugs")
    
    # Write safer code for comparison
    safe_file = src_dir / "safer.c"
    safe_file.write_text(SAFER_CODE)
    print(f"  - Created {safe_file.name} with safer practices")
    
    # Create a header file
    header_code = """
#ifndef UTILS_H
#define UTILS_H

#include <stdlib.h>

// Dangerous macro
#define BUFFER_SIZE 256
#define COPY_STRING(dest, src) strcpy(dest, src)

// Function declarations
void process_buffer(char *buf);

#endif
"""
    header_file = src_dir / "utils.h"
    header_file.write_text(header_code)
    print(f"  - Created {header_file.name}")
    
    print(f"Test repository ready: {temp_dir}")
    return temp_dir


async def run_analysis_test():
    """Run the static analyzer on a test repository."""
    print("\n" + "="*60)
    print("Static Analyzer Bot - Test Run")
    print("="*60 + "\n")
    
    # Create temporary test repository
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = await create_test_repo(Path(temp_dir))
        
        print("\n" + "="*60)
        print("Starting Analysis...")
        print("="*60 + "\n")
        
        # Run analyzer
        bot = StaticAnalyzerBot(repo_path, task_id="test-run-1")
        results = await bot.analyze()
        
        # Display detailed results
        print("\n" + "="*60)
        print("DETAILED FINDINGS")
        print("="*60)
        
        if results['findings']:
            # Group by file
            by_file = {}
            for finding in results['findings']:
                file_path = Path(finding['file_path']).name
                if file_path not in by_file:
                    by_file[file_path] = []
                by_file[file_path].append(finding)
            
            for file_name, findings in sorted(by_file.items()):
                print(f"\n{file_name}:")
                print("-" * 60)
                
                # Group by severity
                for severity in ['error', 'warning', 'info']:
                    sev_findings = [f for f in findings if f['severity'] == severity]
                    if sev_findings:
                        print(f"\n  {severity.upper()} ({len(sev_findings)}):")
                        for f in sev_findings:
                            print(f"    Line {f['line_number']}: [{f['tool_name']}] {f['rule_id']}")
                            print(f"      {f['message']}")
                            if f.get('code_snippet'):
                                print(f"      Code: {f['code_snippet']}")
        else:
            print("\nNo findings detected.")
        
        print("\n" + "="*60)
        print("Test Complete!")
        print("="*60)
        
        return results


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║       Static Analyzer Bot - Demonstration                     ║
║                                                               ║
║  This demo creates a test repo with intentional bugs and      ║
║  runs all configured static analysis tools on it.             ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    results = asyncio.run(run_analysis_test())
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Summary                                                      ║
╠═══════════════════════════════════════════════════════════════╣
║  Files analyzed:    {results['stats']['total_files']:<4}                                  ║
║  Total findings:    {results['stats']['total_findings']:<4}                                  ║
║  Unique findings:   {results['stats']['unique_findings']:<4}                                  ║
║  Time elapsed:      {results['stats']['elapsed_seconds']:.2f}s                                ║
╚══════════════════════════════════════════════════════════════╝
    """)
