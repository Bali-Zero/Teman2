"""Prepare a narrow follow-up against the recorded sibling snapshot only.

Run at the root of the isolated Pro proof worktree after copying the snapshot.
This refuses changed source bytes; it never edits the sibling worktree.
"""

import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
PACK = Path(__file__).resolve().parent
manifest = json.loads((ROOT / 'voa-d-candidate-manifest.json').read_text())
base_path = 'apps/backend-rag/backend/db/migration_base.py'
manager_path = 'apps/backend-rag/backend/db/migration_manager.py'
test_path = 'apps/backend-rag/backend/tests/db/test_migration_runner_dedicated_role.py'
changes = {}


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


for relative in (base_path, manager_path, test_path):
    before = (ROOT / relative).read_text()
    assert hashlib.sha256(before.encode()).hexdigest() == manifest['files'][relative]
    after = before
    if relative == base_path:
        after = replace_once(after,
            'def migration_dsn_is_dedicated() -> bool:\n    """True when the runner is on its own DSN rather than the runtime\'s."""\n    return bool(settings.migration_database_url)',
            'def migration_dsn_is_dedicated(database_url: str | None = None) -> bool:\n'
            '    """Classify the selected URL; a different explicit override stays legacy.\n\n'
            '    An alternate dedicated URL must pass dedicated=True explicitly.\n'
            '    """\n'
            '    return bool(settings.migration_database_url and (\n'
            '        database_url is None or database_url == settings.migration_database_url\n'
            '    ))')
        after = replace_once(after,
            '    async def apply(self, database_url: str | None = None) -> bool:',
            '    async def apply(\n        self, database_url: str | None = None, *, dedicated: bool | None = None\n    ) -> bool:')
        after = replace_once(after,
            '                Defaults to `resolve_migration_dsn()`.\n',
            '                Defaults to `resolve_migration_dsn()`.\n'
            '            dedicated: Bound mode from the manager, or resolve it from\n'
            '                the selected DSN when called standalone.\n')
        after = replace_once(after,
            '        dsn = database_url or resolve_migration_dsn()\n',
            '        dsn = database_url or resolve_migration_dsn()\n'
            '        if dedicated is None:\n'
            '            dedicated = migration_dsn_is_dedicated(dsn)\n')
        after = replace_once(after,
            '            await assume_runtime_role(conn)\n',
            '            await assume_runtime_role(conn, dedicated=dedicated)\n')
        after = replace_once(after,
            '        # `setup` hook runs on EVERY acquire, because asyncpg\'s release-time\n'
            '        # `RESET ALL` undoes `SET ROLE` (kimi, 2026-09-11) -- so the hook must\n'
            '        # be safe both when the reset happened and when it did not.\n',
            '        # `setup` hook runs on EVERY acquire. PostgreSQL RESET ALL preserves\n'
            '        # role; an explicit RESET ROLE by a borrower must still be healed.\n')
    elif relative == manager_path:
        after = replace_once(after, 'import logging\n', 'import logging\nfrom functools import partial\n')
        after = replace_once(after, '    assume_runtime_role,\n', '    assume_runtime_role,\n    migration_dsn_is_dedicated,\n')
        after = replace_once(after,
            '    def __init__(self, database_url: str | None = None) -> None:',
            '    def __init__(\n        self, database_url: str | None = None, *, dedicated: bool | None = None\n    ) -> None:')
        after = replace_once(after,
            '            database_url: Database URL (defaults to settings.database_url)',
            '            database_url: Explicit override, else the configured migration/runtime URL.\n'
            '            dedicated: Override the selected mode for an alternate dedicated URL.')
        after = replace_once(after,
            '        self.database_url = database_url or resolve_migration_dsn()\n',
            '        self.database_url = database_url or resolve_migration_dsn()\n'
            '        self._dedicated = (migration_dsn_is_dedicated(self.database_url)\n'
            '                           if dedicated is None else dedicated)\n')
        after = replace_once(after,
            '                # asyncpg\'s release-time `RESET ALL` undoes `SET ROLE` -- so an\n'
            '                # `init`-only hook would hold for the first acquire and silently\n'
            '                # lapse on the second (kimi, 2026-09-11). The hook is idempotent.\n'
            '                setup=assume_runtime_role,',
            '                # an explicit RESET ROLE by a borrower is healed on checkout.\n'
            '                # Bind mode once with the URL, including explicit overrides.\n'
            '                setup=partial(assume_runtime_role, dedicated=self._dedicated),')
        after = replace_once(after,
            '        return await migration.apply(database_url=self.database_url)',
            '        return await migration.apply(database_url=self.database_url, dedicated=self._dedicated)')
    else:
        after = replace_once(after,
            '        async def apply(self, database_url=None):',
            '        async def apply(self, database_url=None, *, dedicated=None):')
    changes[relative] = (before, after)

patch = ''.join(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
    fromfile='a/' + relative, tofile='b/' + relative)) for relative, (before, after) in changes.items())
for relative, (_, after) in changes.items():
    (ROOT / relative).write_text(after)
(PACK / 'runner-selection-followup.patch').write_text(patch)

relative = 'apps/backend-rag/backend/db/migrations_v2/304_garuda_documents.sql'
before = (ROOT / relative).read_text()
after = replace_once(before, 'DO $garuda_304_owner_transfer$\n', 'RESET ROLE;\nDO $garuda_304_owner_transfer$\n')
after = replace_once(after, '$garuda_304_owner_transfer$;\n', '$garuda_304_owner_transfer$;\nSET ROLE backend_rag_v2;\n')
(PACK / 'migration-304-owner-bracket.patch').write_text(''.join(difflib.unified_diff(
    before.splitlines(True), after.splitlines(True), fromfile='a/' + relative, tofile='b/' + relative)))
(PACK / 'tested-candidate-hashes.json').write_text(json.dumps({
    **{relative: hashlib.sha256(after.encode()).hexdigest() for relative, (_, after) in changes.items()},
    relative: hashlib.sha256(after.encode()).hexdigest(),
}, indent=2) + '\n')
print('PREPARED: selection follow-up and 304 owner bracket; sibling untouched')
