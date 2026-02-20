"""
Zonny Workspace Analyzer - Comprehensive Project Analysis

Generates detailed reports about workspace structure, files, and organization.
"""

import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict


def analyze_workspace(root: str = None) -> dict:
    """
    Perform comprehensive workspace analysis.
    
    Args:
        root: Project root directory (defaults to cwd)
    
    Returns detailed information about:
    - File counts by type
    - Directory structure
    - File sizes
    - Documentation files
    - Code files
    - Test files
    - Configuration files
    """
    workspace = root if root else os.getcwd()
    
    analysis = {
        'workspace': workspace,
        'scan_time': datetime.now().isoformat(),
        'files_by_type': defaultdict(list),
        'files_by_category': defaultdict(list),
        'total_files': 0,
        'total_size': 0,
        'directories': [],
        'documentation': [],
        'code_files': [],
        'test_files': [],
        'config_files': []
    }
    
    # Walk through workspace
    for root_dir, dirs, files in os.walk(workspace):
        # Skip common ignored directories
        dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git', 'node_modules', '.vscode']]
        
        rel_root = os.path.relpath(root_dir, workspace)
        if rel_root != '.':
            analysis['directories'].append(rel_root)
        
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, workspace)
            
            try:
                file_size = os.path.getsize(file_path)
                analysis['total_files'] += 1
                analysis['total_size'] += file_size
                
                # Get extension
                ext = Path(file).suffix.lower()
                
                # Categorize by extension
                analysis['files_by_type'][ext or 'no_extension'].append({
                    'path': rel_path,
                    'size': file_size,
                    'name': file
                })
                
                # Categorize by purpose
                if file.startswith('test_'):
                    analysis['test_files'].append(rel_path)
                    analysis['files_by_category']['tests'].append(rel_path)
                elif ext == '.md':
                    analysis['documentation'].append(rel_path)
                    analysis['files_by_category']['documentation'].append(rel_path)
                elif ext in ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs']:
                    analysis['code_files'].append(rel_path)
                    analysis['files_by_category']['code'].append(rel_path)
                elif ext in ['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.txt']:
                    analysis['config_files'].append(rel_path)
                    analysis['files_by_category']['config'].append(rel_path)
                    
            except (OSError, PermissionError):
                continue
    
    return analysis


