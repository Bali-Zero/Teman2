"""OS-derived local Conductor host identity tests."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.conductor.host_identity import (
    HostIdentityError,
    canonical_hostname,
    observe_local_host,
)


class ConductorHostIdentityTest(unittest.TestCase):
    def test_effective_uid_and_socket_hostname_ignore_spoofed_environment(self) -> None:
        spoofed = {
            "USER": "balizero",
            "LOGNAME": "attacker",
            "HOSTNAME": "Mini-Pro2",
            "HOME": "/tmp/spoofed-home",
        }
        with (
            patch.dict(os.environ, spoofed, clear=False),
            patch(
                "scripts.conductor.host_identity.socket.gethostname",
                return_value="Nuzantara.local",
            ),
            patch("scripts.conductor.host_identity.os.geteuid", return_value=501),
            patch(
                "scripts.conductor.host_identity.pwd.getpwuid",
                return_value=SimpleNamespace(pw_name="nuzantara"),
            ) as account_lookup,
        ):
            identity = observe_local_host()

        account_lookup.assert_called_once_with(501)
        self.assertEqual(identity.machine, "pro")
        self.assertEqual(identity.fleet_label, "Pro")
        self.assertEqual(identity.hostname, "nuzantara")
        self.assertEqual(identity.username, "nuzantara")
        self.assertEqual(identity.effective_uid, 501)

    def test_fleet_labels_preserve_runtime_machine_ids(self) -> None:
        observations = (
            ("Nuzantara", "nuzantara", "pro", "Pro"),
            ("Mini-Pro2.local", "nuzantara", "mini-pro2", "Mini-Pro2"),
            ("Air-M5", "balizero", "air-m5", "Air-M5"),
        )
        for hostname, username, machine, label in observations:
            with (
                self.subTest(hostname=hostname),
                patch(
                    "scripts.conductor.host_identity.socket.gethostname",
                    return_value=hostname,
                ),
                patch("scripts.conductor.host_identity.os.geteuid", return_value=502),
                patch(
                    "scripts.conductor.host_identity.pwd.getpwuid",
                    return_value=SimpleNamespace(pw_name=username),
                ),
            ):
                identity = observe_local_host()
                self.assertEqual(identity.machine, machine)
                self.assertEqual(identity.fleet_label, label)

    def test_unknown_host_and_effective_user_mismatch_fail_closed(self) -> None:
        with (
            patch(
                "scripts.conductor.host_identity.socket.gethostname",
                return_value="remote-claim",
            ),
            self.assertRaisesRegex(HostIdentityError, "outside the attested fleet"),
        ):
            observe_local_host()

        with (
            patch(
                "scripts.conductor.host_identity.socket.gethostname",
                return_value="Air-M5",
            ),
            patch("scripts.conductor.host_identity.os.geteuid", return_value=503),
            patch(
                "scripts.conductor.host_identity.pwd.getpwuid",
                return_value=SimpleNamespace(pw_name="nuzantara"),
            ),
            self.assertRaisesRegex(HostIdentityError, "effective user disagree"),
        ):
            observe_local_host()

    def test_canonical_hostname_rejects_invalid_observations(self) -> None:
        self.assertEqual(canonical_hostname(" Mini-Pro2.local "), "mini-pro2")
        for invalid in ("", "   ", "Air-M5\x00.local"):
            with self.subTest(invalid=invalid), self.assertRaises(HostIdentityError):
                canonical_hostname(invalid)


if __name__ == "__main__":
    unittest.main()
