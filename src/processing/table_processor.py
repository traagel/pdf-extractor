"""
Processor for identifying and parsing tables in text.
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class TableColumn:
    header: str
    width: int = 0
    align: str = 'left'

class TableProcessor:
    """Processes text into structured tables."""
    
    def __init__(self):
        self.column_patterns = {
            'level': r'^\d{1,2}(?:st|nd|rd|th)?$',
            'number': r'^[+-]?\d+$',
            'modifier': r'^[+-]\d+$',
            'feature': r'^[A-Z][a-zA-Z\s,]+$',
            'class_name': r'^[A-Z][a-zA-Z]+$',
            'hit_die': r'^d\d+$',
            'ability': r'^(?:Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)(?:\s*(?:&|\+)\s*(?:Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma))?$'
        }
        
        # Define known table types
        self.table_types = {
            'class_table': {
                'columns': [
                    TableColumn('Class', 1),
                    TableColumn('Description', 3),
                    TableColumn('Hit Die', 1),
                    TableColumn('Primary Ability', 2),
                    TableColumn('Saving Throws', 2),
                    TableColumn('Proficiencies', 3)
                ],
                'patterns': ['class_name', 'hit_die', 'ability']  # Key patterns to identify this table type
            },
            'level_progression': {
                'columns': [
                    TableColumn('Level', 2),
                    TableColumn('Proficiency Bonus', 2),
                    TableColumn('Features', 4),
                    TableColumn('Rages', 2),
                    TableColumn('Rage Damage', 2)
                ],
                'patterns': ['level', 'modifier', 'feature']
            }
        }
    
    def detect_table(self, lines: List[str], min_rows: int = 5) -> bool:
        """Check if lines appear to form a table."""
        if len(lines) < min_rows:
            return False
        
        # Try to identify table type
        pattern_matches = {
            pattern: 0 for pattern in self.column_patterns.keys()
        }
        
        for line in lines:
            line = line.strip()
            for pattern_name, pattern in self.column_patterns.items():
                if re.match(pattern, line, re.IGNORECASE):
                    pattern_matches[pattern_name] += 1
        
        # Check if matches any known table type
        for table_type in self.table_types.values():
            if all(pattern_matches[pattern] >= min_rows/4 for pattern in table_type['patterns']):
                return True
        
        return False
    
    def parse_table(self, lines: List[str]) -> Dict:
        """Parse lines into a structured table."""
        # Identify table type
        table_type = self._identify_table_type(lines)
        if not table_type:
            return {'type': 'text', 'lines': lines}
        
        columns = self.table_types[table_type]['columns']
        
        # Parse based on table type
        if table_type == 'class_table':
            return self._parse_class_table(lines, columns)
        else:
            return self._parse_level_table(lines, columns)
    
    def _identify_table_type(self, lines: List[str]) -> Optional[str]:
        """Identify the type of table from the content."""
        pattern_matches = {
            pattern: 0 for pattern in self.column_patterns.keys()
        }
        
        for line in lines:
            line = line.strip()
            for pattern_name, pattern in self.column_patterns.items():
                if re.match(pattern, line, re.IGNORECASE):
                    pattern_matches[pattern_name] += 1
        
        # Check each table type
        for type_name, type_info in self.table_types.items():
            if all(pattern_matches[pattern] >= 3 for pattern in type_info['patterns']):
                return type_name
        
        return None
    
    def _parse_class_table(self, lines: List[str], columns: List[TableColumn]) -> Dict:
        """Parse the class description table."""
        rows = []
        current_row = []
        current_class = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for new class entry
            if re.match(self.column_patterns['class_name'], line):
                if current_row:
                    rows.append(current_row)
                current_row = [line]
                current_class = line
            elif current_class:
                # Add to description if it's a continuation
                if not re.match(self.column_patterns['hit_die'], line) and \
                   not re.match(self.column_patterns['ability'], line):
                    if len(current_row) == 1:
                        current_row.append(line)
                    else:
                        current_row[-1] = f"{current_row[-1]} {line}"
                else:
                    current_row.append(line)
        
        # Add final row
        if current_row:
            rows.append(current_row)
        
        return {
            'type': 'table',
            'table_type': 'class_table',
            'columns': [col.header for col in columns],
            'rows': rows
        }
    
    def _parse_level_table(self, lines: List[str], columns: List[TableColumn]) -> Dict:
        """Parse the level progression table."""
        rows = []
        current_row = []
        current_col = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if self._matches_column_pattern(line, columns[0]):
                if current_row:
                    rows.append(current_row)
                current_row = [line]
                current_col = 1
            elif current_row:
                if current_col < len(columns) and self._matches_column_pattern(line, columns[current_col]):
                    current_row.append(line)
                    current_col += 1
                else:
                    current_row[-1] = f"{current_row[-1]} {line}"
        
        if current_row:
            rows.append(current_row)
        
        return {
            'type': 'table',
            'table_type': 'level_progression',
            'columns': [col.header for col in columns],
            'rows': rows
        }
    
    def _matches_column_pattern(self, value: str, column: TableColumn) -> bool:
        """Check if value matches the expected pattern for a column."""
        if column.header == 'Level':
            return bool(re.match(self.column_patterns['level'], value))
        elif column.header in ['Proficiency Bonus', 'Rage Damage']:
            return bool(re.match(self.column_patterns['modifier'], value))
        elif column.header == 'Rages':
            return bool(re.match(self.column_patterns['number'], value)) or value.lower() == 'unlimited'
        elif column.header == 'Features':
            return bool(re.match(self.column_patterns['feature'], value))
        return False 