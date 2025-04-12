from .models import UserProfile

def sidebar_data(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        try:
            friends = UserProfile.objects.filter(user__in=[
                profile.user for profile in request.user.profile.friends.all()
            ])
        except Exception:
            friends = []
    else:
        friends = []

    return {'sidebar_friends': friends}

