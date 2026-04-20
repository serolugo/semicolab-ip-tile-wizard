"""
generator.py — generates wrapper RTL and all supporting files for `tilewizard wrap`.
"""

import os
import shutil
from datetime import date
from typing import Dict, List, Tuple

from jinja2 import Environment, FileSystemLoader

from tilewizard.core.validator import (
    TILE_PORTS,
    get_unassigned_output_ranges,
)


_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(os.path.abspath(_TEMPLATES_DIR)),
        keep_trailing_newline=True,
    )


# ── Connection signal string ──────────────────────────────────────────────────

def _signal_str(tile_port: str, hi, lo) -> str:
    """Return the signal expression for a connection, e.g. 'csr_in[3:0]'."""
    width = TILE_PORTS[tile_port]
    if width == 1:
        return tile_port
    if hi is None:
        return tile_port
    if hi == lo:
        return f"{tile_port}[{hi}]"
    if hi == width - 1 and lo == 0:
        return tile_port  # full bus — no slice needed
    return f"{tile_port}[{hi}:{lo}]"


# ── Wrapper RTL ───────────────────────────────────────────────────────────────

def generate_wrapper(cfg: Dict, parsed_ports: Dict, warnings: List[str]) -> str:
    """Return the wrapper Verilog source string."""
    env = _jinja_env()
    tmpl = env.get_template("wrapper_template.j2")

    # Build connection list (only mapped ports)
    connections = []
    for ip_port, (tile_port, hi, lo) in parsed_ports.items():
        if tile_port is None:
            continue
        sig = _signal_str(tile_port, hi, lo)
        connections.append({"port": ip_port, "signal": sig})

    # Build assign lines for unassigned output bits
    assign_lines = []

    # csr_out_we
    if not any(tp == "csr_out_we" for (tp, _, _) in parsed_ports.values()):
        assign_lines.append("assign csr_out_we    = 1'b1;    // no mapeado — TW-W03")

    # csr_in_re
    if not any(tp == "csr_in_re" for (tp, _, _) in parsed_ports.values()):
        assign_lines.append("assign csr_in_re     = 1'b0;    // no mapeado — TW-W04")

    # data_reg_c unassigned bits
    for (h, l) in get_unassigned_output_ranges(parsed_ports, "data_reg_c"):
        if h == l:
            assign_lines.append(f"assign data_reg_c[{h}]   = 1'b0;   // bit sin mapear — TW-W02")
        else:
            width = h - l + 1
            assign_lines.append(
                f"assign data_reg_c[{h}:{l}] = {width}'b0;  // bits sin mapear — TW-W02"
            )

    # csr_out unassigned bits
    for (h, l) in get_unassigned_output_ranges(parsed_ports, "csr_out"):
        if h == l:
            assign_lines.append(f"assign csr_out[{h}]   = 1'b0;   // bit sin mapear — TW-W02")
        else:
            width = h - l + 1
            assign_lines.append(
                f"assign csr_out[{h}:{l}] = {width}'b0;  // bits sin mapear — TW-W02"
            )

    return tmpl.render(
        tile_name=cfg["ip_tile_name"].strip(),
        top_module=cfg["top_module"].strip(),
        author=cfg["author"].strip(),
        date=date.today().isoformat(),
        version=cfg.get("version", "1.0.0"),
        connections=connections,
        unassigned_assigns=assign_lines,
    )


# ── tile_config.yaml ──────────────────────────────────────────────────────────

def generate_tile_config(cfg: Dict, parsed_ports: Dict) -> str:
    tile_name = cfg["ip_tile_name"].strip()
    author = cfg["author"].strip()
    top_wrapper = f"{tile_name}_wrapper"
    description = cfg.get("description", "").strip() or "# TODO: describe tu IP"

    # Build port mapping lines: "  ip_port → tile_signal"
    port_lines = []
    for ip_port, (tile_port, hi, lo) in parsed_ports.items():
        if tile_port is None:
            port_lines.append(f"  {ip_port} → (sin mapeo)")
        else:
            sig = _signal_str(tile_port, hi, lo)
            port_lines.append(f"  {sig} → {ip_port}")
    ports_block = "\n".join(port_lines) if port_lines else "  (sin puertos mapeados)"

    return (
        f'tile_name: "{tile_name}"\n'
        f'tile_author: "{author}"\n'
        f'top_module: "{top_wrapper}"\n'
        f"description: |\n"
        f"  {description}\n"
        f"ports: |\n"
        f"{ports_block}\n"
        f"usage_guide: |\n"
        f"  # TODO: Describe cómo usar este tile\n"
        f"tb_description: |\n"
        f"  # TODO: Describe las pruebas implementadas\n"
    )


