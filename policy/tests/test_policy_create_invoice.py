# Create your tests here.
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.contrib.contenttypes.models import ContentType
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from product.test_helpers import create_test_product
import uuid
from contribution_plan.models import ContributionPlan
from policyholder.models import PolicyHolder
from policy.services import PolicyService
from product.models import Product
from core.test_helpers import create_test_interactive_user
from insuree.test_helpers import create_test_family, create_test_insuree
class TestPolicyInvoice(TestCase):
    def setUp(self):
        self.family = create_test_family()
        self.product = create_test_product(code="TST-HPD1")
        self.user = create_test_interactive_user()
        self.service = PolicyService(self.user)
        print("created user ", self.user)
        print("created user ID", self.user.id)
    @patch("policy.services.update_insuree_policies")
    @patch("invoice.services.invoice.InvoiceService.create")
    def test_create_policy_should_activate_free_policy(
        self,
        mock_create,
        mock_update_insuree_policies
    ):
        mock_create.return_value = {
            "success": False
        }
        data = {
            "family": self.family,
            "product": self.product,
            "audit_user_id": 1,
            "value": 0,
            "start_date": date(2025, 1, 1),
            "enroll_date": date(2025, 1, 1),
        }
        policy = self.service.create_policy(data, self.user)
        self.assertEqual(policy.status, 2)
        self.assertEqual(policy.effective_date, date(2025, 1, 1))
    @patch(
        "contribution.services.check_unique_premium_receipt_code_within_product"
    )
    def test_create_policy_should_fail_when_receipt_already_exists(
        self,
        mock_check,
    ):
        mock_check.return_value = True
        with self.assertRaises(ValidationError):
            self.service.create_policy(
                {
                    "family": self.family,
                    "product": self.product,
                    "receipt": "RCPT001",
                    "audit_user_id": 1,
                    "value": 0,
                    "start_date": date(2025, 1, 1),
                    "enroll_date": date(2025, 1, 1),
                },
                self.user,
            )
    @patch("policy.services.InvoiceLineItemService")
    @patch("policy.services.InvoiceService")
    @patch("policy.services.calculate_due_date")
    @patch("invoice.services.invoice.InvoiceService.create")
    def test_create_invoice_should_create_government_invoice(
        self,
        mock_create,
        mock_due_date,
        # mock_invoice,
        # mock_policy_holder,
        mock_invoice_service,
        mock_invoice_line_service,
    ):
        mock_create.return_value = {
            "success": False
        }
        mock_due_date.return_value = date(2025, 1, 5)
        head = create_test_insuree()
        family = create_test_family()
        family.head_insuree = head
        family.save()
        calculation = str(uuid.uuid4())
        benefit_plan_type = ContentType.objects.get_for_model(Product)
        contribution_plan = ContributionPlan(
            code="AMS",
            name="AMS Subvention totale",
            calculation=calculation,
            date_valid_from=date(2020, 1, 1),
            benefit_plan_type=benefit_plan_type,
            benefit_plan_id=self.product.id,
            periodicity=1
        )
        contribution_plan.save(username=self.user.username)
        policy_holder = PolicyHolder(
            code="AFD",
            trade_name="Agengence Francaise pour le dévelopement"
        )
        policy_holder.save(username=self.user.username)
        data = {
            "family": self.family,
            "product": self.product,
            "audit_user_id": 1,
            "value": 0,
            "start_date": date(2025, 1, 1),
            "enroll_date": date(2025, 1, 1),
        }
        policy = self.service.create_policy(data, self.user)
        invoice_service = MagicMock()
        invoice_service.create.return_value = {
            "success": True,
            "data": {"id": 100},
        }
        mock_invoice_service.return_value = invoice_service
        line_service = MagicMock()
        mock_invoice_line_service.return_value = line_service
        calc_rule = MagicMock()
        calc_rule.signal_calculate_event.send.side_effect = [
            [(None, Decimal("1000"))],
            [(None, Decimal("0"))],
        ]
        print("Policy: ", policy)
        with patch(
            "policy.services.CALCULATION_RULES",
            [calc_rule]
        ):
            self.service.create_invoice(
                {
                    "family_id": family.id,
                    "contribution_plan_id": contribution_plan.uuid,
                    "periodicity": "M",
                    "payment_day": 5,
                },
                self.user,
                policy,
            )
        invoice_service.create.assert_called_once()
        line_service.create.assert_called_once()
