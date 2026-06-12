"""

    Exports notebooks to `.py` files using `nbdev.nb_export`.

    You need to tag relevant notebooks cells with
    `#|default_exp <module_name>` and `#|export` tags.

    It will then export the notebook to the `LIB` directory, specified in this file.
    using the `module_name` as the module name.

    Example:
    ```
    #|default_exp transforms
    #|export
    ```
    This will export the notebook to the `$LIB/transforms.py` file.
"""
import glob
import os
from pathlib import Path

from nbdev.export import nb_export
from rich.console import Console

from psilia import PSILIA_ROOT

console = Console(width=200, markup=True, force_jupyter=False)

NBS_RELATIVE_PATH = "."
LIB_ABSOLUTE_PATH = PSILIA_ROOT / "src/psilia/"

def main():
    lib_relative_path = Path(os.path.relpath(LIB_ABSOLUTE_PATH))
    nbs_relative_path = Path(NBS_RELATIVE_PATH)
    file_pattern = f"{nbs_relative_path}/**/[a-zA-Z0-9]*.ipynb"

    console.print("[blue]Trying to export the following files")

    for fname in glob.glob(file_pattern, recursive=True):

        console.print(f"\t[magenta]{fname}[/]")
        nb_export(fname, lib_path=lib_relative_path, solo_nb=True)

    console.print(
        f"[blue]to [bold]{lib_relative_path}[/]")

if __name__ == "__main__":
    main()
