import 'package:flutter/material.dart';

import '../state/session.dart';

/// Sign-in, including both second-factor paths.
///
/// One screen with three states rather than three routes: the user is in a
/// single continuous flow, and a challenge is only ever valid for a few
/// minutes, so navigating away from it and back is not something to design
/// for.
class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key, required this.session});

  final Session session;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _code = TextEditingController();

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    final awaitingCode = session.stage == AuthStage.twoFactorRequired ||
        session.stage == AuthStage.deviceVerificationRequired;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: awaitingCode ? _codeForm(context) : _credentialsForm(context),
            ),
          ),
        ),
      ),
    );
  }

  Widget _credentialsForm(BuildContext context) {
    final session = widget.session;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('SkilRize', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 6),
        Text('Welcome back', style: Theme.of(context).textTheme.bodyMedium),
        const SizedBox(height: 24),
        if (session.error != null) _errorBanner(context, session.error!),
        TextField(
          key: const Key('email'),
          controller: _email,
          keyboardType: TextInputType.emailAddress,
          autocorrect: false,
          decoration: const InputDecoration(labelText: 'Email'),
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('password'),
          controller: _password,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Password'),
          onSubmitted: (_) => _submitCredentials(),
        ),
        const SizedBox(height: 20),
        FilledButton(
          key: const Key('signIn'),
          onPressed: session.busy ? null : _submitCredentials,
          child: session.busy
              ? const SizedBox(
                  height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Sign in'),
        ),
      ],
    );
  }

  Widget _codeForm(BuildContext context) {
    final session = widget.session;
    final viaEmail = session.stage == AuthStage.deviceVerificationRequired;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Icon(viaEmail ? Icons.mail_outline : Icons.shield_outlined, size: 36),
        const SizedBox(height: 16),
        Text(
          viaEmail ? "Confirm it's you" : 'Enter your code',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        Text(
          viaEmail
              ? "You're signing in from a device we haven't seen before, so we sent a "
                  'six-digit code to ${session.sentTo ?? 'your email'}.'
              : 'Open your authenticator app and enter the six-digit code. '
                  'A recovery code works too.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 20),
        if (session.error != null) _errorBanner(context, session.error!),
        TextField(
          key: const Key('code'),
          controller: _code,
          keyboardType: TextInputType.number,
          textAlign: TextAlign.center,
          decoration: const InputDecoration(labelText: 'Code', hintText: '123456'),
          onSubmitted: (_) => _submitCode(),
        ),
        const SizedBox(height: 20),
        FilledButton(
          key: const Key('verify'),
          onPressed: session.busy ? null : _submitCode,
          child: session.busy
              ? const SizedBox(
                  height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Verify and sign in'),
        ),
        TextButton(
          onPressed: () {
            _code.clear();
            session.cancelChallenge();
          },
          child: const Text('Back to sign in'),
        ),
      ],
    );
  }

  Widget _errorBanner(BuildContext context, String message) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(message, style: TextStyle(color: scheme.onErrorContainer)),
    );
  }

  void _submitCredentials() {
    widget.session.signIn(_email.text.trim(), _password.text);
  }

  void _submitCode() {
    widget.session.submitCode(_code.text.trim());
  }
}
