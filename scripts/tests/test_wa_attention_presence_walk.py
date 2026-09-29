"""Guilt + innocence for the AST presence walk behind check-wa-attention-pii.yml.

Synthetic source only. Each shape the walk must refuse is a guilt case; the shapes it must
keep accepting (and the real corpus) are innocence cases.
"""
import ast
import importlib.util
import pathlib
import textwrap

import pytest

_HELPER = pathlib.Path(__file__).resolve().parents[1] / "wa_attention_presence.py"
_spec = importlib.util.spec_from_file_location("wa_attention_presence", _HELPER)
presence = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(presence)


def run_walk(src):
    expected, problems = set(), []
    tree = ast.parse(textwrap.dedent(src))
    presence.walk("m", tree.body, [], expected, problems, presence.fixture_imports(tree))
    return expected, problems


GUILT = {
    "import_alias_shadow": """
        def test_guard():
            assert False
        from uuid import uuid4 as test_guard
    """,
    "import_alias_module": "import os as test_os\n",
    "import_unaliased_test_name": "from helpers import test_helper\n",
    "import_star": "from helpers import *\n",
    "import_class_alias": "from helpers import Base as TestBase\n",
    "import_under_if_shadows": """
        def test_guard():
            assert False
        if True:
            from uuid import uuid4 as test_guard
    """,
    "tuple_target_rebinding": """
        def test_guard():
            assert False
        test_guard, = (len,)
    """,
    "assign_under_if_rebinding": """
        def test_guard():
            assert False
        if True:
            test_guard = len
    """,
    "testcase_alias_import": """
        from unittest import TestCase as C
        class Checks(C):
            pass
    """,
    "object_alias_base": """
        from helpers import Base as object
        class TestC(object):
            pass
    """,
    "test_method_under_if_in_plain_class": """
        class Checks:
            if True:
                def test_x(self):
                    pass
    """,
    "wrapping_decorator_on_test": """
        from functools import wraps
        def swallow(f):
            @wraps(f)
            def inner():
                return None
            return inner
        @swallow
        def test_guard():
            assert False
    """,
    "decorator_on_test_class": """
        @something
        class TestC:
            def test_a(self):
                pass
    """,
    "module_level_setattr": """
        def test_guard():
            assert False
        setattr(__import__("sys").modules[__name__], "test_guard", len)
    """,
    "module_level_globals_write": """
        def test_guard():
            assert False
        globals().update(test_guard=len)
    """,
    "pytest_name_rebound": """
        import pytest
        pytest = object()
    """,
    "fixture_alias_import": """
        from pytest import fixture as fx
        @fx
        def test_helper():
            return 1
    """,
    'N11_globals_subscript_assign': 'def test_guard():\n    assert False\nglobals()["test_guard"] = lambda: None\n',
    'N17_vars_subscript_assign': 'def test_guard():\n    assert False\nvars()["test_guard"] = lambda: None\n',
    'N19_class_locals_subscript_assign': 'class TestC:\n    def test_guard(self):\n        assert False\n    locals()["test_guard"] = lambda self: None\n',
    'N13_sys_modules_attribute_assign': 'import sys as _sys\ndef test_guard():\n    assert False\n_sys.modules[__name__].test_guard = lambda: None\n',
    'N12_alias_then_code_swap': 'def test_guard():\n    assert False\n_f = test_guard\n_f.__code__ = (lambda: None).__code__\n',
    'N18_module_dict_update': 'import sys as _sys\ndef test_guard():\n    assert False\n_sys.modules[__name__].__dict__.update(test_guard=lambda: None)\n',
    'N14_helper_code_swap': 'def _neuter(f):\n    f.__code__ = (lambda: None).__code__\ndef test_guard():\n    assert False\n_neuter(test_guard)\n',
    'M1_test_def_under_if': 'if True:\n    def test_x():\n        pass\n',
    'M1_test_def_under_try': 'try:\n    def test_x():\n        pass\nexcept Exception:\n    pass\n',
    'M1b_test_class_under_with': "with open('f') as fh:\n    class TestC:\n        pass\n",
    'M2_duplicate_def': 'def helper():\n    pass\ndef helper():\n    pass\n',
    'M2_duplicate_class': 'class Helper:\n    pass\nclass Helper:\n    pass\n',
    'M3_fixture_rebound': 'fixture = len\n',
    'M6_setattr_statement': "setattr(object, 'a', 1)\n",
    'M6_locals_update_statement': 'locals().update(a=1)\n',
    'M6_vars_update_statement': 'vars().update(a=1)\n',
    'M6_exec_statement': "exec('a = 1')\n",
    'M6_eval_statement': "eval('1')\n",
    'M6_dunder_import_statement': "__import__('os')\n",
    'M6_register_statement': 'register(len)\n',
    "inherited_test_base": """
        class _Base:
            def test_inh(self):
                assert False
        class TestC(_Base):
            pass
    """,
    "inherited_from_test_class": """
        class TestA:
            def test_a(self):
                pass
        class TestB(TestA):
            pass
    """,
    "metaclass_keyword": """
        class TestM(metaclass=type):
            def test_m(self):
                pass
    """,
    "testcase_without_test_prefix": """
        import unittest
        class Checks(unittest.TestCase):
            def test_u(self):
                assert False
    """,
    "testcase_bare_name_base": """
        from unittest import TestCase
        class Checks(TestCase):
            pass
    """,
    "non_test_class_with_test_methods": """
        class Checks:
            def test_plain(self):
                pass
    """,
    "nested_non_test_class_with_test_methods": """
        class TestOuter:
            class Inner:
                def test_n(self):
                    pass
    """,
}


