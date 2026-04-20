"""
tilewizard parse --top <top_module>
Reads src/<top_module>.v, extracts ports, writes ip_config.yaml.
"""

import os
import sys

from tilewizard.core.port_parser import extract_ports


_YAML_HEADER = """\
# ─────────────────────────────────────────────
# TileWizard — ip_config.yaml
# Generado por: tilewizard parse
# ─────────────────────────────────────────────

ip_tile_name: {name}      # auto — del nombre del top
top_module:   {name}      # auto — del argumento --top
description:  ""          # TODO: describe tu IP
author:       ""          # TODO: tu nombre
version:      "1.0.0"

# ─────────────────────────────────────────────
# MAPEO DE PUERTOS
# Formato: <puerto_ip>: <puerto_tile>[slice_opcional]
#
# ENTRADAS disponibles:
#   clk                  — reloj del sistema
#   arst_n               — reset asíncrono activo en bajo
#   data_reg_a[31:0]     — registro de datos de entrada A (32 bits)
#   data_reg_b[31:0]     — registro de datos de entrada B (32 bits)
#
#   csr_in[15:0]         — registro de control de entrada, 3 zonas:
#     csr_in[15:12]      — SINGLE PULSE: se activan un ciclo y se limpian solos
#                          ideal para disparar instrucciones o comandos
#     csr_in[11:4]       — STABLE: mantienen su valor hasta que Python los cambie
#                          ideal para condiciones, modos o parámetros
#     csr_in[3:0]        — CLEAR ON READ: se limpian cuando el circuito lee el dato
#                          ideal para órdenes que confirman recepción
#
# SALIDAS disponibles:
#   data_reg_c[31:0]     — registro de datos de salida (32 bits)
#   csr_in_re            — pulso que indica que el tile leyó csr_in
#   csr_out_we           — pulso que indica que el tile escribió csr_out
#
#   csr_out[15:0]        — registro de control de salida, 2 zonas:
#     csr_out[15:4]      — STABLE: flags o valores de salida, mantienen su valor
#     csr_out[3:0]       — CLEAR ON READ: indicadores que se limpian al ser leídos
#                          por la interfaz Python
# ─────────────────────────────────────────────

ports:
"""


def cmd_parse(top_module: str) -> None:
    # ── locate src/ ──────────────────────────────────────────────────────────
    src_dir = os.path.join(os.getcwd(), "src")
    if not os.path.isdir(src_dir):
        print("[TW-E00] Carpeta 'src/' no encontrada en el directorio actual.")
        sys.exit(1)

    rtl_path = os.path.join(src_dir, f"{top_module}.v")
    if not os.path.isfile(rtl_path):
        print(f"[TW-E00] Archivo '{top_module}.v' no encontrado en src/.")
        sys.exit(1)

    with open(rtl_path, "r", encoding="utf-8") as fh:
        source = fh.read()

    # ── extract ports ─────────────────────────────────────────────────────────
    try:
        ports = extract_ports(source, top_module)
    except ValueError as exc:
        print(f"[TW-E00] {exc}")
        sys.exit(1)

    if not ports:
        print(f"[TW-E00] No se encontraron puertos en el módulo '{top_module}'.")
        sys.exit(1)

    # ── build ip_config.yaml ─────────────────────────────────────────────────
    lines = [_YAML_HEADER.format(name=top_module)]
    for port in ports:
        lines.append(f"  {port}:   # → mapear a puerto del tile\n")

    yaml_text = "".join(lines)

    out_path = os.path.join(os.getcwd(), "ip_config.yaml")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(yaml_text)

    print(f"✓ ip_config.yaml generado con {len(ports)} puerto(s):")
    for p in ports:
        print(f"    {p}:")
    print()
    print("Siguientes pasos:")
    print("  1. Edita ip_config.yaml: completa description, author y el mapeo de puertos")
    print("  2. tilewizard wrap")
