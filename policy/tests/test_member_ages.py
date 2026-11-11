"""
The age limits of a product, member by member (review of PR #168, policy.member_ages).

Product: 18 to 60 years, 12 months, 100 per adult. Policy 2024-01-10 to 2025-01-09 (366 days).
Family: head 59 (reaches 60 on 2024-06-01), spouse 34, teen 17 (reaches 18 on 2024-05-01),
child 5, grandparent 64.
"""
import datetime
from decimal import Decimal
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.test_helpers import create_test_interactive_user
from insuree.models import InsureePolicy
from insuree.test_helpers import create_test_insuree
from policy.member_ages import member_coverage, apply_member_dates
from policy.models import Policy
from policy.services import PolicyService, update_insuree_policies
from policy.test_helpers import create_test_policy
from policy.values import policy_values, family_counts

START = datetime.date(2024, 1, 10)
EXPIRY = datetime.date(2025, 1, 9)
PERIOD = (EXPIRY - START).days + 1
HEAD_AGES_OUT = datetime.date(2024, 6, 1)
TEEN_COVERED_FROM = datetime.date(2024, 5, 1)


def _days(first, last):
    return (last - first).days + 1


def _product(code, **props):
    """product.test_helpers imports program.test_helpers, absent on Cameroon's program dev-csu."""
    from program.models import Program
    from product.models import Product
    values = dict(lump_sum=0, premium_adult=100, premium_child=50, max_members=10)
    values.update(props)
    program = Program.objects.create(code=code[:10], nameProgram=f"Program {code}")
    return Product.objects.create(
        code=code, name=f"Test product {code}", grace_period_enrolment=1, insurance_period=12,
        date_from="2019-01-01", date_to="2049-01-01", validity_from="2019-01-01", audit_user_id=-1,
        program=program, **values)


def _member(family, chf_id, dob):
    return create_test_insuree(with_family=False, custom_props={"chf_id": chf_id, "dob": dob, "family": family})


class MemberAgesTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_interactive_user(username="memberages")
        cls.product = _product("AGE1860", age_minimal=18, age_maximal=60)
        cls.no_limit = _product("AGENONE")
        cls.head = create_test_insuree(with_family=True, is_head=True,
                                       custom_props={"chf_id": "AGE000001", "dob": datetime.date(1964, 6, 1)})
        cls.family = cls.head.family
        cls.spouse = _member(cls.family, "AGE000002", datetime.date(1990, 1, 1))
        cls.child = _member(cls.family, "AGE000003", datetime.date(2019, 1, 1))
        cls.grandparent = _member(cls.family, "AGE000004", datetime.date(1960, 1, 1))
        cls.teen = _member(cls.family, "AGE000009", datetime.date(2006, 5, 1))

    def _policy(self, product=None, head=None, **props):
        policy = create_test_policy(product or self.product, head or self.head, link=False, custom_props={
            "enroll_date": START, "start_date": START, "expiry_date": EXPIRY, **props})
        # create_test_policy computes the values on the head alone: back to the full period
        Policy.objects.filter(id=policy.id).update(expiry_date=EXPIRY)
        policy.refresh_from_db()
        return policy

    def _ips(self, policy, field="expiry_date"):
        return {ip.insuree.chf_id: getattr(ip, field)
                for ip in InsureePolicy.objects.filter(policy=policy, validity_to__isnull=True)}

    COVERED_EXPIRY = {"AGE000001": HEAD_AGES_OUT, "AGE000002": EXPIRY, "AGE000009": EXPIRY}
    COVERED_START = {"AGE000001": START, "AGE000002": START, "AGE000009": TEEN_COVERED_FROM}

    # --- the rule, member by member
    def test_member_coverage(self):
        cover = lambda member: member_coverage(self.product, member, START, EXPIRY)
        head, spouse, teen = cover(self.head), cover(self.spouse), cover(self.teen)
        self.assertEqual((True, None, HEAD_AGES_OUT), (head.covered, head.starts_on, head.ends_on))
        self.assertAlmostEqual(_days(START, HEAD_AGES_OUT) / PERIOD, head.share)
        self.assertEqual((True, None, None, 1.0), (spouse.covered, spouse.starts_on, spouse.ends_on, spouse.share))
        self.assertEqual((True, TEEN_COVERED_FROM, None), (teen.covered, teen.starts_on, teen.ends_on))
        self.assertAlmostEqual(_days(TEEN_COVERED_FROM, EXPIRY) / PERIOD, teen.share)
        self.assertEqual((False, "below_min"), (cover(self.child).covered, cover(self.child).reason))
        self.assertEqual((False, "above_max"), (cover(self.grandparent).covered, cover(self.grandparent).reason))
        self.assertEqual("no_dob", member_coverage(self.product, mock.Mock(dob=None), START, EXPIRY).reason)

    def test_without_expiry_checked_on_the_start_date(self):
        """the service checks before the expiry is known: the teen is not 18 on the start date"""
        self.assertFalse(member_coverage(self.product, self.teen, START).covered)
        self.assertTrue(member_coverage(self.product, self.spouse, START).covered)

    def test_no_age_limits_covers_everyone(self):
        for member in (self.head, self.spouse, self.child, self.grandparent, self.teen):
            coverage = member_coverage(self.no_limit, member, START, EXPIRY)
            self.assertEqual((True, None, None, 1.0),
                             (coverage.covered, coverage.starts_on, coverage.ends_on, coverage.share))

    # --- the values preview
    def test_values_pro_rata_of_the_covered_members(self):
        policy, warnings = policy_values(self._policy(), self.family, None, self.user, START)
        expected = 100 + 100 * Decimal(_days(START, HEAD_AGES_OUT)) / PERIOD \
            + 100 * Decimal(_days(TEEN_COVERED_FROM, EXPIRY)) / PERIOD
        self.assertAlmostEqual(float(expected), float(policy.value), places=1,
                               msg="spouse in full, head and teen pro-rata, child and grandparent not counted")
        self.assertEqual(EXPIRY, policy.expiry_date, "the spouse is covered the whole period")
        for key in ("member_not_covered_below_min", "member_not_covered_above_max",
                    "member_coverage_ends", "member_coverage_starts"):
            self.assertIn(f"policy.validation.{key}", warnings)
        self.assertEqual(5, family_counts(self.no_limit, self.family)["total"], "[control] all members")

    def test_lump_sum_is_not_pro_rated(self):
        """a member within the lump sum adds nothing: their partial coverage takes nothing off"""
        lump = _product("AGELUMP", age_minimal=18, age_maximal=60, lump_sum=500, threshold=5)
        policy, _ = policy_values(self._policy(product=lump), self.family, None, self.user, START)
        self.assertEqual(Decimal(500), policy.value)

    def test_policy_ends_with_its_last_member_when_all_age_out(self):
        head = create_test_insuree(with_family=True, is_head=True,
                                   custom_props={"chf_id": "AGE000005", "dob": datetime.date(1964, 6, 1)})
        policy, _ = policy_values(self._policy(head=head), head.family, None, self.user, START)
        self.assertEqual(HEAD_AGES_OUT, policy.expiry_date)

    # --- saving
    def test_policy_covering_no_one_is_refused(self):
        child = create_test_insuree(with_family=True, is_head=True,
                                    custom_props={"chf_id": "AGE000006", "dob": datetime.date(2019, 1, 1)})
        data = dict(family_id=child.family.id, product_id=self.product.id, enroll_date=START,
                    start_date=START, expiry_date=EXPIRY)
        with self.assertRaises(ValidationError) as ctx:
            PolicyService(self.user).update_or_create(data, self.user)
        self.assertIn("AGE000006", str(ctx.exception))
        self.assertIn("n'a pas encore l'âge minimal requis", str(ctx.exception))

    def test_member_reaching_the_minimum_within_the_period_saves(self):
        """a family of one 17 year old reaching 18 within the period: covered from then"""
        teen = create_test_insuree(with_family=True, is_head=True,
                                   custom_props={"chf_id": "AGE000010", "dob": datetime.date(2006, 5, 1)})
        data = dict(family_id=teen.family.id, product_id=self.product.id, enroll_date=START,
                    start_date=START, expiry_date=EXPIRY)
        try:
            PolicyService(self.user).update_or_create(data, self.user)
        except ValidationError as exc:
            self.fail(f"refused: {exc}")
        except Exception:
            pass  # later steps need more data: only the age check matters here

    def test_insuree_policies_of_the_covered_members(self):
        policy = self._policy()
        # a row left from before for a member who is not covered gets closed
        InsureePolicy.objects.create(insuree=self.child, policy=policy, audit_user_id=-1,
                                     effective_date=START, expiry_date=EXPIRY)
        update_insuree_policies(policy, -1)
        self.assertEqual(self.COVERED_EXPIRY, self._ips(policy))
        self.assertEqual(self.COVERED_START, self._ips(policy, "start_date"))

    def test_no_age_limits_every_member_the_whole_period(self):
        policy = self._policy(product=self.no_limit)
        update_insuree_policies(policy, -1)
        self.assertEqual({c: EXPIRY for c in ("AGE000001", "AGE000002", "AGE000003", "AGE000004", "AGE000009")},
                         self._ips(policy))

    # --- payments reset the member dates (contribution._update_policy_insurees / _activate_insurees)
    def test_member_dates_restored_after_a_reset(self):
        policy = self._policy()
        update_insuree_policies(policy, -1)
        pay_date = datetime.date(2024, 2, 1)
        policy.insuree_policies.filter(validity_to__isnull=True).update(
            start_date=START, effective_date=pay_date, expiry_date=EXPIRY)
        apply_member_dates(policy)
        self.assertEqual(self.COVERED_EXPIRY, self._ips(policy))
        self.assertEqual(self.COVERED_START, self._ips(policy, "start_date"))
        self.assertEqual({"AGE000001": pay_date, "AGE000002": pay_date, "AGE000009": TEEN_COVERED_FROM},
                         self._ips(policy, "effective_date"), "the teen is effective once 18")

    def test_no_age_limits_dates_left_as_they_are(self):
        policy = self._policy(product=self.no_limit)
        update_insuree_policies(policy, -1)
        odd = datetime.date(2024, 3, 3)
        policy.insuree_policies.filter(validity_to__isnull=True).update(expiry_date=odd)
        apply_member_dates(policy)
        self.assertEqual({odd}, set(self._ips(policy).values()))

    def test_contribution_mutation_restores_member_dates(self):
        from policy.schema import on_contribution_after_mutation
        policy = self._policy()
        update_insuree_policies(policy, -1)
        policy.insuree_policies.filter(validity_to__isnull=True).update(start_date=START, expiry_date=EXPIRY)
        on_contribution_after_mutation(None, data={"policy_uuid": str(policy.uuid)})
        self.assertEqual(HEAD_AGES_OUT, self._ips(policy)["AGE000001"])
        self.assertEqual(TEEN_COVERED_FROM, self._ips(policy, "start_date")["AGE000009"])

    # --- a member joining the family later
    def test_member_joining_is_checked(self):
        from insuree.services import InsureePolicyService
        policy = self._policy()
        update_insuree_policies(policy, -1)
        baby = _member(self.family, "AGE000007", datetime.date(2023, 5, 5))
        adult = _member(self.family, "AGE000008", datetime.date(1995, 5, 5))
        InsureePolicyService(self.user).add_insuree_policy(baby)
        InsureePolicyService(self.user).add_insuree_policy(adult)
        ips = self._ips(policy)
        self.assertNotIn("AGE000007", ips)
        self.assertEqual(EXPIRY, ips["AGE000008"])
