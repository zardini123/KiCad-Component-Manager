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
        out = cls()

        name_match = out.__name_regex.search(symbol_as_string)

        if name_match:
            out.name = name_match.group(0)

            rest_of_file_index = name_match.end()
            out.rest_of_file = symbol_as_string[rest_of_file_index:]
        else:
            # @TODO: error on no name
            pass

        return out

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
        out = cls()

        matches = out.__component_regex.findall(library_as_string)

        out.symbols = [LegacySymbol().from_str(match) for match in matches]

        return out

    def to_str(self) -> str:
        return self.__prefix + '\n'.join(symbol.to_str() for symbol in self.symbols) + self.__suffix

    def to_file(self, library_path: Path):
        self_as_string = self.to_str()

        with open(library_path, 'w') as file:
            return file.write(self_as_string)

    def merge(self, other):
        # @TODO: Check duplicate names
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
    has_3d_model: bool = False

    __camel_case = re.compile(r'(?<!^)(?=[A-Z])')

    @classmethod
    def from_part_info_file(cls, part_info_file_contents: str):

        part_info_dict = dict(
            entry.split("=") for entry in part_info_file_contents.splitlines()
        )

        # Check if 3D model is present
        model_field = part_info_dict.pop('3D')
        if model_field == 'Y':
            part_info_dict['has_3d_model'] = True
        elif model_field == 'N':
            part_info_dict['has_3d_model'] = False
        else:
            raise Exception("Unknown '3D' option found in part_info.txt")

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
KICAD_PROJECT_ENV_VAR = "${KIPRJMOD}"


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


def get_library_container(part_number: str, group: str, part_category: str, data_selection: ComponentData):
    assert group != ""

    part_base_folder = parts_folder / group

    #   3dmodels:       group.3dshapes folder
    #   footprints:     group.pretty folder
    #   symbols:        group.kicad_sym file
    #   legacy symbols: group.lib file
    # Folder name extensions taken from KiCad's own built-in libraries
    if data_selection == ComponentData.MODEL:
        return (part_base_folder / models_3d_folder / f"{part_category}.3dshapes" / part_number, False)
    if data_selection == ComponentData.PCB:
        return (part_base_folder / pcb_footprints_folder / f"{part_category}.pretty", False)
    if data_selection == ComponentData.SCHEMATIC:
        return (part_base_folder / schematic_symbols_folder / f"{part_category}.kicad_sym", True)
    if data_selection == ComponentData.LEGACY_SCHEMATIC:
        return (part_base_folder / schematic_symbols_folder / f"{LEGACY_PREFIX}_{part_category}.lib", True)

    # If execution gets here, a possibiliy of ComponentData was not implemented above
    assert False


