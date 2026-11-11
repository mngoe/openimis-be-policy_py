"""
The age limits of a product, member by member.

A family policy covers the current members of the family, but a product may carry an age
range (`age_minimal` / `age_maximal`). The age is taken on the policy start date:

- a member who has not reached `age_minimal` yet is not covered;
- coverage of a member ends on the day they reach `age_maximal`: a member reaching it on
  or before the start date is not covered, one reaching it before the policy expiry is
  covered until that day (their `InsureePolicy.expiry_date`, claims use it);
- a member without date of birth cannot be checked, so is not covered.

The members out of the range are not counted in the policy value, and a policy no member
can be covered by is refused. Without age limits every current member is covered.
"""
from dataclasses import dataclass
import datetime as py_datetime

from dateutil.relativedelta import relativedelta


@dataclass
class MemberCoverage:
    member: object
    covered: bool
    # the last covered day when the member ages out before the policy expiry, else None
    ends_on: py_datetime.date = None
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
    """Is `member` covered by a policy of `product` starting on `start_date` ?"""
    if not has_age_limits(product):
        return MemberCoverage(member, True)
    dob = _date(member.dob)
    if dob is None:
        return MemberCoverage(member, False, reason="no_dob")
    start = _date(start_date)
    if product.age_minimal and relativedelta(start, dob).years < product.age_minimal:
        return MemberCoverage(member, False, reason="below_min")
    if product.age_maximal:
        ages_out = dob + relativedelta(years=product.age_maximal)
        if ages_out <= start:
            return MemberCoverage(member, False, reason="above_max")
        expiry = _date(expiry_date)
        if expiry is not None and ages_out < expiry:
            return MemberCoverage(member, True, ends_on=ages_out)
    return MemberCoverage(member, True)


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


def insuree_policy_expiry(product, member, policy):
    """The expiry date of `member` on `policy`: the policy one, or the day they age out."""
    coverage = member_coverage(product, member, policy.start_date, policy.expiry_date)
    if coverage.ends_on and _date(policy.expiry_date) and coverage.ends_on < _date(policy.expiry_date):
        return coverage.ends_on
    return policy.expiry_date


def apply_member_expiry(policy):
    """
    Writes back the member expiry dates of `policy` (current InsureePolicy rows): a write
    resetting them all to the policy expiry (the contribution module does on payment) is
    corrected here.
    """
    if policy is None or not has_age_limits(policy.product):
        return
    for insuree_policy in policy.insuree_policies.filter(validity_to__isnull=True).select_related("insuree"):
        expiry = insuree_policy_expiry(policy.product, insuree_policy.insuree, policy)
        if _date(insuree_policy.expiry_date) != _date(expiry):
            type(insuree_policy).objects.filter(id=insuree_policy.id).update(expiry_date=expiry)
