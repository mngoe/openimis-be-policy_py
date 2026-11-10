"""
Security parity tests for policy (row scope + API rights) against the openimis-dev-tools
reference (release/26.10). Each test asserts the REFERENCE behaviour: a failure is a gap
in the Cameroon code.

Tags: [REF <reference file>::<test>] ported, [NEW] no reference equivalent.

Fixture: core.test_helpers.create_security_tree -> R1>D1>W1>V1 / R2>D2>W2>V2.
`user_a` holds the policy rights in the GLOBAL bag (no UBA) and is assigned district D1 only.
"""
import json

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.test import TestCase, override_settings
from django.utils.translation import gettext as _

from claim.apps import ClaimConfig
from core.models.openimis_graphql_test_case import openIMISGraphQLTestCase
from core.test_helpers import (
    create_security_tree, create_right_only_user, get_test_token, perm_ids, create_test_officer,
)
from insuree.test_helpers import create_test_insuree
from policy.apps import PolicyConfig
from policy.models import Policy
from policy.test_helpers import create_test_policy


def _u(*lists):
    """de-duplicated right ids (a role cannot hold the same right twice)"""
    return list(dict.fromkeys(r for lst in lists for r in lst))


def _product(code):
    """product.test_helpers imports program.test_helpers, absent on Cameroon's program dev-csu."""
    from program.models import Program
    from product.models import Product
    program = Program.objects.create(code=code[:10], nameProgram=f"Program {code}")
    return Product.objects.create(
        code=code, name=f"Test product {code}", lump_sum=123.45, max_members=5,
        grace_period_enrolment=1, insurance_period=12, date_from="2019-01-01", date_to="2049-01-01",
        validity_from="2019-01-01", audit_user_id=-1, program=program)


def _unauthorized(call):
    """Refused *because of rights* (PermissionDenied or an 'unauthorized' error payload)."""
    try:
        result = call()
    except PermissionDenied:
        return True
    text = json.dumps(result or [], default=str).lower()
    return "unauthorized" in text or _("unauthorized").lower() in text


QUERY_RIGHTS = _u(perm_ids(PolicyConfig.gql_query_policies_perms),
                  perm_ids(PolicyConfig.gql_query_policies_by_insuree_perms),
                  perm_ids(PolicyConfig.gql_query_policies_by_family_perms))
WRITE_RIGHTS = _u(perm_ids(PolicyConfig.gql_mutation_create_policies_perms),
                  perm_ids(PolicyConfig.gql_mutation_edit_policies_perms),
                  perm_ids(PolicyConfig.gql_mutation_renew_policies_perms),
                  perm_ids(PolicyConfig.gql_mutation_suspend_policies_perms),
                  perm_ids(PolicyConfig.gql_mutation_delete_policies_perms))


def _build(tree, prefix):
    product = _product(f"{prefix}PR")
    out = {}
    for key, village in (("a", tree.v1), ("b", tree.v2)):
        insuree = create_test_insuree(
            with_family=True, is_head=True,
            custom_props={"chf_id": f"{prefix}0000{1 if key == 'a' else 2}", "current_village": village},
            family_custom_props={"location": village})
        policy = create_test_policy(product, insuree, link=True)
        out[key] = (insuree, policy)
    return product, out