@pytest.mark.parametrize("name", sorted(GUILT))
def test_guilt_shape_is_refused(name):
    _, problems = presence.scan_source("m", textwrap.dedent(GUILT[name]))
    assert problems, f"{name}: the walk accepted a shape it cannot follow"


HOOK_GUILT = {
    "pyfunc_call_def": "def pytest_pyfunc_call(pyfuncitem):\n    return True\n",
    "runtest_call_def": "def pytest_runtest_call(item):\n    pass\n",
    "runtest_protocol_def": "def pytest_runtest_protocol(item, nextitem):\n    return True\n",
    "makereport_def": "def pytest_runtest_makereport(item, call):\n    pass\n",
    "makeitem_def": "def pytest_pycollect_makeitem(collector, name, obj):\n    return None\n",
    "hook_assigned": "pytest_pyfunc_call = lambda pyfuncitem: True\n",
    "plugins_list": "pytest_plugins = ['some.plugin']\n",
    "modifyitems_def": "def pytest_collection_modifyitems(items):\n    for i in items:\n        i.obj = len\n",
    "hook_imported_under_own_name": "from helpers import stop as pytest_pyfunc_call\n",
    "hook_via_specname": "import pytest\n@pytest.hookimpl(specname='pytest_pyfunc_call')\ndef pytest_stop(pyfuncitem):\n    return True\n",
    "body_swap_obj": "def helper(item):\n    item.obj = len\n",
    "C15_conftest_autouse_code_swap": 'import pytest\n@pytest.fixture(autouse=True)\ndef _neuter(request):\n    request.function.__code__ = (lambda: None).__code__\n',
    "logreport_def": "def pytest_runtest_logreport(report):\n    report.outcome = 'passed'\n",
    "sessionfinish_def": "def pytest_sessionfinish(session):\n    pass\n",
    "star_import_in_conftest": "from helper import *\n",
    "plugin_registered_at_runtime": "def pytest_configure(config):\n    config.pluginmanager.register(object())\n",
    "hook_nested_in_if": "if True:\n    def pytest_pyfunc_call(pyfuncitem):\n        return True\n",
}


@pytest.mark.parametrize("name", sorted(HOOK_GUILT))
def test_forbidden_hook_is_refused(name):
    assert presence.hook_problems("conftest.py", ast.parse(HOOK_GUILT[name]))


def test_pytest_configure_and_local_names_are_not_forbidden():
    src = "def pytest_configure(config):\n    pass\ndef test_x():\n    pytest_plugins = []\n    return pytest_plugins\n"
    assert presence.hook_problems("conftest.py", ast.parse(src)) == []


def test_n00_control_a_lone_failing_guard_is_expected_so_a_missing_run_is_red():
    expected, problems = presence.scan_source("m", "def test_guard():\n    assert False\n")
    assert problems == []
    assert expected == {("m", "test_guard")}


def test_lookalike_fixture_decorator_is_still_expected_so_a_missing_run_is_red():
    expected, _ = run_walk(
        """
        def fixture(f):
            return f
        @fixture
        def test_real():
            assert False
        """
    )
    assert ("m", "test_real") in expected


def test_innocent_shapes_are_counted_without_problems():
    expected, problems = run_walk(
        """
        import pytest
        from pytest import fixture
        from x import helper
        import os

        @pytest.fixture
        def test_helper():
            return 1

        @fixture(scope="module")
        def test_helper_two():
            return 2

        class TestFixtureHost:
            def __init__(self):
                pass
            def test_skipped_by_pytest_too(self):
                pass

        class _PlainHelper:
            def build(self):
                pass

        class TestOk(object):
            def test_a(self):
                pass
            class TestNested:
                def test_n(self):
                    pass

        @pytest.mark.parametrize("x", [1, 2])
        def test_param(x):
            pass

        async def test_async():
            pass

        def test_plain():
            pass
        """
    )
    assert problems == []
    assert expected == {("m", "TestOk.test_a"), ("m", "TestOk.TestNested.test_n"), ("m", "test_async"), ("m", "test_param"), ("m", "test_plain")}


def test_real_corpus_has_no_problems_and_pins_every_known_suite():
    root = pathlib.Path(__file__).resolve().parents[2]
    expected, problems, modules = presence.collect(str(root))
    assert problems == []
    assert expected
    assert presence.KNOWN_SUITES <= modules


def test_junit_missing_definition_is_reported(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuites><testsuite>'
        '<testcase classname="scripts.tests.m" name="test_a[p1]"/>'
        '<testcase classname="scripts.tests.m" name="test_b"><skipped/></testcase>'
        "</testsuite></testsuites>"
    )
    cases, skipped, ran = presence.read_junit(str(junit), {"m"})
    assert len(cases) == 2
    assert skipped == ["m::test_b"]
    assert ran == {("m", "test_a")}


def test_declared_gap_unwalked_class_bodies_are_not_refused():
    """Characterization of a DECLARED residual, not a guarantee: the walk enters Test*-named
    classes without __init__ only. If this test fails because the gap was closed, update the
    NOT DEFENDED paragraph of check-wa-attention-pii.yml and the module docstring in the same PR."""
    non_test_class = 'def test_guard():\n    assert False\nclass Helper:\n    globals()["test_guard"] = lambda: None\n    x = test_guard\n'
    test_class_with_init = 'class TestC:\n    def __init__(self):\n        pass\n    def test_guard(self):\n        assert False\n    globals()["test_guard"] = lambda self: None\n'
    for src in (non_test_class, test_class_with_init):
        assert presence.scan_source("m", src)[1] == [], (
            "declared gap closed? update NOT DEFENDED in check-wa-attention-pii.yml and the docstring of "
            "scripts/wa_attention_presence.py, then delete this test"
        )
