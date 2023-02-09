# KiCad Component Manager

[Library Loader](https://www.samacsys.com/library-loader/)

[KiUtils](https://github.com/mvnmgrx/kiutils)

## Motivation

[KiCADSamacSysImporter](https://github.com/ulikoehler/KiCADSamacSysImporter)

[Kandle (KiCAD Component Handler)](https://github.com/HarveyBates/kicad-component-handler)

### Consideration of KiCad plugin

KiCad provides a Python API for building plugins and acheiving some level of automation ([KiCad 6 Python API](https://docs.kicad.org/doxygen-python-6.0/namespaces.html)).  Unfortunately as of currently there is only a Python API for the PCB Editor.  Schematic Python API apparently planned for KiCad 7 ([source](https://forum.kicad.info/t/eeschema-python-api/34042)).

<!-- As the current API does not provide an interface to both the footprint, symbol, and 3d shapes libraries, this project chooses to forgo component management as a KiCad plugin.   -->

## Developers

KiCad 6.0 PCB Editor uses Python 3.8.2 (verified via its Python scripting console).  Due to issues with recent versions of macOS compiler, pipenv is unable to install Python 3.8.2 ([pipenv issue](https://github.com/pyenv/pyenv/issues/2143#issuecomment-1113239762)).  Therefore, this project uses the closest avaliable python version, 3.8.4.

KiCad PCB Editor Python scripting console: *Tools > Scripting Console*