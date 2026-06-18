@echo off
set PGROOT=F:\pgsql\pgsql
set PATH=F:\VS2022\community\VC\Tools\MSVC\14.41.34120\bin\Hostx64\x64;%PATH%
set INCLUDE=F:\pgsql\pgsql\include;F:\pgsql\pgsql\include\server;F:\VS2022\community\VC\Tools\MSVC\14.41.34120\include;C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0\ucrt;C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0\shared;C:\Program Files (x86)\Windows Kits\10\Include\10.0.22621.0\um;%INCLUDE%
set LIB=F:\pgsql\pgsql\lib;F:\VS2022\community\VC\Tools\MSVC\14.41.34120\lib\x64;C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22621.0\ucrt\x64;C:\Program Files (x86)\Windows Kits\10\Lib\10.0.22621.0\um\x64;%LIB%

cd /d "C:\Users\15116\Downloads\pgvector-master\pgvector-master"
nmake /F Makefile.win install > "C:\Users\15116\Desktop\book\build_output.txt" 2>&1
echo Done. Check C:\Users\15116\Desktop\book\build_output.txt
pause
