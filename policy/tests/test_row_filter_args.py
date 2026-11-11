import json
from dataclasses import dataclass

from graphql_jwt.shortcuts import get_token

from core.models import User
from core.models.openimis_graphql_test_case import openIMISGraphQLTestCase
from core.test_helpers import create_test_interactive_user
from insuree.test_helpers import create_test_insuree
from location.test_helpers import create_test_village
from policy.models import Policy
from policy.test_helpers import create_test_policy
from product.test_helpers import create_test_product


@dataclass
class DummyContext:
    user: User


class PolicyRowFilterArgsTest(openIMISGraphQLTestCase):
    """policies: the legacy showHistory keeps its meaning, isDeleted is new.

    Validity is applied by Policy.get_queryset (OP-2029) through PolicyGQLType,
    not by the resolver: the resolver only states what showHistory means.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        village = create_test_village({"name": "PolRowArgs"})
        insuree = create_test_insuree(
            with_family=True, is_head=True,
            custom_props={"chf_id": "PRA000001", "current_village": village},
            family_custom_props={"location": village})
        product = create_test_product("PRAPOL01")
        cls.live = create_test_policy(product, insuree, link=False)
        cls.deleted = create_test_policy(product, insuree, link=False, valid=False)
        cls.copy = create_test_policy(
            product, insuree, link=False, valid=False,
            custom_props={"legacy_id": cls.live.id})
        cls.admin = create_test_interactive_user(username="polRowArgsAdmin")
        cls.token = get_token(cls.admin, DummyContext(user=cls.admin))

    def _uuids(self, args=""):
        response = self.query(
            '{ policies(product_Code: "PRAPOL01"%s) { edges { node { uuid } } } }' % args,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.token}"})
        self.assertResponseNoErrors(response)
        edges = json.loads(response.content)["data"]["policies"]["edges"]
        return {e["node"]["uuid"] for e in edges}

    def _set(self, *policies):
        return {p.uuid for p in policies}

    def test_default_hides_deleted_policies(self):
        self.assertEqual(self._set(self.live), self._uuids())

    def test_show_history_keeps_its_legacy_meaning(self):
        # legacy: no validity filter at all, deleted policies and history copies included
        self.assertEqual(self._set(self.live, self.deleted, self.copy),
                         self._uuids(", showHistory: true"))
        self.assertEqual(self._set(self.live), self._uuids(", showHistory: false"))

    def test_is_deleted(self):
        self.assertEqual(self._set(self.deleted), self._uuids(", isDeleted: true"))
        self.assertEqual(self._set(self.live), self._uuids(", isDeleted: false"))

    def test_is_deleted_overrides_show_history(self):
        self.assertEqual(self._set(self.live, self.copy),
                         self._uuids(", showHistory: true, isDeleted: false"))

    def test_type_default_still_hides_deleted(self):
        """PolicyGQLType is used by other modules: with no rows asked, live only."""
        from policy.gql_queries import PolicyGQLType
        ids = set(PolicyGQLType.get_queryset(
            Policy.objects.filter(product__code="PRAPOL01"), self.admin
        ).values_list("id", flat=True))
        self.assertEqual({self.live.id}, ids)
