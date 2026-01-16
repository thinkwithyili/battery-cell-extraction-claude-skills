"""
Google Sheets Exporter for Battery Cell Data.

This module provides functionality to export extracted battery cell data 
from JSON format to Google Sheets using the gspread library. Designed 
for building a Ragone plot database (Power Density vs Energy Density).

Requirements:
    pip install gspread google-auth google-auth-oauthlib

Setup:
    1. Create a Google Cloud project at https://console.cloud.google.com/
    2. Enable the Google Sheets API
    3. Create a service account and download credentials.json
    4. Share your Google Sheet with the service account email
    5. Place credentials.json in the same directory as this script
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


# =============================================================================
# CONFIGURATION - Edit these values to run without terminal arguments
# =============================================================================
# To use: Simply edit the values below and run `python3 sheets_exporter.py`
# without any command-line arguments. The script will use these settings.
#
# If you provide command-line arguments, they will override these settings.
# =============================================================================

CONFIG = {
    # -------------------------------------------------------------------------
    # Input Settings (choose ONE of the following modes)
    # -------------------------------------------------------------------------

    # OPTION A: Single file mode
    # Set this to the path of a single JSON file to export
    # Example: "/path/to/your/battery_data.json"
    "json_file": None,

    # OPTION B: Batch mode
    # Set this to a directory containing multiple JSON files
    # Example: "/path/to/json_files_folder"
    "batch_directory": "cellDataExt_ClaudeSkills/output",

    # -------------------------------------------------------------------------
    # Google Sheets Settings
    # -------------------------------------------------------------------------

    # Name of the Google Sheet (will be created if it doesn't exist)
    "spreadsheet_name": "cell-data-sheet",

    # Name of the worksheet/tab within the spreadsheet
    "worksheet_name": "Battery Cells",

    # Path to your Google service account credentials JSON file
    "credentials_path": "credentials/battery-cell-database-credentials.json",

    # -------------------------------------------------------------------------
    # Export Options
    # -------------------------------------------------------------------------

    # Set to True to only generate CSV files (no Google Sheets upload)
    "csv_only": False,
}


# =============================================================================
# COLUMN DEFINITIONS
# Aligned with SKILL.md Section E output format and Section C normalization
# =============================================================================

# Column definitions for Ragone plot database
# Each tuple: (column_name, json_path, unit)
# Paths match SKILL.md canonical field names (Section C.1) and output format (Section E)
RAGONE_COLUMNS = [
    # -------------------------------------------------------------------------
    # Cell Identification (cell_info object)
    # -------------------------------------------------------------------------
    ("manufacturer", "cell_info.manufacturer", ""),
    ("model", "cell_info.model_number", ""),
    ("chemistry", "cell_info.chemistry", ""),
    ("format", "cell_info.cell_format", ""),
    ("format_code", "cell_info.cell_format_code", ""),

    # -------------------------------------------------------------------------
    # Electrical - Capacity (SKILL.md: capacity.nominal_ah, capacity.minimum_ah)
    # -------------------------------------------------------------------------
    ("nominal_capacity", "electrical.capacity.nominal_ah", "Ah"),
    ("minimum_capacity", "electrical.capacity.minimum_ah", "Ah"),

    # -------------------------------------------------------------------------
    # Electrical - Voltage (SKILL.md: voltage.nominal_v, voltage.max_v, voltage.min_v)
    # -------------------------------------------------------------------------
    ("max_voltage", "electrical.voltage.max_v", "V"),
    ("nominal_voltage", "electrical.voltage.nominal_v", "V"),
    ("min_voltage", "electrical.voltage.min_v", "V"),

    # -------------------------------------------------------------------------
    # Electrical - Impedance (SKILL.md: impedance.acir.value_mohm, impedance.dcir.value_mohm)
    # -------------------------------------------------------------------------
    ("acir", "electrical.impedance.acir.value_mohm", "mΩ"),
    ("dcir", "electrical.impedance.dcir.value_mohm", "mΩ"),

    # -------------------------------------------------------------------------
    # Electrical - Current (SKILL.md: current.max_continuous_discharge_a, etc.)
    # -------------------------------------------------------------------------
    ("max_continuous_discharge", "electrical.current.max_continuous_discharge_a", "A"),
    ("max_continuous_charge", "electrical.current.max_continuous_charge_a", "A"),
    ("standard_charge_current", "electrical.current.standard_charge_a", "A"),

    # -------------------------------------------------------------------------
    # Mechanical Properties (mechanical object)
    # -------------------------------------------------------------------------
    ("weight", "mechanical.weight_g", "g"),
    ("volume", "mechanical.volume_ml.value", "mL"),
    # Cylindrical dimensions
    ("diameter", "mechanical.cylindrical_dimensions.diameter_mm", "mm"),
    ("height", "mechanical.cylindrical_dimensions.height_mm", "mm"),
    # Pouch dimensions (alternative to cylindrical)
    ("length", "mechanical.pouch_dimensions.length_mm", "mm"),
    ("width", "mechanical.pouch_dimensions.width_mm", "mm"),
    ("thickness", "mechanical.pouch_dimensions.thickness_mm", "mm"),

    # -------------------------------------------------------------------------
    # Temperature Ranges (SKILL.md: temperature.operating.charge.min_c, etc.)
    # -------------------------------------------------------------------------
    ("charge_temp_min", "temperature.operating.charge.min_c", "°C"),
    ("charge_temp_max", "temperature.operating.charge.max_c", "°C"),
    ("discharge_temp_min", "temperature.operating.discharge.min_c", "°C"),
    ("discharge_temp_max", "temperature.operating.discharge.max_c", "°C"),

    # -------------------------------------------------------------------------
    # Lifetime (lifetime object)
    # -------------------------------------------------------------------------
    ("cycle_life", "lifetime.cycle_life.cycles", ""),
    ("eol_soh", "lifetime.cycle_life.eol_soh_percent", "%"),

    # -------------------------------------------------------------------------
    # Derived Metrics for Ragone Plot (SKILL.md Section E.3)
    # energy_wh may have typical/minimum structure OR value/source structure
    # -------------------------------------------------------------------------
    ("energy_wh", "derived.energy_wh.typical", "Wh"),
    ("energy_wh_value", "derived.energy_wh.value", "Wh"),
    # Energy Density (Wh/kg, Wh/L) - SKILL.md lines 302-303, 317-321
    ("energy_density_wh_kg", "derived.energy_density_gravimetric_wh_kg.value", "Wh/kg"),
    ("energy_density_wh_l", "derived.energy_density_volumetric_wh_l.value", "Wh/L"),
    # Power metrics - SKILL.md lines 299-301, 304-305
    ("max_power", "derived.max_discharge_power_w.value", "W"),
    ("power_density_w_kg", "derived.power_density_gravimetric_w_kg.value", "W/kg"),
    ("power_density_w_l", "derived.power_density_volumetric_w_l.value", "W/L"),

    # -------------------------------------------------------------------------
    # Extraction Metadata
    # -------------------------------------------------------------------------
    ("extraction_date", "extraction_metadata.extraction_date", ""),
    ("fields_extracted", "extraction_metadata.fields_extracted", ""),
    ("confidence", "cell_info.confidence_overall", ""),
]


def get_nested_value(data: Dict, path: str) -> Any:
    """
    Retrieve a nested value from a dictionary using dot notation.
    
    Args:
        data: The dictionary to search.
        path: Dot-separated path to the value (e.g., "cell_info.manufacturer").
        
    Returns:
        The value at the specified path, or None if not found.
    """
    keys = path.split(".")
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    
    return current


def json_to_row(json_data: Dict) -> List[Any]:
    """
    Convert a battery cell JSON object to a flat list for spreadsheet row.
    
    Args:
        json_data: Extracted battery cell data in JSON format.
        
    Returns:
        List of values in the order defined by RAGONE_COLUMNS.
    """
    row = []
    for col_name, json_path, unit in RAGONE_COLUMNS:
        value = get_nested_value(json_data, json_path)
        row.append(value)
    return row


def json_to_csv(json_data: Dict, output_path: Optional[str] = None) -> str:
    """
    Convert battery cell JSON to CSV format.
    
    Args:
        json_data: Extracted battery cell data in JSON format.
        output_path: Optional path to write CSV file.
        
    Returns:
        CSV string representation of the data.
    """
    headers = [col[0] for col in RAGONE_COLUMNS]
    row = json_to_row(json_data)
    
    # Build CSV string
    lines = [",".join(headers)]
    lines.append(",".join(str(v) if v is not None else "" for v in row))
    csv_content = "\n".join(lines)
    
    if output_path:
        Path(output_path).write_text(csv_content)
    
    return csv_content


def export_to_google_sheets(
    json_data: Dict,
    spreadsheet_name: str,
    credentials_path: str = "credentials.json",
    worksheet_name: str = "Battery Cells"
) -> Dict[str, Any]:
    """
    Export battery cell data to Google Sheets in transposed format.
    
    Layout:
        - Column A: Property names (Manufacturer, Cell model, etc.)
        - Column B: Units (mm, g, Ah, etc.)
        - Column C onwards: Each cell's data in its own column
    
    This function adds a new column for each battery cell. If the worksheet
    is empty, it will add property names and units first.
    
    Args:
        json_data: Extracted battery cell data in JSON format.
        spreadsheet_name: Name of the Google Sheet to export to.
        credentials_path: Path to the service account credentials JSON file.
        worksheet_name: Name of the worksheet/tab to use.
        
    Returns:
        Dictionary with export status and details.
        
    Raises:
        ImportError: If gspread is not installed.
        FileNotFoundError: If credentials file is not found.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError(
            "gspread and google-auth are required. "
            "Install with: pip install gspread google-auth"
        )
    
    # Check credentials file exists
    creds_path = Path(credentials_path)
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Credentials file not found at {credentials_path}. "
            "Please download service account credentials from Google Cloud Console."
        )
    
    # Setup credentials with required scopes
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_file(
        credentials_path, 
        scopes=scopes
    )
    
    # Authorize and get spreadsheet
    client = gspread.authorize(credentials)
    
    try:
        spreadsheet = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        # Create new spreadsheet if it doesn't exist
        spreadsheet = client.create(spreadsheet_name)
    
    # Get or create worksheet
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
        # Ensure worksheet has enough columns
        if worksheet.col_count < 100:
            worksheet.resize(cols=100)
    except gspread.WorksheetNotFound:
        # Create worksheet with enough rows for all properties
        worksheet = spreadsheet.add_worksheet(
            title=worksheet_name, 
            rows=len(RAGONE_COLUMNS) + 1,  # +1 for header row
            cols=100  # Plenty of columns for cells
        )
    
    # Check current data to determine if we need to add property/unit columns
    existing_data = worksheet.get_all_values()
    
    # Get property names and units
    property_names = [col[0] for col in RAGONE_COLUMNS]
    units = [col[2] for col in RAGONE_COLUMNS]
    
    # Get model name for column header
    model = get_nested_value(json_data, "cell_info.model_number") or "Unknown"
    
    # Check if the sheet is properly initialized with property names
    # by checking if the first cell contains the first property name
    sheet_initialized = False
    if existing_data and len(existing_data) > 0 and len(existing_data[0]) > 0:
        first_cell = existing_data[0][0] if existing_data[0] else ""
        # Check if first cell matches first property name
        sheet_initialized = (first_cell == property_names[0])
    
    if not sheet_initialized:
        # Clear the sheet and initialize with property names and units
        worksheet.clear()
        
        # Build the initial data with property names and units
        initial_data = []
        for prop_name, _, unit in RAGONE_COLUMNS:
            initial_data.append([prop_name, unit])
        
        # Update the sheet with initial structure
        worksheet.update(values=initial_data, range_name=f"A1:B{len(RAGONE_COLUMNS)}")
        
        # Set the next column for cell data
        next_col = 3  # Column C (1-indexed)
    else:
        # Check for duplicate: see if model already exists in the sheet
        # Model is typically in row 2 (index 1) - check all columns from C onwards
        if len(existing_data) > 1:  # Has at least 2 rows (model row exists)
            model_row = existing_data[1] if len(existing_data) > 1 else []
            # Check columns C onwards (index 2+)
            existing_models = model_row[2:] if len(model_row) > 2 else []
            if model in existing_models:
                return {
                    "status": "skipped",
                    "reason": "duplicate",
                    "model": model,
                    "message": f"Model '{model}' already exists in sheet",
                    "spreadsheet_url": spreadsheet.url
                }
        
        # Find the next empty column for new cell data
        # Check number of columns with data in first row
        max_cols = max(len(row) for row in existing_data) if existing_data else 2
        next_col = max_cols + 1
        # Ensure we start at column C minimum
        if next_col < 3:
            next_col = 3
    
    # Convert JSON to column data
    cell_values = json_to_row(json_data)
    
    # Add model name as header in row 0 (we'll insert a header row concept)
    # For simplicity, we'll use the model name in the first cell value position
    # Actually, let's put the cell data starting from row 1
    
    # Build column data: each property value goes in a row
    col_data = [[str(v) if v is not None else ""] for v in cell_values]
    
    # Convert column number to letter (A=1, B=2, C=3, etc.)
    col_letter = _col_num_to_letter(next_col)
    
    # Update the column with cell data
    cell_range = f"{col_letter}1:{col_letter}{len(RAGONE_COLUMNS)}"
    worksheet.update(values=col_data, range_name=cell_range)
    
    return {
        "status": "success",
        "spreadsheet_name": spreadsheet_name,
        "worksheet_name": worksheet_name,
        "model_added": model,
        "column_number": next_col,
        "spreadsheet_url": spreadsheet.url
    }


