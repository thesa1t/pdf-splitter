"""Обработка PDF с настраиваемыми паттернами и параллельным OCR."""

import io
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from config import compile_flags, get_active_pattern, render_template

# Путь к tesseract (PATH в .app может не включать Homebrew)
_found = shutil.which("tesseract")
if _found:
    pytesseract.pytesseract.tesseract_cmd = _found
else:
    for p in [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.isfile(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break

# Латинские буквы-двойники → кириллица (частый артефакт OCR)
_LAT2CYR = str.maketrans(
    "ABCEHKMOPTXaceopxy",
    "АВСЕНКМОРТХасеорху",
)


class PatternMatcher:
    """Скомпилированный паттерн из конфига."""

    __slots__ = ("spec", "regex")

    def __init__(self, spec: dict):
        self.spec = spec
        self.regex = re.compile(spec["regex"], compile_flags(spec.get("flags", [])))

    def match(self, text: str) -> dict | None:
        text = text.translate(_LAT2CYR)
        m = self.regex.search(text)
        if not m:
            return None
        return m.groupdict()


def _ocr_image_bytes(png_bytes: bytes) -> str:
    return pytesseract.image_to_string(
        Image.open(io.BytesIO(png_bytes)), lang="rus"
    )


def _render_page_png(page: fitz.Page, dpi: int) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("png")


def _text_or_ocr(page: fitz.Page, matcher: PatternMatcher, dpi: int):
    """Пытается вытащить данные из текстового слоя; если пусто — возвращает PNG для OCR."""
    text = page.get_text()
    if text and text.strip():
        values = matcher.match(text)
        if values:
            return values, ""
    return None, _render_page_png(page, dpi)


def split_pdf(
    input_path: str,
    output_dir: str,
    cfg: dict,
    progress_callback=None,
) -> list[dict]:
    pattern = get_active_pattern(cfg)
    matcher = PatternMatcher(pattern)
    dpi = int(cfg.get("ocr_dpi", 200))
    workers = max(1, int(cfg.get("workers", 4)))

    filename_tpl = pattern.get("filename") or "стр_{page}.pdf"
    subfolder_tpl = pattern.get("subfolder") or ""
    fallback_name_tpl = pattern.get("fallback_filename") or "стр_{page}_не_распознано.pdf"
    fallback_sub_tpl = pattern.get("fallback_subfolder") or ""

    doc = fitz.open(input_path)
    total = len(doc)

    # 1) Быстрая выборка текстового слоя; для пустых — рендерим PNG
    quick = [None] * total
    needs_ocr: list[tuple[int, bytes]] = []

    for i in range(total):
        values, png = _text_or_ocr(doc[i], matcher, dpi)
        if values is not None:
            quick[i] = {"values": values, "debug": ""}
        else:
            needs_ocr.append((i, png))

    # 2) Параллельный OCR (pytesseract — subprocess, GIL не мешает)
    if needs_ocr:
        done = 0
        with ThreadPoolExecutor(max_workers=min(workers, len(needs_ocr))) as ex:
            futures = {ex.submit(_ocr_image_bytes, png): i for i, png in needs_ocr}
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    ocr_text = fut.result()
                except Exception as e:
                    quick[i] = {"values": None, "debug": f"OCR ERROR: {e}"}
                else:
                    values = matcher.match(ocr_text)
                    quick[i] = {"values": values, "debug": ocr_text if not values else ""}
                done += 1
                if progress_callback:
                    progress_callback(done, len(needs_ocr), os.path.basename(input_path), "ocr")

    # 3) Нарезка PDF в основном потоке (PyMuPDF не любит шаринг doc)
    results = []
    for i in range(total):
        info = quick[i] or {"values": None, "debug": ""}
        values = info["values"]
        debug = info["debug"]

        if values:
            ctx = dict(values)
            ctx["page"] = i + 1
            rel_name = render_template(filename_tpl, ctx)
            rel_sub = render_template(subfolder_tpl, ctx) if subfolder_tpl else ""
        else:
            ctx = {"page": i + 1}
            rel_name = render_template(fallback_name_tpl, ctx)
            rel_sub = render_template(fallback_sub_tpl, ctx) if fallback_sub_tpl else ""

        if not rel_name.lower().endswith(".pdf"):
            rel_name += ".pdf"

        sub = os.path.join(output_dir, rel_sub) if rel_sub else output_dir
        os.makedirs(sub, exist_ok=True)

        out = os.path.join(sub, rel_name)
        if os.path.exists(out):
            base, ext = os.path.splitext(rel_name)
            c = 2
            while os.path.exists(os.path.join(sub, f"{base}_{c}{ext}")):
                c += 1
            rel_name = f"{base}_{c}{ext}"
            out = os.path.join(sub, rel_name)

        try:
            new = fitz.open()
            new.insert_pdf(doc, from_page=i, to_page=i)
            new.save(out)
            new.close()
            results.append({
                "page": i + 1, "filename": rel_name, "status": "ok",
                "error": None, "debug": debug,
            })
        except Exception as e:
            results.append({
                "page": i + 1, "filename": rel_name, "status": "error",
                "error": str(e), "debug": debug,
            })

        if progress_callback:
            progress_callback(i + 1, total, os.path.basename(input_path), "split")

    doc.close()
    return results
