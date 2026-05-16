# PyZip - Archive Manager

A GTK4-based archive manager built with Python (PyGObject). Browse files, view and extract archives, and create new archives with a modern GUI.

## Features

- **File browsing** — navigate your filesystem with a sortable multi-column list
- **Archive support** — open, view, extract, and delete members from ZIP, TAR, TAR.GZ, TAR.BZ2, TAR.XZ archives
- **Archive creation** — create ZIP, TAR, and TAR.GZ archives from files and folders
- **Info dialog** — view archive summary (files, folders, sizes, compression ratio)
- **Context menu** — right-click for Extract, Delete, Info, Copy Path

## Requirements

- Python 3.9+
- GTK 4 (with PyGObject)
- GObject introspection bindings for GTK 4

### Install dependencies (Ubuntu/Debian)

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0
```

### Install dependencies (Fedora)

```bash
sudo dnf install python3-gobject gtk4
```

## Usage

```bash
python main.py
```

### Buttons

| Button    | Description |
|-----------|-------------|
| Open      | Open an archive file |
| Extract   | Extract selected files from archive |
| Add       | Create a new archive |
| Delete    | Delete selected members from archive |
| Up        | Go to parent directory |
| Info      | Show archive or file information |

### File list columns

Icon, Name, Size, Packed, Type, Modified, CRC (CRC shown for ZIP archives).

### Navigation

- Enter a path in the address bar and press Enter (or click Go)
- Double-click a folder to enter it
- Double-click an archive to open it
- Double-click a file to open it with the default application
