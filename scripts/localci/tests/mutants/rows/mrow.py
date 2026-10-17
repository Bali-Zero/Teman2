"""The guard job's zsh preflight step (#8646) must stay mapped by the matrix: one row per way the mapping can be lost, against test_matrix_zsh_preflight.py."""
MX = "scripts/localci/contexts_matrix.yaml"
TS = ("scripts/localci/tests/test_matrix_zsh_preflight.py",)
STEP = "        - workflow_step: harness/fable-gate zsh preflight regression\n"

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "mrow-zsh-mapping-deleted": (MX, STEP, "", TS),
    "mrow-zsh-not-applicable": (MX, STEP, STEP + "          not_applicable: no zsh on the runner\n", TS),
    "mrow-zsh-assertion-dropped": (MX, "              REQUIRE_ZSH=1 python3 -m pytest tests/scripts/test_harness_fable_gate_preflight_zsh_1017.py -q\n", "", TS),
    "mrow-zsh-skip-allowed": (MX, "              REQUIRE_ZSH=1 python3 -m pytest tests/scripts/test_harness_fable_gate_preflight_zsh_1017.py -q\n", "              python3 -m pytest tests/scripts/test_harness_fable_gate_preflight_zsh_1017.py -q\n", TS),
}
