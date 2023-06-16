from django.utils.translation import gettext as _
from .models import Policy
from insuree.models import Insuree
from product.models import Product
from program import models as program_models


def validate_idle_policy(policy_input):
    errors = []
    product_id = policy_input.get('product_id', False)
    program_id = Product.objects.get(id=product_id).program_id
    canSave = False
    if program_id:
        nameProgram = program_models.Program.objects.get(idProgram=program_id).nameProgram
        if nameProgram=='VIH':
            family = policy_input.get('family_id', False)
            if family:
                members = Insuree.objects.filter(family_id=family)
                for member in members:
                    if member.email == 'newhivuser_XM7dw70J0M3N@gmail.com':
                        canSave = True
                        break
    if not canSave:
        return [{
                'message': ("failed to create policy"),
                'detail': ("Cannot create an HIV policy for a patient that does not have HIV (%s)") % (member.chf_id)
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
