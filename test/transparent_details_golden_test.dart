import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:otzaria_icons/otzaria_icons.dart';

// Cross-platform smoke test for the icons that rely on transparent interior
// detail surviving the SVG -> font conversion (white knockouts and fine
// strokes). It previously compared against goldens/transparent_details.png,
// but that golden was never committed and the test was gated to Windows while
// no CI job ran it, so it provided zero coverage and broke a full local
// `flutter test` on Windows. Pixel-exact knockout verification is instead
// guaranteed deterministically by tool/repair_glyphs.py (boolean-difference
// knockouts, checked byte-for-byte by `generate.dart --check`) and visually by
// the Windows icon_gallery golden. This test now just asserts the glyphs load
// and paint without error on every platform.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    final fontData = rootBundle.load(
      'packages/otzaria_icons/lib/fonts/otzaria_icons.otf',
    );
    await (FontLoader('packages/otzaria_icons/OtzariaIcons')..addFont(fontData))
        .load();
  });

  const knockoutIcons = <String, IconData>{
    'book_zim_24_filled': OtzariaIcons.book_zim_24_filled,
    'book_word_24_filled': OtzariaIcons.book_word_24_filled,
    'book_upload_24_filled': OtzariaIcons.book_upload_24_filled,
    'book_pdf_24_filled': OtzariaIcons.book_pdf_24_filled,
    'book_search_24_filled': OtzariaIcons.book_search_24_filled,
    // Renamed, not replaced: the chain-in-a-book is now book_links, and what
    // was book_hyperlink is now book_link. Both entries still name the same
    // two pieces of artwork this test has always covered.
    'book_links_24_filled': OtzariaIcons.book_links_24_filled,
    'book_link_24_regular': OtzariaIcons.book_link_24_regular,
    'bookshelf_24_regular': OtzariaIcons.bookshelf_24_regular,
    'book_open_large_search_24_filled':
        OtzariaIcons.book_open_large_search_24_filled,
    'document_word_24_filled': OtzariaIcons.document_word_24_filled,
    'document_bullet_list_24_filled':
        OtzariaIcons.document_bullet_list_24_filled,
    'book_alef_24_filled': OtzariaIcons.book_alef_24_filled,
  };

  testWidgets('transparent-detail icons load and paint without error', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ColoredBox(
          color: Colors.white,
          child: Wrap(
            children: [
              for (final entry in knockoutIcons.entries)
                for (final size in const [24.0, 48.0, 72.0])
                  Icon(entry.value, size: size, color: Colors.black),
            ],
          ),
        ),
      ),
    );

    expect(tester.takeException(), isNull);
    expect(
      find.byType(Icon),
      findsNWidgets(knockoutIcons.length * 3),
    );
  });
}
