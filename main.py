import os
import sys
import time
import traceback
from pathlib import Path
from typing import Optional, List, Tuple

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Gio, GLib, Gdk, Pango, GObject

from archive_handler import ArchiveHandler, ArchiveEntry, format_size


class ProgressDialog(Gtk.Window):
    def __init__(self, parent, title):
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(420, 130)
        self.set_resizable(False)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        self.set_child(vbox)

        self.file_label = Gtk.Label(label='')
        self.file_label.set_halign(Gtk.Align.START)
        self.file_label.set_ellipsize(Pango.EllipsizeMode.END)
        vbox.append(self.file_label)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        vbox.append(self.progress_bar)

    def update(self, current, total, message):
        self.file_label.set_text(message)
        if total > 0:
            self.progress_bar.set_fraction(current / total)
            self.progress_bar.set_text(f'{current} / {total}')
        while GLib.MainContext.default().iteration(False):
            pass


class FileItem(GObject.Object):
    __gtype_name__ = 'FileItem'

    icon = GObject.Property(type=str, default='text-x-generic-symbolic')
    name = GObject.Property(type=str, default='')
    size = GObject.Property(type=str, default='')
    packed = GObject.Property(type=str, default='')
    ftype = GObject.Property(type=str, default='Folder')
    modified = GObject.Property(type=str, default='')
    crc = GObject.Property(type=str, default='')
    is_dir = GObject.Property(type=bool, default=False)
    full_path = GObject.Property(type=str, default='')
    raw_size = GObject.Property(type=int, default=0)
    raw_packed = GObject.Property(type=int, default=0)
    modified_raw = GObject.Property(type=float, default=0.0)


