"""Tests for the external editor module."""

from __future__ import annotations

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from deepagents_cli.editor import (
    GUI_WAIT_FLAG,
    VIM_EDITORS,
    _prepare_command,
    open_in_editor,
    resolve_editor,
)


class TestResolveEditor:
    """Tests for editor resolution from environment."""

    def test_visual_takes_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VISUAL", "nvim")
        monkeypatch.setenv("EDITOR", "nano")
        assert resolve_editor() == ["nvim"]

    def test_editor_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.setenv("EDITOR", "nano")
        assert resolve_editor() == ["nano"]

    def test_default_vi_on_unix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        with patch("deepagents_cli.editor.sys") as mock_sys:
            mock_sys.platform = "linux"
            result = resolve_editor()
        assert result == ["vi"]

    def test_default_notepad_on_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        with patch("deepagents_cli.editor.sys") as mock_sys:
            mock_sys.platform = "win32"
            result = resolve_editor()
        assert result == ["notepad"]

    def test_editor_with_args(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.setenv("EDITOR", "vim -u NONE")
        assert resolve_editor() == ["vim", "-u", "NONE"]


class TestPrepareCommand:
    """Tests for command preparation with flag injection."""

    def test_gui_editor_gets_wait_flag(self) -> None:
        cmd = _prepare_command(["code"], "/tmp/f.md")
        assert cmd == ["code", "--wait", "/tmp/f.md"]

    def test_subl_gets_w_flag(self) -> None:
        cmd = _prepare_command(["subl"], "/tmp/f.md")
        assert cmd == ["subl", "-w", "/tmp/f.md"]

    def test_no_duplicate_wait_flag(self) -> None:
        cmd = _prepare_command(["code", "--wait"], "/tmp/f.md")
        assert cmd.count("--wait") == 1

    def test_vim_gets_i_none(self) -> None:
        cmd = _prepare_command(["vim"], "/tmp/f.md")
        assert "-i" in cmd
        assert "NONE" in cmd

    def test_vim_no_duplicate_i_flag(self) -> None:
        cmd = _prepare_command(["vim", "-i", "/dev/null"], "/tmp/f.md")
        assert cmd.count("-i") == 1

    def test_plain_terminal_editor(self) -> None:
        cmd = _prepare_command(["nano"], "/tmp/f.md")
        assert cmd == ["nano", "/tmp/f.md"]

    def test_does_not_mutate_input(self) -> None:
        original = ["code"]
        _prepare_command(original, "/tmp/f.md")
        assert original == ["code"]


class TestOpenInEditor:
    """Tests for the full open_in_editor flow."""

    @patch("deepagents_cli.editor.subprocess.run")
    @patch("deepagents_cli.editor.resolve_editor", return_value=["nano"])
    def test_returns_edited_text(
        self, _mock_resolve: MagicMock, mock_run: MagicMock, tmp_path: object
    ) -> None:
        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            # Write edited content to the temp file the editor would open
            filepath = cmd[-1]
            with open(filepath, "w") as f:
                f.write("edited content")
            result = MagicMock()
            result.returncode = 0
            return result

        mock_run.side_effect = fake_run
        result = open_in_editor("original")
        assert result == "edited content"

    @patch("deepagents_cli.editor.subprocess.run")
    @patch("deepagents_cli.editor.resolve_editor", return_value=["nano"])
    def test_returns_none_on_nonzero_exit(
        self, _mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=1)
        result = open_in_editor("text")
        assert result is None

    @patch("deepagents_cli.editor.subprocess.run")
    @patch("deepagents_cli.editor.resolve_editor", return_value=["nano"])
    def test_returns_none_on_empty_edit(
        self, _mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            filepath = cmd[-1]
            with open(filepath, "w") as f:
                f.write("   \n  ")
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run
        result = open_in_editor("original")
        assert result is None

    @patch(
        "deepagents_cli.editor.subprocess.run",
        side_effect=FileNotFoundError("not found"),
    )
    @patch("deepagents_cli.editor.resolve_editor", return_value=["nonexistent"])
    def test_returns_none_on_editor_not_found(
        self, _mock_resolve: MagicMock, _mock_run: MagicMock
    ) -> None:
        result = open_in_editor("text")
        assert result is None

    @patch("deepagents_cli.editor.subprocess.run")
    @patch("deepagents_cli.editor.resolve_editor", return_value=["nano"])
    def test_normalizes_line_endings(
        self, _mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            filepath = cmd[-1]
            with open(filepath, "wb") as f:
                f.write(b"line1\r\nline2\rline3\n")
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run
        result = open_in_editor("")
        assert result == "line1\nline2\nline3\n"

    @patch("deepagents_cli.editor.subprocess.run")
    @patch("deepagents_cli.editor.resolve_editor", return_value=["nano"])
    def test_cleans_up_temp_file(
        self, _mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        created_path: str | None = None

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            nonlocal created_path
            created_path = cmd[-1]
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run
        open_in_editor("text")
        assert created_path is not None
        assert not os.path.exists(created_path)

    @patch("deepagents_cli.editor.subprocess.run")
    @patch("deepagents_cli.editor.resolve_editor", return_value=["nano"])
    def test_temp_file_has_md_extension(
        self, _mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            filepath = cmd[-1]
            assert filepath.endswith(".md")
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_run
        open_in_editor("text")
