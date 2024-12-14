from policy.reports import policy_renewals
from policy.reports.policy_renewals import policy_renewals_query
from policy.reports import primary_operational_indicators
from policy.reports.primary_operational_indicators import policies_primary_indicators_query

report_definitions = [
    {
        "name": "policy_renewals",
        "engine": 0,
        "default_report": policy_renewals.template,
        "description": "Policy renewals",
        "module": "policy",
        "python_query": policy_renewals_query,
        "permission": ["131217"],
    },
    {
        "name": "policy_primary_operational_indicators",
        "engine": 0,
        "default_report": primary_operational_indicators.template,
        "description": "Policy primary operational indicators",
        "module": "policy",
        "python_query": policies_primary_indicators_query,
        "permission": ["131201"],
    },
]
