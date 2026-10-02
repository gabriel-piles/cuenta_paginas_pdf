# PDF Page Counter

Cross-platform desktop GUI that counts pages in every PDF inside a selected
folder and shows the results in a sortable table. Built with **PyQt6** +
**pypdf**, background counting via `QThreadPool` so the UI never blocks.

## Setup (Linux & Windows)

Requires [`uv`](https://docs.astral.sh/uv/) and Python ≥ 3.10.

```bash
uv sync            # create .venv and install locked deps
```

## Run (Linux)

```bash
uv run python main.py
```

1. Click **Seleccionar Carpeta**, pick a folder.
2. The table fills with one row per `.pdf` directly in that folder
   (first level only, case-insensitive):
   **Nombre de Archivo** | **Nº Páginas** | **Hojas A3** | **Estado / Error**,
   plus a bold **TOTAL** row with the sums.
3. Corrupt or password-protected files show `Error: …` / `Encrypted`
   without crashing. The status bar shows total files, page sum and A3-sheet
   sum (A3 = ceil(page count / 4): 4-up printing on A4, one A3 sheet = 4 pages).
4. Click any column header to sort (numeric columns sort numerically).

## Compile the `.exe` (Windows)

PyInstaller cannot cross-compile — run the build **on Windows**, or use CI.

### Local (Windows machine)

```cmd
uv sync
build.bat
```

Output: `dist\cuenta-paginas-pdf.exe` (single file, no console window).
Double-clicking it opens the UI; pick a folder and the table fills with PDF
page counts and A3-sheet estimates.

### Via GitHub Actions (no Windows machine needed)

1. Commit and push this project to a GitHub repository.
2. Push a tag (`git tag v0.1.0 && git push origin v0.1.0`) **or** open the
   Actions tab → **build-windows-exe** → **Run workflow**.
3. When the run finishes, download the artifact
   `cuenta-paginas-pdf-windows` from the run page — it contains
   `cuenta-paginas-pdf.exe`.

On Linux the equivalent is `./build.sh` → `dist/cuenta-paginas-pdf`.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point (`QApplication` + `MainWindow`) |
| `gui.py` | UI setup: header, `QTableWidget`, status bar, scan orchestration |
| `pdf_worker.py` | `find_pdfs`, `count_pages_sync`, `QRunnable` background workers |
| `build.sh` / `build.bat` | One-file PyInstaller builds (Linux / Windows) |
| `pyproject.toml` | `uv`-managed deps (`PyQt6`, `pypdf`, `pyinstaller`) |
