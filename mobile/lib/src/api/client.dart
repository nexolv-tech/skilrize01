import 'dart:convert';

import 'package:http/http.dart' as http;

import 'api_error.dart';
import 'token_store.dart';

/// The SkilRize API client.
///
/// **Bearer, not cookies — the one place this deliberately differs from the
/// web client.** `accounts/auth.py`'s `CookieJWTAuthentication` says it
/// plainly: "Web sends cookies; mobile sends `Authorization: Bearer`. Only
/// the cookie path is CSRF-checked, because only the cookie path is
/// something a browser will attach automatically to a cross-site request."
/// Taking the bearer path means this client never needs a CSRF token, never
/// needs a cookie jar that survives an app restart, and cannot be made to
/// act on a forged cross-site request at all — there is no ambient
/// credential for a browser to attach on its behalf.
///
/// The tokens themselves come from [TokenStore], which on a real device is
/// the platform keystore rather than anything this class can read back.
class ApiClient {
  ApiClient({required this.baseUrl, required this.tokens, http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  final String baseUrl;
  final TokenStore tokens;
  final http.Client _http;

  /// Which marketplace surface the client is looking at, sent on every
  /// request exactly as the web client does. It is a request, not an
  /// instruction: the server re-derives entitlement from the session and
  /// answers 403 rather than trusting this, so a tampered value buys
  /// nothing (`core/scope.py`).
  String surface = 'global';

  /// Shared by every caller, so two requests that both hit a 401 await one
  /// refresh instead of racing. Refresh tokens rotate and presenting a
  /// rotated one is treated by the server as theft — it revokes the whole
  /// family — so a race here would look exactly like an attack and sign the
  /// user out (`accounts/auth.py`, `TokenReuseDetected`).
  Future<bool>? _refreshInFlight;

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final cleaned = query?.map((k, v) => MapEntry(k, '$v'))
      ?..removeWhere((_, v) => v.isEmpty);
    return Uri.parse('$baseUrl/api/v1$path').replace(
      queryParameters: (cleaned == null || cleaned.isEmpty) ? null : cleaned,
    );
  }

  /// Declares this client non-browser, which is what makes the sign-in
  /// endpoints return the bearer tokens in the response body instead of only
  /// setting cookies (`accounts/views.py`, `NATIVE_CLIENT_HEADER`). Without
  /// it the server answers a native client exactly as it answers the web
  /// app — cookies it has no jar for and no tokens it can use.
  static const nativeClientHeader = {'X-Skilrize-Client': 'native'};

  Future<Map<String, String>> _headers({bool json = true}) async {
    final access = await tokens.access();
    return {
      if (json) 'Content-Type': 'application/json',
      if (surface != 'global') 'X-Skilrize-Surface': surface,
      if (access != null) 'Authorization': 'Bearer $access',
      ...nativeClientHeader,
    };
  }

  Future<dynamic> get(String path, [Map<String, dynamic>? query]) =>
      _send('GET', path, query: query);

  Future<dynamic> post(String path, [Object? body]) => _send('POST', path, body: body);

  Future<dynamic> patch(String path, [Object? body]) => _send('PATCH', path, body: body);

  Future<dynamic> delete(String path) => _send('DELETE', path);

  /// Multipart upload — the one request shape `_send` can't cover, since it
  /// always JSON-encodes `body`. Used only by the student ID card upload.
  Future<dynamic> uploadFile(String path, String field, List<int> bytes, String filename) async {
    final request = http.MultipartRequest('POST', _uri(path))
      ..headers.addAll(await _headers(json: false))
      ..files.add(http.MultipartFile.fromBytes(field, bytes, filename: filename));

    final streamed = await _http.send(request);
    final response = await http.Response.fromStream(streamed);

    if (response.statusCode == 401 && path != '/auth/refresh/') {
      if (await _refresh()) {
        return uploadFile(path, field, bytes, filename);
      }
    }

    if (response.statusCode == 204 || response.bodyBytes.isEmpty) return null;
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode >= 400) {
      throw ApiError.fromResponse(response.statusCode, decoded);
    }
    return decoded;
  }

  Future<dynamic> _send(
    String method,
    String path, {
    Object? body,
    Map<String, dynamic>? query,
    bool retrying = false,
  }) async {
    final request = http.Request(method, _uri(path, query))
      ..headers.addAll(await _headers());
    if (body != null) request.body = jsonEncode(body);

    final streamed = await _http.send(request);
    final response = await http.Response.fromStream(streamed);

    // An expired access token is the expected case, not an error: rotate
    // once and replay. `retrying` is what stops a refresh loop recursing.
    if (response.statusCode == 401 && !retrying && path != '/auth/refresh/') {
      if (await _refresh()) {
        return _send(method, path, body: body, query: query, retrying: true);
      }
    }

    if (response.statusCode == 204 || response.bodyBytes.isEmpty) return null;

    // `response.body` decodes using the charset in the Content-Type header
    // and falls back to **latin-1** when there isn't one. DRF answers
    // `application/json` with no charset — correctly, since JSON is defined
    // as UTF-8 — so reading `.body` silently mangles every non-ASCII
    // character: an Urdu project title, a name with an accent, the masked
    // `m•••r@example.com` hint on the device-verification screen. Decoding
    // the raw bytes as UTF-8 is the only correct read of this API.
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode >= 400) {
      throw ApiError.fromResponse(response.statusCode, decoded);
    }
    return decoded;
  }

  Future<bool> _refresh() {
    return _refreshInFlight ??= () async {
      try {
        final refresh = await tokens.refresh();
        if (refresh == null) return false;

        // `/auth/refresh/` reads the token from the body when there is no
        // cookie — the fallback that makes a non-browser client possible at
        // all (`accounts/views.py`).
        final response = await _http.post(
          _uri('/auth/refresh/'),
          headers: {'Content-Type': 'application/json', ...nativeClientHeader},
          body: jsonEncode({'refresh': refresh}),
        );
        if (response.statusCode != 200) {
          await tokens.clear();
          return false;
        }
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        await tokens.save(
          access: data['access'] as String?,
          refresh: data['refresh'] as String?,
        );
        return true;
      } catch (_) {
        return false;
      } finally {
        // Cleared after settling so the next 401 starts a fresh one.
        _refreshInFlight = null;
      }
    }();
  }

  void close() => _http.close();
}
