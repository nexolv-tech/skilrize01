/// Normalised API failure.
///
/// DRF answers a serializer rejection as `{field: ["msg"]}` and everything
/// else as `{detail, code}`. The web client (`web/lib/api.ts`) flattens both
/// into one shape so callers branch on a code rather than sniffing the body;
/// this is the same contract in Dart, deliberately — a screen that handles
/// `two_factor_required` should not care which client it is written against.
class ApiError implements Exception {
  ApiError(this.status, this.code, this.message, [this.fields = const {}]);

  final int status;

  /// The server's own machine-readable reason: `invalid_credentials`,
  /// `two_factor_required`, `not_connected`, `upgrade_required`, and so on.
  /// Branch on this, never on [message].
  final String code;

  final String message;

  /// Per-field messages, when the server rejected a form.
  final Map<String, String> fields;

  /// Parse a DRF error body into the flattened shape.
  factory ApiError.fromResponse(int status, Object? body) {
    if (body is! Map) {
      return ApiError(status, 'error', 'Something went wrong. Please try again.');
    }

    final data = Map<String, dynamic>.from(body);
    final code = data['code'] is String ? data['code'] as String : 'error';

    final fields = <String, String>{};
    for (final entry in data.entries) {
      if (entry.key == 'detail' || entry.key == 'code') continue;
      final value = entry.value;
      final first = value is List && value.isNotEmpty ? value.first : value;
      if (first is String) fields[entry.key] = first;
    }

    final detail = data['detail'] is String
        ? data['detail'] as String
        : (fields.values.isNotEmpty
            ? fields.values.first
            : 'Something went wrong. Please try again.');

    return ApiError(status, code, detail, fields);
  }

  @override
  String toString() => 'ApiError($status, $code): $message';
}
