import os
import sys
import time
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from archive_handler import ArchiveHandler, ArchiveEntry, format_size


class TestFormatSize(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(format_size(0), '0 B')
        self.assertEqual(format_size(500), '500 B')
        self.assertEqual(format_size(1023), '1023 B')

    def test_kb(self):
        self.assertEqual(format_size(1024), '1.0 KB')
        self.assertEqual(format_size(1536), '1.5 KB')
        self.assertEqual(format_size(1024 * 1024 - 1), '1024.0 KB')

    def test_mb(self):
        self.assertEqual(format_size(1024 * 1024), '1.0 MB')
        self.assertEqual(format_size(2 * 1024 * 1024), '2.0 MB')

    def test_gb(self):
        self.assertEqual(format_size(1024 ** 3), '1.00 GB')
        self.assertEqual(format_size(3 * 1024 ** 3), '3.00 GB')


class TestArchiveEntry(unittest.TestCase):
    def test_modified_str(self):
        t = time.mktime((2024, 1, 15, 10, 30, 0, 0, 0, -1))
        e = ArchiveEntry(name='test.txt', size=100, packed_size=50,
                         modified=t, is_dir=False)
        self.assertEqual(e.modified_str, '2024-01-15 10:30')

    def test_size_str_file(self):
        e = ArchiveEntry(name='test.txt', size=2048, packed_size=1024,
                         modified=0, is_dir=False)
        self.assertEqual(e.size_str, '2.0 KB')

    def test_size_str_dir(self):
        e = ArchiveEntry(name='dir/', size=0, packed_size=0,
                         modified=0, is_dir=True)
        self.assertEqual(e.size_str, '')

    def test_packed_str_file(self):
        e = ArchiveEntry(name='test.txt', size=2048, packed_size=1024,
                         modified=0, is_dir=False)
        self.assertEqual(e.packed_str, '1.0 KB')

    def test_packed_str_dir(self):
        e = ArchiveEntry(name='dir/', size=0, packed_size=0,
                         modified=0, is_dir=True)
        self.assertEqual(e.packed_str, '')

    def test_type_str_dir(self):
        e = ArchiveEntry(name='dir/', size=0, packed_size=0,
                         modified=0, is_dir=True)
        self.assertEqual(e.type_str, 'Folder')

    def test_type_str_known_ext(self):
        e = ArchiveEntry(name='main.py', size=100, packed_size=50,
                         modified=0, is_dir=False)
        self.assertEqual(e.type_str, 'Python Source')

    def test_type_str_unknown_ext(self):
        e = ArchiveEntry(name='file.xyz', size=100, packed_size=50,
                         modified=0, is_dir=False)
        self.assertEqual(e.type_str, '.XYZ File')

    def test_type_str_no_ext(self):
        e = ArchiveEntry(name='Makefile', size=100, packed_size=50,
                         modified=0, is_dir=False)
        self.assertEqual(e.type_str, 'File')

    def test_crc_default(self):
        e = ArchiveEntry(name='test.txt', size=100, packed_size=50,
                         modified=0, is_dir=False)
        self.assertEqual(e.crc, '')


class TestArchiveHandlerOpen(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.handler = ArchiveHandler()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_zip(self, name='test.zip'):
        path = os.path.join(self.tmpdir, name)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('file1.txt', 'hello world')
            zf.writestr('file2.txt', 'foo bar baz')
            zf.writestr('subdir/', '')
        return path

    def _create_tar(self, name='test.tar'):
        path = os.path.join(self.tmpdir, name)
        with tarfile.open(path, 'w') as tf:
            tf.addfile(tarfile.TarInfo('file1.txt'), io.BytesIO(b'hello world'))
            tf.addfile(tarfile.TarInfo('file2.txt'), io.BytesIO(b'foo bar baz'))
            t = tarfile.TarInfo('subdir/')
            t.type = tarfile.DIRTYPE
            tf.addfile(t)
        return path

    def _create_tar_gz(self, name='test.tar.gz'):
        path = os.path.join(self.tmpdir, name)
        with tarfile.open(path, 'w:gz') as tf:
            tf.addfile(tarfile.TarInfo('file1.txt'), io.BytesIO(b'hello'))
        return path

    def test_open_zip(self):
        path = self._create_zip()
        entries = self.handler.open(path)
        self.assertEqual(self.handler.type, 'zip')
        self.assertEqual(len(entries), 3)
        names = {e.name for e in entries}
        self.assertIn('file1.txt', names)
        self.assertIn('file2.txt', names)
        self.assertIn('subdir/', names)
        dirs = [e for e in entries if e.is_dir]
        self.assertEqual(len(dirs), 1)
        self.assertEqual(dirs[0].name, 'subdir/')

    def test_open_tar(self):
        path = self._create_tar()
        entries = self.handler.open(path)
        self.assertEqual(self.handler.type, 'tar')
        self.assertEqual(len(entries), 3)

    def test_open_tar_gz(self):
        path = self._create_tar_gz()
        entries = self.handler.open(path)
        self.assertEqual(self.handler.type, 'tar.gz')
        self.assertEqual(len(entries), 1)

    def test_open_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self.handler.open('/nonexistent/archive.zip')

    def test_open_unsupported_format(self):
        path = os.path.join(self.tmpdir, 'test.rar')
        open(path, 'w').close()
        with self.assertRaises(ValueError):
            self.handler.open(path)

    def test_open_twice_replaces(self):
        path1 = self._create_zip('a.zip')
        path2 = self._create_zip('b.zip')
        self.handler.open(path1)
        entries = self.handler.open(path2)
        self.assertEqual(len(entries), 3)
        self.assertNotEqual(self.handler.path, path1)


import zipfile
import tarfile
import io


class TestArchiveHandlerExtract(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.handler = ArchiveHandler()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_zip_with_files(self):
        path = os.path.join(self.tmpdir, 'test.zip')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('file1.txt', 'content1')
            zf.writestr('dir/file2.txt', 'content2')
        self.handler.open(path)
        return path

    def test_extract_single_file(self):
        self._create_zip_with_files()
        dest = os.path.join(self.tmpdir, 'out')
        self.handler.extract(['file1.txt'], dest)
        self.assertTrue(os.path.isfile(os.path.join(dest, 'file1.txt')))

    def test_extract_multiple_files(self):
        self._create_zip_with_files()
        dest = os.path.join(self.tmpdir, 'out')
        self.handler.extract(['file1.txt', 'dir/file2.txt'], dest)
        self.assertTrue(os.path.isfile(os.path.join(dest, 'file1.txt')))
        self.assertTrue(os.path.isfile(os.path.join(dest, 'dir', 'file2.txt')))

    def test_extract_with_progress_callback(self):
        self._create_zip_with_files()
        dest = os.path.join(self.tmpdir, 'out')
        calls = []
        self.handler.extract(['file1.txt', 'dir/file2.txt'], dest,
                             lambda c, t, m: calls.append((c, t, m)))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], (1, 2, 'file1.txt'))
        self.assertEqual(calls[1], (2, 2, 'dir/file2.txt'))

    def test_extract_no_archive_open(self):
        h = ArchiveHandler()
        with self.assertRaises(ValueError):
            h.extract(['file.txt'], '/tmp')

    def test_extract_from_tar(self):
        path = os.path.join(self.tmpdir, 'test.tar')
        with tarfile.open(path, 'w') as tf:
            tf.addfile(tarfile.TarInfo('f.txt'), io.BytesIO(b'data'))
        self.handler.open(path)
        dest = os.path.join(self.tmpdir, 'out')
        self.handler.extract(['f.txt'], dest)
        self.assertTrue(os.path.isfile(os.path.join(dest, 'f.txt')))


class TestExtractHere(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.handler = ArchiveHandler()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_extract_all_zip_to_archive_parent_dir(self):
        archive_dir = os.path.join(self.tmpdir, 'sub')
        os.makedirs(archive_dir)
        archive_path = os.path.join(archive_dir, 'test.zip')
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('file1.txt', b'content1')
            zf.writestr('dir/file2.txt', b'content2')

        self.handler.open(archive_path)
        all_members = [e.name for e in self.handler.entries]
        dest = os.path.dirname(archive_path)
        self.handler.extract(all_members, dest)

        self.assertTrue(os.path.isfile(os.path.join(dest, 'file1.txt')))
        self.assertTrue(os.path.isfile(os.path.join(dest, 'dir', 'file2.txt')))

    def test_extract_all_tar_to_archive_parent_dir(self):
        archive_dir = os.path.join(self.tmpdir, 'sub')
        os.makedirs(archive_dir)
        archive_path = os.path.join(archive_dir, 'test.tar')
        with tarfile.open(archive_path, 'w') as tf:
            tf.addfile(tarfile.TarInfo('a.txt'), io.BytesIO(b'data_a'))
            t = tarfile.TarInfo('nested/')
            t.type = tarfile.DIRTYPE
            tf.addfile(t)
            tf.addfile(tarfile.TarInfo('nested/b.txt'), io.BytesIO(b'data_b'))

        self.handler.open(archive_path)
        all_members = [e.name for e in self.handler.entries]
        dest = os.path.dirname(archive_path)
        self.handler.extract(all_members, dest)

        self.assertTrue(os.path.isfile(os.path.join(dest, 'a.txt')))
        self.assertTrue(os.path.isfile(os.path.join(dest, 'nested', 'b.txt')))

    def test_extract_all_in_subdir_of_archive_dir(self):
        archive_path = os.path.join(self.tmpdir, 'root.zip')
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('x.txt', b'x')

        self.handler.open(archive_path)
        all_members = [e.name for e in self.handler.entries]
        dest = os.path.join(self.tmpdir, 'target')
        os.makedirs(dest)
        self.handler.extract(all_members, dest)

        self.assertTrue(os.path.isfile(os.path.join(dest, 'x.txt')))

    def test_extract_here_all_members_listed(self):
        archive_path = os.path.join(self.tmpdir, 'test.zip')
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('f1.txt', b'1')
            zf.writestr('f2.txt', b'2')

        self.handler.open(archive_path)
        all_members = [e.name for e in self.handler.entries]
        self.assertEqual(sorted(all_members), ['f1.txt', 'f2.txt'])


class TestArchiveHandlerCreateArchive(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.handler = ArchiveHandler()
        # create source files
        src = os.path.join(self.tmpdir, 'src')
        os.makedirs(src)
        for f in ['a.txt', 'b.txt']:
            with open(os.path.join(src, f), 'w') as fh:
                fh.write(f'content of {f}')
        self.src_dir = src

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _file_paths(self, *names):
        return [os.path.join(self.src_dir, n) for n in names]

    def test_create_zip(self):
        out = os.path.join(self.tmpdir, 'out.zip')
        self.handler.create_archive(out, self._file_paths('a.txt', 'b.txt'), 'zip')
        self.assertTrue(os.path.isfile(out))
        with zipfile.ZipFile(out, 'r') as zf:
            names = zf.namelist()
            self.assertIn('a.txt', names)
            self.assertIn('b.txt', names)

    def test_create_tar(self):
        out = os.path.join(self.tmpdir, 'out.tar')
        self.handler.create_archive(out, self._file_paths('a.txt'), 'tar')
        self.assertTrue(os.path.isfile(out))
        with tarfile.open(out, 'r') as tf:
            names = tf.getnames()
            self.assertIn('a.txt', names)

    def test_create_tar_gz(self):
        out = os.path.join(self.tmpdir, 'out.tar.gz')
        self.handler.create_archive(out, self._file_paths('a.txt'), 'tar.gz')
        self.assertTrue(os.path.isfile(out))
        with tarfile.open(out, 'r:gz') as tf:
            names = tf.getnames()
            self.assertIn('a.txt', names)

    def test_create_with_folder(self):
        out = os.path.join(self.tmpdir, 'out.zip')
        self.handler.create_archive(out, [self.src_dir], 'zip')
        self.assertTrue(os.path.isfile(out))
        with zipfile.ZipFile(out, 'r') as zf:
            names = zf.namelist()
            self.assertIn('src/b.txt', names)
            self.assertIn('src/a.txt', names)

    def test_create_with_progress_callback(self):
        out = os.path.join(self.tmpdir, 'out.zip')
        calls = []
        self.handler.create_archive(out, self._file_paths('a.txt', 'b.txt'), 'zip',
                                    lambda c, t, m: calls.append((c, t, m)))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], 1)
        self.assertEqual(calls[1][0], 2)

    def test_create_empty_file_list(self):
        out = os.path.join(self.tmpdir, 'empty.zip')
        self.handler.create_archive(out, [], 'zip')
        self.assertTrue(os.path.isfile(out))
        with zipfile.ZipFile(out, 'r') as zf:
            self.assertEqual(len(zf.namelist()), 0)


class TestArchiveHandlerDelete(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.handler = ArchiveHandler()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_zip(self, name='test.zip'):
        path = os.path.join(self.tmpdir, name)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('keep.txt', b'keep')
            zf.writestr('remove.txt', b'remove')
        return path

    def test_delete_from_zip(self):
        path = self._create_zip()
        self.handler.open(path)
        self.handler.delete_members(['remove.txt'])
        entries = self.handler.entries
        names = [e.name for e in entries]
        self.assertIn('keep.txt', names)
        self.assertNotIn('remove.txt', names)
        # verify file on disk updated
        with zipfile.ZipFile(path, 'r') as zf:
            self.assertIn('keep.txt', zf.namelist())
            self.assertNotIn('remove.txt', zf.namelist())

    def test_delete_no_archive_open(self):
        h = ArchiveHandler()
        with self.assertRaises(ValueError):
            h.delete_members(['file.txt'])

    def test_delete_non_existent_member(self):
        path = self._create_zip()
        self.handler.open(path)
        self.handler.delete_members(['nonexistent.txt'])
        names = [e.name for e in self.handler.entries]
        self.assertIn('keep.txt', names)
        self.assertIn('remove.txt', names)


class TestArchiveHandlerGetMemberInfo(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.handler = ArchiveHandler()
        path = os.path.join(self.tmpdir, 'test.zip')
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('file.txt', b'hello')
        self.handler.open(path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_get_existing_member(self):
        entry = self.handler.get_member_info('file.txt')
        self.assertIsNotNone(entry)
        self.assertEqual(entry.name, 'file.txt')

    def test_get_non_existing_member(self):
        entry = self.handler.get_member_info('nope.txt')
        self.assertIsNone(entry)


class TestArchiveHandlerEdgeCases(unittest.TestCase):
    def test_open_empty_zip(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, 'empty.zip')
            with zipfile.ZipFile(path, 'w') as zf:
                pass
            h = ArchiveHandler()
            entries = h.open(path)
            self.assertEqual(len(entries), 0)
        finally:
            shutil.rmtree(tmpdir)

    def test_open_zip_with_long_filename(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, 'long.zip')
            long_name = 'a' * 200 + '.txt'
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(long_name, b'x')
            h = ArchiveHandler()
            entries = h.open(path)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].name, long_name)
        finally:
            shutil.rmtree(tmpdir)

    def test_open_corrupted_zip(self):
        tmpdir = tempfile.mkdtemp()
        try:
            path = os.path.join(tmpdir, 'bad.zip')
            with open(path, 'wb') as f:
                f.write(b'this is not a zip file')
            h = ArchiveHandler()
            with self.assertRaises(Exception):
                h.open(path)
        finally:
            shutil.rmtree(tmpdir)


if __name__ == '__main__':
    unittest.main()
