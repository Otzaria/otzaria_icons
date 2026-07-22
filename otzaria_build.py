#!/usr/bin/env python3
"""אוצריא אייקונים — כלי בנייה (ממשק גרפי).

מפעיל גרפי קטן לצנרת היצירה של otzaria_icons. בוחרים מה שינו, והכלי מריץ את
הפקודות המתאימות בסדר הנכון, מציג את הפלט, ונעצר בשלב הראשון שנכשל.

מצבים
-----
* אחרי הוספת / עריכת אייקונים — מתקין את כלי הפייתון הנעוצים, מנרמל נתיבי SVG
  חופפים/תפרים, ואז מייצר, בודק, מפרמט, מנתח ומריץ טסטים. (זה המסלול שבו צעדי
  הפייתון חייבים לרוץ לפני היצירה.)
* אחרי שינויי קוד בלבד — מייצר מחדש מהמקורות הקיימים, בודק, מפרמט, מנתח ומריץ
  טסטים. מדלג על נרמול ה-SVG (המקורות לא השתנו).
* עדכון golden (Windows) — מרנדר מחדש את golden הגלריה. הרץ רק ב-Windows, ורק
  אחרי בדיקה ויזואלית של האייקון החדש.

הרצה:  python otzaria_build.py     (או דאבל-קליק על otzaria_build.bat)
דורש את ה-SDK של Flutter/Dart ופייתון 3 ב-PATH.
"""
import os
import queue
import shutil
import subprocess
import sys
import threading

import tkinter as tk
from tkinter import messagebox, scrolledtext

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = '"%s"' % sys.executable  # אותו מפרש שמריץ את הממשק הזה

# שלבי הצנרת, כזוגות (תווית, פקודת-מעטפת). shell=True כדי ש-dart/flutter ייפתרו
# כקובצי .bat ב-Windows ודרך ה-PATH במערכות אחרות. אין קלט לא מהימן.
PUB_GET = ("הורדת תלויות (flutter pub get)", "flutter pub get")
PIP = ("התקנת כלי הפייתון הנעוצים",
       "%s -m pip install -r tool/requirements.txt" % PY)
VALIDATE = ("אימות SVG ומניפסט", "dart run tool/validate.dart")
NORMALIZE = ("נרמול נתיבי SVG חופפים/תפרים",
             "%s tool/normalize_svg_overlaps.py" % PY)
GENERATE = ("יצירת פונט + Dart + קטלוג", "dart run tool/generate.dart")
CHECK = ("בדיקה שהקבצים המחוללים מעודכנים",
         "dart run tool/generate.dart --check")
FORMAT = ("בדיקת פורמט",
          "dart format --output=none --set-exit-if-changed .")
ANALYZE = ("ניתוח סטטי", "flutter analyze")
TEST = ("הרצת טסטים", "flutter test")
GOLDEN = ("עדכון golden של הגלריה (Windows)",
          "flutter test --update-goldens test/icon_gallery_golden_test.dart")

ICONS_STEPS = [PUB_GET, PIP, VALIDATE, NORMALIZE, GENERATE, CHECK,
               FORMAT, ANALYZE, TEST]
CODE_STEPS = [PUB_GET, PIP, GENERATE, CHECK, FORMAT, ANALYZE, TEST]
GOLDEN_STEPS = [GOLDEN]

BG = "#1e1e1e"
FG = "#e6e6e6"
ACCENT = "#9b6c2f"
OK = "#4caf50"
ERR = "#e05252"
MUTED = "#9a948a"


