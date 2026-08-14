import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/marketplace.dart';
import '../state/session.dart';
import '../widgets/money_gate.dart';

/// One project: brief, screening questions, and — if eligible — a proposal
/// form. `can_propose`/`propose_blocked_reason` are server-decided (already
/// proposed, quota exhausted, project closed, own project); the client
/// shows the reason, it never re-derives eligibility itself.
class ProjectDetailScreen extends StatefulWidget {
  const ProjectDetailScreen({super.key, required this.session, required this.projectId});

  final Session session;
  final int projectId;

  @override
  State<ProjectDetailScreen> createState() => _ProjectDetailScreenState();
}

class _ProjectDetailScreenState extends State<ProjectDetailScreen> {
  ProjectDetail? _project;
  String? _error;
  bool _showForm = false;

  final _coverLetter = TextEditingController();
  final _bidAmount = TextEditingController();
  bool _submitting = false;
  ApiError? _submitError;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _coverLetter.dispose();
    _bidAmount.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final project = await widget.session.api.project(widget.projectId);
      if (!mounted) return;
      setState(() => _project = project);
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _submitError = null;
    });
    try {
      await widget.session.api.submitProposal(widget.projectId, {
        'cover_letter': _coverLetter.text.trim(),
        if (_bidAmount.text.trim().isNotEmpty) 'bid_amount': _bidAmount.text.trim(),
      });
      if (!mounted) return;
      setState(() => _showForm = false);
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Proposal submitted.')));
      }
    } on ApiError catch (e) {
      setState(() => _submitError = e);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final project = _project;
    return Scaffold(
      appBar: AppBar(title: Text(project?.title ?? 'Project')),
      body: _error != null
          ? Center(child: Text(_error!))
          : project == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text(project.title, style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 6),
                    Text(project.budgetDisplay, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 4),
                    Text('${project.proposalCount} proposals',
                        style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: 16),
                    Text(project.description),
                    if (project.skills.isNotEmpty) ...[
                      const SizedBox(height: 16),
                      Wrap(
                        spacing: 6,
                        children: [for (final s in project.skills) Chip(label: Text(s))],
                      ),
                    ],
                    const SizedBox(height: 24),
                    if (project.isOwner)
                      const _InfoBanner(
                        icon: Icons.person_outline,
                        text: 'This is your own project.',
                      )
                    else if (project.myProposalId != null)
                      const _InfoBanner(
                        icon: Icons.check_circle_outline,
                        text: "You've already proposed on this project.",
                      )
                    else if (!project.canPropose)
                      _InfoBanner(
                        icon: Icons.block_outlined,
                        text: project.proposeBlockedReason ??
                            'You cannot propose on this project right now.',
                      )
                    else if (_showForm)
                      _proposalForm(context)
                    else
                      FilledButton(
                        onPressed: () => setState(() => _showForm = true),
                        child: const Text('Submit a proposal'),
                      ),
                  ],
                ),
    );
  }

  Widget _proposalForm(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Your proposal', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            if (_submitError != null) ...[
              MoneyGateBanner(error: _submitError!),
              const SizedBox(height: 12),
            ],
            TextField(
              controller: _bidAmount,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Bid amount'),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _coverLetter,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'Cover letter'),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: _submitting || _coverLetter.text.trim().isEmpty ? null : _submit,
              child: _submitting
                  ? const SizedBox(
                      height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Submit'),
            ),
          ],
        ),
      ),
    );
  }
}

class _InfoBanner extends StatelessWidget {
  const _InfoBanner({required this.icon, required this.text});
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration:
          BoxDecoration(color: scheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(10)),
      child: Row(
        children: [
          Icon(icon, color: scheme.outline),
          const SizedBox(width: 10),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}
