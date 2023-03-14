import core

from django.test import TestCase
from insuree.test_helpers import create_test_insuree, create_test_photo
from product.test_helpers import create_test_product
from insuree.models import Relation
from .values import *
from .test_helpers import create_test_policy


class PolicyValuesTestCase(TestCase):
    def test_new_policy_basis(self):
        head_insuree = create_test_insuree(with_family=True, custom_props={"dob": core.datetime.date(1985, 5, 5)})
        spouse = Relation.objects.get(id=8)
        create_test_insuree(
            custom_props={
                "dob": core.datetime.date(1989, 9, 9),
                "relationship": spouse,
                "family": head_insuree.family
            })

        product = create_test_product("SIMPLE", custom_props={
            "max_members": 5,
            "administration_period": 0,
            "lump_sum": 0,
            "premium_adult": 300,
            "premium_child": 200,
            "registration_lump_sum": 250,
            "general_assembly_lump_sum": 130,
            "insurance_period": 12,
        })
        policy = create_test_policy(product, head_insuree, custom_props={
            "enroll_date": core.datetime.date(2020, 11, 10),
        })
        policy, warnings = policy_values(policy, head_insuree.family, None)
        self.assertEquals(policy.start_date, core.datetime.date(2020, 11, 10))
        self.assertEquals(policy.expiry_date, core.datetime.date(2021, 11, 9))
        self.assertEquals(policy.value, 980)  # 2 x 300 + 250 + 130

        # let's add a child and shift date to 1st of a month
        child = Relation.objects.get(id=4)
        create_test_insuree(
            custom_props={
                "dob": core.datetime.date(2020, 2, 20),
                "relationship": child,
                "family": head_insuree.family
            })
        policy = create_test_policy(product, head_insuree, custom_props={
            "enroll_date": core.datetime.date(2020, 11, 1),
        })
        policy, warnings = policy_values(policy, head_insuree.family, None)
        self.assertEquals(policy.start_date, core.datetime.date(2020, 11, 1))
        self.assertEquals(policy.expiry_date, core.datetime.date(2021, 10, 31))
        self.assertEquals(policy.value, 1180)  # 2 x 300 + 200 + 250 + 130

    def test_new_policy_lump_sum_and_cycles(self):
        head_insuree = create_test_insuree(with_family=True, custom_props={"dob": core.datetime.date(1985, 5, 5)})
        spouse = Relation.objects.get(id=8)
        create_test_insuree(
            custom_props={
                "dob": core.datetime.date(1989, 9, 9),
                "relationship": spouse,
                "family": head_insuree.family
            })

        product = create_test_product("SIMPLE", custom_props={
            "max_members": 5,
            "administration_period": 0,
            "lump_sum": 200,
            "threshold": 2,
            "grace_period_enrolment": 1,
            "start_cycle_1": "01-01",
            "start_cycle_2": "01-06",
            "premium_adult": 300,
            "premium_child": 200,
            "registration_lump_sum": 0,
            "registration_fee": 10,
            "general_assembly_lump_sum": 0,
            "general_assembly_fee": 5,
            "insurance_period": 12,
        })
        policy = create_test_policy(product, head_insuree, custom_props={
            "enroll_date": core.datetime.date(2020, 11, 10),
        })
        policy, warnings = policy_values(policy, head_insuree.family, None)
        self.assertEquals(policy.start_date, core.datetime.date(2021, 1, 1))
        self.assertEquals(policy.expiry_date, core.datetime.date(2021, 12, 31))
        self.assertEquals(policy.value, 230)  # 200 + 2 x 10 + 2 x 5

        # let's add a child (outside threshold)  and shift date in 1st cycle grace period
        child = Relation.objects.get(id=4)
        create_test_insuree(
            custom_props={
                "dob": core.datetime.date(2020, 2, 20),
                "relationship": child,
                "family": head_insuree.family
            })
        policy = create_test_policy(product, head_insuree, custom_props={
            "enroll_date": core.datetime.date(2021, 1, 11),
        })
        policy, warnings = policy_values(policy, head_insuree.family, None)
        self.assertEquals(policy.start_date, core.datetime.date(2021, 1, 1))
        self.assertEquals(policy.expiry_date, core.datetime.date(2021, 12, 31))
        self.assertEquals(policy.value, 445)  # 200 + 1 x 200 + 3 x 10 + 3 x 5

    def test_new_policy_admin_period_max_members_insurance_period(self):
        head_insuree = create_test_insuree(with_family=True, custom_props={"dob": core.datetime.date(1985, 5, 5)})
        spouse = Relation.objects.get(id=8)
        create_test_insuree(
            custom_props={
                "dob": core.datetime.date(1989, 9, 9),
                "relationship": spouse,
                "family": head_insuree.family
            })

        product = create_test_product("SIMPLE", custom_props={
            "max_members": 2,
            "administration_period": 1,
            "lump_sum": 200,
            "threshold": 1,
            "grace_period_enrolment": 1,
            "start_cycle_1": "01-01",
            "start_cycle_2": "01-06",
            "premium_adult": 300,
            "premium_child": 200,
            "registration_lump_sum": 0,
            "registration_fee": 10,
            "general_assembly_lump_sum": 0,
            "general_assembly_fee": 5,
            "insurance_period": 6,
        })
        policy = create_test_policy(product, head_insuree, custom_props={
            "enroll_date": core.datetime.date(2021, 1, 10),
        })
        policy, warnings = policy_values(policy, head_insuree.family, None)
        self.assertEquals(policy.start_date, core.datetime.date(2021, 6, 1))  # enroll + admin outside cycle 1 + grace
        self.assertEquals(policy.expiry_date, core.datetime.date(2021, 11, 30))
        self.assertEquals(policy.value, 530)  # 200 + 300 + 2 x 10 + 2 x 5

        # let's add a child... outside max members so not counted!
        # ... and shift date to fall into grace period
        child = Relation.objects.get(id=4)
        create_test_insuree(
            custom_props={
                "dob": core.datetime.date(2020, 2, 20),
                "relationship": child,
                "family": head_insuree.family
            })
        policy = create_test_policy(product, head_insuree, custom_props={
            "enroll_date": core.datetime.date(2021, 12, 11),
        })
        policy, warnings = policy_values(policy, head_insuree.family, None)
        self.assertEquals(policy.start_date, core.datetime.date(2022, 1, 1))  # enroll + admin in cycle 1 + grace
        self.assertEquals(policy.expiry_date, core.datetime.date(2022, 6, 30))
        self.assertEquals(policy.value, 530)  # 200 + 300 + 2 x 10 + 2 x 5
