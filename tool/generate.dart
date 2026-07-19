import 'dart:io';

import 'package:icon_font_generator/icon_font_generator.dart';
// Version 4.1.0 otherwise embeds the current timestamp in the OTF head table.
// This exact version is pinned, and the deterministic timestamp is covered by
// the generation-drift check.
// ignore: implementation_imports
import 'package:icon_font_generator/src/utils/misc.dart';
import 'package:path/path.dart' as p;
import 'package:yaml/yaml.dart';

const _defaultLicense = 'GPL-3.0-only';
const _supportedSchemaVersion = 1;

Future<void> main(List<String> arguments) async {
  final checkOnly = arguments.contains('--check');
  if (arguments.any((argument) => argument != '--check')) {
    _fail('Usage: dart run tool/generate.dart [--check]');
  }
  final config = _readConfig(File('tool/config.yaml'));

  if (checkOnly) {
    await _checkGeneratedFiles(config);
    return;
  }

  await _runCanvasNormalization();
  await _runSanitization();
  await _runValidation();

  final manifestFile = File(config.manifestFile);
  final manifest = _readManifest(manifestFile);
  final svgFiles = Directory(config.sourceDirectory)
      .listSync()
      .whereType<File>()
      .where((file) => p.extension(file.path).toLowerCase() == '.svg')
      .toList()
    ..sort((a, b) => a.path.compareTo(b.path));
  final filesByName = {
    for (final file in svgFiles) p.basenameWithoutExtension(file.path): file,
  };

  var changed = false;
  var nextCodepoint = manifest.icons.isEmpty
      ? config.codepointStart
      : manifest.icons
              .map((icon) => icon.codepoint)
              .reduce((a, b) => a > b ? a : b) +
          1;
  for (final name in filesByName.keys) {
    if (manifest.icons.any((icon) => icon.name == name)) continue;
    final variant = name.endsWith('_filled') ? 'filled' : 'regular';
    manifest.icons.add(
      ManifestIcon(
        id: _nextId(manifest.icons),
        name: name,
        source: p.posix.join(config.sourceDirectory, '$name.svg'),
        codepoint: nextCodepoint++,
        variant: variant,
        size: config.canvasWidth,
        matchTextDirection: false,
        deprecated: false,
        upstreamStatus: 'missing',
        upstreamEquivalent: null,
        origin: 'custom',
        basedOn: null,
        author: 'Otzaria contributors',
        license: _defaultLicense,
        upstreamCommit: null,
      ),
    );
    changed = true;
  }

  final missingFiles = manifest.icons
      .where((icon) => !filesByName.containsKey(icon.name))
      .map((icon) => icon.name)
      .toList();
  if (missingFiles.isNotEmpty) {
    _fail(
      'Manifest icons have no SVG file: ${missingFiles.join(', ')}. '
      'Existing codepoints cannot be silently removed.',
    );
  }

  manifest.icons.sort((a, b) => a.codepoint.compareTo(b.codepoint));
  _requireContiguousCodepoints(manifest, config.codepointStart);
  if (changed) {
    manifestFile.writeAsStringSync(_serializeManifest(manifest));
    stdout.writeln('Updated ${config.manifestFile} with new icon allocations.');
  }

  final svgMap = <String, String>{
    for (final icon in manifest.icons)
      icon.name: filesByName[icon.name]!.readAsStringSync(),
  };
  if (svgMap.isEmpty) {
    _fail('No SVG files found in ${config.sourceDirectory}.');
  }

  MockableDateTime.mockedDate = DateTime.utc(2026);
  final result = svgToOtf(
    svgMap: svgMap,
    fontName: config.fontFamily,
    normalize: config.normalize,
    ignoreShapes: config.ignoreShapes,
  );
  if (result.glyphList.length != manifest.icons.length) {
    _fail(
      'Generator returned ${result.glyphList.length} glyphs for '
      '${manifest.icons.length} manifest icons.',
    );
  }
  for (var index = 0; index < manifest.icons.length; index++) {
    final expected = manifest.icons[index];
    final actual = result.glyphList[index].metadata;
    if (actual.name != expected.name || actual.charCode != expected.codepoint) {
      _fail(
        'Glyph mismatch at index $index: expected ${expected.name} at '
        '0x${expected.codepoint.toRadixString(16)}, got ${actual.name} at '
        '0x${actual.charCode?.toRadixString(16)}.',
      );
    }
  }

  File(config.fontFile).parent.createSync(recursive: true);
  writeToFile(config.fontFile, result.font);
  File(config.dartOutput)
    ..parent.createSync(recursive: true)
    ..writeAsStringSync(_generateDart(config, manifest.icons));
  File(config.galleryOutput)
    ..parent.createSync(recursive: true)
    ..writeAsStringSync(_generateGalleryCatalog(manifest.icons));
  File(config.testExpectationsOutput)
    ..parent.createSync(recursive: true)
    ..writeAsStringSync(_generateTestExpectations(manifest.icons));
  File(config.noticesOutput)
      .writeAsStringSync(_generateNotices(manifest.icons));
  File(config.catalogOutput)
    ..parent.createSync(recursive: true)
    ..writeAsStringSync(_generateSvgCatalog(manifest.icons));
  File(config.webCatalogOutput)
    ..parent.createSync(recursive: true)
    ..writeAsStringSync(_generateWebCatalog(manifest.icons));

  final formatResult = await Process.run(
    Platform.resolvedExecutable,
    [
      'format',
      config.dartOutput,
      config.galleryOutput,
      config.testExpectationsOutput,
    ],
  );
  if (formatResult.exitCode != 0) {
    stderr.write(formatResult.stderr);
    exit(formatResult.exitCode);
  }
  final analyzeResult = await Process.run(
    Platform.resolvedExecutable,
    ['analyze', config.dartOutput],
  );
  stdout.write(analyzeResult.stdout);
  stderr.write(analyzeResult.stderr);
  if (analyzeResult.exitCode != 0) {
    exit(analyzeResult.exitCode);
  }

  stdout.writeln(
    'Generated ${manifest.icons.length} icons and all derived artifacts.',
  );
}