# ── run_config.yaml ───────────────────────────────────────────────────────────

def generate_run_config() -> str:
    return (
        'run_author: ""\n'
        'objective: ""\n'
        'tags: ""\n'
        "main_change: |\n"
        "notes: |\n"
    )


# ── README.md ─────────────────────────────────────────────────────────────────

def generate_readme(cfg: Dict) -> str:
    tile_name = cfg["ip_tile_name"].strip()
    top_module = cfg["top_module"].strip()
    author = cfg["author"].strip()
    description = cfg.get("description", "").strip()
    version = cfg.get("version", "1.0.0")
    today = date.today().isoformat()
    desc_str = description if description else "_TODO: agrega una descripción._"

    lines = []
    lines.append(f"# {tile_name}\n")
    lines.append(f"\n**Generado por TileWizard V1** — {today}\n")
    lines.append(f"\n| Campo | Valor |")
    lines.append(f"\n|-------|-------|")
    lines.append(f"\n| Tile | `{tile_name}` |")
    lines.append(f"\n| Wrapper top | `{tile_name}_wrapper` |")
    lines.append(f"\n| IP top module | `{top_module}` |")
    lines.append(f"\n| Autor | {author} |")
    lines.append(f"\n| Versión | {version} |")
    lines.append(f"\n\n## Descripción\n\n{desc_str}\n")
    lines.append("\n## Interfaz SemiCoLab\n")
    lines.append("\nLos puertos del wrapper son fijos para todos los tiles SemiCoLab.")
    lines.append(" La interfaz Python los accede por nombre.")
    lines.append("\n\n### Puertos principales\n")
    lines.append("\n| Puerto | Dir | Bits | Descripción |")
    lines.append("\n|--------|-----|------|-------------|")
    lines.append("\n| `clk` | input | 1 | Reloj del sistema |")
    lines.append("\n| `arst_n` | input | 1 | Reset asíncrono activo en bajo |")
    lines.append("\n| `csr_in` | input | 16 | Registro de control de entrada (ver detalle) |")
    lines.append("\n| `data_reg_a` | input | 32 | Registro de datos de entrada A |")
    lines.append("\n| `data_reg_b` | input | 32 | Registro de datos de entrada B |")
    lines.append("\n| `data_reg_c` | output | 32 | Registro de datos de salida |")
    lines.append("\n| `csr_out` | output | 16 | Registro de control de salida (ver detalle) |")
    lines.append("\n| `csr_in_re` | output | 1 | Pulso: el tile leyó `csr_in` |")
    lines.append("\n| `csr_out_we` | output | 1 | Pulso: el tile escribió `csr_out` |")
    lines.append("\n\n### `csr_in[15:0]` — detalle de bits (entrada)\n")
    lines.append("\n| Bits | Tipo | Comportamiento |")
    lines.append("\n|------|------|----------------|")
    lines.append("\n| `[15:12]` | **Single pulse** | Se activan un ciclo y se limpian solos. Ideal para disparar instrucciones o comandos desde Python. |")
    lines.append("\n| `[11:4]` | **Stable** | Mantienen su valor hasta que Python los cambie. Ideal para condiciones, modos o parámetros. |")
    lines.append("\n| `[3:0]` | **Clear on read** | Se limpian cuando el circuito lee el dato. Útiles para órdenes que confirman su propia recepción. |")
    lines.append("\n\n### `csr_out[15:0]` — detalle de bits (salida)\n")
    lines.append("\n| Bits | Tipo | Comportamiento |")
    lines.append("\n|------|------|----------------|")
    lines.append("\n| `[15:4]` | **Stable** | Mantienen su valor. Útiles para flags de estado o valores que Python lee periódicamente. |")
    lines.append("\n| `[3:0]` | **Clear on read** | Se limpian cuando Python lee el dato. Útiles como indicadores de evento de una sola lectura. |")
    lines.append("\n\n## Uso\n\n_TODO: describe cómo usar este tile en una plataforma SemiCoLab._\n")
    return "".join(lines)