ARCHIVE_EXTENSIONS = {'.zip', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz', '.7z'}


def get_file_type(name: str) -> str:
    ext = Path(name).suffix.lower()
    m = {
        '.txt': 'Text Document',
        '.py': 'Python Source', '.c': 'C Source', '.h': 'C Header',
        '.cpp': 'C++ Source', '.hpp': 'C++ Header',
        '.md': 'Markdown', '.json': 'JSON File', '.xml': 'XML File',
        '.html': 'HTML Document', '.css': 'Stylesheet',
        '.js': 'JavaScript', '.ts': 'TypeScript',
        '.png': 'PNG Image', '.jpg': 'JPEG Image', '.jpeg': 'JPEG Image',
        '.gif': 'GIF Image', '.svg': 'SVG Image',
        '.pdf': 'PDF Document',
        '.doc': 'Word Document', '.docx': 'Word Document',
        '.xls': 'Excel Spreadsheet', '.xlsx': 'Excel Spreadsheet',
        '.zip': 'ZIP Archive', '.tar': 'TAR Archive',
        '.gz': 'GZip Archive', '.bz2': 'BZip2 Archive', '.xz': 'XZ Archive',
        '.7z': '7Z Archive',
    }
    return m.get(ext, f'{ext.upper()} File') if ext else 'File'


def get_icon_for_file(name: str, ext: str) -> str:
    m = {
        '.txt': 'text-x-generic-symbolic',
        '.py': 'text-x-python-symbolic',
        '.c': 'text-x-c-symbolic', '.h': 'text-x-c-symbolic',
        '.cpp': 'text-x-c-symbolic', '.hpp': 'text-x-c-symbolic',
        '.md': 'text-x-generic-symbolic', '.json': 'text-x-generic-symbolic',
        '.xml': 'text-x-generic-symbolic', '.html': 'text-html-symbolic',
        '.css': 'text-x-generic-symbolic', '.js': 'text-x-javascript-symbolic',
        '.ts': 'text-x-javascript-symbolic',
        '.png': 'image-x-generic-symbolic', '.jpg': 'image-x-generic-symbolic',
        '.jpeg': 'image-x-generic-symbolic', '.gif': 'image-x-generic-symbolic',
        '.svg': 'image-x-generic-symbolic',
        '.pdf': 'x-office-document-symbolic',
        '.doc': 'x-office-document-symbolic', '.docx': 'x-office-document-symbolic',
        '.xls': 'x-office-spreadsheet-symbolic', '.xlsx': 'x-office-spreadsheet-symbolic',
        '.zip': 'application-x-archive-symbolic', '.tar': 'application-x-archive-symbolic',
        '.gz': 'application-x-archive-symbolic', '.bz2': 'application-x-archive-symbolic',
        '.xz': 'application-x-archive-symbolic', '.7z': 'application-x-archive-symbolic',
    }
    return m.get(ext, 'text-x-generic-symbolic')


def is_archive(path: str) -> bool:
    p = path.lower()
    return any(p.endswith(ext) for ext in ARCHIVE_EXTENSIONS)


class ExtractDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, archive_name: str):
        super().__init__(title=f'Extract - {archive_name}', transient_for=parent, modal=True)
        self.set_default_size(450, 200)
        self._result = None

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.set_margin_top(12)
        area.set_margin_bottom(12)

        area.append(self._make_label('Destination directory:'))
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.dir_entry = Gtk.Entry()
        self.dir_entry.set_text(os.path.expanduser('~'))
        self.dir_entry.set_hexpand(True)
        hbox.append(self.dir_entry)
        browse_btn = Gtk.Button(label='Browse...')
        browse_btn.connect('clicked', self._on_browse, parent)
        hbox.append(browse_btn)
        area.append(hbox)

        self.overwrite_check = Gtk.CheckButton(label='Overwrite existing files')
        self.overwrite_check.set_active(True)
        area.append(self.overwrite_check)

        area.append(Gtk.Label())
        self.add_button('Cancel', Gtk.ResponseType.CANCEL)
        self.add_button('Extract', Gtk.ResponseType.OK)

    def _make_label(self, text):
        lbl = Gtk.Label(label=text)
        lbl.set_halign(Gtk.Align.START)
        return lbl

    def _on_browse(self, btn, parent):
        dialog = Gtk.FileDialog.new()
        dialog.set_title('Select destination')
        def on_open(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
                self.dir_entry.set_text(folder.get_path())
            except GLib.Error:
                pass
        dialog.select_folder(parent, None, on_open)

    def get_result(self):
        return self.dir_entry.get_text().strip() if self._result == Gtk.ResponseType.OK else None

    def do_response(self, response):
        self._result = response


class AddDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, current_dir: str):
        super().__init__(title='Add to Archive', transient_for=parent, modal=True)
        self.set_default_size(500, 400)
        self._result = None

        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.set_margin_top(12)
        area.set_margin_bottom(12)

        area.append(self._make_label('Archive name:'))
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(os.path.join(current_dir, 'archive.zip'))
        area.append(self.name_entry)

        area.append(self._make_label('Archive format:'))
        self.format_combo = Gtk.DropDown(model=Gtk.StringList.new(['ZIP', 'TAR', 'TAR.GZ', '7Z']))
        self.format_combo.set_selected(0)
        area.append(self.format_combo)

        area.append(self._make_label('Files to add:'))
        self.file_store = Gtk.ListStore.new([GObject.TYPE_STRING, GObject.TYPE_STRING])
        self.file_view = Gtk.TreeView(model=self.file_store)
        col = Gtk.TreeViewColumn('File', Gtk.CellRendererText(), text=1)
        self.file_view.append_column(col)
        self.file_view.set_hexpand(True)
        self.file_view.set_vexpand(True)

        sw = Gtk.ScrolledWindow()
        sw.set_child(self.file_view)
        sw.set_min_content_height(150)
        area.append(sw)

        btn_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for lbl, cb in [('Add Files...', self._on_add_files),
                        ('Add Folder...', self._on_add_dir),
                        ('Remove', self._on_remove)]:
            b = Gtk.Button(label=lbl)
            b.connect('clicked', cb, parent)
            btn_hbox.append(b)
        area.append(btn_hbox)

        self.add_button('Cancel', Gtk.ResponseType.CANCEL)
        self.add_button('Create', Gtk.ResponseType.OK)

    def _make_label(self, text):
        lbl = Gtk.Label(label=text)
        lbl.set_halign(Gtk.Align.START)
        return lbl

    def _on_add_files(self, btn, parent):
        dialog = Gtk.FileDialog.new()
        dialog.set_title('Select files')
        dialog.set_modal(True)
        def on_open(dlg, result):
            try:
                files = dlg.open_multiple_finish(result)
                for f in files:
                    p = f.get_path()
                    self.file_store.append([p, os.path.basename(p)])
            except GLib.Error:
                pass
        dialog.open_multiple(parent, None, on_open)

    def _on_add_dir(self, btn, parent):
        dialog = Gtk.FileDialog.new()
        dialog.set_title('Select folder')
        dialog.set_modal(True)
        def on_open(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
                p = folder.get_path()
                self.file_store.append([p, os.path.basename(p) + '/'])
            except GLib.Error:
                pass
        dialog.select_folder(parent, None, on_open)

    def _on_remove(self, btn, parent=None):
        sel = self.file_view.get_selection()
        m, it = sel.get_selected()
        if it:
            self.file_store.remove(it)

    def get_result(self):
        if self._result == Gtk.ResponseType.OK:
            name = self.name_entry.get_text().strip()
            fmt = {0: 'zip', 1: 'tar', 2: 'tar.gz', 3: '7z'}[self.format_combo.get_selected()]
            files = [row[0] for row in self.file_store]
            return name, fmt, files
        return None

    def do_response(self, response):
        self._result = response


class InfoDialog(Gtk.Dialog):
    def __init__(self, parent, archive_path, entries):
        title = f'Info - {os.path.basename(archive_path)}'
        super().__init__(title=title, transient_for=parent, modal=True)
        self.set_default_size(400, 300)

        area = self.get_content_area()
        area.set_spacing(6)
        area.set_margin_start(12)
        area.set_margin_end(12)
        area.set_margin_top(12)
        area.set_margin_bottom(12)

        total_files = sum(1 for e in entries if not e.is_dir)
        total_dirs = sum(1 for e in entries if e.is_dir)
        total_size = sum(e.size for e in entries if not e.is_dir)
        total_packed = sum(e.packed_size for e in entries if not e.is_dir)

        txt = (
            f'Archive: {archive_path}\n'
            f'Format: {Path(archive_path).suffix}\n'
            f'Files: {total_files}\n'
            f'Folders: {total_dirs}\n'
            f'Total size: {format_size(total_size)}\n'
            f'Packed size: {format_size(total_packed)}\n'
        )
        if total_size > 0:
            ratio = (1 - total_packed / total_size) * 100
            txt += f'Compression ratio: {ratio:.1f}%\n'

        lbl = Gtk.Label(label=txt)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_valign(Gtk.Align.START)
        lbl.set_selectable(True)
        area.append(lbl)

        self.add_button('Close', Gtk.ResponseType.CLOSE)


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app)
        self.set_title('PyZip - Archive Manager')
        self.set_default_size(1000, 650)

        self.archive_handler = ArchiveHandler()
        self.current_path: str = os.path.expanduser('~')
        self.mode: int = 0  # 0=FS, 1=Archive
        self.archive_internal_path: str = ''

        self._setup_css()
        self._setup_ui()
        self._load_directory(self.current_path)

    def _setup_css(self):
        css = '''
        .status-bar { font-size: 9pt; padding: 2px 6px; }
        '''
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _setup_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(vbox)
        self._setup_headerbar()
        self._register_menu_actions()
        self._setup_menu_bar(vbox)
        self._setup_toolbar(vbox)
        self._setup_address_bar(vbox)
        self._setup_file_list(vbox)
        self._setup_status_bar(vbox)

    def _on_not_implemented(self, action=None, param=None):
        self._show_message('This feature is not yet implemented.')

    def _on_close_archive(self, action=None, param=None):
        if self.mode == 1:
            parent = os.path.dirname(self.current_path)
            self.archive_handler = ArchiveHandler()
            self.mode = 0
            self._load_directory(parent)

    def _register_menu_actions(self):
        action_defs = [
            ('open', self._on_open_archive),
            ('close', self._on_close_archive),
            ('password', self._on_not_implemented),
            ('set_default', self._on_not_implemented),
            ('add', self._on_add),
            ('extract', self._on_extract),
            ('extract_here', self._on_extract_here),
            ('test', self._on_not_implemented),
            ('view', self._on_not_implemented),
            ('delete', self._on_delete),
            ('find', self._on_not_implemented),
            ('info', self._on_info),
            ('repair', self._on_not_implemented),
            ('convert', self._on_not_implemented),
            ('benchmark', self._on_not_implemented),
            ('settings', self._on_not_implemented),
            ('add_fav', self._on_not_implemented),
            ('org_fav', self._on_not_implemented),
            ('help_topics', self._on_not_implemented),
            ('about', self._on_not_implemented),
        ]
        for name, cb in action_defs:
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', lambda a, p, cb=cb: cb())
            self.add_action(action)

    def _setup_menu_bar(self, parent):
        def sub(*items):
            m = Gio.Menu()
            for item in items:
                if item is None:
                    m.append_section(None, Gio.Menu())
                elif isinstance(item, tuple):
                    m.append(*item)
            return m

        menu_bar = Gio.Menu()

        menu_bar.append_submenu('File', sub(
            ('Open Archive…', 'win.open'),
            ('Close Archive', 'win.close'),
            None,
            ('Password…', 'win.password'),
            None,
            ('Set Default…', 'win.set_default'),
            None,
            ('Exit', 'app.quit'),
        ))

        menu_bar.append_submenu('Commands', sub(
            ('Add…', 'win.add'),
            ('Extract…', 'win.extract'),
            ('Extract Here', 'win.extract_here'),
            None,
            ('Test', 'win.test'),
            ('View…', 'win.view'),
            ('Delete', 'win.delete'),
            ('Find…', 'win.find'),
            ('Info', 'win.info'),
            None,
            ('Repair…', 'win.repair'),
        ))

        menu_bar.append_submenu('Tools', sub(
            ('Convert Archives…', 'win.convert'),
            None,
            ('Benchmark…', 'win.benchmark'),
            None,
            ('Settings…', 'win.settings'),
        ))

        menu_bar.append_submenu('Favorites', sub(
            ('Add to Favorites', 'win.add_fav'),
            ('Organize Favorites…', 'win.org_fav'),
        ))

        menu_bar.append_submenu('Options', sub(
            ('Settings…', 'win.settings'),
        ))

        menu_bar.append_submenu('Help', sub(
            ('Help Topics', 'win.help_topics'),
            None,
            ('About PyZip…', 'win.about'),
        ))

        popover = Gtk.PopoverMenuBar.new_from_model(menu_bar)
        parent.append(popover)

    def _setup_headerbar(self):
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

    def _setup_toolbar(self, parent):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hbox.set_margin_start(6)
        hbox.set_margin_end(6)
        hbox.set_margin_top(6)
        hbox.set_margin_bottom(3)

        for lbl, tip, cb in [
            ('Open', 'Open archive', self._on_open_archive),
            ('Extract', 'Extract selected files', self._on_extract),
            ('Extract Here', 'Extract all to archive folder', self._on_extract_here),
            ('Add', 'Create archive', self._on_add),
            ('Delete', 'Delete selected from archive', self._on_delete),
            ('Up', 'Go to parent directory', self._on_up),
            ('Info', 'Show information', self._on_info),
        ]:
            btn = Gtk.Button(label=lbl)
            btn.set_tooltip_text(tip)
            hbox.append(btn)
            btn.connect('clicked', cb)

        parent.append(hbox)

    def _setup_address_bar(self, parent):
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hbox.set_margin_start(6)
        hbox.set_margin_end(6)
        hbox.set_margin_top(6)
        hbox.set_margin_bottom(3)

        self.address_entry = Gtk.Entry()
        self.address_entry.set_hexpand(True)
        self.address_entry.set_text(self.current_path)
        self.address_entry.connect('activate', self._on_address_activate)
        hbox.append(self.address_entry)

        go_btn = Gtk.Button(label='Go')
        go_btn.connect('clicked', self._on_go)
        hbox.append(go_btn)

        parent.append(hbox)

    # ---- ColumnView Setup ----

    def _setup_file_list(self, parent):
        self.file_model = Gio.ListStore.new(FileItem)

        sort_model = Gtk.SortListModel(model=self.file_model, sorter=Gtk.ColumnViewSorter())
        selection = Gtk.MultiSelection.new(sort_model)
        selection.connect('selection-changed', self._on_selection_changed)

        self.column_view = Gtk.ColumnView(model=selection)
        self.column_view.set_vexpand(True)
        self.column_view.set_hexpand(True)
        self.column_view.connect('activate', self._on_row_activated)

        # Column definitions: (title, width, factory, expand, sort_prop, is_numeric)
        cols = [
            ('', 32, self._make_icon_factory(), False, None, False),
            ('Name', 250, self._make_text_factory('name'), True, 'name', False),
            ('Size', 80, self._make_text_factory('size'), False, 'raw_size', True),
            ('Packed', 80, self._make_text_factory('packed'), False, 'raw_packed', True),
            ('Type', 120, self._make_text_factory('ftype'), False, 'ftype', False),
            ('Modified', 140, self._make_text_factory('modified'), False, 'modified_raw', True),
            ('CRC', 80, self._make_text_factory('crc'), False, 'crc', False),
        ]

        for title, width, factory, expand, sort_prop, is_num in cols:
            col = Gtk.ColumnViewColumn(title=title, factory=factory)
            col.set_resizable(True)
            col.set_fixed_width(width)
            if expand:
                col.set_expand(True)
            if sort_prop:
                col.set_sorter(self._make_sorter(sort_prop, is_num))
            self.column_view.append_column(col)

        sw = Gtk.ScrolledWindow()
        sw.set_child(self.column_view)
        parent.append(sw)

        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect('pressed', self._on_right_click)
        self.column_view.add_controller(right_click)

    def _make_sorter(self, prop_name, is_numeric=False):
        def compare(a, b):
            va = getattr(a.props, prop_name, 0 if is_numeric else '')
            vb = getattr(b.props, prop_name, 0 if is_numeric else '')
            if va < vb:
                return Gtk.Ordering.SMALLER
            elif va > vb:
                return Gtk.Ordering.LARGER
            return Gtk.Ordering.EQUAL
        return Gtk.CustomSorter.new(compare)

    def _make_icon_factory(self):
        f = Gtk.SignalListItemFactory()
        f.connect('setup', self._icon_setup)
        f.connect('bind', self._icon_bind)
        return f

    def _icon_setup(self, factory, item):
        img = Gtk.Image()
        item.set_child(img)

    def _icon_bind(self, factory, item):
        img = item.get_child()
        fi = item.get_item()
        img.set_from_icon_name(fi.props.icon)

    def _make_text_factory(self, prop_name):
        f = Gtk.SignalListItemFactory()
        f.connect('setup', lambda f, i: i.set_child(Gtk.Label(
            xalign=1.0 if prop_name in ('size', 'packed') else 0.0,
            ellipsize=Pango.EllipsizeMode.END,
        )))
        f.connect('bind', lambda f, i: self._text_bind(i, prop_name))
        return f

    def _text_bind(self, item, prop_name):
        lbl = item.get_child()
        fi = item.get_item()
        lbl.set_text(getattr(fi.props, prop_name, ''))

    def _append_file_item(self, fi: FileItem):
        self.file_model.append(fi)

    def _clear_model(self):
        n = self.file_model.get_n_items()
        if n > 0:
            self.file_model.splice(0, n, [])

    def _get_item(self, position: int) -> Optional[FileItem]:
        sel = self.column_view.get_model()
        sort_model = sel.get_model()
        if 0 <= position < sort_model.get_n_items():
            return sort_model.get_item(position)
        return None

    def _get_selected_items(self) -> List[FileItem]:
        sel = self.column_view.get_model()
        sort_model = sel.get_model()
        result = []
        for i in range(sort_model.get_n_items()):
            if sel.is_selected(i):
                result.append(sort_model.get_item(i))
        return result

    def _get_selected_paths(self) -> List[str]:
        return [fi.props.full_path for fi in self._get_selected_items()]

    def _get_file_item(self, position: int) -> Optional[FileItem]:
        return self._get_item(position)

    # ---- Event Handlers ----

    def _on_selection_changed(self, selection, position, n_items):
        pass

    def _on_row_activated(self, view, position):
        fi = self._get_item(position)
        if not fi:
            return

        if self.mode == 1:  # Archive mode
            if fi.props.is_dir:
                self.archive_internal_path = fi.props.name
                self._filter_archive_entries(fi.props.name)
            else:
                self._open_external(fi.props.full_path)
        else:
            path = fi.props.full_path
            if fi.props.is_dir:
                self._load_directory(path)
            elif is_archive(path):
                self._load_archive(path)
            else:
                self._open_external(path)

    def _on_right_click(self, gesture, n_press, x, y):
        menu = self._build_context_menu()
        popover = Gtk.PopoverMenu()
        popover.set_child(menu)
        popover.set_parent(self.column_view)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        popover.set_pointing_to(rect)
        popover.popup()

    def _on_address_activate(self, entry):
        path = entry.get_text().strip()
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            self._load_directory(path)
        elif os.path.isfile(path) and is_archive(path):
            self._load_archive(path)
        else:
            self._update_status(f'Invalid path: {path}')

    def _on_go(self, btn):
        self._on_address_activate(self.address_entry)

    def _on_up(self, btn=None):
        self._go_up()

    # ---- Status Bar ----

    def _setup_status_bar(self, parent):
        self.status_label = Gtk.Label(label='Ready')
        self.status_label.add_css_class('status-bar')
        self.status_label.set_margin_start(8)
        self.status_label.set_margin_end(8)
        self.status_label.set_margin_top(3)
        self.status_label.set_margin_bottom(3)
        self.status_label.set_halign(Gtk.Align.START)
        parent.append(self.status_label)

    def _update_status(self, text: str):
        self.status_label.set_text(text)

    # ---- Directory Loading ----

    def _load_directory(self, path: str):
        self.mode = 0
        self._clear_model()
        self.current_path = os.path.abspath(path)
        self.address_entry.set_text(self.current_path)
        self.set_title(f'PyZip - {self.current_path}')

        try:
            entries = sorted(os.scandir(self.current_path),
                             key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            self._update_status(f'Permission denied: {self.current_path}')
            return
        except FileNotFoundError:
            self._update_status(f'Not found: {self.current_path}')
            return

        file_count = 0
        dir_count = 0
        total_size = 0

        for entry in entries:
            try:
                is_dir_flag = entry.is_dir()
            except OSError:
                continue

            name = entry.name
            fpath = entry.path

            if is_dir_flag:
                fi = FileItem(icon='folder-symbolic', name=name, size='',
                              ftype='Folder', full_path=fpath,
                              is_dir=True, modified_raw=0.0)
                dir_count += 1
            else:
                try:
                    st = entry.stat()
                except OSError:
                    continue
                sz = st.st_size
                total_size += sz
                ext = Path(name).suffix.lower()
                fi = FileItem(
                    icon=get_icon_for_file(name, ext),
                    name=name,
                    size=format_size(sz),
                    ftype=get_file_type(name),
                    modified=time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime)),
                    full_path=fpath,
                    raw_size=sz,
                    modified_raw=st.st_mtime,
                )
                file_count += 1

            self._append_file_item(fi)

        self._update_status(
            f'Files: {file_count}, Folders: {dir_count}, '
            f'Total size: {format_size(total_size)}'
        )

    def _load_archive(self, path: str):
        self.mode = 1
        self.archive_internal_path = ''
        self._clear_model()
        self.current_path = os.path.abspath(path)
        self.address_entry.set_text(self.current_path)
        self.set_title(f'PyZip - {os.path.basename(path)}')

        try:
            entries = self.archive_handler.open(path)
        except Exception as e:
            self._update_status(f'Error opening archive: {e}')
            self.mode = 0
            self._load_directory(os.path.dirname(path))
            return

        file_count = 0
        dir_count = 0
        total_size = 0
        total_packed = 0

        for entry in entries:
            name = entry.name
            if entry.is_dir:
                fi = FileItem(icon='folder-symbolic', name=name,
                              ftype='Folder', full_path=name,
                              is_dir=True, modified=entry.modified_str,
                              modified_raw=entry.modified)
                dir_count += 1
            else:
                total_size += entry.size
                total_packed += entry.packed_size
                ext = Path(name).suffix.lower()
                fi = FileItem(
                    icon=get_icon_for_file(name, ext),
                    name=name,
                    size=entry.size_str,
                    packed=entry.packed_str,
                    ftype=entry.type_str,
                    modified=entry.modified_str,
                    crc=entry.crc,
                    full_path=name,
                    raw_size=entry.size,
                    raw_packed=entry.packed_size,
                    modified_raw=entry.modified,
                )
                file_count += 1

            self._append_file_item(fi)

        ratio = ''
        if total_size > 0:
            r = (1 - total_packed / total_size) * 100
            ratio = f', Ratio: {r:.1f}%'

        self._update_status(
            f'Files: {file_count}, Folders: {dir_count}, '
            f'Size: {format_size(total_size)}, '
            f'Packed: {format_size(total_packed)}{ratio}'
        )

    def _filter_archive_entries(self, prefix: str):
        self._clear_model()
        file_count = 0
        dir_count = 0
        total_size = 0
        total_packed = 0

        for entry in self.archive_handler.entries:
            if not entry.name.startswith(prefix):
                continue
            rest = entry.name[len(prefix):]
            if '/' in rest.rstrip('/'):
                continue

            if entry.is_dir:
                fi = FileItem(icon='folder-symbolic', name=entry.name,
                              ftype='Folder', full_path=entry.name,
                              is_dir=True, modified=entry.modified_str,
                              modified_raw=entry.modified)
                dir_count += 1
            else:
                total_size += entry.size
                total_packed += entry.packed_size
                ext = Path(entry.name).suffix.lower()
                fi = FileItem(
                    icon=get_icon_for_file(entry.name, ext),
                    name=entry.name,
                    size=entry.size_str,
                    packed=entry.packed_str,
                    ftype=entry.type_str,
                    modified=entry.modified_str,
                    crc=entry.crc,
                    full_path=entry.name,
                    raw_size=entry.size,
                    raw_packed=entry.packed_size,
                    modified_raw=entry.modified,
                )
                file_count += 1

            self._append_file_item(fi)

        self.address_entry.set_text(os.path.join(self.current_path, prefix))
        self._update_status(
            f'Files: {file_count}, Folders: {dir_count}, '
            f'Size: {format_size(total_size)}'
        )

    def _go_up(self):
        if self.mode == 1:
            if self.archive_internal_path:
                parent = os.path.dirname(self.archive_internal_path.rstrip('/'))
                if parent:
                    self.archive_internal_path = parent + '/'
                    self._filter_archive_entries(self.archive_internal_path)
                else:
                    self.archive_internal_path = ''
                    self._load_archive(self.current_path)
            else:
                parent = os.path.dirname(self.current_path)
                self.archive_handler = ArchiveHandler()
                self.mode = 0
                self._load_directory(parent)
        else:
            parent = os.path.dirname(self.current_path)
            if parent != self.current_path:
                self._load_directory(parent)

    def _open_external(self, path: str):
        try:
            Gio.AppInfo.launch_default_for_uri(f'file://{path}')
        except Exception:
            self._update_status(f'Cannot open: {path}')

    # ---- Toolbar Actions ----

    def _on_open_archive(self, btn=None):
        dialog = Gtk.FileDialog.new()
        dialog.set_title('Open Archive')

        fz = Gtk.FileFilter()
        fz.set_name('Archives')
        for pat in ['*.zip', '*.tar', '*.tar.gz', '*.tgz',
                     '*.tar.bz2', '*.tbz2', '*.tar.xz', '*.txz', '*.7z']:
            fz.add_pattern(pat)
        fa = Gtk.FileFilter()
        fa.set_name('All files')
        fa.add_pattern('*')

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(fz)
        filters.append(fa)
        dialog.set_filters(filters)

        def on_open(dlg, result):
            try:
                file = dlg.open_finish(result)
                path = file.get_path()
                if path:
                    self._load_archive(path)
            except GLib.Error:
                pass

        dialog.open(self, None, on_open)

    def _on_extract(self, btn=None):
        if self.mode != 1:
            self._show_message('No archive is open.')
            return
        selected = self._get_selected_paths()
        if not selected:
            self._show_message('Select files to extract.')
            return

        dialog = ExtractDialog(self, os.path.basename(self.current_path))
        dialog.connect('response', self._on_extract_response, selected)
        dialog.show()

    def _on_extract_here(self, btn=None):
        if self.mode == 1:
            dest = os.path.dirname(self.current_path)
            members = [e.name for e in self.archive_handler.entries]
            self._do_extract(members, dest)
            self._load_directory(dest)
        else:
            selected = self._get_selected_paths()
            if len(selected) != 1 or not is_archive(selected[0]):
                self._show_message('Select a single archive file to extract.')
                return
            path = selected[0]
            dest = os.path.dirname(path)
            try:
                ah = ArchiveHandler()
                entries = ah.open(path)
                self._do_extract_static(ah, [e.name for e in entries], dest)
                self._load_directory(dest)
            except Exception as e:
                traceback.print_exc()
                self._show_message(f'Extraction error: {e}')

    def _do_extract_static(self, handler, members, dest):
        dialog = ProgressDialog(self, 'Extracting...')
        dialog.present()
        try:
            handler.extract(members, dest, dialog.update)
            self._update_status(f'Extracted {len(members)} files to {dest}')
        except Exception as e:
            traceback.print_exc()
            self._show_message(f'Extraction error: {e}')
            self._update_status('Extraction failed')
        finally:
            dialog.destroy()

    def _on_extract_response(self, dialog, response, selected):
        if response == Gtk.ResponseType.OK:
            dest = dialog.get_result()
            dialog.destroy()
            if dest:
                self._do_extract(selected, dest)
        else:
            dialog.destroy()

    def _do_extract(self, members, dest):
        dialog = ProgressDialog(self, 'Extracting...')
        dialog.present()
        try:
            self.archive_handler.extract(members, dest, dialog.update)
            self._update_status(f'Extracted {len(members)} files to {dest}')
        except Exception as e:
            traceback.print_exc()
            self._show_message(f'Extraction error: {e}')
            self._update_status('Extraction failed')
        finally:
            dialog.destroy()

    def _on_add(self, btn=None):
        d = AddDialog(self, self.current_path if self.mode == 0 else os.path.dirname(self.current_path))
        if self.mode == 1:
            d.name_entry.set_text(self.current_path)
        d.connect('response', self._on_add_response)
        d.show()

    def _on_add_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            result = dialog.get_result()
            dialog.destroy()
            if result:
                name, fmt, files = result
                if files:
                    self._do_create(name, fmt, files)
        else:
            dialog.destroy()

    def _do_create(self, archive_path, fmt, files):
        dialog = ProgressDialog(self, 'Creating archive...')
        dialog.present()
        try:
            self.archive_handler.create_archive(archive_path, files, fmt, dialog.update)
            self._update_status(f'Created: {archive_path}')
            if self.mode == 0:
                self._load_directory(self.current_path)
        except Exception as e:
            self._show_message(f'Archive creation error: {e}')
            self._update_status('Archive creation failed')
        finally:
            dialog.destroy()

    def _on_delete(self, btn=None):
        if self.mode != 1:
            self._show_message('Open an archive first.')
            return
        selected = self._get_selected_paths()
        if not selected:
            self._show_message('Select files to delete.')
            return

        alert = Gtk.AlertDialog(message=f'Delete {len(selected)} file(s)?')
        alert.set_buttons(['Cancel', 'Delete'])
        alert.set_cancel_button(0)
        alert.set_default_button(1)
        def on_confirm(dialog, result):
            try:
                btn = dialog.choose_finish(result)
            except GLib.Error:
                return
            if btn == 1:
                self._do_delete(selected)

        alert.choose(self, None, on_confirm)

    def _do_delete(self, selected):
        try:
            self._update_status('Deleting...')
            while GLib.MainContext.default().iteration(False):
                pass
            self.archive_handler.delete_members(selected)
            self._load_archive(self.current_path)
            self._update_status(f'Deleted {len(selected)} file(s)')
        except Exception as e:
            self._show_message(f'Delete error: {e}')
            self._update_status('Delete failed')

    def _on_info(self, btn=None):
        if self.mode == 1:
            d = InfoDialog(self, self.current_path, self.archive_handler.entries)
            d.connect('response', lambda dlg, r: dlg.destroy())
            d.show()
        elif self.mode == 0:
            selected = self._get_selected_paths()
            if len(selected) == 1:
                if os.path.isfile(selected[0]) and is_archive(selected[0]):
                    try:
                        ah = ArchiveHandler()
                        entries = ah.open(selected[0])
                        d = InfoDialog(self, selected[0], entries)
                        d.connect('response', lambda dlg, r: dlg.destroy())
                        d.show()
                    except Exception as e:
                        self._show_message(f'Error: {e}')
                else:
                    self._show_file_info(selected[0])
            else:
                self._show_message('Select a file/archive to view info.')

    def _show_file_info(self, path):
        try:
            st = os.stat(path)
            txt = (
                f'File: {path}\n'
                f'Size: {format_size(st.st_size)}\n'
                f'Modified: {time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))}\n'
                f'Permissions: {oct(st.st_mode)[-3:]}\n'
            )
            self._show_message(txt)
        except Exception as e:
            self._show_message(f'Error: {e}')

    def _show_message(self, text, callback=None):
        alert = Gtk.AlertDialog(message=text)
        def on_response(dialog, result):
            try:
                dialog.choose_finish(result)
            except GLib.Error:
                pass
            if callback:
                callback()
        alert.choose(self, None, on_response)

    # ---- Context Menu ----

    def _build_context_menu(self) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        items = []
        if self.mode == 1:
            items.append(('Extract', self._on_extract))
            items.append(('Delete', self._on_delete))
        items.append(('Info', self._on_info))
        items.append(('Copy Path', self._on_copy_path))

        for lbl, cb in items:
            btn = Gtk.Button(label=lbl)
            btn.add_css_class('flat')
            btn.set_halign(Gtk.Align.FILL)
            btn.connect('clicked', lambda b, cb=cb: self._context_action(cb))
            box.append(btn)
        return box

    def _context_action(self, callback):
        callback()

    def _on_copy_path(self, btn=None):
        selected = self._get_selected_paths()
        if selected:
            self.get_clipboard().set(selected[0])
            self._update_status(f'Copied: {selected[0]}')


class PyZipApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.pyzip.app', flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = MainWindow(self)
        win.present()


def main():
    app = PyZipApplication()
    return app.run(sys.argv)


if __name__ == '__main__':
    sys.exit(main())
