import uuid
import sys
from core import fields
from core import models as core_models
from core.utils import filter_validity
from core.models import Officer
from core.apps import ENROLMENT_UBA_LINK_TYPE
from django.core.cache import caches
cache = caches['coverage']

from django.conf import settings
from django.db import models
from django.apps import apps
from graphql import ResolveInfo
from insuree.models import Family, InsureePolicy
from product.models import Product
from django.utils import timezone as django_tz 
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from location.models import LocationManager


class Policy(core_models.VersionedModel):
    id = models.AutoField(db_column='PolicyID', primary_key=True)
    uuid = models.CharField(db_column='PolicyUUID', max_length=36, default=uuid.uuid4, unique=True)

    stage = models.CharField(db_column='PolicyStage', max_length=1, blank=True, null=True)
    status = models.SmallIntegerField(db_column='PolicyStatus', blank=True, null=True)
    value = models.DecimalField(db_column='PolicyValue', max_digits=18, decimal_places=2, blank=True, null=True)

    family = models.ForeignKey(Family, models.DO_NOTHING, db_column='FamilyID', related_name="policies")
    enroll_date = fields.DateField(db_column='EnrollDate')
    start_date = fields.DateField(db_column='StartDate')
    effective_date = fields.DateField(db_column='EffectiveDate', blank=True, null=True)
    expiry_date = fields.DateField(db_column='ExpiryDate', blank=True, null=True)

    product = models.ForeignKey(Product, models.DO_NOTHING, db_column='ProdID', related_name="policies")
    officer = models.ForeignKey(Officer, models.DO_NOTHING, db_column='OfficerID', blank=True, null=True,
                                related_name="policies")

    offline = models.BooleanField(db_column='isOffline', blank=True, null=True)
    audit_user_id = models.IntegerField(db_column='AuditUserID')
    # row_id = models.BinaryField(db_column='RowID', blank=True, null=True)
    policy_number = models.CharField(db_column='policyNumber', max_length=50, blank=True, null=True)
    creation_date = models.DateField(db_column='creationDate', default=django_tz.now, blank=True, null=True)
    pregnancy_age = models.PositiveSmallIntegerField(db_column='PregnancyAge', blank=True, null=True)

    @staticmethod
    def get_query_sum_premium(photo=False):
        return models.Sum(
            'premiums__amount', 
            filter=models.Q(*filter_validity(prefix='premiums__'),premiums__is_photo_fee=photo)
            )
    
    def sum_premiums(self, photo = False):
        return Policy.objects.filter(id=self.id).aggregate(
                sum_premiums=Policy.get_query_sum_premium(photo)
                )['sum_premiums'] or 0

    def claim_ded_rems(self):
        return self.claim_ded_rems

    def is_new(self):
        return not self.stage or self.stage == Policy.STAGE_NEW

    def can_add_insuree(self):
        return self.family.members.filter(validity_to__isnull=True).count() < self.product.max_members
    class Meta:
        managed = True
        db_table = 'tblPolicy'

    STATUS_IDLE = 1
    STATUS_ACTIVE = 2
    STATUS_SUSPENDED = 4
    STATUS_EXPIRED = 8
    STATUS_READY = 16

    STAGE_NEW = 'N'
    STAGE_RENEWED = 'R'

    @classmethod
    def get_queryset(cls, queryset, user):
        queryset = Policy.filter_queryset(queryset)
        # GraphQL calls with an info object while Rest calls with the user itself
        if isinstance(user, ResolveInfo):
            user = user.context.user
        if settings.ROW_SECURITY and user.is_anonymous:
            return queryset.filter(id=-1)
        if settings.ROW_SECURITY:
            # The "how do we reach the location of a policy ?" the TODO above asked about:
            # through the family it covers, whose own location is a village. That is also
            # the path the ENROLMENT narrowing takes, `build_user_location_filter_query`
            # walking it down to the village the credential is held on.
            queryset = LocationManager().build_user_location_filter_query(
                user._u, prefix='family__location__parent__parent',
                queryset=queryset, loc_types=['D'],
                link_types=ENROLMENT_UBA_LINK_TYPE)
        return queryset


