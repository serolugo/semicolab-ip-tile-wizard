"""
validator.py — validates ip_config.yaml and port mappings for `tilewizard wrap`.
"""

import os
import re
import sys
from typing import Any, Dict, List, Tuple

import yaml


# ── SemiCoLab tile interface definition ──────────────────────────────────────

TILE_INPUTS = {
    "clk":        1,
    "arst_n":     1,
    "csr_in":     16,
    "data_reg_a": 32,
    "data_reg_b": 32,
}

TILE_OUTPUTS = {
    "data_reg_c": 32,
    "csr_out":    16,
    "csr_in_re":  1,
    "csr_out_we": 1,
}

TILE_PORTS = {**TILE_INPUTS, **TILE_OUTPUTS}

# Ports that are 1-bit (no slice syntax allowed)
_SCALAR_PORTS = {"clk", "arst_n", "csr_in_re", "csr_out_we"}

# Pattern: port_name  or  port_name[hi:lo]  or  port_name[bit]
_MAP_RE = re.compile(r"^(\w+)(?:\[(\d+)(?::(\d+))?\])?$")


def _parse_map_to(value: str) -> Tuple[str, Any, Any]:
    """Parse a map_to string like 'csr_in[3:0]' → ('csr_in', 3, 0).

    Returns (port_name, hi, lo).  hi/lo are None for scalar ports.
    Raises ValueError on parse failure.
    """
    value = str(value).strip()
    m = _MAP_RE.match(value)
    if not m:
        raise ValueError(f"Sintaxis de mapeo inválida: '{value}'")
    port_name = m.group(1)
    hi = int(m.group(2)) if m.group(2) is not None else None
    lo = int(m.group(3)) if m.group(3) is not None else None
    # single-bit slice like [4] → hi=4, lo=None → normalise to hi=4, lo=4
    if hi is not None and lo is None:
        lo = hi
    return port_name, hi, lo


def load_and_validate_config(cwd: str) -> Dict:
    """Load ip_config.yaml and run all validations.

    Returns the validated config dict.  Exits with sys.exit(1) on fatal error.
    """
    config_path = os.path.join(cwd, "ip_config.yaml")
    if not os.path.isfile(config_path):
        print("[TW-E01] ip_config.yaml no encontrado en el directorio actual.")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        print(f"[TW-E02] Sintaxis YAML inválida: {exc}")
        sys.exit(1)

    if not isinstance(cfg, dict):
        print("[TW-E02] ip_config.yaml no contiene un mapa YAML válido.")
        sys.exit(1)

    # TW-E03 — required fields
    required = ["ip_tile_name", "top_module", "author", "description"]
    for field in required:
        val = cfg.get(field)
        if val is None or str(val).strip() == "":
            print(f"[TW-E03] Campo obligatorio ausente o vacío: '{field}'.")
            sys.exit(1)

    return cfg


def validate_src_and_top(cfg: Dict, cwd: str) -> List[str]:
    """Validate src/ exists and contains the top_module.

    Returns the list of .v file paths in src/.
    """
    src_dir = os.path.join(cwd, "src")
    if not os.path.isdir(src_dir):
        print("[TW-E04] Carpeta 'src/' no encontrada.")
        sys.exit(1)

    v_files = [
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.endswith(".v")
    ]
    if not v_files:
        print("[TW-E04] Carpeta 'src/' vacía o sin archivos .v.")
        sys.exit(1)

    top_module = cfg["top_module"].strip()
    found = False
    module_re = re.compile(r"\bmodule\s+" + re.escape(top_module) + r"\b")
    for vf in v_files:
        with open(vf, "r", encoding="utf-8") as fh:
            if module_re.search(fh.read()):
                found = True
                break

    if not found:
        print(f"[TW-E05] top_module '{top_module}' no encontrado como módulo en ningún .v de src/.")
        sys.exit(1)

    return v_files