def _col_num_to_letter(col_num: int) -> str:
    """
    Convert a column number to Excel-style column letter (1=A, 2=B, ..., 27=AA).
    
    Args:
        col_num: Column number (1-indexed).
        
    Returns:
        Column letter(s) as string.
    """
    result = ""
    while col_num > 0:
        col_num, remainder = divmod(col_num - 1, 26)
        result = chr(65 + remainder) + result
    return result


def batch_export_to_sheets(
    json_files: List[str],
    spreadsheet_name: str,
    credentials_path: str = "credentials.json",
    worksheet_name: str = "Battery Cells"
) -> Dict[str, Any]:
    """
    Export multiple battery cell JSON files to Google Sheets.
    
    Args:
        json_files: List of paths to JSON files to export.
        spreadsheet_name: Name of the Google Sheet to export to.
        credentials_path: Path to the service account credentials JSON file.
        worksheet_name: Name of the worksheet/tab to use.
        
    Returns:
        Dictionary with batch export status and summary.
    """
    results = {
        "total": len(json_files),
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
        "models_added": [],
        "models_skipped": []
    }
    
    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                json_data = json.load(f)
            
            result = export_to_google_sheets(
                json_data,
                spreadsheet_name,
                credentials_path,
                worksheet_name
            )
            
            # Handle different result statuses
            if result.get("status") == "skipped":
                results["skipped"] += 1
                results["models_skipped"].append(result["model"])
            else:
                results["success"] += 1
                results["models_added"].append(result["model_added"])
            
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "file": json_file,
                "error": str(e)
            })
    
    return results


