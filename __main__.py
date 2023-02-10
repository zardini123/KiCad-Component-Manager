import sys
import pathlib

import kiutils.libraries

lib_path = pathlib.Path(
    "../Relay Box Controller/(PCB) Relay Box Controller/fp-lib-table"
)


def main() -> int:
    lib_table = kiutils.libraries.LibTable(type="fp_lib_table")
    lib_table = lib_table.from_file(lib_path)

    print(lib_table)
    return 0


if __name__ == '__main__':
    sys.exit(main())
