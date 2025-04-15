from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt 
from django.contrib import messages
from pathlib import Path
from .models import Post, Comment, Like, UserProfile
from .forms import PostForm, CommentForm, UsernameChangeForm, SignUpForm, UserProfileForm
import json
from collections import Counter
from django.db import IntegrityError
from .models import FriendRequest
from django.http import Http404, HttpResponseRedirect
from django.http import JsonResponse, HttpResponse
User = get_user_model()
import logging
logger = logging.getLogger(__name__)
# ---------------- AUTH VIEWS ----------------
@login_required
def edit_profile(request, username):
    user_profile = get_object_or_404(UserProfile, user__username=username)
    if request.user != user_profile.user:
        return redirect('feed')

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            return redirect('user_profile', username=username)
    else:
        form = UserProfileForm(instance=user_profile)

    return render(request, 'profile_edit.html', {'form': form})


@login_required
def update_profile_pic(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Profile picture updated successfully',
                    'image_url': profile.profile_picture.url
                })
            
            messages.success(request, "Profile picture updated.")
            return redirect('user_profile', username=request.user.username)
    else:
        form = UserProfileForm(instance=profile)

    return redirect('user_profile', username=request.user.username)



def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            profile = user.userprofile
            if 'profile_picture' in request.FILES:
                profile.profile_picture = request.FILES['profile_picture']
                profile.save()
            login(request, user)
            return redirect('feed')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('feed')
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# ---------------- FEED VIEW ----------------
@login_required
def feed(request):
    posts = Post.objects.all().order_by('-created_at')
    user_profile = UserProfile.objects.filter(user=request.user).first()

    for post in posts:
        # 👇 Ensure every user has a profile to avoid template crash
        UserProfile.objects.get_or_create(user=post.user)

        if post.image:
            ext = Path(post.image.name).suffix.lower()
            post.media_type = 'image' if ext in ['.jpg', '.jpeg', '.png', '.gif'] else 'unknown'
            post.media = post.image
        elif post.video:
            ext = Path(post.video.name).suffix.lower()
            post.media_type = 'video' if ext in ['.mp4', '.webm', '.ogg'] else 'unknown'
            post.media = post.video
        else:
            post.media_type = 'none'
            post.media = None

        post.liked_by_user = Like.objects.filter(user=request.user, post=post).exists()
        post.total_likes = post.likes.count()
        post.total_comments = post.comment_set.count()

    return render(request, 'feed.html', {
        'posts': posts,
        'user': request.user,
        'user_profile': user_profile,
    })



# ---------------- POST VIEWS ----------------
@login_required
def post_create(request):
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.user = request.user
        post.save()
        return redirect('feed')
    return render(request, 'post_create.html', {'form': form})


@login_required
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk, user=request.user)
    post.delete()
    return redirect('feed')


# ---------------- COMMENT VIEWS ----------------
@login_required
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk, user=request.user)
    comment.delete()
    return redirect('feed')



@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if request.method == 'POST':
        comment_text = request.POST.get('comment') or request.POST.get('text')  # Handle both field names
        
        # Common duplicate check logic
        def is_duplicate(text):
            return Comment.objects.filter(
                user=request.user,
                post=post,
                text=text,
                created_at__gte=timezone.now() - timezone.timedelta(seconds=5)
            ).exists()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Handle AJAX request
            if comment_text:
                if is_duplicate(comment_text):
                    return JsonResponse({'success': False, 'error': 'Duplicate comment detected'}, status=400)
                
                comment = Comment.objects.create(
                    user=request.user,
                    post=post,
                    text=comment_text
                )
                profile = UserProfile.objects.get(user=request.user)

                return JsonResponse({
                    'success': True,
                    'id': comment.id,
                    'username': request.user.username,
                    'text': comment.text,
                    'created_at': 'Just now',
                    'profile_pic_url': profile.get_image_url()
                })
            return JsonResponse({'success': False, 'error': 'Comment text is required'}, status=400)

        else:
            # Handle regular form submission
            form = CommentForm(request.POST)
            if form.is_valid():
                comment_text = form.cleaned_data['text']
                if not is_duplicate(comment_text):
                    comment = form.save(commit=False)
                    comment.user = request.user
                    comment.post = post
                    comment.save()
            return redirect('post_detail', post_id=post_id)

    else:
        # GET request
        form = CommentForm()

    return render(request, 'comment_form.html', {'form': form, 'post': post})
