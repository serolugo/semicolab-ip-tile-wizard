# SemiCoLab TileWizard V1

**TileWizard** is a CLI tool that wraps generic Verilog RTL into tiles compatible with the SemiCoLab multi-project ASIC platform.

---

## What it does

SemiCoLab tiles must expose a fixed 9-port interface. TileWizard automates the mechanical work of wrapping any IP into that interface — extracting ports, generating the wrapper RTL, testbench scaffold, and all configuration files expected by [VeriFlow](https://github.com/semicolab/veriflow).

```
Your IP RTL  ──►  tilewizard parse  ──►  ip_config.yaml  ──►  tilewizard wrap  ──►  SemiCoLab tile
```

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

Requires Python 3.10+, [PyYAML](https://pypi.org/project/PyYAML/) and [Jinja2](https://pypi.org/project/Jinja2/).

## Quick start

```bash
# 1 — Initialize project
tilewizard init my_ip

# 2 — Place your RTL
cp my_ip.v my_ip/src/

# 3 — Extract ports
cd my_ip
tilewizard parse --top my_ip

# 4 — Edit ip_config.yaml and fill in the port mapping

# 5 — Generate tile
tilewizard wrap
```

## SemiCoLab interface

Every generated tile exposes exactly these 9 ports:

| Port | Dir | Width | Description |
|------|-----|-------|-------------|
| `clk` | input | 1 | System clock |
| `arst_n` | input | 1 | Async reset, active low |
| `csr_in` | input | 16 | Control/status input register |
| `data_reg_a` | input | 32 | Data input register A |
| `data_reg_b` | input | 32 | Data input register B |
| `data_reg_c` | output | 32 | Data output register |
| `csr_out` | output | 16 | Control/status output register |
| `csr_in_re` | output | 1 | Pulse: tile read `csr_in` |
| `csr_out_we` | output | 1 | Pulse: tile wrote `csr_out` |

`csr_in` and `csr_out` are subdivided into bit zones with different behaviors — see [MANUAL.md](docs/MANUAL.md) for details.

## Output structure

```
<ip_tile_name>/
├── output/
│   ├── rtl/          ← IP source files + generated wrapper
│   └── docs/         ← README.md + port_map.md
└── veriflow/
    ├── tile_config.yaml
    ├── run_config.yaml
    └── src/
        ├── rtl/      ← same RTL, ready for VeriFlow
        └── tb/
            └── tb_tile.v
```

## Error and warning codes

| Code | Type | Description |
|------|------|-------------|
| `TW-E01` | Error | `ip_config.yaml` not found |
| `TW-E02` | Error | Invalid YAML syntax |
| `TW-E03` | Error | Required field missing |
| `TW-E04` | Error | `src/` empty or no `.v` files |
| `TW-E05` | Error | `top_module` not found in any `.v` |
| `TW-E06` | Error | Bit conflict in port mapping |
| `TW-E07` | Error | Invalid slice for tile port width |
| `TW-E08` | Error | Unrecognized tile port name |
| `TW-W01` | Warning | IP port without mapping — ignored |
| `TW-W02` | Warning | Unassigned output bits — auto `assign 0` |
| `TW-W03` | Warning | `csr_out_we` unmapped — auto `assign 1` |
| `TW-W04` | Warning | `csr_in_re` unmapped — auto `assign 0` |
| `TW-W05` | Warning | `data_reg_b` unmapped |

## Running tests

```bash
python tests/test_tilewizard.py
```

17 standalone integration tests, no external test framework required.

## Documentation

| Document | Description |
|----------|-------------|
| [MANUAL.md](docs/MANUAL.md) | Full user guide — commands, mapping, examples |
| [SPEC.md](docs/SPEC.md) | Interface specification and behavioral rules |
| [TECHNICAL.md](docs/TECHNICAL.md) | Architecture and implementation details |

## Related tools

- **VeriFlow** — verifies and documents SemiCoLab tiles

---

*SemiCoLab TileWizard V1*
