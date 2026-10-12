"""Tests for scripts/agy_image.py: no real agy call."""
from __future__ import annotations

import json
import subprocess

import pytest
from PIL import Image

from scripts import agy_image
from scripts.agy_image import AgyImageError, generate_image_with_agy


def _png(path, size=(1376, 768)):
    Image.new("RGB", size, (200, 30, 30)).save(path)
    return path


def _fake_run(stdout):
    def run(argv, **kw):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")
    return run


def test_happy_path(tmp_path, monkeypatch):
    src = _png(tmp_path / "a.png")
    monkeypatch.setattr(subprocess, "run", _fake_run(f"![x](file://{src})\n**File link:** file://{src}"))
    out = generate_image_with_agy("p", tmp_path / "sub" / "o.jpg", width=640, height=360)
    with Image.open(out) as im:
        assert im.size == (640, 360) and im.mode == "RGB" and im.format == "JPEG"


def test_picks_last_link(tmp_path, monkeypatch):
    a = _png(tmp_path / "a.png", (100, 100))
    b = _png(tmp_path / "b.png", (400, 400))
    seen = {}

    def run(argv, **kw):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, stdout=f"file://{a}\nfile://{b}\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    out = generate_image_with_agy("p", tmp_path / "o.jpg", width=200, height=100)
    with Image.open(out) as im:
        assert im.size == (200, 100)
    assert seen["argv"][:2] == [agy_image.AGY_BIN, "-p"]
    assert seen["argv"][-1] == "220s"


def test_no_link_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("nothing here"))
    with pytest.raises(AgyImageError):
        generate_image_with_agy("p", tmp_path / "o.jpg")


def test_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(f"file://{tmp_path}/gone.png"))
    with pytest.raises(AgyImageError):
        generate_image_with_agy("p", tmp_path / "o.jpg")


def test_env_strips_secrets(monkeypatch):
    monkeypatch.setenv("FOO_API_KEY", "x")
    monkeypatch.setenv("X_TOKEN", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("HOME", "/h")
    env = agy_image._agy_env({"EXTRA": "1"})
    assert not {"FOO_API_KEY", "X_TOKEN", "ANTHROPIC_API_KEY"} & set(env)
    assert env["HOME"] == "/h" and env["EXTRA"] == "1" and env["TERM"] == "dumb"
    assert env["PATH"].startswith(agy_image.os.path.expanduser("~/.local/bin"))


@pytest.mark.parametrize("size", [(2000, 768), (768, 2000)])
def test_center_crop_aspect(size):
    with Image.new("RGB", size) as im:
        c = agy_image._center_crop(im, 1344, 768)
    assert abs(c.size[0] / c.size[1] - 1344 / 768) < 0.01


@pytest.mark.parametrize("found", [True, False])
def test_available(monkeypatch, found):
    monkeypatch.setattr(agy_image.shutil, "which", lambda b: "/x/agy" if found else None)
    assert agy_image.agy_image_available() is found


def test_cli_success(tmp_path, monkeypatch, capsys):
    def fake(prompt, dest, **kw):
        _png(dest)
        return dest

    monkeypatch.setattr(agy_image, "generate_image_with_agy", fake)
    dest = tmp_path / "o.png"
    rc = agy_image.main(["generate-image", "--prompt", "p", "--dest", str(dest)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert dest.is_file()


def test_cli_failure(tmp_path, monkeypatch, capsys):
    def boom(*a, **kw):
        raise AgyImageError("nope")

    monkeypatch.setattr(agy_image, "generate_image_with_agy", boom)
    rc = agy_image.main(["generate-image", "--prompt", "p", "--dest", str(tmp_path / "o.png")])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and "nope" in out["error"]
