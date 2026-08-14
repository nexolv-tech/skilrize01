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
  Future<void> clear();
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

  final FlutterSecureStorage _storage;

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
}
