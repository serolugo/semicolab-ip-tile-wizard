"""
tilewizard.ui.tui
─────────────────
Redirige al TUI de tilebench (modo TileWizard).
Requiere que tilebench esté instalado.
"""
from pathlib import Path


def run_tui(workspace: Path = Path(".")) -> None:
    from tilebench.tui.selector import run_tilewizard
    run_tilewizard(workspace=None)  # None → _get_workspace() detecta /workspace en Docker
