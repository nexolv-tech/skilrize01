import 'package:flutter/material.dart';

/// The accent the web app uses, so the two clients read as one product
/// rather than two teams' guesses.
const _accent = Color(0xFF5A4CE8);

ThemeData skilrizeTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: _accent, brightness: brightness);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: scheme.surface,
    appBarTheme: AppBarTheme(
      backgroundColor: scheme.surface,
      surfaceTintColor: Colors.transparent,
      centerTitle: false,
      elevation: 0,
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: scheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: scheme.outlineVariant),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: scheme.surfaceContainerLowest,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: scheme.outlineVariant),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
  );
}

/// Contract and project statuses map to a colour the same way the web app's
/// badges do, so "delivered" does not mean one thing on one client and
/// something else on the other.
Color statusColor(ColorScheme scheme, String status) => switch (status) {
      'completed' || 'released' || 'active' => Colors.green.shade600,
      'delivered' || 'approved' || 'funded' => Colors.amber.shade700,
      'disputed' || 'cancelled' => scheme.error,
      _ => scheme.outline,
    };
