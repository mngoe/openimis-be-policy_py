from django.apps import AppConfig
from django.conf import settings

MODULE_NAME = "policy"

DEFAULT_CFG = {
    "gql_query_policies_perms": ['101201'],
    "gql_query_policy_officers_perms": [],
    "gql_query_policies_by_insuree_perms": ['101201'],
    "gql_query_policies_by_family_perms": ['101201'],
    "gql_query_eligibilities_perms": ['101201'],
    "gql_mutation_create_policies_perms": ['101202'],
    "gql_mutation_renew_policies_perms": ['101205'],
    "gql_mutation_edit_policies_perms": ['101203'],
    "gql_mutation_suspend_policies_perms": ['101203'],
    "gql_mutation_delete_policies_perms": ['101204'],
    "policy_renewal_interval": 14,  # Notify renewal nb of days before expiry date
    "policy_location_via": "family",  # ... or product
    "default_eligibility_disabled": False,
    "activation_option": 1,
    "max_insuree_score": 100,
}


class PolicyConfig(AppConfig):
    name = MODULE_NAME

    gql_query_policies_perms = []
    gql_query_policy_officers_perms = []
    gql_query_policies_by_insuree_perms = []
    gql_query_policies_by_family_perms = []
    gql_query_eligibilities_perms = []
    gql_mutation_create_policies_perms = []
    gql_mutation_renew_policies_perms = []
    gql_mutation_edit_policies_perms = []
    gql_mutation_suspend_policies_perms = []
    gql_mutation_delete_policies_perms = []
    policy_renewal_interval = 14
    policy_location_via = 'family'
    default_eligibility_disabled = False
    ACTIVATION_OPTION_CONTRIBUTION = 1
    ACTIVATION_OPTION_PAYMENT = 2
    ACTIVATION_OPTION_READY = 3
    activation_option = ACTIVATION_OPTION_CONTRIBUTION
    max_insuree_score = 100

    def _configure_permissions(self, cfg):
        PolicyConfig.gql_query_policies_perms = cfg["gql_query_policies_perms"]
        PolicyConfig.gql_query_policy_officers_perms = cfg["gql_query_policy_officers_perms"]
        PolicyConfig.gql_query_policies_by_insuree_perms = cfg["gql_query_policies_by_insuree_perms"]
        PolicyConfig.gql_query_policies_by_family_perms = cfg["gql_query_policies_by_family_perms"]
        PolicyConfig.gql_mutation_create_policies_perms = cfg["gql_mutation_create_policies_perms"]
        PolicyConfig.gql_mutation_renew_policies_perms = cfg["gql_mutation_renew_policies_perms"]
        PolicyConfig.gql_mutation_edit_policies_perms = cfg["gql_mutation_edit_policies_perms"]
        PolicyConfig.gql_mutation_suspend_policies_perms = cfg["gql_mutation_suspend_policies_perms"]
        PolicyConfig.gql_mutation_delete_policies_perms = cfg["gql_mutation_delete_policies_perms"]
        PolicyConfig.gql_query_eligibilities_perms = cfg["gql_query_eligibilities_perms"]

    def _configure_eligibility(self, cfg):
        PolicyConfig.default_eligibility_disabled = cfg["default_eligibility_disabled"]

    def _configure_renewal(self, cfg):
        PolicyConfig.policy_renewal_interval = cfg["policy_renewal_interval"]

    def _configure_location(self, cfg):
        PolicyConfig.policy_location_via = cfg["policy_location_via"]

    def _configure_insuree_maximum_score(self, cfg):
        PolicyConfig.max_insuree_score = cfg["max_insuree_score"]

    def _configure_activation(self, cfg):
        PolicyConfig.activation_option = cfg["activation_option"]

    def ready(self):
        from core.models import ModuleConfiguration
        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self._configure_permissions(cfg)
        self._configure_renewal(cfg)
        self._configure_location(cfg)
        self._configure_eligibility(cfg)
        self._configure_activation(cfg)
        self._configure_insuree_maximum_score(cfg)
