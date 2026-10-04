import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from adapters.stores.mock_store import MockStore
from agents.llm import SYSTEM_PROMPT, draft_support_reply
from agents.tools import GuardedTools, GuardrailViolation
from core.db import Repository


class GuardedToolsTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()
        self.store = MockStore("store-1")
        self.tools = GuardedTools(self.repo, [self.store])

    def tearDown(self):
        self.repo.close()

    def test_price_changes_are_bounded_and_audited(self):
        price = self.tools.update_price(
            "store-1", "sku-1", 16, 2, cost=10, shipping_cost=1
        )
        self.assertEqual(price, 14.66)
        self.assertEqual(self.store.prices["sku-1"], 14.66)
        audit = self.repo.audit()
        self.assertEqual(audit[0]["action"], "price_updated")
        self.assertEqual(audit[0]["detail"]["final_price"], 14.66)

        capped = self.tools.update_price(
            "store-1", "sku-1", 16, 100, cost=10, shipping_cost=1
        )
        self.assertEqual(capped, 17.6)

    def test_price_below_floor_is_rejected_without_store_update(self):
        with self.assertRaises(GuardrailViolation):
            self.tools.update_price(
                "store-1", "sku-1", 14, 20, cost=10, shipping_cost=1
            )
        self.assertNotIn("sku-1", self.store.prices)
        self.assertEqual(self.repo.audit(), [])

    def test_refund_requests_are_classified_without_payment_action(self):
        self.assertEqual(self.tools.request_refund(25), "auto_approved")
        self.assertEqual(
            self.tools.request_refund(25.01), "needs_human_approval"
        )
        with self.assertRaises(GuardrailViolation):
            self.tools.request_refund(-1)


class DraftSupportReplyTests(unittest.TestCase):
    def test_uses_configured_model_and_refund_safe_system_prompt(self):
        response = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="We can review your request.")]
        )
        client = types.SimpleNamespace(
            messages=types.SimpleNamespace(create=Mock(return_value=response))
        )
        anthropic_module = types.ModuleType("anthropic")
        anthropic_module.Anthropic = Mock(return_value=client)

        with patch.dict(
            os.environ, {"ANTHROPIC_MODEL": "test-model"}, clear=False
        ), patch.dict(sys.modules, {"anthropic": anthropic_module}):
            draft = draft_support_reply(
                "Can I get a refund?", {"status": "shipped"}
            )

        self.assertEqual(draft, "We can review your request.")
        call = client.messages.create.call_args.kwargs
        self.assertEqual(call["model"], "test-model")
        self.assertIn("Never promise", call["system"])
        self.assertIn("Can I get a refund?", call["messages"][0]["content"])

    def test_requires_model_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_MODEL"):
                draft_support_reply("Question", {})


if __name__ == "__main__":
    unittest.main()