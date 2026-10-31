"""Violet-and-rose notebook theme with a pixel librarian mascot."""
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QPointF, QSize
from PySide6.QtGui import QColor, QPainter, QPixmap, QFontDatabase, QPalette
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QGraphicsDropShadowEffect


STYLE = '''
QWidget { font-family: "Microsoft YaHei", "Segoe UI Symbol"; font-size: 13px; color: #eadff3; }
QMainWindow, QDialog { background: #21172e; }
QFrame#heroCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #352044, stop:0.65 #3f2852, stop:1 #2d203f);
    border: 2px dashed #8d65a6; border-radius: 18px;
}
QFrame#sourceCard { background: #2e233e; border: 1px solid #624975; border-radius: 14px; }
QFrame#paperCard { background: #291e37; border: 1px solid #5c4575; border-radius: 14px; }
QLabel#brand { font-size: 27px; font-weight: 700; color: #e5b6e8; }
QLabel#eyebrow { font-family: "Segoe UI"; font-size: 10px; font-weight: 600; color: #b18cc5; }
QLabel#muted { color: #bea9cc; font-size: 12px; }
QLabel#section { font-size: 15px; font-weight: 600; color: #dfc0ee; }
QLabel#step { color: #deb4ea; background: #4b335e; border-radius: 7px; padding: 4px 7px; font-size: 11px; font-weight: 600; }
QLabel#badge { color: #dcb6eb; background: #3e2c51; border: 1px solid #73568d; border-radius: 12px; padding: 7px 12px; font-size: 12px; }
QLabel#summary { color: #d1b8df; background: #352640; border: 1px solid #5c436e; border-radius: 9px; padding: 7px 12px; font-size: 12px; }
QLabel#emptyTitle { font-size: 19px; color: #d8b1ea; font-weight: 600; }
QLabel#emptyNote { color: #c1a7cf; font-size: 13px; }
QLabel#emptyTag { color: #c8a1dc; background: #412c56; border-radius: 10px; padding: 5px 11px; font-size: 11px; }
QLabel#footerCharm { color: #9d79b1; font-size: 12px; }
QLineEdit, QComboBox, QSpinBox { background: #2e233e; border: 1px solid #634a77; border-radius: 9px; padding: 8px; selection-background-color: #794a91; selection-color: #fff2fc; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #be86ce; background: #291e37; }
QLineEdit:disabled { color: #9982a8; background: #30243e; }
QComboBox { padding-right: 22px; }
QComboBox::drop-down { border: none; width: 21px; }
QComboBox::down-arrow { image: url("@@UI@@/chevron-down.svg"); width: 10px; height: 7px; }
QSpinBox { padding-right: 24px; }
QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 19px; border-left: 1px solid #674878; border-top-right-radius: 8px; background: #3e2a50; }
QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 19px; border-left: 1px solid #674878; border-bottom-right-radius: 8px; background: #3e2a50; }
QSpinBox::up-arrow { image: url("@@UI@@/chevron-up.svg"); width: 9px; height: 6px; }
QSpinBox::down-arrow { image: url("@@UI@@/chevron-down.svg"); width: 9px; height: 6px; }
QComboBox QAbstractItemView { background: #2e233e; color: #ebd9f4; selection-background-color: #684380; selection-color: #fff1fb; border: 1px solid #866098; outline: none; padding: 5px; }
QPushButton { background: #24182f; border: 1px solid #765189; border-radius: 9px; padding: 8px 13px; color: #e1bfe9; }
QPushButton:hover { background: #543364; border-color: #ba83c8; }
QPushButton:pressed { background: #6a407d; }
QPushButton:focus { border: 1px solid #d097df; }
QPushButton#primary { background: #a64b95; color: white; border: 1px solid #a64b95; font-weight: 600; }
QPushButton#primary:hover { background: #b75ba8; border-color: #b75ba8; }
QPushButton#primary:pressed { background: #8a3b85; }
QPushButton#openGame { background: #3e2c51; color: #e7c5f0; border: 1px solid #8d64a6; font-weight: 600; }
QPushButton#openGame:hover { background: #503565; border-color: #ba89cd; }
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#openGame:disabled { color: #9e86ac; background: #30243e; border: 1px solid #48354e; }
QTreeWidget { background: #291e37; border: none; outline: none; selection-background-color: #664078; selection-color: #f1daff; }
QTreeWidget::item { padding: 6px 2px; border-radius: 5px; }
QTreeWidget::item:hover { background: #3b294a; }
QTreeWidget::item:selected { background: #5d3d73; color: #f7e8ff; }
QTableView { background: #291e37; alternate-background-color: #24182f; gridline-color: #3a294a; border: 1px solid #57406a; border-radius: 10px; outline: none; selection-background-color: #67417f; selection-color: #fff1ff; }
QTableView::item { padding: 6px; border: none; }
QTableView::item:selected { background: #67417f; color: #fff1ff; }
QHeaderView::section { background: #44304f; color: #d7b8e5; border: none; border-bottom: 1px solid #624471; padding: 10px 6px; font-size: 12px; font-weight: 600; }
QPlainTextEdit { background: #f3ecfa; color: #54405f; border: 1px solid #d9c5e4; border-radius: 10px; selection-background-color: #dfc9ef; selection-color: #4e315f; }
QPlainTextEdit:focus { border-color: #b482ca; }
QTabWidget::pane { border: none; padding-top: 7px; background: transparent; }
QTabBar::tab { padding: 8px 12px; margin-right: 4px; background: #3d2d4c; color: #c1a2cf; border: 1px solid #58406b; border-radius: 8px; }
QTabBar::tab:selected { background: #5c3e75; color: #f0d9fa; border-color: #a275ba; font-weight: 600; }
QTabBar::tab:hover { background: #513460; }
QSplitter::handle { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 1px; }
QScrollBar::handle:vertical { background: #7f5a95; border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #a579b9; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 1px 4px; }
QScrollBar::handle:horizontal { background: #7f5a95; border-radius: 4px; min-width: 28px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QProgressBar { border: none; background: #3d2b4b; border-radius: 3px; max-height: 5px; }
QProgressBar::chunk { background: #bd85d3; border-radius: 3px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #8d65a6; border-radius: 5px; background: #2e233e; }
QCheckBox::indicator:checked { background: #9a60b6; border-color: #9a60b6; image: url("@@UI@@/check.svg"); }
QToolTip { background: #3f2852; color: #ecd7f7; border: 1px solid #8c629f; padding: 7px; }
'''


