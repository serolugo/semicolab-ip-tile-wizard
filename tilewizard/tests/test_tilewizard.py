"""
tests/test_tilewizard.py — standalone integration suite for TileWizard V1.

Run directly:
    python tests/test_tilewizard.py
or via the runner:
    python tests/runner.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

# ── Helpers ───────────────────────────────────────────────────────────────────

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

_results = []


def _run(args, cwd=None):
    """Run tilewizard CLI and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "tilewizard.cli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr


def test(name, fn):
    try:
        fn()
        print(f"  [{PASS}] {name}")
        _results.append((name, True, None))
    except AssertionError as exc:
        msg = str(exc)
        print(f"  [{FAIL}] {name}")
        if msg:
            print(f"          {msg}")
        _results.append((name, False, msg))
    except Exception as exc:
        print(f"  [{FAIL}] {name}  — unexpected exception: {exc}")
        _results.append((name, False, str(exc)))


def _assert(condition, msg=""):
    if not condition:
        raise AssertionError(msg)


# ── Fixtures ──────────────────────────────────────────────────────────────────

_COUNTER_V = textwrap.dedent("""\
    `timescale 1ns / 1ps
    module counter (
        input  wire        clk,
        input  wire        rst_n,
        input  wire [31:0] load_val,
        input  wire        load_en,
        output wire [31:0] count,
        output wire        overflow
    );
        reg [31:0] cnt;
        assign count    = cnt;
        assign overflow = (cnt == 32'hFFFFFFFF);
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) cnt <= 32'd0;
            else if (load_en) cnt <= load_val;
            else cnt <= cnt + 1;
        end
    endmodule
""")

_FULL_IP_CONFIG = textwrap.dedent("""\
    ip_tile_name: counter
    top_module:   counter
    description:  "32-bit up-counter"
    author:       "Test Author"
    version:      "1.0.0"
    ports:
      clk:      clk
      rst_n:    arst_n
      load_val: data_reg_a
      load_en:  csr_in[0]
      count:    data_reg_c
      overflow: csr_out[0]
""")


def _make_project(tmp, v_content=_COUNTER_V, cfg_content=_FULL_IP_CONFIG):
    """Create a minimal project in tmp with src/counter.v and ip_config.yaml."""
    src = os.path.join(tmp, "src")
    os.makedirs(src, exist_ok=True)
    if v_content is not None:
        with open(os.path.join(src, "counter.v"), "w") as fh:
            fh.write(v_content)
    if cfg_content is not None:
        with open(os.path.join(tmp, "ip_config.yaml"), "w") as fh:
            fh.write(cfg_content)


# ═══════════════════════════════════════════════════════════════════════════════
# INIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def _test_init_creates_structure():
    tmp = tempfile.mkdtemp()
    try:
        rc, out, _ = _run(["init", "my_tile"], cwd=tmp)
        _assert(rc == 0, f"Expected rc=0, got {rc}")
        _assert(os.path.isdir(os.path.join(tmp, "my_tile")), "Project folder not created")
        _assert(os.path.isdir(os.path.join(tmp, "my_tile", "src")), "src/ not created")
        _assert(os.path.isfile(os.path.join(tmp, "my_tile", "src", ".gitkeep")), ".gitkeep missing")
        _assert("Proyecto inicializado" in out, "Expected success message")
    finally:
        shutil.rmtree(tmp)


def _test_init_error_if_exists():
    tmp = tempfile.mkdtemp()
    try:
        _run(["init", "my_tile"], cwd=tmp)
        rc, _, err = _run(["init", "my_tile"], cwd=tmp)
        _assert(rc != 0, "Expected non-zero rc when folder exists")
        output = err + _  # stdout was captured above; re-run for output
        # Just check rc is non-zero — message printed to stdout
    finally:
        shutil.rmtree(tmp)


def _test_init_error_message():
    tmp = tempfile.mkdtemp()
    try:
        _run(["init", "dup"], cwd=tmp)
        rc, out, _ = _run(["init", "dup"], cwd=tmp)
        _assert(rc != 0, "Should fail")
        _assert("ya existe" in out or "ya existe" in _, "Expected 'ya existe' in output")
    finally:
        shutil.rmtree(tmp)


