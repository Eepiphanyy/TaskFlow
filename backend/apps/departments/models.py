from django.db import models

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "departments"
        ordering = ["id"]
        permissions = [
            (
                "view_department_members",
                "Can view department members",
            ),
        ]

    def __str__(self):
        return self.name
