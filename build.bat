@echo off
REM Build single-file .exe on Windows.
uv run pyinstaller --onefile --noconsole --name cuenta-paginas-pdf main.py
