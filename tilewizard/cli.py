"""
TileWizard CLI — SemiCoLab IP Tile Wizard V1
"""

import argparse
import sys
from pathlib import Path

from tilewizard.commands.init_cmd import cmd_init
from tilewizard.commands.parse_cmd import cmd_parse
from tilewizard.commands.wrap_cmd import cmd_wrap


def main():
    # No arguments → TUI interactiva
    if len(sys.argv) == 1:
        from tilewizard.ui.tui import run_tui
        run_tui()
        return

    parser = argparse.ArgumentParser(
        prog="tilewizard",
        description="SemiCoLab IP Tile Wizard V1 — wraps generic RTL into SemiCoLab-compatible tiles.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # ── init
    p_init = subparsers.add_parser("init", help="Initialize a new TileWizard project folder.")
    p_init.add_argument("project_name", help="Name of the project folder to create.")

    # ── parse
    p_parse = subparsers.add_parser("parse", help="Extract ports from RTL and generate ip_config.yaml.")
    p_parse.add_argument("--top", required=True, metavar="<top_module>",
                         help="Name of the top-level Verilog module (without .v extension).")

    # ── wrap
    subparsers.add_parser("wrap", help="Generate the complete SemiCoLab tile output.")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "init":
        cmd_init(args.project_name)
    elif args.command == "parse":
        cmd_parse(args.top)
    elif args.command == "wrap":
        cmd_wrap()


if __name__ == "__main__":
    main()
