"""CircuitForge — open-source EDA suite (schematic + SPICE + PCB).

Copyright (C) 2026 Enlightec Ltd. <https://www.enlightec.com>
Author: Robert Andrew Stillwell <andrew.stillwell@enlightec.com>

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

__version__ = "0.1.0"
__copyright__ = "Copyright (C) 2026 Enlightec Ltd."
__author__ = "Robert Andrew Stillwell"
__email__ = "andrew.stillwell@enlightec.com"
__license__ = "GPL-3.0-or-later"
__url__ = "https://www.enlightec.com"

__all__ = ["core", "components", "simulation", "schematic", "pcb", "io", "gui"]


SHORT_NOTICE = (
    f"CircuitForge {__version__}  {__copyright__}\n"
    "This program comes with ABSOLUTELY NO WARRANTY; for details run with "
    "`--show-w'.\nThis is free software, and you are welcome to redistribute "
    "it under certain conditions; run with `--show-c' for details.\n"
    f"Author: {__author__} <{__email__}>  ·  {__url__}"
)


def show_w():
    """Return the warranty-disclaimer extract from the GNU GPL v3 (§ 15–17)."""
    return (
        "  15. Disclaimer of Warranty.\n\n"
        "  THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY\n"
        "APPLICABLE LAW.  EXCEPT WHEN OTHERWISE STATED IN WRITING THE COPYRIGHT\n"
        "HOLDERS AND/OR OTHER PARTIES PROVIDE THE PROGRAM \"AS IS\" WITHOUT\n"
        "WARRANTY OF ANY KIND, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT\n"
        "LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR\n"
        "A PARTICULAR PURPOSE.  THE ENTIRE RISK AS TO THE QUALITY AND\n"
        "PERFORMANCE OF THE PROGRAM IS WITH YOU.  SHOULD THE PROGRAM PROVE\n"
        "DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING, REPAIR OR\n"
        "CORRECTION.\n\n"
        "(See LICENSE §15–17 for the full text.)"
    )


def show_c():
    """Return a one-paragraph summary of the redistribution conditions."""
    return (
        "CircuitForge is distributed under the GNU General Public License,\n"
        "version 3 or later. You may redistribute and/or modify it under\n"
        "those terms; in particular, derivative works must also be released\n"
        "under the GPL v3 (or later), with source available to anyone who\n"
        "receives the binary. The full license text is in the LICENSE file.\n"
    )
