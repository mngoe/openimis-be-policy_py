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
    "ACTIVATION_OPTION_CONTRIBUTION": 1,
    "CTIVATION_OPTION_PAYMENT": 2,
    "ACTIVATION_OPTION_READY": 3,
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
    policy_renewal_interval = None
    policy_location_via = None
    default_eligibility_disabled = None
    ACTIVATION_OPTION_CONTRIBUTION = None
    ACTIVATION_OPTION_PAYMENT = None
    ACTIVATION_OPTION_READY = None
    activation_option = None

    def __load_config(self, cfg):
        for field in cfg:
            if hasattr(PolicyConfig, field):
                setattr(PolicyConfig, field, cfg[field])

    def ready(self):
        from core.models import ModuleConfiguration
        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self.__load_config(cfg)
