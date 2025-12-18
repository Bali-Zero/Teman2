# Quick Start Guide - TeamMembersListPlugin Tests

## Test File Location
```
tests/unit/plugins/team/test_list_members_plugin.py
```

## Quick Test Commands

### Run All Tests
```bash
cd /Users/antonellosiano/Desktop/nuzantara/apps/backend-rag
pytest tests/unit/plugins/team/test_list_members_plugin.py -v
```

### Run with Coverage
```bash
pytest tests/unit/plugins/team/test_list_members_plugin.py \
  --cov=backend/plugins/team/list_members_plugin \
  --cov-report=term-missing \
  -v
```

### Generate HTML Coverage Report
```bash
pytest tests/unit/plugins/team/test_list_members_plugin.py \
  --cov=backend/plugins/team/list_members_plugin \
  --cov-report=html \
  -v

# Open coverage report
open htmlcov/index.html
```

### Run Specific Test Categories

```bash
# Run only model tests
pytest tests/unit/plugins/team/test_list_members_plugin.py -v -k "team_list_input or team_list_output"

# Run only metadata tests
pytest tests/unit/plugins/team/test_list_members_plugin.py -v -k "metadata"

# Run only execute tests
pytest tests/unit/plugins/team/test_list_members_plugin.py -v -k "execute"

# Run only error handling tests
pytest tests/unit/plugins/team/test_list_members_plugin.py -v -k "exception or error"

# Run only async tests
pytest tests/unit/plugins/team/test_list_members_plugin.py -v -k "asyncio"
```

## Expected Output

### All Tests Passing
```
test_list_members_plugin.py::test_team_list_input_no_department PASSED
test_list_members_plugin.py::test_team_list_input_with_department PASSED
test_list_members_plugin.py::test_team_list_input_field_metadata PASSED
...
============= 48 passed in X.XXs =============
```

### Coverage Report
```
Name                                          Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------
backend/plugins/team/list_members_plugin.py      XX      X    95%+
---------------------------------------------------------------------------
TOTAL                                            XX      X    95%+
```

## Test Structure

```
48 Tests Total:
├── 3 Fixtures
│   ├── mock_collaborator_profile
│   ├── mock_collaborator_service
│   └── plugin_with_mock_service
│
├── 6 Model Tests
│   ├── TeamListInput (3)
│   └── TeamListOutput (3)
│
├── 4 Initialization Tests
├── 11 Metadata Tests
├── 2 Schema Tests
│
├── 18 Execute Tests
│   ├── Success Cases (5)
│   ├── Roster Building (2)
│   ├── Department Grouping (3)
│   ├── Team Stats (2)
│   ├── Output Structure (2)
│   └── Edge Cases (4)
│
├── 4 Error Handling Tests
├── 2 Integration Tests
└── 2 Logging Tests
```

## Troubleshooting

### Import Errors
If you get import errors, ensure you're running from the correct directory:
```bash
cd /Users/antonellosiano/Desktop/nuzantara/apps/backend-rag
```

### Missing Dependencies
Install test dependencies:
```bash
pip install pytest pytest-asyncio pytest-cov
```

### Path Issues
The test file automatically adds the backend directory to sys.path. If issues persist, verify:
```python
backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
```

## Verify Test File

### Check Syntax
```bash
python -m py_compile tests/unit/plugins/team/test_list_members_plugin.py
```

### Count Tests
```bash
# Count test functions
grep -c "^def test_\|^async def test_" tests/unit/plugins/team/test_list_members_plugin.py

# Expected output: 48
```

### List All Tests
```bash
pytest tests/unit/plugins/team/test_list_members_plugin.py --collect-only
```

## Coverage Analysis

### Generate Detailed Report
```bash
pytest tests/unit/plugins/team/test_list_members_plugin.py \
  --cov=backend/plugins/team/list_members_plugin \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-branch \
  -v
```

### Coverage Targets
- **Line Coverage**: 95%+ ✅
- **Branch Coverage**: 95%+ ✅
- **Function Coverage**: 100% ✅

## CI/CD Integration

### Add to pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
```

### Automated Testing Example
```yaml
# Example automated testing configuration
test-team-plugin:
  stage: test
  image: python:3.11-slim
  script:
    - pip install -r requirements.txt pytest pytest-cov
    - pytest tests/unit/plugins/team/test_list_members_plugin.py \
        --cov=backend/plugins/team/list_members_plugin \
        --cov-report=xml \
        --cov-fail-under=95
```

## Quick Verification Checklist

- [ ] All 48 tests pass
- [ ] Coverage is 95%+
- [ ] No import errors
- [ ] No deprecation warnings
- [ ] All async tests work correctly
- [ ] Mock assertions pass
- [ ] Error scenarios covered
- [ ] Edge cases covered
- [ ] Logging tests pass

## Files Created

1. **test_list_members_plugin.py** - Main test file (743 lines)
2. **__init__.py** - Package marker
3. **README_TEST_COVERAGE.md** - Detailed coverage documentation
4. **TEST_SUMMARY.md** - Implementation summary
5. **QUICK_START.md** - This file

## Support

For issues or questions:
1. Check test output for specific failures
2. Review README_TEST_COVERAGE.md for details
3. Review TEST_SUMMARY.md for implementation notes
4. Verify all fixtures are properly configured
5. Ensure CollaboratorService is properly mocked
