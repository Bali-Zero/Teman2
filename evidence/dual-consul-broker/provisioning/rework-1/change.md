# Provisioning correction after native review 1

The parent directory retains the original pre-review proof and its original
release digest. It is historical evidence, not proof for this corrected source.
This directory records the first correction cycle and its distinct bundle.

Native review identified that byte hashes do not cover setuid/setgid mode bits.
The macOS `ditto(1)` manual confirms that privileged copies preserve those bits;
neither a content digest nor an assumption about `chown` is sufficient.

The installer now copies into a fresh private mode-0700 staging directory. It
checks content and rejects links, explicitly removes setuid and setgid before
changing ownership, removes copied ACLs/xattrs and group/other write access,
checks the resulting modes, then publishes the release directory. A failed copy
remains private and is not a binding. Existing releases and rollback candidates
pass a shell mode check before their Python executable is invoked. The Python
immutable verifier independently rejects the combined unsafe mask `0o6022`.

The focused suite now passes **36 tests on M5 (5.41 seconds)** and **36 tests on
Pro (1.36 seconds)**. New cases cover matching hashes with modes 4755, 2755 and
6755, normalization before ownership/publication, and refusal before execution
of an unsafe existing or rollback release. Root metadata and ownership changes
are modeled in unit fixtures; actual files remain ordinary-user temporary test
files. No root provisioning, service activation, or live rollback was performed.

The rebuild also includes the parent's frozen review corrections, including
the shared `scripts/conductor/native_canary_contract.py` import. Those changes
are identified by the source manifests and were not authored by this package
worker.
