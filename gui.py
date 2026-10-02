"""Main window: folder picker, sortable results table, totals status bar."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThreadPool, Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pdf_worker import PdfCountRunnable, WorkerSignals, a3_sheets, explorer_key, find_pdfs

COL_FILE, COL_PAGES, COL_A3, COL_FOTOCOPIAS, COL_STATUS = 0, 1, 2, 3, 4
_SUM_SENTINEL = "__TOTAL__"  # UserRole marker for the sum row


def fotocopias(sheets: int) -> int:
    """Photocopies for a file: A3 sheets x 4."""
    return sheets * 4


# Filename column sorts like Windows Explorer (same key as find_pdfs).
class _NameItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return explorer_key(self.text()) < explorer_key(other.text())
        except Exception:
            return super().__lt__(other)


# Numeric sorting for the count columns (via EditRole data comparison).
class _NumericItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        a = self.data(Qt.ItemDataRole.EditRole)
        b = other.data(Qt.ItemDataRole.EditRole)
        if isinstance(a, int) and isinstance(b, int):
            return a < b
        return super().__lt__(other)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Contador de Páginas PDF")
        self.resize(760, 500)

        self._row_of: dict[str, int] = {}  # file path -> table row
        self._pending = 0
        self._total_pages = 0
        self._total_sheets = 0
        self._signals: WorkerSignals | None = None
        self._pool = QThreadPool.globalInstance()
        # 8 threads is plenty; saturating all cores starves the Qt event loop.
        self._pool.setMaxThreadCount(min(8, max(4, self._pool.maxThreadCount())))

        # --- Header: button + folder path field ---
        self.select_btn = QPushButton("Seleccionar Carpeta")
        self.select_btn.clicked.connect(self.select_folder)
        self.path_field = QLineEdit()
        self.path_field.setReadOnly(True)
        self.path_field.setPlaceholderText("Ninguna carpeta seleccionada…")

        header = QHBoxLayout()
        header.addWidget(self.select_btn)
        header.addWidget(self.path_field, stretch=1)

        # --- Main: results table ---
        self.table = QTableWidget(0, 5)
        self.table.setItemPrototype(_NumericItem(""))
        self.table.setHorizontalHeaderLabels(
            ["Nombre de Archivo", "Nº Páginas", "Hojas A3", "N. Fotocopias", "Estado / Error"]
        )
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(COL_FILE, header_view.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(COL_PAGES, header_view.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(COL_A3, header_view.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(COL_FOTOCOPIAS, header_view.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(COL_STATUS, header_view.ResizeMode.Stretch)
        header_view.setStretchLastSection(True)

        layout = QVBoxLayout()
        layout.addLayout(header)
        layout.addWidget(QLabel("Archivos PDF:"))
        layout.addWidget(self.table, stretch=1)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        # --- Status bar: totals ---
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.files_label = QLabel("Archivos: 0")
        self.pages_label = QLabel("Páginas totales: 0")
        self.sheets_label = QLabel("Hojas A3: 0")
        self.status.addPermanentWidget(self.files_label)
        self.status.addPermanentWidget(self.pages_label)
        self.status.addPermanentWidget(self.sheets_label)
        self.status.showMessage("Listo")

    # --- Slots ---
    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecciona carpeta con PDFs")
        if not folder:
            return
        self.scan_folder(folder)

    def scan_folder(self, folder: str) -> None:
        pdfs = find_pdfs(folder)
        self.path_field.setText(str(Path(folder)))
        self._row_of = {str(p): i for i, p in enumerate(pdfs)}
        self._pending = len(pdfs)
        self._total_pages = 0
        self._total_sheets = 0

        # Sorting stays OFF while results arrive: with it on, Qt moves rows and
        # both _row_of and the bottom sum row would point at the wrong rows.
        # It is re-enabled in _on_all_done.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(pdfs) + 1)  # last row is the sum row
        for i, p in enumerate(pdfs):
            name_item = _NameItem(p.name)
            name_item.setData(Qt.ItemDataRole.UserRole, str(p))  # full path, sort-safe
            pages_item = QTableWidgetItem("…")
            pages_item.setData(Qt.ItemDataRole.UserRole, -1)
            pages_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            # "…" sorts before any page number via numeric sort key below.
            a3_item = QTableWidgetItem("…")
            a3_item.setData(Qt.ItemDataRole.EditRole, -1)  # numeric sort key
            a3_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            # "…" sorts before any number via numeric sort key below.
            foto_item = QTableWidgetItem("…")
            foto_item.setData(Qt.ItemDataRole.EditRole, -1)  # numeric sort key
            foto_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            status_item = QTableWidgetItem("Pending…")
            self.table.setItem(i, COL_FILE, name_item)
            self.table.setItem(i, COL_PAGES, pages_item)
            self.table.setItem(i, COL_A3, a3_item)
            self.table.setItem(i, COL_FOTOCOPIAS, foto_item)
            self.table.setItem(i, COL_STATUS, status_item)
        self._set_sum_row(0, 0)
        self._update_totals(len(pdfs), 0, 0)

        if not pdfs:
            self.status.showMessage("No se han encontrado archivos PDF en la carpeta seleccionada")
            return

        self.status.showMessage(f"Contando páginas de {len(pdfs)} archivo(s)…")
        self.select_btn.setEnabled(False)
        self._signals = WorkerSignals()
        self._signals.finished_one.connect(self._on_result)
        self._signals.finished_all.connect(self._on_all_done)
        for p in pdfs:
            self._pool.start(PdfCountRunnable(str(p), self._signals))

    def _set_sum_row(self, pages: int, sheets: int) -> None:
        """Create or update the bottom sum row (call only while sorting is off)."""
        if self.table.rowCount() == 0:
            self.table.setRowCount(1)
        self._update_sum_items(pages, sheets)

    def _sum_row(self) -> int:
        """Locate the sum row by its sentinel, wherever sorting placed it."""
        for r in range(self.table.rowCount()):
            item = self.table.item(r, COL_FILE)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == _SUM_SENTINEL:
                return r
        return -1

    def _update_sum_items(self, pages: int, sheets: int) -> None:
        """Fill the sentinel-marked sum row with running totals (sort-safe)."""
        row = self._sum_row()
        if row < 0:
            row = self.table.rowCount() - 1
        bold = self.table.font()
        bold.setBold(True)
        if self.table.item(row, COL_FILE) is None:
            self.table.setItem(row, COL_FILE, QTableWidgetItem())
        name_item = self.table.item(row, COL_FILE)
        assert name_item is not None
        name_item.setText("TOTAL")
        name_item.setData(Qt.ItemDataRole.UserRole, _SUM_SENTINEL)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        name_item.setFont(bold)
        pages_item = self.table.item(row, COL_PAGES)
        if pages_item is None:
            pages_item = QTableWidgetItem()
            self.table.setItem(row, COL_PAGES, pages_item)
        pages_item.setText(str(pages))
        pages_item.setData(Qt.ItemDataRole.EditRole, pages)
        pages_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        pages_item.setFont(bold)
        sheets_item = self.table.item(row, COL_A3)
        if sheets_item is None:
            sheets_item = QTableWidgetItem()
            self.table.setItem(row, COL_A3, sheets_item)
        sheets_item.setText(str(sheets))
        sheets_item.setData(Qt.ItemDataRole.EditRole, sheets)
        sheets_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        sheets_item.setFont(bold)
        foto_item = self.table.item(row, COL_FOTOCOPIAS)
        if foto_item is None:
            foto_item = QTableWidgetItem()
            self.table.setItem(row, COL_FOTOCOPIAS, foto_item)
        foto_item.setText(str(sheets * 4))
        foto_item.setData(Qt.ItemDataRole.EditRole, sheets * 4)
        foto_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        foto_item.setFont(bold)
        status_item = self.table.item(row, COL_STATUS)
        if status_item is None:
            status_item = QTableWidgetItem()
            self.table.setItem(row, COL_STATUS, status_item)
        status_item.setText("")
        status_item.setFont(bold)

    def _on_result(self, file_path: str, pages: int, status: str) -> None:
        row = self._row_of.get(file_path, -1)
        if row < 0:
            return
        pages_item = self.table.item(row, COL_PAGES)
        if pages_item is not None:
            pages_item.setText(str(pages) if pages >= 0 else "—")
            pages_item.setData(Qt.ItemDataRole.EditRole, pages)  # numeric sort key
        a3_item = self.table.item(row, COL_A3)
        if a3_item is not None:
            sheets = a3_sheets(pages) if pages >= 0 else -1
            a3_item.setText(str(sheets) if sheets >= 0 else "—")
            a3_item.setData(Qt.ItemDataRole.EditRole, sheets)
        foto_item = self.table.item(row, COL_FOTOCOPIAS)
        if foto_item is not None:
            f = fotocopias(sheets) if sheets >= 0 else -1
            foto_item.setText(str(f) if f >= 0 else "—")
            foto_item.setData(Qt.ItemDataRole.EditRole, f)
        status_item = self.table.item(row, COL_STATUS)
        if status_item is not None:
            status_item.setText(status)
        if pages > 0:
            self._total_pages += pages
            self._total_sheets += sheets
        self._pending -= 1
        self._update_totals(self.table.rowCount() - 1, self._total_pages, self._total_sheets)
        if self.table.isSortingEnabled():
            # Sorting on: row indices are unreliable, update in place instead.
            self._update_sum_items(self._total_pages, self._total_sheets)
        else:
            self._set_sum_row(self._total_pages, self._total_sheets)
        if self._pending <= 0 and self._signals is not None:
            self._signals.finished_all.emit()

    def _on_all_done(self) -> None:
        self.select_btn.setEnabled(True)
        self.table.sortItems(COL_FILE)  # restore original order, sum row lands last
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.status.showMessage("Hecho")

    def _update_totals(self, files: int, pages: int, sheets: int | None = None) -> None:
        self.files_label.setText(f"Archivos: {files}")
        self.pages_label.setText(f"Páginas totales: {pages}")
        if sheets is not None:
            self.sheets_label.setText(f"Hojas A3: {sheets}")
