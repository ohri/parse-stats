# Fantasy Football Stats Parser

Python tool for parsing NFL play-by-play CSV data and generating SQL statements for fantasy league statistics.

## Requirements

- Python 3.6+
- No external dependencies (uses only standard library)

## Usage

```bash
python parse_stats.py -f INPUT_FILE -s SEASON -w WEEK [-o OUTPUT_FILE] [-d]
```

### Arguments

- `-f, --file`: Path to input CSV file (required)
- `-s, --season`: Season year, e.g., 2025 (required)
- `-w, --week`: Week number, e.g., 17 (required)
- `-o, --output`: Output SQL file path (optional, default: replaces .csv with .sql)
- `-d, --debug`: Enable debug output to stderr (optional)

### Examples

```bash
# Parse week 17 data - automatically creates w17mnf.sql
python parse_stats.py -f w17mnf.csv -s 2025 -w 17

# Parse with custom output filename
python parse_stats.py -f test_data/w17sat.csv -s 2025 -w 17 -o week17_saturday.sql

# With debug output
python parse_stats.py -f w17mnf.csv -s 2025 -w 17 -d
```

## Output

The script automatically creates a SQL file with the same name as the input CSV (replacing `.csv` with `.sql`). You can override this with the `-o` option.

The generated SQL statements are in Oracle PL/SQL format:

- Player statistics: `gsis_add_player_raw_stat` stored procedure calls
- Team blocking statistics: `gsis_add_blocking_performance` stored procedure calls
- Field goal attempts: Individual made field goal distances plus totals

Success/error messages are written to stderr.

## Improvements Over Original

This Python version:

- ✅ Fixes the "NA" bug where invalid player IDs were occasionally output
- ✅ Provides cleaner command-line interface using argparse
- ✅ Maintains minimal output unless problems occur
- ✅ Produces identical SQL output to the original .NET version (excluding the NA bug)

## Testing

### Unit & Integration Tests

Comprehensive test suite with pytest covering 95%+ of code:

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest test_parse_stats.py -v

# Run with coverage
pytest test_parse_stats.py --cov=parse_stats --cov-report=term-missing
```

Test coverage includes:
- ✅ All play type parsing (runs, passes, kicks, punts, tackles, fumbles)
- ✅ SQL generation (player stats, team blocking, field goals)
- ✅ Data validation and pre-scanning
- ✅ Edge cases (negative values, missing fields, NA filtering)
- ✅ Integration tests with all 5 test data files

See [TESTING.md](TESTING.md) for detailed testing guide.
