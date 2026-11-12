import logging
from django.utils.translation import gettext as _
from .member_ages import members_coverage, covered_members, policy_expiry_date
from django.db.models import Q,Count
import datetime as py_datetime
from decimal import *
from .models import Policy
from .apps import PolicyConfig

from core.apps import CoreConfig
from dateutil.relativedelta import relativedelta
from core.apps import CoreConfig

logger = logging.getLogger(__name__)


def cycle_start(product, cycle, ref_date):
    c = getattr(product, "start_cycle_%s" % (cycle + 1), None)
    if not c:
        return None
    if CoreConfig.secondary_calendar == 'Nepal':
        import nepali_datetime
        nepali_start = nepali_datetime.datetime.strptime("%s-%s" % (c, nepali_datetime.date.today().year), '%d-%m-%Y')
        start = nepali_start.to_datetime_date()
    else:
        start = py_datetime.datetime.strptime("%s-%s" % (c, ref_date.year), '%d-%m-%Y')
    if ref_date <= start:
        return start


def set_start_date(policy, earliest_start=None):
    """
    `earliest_start`: the first day a member is covered (product age limits,
    policy.member_ages): when later than the enrolment, the policy starts from it (cycles
    apply after).
    """
    from core import datetime, datetimedelta
    product = policy.product
    ref_enroll_date = policy.enroll_date
    if earliest_start is not None and earliest_start > _plain_date(ref_enroll_date):
        ref_enroll_date = earliest_start
    if policy.stage == Policy.STAGE_NEW and product.administration_period:
        ref_enroll_date = (
                datetime.date.from_ad_date(ref_enroll_date) +
                datetimedelta(months=product.administration_period)
        ).to_ad_date()

    if not product.has_cycle():
        policy.start_date = ref_enroll_date
        return

    grace = 0
    if policy.stage == Policy.STAGE_NEW and product.grace_period_enrolment:
        grace = product.grace_period_enrolment
    elif policy.stage == Policy.STAGE_RENEWED and product.grace_period_renewal:
        grace = product.grace_period_renewal

    ref_date = (datetime.date.from_ad_date(ref_enroll_date) - datetimedelta(months=grace)).to_ad_date()
    for i in range(4):
        start = cycle_start(product, i, ref_date)
        if start:
            policy.start_date = datetime.date.from_ad_date(start)
            return
    policy.start_date = datetime.date.from_ad_date(py_datetime.datetime.strptime(
        "%s-%s" % (product.start_cycle_1, ref_date.year + 1),
        '%d-%m-%Y'
    ))


def _plain_date(value):
    if isinstance(value, py_datetime.datetime):
        return value.date()
    if isinstance(value, str):
        return py_datetime.datetime.strptime(value[:10], "%Y-%m-%d").date()
    return value


def earliest_covered_start(policy, coverages):
    """The first day a member is covered, when no member is covered from the start."""
    covered = [coverage for coverage in coverages if coverage.covered]
    if covered and all(coverage.starts_on for coverage in covered):
        return min(coverage.starts_on for coverage in covered)
    return None