@override_settings(ROW_SECURITY=True)
class PolicyReadScopeTest(openIMISGraphQLTestCase):
    """[REF policy/tests/test_policy_row_security.py] reads stay in the user's districts."""

    @classmethod
    def setUpTestData(cls):
        cls.t = create_security_tree("SPP")
        cls.product, built = _build(cls.t, "SPP")
        cls.ins_a, cls.pol_a = built["a"]
        cls.ins_b, cls.pol_b = built["b"]
        cls.user_a = create_right_only_user("sppread", QUERY_RIGHTS, [cls.t.d1.id])
        cls.token = get_test_token(cls.user_a)
        cls.claim_only = create_right_only_user(
            "sppclaim", perm_ids(ClaimConfig.gql_query_claims_perms), [cls.t.d1.id])
        cls.claim_token = get_test_token(cls.claim_only)
        cls.officer_b = create_test_officer(custom_props={"code": "SPPOFB"}, villages=[cls.t.v2])

    def setUp(self):
        cache.clear()

    def _q(self, query, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        resp = self.query(query, headers=headers)
        return json.loads(resp.content)

    def test_model_scope_excludes_other_district(self):
        """[REF test_policy_row_security.py::test_policies_keep_own_district] (model level)"""
        ids = set(Policy.get_queryset(
            Policy.objects.filter(id__in=[self.pol_a.id, self.pol_b.id]), self.user_a
        ).values_list("id", flat=True))
        self.assertEqual({self.pol_a.id}, ids)

    def test_gql_policies_scoped(self):
        """[REF test_policy_row_security.py::test_policies_keep_own_district]"""
        content = self._q('{ policies { edges { node { uuid } } } }', self.token)
        self.assertNotIn("errors", content, content.get("errors"))
        uuids = {e["node"]["uuid"].upper() for e in content["data"]["policies"]["edges"]}
        self.assertIn(str(self.pol_a.uuid).upper(), uuids)
        self.assertNotIn(str(self.pol_b.uuid).upper(), uuids)

    def test_gql_policies_by_family_foreign_family_refused(self):
        """[REF test_policy_row_security.py::test_policies_by_family_keep_own_district]
        a user holding the right globally must not list the policies of a district-2 family
        (Cameroon `_check_in_scope` returns early for a global-bag user, schema.py:52)."""
        content = self._q(
            f'{{ policiesByFamily(familyUuid: "{self.ins_b.family.uuid}") {{ edges {{ node {{ policyUuid }} }} }} }}',
            self.token)
        edges = ((content.get("data") or {}).get("policiesByFamily") or {}).get("edges") or []
        self.assertEqual([], edges, "district-2 family policies listed")

    def test_gql_policies_by_insuree_is_open_to_the_read_right(self):
        """[DECISION 2026-11-10, differs from the reference] the lookup by CHF ID is open,
        unscoped, to a holder of the normal read right: a district-1 user sees the policies
        of a district-2 insuree."""
        content = self._q(
            f'{{ policiesByInsuree(chfId: "{self.ins_b.chf_id}") {{ edges {{ node {{ policyUuid }} }} }} }}',
            self.token)
        self.assertNotIn("errors", content)
        edges = ((content.get("data") or {}).get("policiesByInsuree") or {}).get("edges") or []
        self.assertTrue(edges, "district-2 insuree policies not listed")

    def test_gql_policies_by_insuree_claim_right_does_not_unlock(self):
        """[REF policy/tests/test_enquiry_right.py] the claim query right alone does not open
        the by-insuree listing of an insuree outside the user's districts
        (Cameroon: schema.py:239-242 skips the scope for claim-right holders)."""
        content = self._q(
            f'{{ policiesByInsuree(chfId: "{self.ins_b.chf_id}") {{ edges {{ node {{ policyUuid }} }} }} }}',
            self.claim_token)
        edges = ((content.get("data") or {}).get("policiesByInsuree") or {}).get("edges") or []
        self.assertEqual([], edges, "claim right alone lists district-2 policies")

    def test_gql_policy_number_validity_requires_auth(self):
        """[NEW] `policyNumberValidity` must not answer anonymous callers (schema.py:370)."""
        content = self._q('{ policyNumberValidity(policyNumber: "SPP-1") }')
        self.assertTrue(content.get("errors") or (content.get("data") or {}).get("policyNumberValidity") is None,
                        content)

    def test_policy_officers_refuses_anonymous(self):
        """[DECISION 2026-11-10] no dedicated officers right (covered by UBA / location
        scope), but anonymous callers are refused."""
        content = self._q('{ policyOfficers(search: "SPPOF") { edges { node { code } } } }')
        edges = ((content.get("data") or {}).get("policyOfficers") or {}).get("edges") or []
        self.assertTrue(content.get("errors") or not edges, content)

    def test_gql_policy_officers_scoped(self):
        """[NEW] `policyOfficers` does not list officers of district 2 to a district-1 user."""
        content = self._q('{ policyOfficers(search: "SPPOF") { edges { node { code } } } }', self.token)
        edges = ((content.get("data") or {}).get("policyOfficers") or {}).get("edges") or []
        self.assertNotIn("SPPOFB", [e["node"]["code"] for e in edges])

    def test_gql_policies_without_right_denied(self):
        """[REF policy/tests/test_rights_policies.py] no right -> error."""
        content = self._q('{ policies { edges { node { uuid } } } }', self.claim_token)
        self.assertIn("errors", content)


@override_settings(ROW_SECURITY=True)
class PolicyWriteScopeTest(TestCase):
    """[REF policy/services.py / gql_mutations.py target lookups through the row scope]
    writes on a district-2 policy are refused for a district-1 user holding the rights
    globally. NB the reference itself still has unscoped policy update/suspend/delete
    targets (policy/services.py:96, gql_mutations.py:170) - those tests are [NEW]."""

    @classmethod
    def setUpTestData(cls):
        cls.t = create_security_tree("SPQ")
        cls.product, built = _build(cls.t, "SPQ")
        cls.ins_a, cls.pol_a = built["a"]
        cls.ins_b, cls.pol_b = built["b"]
        cls.user_a = create_right_only_user("spqwrite", _u(QUERY_RIGHTS, WRITE_RIGHTS), [cls.t.d1.id])
        cls.officer = create_test_officer(custom_props={"code": "SPQOF"}, villages=[cls.t.v1])

    def setUp(self):
        cache.clear()

    def _payload(self, policy, family):
        return dict(uuid=str(policy.uuid), enroll_date=policy.enroll_date, start_date=policy.start_date,
                    expiry_date=policy.expiry_date, value=policy.value or 10, product_id=self.product.id,
                    family_id=family.id, officer_id=self.officer.id)

    def test_update_foreign_policy_refused(self):
        """[NEW] UpdatePolicy on a district-2 policy is refused for rights."""
        from policy.gql_mutations import UpdatePolicyMutation
        self.assertTrue(_unauthorized(lambda: UpdatePolicyMutation.async_mutate(
            self.user_a, **self._payload(self.pol_b, self.ins_b.family))))

    def test_create_policy_on_foreign_family_refused(self):
        """[NEW] CreatePolicy for a district-2 family is refused."""
        from policy.gql_mutations import CreatePolicyMutation
        data = self._payload(self.pol_b, self.ins_b.family)
        data.pop("uuid")
        self.assertTrue(_unauthorized(lambda: CreatePolicyMutation.async_mutate(self.user_a, **data)))

    def test_renew_policy_on_foreign_family_refused(self):
        """[NEW] RenewPolicy for a district-2 family is refused."""
        from policy.gql_mutations import RenewPolicyMutation
        data = self._payload(self.pol_b, self.ins_b.family)
        data.pop("uuid")
        self.assertTrue(_unauthorized(lambda: RenewPolicyMutation.async_mutate(self.user_a, **data)))

    def test_suspend_foreign_policy_refused(self):
        """[NEW] SuspendPolicies on a district-2 policy leaves it untouched."""
        from policy.gql_mutations import SuspendPoliciesMutation
        status = Policy.objects.get(id=self.pol_b.id).status
        SuspendPoliciesMutation.async_mutate(self.user_a, uuids=[str(self.pol_b.uuid)])
        self.assertEqual(status, Policy.objects.get(id=self.pol_b.id).status, "district-2 policy suspended")

    def test_delete_foreign_policy_refused(self):
        """[NEW] DeletePolicies on a district-2 policy leaves it valid."""
        from policy.gql_mutations import DeletePoliciesMutation
        DeletePoliciesMutation.async_mutate(self.user_a, uuids=[str(self.pol_b.uuid)])
        self.assertIsNone(Policy.objects.get(id=self.pol_b.id).validity_to, "district-2 policy deleted")

    def test_delete_own_policy_allowed(self):
        """[control] the same delete on a district-1 policy works."""
        from policy.gql_mutations import DeletePoliciesMutation
        DeletePoliciesMutation.async_mutate(self.user_a, uuids=[str(self.pol_a.uuid)])
        self.assertIsNotNone(Policy.objects.get(id=self.pol_a.id).validity_to)

    def test_delete_without_right_refused(self):
        """[REF policy/tests/test_right_names.py] no delete right -> refused."""
        from policy.gql_mutations import DeletePoliciesMutation
        reader = create_right_only_user("spqreader", QUERY_RIGHTS, [self.t.d1.id])
        self.assertTrue(_unauthorized(lambda: DeletePoliciesMutation.async_mutate(
            reader, uuids=[str(self.pol_a.uuid)])))
        self.assertIsNone(Policy.objects.get(id=self.pol_a.id).validity_to)
