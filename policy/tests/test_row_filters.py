"""get_queryset honours the OP-2029 validity contract (epic OP-3317, phase 1).

Explicit validity values return the expected rows; a caller asking for
nothing gets what it got before the contract existed.
"""

from django.test import TestCase

from core.test_helpers import assert_row_filters, create_test_interactive_user, mark_deleted
from insuree.test_helpers import create_test_insuree
from policy.models import Policy
from policy.test_helpers import create_test_policy
from product.test_helpers import create_test_product


class PolicyRowFiltersTest(TestCase):
    def test_policy(self):
        user = create_test_interactive_user(username="policyrowfilters")
        product = create_test_product("RWF1")
        live = create_test_policy(product, create_test_insuree())
        deleted = mark_deleted(create_test_policy(product, create_test_insuree()))
        assert_row_filters(
            self, Policy, Policy.objects.filter(id__in=[live.id, deleted.id]), user,
            live.id, deleted.id, default_hides_deleted=True,
        )
