import 'package:flutter/foundation.dart';

import '../api/api_error.dart';
import '../api/endpoints.dart';
import '../api/token_store.dart';
import '../models/models.dart';

/// What the sign-in flow is currently waiting on.
///
/// The server decides which of these applies, never the client — an account
/// with an authenticator is always sent down the TOTP path, and the emailed
/// path is only ever offered to accounts that have none. Letting the client
/// choose would be letting an attacker choose (`accounts/views.py`).
enum AuthStage {
  signedOut,

  /// Password accepted; a TOTP or recovery code is due.
  twoFactorRequired,

  /// No authenticator, unrecognised device; a code went to the user's email.
  deviceVerificationRequired,

  signedIn,
}

/// Session state for the whole app.
///
/// A `ChangeNotifier` rather than a heavier state-management dependency:
/// there is exactly one piece of global state here (who is signed in), and
/// everything else is per-screen. Adding Riverpod or Bloc for one object
/// would be architecture ahead of the problem.
class Session extends ChangeNotifier {
  Session({required this.api, required this.tokens});

  final SkilrizeApi api;
  final TokenStore tokens;

  AuthStage stage = AuthStage.signedOut;
  User? user;
  String? error;
  bool busy = false;

  /// Set alongside [AuthStage.twoFactorRequired] /
  /// [AuthStage.deviceVerificationRequired]; meaningless otherwise.
  String? challenge;

  /// A masked hint at where an emailed code went — enough to reassure the
  /// right person and useless to anyone else.
  String? sentTo;

  /// Whether this deployment can actually deliver a push, from `/config/`.
  bool pushEnabled = false;

  bool get isSignedIn => stage == AuthStage.signedIn && user != null;

  /// Restore a session from stored tokens on launch. Returns quietly when
  /// there is nothing stored or the token no longer works — a failed restore
  /// is a signed-out app, not an error worth showing anyone.
  Future<void> restore() async {
    _set(busy: true);
    try {
      final config = await api.config();
      pushEnabled = config['push_enabled'] == true;
    } catch (_) {
      // A config call that fails should not block sign-in.
    }

    if (await tokens.access() == null) {
      _set(busy: false, stage: AuthStage.signedOut);
      return;
    }
    try {
      user = await api.me();
      _set(busy: false, stage: AuthStage.signedIn);
    } catch (_) {
      await tokens.clear();
      _set(busy: false, stage: AuthStage.signedOut);
    }
  }

  Future<void> signIn(String email, String password) async {
    _set(busy: true, error: null);
    try {
      final result = await api.login(email, password);

      if (result['two_factor_required'] == true) {
        challenge = result['challenge'] as String?;
        _set(busy: false, stage: AuthStage.twoFactorRequired);
        return;
      }
      if (result['device_verification_required'] == true) {
        challenge = result['challenge'] as String?;
        sentTo = result['sent_to'] as String?;
        _set(busy: false, stage: AuthStage.deviceVerificationRequired);
        return;
      }
      await _completeSignIn(result);
    } on ApiError catch (e) {
      _set(busy: false, error: e.message);
    }
  }

  /// Submit the six-digit code for whichever challenge is outstanding.
  Future<void> submitCode(String code) async {
    if (challenge == null) return;
    _set(busy: true, error: null);
    try {
      final result = stage == AuthStage.twoFactorRequired
          ? await api.loginTwoFactor(challenge!, code)
          : await api.loginVerifyDevice(challenge!, code);
      await _completeSignIn(result);
    } on ApiError catch (e) {
      _set(busy: false, error: e.message);
    }
  }

  Future<void> _completeSignIn(Map<String, dynamic> result) async {
    await tokens.save(
      access: result['access'] as String?,
      refresh: result['refresh'] as String?,
    );
    user = User.fromJson(Map<String, dynamic>.from(result['user'] as Map));
    challenge = null;
    sentTo = null;
    _set(busy: false, stage: AuthStage.signedIn);
  }

  Future<void> signOut() async {
    // Hand the refresh token back so the server revokes the session rather
    // than merely losing track of it on this device.
    final refresh = await tokens.refresh();
    try {
      await api.logout(refresh);
    } catch (_) {
      // Signing out locally must succeed even if the network does not.
    }
    await tokens.clear();
    user = null;
    challenge = null;
    _set(busy: false, stage: AuthStage.signedOut);
  }

  void cancelChallenge() {
    challenge = null;
    sentTo = null;
    _set(stage: AuthStage.signedOut, error: null);
  }

  void _set({bool? busy, AuthStage? stage, String? error}) {
    if (busy != null) this.busy = busy;
    if (stage != null) this.stage = stage;
    this.error = error;
    notifyListeners();
  }
}
