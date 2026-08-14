/// Wire models.
///
/// Hand-written rather than code-generated: the app reads a deliberately
/// small slice of a large API, and a build_runner step would be more
/// machinery than the handful of types below is worth. Field names match the
/// server's JSON exactly so a mismatch is a compile error here rather than a
/// silent null at runtime.
library;

class Paginated<T> {
  Paginated({required this.count, required this.results, this.next});

  final int count;
  final List<T> results;
  final String? next;

  factory Paginated.from(Map<String, dynamic> json, T Function(Map<String, dynamic>) item) {
    return Paginated(
      count: json['count'] as int? ?? 0,
      next: json['next'] as String?,
      results: ((json['results'] as List?) ?? const [])
          .map((e) => item(Map<String, dynamic>.from(e as Map)))
          .toList(),
    );
  }
}

class User {
  User({
    required this.id,
    required this.email,
    required this.handle,
    required this.displayName,
    required this.canTransact,
    required this.profileComplete,
    required this.missingRequirements,
    required this.hasTwoFactor,
    required this.profileStrength,
    this.adminRole = '',
    this.avatarUrl,
    this.headline = '',
  });

  final int id;
  final String email;
  final String handle;
  final String displayName;
  final bool canTransact;
  final bool profileComplete;

  /// Which of email / phone / identity are still outstanding. The server
  /// decides this, not the client — the same gate blocks the API regardless
  /// of what the UI shows.
  final List<String> missingRequirements;
  final bool hasTwoFactor;
  final int profileStrength;
  final String adminRole;
  final String? avatarUrl;
  final String headline;

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'] as int,
        email: json['email'] as String,
        handle: json['handle'] as String? ?? '',
        displayName: json['display_name'] as String? ?? '',
        canTransact: json['can_transact'] as bool? ?? false,
        profileComplete: json['profile_complete'] as bool? ?? false,
        missingRequirements:
            ((json['missing_requirements'] as List?) ?? const []).map((e) => '$e').toList(),
        hasTwoFactor: json['has_two_factor'] as bool? ?? false,
        profileStrength: json['profile_strength'] as int? ?? 0,
        adminRole: json['admin_role'] as String? ?? '',
        avatarUrl: json['avatar_url'] as String?,
        headline: json['headline'] as String? ?? '',
      );
}

class ProjectSummary {
  ProjectSummary({
    required this.id,
    required this.title,
    required this.description,
    required this.budgetDisplay,
    required this.status,
    required this.proposalCount,
    required this.clientName,
    required this.skills,
    this.categoryName,
    this.experienceLevel = '',
  });

  final int id;
  final String title;
  final String description;
  final String budgetDisplay;
  final String status;
  final int proposalCount;
  final String clientName;
  final List<String> skills;
  final String? categoryName;
  final String experienceLevel;

  factory ProjectSummary.fromJson(Map<String, dynamic> json) => ProjectSummary(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        description: json['description'] as String? ?? '',
        budgetDisplay: json['budget_display'] as String? ?? '',
        status: json['status'] as String? ?? '',
        proposalCount: json['proposal_count'] as int? ?? 0,
        clientName: json['client_name'] as String? ?? '',
        skills: ((json['skills'] as List?) ?? const [])
            .map((e) => (e is Map ? e['name'] : e).toString())
            .toList(),
        categoryName: json['category_name'] as String?,
        experienceLevel: json['experience_level'] as String? ?? '',
      );
}

class ContractSummary {
  ContractSummary({
    required this.id,
    required this.title,
    required this.contractType,
    required this.status,
    required this.myRole,
    required this.fundedAmount,
    required this.releasedAmount,
    required this.clientName,
    required this.freelancerName,
    this.totalAmount,
    this.hourlyRate,
  });

  final int id;
  final String title;
  final String contractType;
  final String status;
  final String myRole;
  final String fundedAmount;
  final String releasedAmount;
  final String clientName;
  final String freelancerName;
  final String? totalAmount;
  final String? hourlyRate;

  /// What the contract is worth, whichever field carries it for this type.
  String get headlineAmount => totalAmount ?? hourlyRate ?? '0';

  factory ContractSummary.fromJson(Map<String, dynamic> json) => ContractSummary(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        contractType: json['contract_type'] as String? ?? '',
        status: json['status'] as String? ?? '',
        myRole: json['my_role'] as String? ?? '',
        fundedAmount: '${json['funded_amount'] ?? '0'}',
        releasedAmount: '${json['released_amount'] ?? '0'}',
        clientName: json['client_name'] as String? ?? '',
        freelancerName: json['freelancer_name'] as String? ?? '',
        totalAmount: json['total_amount'] as String?,
        hourlyRate: json['hourly_rate'] as String?,
      );
}

class Milestone {
  Milestone({
    required this.id,
    required this.title,
    required this.amount,
    required this.status,
  });

  final int id;
  final String title;
  final String amount;
  final String status;

  factory Milestone.fromJson(Map<String, dynamic> json) => Milestone(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        amount: '${json['amount'] ?? '0'}',
        status: json['status'] as String? ?? '',
      );
}

class ContractDetail extends ContractSummary {
  ContractDetail({
    required super.id,
    required super.title,
    required super.contractType,
    required super.status,
    required super.myRole,
    required super.fundedAmount,
    required super.releasedAmount,
    required super.clientName,
    required super.freelancerName,
    required this.milestones,
    super.totalAmount,
    super.hourlyRate,
    this.projectTitle,
  });

  final List<Milestone> milestones;
  final String? projectTitle;

  factory ContractDetail.fromJson(Map<String, dynamic> json) {
    final summary = ContractSummary.fromJson(json);
    return ContractDetail(
      id: summary.id,
      title: summary.title,
      contractType: summary.contractType,
      status: summary.status,
      myRole: summary.myRole,
      fundedAmount: summary.fundedAmount,
      releasedAmount: summary.releasedAmount,
      clientName: summary.clientName,
      freelancerName: summary.freelancerName,
      totalAmount: summary.totalAmount,
      hourlyRate: summary.hourlyRate,
      projectTitle: json['project_title'] as String?,
      milestones: ((json['milestones'] as List?) ?? const [])
          .map((e) => Milestone.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
    );
  }
}

class AppNotification {
  AppNotification({
    required this.id,
    required this.category,
    required this.title,
    required this.body,
    required this.isRead,
    required this.createdAt,
  });

  final int id;
  final String category;
  final String title;
  final String body;
  final bool isRead;
  final DateTime createdAt;

  factory AppNotification.fromJson(Map<String, dynamic> json) => AppNotification(
        id: json['id'] as int,
        category: json['category'] as String? ?? '',
        title: json['title'] as String? ?? '',
        body: json['body'] as String? ?? '',
        isRead: json['is_read'] as bool? ?? false,
        createdAt:
            DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ?? DateTime.now(),
      );
}
