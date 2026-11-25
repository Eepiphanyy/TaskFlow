from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(
    post_save,
    sender=User,
    dispatch_uid="users.create_user_profile",
)
def create_user_profile(sender, instance, created, **kwargs):
    if created and not kwargs.get("raw", False):
        UserProfile.objects.get_or_create(user=instance)