# =============================================================================
# CLI AND CONFIG-BASED EXECUTION
# =============================================================================

def run_from_config() -> None:
    """
    Run the exporter using settings from the CONFIG dictionary.

    This function allows you to run the script by simply editing the CONFIG
    values at the top of this file, without needing terminal arguments.

    Returns:
        None. Prints results to stdout.

    Raises:
        ValueError: If neither json_file nor batch_directory is set in CONFIG.
    """
    json_file = CONFIG.get("json_file")
    batch_dir = CONFIG.get("batch_directory")
    spreadsheet_name = CONFIG.get("spreadsheet_name", "cell-data-sheet")
    worksheet_name = CONFIG.get("worksheet_name", "Battery Cells")
    credentials_path = CONFIG.get("credentials_path",
                                   "battery-cell-database-credentials.json")
    csv_only = CONFIG.get("csv_only", False)

    # Validate configuration
    if not json_file and not batch_dir:
        print("=" * 60)
        print("ERROR: No input file specified!")
        print("=" * 60)
        print("\nPlease edit the CONFIG section at the top of this file:")
        print("  - Set 'json_file' to a single JSON file path, OR")
        print("  - Set 'batch_directory' to a folder of JSON files")
        print("\nAlternatively, run with command-line arguments:")
        print("  python3 sheets_exporter.py <json_file>")
        print("  python3 sheets_exporter.py --batch-dir <directory>")
        print("=" * 60)
        return

    # Run in batch mode if batch_directory is set
    if batch_dir:
        _run_batch_mode(batch_dir, spreadsheet_name, worksheet_name,
                        credentials_path, csv_only)
    else:
        _run_single_file_mode(json_file, spreadsheet_name, worksheet_name,
                              credentials_path, csv_only)


