import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import 'src/api/client.dart';
import 'src/api/endpoints.dart';
import 'src/api/token_store.dart';
import 'src/screens/home_shell.dart';
import 'src/screens/sign_in_screen.dart';
import 'src/state/session.dart';
import 'src/theme.dart';

/// Where the API lives.
///
/// `--dart-define=API_BASE_URL=...` at build time, defaulting to the local
/// stack. `10.0.2.2` is how the Android emulator reaches the host's
/// localhost; a real device needs the machine's LAN address passed in.
const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);

void main() {
  // The web build has no keystore, so it keeps tokens in memory only and
  // signs out on reload — see `MemoryTokenStore`'s docstring for why that is
  // the honest choice rather than reaching for localStorage.
  final tokens = kIsWeb ? MemoryTokenStore() : SecureTokenStore();
  final api = SkilrizeApi(ApiClient(baseUrl: apiBaseUrl, tokens: tokens));
  runApp(SkilrizeApp(session: Session(api: api, tokens: tokens)));
}

class SkilrizeApp extends StatefulWidget {
  const SkilrizeApp({super.key, required this.session});

  final Session session;

  @override
  State<SkilrizeApp> createState() => _SkilrizeAppState();
}

class _SkilrizeAppState extends State<SkilrizeApp> {
  @override
  void initState() {
    super.initState();
    widget.session.restore();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SkilRize',
      debugShowCheckedModeBanner: false,
      theme: skilrizeTheme(Brightness.light),
      darkTheme: skilrizeTheme(Brightness.dark),
      home: AnimatedBuilder(
        animation: widget.session,
        builder: (context, _) {
          final session = widget.session;
          if (session.isSignedIn) return HomeShell(session: session);
          return SignInScreen(session: session);
        },
      ),
    );
  }
}
