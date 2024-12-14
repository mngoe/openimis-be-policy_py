# Create your tests here.

# Create your tests here.
from django.test import TestCase

from contribution.test_helpers import create_test_premium
from core.test_helpers import create_test_officer
from policy.models import Policy
from policy.test_helpers import create_test_policy2,create_test_policy_with_IPs,create_test_insuree_for_policy
from product.test_helpers import create_test_product, create_test_product_service


class TaskGroupServiceTest(TestCase):
    def test_helper(self):
        insuree, family = create_test_insuree_for_policy(with_family=True, is_head=False, custom_props={"chf_id": "paysimp"}, family_custom_props=None)
        product = create_test_product("ELI1")
        (policy, insuree_policy) = create_test_policy2(product, insuree, custom_props={
            "value": 1000, "status": Policy.STATUS_IDLE})

        policy = create_test_policy_with_IPs(product, insuree, valid=True, policy_props={"value": 1000, "status": Policy.STATUS_ACTIVE}, IP_props=None, premium_props=None)
