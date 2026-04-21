"""PDF Splitter — разделение PDF по настраиваемым паттернам."""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import config as cfg_mod


def _pick_files_or_folders_native() -> list[str]:
    """Нативный NSOpenPanel на macOS: выбор файлов И папок в одном диалоге."""
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSOpenPanel  # type: ignore
    except ImportError:
        return None
    panel = NSOpenPanel.openPanel()
    panel.setCanChooseFiles_(True)
    panel.setCanChooseDirectories_(True)
    panel.setAllowsMultipleSelection_(True)
    panel.setTitle_("Выберите PDF-файлы или папку")
    try:
        panel.setAllowedFileTypes_(["pdf"])
    except Exception:
        pass
    if panel.runModal() != 1:
        return []
    return [str(u.path()) for u in panel.URLs()]


def _expand_inputs(paths: list[str]) -> list[str]:
    """Разворачивает папки в список PDF-файлов."""
    out: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.lower().endswith(".pdf"):
                    out.append(os.path.join(p, name))
        elif p.lower().endswith(".pdf"):
            out.append(p)
    return out


class PDFSplitterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF Splitter")
        self.root.geometry("720x620")
        self.root.minsize(560, 480)

        self.cfg = cfg_mod.load()

        self.input_display = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.active_pattern = tk.StringVar(value=self.cfg.get("active", ""))
        self._selected_paths: list[str] = []

        self._build_ui()

    # ---------- UI ----------

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill=tk.BOTH, expand=True)

        # Паттерн
        pf = ttk.Frame(main)
        pf.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(pf, text="Шаблон:").pack(side=tk.LEFT)
        self.pattern_box = ttk.Combobox(
            pf, textvariable=self.active_pattern,
            values=self._pattern_names(), state="readonly",
        )
        self.pattern_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.pattern_box.bind("<<ComboboxSelected>>", self._on_pattern_changed)
        ttk.Button(pf, text="Настроить шаблоны…", command=self._open_pattern_editor).pack(side=tk.RIGHT)

        # Источник — единая кнопка
        ttk.Label(main, text="Исходные PDF (файлы или папка):").pack(anchor=tk.W)
        inp = ttk.Frame(main)
        inp.pack(fill=tk.X, pady=(4, 4))
        self.input_entry = ttk.Entry(inp, textvariable=self.input_display)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.input_entry.bind("<FocusOut>", lambda e: self._sync_from_entry())
        ttk.Button(inp, text="Обзор…", command=self._browse_input).pack(side=tk.RIGHT)

        self.files_label = ttk.Label(main, text="", foreground="gray")
        self.files_label.pack(anchor=tk.W, pady=(0, 8))

        # Выход
        ttk.Label(main, text="Папка для сохранения:").pack(anchor=tk.W)
        out = ttk.Frame(main)
        out.pack(fill=tk.X, pady=(4, 12))
        ttk.Entry(out, textvariable=self.output_dir).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(out, text="Обзор…", command=self._browse_output).pack(side=tk.RIGHT)

        # Запуск
        self.run_btn = ttk.Button(main, text="Разделить PDF", command=self._run)
        self.run_btn.pack(pady=(0, 12))

        # Прогресс
        self.pct = tk.DoubleVar()
        ttk.Progressbar(main, variable=self.pct, maximum=100).pack(fill=tk.X, pady=(0, 4))
        self.status = ttk.Label(main, text="")
        self.status.pack(anchor=tk.W, pady=(0, 8))

        # Лог
        ttk.Label(main, text="Результаты:").pack(anchor=tk.W)
        lf = ttk.Frame(main)
        lf.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(lf, height=10, state=tk.DISABLED, wrap=tk.WORD)
        sb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _pattern_names(self) -> list[str]:
        return [p["name"] for p in self.cfg.get("patterns", [])]

    def _on_pattern_changed(self, _=None):
        self.cfg["active"] = self.active_pattern.get()
        cfg_mod.save(self.cfg)

    # ---------- Выбор источника ----------

    def _browse_input(self):
        paths = _pick_files_or_folders_native()
        if paths is None:
            # Фолбэк: стандартный диалог файлов (папку можно вписать в поле вручную)
            paths = list(filedialog.askopenfilenames(
                title="Выберите PDF-файлы",
                filetypes=[("PDF", "*.pdf"), ("Все", "*.*")],
            ))
        if not paths:
            return
        self._set_paths(paths)

    def _set_paths(self, raw_paths: list[str]):
        files = _expand_inputs(raw_paths)
        if not files:
            messagebox.showwarning("Внимание", "Не найдено PDF-файлов.")
            return

        self._selected_paths = files
        if len(raw_paths) == 1:
            self.input_display.set(raw_paths[0])
        else:
            self.input_display.set("; ".join(raw_paths))

        n = len(files)
        r = n % 10
        w = "файлов" if 11 <= n % 100 <= 19 else (
            "файл" if r == 1 else "файла" if 2 <= r <= 4 else "файлов"
        )
        self.files_label.configure(text=f"К обработке: {n} {w}")

        if not self.output_dir.get():
            base = raw_paths[0] if os.path.isdir(raw_paths[0]) else os.path.dirname(raw_paths[0])
            self.output_dir.set(os.path.join(base, "Результат"))

    def _sync_from_entry(self):
        """Если пользователь вручную вписал путь — разобрать и подтянуть."""
        text = self.input_display.get().strip()
        if not text:
            self._selected_paths = []
            self.files_label.configure(text="")
            return
        parts = [p.strip() for p in text.split(";") if p.strip()]
        if parts and any(os.path.exists(p) for p in parts):
            self._set_paths(parts)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Выберите папку для сохранения")
        if path:
            self.output_dir.set(path)

    # ---------- Редактор шаблонов ----------

    def _open_pattern_editor(self):
        PatternEditor(self.root, self.cfg, on_save=self._reload_patterns)

    def _reload_patterns(self):
        self.cfg = cfg_mod.load()
        self.pattern_box["values"] = self._pattern_names()
        if self.active_pattern.get() not in self._pattern_names():
            if self._pattern_names():
                self.active_pattern.set(self._pattern_names()[0])
                self.cfg["active"] = self.active_pattern.get()
                cfg_mod.save(self.cfg)

    # ---------- Лог ----------

    def _append_log(self, msg: str):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    # ---------- Запуск ----------

    def _run(self):
        self._sync_from_entry()
        if not self._selected_paths:
            messagebox.showwarning("Внимание", "Выберите PDF-файлы или папку.")
            return
        out = self.output_dir.get().strip()
        if not out:
            messagebox.showwarning("Внимание", "Выберите папку для сохранения.")
            return

        os.makedirs(out, exist_ok=True)
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.run_btn.configure(state=tk.DISABLED)
        self.pct.set(0)

        threading.Thread(
            target=self._worker,
            args=(list(self._selected_paths), out, dict(self.cfg)),
            daemon=True,
        ).start()

    def _worker(self, files: list[str], out: str, cfg: dict):
        from pdf_processor import split_pdf  # ленивый импорт

        all_res = []
        total = len(files)

        for fi, path in enumerate(files):
            label = os.path.basename(path)
            self.root.after(0, self._append_log, f"--- {label} ---")

            def on_progress(cur, tot, fname, phase, _fi=fi, _t=total):
                p = (_fi + cur / max(tot, 1)) / _t * 100
                self.root.after(0, self._on_progress, p, cur, tot, fname, phase)

            try:
                res = split_pdf(path, out, cfg, progress_callback=on_progress)
                all_res.extend(res)
            except Exception as e:
                self.root.after(0, self._append_log, f"  ОШИБКА: {e}")

        self.root.after(0, self._on_done, all_res)

    def _on_progress(self, p, cur, tot, fname, phase):
        self.pct.set(p)
        phase_label = "OCR" if phase == "ocr" else "сохранение"
        self.status.configure(text=f"{phase_label}: {cur}/{tot} — {fname}")

    def _on_done(self, results: list[dict]):
        ok = err = 0
        for r in results:
            if r["status"] == "ok":
                ok += 1
                self._append_log(f"  Стр. {r['page']}: {r['filename']}")
            else:
                err += 1
                self._append_log(f"  Стр. {r['page']}: ОШИБКА — {r['error']}")
            if r.get("debug"):
                self._append_log(f"    [OCR]: {r['debug'][:300]}")

        self._append_log(f"\nГотово! Успешно: {ok}, ошибок: {err}")
        self.status.configure(text=f"Готово! {ok} файлов создано.")
        self.run_btn.configure(state=tk.NORMAL)

        if err == 0:
            messagebox.showinfo("Готово", f"Успешно: {ok} файлов.")
        else:
            messagebox.showwarning("Готово", f"Успешно: {ok}\nНе распознано/ошибок: {err}")


