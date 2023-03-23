import sys
import pathlib
import os

import click
import dotenv

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

PROJECT_FOLDER_ENVIROMENT_VAR = "KICAD_PROJECT_FOLDER"


def kicad_project_folder_option(function):
    function = click.argument('kicad_project_folder',
                              type=click.Path(exists=True))(function)
    return function


@click.command()
@kicad_project_folder_option
def set_project_path(kicad_project_folder):
    working_directory = pathlib.Path(os.getcwd()).resolve()

    dotenv.set_key(
        dotenv_path=working_directory / '.env',
        key_to_set=PROJECT_FOLDER_ENVIROMENT_VAR,
        value_to_set=kicad_project_folder
    )


def get_project_folder():
    return os.environ.get(PROJECT_FOLDER_ENVIROMENT_VAR)


def ensure_project_folder_is_set():
    kicad_project_folder = get_project_folder()
    if kicad_project_folder is None:
        print("ERROR: Project folder not set!  Set with command `set-project`",
              file=sys.stderr)
        sys.exit(1)

    return pathlib.Path(kicad_project_folder)


@click.command()
@click.argument('zip_file', type=click.Path(exists=True))
def add_parts(zip_file):
    kicad_project_folder = ensure_project_folder_is_set()

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
        "- Run this script's `post-migrate` command\n"
        "- Open KiCad and use parts"
    )


@click.command()
def merge_migrated_symbol_libraries():
    kicad_project_folder = ensure_project_folder_is_set()

    utils.merge_newly_migrated_symbol_libraries(kicad_project_folder, GROUP)


@click.command()
@click.argument('part_name', type=str)
@click.argument('part_category', type=str)
def new_part(part_name, part_category):
    kicad_project_folder = ensure_project_folder_is_set()

    utils.new_part(
        kicad_project_folder, part_name, part_category, GROUP
    )


@click.group()
def main():
    dotenv.load_dotenv()


main.add_command(set_project_path, "set-project")
main.add_command(add_parts, "add")
main.add_command(merge_migrated_symbol_libraries, "post-migrate")
main.add_command(new_part, "new")


if __name__ == '__main__':
    sys.exit(main())
