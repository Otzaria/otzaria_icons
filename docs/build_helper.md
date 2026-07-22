# Build helper (GUI)

`otzaria_build.py` is a small graphical launcher for the generation pipeline. It
runs the correct commands, in the correct order, so you don't have to remember
that the Python steps must come before `dart run tool/generate.dart`. It streams
each command's output and stops on the first failure.

## Running it

- **Windows:** double-click `otzaria_build.bat` (it opens the window with no
  lingering console). Or run `python otzaria_build.py` from the repository root.
- **macOS / Linux:** run `python3 otzaria_build.py` from the repository root.

Both files live in the repository root and assume they are run from there (the
script uses its own location as the working directory).

## Prerequisites

- Flutter/Dart SDK on `PATH` (`dart`, `flutter`).
- Python 3 on `PATH`. Tkinter ships with the standard python.org build; no extra
  install is needed for the window itself.
- The pinned Python generation tools are installed automatically by the helper
  (`pip install -r tool/requirements.txt`), so a first run may take a moment.

On start-up the helper prints the working directory and whether `dart`,
`flutter`, and `python` were found, so you can spot a missing SDK immediately.

The interface is in Hebrew. Alongside the build buttons there is a "העתקת הפלט"
(copy output) button that copies the whole log to the clipboard — handy for
pasting a failing run somewhere for help — and a "ניקוי" (clear) button.

## The buttons

### 🎨 After adding / editing icons

Use this whenever you added, replaced, or edited an SVG in `assets_src/svg/`. It
runs the full flow, including the SVG-normalization step that **must** precede
generation:

```
flutter pub get
python -m pip install -r tool/requirements.txt
dart run tool/validate.dart
python tool/normalize_svg_overlaps.py
dart run tool/generate.dart
dart run tool/generate.dart --check
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```

### 🛠 After code changes only

Use this when you changed Dart/tooling code but **not** any icon source. It skips
SVG normalization (there is nothing new to normalize):

```
flutter pub get
python -m pip install -r tool/requirements.txt
dart run tool/generate.dart
dart run tool/generate.dart --check
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```

### 🖼 עדכון golden (Windows) — update the gallery golden

Run this **only on Windows**, and **only after** you have visually confirmed the
new/changed icon looks right. Adding or changing an icon grows the gallery
golden image, so `flutter test` will fail on `test/goldens/icon_gallery.png`
until the golden is regenerated. This button runs:

```
flutter test --update-goldens test/icon_gallery_golden_test.dart
```

Review the updated `test/goldens/icon_gallery.png` for blank, clipped, crowded,
or unexpectedly filled glyphs before committing it.

You usually don't need to reach for this button manually: when the "After adding
/ editing icons" flow fails on the golden test, the helper detects it and pops a
dialog offering to update the golden right there. It is a deliberate confirm
(not silent) on purpose — auto-blessing the golden every run would defeat its
job as the visual safety net, so you still review the image afterwards.

### ✕ Close

Closes the window without running anything.

## Why the order matters

`dart run tool/generate.dart` calls Python internally for the overlap gate and
the final glyph-repair step, so the pinned tools must be installed first. If you
edited icons and skip normalization, generation now fails fast with a clear
message (the overlap gate added in `generate.dart`) rather than shipping a
corrupted glyph — but running normalization up front avoids that stop entirely.
This mirrors `docs/adding_icons.md` and `docs/testing_and_ci.md`.

## After a successful build

If any glyph changed, regenerate the Windows-only visual golden and review it
before committing (the golden is pinned to one OS to avoid rasterization
differences, so do this on Windows):

```
flutter test --update-goldens test/icon_gallery_golden_test.dart
```

Then commit the SVG plus every regenerated artifact (manifest, OTF,
`lib/src/generated/`, catalogs, notices) and add a `CHANGELOG.md` entry.

## Troubleshooting

- **"Run tests" (הרצת טסטים) failed after adding an icon** — almost always the
  gallery golden. The golden image grew with your new icon, so it no longer
  matches. Visually check the icon, then click "עדכון golden (Windows)" on
  Windows (or run `flutter test --update-goldens
  test/icon_gallery_golden_test.dart`), review `test/goldens/icon_gallery.png`,
  and rerun. If it's a different test, use "העתקת הפלט" to copy the output.
- **"Verify formatting" step failed** — formatting drifted. Run `dart format .`
  to fix, then rebuild.
- **A "normalize" / overlap step failed** — a source SVG still has overlapping or
  seaming paths. Review the normalized files it reports before committing.
- **`dart` / `flutter` shown as NOT FOUND** — the SDK isn't on `PATH`. Add it and
  reopen the helper.
- **Window doesn't open / Tkinter error** — reinstall Python from python.org with
  the Tcl/Tk option enabled, or run `python otzaria_build.py` to see the error.
