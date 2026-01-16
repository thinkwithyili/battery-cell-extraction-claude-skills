"""
Battery Cell Datasheet Extraction Utilities.

This module provides deterministic parsing and normalization functions
for extracting battery cell specifications from PDF datasheets.
Designed to work with the Claude Battery Cell Extraction Skill.

Author: Yi Li
Version: 1.0
Last Updated: 2026-01-09
"""

from typing import Dict, List, Optional, Tuple, Any, Union
import re
import math


# =============================================================================
# UNIT CONVERSION FUNCTIONS
# =============================================================================

def normalize_units(value: Union[str, float], target_unit: str) -> Optional[float]:
    """
    Convert battery-related values to a target unit.

    Supports conversions:
    - Capacity: mAh <-> Ah
    - Resistance: Ω <-> mΩ
    - Weight: kg <-> g
    - Current: C-rate -> A (requires capacity context)

    Args:
        value: The value to convert (can include unit string)
        target_unit: The desired output unit ('ah', 'mah', 'mohm', 'ohm', 'g', 'kg')

    Returns:
        Converted value as float, or None if conversion fails

    Examples:
        >>> normalize_units("3200mAh", "ah")
        3.2
        >>> normalize_units("45mΩ", "ohm")
        0.045
        >>> normalize_units(3.2, "mah")  # float input, convert Ah to mAh
        3200.0
    """
    if value is None:
        return None

    # Handle string input with embedded unit
    if isinstance(value, str):
        # Extract numeric value and unit from string
        parsed = _parse_value_with_unit(value)
        if parsed is None:
            return None
        numeric_value, source_unit = parsed
    else:
        # Float input - assume it's already in a standard form
        numeric_value = float(value)
        source_unit = None

    target_unit = target_unit.lower()

    # Capacity conversions
    if target_unit in ['ah', 'mah']:
        if source_unit and 'mah' in source_unit.lower():
            # Source is mAh
            return numeric_value / 1000 if target_unit == 'ah' else numeric_value
        elif source_unit and 'ah' in source_unit.lower():
            # Source is Ah
            return numeric_value * 1000 if target_unit == 'mah' else numeric_value
        else:
            # No source unit - assume mAh if value > 100, else Ah
            if numeric_value > 100:
                # Likely mAh
                return numeric_value / 1000 if target_unit == 'ah' else numeric_value
            else:
                # Likely Ah
                return numeric_value * 1000 if target_unit == 'mah' else numeric_value

    # Resistance conversions
    elif target_unit in ['mohm', 'ohm', 'mω', 'ω']:
        if source_unit and ('mohm' in source_unit.lower() or 'mω' in source_unit):
            # Source is mΩ
            return numeric_value / 1000 if target_unit in ['ohm', 'ω'] else numeric_value
        elif source_unit and ('ohm' in source_unit.lower() or 'ω' in source_unit):
            # Source is Ω
            return numeric_value * 1000 if target_unit in ['mohm', 'mω'] else numeric_value
        else:
            # No source unit - return as-is
            return numeric_value

    # Weight conversions
    elif target_unit in ['g', 'kg']:
        if source_unit and 'kg' in source_unit.lower():
            return numeric_value * 1000 if target_unit == 'g' else numeric_value
        elif source_unit and 'g' in source_unit.lower():
            return numeric_value / 1000 if target_unit == 'kg' else numeric_value
        else:
            return numeric_value

    return numeric_value


def _parse_value_with_unit(text: str) -> Optional[Tuple[float, str]]:
    """
    Parse a string containing a numeric value and optional unit.

    Args:
        text: String to parse (e.g., "3200mAh", "45 mΩ", "≤18mΩ")

    Returns:
        Tuple of (numeric_value, unit_string) or None if parsing fails
    """
    if not text:
        return None

    # Remove common prefixes like ≤, ≥, <, >, ~, approximately, etc.
    text = re.sub(r'^[≤≥<>~±]', '', text.strip())
    text = re.sub(r'^(approximately|approx\.?|about|typ\.?|typical)\s*', '', text,
                  flags=re.IGNORECASE)

    # Pattern to match number followed by optional unit
    # Handles: 3200, 3200mAh, 3.2 Ah, 45mΩ, 0.045Ω, etc.
    pattern = r'([-+]?\d*\.?\d+)\s*([a-zA-ZΩω%°]*)'
    match = re.search(pattern, text)

    if match:
        try:
            numeric_value = float(match.group(1))
            unit = match.group(2).strip() if match.group(2) else ''
            return (numeric_value, unit)
        except ValueError:
            return None

    return None


