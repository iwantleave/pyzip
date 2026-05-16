import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    gi.require_version('Pango', '1.0')
    from gi.repository import Gtk, GLib, Pango
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


if GTK_AVAILABLE:
    from main import ProgressDialog


@unittest.skipIf(not GTK_AVAILABLE, 'GTK not available')
class TestProgressDialogInit(unittest.TestCase):
    def test_create_and_close(self):
        d = ProgressDialog(None, 'Test Title')
        self.assertIsNotNone(d)
        self.assertEqual(d.get_title(), 'Test Title')
        d.destroy()

    def test_default_size(self):
        d = ProgressDialog(None, 'Size')
        w, h = d.get_default_size()
        self.assertEqual(w, 420)
        self.assertEqual(h, 130)
        d.destroy()

    def test_not_resizable(self):
        d = ProgressDialog(None, 'Resize')
        self.assertFalse(d.get_resizable())
        d.destroy()

    def test_modal(self):
        d = ProgressDialog(None, 'Modal')
        self.assertTrue(d.get_modal())
        d.destroy()


@unittest.skipIf(not GTK_AVAILABLE, 'GTK not available')
class TestProgressDialogUpdate(unittest.TestCase):
    def setUp(self):
        self.dlg = ProgressDialog(None, 'Test')

    def tearDown(self):
        self.dlg.destroy()

    def test_update_label(self):
        self.dlg.update(0, 1, 'hello.txt')
        self.assertEqual(self.dlg.file_label.get_text(), 'hello.txt')

    def test_update_changes_label(self):
        self.dlg.update(0, 1, 'first')
        self.dlg.update(0, 1, 'second')
        self.assertEqual(self.dlg.file_label.get_text(), 'second')

    def test_update_progress_fraction(self):
        self.dlg.update(5, 10, 'f.txt')
        self.assertAlmostEqual(self.dlg.progress_bar.get_fraction(), 0.5)

    def test_update_progress_complete(self):
        self.dlg.update(10, 10, 'done.txt')
        self.assertAlmostEqual(self.dlg.progress_bar.get_fraction(), 1.0)

    def test_update_progress_zero(self):
        self.dlg.update(0, 10, 'start.txt')
        self.assertAlmostEqual(self.dlg.progress_bar.get_fraction(), 0.0)

    def test_update_progress_text(self):
        self.dlg.update(3, 10, 'xyz.txt')
        self.assertEqual(self.dlg.progress_bar.get_text(), '3 / 10')

    def test_update_progress_text_zero_total(self):
        self.dlg.update(0, 0, 'none')
        self.assertAlmostEqual(self.dlg.progress_bar.get_fraction(), 0.0)
        self.assertIsNone(self.dlg.progress_bar.get_text())

    def test_update_ellipsis_long_message(self):
        long_name = 'a' * 500 + '.txt'
        self.dlg.update(1, 1, long_name)
        rendered = self.dlg.file_label.get_text()
        self.assertEqual(len(rendered), len(long_name))
        self.assertTrue(rendered.endswith('.txt'))


@unittest.skipIf(not GTK_AVAILABLE, 'GTK not available')
class TestProgressDialogMultipleUpdates(unittest.TestCase):
    def setUp(self):
        self.dlg = ProgressDialog(None, 'Batch')

    def tearDown(self):
        self.dlg.destroy()

    def test_multiple_updates(self):
        updates = [(1, 4, 'f1.txt'), (2, 4, 'f2.txt'),
                   (3, 4, 'f3.txt'), (4, 4, 'f4.txt')]
        for cur, tot, msg in updates:
            self.dlg.update(cur, tot, msg)
            expected = cur / tot
            self.assertAlmostEqual(self.dlg.progress_bar.get_fraction(), expected)
            self.assertEqual(self.dlg.file_label.get_text(), msg)
            self.assertEqual(self.dlg.progress_bar.get_text(), f'{cur} / {tot}')

    def test_update_reverse_order(self):
        self.dlg.update(10, 10, 'full')
        self.assertAlmostEqual(self.dlg.progress_bar.get_fraction(), 1.0)
        self.dlg.update(0, 10, 'reset')
        self.assertAlmostEqual(self.dlg.progress_bar.get_fraction(), 0.0)
        self.assertEqual(self.dlg.file_label.get_text(), 'reset')


if __name__ == '__main__':
    unittest.main()
