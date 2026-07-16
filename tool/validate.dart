import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:xml/xml.dart';
import 'package:yaml/yaml.dart';

const _namePattern = r'^[a-z][a-z0-9_]*_24_(regular|filled)$';

void main(List<String> arguments) {
  final root = Directory.current;
  final sourceDir = Directory(p.join(root.path, 'assets_src', 'svg'));
  final manifestFile = File(p.join(root.path, 'icon_manifest.yaml'));
  final errors = <String>[];
  final warnings = <String>[];

  if (!sourceDir.existsSync()) {
    errors.add('Missing source directory: ${sourceDir.path}');
  }
  if (!manifestFile.existsSync()) {
    errors.add('Missing icon_manifest.yaml');
  }

  final files = sourceDir.existsSync()
      ? sourceDir
          .listSync()
          .whereType<File>()
          .where((file) => p.extension(file.path).toLowerCase() == '.svg')
          .toList()
      : <File>[];
  files.sort((a, b) => a.path.compareTo(b.path));

  final normalizedNames = <String, String>{};
  final sourceNames = <String>{};
  for (final file in files) {
    final fileName = p.basenameWithoutExtension(file.path);
    sourceNames.add(fileName);
    if (!RegExp(_namePattern).hasMatch(fileName)) {
      errors.add(
        '$fileName.svg: name must match $_namePattern',
      );
    }
    final normalized = fileName
        .replaceAll(RegExp(r'[-\s]+'), '_')
        .replaceAll(RegExp(r'_+'), '_')
        .toLowerCase();
    final previous = normalizedNames[normalized];
    if (previous != null) {
      errors.add(
        '$fileName.svg collides with $previous.svg after normalization',
      );
    } else {
      normalizedNames[normalized] = fileName;
    }

    try {
      final document = XmlDocument.parse(file.readAsStringSync());
      final rootElement = document.rootElement;
      if (rootElement.name.local != 'svg') {
        errors.add('$fileName.svg: root element is not <svg>');
        continue;
      }
      if (rootElement.getAttribute('viewBox') != '0 0 24 24') {
        errors.add('$fileName.svg: viewBox must be exactly "0 0 24 24"');
      }
      if (rootElement.getAttribute('width') != '24' ||
          rootElement.getAttribute('height') != '24') {
        errors.add('$fileName.svg: width and height must both be exactly "24"');
      }
      if (document.descendants.whereType<XmlElement>().any(
            (element) =>
                element.name.local == 'style' || element.name.local == 'script',
          )) {
        errors.add('$fileName.svg: style/script elements are not allowed');
      }
      if (document.descendants.whereType<XmlElement>().any(
            (element) => element.getAttribute('transform') != null,
          )) {
        errors.add(
          '$fileName.svg: transforms are not allowed; flatten geometry into '
          'final 24x24 path coordinates',
        );
      }
      if (document.descendants.whereType<XmlElement>().any(
            (element) =>
                element.name.local == 'line' ||
                element.getAttribute('stroke') != null ||
                element.getAttribute('stroke-width') != null,
          )) {
        errors.add('$fileName.svg: strokes must be converted to filled paths');
      }
      const allowedElements = {'svg', 'path'};
      final unsupportedElements = document.descendants
          .whereType<XmlElement>()
          .map((element) => element.name.local)
          .where((name) => !allowedElements.contains(name))
          .toSet();
      if (unsupportedElements.isNotEmpty) {
        errors.add(
          '$fileName.svg: only direct path elements are allowed; found '
          '${unsupportedElements.toList()..sort()}',
        );
      }
      final paths = document.descendants
          .whereType<XmlElement>()
          .where((element) => element.name.local == 'path')
          .toList();
      if (paths.any((path) => path.parentElement != rootElement)) {
        errors.add('$fileName.svg: every path must be a direct child of <svg>');
      }
      if (paths.isEmpty) {
        errors.add('$fileName.svg: no path elements found');
      } else if (paths.length > 20) {
        warnings.add(
          '$fileName.svg: unusually high path count (${paths.length})',
        );
      }
    } on XmlParserException catch (error) {
      errors.add('$fileName.svg: invalid XML ($error)');
    }
  }

  if (manifestFile.existsSync()) {
    final yaml = loadYaml(manifestFile.readAsStringSync());
    if (yaml is! YamlMap || yaml['icons'] is! YamlList) {
      errors.add('icon_manifest.yaml: "icons" must be a list');
    } else {
      if (yaml['schema_version'] != 1) {
        errors.add('icon_manifest.yaml: unsupported schema_version');
      }
      final ids = <String>{};
      final names = <String>{};
      final codepoints = <int>{};
      for (final item in yaml['icons'] as YamlList) {
        if (item is! YamlMap) {
          errors.add('icon_manifest.yaml: every icon must be a map');
          continue;
        }
        final id = item['id'];
        final name = item['name'];
        final codepoint = item['codepoint'];
        final source = item['source'];
        final variant = item['variant'];
        final size = item['size'];
        final matchTextDirection = item['match_text_direction'];
        final deprecated = item['deprecated'];
        final license = item['license'];
        final upstreamStatus = item['upstream_status'];
        final upstreamEquivalent = item['upstream_equivalent'];
        final origin = item['origin'];
        final basedOn = item['based_on'];
        final author = item['author'];
        final upstreamCommit = item['upstream_commit'];
        if (id is! String ||
            !RegExp(r'^icon-\d{4,}$').hasMatch(id) ||
            !ids.add(id)) {
          errors.add('icon_manifest.yaml: duplicate or invalid id "$id"');
        }
        if (name is! String || !names.add(name)) {
          errors.add('icon_manifest.yaml: duplicate or invalid name "$name"');
        } else if (!sourceNames.contains(name)) {
          errors.add('icon_manifest.yaml: "$name" has no matching SVG');
        }
        final parsedCodepoint = _parseCodepoint(codepoint);
        if (parsedCodepoint == null || !codepoints.add(parsedCodepoint)) {
          errors.add(
            'icon_manifest.yaml: duplicate or invalid codepoint "$codepoint"',
          );
        } else if (parsedCodepoint < 0xe000 || parsedCodepoint > 0xf8ff) {
          errors.add(
            'icon_manifest.yaml: "$name" codepoint must be in '
            '0xE000–0xF8FF',
          );
        }
        if (source != 'assets_src/svg/$name.svg') {
          errors.add('icon_manifest.yaml: "$name" has an invalid source path');
        }
        final expectedVariant =
            name is String && name.endsWith('_filled') ? 'filled' : 'regular';
        if (variant != expectedVariant) {
          errors.add('icon_manifest.yaml: "$name" has an invalid variant');
        }
        if (size != 24) {
          errors.add('icon_manifest.yaml: "$name" size must be 24');
        }
        if (matchTextDirection is! bool || deprecated is! bool) {
          errors.add(
            'icon_manifest.yaml: "$name" direction/deprecated flags '
            'must be booleans',
          );
        }
        if (license is! String || license.trim().isEmpty) {
          errors.add('icon_manifest.yaml: "$name" has no license status');
        } else if (license == 'pending-review') {
          warnings.add(
            'icon_manifest.yaml: "$name" license is pending review',
          );
        }
        if (upstreamStatus is! String ||
            !{'missing', 'available', 'not-applicable'}
                .contains(upstreamStatus)) {
          errors.add(
            'icon_manifest.yaml: "$name" has invalid upstream_status',
          );
        }
        if (upstreamStatus == 'available' &&
            (upstreamEquivalent is! String || upstreamEquivalent.isEmpty)) {
          errors.add(
            'icon_manifest.yaml: "$name" needs upstream_equivalent',
          );
        }
        if (origin is! String ||
            !{'custom', 'modified_fluent'}.contains(origin)) {
          errors.add('icon_manifest.yaml: "$name" has invalid origin');
        }
        if (origin == 'modified_fluent' &&
            (basedOn is! String ||
                basedOn.isEmpty ||
                upstreamCommit is! String ||
                upstreamCommit.isEmpty)) {
          errors.add(
            'icon_manifest.yaml: "$name" modified_fluent provenance '
            'is incomplete',
          );
        }
        if (author is! String || author.trim().isEmpty) {
          errors.add('icon_manifest.yaml: "$name" has no author');
        }
      }
      final unregistered = sourceNames.difference(names);
      if (unregistered.isNotEmpty) {
        warnings.add(
          'SVG files not yet allocated in manifest: '
          '${unregistered.toList()..sort()}',
        );
      }
    }
  }

  for (final warning in warnings) {
    stderr.writeln('WARNING: $warning');
  }
  for (final error in errors) {
    stderr.writeln('ERROR: $error');
  }
  stdout.writeln(
    'Validated ${files.length} SVG file(s): '
    '${errors.length} error(s), ${warnings.length} warning(s).',
  );
  if (errors.isNotEmpty) {
    exitCode = 1;
  }
}

int? _parseCodepoint(Object? value) {
  if (value is int) return value;
  if (value is String) {
    return int.tryParse(value.replaceFirst(RegExp(r'^0x'), ''), radix: 16);
  }
  return null;
}
