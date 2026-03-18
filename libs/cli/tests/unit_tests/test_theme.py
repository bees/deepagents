"""Tests for theming infrastructure."""

from __future__ import annotations

import dataclasses
import io
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from deepagents_cli.config import (
    BUILTIN_THEMES,
    COLORS,
    Theme,
    _load_theme_file,
    apply_theme,
    load_theme,
    theme,
)


class TestThemeDataclass:
    """Tests for the Theme dataclass."""

    def test_defaults_are_strings(self) -> None:
        """Every default value should be a non-empty string."""
        t = Theme()
        for field in dataclasses.fields(t):
            value = getattr(t, field.name)
            assert isinstance(value, str), field.name
            assert value, f"{field.name} is empty"

    def test_override_single_field(self) -> None:
        """Creating a Theme with one override leaves others at defaults."""
        t = Theme(primary="#000000")
        assert t.primary == "#000000"
        assert t.error == Theme().error

    def test_as_colors_dict_keys(self) -> None:
        """as_colors_dict must contain the legacy COLORS keys."""
        t = Theme()
        d = t.as_colors_dict()
        expected = {
            "primary",
            "primary_dev",
            "dim",
            "user",
            "agent",
            "thinking",
            "tool",
            "mode_shell",
            "mode_command",
        }
        assert set(d.keys()) == expected

    def test_as_colors_dict_values_match(self) -> None:
        """Dict values must match the corresponding Theme fields."""
        t = Theme(primary="#aabbcc", text_muted="#112233")
        d = t.as_colors_dict()
        assert d["primary"] == "#aabbcc"
        assert d["dim"] == "#112233"


class TestBuiltinThemes:
    """Tests for built-in theme definitions."""

    def test_dark_is_empty(self) -> None:
        """Dark theme is just the defaults."""
        assert BUILTIN_THEMES["dark"] == {}

    def test_light_and_solarized_exist(self) -> None:
        """Light and solarized-dark themes are defined."""
        assert "light" in BUILTIN_THEMES
        assert "solarized-dark" in BUILTIN_THEMES

    def test_builtin_keys_are_valid_fields(self) -> None:
        """Every key in every built-in theme must be a valid Theme field."""
        valid = {f.name for f in dataclasses.fields(Theme)}
        for name, overrides in BUILTIN_THEMES.items():
            invalid = set(overrides.keys()) - valid
            assert not invalid, (
                f"Built-in theme {name!r} has invalid keys: {invalid}"
            )

    def test_builtin_values_are_strings(self) -> None:
        """All built-in theme values must be strings."""
        for name, overrides in BUILTIN_THEMES.items():
            for key, value in overrides.items():
                assert isinstance(value, str), (
                    f"{name}.{key} is {type(value)}"
                )


class TestLoadThemeFile:
    """Tests for _load_theme_file."""

    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        """Valid YAML with known keys is loaded."""
        f = tmp_path / "theme.yaml"
        f.write_text("primary: '#ff0000'\nerror: red\n")
        result = _load_theme_file(f)
        assert result == {"primary": "#ff0000", "error": "red"}

    def test_ignores_unknown_keys(self, tmp_path: Path) -> None:
        """Unknown keys are silently dropped."""
        f = tmp_path / "theme.yaml"
        f.write_text("primary: '#ff0000'\nno_such_field: blue\n")
        result = _load_theme_file(f)
        assert "no_such_field" not in result
        assert result["primary"] == "#ff0000"

    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        """Missing file returns empty dict."""
        result = _load_theme_file(tmp_path / "missing.yaml")
        assert result == {}

    def test_returns_empty_on_invalid_yaml(
        self, tmp_path: Path
    ) -> None:
        """Malformed YAML returns empty dict."""
        f = tmp_path / "theme.yaml"
        f.write_text(":\n  - :\n  - [")
        result = _load_theme_file(f)
        assert result == {}

    def test_returns_empty_on_non_mapping(
        self, tmp_path: Path
    ) -> None:
        """YAML that isn't a mapping returns empty dict."""
        f = tmp_path / "theme.yaml"
        f.write_text("- item1\n- item2\n")
        result = _load_theme_file(f)
        assert result == {}


class TestLoadTheme:
    """Tests for load_theme cascading."""

    def test_default_returns_dark(self) -> None:
        """No arguments returns default (dark) theme."""
        with patch.object(Path, "is_file", return_value=False):
            t = load_theme()
        assert t.primary == Theme().primary

    def test_builtin_name_applies(self) -> None:
        """Passing a built-in name applies its overrides."""
        with patch.object(Path, "is_file", return_value=False):
            t = load_theme(theme_name="light")
        assert t.primary == BUILTIN_THEMES["light"]["primary"]

    def test_unknown_name_falls_back(self) -> None:
        """Unknown name logs warning and uses defaults."""
        with patch.object(Path, "is_file", return_value=False):
            t = load_theme(theme_name="nonexistent")
        assert t.primary == Theme().primary

    def test_project_overrides_user(self, tmp_path: Path) -> None:
        """Project theme.yaml overrides user theme.yaml."""
        user_dir = tmp_path / "home" / ".deepagents"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "theme.yaml"
        user_file.write_text("primary: '#111111'\nerror: '#222222'\n")

        proj_dir = tmp_path / "project" / ".deepagents"
        proj_dir.mkdir(parents=True)
        proj_file = proj_dir / "theme.yaml"
        proj_file.write_text("primary: '#333333'\n")

        with patch.object(
            Path, "home", return_value=tmp_path / "home"
        ):
            t = load_theme(project_root=tmp_path / "project")

        assert t.primary == "#333333"
        assert t.error == "#222222"

    def test_file_path_as_theme_name(
        self, tmp_path: Path
    ) -> None:
        """A filesystem path as theme_name loads it."""
        f = tmp_path / "custom.yaml"
        f.write_text("primary: '#abcdef'\n")
        with patch.object(
            Path, "home", return_value=tmp_path / "nohome"
        ):
            t = load_theme(theme_name=str(f))
        assert t.primary == "#abcdef"


