"""Обработка PDF с настраиваемыми паттернами и параллельным OCR."""

import io
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from config import compile_flags, get_active_pattern, render_template


def _resolve_tesseract():
    """Tesseract бандлится внутрь .app/.exe — сначала ищем там, системный только для запуска из исходников."""
    bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

    if sys.platform == "win32":
        bundled_bin = os.path.join(bundle_root, "Tesseract-OCR", "tesseract.exe")
        bundled_data = os.path.join(bundle_root, "Tesseract-OCR", "tessdata")
    else:
        bundled_bin = os.path.join(bundle_root, "tesseract")
        bundled_data = os.path.join(bundle_root, "tessdata")

    if os.path.isfile(bundled_bin):
        pytesseract.pytesseract.tesseract_cmd = bundled_bin
        if os.path.isdir(bundled_data):
            os.environ["TESSDATA_PREFIX"] = bundled_data
        return

    found = shutil.which("tesseract")
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
        return

    for p in [
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.isfile(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return


_resolve_tesseract()

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
    # PSM 4 (single column) устойчивее дефолтного 3 на бланках с таблицами:
    # дефолт иногда целиком выкидывает блок ФИО из формы полиса.
    return pytesseract.image_to_string(
        Image.open(io.BytesIO(png_bytes)), lang="rus", config="--psm 4"
    )


def _render_page_png(page: fitz.Page, dpi: int) -> bytes:
    return page.get_pixmap(dpi=dpi).tobytes("png")


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
    pages_per_doc = max(1, int(pattern.get("pages_per_document", 1) or 1))

    filename_tpl = pattern.get("filename") or "стр_{page}.pdf"
    subfolder_tpl = pattern.get("subfolder") or ""
    fallback_name_tpl = pattern.get("fallback_filename") or "стр_{page}_не_распознано.pdf"
    fallback_sub_tpl = pattern.get("fallback_subfolder") or ""

    doc = fitz.open(input_path)
    total = len(doc)

    # 1) Текстовый слой для каждой страницы; пустые → в очередь OCR
    page_texts: list[str] = [""] * total
    needs_ocr: list[tuple[int, bytes]] = []

    for i in range(total):
        text = doc[i].get_text()
        if text and text.strip():
            page_texts[i] = text
        else:
            needs_ocr.append((i, _render_page_png(doc[i], dpi)))

    # 2) Параллельный OCR (pytesseract — subprocess, GIL не мешает)
    if needs_ocr:
        done = 0
        with ThreadPoolExecutor(max_workers=min(workers, len(needs_ocr))) as ex:
            futures = {ex.submit(_ocr_image_bytes, png): i for i, png in needs_ocr}
            for fut in as_completed(futures):
                i = futures[fut]
                try:
                    page_texts[i] = fut.result()
                except Exception as e:
                    page_texts[i] = f"[OCR ERROR: {e}]"
                done += 1
                if progress_callback:
                    progress_callback(done, len(needs_ocr), os.path.basename(input_path), "ocr")

    # 3) Группируем страницы по pages_per_doc и режем в основном потоке
    groups = [(s, min(s + pages_per_doc, total)) for s in range(0, total, pages_per_doc)]
    results = []

    for gi, (start, end) in enumerate(groups):
        combined = "\n".join(page_texts[start:end]).strip()
        values = matcher.match(combined) if combined else None

        start_page = start + 1
        end_page = end  # end — exclusive, 1-based последняя = end
        pages_str = f"{start_page}-{end_page}" if end_page > start_page else str(start_page)

        ctx_base = {"page": start_page, "page_end": end_page, "pages": pages_str}

        if values:
            ctx = dict(values)
            ctx.update(ctx_base)
            rel_name = render_template(filename_tpl, ctx)
            rel_sub = render_template(subfolder_tpl, ctx) if subfolder_tpl else ""
            debug = ""
        else:
            rel_name = render_template(fallback_name_tpl, ctx_base)
            rel_sub = render_template(fallback_sub_tpl, ctx_base) if fallback_sub_tpl else ""
            debug = combined

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
            new.insert_pdf(doc, from_page=start, to_page=end - 1)
            new.save(out)
            new.close()
            results.append({
                "page": start_page, "filename": rel_name, "status": "ok",
                "error": None, "debug": debug,
            })
        except Exception as e:
            results.append({
                "page": start_page, "filename": rel_name, "status": "error",
                "error": str(e), "debug": debug,
            })

        if progress_callback:
            progress_callback(gi + 1, len(groups), os.path.basename(input_path), "split")

    doc.close()
    return results
