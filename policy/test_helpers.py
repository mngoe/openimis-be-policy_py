from contribution.models import Premium
from insuree.models import InsureePolicy, Family, Gender, Insuree
from insuree.test_helpers import create_test_insuree
from policy.models import Policy
from policy.values import policy_values
from product.models import Product
from contribution_plan.models import ContributionPlan
from core.utils import filter_validity
from core.test_helpers import create_test_interactive_user
from core.models import User
from django.core.exceptions import ObjectDoesNotExist
import datetime
import uuid
from product.test_helpers import create_test_product
from django.contrib.contenttypes.models import ContentType


def create_test_policy(product, insuree, link=True, valid=True, custom_props=None, check=False, contribution_plan=None):
    """
    Compatibility method that only return the Policy
    """
    return create_test_policy2(product, insuree, link, valid, custom_props, check, contribution_plan)[0]

def dts(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()

def create_test_policy2(product, insuree, link=True, valid=True, custom_props=None, check=False, contribution_plan=None):
    """
    Creates a Policy and optionally an InsureePolicy
    :param product: Product on which this Policy is based (or its ID)
    :param insuree: The Policy will be linked to this Insuree's family and if link is True, the InsureePolicy will
     belong to him
    :param link: if True (default), an InsureePolicy will also be created
    :param valid: Whether the created Policy should be valid (validity_to)
    :param custom_props: dictionary of custom values for the Policy, when overriding a foreign key, override the _id
    :return: The created Policy and InsureePolicy
    """
    product = create_test_product("TEST")
    try:
        user = User.objects.get(username='TestInteractiveTest')
    except ObjectDoesNotExist:
        user = create_test_interactive_user()
    benefit_plan_type = ContentType.objects.get_for_model(Product)
    if not contribution_plan:
        contribution_plan = ContributionPlan(
            code="AMS",
            name="AMS Subvention totale",
            calculation= str(uuid.uuid4()),
            date_valid_from=datetime.date(2020, 1, 1),
            benefit_plan_type=benefit_plan_type,
            benefit_plan_id=product.id,
            periodicity=1
        )
        contribution_plan.save(username=user.username)
    policy = Policy.objects.create(
        **{
            "family": insuree.family,
            "product_id": product.id if isinstance(product, Product) else product,
            "contribution_plan_id": contribution_plan.id if isinstance(contribution_plan, ContributionPlan) else contribution_plan,
            "status": Policy.STATUS_ACTIVE,
            "stage": Policy.STAGE_NEW,
            "enroll_date": dts("2019-01-01"),
            "start_date": dts("2019-01-02"),
            "validity_from": dts("2019-01-01"),
            "effective_date": dts("2019-01-01"),
            "expiry_date": dts("2039-06-01"),
            "validity_to": None if valid else dts("2019-01-01"),
            "audit_user_id": -1,
            **(custom_props if custom_props else {})
        }
    )
    if link:
        insuree_policy = InsureePolicy.objects.create(
            insuree=insuree,
            policy=policy,
            audit_user_id=-1,
            effective_date=dts("2019-01-01"),
            expiry_date=dts("2039-06-01"),
            validity_from=dts("2019-01-01"),
            validity_to=None if valid else dts("2019-01-01"),
        )
    else:
        insuree_policy = None

    # Was added for OMT-333 but breaks tests that explicitly call policy_values
    try:
        user = User.objects.get(username='Le-positif')
    except ObjectDoesNotExist:
        user = create_test_interactive_user(username='Le-positif', password="positif123")
    policy, warnings = policy_values(policy, insuree.family, None, user)
    if check and warnings:
        raise Exception("Policy has warnings: {}".format(warnings))
    return policy, insuree_policy


def create_test_policy_with_IPs(product, insuree, valid=True, policy_props=None, IP_props=None, premium_props=None):
    """
    Creates a Policy with its related InsureePolicys for each Family member.
    :param product: Product on which this Policy is based (or its ID)
    :param insuree: The Policy will be linked to this Insuree's family
    :param valid: Whether the created Policy should be valid (validity_to)
    :param policy_props: dictionary of custom values for the Policy, when overriding a foreign key, override the _id
    :param IP_props: dictionary of custom values for the InsureePolicy, when overriding a foreign key, override the _id
    :param premium_props: dictionary of custom values for the Premium, when overriding a foreign key, override the _id
    :return: The created Policy and InsureePolicy
    """
    value = 10000.00
    default_date = dts("2019-01-01")
    start_date = dts("2019-01-02")
    expiry_date = dts("2039-06-01")

    policy = Policy.objects.create(
        **{
            "family": insuree.family,
            "product_id": product.id if isinstance(product, Product) else product,
            "status": Policy.STATUS_ACTIVE,
            "stage": Policy.STAGE_NEW,
            "enroll_date": default_date,
            "start_date": start_date,
            "validity_from": default_date,
            "effective_date": default_date,
            "expiry_date": expiry_date,
            "value": value,
            "validity_to": None if valid else default_date,
            "audit_user_id": -1,
            **(policy_props if policy_props else {})
        }
    )

    for member in policy.family.members.filter(validity_to__isnull=True):
        InsureePolicy.objects.create(
            **{
                "insuree": member,
                "policy": policy,
                "audit_user_id": -1,
                "effective_date": default_date,
                "expiry_date": expiry_date,
                "start_date": start_date,
                "enrollment_date": default_date,
                "validity_from": default_date,
                "validity_to": None if valid else default_date,
                **(IP_props if IP_props else {})
            }
        )

    Premium.objects.create(
        **{
            "amount": value,
            "receipt": "TEST1234",
            "pay_date": default_date,
            "pay_type": "C",
            "validity_from": default_date,
            "policy_id": policy.id,
            "audit_user_id": -1,
            "validity_to": None if valid else default_date,
            "created_date": default_date,
            **(premium_props if premium_props else {})
        }
    )

    return policy


def create_test_insuree_for_policy(with_family=True, is_head=False, custom_props=None, family_custom_props=None):
    # To establish the mandatory reference between "Insuree" and "Family" objects, we can insert the "Family" object
    # with a temporary ID and later update it to associate with the respective "Insuree" object.
    insuree=  create_test_insuree(with_family=with_family, is_head=is_head, custom_props=custom_props, family_custom_props=family_custom_props)


    return insuree, insuree.family
