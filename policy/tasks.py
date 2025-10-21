import logging
import time

from policy.services import insert_renewals, update_renewals, policy_renewal_sms

logger = logging.getLogger(__name__)


def get_policies_for_renewal(interval=None, region=None, district=None, ward=None, village=None, officer=None,
                             date_from=None, date_to=None, family_message_template=None, sms_header_template=None):
    """
    Find policies that are due for renewal, add them to the renewal queue, mark the expired policies as expired
    All parameters are optional.
    This method is more a sample than the actual code since it should be heavily customized

    :param interval: number of days before expiration to send renewal
    :param region: region id for which to send the renewals
    :param district: district for which to send the renewals
    :param ward: ward for which to send the renewals
    :param village: village for which to send the renewals
    :param officer: limit renewals to a specific officer
    :param date_from: date range to send renewals
    :param date_to: date range to send renewals
    :param family_message_template: family message template. This a Django template that provides: renewal object,
            district_name, ward_name, village_name, ...
    :param sms_header_template: Also a Django template for the SMS header
    :return: nothing
    """
    start = time.time()
    logger.debug("debut du cron!!!!!")
    logger.info("debut du cron!!!!!")
    print("debut du cron!!!!!")
    for item in [region, district, ward, village]:
        if item:
            location = item
            break
    else:
        location = None
    insert_renewals(date_from, date_to, officer_id=officer, reminding_interval=interval, location_id=location)
    update_renewals()
    sms_queue = policy_renewal_sms(family_message_template, date_from, date_to, sms_header_template)
    for sms in sms_queue:
        send_sms(sms)
    elapsed = time.time() - start
    logger.debug(" FIN DU CRON  Durée totale : %.2f secondes", elapsed)
    logger.info(" FIN DU CRON  Durée totale : %.2f secondes", elapsed)
    print(f" FIN DU CRON  Durée totale : {elapsed} secondes")


def send_sms(sms):
    """
    This method is quite specific to the SMS provider. It would be a good idea to adapt the above task to suit
    the needs of the gateway, its processing status etc.
    :param sms: sms queue item, contains phone, sms_message, index
    """
    logger.warning("Sending an SMS needs a defined gateway, pretending to send to %s:\n%s", sms.phone, sms.sms_message)
