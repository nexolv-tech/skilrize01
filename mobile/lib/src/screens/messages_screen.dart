import 'package:flutter/material.dart';

import '../api/api_error.dart';
import '../models/messaging.dart';
import '../state/session.dart';
import '../widgets/async_list.dart';

class MessagesScreen extends StatelessWidget {
  const MessagesScreen({super.key, required this.session});
  final Session session;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Messages')),
      body: AsyncList<Conversation>(
        loader: () async => (await session.api.conversations()).results,
        emptyIcon: Icons.chat_bubble_outline,
        emptyText: 'No conversations yet.',
        itemBuilder: (context, conversation) => Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            title: Text(conversation.otherName),
            subtitle: Text(
              conversation.lastMessage,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            trailing: conversation.unreadCount > 0
                ? CircleAvatar(
                    radius: 11,
                    child: Text('${conversation.unreadCount}',
                        style: const TextStyle(fontSize: 11)),
                  )
                : null,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => ThreadScreen(session: session, conversation: conversation),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ThreadScreen extends StatefulWidget {
  const ThreadScreen({super.key, required this.session, required this.conversation});
  final Session session;
  final Conversation conversation;

  @override
  State<ThreadScreen> createState() => _ThreadScreenState();
}

class _ThreadScreenState extends State<ThreadScreen> {
  List<DirectMessage>? _messages;
  final _body = TextEditingController();
  bool _sending = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _body.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      // Newest page first from the API; reversed here so the list renders
      // oldest-at-top like every chat surface. `CompactPagination` gives a
      // smaller page than the app's other lists — that's the server's call,
      // not something this screen needs to know the size of.
      final page = await widget.session.api.thread(widget.conversation.id);
      if (!mounted) return;
      setState(() => _messages = page.results.reversed.toList());
    } on ApiError catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    }
  }

  Future<void> _send() async {
    final text = _body.text.trim();
    if (text.isEmpty) return;
    setState(() => _sending = true);
    try {
      await widget.session.api.sendMessage(widget.conversation.id, text);
      _body.clear();
      await _load();
    } on ApiError catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final me = widget.session.user!.id;
    return Scaffold(
      appBar: AppBar(title: Text(widget.conversation.otherName)),
      body: Column(
        children: [
          if (_error != null) Padding(padding: const EdgeInsets.all(8), child: Text(_error!)),
          Expanded(
            child: _messages == null
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: _messages!.length,
                    itemBuilder: (context, i) {
                      final message = _messages![i];
                      final mine = message.senderId == me;
                      return Align(
                        alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                        child: Container(
                          margin: const EdgeInsets.symmetric(vertical: 4),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          constraints: BoxConstraints(
                              maxWidth: MediaQuery.of(context).size.width * 0.75),
                          decoration: BoxDecoration(
                            color: mine
                                ? Theme.of(context).colorScheme.primaryContainer
                                : Theme.of(context).colorScheme.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Text(message.body),
                        ),
                      );
                    },
                  ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _body,
                      decoration: const InputDecoration(hintText: 'Message'),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  IconButton(
                    onPressed: _sending ? null : _send,
                    icon: const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
