from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'  # Ensure this matches your app name exactly
    label = 'core'  # Add this line explicitly

