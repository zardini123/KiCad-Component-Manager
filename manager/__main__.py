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

from . import utils
# autopep8: on

GROUP = "Extern"


def kicad_project_folder_option(function):
    function = click.argument('kicad_project_folder',
                              type=click.Path(exists=True))(function)
    return function


@click.command()
@kicad_project_folder_option
@click.argument('zip_file', type=click.Path(exists=True))
def add_parts(kicad_project_folder, zip_file):
    kicad_project_folder = pathlib.Path(kicad_project_folder)

    utils.import_parts(zip_file, kicad_project_folder, GROUP)

    print(
        "Part has legacy symbol files.  Do the following to have them be editable:\n"
        "- Quit KiCad (if not closed already)\n"
        "- Open KiCad (to refresh libraries)\n"
        "- Enter KiCad's `Symbol Editor` for the project\n"
        "- Open `Preferences > Manage Symbol Libraries...` and go to `Project Specific Libraries` tab\n"
        "- Find all entries starting with `LEGACY_` in the nickname\n"
        "- One at a time, click each `LEGACY_` entry and press `Migrate Libraries` button\n"
        "- Press `OK` to save the library entries and close the symbol library manager\n"
        "- Quit KiCad\n"
        "- Run this script's `post-migrate` command on your project folder\n"
        "Symbol libraries are ready to go.  Open KiCad and enjoy."
    )


@click.command()
@kicad_project_folder_option
def merge_migrated_symbol_libraries(kicad_project_folder):
    kicad_project_folder = pathlib.Path(kicad_project_folder)

    utils.merge_newly_migrated_symbol_libraries(kicad_project_folder, GROUP)


@click.command()
@kicad_project_folder_option
@click.argument('part_name', type=str)
@click.argument('part_category', type=str)
def new_part(kicad_project_folder, part_name, part_category):
    kicad_project_folder = pathlib.Path(kicad_project_folder)

    utils.new_part(
        kicad_project_folder, part_name, part_category, GROUP
    )


@click.group()
def main():
    pass


main.add_command(add_parts, "add")
main.add_command(merge_migrated_symbol_libraries, "post-migrate")
main.add_command(new_part, "new")


if __name__ == '__main__':
    sys.exit(main())
