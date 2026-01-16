# Google Sheets API Setup Guide

This guide walks you through setting up Google Sheets API access for exporting battery cell data.

## Prerequisites

Install the required Python packages:

```bash
pip install gspread google-auth google-auth-oauthlib
```

---

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Create Project** (or select an existing project)
3. Name it something like `battery-cell-database`

---

## Step 2: Enable Google Sheets API

1. In your project, go to **APIs & Services** → **Library**
2. Search for **Google Sheets API**
3. Click **Enable**

---

## Step 3: Create Service Account Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **Service Account**
3. Fill in:
   - Name: `battery-sheets-exporter`
   - Click **Create and Continue**
   - Skip roles (click **Continue**)
   - Click **Done**
4. Click on the service account you just created
5. Go to **Keys** tab → **Add Key** → **Create new key**
6. Select **JSON** format → **Create**
7. Save the downloaded file as `credentials.json` in the `battery-cell-extraction/` folder

> ⚠️ **Important**: Never commit `credentials.json` to git!

---

## Step 4: Share Your Sheet with the Service Account

1. Open the **Google Sheet** you want to use (or create a new one)
2. Click **Share**
3. Paste the **service account email** (found in `credentials.json` under `client_email`)
   - It looks like: `battery-sheets-exporter@your-project.iam.gserviceaccount.com`
4. Give it **Editor** access
5. Click **Send**

---

## Usage

### Export to Google Sheets

```bash
python sheets_exporter.py output.json --sheet "Battery Cell Database"
```

### Export multiple files

```bash
python sheets_exporter.py cell1.json cell2.json cell3.json --sheet "My Cells"
```

### CSV-only mode (no API)

```bash
python sheets_exporter.py output.json --csv-only
```

---

## Ragone Plot Columns

The exporter creates columns optimized for Ragone plots:

| Column | Unit | Description |
|--------|------|-------------|
| energy_density_wh_kg | Wh/kg | Gravimetric energy density (X-axis) |
| power_density_w_kg | W/kg | Gravimetric power density (Y-axis) |
| energy_density_wh_l | Wh/L | Volumetric energy density |
| power_density_w_l | W/L | Volumetric power density |

---

## Creating a Ragone Chart in Google Sheets

1. Select the `energy_density_wh_kg` and `power_density_w_kg` columns
2. Click **Insert** → **Chart**
3. Choose **Scatter chart**
4. Set X-axis: `energy_density_wh_kg`
5. Set Y-axis: `power_density_w_kg`
6. Check **Logarithmic** for both axes (typical for Ragone plots)
