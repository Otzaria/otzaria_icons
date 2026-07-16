import 'dart:io';

import 'package:path_parsing/path_parsing.dart';
import 'package:xml/xml.dart';

/// Flattens the simple translate/scale wrapper used by legacy source artwork.
///
/// The path parser normalizes relative and shorthand commands before the
/// transform is applied, so this preserves the exact geometry rather than
/// redrawing or simplifying the icon.
void main(List<String> arguments) {
  if (arguments.isEmpty) {
    stderr.writeln(
      'Usage: dart run tool/flatten_svg_transforms.dart <svg> [<svg> ...]',
    );
    exitCode = 64;
    return;
  }

  for (final path in arguments) {
    final file = File(path);
    final source = file.readAsStringSync();
    final document = XmlDocument.parse(source);
    final groups = document.descendants
        .whereType<XmlElement>()
        .where((element) => element.name.local == 'g')
        .toList();
    if (groups.length != 1 ||
        groups.single.parentElement != document.rootElement) {
      throw FormatException('$path: expected one direct wrapper <g>');
    }

    final group = groups.single;
    final transform = group.getAttribute('transform');
    final match = RegExp(
      r'^\s*translate\(\s*([-+.\deE]+)[,\s]+([-+.\deE]+)\s*\)'
      r'\s*scale\(\s*([-+.\deE]+)(?:[,\s]+([-+.\deE]+))?\s*\)\s*$',
    ).firstMatch(transform ?? '');
    if (match == null) {
      throw FormatException('$path: unsupported transform "$transform"');
    }
    if (group.attributes.length != 1 ||
        group.children.whereType<XmlElement>().any(
              (element) => element.name.local != 'path',
            )) {
      throw FormatException('$path: wrapper must contain only path elements');
    }

    final translateX = double.parse(match.group(1)!);
    final translateY = double.parse(match.group(2)!);
    final scaleX = double.parse(match.group(3)!);
    final scaleY = double.parse(match.group(4) ?? match.group(3)!);
    var output = source;
    final pathPattern = RegExp(r'\bd="([^"]*)"');
    output = output.replaceAllMapped(pathPattern, (pathMatch) {
      final writer = _TransformedPathWriter(
        translateX,
        translateY,
        scaleX,
        scaleY,
      );
      writeSvgPathDataToPath(pathMatch.group(1), writer);
      return 'd="${writer.result}"';
    });
    output = output.replaceFirst(
      RegExp(r'<g\s+transform="[^"]*">'),
      '',
    );
    output = output.replaceFirst('</g>', '');
    file.writeAsStringSync('${output.trimRight()}\n');
    stdout.writeln('Flattened $path');
  }
}

class _TransformedPathWriter extends PathProxy {
  _TransformedPathWriter(
    this.translateX,
    this.translateY,
    this.scaleX,
    this.scaleY,
  );

  final double translateX;
  final double translateY;
  final double scaleX;
  final double scaleY;
  final StringBuffer _buffer = StringBuffer();

  String get result => _buffer.toString();

  String _x(double value) => _number(value * scaleX + translateX);
  String _y(double value) => _number(value * scaleY + translateY);

  @override
  void moveTo(double x, double y) => _buffer.write('M${_x(x)} ${_y(y)}');

  @override
  void lineTo(double x, double y) => _buffer.write('L${_x(x)} ${_y(y)}');

  @override
  void cubicTo(
    double x1,
    double y1,
    double x2,
    double y2,
    double x3,
    double y3,
  ) {
    _buffer.write(
      'C${_x(x1)} ${_y(y1)} ${_x(x2)} ${_y(y2)} ${_x(x3)} ${_y(y3)}',
    );
  }

  @override
  void close() => _buffer.write('Z');
}

String _number(double value) {
  final rounded = value.toStringAsFixed(6);
  return rounded
      .replaceFirst(RegExp(r'0+$'), '')
      .replaceFirst(RegExp(r'\.$'), '')
      .replaceFirst(RegExp(r'^-0$'), '0');
}
