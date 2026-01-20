"""
API endpoints for Static Analysis integration.

Add these to: orchestrator/src/buttercup/orchestrator/ui/competition_api/main.py
"""

from fastapi import Depends, HTTPException
from sqlalchemy import func
from typing import Any
from collections import defaultdict

from buttercup.orchestrator.ui.database import DatabaseManager, StaticAnalysisFinding
from buttercup.orchestrator.ui.competition_api.dependencies import get_database_manager


# ============================================================================
# ENDPOINT 1: Get all static analysis findings (with filtering)
# ============================================================================

@app.get("/v1/dashboard/static_findings")
def get_static_findings(
    task_id: str | None = None,
    tool_name: str | None = None,
    severity: str | None = None,
    rule_id: str | None = None,
    database_manager: DatabaseManager = Depends(get_database_manager)
) -> dict[str, Any]:
    """Get static analysis findings with optional filtering.
    
    Query parameters:
        task_id: Filter by task ID
        tool_name: Filter by tool (e.g., 'clang-tidy', 'cppcheck')
        severity: Filter by severity ('error', 'warning', 'info')
        rule_id: Filter by specific rule ID
    
    Returns:
        {
            'findings': [...],
            'total': int,
            'stats': {...}
        }
    """
    session = database_manager.get_session()
    
    try:
        # Build query with filters
        query = session.query(StaticAnalysisFinding)
        
        if task_id:
            query = query.filter(StaticAnalysisFinding.task_id == task_id)
        if tool_name:
            query = query.filter(StaticAnalysisFinding.tool_name == tool_name)
        if severity:
            query = query.filter(StaticAnalysisFinding.severity == severity)
        if rule_id:
            query = query.filter(StaticAnalysisFinding.rule_id == rule_id)
        
        # Get all findings
        findings = query.order_by(
            StaticAnalysisFinding.severity.desc(),
            StaticAnalysisFinding.created_at.desc()
        ).all()
        
        # Calculate statistics
        stats = {
            'total': len(findings),
            'by_severity': {
                'error': len([f for f in findings if f.severity == 'error']),
                'warning': len([f for f in findings if f.severity == 'warning']),
                'info': len([f for f in findings if f.severity == 'info']),
            },
            'by_tool': {},
            'by_file': {},
        }
        
        # Count by tool
        for finding in findings:
            stats['by_tool'][finding.tool_name] = stats['by_tool'].get(finding.tool_name, 0) + 1
            
            # Count by file
            from pathlib import Path
            filename = Path(finding.file_path).name
            stats['by_file'][filename] = stats['by_file'].get(filename, 0) + 1
        
        return {
            'findings': [f.to_dict() for f in findings],
            'total': len(findings),
            'stats': stats,
        }
    
    finally:
        session.close()


# ============================================================================
# ENDPOINT 2: Get clustered static analysis findings (like crash clusters)
# ============================================================================

@app.get("/v1/dashboard/static_clusters")
def get_static_clusters(
    task_id: str | None = None,
    database_manager: DatabaseManager = Depends(get_database_manager)
) -> dict[str, Any]:
    """Get static analysis findings clustered by dedup_token.
    
    Similar to crash clustering, this groups findings by their dedup token
    to show unique issues rather than individual findings.
    
    Query parameters:
        task_id: Filter by task ID
    
    Returns:
        {
            'clusters': [
                {
                    'cluster_id': str,
                    'dedup_token': str,
                    'count': int,
                    'severity': str,  # highest severity in cluster
                    'rule_id': str,
                    'message': str,
                    'tool_names': [str],
                    'file_paths': [str],
                    'findings': [...]  # individual findings
                }
            ],
            'stats': {...}
        }
    """
    session = database_manager.get_session()
    
    try:
        # Build base query
        query = session.query(StaticAnalysisFinding)
        
        if task_id:
            query = query.filter(StaticAnalysisFinding.task_id == task_id)
        
        # Get all findings
        all_findings = query.all()
        
        # Group by dedup_token
        clusters = defaultdict(list)
        unclustered = []
        
        for finding in all_findings:
            if finding.dedup_token:
                clusters[finding.dedup_token].append(finding)
            else:
                unclustered.append(finding)
        
        # Build cluster objects
        cluster_list = []
        
        for idx, (dedup_token, findings) in enumerate(sorted(clusters.items()), 1):
            # Determine highest severity in cluster
            severity_priority = {'error': 3, 'warning': 2, 'info': 1}
            highest_severity = max(findings, key=lambda f: severity_priority.get(f.severity, 0)).severity
            
            # Get unique tool names and file paths
            tool_names = sorted(set(f.tool_name for f in findings))
            file_paths = sorted(set(f.file_path for f in findings))
            
            # Use first finding as representative
            representative = findings[0]
            
            cluster_list.append({
                'cluster_id': idx,
                'dedup_token': dedup_token,
                'count': len(findings),
                'severity': highest_severity,
                'rule_id': representative.rule_id,
                'message': representative.message,
                'tool_names': tool_names,
                'file_paths': file_paths,
                'line_number': representative.line_number,
                'first_seen': min(f.created_at for f in findings).isoformat(),
                'last_seen': max(f.created_at for f in findings).isoformat(),
                'findings': [f.to_dict() for f in findings],
            })
        
        # Calculate statistics
        stats = {
            'total_findings': len(all_findings),
            'unique_issues': len(clusters),
            'unclustered': len(unclustered),
            'by_severity': {
                'error': len([f for f in all_findings if f.severity == 'error']),
                'warning': len([f for f in all_findings if f.severity == 'warning']),
                'info': len([f for f in all_findings if f.severity == 'info']),
            },
        }
        
        return {
            'clusters': cluster_list,
            'unclustered': [f.to_dict() for f in unclustered],
            'stats': stats,
        }
    
    finally:
        session.close()


