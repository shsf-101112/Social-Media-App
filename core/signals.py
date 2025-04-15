# signals.py
from django.apps import apps
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()

from .models import UserProfile


@receiver(post_delete, sender=apps.get_model('core', 'Post'))
def delete_post_media(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(False)
    if instance.video:
        instance.video.delete(False)

# core/signals.py

from django.conf import settings

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