def asset_path(relative: str) -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / relative


STYLE = STYLE.replace('@@UI@@', asset_path('assets/ui').as_posix())


def apply_theme(app):
    # Qt's offscreen renderer also needs explicit font registration for symbols.
    import os
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for name in ('msyh.ttc', 'seguisym.ttf'):
        path = fonts / name
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))
    app.setStyle('Fusion')
    palette = app.palette()
    for role, color in (
        (QPalette.ColorRole.Window, '#24182f'), (QPalette.ColorRole.WindowText, '#eadff3'),
        (QPalette.ColorRole.Base, '#2e233e'), (QPalette.ColorRole.Text, '#eadff3'),
        (QPalette.ColorRole.Button, '#3e2c51'), (QPalette.ColorRole.ButtonText, '#e1bfe9'),
        (QPalette.ColorRole.Highlight, '#67417f'), (QPalette.ColorRole.HighlightedText, '#fff1ff'),
        (QPalette.ColorRole.PlaceholderText, '#b59fc2'),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setStyleSheet(STYLE)


def mascot(size: int, parent=None) -> QLabel:
    image = QLabel(parent)
    image.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pixmap = QPixmap(str(asset_path('assets/icons/textlight-mascot-ui-v3.png')))
    if pixmap.isNull():
        image.setText('✦')
    else:
        image.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    image.setFixedSize(size, size)
    image.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    return image


class NotebookCanvas(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#24182f'))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#4d345d'))
        for x in range(12, self.width(), 24):
            for y in range(12, self.height(), 24):
                painter.drawEllipse(QPointF(x, y), 0.9, 0.9)


class PaperCard(QFrame):
    def __init__(self, kind='paperCard', parent=None):
        super().__init__(parent)
        self.setObjectName(kind)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setOffset(2, 3)
        shadow.setBlurRadius(5)
        shadow.setColor(QColor(115, 60, 145, 90))
        self.setGraphicsEffect(shadow)


class EmptyPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_empty = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addStretch()
        self.portrait = mascot(138)
        layout.addWidget(self.portrait, 0, Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel('把下一段故事，收进这里')
        self.title.setObjectName('emptyTitle')
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.note = QLabel('选择游戏文件夹，或把游戏 EXE 拖进来。\n提取后，就能在这里整理与阅读台词。')
        self.note.setObjectName('emptyNote')
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.tag = QLabel('RPG Maker  ·  SRPG Studio  ·  Unity')
        self.tag.setObjectName('emptyTag')
        layout.addWidget(self.tag, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def set_search_empty(self):
        self.search_empty = True
        self.portrait.hide()
        self.title.setText('这一页，暂时没有找到台词')
        self.note.setText('试试其他关键词，或切换文本类别。\n也可以点击“重置筛选”重新查看。')
        self.tag.setText('换个关键词，再找找吧 ♡')

    def minimumSizeHint(self):
        return QSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.portrait.setVisible(not self.search_empty and self.height() >= 300)
        self.tag.setVisible(self.height() >= 160)
