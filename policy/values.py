from django.utils.translation import gettext as _
import datetime as py_datetime
from core.apps import CoreConfig
from .models import Policy


def cycle_start(product, cycle, ref_date):
    c = getattr(product, "start_cycle_%s" % (cycle + 1), None)
    if not c:
        return None
    start = py_datetime.datetime.strptime("%s-%s" % (c, ref_date.year), '%d-%m-%Y')
    if ref_date <= start:
        return start


def set_start_date(policy):
    from core import datetime, datetimedelta
    product = policy.product
    ref_enroll_date = policy.enroll_date
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


def set_expiry_date(policy):
    product = policy.product
    from core import datetime, datetimedelta

    insurance_period = datetimedelta(
        months=product.insurance_period) if product.insurance_period % 12 != 0 else datetimedelta(
        years=product.insurance_period // 12)
    policy.expiry_date = (
            datetime.date.from_ad_date(policy.start_date) +
            insurance_period -
            datetimedelta(days=1)
    ).to_ad_date()


def family_counts(product, family):
    adults = 0
    other_adults = 0
    extra_adults = 0
    children = 0
    other_children = 0
    extra_children = 0
    total = 0
    # sad, but can't get the limit inside the prefetch
    # product.max_members is NOT NULL (but can be 0)
    for member in family.members.all()[:product.max_members]:
        total += 1
        age = member.age()
        if age >= CoreConfig.age_of_majority and member.relationship_id != 7:
            adults += 1
        elif age >= CoreConfig.age_of_majority:
            other_adults += 1
        elif member.relationship_id != 7:
            children += 1
        else:
            other_children += 1
    if product.threshold:
        extra_adults = max(0, adults - product.threshold)
        extra_children = max(0, children - (product.threshold - adults + extra_adults))

    return {
        "adults": adults,
        "extra_adults": extra_adults,
        "other_adults": other_adults,
        "children": children,
        "extra_children": extra_children,
        "other_children": other_children,
        "total": total,
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


def set_value(policy, family, prev_policy):
    product = policy.product
    f_counts = family_counts(policy.product, family)
    contributions = sum_contributions(product, f_counts)
    general_assembly = sum_general_assemblies(product, f_counts)
    registration = sum_registrations(policy, product, f_counts)
    policy.value = contributions + general_assembly + registration
    discount(policy, prev_policy)


def policy_values(policy, family, prev_policy):
    members = family.members.filter(validity_to__isnull=True).count()
    max_members = policy.product.max_members
    above_max = max(0, members - max_members)
    warnings = []
    if above_max:
        warnings.append(_("policy.validation.members_count_above_max") % {'max': max_members, 'count': members})
    set_start_date(policy)
    set_expiry_date(policy)
    set_value(policy, family, prev_policy)
    return policy, warnings
