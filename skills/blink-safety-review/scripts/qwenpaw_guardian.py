"""Optional host-process integration; importing a skill alone does not install it."""
from __future__ import annotations

import uuid

from qwenpaw.security.tool_guard.guardians import BaseToolGuardian
from qwenpaw.security.tool_guard.models import GuardFinding, GuardSeverity, GuardThreatCategory

from review_action import advice, review


class BlinkGuardian(BaseToolGuardian):
    def __init__(self, *, endpoint, model, context_provider, threshold=None):
        super().__init__('blink-safety-review', always_run=True)
        self.endpoint, self.model = endpoint, model
        self.context_provider, self.threshold = context_provider, threshold

    def guard(self, tool_name, params):
        try:
            # Obtain request-scoped authorization from the host, never shared global chat state.
            context = self.context_provider()
            action = {'tool_name': tool_name, 'arguments': params,
                      'user_request': context['user_request'], 'authorized_scope': context['authorized_scope']}
            result = review(action, endpoint=self.endpoint, model=self.model, threshold=self.threshold)
        except Exception:
            result = advice('trusted_authorization_context_unavailable')
        if result['decision'] == 'allow':
            return []  # Other guardians and the host's approval policy still apply.
        return [GuardFinding(
            id=str(uuid.uuid4()), rule_id='BLINK_ACTION_REVIEW',
            category=GuardThreatCategory.CODE_EXECUTION, severity=GuardSeverity.HIGH,
            title='Blink: ' + result['decision'],
            description='Blink action review requires attention: ' + result['reason'],
            tool_name=tool_name, guardian=self.name,
            remediation='Keep the action pending and use the existing human approval flow.',
            metadata={'blink_advice': result},
        )]
