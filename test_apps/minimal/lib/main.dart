import 'package:flutter/material.dart';
import 'package:otzaria_icons/otzaria_icons.dart';

void main() => runApp(const MinimalIconApp());

class MinimalIconApp extends StatelessWidget {
  const MinimalIconApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      home: Scaffold(
        body: Center(
          child: Icon(OtzariaIcons.book_open_large_24_regular),
        ),
      ),
    );
  }
}
