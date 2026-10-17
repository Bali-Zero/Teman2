"""B30-adjacent: the egress step's network exemption judges pip-audit's finding, never its clean line (#8613)."""
import pytest

from scripts.localci import runner

TIMEOUT = ("urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool(host='pypi.org', port=443): Read timed out.\n"
           "::error::pip-audit failed on requirements.lock.txt\n::endgroup::\n")
CLEAN = "No known vulnerabilities found\n"
FINDING = ("Found 1 known vulnerability in 1 package\nName Version ID             Fix Versions\n---- ------- -------------- ------------\n"
           "mcp  2.0.0   CVE-2026-59951 1.30.0,2.2.0\n::error::pip-audit failed on requirements.lock.txt\n")


def run_egress(tmp_path, monkeypatch, log_text, rc):
    def fake_exec(name, spec, run_dir, plan, inner, a, extra, env, log, junit, *rest, **kw):
        log.write_text(log_text)
        suite = runner.ET.Element("testsuite")
        case = runner.ET.SubElement(suite, "testcase", name="audit")
        if rc:
            runner.ET.SubElement(case, "failure", message=f"rc={rc}")
        runner.ET.ElementTree(suite).write(junit)
        return rc, None
    monkeypatch.setattr(runner, "execute_contained", fake_exec)
    for d in ("receipts", "logs"):
        (tmp_path / d).mkdir(exist_ok=True)
    st = {"name": "audit", "side": {"where": "egress", "inputs": [], "rewrite": []}}
    return runner._run_egress("ctx.t", {"context": "t"}, {"timeout_s": 60, "image_id": "i"}, st, "s", {}, {}, {}, [], tmp_path, {})


@pytest.mark.parametrize("log_text, rc, no_verdict", [
    (TIMEOUT + CLEAN, 1, True),                     # #8613: timeout on one lock, the other lock clean
    (TIMEOUT + FINDING, 1, False),                  # a real finding beside a timeout stays a verdict
    (FINDING, 1, False),                            # #8576: a finding alone
    (TIMEOUT + "Found 2 known vulnerabilities in 1 package\n", 1, False),   # the plural, header-less
    ("Name Version ID\nmcp 2.0.0 CVE-1\n" + TIMEOUT, 1, False),   # the table header alone is a finding
    (TIMEOUT + "Found 0 known vulnerabilities in 1 package\n", 1, True),   # N = 0 is no finding
    (CLEAN, 0, False),                              # clean, rc 0: the step's own PASS
])
def test_the_network_exemption_judges_the_finding_not_the_clean_line(tmp_path, monkeypatch, log_text, rc, no_verdict):
    got = run_egress(tmp_path, monkeypatch, log_text, rc)
    if no_verdict:
        assert got["rc"] is None and "the network failed" in got["reason"]
    else:
        assert got["rc"] == rc
