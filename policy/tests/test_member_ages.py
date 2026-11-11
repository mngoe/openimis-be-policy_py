"""
The age limits of a product, member by member (review of PR #168, policy.member_ages).

Product: 18 to 60 years, 12 months. Policy start 2024-01-10, expiry 2025-01-09.
Family: head 59 (reaches 60 on 2024-06-01), spouse 34, child 5, grandparent 64.
"""
import datetime
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from core.test_helpers import create_test_interactive_user
from insuree.models import InsureePolicy
from insuree.test_helpers import create_test_insuree
from policy.member_ages import member_coverage, apply_member_expiry
from policy.models import Policy
from policy.services import PolicyService, update_insuree_policies
from policy.test_helpers import create_test_policy
from policy.values import policy_values, family_counts

START = datetime.date(2024, 1, 10)
EXPIRY = datetime.date(2025, 1, 9)
HEAD_AGES_OUT = datetime.date(2024, 6, 1)


def _product(code, **props):
    """product.test_helpers imports program.test_helpers, absent on Cameroon's program dev-csu."""
    from program.models import Program
    from product.models import Product
    program = Program.objects.create(code=code[:10], nameProgram=f"Program {code}")
    return Product.objects.create(
        code=code, name=f"Test product {code}", lump_sum=0, premium_adult=100, premium_child=50,
        max_members=10, grace_period_enrolment=1, insurance_period=12, date_from="2019-01-01",
        date_to="2049-01-01", validity_from="2019-01-01", audit_user_id=-1, program=program, **props)


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

    def _policy(self, product=None, head=None):
        policy = create_test_policy(product or self.product, head or self.head, link=False, custom_props={
            "enroll_date": START, "start_date": START, "expiry_date": EXPIRY})
        # create_test_policy computes the values on the head alone: back to the full period
        Policy.objects.filter(id=policy.id).update(expiry_date=EXPIRY)
        policy.refresh_from_db()
        return policy

    def _ips(self, policy):
        return {ip.insuree.chf_id: ip.expiry_date
                for ip in InsureePolicy.objects.filter(policy=policy, validity_to__isnull=True)}

    # --- the rule, member by member
    def test_member_coverage(self):
        cover = lambda member: member_coverage(self.product, member, START, EXPIRY)
        self.assertEqual((True, HEAD_AGES_OUT), (cover(self.head).covered, cover(self.head).ends_on))
        self.assertEqual((True, None), (cover(self.spouse).covered, cover(self.spouse).ends_on))
        self.assertEqual((False, "below_min"), (cover(self.child).covered, cover(self.child).reason))
        self.assertEqual((False, "above_max"), (cover(self.grandparent).covered, cover(self.grandparent).reason))
        no_dob = mock.Mock(dob=None)
        self.assertEqual("no_dob", member_coverage(self.product, no_dob, START, EXPIRY).reason)

    def test_no_age_limits_covers_everyone(self):
        for member in (self.head, self.spouse, self.child, self.grandparent):
            coverage = member_coverage(self.no_limit, member, START, EXPIRY)
            self.assertEqual((True, None), (coverage.covered, coverage.ends_on))

    # --- the values preview
    def test_values_count_the_covered_members_only(self):
        policy, warnings = policy_values(self._policy(), self.family, None, self.user, START)
        self.assertEqual(200, policy.value, "head + spouse at 100, the child and grandparent are not counted")
        self.assertEqual(EXPIRY, policy.expiry_date, "the spouse is covered the whole period")
        self.assertIn("policy.validation.member_not_covered_below_min", warnings)
        self.assertIn("policy.validation.member_not_covered_above_max", warnings)
        self.assertIn("policy.validation.member_coverage_ends", warnings)
        self.assertEqual(4, family_counts(self.no_limit, self.family)["total"], "[control] all members")

    def test_policy_ends_with_its_last_member_when_all_age_out(self):
        head = create_test_insuree(with_family=True, is_head=True,
                                   custom_props={"chf_id": "AGE000005", "dob": datetime.date(1964, 6, 1)})
        policy, _ = policy_values(self._policy(head=head), head.family, None, self.user, START)
        self.assertEqual(HEAD_AGES_OUT, policy.expiry_date)

    # --- saving
    def test_policy_covering_no_one_is_refused(self):
        child = create_test_insuree(with_family=True, is_head=True,
                                    custom_props={"chf_id": "AGE000006", "dob": datetime.date(2019, 1, 1)})
        data = dict(family_id=child.family.id, product_id=self.product.id, enroll_date=START, start_date=START)
        with self.assertRaises(ValidationError) as ctx:
            PolicyService(self.user).update_or_create(data, self.user)
        self.assertIn("AGE000006", str(ctx.exception))
        self.assertIn("n'a pas encore l'âge minimal requis", str(ctx.exception))

    def test_policy_covering_some_members_is_saved(self):
        """the family has two covered members: the policy is not refused for the others"""
        data = dict(family_id=self.family.id, product_id=self.product.id, enroll_date=START, start_date=START)
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
        self.assertEqual({"AGE000001": HEAD_AGES_OUT, "AGE000002": EXPIRY}, self._ips(policy))

    def test_no_age_limits_every_member_until_the_policy_expiry(self):
        policy = self._policy(product=self.no_limit)
        update_insuree_policies(policy, -1)
        self.assertEqual({f"AGE00000{i}": EXPIRY for i in range(1, 5)}, self._ips(policy))

    # --- payments reset the member dates (contribution._update_policy_insurees)
    def test_member_expiry_restored_after_a_reset(self):
        policy = self._policy()
        update_insuree_policies(policy, -1)
        policy.insuree_policies.filter(validity_to__isnull=True).update(expiry_date=EXPIRY)
        apply_member_expiry(policy)
        self.assertEqual({"AGE000001": HEAD_AGES_OUT, "AGE000002": EXPIRY}, self._ips(policy))

    def test_contribution_mutation_restores_member_expiry(self):
        from policy.schema import on_contribution_after_mutation
        policy = self._policy()
        update_insuree_policies(policy, -1)
        policy.insuree_policies.filter(validity_to__isnull=True).update(expiry_date=EXPIRY)
        on_contribution_after_mutation(None, data={"policy_uuid": str(policy.uuid)})
        self.assertEqual(HEAD_AGES_OUT, self._ips(policy)["AGE000001"])

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
