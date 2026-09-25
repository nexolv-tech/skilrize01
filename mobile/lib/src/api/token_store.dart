import 'dart:convert';
import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Where the bearer tokens live between launches.
///
/// An interface rather than a concrete class because the tests need to drive
/// the refresh-once-on-401 path without a platform keystore behind them, and
/// because the honest storage answer differs by platform: the Android
/// Keystore and the iOS Keychain are real secure storage, and the web build
/// has nothing equivalent (see [WebTokenStore]).
abstract class TokenStore {
  Future<String?> access();
  Future<String?> refresh();
  Future<void> save({String? access, String? refresh});

  /// Forgets the session. The device id stays: signing out and back in on
  /// the same phone is not a new device.
  Future<void> clear();

  /// This install's device id, created on first use and kept for good.
  ///
  /// Sent as `X-Skilrize-Device` so the server recognises this phone across
  /// app updates (`accounts/devices.py`). Before it, the phone was known by
  /// its user agent, which every Dart update changes and every copy of the
  /// app shares.
  Future<String> deviceId();
}

/// 32 random bytes, URL-safe: the shape `accounts/devices.py` accepts.
String newDeviceId() {
  final random = Random.secure();
  final bytes = List<int>.generate(32, (_) => random.nextInt(256));
  return base64Url.encode(bytes).replaceAll('=', '');
}

/// Platform-backed storage: Android Keystore, iOS Keychain.
///
/// `flutter_secure_storage` is the one dependency here that genuinely earns
/// itself — hand-rolling keystore/keychain bindings for two platforms is not
/// a thing to improvise on the component holding session tokens.
class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
            );

  static const _accessKey = 'skilrize.access';
  static const _refreshKey = 'skilrize.refresh';
  static const _deviceKey = 'skilrize.device';

  final FlutterSecureStorage _storage;
  String? _device;

  @override
  Future<String?> access() => _storage.read(key: _accessKey);

  @override
  Future<String?> refresh() => _storage.read(key: _refreshKey);

  @override
  Future<void> save({String? access, String? refresh}) async {
    if (access != null) await _storage.write(key: _accessKey, value: access);
    if (refresh != null) await _storage.write(key: _refreshKey, value: refresh);
  }

  @override
  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }

  @override
  Future<String> deviceId() async {
    final known = _device ?? await _storage.read(key: _deviceKey);
    if (known != null) return _device = known;
    final created = newDeviceId();
    await _storage.write(key: _deviceKey, value: created);
    return _device = created;
  }
}

/// In-memory only, for the web build.
///
/// **Deliberately does not persist, and this is the honest choice rather than
/// a missing feature.** The browser has no keystore; the options are
/// `localStorage` (readable by any script that gets injected into the page —
/// exactly what the web client avoids by using HttpOnly cookies) or nothing.
/// A refresh of the tab therefore signs the user out here, which is the
/// correct trade for a build that exists so the app can be *run and verified*
/// on a machine with no Android emulator. A shipped web client should use the
/// cookie path the Next.js app already uses, not this.
class MemoryTokenStore implements TokenStore {
  String? _access;
  String? _refresh;
  final String _device = newDeviceId();

  @override
  Future<String?> access() async => _access;

  @override
  Future<String?> refresh() async => _refresh;

  @override
  Future<void> save({String? access, String? refresh}) async {
    if (access != null) _access = access;
    if (refresh != null) _refresh = refresh;
  }

  @override
  Future<void> clear() async {
    _access = null;
    _refresh = null;
  }

  @override
  Future<String> deviceId() async => _device;
}