# =============================================================================
# TEMPERATURE PARSING
# =============================================================================

def parse_temperature_range(text: str) -> Dict[str, Optional[float]]:
    """
    Extract temperature range from various text formats.

    Handles multiple notations:
    - "0~45°C"
    - "0°C to 45°C"
    - "-20 to 60 deg C"
    - "-30°C ~ +55°C"
    - "0 - 45 °C"
    - "-20°C~60°C"

    Args:
        text: String containing temperature range

    Returns:
        Dictionary with 'min_c' and 'max_c' keys

    Examples:
        >>> parse_temperature_range("0~45°C")
        {'min_c': 0.0, 'max_c': 45.0}
        >>> parse_temperature_range("-20 to 60 deg C")
        {'min_c': -20.0, 'max_c': 60.0}
    """
    result = {'min_c': None, 'max_c': None}

    if not text:
        return result

    # Normalize the text
    text = text.strip()

    # Pattern for temperature range with various separators
    # Matches: -20~60, 0 to 45, -30 - +55, etc.
    patterns = [
        # Pattern 1: "min ~ max °C" or "min~max°C"
        r'([-+]?\d+\.?\d*)\s*[°]?[CcFf]?\s*[~\-–—to]+\s*[\+]?([-+]?\d+\.?\d*)\s*[°]?[CcFf]?',
        # Pattern 2: "min°C to max°C"
        r'([-+]?\d+\.?\d*)\s*[°][CcFf]\s*(?:to|~|-|–)\s*[\+]?([-+]?\d+\.?\d*)\s*[°][CcFf]',
        # Pattern 3: Simple "min to max"
        r'([-+]?\d+\.?\d*)\s*(?:to|~)\s*[\+]?([-+]?\d+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                min_val = float(match.group(1))
                max_val = float(match.group(2))

                # Ensure min < max
                if min_val > max_val:
                    min_val, max_val = max_val, min_val

                result['min_c'] = min_val
                result['max_c'] = max_val
                break
            except (ValueError, IndexError):
                continue

    return result


# =============================================================================
# DCIR/IMPEDANCE PARSING
# =============================================================================

def extract_dcir_spec(text: str) -> Dict[str, Any]:
    """
    Parse DCIR/impedance specification with conditions.

    Extracts:
    - value_mohm: The impedance value in mΩ
    - temperature_c: Test temperature
    - soc_percent: State of charge
    - pulse_duration_s: Pulse duration (for DCIR)
    - frequency_hz: Measurement frequency (for ACIR)
    - type: 'acir' or 'dcir'

    Args:
        text: String containing impedance specification

    Returns:
        Dictionary with extracted values

    Examples:
        >>> extract_dcir_spec("DCIR @ 50% SOC, 25°C, 10s pulse")
        {'value_mohm': None, 'temperature_c': 25, 'soc_percent': 50, 
         'pulse_duration_s': 10, 'type': 'dcir'}
        >>> extract_dcir_spec("≤18mΩ (AC 1kHz)")
        {'value_mohm': 18.0, 'frequency_hz': 1000, 'type': 'acir'}
    """
    result = {
        'value_mohm': None,
        'temperature_c': None,
        'soc_percent': None,
        'pulse_duration_s': None,
        'frequency_hz': None,
        'type': None
    }

    if not text:
        return result

    text = text.strip()

    # Determine type (ACIR vs DCIR)
    if re.search(r'(ac|1\s*k\s*hz|1000\s*hz)', text, re.IGNORECASE):
        result['type'] = 'acir'
        result['frequency_hz'] = 1000
    elif re.search(r'(dc|dcir)', text, re.IGNORECASE):
        result['type'] = 'dcir'

    # Extract impedance value
    value_patterns = [
        r'[≤≥<>]?\s*([\d.]+)\s*m[Ωω]',  # mΩ format
        r'[≤≥<>]?\s*([\d.]+)\s*mohm',   # mohm format
        r'impedance[:\s]+[≤≥<>]?\s*([\d.]+)',  # Generic impedance
    ]

    for pattern in value_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                result['value_mohm'] = float(match.group(1))
                break
            except ValueError:
                continue

    # Extract temperature
    temp_match = re.search(r'([-+]?\d+)\s*[°]?[Cc](?![Cc])', text)
    if temp_match:
        result['temperature_c'] = float(temp_match.group(1))

    # Extract SOC
    soc_match = re.search(r'(\d+)\s*%\s*SOC', text, re.IGNORECASE)
    if soc_match:
        result['soc_percent'] = float(soc_match.group(1))

    # Extract pulse duration
    pulse_match = re.search(r'(\d+)\s*s(?:ec)?\s*(?:pulse)?', text, re.IGNORECASE)
    if pulse_match:
        result['pulse_duration_s'] = float(pulse_match.group(1))

    return result


# =============================================================================
# CAPACITY AND CURRENT PARSING
# =============================================================================

def parse_capacity(text: str) -> Dict[str, Any]:
    """
    Parse capacity specification.

    Handles:
    - "3000mAh (typ.)"
    - "Min: 2900mAh, Nom: 3000mAh"
    - "3.0Ah nominal"
    - "Typical: 5000mAh, Minimum: 4850mAh"

    Args:
        text: String containing capacity specification

    Returns:
        Dictionary with 'nominal_ah', 'minimum_ah', 'unit_original'
    """
    result = {
        'nominal_ah': None,
        'minimum_ah': None,
        'unit_original': None
    }

    if not text:
        return result

    # Check for typical/nominal value
    typ_patterns = [
        r'(?:typ\.?|typical|nom\.?|nominal)[:\s]*([\d.]+)\s*(m?ah)',
        r'([\d.]+)\s*(m?ah)\s*\(?typ\.?\)?',
        r'([\d.]+)\s*(m?ah)',  # Fallback
    ]

    for pattern in typ_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            result['unit_original'] = unit

            if 'mah' in unit:
                result['nominal_ah'] = value / 1000
            else:
                result['nominal_ah'] = value
            break

    # Check for minimum value
    min_patterns = [
        r'(?:min\.?|minimum)[:\s]*([\d.]+)\s*(m?ah)',
        r'([\d.]+)\s*(m?ah)\s*\(?min\.?\)?',
    ]

    for pattern in min_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()

            if 'mah' in unit:
                result['minimum_ah'] = value / 1000
            else:
                result['minimum_ah'] = value
            break

    return result


def parse_current_rating(text: str, capacity_ah: Optional[float] = None
                         ) -> Dict[str, Any]:
    """
    Parse current rating from various formats.

    Handles:
    - "10A"
    - "2C" (requires capacity for conversion)
    - "10A (continuous)"
    - "15A for 10s"

    Args:
        text: String containing current specification
        capacity_ah: Nominal capacity in Ah (for C-rate conversion)

    Returns:
        Dictionary with current value and conditions
    """
    result = {
        'value_a': None,
        'is_c_rate': False,
        'c_rate': None,
        'duration_s': None,
        'is_pulse': False
    }

    if not text:
        return result

    # Check for C-rate
    c_rate_match = re.search(r'([\d.]+)\s*C\b', text)
    if c_rate_match:
        c_rate = float(c_rate_match.group(1))
        result['c_rate'] = c_rate
        result['is_c_rate'] = True

        if capacity_ah:
            result['value_a'] = c_rate * capacity_ah

    # Check for direct Amperage
    amp_match = re.search(r'([\d.]+)\s*A\b(?!\s*h)', text)
    if amp_match and result['value_a'] is None:
        result['value_a'] = float(amp_match.group(1))

    # Check for pulse duration
    duration_match = re.search(r'(?:for\s+)?(\d+)\s*s(?:ec)?', text)
    if duration_match:
        result['duration_s'] = float(duration_match.group(1))
        result['is_pulse'] = True

    # Check for pulse keywords
    if re.search(r'pulse|peak|burst', text, re.IGNORECASE):
        result['is_pulse'] = True

    return result


# =============================================================================
# DIMENSIONS PARSING
# =============================================================================

def parse_dimensions(text: str, cell_format: str = None) -> Dict[str, Any]:
    """
    Parse cell dimensions from various formats.

    Handles:
    - Cylindrical: "Ø21 x 70mm", "21700", "18.4 x 65.0 mm"
    - Pouch: "100 x 150 x 10 mm" (L x W x T)
    - Prismatic: "148 x 91 x 27 mm" (L x W x H)

    Args:
        text: String containing dimension specification
        cell_format: One of 'cylindrical', 'pouch', 'prismatic'

    Returns:
        Dictionary with parsed dimensions
    """
    result = {}

    if not text:
        return result

    # Cylindrical format: Ø21 x 70
    cyl_patterns = [
        r'[Øø∅]?\s*([\d.]+)\s*[x×]\s*([\d.]+)\s*(?:mm)?',
        r'([\d.]+)\s*mm?\s*[x×]\s*([\d.]+)\s*mm?',
    ]

    if cell_format == 'cylindrical' or re.search(r'[Øø∅]', text):
        for pattern in cyl_patterns:
            match = re.search(pattern, text)
            if match:
                dim1 = float(match.group(1))
                dim2 = float(match.group(2))

                # Smaller value is diameter, larger is height
                if dim1 < dim2:
                    result['diameter_mm'] = dim1
                    result['height_mm'] = dim2
                else:
                    result['diameter_mm'] = dim2
                    result['height_mm'] = dim1
                break

    # Three-dimension format: L x W x T/H
    three_dim_match = re.search(
        r'([\d.]+)\s*[x×*]\s*([\d.]+)\s*[x×*]\s*([\d.]+)\s*(?:mm)?',
        text
    )

    if three_dim_match:
        dims = sorted([
            float(three_dim_match.group(1)),
            float(three_dim_match.group(2)),
            float(three_dim_match.group(3))
        ], reverse=True)

        if cell_format == 'pouch':
            result['length_mm'] = dims[0]
            result['width_mm'] = dims[1]
            result['thickness_mm'] = dims[2]
        elif cell_format == 'prismatic':
            result['length_mm'] = dims[0]
            result['width_mm'] = dims[1]
            result['height_mm'] = dims[2]
        else:
            # Default to longest=length, middle=width, shortest=thickness/height
            result['length_mm'] = dims[0]
            result['width_mm'] = dims[1]
            result['thickness_mm'] = dims[2]

    return result


# =============================================================================
# CYCLE LIFE PARSING
# =============================================================================

def parse_cycle_life(text: str) -> Dict[str, Any]:
    """
    Parse cycle life specification with conditions.

    Handles:
    - "500 cycles at 80% DOD"
    - "2000 times (0.5C/0.5C)"
    - "≥800 cycles to 80% capacity"
    - "1000 cycles @1C charge/1C discharge, 25°C"

    Args:
        text: String containing cycle life specification

    Returns:
        Dictionary with cycle life and test conditions
    """
    result = {
        'cycles': None,
        'end_of_life_soh_percent': 80.0,  # Default to 80%
        'dod_percent': None,
        'charge_rate_c': None,
        'discharge_rate_c': None,
        'temperature_c': None,
        'notes': None
    }

    if not text:
        return result

    # Extract cycle count
    cycle_patterns = [
        r'[≥>]?\s*([\d,]+)\s*(?:cycles?|times)',
        r'(?:cycles?|times)[:\s]+([\d,]+)',
    ]

    for pattern in cycle_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result['cycles'] = int(match.group(1).replace(',', ''))
            break

    # Extract DOD
    dod_match = re.search(r'(\d+)\s*%\s*DOD', text, re.IGNORECASE)
    if dod_match:
        result['dod_percent'] = float(dod_match.group(1))

    # Extract EOL SOH
    eol_patterns = [
        r'(?:to|at)\s+(\d+)\s*%\s*(?:capacity|SOH)',
        r'(\d+)\s*%\s*(?:remaining|retention)',
    ]
    for pattern in eol_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result['end_of_life_soh_percent'] = float(match.group(1))
            break

    # Extract C-rates (charge/discharge)
    c_rate_match = re.search(r'([\d.]+)\s*C\s*/\s*([\d.]+)\s*C', text)
    if c_rate_match:
        result['charge_rate_c'] = float(c_rate_match.group(1))
        result['discharge_rate_c'] = float(c_rate_match.group(2))
    else:
        # Single C-rate for both
        single_c = re.search(r'@?\s*([\d.]+)\s*C(?!\s*/)', text)
        if single_c:
            rate = float(single_c.group(1))
            result['charge_rate_c'] = rate
            result['discharge_rate_c'] = rate

    # Extract temperature
    temp_match = re.search(r'([-+]?\d+)\s*°?C', text)
    if temp_match:
        result['temperature_c'] = float(temp_match.group(1))

    # Store original text as notes
    result['notes'] = text.strip()

    return result


# =============================================================================
# DERIVED PROPERTY CALCULATIONS
# =============================================================================

def calculate_energy(voltage_nominal: float, capacity_ah: float) -> Dict[str, Any]:
    """
    Calculate energy in Wh.

    Args:
        voltage_nominal: Nominal voltage in V
        capacity_ah: Nominal capacity in Ah

    Returns:
        Dictionary with value, source, and calculation details
    """
    if voltage_nominal is None or capacity_ah is None:
        return {'value': None, 'source': 'missing', 'calculation': None}

    energy = voltage_nominal * capacity_ah
    return {
        'value': round(energy, 2),
        'source': 'calculated',
        'calculation': f"{voltage_nominal}V × {capacity_ah}Ah"
    }


def calculate_max_power(voltage: float, current_continuous: float = None,
                        current_pulse: float = None) -> Dict[str, Any]:
    """
    Calculate maximum power with fallback logic.

    Prefers pulse current if available, falls back to continuous.

    Args:
        voltage: Nominal voltage in V
        current_continuous: Max continuous discharge current in A
        current_pulse: Max pulse discharge current in A

    Returns:
        Dictionary with value, source, calculation, and pulse_data_available flag
    """
    if voltage is None:
        return {'value': None, 'source': 'missing', 'pulse_data_available': False}

    # Prefer pulse current
    if current_pulse is not None:
        power = voltage * current_pulse
        return {
            'value': round(power, 1),
            'source': 'calculated_from_pulse',
            'calculation': f"{voltage}V × {current_pulse}A (pulse)",
            'pulse_data_available': True
        }

    # Fallback to continuous
    if current_continuous is not None:
        power = voltage * current_continuous
        return {
            'value': round(power, 1),
            'source': 'calculated_from_continuous',
            'calculation': f"{voltage}V × {current_continuous}A (continuous)",
            'pulse_data_available': False
        }

    return {'value': None, 'source': 'missing', 'pulse_data_available': False}


def calculate_volume(cell_format: str, dimensions: Dict) -> Dict[str, Any]:
    """
    Calculate cell volume based on format.

    Args:
        cell_format: One of 'cylindrical', 'pouch', 'prismatic'
        dimensions: Dictionary with relevant dimension values

    Returns:
        Dictionary with volume in mL, source, and calculation method
    """
    if not dimensions:
        return {'value': None, 'source': 'missing', 'calculation': None}

    if cell_format == 'cylindrical':
        diameter = dimensions.get('diameter_mm')
        height = dimensions.get('height_mm')

        if diameter is None or height is None:
            return {'value': None, 'source': 'missing', 'calculation': None}

        # Volume = π × r² × h, convert mm³ to mL (cm³)
        radius_cm = diameter / 20  # mm to cm, then /2 for radius
        height_cm = height / 10    # mm to cm
        volume = math.pi * (radius_cm ** 2) * height_cm

        return {
            'value': round(volume, 2),
            'source': 'calculated',
            'calculation': 'π × (d/2)² × h'
        }

    elif cell_format == 'pouch':
        length = dimensions.get('length_mm')
        width = dimensions.get('width_mm')
        thickness = dimensions.get('thickness_mm')

        if any(v is None for v in [length, width, thickness]):
            return {'value': None, 'source': 'missing', 'calculation': None}

        volume = (length * width * thickness) / 1000  # mm³ to cm³

        return {
            'value': round(volume, 2),
            'source': 'calculated',
            'calculation': 'L × W × T / 1000'
        }

    elif cell_format == 'prismatic':
        length = dimensions.get('length_mm')
        width = dimensions.get('width_mm')
        height = dimensions.get('height_mm')

        if any(v is None for v in [length, width, height]):
            return {'value': None, 'source': 'missing', 'calculation': None}

        volume = (length * width * height) / 1000  # mm³ to cm³

        return {
            'value': round(volume, 2),
            'source': 'calculated',
            'calculation': 'L × W × H / 1000'
        }

    return {'value': None, 'source': 'unknown_format', 'calculation': None}


def calculate_densities(energy_wh: float, max_power_w: float,
                        weight_g: float, volume_ml: float,
                        pulse_data_available: bool = False) -> Dict[str, Any]:
    """
    Calculate gravimetric and volumetric densities.

    Args:
        energy_wh: Total energy in Wh
        max_power_w: Maximum power in W
        weight_g: Cell weight in grams
        volume_ml: Cell volume in mL (cm³)
        pulse_data_available: Whether pulse current data was used for power

    Returns:
        Dictionary with all density values
    """
    result = {
        'energy_density_gravimetric_wh_per_kg': None,
        'power_density_gravimetric_w_per_kg': None,
        'energy_density_volumetric_wh_per_l': None,
        'power_density_volumetric_w_per_l': None,
        'pulse_data_available': pulse_data_available
    }

    weight_kg = weight_g / 1000 if weight_g else None
    volume_l = volume_ml / 1000 if volume_ml else None

    if energy_wh is not None:
        if weight_kg:
            result['energy_density_gravimetric_wh_per_kg'] = round(
                energy_wh / weight_kg, 1
            )
        if volume_l:
            result['energy_density_volumetric_wh_per_l'] = round(
                energy_wh / volume_l, 1
            )

    if max_power_w is not None:
        if weight_kg:
            result['power_density_gravimetric_w_per_kg'] = round(
                max_power_w / weight_kg, 1
            )
        if volume_l:
            result['power_density_volumetric_w_per_l'] = round(
                max_power_w / volume_l, 1
            )

    return result


# =============================================================================
# TABLE LAYOUT DETECTION
# =============================================================================

def detect_table_layout(table_text: str, num_columns: int = None
                       ) -> Dict[str, Any]:
    """
    Detect the layout pattern of a specification table.

    Args:
        table_text: Text content of the table
        num_columns: Number of columns if known

    Returns:
        Dictionary with detected pattern and confidence
    """
    result = {
        'pattern': 'unknown',
        'confidence': 'low',
        'indicators': []
    }

    if not table_text:
        return result

    text_lower = table_text.lower()

    # Check for Pattern D: Multi-product comparison
    # Look for multiple model numbers in header row
    if (re.search(r'(e\d+[a-z]+|model\s*[a-z]|type\s*[a-z])', text_lower,
                  re.IGNORECASE)
        and num_columns and num_columns > 3):
        result['pattern'] = 'comparison_table'
        result['confidence'] = 'medium'
        result['indicators'].append('Multiple product columns detected')
        return result

    # Check for Pattern B: Multi-condition tables
    if re.search(r'(item|條項).*?(condition|條件).*?(specification|規格)',
                 text_lower, re.IGNORECASE):
        result['pattern'] = 'multi_condition'
        result['confidence'] = 'high'
        result['indicators'].append('Item/Condition/Specification headers found')
        return result

    # Check for numbered items (common in Samsung/LG)
    if re.search(r'\b[12]\.[0-9]\s+\w+', text_lower):
        result['pattern'] = 'multi_condition'
        result['confidence'] = 'medium'
        result['indicators'].append('Numbered item format (e.g., 2.1, 2.2)')
        return result

    # Check for Pattern A: Key-value (2-column)
    if num_columns == 2:
        result['pattern'] = 'key_value'
        result['confidence'] = 'high'
        result['indicators'].append('Two-column table detected')
        return result

    # Check for Pattern C: Visual grouping (indentation-based)
    if re.search(r'^\s{2,}', table_text, re.MULTILINE):
        result['pattern'] = 'visual_grouping'
        result['confidence'] = 'medium'
        result['indicators'].append('Indentation-based hierarchy detected')
        return result

    return result


# =============================================================================
# CONFIDENCE SCORING
# =============================================================================

def calculate_confidence(extracted_data: Dict[str, Any],
                        required_fields: List[str] = None) -> Dict[str, str]:
    """
    Calculate confidence scores for each section of extracted data.

    Args:
        extracted_data: The extracted cell data dictionary
        required_fields: List of required field paths (e.g., ['capacity.nominal_ah'])

    Returns:
        Dictionary with confidence scores per section
    """
    if required_fields is None:
        required_fields = [
            'cell_info.manufacturer',
            'cell_info.model_number',
            'electrical.capacity.nominal_ah',
            'electrical.voltage.nominal_v',
        ]

    scores = {
        'mechanical': 'medium',
        'electrical': 'medium',
        'temperature': 'medium',
        'lifetime': 'medium',
        'overall': 'medium'
    }

    # Helper to safely get nested values
    def get_nested(data: dict, path: str):
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    # Check required fields
    missing_required = 0
    for field in required_fields:
        if get_nested(extracted_data, field) is None:
            missing_required += 1

    if missing_required == 0:
        scores['overall'] = 'high'
    elif missing_required <= 1:
        scores['overall'] = 'medium'
    else:
        scores['overall'] = 'low'

    # Score each section based on completeness
    sections = {
        'mechanical': ['weight_g', 'volume_ml'],
        'electrical': ['capacity.nominal_ah', 'voltage.nominal_v',
                      'impedance.acir.value_mohm'],
        'temperature': ['operating.charge.min_c', 'operating.discharge.min_c'],
        'lifetime': ['cycle_life.cycles']
    }

    for section, fields in sections.items():
        section_data = extracted_data.get(section, {})
        found = 0
        for field in fields:
            if get_nested(section_data, field) is not None:
                found += 1

        if found == len(fields):
            scores[section] = 'high'
        elif found > 0:
            scores[section] = 'medium'
        else:
            scores[section] = 'low'

    return scores


# =============================================================================
# VALIDATION UTILITIES
# =============================================================================

def validate_value_range(value: float, field_name: str) -> Tuple[bool, str]:
    """
    Validate that a value falls within expected ranges.

    Args:
        value: The value to validate
        field_name: Name of the field for lookup

    Returns:
        Tuple of (is_valid, warning_message)
    """
    ranges = {
        'capacity_ah': (0.01, 500),       # Ah
        'voltage_nominal': (2.5, 4.5),    # V
        'voltage_max': (3.0, 5.0),        # V
        'voltage_min': (1.0, 3.5),        # V
        'impedance_mohm': (0.1, 500),     # mΩ
        'weight_g': (1, 10000),           # g
        'temperature_c': (-60, 100),      # °C
        'current_a': (0.01, 1000),        # A
        'cycles': (1, 100000),            # cycles
    }

    if field_name not in ranges:
        return (True, '')

    min_val, max_val = ranges[field_name]

    if value is None:
        return (True, '')

    if value < min_val or value > max_val:
        return (
            False,
            f"{field_name} value {value} outside expected range "
            f"[{min_val}, {max_val}]"
        )

    return (True, '')


# =============================================================================
# MAIN EXTRACTION ORCHESTRATOR
# =============================================================================

def extract_cell_specs(raw_data: Dict[str, str]) -> Dict[str, Any]:
    """
    Main orchestrator function to extract and normalize cell specifications.

    Takes raw text data organized by field and produces standardized output.

    Args:
        raw_data: Dictionary with raw text for each field type
                 e.g., {'capacity': '3200mAh', 'voltage': '3.67V nominal'}

    Returns:
        Standardized cell specification dictionary
    """
    result = {
        'cell_info': {},
        'mechanical': {},
        'electrical': {},
        'temperature': {},
        'lifetime': {},
        'derived': {},
        'extraction_metadata': {
            'fields_extracted': 0,
            'fields_calculated': 0,
            'fields_missing': [],
            'warnings': []
        }
    }

    # Track extraction success
    extracted = 0
    calculated = 0
    missing = []
    warnings = []

    # --- Extract Capacity ---
    if 'capacity' in raw_data:
        cap = parse_capacity(raw_data['capacity'])
        result['electrical']['capacity'] = cap
        if cap['nominal_ah']:
            extracted += 1
        else:
            missing.append('capacity.nominal_ah')
    else:
        missing.append('capacity')

    # --- Extract Voltage ---
    # (Would need more parsing logic here)

    # --- Calculate derived properties ---
    if result['electrical'].get('capacity', {}).get('nominal_ah'):
        nominal_v = result['electrical'].get('voltage', {}).get('nominal_v', 3.6)
        cap_ah = result['electrical']['capacity']['nominal_ah']

        energy = calculate_energy(nominal_v, cap_ah)
        if energy['value']:
            result['derived']['energy_wh'] = energy
            calculated += 1

    # Update metadata
    result['extraction_metadata']['fields_extracted'] = extracted
    result['extraction_metadata']['fields_calculated'] = calculated
    result['extraction_metadata']['fields_missing'] = missing
    result['extraction_metadata']['warnings'] = warnings

    return result


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Unit conversion
    'normalize_units',

    # Parsing functions
    'parse_temperature_range',
    'extract_dcir_spec',
    'parse_capacity',
    'parse_current_rating',
    'parse_dimensions',
    'parse_cycle_life',

    # Calculations
    'calculate_energy',
    'calculate_max_power',
    'calculate_volume',
    'calculate_densities',

    # Table detection
    'detect_table_layout',

    # Validation
    'calculate_confidence',
    'validate_value_range',

    # Main orchestrator
    'extract_cell_specs',
]


