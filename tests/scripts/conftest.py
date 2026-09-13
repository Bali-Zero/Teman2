def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs live internet; skipped unless explicitly enabled")
