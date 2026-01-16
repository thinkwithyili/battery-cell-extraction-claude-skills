# Battery Cell Data Extraction with Claude Skills

A workflow for extracting battery cell specifications from supplier PDF datasheets and exporting them to Google Sheets using Claude Skills.

---

## Overview

This project provides a Claude Skill that automates the extraction and standardization of Li-ion battery cell specifications from supplier datasheets. The workflow converts unstructured PDF data into structured JSON, which can then be exported to Google Sheets for database building and Ragone plot analysis.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  PDF Datasheet  │ ─▶ │  Claude Skills  │ ─▶ │   JSON Output   │ ─▶ │  Google Sheets  │
│    (Input)      │    │   Extraction    │    │   (Download)    │    │    (Database)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## What is Claude Skills?

**Claude Skills** are modular, markdown-based instruction packages that teach Claude how to perform specialized tasks. Key benefits:

- **Portable**: Work across Claude.ai, Claude Code, and API
- **Auto-loading**: Claude automatically detects and loads relevant skills based on context
- **Composable**: Multiple skills can work together for complex workflows
- **Iterative**: Skills can be refined and improved over time

---

## What's Included

| Component | Size | Features |
|-----------|------|----------|
| **SKILL.md** | ~13KB | 5 instruction sections, 3 worked examples, pattern recognition guide |
| **extractor.py** | ~34KB | 15+ parsing functions, unit conversion, derived calculations |
| **normalization_rules.yaml** | ~19KB | 4 layout patterns, 7 supplier mappings, 100+ field aliases |
| **validation_schema.json** | ~38KB | JSON Schema v7 with complete property definitions |

---

## Quick Start

1. **Install the Skill**:
   - Create a zip file of the `battery-cell-extraction` folder
   - Open Claude settings and import the zip file to add the custom skill
2. **Drop a PDF** into Claude and say: *"Extract cell data sheets for me."*
3. Claude automatically loads this skill and extracts structured data
4. **Copy the JSON** output to your local `output/` folder
5. (Optional) **Export to Google Sheets**:
   - Refer to instructions and demo scripts in the `jsonToGoogleSheet/` folder
   - Run the exporter: `python jsonToGoogleSheet/sheets_exporter.py output/cell_data.json`

---

## Complete Workflow

### Step 1: Prepare Your PDF Datasheet

Collect battery cell specification PDF from your supplier (e.g., LG, Samsung, EVE, A123, SK On).

### Step 2: Extract Data Using Claude Skills

1. Open **Claude.ai** or **Claude Code**
2. Upload/attach the PDF datasheet
3. Ask Claude to extract the battery specifications

   ```
   Please extract the battery cell specifications from this datasheet 
   using the battery-cell-extraction skill.
   ```

4. Claude automatically:
   - Detects the skill based on keywords ("battery", "datasheet", "specification")
   - Identifies table layouts (2-column, multi-condition, visual grouping, etc.)
   - Extracts and normalizes specifications using `normalization_rules.yaml`
   - Validates data against `validation_schema.json`

### Step 3: Download JSON Output

Claude generates a standardized JSON file with extracted data:

```json
{
  "cell_info": {
    "manufacturer": "Samsung SDI",
    "model_number": "INR21700-50E",
    "chemistry": "NCA",
    "cell_format": "cylindrical"
  },
  "electrical": {
    "capacity": {"nominal_ah": 5.0, "minimum_ah": 4.85},
    "voltage": {"nominal_v": 3.6, "max_v": 4.2, "min_v": 2.5}
  },
  "derived": {
    "energy_density_wh_kg": 263.5,
    "power_density_w_kg": 789.1
  },
  "extraction_metadata": {
    "confidence_overall": "high",
    "fields_missing": ["dcir"],
    "warnings": ["DCIR not provided"]
  }
}
```

**Download the JSON file** from Claude's output to your local machine.

### Step 4: Upload to Google Sheets
 
We have provided a dedicated set of scripts and instructions in the `jsonToGoogleSheet/` folder to help you export the JSON data.

1. **Setup**: Follow the guides in `jsonToGoogleSheet/SHEETS_SETUP.md` to configure Google API credentials.
2. **Export**: Run the exporter script:
   ```bash
   python jsonToGoogleSheet/sheets_exporter.py output/cell2.json --sheet "Battery Cell Database"
   ```
3. **Batch Export**:
   ```bash
   python jsonToGoogleSheet/sheets_exporter.py --batch-dir output/ --sheet "My Cells"
   ```
4. **CSV Option**:
   ```bash
   python jsonToGoogleSheet/sheets_exporter.py output/cell2.json --csv-only
   ```

---

## Data Validation & Quality Assurance

LLMs can hallucinate. This skill includes comprehensive validation to catch errors before they pollute your database:

### Schema Validation

The `validation_schema.json` uses JSON Schema v7 to enforce structure. Required fields like `manufacturer`, `model_number`, and `cell_format` must be present. Chemistry values must match an allowed list (NMC, LFP, NCA, etc.). This catches structural errors immediately.

### Range Checking

Sanity checks prevent obviously wrong values from slipping through. Capacity must be > 0 (typically 0.5-200 Ah). Voltage must fall within Li-ion limits (nominal: 2.5-4.5V, max: ≤ 5V). If DCIR shows 5000 mΩ, something's wrong—flag it.

### Confidence Scoring

Each section gets a confidence rating—high, medium, or low. High means all fields found with clear values. Medium indicates some values were inferred or conditions were ambiguous. Low flags OCR issues or unfamiliar formats. This helps you prioritize which extractions need human review.

### Explicit Flagging

Missing fields are listed in a `fields_missing` array. Warnings capture specific issues like "Min discharge voltage not specified" or "DCIR provided without temperature condition." No silent failures—everything uncertain gets documented.

---

## Project Structure

```
claude-skills-vault/
├── README.md                         # This file
└── cellDataExt_ClaudeSkills/
    ├── battery-cell-extraction/
    │   ├── SKILL.md                  # Claude Skill definition
    │   ├── sheets_exporter.py        # Google Sheets export script
    │   ├── SHEETS_SETUP.md           # Google API setup guide
    │   ├── normalization_rules.yaml  # Supplier-specific format mappings
    │   ├── validation_schema.json    # Output validation schema
    │   └── scripts/
    │       └── extractor.py          # Text parsing utilities
    ├── celldataSheet/                # Sample datasheets
    └── plan/                         # Planning documents
```

---

## Supported Suppliers

Tested with datasheets from:
- Samsung SDI
- LG Energy Solution
- A123 Systems
- Molicel


---

## License

MIT License