Future<void> _runCanvasNormalization() async {
  final result = await Process.run(
    Platform.resolvedExecutable,
    ['run', 'tool/normalize_canvas.dart'],
  );
  stdout.write(result.stdout);
  stderr.write(result.stderr);
  if (result.exitCode != 0) exit(result.exitCode);
}

Future<void> _runSanitization() async {
  final result = await Process.run(
    Platform.resolvedExecutable,
    ['run', 'tool/sanitize.dart'],
  );
  stdout.write(result.stdout);
  stderr.write(result.stderr);
  if (result.exitCode != 0) exit(result.exitCode);
}

Future<void> _runValidation() async {
  final result = await Process.run(
    Platform.resolvedExecutable,
    ['run', 'tool/validate.dart'],
  );
  stdout.write(result.stdout);
  stderr.write(result.stderr);
  if (result.exitCode != 0) exit(result.exitCode);
}

Future<void> _checkGeneratedFiles(IconConfig config) async {
  final temp = Directory.systemTemp.createTempSync('otzaria_icons_check_');
  try {
    for (final path in [
      'tool',
      'assets_src',
      '.dart_tool',
      'lib',
      'example/lib/generated',
      'test/generated',
      'analysis_options.yaml',
      'pubspec.yaml',
      config.manifestFile,
      config.noticesOutput,
      config.catalogOutput,
      config.webCatalogOutput,
    ]) {
      final source = FileSystemEntity.typeSync(path);
      final destination = p.join(temp.path, path);
      if (source == FileSystemEntityType.directory) {
        _copyDirectory(Directory(path), Directory(destination));
      } else if (source == FileSystemEntityType.file) {
        File(destination).parent.createSync(recursive: true);
        File(path).copySync(destination);
      }
    }

    final result = await Process.run(
      Platform.resolvedExecutable,
      ['run', 'tool/generate.dart'],
      workingDirectory: temp.path,
    );
    stdout.write(result.stdout);
    stderr.write(result.stderr);
    if (result.exitCode != 0) exit(result.exitCode);

    final checkedPaths = <String>[
      config.manifestFile,
      config.fontFile,
      config.dartOutput,
      config.galleryOutput,
      config.testExpectationsOutput,
      config.noticesOutput,
      config.catalogOutput,
      config.webCatalogOutput,
      ...Directory(config.sourceDirectory)
          .listSync()
          .whereType<File>()
          .map((file) => p.relative(file.path)),
    ];
    final drift = <String>[];
    for (final path in checkedPaths) {
      final current = File(path);
      final generated = File(p.join(temp.path, path));
      if (!current.existsSync() ||
          !generated.existsSync() ||
          !_bytesEqual(
              current.readAsBytesSync(), generated.readAsBytesSync())) {
        drift.add(path);
      }
    }
    if (drift.isNotEmpty) {
      _fail(
        'Generated files are stale: ${drift.join(', ')}. '
        'Run dart run tool/generate.dart.',
      );
    }
    stdout
        .writeln('Generation check passed; repository files were not changed.');
  } finally {
    temp.deleteSync(recursive: true);
  }
}

