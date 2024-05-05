from .apps import PolicyConfig
from core.signals import Signal
from core.service_signals import ServiceSignalBindType
from core.signals import bind_service_signal
from insuree.models import Family

_check_formal_sector_for_policy_signal_params = ["user", "policy_id"]
signal_check_formal_sector_for_policy = Signal(_check_formal_sector_for_policy_signal_params)

def bind_service_signals():
    bind_service_signal(
        'policy_service.create_or_update', _on_add_policy, ServiceSignalBindType.BEFORE)

def _on_add_policy(*args, **kwargs):
    data = kwargs.get('data', None)
    if data:
        if PolicyConfig.comores_features_enabled:
            if "family_id" in data[0][0]:
                family = Family.objects.filter(id=data[0][0]["family_id"]).first()
                if family:
                    if family.family_level == "1":
                        raise Exception("Impossible d'attribuer une police à une famille de niveau 1")