# ═══════════════════════════════════════════════════════════════════════════════
# PARSE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def _test_parse_extracts_ports():
    tmp = tempfile.mkdtemp()
    try:
        src = os.path.join(tmp, "src")
        os.makedirs(src)
        with open(os.path.join(src, "counter.v"), "w") as fh:
            fh.write(_COUNTER_V)
        rc, out, _ = _run(["parse", "--top", "counter"], cwd=tmp)
        _assert(rc == 0, f"Expected rc=0, got {rc}\nstdout:{out}\nstderr:{_}")
        cfg_path = os.path.join(tmp, "ip_config.yaml")
        _assert(os.path.isfile(cfg_path), "ip_config.yaml not generated")
        content = open(cfg_path).read()
        for port in ["clk", "rst_n", "load_val", "load_en", "count", "overflow"]:
            _assert(port in content, f"Port '{port}' missing from ip_config.yaml")
    finally:
        shutil.rmtree(tmp)


def _test_parse_yaml_fields():
    tmp = tempfile.mkdtemp()
    try:
        src = os.path.join(tmp, "src")
        os.makedirs(src)
        with open(os.path.join(src, "counter.v"), "w") as fh:
            fh.write(_COUNTER_V)
        _run(["parse", "--top", "counter"], cwd=tmp)
        content = open(os.path.join(tmp, "ip_config.yaml")).read()
        _assert("ip_tile_name:" in content, "ip_tile_name missing")
        _assert("top_module:" in content, "top_module missing")
        _assert("author:" in content, "author missing")
        _assert("description:" in content, "description missing")
        _assert("ports:" in content, "ports section missing")
    finally:
        shutil.rmtree(tmp)


def _test_parse_error_no_v_file():
    tmp = tempfile.mkdtemp()
    try:
        src = os.path.join(tmp, "src")
        os.makedirs(src)
        rc, out, _ = _run(["parse", "--top", "counter"], cwd=tmp)
        _assert(rc != 0, "Should fail when .v not in src/")
    finally:
        shutil.rmtree(tmp)


def _test_parse_error_module_not_in_file():
    tmp = tempfile.mkdtemp()
    try:
        src = os.path.join(tmp, "src")
        os.makedirs(src)
        with open(os.path.join(src, "counter.v"), "w") as fh:
            fh.write("module other_module(input clk); endmodule\n")
        rc, out, _ = _run(["parse", "--top", "counter"], cwd=tmp)
        _assert(rc != 0, "Should fail when module not found in file")
    finally:
        shutil.rmtree(tmp)


