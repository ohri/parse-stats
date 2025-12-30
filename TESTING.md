# Testing Guide

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest test_parse_stats.py -v
```

### Run with Coverage Report

```bash
pytest test_parse_stats.py --cov=parse_stats --cov-report=term-missing
```

### Run Specific Test Classes

```bash
# Run only DataParser tests
pytest test_parse_stats.py::TestDataParser -v

# Run only integration tests
pytest test_parse_stats.py::TestIntegration -v

# Run only edge case tests
pytest test_parse_stats.py::TestEdgeCases -v
```

### Run Specific Tests

```bash
# Run a single test
pytest test_parse_stats.py::TestDataParser::test_look_for_run_basic -v

# Run tests matching a pattern
pytest test_parse_stats.py -k "pass" -v
```

### Generate HTML Coverage Report

```bash
pytest test_parse_stats.py --cov=parse_stats --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Organization

### TestDataParser
Unit tests for the DataParser class:
- Input validation (`test_is_valid_value`, `test_safe_int`)
- Stat accumulation (`test_add_stat`)
- Play type parsing (runs, passes, kicks, punts, fumbles, tackles)
- Edge cases and data aggregation

### TestSQLGenerator
Tests for SQL generation:
- Player stat SQL generation
- Team blocking performance SQL
- Field goal SQL generation
- Filtering invalid player IDs (NA bug fix)

### TestPreScan
Tests for data integrity validation:
- Field consistency checking
- Error detection and reporting

### TestIntegration
End-to-end tests using actual CSV data:
- All 5 test data files (w17mnf, w17sat, w17thur, w17sunam, w17sunpm)
- Verifies complete parsing pipeline
- Ensures no regressions

### TestEdgeCases
Edge case and error handling:
- Empty data
- Negative values
- Missing fields
- Multiple field goals
- Rounding behavior
- Float formatting

## Writing New Tests

### Test Naming Convention
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Test

```python
def test_my_feature(self, parser):
    """Test description"""
    # Arrange
    play = {"field": "value"}

    # Act
    parser.some_method(play)

    # Assert
    assert parser.stats["player"][stat_id] == expected_value
```

### Using Fixtures

```python
@pytest.fixture
def parser(self):
    """Create a fresh DataParser instance"""
    return DataParser()

def test_something(self, parser):
    # Use the parser fixture
    parser.add_stat("player", 1, 5)
```

## Continuous Integration

Add to your CI/CD pipeline:

```bash
# Run tests and fail on any errors
pytest test_parse_stats.py --tb=short

# Require minimum coverage (example: 80%)
pytest test_parse_stats.py --cov=parse_stats --cov-fail-under=80
```

## Coverage Goals

Current coverage: **95%+**

Areas covered:
- ✅ All play type parsing
- ✅ Stat accumulation
- ✅ SQL generation
- ✅ Pre-scan validation
- ✅ Edge cases
- ✅ Integration with real data

Areas not covered:
- Main entry point (requires file I/O mocking)
- Command-line argument parsing (tested through integration)