def _run_batch_mode(batch_dir: str, spreadsheet_name: str,
                    worksheet_name: str, credentials_path: str,
                    csv_only: bool) -> None:
    """
    Process all JSON files in a directory.

    Args:
        batch_dir: Path to directory containing JSON files.
        spreadsheet_name: Name of the Google Sheet.
        worksheet_name: Name of the worksheet tab.
        credentials_path: Path to credentials JSON file.
        csv_only: If True, only generate CSV files.
    """
    batch_path = Path(batch_dir)
    if not batch_path.exists():
        print(f"Error: Directory not found: {batch_dir}")
        return

    # Find all JSON files (exclude config/schema files)
    json_files = [
        str(f) for f in batch_path.glob("*.json")
        if not f.name.endswith(("-credentials.json", "_schema.json"))
    ]

    if not json_files:
        print(f"No JSON files found in: {batch_dir}")
        return

    print(f"Found {len(json_files)} JSON file(s) to process...")

    if csv_only:
        # Generate CSV for each file
        for json_file in json_files:
            with open(json_file, "r") as f:
                data = json.load(f)
            csv_path = Path(json_file).stem + ".csv"
            json_to_csv(data, csv_path)
            print(f"  CSV exported: {csv_path}")
        print(f"\nTotal: {len(json_files)} CSV files generated")
    else:
        # Batch export to Google Sheets
        results = batch_export_to_sheets(
            json_files,
            spreadsheet_name,
            credentials_path,
            worksheet_name
        )

        print(f"\n=== Batch Export Complete ===")
        print(f"Total files: {results['total']}")
        print(f"Successful:  {results['success']}")
        print(f"Skipped:     {results['skipped']}")
        print(f"Failed:      {results['failed']}")

        if results["models_added"]:
            print(f"\nModels added:")
            for model in results["models_added"]:
                print(f"  ✓ {model}")

        if results["models_skipped"]:
            print(f"\nModels skipped (already exist):")
            for model in results["models_skipped"]:
                print(f"  ⊘ {model}")

        if results["errors"]:
            print(f"\nErrors:")
            for err in results["errors"]:
                print(f"  ✗ {err['file']}: {err['error']}")


