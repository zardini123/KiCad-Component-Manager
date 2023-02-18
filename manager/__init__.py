import os
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from pathlib import Path

import re
import zipfile

import kiutils.symbol
import kiutils.libraries
import kiutils.utils
import kiutils.footprint


@dataclass
class LegacySymbol:
    rest_of_file: str = ""
    name: str = ""

    __name_regex = re.compile(r'(?<=DEF\W)(.*?)(?=\W)')

    @classmethod
    def from_str(cls, symbol_as_string):
        object = cls()

        name_match = object.__name_regex.search(symbol_as_string)

        if name_match:
            object.name = name_match.group(0)

            rest_of_file_index = name_match.end()
            object.rest_of_file = symbol_as_string[rest_of_file_index:]
        else:
            # @TODO: error on no name
            pass

        return object

    def to_str(self) -> str:
        return f"DEF {self.name} {self.rest_of_file}"


@dataclass
class LegacySymbolLibrary:
    symbols: List[LegacySymbol] = field(default_factory=list)

    __component_regex = re.compile(r'DEF[\s\S]*?ENDDEF')

    # Taken from Component Search Engine KiCad .lib file
    __prefix = (
        "EESchema-LIBRARY Version 2.3\n"
        "#encoding utf-8\n"
    )
    __suffix = (
        "\n#End Library"
    )

    def __init__(self, symbols=[]) -> None:
        self.symbols = symbols

    @classmethod
    def from_file(cls, library_path: Path):
        with open(library_path, 'r') as file:
            file_content = file.read()
            return cls.from_str(file_content)

    @classmethod
    def from_str(cls, library_as_string: str):
        object = cls()

        matches = object.__component_regex.findall(library_as_string)

        object.symbols = [LegacySymbol().from_str(match) for match in matches]

        return object

    def to_str(self) -> str:
        return self.__prefix + '\n'.join(symbol.to_str() for symbol in self.symbols) + self.__suffix

    def to_file(self, library_path: Path):
        self_as_string = self.to_str()

        with open(library_path, 'w') as file:
            return file.write(self_as_string)

    def merge(self, other):
        return LegacySymbolLibrary(self.symbols + other.symbols)


@dataclass
class Part:
    manufacturer: str = ""
    part_number: str = ""
    part_category: str = ""
    package_category: str = ""
    pin_count: int = -1
    version: Tuple[int, int, int] = (-1, -1, -1)
    released: Optional[datetime] = None
    downloaded: Optional[datetime] = None
    three_d: str = ""

    __camel_case = re.compile(r'(?<!^)(?=[A-Z])')

    @classmethod
    def from_part_info_file(cls, part_info_file_contents: str):

        part_info_dict = dict(
            entry.split("=") for entry in part_info_file_contents.splitlines()
        )

        # Special name changing
        part_info_dict['three_d'] = part_info_dict.pop('3D')

        # Part info text file keys in camel case.  Convert to snake case
        #   Conversion source: https://stackoverflow.com/a/1176023/6183001
        for key in list(part_info_dict):
            snake_case = cls.__camel_case.sub('_', key).lower()
            snake_case = snake_case.replace('__', '_')

            part_info_dict[snake_case] = part_info_dict.pop(key)

        # Dates in part_info.txt seem to be of ISO 8601 format
        #   https://www.iso.org/iso-8601-date-and-time-format.html
        for date_key in ['released', 'downloaded']:
            part_info_dict[date_key] = datetime.fromisoformat(
                part_info_dict[date_key]
            )

        # Convert version number to 3 part version number to comply with
        #   semantic versioning: https://semver.org
        # No idea how SamacSys interprets their version number
        version_as_int_list = [
            int(decimal) for decimal in part_info_dict['version'].split('.')
        ]
        # Ensure there are 3 parts to the version number
        number_of_decimals_in_version = 3
        version_as_int_list = version_as_int_list + (
            [0] * (number_of_decimals_in_version - len(version_as_int_list))
        )
        part_info_dict['version'] = tuple(version_as_int_list)

        # @TODO: Error handling when non-matching keys
        return cls(**part_info_dict)


parts_folder = Path("parts")
models_3d_folder = Path("3dmodels")
pcb_footprints_folder = Path("footprints")
schematic_symbols_folder = Path("symbols")

LEGACY_PREFIX = "LEGACY"
KICAD_PROJECT_ENVIROMENT_VARIABLE = "${KIPRJMOD}"


class ComponentData(Enum):
    PCB = 0
    SCHEMATIC = 1
    LEGACY_SCHEMATIC = 2
    MODEL = 3