void _copyDirectory(Directory source, Directory destination) {
  destination.createSync(recursive: true);
  for (final entity in source.listSync()) {
    final target = p.join(destination.path, p.basename(entity.path));
    if (entity is Directory) {
      _copyDirectory(entity, Directory(target));
    } else if (entity is File) {
      entity.copySync(target);
    }
  }
}

bool _bytesEqual(List<int> a, List<int> b) {
  if (a.length != b.length) return false;
  for (var index = 0; index < a.length; index++) {
    if (a[index] != b[index]) return false;
  }
  return true;
}

IconManifest _readManifest(File file) {
  final yaml = loadYaml(file.readAsStringSync()) as YamlMap;
  if (yaml['schema_version'] != _supportedSchemaVersion) {
    _fail(
      '${file.path}: unsupported schema_version '
      '${yaml['schema_version']}; expected $_supportedSchemaVersion.',
    );
  }
  final icons = <ManifestIcon>[];
  for (final value in yaml['icons'] as YamlList) {
    final item = value as YamlMap;
    icons.add(
      ManifestIcon(
        id: item['id'] as String,
        name: item['name'] as String,
        source: item['source'] as String,
        codepoint: _parseCodepoint(item['codepoint'])!,
        variant: item['variant'] as String,
        size: item['size'] as int,
        matchTextDirection: item['match_text_direction'] as bool,
        deprecated: item['deprecated'] as bool,
        upstreamStatus: item['upstream_status'] as String,
        upstreamEquivalent: item['upstream_equivalent'] as String?,
        origin: item['origin'] as String,
        basedOn: item['based_on'] as String?,
        author: item['author'] as String,
        license: item['license'] as String? ?? _defaultLicense,
        upstreamCommit: item['upstream_commit'] as String?,
      ),
    );
  }
  return IconManifest(
    schemaVersion: yaml['schema_version'] as int,
    icons: icons,
  );
}

void _requireContiguousCodepoints(IconManifest manifest, int codepointStart) {
  for (var index = 0; index < manifest.icons.length; index++) {
    final expected = codepointStart + index;
    if (manifest.icons[index].codepoint != expected) {
      _fail(
        'icon_font_generator 4.1.0 requires contiguous codepoints. '
        '${manifest.icons[index].name} must be 0x${expected.toRadixString(16)} '
        'but is 0x${manifest.icons[index].codepoint.toRadixString(16)}.',
      );
    }
  }
}

