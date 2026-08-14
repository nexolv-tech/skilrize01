library;

class Conversation {
  Conversation({
    required this.id,
    required this.otherName,
    required this.lastMessage,
    required this.unreadCount,
    this.otherHandle = '',
  });

  final int id;
  final String otherName;
  final String otherHandle;
  final String lastMessage;
  final int unreadCount;

  factory Conversation.fromJson(Map<String, dynamic> json) => Conversation(
        id: json['id'] as int,
        otherName: (json['other_user'] is Map ? json['other_user']['display_name'] : null)
                as String? ??
            json['other_name'] as String? ??
            '',
        otherHandle: (json['other_user'] is Map ? json['other_user']['handle'] : null) as String? ??
            '',
        lastMessage: json['last_message'] as String? ?? '',
        unreadCount: json['unread_count'] as int? ?? 0,
      );
}

class DirectMessage {
  DirectMessage({
    required this.id,
    required this.body,
    required this.senderId,
    required this.createdAt,
  });

  final int id;
  final String body;
  final int senderId;
  final DateTime createdAt;

  factory DirectMessage.fromJson(Map<String, dynamic> json) => DirectMessage(
        id: json['id'] as int,
        body: json['body'] as String? ?? '',
        senderId: json['sender'] as int? ?? json['sender_id'] as int? ?? 0,
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );
}
