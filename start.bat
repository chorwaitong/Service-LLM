@echo off
cd /d %~dp0

rem Primary and fallback python executables
set "PY1=C:\Anaconda\envs\envServiceLLM\python.exe"
set "PY2=C:\Users\User\miniconda3\envs\envServiceLLM\python.exe"

if exist "%PY1%" (
	echo Using %PY1%
	"%PY1%" main.py
) else if exist "%PY2%" (
	echo Using %PY2%
	"%PY2%" main.py
) else (
	echo Neither %PY1% nor %PY2% found. Trying system python.
)