class PolicyRenewal(core_models.VersionedModel):
    id = models.AutoField(db_column='RenewalID', primary_key=True)
    uuid = models.CharField(db_column='RenewalUUID', max_length=36, default=uuid.uuid4, unique=True)

    new_officer = models.ForeignKey(Officer, models.DO_NOTHING, db_column='NewOfficerID',
                                    blank=True, null=True, related_name="policy_renewals")
    insuree = models.ForeignKey('insuree.Insuree', models.DO_NOTHING, db_column='InsureeID',
                                related_name='policy_renewals')
    policy = models.ForeignKey('policy.Policy', models.DO_NOTHING, db_column='PolicyID',
                               related_name='policy_renewals')
    new_product = models.ForeignKey(Product, db_column='NewProdID', on_delete=models.DO_NOTHING,
                                       related_name="policy_renewals")

    renewal_prompt_date = fields.DateField(db_column='RenewalPromptDate')
    renewal_date = fields.DateField(db_column='RenewalDate')
    phone_number = models.CharField(db_column='PhoneNumber', max_length=25, blank=True, null=True)
    sms_status = models.SmallIntegerField(db_column='SMSStatus', default=0)  # TODO choices
    renewal_warnings = models.SmallIntegerField(db_column='RenewalWarnings', null=True, blank=True, default=0)  # TODO choices
    response_status = models.IntegerField(db_column='ResponseStatus', null=True, blank=True, default=0)  # TODO Choices
    response_date = fields.DateTimeField(db_column='ResponseDate', null=True, blank=True)

    audit_user_id = models.IntegerField(db_column='AuditCreateUser', null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['policy', 'validity_to'],
                name='unique_policy_validity_to_null',
                condition=models.Q(validity_to__isnull=True)
            )
        ]
        managed = True
        db_table = 'tblPolicyRenewals'


class PolicyMutation(core_models.UUIDModel, core_models.ObjectMutation):
    policy = models.ForeignKey(Policy, models.DO_NOTHING,
                                 related_name='mutations')
    mutation = models.ForeignKey(
        core_models.MutationLog, models.DO_NOTHING, related_name='policies')

    class Meta:
        managed = True
        db_table = "policy_PolicyMutation"

class PolicyRenewalMutation(core_models.UUIDModel, core_models.ObjectMutation):
    policy_renewal = models.ForeignKey(PolicyRenewal, models.DO_NOTHING,
                                 related_name='mutations')
    mutation = models.ForeignKey(
        core_models.MutationLog, models.DO_NOTHING, related_name='policy_renewals')

    class Meta:
        managed = True
        db_table = "policy_renewal_PolicyMutation"

ELIGIBILITY_GENERATION_KEY = "eligibility_generation"


def eligibility_cache_key(owner_id):
    """
    The eligibility cache entry of a family (or of an insuree without one). The key
    carries a generation so that every entry can be dropped at once by bumping it,
    without clearing the cache: the cache aliases share their store.
    """
    generation = cache.get(ELIGIBILITY_GENERATION_KEY, 0)
    return f"eligibility_{generation}_{owner_id}"


def invalidate_all_eligibility_cache():
    try:
        cache.incr(ELIGIBILITY_GENERATION_KEY)
    except ValueError:
        # incr fails on a missing key
        cache.set(ELIGIBILITY_GENERATION_KEY, 1, None)
    if hasattr(cache, "delete_pattern"):
        # django-redis: also free the entries of the previous generations
        cache.delete_pattern("eligibility_*_*")


if "claim" in sys.modules:
    from claim.models import Claim

    @receiver(post_save, sender=Claim)
    @receiver(post_delete, sender=Claim)
    def clean_enquire_cache_claim(sender, instance, *args, **kwargs):
        cache.delete(eligibility_cache_key(instance.insuree.family_id or instance.insuree.id))

@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def clean_all_enquire_cache_product(sender, instance, *args, **kwargs):
    invalidate_all_eligibility_cache()


@receiver(post_save, sender=Policy)
@receiver(post_delete, sender=Policy)
def clean_all_enquire_cache_policy(sender, instance, *args, **kwargs):
    cache.delete(eligibility_cache_key(instance.family_id))


@receiver(post_save, sender=InsureePolicy)
@receiver(post_delete, sender=InsureePolicy)
def clean_enquire_cache_insuree_policy(sender, instance, *args, **kwargs):
    cache.delete(eligibility_cache_key(instance.insuree.family_id or instance.insuree_id))


@receiver(post_save, sender=Family)
@receiver(post_delete, sender=Family)
def clean_all_enquire_cache_family(sender, instance, *args, **kwargs):
    cache.delete(eligibility_cache_key(instance.id))
