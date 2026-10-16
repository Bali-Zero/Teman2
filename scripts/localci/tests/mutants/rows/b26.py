"""B26: the bulk receipts of a finished run go after 24 hours, the kept pysa receipts are gzipped atomically (prune.py)."""
from merger_mutants import PRUNE, PRUNE_T

B26_T = (PRUNE_T,)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "bulk-status-required-again": (PRUNE, "bulk_now = age_h >= BULK_KEEP_H\n", 'bulk_now = age_h >= BULK_KEEP_H and (run / "status.json").is_file()\n', B26_T),
    "bulk-24h-ignored": (PRUNE, "bulk_now = age_h >= BULK_KEEP_H\n", "bulk_now = age_h >= FULL_DAYS * 24\n", B26_T),
    "gzip-original-unlinked-before-the-rename": (PRUNE, "                    os.replace(part, gz)\n", "                    src.unlink()\n                    os.replace(part, gz)\n", B26_T),
    "gzip-file-symlink-followed": (PRUNE, "if src in skip or src.is_symlink() or not src.is_file() or gz.is_symlink():", "if src in skip or not src.is_file() or gz.is_symlink():", B26_T),
    "gzip-dir-symlink-followed": (PRUNE, "if side.is_symlink() or res.is_symlink() or not res.is_dir():", "if not res.is_dir():", B26_T),
    "taint-output-deleted-not-compressed": (PRUNE, "                    os.replace(part, gz)\n", "                    part.unlink()\n                    gz.write_bytes(b\"\")\n", B26_T),
    "gzip-stray-part-kept": (PRUNE, "                size = stale.lstat().st_size\n                if not dry:\n                    stale.unlink()\n", "                size = stale.lstat().st_size\n                if False:\n                    stale.unlink()\n", B26_T),
    "gzip-ignores-existing-gz": (PRUNE, "                if gz.is_file():", "                if False:", B26_T),
    "gzip-part-oserror-raises": (PRUNE, "            except OSError as exc:\n                if errors is not None:\n                    errors.append(f\"{stale.relative_to(run).as_posix()}", "            except ZeroDivisionError as exc:\n                if errors is not None:\n                    errors.append(f\"{stale.relative_to(run).as_posix()}", B26_T),
    "gzip-no-fsync-before-rename": (PRUNE, "                        fo.flush()\n                        os.fsync(fo.fileno())\n", "                        fo.flush()\n", B26_T),
    "gzip-no-directory-fsync": (PRUNE, "                        os.fsync(dfd)\n", "                        pass\n", B26_T),
    "gzip-symlinked-gz-trusted": (PRUNE, "or not src.is_file() or gz.is_symlink():", "or not src.is_file():", B26_T),
    "gzip-linked-receipts-followed": (PRUNE, '    if run.is_symlink() or (run / "receipts").is_symlink() or base.is_symlink() or not base.is_dir():', "    if not base.is_dir():", B26_T),
    "prune-errors-not-failed": (PRUNE, '        + (["runs"] if rec.get("runs", {}).get("errors") else [])', "", B26_T),
    "gzip-fsyncs-the-file-not-the-directory": (PRUNE, "                        os.fsync(dfd)\n", "                        os.fsync(os.open(gz, os.O_RDONLY))\n", B26_T),
    "gzip-failure-not-in-errors": (PRUNE, '            except OSError as exc:\n                if errors is not None:\n                    errors.append(f"{src.relative_to(run)', '            except OSError as exc:\n                if False:\n                    errors.append(f"{src.relative_to(run)', B26_T),
    "bulk-includes-the-verdict": (PRUNE, "bulk = full and bulk_now and f in BULK", 'bulk = full and bulk_now and (f in BULK or f == "taint-output.json")', B26_T),
    "bulk-symlink-followed": (PRUNE, "for root, dirs, files in os.walk(run):", "for root, dirs, files in os.walk(run, followlinks=True):", B26_T),
    "bulk-not-listed": (PRUNE, '                if bulk_hit:\n                    out["trimmed_bulk"].append(run.name)\n', '                if False:\n                    out["trimmed_bulk"].append(run.name)\n', B26_T),
    "gzip-part-open-follows-symlink": (PRUNE, 'os.fdopen(os.open(part, flags, 0o644), "wb")', 'open(part, "wb")', B26_T),
    "gzip-recovery-skips-dir-fsync": (PRUNE, "                if not dry:\n                    dfd = os.open(res, os.O_RDONLY)", "                if not dry and not gz.is_file():\n                    dfd = os.open(res, os.O_RDONLY)", B26_T),
}