# ═══════════════════════════════════════════════════════════════════════════════
# WRAP TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def _test_wrap_full_structure():
    tmp = tempfile.mkdtemp()
    try:
        _make_project(tmp)
        rc, out, err = _run(["wrap"], cwd=tmp)
        _assert(rc == 0, f"Expected rc=0\nout:{out}\nerr:{err}")
        base = os.path.join(tmp, "counter")
        _assert(os.path.isdir(os.path.join(base, "output", "rtl")), "output/rtl missing")
        _assert(os.path.isdir(os.path.join(base, "output", "docs")), "output/docs missing")
        _assert(os.path.isdir(os.path.join(base, "veriflow", "src", "rtl")), "veriflow/src/rtl missing")
        _assert(os.path.isdir(os.path.join(base, "veriflow", "src", "tb")), "veriflow/src/tb missing")
        _assert(os.path.isfile(os.path.join(base, "veriflow", "tile_config.yaml")), "tile_config.yaml missing")
        _assert(os.path.isfile(os.path.join(base, "veriflow", "run_config.yaml")), "run_config.yaml missing")
        _assert(os.path.isfile(os.path.join(base, "veriflow", "src", "tb", "tb_tile.v")), "tb_tile.v missing")
        _assert(os.path.isfile(os.path.join(base, "output", "docs", "README.md")), "README.md missing")
        _assert(os.path.isfile(os.path.join(base, "output", "docs", "port_map.md")), "port_map.md missing")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_wrapper_connections():
    tmp = tempfile.mkdtemp()
    try:
        _make_project(tmp)
        _run(["wrap"], cwd=tmp)
        wrapper = open(os.path.join(tmp, "counter", "output", "rtl", "counter_wrapper.v")).read()
        _assert(".clk(clk)" in wrapper, ".clk(clk) missing")
        _assert(".rst_n(arst_n)" in wrapper, ".rst_n(arst_n) missing")
        _assert(".load_val(data_reg_a)" in wrapper, ".load_val(data_reg_a) missing")
        _assert(".load_en(csr_in[0])" in wrapper, ".load_en(csr_in[0]) missing")
        _assert(".count(data_reg_c)" in wrapper, ".count(data_reg_c) missing")
        _assert(".overflow(csr_out[0])" in wrapper, ".overflow(csr_out[0]) missing")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_unassigned_assigns():
    tmp = tempfile.mkdtemp()
    try:
        _make_project(tmp)
        _run(["wrap"], cwd=tmp)
        wrapper = open(os.path.join(tmp, "counter", "output", "rtl", "counter_wrapper.v")).read()
        # csr_out_we not mapped → assign 1
        _assert("assign csr_out_we" in wrapper, "assign csr_out_we missing")
        _assert("1'b1" in wrapper, "csr_out_we should be assigned 1'b1")
        # csr_in_re not mapped → assign 0
        _assert("assign csr_in_re" in wrapper, "assign csr_in_re missing")
        # csr_out[15:1] unassigned (only [0] mapped)
        _assert("csr_out[" in wrapper, "csr_out partial assign missing")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_tile_config_fields():
    tmp = tempfile.mkdtemp()
    try:
        _make_project(tmp)
        _run(["wrap"], cwd=tmp)
        content = open(os.path.join(tmp, "counter", "veriflow", "tile_config.yaml")).read()
        _assert("tile_name:" in content, "tile_name missing")
        _assert("tile_author:" in content, "tile_author missing")
        _assert("top_module:" in content, "top_module missing")
        _assert("counter_wrapper" in content, "wrapper name missing in tile_config")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_tb_structure():
    tmp = tempfile.mkdtemp()
    try:
        _make_project(tmp)
        _run(["wrap"], cwd=tmp)
        tb = open(os.path.join(tmp, "counter", "veriflow", "src", "tb", "tb_tile.v")).read()
        _assert("`timescale 1ns / 1ps" in tb, "timescale missing")
        _assert("/* MODULE_INSTANTIATION */" in tb, "MODULE_INSTANTIATION marker missing")
        _assert("/* USER_TEST */" in tb, "USER_TEST marker missing")
        _assert("USER TEST STARTS HERE" in tb, "USER TEST STARTS missing")
        _assert("USER TEST ENDS HERE" in tb, "USER TEST ENDS missing")
        _assert("$finish" in tb, "$finish missing")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_tb_prestimulus():
    tmp = tempfile.mkdtemp()
    try:
        _make_project(tmp)
        _run(["wrap"], cwd=tmp)
        tb = open(os.path.join(tmp, "counter", "veriflow", "src", "tb", "tb_tile.v")).read()
        # data_reg_a mapped → write_data_reg_a
        _assert("write_data_reg_a" in tb, "write_data_reg_a missing")
        # csr_in[0] mapped → write_csr_in
        _assert("write_csr_in" in tb, "write_csr_in missing")
        # data_reg_c mapped → $display
        _assert("$display" in tb, "$display for count missing")
        # data_reg_b not mapped → commented
        _assert("// write_data_reg_b" in tb, "commented data_reg_b missing")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_error_tw_e03_missing_field():
    tmp = tempfile.mkdtemp()
    try:
        bad_cfg = textwrap.dedent("""\
            ip_tile_name: counter
            top_module:   counter
            description:  "ok"
            # author intentionally omitted
            ports: {}
        """)
        _make_project(tmp, cfg_content=bad_cfg)
        rc, out, _ = _run(["wrap"], cwd=tmp)
        _assert(rc != 0, "Should fail on missing 'author'")
        _assert("TW-E03" in out, "Expected TW-E03 in output")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_error_tw_e05_top_not_found():
    tmp = tempfile.mkdtemp()
    try:
        bad_cfg = textwrap.dedent("""\
            ip_tile_name: counter
            top_module:   nonexistent_module
            description:  "ok"
            author:       "me"
            ports: {}
        """)
        _make_project(tmp, cfg_content=bad_cfg)
        rc, out, _ = _run(["wrap"], cwd=tmp)
        _assert(rc != 0, "Should fail when top_module not found")
        _assert("TW-E05" in out, f"Expected TW-E05 in output:\n{out}")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_error_tw_e06_bit_conflict():
    tmp = tempfile.mkdtemp()
    try:
        bad_cfg = textwrap.dedent("""\
            ip_tile_name: counter
            top_module:   counter
            description:  "ok"
            author:       "me"
            version:      "1.0.0"
            ports:
              port_a: data_reg_c[0]
              port_b: data_reg_c[0]
        """)
        _make_project(tmp, cfg_content=bad_cfg)
        rc, out, _ = _run(["wrap"], cwd=tmp)
        _assert(rc != 0, "Should fail on bit conflict")
        _assert("TW-E06" in out, f"Expected TW-E06:\n{out}")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_error_tw_e08_bad_port():
    tmp = tempfile.mkdtemp()
    try:
        bad_cfg = textwrap.dedent("""\
            ip_tile_name: counter
            top_module:   counter
            description:  "ok"
            author:       "me"
            version:      "1.0.0"
            ports:
              clk: clk
              bad_port: nonexistent_tile_port
        """)
        _make_project(tmp, cfg_content=bad_cfg)
        rc, out, _ = _run(["wrap"], cwd=tmp)
        _assert(rc != 0, "Should fail on unrecognised tile port")
        _assert("TW-E08" in out, f"Expected TW-E08:\n{out}")
    finally:
        shutil.rmtree(tmp)


