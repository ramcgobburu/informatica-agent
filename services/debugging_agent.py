import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import re

from models.workflow_models import (
    Workflow, WorkflowSearchResult, DebugResult, 
    SourceTable, TargetTable, Transformation, Session
)
from services.workflow_search_engine import WorkflowSearchEngine
from services.azure_integration import AzureIntegrationService

logger = logging.getLogger(__name__)

class DebuggingAgent:
    """Intelligent debugging agent for Informatica workflow issues"""
    
    def __init__(self, search_engine: WorkflowSearchEngine, azure_service: AzureIntegrationService):
        self.search_engine = search_engine
        self.azure_service = azure_service
        self.debug_patterns = self._load_debug_patterns()
    
    def _load_debug_patterns(self) -> List[Dict[str, Any]]:
        """Load common debugging patterns and solutions"""
        return [
            {
                "pattern": "empty table",
                "description": "Table is empty or has no data",
                "common_causes": [
                    "Source data is empty or not available",
                    "Session failed during execution",
                    "Transformation filters out all records",
                    "Target connection issues",
                    "Workflow not scheduled or not running",
                    "Source query returns no results"
                ],
                "debugging_steps": [
                    "Check session logs for errors",
                    "Verify source data availability",
                    "Check transformation logic and filters",
                    "Verify target database connection",
                    "Check workflow schedule and status",
                    "Review source query conditions"
                ],
                "solutions": [
                    "Fix source data issues",
                    "Correct transformation logic",
                    "Resolve connection problems",
                    "Update workflow schedule",
                    "Modify source query if needed"
                ]
            },
            {
                "pattern": "session failure",
                "description": "Workflow session fails to execute",
                "common_causes": [
                    "Source connection timeout",
                    "Target connection issues",
                    "Insufficient memory or resources",
                    "Transformation errors",
                    "Data type mismatches",
                    "Permission issues"
                ],
                "debugging_steps": [
                    "Check session logs for specific error messages",
                    "Verify all connections are working",
                    "Check system resources and memory",
                    "Review transformation expressions",
                    "Validate data types and mappings",
                    "Check user permissions"
                ],
                "solutions": [
                    "Fix connection configurations",
                    "Increase memory allocation",
                    "Correct transformation logic",
                    "Resolve data type issues",
                    "Update user permissions"
                ]
            },
            {
                "pattern": "data quality issues",
                "description": "Data quality problems in target tables",
                "common_causes": [
                    "Source data contains invalid values",
                    "Transformation logic errors",
                    "Missing data validation rules",
                    "Incorrect data type conversions",
                    "Null value handling issues"
                ],
                "debugging_steps": [
                    "Analyze source data quality",
                    "Review transformation expressions",
                    "Check data validation rules",
                    "Verify data type mappings",
                    "Test null value handling"
                ],
                "solutions": [
                    "Implement data validation rules",
                    "Fix transformation logic",
                    "Add data cleansing steps",
                    "Improve error handling",
                    "Update data type mappings"
                ]
            },
            {
                "pattern": "performance issues",
                "description": "Workflow runs slowly or times out",
                "common_causes": [
                    "Large data volumes",
                    "Inefficient transformations",
                    "Poor connection performance",
                    "Resource constraints",
                    "Suboptimal query design"
                ],
                "debugging_steps": [
                    "Analyze data volumes",
                    "Review transformation performance",
                    "Check connection performance",
                    "Monitor system resources",
                    "Analyze query execution plans"
                ],
                "solutions": [
                    "Optimize transformation logic",
                    "Improve connection performance",
                    "Increase system resources",
                    "Optimize source queries",
                    "Implement data partitioning"
                ]
            },
            {
                "pattern": "dependency issues",
                "description": "Workflow dependencies not met",
                "common_causes": [
                    "Upstream workflow failed",
                    "Source table not updated",
                    "File not available",
                    "Database connection issues",
                    "Schedule conflicts"
                ],
                "debugging_steps": [
                    "Check upstream workflow status",
                    "Verify source table updates",
                    "Check file availability",
                    "Test database connections",
                    "Review workflow schedules"
                ],
                "solutions": [
                    "Fix upstream workflow issues",
                    "Update source data",
                    "Resolve file access issues",
                    "Fix connection problems",
                    "Adjust workflow schedules"
                ]
            }
        ]
    
    async def analyze_table_issue(self, table_name: str, issue_description: str = "") -> DebugResult:
        """Analyze why a table might be empty or have issues"""
        try:
            logger.info(f"Analyzing table issue for: {table_name}")
            
            # Find workflows that load this table
            workflow_results = await self.search_engine.search_table_workflows(table_name)
            
            if not workflow_results:
                return DebugResult(
                    table_name=table_name,
                    responsible_workflows=[],
                    potential_issues=["No workflows found that load this table"],
                    recommendations=[
                        "Verify the table name is correct",
                        "Check if workflows exist in other sets",
                        "Confirm the table is actually a target table in any workflow"
                    ],
                    confidence_score=0.0
                )
            
            # Analyze the workflows and their components
            analysis = await self._analyze_workflow_components(table_name, workflow_results)
            
            # Match against known debug patterns
            pattern_matches = self._match_debug_patterns(issue_description, analysis)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(analysis, pattern_matches)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(analysis, pattern_matches)
            
            return DebugResult(
                table_name=table_name,
                responsible_workflows=workflow_results,
                potential_issues=analysis.get("potential_issues", []),
                recommendations=recommendations,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            logger.error(f"Error analyzing table issue: {e}")
            return DebugResult(
                table_name=table_name,
                responsible_workflows=[],
                potential_issues=[f"Analysis error: {str(e)}"],
                recommendations=["Check system configuration and try again"],
                confidence_score=0.0
            )
    
    async def _analyze_workflow_components(self, table_name: str, workflow_results: List[WorkflowSearchResult]) -> Dict[str, Any]:
        """Analyze workflow components to identify potential issues"""
        analysis = {
            "potential_issues": [],
            "workflow_analysis": [],
            "component_analysis": [],
            "dependency_analysis": []
        }
        
        for result in workflow_results:
            workflow = result.workflow
            
            # Analyze each workflow
            workflow_analysis = {
                "workflow_name": workflow.name,
                "set_file": workflow.set_file,
                "confidence": result.confidence_score,
                "issues": [],
                "recommendations": []
            }
            
            # Check workflow status
            if workflow.status != "active":
                workflow_analysis["issues"].append(f"Workflow status is {workflow.status}")
                workflow_analysis["recommendations"].append("Check workflow status and activate if needed")
            
            # Analyze sessions
            for session in workflow.sessions:
                session_issues = self._analyze_session(session, table_name)
                if session_issues:
                    workflow_analysis["issues"].extend(session_issues)
            
            # Analyze source tables
            for source_table in workflow.source_tables:
                source_issues = self._analyze_source_table(source_table)
                if source_issues:
                    workflow_analysis["issues"].extend(source_issues)
            
            # Analyze target tables
            for target_table in workflow.target_tables:
                if target_table.name.lower() == table_name.lower():
                    target_issues = self._analyze_target_table(target_table)
                    if target_issues:
                        workflow_analysis["issues"].extend(target_issues)
            
            # Analyze transformations
            for transformation in workflow.transformations:
                trans_issues = self._analyze_transformation(transformation)
                if trans_issues:
                    workflow_analysis["issues"].extend(trans_issues)
            
            analysis["workflow_analysis"].append(workflow_analysis)
            
            # Collect potential issues
            analysis["potential_issues"].extend(workflow_analysis["issues"])
        
        # Remove duplicates
        analysis["potential_issues"] = list(set(analysis["potential_issues"]))
        
        return analysis
    
    def _analyze_session(self, session: Session, table_name: str) -> List[str]:
        """Analyze session for potential issues"""
        issues = []
        
        # Check session properties
        if not session.source_connections:
            issues.append(f"Session {session.name} has no source connections")
        
        if not session.target_connections:
            issues.append(f"Session {session.name} has no target connections")
        
        # Check for common session issues
        if session.last_run_status and session.last_run_status.lower() in ["failed", "error"]:
            issues.append(f"Session {session.name} last run status: {session.last_run_status}")
        
        # Check session properties for potential issues
        for prop_name, prop_value in session.properties.items():
            if prop_name.lower() in ["error_threshold", "stop_on_error"]:
                if prop_value and prop_value.lower() == "true":
                    issues.append(f"Session {session.name} has {prop_name} set to {prop_value}")
        
        return issues
    
    def _analyze_source_table(self, source_table: SourceTable) -> List[str]:
        """Analyze source table for potential issues"""
        issues = []
        
        # Check connection
        if not source_table.connection:
            issues.append(f"Source table {source_table.name} has no connection specified")
        
        # Check schema and database
        if not source_table.schema and not source_table.database:
            issues.append(f"Source table {source_table.name} has no schema or database specified")
        
        # Check for filters that might exclude all data
        if source_table.filters:
            for filter_expr in source_table.filters:
                if "1=0" in filter_expr or "false" in filter_expr.lower():
                    issues.append(f"Source table {source_table.name} has filter that excludes all data: {filter_expr}")
        
        return issues
    
    def _analyze_target_table(self, target_table: TargetTable) -> List[str]:
        """Analyze target table for potential issues"""
        issues = []
        
        # Check connection
        if not target_table.connection:
            issues.append(f"Target table {target_table.name} has no connection specified")
        
        # Check schema and database
        if not target_table.schema and not target_table.database:
            issues.append(f"Target table {target_table.name} has no schema or database specified")
        
        # Check load type
        if not target_table.load_type:
            issues.append(f"Target table {target_table.name} has no load type specified")
        
        return issues
    
    def _analyze_transformation(self, transformation: Transformation) -> List[str]:
        """Analyze transformation for potential issues"""
        issues = []
        
        # Check for common transformation issues
        if transformation.type.lower() == "filter":
            if transformation.expression and "1=0" in transformation.expression:
                issues.append(f"Filter transformation {transformation.name} has expression that excludes all data")
        
        # Check for expression errors
        if transformation.expression:
            if "error" in transformation.expression.lower() or "null" in transformation.expression.lower():
                issues.append(f"Transformation {transformation.name} has potentially problematic expression")
        
        # Check for missing input/output ports
        if not transformation.input_ports:
            issues.append(f"Transformation {transformation.name} has no input ports")
        
        if not transformation.output_ports:
            issues.append(f"Transformation {transformation.name} has no output ports")
        
        return issues
    
    def _match_debug_patterns(self, issue_description: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Match analysis against known debug patterns"""
        matches = []
        
        issue_lower = issue_description.lower()
        
        for pattern in self.debug_patterns:
            pattern_name = pattern["pattern"]
            
            # Check if issue description matches pattern
            if pattern_name in issue_lower or any(keyword in issue_lower for keyword in pattern["common_causes"]):
                matches.append(pattern)
            
            # Check if analysis issues match pattern
            for issue in analysis.get("potential_issues", []):
                if any(keyword in issue.lower() for keyword in pattern["common_causes"]):
                    matches.append(pattern)
                    break
        
        return matches
    
    def _generate_recommendations(self, analysis: Dict[str, Any], pattern_matches: List[Dict[str, Any]]) -> List[str]:
        """Generate specific recommendations based on analysis"""
        recommendations = []
        
        # Add recommendations from pattern matches
        for pattern in pattern_matches:
            recommendations.extend(pattern.get("solutions", []))
        
        # Add specific recommendations based on analysis
        for workflow_analysis in analysis.get("workflow_analysis", []):
            for issue in workflow_analysis.get("issues", []):
                if "connection" in issue.lower():
                    recommendations.append("Check and fix database connections")
                elif "status" in issue.lower():
                    recommendations.append("Verify workflow and session status")
                elif "filter" in issue.lower():
                    recommendations.append("Review and correct filter expressions")
                elif "transformation" in issue.lower():
                    recommendations.append("Check transformation logic and expressions")
                elif "schema" in issue.lower() or "database" in issue.lower():
                    recommendations.append("Verify schema and database configurations")
        
        # Add general recommendations
        recommendations.extend([
            "Check session logs for detailed error messages",
            "Verify source data availability and quality",
            "Test database connections manually",
            "Review workflow schedule and dependencies",
            "Check system resources and performance"
        ])
        
        # Remove duplicates and limit to top recommendations
        unique_recommendations = list(dict.fromkeys(recommendations))
        return unique_recommendations[:10]
    
    def _calculate_confidence_score(self, analysis: Dict[str, Any], pattern_matches: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for the analysis"""
        score = 0.0
        
        # Base score for having workflows
        if analysis.get("workflow_analysis"):
            score += 0.3
        
        # Score for identifying specific issues
        issue_count = len(analysis.get("potential_issues", []))
        if issue_count > 0:
            score += min(0.4, issue_count * 0.1)
        
        # Score for pattern matches
        if pattern_matches:
            score += min(0.3, len(pattern_matches) * 0.1)
        
        return min(1.0, score)
    
    async def debug_workflow_issue(self, workflow_name: str, issue_description: str = "") -> Dict[str, Any]:
        """Debug a specific workflow issue"""
        try:
            logger.info(f"Debugging workflow issue for: {workflow_name}")
            
            # Find the workflow
            workflow_results = await self.search_engine.search_workflow_by_name(workflow_name)
            
            if not workflow_results:
                return {
                    "workflow_name": workflow_name,
                    "found": False,
                    "issues": ["Workflow not found"],
                    "recommendations": ["Verify workflow name and check if it exists"]
                }
            
            # Get the best match
            best_match = workflow_results[0]
            workflow = best_match.workflow
            
            # Analyze the workflow
            analysis = {
                "workflow_name": workflow.name,
                "set_file": workflow.set_file,
                "found": True,
                "issues": [],
                "recommendations": [],
                "components": {
                    "sessions": len(workflow.sessions),
                    "source_tables": len(workflow.source_tables),
                    "target_tables": len(workflow.target_tables),
                    "transformations": len(workflow.transformations)
                }
            }
            
            # Check workflow status
            if workflow.status != "active":
                analysis["issues"].append(f"Workflow status is {workflow.status}")
                analysis["recommendations"].append("Check workflow status and activate if needed")
            
            # Analyze sessions
            for session in workflow.sessions:
                session_issues = self._analyze_session(session, "")
                if session_issues:
                    analysis["issues"].extend(session_issues)
            
            # Analyze components
            for source_table in workflow.source_tables:
                source_issues = self._analyze_source_table(source_table)
                if source_issues:
                    analysis["issues"].extend(source_issues)
            
            for target_table in workflow.target_tables:
                target_issues = self._analyze_target_table(target_table)
                if target_issues:
                    analysis["issues"].extend(target_issues)
            
            for transformation in workflow.transformations:
                trans_issues = self._analyze_transformation(transformation)
                if trans_issues:
                    analysis["issues"].extend(trans_issues)
            
            # Match against debug patterns
            pattern_matches = self._match_debug_patterns(issue_description, {"potential_issues": analysis["issues"]})
            
            # Generate recommendations
            recommendations = self._generate_recommendations({"potential_issues": analysis["issues"]}, pattern_matches)
            analysis["recommendations"].extend(recommendations)
            
            # Remove duplicates
            analysis["issues"] = list(set(analysis["issues"]))
            analysis["recommendations"] = list(set(analysis["recommendations"]))
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error debugging workflow issue: {e}")
            return {
                "workflow_name": workflow_name,
                "found": False,
                "issues": [f"Debug analysis error: {str(e)}"],
                "recommendations": ["Check system configuration and try again"]
            }
    
    async def get_debugging_statistics(self) -> Dict[str, Any]:
        """Get debugging agent statistics"""
        return {
            "debug_patterns_loaded": len(self.debug_patterns),
            "search_engine_available": self.search_engine is not None,
            "azure_service_available": self.azure_service is not None,
            "patterns": [pattern["pattern"] for pattern in self.debug_patterns]
        }