# =============================================================================
# TESTING / EXAMPLES
# =============================================================================

if __name__ == '__main__':
    # Example usage
    print("=== Battery Cell Extractor Test ===\n")

    # Test temperature parsing
    print("Temperature parsing:")
    test_temps = ["0~45°C", "-20°C to 60°C", "-30 - +55 deg C", "0 to 45°C"]
    for temp in test_temps:
        print(f"  '{temp}' -> {parse_temperature_range(temp)}")

    print("\nUnit normalization:")
    test_units = [("3200mAh", "ah"), ("45mΩ", "ohm"), ("3.2Ah", "mah")]
    for value, target in test_units:
        print(f"  '{value}' -> {target}: {normalize_units(value, target)}")

    print("\nImpedance parsing:")
    test_dcir = ["DCIR @ 50% SOC, 25°C", "≤18mΩ (AC 1kHz)", "45mΩ at 25°C"]
    for dcir in test_dcir:
        print(f"  '{dcir}' -> {extract_dcir_spec(dcir)}")

    print("\nCycle life parsing:")
    test_cycles = ["500 cycles at 80% DOD", "2000 times (0.5C/0.5C)",
                   "≥800 cycles to 80% capacity"]
    for cycle in test_cycles:
        print(f"  '{cycle}' -> {parse_cycle_life(cycle)}")
