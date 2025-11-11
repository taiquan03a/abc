"""
AI Analysis Module for Mock and Real AI Processing
"""

from .mock_analyzer import MockAIAnalyzer
from .incident_types import (
    IncidentTypes, 
    SeverityLevel, 
    INCIDENT_DEFINITIONS,
    get_incident_info
)

__all__ = [
    'MockAIAnalyzer', 
    'IncidentTypes', 
    'SeverityLevel', 
    'INCIDENT_DEFINITIONS',
    'get_incident_info'
]
