from .models import UserProfile, FriendRequest

def sidebar_data(request):
    if request.user.is_authenticated:
        sent = FriendRequest.objects.filter(sender=request.user, accepted=True).values_list('receiver', flat=True)
        received = FriendRequest.objects.filter(receiver=request.user, accepted=True).values_list('sender', flat=True)
        friend_ids = set(sent) | set(received)  # Combine sender and receiver
        friends = UserProfile.objects.filter(user__id__in=friend_ids)
    else:
        friends = UserProfile.objects.none()

    return {'sidebar_friends': friends}