IconConfig _readConfig(File file) {
  if (!file.existsSync()) _fail('Missing ${file.path}.');
  final yaml = loadYaml(file.readAsStringSync());
  if (yaml is! YamlMap) _fail('${file.path}: root must be a map.');

  T requiredValue<T>(String key) {
    final value = yaml[key];
    if (value is! T) _fail('${file.path}: "$key" must be a $T.');
    return value;
  }

  final width = requiredValue<int>('canvas_width');
  final height = requiredValue<int>('canvas_height');
  if (width != height) _fail('Only square icon canvases are supported.');
  final start = _parseCodepoint(yaml['codepoint_start']);
  if (start == null) _fail('${file.path}: invalid codepoint_start.');
  return IconConfig(
    packageName: requiredValue<String>('package_name'),
    className: requiredValue<String>('class_name'),
    fontFamily: requiredValue<String>('font_family'),
    fontFile: requiredValue<String>('font_file'),
    sourceDirectory: requiredValue<String>('source_directory'),
    manifestFile: requiredValue<String>('manifest_file'),
    dartOutput: requiredValue<String>('dart_output'),
    galleryOutput: requiredValue<String>('gallery_output'),
    testExpectationsOutput: requiredValue<String>('test_expectations_output'),
    noticesOutput: requiredValue<String>('notices_output'),
    catalogOutput: requiredValue<String>('catalog_output'),
    webCatalogOutput: requiredValue<String>('web_catalog_output'),
    canvasWidth: width,
    canvasHeight: height,
    codepointStart: start,
    normalize: requiredValue<bool>('normalize'),
    ignoreShapes: requiredValue<bool>('ignore_shapes'),
  );
}

String _generateDart(IconConfig config, List<ManifestIcon> icons) {
  final buffer = StringBuffer()
    ..writeln('// GENERATED CODE - DO NOT MODIFY BY HAND.')
    ..writeln('// Generated by tool/generate.dart from icon_manifest.yaml.')
    ..writeln('// ignore_for_file: constant_identifier_names')
    ..writeln()
    ..writeln("import 'package:flutter/widgets.dart';")
    ..writeln()
    ..writeln('/// Custom icons used by Otzaria.')
    ..writeln('abstract final class ${config.className} {')
    ..writeln("  static const String fontFamily = '${config.fontFamily}';")
    ..writeln("  static const String fontPackage = '${config.packageName}';")
    ..writeln();
  for (final icon in icons) {
    buffer
      ..writeln('  /// `${icon.name}.svg`')
      ..writeln('  static const IconData ${icon.name} = IconData(')
      ..writeln('    0x${icon.codepoint.toRadixString(16)},')
      ..writeln('    fontFamily: fontFamily,')
      ..writeln('    fontPackage: fontPackage,')
      ..writeln('  );')
      ..writeln();
  }
  buffer.writeln('}');
  return buffer.toString();
}

String _generateGalleryCatalog(List<ManifestIcon> icons) {
  final buffer = StringBuffer()
    ..writeln('// GENERATED CODE - DO NOT MODIFY BY HAND.')
    ..writeln('// Generated by tool/generate.dart from icon_manifest.yaml.')
    ..writeln()
    ..writeln("import 'package:flutter/widgets.dart';")
    ..writeln("import 'package:otzaria_icons/otzaria_icons.dart';")
    ..writeln()
    ..writeln('final class GalleryIcon {')
    ..writeln('  const GalleryIcon(this.name, this.data);')
    ..writeln()
    ..writeln('  final String name;')
    ..writeln('  final IconData data;')
    ..writeln('}')
    ..writeln()
    ..writeln('const iconCatalog = <GalleryIcon>[');
  for (final icon in icons) {
    buffer.writeln(
      "  GalleryIcon('${icon.name}', OtzariaIcons.${icon.name}),",
    );
  }
  buffer.writeln('];');
  return buffer.toString();
}

String _generateTestExpectations(List<ManifestIcon> icons) {
  final buffer = StringBuffer()
    ..writeln('// GENERATED CODE - DO NOT MODIFY BY HAND.')
    ..writeln('// Generated by tool/generate.dart from icon_manifest.yaml.')
    ..writeln()
    ..writeln("import 'package:flutter/widgets.dart';")
    ..writeln("import 'package:otzaria_icons/otzaria_icons.dart';")
    ..writeln()
    ..writeln('const generatedIconExpectations = <String, IconData>{');
  for (final icon in icons) {
    buffer.writeln(
      "  '${icon.name}': OtzariaIcons.${icon.name},",
    );
  }
  buffer.writeln('};');
  return buffer.toString();
}