def generate_report(analysis: dict, detailed: bool = True) -> str:
    """
    Generate human-readable report from analysis.
    
    Args:
        analysis: Analysis dict from analyze_workspace()
        detailed: If True, include detailed file listings
        
    Returns:
        Formatted report string
    """
    report_lines = []
    
    # Header
    report_lines.append("=" * 80)
    report_lines.append("ZONNY WORKSPACE COMPREHENSIVE REVIEW")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append(f"Workspace: {analysis['workspace']}")
    report_lines.append(f"Scan Time: {analysis['scan_time']}")
    report_lines.append(f"Total Files: {analysis['total_files']}")
    report_lines.append(f"Total Size: {format_bytes(analysis['total_size'])}")
    report_lines.append(f"Directories: {len(analysis['directories'])}")
    report_lines.append("")
    
    # Summary by category
    report_lines.append("-" * 80)
    report_lines.append("FILE CATEGORIES")
    report_lines.append("-" * 80)
    report_lines.append(f"Documentation Files: {len(analysis['documentation'])} files")
    report_lines.append(f"Code Files: {len(analysis['code_files'])} files")
    report_lines.append(f"Test Files: {len(analysis['test_files'])} files")
    report_lines.append(f"Configuration Files: {len(analysis['config_files'])} files")
    report_lines.append("")
    
    # Files by type
    report_lines.append("-" * 80)
    report_lines.append("FILE TYPES")
    report_lines.append("-" * 80)
    
    # Sort by count
    sorted_types = sorted(analysis['files_by_type'].items(), 
                         key=lambda x: len(x[1]), reverse=True)
    
    for ext, files in sorted_types:
        total_size = sum(f['size'] for f in files)
        display_ext = ext if ext else "no extension"
        report_lines.append(f"{display_ext:20} {len(files):3} files  {format_bytes(total_size):>12}")
    
    report_lines.append("")
    
    # Directory structure
    report_lines.append("-" * 80)
    report_lines.append("DIRECTORY STRUCTURE")
    report_lines.append("-" * 80)
    
    if analysis['directories']:
        for directory in sorted(analysis['directories'])[:20]:  # Top 20
            report_lines.append(f"📁 {directory}")
    else:
        report_lines.append("(Flat structure - no subdirectories)")
    
    report_lines.append("")
    
    # Documentation files
    if analysis['documentation']:
        report_lines.append("-" * 80)
        report_lines.append("DOCUMENTATION FILES")
        report_lines.append("-" * 80)
        for doc in sorted(analysis['documentation']):
            report_lines.append(f"📄 {doc}")
        report_lines.append("")
    
    # Test files
    if analysis['test_files']:
        report_lines.append("-" * 80)
        report_lines.append("TEST FILES")
        report_lines.append("-" * 80)
        for test in sorted(analysis['test_files']):
            report_lines.append(f"🧪 {test}")
        report_lines.append("")
    
    # Key Python files (if any)
    py_files = analysis['files_by_type'].get('.py', [])
    if py_files:
        report_lines.append("-" * 80)
        report_lines.append(f"PYTHON FILES ({len(py_files)} total)")
        report_lines.append("-" * 80)
        
        # Filter to show main files (not in subdirectories for brevity)
        main_py = [f for f in py_files if '/' not in f['path'] and '\\' not in f['path']]
        
        for py_file in sorted(main_py, key=lambda x: x['name']):
            report_lines.append(f"🐍 {py_file['path']:40} {format_bytes(py_file['size']):>12}")
        
        if len(py_files) > len(main_py):
            report_lines.append(f"... and {len(py_files) - len(main_py)} more Python files in subdirectories")
        
        report_lines.append("")
    
    # Notable patterns
    report_lines.append("-" * 80)
    report_lines.append("PROJECT INSIGHTS")
    report_lines.append("-" * 80)
    
    insights = []
    
    # Check for common patterns
    if len(analysis['test_files']) > 0:
        coverage = len(analysis['test_files']) / max(1, len(analysis['code_files'])) * 100
        insights.append(f"✅ Testing: {len(analysis['test_files'])} test files ({coverage:.0f}% test coverage ratio)")
    else:
        insights.append("⚠️  No test files detected")
    
    if len(analysis['documentation']) > 5:
        insights.append(f"✅ Well documented: {len(analysis['documentation'])} documentation files")
    elif len(analysis['documentation']) > 0:
        insights.append(f"📝 Some documentation: {len(analysis['documentation'])} files")
    else:
        insights.append("⚠️  No documentation files detected")
    
    # Check for specific files
    all_files = set()
    for files_list in analysis['files_by_type'].values():
        all_files.update(f['path'] for f in files_list)
    
    if 'requirements.txt' in all_files:
        insights.append("✅ Python dependencies: requirements.txt found")
    
    if 'server.py' in all_files or 'main.py' in all_files:
        insights.append("✅ Server application detected")
    
    if any('agent' in f.lower() for f in all_files):
        insights.append("✅ Agent-based architecture detected")
    
    for insight in insights:
        report_lines.append(f"  {insight}")
    
    report_lines.append("")
    
    # Footer
    report_lines.append("=" * 80)
    report_lines.append("END OF REPORT")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def create_workspace_report(output_file: str = "report.txt", detailed: bool = True, root: str = None) -> str:
    """
    Analyze workspace and create comprehensive report file.
    
    Args:
        output_file: Path to output file
        detailed: Include detailed listings
        root: Project root directory (defaults to cwd)
        
    Returns:
        Status message
    """
    try:
        # Analyze workspace
        analysis = analyze_workspace(root=root)
        
        # Generate report
        report = generate_report(analysis, detailed=detailed)
        
        # Determine output path
        workspace = root if root else os.getcwd()
        output_path = os.path.join(workspace, output_file) if not os.path.isabs(output_file) else output_file
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        file_size = len(report.encode('utf-8'))
        
        return f"✅ Comprehensive workspace report written to {output_file} ({format_bytes(file_size)})\n\nSummary:\n- {analysis['total_files']} files analyzed\n- {len(analysis['directories'])} directories\n- {len(analysis['documentation'])} documentation files\n- {len(analysis['code_files'])} code files\n- {len(analysis['test_files'])} test files"
        
    except Exception as e:
        return f"❌ Error creating report: {e}"
