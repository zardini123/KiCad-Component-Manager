import sys
import pathlib

import kiutils.libraries
import kiutils.footprint
import click

import manager

GROUP = "Extern"


def kicad_project_folder_option(function):
    function = click.argument('kicad_project_folder',
                              type=click.Path(exists=True))(function)
    return function


@click.command()
@kicad_project_folder_option
@click.argument('zip_file', type=click.Path(exists=True))
# @click.option('--name', prompt='Your name', help='The person to greet.')
def import_parts(kicad_project_folder, zip_file):
    kicad_project_folder = pathlib.Path(kicad_project_folder)

    manager.import_parts(zip_file, kicad_project_folder, GROUP)


@click.command()
@kicad_project_folder_option
def merge_migrated_symbol_libraries(kicad_project_folder):
    kicad_project_folder = pathlib.Path(kicad_project_folder)

    manager.merge_newly_migrated_symbol_libraries(kicad_project_folder, GROUP)


@click.group()
def main():
    pass


main.add_command(import_parts)
main.add_command(merge_migrated_symbol_libraries)


if __name__ == '__main__':
    sys.exit(main())