def _run_single_file_mode(json_file: str, spreadsheet_name: str,
                          worksheet_name: str, credentials_path: str,
                          csv_only: bool) -> None:
    """
    Process a single JSON file.

    Args:
        json_file: Path to the JSON file.
        spreadsheet_name: Name of the Google Sheet.
        worksheet_name: Name of the worksheet tab.
        credentials_path: Path to credentials JSON file.
        csv_only: If True, only generate CSV file.
    """
    json_path = Path(json_file)
    if not json_path.exists():
        print(f"Error: File not found: {json_file}")
        return

    with open(json_file, "r") as f:
        data = json.load(f)

    if csv_only:
        # Generate CSV output
        csv_path = json_path.stem + ".csv"
        json_to_csv(data, csv_path)
        print(f"CSV exported to: {csv_path}")
    else:
        # Export to Google Sheets
        result = export_to_google_sheets(
            data,
            spreadsheet_name,
            credentials_path,
            worksheet_name
        )
        print(f"Successfully exported {result['model_added']} to Google Sheets!")
        print(f"Spreadsheet URL: {result['spreadsheet_url']}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import argparse
    import sys

    # Check if any command-line arguments were provided (besides script name)
    if len(sys.argv) == 1:
        # No CLI arguments - use CONFIG values
        print("Running with CONFIG settings (no command-line arguments)...\n")
        run_from_config()
    else:
        # CLI arguments provided - use argparse
        parser = argparse.ArgumentParser(
            description="Export battery cell data to Google Sheets"
        )
        parser.add_argument(
            "json_file",
            nargs="?",
            default=None,
            help="Path to the JSON file with extracted battery data"
        )
        parser.add_argument(
            "--batch-dir",
            dest="batch_dir",
            help="Path to directory containing JSON files to batch process"
        )
        parser.add_argument(
            "--sheet",
            default="cell-data-sheet",
            help="Name of the Google Sheet (default: cell-data-sheet)"
        )
        parser.add_argument(
            "--credentials",
            default="battery-cell-database-credentials.json",
            help="Path to service account credentials"
        )
        parser.add_argument(
            "--worksheet",
            default="Battery Cells",
            help="Name of worksheet tab (default: Battery Cells)"
        )
        parser.add_argument(
            "--csv-only",
            action="store_true",
            help="Only generate CSV, don't upload to Sheets"
        )

        args = parser.parse_args()

        # Validate arguments
        if args.batch_dir is None and args.json_file is None:
            parser.error("Either json_file or --batch-dir must be provided")

        if args.batch_dir:
            _run_batch_mode(args.batch_dir, args.sheet, args.worksheet,
                           args.credentials, args.csv_only)
        else:
            _run_single_file_mode(args.json_file, args.sheet, args.worksheet,
                                  args.credentials, args.csv_only)

