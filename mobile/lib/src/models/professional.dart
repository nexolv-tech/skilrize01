library;

class SubscriptionPlan {
  SubscriptionPlan({
    required this.tier,
    required this.name,
    required this.monthlyPrice,
    required this.isPaid,
    required this.features,
  });

  final String tier;
  final String name;
  final String monthlyPrice;
  final bool isPaid;
  final List<String> features;

  factory SubscriptionPlan.fromJson(Map<String, dynamic> json) => SubscriptionPlan(
        tier: json['tier'] as String? ?? '',
        name: json['name'] as String? ?? '',
        monthlyPrice: '${json['monthly_price'] ?? '0'}',
        isPaid: json['is_paid'] as bool? ?? false,
        features:
            ((json['features'] as List?) ?? const []).map((e) => e.toString()).toList(),
      );
}

class Entitlements {
  Entitlements({
    required this.tier,
    required this.planName,
    required this.proposalQuota,
    required this.crmContactLimit,
    required this.canSellRetainers,
    required this.canCreateAgency,
  });

  final String tier;
  final String planName;
  final int proposalQuota;
  final int crmContactLimit;
  final bool canSellRetainers;
  final bool canCreateAgency;

  static const unlimited = -1;

  factory Entitlements.fromJson(Map<String, dynamic> json) => Entitlements(
        tier: json['tier'] as String? ?? 'free',
        planName: json['plan_name'] as String? ?? 'Free',
        proposalQuota: json['proposal_quota'] as int? ?? 0,
        crmContactLimit: json['crm_contact_limit'] as int? ?? 0,
        canSellRetainers: json['can_sell_retainers'] as bool? ?? false,
        canCreateAgency: json['can_create_agency'] as bool? ?? false,
      );
}

class CrmContact {
  CrmContact({required this.id, required this.name, this.email = '', this.company = ''});
  final int id;
  final String name;
  final String email;
  final String company;

  factory CrmContact.fromJson(Map<String, dynamic> json) => CrmContact(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        email: json['email'] as String? ?? '',
        company: json['company'] as String? ?? '',
      );
}

class CrmDeal {
  CrmDeal({required this.id, required this.title, required this.stage, this.value = '0'});
  final int id;
  final String title;
  final String stage;
  final String value;

  factory CrmDeal.fromJson(Map<String, dynamic> json) => CrmDeal(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        stage: json['stage'] as String? ?? '',
        value: '${json['value'] ?? '0'}',
      );
}

class CrmTask {
  CrmTask({required this.id, required this.title, required this.isComplete, this.dueDate});
  final int id;
  final String title;
  final bool isComplete;
  final String? dueDate;

  factory CrmTask.fromJson(Map<String, dynamic> json) => CrmTask(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        isComplete: json['is_complete'] as bool? ?? false,
        dueDate: json['due_date'] as String?,
      );
}

class AgencyTeam {
  AgencyTeam({required this.id, required this.name, required this.memberCount});
  final int id;
  final String name;
  final int memberCount;

  factory AgencyTeam.fromJson(Map<String, dynamic> json) => AgencyTeam(
        id: json['id'] as int,
        name: json['name'] as String? ?? '',
        memberCount: json['member_count'] as int? ?? 0,
      );
}

class SharedWorkspace {
  SharedWorkspace({required this.id, required this.name});
  final int id;
  final String name;

  factory SharedWorkspace.fromJson(Map<String, dynamic> json) =>
      SharedWorkspace(id: json['id'] as int, name: json['name'] as String? ?? '');
}

class Retainer {
  Retainer({required this.id, required this.title, required this.monthlyPrice, this.sellerName = ''});
  final int id;
  final String title;
  final String monthlyPrice;
  final String sellerName;

  factory Retainer.fromJson(Map<String, dynamic> json) => Retainer(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        monthlyPrice: '${json['monthly_price'] ?? '0'}',
        sellerName: json['seller_name'] as String? ?? '',
      );
}