# def get_part_filename(part_name: str, group: str, data_type: ComponentData, is_legacy: bool):
#     if data_type == ComponentData.MODEL:
#         return f"{out}"
#     elif data_type == ComponentData.PCB:
#         return f"{group}.pretty"
#     elif data_selection == ComponentData.SCHEMATIC:
#         return f"{group}.kicad_sym"


def get_library_nickname(group: str, part_category: str):
    return f"{group}_{part_category}"


def get_legacy_library_nickname(group: str, part_category: str):
    return f"{LEGACY_PREFIX}_{group}_{part_category}"


def get_library_container(group: str, part_category: str, data_selection: ComponentData):
    assert group != ""

    part_base_folder = parts_folder / group

    #   3dmodels:       group.3dshapes folder
    #   footprints:     group.pretty folder
    #   symbols:        group.kicad_sym file
    #   legacy symbols: group.lib file
    # Folder name extensions taken from KiCad's own built-in libraries
    if data_selection == ComponentData.MODEL:
        return (part_base_folder / models_3d_folder / f"{part_category}.3dshapes", False)
    elif data_selection == ComponentData.PCB:
        return (part_base_folder / pcb_footprints_folder / f"{part_category}.pretty", False)
    elif data_selection == ComponentData.SCHEMATIC:
        return (part_base_folder / schematic_symbols_folder / f"{part_category}.kicad_sym", True)
    elif data_selection == ComponentData.LEGACY_SCHEMATIC:
        return (part_base_folder / schematic_symbols_folder / f"{LEGACY_PREFIX}_{part_category}.lib", True)

    # If execution gets here, a possibiliy of ComponentData was not implemented above
    assert False


def ensure_part_containers(project_folder: Path, group: str, part_category: str):
    for data_selection in ComponentData:
        # @HACK: Contact KiUtils developers to set version number default so KiCad can import
        #   fresh schematic files
        # if data_selection == ComponentData.SCHEMATIC:
        #     continue

        container, is_file = get_library_container(
            group, part_category, data_selection
        )
        container = project_folder / container

        if is_file:
            container.parent.mkdir(parents=True, exist_ok=True)
            # @FIXME: Assumes a file container is a symbol library

            if not container.exists():
                if data_selection == ComponentData.SCHEMATIC:
                    new_symbol_lib = kiutils.symbol.SymbolLib()
                    new_symbol_lib.version = "20211014"
                    new_symbol_lib.to_file(container)
                elif data_selection == ComponentData.LEGACY_SCHEMATIC:
                    LegacySymbolLibrary().to_file(container)
        else:
            container.mkdir(parents=True, exist_ok=True)


def is_relative_to(path, base_path):
    # is_relative_to in pathlib is not introduced till Python 3.9
    #   https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_relative_to

    base_path_parts = base_path.parts

    return base_path_parts == path.parts[:len(base_path_parts)]


def read_file_in_zip(zip_file, file_in_zip):
    with zip_file.open(file_in_zip) as file_in_zip:
        file_content = file_in_zip.read()

    return file_content


def extract_part_data_zip(zip_file_path: Path):
    with zipfile.ZipFile(zip_file_path) as zip_file:
        # 1. Find all part_info.txt to get all part metadatas
        # @TODO: Make parts_metadatas a set due to there being no explicit order
        #   Cannot make set as Part is not hashable
        parts_metadatas = []

        for file_in_zip in zip_file.infolist():
            current_file_in_zip = Path(file_in_zip.filename)

            if current_file_in_zip.name == "part_info.txt":
                file_content = read_file_in_zip(
                    zip_file, file_in_zip
                )

                part_metadata = Part.from_part_info_file(
                    file_content.decode(encoding="utf-8")
                )
                parts_metadatas.append(part_metadata)

        # 2. Go to each part folder and get files relating to KiCad parts
        parts = []

        for part_metadata in parts_metadatas:
            part_folder = Path(part_metadata.part_number)

            model_files = set()
            pcb_footprint_file = None
            legacy_schematic_symbol_file = None

            for file_in_zip in zip_file.infolist():
                current_file_in_zip = Path(file_in_zip.filename)

                # All files from {part_name}/3D folder
                if is_relative_to(current_file_in_zip, (part_folder / '3D')):
                    name = current_file_in_zip.name
                    file_content = read_file_in_zip(
                        zip_file, file_in_zip
                    )

                    model_files.add((name, file_content))

                if is_relative_to(current_file_in_zip, (part_folder / 'KiCad')):
                    # {part_name}.lib from {part_name}/KiCad/ folder
                    if current_file_in_zip.suffix == '.lib':
                        # @TODO: Proper error handling
                        #   Found two legacy schematic symbol files in one part
                        assert legacy_schematic_symbol_file is None

                        legacy_schematic_symbol_file = read_file_in_zip(
                            zip_file, file_in_zip
                        )
                        legacy_schematic_symbol_file = \
                            legacy_schematic_symbol_file.decode('utf-8')

                    # {part_name}.kicad_mod from {part_name}/KiCad/ folder
                    if current_file_in_zip.suffix == '.kicad_mod':
                        # @TODO: Proper error handling
                        #   Found two pcb footprint files in one part
                        assert pcb_footprint_file is None

                        pcb_footprint_file = read_file_in_zip(
                            zip_file, file_in_zip
                        )
                        pcb_footprint_file = pcb_footprint_file.decode('utf-8')

            # @TODO: Proper error handling
            #   Never found pcb or schematic file if fail here
            assert pcb_footprint_file is not None
            assert legacy_schematic_symbol_file is not None

            parts.append({
                'part_metadata': part_metadata,
                'pcb_footprint_file': pcb_footprint_file,
                'legacy_schematic_symbol_file': legacy_schematic_symbol_file,
                '3d_model_files': model_files,
            })

    return parts


