import sys
import pathlib

import click

# autopep8: off

# Manual inclusion of kiutils repository
# KIUTILS_PATH = pathlib.Path(__file__).resolve().parents[1] / 'kiutils' / 'src'
# assert KIUTILS_PATH.is_dir()
# 
# sys.path.append(str(KIUTILS_PATH))

import kiutils.libraries
import kiutils.footprint

import manager
# autopep8: on

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


@click.command()
@kicad_project_folder_option
@click.argument('part_name', type=str)
@click.argument('part_category', type=str)
def new_part(kicad_project_folder, part_name, part_category):
    kicad_project_folder = pathlib.Path(kicad_project_folder)

    manager.new_part(
        kicad_project_folder, part_name, part_category, GROUP
    )


@click.group()
def main():
    pass


main.add_command(import_parts, "add")
main.add_command(merge_migrated_symbol_libraries, "post-migrate")
main.add_command(new_part, "new")


if __name__ == '__main__':
    sys.exit(main())