def validate_port_map(cfg: Dict) -> Tuple[Dict, List[str]]:
    """Validate the ports section of ip_config.yaml.

    Returns:
        parsed_ports  — dict  ip_port → (tile_port, hi, lo)  for mapped ports
        warnings      — list of warning strings
    """
    raw_ports = cfg.get("ports")
    if not raw_ports or not isinstance(raw_ports, dict):
        # No ports section — not fatal, just nothing to connect
        return {}, ["[TW-W01] Sección 'ports' ausente o vacía — no se generarán conexiones."]

    warnings: List[str] = []
    parsed: Dict[str, Tuple[str, Any, Any]] = {}

    # Track bit-level usage per tile port to detect TW-E06
    # tile_port → set of bit indices already assigned
    used_bits: Dict[str, set] = {p: set() for p in TILE_PORTS}

    for ip_port, map_value in raw_ports.items():
        if map_value is None or str(map_value).strip() == "":
            warnings.append(f"[TW-W01] Puerto '{ip_port}' sin mapeo — será ignorado.")
            parsed[ip_port] = (None, None, None)
            continue

        try:
            tile_port, hi, lo = _parse_map_to(str(map_value))
        except ValueError as exc:
            print(f"[TW-E07] {exc} (puerto IP: '{ip_port}')")
            sys.exit(1)

        # TW-E08 — unrecognised tile port
        if tile_port not in TILE_PORTS:
            print(f"[TW-E08] Puerto tile '{tile_port}' no reconocido "
                  f"(mapeado desde '{ip_port}'). Puertos válidos: {sorted(TILE_PORTS)}.")
            sys.exit(1)

        tile_width = TILE_PORTS[tile_port]

        # Determine the set of bits being claimed
        if tile_width == 1:
            # Scalar port — no slice accepted (or slice must be [0])
            if hi is not None and not (hi == 0 and lo == 0):
                print(f"[TW-E07] Puerto '{tile_port}' es escalar (1 bit); "
                      f"slice [{hi}:{lo}] inválido (ip: '{ip_port}').")
                sys.exit(1)
            bits_claimed = {0}
        else:
            # Bus port
            if hi is None:
                # Full bus
                bits_claimed = set(range(tile_width))
                hi = tile_width - 1
                lo = 0
            else:
                if hi >= tile_width or lo < 0 or hi < lo:
                    print(f"[TW-E07] Slice [{hi}:{lo}] fuera de rango para "
                          f"'{tile_port}[{tile_width-1}:0]' (ip: '{ip_port}').")
                    sys.exit(1)
                bits_claimed = set(range(lo, hi + 1))

        # TW-E06 — bit conflict
        overlap = used_bits[tile_port] & bits_claimed
        if overlap:
            print(f"[TW-E06] Conflicto de mapeo: bits {sorted(overlap)} de '{tile_port}' "
                  f"ya asignados (conflicto en ip: '{ip_port}').")
            sys.exit(1)

        used_bits[tile_port] |= bits_claimed
        parsed[ip_port] = (tile_port, hi, lo)

    # ── collect per-port warnings ─────────────────────────────────────────────
    # TW-W03 / TW-W04 / TW-W05
    if not used_bits["csr_out_we"]:
        warnings.append("[TW-W03] csr_out_we no mapeado — se asignará 1'b1.")
    if not used_bits["csr_in_re"]:
        warnings.append("[TW-W04] csr_in_re no mapeado — se asignará 1'b0.")
    if not used_bits["data_reg_b"]:
        warnings.append("[TW-W05] data_reg_b no mapeado — sin asignación (documentado).")

    # TW-W02 — unassigned bits on bus outputs
    for out_port in ["data_reg_c", "csr_out"]:
        width = TILE_PORTS[out_port]
        all_bits = set(range(width))
        assigned = used_bits[out_port]
        free_bits = all_bits - assigned
        if free_bits:
            # Build compact range description for the warning
            ranges = _bits_to_ranges(sorted(free_bits))
            for (h, l) in ranges:
                if h == l:
                    bit_desc = f"[{h}]"
                else:
                    bit_desc = f"[{h}:{l}]"
                warnings.append(
                    f"[TW-W02] {out_port}{bit_desc} sin asignar — "
                    f"se generará assign {out_port}{bit_desc} = 0."
                )

    return parsed, warnings


def _bits_to_ranges(bits: List[int]) -> List[Tuple[int, int]]:
    """Convert a sorted list of bit indices to (hi, lo) contiguous ranges."""
    if not bits:
        return []
    ranges = []
    lo = hi = bits[0]
    for b in bits[1:]:
        if b == hi + 1:
            hi = b
        else:
            ranges.append((hi, lo))
            lo = hi = b
    ranges.append((hi, lo))
    return ranges


def get_unassigned_output_ranges(parsed_ports: Dict, tile_port: str) -> List[Tuple[int, int]]:
    """Return list of (hi, lo) ranges that are NOT covered by parsed_ports for a tile output."""
    width = TILE_PORTS[tile_port]
    used = set()
    for ip_port, (tp, hi, lo) in parsed_ports.items():
        if tp != tile_port or hi is None:
            continue
        used |= set(range(lo, hi + 1))
    free = set(range(width)) - used
    return _bits_to_ranges(sorted(free))
