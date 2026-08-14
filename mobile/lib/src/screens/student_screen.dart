import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../api/api_error.dart';
import '../models/misc.dart';
import '../state/session.dart';

/// Student verification — mirrors `web/components/student.tsx`'s single
/// step-by-step card. `application.next_step` (server-decided, never
/// re-derived here — see the model doc) picks which form shows; some
/// universities skip the ID card step entirely (`id_card_required`).
class StudentScreen extends StatefulWidget {
  const StudentScreen({super.key, required this.session});
  final Session session;

  @override
  State<StudentScreen> createState() => _StudentScreenState();
}

class _StudentScreenState extends State<StudentScreen> {
  StudentApplication? _application;
  bool _loaded = false;
  bool _busy = false;
  ApiError? _error;

  final _email = TextEditingController();
  final _code = TextEditingController();
  XFile? _pickedFile;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final application = await widget.session.api.studentApplication();
      if (mounted) {
        setState(() {
          _application = application;
          _loaded = true;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loaded = true);
    }
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } on ApiError catch (e) {
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _start() => _run(() async {
        final application =
            await widget.session.api.startStudentVerification(_email.text.trim());
        setState(() {
          _application = application;
          _email.clear();
        });
      });

  Future<void> _confirm() => _run(() async {
        final application = await widget.session.api.confirmStudentEmail(_code.text.trim());
        setState(() {
          _application = application;
          _code.clear();
        });
        await widget.session.refreshUser();
      });

  Future<void> _pickFile() async {
    final file = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 90);
    if (file != null) setState(() => _pickedFile = file);
  }

  Future<void> _upload() => _run(() async {
        final file = _pickedFile;
        if (file == null) return;
        final bytes = await file.readAsBytes();
        final application =
            await widget.session.api.uploadStudentIdCard(bytes, file.name);
        setState(() {
          _application = application;
          _pickedFile = null;
        });
      });

  @override
  Widget build(BuildContext context) {
    final user = widget.session.user;
    final application = _application;

    return Scaffold(
      appBar: AppBar(title: const Text('Student verification')),
      body: !_loaded
          ? const Center(child: CircularProgressIndicator())
          : (user?.isVerifiedStudent ?? false)
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.verified, size: 48, color: Colors.green),
                        const SizedBox(height: 12),
                        Text('You are verified at ${user?.universityName ?? 'your university'}.'),
                      ],
                    ),
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (application?.status == 'rejected')
                      Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: _Banner(
                          text: application!.rejectionReason.isEmpty
                              ? 'Your last application was not approved.'
                              : application.rejectionReason,
                        ),
                      ),
                    if (_error != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: _Banner(text: _error!.message),
                      ),
                    if (application == null || application.nextStep == 'start_again') ...[
                      TextField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        decoration: const InputDecoration(
                          labelText: 'University email',
                          hintText: 'you@university.edu',
                        ),
                      ),
                      const SizedBox(height: 12),
                      FilledButton(
                        onPressed: _busy ? null : _start,
                        child: const Text('Send code'),
                      ),
                    ] else if (application.nextStep == 'confirm_email') ...[
                      Text('We sent a six-digit code to ${application.universityEmail}.'),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _code,
                        keyboardType: TextInputType.number,
                        maxLength: 6,
                        decoration: const InputDecoration(labelText: 'Code'),
                      ),
                      FilledButton(
                        onPressed: _busy ? null : _confirm,
                        child: const Text('Confirm'),
                      ),
                    ] else if (application.nextStep == 'upload_id_card') ...[
                      Text(
                        '${application.universityEmail} confirmed. '
                        '${application.universityName ?? 'Your university'} also asks for your student ID card.',
                      ),
                      const SizedBox(height: 12),
                      OutlinedButton.icon(
                        onPressed: _pickFile,
                        icon: const Icon(Icons.photo_camera_outlined),
                        label: Text(_pickedFile == null ? 'Choose a photo' : _pickedFile!.name),
                      ),
                      const SizedBox(height: 12),
                      FilledButton(
                        onPressed: _busy || _pickedFile == null ? null : _upload,
                        child: const Text('Submit for review'),
                      ),
                    ] else if (application.nextStep == 'wait_for_review') ...[
                      _Banner(
                        text: 'We are reviewing your ${application.universityName ?? ''} '
                            'verification. You will be notified as soon as it is decided.',
                        tone: Colors.orange,
                      ),
                    ],
                  ],
                ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.text, this.tone = Colors.red});
  final String text;
  final Color tone;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: tone.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(text),
      );
}
