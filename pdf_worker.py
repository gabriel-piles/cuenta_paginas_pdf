"""Background PDF page counting (non-blocking UI via QThreadPool)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

# pypdf logs repair warnings for damaged PDFs to stderr; thousands of lines
# stall the console (and thus perceived app speed). Counting them is pointless.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def find_pdfs(folder: str | os.PathLike) -> list[Path]:
    """Return sorted list of .pdf files (case-insensitive) directly in folder.

    No recursion: subdirectories are ignored.
    """
    root = Path(folder)
    if not root.is_dir():
        return []
    try:
        with os.scandir(root) as it:
            paths = [
                Path(entry.path)
                for entry in it
                if entry.is_file() and entry.name.lower().endswith(".pdf")
            ]
    except OSError:
        return []
    return sorted(paths, key=lambda p: p.name.lower())


def count_pages_sync(path: str | os.PathLike) -> tuple[int | None, str]:
    """Count pages in one PDF. Returns (page_count or None, status string).

    Status is "OK", "Encrypted", or "Error: <reason>".
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                # Blank-password PDFs (e.g. print-restricted) open fine with "".
                if reader.decrypt("") == 0:
                    return None, "Encrypted"
            except Exception:
                return None, "Encrypted"
        try:
            return len(reader.pages), "OK"
        except PdfReadError as exc:
            return None, f"Error: {exc}"
    except Exception as exc:  # corrupt / unreadable / missing — never raise
        return None, f"Error: {exc}"


def a3_sheets(pages: int) -> int:
    """A3 sheets needed for `pages` printed 4-up on A4: ceil(pages / 4)."""
    return max(0, (pages + 3) // 4)


class WorkerSignals(QObject):
    """Per-batch signals; one instance shared by all runnables of a scan."""

    finished_one = pyqtSignal(str, int, str)  # file_path, pages (-1 on error), status
    finished_all = pyqtSignal()


class PdfCountRunnable(QRunnable):
    """QRunnable worker: counts pages of a single PDF file."""

    def __init__(self, file_path: str, signals: WorkerSignals) -> None:
        super().__init__()
        self.file_path = file_path
        self.signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        pages, status = count_pages_sync(self.file_path)
        self.signals.finished_one.emit(
            self.file_path, pages if pages is not None else -1, status
        )