String _generateNotices(List<ManifestIcon> icons) {
  final modified = icons.where((icon) => icon.origin == 'modified_fluent');
  final buffer = StringBuffer()
    ..writeln('# Third-party notices')
    ..writeln()
    ..writeln(
      'This file is generated from `icon_manifest.yaml` by '
      '`tool/generate.dart`.',
    )
    ..writeln();
  if (modified.isEmpty) {
    buffer
      ..writeln(
        'No third-party icon artwork is included in the current release.',
      )
      ..writeln()
      ..writeln(
        'Every current icon is recorded as original artwork (`origin: custom`) '
        'and is released under GPL-3.0-only. See `LICENSE`.',
      );
  } else {
    buffer
      ..writeln('## Modified Fluent UI System Icons')
      ..writeln()
      ..writeln(
        'The following entries are derivative works and retain the provenance '
        'recorded in the manifest:',
      )
      ..writeln();
    for (final icon in modified) {
      buffer.writeln(
        '- `${icon.name}` — based on `${icon.basedOn}` at '
        '`${icon.upstreamCommit}`; license: ${icon.license}.',
      );
    }
  }
  return buffer.toString();
}

String _generateSvgCatalog(List<ManifestIcon> icons) {
  const cardWidth = 480;
  const cardHeight = 112;
  const columns = 2;
  final rows = (icons.length / columns).ceil();
  const width = cardWidth * columns;
  final height = 72 + rows * cardHeight + 24;
  final buffer = StringBuffer()
    ..writeln(
      '<svg xmlns="http://www.w3.org/2000/svg" '
      'width="$width" height="$height" viewBox="0 0 $width $height">',
    )
    ..writeln('<rect width="100%" height="100%" fill="#ffffff"/>')
    ..writeln(
      '<text x="24" y="42" font-family="Arial, sans-serif" font-size="24" '
      'font-weight="600" fill="#202020">Otzaria Icons</text>',
    );
  for (var index = 0; index < icons.length; index++) {
    final icon = icons[index];
    final x = (index % columns) * cardWidth + 16;
    final y = (index ~/ columns) * cardHeight + 64;
    final document = File(icon.source).readAsStringSync();
    final body = document.substring(
      document.indexOf('>') + 1,
      document.lastIndexOf('</svg>'),
    );
    buffer
      ..writeln(
        '<rect x="$x" y="$y" width="${cardWidth - 16}" '
        'height="${cardHeight - 8}" rx="12" fill="#f7f7f7" '
        'stroke="#dedede"/>',
      )
      ..writeln(
        '<svg x="${x + 20}" y="${y + 20}" width="64" height="64" '
        'viewBox="0 0 24 24" color="#202020">$body</svg>',
      )
      ..writeln(
        '<text x="${x + 104}" y="${y + 49}" '
        'font-family="Consolas, monospace" font-size="15" '
        'fill="#202020">${icon.name}</text>',
      )
      ..writeln(
        '<text x="${x + 104}" y="${y + 72}" '
        'font-family="Arial, sans-serif" font-size="13" '
        'fill="#666666">U+${icon.codepoint.toRadixString(16).toUpperCase()}'
        ' · ${icon.variant} · 24 px</text>',
      );
  }
  return '${buffer.toString()}</svg>\n';
}

