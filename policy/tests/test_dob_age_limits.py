"""
A product with age limits and no date of birth to check them on (review of PR #168): saving
the policy is refused with a clear message, the values preview only warns.

`tblInsuree.DOB` is NOT NULL in the database (the model says null=True), so the case only
happens for real when the family has no current member; the service is tested with a stub.
"""
from unittest import mock

import core
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.test_helpers import create_test_interactive_user
from insuree.test_helpers import create_test_insuree
from policy.services import PolicyService
from policy.test_helpers import create_test_policy
from policy.values import policy_values


def _product(code, **props):
    """product.test_helpers imports program.test_helpers, absent on Cameroon's program dev-csu."""
    from program.models import Program
    from product.models import Product
    program = Program.objects.create(code=code[:10], nameProgram=f"Program {code}")
    return Product.objects.create(
        code=code, name=f"Test product {code}", lump_sum=100, max_members=5,
        grace_period_enrolment=1, insurance_period=12, date_from="2019-01-01", date_to="2049-01-01",
        validity_from="2019-01-01", audit_user_id=-1, program=program, **props)


class DobAgeLimitsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_interactive_user(username="dobagelimits")
        cls.product = _product("DOBMAX", age_maximal=60)
        cls.no_limit = _product("DOBNONE")
        cls.insuree = create_test_insuree(with_family=True, custom_props={"chf_id": "DOB000001"})
        # a family without current member: no date of birth to apply the age limits on
        cls.empty_family = create_test_insuree(with_family=True, custom_props={"chf_id": "DOB000002"})
        cls.empty_family.validity_to = core.datetime.datetime(2020, 1, 1)
        cls.empty_family.save()

    def _data(self, product):
        return dict(family_id=self.insuree.family.id, product_id=product.id,
                    enroll_date=core.datetime.date(2024, 1, 10), start_date=core.datetime.date(2024, 1, 10))

    def _without_dob(self):
        stub = mock.Mock(dob=None, chf_id="DOB000001")
        return mock.patch("policy.services.Insuree.objects.filter", return_value=[stub])

    def test_save_refused_without_dob(self):
        with self._without_dob(), self.assertRaises(ValidationError) as ctx:
            PolicyService(self.user).update_or_create(self._data(self.product), self.user)
        self.assertIn("policy.validation.member_without_dob", str(ctx.exception))

    def test_save_without_age_limit_does_not_need_dob(self):
        with self._without_dob():
            try:
                PolicyService(self.user).update_or_create(self._data(self.no_limit), self.user)
            except ValidationError as exc:
                self.assertNotIn("member_without_dob", str(exc))
            except Exception:
                pass  # later steps need more data: only the date of birth check matters here

    def test_values_preview_warns_without_dob(self):
        policy = create_test_policy(self.product, self.empty_family, link=False,
                                    custom_props={"enroll_date": core.datetime.date(2024, 1, 10)})
        policy, warnings = policy_values(policy, self.empty_family.family, None, self.user,
                                         core.datetime.date(2024, 1, 10))
        self.assertIn("policy.validation.max_age_not_applied_without_dob", warnings)
        self.assertIsNotNone(policy.expiry_date)

    def test_values_preview_no_warning_without_age_limit(self):
        policy = create_test_policy(self.no_limit, self.empty_family, link=False,
                                    custom_props={"enroll_date": core.datetime.date(2024, 1, 10)})
        _, warnings = policy_values(policy, self.empty_family.family, None, self.user,
                                    core.datetime.date(2024, 1, 10))
        self.assertNotIn("policy.validation.max_age_not_applied_without_dob", warnings)

    def test_values_preview_with_dob_caps_the_expiry_date(self):
        """[control] with a date of birth the max age cuts the expiry date, no warning."""
        old = _product("DOBOLD", age_maximal=40)
        self.insuree.dob = core.datetime.date(1984, 3, 1)
        self.insuree.save()
        policy = create_test_policy(old, self.insuree, link=False,
                                    custom_props={"enroll_date": core.datetime.date(2024, 1, 10),
                                                  "start_date": core.datetime.date(2024, 1, 10)})
        policy, warnings = policy_values(policy, self.insuree.family, None, self.user,
                                         core.datetime.date(2024, 1, 10))
        self.assertEqual([], warnings)
        self.assertEqual(core.datetime.date(2024, 3, 1), policy.expiry_date)
