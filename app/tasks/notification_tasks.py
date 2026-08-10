"""
通知异步任务 — 短信 / 邮件 / 工单同步。

Celery Queue: notification
"""

from __future__ import annotations

from app.tasks.celery_app import celery_app
from app.core.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, queue="notification")
def send_sms_notification(self, phone: str, message: str, template_id: str = "") -> dict:
    """发送短信通知。

    场景：工单创建成功、客服已接单、维修完成等。

    Args:
        phone: 手机号
        message: 短信内容
        template_id: 短信模板 ID

    Returns:
        {"status": "sent", "phone": phone, "message_id": "..."}
    """
    logger.info("sms_send_start", phone=phone[-4:], template=template_id)

    # TODO: 对接短信服务商（阿里云短信 / 腾讯云短信）
    # response = sms_client.send(phone, message, template_id)
    # if not response.success:
    #     raise self.retry()

    return {
        "status": "sent",
        "phone": f"{phone[:3]}****{phone[-4:]}",
        "message_id": f"sms_{self.request.id}",
        "channel": "sms",
    }


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60, queue="notification")
def send_email_notification(
    self,
    to_email: str,
    subject: str,
    body: str,
    html_body: str = "",
) -> dict:
    """发送邮件通知。

    场景：工单状态变更、保修到期提醒等。
    """
    logger.info("email_send_start", to=to_email, subject=subject[:50])

    # TODO: 对接邮件服务（SMTP / SendGrid / SES）
    # send_email(to_email, subject, body, html_body)

    return {
        "status": "sent",
        "to": to_email,
        "subject": subject,
        "channel": "email",
    }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, queue="ticket_sync")
def sync_ticket_to_crm(self, ticket_id: str, action: str = "create") -> dict:
    """同步工单到外部 CRM/售后系统。

    Args:
        ticket_id: 工单 ID
        action: create / update / close
    """
    logger.info("ticket_sync_start", ticket_id=ticket_id, action=action)

    # TODO: 对接外部 CRM API
    # response = crm_client.sync_ticket(ticket_id, action)

    return {
        "ticket_id": ticket_id,
        "action": action,
        "status": "synced",
    }