# ---------------- LIKE VIEW ----------------
@login_required
def like_post_ajax(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    user = request.user
    
    # Check if user already liked the post
    like_exists = Like.objects.filter(user=user, post=post).exists()
    
    if like_exists:
        # User already liked the post, so unlike it
        Like.objects.filter(user=user, post=post).delete()
        # Also remove from the ManyToMany field
        post.likes.remove(user)
        liked = False
    else:
        # User hasn't liked the post yet, so create a like
        try:
            Like.objects.create(user=user, post=post)
            # Also add to the ManyToMany field
            post.likes.add(user)
            liked = True
        except IntegrityError:
            # Handle rare race condition if like already exists
            liked = True
    
    like_count = post.likes.count()
    
    return JsonResponse({
        'success': True,
        'liked': liked,
        'like_count': like_count,
        'like_text': f"{like_count} like{'s' if like_count != 1 else ''}"
    })

# ---------------- PROFILE VIEWS ----------------
@login_required
def user_profile(request, username):
    # Get the user whose profile is being viewed
    profile_user = get_object_or_404(User, username=username)
    
    # Get or create the profile for the profile user
    profile, _ = UserProfile.objects.get_or_create(user=profile_user)
    
    # Default values
    is_friend = False
    pending_request = None
    received_request = None
    
    # If viewing someone else's profile
    if request.user != profile_user:
        # Check friendship status
        current_profile, _ = UserProfile.objects.get_or_create(user=request.user)
        is_friend = current_profile.friends.filter(pk=profile.pk).exists()
        
        # Check if there's a pending friend request FROM the current user
        pending_request = FriendRequest.objects.filter(
            sender=request.user, 
            receiver=profile_user,
            accepted=False
        ).first()
        
        # Check if there's a pending friend request TO the current user
        received_request = FriendRequest.objects.filter(
            sender=profile_user,
            receiver=request.user,
            accepted=False
        ).first()
    
    # Get all posts for this user
    posts = Post.objects.filter(user=profile_user).order_by('-created_at')
    
    # For right sidebar - get pending friend requests
    friend_requests = None
    if request.user == profile_user:
        friend_requests = FriendRequest.objects.filter(receiver=request.user, accepted=False)
    
    context = {
        'profile_user': profile_user,
        'profile': profile,
        'posts': posts,
        'is_friend': is_friend,
        'pending_request': pending_request,
        'received_request': received_request,
        'friend_requests': friend_requests,
    }
    
    return render(request, 'user_profile.html', context)


def guest_profile(request, username):
    user = get_object_or_404(User, username=username)
    posts = Post.objects.filter(user=user)
    return render(request, 'guest_profile.html', {'profile_user': user, 'posts': posts})


@login_required
def change_username(request):
    return JsonResponse({'message': 'Change username logic not implemented yet'})


# ---------------- SEARCH VIEW ----------------
@login_required
def search_users_ajax(request):
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []}) if request.headers.get('X-Requested-With') == 'XMLHttpRequest' else redirect('home')

    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    )[:10]  # Limit to 10 results

    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Redirect to profile if exactly one match
        if users.count() == 1:
            return HttpResponseRedirect(f"/profile/{users[0].username}/")
        # Otherwise, show list in template
        return render(request, 'search_results.html', {'users': users, 'query': query})

    # For AJAX: build result list
    results = []
    for user in users:
        try:
            profile_pic = user.userprofile.profile_picture.url
        except:
            profile_pic = None
            
        results.append({
            'username': user.username,
            'full_name': f"{user.first_name} {user.last_name}".strip(),
            'profile_pic': profile_pic,
            'profile_url': f"/profile/{user.username}/"
        })
    
    return JsonResponse({'results': results})


# ---------------- SIDEBAR VIEW ----------------
@login_required
def sidebar(request):
    user_profile = UserProfile.objects.filter(user=request.user).first()
    friends = user_profile.followers.all() if user_profile else []
    return render(request, 'sidebar.html', {'friends': friends})





@login_required
def view_friend_requests(request):
    # Get friend requests where Sanjay is the receiver and not yet accepted
    pending_requests = FriendRequest.objects.filter(receiver=request.user, accepted=False)
    return render(request, 'friend_requests.html', {'friend_requests': pending_requests})



@login_required
def send_friend_request(request, username):
    logger.info("send_friend_request called by %s to %s", request.user.username, username)
    receiver = get_object_or_404(User, username=username)
    
    if request.user == receiver:
        messages.error(request, "You cannot send a friend request to yourself.")
        return redirect('user_profile', username=username)

    # Optional: Delete any existing friend request records between these two users.
    FriendRequest.objects.filter(sender=request.user, receiver=receiver).delete()
    FriendRequest.objects.filter(sender=receiver, receiver=request.user).delete()
    
    # Now create a new friend request.
    friend_request, created = FriendRequest.objects.get_or_create(
        sender=request.user,
        receiver=receiver,
        defaults={'accepted': False, 'created_at': timezone.now()}
    )
    
    if created:
        messages.success(request, "Friend request sent!")
    else:
        messages.info(request, "A friend request has already been sent.")
    
    return redirect('user_profile', username=username)

