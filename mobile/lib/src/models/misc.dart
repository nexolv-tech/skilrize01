/// Challenges, integrations, admin console, student verification, search —
/// grouped together since each is a small, self-contained slice.
library;

class Challenge {
  Challenge({
    required this.slug,
    required this.title,
    required this.brief,
    required this.isOpen,
    required this.closesAt,
    this.myParticipationId,
  });

  final String slug;
  final String title;
  final String brief;
  final bool isOpen;
  final DateTime closesAt;
  final int? myParticipationId;

  factory Challenge.fromJson(Map<String, dynamic> json) => Challenge(
        slug: json['slug'] as String? ?? '',
        title: json['title'] as String? ?? '',
        brief: json['brief'] as String? ?? '',
        isOpen: json['is_open'] as bool? ?? false,
        closesAt:
            DateTime.tryParse(json['closes_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
        myParticipationId: json['my_participation_id'] as int?,
      );
}

class ChallengeParticipation {
  ChallengeParticipation({
    required this.id,
    required this.challengeTitle,
    required this.status,
    this.finalScore,
  });

  final int id;
  final String challengeTitle;
  final String status;
  final int? finalScore;

  factory ChallengeParticipation.fromJson(Map<String, dynamic> json) => ChallengeParticipation(
        id: json['id'] as int,
        challengeTitle: json['challenge_title'] as String? ?? '',
        status: json['status'] as String? ?? '',
        finalScore: json['final_score'] as int?,
      );
}

class ProviderStatus {
  ProviderStatus({
    required this.provider,
    required this.label,
    required this.isEnabled,
    required this.isConnected,
    this.externalLabel = '',
  });

  final String provider;
  final String label;
  final bool isEnabled;
  final bool isConnected;
  final String externalLabel;

  factory ProviderStatus.fromJson(Map<String, dynamic> json) => ProviderStatus(
        provider: json['provider'] as String? ?? '',
        label: json['label'] as String? ?? '',
        isEnabled: json['is_enabled'] as bool? ?? false,
        isConnected: json['is_connected'] as bool? ?? false,
        externalLabel: json['external_label'] as String? ?? '',
      );
}

class ContractMeeting {
  ContractMeeting({
    required this.id,
    required this.topic,
    required this.provider,
    required this.startTime,
    required this.joinUrl,
    required this.status,
  });

  final int id;
  final String topic;
  final String provider;
  final DateTime startTime;
  final String joinUrl;
  final String status;

  factory ContractMeeting.fromJson(Map<String, dynamic> json) => ContractMeeting(
        id: json['id'] as int,
        topic: json['topic'] as String? ?? '',
        provider: json['provider'] as String? ?? '',
        startTime:
            DateTime.tryParse(json['start_time'] as String? ?? '')?.toLocal() ?? DateTime.now(),
        joinUrl: json['join_url'] as String? ?? '',
        status: json['status'] as String? ?? '',
      );
}

class ActivitySource {
  ActivitySource({
    required this.id,
    required this.provider,
    required this.externalRef,
    this.lastSyncedAt,
  });

  final int id;
  final String provider;
  final String externalRef;
  final DateTime? lastSyncedAt;

  factory ActivitySource.fromJson(Map<String, dynamic> json) => ActivitySource(
        id: json['id'] as int,
        provider: json['provider'] as String? ?? '',
        externalRef: json['external_ref'] as String? ?? '',
        lastSyncedAt: json['last_synced_at'] == null
            ? null
            : DateTime.tryParse(json['last_synced_at'] as String),
      );
}

class AdminVerification {
  AdminVerification({
    required this.id,
    required this.applicantName,
    required this.universityName,
    required this.status,
  });

  final int id;
  final String applicantName;
  final String universityName;
  final String status;

  factory AdminVerification.fromJson(Map<String, dynamic> json) => AdminVerification(
        id: json['id'] as int,
        applicantName: json['applicant_name'] as String? ?? '',
        universityName: json['university_name'] as String? ?? '',
        status: json['status'] as String? ?? '',
      );
}

class AdminUserRow {
  AdminUserRow({
    required this.id,
    required this.email,
    required this.displayName,
    required this.isActive,
  });

  final int id;
  final String email;
  final String displayName;
  final bool isActive;

  factory AdminUserRow.fromJson(Map<String, dynamic> json) => AdminUserRow(
        id: json['id'] as int,
        email: json['email'] as String? ?? '',
        displayName: json['display_name'] as String? ?? '',
        isActive: json['is_active'] as bool? ?? true,
      );
}

class AuditLogEntry {
  AuditLogEntry({
    required this.id,
    required this.action,
    required this.actorName,
    required this.createdAt,
  });

  final int id;
  final String action;
  final String? actorName;
  final DateTime createdAt;

  factory AuditLogEntry.fromJson(Map<String, dynamic> json) => AuditLogEntry(
        id: json['id'] as int,
        action: json['action'] as String? ?? '',
        actorName: json['actor_name'] as String?,
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );
}

class StudentApplication {
  StudentApplication({
    required this.nextStep,
    this.universityName,
    this.universityEmail = '',
    this.status = 'pending',
    this.rejectionReason = '',
    this.idCardRequired = true,
  });
  final String nextStep;
  final String? universityName;
  final String universityEmail;
  final String status;
  final String rejectionReason;
  final bool idCardRequired;

  factory StudentApplication.fromJson(Map<String, dynamic> json) {
    final university = json['university'] as Map?;
    return StudentApplication(
      nextStep: json['next_step'] as String? ?? 'start_again',
      universityName: university?['name'] as String? ?? json['university_name'] as String?,
      universityEmail: json['university_email'] as String? ?? '',
      status: json['status'] as String? ?? 'pending',
      rejectionReason: json['rejection_reason'] as String? ?? '',
      idCardRequired: json['id_card_required'] as bool? ?? true,
    );
  }
}

/// A signed-in device, from `/auth/sessions/`. Named `AuthSession` rather
/// than `Session` deliberately — `state/session.dart`'s `Session` (this
/// app's own signed-in state) is imported everywhere, and reusing the name
/// for an unrelated model would make every settings-screen import a
/// disambiguation problem instead of a plain one.
class AuthSession {
  AuthSession({
    required this.family,
    required this.isCurrent,
    this.deviceLabel = '',
    this.ipAddress,
  });

  final String family;
  final bool isCurrent;
  final String deviceLabel;
  final String? ipAddress;

  factory AuthSession.fromJson(Map<String, dynamic> json) => AuthSession(
        family: json['family'] as String? ?? '',
        isCurrent: json['is_current'] as bool? ?? false,
        deviceLabel: json['device_label'] as String? ?? '',
        ipAddress: json['ip_address'] as String?,
      );
}

class ShowcasePiece {
  ShowcasePiece({required this.id, required this.title, this.summary = ''});
  final int id;
  final String title;
  final String summary;

  factory ShowcasePiece.fromJson(Map<String, dynamic> json) => ShowcasePiece(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        summary: json['summary'] as String? ?? '',
      );
}