String _generateWebCatalog(List<ManifestIcon> icons) {
  final iconData = icons
      .map(
        (icon) =>
            "    { name: '${icon.name}', codepoint: 0x${icon.codepoint.toRadixString(16)} },",
      )
      .join('\n');
  return r'''<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="קטלוג האייקונים של אוצריא">
  <title>אייקוני אוצריא</title>
  <style>
    @font-face {
      font-family: "OtzariaIcons";
      src: url("./lib/fonts/otzaria_icons.otf") format("opentype");
      font-display: block;
    }
    :root { color-scheme: light dark; --bg: #fafafa; --card: #fff; --text: #202020; --muted: #686868; --border: #e3e3e3; --accent: #6b4eff; }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: Arial, sans-serif; text-align: center; }
    main { width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0 64px; }
    h1 { margin: 0 0 8px; font-size: clamp(2rem, 5vw, 3.2rem); }
    .subtitle { margin: 0 0 30px; color: var(--muted); }
    .controls { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 12px; margin-bottom: 28px; }
    input[type="search"] { width: min(420px, 100%); min-height: 44px; padding: 0 16px; border: 1px solid var(--border); border-radius: 10px; background: var(--card); color: var(--text); font: inherit; }
    .size-control { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 10px; border: 1px solid var(--border); border-radius: 10px; background: var(--card); }
    button { width: 34px; height: 34px; border: 0; border-radius: 8px; background: transparent; color: var(--text); font-size: 22px; cursor: pointer; }
    button:hover { background: color-mix(in srgb, var(--accent) 12%, transparent); }
    input[type="range"] { width: 120px; accent-color: var(--accent); }
    #grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 14px; }
    .card { min-width: 0; padding: 24px 14px 16px; border: 1px solid var(--border); border-radius: 14px; background: var(--card); }
    .icon { display: grid; min-height: 124px; place-items: center; font-family: "OtzariaIcons"; font-size: var(--icon-size, 64px); line-height: 1; }
    .name { direction: ltr; overflow-wrap: anywhere; font: 13px/1.5 Consolas, monospace; color: var(--muted); }
    #empty { display: none; padding: 60px 0; color: var(--muted); }
    @media (prefers-color-scheme: dark) { :root { --bg: #171717; --card: #222; --text: #f3f3f3; --muted: #b9b9b9; --border: #3a3a3a; } }
  </style>
</head>
<body>
  <main>
    <h1>אייקוני אוצריא</h1>
    <p class="subtitle"><span id="count"></span> אייקונים בספרייה</p>
    <div class="controls">
      <input id="search" type="search" placeholder="חיפוש לפי שם האייקון" aria-label="חיפוש אייקונים">
      <div class="size-control" aria-label="שינוי גודל התצוגה">
        <button id="smaller" type="button" title="הקטנה" aria-label="הקטנת האייקונים">−</button>
        <input id="size" type="range" min="32" max="120" step="4" value="64" aria-label="גודל האייקונים">
        <button id="larger" type="button" title="הגדלה" aria-label="הגדלת האייקונים">+</button>
      </div>
    </div>
    <section id="grid" aria-live="polite"></section>
    <p id="empty">לא נמצאו אייקונים מתאימים.</p>
  </main>
  <script>
  const icons = [
{{ICON_DATA}}
  ];
  const grid = document.querySelector('#grid');
  const search = document.querySelector('#search');
  const size = document.querySelector('#size');
  const empty = document.querySelector('#empty');
  const count = document.querySelector('#count');

  function render() {
    const query = search.value.trim().toLowerCase();
    const visible = icons.filter(icon => icon.name.toLowerCase().includes(query));
    grid.replaceChildren(...visible.map(icon => {
      const card = document.createElement('article');
      card.className = 'card';
      const glyph = document.createElement('span');
      glyph.className = 'icon';
      glyph.setAttribute('aria-hidden', 'true');
      glyph.textContent = String.fromCodePoint(icon.codepoint);
      const name = document.createElement('div');
      name.className = 'name';
      name.textContent = icon.name;
      card.append(glyph, name);
      return card;
    }));
    count.textContent = visible.length;
    empty.style.display = visible.length ? 'none' : 'block';
  }

  function changeSize(delta) {
    size.value = Math.min(Number(size.max), Math.max(Number(size.min), Number(size.value) + delta));
    size.dispatchEvent(new Event('input'));
  }
  search.addEventListener('input', render);
  size.addEventListener('input', () => document.documentElement.style.setProperty('--icon-size', `${size.value}px`));
  document.querySelector('#smaller').addEventListener('click', () => changeSize(-4));
  document.querySelector('#larger').addEventListener('click', () => changeSize(4));
  render();
  </script>
</body>
</html>
'''
      .replaceFirst('{{ICON_DATA}}', iconData);
}

