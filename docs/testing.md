# Testing

This document describes the testing capabilities of the Praetorian CLI.

## Integration Tests

Run the integration test suite with:

```bash
praetorian chariot test
```

### Options

- `-s, --suite [coherence|cli]`: Run a specific test suite
- `KEY`: Optional key to filter tests (e.g., test name pattern)

## Performance Tests

The CLI includes a performance testing suite to measure API response times for various operations.

### Running Performance Tests

```bash
praetorian chariot test-speed [OPTIONS]
```

### Options

- `--profile TEXT`: Keychain profile name (defaults to test profile)
- `--account TEXT`: Account to use
- `--iterations INTEGER`: Number of iterations for each test
- `--test [assets|search|risks|all]`: Test category to run (default: all)
- `--output TEXT`: Save results to this JSON file

### Example Usage

```bash
# Run all performance tests with 5 iterations
praetorian chariot test-speed --iterations 5

# Run only asset tests and save results
praetorian chariot test-speed --test assets --output results.json

# Run tests with a specific profile
praetorian chariot test-speed --profile "United States" --test search
```

### Test Categories

- `assets`: Tests asset listing and retrieval operations
- `search`: Tests search operations using key prefix and source
- `risks`: Tests risk listing operations
- `all`: Runs all test categories

### Output Format

The test results are displayed in a table format with the following columns:

- API Call: Name of the API operation being tested
- Iterations: Number of times the operation was executed
- Avg Time: Average execution time in seconds
- Min Time: Minimum execution time in seconds
- Max Time: Maximum execution time in seconds
- Std Dev: Standard deviation of execution times
- Success: Whether all iterations completed successfully

If the `--output` option is specified, the results are also saved to a JSON file.
