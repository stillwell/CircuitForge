import os
import shutil
from setuptools import setup, find_packages

# Mirror the top-level images/ into the package so `pip install` ships them.
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "images")
DST = os.path.join(HERE, "circuitforge", "_resources")
if os.path.isdir(SRC):
    os.makedirs(DST, exist_ok=True)
    for fname in os.listdir(SRC):
        s = os.path.join(SRC, fname)
        d = os.path.join(DST, fname)
        if os.path.isfile(s) and (not os.path.exists(d) or
                                   os.path.getmtime(s) > os.path.getmtime(d)):
            shutil.copy2(s, d)

_readme = os.path.join(HERE, "README.md")
_long = open(_readme, encoding="utf-8").read() if os.path.exists(_readme) else ""

setup(
    name="circuitforge",
    version="0.1.0",
    description="Open-source EDA suite: schematic capture, SPICE simulation, PCB layout.",
    long_description=_long,
    long_description_content_type="text/markdown",
    author="Robert Andrew Stillwell",
    author_email="andrew.stillwell@enlightec.com",
    maintainer="Enlightec Ltd.",
    maintainer_email="andrew.stillwell@enlightec.com",
    url="https://www.enlightec.com",
    license="GPL-3.0-or-later",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "circuitforge": ["_resources/*.png", "libs/*.json",
                         "web/templates/*.html", "web/static/*"],
    },
    install_requires=[
        "numpy>=1.21",
        "scipy>=1.7",
        "matplotlib>=3.5",
        "pyparsing>=3.0",
    ],
    extras_require={
        "gui": ["PyQt5>=5.15"],
        "gui-pyside": ["PySide6>=6.4"],
    },
    entry_points={
        "console_scripts": [
            "circuitforge=circuitforge.cli:main",
        ],
        "gui_scripts": [
            "circuitforge-gui=circuitforge.app:run",
        ],
    },
    python_requires=">=3.8",
)
