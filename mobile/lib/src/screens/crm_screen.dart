import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/professional.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';
import '../widgets/money_gate.dart';

const _dealStages = [
  ('lead', 'Lead'),
  ('qualified', 'Qualified'),
  ('proposed', 'Proposal sent'),
  ('negotiating', 'Negotiating'),
  ('won', 'Won'),
  ('lost', 'Lost'),
];

/// Contacts / deals / tasks — mirrors `web/components/crm.tsx`. The web
/// version renders deals as a drag-drop kanban board; a phone has no room
/// for that, so stage changes here are a plain menu on each card instead.
class CrmScreen extends StatefulWidget {
  const CrmScreen({super.key, required this.session});
  final Session session;

  @override
  State<CrmScreen> createState() => _CrmScreenState();
}

class _CrmScreenState extends State<CrmScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 3, vsync: this);
  final _dealsKey = GlobalKey<AsyncListState<CrmDeal>>();
  ApiError? _error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CRM'),
        bottom: TabBar(
          controller: _tabs,
          tabs: const [Tab(text: 'Contacts'), Tab(text: 'Deals'), Tab(text: 'Tasks')],
        ),
      ),
      body: Column(
        children: [
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: MoneyGateBanner(error: _error!),
            ),
          Expanded(
            child: TabBarView(
              controller: _tabs,
              children: [
                AsyncList<CrmContact>(
                  loader: () async => (await widget.session.api.crmContacts()).results,
                  emptyIcon: Icons.person_outline,
                  emptyText: 'No contacts yet.',
                  itemBuilder: (context, contact) => Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      title: Text(contact.name),
                      subtitle: Text(
                        [contact.company, contact.email].where((s) => s.isNotEmpty).join(' · '),
                      ),
                    ),
                  ),
                ),
                AsyncList<CrmDeal>(
                  key: _dealsKey,
                  loader: () async => (await widget.session.api.crmDeals()).results,
                  emptyIcon: Icons.handshake_outlined,
                  emptyText: 'No deals yet.',
                  itemBuilder: (context, deal) => Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      title: Text(deal.title),
                      subtitle: Text('Rs ${deal.value}'),
                      trailing: PopupMenuButton<String>(
                        initialValue: deal.stage,
                        onSelected: (stage) async {
                          try {
                            await widget.session.api.moveDeal(deal.id, stage);
                            _dealsKey.currentState?.reload();
                          } on ApiError catch (e) {
                            setState(() => _error = e);
                          }
                        },
                        itemBuilder: (_) => [
                          for (final (value, label) in _dealStages)
                            PopupMenuItem(value: value, child: Text(label)),
                        ],
                        child: Chip(
                          label: Text(
                            _dealStages.firstWhere((s) => s.$1 == deal.stage, orElse: () => (deal.stage, deal.stage)).$2,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                AsyncList<CrmTask>(
                  loader: () async => (await widget.session.api.crmTasks()).results,
                  emptyIcon: Icons.checklist_outlined,
                  emptyText: 'No tasks yet.',
                  itemBuilder: (context, task) => Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: CheckboxListTile(
                      value: task.isComplete,
                      onChanged: (_) async {
                        await widget.session.api.toggleCrmTask(task.id);
                        setState(() {});
                      },
                      title: Text(task.title),
                      subtitle: task.dueDate == null ? null : Text('Due ${task.dueDate}'),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
