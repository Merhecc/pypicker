# -*- coding: utf-8 -*-
"""Windows 可执行文件的版本资源文件生成"""
from .utils import parse_version


VERSION_TPL = """\
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={filevers},
    prodvers={prodvers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '{langcodepage}',
        [{strings}])
      ]),
    VarFileInfo([VarStruct('Translation', [{translation}])])
  ]
)
"""


def make_version_file(path, v):
    """根据字段字典生成 PyInstaller 可用的版本信息文件。"""
    def q(s):
        s = str(s).replace("\\", "\\\\").replace("'", "\\'")
        return "'" + s + "'"

    fv = parse_version(v.get("file_version") or "1.0.0.0")
    pv = parse_version(v.get("product_version") or "1.0.0.0")

    items = [
        ("CompanyName", v.get("company", "")),
        ("FileDescription", v.get("description", "")),
        ("FileVersion", v.get("file_version", "")),
        ("InternalName", v.get("internal_name", "")),
        ("LegalCopyright", v.get("copyright", "")),
        ("OriginalFilename", v.get("original_filename", "")),
        ("ProductName", v.get("product_name", "")),
        ("ProductVersion", v.get("product_version", "")),
    ]

    lines = []
    for i, (k, val) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append("          StringStruct(%s, %s)%s" % (q(k), q(val), comma))

    content = VERSION_TPL.format(
        filevers=fv, prodvers=pv,
        langcodepage="080404b0",
        strings="\n".join(lines),
        translation="2052, 1200")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path