# def extract_part_data_folder(base_folder: Path):
#     for tuple in os.walk(base_folder):
#         print(tuple)

#     return {
#         'part_name': "",
#         'pcb_footprint_file': None,
#         'legacy_schematic_symbol_file': None,
#         '3d_model_files': [],
#     }

def verify_model_entries(model_files: List[Tuple[int, bytes]], model_entires: List[kiutils.footprint.Model]):
    models_provided = [
        model[0] for model in model_files
    ]
    models_in_footprint = [
        Path(model_entry.path) for model_entry in model_entires
    ]

    for model_filename in models_provided:
        model_found = False
        for model_entry_path in models_in_footprint:
            if model_filename == model_entry_path.name:
                model_found = True

        # @TODO: Proper error handling
        assert model_found


def get_library_table_else_new(lib_type: str, library_table_path: Path) -> kiutils.libraries.LibTable:
    if library_table_path.exists():
        # from_file sets lib table type
        return kiutils.libraries.LibTable.from_file(library_table_path)

    out = kiutils.libraries.LibTable.create_new(type=lib_type)
    out.filePath = library_table_path

    return out


def find_libray_with_nickname(nickname: str, library_table: kiutils.libraries.LibTable) -> Optional[kiutils.libraries.Library]:
    for lib in library_table.libs:
        if lib.name == nickname:
            return lib

    return None


def ensure_library_entry(nickname: str, library_table: kiutils.libraries.LibTable, part_container: Path, legacy=False) -> kiutils.libraries.Library:
    lib = find_libray_with_nickname(nickname, library_table)

    if lib is None:
        lib = kiutils.libraries.Library(
            name=nickname,
            uri=KICAD_PROJECT_ENVIROMENT_VARIABLE / part_container
        )
        if legacy:
            lib.type = "Legacy"

        library_table.libs.append(lib)

    return lib


def get_symbol_library_table(project_folder: Path) -> Path:
    # @NOTE: Notice dash versus underscore for table types
    #   KiCad requires file names to use dashes,
    #   and the corresponding S-exper token to use underscores
    return project_folder / 'sym-lib-table'


def get_footprint_library_table(project_folder: Path) -> Path:
    return project_folder / 'fp-lib-table'