# ============================================================================
# ENDPOINT 3: Get static analysis summary for a task
# ============================================================================

@app.get("/v1/dashboard/static_summary/{task_id}")
def get_static_analysis_summary(
    task_id: str,
    database_manager: DatabaseManager = Depends(get_database_manager)
) -> dict[str, Any]:
    """Get a summary of static analysis for a specific task.
    
    Returns high-level statistics and top findings.
    """
    session = database_manager.get_session()
    
    try:
        findings = session.query(StaticAnalysisFinding).filter(
            StaticAnalysisFinding.task_id == task_id
        ).all()
        
        if not findings:
            return {
                'task_id': task_id,
                'has_results': False,
                'message': 'No static analysis results found for this task'
            }
        
        # Calculate comprehensive statistics
        severity_counts = {
            'error': len([f for f in findings if f.severity == 'error']),
            'warning': len([f for f in findings if f.severity == 'warning']),
            'info': len([f for f in findings if f.severity == 'info']),
        }
        
        # Count by tool
        tool_counts = {}
        for finding in findings:
            tool_counts[finding.tool_name] = tool_counts.get(finding.tool_name, 0) + 1
        
        # Top 5 most common issues
        rule_counts = {}
        for finding in findings:
            key = (finding.rule_id, finding.message[:100])
            rule_counts[key] = rule_counts.get(key, 0) + 1
        
        top_issues = [
            {'rule_id': rule_id, 'message': msg, 'count': count}
            for (rule_id, msg), count in sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        # Files with most issues
        file_counts = {}
        for finding in findings:
            from pathlib import Path
            filename = Path(finding.file_path).name
            file_counts[filename] = file_counts.get(filename, 0) + 1
        
        top_files = [
            {'file': file, 'count': count}
            for file, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        return {
            'task_id': task_id,
            'has_results': True,
            'total_findings': len(findings),
            'severity_counts': severity_counts,
            'tool_counts': tool_counts,
            'top_issues': top_issues,
            'top_files': top_files,
            'first_analysis': min(f.created_at for f in findings).isoformat(),
            'last_analysis': max(f.created_at for f in findings).isoformat(),
        }
    
    finally:
        session.close()


# ============================================================================
# ENDPOINT 4: Submit static analysis results (for the bot to use)
# ============================================================================

@app.post("/v1/submit/static_analysis")
def submit_static_analysis_results(
    task_id: str,
    findings: list[dict[str, Any]],
    database_manager: DatabaseManager = Depends(get_database_manager)
) -> dict[str, Any]:
    """Submit static analysis results from the analyzer bot.
    
    Request body:
        {
            'task_id': str,
            'findings': [
                {
                    'tool_name': str,
                    'file_path': str,
                    'line_number': int,
                    'column': int,
                    'severity': str,
                    'message': str,
                    'rule_id': str,
                    'code_snippet': str (optional)
                }
            ]
        }
    
    Returns:
        {
            'success': bool,
            'submitted': int,
            'duplicates_skipped': int
        }
    """
    session = database_manager.get_session()
    
    try:
        from buttercup.orchestrator.ui.database import generate_static_analysis_dedup_token
        
        submitted = 0
        duplicates = 0
        
        for finding_data in findings:
            # Generate dedup token
            dedup_token = generate_static_analysis_dedup_token(
                finding_data['file_path'],
                finding_data['line_number'],
                finding_data['rule_id']
            )
            
            # Check if this finding already exists
            existing = session.query(StaticAnalysisFinding).filter(
                StaticAnalysisFinding.task_id == task_id,
                StaticAnalysisFinding.dedup_token == dedup_token
            ).first()
            
            if existing:
                duplicates += 1
                continue
            
            # Create new finding
            finding = StaticAnalysisFinding(
                task_id=task_id,
                tool_name=finding_data['tool_name'],
                file_path=finding_data['file_path'],
                line_number=finding_data['line_number'],
                column=finding_data['column'],
                severity=finding_data['severity'],
                message=finding_data['message'],
                rule_id=finding_data['rule_id'],
                code_snippet=finding_data.get('code_snippet'),
                dedup_token=dedup_token,
            )
            
            session.add(finding)
            submitted += 1
        
        session.commit()
        
        return {
            'success': True,
            'submitted': submitted,
            'duplicates_skipped': duplicates,
        }
    
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit findings: {str(e)}")
    
    finally:
        session.close()
