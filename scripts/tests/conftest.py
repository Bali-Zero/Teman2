from __future__ import annotations

MIN_TEST_NOFILE_LIMIT = 4096


def pytest_configure(config: object) -> None:
    _ = config
    try:
        import resource
    except ImportError:
        return

    try:
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    except (OSError, ValueError):
        return

    if soft_limit == resource.RLIM_INFINITY:
        return

    target_limit = max(soft_limit, MIN_TEST_NOFILE_LIMIT)
    if hard_limit != resource.RLIM_INFINITY:
        target_limit = min(target_limit, hard_limit)
    if target_limit <= soft_limit:
        return

    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target_limit, hard_limit))
    except (OSError, ValueError):
        return
