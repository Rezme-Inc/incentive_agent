# Multi-Agent Incentive Program Discovery System

A sophisticated multi-agent system that discovers, extracts, verifies, and categorizes government hiring incentive programs using Anthropic Claude API.

## Architecture

The system uses 4 specialized agents that process data sequentially:

1. **Discovery Agent** (Extended Thinking)
   - Temperature: 1.0
   - Thinking Budget: 12,000 tokens
   - Task: Comprehensive research to find ALL programs

2. **Extraction Agent** (Standard)
   - Temperature: 0.5
   - Task: Convert narrative research → Structured JSON

3. **Verification Agent** (Standard, Critical)
   - Temperature: 0.3
   - Task: Find duplicates, errors, missing URLs

4. **Categorization Agent** (Standard)
   - Temperature: 0.5
   - Task: Organize issues into action buckets

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env with your API key and configuration
```

Required environment variables:
- `ANTHROPIC_API_KEY` - Your Anthropic API key
- `JURISDICTION` - The jurisdiction to research (e.g., "Illinois State and municipalities")
- `STATE` - State name
- `CITIES` - Comma-separated list of major cities
- `COUNTIES` - Comma-separated list of counties
- `SPREADSHEET_NAME` - Name for Google Sheets export (optional)
- `GOOGLE_CREDENTIALS_PATH` - Path to Google service account JSON (optional)

### 3. Set Up Google Sheets (Optional)

To enable Google Sheets export:

1. Create a Google Cloud Project
2. Enable Google Sheets API and Google Drive API
3. Create a Service Account
4. Download credentials JSON as `credentials.json`
5. Share your Google Sheet with the service account email

## Usage

### Basic Usage

```bash
python main.py
```

The system will:
1. Run discovery agent (saves `outputs/01_discovery_raw.txt`)
2. Extract to JSON (saves `outputs/02_programs_extracted.json`)
3. Verify data (saves `outputs/03_verification_results.json`)
4. Create action plan (saves `outputs/04_action_plan.json`)
5. Export to Google Sheets (if credentials provided)

### Custom Jurisdiction

Edit `.env` file or set environment variables:

```bash
export JURISDICTION="California"
export STATE="California"
export CITIES="Los Angeles, San Francisco, San Diego"
export COUNTIES="Los Angeles County, Orange County"
python main.py
```

## Output Structure

All intermediate files are saved in the `outputs/` directory:

- `01_discovery_raw.txt` - Raw research from discovery agent
- `02_programs_extracted.json` - Structured program data
- `03_verification_results.json` - Quality check results
- `04_action_plan.json` - Organized action plan

### Google Sheets Export

If credentials are provided, the system exports to Google Sheets with 4 tabs:

- **Programs**: All discovered programs
- **Verification**: Issues and quality checks
- **Actions**: Organized action plan
- **Clean Database**: Programs after removing duplicates/errors

## Program Data Schema

Each program includes:

- `program_id` - Unique identifier
- `program_name` - Official program name
- `administering_agency` - Array of agencies
- `jurisdiction_level` - federal/state/local
- `program_category` - tax_credit, wage_reimbursement, etc.
- `status` - active/expired/proposed/status_unclear
- `target_populations` - Array of eligible groups
- `max_value_per_employee` - Value details (amount, type, notes)
- `employer_eligibility` - Entity types, size limits, restrictions
- `geographic_trigger` - Address requirements
- `sources` - Array of source citations
- `confidence_level` - high/medium/low
- `potential_issues` - Flags for verification

## Verification Checks

The verification agent performs 7 critical checks:

1. **Duplicate Detection** - Finds same program listed multiple times
2. **Hallucination Detection** - Identifies programs that don't exist
3. **Status Verification** - Checks if status claims are accurate
4. **Value Assessment** - Finds incorrect value calculations
5. **Categorization Issues** - Flags non-incentives
6. **Missing Information** - Identifies critical data gaps
7. **Source URL Validation** - Validates URL format and domains

## Action Plan Structure

The categorization agent organizes programs into 8 decision buckets:

- **KEEP_AS_IS** - Clean, verified, ready to use
- **DELETE** - Hallucinations, not applicable
- **MERGE_DUPLICATES** - Consolidate same programs
- **UPDATE_STATUS** - Fix incorrect status
- **FIX_VALUE** - Correct value calculations
- **RECLASSIFY** - Move non-incentives
- **RESEARCH_NEEDED** - Missing critical info
- **FEDERAL_RECLASSIFY** - Federal-only programs

## Cost Estimates

Per jurisdiction:
- Discovery: ~$0.20-0.30 (extended thinking)
- Extraction: ~$0.10-0.15
- Verification: ~$0.15-0.20
- Categorization: ~$0.10-0.15
- **Total: ~$0.55-0.80 per jurisdiction**

Actual costs may vary based on response length and complexity.

## Known Issues & Edge Cases

The system is designed to handle:

- **WOTC Expiration**: Automatically marks WOTC as expired after 12/31/2025
- **Duplicate Detection**: Identifies population-specific and geographic duplicates
- **Value Types**: Distinguishes between cash, opportunity_cost, insurance_limit, non_quantifiable
- **Status Accuracy**: Verifies program status against known facts
- **Source Quality**: Prioritizes .gov sources over third-party

## Troubleshooting

### API Key Issues
- Ensure `ANTHROPIC_API_KEY` is set in `.env`
- Check API key is valid and has sufficient credits

### Google Sheets Export Fails
- Verify `credentials.json` exists and is valid
- Ensure service account has access to Google Sheets API
- Share spreadsheet with service account email

### JSON Parsing Errors
- Check intermediate output files for raw content
- Verify API responses are complete
- Review error messages in output files

## License

This project is for internal use only.

