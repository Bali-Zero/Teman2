# Data Processing Template

## Task Description
Process data files in [FOLDER_PATH]:
- Clean and validate data
- Transform formats
- Extract insights
- Generate reports

## Instructions
1. Identify data files: JSON, CSV, Excel, etc.
2. For each file:
   - Validate structure and format
   - Check for missing/invalid data
   - Apply transformations (if specified)
   - Extract key metrics

3. Generate consolidated report

## Common Transformations
- **Format conversion**: CSV → JSON, JSON → Excel
- **Data cleaning**: Remove duplicates, fix formatting
- **Aggregation**: Sum, average, count by category
- **Filtering**: Select rows matching criteria
- **Merging**: Combine multiple files

## Output
1. Processed data files in [OUTPUT_FOLDER]
2. Summary report:
   ```markdown
   # Data Processing Report

   ## Input Files
   - File 1: [N] records, [SIZE]
   - File 2: [N] records, [SIZE]

   ## Transformations Applied
   - Transformation 1: [DESCRIPTION]
   - Transformation 2: [DESCRIPTION]

   ## Output
   - Output file: [PATH]
   - Total records: [N]
   - Data quality: [%]

   ## Issues Found
   - Issue 1: [DESCRIPTION]
   - Issue 2: [DESCRIPTION]
   ```

## Quality Checks
- Data completeness: ≥95%
- Format consistency: 100%
- Duplicate records: 0
- Invalid values: ≤1%
