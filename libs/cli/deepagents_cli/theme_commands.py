"""CLI commands for theme management."""

from __future__ import annotations

import dataclasses
import functools
from typing import TYPE_CHECKING, Any

from rich.console import Console

if TYPE_CHECKING:
    import argparse

console = Console()


def _list(*, output_format: str = "text") -> None:
    """List all available built-in themes.

    Args:
        output_format: Output format (`"text"` or `"json"`).
    """
    from deepagents_cli.config import BUILTIN_THEMES, theme

    names = sorted(BUILTIN_THEMES)

    if output_format == "json":
        import json

        console.print(json.dumps({"themes": names}))
        return

    console.print()
    console.print("[bold]Available themes:[/bold]", style=theme.primary)
    for name in names:
        console.print(f"  {name}")
    console.print()
    console.print(
        "Set a theme with DA_THEME=<name>, "
        "~/.deepagents/theme.yaml, "
        "or .deepagents/theme.yaml",
        style=theme.text_muted,
    )
    console.print()


def _current(*, output_format: str = "text") -> None:
    """Show the current active theme values.

    Args:
        output_format: Output format (`"text"` or `"json"`).
    """
    from deepagents_cli.config import Theme, theme

    fields = dataclasses.fields(Theme)
    defaults = Theme()

    if output_format == "json":
        import json

        data = {f.name: getattr(theme, f.name) for f in fields}
        console.print(json.dumps(data, indent=2))
        return

    console.print()
    console.print("[bold]Current theme:[/bold]", style=theme.primary)
    for field in fields:
        value = getattr(theme, field.name)
        default = getattr(defaults, field.name)
        marker = "" if value == default else " *"
        if value:
            console.print(f"  {field.name}: [{value}]■[/{value}] {value}{marker}")
        else:
            console.print(f"  {field.name}: (unset){marker}")
    console.print()
    console.print("  * = overridden from default", style=theme.text_muted)
    console.print()


def _init(*, project: bool = False, output_format: str = "text") -> None:
    """Scaffold a theme.yaml file.

    Args:
        project: If `True`, create in `.deepagents/theme.yaml` (project-level).
            Otherwise create in `~/.deepagents/theme.yaml` (user-level).
        output_format: Output format (`"text"` or `"json"`).
    """
    import json
    from pathlib import Path

    from deepagents_cli.config import Theme, theme

    if project:
        target = Path.cwd() / ".deepagents" / "theme.yaml"
    else:
        target = Path.home() / ".deepagents" / "theme.yaml"

    if target.exists():
        if output_format == "json":
            console.print(json.dumps({
                "error": f"File already exists: {target}",
                "path": str(target),
            }))
        else:
            console.print(
                f"\n[bold {theme.warning}]"
                f"File already exists:"
                f"[/bold {theme.warning}] {target}\n"
            )
        return

    fields = dataclasses.fields(Theme)
    lines = [
        "# Deep Agents CLI theme configuration",
        "#",
        "# Uncomment and edit values to customize colors.",
        "# Colors can be hex (#rrggbb), named (red, cyan), etc.",
        "#",
        "# See all fields: deepagents theme current",
        "",
    ]
    lines.extend(
        f"# {field.name}: {field.default!r}" for field in fields
    )
    lines.append("")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")

    if output_format == "json":
        console.print(json.dumps({"path": str(target)}))
    else:
        console.print(
            f"\n[bold {theme.success}]Created:[/bold {theme.success}] {target}\n"
        )


def execute_theme_command(args: argparse.Namespace) -> None:
    """Execute theme subcommands based on parsed arguments.

    Args:
        args: Parsed command line arguments with `theme_command` attribute.
    """
    from deepagents_cli.ui import show_theme_help

    output_format = getattr(args, "output_format", "text")

    if args.theme_command in {"list", "ls"}:
        _list(output_format=output_format)
    elif args.theme_command == "current":
        _current(output_format=output_format)
    elif args.theme_command == "init":
        _init(project=getattr(args, "project", False), output_format=output_format)
    else:
        show_theme_help()


def setup_theme_parser(
    subparsers: Any,  # noqa: ANN401
    *,
    make_help_action: Any,  # noqa: ANN401
    add_output_args: Any | None = None,  # noqa: ANN401
) -> argparse.ArgumentParser:
    """Set up the theme subcommand parser.

    Args:
        subparsers: Parent subparsers object.
        make_help_action: Factory that accepts a help callable and returns
            an argparse Action class.
        add_output_args: Optional hook to add `--json` flag.

    Returns:
        The theme subparser.
    """
    from deepagents_cli.ui import (
        build_help_parent,
        show_theme_current_help,
        show_theme_help,
        show_theme_init_help,
        show_theme_list_help,
    )

    help_parent = functools.partial(
        build_help_parent, make_help_action=make_help_action
    )

    theme_parser = subparsers.add_parser(
        "theme",
        help="Manage color themes",
        description=(
            "Manage color themes — list built-in themes, "
            "view current values, or scaffold a theme file."
        ),
        add_help=False,
        parents=help_parent(show_theme_help),
    )
    if add_output_args is not None:
        add_output_args(theme_parser)
    theme_sub = theme_parser.add_subparsers(
        dest="theme_command", help="Theme command"
    )

    list_parser = theme_sub.add_parser(
        "list",
        aliases=["ls"],
        help="List available built-in themes",
        add_help=False,
        parents=help_parent(show_theme_list_help),
    )
    if add_output_args is not None:
        add_output_args(list_parser)

    current_parser = theme_sub.add_parser(
        "current",
        help="Show current theme values",
        add_help=False,
        parents=help_parent(show_theme_current_help),
    )
    if add_output_args is not None:
        add_output_args(current_parser)

    init_parser = theme_sub.add_parser(
        "init",
        help="Create a theme.yaml template",
        add_help=False,
        parents=help_parent(show_theme_init_help),
    )
    if add_output_args is not None:
        add_output_args(init_parser)
    init_parser.add_argument(
        "--project",
        action="store_true",
        help="Create in .deepagents/theme.yaml (project-level) instead of user-level",
    )

    return theme_parser


__all__ = [
    "execute_theme_command",
    "setup_theme_parser",
]