def import_parts(new_parts_zip_path: Path, project_folder: Path, group: str, part_category: str):
    # Get part files from .zip
    #   In KiCad folder:
    #       POOR ASSUMPTION: footprints/symbol only have one of each in them
    #       ASSUME arbitrary number of footprints/symbols in library files
    #   - footprint
    #   - symbol
    #   In 3D folder:
    #       POOR ASSUMPTION: Only a .stp file for part
    #       ASSUME arbitrary number of 3d files in library files
    new_parts = extract_part_data_zip(new_parts_zip_path)

    for part_dict in new_parts:
        part_metadata = part_dict['part_metadata']
        part_number = part_metadata.part_number
        part_category = part_metadata.part_category.replace(' ', '_')

        ####################################
        # Ensure containers

        # @TODO: Do not create folders until finish without errors
        ensure_part_containers(
            project_folder, group, part_category
        )

        ####################################
        # Merge new part into libraries and folders/files

        models_container_path, _ = get_library_container(
            group, part_category, ComponentData.MODEL
        )
        footprint_container_path, _ = get_library_container(
            group, part_category, ComponentData.PCB
        )
        symbol_container_path, _ = get_library_container(
            group, part_category, ComponentData.SCHEMATIC
        )
        legacy_symbol_container_path, _ = get_library_container(
            group, part_category, ComponentData.LEGACY_SCHEMATIC
        )

        legacy_file = LegacySymbolLibrary.from_file(
            project_folder / legacy_symbol_container_path
        )
        final_legacy_file = legacy_file.merge(
            LegacySymbolLibrary.from_str(
                part_dict['legacy_schematic_symbol_file'])
        )

        # Check for duplicates of files in folder MODELS and PCB
        #   If duplicates, throw error
        # @TODO:

        # Check for duplicate symbol in legacy symbol library SYMBOL
        #   If duplicate, throw error
        #   Else, merge legacy symbol library in memory
        # @TODO:

        part_footprint_string = part_dict['pcb_footprint_file']

        # Read PCB file string into Footprint object
        #   From: https://github.com/mvnmgrx/kiutils/blob/63c57a7697e453829482fd04dfccc11fa9cc9e74/src/kiutils/footprint.py#L861
        part_footprint_sexpr = kiutils.utils.sexpr.parse_sexp(
            part_footprint_string
        )
        part_footprint_kiutils = kiutils.footprint.Footprint.from_sexpr(
            part_footprint_sexpr
        )

        # Check to make sure .kicad_mod model entries points to file in new parts 3D models folder
        verify_model_entries(
            part_dict['3d_model_files'], part_footprint_kiutils.models
        )

        # Modify footprint model in memory to point to parts folder
        #   https://kiutils.readthedocs.io/en/latest/module/kiutils.html#kiutils.footprint.Footprint.models
        #   part_footprint_kiutils.models
        for model_entry in part_footprint_kiutils.models:
            model_filename = Path(model_entry.path).name

            # Change footprint model directory
            model_entry.path = \
                KICAD_PROJECT_ENVIROMENT_VARIABLE / \
                models_container_path / part_number / model_filename

        footprint_table_path = get_footprint_library_table(project_folder)
        symbol_table_path = get_symbol_library_table(project_folder)

        # Load footprint and symbol tables
        footprint_table = get_library_table_else_new(
            'fp_lib_table', footprint_table_path
        )
        symbol_table = get_library_table_else_new(
            'sym_lib_table', symbol_table_path
        )

        # Ensure library entries of:
        #   -
        # @TODO: Logging of if entries were already present or not
        library_nickname = get_library_nickname(group, part_category)

        ensure_library_entry(
            library_nickname, footprint_table, footprint_container_path
        )

        # @TODO: Contact KiUtils developers to have default version number so
        #   fresh symbol files can be imported
        ensure_library_entry(
            library_nickname, symbol_table, symbol_container_path
        )

        legacy_library_nickname = get_legacy_library_nickname(
            group, part_category
        )
        ensure_library_entry(
            legacy_library_nickname,
            symbol_table,
            legacy_symbol_container_path,
            legacy=True
        )

        print(footprint_table)
        print(symbol_table)

        # Save to PCB folder
        with open(project_folder / footprint_container_path / f'{part_number}.kicad_mod', 'w') as footprint_file:
            footprint_file.write(part_footprint_kiutils.to_sexpr())

        # Add MODEL files to 3d folder
        (
            project_folder / models_container_path / part_number
        ).mkdir(parents=True, exist_ok=True)
        for model_filename, model_file_string in part_dict['3d_model_files']:
            with open(project_folder / models_container_path / part_number / model_filename, 'wb') as model_file:
                model_file.write(model_file_string)

        # Save merged legacy symbol library to file
        with open(project_folder / legacy_symbol_container_path, 'w') as legacy_file:
            legacy_file.write(final_legacy_file.to_str())

        # Save library tables
        footprint_table.to_file()
        symbol_table.to_file()

        # @TODO: Do not commit saving files until every file has been successfully saven
        #   Could this be done by doing library operations in temporary clone folder,
        #   and replacing original folder when done?

        ####################################
        # Request user to migrate legacy entry

        ####################################
        # Merging migrated symbol files

        # Find pair of entries with nicknames:
        # - legacy prefix with nickname and is .kicad_sym
        # - nickname and is .kicad_sym

        # Load both symbol libraries
        # Merge together
        # Save to nickname library file

        # Remove legacy entry from symbol table
        # Delete legacy file that is .kicad_sym

        ####################################
        # Opposite actions

        # OPP: Remove part from category library
        #   Needs footprint name

        # OPP: Remove base folder (remove all libraries)

        # https://en.wikipedia.org/wiki/Atomicity_(database_systems)
        #   "consistency also relies on atomicity to roll back the enclosing
        #   transaction in the event of a consistency violation by an illegal
        #   transaction."

    pass


def merge_newly_migrated_symbol_libraries(project_folder: Path, group: str):
    symbol_library_table_path = get_symbol_library_table(project_folder)
    symbol_library_table = kiutils.libraries.LibTable.from_file(project_folder)
