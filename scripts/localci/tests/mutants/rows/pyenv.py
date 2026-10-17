"""pytest env v2: the kind-`pytest` sandbox has hosted's sweep environment — one rule per row, against test_pyenv.py."""
RUN = "scripts/localci/runner.py"
WRAP = "scripts/localci/pytest_indexed.py"
PE = ("scripts/localci/tests/test_pyenv.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    # the image and what runs in it
    "pyenv-bare-image-kept": (RUN, 'image_id=spec.get("deps_image") if kind == "pytest" else None)', "image_id=None)", PE),
    "pyenv-home-stays-tmp": (RUN, "            env.update(SWEEP_ENV)\n", "            pass\n", PE),
    "pyenv-install-not-shipped": (RUN, '**({"install": SWEEP_INSTALL, "home_dirs": ["logs"]} if sweep else {})', '**({"home_dirs": ["logs"]} if sweep else {})', PE),
    "pyenv-logs-not-made": (RUN, '"home_dirs": ["logs"]} if sweep', '"home_dirs": []} if sweep', PE),
    "pyenv-image-not-named-in-log": (RUN, '            notes.append(f"# env: deps image', '            notes.append(f"# env: image', PE),
    # the sweep's own lines and constants
    "pyenv-test-packages-dropped": (RUN, '"pytest", "pytest-asyncio", "pytest-mock", "fakeredis"]))', '"pytest", "pytest-asyncio", "pytest-mock"]))', PE),
    "pyenv-login-name-unset": (RUN, '"HOME": "/home/runner", "USER": "runner", "LOGNAME": "runner", "UV_OFFLINE"', '"HOME": "/home/runner", "UV_OFFLINE"', PE),
    "pyenv-lock-not-installed": (RUN, '"-r", "requirements.lock.txt"]', '"-r", "requirements.txt"]', PE),
    "pyenv-cell-core-not-installed": (RUN, '"-e", "../../packages/cell-core"]', '"-e", "../../packages/cell-core-x"]', PE),
    "pyenv-online-install": (RUN, '"PIP_FIND_LINKS": "/opt/wheels", "PIP_NO_INDEX": "1",', '"PIP_FIND_LINKS": "/opt/wheels", "PIP_NO_INDEX": "0",', PE),
    "pyenv-services-faked": (RUN, '"API_KEYS": "test_api_key_1,test_api_key_2"}   # pragma', '"API_KEYS": "test_api_key_1,test_api_key_2", "REDIS_URL": "redis://localhost:6379"}   # pragma', PE),
    "pyenv-install-failure-is-a-verdict": (RUN, '        return "ERROR", "the sandbox\'s offline env install failed', '        return "FAIL", "the sandbox\'s offline env install failed', PE),
    # the plan
    "pyenv-other-recipe-prefix": (RUN, 'os.path.dirname(hosted_python(iso)), run_dir, "backend-tests")', '"", run_dir, "backend-tests")', PE),
    "pyenv-image-failure-falls-back-bare": (RUN, '{**sc, "deps_image": image, "deps_note": note} if image else \\', '{**sc, "deps_image": image, "deps_note": note} if True else \\', PE),
    "pyenv-missing-recipe-falls-through": (RUN, 'else (None, f"the contexts matrix has no deps recipe for', 'else ("sha256:" + "0" * 64, f"the contexts matrix has no deps recipe for', PE),
    "pyenv-plan-ignores-the-matrix-status": (RUN, 'and iso.get("mode") == "container" and ctxs["status"] == "ok":', 'and iso.get("mode") == "container":', PE),
    "pyenv-extra-may-claim-the-image": (RUN, '"trusted_files", "deps_image", "deps_note"})', '"trusted_files"})', PE),
    # the wrapper
    "pyenv-install-failure-continues": (WRAP, "            return INSTALL_RC\n", "            pass\n", PE),
    "pyenv-install-code-drifts": (WRAP, "INSTALL_RC = 97   # runner.INSTALL_RC", "INSTALL_RC = 3   # runner.INSTALL_RC", PE),
    "pyenv-home-dirs-skipped": (WRAP, '        (Path(os.path.expanduser("~")) / rel).mkdir(parents=True, exist_ok=True)', "        pass", PE),
    "pyenv-install-runs-at-root": (WRAP, 'cwd=os.path.join(cfg["root"], cwd)', 'cwd=cfg["root"]', PE),
    "pyenv-install-after-pytest": (WRAP, '    for cwd, argv in cfg.get("install") or []:', '    for cwd, argv in []:', PE),
}
