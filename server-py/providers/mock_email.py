"""Mock email provider that writes lifecycle to MongoDB."""

from __future__ import annotations

from datetime import datetime

from models import EmailLog
from providers.base import EmailProvider


class MockEmailProvider(EmailProvider):
    """Create and send email logs without external delivery."""

    def create_draft(
        self,
        *,
        employee_id: str,
        template_type: str,
        recipient: str,
        subject: str,
        body_html: str,
    ) -> dict:
        email_log = EmailLog(
            employee_id=employee_id,
            template_type=template_type,
            recipient=recipient,
            subject=subject,
            body_html=body_html,
            status="pending_review",
        ).save()
        return self._serialize(email_log)

    def send(self, *, email_log_id: str, sent_by: str, sent_at: datetime) -> dict:
        email_log = EmailLog.objects(id=email_log_id).first()
        if email_log is None:
            raise ValueError(f"Email log not found: {email_log_id}")

        email_log.status = "sent"
        email_log.sent_at = sent_at
        email_log.sent_by = sent_by
        email_log.save()
        return self._serialize(email_log)

    @staticmethod
    def _serialize(email_log: EmailLog) -> dict:
        return {
            "id": str(email_log.id),
            "employee_id": email_log.employee_id,
            "template_type": email_log.template_type,
            "recipient": email_log.recipient,
            "subject": email_log.subject,
            "status": email_log.status,
            "sent_at": email_log.sent_at.isoformat() if email_log.sent_at else None,
            "sent_by": email_log.sent_by,
            "created_at": email_log.created_at.isoformat(),
        }