def ensure_part_containers(project_folder: Path, part_number: str, group: str, part_category: str, include_legacy=False):
    for data_selection in ComponentData:
        # Skip legacy if directed not to include it
        if (not include_legacy) and (data_selection == ComponentData.LEGACY_SCHEMATIC):
            continue

        container, is_file = get_library_container(
            part_number, group, part_category, data_selection
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
    with zip_file.open(file_in_zip) as file:
        file_content = file.read()

    return file_content


def cse_file_name_sanitization(string_to_sanitize: str):
    # CSE = Component Search Engine
    out = string_to_sanitize
    # Test parts: TLP292(TPL,E
    out = out.replace('(', '_')
    # Test parts: MCP1402T-E/OT
    out = out.replace('/', '_')
    return out


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
            sanitized_part_name = cse_file_name_sanitization(
                part_metadata.part_number
            )
            part_folder = Path(sanitized_part_name)

            # @TODO: Check if part_folder exists in zip_file

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


def ensure_library_entry(library_table: kiutils.libraries.LibTable, part_container: Path, nickname: str, legacy=False) -> kiutils.libraries.Library:
    lib = find_libray_with_nickname(nickname, library_table)

    if lib is None:
        lib = kiutils.libraries.Library(
            name=nickname,
            uri=KICAD_PROJECT_ENV_VAR / part_container
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


def sanitize_for_filesystem(string_to_sanitize: str) -> str:
    out = string_to_sanitize
    # Test parts: MCP1402T-E/OT
    out = out.replace('/', '_')
    return out


def import_parts(new_parts_zip_path: Path, project_folder: Path, group: str):
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
        part_number_filesystem = sanitize_for_filesystem(part_number)

        # Remove non alpha-numeric and not whitespace
        part_category = re.sub(
            r'[^\s\-a-zA-Z0-9]', '', part_metadata.part_category
        )
        part_category = part_category.replace(' ', '_')
        part_category = part_category.replace('-', '_')

        ####################################
        # Ensure containers

        # @TODO: Do not create folders until finish without errors
        ensure_part_containers(
            project_folder, part_number_filesystem, group, part_category, include_legacy=True
        )

        ####################################
        # Merge new part into libraries and folders/files

        models_container_path, _ = get_library_container(
            part_number_filesystem, group, part_category, ComponentData.MODEL
        )
        footprint_container_path, _ = get_library_container(
            part_number_filesystem, group, part_category, ComponentData.PCB
        )
        symbol_container_path, _ = get_library_container(
            part_number_filesystem, group, part_category, ComponentData.SCHEMATIC
        )
        legacy_symbol_container_path, _ = get_library_container(
            part_number_filesystem, group, part_category, ComponentData.LEGACY_SCHEMATIC
        )

        output_footprint_file_path = \
            project_folder / \
            footprint_container_path / \
            f'{part_number_filesystem}.kicad_mod'

        # Load legacy symbol library from zip
        legacy_symbol = LegacySymbolLibrary.from_str(
            part_dict['legacy_schematic_symbol_file']
        )

        # Oddly symbols in CSE have the sanitized part number whereas footprints
        #   are full, original part number.
        #   Change so both symbol and footprint is consistent.
        # @FIXME: Use a `find` API to get symbol with name
        legacy_symbol.symbols[0].name = part_number

        # Merge legacy symbol library
        legacy_symbol_library = LegacySymbolLibrary.from_file(
            project_folder / legacy_symbol_container_path
        )

        final_legacy_symbol_library = \
            legacy_symbol_library.merge(legacy_symbol)

        # Check for duplicate of footprint file
        if output_footprint_file_path.is_file():
            raise Exception(f"Footprint of {part_number} already exists!")

        # @TODO: Check for duplicates of files in models folder
         #   If duplicate, throw error

        # @TODO: Check for duplicate symbol in legacy symbol library SYMBOL
        #   If duplicate, throw error

        part_footprint_string = part_dict['pcb_footprint_file']

        # Read PCB file string into Footprint object
        #   ComponentSearchEngine's .kicad_mod files are intended for prior to
        #       KiCad 6, as the footprint's first token was "module"
        #       instead of "footprint"
        #   Use KiUtils to upgrade to newer version by loading file
        part_footprint_sexpr = kiutils.utils.sexpr.parse_sexp(
            part_footprint_string
        )
        part_footprint_kiutils = kiutils.footprint.Footprint.from_sexpr(
            part_footprint_sexpr
        )
        # Date is the day after last use of old fp_arc formatting
        #   Source: https://gitlab.com/kicad/code/kicad/-/blob/master/pcbnew/plugins/kicad/pcb_plugin.h#L136
        part_footprint_kiutils.version = "20210926"
        # Ensure footprint name is of right name as some footprints have wrong name with CSE provider for some reason
        # @TODO Test: MCP1402T-E/OT
        part_footprint_kiutils.entryName = part_number

        if part_metadata.has_3d_model:
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
                    KICAD_PROJECT_ENV_VAR / \
                    models_container_path / model_filename

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
        #   - Footprint (.pretty)
        #   - Symbol (.kicad_sym)
        #   - Legacy symbol (.lib)
        # @TODO: Logging of if entries were already present or not
        library_nickname = get_library_nickname(group, part_category)

        # Ensure footprint
        ensure_library_entry(
            footprint_table, footprint_container_path, library_nickname
        )

        # @TODO: Contact KiUtils developers to have default version number so
        #   fresh symbol files can be imported
        ensure_library_entry(
            symbol_table, symbol_container_path, library_nickname
        )

        legacy_library_nickname = get_legacy_library_nickname(
            group, part_category
        )
        ensure_library_entry(
            symbol_table,
            legacy_symbol_container_path,
            legacy_library_nickname,
            legacy=True
        )

        # Save to PCB folder
        with open(output_footprint_file_path, 'w') as footprint_file:
            footprint_file.write(part_footprint_kiutils.to_sexpr())

        if part_metadata.has_3d_model:
            # Add MODEL files to 3d folder
            for model_filename, model_file_string in part_dict['3d_model_files']:
                with open(project_folder / models_container_path / model_filename, 'wb') as model_file:
                    model_file.write(model_file_string)

        # Save merged legacy symbol library to file
        with open(project_folder / legacy_symbol_container_path, 'w') as legacy_file:
            legacy_file.write(final_legacy_symbol_library.to_str())

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


def merge_newly_migrated_symbol_libraries(project_folder: Path, group: str):
    symbol_library_table_path = get_symbol_library_table(project_folder)
    symbol_library_table = kiutils.libraries.LibTable.from_file(
        symbol_library_table_path
    )

    # Find all library entries that have been converted to modern library:
    #   - legacy prefix in nickname
    #   - are type KiCad
    #   - have .kicad_sym file extension
    migrated_libs = []

    for symbol_lib in symbol_library_table.libs:
        prefix_part = symbol_lib.name[:len(LEGACY_PREFIX)]

        has_legacy_prefix = prefix_part == LEGACY_PREFIX
        is_type_kicad = symbol_lib.type == 'KiCad'
        has_modern_extension = Path(symbol_lib.uri).suffix == ".kicad_sym"

        if has_legacy_prefix and is_type_kicad and has_modern_extension:
            migrated_libs.append(symbol_lib)

    if len(migrated_libs) == 0:
        raise Exception("No migrated symbol libraries found!")

    # For each converted lib, find existing modern sym library entry without
    #   legacy extension and merge both libs
    nicknames_to_delete = set()
    files_to_delete = set()
    modern_libs_to_save = []

    for migrated_lib_entry in migrated_libs:
        matching_lib_found = False
        for modern_lib_entry in symbol_library_table.libs:
            non_legacy_name = migrated_lib_entry.name[len(LEGACY_PREFIX) + 1:]

            if non_legacy_name == modern_lib_entry.name:
                migrated_lib_path = project_folder / \
                    Path(migrated_lib_entry.uri).relative_to(
                        KICAD_PROJECT_ENV_VAR)
                modern_lib_path = project_folder / \
                    Path(modern_lib_entry.uri).relative_to(
                        KICAD_PROJECT_ENV_VAR)

                migrated_lib = kiutils.symbol.SymbolLib.from_file(
                    migrated_lib_path
                )
                modern_lib = kiutils.symbol.SymbolLib.from_file(
                    modern_lib_path
                )

                # Set "Footprint" property of new symbols to ensure symbol points to footprint
                #   https://dev-docs.kicad.org/en/file-formats/sexpr-intro/index.html#_library_identifier
                for symbol in migrated_lib.symbols:
                    for sym_property in symbol.properties:
                        if sym_property.key == "Footprint":
                            # KiCad has symbol point to its associated footprint where after the colon (:) is the footprint library FILENAME
                            footprint_filename = sanitize_for_filesystem(
                                symbol.entryName
                            )
                            sym_property.value = f'{non_legacy_name}:{footprint_filename}'

                # Merge two symbol libraries
                # @TODO: Check duplicate names
                modern_lib.symbols += migrated_lib.symbols

                # Mark migrated library to be removed from library table
                nicknames_to_delete.add(migrated_lib_entry.name)

                # Save symbol library
                modern_libs_to_save.append(modern_lib)

                # Delete legacy library file (.lib)
                files_to_delete.add(migrated_lib_path.with_suffix('.lib'))
                # Delete migrated library file (.kicad_sym)
                files_to_delete.add(migrated_lib_path)

                matching_lib_found = True

                continue

        if not matching_lib_found:
            raise Exception(
                f"No modern matching symbol library to {migrated_lib_entry.name} is found!"
            )

    # Remove all marked library table entries
    for nickname_to_delete in nicknames_to_delete:
        for symbol_lib_entry in symbol_library_table.libs:
            if symbol_lib_entry.name == nickname_to_delete:
                symbol_library_table.libs.remove(symbol_lib_entry)

    # Delete all files to delete
    for file_to_delete in files_to_delete:
        file_to_delete.unlink()

    # Save symbol libraries
    for modern_lib in modern_libs_to_save:
        modern_lib.to_file()

    # Save symbol library table
    symbol_library_table.to_file()


def new_part(project_folder: Path, part_number: str, part_category: str, group: str):

    ensure_part_containers(project_folder, part_number, group, part_category)

    # Add blank symbol
    symbol_library_path, _ = get_library_container(
        part_number, group, part_category, ComponentData.SCHEMATIC
    )

    # @TODO: Unitize this
    library_nickname = get_library_nickname(group, part_category)
    library_link = f'{library_nickname}:{part_number}'

    symbol_library = kiutils.symbol.SymbolLib.from_file(
        project_folder / symbol_library_path
    )
    new_part_symbol = kiutils.symbol.Symbol.create_new(
        id=library_link,
        value=part_number,
        reference=part_number,
        footprint=library_link
    )
    # @TODO: Check for duplicate part numbers
    symbol_library.symbols.append(new_part_symbol)

    # Add blank footprint
    footprint_library_path, _ = get_library_container(
        part_number, group, part_category, ComponentData.PCB
    )

    new_part_footprint = kiutils.footprint.Footprint.create_new(
        library_link=library_link,
        value=part_number
    )

    # @TODO: Set a model entry to the model container folder (but no file)

    # Add to library tables
    # @TODO: Unitize this
    # @FIXME: Duplicate code
    footprint_table_path = get_footprint_library_table(project_folder)
    symbol_table_path = get_symbol_library_table(project_folder)

    footprint_table = get_library_table_else_new(
        'fp_lib_table', footprint_table_path
    )
    symbol_table = get_library_table_else_new(
        'sym_lib_table', symbol_table_path
    )

    # Ensure footprint
    ensure_library_entry(
        footprint_table, footprint_library_path, library_nickname
    )

    ensure_library_entry(
        symbol_table, symbol_library_path, library_nickname
    )

    # Commit additions
    symbol_library.to_file()
    new_part_footprint.to_file(
        project_folder / footprint_library_path / f'{part_number}.kicad_mod'
    )

    footprint_table.to_file()
    symbol_table.to_file()