# ============================================================================
# Редактор шаблонов
# ============================================================================

class PatternEditor(tk.Toplevel):
    """Диалог: список шаблонов + редактор регулярки и имени файла."""

    def __init__(self, parent, cfg: dict, on_save):
        super().__init__(parent)
        self.title("Шаблоны распознавания")
        self.geometry("780x560")
        self.transient(parent)
        self.grab_set()

        self.cfg = cfg
        self.on_save = on_save
        self._current_idx: int | None = None
        self._dirty = False

        self._build()
        self._load_list()
        if self.cfg.get("patterns"):
            self.listbox.selection_set(0)
            self._on_select()

    def _build(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        # Левая панель — список
        left = ttk.Frame(root)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        ttk.Label(left, text="Шаблоны:").pack(anchor=tk.W)
        self.listbox = tk.Listbox(left, width=24, height=18, exportselection=False)
        self.listbox.pack(fill=tk.Y, expand=True)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._on_select())
        lb_btns = ttk.Frame(left)
        lb_btns.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(lb_btns, text="+", width=3, command=self._add).pack(side=tk.LEFT)
        ttk.Button(lb_btns, text="−", width=3, command=self._delete).pack(side=tk.LEFT, padx=4)

        # Правая панель — редактор
        right = ttk.Frame(root)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.name_var = tk.StringVar()
        self.sub_var = tk.StringVar()
        self.fname_var = tk.StringVar()
        self.fb_name_var = tk.StringVar()
        self.fb_sub_var = tk.StringVar()
        self.flag_i = tk.BooleanVar()
        self.flag_s = tk.BooleanVar()
        self.flag_m = tk.BooleanVar()

        def field(parent, label, var, width=None):
            f = ttk.Frame(parent)
            f.pack(fill=tk.X, pady=4)
            ttk.Label(f, text=label, width=22).pack(side=tk.LEFT)
            e = ttk.Entry(f, textvariable=var)
            e.pack(side=tk.LEFT, fill=tk.X, expand=True)
            var.trace_add("write", lambda *_: self._mark_dirty())
            return e

        field(right, "Название:", self.name_var)

        ttk.Label(right, text="Регулярка (regex):").pack(anchor=tk.W, pady=(6, 0))
        self.regex_txt = tk.Text(right, height=5, wrap=tk.WORD)
        self.regex_txt.pack(fill=tk.X, pady=(2, 4))
        self.regex_txt.bind("<<Modified>>", self._on_text_mod)

        flags = ttk.Frame(right)
        flags.pack(fill=tk.X)
        ttk.Checkbutton(flags, text="IGNORECASE", variable=self.flag_i,
                        command=self._mark_dirty).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(flags, text="DOTALL", variable=self.flag_s,
                        command=self._mark_dirty).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(flags, text="MULTILINE", variable=self.flag_m,
                        command=self._mark_dirty).pack(side=tk.LEFT)

        field(right, "Имя файла:", self.fname_var)
        field(right, "Подпапка:", self.sub_var)
        field(right, "Имя при непризнании:", self.fb_name_var)
        field(right, "Подпапка при непризнании:", self.fb_sub_var)

        hint = ttk.Label(
            right,
            text=("Подставляются имена групп регулярки (?P<name>...) и {page}.\n"
                  "Фильтры: |cap |upper |lower |title. Слэш в подпапке — вложенные папки."),
            foreground="gray", justify=tk.LEFT,
        )
        hint.pack(anchor=tk.W, pady=(8, 4))

        # Производительность
        perf = ttk.LabelFrame(right, text="Производительность", padding=8)
        perf.pack(fill=tk.X, pady=(6, 4))
        self.dpi_var = tk.IntVar(value=int(self.cfg.get("ocr_dpi", 200)))
        self.workers_var = tk.IntVar(value=int(self.cfg.get("workers", 4)))
        pf = ttk.Frame(perf)
        pf.pack(fill=tk.X)
        ttk.Label(pf, text="OCR DPI:").pack(side=tk.LEFT)
        ttk.Spinbox(pf, from_=100, to=400, increment=50, textvariable=self.dpi_var,
                    width=6).pack(side=tk.LEFT, padx=(4, 14))
        ttk.Label(pf, text="Потоков:").pack(side=tk.LEFT)
        ttk.Spinbox(pf, from_=1, to=16, textvariable=self.workers_var,
                    width=6).pack(side=tk.LEFT, padx=4)

        # Кнопки
        btns = ttk.Frame(right)
        btns.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btns, text="Сохранить", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side=tk.RIGHT, padx=6)

    # ---- логика ----

    def _mark_dirty(self):
        self._dirty = True

    def _on_text_mod(self, _=None):
        if self.regex_txt.edit_modified():
            self._mark_dirty()
            self.regex_txt.edit_modified(False)

    def _load_list(self):
        self.listbox.delete(0, tk.END)
        for p in self.cfg.get("patterns", []):
            self.listbox.insert(tk.END, p["name"])

    def _on_select(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        if self._current_idx is not None and self._dirty:
            self._commit_current()
        idx = sel[0]
        self._current_idx = idx
        p = self.cfg["patterns"][idx]
        self.name_var.set(p.get("name", ""))
        self.regex_txt.delete("1.0", tk.END)
        self.regex_txt.insert("1.0", p.get("regex", ""))
        self.fname_var.set(p.get("filename", ""))
        self.sub_var.set(p.get("subfolder", ""))
        self.fb_name_var.set(p.get("fallback_filename", ""))
        self.fb_sub_var.set(p.get("fallback_subfolder", ""))
        fl = p.get("flags", [])
        self.flag_i.set("IGNORECASE" in fl)
        self.flag_s.set("DOTALL" in fl)
        self.flag_m.set("MULTILINE" in fl)
        self._dirty = False

    def _commit_current(self):
        if self._current_idx is None:
            return
        fl = []
        if self.flag_i.get(): fl.append("IGNORECASE")
        if self.flag_s.get(): fl.append("DOTALL")
        if self.flag_m.get(): fl.append("MULTILINE")
        self.cfg["patterns"][self._current_idx] = {
            "name": self.name_var.get().strip() or "Без названия",
            "regex": self.regex_txt.get("1.0", "end-1c"),
            "flags": fl,
            "filename": self.fname_var.get(),
            "subfolder": self.sub_var.get(),
            "fallback_filename": self.fb_name_var.get(),
            "fallback_subfolder": self.fb_sub_var.get(),
        }
        self._dirty = False

    def _add(self):
        self._commit_current()
        new = {
            "name": f"Новый шаблон {len(self.cfg['patterns']) + 1}",
            "regex": "",
            "flags": ["IGNORECASE", "DOTALL"],
            "filename": "{page}.pdf",
            "subfolder": "",
            "fallback_filename": "стр_{page}_не_распознано.pdf",
            "fallback_subfolder": "",
        }
        self.cfg["patterns"].append(new)
        self._load_list()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(tk.END)
        self._on_select()

    def _delete(self):
        if self._current_idx is None:
            return
        if len(self.cfg["patterns"]) <= 1:
            messagebox.showinfo("Информация", "Должен остаться хотя бы один шаблон.")
            return
        del self.cfg["patterns"][self._current_idx]
        self._current_idx = None
        self._dirty = False
        self._load_list()
        if self.cfg["patterns"]:
            self.listbox.selection_set(0)
            self._on_select()

    def _save(self):
        self._commit_current()
        self.cfg["ocr_dpi"] = int(self.dpi_var.get())
        self.cfg["workers"] = int(self.workers_var.get())
        # Проверка регулярок
        import re
        for p in self.cfg["patterns"]:
            try:
                re.compile(p["regex"] or "")
            except re.error as e:
                messagebox.showerror(
                    "Ошибка в регулярке",
                    f"Шаблон «{p['name']}»: {e}",
                )
                return
        cfg_mod.save(self.cfg)
        self.on_save()
        self.destroy()


def main():
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    PDFSplitterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
