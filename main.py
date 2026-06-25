from __future__ import annotations

import subprocess
import shutil
import os
import sys
import platform
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading

# ── Windows: evitar ventana de consola al llamar a ffmpeg ──────────────────
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)  # texto nítido en pantallas HiDPI
    except Exception:
        pass
    _POPEN_FLAGS = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _POPEN_FLAGS = {}


def _platform_font(size: int, weight: str = "normal") -> tuple[str, int, str]:
    """Devuelve la fuente del sistema más adecuada para cada plataforma."""
    system = platform.system()
    if system == "Windows":
        face = "Segoe UI"
    elif system == "Darwin":
        face = "SF Pro Display"
    else:
        face = "DejaVu Sans"
    return (face, size, weight)


def _ffmpeg_install_hint() -> str:
    system = platform.system()
    if system == "Windows":
        return "Descárgalo desde https://ffmpeg.org\ny añádelo al PATH del sistema."
    elif system == "Darwin":
        return "Instálalo con:\n  brew install ffmpeg"
    else:
        return "Instálalo con:\n  sudo apt install ffmpeg"


class VideoEncoderApp:
    def __init__(self, root: tk.Tk) -> None:
        BG     = "#151515"
        CARD   = "#1E1E1E"
        CARD_2 = "#242424"
        TEXT   = "#F2F2F2"
        MUTED  = "#9A9A9A"
        BORDER = "#333333"
        ACCENT = "#6F8FAF"
        DANGER = "#A94A4A"

        self.root = root
        self.root.title("FFmpeg Encoder")
        self.root.geometry("560x710")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        self.filename: str | None = None
        self.output_dir: str | None = None
        self.cancel_event = threading.Event()
        self.process: subprocess.Popen | None = None

        self.quality_var = tk.IntVar(value=2)

        if not shutil.which("ffmpeg"):
            messagebox.showerror(
                "ffmpeg no encontrado",
                "ffmpeg no está instalado o no está en el PATH.\n\n"
                + _ffmpeg_install_hint(),
            )
            root.destroy()
            return

        style = ttk.Style()
        # 'clam' garantiza aspecto consistente en Win, macOS y Linux
        style.theme_use("clam")

        style.configure("Main.TFrame",  background=BG)
        style.configure("Card.TFrame",  background=CARD, relief="flat", borderwidth=1)

        style.configure(
            "Title.TLabel",
            background=BG, foreground=TEXT,
            font=_platform_font(22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=BG, foreground=MUTED,
            font=_platform_font(10),
        )
        style.configure(
            "CardTitle.TLabel",
            background=CARD, foreground=TEXT,
            font=_platform_font(11, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=CARD, foreground=MUTED,
            font=_platform_font(9),
        )
        style.configure(
            "Status.TLabel",
            background=BG, foreground=ACCENT,
            font=_platform_font(10, "italic"),
        )

        style.configure(
            "Primary.TButton",
            background=ACCENT, foreground="#111111",
            borderwidth=0, focusthickness=0,
            padding=(18, 12),
            font=_platform_font(10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#86A4C1"), ("disabled", "#333333")],
            foreground=[("disabled", "#777777")],
        )

        style.configure(
            "Secondary.TButton",
            background=CARD_2, foreground=TEXT,
            borderwidth=0, padding=(14, 10),
            font=_platform_font(10),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#303030"), ("disabled", "#242424")],
            foreground=[("disabled", "#555555")],
        )

        style.configure(
            "Danger.TButton",
            background=DANGER, foreground=TEXT,
            borderwidth=0, padding=(14, 10),
            font=_platform_font(10),
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#C05C5C"), ("disabled", "#242424")],
            foreground=[("disabled", "#555555")],
        )

        style.configure(
            "TRadiobutton",
            background=BG, foreground=TEXT,
            font=_platform_font(10),
            indicatorbackground=CARD,
            indicatorforeground=ACCENT,
            upperbordercolor=BORDER,
            lowerbordercolor=BORDER,
        )
        style.map(
            "TRadiobutton",
            background=[("active", BG)],
            foreground=[("active", TEXT)],
            indicatorbackground=[("active", CARD_2), ("!disabled", CARD)],
            indicatorforeground=[("selected", ACCENT), ("!selected", CARD)],
            upperbordercolor=[("active", ACCENT), ("!disabled", BORDER)],
            lowerbordercolor=[("active", ACCENT), ("!disabled", BORDER)],
        )

        self.create_widgets()
        self._set_button_enabled(self.button_convert, False)
        self._set_button_enabled(self.button_cancel, False)

    # ── Widgets ──────────────────────────────────────────────────────────────

    def create_widgets(self) -> None:
        container = ttk.Frame(self.root, style="Main.TFrame", padding=(32, 20))
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="FFmpeg Encoder", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            container, text="Codificación de vídeo local",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 16))

        # — Archivo ──────────────────────────────────────────────────────────
        card_file = ttk.Frame(container, style="Card.TFrame", padding=(20, 14))
        card_file.pack(fill="x", pady=(0, 12))

        ttk.Label(card_file, text="Archivo", style="CardTitle.TLabel").pack(anchor="w")
        self.label_file = ttk.Label(
            card_file, text="Ningún archivo seleccionado", style="Muted.TLabel"
        )
        self.label_file.pack(anchor="w", pady=(4, 14))
        self.button_browse = ttk.Button(
            card_file, text="Seleccionar vídeo",
            style="Secondary.TButton", command=self.browse_files,
        )
        self.button_browse.pack(anchor="w")

        # — Salida ───────────────────────────────────────────────────────────
        card_out = ttk.Frame(container, style="Card.TFrame", padding=(20, 14))
        card_out.pack(fill="x", pady=(0, 12))

        ttk.Label(card_out, text="Salida", style="CardTitle.TLabel").pack(anchor="w")
        self.label_out = ttk.Label(
            card_out, text="Mismo directorio que el origen", style="Muted.TLabel"
        )
        self.label_out.pack(anchor="w", pady=(4, 14))
        self.button_outdir = ttk.Button(
            card_out, text="Cambiar carpeta",
            style="Secondary.TButton", command=self.browse_output_dir,
        )
        self.button_outdir.pack(anchor="w")

        # — Calidad ──────────────────────────────────────────────────────────
        ttk.Label(container, text="Calidad", style="Subtitle.TLabel").pack(
            anchor="w", pady=(4, 8)
        )
        for value, label_text in [
            (1, "Alta     CRF 18 · preset slow"),
            (2, "Media   CRF 23 · preset medium"),
            (3, "Baja     CRF 28 · preset fast"),
        ]:
            ttk.Radiobutton(
                container, text=label_text,
                variable=self.quality_var, value=value,
                style="TRadiobutton",
            ).pack(anchor="w", pady=2)

        # — Convertir ────────────────────────────────────────────────────────
        self.button_convert = ttk.Button(
            container, text="CONVERTIR",
            style="Primary.TButton", command=self.start_encoding,
        )
        self.button_convert.pack(fill="x", pady=(16, 12))

        # — Cancelar / Salir ─────────────────────────────────────────────────
        bottom = ttk.Frame(container, style="Main.TFrame")
        bottom.pack(fill="x", pady=(12, 0))

        self.button_cancel = ttk.Button(
            bottom, text="Cancelar",
            style="Secondary.TButton", command=self.cancel_encoding,
        )
        self.button_cancel.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.button_exit = ttk.Button(
            bottom, text="Salir",
            style="Danger.TButton", command=self.root.destroy,
        )
        self.button_exit.pack(side="right", fill="x", expand=True, padx=(6, 0))

        # — Estado ───────────────────────────────────────────────────────────
        self.label_status = ttk.Label(container, text="", style="Status.TLabel")
        self.label_status.pack(pady=8)

    # ── Callbacks GUI (hilo principal) ───────────────────────────────────────

    def browse_files(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=os.path.expanduser("~"),
            title="Selecciona un archivo de vídeo",
            filetypes=(
                ("Archivos de vídeo", "*.mov *.mp4 *.avi *.mkv *.mxf *.webm"),
                ("Todos los archivos", "*.*"),
            ),
        )
        if path:
            self.filename = path
            if self.output_dir is None:
                self.output_dir = os.path.dirname(path)
            self.label_file.configure(text="Archivo: " + os.path.basename(path))
            self.label_out.configure(text="Directorio de salida: " + self.output_dir)
            self._set_button_enabled(self.button_convert, True)
            self.label_status.configure(text="Listo para convertir")

    def browse_output_dir(self) -> None:
        directory = filedialog.askdirectory(
            initialdir=self.output_dir or os.path.expanduser("~"),
            title="Selecciona carpeta de salida",
        )
        if directory:
            self.output_dir = directory
            self.label_out.configure(text="Directorio de salida: " + directory)

    def start_encoding(self) -> None:
        output_path = self._generate_output_path()
        if os.path.exists(output_path):
            proceed = messagebox.askyesno(
                "Confirmar",
                f"El archivo {os.path.basename(output_path)} ya existe.\n¿Sobrescribir?",
            )
            if not proceed:
                return

        self.cancel_event.clear()
        self._set_ui_busy(True)
        threading.Thread(
            target=self._encode, args=(output_path,), daemon=True
        ).start()

    def cancel_encoding(self) -> None:
        self.cancel_event.set()
        if self.process:
            self.process.terminate()
        self.label_status.configure(text="Cancelando...")

    # ── Helpers thread-safe ──────────────────────────────────────────────────

    def _gui(self, func):
        self.root.after(0, func)

    def _set_button_enabled(self, button, enabled: bool) -> None:
        button.configure(state="normal" if enabled else "disabled")

    def _set_ui_busy(self, busy: bool) -> None:
        self._gui(lambda: self._set_button_enabled(self.button_convert, not busy))
        self._gui(lambda: self._set_button_enabled(self.button_cancel, busy))
        self._gui(lambda: self._set_button_enabled(self.button_browse, not busy))
        self._gui(lambda: self._set_button_enabled(self.button_outdir, not busy))
        if busy:
            self._gui(
                lambda: self.label_status.configure(text="Codificando… Por favor espere.")
            )

    def _set_status(self, text: str) -> None:
        self._gui(lambda: self.label_status.configure(text=text))

    def _show_info(self, title: str, text: str) -> None:
        self._gui(lambda: messagebox.showinfo(title, text))

    def _show_error(self, title: str, text: str) -> None:
        self._gui(lambda: messagebox.showerror(title, text))

    def _show_celebration(self) -> None:
        self._gui(self._build_celebration_window)

    def _build_celebration_window(self) -> None:
        BG     = "#151515"
        ACCENT = "#6F8FAF"
        TEXT   = "#F2F2F2"
        MUTED  = "#9A9A9A"

        win = tk.Toplevel(self.root)
        win.title("")
        win.geometry("320x240")
        win.resizable(False, False)
        win.configure(bg=BG)
        win.grab_set()

        # Centrar sobre la ventana principal
        self.root.update_idletasks()
        rx = self.root.winfo_x() + (self.root.winfo_width()  - 320) // 2
        ry = self.root.winfo_y() + (self.root.winfo_height() - 240) // 2
        win.geometry(f"+{rx}+{ry}")

        tk.Label(
            win, text="✓", bg=BG, fg=ACCENT,
            font=_platform_font(42, "bold"),
        ).pack(pady=(24, 4))

        tk.Label(
            win, text="Trabajo completado", bg=BG, fg=TEXT,
            font=_platform_font(14, "bold"),
        ).pack()

        tk.Label(
            win, text="Oh Yeah!", bg=BG, fg=MUTED,
            font=_platform_font(11, "italic"),
        ).pack(pady=(4, 20))

        ttk.Button(
            win, text="OK",
            style="Primary.TButton",
            command=win.destroy,
        ).pack(ipadx=20)

    # ── Codificación (hilo secundario) ────────────────────────────────────────

    def _generate_output_path(self) -> str:
        assert self.filename is not None
        out_dir = self.output_dir or os.path.dirname(self.filename)
        base, _ = os.path.splitext(os.path.basename(self.filename))
        if base.startswith("encoded_"):
            base = base[len("encoded_"):]
        return os.path.join(out_dir, f"encoded_{base}.mp4")

    def _encode(self, output_path: str) -> None:
        try:
            quality = self.quality_var.get()
            if quality == 1:
                crf, preset = "18", "slow"
            elif quality == 3:
                crf, preset = "28", "fast"
            else:
                crf, preset = "23", "medium"

            cmd = [
                "ffmpeg", "-y",
                "-i", self.filename,
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", crf,
                "-c:a", "aac",
                "-b:a", "128k",
                output_path,
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                **_POPEN_FLAGS,          # CREATE_NO_WINDOW en Windows
            )
            _, stderr = self.process.communicate()

            if self.cancel_event.is_set():
                # Eliminar archivo parcial si se canceló
                try:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                except OSError:
                    pass
                self._set_status("Codificación cancelada")
                return

            if self.process.returncode == 0:
                self._set_status(f"¡Éxito! Guardado: {os.path.basename(output_path)}")
                self._show_celebration()
            else:
                self._set_status("Error en la codificación")
                self._show_error("Error de ffmpeg", f"ffmpeg devolvió un error:\n{stderr[-600:]}")

        except Exception as e:
            self._set_status(f"Error: {e}")
            self._show_error("Error", str(e))
        finally:
            self._set_ui_busy(False)
            self.process = None


if __name__ == "__main__":
    window = tk.Tk()
    app = VideoEncoderApp(window)
    window.mainloop()
