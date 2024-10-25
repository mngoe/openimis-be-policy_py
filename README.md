# openIMIS Backend Policy reference module
This repository holds the files of the openIMIS Backend Policy reference module. It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Code climate (develop branch)

[![Maintainability](https://img.shields.io/codeclimate/maintainability/openimis/openimis-be-policy_py.svg)](https://codeclimate.com/github/openimis/openimis-be-policy_py/maintainability)
[![Test Coverage](https://img.shields.io/codeclimate/coverage/openimis/openimis-be-policy_py.svg)](https://codeclimate.com/github/openimis/openimis-be-policy_py)

## ORM mapping:
* tblPolicy > Policy
* tblPolicyRenewal > PolicyRenewal

## Listened Django Signals
* `signal_mutation_module_validate["policy"]`: handles PolicyMutations (create, update, renew, suspend and delete)

## Services
* ByFamilyService - retrieves policies of a family
* ByInsureeService - retrieves policies of an insuree
* FilteredPoliciesService - generic policy fetch service (used by ByFamilyService and ByInsureeService services)
* EligibilityService - can be disabled in config and exposes signals

## Reports (template can be overloaded via report.ReportDefinition)
None

## GraphQL Queries
* policy_values: gql to compute policy values (start/end date and value), based on family (composition), enrollment date and product
* policies: gql binding to PolicyGQLType
* policies_by_family: gql binding to ByFamilyService
* policies_by_insuree: gql binding to ByInsureeService
* policy_eligibility_by_insuree: gql binding to EligibilityService, with insuree criteria
* policy_item_eligibility_by_insuree: gql binding to EligibilityService, with insuree and item  criteria
* policy_service_eligibility_by_insuree: gql binding to EligibilityService, with insuree and service criteria
* policy_officers: gql binding to OfficerGQLType

## GraphQL Mutations - each mutation emits default signals and return standard error lists (cfr. openimis-be-core_py)
* create_policy
* update_policy
* delete_policies
* renew_policy
* suspend_policies

## Configuration options (can be changed via core.ModuleConfiguration)
* gql_query_policies_perms: required rights to query policies (default `['101201']`)
* gql_query_policy_officers_perms": required rights to query policy officers (`[]` i.e. none, as in 'open to everybody'),
* gql_query_policies_by_family_perms: required rights to call policies_by_family gql (default `['101201']`)
* gql_query_policies_by_insuree_perms: required rights to call policies_by_insuree gql (default `['101201']`)
* gql_mutation_create_policies_perms": required rights to perform 'create' mutation (default `['101202']`),
* gql_mutation_renew_policies_perms": required rights to perform 'renew' mutation (default `['101205']`),
* gql_mutation_edit_policies_perms": required rights to perform 'update' mutation (default `['101203']`),
* gql_mutation_suspend_policies_perms": required rights to perform 'suspend' mutation (default `['101203']`),
* gql_mutation_delete_policies_perms": required rights to perform 'delete' mutation (default `['101204']`),
* gql_query_eligibilities_perms: required rights to call policy_eligibility_by_insuree, policy_item_eligibility_by_insureegql, policy_service_eligibility_by_insuree (default `['101201']`)
* default_eligibility_disabled: disable the stock eligibility service and rely only on signals (default: `False`)
* policy_renewal_interval: Notify renewal nb of days before expiry date, default: `14`
* policy_location_via: Filter policies on user's location path. Default: via `family` location (otherwize via product)
* enable_polygamic_family: Define if the polygamic family implemetation should be enabled or not default: `False`.

## openIMIS Modules Dependencies
* claim.models.ClaimOfficer
* insuree.models.Family
* product.models.Product
