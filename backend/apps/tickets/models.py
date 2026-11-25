from django.conf import settings
from django.db import models

class TicketCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "ticket_categories"

    def __str__(self):
        return self.name

class Ticket(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待处理"
        PROCESSING = "processing", "处理中"
        RESOLVED = "resolved", "已解决"
        CLOSED = "closed", "已关闭"

    class Priority(models.TextChoices):
        LOW = "low", "低"
        MEDIUM = "medium", "普通"
        HIGH = "high", "高"
        URGENT = "urgent", "紧急"

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        TicketCategory, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="tickets"
    )
    department = models.ForeignKey(
        "departments.Department",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_tickets"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assigned_tickets"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tickets"
        ordering = ["-created_at"]
        permissions = [
            ("assign_ticket", "Can assign ticket"),
            ("process_ticket", "Can process ticket"),
            ("close_ticket", "Can close ticket"),
        ]
        indexes = [
            models.Index(fields=["status", "priority"], name="ticket_status_priority_idx"),
            models.Index(fields=["created_at"], name="ticket_created_at_idx"),
        ]

    def __str__(self):
        return self.title

class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_comments"
        ordering = ["created_at"]
