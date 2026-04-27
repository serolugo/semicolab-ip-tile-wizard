from setuptools import setup, find_packages

setup(
    name="tilewizard",
    version="1.0.0",
    description="SemiCoLab IP Tile Wizard V1 — wraps generic RTL into SemiCoLab tiles.",
    author="",
    package_dir={"": "tilewizard"},
    packages=find_packages("tilewizard"),
    include_package_data=True,
    package_data={
        "tilewizard": ["templates/*.j2", "templates/*.yaml"],
    },
    install_requires=[
        "PyYAML>=6.0",
        "Jinja2>=3.1",
    ],
    entry_points={
        "console_scripts": [
            "tilewizard=tilewizard.cli:main",
        ],
    },
    python_requires=">=3.10",
)
