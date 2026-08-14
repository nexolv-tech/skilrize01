library;

class GigPackage {
  GigPackage({
    required this.id,
    required this.tier,
    required this.name,
    required this.price,
    required this.deliveryDays,
    required this.isActive,
  });

  final int id;
  final String tier;
  final String name;
  final String price;
  final int deliveryDays;
  final bool isActive;

  factory GigPackage.fromJson(Map<String, dynamic> json) => GigPackage(
        id: json['id'] as int,
        tier: json['tier'] as String? ?? '',
        name: json['name'] as String? ?? '',
        price: '${json['price'] ?? '0'}',
        deliveryDays: json['delivery_days'] as int? ?? 0,
        isActive: json['is_active'] as bool? ?? true,
      );
}

class GigSummary {
  GigSummary({
    required this.id,
    required this.title,
    required this.startingPrice,
    required this.sellerName,
    required this.status,
    this.categoryName,
  });

  final int id;
  final String title;
  final String startingPrice;
  final String sellerName;
  final String status;
  final String? categoryName;

  factory GigSummary.fromJson(Map<String, dynamic> json) => GigSummary(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        startingPrice: '${json['starting_price'] ?? json['price'] ?? '0'}',
        sellerName: json['seller_name'] as String? ?? '',
        status: json['status'] as String? ?? '',
        categoryName: json['category_name'] as String?,
      );
}

class GigDetail extends GigSummary {
  GigDetail({
    required super.id,
    required super.title,
    required super.startingPrice,
    required super.sellerName,
    required super.status,
    required this.description,
    required this.packages,
    required this.isOwner,
    required this.canOrder,
    super.categoryName,
    this.orderBlockedReason,
  });

  final String description;
  final List<GigPackage> packages;
  final bool isOwner;
  final bool canOrder;
  final String? orderBlockedReason;

  factory GigDetail.fromJson(Map<String, dynamic> json) {
    final summary = GigSummary.fromJson(json);
    return GigDetail(
      id: summary.id,
      title: summary.title,
      startingPrice: summary.startingPrice,
      sellerName: summary.sellerName,
      status: summary.status,
      categoryName: summary.categoryName,
      description: json['description'] as String? ?? '',
      packages: ((json['packages'] as List?) ?? const [])
          .map((e) => GigPackage.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
      isOwner: json['is_owner'] as bool? ?? false,
      canOrder: json['can_order'] as bool? ?? true,
      orderBlockedReason: json['order_blocked_reason'] as String?,
    );
  }
}

class GigOrder {
  GigOrder({
    required this.id,
    required this.gigTitle,
    required this.price,
    required this.status,
    required this.myRole,
    required this.revisionsLeft,
    this.buyerName = '',
    this.sellerName = '',
    this.dueAt,
  });

  final int id;
  final String gigTitle;
  final String price;
  final String status;
  final String myRole;
  final int revisionsLeft;
  final String buyerName;
  final String sellerName;
  final DateTime? dueAt;

  factory GigOrder.fromJson(Map<String, dynamic> json) => GigOrder(
        id: json['id'] as int,
        gigTitle: json['gig_title'] as String? ?? '',
        price: '${json['price'] ?? '0'}',
        status: json['status'] as String? ?? '',
        myRole: json['my_role'] as String? ?? '',
        revisionsLeft: json['revisions_left'] as int? ?? 0,
        buyerName: json['buyer_name'] as String? ?? '',
        sellerName: json['seller_name'] as String? ?? '',
        dueAt: json['due_at'] == null ? null : DateTime.tryParse(json['due_at'] as String),
      );
}
