library;

class Community {
  Community({
    required this.id,
    required this.name,
    required this.kind,
    required this.memberCount,
    required this.isMember,
    this.description = '',
    this.isModerator = false,
  });

  final int id;
  final String name;
  final String kind;
  final int memberCount;
  final bool isMember;
  final String description;
  final bool isModerator;

  factory Community.fromJson(Map<String, dynamic> json) => Community(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        kind: json['kind'] as String? ?? '',
        memberCount: json['member_count'] as int? ?? 0,
        isMember: json['is_member'] as bool? ?? false,
        description: json['description'] as String? ?? '',
        isModerator: json['is_moderator'] as bool? ?? false,
      );
}

class CommunityThread {
  CommunityThread({
    required this.id,
    required this.title,
    required this.replyCount,
    required this.authorName,
    required this.createdAt,
    this.isPinned = false,
    this.isLocked = false,
  });

  final int id;
  final String title;
  final int replyCount;
  final String authorName;
  final DateTime createdAt;
  final bool isPinned;
  final bool isLocked;

  factory CommunityThread.fromJson(Map<String, dynamic> json) => CommunityThread(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        replyCount: json['reply_count'] as int? ?? 0,
        authorName: json['author_name'] as String? ?? '',
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
        isPinned: json['is_pinned'] as bool? ?? false,
        isLocked: json['is_locked'] as bool? ?? false,
      );
}

class ThreadReply {
  ThreadReply({
    required this.id,
    required this.body,
    required this.authorName,
    required this.createdAt,
  });

  final int id;
  final String body;
  final String authorName;
  final DateTime createdAt;

  factory ThreadReply.fromJson(Map<String, dynamic> json) => ThreadReply(
        id: json['id'] as int,
        body: json['body'] as String? ?? '',
        authorName: json['author_name'] as String? ?? '',
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );
}

class ChatMessage {
  ChatMessage({
    required this.id,
    required this.body,
    required this.authorName,
    required this.createdAt,
  });

  final int id;
  final String body;
  final String authorName;
  final DateTime createdAt;

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id'] as int,
        body: json['body'] as String? ?? '',
        authorName: json['author_name'] as String? ?? '',
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );
}

class CommunityEvent {
  CommunityEvent({
    required this.id,
    required this.title,
    required this.startsAt,
    required this.myRsvp,
  });

  final int id;
  final String title;
  final DateTime startsAt;
  final String? myRsvp;

  factory CommunityEvent.fromJson(Map<String, dynamic> json) => CommunityEvent(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        startsAt:
            DateTime.tryParse(json['starts_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
        myRsvp: json['my_rsvp'] as String?,
      );
}

class CommunityResource {
  CommunityResource({required this.id, required this.title, required this.url});

  final int id;
  final String title;
  final String url;

  factory CommunityResource.fromJson(Map<String, dynamic> json) => CommunityResource(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        url: json['url'] as String? ?? '',
      );
}

class FeedEntry {
  FeedEntry({
    required this.id,
    required this.verb,
    required this.summary,
    required this.createdAt,
  });

  final int id;
  final String verb;
  final String summary;
  final DateTime createdAt;

  factory FeedEntry.fromJson(Map<String, dynamic> json) => FeedEntry(
        id: json['id'] as int,
        verb: json['verb'] as String? ?? '',
        summary: json['summary'] as String? ?? json['title'] as String? ?? '',
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );
}
