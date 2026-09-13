"""Native receipt binding, with synthetic sessions and no provider calls."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "saetta_receipt.py"
spec = importlib.util.spec_from_file_location("saetta_receipt", SOURCE)
receipt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receipt)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.session = "11111111-1111-4111-8111-111111111111"
        self.path = self.root / "projects/repo" / (self.session + ".jsonl")
        self.path.parent.mkdir(parents=True)
        self.base = self.path.with_suffix("")
        self.journal = self.base / "subagents/workflows/wf_test/journal.jsonl"
        self.journal.parent.mkdir(parents=True)
        self.script = self.base / "workflows/scripts/smoke.js"
        self.script.parent.mkdir(parents=True)
        self.script.write_text("return 1;")
        self.request = {"script": "return 1;"}
        self.result = {"marker": "SAETTA_NATIVE_SMOKE"}
        self.rows = [
            {"type": "assistant", "sessionId": self.session, "message": {"content": [
                {"type": "tool_use", "name": "Workflow", "id": "tool_one", "input": self.request}]}},
            {"type": "user", "sessionId": self.session, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "tool_one"}]}, "toolUseResult": {
                    "status": "async_launched", "taskType": "local_workflow", "taskId": "task_one",
                    "runId": "wf_test", "transcriptDir": str(self.journal.parent), "scriptPath": str(self.script)}},
            {"type": "attachment", "sessionId": self.session, "attachment": {
                "type": "queued_command", "commandMode": "task-notification", "prompt": self.notification()}},
        ]
        self.journal.write_text('\n'.join(json.dumps(x) for x in [
            {"type": "launched"}, {"type": "started", "key": "key", "agentId": "child"},
            {"type": "result", "key": "key", "agentId": "child", "result": self.result}]))

    def notification(self):
        return '<task-notification><task-id>task_one</task-id><tool-use-id>tool_one</tool-use-id><status>completed</status><result>' + json.dumps(self.result) + '</result></task-notification>'

    def check(self, *, smoke=True, script_sha256=None):
        self.path.write_text('\n'.join(json.dumps(x) for x in self.rows))
        return receipt.verify(self.session, [self.root], self.request, smoke=smoke, script_sha256=script_sha256)

    def test_accepts_bound_completion_and_actual_journal(self):
        self.assertEqual(self.check()["verdict"], "PASS")

    def test_assistant_prose_and_launch_only_are_not_completion(self):
        self.rows.pop()
        self.rows.append({"type": "assistant", "message": {"content": [{"type": "text", "text": "PASS"}]}})
        self.assertEqual(self.check()["verdict"], "BLOCK")

    def test_runtime_block_cannot_be_upgraded_by_agent_journal(self):
        self.result = {"verdict": "BLOCK"}
        self.rows[-1]["attachment"]["prompt"] = self.notification()
        self.assertEqual(self.check()["verdict"], "BLOCK")

    def test_wrong_task_or_tool_or_script_or_session_is_rejected(self):
        original = copy.deepcopy(self.rows)
        for old, new in [("task_one", "other"), ("tool_one", "other")]:
            self.rows = copy.deepcopy(original)
            self.rows[-1]["attachment"]["prompt"] = self.notification().replace(old, new)
            self.assertEqual(self.check()["verdict"], "BLOCK")
        self.rows = copy.deepcopy(original)
        self.rows[0]["message"]["content"][0]["input"] = {"script": "return 2;"}
        self.assertEqual(self.check()["verdict"], "BLOCK")
        self.rows = copy.deepcopy(original)
        self.rows[1]["sessionId"] = "other"
        self.assertEqual(self.check()["verdict"], "BLOCK")

    def test_duplicate_launch_and_stale_journal_rejected(self):
        original = copy.deepcopy(self.rows)
        self.rows.insert(1, copy.deepcopy(self.rows[0]))
        self.assertEqual(self.check()["verdict"], "BLOCK")
        self.rows = original
        self.rows[1]["toolUseResult"]["transcriptDir"] = str(self.root / "old")
        self.assertEqual(self.check()["verdict"], "BLOCK")

    def test_missing_agent_result_rejected(self):
        self.journal.write_text('{"type":"launched"}\n')
        self.assertEqual(self.check()["verdict"], "BLOCK")

    def test_mission_requires_exact_args_script_hash_and_runtime_pass(self):
        script = self.root / "saetta.js"
        script.write_text("return 1;")
        script_hash = receipt.digest(script.read_bytes())
        self.request = {"scriptPath": str(script), "args": {"mission": "test", "tasks": [{"key": "one"}]}}
        self.rows[0]["message"]["content"][0]["input"] = copy.deepcopy(self.request)
        self.rows[1]["toolUseResult"]["scriptPath"] = str(script)
        self.result = {"mission": "test", "verdict": "PASS", "results": [{"key": "one", "verdict": "PASS"}],
                       "close": {"recorded": True, "verdict": "PASS", "receipt": str(self.root / "close.json")}}
        self.rows[-1]["attachment"]["prompt"] = self.notification()
        self.assertEqual(self.check(smoke=False, script_sha256=script_hash)["verdict"], "PASS")
        self.rows[0]["message"]["content"][0]["input"]["args"]["mission"] = "other"
        self.assertEqual(self.check(smoke=False, script_sha256=script_hash)["verdict"], "BLOCK")
        self.rows[0]["message"]["content"][0]["input"] = copy.deepcopy(self.request)
        self.assertEqual(self.check(smoke=False, script_sha256="wrong")["verdict"], "BLOCK")
        for edit in [lambda: self.result.update(verdict="BLOCK"), lambda: self.result["close"].update(recorded=False)]:
            self.result["verdict"] = "PASS"
            edit()
            self.rows[-1]["attachment"]["prompt"] = self.notification()
            self.assertEqual(self.check(smoke=False, script_sha256=script_hash)["verdict"], "BLOCK")


if __name__ == "__main__":
    unittest.main()
