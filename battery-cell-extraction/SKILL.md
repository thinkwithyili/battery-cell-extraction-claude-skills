---
name: battery-cell-extraction
description: Extract and normalize Li-ion battery cell specifications from supplier PDFs to a standardized format. Handles heterogeneous supplier data formats including cylindrical (18650, 21700, 4680), pouch, and prismatic cells.
---

# Battery Cell Datasheet Extraction Skill

## Overview
This skill extracts and standardizes battery cell specifications from supplier datasheets (PDFs). It handles variations in terminology, units, and table formats across different manufacturers.

---

## Section A: Data Identification

### 1. Locate Specification Tables

**Primary locations**: "Electrical Characteristics", "Physical Specifications", "General Specifications", "Nominal Specification" tables.

**Secondary sources**: Header/footer areas, performance graphs, notes sections.

### 2. Table Layout Patterns

| Pattern | Identifier | Handling |
|---------|-----------|----------|
| **A: Key-Value** | 2-column (param \| value) | Direct mapping |
| **B: Multi-Condition** | 3+ columns with merged cells | Inherit parent from previous row for empty cells |
| **C: Visual Grouping** | Indentation-based, no borders | Use text position for hierarchy |
| **D: Multi-Product** | Multiple model columns | Extract each column as separate cell object |

### 3. Common Field Variations

| Standard Field | Variations |
|---------------|------------|
| Nominal Capacity | Rated Capacity, Typical Capacity, Cell Capacity |
| Nominal Voltage | Cell Voltage, Operating Voltage |
| DCIR | DC Internal Resistance, AC Impedance, Internal Resistance |
| Max Discharge | Maximum Continuous Discharge, Discharge Current |

---

## Section B: Extraction Procedures

### 1. Basic Cell Information
Extract: **Manufacturer**, **Model Number**, **Chemistry** (NMC/LFP/NCA/NCMA), **Cell Format** (cylindrical/pouch/prismatic), **Format Code** (18650/21700/4680).

### 2. Electrical Properties

| Property | Notes | Conversion |
|----------|-------|------------|
| **Capacity** | Look for Nominal/Rated/Typical; may have Typ/Min values | mAh → Ah (÷1000) |
| **Voltage** | Nominal, Max (charge cutoff), Min (discharge cutoff) | — |
| **Impedance** | ACIR at 1kHz most common; record test conditions | Ω → mΩ (×1000) |
| **Current** | Continuous discharge, charge, pulse (with duration) | C-rate → A: C × Capacity(Ah) |

### 3. Temperature Properties
Parse formats: "0~45°C", "0°C to 45°C", "-20 to 60 deg C" → `{min_c, max_c}`

Extract separately for: charge, discharge, storage ranges.

### 4. Physical Properties

| Format | Dimensions |
|--------|-----------|
| **Cylindrical** | Diameter (mm), Height (mm) |
| **Pouch** | Length × Width × Thickness (mm) |
| **Prismatic** | Length × Width × Height (mm) |

Weight: grams (convert kg → g if needed).

### 5. Cycle Life
Parse: "500 cycles at 80% DOD" → `{cycles: 500, dod: 80}`

Record: temperature, C-rates, EOL SOH threshold.

---

## Section C: Normalization Rules

### 1. Standard Field Names
Use canonical names: `capacity.nominal_ah`, `voltage.nominal_v`, `impedance.acir.value_mohm`, `current.max_continuous_discharge_a`, `temperature.operating.charge.min_c`.

### 2. Unit Conversions

| From | To | Operation |
|------|----|-----------|
| mAh | Ah | ÷ 1000 |
| Ω | mΩ | × 1000 |
| kg | g | × 1000 |
| C-rate | A | C × Capacity(Ah) |

### 3. Missing/Ambiguous Data
- Not found: set `null`, add to `fields_missing`
- Ambiguous: extract best estimate, flag "medium" confidence
- Multiple values: extract all (typ/min/max)
- Store `unit_original` field

### 4. Reference Files
- **`normalization_rules.yaml`**: Supplier-specific patterns
- **`validation_schema.json`**: JSON schema for output validation
- **`scripts/extractor.py`**: Deterministic parsing functions

---

## Section D: Validation

### 1. Required Fields
Manufacturer, Model Number, Nominal Capacity, Nominal Voltage, Cell Format.

### 2. Value Ranges

| Property | Valid Range |
|----------|-------------|
| Capacity | 0.5 - 200 Ah |
| Nominal Voltage | 2.5 - 4.5 V |
| Max Voltage | ≤ 5.0 V |
| DCIR | 1 - 200 mΩ |
| Weight | 10 - 5000 g |

### 3. Confidence Scoring
- **High**: All fields found, clear values, known format
- **Medium**: Some inferred, ambiguous conditions
- **Low**: Many missing, unfamiliar format, OCR issues

---

## Section E: Output Format

### 1. JSON Structure
Output follows `validation_schema.json`. Top-level objects:
- `cell_info`: manufacturer, model, chemistry, format, confidence
- `mechanical`: dimensions, weight, volume
- `electrical`: capacity, voltage, impedance, current
- `temperature`: operating ranges (charge/discharge/storage)
- `lifetime`: cycle life specifications
- `derived`: calculated properties
- `extraction_metadata`: fields_extracted, fields_missing, warnings

### 2. Derived Properties (calculate if not provided)

| Property | Calculation |
|----------|-------------|
| Energy (Wh) | Voltage × Capacity |
| Max Power (W) | Voltage × Max Discharge Current |
| Gravimetric Energy (Wh/kg) | Energy ÷ Weight |
| Volumetric Energy (Wh/L) | Energy ÷ Volume |

### 3. Export to Sheets
```bash
python sheets_exporter.py output.json --sheet "Battery Cell Database"
```

---

## Worked Example: Samsung INR21700-50E

**Input** (Pattern B - multi-condition):
```
2.1 Capacity: Typical 5000mAh, Minimum 4850mAh
2.2 Voltage: Nominal 3.6V, Charge 4.2V, Cutoff 2.5V
2.3 Impedance: AC 1kHz ≤18mΩ (50% SOC, 25°C)
```

**Extraction**:
1. Pattern B identified → parse nested structure
2. Capacity: typical=5.0Ah, minimum=4.85Ah
3. Voltage: nominal=3.6V, max=4.2V, min=2.5V
4. Impedance: ACIR=18mΩ at 1kHz, 50% SOC, 25°C

**Output** (abbreviated):
```json
{
  "cell_info": {"manufacturer": "Samsung", "model_number": "INR21700-50E", "chemistry": "NMC", "cell_format": "cylindrical"},
  "electrical": {
    "capacity": {"nominal_ah": 5.0, "minimum_ah": 4.85},
    "voltage": {"nominal_v": 3.6, "max_v": 4.2, "min_v": 2.5},
    "impedance": {"acir": {"value_mohm": 18.0, "frequency_hz": 1000, "temperature_c": 25, "soc_percent": 50}}
  },
  "derived": {"energy_wh": {"value": 18.0, "calculation": "3.6V × 5.0Ah"}}
}
```

---

## Quick Tips
1. Start with manufacturer ID → predicts format patterns
2. Check notes/footnotes → contain critical conditions
3. Cross-reference values → verify energy = V×Ah
4. When uncertain → flag with warnings, don't guess
