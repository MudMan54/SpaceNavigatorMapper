@echo off
rem Start SpaceNavigator Mapper with a console window, so startup messages and
rem errors stay visible. The startup log is in %LOCALAPPDATA%\SpaceNavigatorMapper.
cd /d "%~dp0"
py -3 main.py %*
echo.
echo Exit code: %ERRORLEVEL%
pause
