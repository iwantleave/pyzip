import zipfile
import tarfile
import py7zr
import pyzipper
import os
import time
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ArchiveEntry:
    name: str
    size: int
    packed_size: int
    modified: float
    is_dir: bool
    crc: str = ''

    @property
    def modified_str(self) -> str:
        return time.strftime('%Y-%m-%d %H:%M', time.localtime(self.modified))

    @property
    def size_str(self) -> str:
        if self.is_dir:
            return ''
        return format_size(self.size)

    @property
    def packed_str(self) -> str:
        if self.is_dir:
            return ''
        return format_size(self.packed_size)

    @property
    def type_str(self) -> str:
        if self.is_dir:
            return 'Folder'
        ext = Path(self.name).suffix.lower()
        type_map = {
            '.txt': 'Text Document',
            '.py': 'Python Source',
            '.c': 'C Source',
            '.h': 'C Header',
            '.cpp': 'C++ Source',
            '.hpp': 'C++ Header',
            '.md': 'Markdown',
            '.json': 'JSON File',
            '.xml': 'XML File',
            '.html': 'HTML Document',
            '.css': 'Stylesheet',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.png': 'PNG Image',
            '.jpg': 'JPEG Image',
            '.jpeg': 'JPEG Image',
            '.gif': 'GIF Image',
            '.svg': 'SVG Image',
            '.pdf': 'PDF Document',
            '.doc': 'Word Document',
            '.docx': 'Word Document',
            '.xls': 'Excel Spreadsheet',
            '.xlsx': 'Excel Spreadsheet',
            '.zip': 'ZIP Archive',
            '.tar': 'TAR Archive',
            '.gz': 'GZip Archive',
            '.bz2': 'BZip2 Archive',
            '.xz': 'XZ Archive',
            '.so': 'Shared Library',
            '.o': 'Object File',
            '.exe': 'Executable',
            '.7z': '7Z Archive',
        }
        return type_map.get(ext, f'{ext.upper()} File') if ext else 'File'


def format_size(size: int) -> str:
    if size < 1024:
        return f'{size} B'
    elif size < 1024 * 1024:
        return f'{size / 1024:.1f} KB'
    elif size < 1024 * 1024 * 1024:
        return f'{size / 1024 / 1024:.1f} MB'
    else:
        return f'{size / 1024 / 1024 / 1024:.2f} GB'


