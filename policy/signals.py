from core.signals import Signal

_check_formal_sector_for_policy_signal_params = ["user", "policy_id"]
signal_check_formal_sector_for_policy = Signal(providing_args=_check_formal_sector_for_policy_signal_params)