# ── port_map.md ───────────────────────────────────────────────────────────────

def generate_port_map(cfg: Dict, parsed_ports: Dict) -> str:
    tile_name = cfg["ip_tile_name"].strip()
    lines = [
        f"# Port Map — {tile_name}\n\n",
        "| Puerto IP | Puerto Tile | Slice |\n",
        "|-----------|-------------|-------|\n",
    ]
    for ip_port, (tile_port, hi, lo) in parsed_ports.items():
        if tile_port is None:
            lines.append(f"| `{ip_port}` | _(sin mapeo)_ | — |\n")
        else:
            sig = _signal_str(tile_port, hi, lo)
            lines.append(f"| `{ip_port}` | `{tile_port}` | `{sig}` |\n")
    return "".join(lines)


# ── Output folder builder ─────────────────────────────────────────────────────

def build_output(cfg: Dict, parsed_ports: Dict, v_files: List[str], warnings: List[str], cwd: str) -> List[str]:
    """Create the full output directory tree. Returns list of generated file paths."""
    tile_name = cfg["ip_tile_name"].strip()
    root = os.path.join(cwd, tile_name)

    # Paths
    out_rtl     = os.path.join(root, "output", "rtl")
    out_docs    = os.path.join(root, "output", "docs")
    vf_rtl      = os.path.join(root, "veriflow", "src", "rtl")
    vf_tb       = os.path.join(root, "veriflow", "src", "tb")
    vf_root     = os.path.join(root, "veriflow")

    for d in [out_rtl, out_docs, vf_rtl, vf_tb]:
        os.makedirs(d, exist_ok=True)

    generated = []

    # ── Copy source .v files ─────────────────────────────────────────────────
    for src in v_files:
        fname = os.path.basename(src)
        for dest_dir in [out_rtl, vf_rtl]:
            shutil.copy2(src, os.path.join(dest_dir, fname))

    # ── Wrapper RTL ──────────────────────────────────────────────────────────
    wrapper_src = generate_wrapper(cfg, parsed_ports, warnings)
    wrapper_fname = f"{tile_name}_wrapper.v"

    for dest_dir in [out_rtl, vf_rtl]:
        p = os.path.join(dest_dir, wrapper_fname)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(wrapper_src)
    generated.append(os.path.join("output/rtl", wrapper_fname))
    generated.append(os.path.join("veriflow/src/rtl", wrapper_fname))

    # ── tile_config.yaml ─────────────────────────────────────────────────────
    p = os.path.join(vf_root, "tile_config.yaml")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(generate_tile_config(cfg, parsed_ports))
    generated.append("veriflow/tile_config.yaml")

    # ── run_config.yaml ──────────────────────────────────────────────────────
    p = os.path.join(vf_root, "run_config.yaml")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(generate_run_config())
    generated.append("veriflow/run_config.yaml")

    # ── tb_tile.v ────────────────────────────────────────────────────────────
    from tilewizard.core.tb_generator import generate_tb
    tb_src = generate_tb(cfg, parsed_ports)
    p = os.path.join(vf_tb, "tb_tile.v")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(tb_src)
    generated.append("veriflow/src/tb/tb_tile.v")

    # ── README.md ─────────────────────────────────────────────────────────────
    p = os.path.join(out_docs, "README.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(generate_readme(cfg))
    generated.append("output/docs/README.md")

    # ── port_map.md ──────────────────────────────────────────────────────────
    p = os.path.join(out_docs, "port_map.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(generate_port_map(cfg, parsed_ports))
    generated.append("output/docs/port_map.md")

    return generated
