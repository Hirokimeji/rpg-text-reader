import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import unittest
from unittest.mock import patch
from dataclasses import replace
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QMimeData, QUrl, QPoint, QPointF, QCoreApplication, QEvent
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest

from app import MainWindow, ReadingDialog
from test_engine import ExtractionTests
from engine import STORY


APP = QApplication.instance() or QApplication([])


class GuiTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        # Destroy native Qt objects before Python interpreter shutdown on CI.
        APP.clipboard().clear()
        for widget in APP.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()
        import shiboken6
        shiboken6.delete(APP)

    def setUp(self):
        self.fixture = ExtractionTests()
        self.fixture.setUp()
        self.result = self.fixture.run_extract()
        self.window = MainWindow()
        self.window.loaded(self.result)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()
        self.fixture.tearDown()

    def test_search_categories_scene_and_translation_view(self):
        self.assertTrue(all(self.window.model.record(i).category in STORY for i in range(self.window.model.rowCount())))
        self.window.search.setText('你好')
        self.window.filter()
        self.assertGreater(self.window.model.rowCount(), 0)
        self.assertTrue(all('你好' in self.window.model.record(i).display for i in range(self.window.model.rowCount())))
        self.window.view.setCurrentIndex(1)
        self.assertIn('Hello', self.window.panes[0].toPlainText())
        self.window.reset_filters()
        self.window.scene_filter = ('scene', 'Map001/event1/page2')
        self.window.filter()
        self.assertEqual(self.window.model.rowCount(), 1)
        self.window.search.setText('NOT_PRESENT_IN_ANY_TEXT')
        self.window.filter()
        self.assertEqual(self.window.model.rowCount(), 0)
        self.assertFalse(self.window.read_button.isEnabled())
        self.assertFalse(self.window.copy_button.isEnabled())

    def test_pagination_keeps_full_search_and_copy_scope(self):
        template = next(r for r in self.result.records if r.category == '对白')
        self.result.records = [replace(template, seq=i+1) for i in range(501)]
        self.window.loaded(self.result)
        self.assertEqual(len(self.window.filtered_indices), 501)
        self.assertEqual(self.window.model.rowCount(), 200)
        self.window.turn_table(1)
        self.assertEqual(self.window.model.record(0).seq, 201)
        self.window.turn_table(1)
        self.assertEqual(self.window.model.rowCount(), 101)
        self.assertFalse(self.window.next_page.isEnabled())
        self.window.copy_results()
        self.assertEqual(APP.clipboard().text().count('你好'), 501)
        reader = ReadingDialog(self.result.records)
        self.assertEqual(reader.page, 0)
        reader.turn(1)
        self.assertIn('101', reader.info.text())
        reader.close()
        reader.deleteLater()

    def test_drop_folder_exe_and_json_routes_to_loader(self):
        captured = []
        self.window.load = captured.append
        for path in [self.fixture.root, self.fixture.translation, self.fixture.root / 'Game.exe']:
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(path))])
            enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.window.dragEnterEvent(enter)
            self.assertTrue(enter.isAccepted())
            drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.window.dropEvent(drop)
        self.assertEqual(len(captured), 3)

    def test_background_load_can_be_repeated(self):
        for _ in range(2):
            self.window.load(str(self.fixture.root), str(self.fixture.translation))
            for tick in range(1000):
                APP.processEvents()
                if self.window.worker is None:
                    break
                QTest.qWait(10)
            self.assertIsNone(self.window.worker)
            self.assertGreater(self.window.model.rowCount(), 0)
            self.assertTrue(self.window.open_folder.isEnabled())

    def test_drop_exe_with_cache_reads_game_without_translation_prompt(self):
        self.fixture.translation.unlink()
        (self.fixture.root / 'MTool_TilesetDefinedCache.json').write_text('[]')
        exe = self.fixture.root / 'Game.exe'
        exe.write_bytes(b'fixture')
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(exe))])
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        with patch('app.TranslationDialog') as dialog, patch('app.QMessageBox.warning') as warning:
            self.window.dropEvent(drop)
            for _ in range(1000):
                APP.processEvents()
                if self.window.worker is None:
                    break
                QTest.qWait(10)
            self.assertIsNone(self.window.worker)
            dialog.assert_not_called()
            warning.assert_not_called()
        self.assertEqual(self.window.result.translation_file, '')
        self.assertTrue(self.window.result.records)
        self.assertTrue(all(r.status == '游戏内文本' for r in self.window.result.records))


if __name__ == '__main__':
    unittest.main()
