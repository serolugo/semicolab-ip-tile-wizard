"""
tilewizard wrap
Reads ip_config.yaml, validates everything, and generates the full tile output.
"""

import os

from tilewizard.core.validator import (
    load_and_validate_config,
    validate_src_and_top,
    validate_port_map,
)
from tilewizard.core.generator import build_output


def cmd_wrap() -> None:
    cwd = os.getcwd()

    # 1 — Load and validate config
    cfg = load_and_validate_config(cwd)

    # 2 — Validate src/ and top_module
    v_files = validate_src_and_top(cfg, cwd)

    # 3 — Validate port mappings
    parsed_ports, warnings = validate_port_map(cfg)

    # 4 — Print warnings (non-blocking)
    for w in warnings:
        print(w)

    # 5 — Generate output
    generated = build_output(cfg, parsed_ports, v_files, warnings, cwd)

    # 6 — Summary
    tile_name = cfg["ip_tile_name"].strip()
    top_module = cfg["top_module"].strip()
    mapped = sum(1 for (tp, _, _) in parsed_ports.values() if tp is not None)

    print()
    print("─" * 56)
    print(f"  TileWizard V1 — tile generado exitosamente")
    print("─" * 56)
    print(f"  Tile name    : {tile_name}")
    print(f"  Top module   : {top_module}")
    print(f"  Wrapper      : {tile_name}_wrapper")
    print(f"  Puertos IP   : {len(parsed_ports)} ({mapped} mapeados)")
    print(f"  Archivos .v  : {len(v_files)} copiados + wrapper")
    print(f"  Warnings     : {len(warnings)}")
    print()
    print(f"  Output en: {tile_name}/")
    print(f"    ├── output/rtl/")
    print(f"    ├── output/docs/")
    print(f"    └── veriflow/")
    print("─" * 56)