@login_required
def accept_friend_request(request, request_id):
    try:
        friend_request = FriendRequest.objects.get(id=request_id, receiver=request.user, accepted=False)
    except FriendRequest.DoesNotExist:
        # Instead of throwing a 404 error, redirect with a message.
        messages.error(request, "This friend request does not exist or has already been processed.")
        return redirect('user_profile', username=request.user.username)
    
    # Mark request as accepted.
    friend_request.accepted = True
    friend_request.save()
    
    # Get the profiles explicitly.
    sender_profile = UserProfile.objects.get(user=friend_request.sender)
    receiver_profile = UserProfile.objects.get(user=request.user)
    
    # Add each other as friends.
    sender_profile.friends.add(receiver_profile)
    receiver_profile.friends.add(sender_profile)
    
    messages.success(request, "Friend request accepted!")
    return redirect('view_friend_requests')  # or redirect to an appropriate page
@login_required
def suggest_friends(request):
    user_profile = request.user.userprofile
    all_profiles = User.objects.exclude(id=request.user.id)
    suggestions = []

    for other_user in all_profiles:
        mutual_friends = user_profile.get_mutual_friends(other_user)
        if mutual_friends.exists() and not user_profile.friends.filter(user=other_user).exists():
            suggestions.append({
                'user': other_user,
                'mutual_count': mutual_friends.count(),
                'mutual_names': [friend.username for friend in mutual_friends],
            })

    return render(request, 'friend_suggestions.html', {'suggestions': suggestions})

@login_required
def remove_friend(request, username):
    # Get the profile of the user to remove.
    friend_profile = get_object_or_404(UserProfile, user__username=username)
    current_profile = get_object_or_404(UserProfile, user=request.user)
    
    if current_profile.friends.filter(pk=friend_profile.pk).exists():
        # Remove the friend from both users.
        current_profile.friends.remove(friend_profile)
        friend_profile.friends.remove(current_profile)
        messages.success(request, f"You have removed {username} from your friends list.")
    else:
        messages.warning(request, f"{username} is not in your friends list.")

    return redirect('user_profile', username=request.user.username)
@login_required
def decline_friend_request(request, request_id):
    try:
        friend_request = FriendRequest.objects.get(id=request_id, receiver=request.user, accepted=False)
    except FriendRequest.DoesNotExist:
        messages.error(request, "This friend request does not exist or has already been processed.")
        return redirect('user_profile', username=request.user.username)
    
    # Delete the friend request
    friend_request.delete()
    
    messages.success(request, "Friend request declined.")
    return redirect('view_friend_requests')  # or redirect to an appropriate page
@login_required
def cancel_friend_request(request, request_id):
    try:
        friend_request = FriendRequest.objects.get(id=request_id, sender=request.user, accepted=False)
        receiver_username = friend_request.receiver.username
        friend_request.delete()
        messages.success(request, "Friend request cancelled.")
    except FriendRequest.DoesNotExist:
        messages.error(request, "This friend request does not exist or has already been processed.")
        receiver_username = request.GET.get('username', request.user.username)
    
    return redirect('user_profile', username=receiver_username)


def get_friends(user):
    return User.objects.filter(
        Q(friends_sent__receiver=user, friends_sent__status='accepted') |
        Q(friends_received__sender=user, friends_received__status='accepted')
    ).distinct()


@login_required
def suggest_mutual_friends(request):
    user = request.user
    friends = get_friends(user)

    mutual_candidates = []

    for friend in friends:
        friend_friends = get_friends(friend)
        for ff in friend_friends:
            if ff != user and ff not in friends:
                mutual_candidates.append(ff)

    mutual_counts = Counter(mutual_candidates)
    # Sort by number of mutual friends
    suggestions = sorted(mutual_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    results = []
    for suggested_user, count in suggestions:
        try:
            profile_pic = suggested_user.userprofile.profile_picture.url
        except:
            profile_pic = None

        results.append({
            'username': suggested_user.username,
            'full_name': f"{suggested_user.first_name} {suggested_user.last_name}".strip(),
            'profile_pic': profile_pic,
            'profile_url': f"/profile/{suggested_user.username}/",
            'mutual_friends': count
        })

    return JsonResponse({'results': results})