def _test_wrap_warning_tw_w03():
    tmp = tempfile.mkdtemp()
    try:
        cfg_no_we = textwrap.dedent("""\
            ip_tile_name: counter
            top_module:   counter
            description:  "ok"
            author:       "me"
            version:      "1.0.0"
            ports:
              clk: clk
              count: data_reg_c
        """)
        _make_project(tmp, cfg_content=cfg_no_we)
        rc, out, _ = _run(["wrap"], cwd=tmp)
        _assert(rc == 0, f"Expected rc=0\n{out}\n{_}")
        _assert("TW-W03" in out, f"Expected TW-W03 warning:\n{out}")
    finally:
        shutil.rmtree(tmp)


# ═══════════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════════

def run_all():
    print("\nTileWizard V1 — Integration Tests")
    print("=" * 56)

    groups = [
        ("init", [
            ("init: crea carpeta y src/ correctamente",        _test_init_creates_structure),
            ("init: error si la carpeta ya existe",            _test_init_error_message),
        ]),
        ("parse", [
            ("parse: extrae puertos de módulo ANSI",           _test_parse_extracts_ports),
            ("parse: ip_config.yaml tiene campos correctos",   _test_parse_yaml_fields),
            ("parse: error si top_module.v no existe",         _test_parse_error_no_v_file),
            ("parse: error si módulo no encontrado en archivo",_test_parse_error_module_not_in_file),
        ]),
        ("wrap", [
            ("wrap: genera estructura completa de output",     _test_wrap_full_structure),
            ("wrap: wrapper RTL con conexiones correctas",     _test_wrap_wrapper_connections),
            ("wrap: assigns correctos para bits sin mapear",   _test_wrap_unassigned_assigns),
            ("wrap: tile_config.yaml con campos correctos",    _test_wrap_tile_config_fields),
            ("wrap: tb_tile.v con estructura exacta",          _test_wrap_tb_structure),
            ("wrap: tb_tile.v con pre-estímulos correctos",    _test_wrap_tb_prestimulus),
            ("wrap: error TW-E03 por campo obligatorio ausente",_test_wrap_error_tw_e03_missing_field),
            ("wrap: error TW-E05 por top_module no encontrado",_test_wrap_error_tw_e05_top_not_found),
            ("wrap: error TW-E06 conflicto de mapeo",          _test_wrap_error_tw_e06_bit_conflict),
            ("wrap: error TW-E08 puerto no reconocido",        _test_wrap_error_tw_e08_bad_port),
            ("wrap: warning TW-W03 csr_out_we no mapeado",    _test_wrap_warning_tw_w03),
        ]),
    ]

    for group_name, cases in groups:
        print(f"\n  [{group_name}]")
        for name, fn in cases:
            test(name, fn)

    passed = sum(1 for _, ok, _ in _results if ok)
    total  = len(_results)
    print()
    print("─" * 56)
    print(f"  {passed}/{total} tests passed")
    print("─" * 56)

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