class BuildApp:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.running = False
        self._golden_failure = False
        root.title("אוצריא אייקונים — כלי בנייה")
        root.configure(bg=BG)
        root.geometry("780x600")
        root.minsize(660, 500)

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(header, text="אוצריא אייקונים — כלי בנייה", bg=BG, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack(anchor="e")
        tk.Label(header,
                 text="בחר מה שינית. הפקודות המתאימות ירוצו לפי הסדר, "
                      "והפלט יוצג למטה.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="e")

        btns = tk.Frame(root, bg=BG)
        btns.pack(fill="x", padx=18, pady=6)
        self.b_icons = self._button(
            btns, "🎨  אחרי הוספת / עריכת אייקונים",
            lambda: self.run(ICONS_STEPS, "icons"))
        self.b_icons.pack(side="right", expand=True, fill="x", padx=(6, 0))
        self.b_code = self._button(
            btns, "🛠  אחרי שינויי קוד בלבד",
            lambda: self.run(CODE_STEPS, "code"))
        self.b_code.pack(side="right", expand=True, fill="x", padx=6)
        self.b_golden = self._button(
            btns, "🖼  עדכון golden (Windows)",
            lambda: self.run(GOLDEN_STEPS, "golden"), accent=False)
        self.b_golden.pack(side="right", expand=True, fill="x", padx=(0, 6))

        self.log = scrolledtext.ScrolledText(
            root, bg="#141414", fg=FG, insertbackground=FG,
            font=("Consolas", 10), wrap="word", relief="flat",
            borderwidth=0, state="disabled")
        self.log.pack(fill="both", expand=True, padx=18, pady=(8, 6))
        self.log.tag_config("step", foreground=ACCENT,
                            font=("Consolas", 10, "bold"))
        self.log.tag_config("ok", foreground=OK,
                            font=("Consolas", 10, "bold"))
        self.log.tag_config("err", foreground=ERR,
                            font=("Consolas", 10, "bold"))
        self.log.tag_config("muted", foreground=MUTED)

        bottom = tk.Frame(root, bg=BG)
        bottom.pack(fill="x", padx=18, pady=(0, 6))
        self.b_copy = self._button(
            bottom, "📋  העתקת הפלט", self.on_copy, accent=False)
        self.b_copy.pack(side="right", padx=(6, 0))
        self.b_clear = self._button(
            bottom, "🧹  ניקוי", self.on_clear, accent=False)
        self.b_clear.pack(side="right", padx=6)
        self.b_cancel = self._button(
            bottom, "✕  סגירה", self.on_cancel, accent=False)
        self.b_cancel.pack(side="left")

        self.status = tk.Label(root, text="מוכן.", bg=BG, fg=MUTED,
                               anchor="e", font=("Segoe UI", 10))
        self.status.pack(fill="x", padx=18, pady=(0, 12))

        self._preflight()

    def _button(self, parent, text, cmd, accent=True):
        return tk.Button(
            parent, text=text, command=cmd, relief="flat", cursor="hand2",
            bg=(ACCENT if accent else "#3a3a3a"), fg="white",
            activebackground=(ACCENT if accent else "#4a4a4a"),
            activeforeground="white", font=("Segoe UI", 10, "bold"),
            padx=10, pady=11, borderwidth=0)

    def _preflight(self):
        self._append("תיקיית עבודה: %s\n" % ROOT, "muted")
        if not os.path.exists(os.path.join(ROOT, "tool", "generate.dart")):
            self._append(
                "אזהרה: לא נמצא כאן tool/generate.dart. שים את הקובץ בשורש "
                "מאגר otzaria_icons.\n", "err")
        for exe in ("dart", "flutter"):
            found = shutil.which(exe)
            self._append(
                "  %-8s %s\n" % (exe, found or "לא נמצא ב-PATH"),
                "muted" if found else "err")
        self._append("  python   %s\n\n" % sys.executable, "muted")

    def _append(self, text, tag=None):
        self.log.configure(state="normal")
        if tag:
            self.log.insert("end", text, tag)
        else:
            self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        for b in (self.b_icons, self.b_code, self.b_golden):
            b.configure(state=state)

    def on_cancel(self):
        if not self.running:
            self.root.destroy()

    def on_copy(self):
        text = self.log.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()  # שומר את הלוח גם אחרי סגירת החלון
        self.status.configure(text="הפלט הועתק ללוח.", fg=OK)

    def on_clear(self):
        if self.running:
            return
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._preflight()
        self.status.configure(text="מוכן.", fg=MUTED)

    def run(self, steps, mode):
        if self.running:
            return
        self.running = True
        self._golden_failure = False
        self._set_buttons(False)
        self.status.configure(text="מריץ…", fg=FG)
        labels = {"icons": "אחרי הוספת/עריכת אייקונים",
                  "code": "אחרי שינויי קוד",
                  "golden": "עדכון golden"}
        self._append("\n%s\nמתחיל בנייה (%s)\n%s\n"
                     % ("=" * 60, labels.get(mode, mode), "=" * 60), "step")
        threading.Thread(target=self._worker, args=(steps,),
                         daemon=True).start()
        self.root.after(60, self._drain)

    def _worker(self, steps):
        ok = True
        for i, (label, cmd) in enumerate(steps, 1):
            self.q.put(("step", "\n▶ [%d/%d] %s\n" % (i, len(steps), label)))
            self.q.put(("muted", "  $ %s\n" % cmd))
            try:
                proc = subprocess.Popen(
                    cmd, shell=True, cwd=ROOT, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1,
                    errors="replace")
            except Exception as exc:  # noqa: BLE001
                self.q.put(("err", "  לא ניתן להריץ: %s\n" % exc))
                ok = False
                break
            step_out = []
            for line in proc.stdout:
                step_out.append(line)
                self.q.put(("line", line))
            code = proc.wait()
            if code != 0:
                self.q.put(("err", "  ✗ נכשל (קוד %d): %s\n" % (code, label)))
                self._hint(label)
                if label == TEST[0]:
                    joined = "".join(step_out).lower()
                    if "icon_gallery" in joined or "golden" in joined:
                        self.q.put(("gflag", True))
                ok = False
                break
            self.q.put(("ok", "  ✓ הושלם\n"))
        self.q.put(("finished", ok))

    def _hint(self, label):
        if label == FORMAT[0]:
            self.q.put(("muted", "    לתיקון הרץ:  dart format .\n"))
        elif label == TEST[0]:
            self.q.put((
                "muted",
                "    אם זו שגיאת golden אחרי הוספת/שינוי אייקון — זה צפוי.\n"
                "    בדוק ויזואלית את הגלריה, ואז לחץ 'עדכון golden (Windows)'\n"
                "    (או הרץ: flutter test --update-goldens "
                "test/icon_gallery_golden_test.dart).\n"
                "    אם זו שגיאה אחרת — לחץ 'העתקת הפלט' ושלח אותה לבדיקה.\n"))
        elif "נרמול" in label or "overlap" in label.lower():
            self.q.put(("muted",
                        "    בדוק ויזואלית את קבצי ה-SVG שנורמלו לפני commit.\n"))

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "finished":
                    self._finish(payload)
                    return
                elif kind == "gflag":
                    self._golden_failure = True
                elif kind == "line":
                    self._append(payload)
                else:
                    self._append(payload, kind)
        except queue.Empty:
            pass
        self.root.after(60, self._drain)

    def _finish(self, ok):
        self.running = False
        self._set_buttons(True)
        if ok:
            self._append("\n✓ כל השלבים עברו.\n", "ok")
            self._append(
                "אם השתנה glyph, עדכן את golden הגלריה ב-Windows ובדוק אותו:\n"
                "  flutter test --update-goldens "
                "test/icon_gallery_golden_test.dart\n", "muted")
            self.status.configure(text="הבנייה עברה.", fg=OK)
        else:
            self._append("\n✗ הבנייה נעצרה בשלב שנכשל (ראה למעלה).\n", "err")
            self.status.configure(text="הבנייה נכשלה.", fg=ERR)
            if self._golden_failure:
                self._offer_golden_update()

    def _offer_golden_update(self):
        # A golden failure after adding/changing an icon is expected. Offer to
        # update it right here (one click), but keep it a conscious choice: the
        # golden is the visual safety net, so it must be reviewed afterwards.
        if messagebox.askyesno(
                "עדכון golden",
                "טסט ה-golden נכשל — זה צפוי אחרי הוספת או שינוי אייקון.\n\n"
                "לעדכן את golden הגלריה עכשיו?\n\n"
                "לאחר מכן חשוב לפתוח את test/goldens/icon_gallery.png ולוודא "
                "שאין glyph ריק, חתוך או מרוסק לפני commit."):
            self.run(GOLDEN_STEPS, "golden")


def main():
    root = tk.Tk()
    BuildApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
