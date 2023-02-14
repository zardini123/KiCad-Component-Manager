import sys
import pathlib

import kiutils.libraries
import kiutils.footprint
import click

import manager

# lib_path = pathlib.Path(
#     "../Relay Box Controller/(PCB) Relay Box Controller/fp-lib-table"
# )

footprint_path = pathlib.Path(
    "/Users/tp3/Downloads/LIB_TPIC6B595N/TPIC6B595N/KiCad/DIP794W53P254L2540H508Q20N.kicad_mod"
)

footprint_2_path = pathlib.Path(
    "/Users/tp3/Documents/Projects/2023/Lighting System/Relay Box Controller/PCB Version/(PCB) Relay Box Controller/components/extern/footprints/ic.pretty/TPIC6B595N.kicad_mod"
)


# def main() -> int:
#     # lib_table = kiutils.libraries.LibTable(type="fp_lib_table")
#     # lib_table = lib_table.from_file(lib_path)

#     footprint = kiutils.footprint.Footprint()
#     footprint = footprint.from_file(footprint_path)

#     footprint_2 = kiutils.footprint.Footprint()
#     footprint_2 = footprint.from_file(footprint_2_path)

#     footprint.to_file("out1.out")
#     footprint_2.to_file("out2.out")
#     # print(lib_table)
#     return 0


@click.command()
@click.argument('kicad_project_folder', type=click.Path(exists=True))
@click.argument('zip_file', type=click.Path(exists=True))
# @click.option('--name', prompt='Your name', help='The person to greet.')
def main(kicad_project_folder, zip_file) -> int:
    kicad_project_folder = pathlib.Path(kicad_project_folder)
    # schematic_library = pathlib.Path(schematic_library)

    # legacy_schematic = manager.LegacySymbolLibrary()
    # legacy_schematic = legacy_schematic.from_file(schematic_library)

    manager.import_parts(zip_file, kicad_project_folder, "Extern", "IC")

    manager.extract_part_data_zip(pathlib.Path(
        "/Users/tp3/Downloads/LIB_TPIC6B595N.zip"
    ))
    # manager.extract_part_data_folder(pathlib.Path(
    #     "/Users/tp3/Downloads/LIB_TPIC6B595N"
    # ))

    return 0


if __name__ == '__main__':
    sys.exit(main())
