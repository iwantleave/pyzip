import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gdk', '4.0')
    gi.require_version('Pango', '1.0')
    from main import is_archive, get_file_type, get_icon_for_file
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


@unittest.skipIf(not GTK_AVAILABLE, 'GTK not available')
class TestIsArchive(unittest.TestCase):
    def test_zip(self):
        self.assertTrue(is_archive('test.zip'))
        self.assertTrue(is_archive('/path/to/file.ZIP'))

    def test_tar(self):
        self.assertTrue(is_archive('test.tar'))
        self.assertTrue(is_archive('test.TAR'))

    def test_tar_gz(self):
        self.assertTrue(is_archive('test.tar.gz'))
        self.assertTrue(is_archive('test.TAR.GZ'))
        self.assertTrue(is_archive('test.tgz'))
        self.assertTrue(is_archive('test.TGZ'))

    def test_tar_bz2(self):
        self.assertTrue(is_archive('test.tar.bz2'))
        self.assertTrue(is_archive('test.tbz2'))

    def test_tar_xz(self):
        self.assertTrue(is_archive('test.tar.xz'))
        self.assertTrue(is_archive('test.txz'))

    def test_non_archive(self):
        self.assertFalse(is_archive('test.txt'))
        self.assertFalse(is_archive('test.py'))
        self.assertFalse(is_archive('test'))
        self.assertFalse(is_archive('.hidden'))

    def test_dotfile_archive(self):
        self.assertTrue(is_archive('.zip'))
        self.assertTrue(is_archive('a.zip'))
        self.assertFalse(is_archive('archive.tar.old'))


@unittest.skipIf(not GTK_AVAILABLE, 'GTK not available')
class TestGetFileType(unittest.TestCase):
    def test_txt(self):
        self.assertEqual(get_file_type('readme.txt'), 'Text Document')

    def test_python(self):
        self.assertEqual(get_file_type('main.py'), 'Python Source')

    def test_c_source(self):
        self.assertEqual(get_file_type('main.c'), 'C Source')
        self.assertEqual(get_file_type('main.h'), 'C Header')

    def test_markdown(self):
        self.assertEqual(get_file_type('readme.md'), 'Markdown')

    def test_image(self):
        self.assertEqual(get_file_type('photo.png'), 'PNG Image')
        self.assertEqual(get_file_type('photo.jpg'), 'JPEG Image')
        self.assertEqual(get_file_type('photo.jpeg'), 'JPEG Image')

    def test_archive_types(self):
        self.assertEqual(get_file_type('a.zip'), 'ZIP Archive')
        self.assertEqual(get_file_type('a.tar'), 'TAR Archive')
        self.assertEqual(get_file_type('a.gz'), 'GZip Archive')

    def test_unknown_ext(self):
        self.assertEqual(get_file_type('file.xyz'), '.XYZ File')

    def test_no_ext(self):
        self.assertEqual(get_file_type('Makefile'), 'File')

    def test_empty_name(self):
        self.assertEqual(get_file_type(''), 'File')


@unittest.skipIf(not GTK_AVAILABLE, 'GTK not available')
class TestGetIconForFile(unittest.TestCase):
    def test_folder_not_used(self):
        self.assertEqual(get_icon_for_file('dir', '.txt'),
                         'text-x-generic-symbolic')

    def test_python_icon(self):
        self.assertEqual(get_icon_for_file('main.py', '.py'),
                         'text-x-python-symbolic')

    def test_image_icon(self):
        self.assertEqual(get_icon_for_file('img.png', '.png'),
                         'image-x-generic-symbolic')

    def test_archive_icon(self):
        self.assertEqual(get_icon_for_file('a.zip', '.zip'),
                         'application-x-archive-symbolic')

    def test_unknown_icon(self):
        self.assertEqual(get_icon_for_file('f.xyz', '.xyz'),
                         'text-x-generic-symbolic')


if __name__ == '__main__':
    unittest.main()
