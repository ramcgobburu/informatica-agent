import xml.etree.ElementTree as ET
import xmltodict
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from pathlib import Path

from models.workflow_models import (
    Workflow, SourceTable, TargetTable, Transformation, 
    Session, ComponentType, ComponentStatus
)

logger = logging.getLogger(__name__)

class PowerCenterXMLParser:
    """Parser for PowerCenter exported XML metadata files"""
    
    def __init__(self):
        self.namespaces = {
            'ns': 'http://www.informatica.com/solutions/avos/xml',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
    
    def parse_xml_file(self, file_path: str) -> List[Workflow]:
        """Parse a PowerCenter XML file and extract workflow information"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Parse XML using ElementTree
            root = ET.fromstring(content)
            
            workflows = []
            
            # Extract set file name from filename
            set_file = Path(file_path).stem
            
            # Find all workflow elements
            for workflow_elem in root.findall('.//ns:WORKFLOW', self.namespaces):
                workflow = self._parse_workflow(workflow_elem, set_file)
                if workflow:
                    workflows.append(workflow)
            
            logger.info(f"Parsed {len(workflows)} workflows from {file_path}")
            return workflows
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error in {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return []
    
    def _parse_workflow(self, workflow_elem: ET.Element, set_file: str) -> Optional[Workflow]:
        """Parse a single workflow element"""
        try:
            name = self._get_element_text(workflow_elem, 'ns:NAME')
            if not name:
                return None
            
            description = self._get_element_text(workflow_elem, 'ns:DESCRIPTION')
            created_date = self._parse_date(self._get_element_text(workflow_elem, 'ns:CREATED'))
            modified_date = self._parse_date(self._get_element_text(workflow_elem, 'ns:MODIFIED'))
            
            # Parse sessions
            sessions = self._parse_sessions(workflow_elem)
            
            # Parse source and target tables from sessions
            source_tables = []
            target_tables = []
            transformations = []
            
            for session in sessions:
                # Extract tables from session mappings
                session_source_tables = self._extract_source_tables_from_session(workflow_elem, session.name)
                session_target_tables = self._extract_target_tables_from_session(workflow_elem, session.name)
                session_transformations = self._extract_transformations_from_session(workflow_elem, session.name)
                
                source_tables.extend(session_source_tables)
                target_tables.extend(session_target_tables)
                transformations.extend(session_transformations)
            
            # Remove duplicates
            source_tables = list({table.name: table for table in source_tables}.values())
            target_tables = list({table.name: table for table in target_tables}.values())
            transformations = list({trans.name: trans for trans in transformations}.values())
            
            workflow = Workflow(
                name=name,
                set_file=set_file,
                description=description,
                created_date=created_date,
                modified_date=modified_date,
                status=ComponentStatus.ACTIVE,
                sessions=sessions,
                source_tables=source_tables,
                target_tables=target_tables,
                transformations=transformations,
                metadata=self._extract_workflow_metadata(workflow_elem)
            )
            
            return workflow
            
        except Exception as e:
            logger.error(f"Error parsing workflow: {e}")
            return None
    
    def _parse_sessions(self, workflow_elem: ET.Element) -> List[Session]:
        """Parse sessions from workflow element"""
        sessions = []
        
        for session_elem in workflow_elem.findall('.//ns:SESSION', self.namespaces):
            try:
                name = self._get_element_text(session_elem, 'ns:NAME')
                if not name:
                    continue
                
                # Get workflow name
                workflow_name = self._get_element_text(workflow_elem, 'ns:NAME')
                
                # Get mapping name
                mapping_name = self._get_element_text(session_elem, 'ns:MAPPING')
                
                # Extract connection information
                source_connections = self._extract_connections(session_elem, 'SOURCE')
                target_connections = self._extract_connections(session_elem, 'TARGET')
                
                # Extract session properties
                properties = self._extract_session_properties(session_elem)
                
                session = Session(
                    name=name,
                    workflow_name=workflow_name,
                    mapping_name=mapping_name,
                    source_connections=source_connections,
                    target_connections=target_connections,
                    properties=properties
                )
                
                sessions.append(session)
                
            except Exception as e:
                logger.error(f"Error parsing session: {e}")
                continue
        
        return sessions
    
    def _extract_source_tables_from_session(self, workflow_elem: ET.Element, session_name: str) -> List[SourceTable]:
        """Extract source tables from session"""
        source_tables = []
        
        # Find the session element
        session_elem = None
        for sess_elem in workflow_elem.findall('.//ns:SESSION', self.namespaces):
            if self._get_element_text(sess_elem, 'ns:NAME') == session_name:
                session_elem = sess_elem
                break
        
        if not session_elem:
            return source_tables
        
        # Find mapping and extract source tables
        mapping_name = self._get_element_text(session_elem, 'ns:MAPPING')
        if mapping_name:
            # Look for source tables in the mapping
            for source_elem in workflow_elem.findall('.//ns:SOURCE', self.namespaces):
                try:
                    name = self._get_element_text(source_elem, 'ns:NAME')
                    if not name:
                        continue
                    
                    # Extract table properties
                    schema = self._get_element_text(source_elem, 'ns:SCHEMA')
                    database = self._get_element_text(source_elem, 'ns:DATABASE')
                    connection = self._get_element_text(source_elem, 'ns:CONNECTION')
                    
                    # Extract columns
                    columns = self._extract_columns(source_elem)
                    
                    source_table = SourceTable(
                        name=name,
                        schema=schema,
                        database=database,
                        connection=connection,
                        columns=columns
                    )
                    
                    source_tables.append(source_table)
                    
                except Exception as e:
                    logger.error(f"Error extracting source table: {e}")
                    continue
        
        return source_tables
    
    def _extract_target_tables_from_session(self, workflow_elem: ET.Element, session_name: str) -> List[TargetTable]:
        """Extract target tables from session"""
        target_tables = []
        
        # Find the session element
        session_elem = None
        for sess_elem in workflow_elem.findall('.//ns:SESSION', self.namespaces):
            if self._get_element_text(sess_elem, 'ns:NAME') == session_name:
                session_elem = sess_elem
                break
        
        if not session_elem:
            return target_tables
        
        # Find mapping and extract target tables
        mapping_name = self._get_element_text(session_elem, 'ns:MAPPING')
        if mapping_name:
            # Look for target tables in the mapping
            for target_elem in workflow_elem.findall('.//ns:TARGET', self.namespaces):
                try:
                    name = self._get_element_text(target_elem, 'ns:NAME')
                    if not name:
                        continue
                    
                    # Extract table properties
                    schema = self._get_element_text(target_elem, 'ns:SCHEMA')
                    database = self._get_element_text(target_elem, 'ns:DATABASE')
                    connection = self._get_element_text(target_elem, 'ns:CONNECTION')
                    load_type = self._get_element_text(target_elem, 'ns:LOADTYPE')
                    
                    # Extract columns
                    columns = self._extract_columns(target_elem)
                    
                    target_table = TargetTable(
                        name=name,
                        schema=schema,
                        database=database,
                        connection=connection,
                        columns=columns,
                        load_type=load_type
                    )
                    
                    target_tables.append(target_table)
                    
                except Exception as e:
                    logger.error(f"Error extracting target table: {e}")
                    continue
        
        return target_tables
    
    def _extract_transformations_from_session(self, workflow_elem: ET.Element, session_name: str) -> List[Transformation]:
        """Extract transformations from session"""
        transformations = []
        
        # Find the session element
        session_elem = None
        for sess_elem in workflow_elem.findall('.//ns:SESSION', self.namespaces):
            if self._get_element_text(sess_elem, 'ns:NAME') == session_name:
                session_elem = sess_elem
                break
        
        if not session_elem:
            return transformations
        
        # Find mapping and extract transformations
        mapping_name = self._get_element_text(session_elem, 'ns:MAPPING')
        if mapping_name:
            # Look for transformations in the mapping
            for trans_elem in workflow_elem.findall('.//ns:TRANSFORMATION', self.namespaces):
                try:
                    name = self._get_element_text(trans_elem, 'ns:NAME')
                    if not name:
                        continue
                    
                    trans_type = self._get_element_text(trans_elem, 'ns:TYPE')
                    
                    # Extract input and output ports
                    input_ports = self._extract_ports(trans_elem, 'INPUT')
                    output_ports = self._extract_ports(trans_elem, 'OUTPUT')
                    
                    # Extract properties
                    properties = self._extract_transformation_properties(trans_elem)
                    
                    # Extract expression if available
                    expression = self._get_element_text(trans_elem, 'ns:EXPRESSION')
                    
                    transformation = Transformation(
                        name=name,
                        type=trans_type,
                        input_ports=input_ports,
                        output_ports=output_ports,
                        properties=properties,
                        expression=expression
                    )
                    
                    transformations.append(transformation)
                    
                except Exception as e:
                    logger.error(f"Error extracting transformation: {e}")
                    continue
        
        return transformations
    
    def _extract_connections(self, session_elem: ET.Element, connection_type: str) -> List[str]:
        """Extract connection names from session"""
        connections = []
        
        for conn_elem in session_elem.findall(f'.//ns:{connection_type}CONNECTION', self.namespaces):
            conn_name = self._get_element_text(conn_elem, 'ns:NAME')
            if conn_name:
                connections.append(conn_name)
        
        return connections
    
    def _extract_session_properties(self, session_elem: ET.Element) -> Dict[str, Any]:
        """Extract session properties"""
        properties = {}
        
        for prop_elem in session_elem.findall('.//ns:PROPERTY', self.namespaces):
            name = self._get_element_text(prop_elem, 'ns:NAME')
            value = self._get_element_text(prop_elem, 'ns:VALUE')
            if name and value:
                properties[name] = value
        
        return properties
    
    def _extract_transformation_properties(self, trans_elem: ET.Element) -> Dict[str, Any]:
        """Extract transformation properties"""
        properties = {}
        
        for prop_elem in trans_elem.findall('.//ns:PROPERTY', self.namespaces):
            name = self._get_element_text(prop_elem, 'ns:NAME')
            value = self._get_element_text(prop_elem, 'ns:VALUE')
            if name and value:
                properties[name] = value
        
        return properties
    
    def _extract_columns(self, table_elem: ET.Element) -> List[Dict[str, Any]]:
        """Extract column information from table element"""
        columns = []
        
        for col_elem in table_elem.findall('.//ns:COLUMN', self.namespaces):
            try:
                name = self._get_element_text(col_elem, 'ns:NAME')
                data_type = self._get_element_text(col_elem, 'ns:DATATYPE')
                precision = self._get_element_text(col_elem, 'ns:PRECISION')
                scale = self._get_element_text(col_elem, 'ns:SCALE')
                
                if name:
                    column = {
                        'name': name,
                        'data_type': data_type,
                        'precision': precision,
                        'scale': scale
                    }
                    columns.append(column)
                    
            except Exception as e:
                logger.error(f"Error extracting column: {e}")
                continue
        
        return columns
    
    def _extract_ports(self, trans_elem: ET.Element, port_type: str) -> List[str]:
        """Extract input/output ports from transformation"""
        ports = []
        
        for port_elem in trans_elem.findall(f'.//ns:{port_type}PORT', self.namespaces):
            port_name = self._get_element_text(port_elem, 'ns:NAME')
            if port_name:
                ports.append(port_name)
        
        return ports
    
    def _extract_workflow_metadata(self, workflow_elem: ET.Element) -> Dict[str, Any]:
        """Extract additional workflow metadata"""
        metadata = {}
        
        # Extract workflow properties
        for prop_elem in workflow_elem.findall('.//ns:PROPERTY', self.namespaces):
            name = self._get_element_text(prop_elem, 'ns:NAME')
            value = self._get_element_text(prop_elem, 'ns:VALUE')
            if name and value:
                metadata[name] = value
        
        return metadata
    
    def _get_element_text(self, elem: ET.Element, path: str) -> Optional[str]:
        """Get text content from element path"""
        try:
            element = elem.find(path, self.namespaces)
            return element.text if element is not None else None
        except:
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_str:
            return None
        
        try:
            # Try different date formats
            date_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%m/%d/%Y %H:%M:%S',
                '%m/%d/%Y'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            return None
        except:
            return None