String _serializeManifest(IconManifest manifest) {
  final buffer = StringBuffer()
    ..writeln('schema_version: ${manifest.schemaVersion}')
    ..writeln('icons:');
  for (final icon in manifest.icons) {
    buffer
      ..writeln('  - id: ${icon.id}')
      ..writeln('    name: ${icon.name}')
      ..writeln('    source: ${icon.source}')
      ..writeln('    codepoint: 0x${icon.codepoint.toRadixString(16)}')
      ..writeln('    variant: ${icon.variant}')
      ..writeln('    size: ${icon.size}')
      ..writeln('    match_text_direction: ${icon.matchTextDirection}')
      ..writeln('    deprecated: ${icon.deprecated}')
      ..writeln('    upstream_status: ${icon.upstreamStatus}')
      ..writeln(
        '    upstream_equivalent: ${_yamlNullable(icon.upstreamEquivalent)}',
      )
      ..writeln('    origin: ${icon.origin}')
      ..writeln('    based_on: ${_yamlNullable(icon.basedOn)}')
      ..writeln('    author: ${icon.author}')
      ..writeln('    license: ${icon.license}')
      ..writeln('    upstream_commit: ${_yamlNullable(icon.upstreamCommit)}');
  }
  return buffer.toString();
}

String _yamlNullable(String? value) => value ?? 'null';

String _nextId(List<ManifestIcon> icons) {
  final numbers = icons
      .map((icon) => RegExp(r'^icon-(\d+)$').firstMatch(icon.id))
      .whereType<RegExpMatch>()
      .map((match) => int.parse(match.group(1)!));
  final next =
      numbers.isEmpty ? 1 : numbers.reduce((a, b) => a > b ? a : b) + 1;
  return 'icon-${next.toString().padLeft(4, '0')}';
}

int? _parseCodepoint(Object? value) {
  if (value is int) return value;
  if (value is String) {
    return int.tryParse(value.replaceFirst(RegExp(r'^0x'), ''), radix: 16);
  }
  return null;
}

Never _fail(String message) {
  stderr.writeln('ERROR: $message');
  exit(1);
}

final class IconManifest {
  IconManifest({
    required this.schemaVersion,
    required this.icons,
  });

  final int schemaVersion;
  final List<ManifestIcon> icons;
}

final class ManifestIcon {
  ManifestIcon({
    required this.id,
    required this.name,
    required this.source,
    required this.codepoint,
    required this.variant,
    required this.size,
    required this.matchTextDirection,
    required this.deprecated,
    required this.upstreamStatus,
    required this.upstreamEquivalent,
    required this.origin,
    required this.basedOn,
    required this.author,
    required this.license,
    required this.upstreamCommit,
  });

  final String id;
  final String name;
  final String source;
  final int codepoint;
  final String variant;
  final int size;
  final bool matchTextDirection;
  final bool deprecated;
  final String upstreamStatus;
  final String? upstreamEquivalent;
  final String origin;
  final String? basedOn;
  final String author;
  final String license;
  final String? upstreamCommit;
}

final class IconConfig {
  const IconConfig({
    required this.packageName,
    required this.className,
    required this.fontFamily,
    required this.fontFile,
    required this.sourceDirectory,
    required this.manifestFile,
    required this.dartOutput,
    required this.galleryOutput,
    required this.testExpectationsOutput,
    required this.noticesOutput,
    required this.catalogOutput,
    required this.webCatalogOutput,
    required this.canvasWidth,
    required this.canvasHeight,
    required this.codepointStart,
    required this.normalize,
    required this.ignoreShapes,
  });

  final String packageName;
  final String className;
  final String fontFamily;
  final String fontFile;
  final String sourceDirectory;
  final String manifestFile;
  final String dartOutput;
  final String galleryOutput;
  final String testExpectationsOutput;
  final String noticesOutput;
  final String catalogOutput;
  final String webCatalogOutput;
  final int canvasWidth;
  final int canvasHeight;
  final int codepointStart;
  final bool normalize;
  final bool ignoreShapes;
}