class TestApplyTheme:
    """Tests for apply_theme."""

    def test_mutates_singleton(self) -> None:
        """apply_theme updates the module-level singleton."""
        original = theme.primary
        new = Theme(primary="#000000")
        apply_theme(new)
        assert theme.primary == "#000000"
        apply_theme(Theme(primary=original))

    def test_colors_proxy_follows(self) -> None:
        """COLORS proxy reflects apply_theme changes."""
        original = theme.primary
        apply_theme(Theme(primary="#abcdef"))
        assert COLORS["primary"] == "#abcdef"
        apply_theme(Theme(primary=original))


class TestColorsProxy:
    """Tests for the _ColorsProxy dict wrapper."""

    def test_getitem(self) -> None:
        """Subscript access returns theme value."""
        assert COLORS["primary"] == theme.primary

    def test_get_with_default(self) -> None:
        """get() with missing key returns default."""
        assert COLORS.get("nonexistent", "fallback") == "fallback"

    def test_get_existing(self) -> None:
        """get() with existing key returns value."""
        assert COLORS.get("agent") == theme.agent


class TestThemeCommands:
    """Tests for CLI theme subcommands."""

    def test_list_text(self) -> None:
        """Theme list prints built-in theme names."""
        from deepagents_cli.theme_commands import _list

        buf = io.StringIO()
        with patch(
            "deepagents_cli.theme_commands.console",
            Console(file=buf, highlight=False),
        ):
            _list()
        output = buf.getvalue()
        for name in BUILTIN_THEMES:
            assert name in output

    def test_list_json(self) -> None:
        """Theme list --json outputs valid JSON."""
        import json

        from deepagents_cli.theme_commands import _list

        buf = io.StringIO()
        with patch(
            "deepagents_cli.theme_commands.console",
            Console(file=buf, highlight=False),
        ):
            _list(output_format="json")
        data = json.loads(buf.getvalue())
        assert set(data["themes"]) == set(BUILTIN_THEMES.keys())

    def test_current_text(self) -> None:
        """Theme current shows all field names."""
        from deepagents_cli.theme_commands import _current

        buf = io.StringIO()
        with patch(
            "deepagents_cli.theme_commands.console",
            Console(file=buf, highlight=False),
        ):
            _current()
        output = buf.getvalue()
        for field in dataclasses.fields(Theme):
            assert field.name in output

    def test_current_json(self) -> None:
        """Theme current --json outputs all fields."""
        import json

        from deepagents_cli.theme_commands import _current

        buf = io.StringIO()
        with patch(
            "deepagents_cli.theme_commands.console",
            Console(file=buf, highlight=False),
        ):
            _current(output_format="json")
        data = json.loads(buf.getvalue())
        field_names = {f.name for f in dataclasses.fields(Theme)}
        assert set(data.keys()) == field_names

    def test_init_creates_file(self, tmp_path: Path) -> None:
        """Theme init creates a commented theme.yaml."""
        from deepagents_cli.theme_commands import _init

        buf = io.StringIO()
        with (
            patch(
                "deepagents_cli.theme_commands.console",
                Console(file=buf, highlight=False),
            ),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            _init()

        target = tmp_path / ".deepagents" / "theme.yaml"
        assert target.exists()
        content = target.read_text()
        assert "# primary:" in content

    def test_init_refuses_existing(self, tmp_path: Path) -> None:
        """Theme init won't overwrite an existing file."""
        from deepagents_cli.theme_commands import _init

        target = tmp_path / ".deepagents" / "theme.yaml"
        target.parent.mkdir(parents=True)
        target.write_text("existing\n")

        buf = io.StringIO()
        with (
            patch(
                "deepagents_cli.theme_commands.console",
                Console(file=buf, highlight=False),
            ),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            _init()

        assert target.read_text() == "existing\n"
        assert "already exists" in buf.getvalue()

    def test_init_project_flag(self, tmp_path: Path) -> None:
        """Theme init --project creates in .deepagents/."""
        from deepagents_cli.theme_commands import _init

        buf = io.StringIO()
        with (
            patch(
                "deepagents_cli.theme_commands.console",
                Console(file=buf, highlight=False),
            ),
            patch("pathlib.Path.cwd", return_value=tmp_path),
        ):
            _init(project=True)

        target = tmp_path / ".deepagents" / "theme.yaml"
        assert target.exists()


class TestAppCSSVariables:
    """Tests for CSS variable injection in DeepAgentsApp."""

    def test_get_css_variables_includes_diff_colors(self) -> None:
        """App.get_css_variables returns diff theme colors."""
        from deepagents_cli.app import DeepAgentsApp

        assert hasattr(DeepAgentsApp, "get_css_variables")

        method = DeepAgentsApp.get_css_variables
        assert callable(method)
