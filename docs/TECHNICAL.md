# TileWizard V1 — Technical Design Document

SemiCoLab
Version: 1.0.0 | Status: Released

---

## Table of contents

1. [Repository structure](#1-repository-structure)
2. [Architecture overview](#2-architecture-overview)
3. [Module reference](#3-module-reference)
4. [Data flow](#4-data-flow)
5. [Key design decisions](#5-key-design-decisions)
6. [Test suite](#6-test-suite)
7. [Dependencies](#7-dependencies)
8. [Integration with VeriFlow](#8-integration-with-veriflow)

---

## 1. Repository structure

```
tilewizard/
├── tilewizard/                  ← Python package
│   ├── __init__.py              ← version string
│   ├── cli.py                   ← argparse entry point
│   ├── commands/
│   │   ├── init_cmd.py          ← tilewizard init
│   │   ├── parse_cmd.py         ← tilewizard parse
│   │   └── wrap_cmd.py          ← tilewizard wrap
│   ├── core/
│   │   ├── port_parser.py       ← Verilog port extraction
│   │   ├── validator.py         ← config + mapping validation
│   │   ├── generator.py         ← RTL + file generation
│   │   └── tb_generator.py      ← testbench generation
│   └── templates/
│       └── wrapper_template.j2  ← Jinja2 wrapper RTL template
├── tests/
│   ├── test_tilewizard.py       ← integration test suite
│   └── runner.py                ← test entry point
├── examples/
│   └── counter_example/         ← minimal working example
├── docs/
│   ├── README.md                ← GitHub landing page
│   ├── MANUAL.md                ← user guide
│   ├── SPEC.md                  ← behavioral specification
│   └── TECHNICAL.md             ← this document
├── setup.py
└── requirements.txt
```

---

## 2. Architecture overview

TileWizard is organized as a layered pipeline. Each layer has a single responsibility and communicates through plain Python data structures.

```
CLI (cli.py)
    │
    ├── commands/init_cmd.py     ← filesystem operations only
    │
    ├── commands/parse_cmd.py   ← orchestrates port_parser → writes YAML
    │
    └── commands/wrap_cmd.py    ← orchestrates validator → generator
            │
            ├── core/validator.py
            │       load_and_validate_config()
            │       validate_src_and_top()
            │       validate_port_map()   ──► parsed_ports dict
            │
            └── core/generator.py
                    build_output()
                        ├── generate_wrapper()     uses Jinja2
                        ├── generate_tile_config() string building
                        ├── generate_run_config()  string building
                        ├── generate_readme()      string building
                        ├── generate_port_map()    string building
                        └── tb_generator.generate_tb()  string building
```

---

## 3. Module reference

### 3.1 `cli.py`

Entry point registered by `setup.py` as the `tilewizard` console script. Uses `argparse` with three subparsers: `init`, `parse`, `wrap`. Dispatches to the corresponding command module. No business logic.

### 3.2 `commands/init_cmd.py`

`cmd_init(project_name)` — Creates the folder tree and `.gitkeep`. Pure filesystem operations. Exits with code 1 if the folder already exists.

### 3.3 `commands/parse_cmd.py`

`cmd_parse(top_module)` — Locates `src/<top_module>.v`, calls `port_parser.extract_ports()`, and writes `ip_config.yaml`. The YAML is a hand-built string (not serialized via PyYAML) to preserve the comment block that documents the bit zones.

### 3.4 `commands/wrap_cmd.py`

`cmd_wrap()` — Orchestration only. Calls `validator` functions in sequence, then calls `generator.build_output()`. Prints warnings and the final summary.

### 3.5 `core/port_parser.py`

#### `extract_ports(verilog_source, top_module) → List[str]`

Extracts port names from a Verilog module declaration using regex.

**Approach:**
1. Locate the module header with a `re.DOTALL` pattern that captures everything between the outer parentheses of `module <top_module> (...)`.
2. Apply `_PORT_RE` to the header body to find port declarations.
3. If no ports found in the header (old-style non-ANSI), fall back to scanning the full module body.

**`_PORT_RE` pattern** matches:
```
\b(input|output|inout)\b   ← direction
(?:\s+(?:wire|reg|logic))?  ← optional net type
(?:\s*\[[\w\s:+-]+\])?      ← optional bus width
\s+([\w]+)                  ← port name  (group 2)
\s*[,;)\n]                  ← terminator
```

Only the port name (group 2) is captured. Direction and width are discarded.

### 3.6 `core/validator.py`

Three public functions called in sequence by `wrap_cmd`:

#### `load_and_validate_config(cwd) → Dict`

- Checks for `ip_config.yaml` existence (`TW-E01`).
- Parses with `yaml.safe_load` (`TW-E02`).
- Validates required fields are non-empty (`TW-E03`).

#### `validate_src_and_top(cfg, cwd) → List[str]`

- Checks `src/` exists and contains `.v` files (`TW-E04`).
- Searches each `.v` file for `module <top_module>` declaration (`TW-E05`).
- Returns the list of `.v` file paths.

#### `validate_port_map(cfg) → Tuple[Dict, List[str]]`

- Iterates over each entry in `ports:`.
- Parses the map-to expression with `_MAP_RE`: `^(\w+)(?:\[(\d+)(?::(\d+))?\])?$`.
- Validates tile port name (`TW-E08`), slice range (`TW-E07`), and bit conflicts (`TW-E06`).
- Tracks assigned bits per tile port in `used_bits: Dict[str, set]`.
- Collects all warnings (`TW-W01` through `TW-W05`).
- Returns `parsed_ports: Dict[ip_port → (tile_port, hi, lo)]` and the warning list.

**`parsed_ports` structure:**
```python
{
    "clk":      ("clk",        None, None),   # scalar, no slice
    "data_in":  ("data_reg_a", 31,   0   ),   # full bus
    "ctrl":     ("csr_in",     3,    0   ),   # partial slice
    "enable":   ("csr_in",     4,    4   ),   # single bit
    "unmapped": (None,         None, None),   # TW-W01
}
```

#### Helper: `get_unassigned_output_ranges(parsed_ports, tile_port) → List[Tuple[int,int]]`

Computes the complement of assigned bits for a given output port. Returns a list of `(hi, lo)` contiguous ranges. Used by `generator.py` to emit `assign` statements only for the free bit ranges.

#### Helper: `_bits_to_ranges(bits) → List[Tuple[int,int]]`

Converts a sorted list of integers to a list of contiguous `(hi, lo)` ranges. Used internally for both warnings and unassigned-assign generation.

### 3.7 `core/generator.py`

#### `build_output(cfg, parsed_ports, v_files, warnings, cwd) → List[str]`

Top-level orchestrator for file generation. Creates the full directory tree and calls all generation functions. Returns a list of generated file paths (relative to the tile root) for the summary.

#### `generate_wrapper(cfg, parsed_ports, warnings) → str`

Renders `wrapper_template.j2` via Jinja2. Builds two lists before rendering:

- `connections`: `[{port: ip_port, signal: tile_signal_str}]` for all mapped ports.
- `unassigned_assigns`: `assign` statements for `csr_out_we`, `csr_in_re`, and unassigned output bus bits.

#### `_signal_str(tile_port, hi, lo) → str`

Converts a `(tile_port, hi, lo)` tuple to the Verilog signal expression used in the instantiation:

| Input | Output |
|-------|--------|
| `("clk", None, None)` | `"clk"` |
| `("data_reg_a", 31, 0)` | `"data_reg_a"` (full bus — no slice) |
| `("csr_in", 3, 0)` | `"csr_in[3:0]"` |
| `("csr_in", 4, 4)` | `"csr_in[4]"` |

#### `generate_tile_config(cfg, parsed_ports) → str`

Builds `tile_config.yaml` as a plain string. The `ports` block lists one line per mapped IP port: `<tile_signal> → <ip_port>` (SemiCoLab interface on the left, IP port on the right).

#### Other generation functions

`generate_run_config()`, `generate_readme(cfg)`, `generate_port_map(cfg, parsed_ports)` — pure string building, no external dependencies.

### 3.8 `core/tb_generator.py`

#### `generate_tb(cfg, parsed_ports) → str`

Builds `tb_tile.v` as a string concatenation of a fixed header (`_TB_HEADER`), a generated stimulus block, and a fixed footer (`_TB_FOOTER`).

The stimulus block iterates `parsed_ports` and emits lines according to the mapping target:
- Write calls (`write_data_reg_a`, `write_data_reg_b`, `write_csr_in`) for IP inputs.
- `$display` calls for IP outputs.
- A `@(posedge clk);` separator between writes and reads.
- A commented-out `write_data_reg_b` line if `data_reg_b` is unmapped.

### 3.9 `templates/wrapper_template.j2`

Jinja2 template for the wrapper RTL. Uses whitespace control (`{%-`, `-%}`) to avoid blank lines between port connections. Two blocks:

- `u_{{ top_module }}` instantiation loop over `connections`.
- Conditional `unassigned_assigns` section, only rendered if the list is non-empty.

---

## 4. Data flow

```
ip_config.yaml
      │
      ▼
load_and_validate_config() ──► cfg: Dict
      │
      ▼
validate_src_and_top(cfg) ──► v_files: List[str]
      │
      ▼
validate_port_map(cfg) ──────► parsed_ports: Dict[str, Tuple]
                         ────► warnings: List[str]
      │
      ▼
build_output(cfg, parsed_ports, v_files, warnings)
      │
      ├── generate_wrapper(cfg, parsed_ports)
      │       └── Jinja2 render → wrapper_template.j2
      │
      ├── generate_tile_config(cfg, parsed_ports)
      ├── generate_run_config()
      ├── generate_tb(cfg, parsed_ports)
      ├── generate_readme(cfg)
      └── generate_port_map(cfg, parsed_ports)
```

---

## 5. Key design decisions

### Regex-based port parsing over a full Verilog parser

TileWizard targets Verilog 2001 ANSI-style module declarations, which is the format used throughout the SemiCoLab ecosystem. A full parser (e.g., pyverilog) would add a heavy dependency and complexity for a task that only needs port names. The regex approach is lightweight and sufficient for the intended scope.

Limitation: does not handle parameterized port widths, generate blocks, or SystemVerilog syntax. These are out of scope for V1.

### Manual mapping over automatic mapping

Port mapping is intentionally left to the user. Automatic heuristics based on port name or width would produce plausible but potentially incorrect connections — in hardware, a silently wrong mapping compiles without errors and may only surface in simulation or, worse, in silicon. The `ip_config.yaml` comment block provides enough context (bit zones, available ports) for the user to make informed decisions.

### String building over PyYAML serialization for YAML output

Generated YAML files (`ip_config.yaml`, `tile_config.yaml`) are built as plain strings rather than serialized through `yaml.dump()`. This preserves the comment blocks that document the bit zones, which are the primary documentation aid for the user. PyYAML does not support round-trip comment preservation.

### Jinja2 only for the wrapper RTL

The wrapper is the only file complex enough to benefit from a template engine — it has a conditional section and a variable-length loop. All other files are simple enough to be built with f-strings.

### Separate `output/` and `veriflow/` trees

The output is split into two parallel trees: `output/` for the tile deliverable (RTL + docs), and `veriflow/` for the VeriFlow integration (same RTL + testbench scaffold + config files). This allows TileWizard output to be handed off to VeriFlow without any manual file reorganization.

---

## 6. Test suite

`tests/test_tilewizard.py` is a standalone integration suite with no external test framework. It runs TileWizard commands as subprocesses via `python -m tilewizard.cli`, using `tempfile.mkdtemp()` for isolated environments that are cleaned up after each test.

Each test is a function registered with a `test(name, fn)` helper that catches `AssertionError` and prints `PASS` / `FAIL` with color codes.

**Coverage — 17 tests:**

| Group | Tests |
|-------|-------|
| `init` | Creates structure correctly; fails if folder exists |
| `parse` | Extracts ANSI ports; correct YAML fields; missing `.v` error; module not found error |
| `wrap` | Full output structure; wrapper connections; unassigned assigns; `tile_config` fields; `tb_tile.v` structure; `tb_tile.v` pre-stimulus; `TW-E03`; `TW-E05`; `TW-E06`; `TW-E08`; `TW-W03` |

Run with:
```bash
python tests/test_tilewizard.py
# or
python tests/runner.py
```

---

## 7. Dependencies

| Package | Version | Usage |
|---------|---------|-------|
| PyYAML | ≥ 6.0 | Parsing `ip_config.yaml` in `wrap` |
| Jinja2 | ≥ 3.1 | Rendering `wrapper_template.j2` |

Standard library only: `os`, `shutil`, `re`, `sys`, `argparse`, `tempfile`, `subprocess`, `datetime`.

No test framework dependency — the suite uses only `subprocess` and `tempfile`.

---

## 8. Integration with VeriFlow

TileWizard's `veriflow/` output is designed to match the directory layout expected by VeriFlow:

```
veriflow/
├── tile_config.yaml    ← read by VeriFlow init
├── run_config.yaml     ← read by VeriFlow run
└── src/
    ├── rtl/            ← all .v files including wrapper
    └── tb/
        └── tb_tile.v   ← VeriFlow replaces MODULE_INSTANTIATION marker
```

VeriFlow injects the DUT instantiation at the `/* MODULE_INSTANTIATION */` marker in `tb_tile.v`. The `top_module` field in `tile_config.yaml` points to `<ip_tile_name>_wrapper`, which is the SemiCoLab-compatible entry point that VeriFlow instantiates.

The `ports` field in `tile_config.yaml` is used by VeriFlow for documentation only — it does not affect simulation or synthesis behavior.
