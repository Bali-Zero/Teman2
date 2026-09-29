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
    "fixture_alias_import": """
        from pytest import fixture as fx
        @fx
        def test_helper():
            return 1
    """,
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
    _, problems = run_walk(GUILT[name])
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
    "hook_nested_in_if": "if True:\n    def pytest_pyfunc_call(pyfuncitem):\n        return True\n",
}


@pytest.mark.parametrize("name", sorted(HOOK_GUILT))
def test_forbidden_hook_is_refused(name):
    assert presence.hook_problems("conftest.py", ast.parse(HOOK_GUILT[name]))


def test_pytest_configure_and_local_names_are_not_forbidden():
    src = "def pytest_configure(config):\n    pass\ndef test_x():\n    pytest_plugins = []\n    return pytest_plugins\n"
    assert presence.hook_problems("conftest.py", ast.parse(src)) == []


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

        async def test_async():
            pass

        def test_plain():
            pass
        """
    )
    assert problems == []
    assert expected == {("m", "TestOk.test_a"), ("m", "TestOk.TestNested.test_n"), ("m", "test_async"), ("m", "test_plain")}


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
