from django.utils.translation import gettext as _
from .models import Policy
from .apps import PolicyConfig
from insuree.models import Family


def validate_idle_policy(policy_input):
    errors = []
    family = policy_input.get('family_id', False)
    import os
    print("NO_DATABASE", bool(os.environ.get('NO_DATABASE')))
    if family:
        head_insuree = Family.objects.get(id=family).head_insuree
        if head_insuree.score:
            if head_insuree.score < PolicyConfig.max_insuree_score:
                return [{
                    'message': _("policy.mutation.failed_to_update_policy"),
                    'detail': ("Head insuree doesn't have the minimum\
                        score required to have a policy. The minimum score is %s") % PolicyConfig.max_insuree_score
                }]
    policy_uuid = policy_input.get('uuid')
    if policy_uuid:
        policy = Policy.objects.filter(uuid=policy_uuid, validity_to__isnull=True).first()
        if policy is None:
            return [{
                'message': _("policy.mutation.failed_to_update_policy"),
                'detail': _("policy.validation.id_does_not_exist") % {'id': policy_uuid}
            }]
        errors += check_can_update(policy)
    # TODO: check dates,...
    return errors


def check_can_update(policy):
    if policy.status != Policy.STATUS_IDLE:
        return [{
            'message': _("policy.mutation.failed_to_update_policy"),
            'detail': _("policy.mutation.policy_not_idle")
        }]
    return []
