# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python tool for parsing NFL play-by-play CSV data and generating Oracle PL/SQL statements for a fantasy football league database. This replaces a legacy .NET implementation with improved error handling (fixes the "NA" bug where invalid player IDs were output).

## Key Commands

### Running the Parser
```bash
# Basic usage - automatically creates w17mnf.sql
python parse_stats.py -f w17mnf.csv -s 2025 -w 17

# Parse multiple matching files; each gets its own .sql output
python parse_stats.py -f 'test_data/w17*.csv' -s 2025 -w 17

# Custom output path
python parse_stats.py -f test_data/w17sat.csv -s 2025 -w 17 -o custom.sql

# Debug mode (verbose output to stderr)
python parse_stats.py -f w17mnf.csv -s 2025 -w 17 -d
```

### Testing
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest test_parse_stats.py -v

# Run with coverage
pytest test_parse_stats.py --cov=parse_stats --cov-report=term-missing

# Run specific test class
pytest test_parse_stats.py::TestDataParser -v

# Run single test
pytest test_parse_stats.py::TestDataParser::test_look_for_run_basic -v

# Run tests matching pattern
pytest test_parse_stats.py -k "pass" -v
```

### Validation
```bash
# Compare output against expected (excluding old NA bug)
diff <(grep "^exec" output.sql | sort) \
     <(grep "^exec" expected.sql | grep -v "'NA'" | sort)
```

## Architecture

### Core Components

**DataParser** (`parse_stats.py:108-440`)
- Main parsing engine that processes CSV play-by-play data
- Routes each play to appropriate handlers based on `play_type` and flags
- Accumulates statistics in nested dictionaries: `stats[player_id][stat_type_id] = value`
- Collects field goals and punts in separate structures for post-processing
- Key methods:
  - `route_parsing()` - Dispatches plays to type-specific handlers
  - `look_for_run()` - Handles rushing plays, tracks direction (left/center/right)
  - `look_for_pass()` - Handles pass attempts, completions, sacks, interceptions
  - `look_for_kick()` - Handles PATs, kickoffs, field goals
  - `look_for_punt()` - Collects punt data for aggregation
  - `look_for_tackles()` - Processes all tackle types (solo, assist, stuff)
  - `look_for_fumbles()` - Handles forced fumbles, recoveries, returns
  - `reduce_punts()` - Aggregates raw punt data into statistics

**SQLGenerator** (`parse_stats.py:443-510`)
- Generates Oracle PL/SQL stored procedure calls
- Two main output types:
  1. Player stats: `gsis_add_player_raw_stat(player_id, season, week, stat_id, value)`
  2. Team blocking: `gsis_add_blocking_performance(team, season, week, ...14 params)`
- Critical: Filters out 'NA' player IDs to avoid the original bug
- Formats values properly (integers vs floats)

**PreScan** (`parse_stats.py:513-571`)
- Data integrity validation before parsing
- Checks consistency between player_id and player_name fields
- Reports mismatches (e.g., ID populated but name is "NA")

### Data Flow

```
CSV Input → PreScan (validate) → DataParser (accumulate) → reduce_punts() → SQLGenerator (output)
                                       ↓
                              stats{}, kicks{}, punts{}
```

### Stat Type Enums

**PlayerStatTypes** - Database stat IDs (1-79)
- Example: CARRIES=1, RUSH_YARDS=2, RUSH_TDS=5, SACKS=64

**TeamStatTypes** - Internal IDs for team blocking stats (1001-1032)
- Example: TEAM_RUSH_YARDS_LEFT=1010, TEAM_PASS_ATTEMPTS=1030
- These are NOT database IDs - they're aggregated into the blocking performance call

### Critical Implementation Details

1. **NA Filtering**: Always check `player_id.upper() != 'NA'` before outputting SQL
2. **Punt Averaging**: Uses integer division (`//`) to match .NET behavior
3. **Half Sacks**: Each defender gets 0.5 sacks when two defenders share a sack
4. **Stuff Detection**: Tackle for loss OR run/pass gaining < 1 yard
5. **Team Stats**: 2-4 character abbreviations (KC, ATL, LA) vs player IDs (00-0012345)
6. **Output**: Automatically creates `.sql` file matching input `.csv` name

### Test Structure

- **TestDataParser**: Unit tests for parsing logic (21 tests)
- **TestSQLGenerator**: SQL output validation (4 tests)
- **TestPreScan**: Data integrity checks (4 tests)
- **TestIntegration**: End-to-end with real CSV files (5 tests)
- **TestEdgeCases**: Edge cases and error handling (7 tests)

All 5 test data files in `test_data/` provide integration test coverage and regression detection.

## Working with This Codebase

### Adding New Stat Types

1. Add enum value to `PlayerStatTypes` or `TeamStatTypes` with correct database ID
2. Update relevant `look_for_*()` method in DataParser
3. Add test case in `test_parse_stats.py`
4. Run tests to verify

### Debugging Parse Issues

1. Use `--debug` flag to see all accumulated stats before SQL generation
2. Check `PreScan` output for data integrity issues (player_id/name mismatches)
3. Examine play_id in error messages to find problematic rows in CSV
4. Verify stat accumulation with unit tests before integration testing

### Common Gotchas

- **Field goal stats**: Stored separately during parsing, then output after player/team stats
- **Punt aggregation**: Must call `reduce_punts()` before SQL generation
- **NA values**: CSV contains "NA" strings for missing data - filter these out
- **Integer division**: Punt averages must use `//` not `/` to match legacy behavior
- **Team vs Player**: Length check determines routing (len > 4 = player, else team)
