"""
The age limits of a product, member by member.

A family policy covers the current members of the family, but a product may carry an age
range (`age_minimal` / `age_maximal`). Each member is checked over the policy period:

- coverage of a member starts on the policy start date, or on the day they reach
  `age_minimal` when that falls within the period;
- coverage of a member ends on the policy expiry date, or on the day they reach
  `age_maximal` when that falls before it (that day included);
- a member reaching `age_maximal` on or before the start date, or `age_minimal` after the
  expiry date, is not covered; nor is a member without date of birth.

Each covered member gets their own dates on their InsureePolicy (claims check those), and
pays in full - or the share of the period they are covered with the module configuration
`age_limit_pro_rata` (see policy.values). The policy
keeps its period unless every member ages out before it ends; a policy covering no member
is refused. Without age limits every current member is covered the whole period, and the
member dates are left as they are (`member_dates` gives nothing to apply).
"""
from dataclasses import dataclass
import datetime as py_datetime

from dateutil.relativedelta import relativedelta


@dataclass
class MemberCoverage:
    member: object
    covered: bool
    # the first / last covered day when it differs from the policy start / expiry
    starts_on: py_datetime.date = None
    ends_on: py_datetime.date = None
    # the covered share of the policy period (1 = the whole period)
    share: float = 1.0
    reason: str = None


def has_age_limits(product):
    return bool(product.age_minimal or product.age_maximal)


def _date(value):
    if value is None:
        return None
    if isinstance(value, py_datetime.datetime):
        return value.date()
    if isinstance(value, py_datetime.date):
        return py_datetime.date(value.year, value.month, value.day)
    return py_datetime.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def member_coverage(product, member, start_date, expiry_date=None):
    """
    The coverage of `member` by a policy of `product` from `start_date` to `expiry_date`
    (unknown expiry: checked on the start date only).
    """
    if not has_age_limits(product):
        return MemberCoverage(member, True)
    dob = _date(member.dob)
    if dob is None:
        return MemberCoverage(member, False, share=0, reason="no_dob")
    start = _date(start_date)
    expiry = _date(expiry_date)
    starts_on = ends_on = None
    if product.age_minimal:
        reaches_min = dob + relativedelta(years=product.age_minimal)
        if reaches_min > (expiry or start):
            return MemberCoverage(member, False, share=0, reason="below_min")
        if reaches_min > start:
            starts_on = reaches_min
    if product.age_maximal:
        reaches_max = dob + relativedelta(years=product.age_maximal)
        if reaches_max <= (starts_on or start):
            return MemberCoverage(member, False, share=0, reason="above_max")
        if expiry is not None and reaches_max < expiry:
            ends_on = reaches_max
    share = 1.0
    if expiry is not None and (starts_on or ends_on):
        period = (expiry - start).days + 1
        covered = ((ends_on or expiry) - (starts_on or start)).days + 1
        share = max(0.0, min(1.0, covered / period)) if period > 0 else 1.0
    return MemberCoverage(member, True, starts_on=starts_on, ends_on=ends_on, share=share)


def current_members(family):
    return list(family.members.filter(validity_to__isnull=True).order_by("id")) if family else []


def members_coverage(product, family, start_date, expiry_date=None, members=None):
    members = current_members(family) if members is None else list(members)
    return [member_coverage(product, member, start_date, expiry_date) for member in members]


def covered_members(coverages):
    return [coverage.member for coverage in coverages if coverage.covered]


def policy_expiry_date(coverages, expiry_date):
    """The policy runs its full period unless every covered member ages out before."""
    covered = [coverage for coverage in coverages if coverage.covered]
    if covered and all(coverage.ends_on for coverage in covered):
        return max(coverage.ends_on for coverage in covered)
    return expiry_date


def member_dates(product, member, policy, effective_date=None):
    """
    The InsureePolicy dates of `member` on `policy`: {start_date, effective_date,
    expiry_date}. None when the product has no age limits (nothing to adjust) or the
    member is not covered. `effective_date`: the one of the member row (activation),
    the policy one by default; a member covered later is effective from that day.
    """
    if not has_age_limits(product):
        return None
    coverage = member_coverage(product, member, policy.start_date, policy.expiry_date)
    if not coverage.covered:
        return None
    effective = _date(effective_date if effective_date is not None else policy.effective_date)
    first_day = coverage.starts_on or _date(policy.start_date)
    if effective is not None and first_day and first_day > effective:
        effective = first_day  # never effective before the member (or the policy) starts
    return {
        "start_date": coverage.starts_on or _date(policy.start_date),
        "effective_date": effective,
        "expiry_date": coverage.ends_on or _date(policy.expiry_date),
    }


def insuree_policy_values(product, member, policy):
    """The dates of a new InsureePolicy of `member`: theirs, or the policy ones."""
    return member_dates(product, member, policy) or {
        "start_date": policy.start_date,
        "effective_date": policy.effective_date,
        "expiry_date": policy.expiry_date,
    }


def apply_member_dates(policy):
    """
    Writes back the member dates of `policy` on its current InsureePolicy rows: a write
    resetting them all to the policy dates (the contribution module does on payment) is
    corrected here. A member the code gives no dates for is left as it is, except that no
    member is effective before the policy start (a payment of a policy dated in the
    future).
    """
    if policy is None:
        return
    rows = policy.insuree_policies.filter(validity_to__isnull=True).select_related("insuree")
    if not has_age_limits(policy.product):
        # the payment activates from its date: never before the policy start
        if policy.start_date is not None:
            rows.filter(effective_date__lt=policy.start_date).update(effective_date=policy.start_date)
        return
    for insuree_policy in rows:
        dates = member_dates(policy.product, insuree_policy.insuree, policy,
                             effective_date=insuree_policy.effective_date)
        if dates is None:
            continue
        changed = {field: value for field, value in dates.items()
                   if _date(getattr(insuree_policy, field)) != _date(value)}
        if changed:
            type(insuree_policy).objects.filter(id=insuree_policy.id).update(**changed)
