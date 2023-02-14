# KiCad Component Manager

[Library Loader](https://www.samacsys.com/library-loader/)

As of currently, _Component Search Engine_ provides the component in the following KiCad formats:
- Legacy (KiCad < 6.0) ([format documentations](https://dev-docs.kicad.org/en/file-formats/legacy-4-to-6/legacy_file_format_documentation.pdf)):
  - footprint (_.mod_)
  - symbol (_.lib_)
  - doc lib (_.dcm_) (cannot find documentation for format)
- Current (KiCad >= 6.0):
  - footprint (_.kicad\_mod_) ([format documentation](https://dev-docs.kicad.org/en/file-formats/sexpr-footprint/))

KiCad seperates data of a component into three seperate systems:
- Footprints are under a _.pretty_ folder, where each component is its own seperate _.kicad\_mod_ file
  - Each component points to a 3D file via a path in the _model_ expression
  - KiCad **does not** provide tool to migrate _.mod_ to _.kicad\_mod_
- Symbols are under a _.kicad\_sym_ file, where multiple components are in one file, seperated syntatically
  - KiCad provides "Migrate Libraries" button to migrate each _.lib_ into a _.kicad\_sym_ in *Preferences > Manage Symbol Libraries...*
    - Irreversable, one-way conversion.
- 3D files are under a _.3dshapes_ folder, where each component has its own 3d file
  - No syntax provided to associate 3D file with its associated footprints
    - Association delegated to footprint file (_.kicad\_mod_).

Once user migrates symbol libraries to current version, merging libraries would be between versions.
Therefore to mitigate, 
- Manager imports components using old version and merges with existing category library entry (_.lib_) (nickname "Legacy\_Extern\_\<category\>", filename "Legacy_\<category\>")
- Library set to inactive

Invariants:

- Components of category in current version (_.kicad\_sym_) (prefix "Extern_")
- Components of category in old version (_.lib_) (inactive) (prefix "Legacy_Extern_")

Then, merge process:

- Ask user to click "Migrate Libraries" button on old version components

Then:

- Continue script

Invariants:

- Components of category in current version (_.kicad\_sym_)
- New components of category in current version (_.kicad\_sym_) (inactive)

Then:

- Use KiUtils to merge the two _.kicad\_sym_'s into one

[KiUtils](https://github.com/mvnmgrx/kiutils)

## Motivation

[KiCADSamacSysImporter](https://github.com/ulikoehler/KiCADSamacSysImporter)

[Kandle (KiCAD Component Handler)](https://github.com/HarveyBates/kicad-component-handler)

### Consideration of KiCad plugin

KiCad provides a Python API for building plugins and acheiving some level of automation ([KiCad 6 Python API](https://docs.kicad.org/doxygen-python-6.0/namespaces.html)).  Unfortunately as of currently there is only a Python API for the PCB Editor.  Schematic Python API apparently planned for KiCad 7 ([source](https://forum.kicad.info/t/eeschema-python-api/34042)).

<!-- As the current API does not provide an interface to both the footprint, symbol, and 3d shapes libraries, this project chooses to forgo component management as a KiCad plugin.   -->

## Developers

KiCad 6.0 PCB Editor uses Python 3.8.2 (verified via its Python scripting console).  Due to issues with recent versions of macOS compiler, pipenv is unable to install Python 3.8.2 ([pipenv issue](https://github.com/pyenv/pyenv/issues/2143#issuecomment-1113239762)).  Therefore, this project uses the closest avaliable python version, 3.8.4.

[KiCad PCB Editor official documentation on plugin creation/layout](https://dev-docs.kicad.org/en/python/pcbnew/) 

KiCad PCB Editor Python scripting console: *Tools > Scripting Console*

Get plugin loading issue traceback: *Preferences > PCB Editor / Action Plugins*, warning symbol bottom of list

Install dev dependencies
```bash
pipenv install --dev
```

Determined provided pip packages by PCB Editor Python enviroment by running in Scripting Console ([source](https://stackoverflow.com/questions/739993/how-do-i-get-a-list-of-locally-installed-python-modules#comment66310778_23885252)):
```python
import pkg_resources
installed_packages = [(d.project_name, d.version) for d in pkg_resources.working_set]
print(installed_packages)
```

Printed:

```python
[('wxPython', '4.1.1'), ('wheel', '0.38.4'), ('urllib3', '1.26.13'), ('six', '1.16.0'), ('setuptools', '41.2.0'), ('requests', '2.28.1'), ('pip', '19.2.3'), ('idna', '3.4'), ('charset-normalizer', '2.1.1'), ('certifi', '2022.12.7')]
```