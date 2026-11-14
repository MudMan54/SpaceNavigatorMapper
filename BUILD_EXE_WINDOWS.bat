@echo off
setlocal EnableExtensions
rem ===========================================================================
rem  Build SpaceNavigatorMapper.exe with Nuitka: the Python code is translated
rem  to C and compiled into one Windows EXE that runs without Python installed.
rem
rem  Needs: Python 3.10 or newer (python.org), an internet connection for the
rem  first build, and a C compiler. Nuitka uses Visual Studio Build Tools
rem  ("Desktop development with C++") if installed; otherwise it offers to
rem  download MinGW64 for you - answer Yes.
rem
rem  The EXE is placed beside main.py, so it uses the same configs\ folder as
rem  the Python version. The generated C code stays in build\main.build.
rem ===========================================================================
cd /d "%~dp0"

if not exist "main.py" (
    echo main.py was not found. Keep this file in the SpaceNavigatorMapper folder.
    goto :fail
)

rem --- Python: the py launcher if present, otherwise python on PATH ---
set "PY=py -3"
%PY% --version >nul 2>&1
if errorlevel 1 set "PY=python"
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo Python 3 was not found. Install it from https://www.python.org/ first.
    goto :fail
)
echo Using:
%PY% --version

rem --- Version from spnav_mapper\version.py, e.g. v108.143 becomes 108.143.0.0 ---
set "APPVER="
for /f "usebackq delims=" %%V in (`%PY% -c "from spnav_mapper.version import VERSION as v; p = (v.lstrip('v').split('.') + ['0'] * 4)[:4]; print('.'.join(p))"`) do set "APPVER=%%V"
if not defined APPVER (
    echo Could not read the version from spnav_mapper\version.py.
    goto :fail
)
echo Building SpaceNavigator Mapper %APPVER%
echo.

rem --- Nuitka and the app's own packages ---
%PY% -m pip install --upgrade nuitka zstandard
if errorlevel 1 goto :fail
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo.

rem --- Compile ---
%PY% -m nuitka main.py ^
    --onefile ^
    --windows-console-mode=disable ^
    --enable-plugin=pyqt5 ^
    --include-data-dir=spnav_mapper\resources=spnav_mapper\resources ^
    --windows-icon-from-ico=spnav_mapper\resources\SpaceNavigatorMapper.ico ^
    --company-name="MudMan54" ^
    --product-name="SpaceNavigator Mapper" ^
    --file-description="SpaceNavigator Mapper" ^
    --copyright="Don Muddiman" ^
    --file-version=%APPVER% ^
    --product-version=%APPVER% ^
    --output-dir=build ^
    --output-filename=SpaceNavigatorMapper.exe
if errorlevel 1 goto :fail
if not exist "build\SpaceNavigatorMapper.exe" (
    echo Nuitka finished but build\SpaceNavigatorMapper.exe is missing.
    goto :fail
)

rem --- Put the EXE beside main.py ---
copy /y "build\SpaceNavigatorMapper.exe" "SpaceNavigatorMapper.exe" >nul
if errorlevel 1 (
    echo Could not replace SpaceNavigatorMapper.exe - is it still running?
    echo Exit it ^(Options ^> Exit SpaceNavigator Mapper^), then run this file again.
    goto :fail
)

echo.
echo Done: %CD%\SpaceNavigatorMapper.exe  (version %APPVER%)
echo.
pause
exit /b 0

:fail
echo.
echo The build did not finish. See the messages above.
pause
exit /b 1
