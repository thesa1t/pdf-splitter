"""Конфигурация: шаблоны паттернов и имён файлов.

Формат конфига (JSON):
{
  "patterns": [
    {
      "name": "Платёжные поручения",
      "regex": "гражданин[ауе]\\s+(?P<name>[А-ЯЁа-яё]+)\\s+(?P<surname>[А-ЯЁа-яё]+)\\s+[Сс]умма\\s+(?P<amount>\\d+)",
      "flags": ["IGNORECASE", "DOTALL"],
      "pages_per_document": 1,
      "filename":  "пп{amount}_{name|cap} {surname|cap}.pdf",
      "subfolder": "пп{amount}",
      "fallback_filename": "стр_{page}_не_распознано.pdf",
      "fallback_subfolder": ""
    }
  ],
  "active": "Платёжные поручения",
  "ocr_dpi": 200,
  "workers": 4
}

В шаблонах filename/subfolder доступны имена групп из regex и {page}, {page_end}, {pages}.
Фильтры: |cap (capitalize), |upper, |lower, |title.
"""

import json
import os
import re
import sys


def config_dir() -> str:
    if sys.platform == "darwin":
        d = os.path.expanduser("~/Library/Application Support/PDFSplitter")
    elif sys.platform == "win32":
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PDFSplitter")
    else:
        d = os.path.expanduser("~/.config/pdf-splitter")
    os.makedirs(d, exist_ok=True)
    return d


CONFIG_PATH = os.path.join(config_dir(), "config.json")


DEFAULT_CONFIG = {
    "patterns": [
        {
            "name": "Платёжные поручения",
            "regex": r"гражданин[ауе]\s+(?P<name>[А-ЯЁа-яё]+)\s+(?P<surname>[А-ЯЁа-яё]+)\s+[Сс]умма\s+(?P<amount>\d+)",
            "flags": ["IGNORECASE", "DOTALL"],
            "pages_per_document": 1,
            "filename": "пп{amount}_{name|cap} {surname|cap}.pdf",
            "subfolder": "пп{amount}",
            "fallback_filename": "стр_{page}_не_распознано.pdf",
            "fallback_subfolder": "",
        },
        {
            # `[О0]` — tesseract на сканах полисов стабильно видит цифру 0 вместо буквы О после двоеточия.
            "name": "Полис ДМС",
            "regex": r"Ф\.?\s*И\.?\s*[О0]\.?:?\s*(?P<surname>[А-ЯЁ][А-ЯЁ\-]+)\s+(?P<name>[А-ЯЁ][А-ЯЁ\-]+)",
            "flags": ["IGNORECASE", "DOTALL"],
            "pages_per_document": 1,
            "filename": "ДМС_{surname|cap} {name|cap}.pdf",
            "subfolder": "",
            "fallback_filename": "стр_{page}_не_распознано.pdf",
            "fallback_subfolder": "",
        },
    ],
    "active": "Платёжные поручения",
    "ocr_dpi": 300,
    "workers": 4,
}


def load() -> dict:
    if not os.path.isfile(CONFIG_PATH):
        save(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return json.loads(json.dumps(DEFAULT_CONFIG))


def save(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_active_pattern(cfg: dict) -> dict:
    name = cfg.get("active")
    for p in cfg.get("patterns", []):
        if p.get("name") == name:
            return p
    return cfg.get("patterns", [DEFAULT_CONFIG["patterns"][0]])[0]


def compile_flags(flags_list) -> int:
    v = 0
    for f in flags_list or []:
        v |= getattr(re, f, 0)
    return v


_FILTERS = {
    "cap": str.capitalize,
    "upper": str.upper,
    "lower": str.lower,
    "title": str.title,
    "": lambda s: s,
}


_PLACEHOLDER_RE = re.compile(r"\{([^{}|]+)(?:\|([^{}]+))?\}")


def _sanitize(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip() or "_"


def render_template(template: str, values: dict) -> str:
    def repl(m):
        key, flt = m.group(1), (m.group(2) or "").strip()
        v = values.get(key, "")
        fn = _FILTERS.get(flt)
        if fn is None:
            return str(v)
        return fn(str(v))

    rendered = _PLACEHOLDER_RE.sub(repl, template)
    parts = [_sanitize(p) for p in rendered.replace("\\", "/").split("/") if p]
    return "/".join(parts)
