# 7Z / RAR 格式支持方案

**日期**: 2026-05-23

---

## 1. 7Z 格式

### 方案：`py7zr`（纯 Python）

| 项目 | 说明 |
|------|------|
| 库 | **py7zr** |
| 读取 | 完整支持（LZMA/LZMA2/BZip2/Deflate/PPMd） |
| 写入 | 完整支持，可选压缩级别、固实归档 |
| 加密 | AES-256 |
| 分卷 | 支持多卷 |
| 系统依赖 | 无 |
| 安装 | `pip install py7zr` |
| 许可证 | LGPL 2.1 |

**接入方式**：在 `archive_handler.py` 中

- `open()` — 增加 `.7z` 分支，调用 `py7zr.SevenZipFile` 读取成员列表
- `extract()` — 增加对应分支提取文件
- `create_archive()` — 增加 `7z` 类型写入

py7zr 的 API 与 `zipfile.ZipFile` 类似，改造成本低。

---

## 2. RAR 格式

### 2.1 读取方案：`rarfile` + `libunrar`

| 项目 | 说明 |
|------|------|
| 库 | **rarfile**（ctypes 调用 C 库） |
| 读取 | 支持 RAR3 + RAR5 |
| 写入 | 不支持 |
| 系统依赖 | `libunrar5` 或 `unrar` CLI |
| 安装 | `pip install rarfile` + `apt install libunrar5` |

**接入方式**：在 `archive_handler.py` 中

- `open()` — 增加 `.rar` / `.cbr` 分支，调用 `rarfile.RarFile`
- `extract()` — 增加对应分支提取
- `create_archive()` — 不添加（RAR 写入无开源方案）

`rarfile.RarFile` 的 API 同样与 `zipfile.ZipFile` 兼容。

**注意**：`rarfile` 依赖系统 `libunrar`，若库缺失应抛出清晰的错误提示。

### 2.2 写入方案：不可行

RAR 压缩算法为 **专有/商业** 软件，没有开源库能创建 .rar 文件。可选变通方案：

| 方案 | 说明 | 可行性 |
|------|------|--------|
| 调用 `rar` CLI | 需安装商业 WinRAR 命令行工具 | 可行但依赖第三方商业软件 |
| `patool` 包装 CLI | 同上依赖 | 同 |
| 放弃 RAR 写入 | 只读 RAR，创建时推荐用户改用 7Z / ZIP | **主流做法** |

GNOME File Roller、KDE Ark 等 Linux 归档管理器均只读 RAR，不提供写入。

---

## 3. 方案对比

| 维度 | 7Z (py7zr) | RAR 读 (rarfile) | RAR 写 |
|------|------------|-------------------|--------|
| Python 包 | `py7zr` | `rarfile` | 无可用包 |
| 系统依赖 | 无 | `libunrar5` | 需商业 `rar` |
| 代码改动量 | ~40 行 | ~40 行 | ~20 行（调 CLI） |
| 复杂度 | 低 | 中（需处理 lib 缺失） | 高 |
| 新增测试 | `test_7z.py` | `test_rar.py` | 无 |

---

## 4. 推荐实施顺序

```
P0: 集成 py7zr → 7Z 完整读写
P0: 集成 rarfile → RAR 只读
P1: 通过 subprocess 包装 rar CLI → RAR 写入（可选）
```

当前 `archive_handler.py` 的 `open()` / `extract()` / `create_archive()` 三个方法各自通过后缀名分发到不同格式处理，只需在每处增加 `.7z` 和 `.rar` 的分支即可，无需重构现有架构。
