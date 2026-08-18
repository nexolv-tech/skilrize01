import 'package:flutter/material.dart';

import '../models/misc.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';

/// Connect/disconnect Zoom, Google Meet, GitHub, Figma, Notion — mirrors
/// `web/app/(app)/settings/integrations`. The actual OAuth redirect (the
/// `authorize_url` step) needs a web view or an external-browser launch to
/// complete on a phone; that launch step is a `TODO` in the same spirit as
/// the FCM token in `push_settings.dart` — everything up to and after the
/// redirect is real, the browser hop itself needs a launcher package added
/// back when a provider actually has credentials to test against.
class IntegrationsScreen extends StatelessWidget {
  const IntegrationsScreen({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Integrations')),
      body: AsyncList<ProviderStatus>(
        loader: () => session.api.providers(),
        itemBuilder: (context, provider) => Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            title: Text(provider.label),
            subtitle: Text(
              provider.isConnected
                  ? (provider.externalLabel.isEmpty ? 'Connected' : provider.externalLabel)
                  : provider.isEnabled
                      ? 'Not connected'
                      : 'Not available yet in this environment',
            ),
            trailing: provider.isConnected
                ? TextButton(
                    onPressed: () => session.api.disconnectProvider(provider.provider),
                    child: const Text('Disconnect'),
                  )
                : FilledButton.tonal(
                    onPressed: provider.isEnabled
                        ? () => session.api.authorizeProvider(provider.provider)
                        : null,
                    child: const Text('Connect'),
                  ),
          ),
        ),
      ),
    );
  }
}

/// Meetings + linked activity for one contract — embedded in
/// `ContractDetailScreen` via a "Integrations" button rather than always
/// shown, since most contracts never use either.
class ContractIntegrationsScreen extends StatelessWidget {
  const ContractIntegrationsScreen({super.key, required this.session, required this.contractId});
  final Session session;
  final int contractId;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Meetings & activity'),
          bottom: const TabBar(tabs: [Tab(text: 'Meetings'), Tab(text: 'Activity')]),
        ),
        body: TabBarView(
          children: [
            AsyncList<ContractMeeting>(
              loader: () => session.api.meetings(contractId),
              emptyIcon: Icons.video_call_outlined,
              emptyText: 'No meetings scheduled.',
              itemBuilder: (context, meeting) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  title: Text(meeting.topic),
                  subtitle: Text('${meeting.provider} · ${meeting.startTime}'),
                  trailing: StatusPill(meeting.status),
                ),
              ),
            ),
            AsyncList<ActivitySource>(
              loader: () => session.api.activitySources(contractId),
              emptyIcon: Icons.link_outlined,
              emptyText: 'Nothing linked yet.',
              itemBuilder: (context, source) => Card(
                margin: const EdgeInsets.only(bottom: 8),
                child: ListTile(
                  title: Text('${source.provider}: ${source.externalRef}'),
                  subtitle: Text(source.lastSyncedAt == null
                      ? 'Never synced'
                      : 'Synced ${source.lastSyncedAt}'),
                  trailing: IconButton(
                    icon: const Icon(Icons.sync),
                    onPressed: () => session.api.syncActivitySource(source.id),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