class ArchiveHandler:
    def __init__(self, password: Optional[str] = None):
        self.path: Optional[str] = None
        self.entries: List[ArchiveEntry] = []
        self.type: Optional[str] = None
        self.password: Optional[str] = password

    def open(self, path: str, password: Optional[str] = None) -> List[ArchiveEntry]:
        if password is not None:
            self.password = password
        if not os.path.isfile(path):
            raise FileNotFoundError(f'File not found: {path}')
        self.path = path
        self.entries = []
        path_lower = path.lower()

        if path_lower.endswith('.zip'):
            self.type = 'zip'
            self._read_zip()
        elif path_lower.endswith('.tar.gz') or path_lower.endswith('.tgz'):
            self.type = 'tar.gz'
            self._read_tar('r:gz')
        elif path_lower.endswith('.tar.bz2') or path_lower.endswith('.tbz2'):
            self.type = 'tar.bz2'
            self._read_tar('r:bz2')
        elif path_lower.endswith('.tar.xz') or path_lower.endswith('.txz'):
            self.type = 'tar.xz'
            self._read_tar('r:xz')
        elif path_lower.endswith('.tar'):
            self.type = 'tar'
            self._read_tar('r:')
        elif path_lower.endswith('.7z'):
            self.type = '7z'
            self._read_7z()
        else:
            raise ValueError(f'Unsupported archive format: {path}')

        return self.entries

    def _read_zip(self):
        if self.password:
            zf = pyzipper.AESZipFile(self.path, 'r')
            zf.setpassword(self.password.encode())
        else:
            zf = zipfile.ZipFile(self.path, 'r')
        with zf:
            for info in zf.infolist():
                dt = info.date_time
                try:
                    mtime = time.mktime(dt + (0, 0, -1))
                except (OverflowError, ValueError, OSError):
                    mtime = 0.0
                crc_val = ''
                if info.CRC != 0 or not self.password:
                    crc_val = f'{info.CRC:08X}'
                entry = ArchiveEntry(
                    name=info.filename,
                    size=info.file_size,
                    packed_size=info.compress_size,
                    modified=mtime,
                    is_dir=info.filename.endswith('/'),
                    crc=crc_val,
                )
                self.entries.append(entry)

    def _read_tar(self, mode: str):
        with tarfile.open(self.path, mode) as tf:
            for info in tf.getmembers():
                mtime = info.mtime if info.mtime else 0.0
                entry = ArchiveEntry(
                    name=info.name,
                    size=info.size,
                    packed_size=info.size,
                    modified=mtime,
                    is_dir=info.isdir(),
                )
                self.entries.append(entry)

    def _read_7z(self):
        kwargs = {}
        if self.password:
            kwargs['password'] = self.password
        with py7zr.SevenZipFile(self.path, 'r', **kwargs) as sz:
            for info in sz.list():
                modified = 0.0
                if info.creationtime:
                    modified = info.creationtime.timestamp()
                crc_str = f'{info.crc32:08X}' if info.crc32 is not None else ''
                packed = info.compressed if info.compressed is not None else 0
                entry = ArchiveEntry(
                    name=info.filename,
                    size=info.uncompressed,
                    packed_size=packed,
                    modified=modified,
                    is_dir=info.is_directory,
                    crc=crc_str,
                )
                self.entries.append(entry)

    def extract(self, members: List[str], dest_dir: str, progress_callback=None,
                password: Optional[str] = None):
        if not self.path:
            raise ValueError('No archive open')
        if password is not None:
            self.password = password

        os.makedirs(dest_dir, exist_ok=True)
        total = len(members)
        path_lower = self.path.lower()

        if path_lower.endswith('.zip'):
            if self.password:
                zf = pyzipper.AESZipFile(self.path, 'r')
                zf.setpassword(self.password.encode())
            else:
                zf = zipfile.ZipFile(self.path, 'r')
            with zf:
                for i, member in enumerate(members):
                    zf.extract(member, dest_dir)
                    if progress_callback:
                        progress_callback(i + 1, total, member)
        elif path_lower.endswith('.7z'):
            kwargs = {}
            if self.password:
                kwargs['password'] = self.password
            with py7zr.SevenZipFile(self.path, 'r', **kwargs) as sz:
                sz.extract(dest_dir, targets=members)
                for i, member in enumerate(members):
                    if progress_callback:
                        progress_callback(i + 1, total, member)
        else:
            if self.password:
                raise ValueError('Password encryption is not supported for this archive format')
            mode = 'r:'
            if self.type == 'tar.gz':
                mode = 'r:gz'
            elif self.type == 'tar.bz2':
                mode = 'r:bz2'
            elif self.type == 'tar.xz':
                mode = 'r:xz'
            with tarfile.open(self.path, mode) as tf:
                for i, member in enumerate(members):
                    tf.extract(member, dest_dir)
                    if progress_callback:
                        progress_callback(i + 1, total, member)

    def create_archive(self, archive_path: str, file_paths: List[str],
                       archive_type: str, progress_callback=None,
                       password: Optional[str] = None):
        if password is not None:
            self.password = password

        total = len(file_paths)
        base_dir = os.path.dirname(os.path.commonpath(file_paths)) if file_paths else ''

        if archive_type == 'zip':
            if self.password:
                zf = pyzipper.AESZipFile(archive_path, 'w',
                                         compression=zipfile.ZIP_DEFLATED,
                                         encryption=pyzipper.WZ_AES)
                zf.setpassword(self.password.encode())
            else:
                zf = zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED)
            with zf:
                for i, fp in enumerate(file_paths):
                    if os.path.isfile(fp):
                        arcname = os.path.basename(fp)
                        zf.write(fp, arcname)
                    elif os.path.isdir(fp):
                        for root, dirs, filenames in os.walk(fp):
                            for fn in filenames:
                                full = os.path.join(root, fn)
                                arcname = os.path.relpath(full, os.path.dirname(fp))
                                zf.write(full, arcname)
                    if progress_callback:
                        progress_callback(i + 1, total, fp)
        elif archive_type == '7z':
            kwargs = {}
            if self.password:
                kwargs['password'] = self.password
            with py7zr.SevenZipFile(archive_path, 'w', **kwargs) as sz:
                for i, fp in enumerate(file_paths):
                    if os.path.isfile(fp):
                        sz.write(fp, os.path.basename(fp))
                    elif os.path.isdir(fp):
                        sz.write(fp, os.path.basename(fp))
                    if progress_callback:
                        progress_callback(i + 1, total, fp)
        elif archive_type in ('tar', 'tar.gz', 'tar.bz2', 'tar.xz'):
            if self.password:
                raise ValueError('Password encryption is not supported for this archive format')
            mode_map = {
                'tar': 'w',
                'tar.gz': 'w:gz',
                'tar.bz2': 'w:bz2',
                'tar.xz': 'w:xz',
            }
            mode = mode_map[archive_type]
            with tarfile.open(archive_path, mode) as tf:
                for i, fp in enumerate(file_paths):
                    if os.path.isfile(fp):
                        tf.add(fp, os.path.basename(fp))
                    elif os.path.isdir(fp):
                        tf.add(fp, os.path.basename(fp))
                    if progress_callback:
                        progress_callback(i + 1, total, fp)

    def delete_members(self, members: List[str], password: Optional[str] = None):
        if not self.path:
            raise ValueError('No archive open')
        if password is not None:
            self.password = password

        temp_fd, temp_path = tempfile.mkstemp(suffix=f'_{os.path.basename(self.path)}')
        os.close(temp_fd)

        try:
            path_lower = self.path.lower()
            if path_lower.endswith('.zip'):
                if self.password:
                    src = pyzipper.AESZipFile(self.path, 'r')
                    src.setpassword(self.password.encode())
                    dst = pyzipper.AESZipFile(temp_path, 'w',
                                              compression=zipfile.ZIP_DEFLATED,
                                              encryption=pyzipper.WZ_AES)
                    dst.setpassword(self.password.encode())
                else:
                    src = zipfile.ZipFile(self.path, 'r')
                    dst = zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED)
                with src, dst:
                    for info in src.infolist():
                        if info.filename not in members:
                            dst.writestr(info, src.read(info.filename))
            elif path_lower.endswith('.7z'):
                extract_tmp = tempfile.mkdtemp(suffix='_7z_delete')
                try:
                    kwargs = {}
                    if self.password:
                        kwargs['password'] = self.password
                    with py7zr.SevenZipFile(self.path, 'r', **kwargs) as src:
                        keep = [n for n in src.getnames() if n not in members]
                        if keep:
                            src.extract(path=extract_tmp, targets=keep)
                    for root, _dirs, files in os.walk(extract_tmp):
                        for fn in files:
                            os.chmod(os.path.join(root, fn), 0o644)
                    kwargs_w = {}
                    if self.password:
                        kwargs_w['password'] = self.password
                    with py7zr.SevenZipFile(temp_path, 'w', **kwargs_w) as dst:
                        for root, _dirs, files in os.walk(extract_tmp):
                            for fn in files:
                                full = os.path.join(root, fn)
                                arcname = os.path.relpath(full, extract_tmp)
                                dst.write(full, arcname)
                finally:
                    shutil.rmtree(extract_tmp, ignore_errors=True)
            else:
                if self.password:
                    raise ValueError('Password encryption is not supported for this archive format')
                mode = 'r:'
                wmode = 'w:'
                if self.type == 'tar.gz':
                    mode = 'r:gz'
                    wmode = 'w:gz'
                elif self.type == 'tar.bz2':
                    mode = 'r:bz2'
                    wmode = 'w:bz2'
                elif self.type == 'tar.xz':
                    mode = 'r:xz'
                    wmode = 'w:xz'
                with tarfile.open(self.path, mode) as src:
                    with tarfile.open(temp_path, wmode) as dst:
                        for member in src.getmembers():
                            if member.name not in members:
                                f = src.extractfile(member)
                                dst.addfile(member, f)

            shutil.move(temp_path, self.path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        self.open(self.path)

    def get_member_info(self, name: str) -> Optional[ArchiveEntry]:
        for entry in self.entries:
            if entry.name == name:
                return entry
        return None
