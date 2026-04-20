"""
tilewizard init <project_name>
Creates the project folder and src/ with .gitkeep.
"""

import os
import sys


def cmd_init(project_name: str) -> None:
    if os.path.exists(project_name):
        print(f"[TW-E00] La carpeta '{project_name}' ya existe. Elige otro nombre.")
        sys.exit(1)

    src_dir = os.path.join(project_name, "src")
    os.makedirs(src_dir)

    gitkeep = os.path.join(src_dir, ".gitkeep")
    open(gitkeep, "w").close()

    print(f"✓ Proyecto inicializado: {project_name}/")
    print(f"  └── src/  (coloca tus archivos .v aquí)")
    print()
    print("Siguientes pasos:")
    print(f"  1. Copia tu IP RTL (.v) dentro de  {project_name}/src/")
    print(f"  2. cd {project_name}")
    print(f"  3. tilewizard parse --top <top_module>")
    print(f"  4. Edita ip_config.yaml y completa el mapeo de puertos")
    print(f"  5. tilewizard wrap")
