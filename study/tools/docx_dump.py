"""Dump DOCX block-level content (paragraphs and tables) with indices.

Stdlib only: zipfile + xml.etree. Usage:
    python docx_dump.py <file.docx> [out.txt]

Each block is printed as:
    [P0042] paragraph text
    [T01 R02 C03] cell text        (table cells, row/col indices)
    [TBL-START 01] / [TBL-END 01]
"""
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def para_text(p):
    parts = []
    for node in p.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append("\t")
        elif node.tag == W + "br":
            parts.append("\n")
    return "".join(parts)


def iter_blocks(parent):
    """Yield ('p', elem) / ('tbl', elem) in document order for a body/cell."""
    for child in parent:
        if child.tag == W + "p":
            yield "p", child
        elif child.tag == W + "tbl":
            yield "tbl", child


def dump(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(W + "body")
    lines = []
    p_idx = 0
    t_idx = 0
    for kind, el in iter_blocks(body):
        if kind == "p":
            txt = para_text(el)
            lines.append(f"[P{p_idx:04d}] {txt}")
            p_idx += 1
        else:
            t_idx += 1
            lines.append(f"[TBL-START {t_idx:02d}]")
            for r_i, tr in enumerate(el.findall(W + "tr")):
                for c_i, tc in enumerate(tr.findall(W + "tc")):
                    cell_txt = " | ".join(
                        para_text(p) for p in tc.iter(W + "p")
                    )
                    lines.append(f"[T{t_idx:02d} R{r_i:02d} C{c_i:02d}] {cell_txt}")
            lines.append(f"[TBL-END {t_idx:02d}]")
    return "\n".join(lines)


if __name__ == "__main__":
    src = sys.argv[1]
    out = dump(src)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            f.write(out)
        print(f"wrote {sys.argv[2]} ({len(out)} chars)")
    else:
        print(out)
