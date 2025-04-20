from .models import UserProfile, FriendRequest
from django.db.models import Q
from core.models import CustomUser as User  # Or wherever your CustomUser is defined
def sidebar_data(request):
    if request.user.is_authenticated:
        sent = FriendRequest.objects.filter(sender=request.user, accepted=True).values_list('receiver', flat=True)
        received = FriendRequest.objects.filter(receiver=request.user, accepted=True).values_list('sender', flat=True)
        friend_ids = set(sent) | set(received)  # Combine sender and receiver
        friends = UserProfile.objects.filter(user__id__in=friend_ids)
    else:
        friends = UserProfile.objects.none()

    return {'sidebar_friends': friends}
def friend_requests_processor(request):
    if request.user.is_authenticated:
        # Get pending friend requests for the current user (where accepted is False)
        friend_requests = FriendRequest.objects.filter(receiver=request.user, accepted=False)
        return {'friend_requests': friend_requests}
    return {'friend_requests': []}


def get_friends(user):
    return User.objects.filter(
        Q(friends_sent__receiver=user, friends_sent__status='accepted') |
    Q(friends_received__sender=user, friends_received__status='accepted')
    ).distinct()

def suggestions_processor(request):
    if request.user.is_authenticated:
        all_users = User.objects.exclude(id=request.user.id)
        user_friends = set(get_friends(request.user))
        suggestions = []

        for u in all_users:
            u_friends = set(get_friends(u))
            mutual = user_friends & u_friends
            if mutual and u not in user_friends:
                suggestions.append({
                    'user': u,
                    'mutual_count': len(mutual),
                })
        return {'suggestions': suggestions[:5]}  # Limit to 5 suggestions
    return {}

