"""
port_parser.py — Verilog port extraction using regex.

Handles ANSI-style module declarations (the most common in modern Verilog):
    input  wire [N:0] port_name,
    output reg        port_name,
    input             port_name
"""

import re
from typing import List


# Match ANSI-style port declarations inside a module header
_PORT_RE = re.compile(
    r"\b(input|output|inout)\b"     # direction
    r"(?:\s+(?:wire|reg|logic))?"   # optional net/var type
    r"(?:\s*\[[\w\s:+-]+\])?"       # optional bus width
    r"\s+([\w]+)"                   # port name
    r"\s*[,;)\n]",                  # terminator
    re.IGNORECASE,
)

# Locate module declaration header (everything up to the closing parenthesis + semicolon)
_MODULE_HEADER_RE = re.compile(
    r"\bmodule\s+({top})\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;",
    re.DOTALL | re.IGNORECASE,
)


def extract_ports(verilog_source: str, top_module: str) -> List[str]:
    """Return a list of port names from *top_module* in *verilog_source*.

    Raises ValueError if the module declaration is not found.
    """
    pattern = re.compile(
        r"\bmodule\s+" + re.escape(top_module) + r"\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(verilog_source)
    if not m:
        raise ValueError(f"Módulo '{top_module}' no encontrado en el archivo.")

    header_body = m.group(1)  # content between the outer parentheses

    ports = []
    for pm in _PORT_RE.finditer(header_body):
        port_name = pm.group(2)
        if port_name not in ports:
            ports.append(port_name)

    # Fallback: bare port list (old-style without direction inside header)
    if not ports:
        # Some old-style modules just have comma-separated names in the header
        # and declare directions in the body. We do a best-effort scan of the
        # full source within that module.
        module_body_pat = re.compile(
            r"\bmodule\s+" + re.escape(top_module) + r"\b.*?endmodule",
            re.DOTALL | re.IGNORECASE,
        )
        bm = module_body_pat.search(verilog_source)
        if bm:
            for pm in _PORT_RE.finditer(bm.group(0)):
                port_name = pm.group(2)
                if port_name not in ports:
                    ports.append(port_name)

    return ports
