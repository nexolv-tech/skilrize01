/// Marketplace models beyond `ProjectSummary`/`ContractSummary` in
/// `models.dart`: project detail, proposals, and the trial-to-hire flow.
library;

class Category {
  Category({required this.id, required this.name, required this.slug});
  final int id;
  final String name;
  final String slug;

  factory Category.fromJson(Map<String, dynamic> json) => Category(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        slug: json['slug'] as String? ?? '',
      );
}

class Skill {
  Skill({required this.id, required this.name, required this.slug});
  final int id;
  final String name;
  final String slug;

  factory Skill.fromJson(Map<String, dynamic> json) => Skill(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        slug: json['slug'] as String? ?? '',
      );
}

class ScreeningQuestion {
  ScreeningQuestion({required this.id, required this.text, required this.isRequired});
  final int id;
  final String text;
  final bool isRequired;

  factory ScreeningQuestion.fromJson(Map<String, dynamic> json) => ScreeningQuestion(
        id: json['id'] as int,
        text: json['text'] as String? ?? '',
        isRequired: json['is_required'] as bool? ?? false,
      );
}

class ProjectDetail {
  ProjectDetail({
    required this.id,
    required this.title,
    required this.description,
    required this.budgetDisplay,
    required this.status,
    required this.proposalCount,
    required this.skills,
    required this.screeningQuestions,
    required this.isOwner,
    required this.canPropose,
    this.proposeBlockedReason,
    this.myProposalId,
    this.clientName = '',
  });

  final int id;
  final String title;
  final String description;
  final String budgetDisplay;
  final String status;
  final int proposalCount;
  final List<String> skills;
  final List<ScreeningQuestion> screeningQuestions;
  final bool isOwner;
  final bool canPropose;
  final String? proposeBlockedReason;
  final int? myProposalId;
  final String clientName;

  factory ProjectDetail.fromJson(Map<String, dynamic> json) => ProjectDetail(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        description: json['description'] as String? ?? '',
        budgetDisplay: json['budget_display'] as String? ?? '',
        status: json['status'] as String? ?? '',
        proposalCount: json['proposal_count'] as int? ?? 0,
        skills: ((json['skills'] as List?) ?? const [])
            .map((e) => (e is Map ? e['name'] : e).toString())
            .toList(),
        screeningQuestions: ((json['screening_questions'] as List?) ?? const [])
            .map((e) => ScreeningQuestion.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList(),
        isOwner: json['is_owner'] as bool? ?? false,
        canPropose: json['can_propose'] as bool? ?? false,
        proposeBlockedReason: json['propose_blocked_reason'] as String?,
        myProposalId: json['my_proposal_id'] as int?,
        clientName: (json['client'] is Map ? json['client']['display_name'] : null) as String? ??
            '',
      );
}

class ProposedMilestone {
  ProposedMilestone({required this.title, required this.amount, this.dueDate});
  final String title;
  final String amount;
  final String? dueDate;

  Map<String, dynamic> toJson() => {
        'title': title,
        'amount': amount,
        if (dueDate != null) 'due_date': dueDate,
      };

  factory ProposedMilestone.fromJson(Map<String, dynamic> json) => ProposedMilestone(
        title: json['title'] as String? ?? '',
        amount: '${json['amount'] ?? '0'}',
        dueDate: json['due_date'] as String?,
      );
}

class Trial {
  Trial({
    required this.id,
    required this.brief,
    required this.amount,
    required this.status,
    this.contractId,
    this.convertedContractId,
  });

  final int id;
  final String brief;
  final String amount;
  final String status;
  final int? contractId;
  final int? convertedContractId;

  factory Trial.fromJson(Map<String, dynamic> json) => Trial(
        id: json['id'] as int,
        brief: json['brief'] as String? ?? '',
        amount: '${json['amount'] ?? '0'}',
        status: json['status'] as String? ?? '',
        contractId: json['contract_id'] as int?,
        convertedContractId: json['converted_contract_id'] as int?,
      );
}

class Proposal {
  Proposal({
    required this.id,
    required this.project,
    required this.projectTitle,
    required this.coverLetter,
    required this.status,
    required this.isEditable,
    this.bidAmount,
    this.hourlyRate,
    this.estimatedDays,
    this.trial,
  });

  final int id;
  final int project;
  final String projectTitle;
  final String coverLetter;
  final String status;
  final bool isEditable;
  final String? bidAmount;
  final String? hourlyRate;
  final int? estimatedDays;
  final Trial? trial;

  factory Proposal.fromJson(Map<String, dynamic> json) => Proposal(
        id: json['id'] as int,
        project: json['project'] as int,
        projectTitle: json['project_title'] as String? ?? '',
        coverLetter: json['cover_letter'] as String? ?? '',
        status: json['status'] as String? ?? '',
        isEditable: json['is_editable'] as bool? ?? false,
        bidAmount: json['bid_amount'] as String?,
        hourlyRate: json['hourly_rate'] as String?,
        estimatedDays: json['estimated_days'] as int?,
        trial: json['trial'] == null
            ? null
            : Trial.fromJson(Map<String, dynamic>.from(json['trial'] as Map)),
      );
}