def period_expiry_date(policy):
    """The end of the product insurance period from the policy start date."""
    product = policy.product
    from core import datetime, datetimedelta

    insurance_period = datetimedelta(
        months=product.insurance_period) if product.insurance_period % 12 != 0 else datetimedelta(
        years=product.insurance_period // 12)
    return (
            datetime.date.from_ad_date(policy.start_date) +
            insurance_period -
            datetimedelta(days=1)
    ).to_ad_date()


def set_expiry_date(policy, family, enroll_date, members=None):
    """
    The policy period, cut only when every covered member ages out before its end (then
    it ends with the last of them). A member covered for part of the period keeps their
    own dates on their InsureePolicy (see policy.member_ages). Returns the warnings.
    """
    logger.debug("enroll_date %s", enroll_date)
    expiry_date = period_expiry_date(policy)
    coverages = members_coverage(policy.product, family, policy.start_date, expiry_date, members=members)
    policy.expiry_date = policy_expiry_date(coverages, expiry_date)
    return coverage_warnings(coverages)


def coverage_warnings(coverages):
    warnings = []
    for coverage in coverages:
        chf_id = getattr(coverage.member, "chf_id", None)
        if not coverage.covered:
            warnings.append(_("policy.validation.member_not_covered_%s" % coverage.reason)
                            % {'chf_id': chf_id})
        else:
            if coverage.starts_on:
                warnings.append(_("policy.validation.member_coverage_starts")
                                % {'chf_id': chf_id, 'date': coverage.starts_on})
            if coverage.ends_on:
                warnings.append(_("policy.validation.member_coverage_ends")
                                % {'chf_id': chf_id, 'date': coverage.ends_on})
    if coverages and not any(coverage.covered for coverage in coverages):
        warnings.append(_("policy.validation.no_member_covered"))
    return warnings


def family_counts(product, family, members=None):
    """`members`: count these insurees only (the covered ones) instead of all current members."""
    adults = 0
    other_adults = 0
    extra_adults = 0
    children = 0
    other_children = 0
    extra_children = 0
    total = 0
    date_threshold = py_datetime.date.today()- relativedelta(years= CoreConfig.age_of_majority)
    counted = family.members.filter(Q(validity_to__isnull=True))
    if members is not None:
        counted = counted.filter(id__in=[member.id for member in members])
    counts = counted.aggregate(
        adults=Count('id',filter=Q(Q(dob__lt=date_threshold) & ~Q(relationship_id=7))),
        children=Count('id', filter=Q(Q(dob__gte=date_threshold) & ~Q(relationship_id=7))),
        other_children=Count('id', filter=Q(relationship_id=7, dob__gte=date_threshold)),
        other_adults=Count('id', filter=Q(relationship_id=7, dob__lt=date_threshold))
    )
    adults = counts['adults'] 
    children =  counts['children'] 
    other_children =  counts['other_children'] 
    other_adults =  counts['other_adults'] 
    
    over_children = 0
    over_adults = 0

    if product.max_members:
        over_adults = max(0,adults   - product.max_members)
        over_children = max(0,adults  + children  - over_adults - product.max_members)
        over_other_children = max(0,adults + children + other_children -over_adults -over_children- product.max_members)
        over_other_adults = max(0,adults  + other_adults + children + other_children -over_adults - over_other_children - over_children - product.max_members)
        
    # remove over from count
    children -= over_children
    adults -= over_adults
    other_children -= over_other_children
    other_adults -= over_other_adults
    if product.threshold:   
        extra_adults = max(0, adults -   product.threshold)
        extra_children = max(0,children + adults - extra_adults - product.threshold)


    return {
        "adults":adults -extra_adults, # adult part of the "lump sum"
        "extra_adults": extra_adults, # adult not part of the "lump sum" because of threshold
        "other_adults": other_adults , # adult never of the "lump sum"
        "children": children-extra_children,  # children part of the "lump sum"
        "extra_children": extra_children, # children never part of the "lump sum" because of threshold
        "other_children": other_children,# children never part of the "lump sum"
        "total": adults  + other_adults + children  +  other_children,
    }


def get_attr(product, attr):
    #  getattr(product, attr, 0)... returns None if the attr is there (with None as value!)
    value = getattr(product, attr, 0)
    return value if value else 0


def sum_contributions(product, f_counts):
    contributions = 0
    premium_adult = get_attr(product, 'premium_adult')
    premium_child = get_attr(product, 'premium_child')
    if product.lump_sum:
        contributions = product.lump_sum
        contributions += f_counts["extra_adults"] * premium_adult
        contributions += f_counts["extra_children"] * premium_child
    else:
        contributions += f_counts["adults"] * premium_adult
        contributions += f_counts["children"] * premium_child
    contributions += f_counts["other_adults"] * premium_adult
    contributions += f_counts["other_children"] * premium_child
    return contributions


def sum_general_assemblies(product, f_counts):
    if product.general_assembly_lump_sum:
        return product.general_assembly_lump_sum
    return f_counts["total"] * get_attr(product, 'general_assembly_fee')


def sum_registrations(policy, product, f_counts):
    if policy.stage != Policy.STAGE_NEW:
        return 0
    if product.registration_lump_sum:
        return product.registration_lump_sum
    return f_counts["total"] * get_attr(product, 'registration_fee')


def discount_new(policy):
    product = policy.product
    if product.has_enrolment_discount() and product.has_cycle():
        from core import datetime, datetimedelta
        min_discount_date = (
                datetime.date.from_ad_date(policy.start_date) - datetimedelta(months=product.enrolment_discount_period)
        ).to_ad_datetime()
        if policy.enroll_date <= min_discount_date:
            policy.value -= policy.value * product.enrolment_discount_perc / 100


def discount_renew(policy, prev_policy):
    product = policy.product
    if product.has_renewal_discount():
        from core import datetime, datetimedelta
        min_discount_date = (
                datetime.date.from_ad_date(prev_policy.expiry_date) +
                datetimedelta(days=1) -
                datetimedelta(months=product.renewal_discount_period)
        ).to_ad_datetime()
        if policy.enroll_date <= min_discount_date:
            policy.value -= policy.value * product.renewal_discount_perc / 100


def discount(policy, prev_policy):
    if policy.stage == Policy.STAGE_NEW:
        discount_new(policy)
    elif policy.stage == Policy.STAGE_RENEWED:
        discount_renew(policy, prev_policy)


def pro_rata_contributions(product, family, coverages):
    """
    The contributions of the covered members, a member covered for part of the period
    paying that share of what they add (their marginal contribution: nothing when they
    sit in the lump sum, their premium otherwise).
    """
    covered = covered_members(coverages)
    contributions = Decimal(sum_contributions(product, family_counts(product, family, covered)))
    reduction = Decimal(0)
    for coverage in coverages:
        if not coverage.covered or coverage.share >= 1:
            continue
        others = [member for member in covered if member.id != coverage.member.id]
        marginal = contributions - Decimal(sum_contributions(product, family_counts(product, family, others)))
        reduction += marginal * (1 - Decimal(str(coverage.share)))
    return contributions - reduction


def set_value(policy, family, prev_policy, members=None, coverages=None):
    """`coverages`: the member coverages (policy.member_ages) to pro-rate the
    contributions on, when the module configuration `age_limit_pro_rata` asks so (by
    default a covered member pays in full, however short their coverage); general
    assembly and registration count the covered members."""
    product = policy.product
    f_counts = family_counts(policy.product, family, members)
    if coverages is not None and PolicyConfig.age_limit_pro_rata:
        contributions = pro_rata_contributions(product, family, coverages)
    else:
        contributions = sum_contributions(product, f_counts)
    general_assembly = sum_general_assemblies(product, f_counts)
    registration = sum_registrations(policy, product, f_counts)
    policy.value = round(Decimal(contributions + general_assembly + registration), 2)
    discount(policy, prev_policy)


def policy_values(policy, family, prev_policy, user, enroll_date, members=None):
    """`members`: the insurees to count instead of the active members of `family`;
    only those the product's age limits cover are counted (policy.member_ages), pro-rata
    of their covered share of the period with `age_limit_pro_rata`."""
    set_start_date(policy)
    coverages = members_coverage(policy.product, family, policy.start_date,
                                 period_expiry_date(policy), members=members or None)
    # no member covered from the start: the policy starts with the first of them
    earliest = earliest_covered_start(policy, coverages)
    if earliest is not None:
        set_start_date(policy, earliest_start=earliest)
        coverages = members_coverage(policy.product, family, policy.start_date,
                                     period_expiry_date(policy), members=members or None)
    covered = covered_members(coverages)
    member_count = len(covered)
    max_members = policy.product.max_members
    above_max = max(0, member_count - max_members)
    warnings = []
    if above_max:
        warnings.append(_("policy.validation.members_count_above_max") % {'max': max_members, 'count': member_count})
    warnings += set_expiry_date(policy, family, enroll_date, members=members or None)
    set_value(policy, family, prev_policy, covered, coverages)
    return policy, warnings
