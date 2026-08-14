import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/misc.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';

class ChallengesScreen extends StatelessWidget {
  const ChallengesScreen({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Challenges')),
      body: AsyncList<Challenge>(
        loader: () async => (await session.api.challenges()).results,
        emptyIcon: Icons.emoji_events_outlined,
        emptyText: 'No challenges open right now.',
        itemBuilder: (context, challenge) => Card(
          margin: const EdgeInsets.only(bottom: 10),
          child: ListTile(
            title: Text(challenge.title),
            subtitle: Text(challenge.isOpen ? 'Open' : 'Closed'),
            trailing: challenge.myParticipationId != null
                ? const Icon(Icons.check_circle_outline)
                : null,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => ChallengeDetailScreen(session: session, slug: challenge.slug),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ChallengeDetailScreen extends StatefulWidget {
  const ChallengeDetailScreen({super.key, required this.session, required this.slug});
  final Session session;
  final String slug;

  @override
  State<ChallengeDetailScreen> createState() => _ChallengeDetailScreenState();
}

class _ChallengeDetailScreenState extends State<ChallengeDetailScreen> {
  Challenge? _challenge;
  bool _joined = false;
  bool _busy = false;
  ApiError? _error;
  final _url = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final challenge = await widget.session.api.challenge(widget.slug);
    if (mounted) {
      setState(() {
        _challenge = challenge;
        _joined = challenge.myParticipationId != null;
      });
    }
  }

  Future<void> _join() async {
    setState(() => _busy = true);
    try {
      await widget.session.api.joinChallenge(widget.slug);
      if (mounted) setState(() => _joined = true);
    } on ApiError catch (e) {
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    setState(() => _busy = true);
    try {
      await widget.session.api.submitChallenge(widget.slug, submissionUrl: _url.text.trim());
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Submitted for grading.')));
      }
    } on ApiError catch (e) {
      setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final challenge = _challenge;
    return Scaffold(
      appBar: AppBar(title: Text(challenge?.title ?? 'Challenge')),
      body: challenge == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(challenge.brief),
                const SizedBox(height: 16),
                if (_error != null) Text(_error!.message),
                if (!_joined)
                  FilledButton(
                    onPressed: challenge.isOpen && !_busy ? _join : null,
                    child: const Text('Join'),
                  )
                else ...[
                  TextField(
                    controller: _url,
                    decoration: const InputDecoration(labelText: 'Deployed URL'),
                  ),
                  const SizedBox(height: 10),
                  FilledButton(
                    onPressed: _busy ? null : _submit,
                    child: const Text('Submit'),
                  ),
                ],
              ],
            ),
    );
  }
}
