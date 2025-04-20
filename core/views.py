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
from .models import Post, Comment, Like, UserProfile, FriendRequest,Message
from .forms import PostForm, CommentForm, UsernameChangeForm, SignUpForm, UserProfileForm
import json
from collections import Counter
from django.db import IntegrityError
from .models import FriendRequest
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
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
    suggestions, debug = get_friend_suggestions_data(request.user)

    return render(request, 'feed.html', {
        'posts': posts,
        'user': request.user,
        'user_profile': user_profile,
        'suggestions': suggestions,
        'debug': debug,
    })



# ---------------- POST VIEWS ----------------
@login_required
def post_create(request):
    form = PostForm(request.POST or None, request.FILES or None)

    # Fetch friend suggestions for the sidebar
    suggestions, debug = get_friend_suggestions_data(request.user)

    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.user = request.user
        post.save()
        return redirect('feed')
    
    # Include suggestions in the context
    return render(request, 'post_create.html', {
        'form': form,
        'suggestions': suggestions,  # Friend suggestions for the sidebar
        'debug': debug,              # Optional for debugging purposes
    })



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
            return redirect('feed')

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
    
    # Integrate sidebar functionality: Get friends and their unread message counts
    user_profile = UserProfile.objects.filter(user=request.user).first()
    friends = user_profile.friends.all() if user_profile else []

    friend_notifications = []
    for friend in friends:
        unread_messages = Message.objects.filter(sender=friend.user, receiver=request.user, is_read=False).count()
        friend_notifications.append({
            "friend": friend,
            "unread_messages": unread_messages
        })
    
    # Get friend suggestions (existing logic)
    suggestions, debug = get_friend_suggestions_data(request.user)

    # Final context
    context = {
        'profile_user': profile_user,
        'profile': profile,
        'posts': posts,
        'is_friend': is_friend,
        'pending_request': pending_request,
        'received_request': received_request,
        'friend_requests': friend_requests,
        'suggestions': suggestions,  # Pass friend suggestions here
        'debug': debug,
        'friend_notifications': friend_notifications,  # Integrate friends and unread message counts
    }
    
    return render(request, 'user_profile.html', context)




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
    return redirect('user_profile', username=friend_request.sender.username)


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

    # Redirect to the removed user's profile
    return redirect('user_profile', username=username)

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
    return redirect('feed')  # or redirect to an appropriate page
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


def get_friend_suggestions_data(user):
    """Helper function to generate friend suggestions."""
    try:
        user_profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return [], {}

    # Get user's direct friends
    direct_friends = user_profile.friends.all()

    # Retrieve users who have already been sent a friend request
    sent_friend_requests = FriendRequest.objects.filter(sender=user, accepted=False)
    sent_request_users = [request.receiver for request in sent_friend_requests]

    suggestions = []
    mutual_friends_data = []

    # Exclude sent friend request users in suggestions
    if direct_friends.exists():
        for friend_profile in direct_friends:
            for potential_friend in friend_profile.friends.all():
                # Skip the logged-in user, direct friends, or users who already received friend requests
                if potential_friend.user == user or potential_friend in direct_friends or potential_friend.user in sent_request_users:
                    continue
                mutual_friends_data.append(potential_friend.user)

        mutual_counts = Counter(mutual_friends_data)

        for suggested_user, count in mutual_counts.most_common(10):
            mutual_profiles = [
                friend_profile
                for friend_profile in direct_friends
                if suggested_user in [fp.user for fp in friend_profile.friends.all()]
            ]
            mutual_names = [profile.user.username for profile in mutual_profiles[:3]]

            try:
                suggested_profile = UserProfile.objects.get(user=suggested_user)
                profile_pic = suggested_profile.get_image_url()
            except:
                profile_pic = '/media/profile_pics/default.jpg'

            suggestions.append({
                'user': suggested_user,
                'profile_pic': profile_pic,
                'mutual_count': count,
                'mutual_names': mutual_names,
                'reason': 'mutual_friends'
            })

    # Fallback: General suggestions for new users not in direct friends or sent requests
    if not suggestions:
        excluded_ids = [friend.user.id for friend in direct_friends]
        excluded_ids += [user.id] + [sent_request_user.id for sent_request_user in sent_request_users]

        potential_friends = UserProfile.objects.exclude(
            user__id__in=excluded_ids
        ).order_by('-user__date_joined')[:10]

        for profile in potential_friends:
            try:
                profile_pic = profile.get_image_url()
            except:
                profile_pic = '/media/profile_pics/default.jpg'

            suggestions.append({
                'user': profile.user,
                'profile_pic': profile_pic,
                'mutual_count': 0,
                'mutual_names': [],
                'reason': 'new_user'
            })

    debug_info = {
        'friend_count': direct_friends.count(),
        'friend_names': [f.user.username for f in direct_friends],
        'sent_requests_count': len(sent_request_users),
        'mutual_data_count': len(mutual_friends_data),
        'has_general_suggestions': any(s['reason'] == 'new_user' for s in suggestions)
    }

    return suggestions,debug_info

@login_required
def chat_view(request, username):
    user = request.user
    other_user = User.objects.get(username=username)

    if request.method == "POST":
        # Handle message creation
        content = request.POST.get("content")
        if content:
            Message.objects.create(sender=user, receiver=other_user, content=content)

    # Mark messages as read
    Message.objects.filter(sender=other_user, receiver=user, is_read=False).update(is_read=True)

    # Fetch only messages exchanged between the current user and other_user
    messages = Message.objects.filter(
        sender__in=[user, other_user],
        receiver__in=[user, other_user]
    ).order_by("timestamp")

    return render(request, "chat.html", {
        "messages": messages,
        "other_user": other_user
    })


@login_required
@csrf_exempt
def send_message(request, username):
    if request.method == "POST":
        content = request.POST.get("content")
        receiver = User.objects.get(username=username)
        if content:
            Message.objects.create(sender=request.user, receiver=receiver, content=content)
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "fail"}, status=400)

@login_required
def get_messages(request, username):
    user = request.user
    other_user = User.objects.get(username=username)

    # Fetch only messages exchanged between the current user and other_user
    messages = Message.objects.filter(
        sender__in=[user, other_user],
        receiver__in=[user, other_user]
    ).order_by("timestamp")

    return JsonResponse({
        "messages": [
            {
                "sender": msg.sender.username,
                "content": msg.content,
                "timestamp": msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            } for msg in messages
        ]
    })
from django.db.models import Count, Q, F, Value, IntegerField
from django.db.models.functions import Coalesce
from .models import UserSkill, UserProjectInterest, UserAvailability, Skill, ProjectInterest
import math


@login_required
def collab_radar(request):
    """
    Main view for the Collab Radar feature
    """
    # Get user's skills and interests
    user_skills = UserSkill.objects.filter(user=request.user).select_related('skill')
    user_interests = UserProjectInterest.objects.filter(user=request.user).select_related('project_interest')
    
    # Get top skills and interests for filtering
    top_skills = Skill.objects.annotate(user_count=Count('userskill')).order_by('-user_count')[:15]
    top_interests = ProjectInterest.objects.annotate(user_count=Count('userprojectinterest')).order_by('-user_count')[:15]
    
    try:
        user_availability = UserAvailability.objects.get(user=request.user)
    except UserAvailability.DoesNotExist:
        user_availability = UserAvailability.objects.create(user=request.user)
    
    context = {
        'user_skills': user_skills,
        'user_interests': user_interests,
        'user_availability': user_availability,
        'top_skills': top_skills,
        'top_interests': top_interests,
    }
    
    return render(request, 'collab_radar.html', context)

@login_required
def collab_radar_search(request):
    """
    AJAX view to search for potential collaborators
    """
    if request.method == 'POST':
        # Parse JSON data from request
        data = json.loads(request.body)
        
        # Get selected skills and interests
        skill_ids = data.get('skills', [])
        interest_ids = data.get('interests', [])
        availability_min = data.get('availability_min', 0)
        
        # Get user's skills and interests for matching
        user_skills = list(UserSkill.objects.filter(user=request.user).values_list('skill_id', flat=True))
        user_interests = list(UserProjectInterest.objects.filter(user=request.user).values_list('project_interest_id', flat=True))
        
        # Base query for users with availability info
        users_query = UserAvailability.objects.filter(
            available_for_collab=True,
            availability_hours__gte=availability_min
        ).exclude(user=request.user)
        
        # Filter by skills if provided
        if skill_ids:
            users_query = users_query.filter(user__skills__skill_id__in=skill_ids)
        
        # Filter by interests if provided
        if interest_ids:
            users_query = users_query.filter(user__project_interests__project_interest_id__in=interest_ids)
        
        # Add distinct to avoid duplicates
        users_query = users_query.distinct()
        
        # Calculate match score for each user
        matched_users = []
        for user_avail in users_query:
            user = user_avail.user
            
            # Calculate skill match score
            user_skill_ids = set(UserSkill.objects.filter(user=user).values_list('skill_id', flat=True))
            skill_match = len(user_skill_ids.intersection(user_skills))
            
            # Calculate interest match score
            user_interest_ids = set(UserProjectInterest.objects.filter(user=user).values_list('project_interest_id', flat=True))
            interest_match = len(user_interest_ids.intersection(user_interests))
            
            # Calculate overall match score (weighted)
            match_score = (skill_match * 2) + interest_match
            
            # Calculate distance for radar visualization (inverse of match score)
            # The higher the match, the closer to the center
            distance = max(10, 100 - (match_score * 10))
            angle = (hash(user.username) % 360) * (math.pi / 180)  # random angle based on username hash
            x = distance * math.cos(angle)
            y = distance * math.sin(angle)
            
            # Basic profile info
            profile = user.userprofile
            skills = UserSkill.objects.filter(user=user).select_related('skill')[:5]
            interests = UserProjectInterest.objects.filter(user=user).select_related('project_interest')[:5]
            
            matched_users.append({
                'id': user.id,
                'username': user.username,
                'profile_pic': profile.get_image_url(),
                'match_score': match_score,
                'distance': distance,
                'x': x,
                'y': y,
                'availability': user_avail.get_availability_hours_display(),
                'skills': [{'name': s.skill.name, 'level': s.get_proficiency_level_display()} for s in skills],
                'interests': [{'name': i.project_interest.name, 'level': i.get_interest_level_display()} for i in interests],
            })
        
        # Sort by match score (highest first)
        matched_users.sort(key=lambda x: x['match_score'], reverse=True)
        
        return JsonResponse({
            'users': matched_users,
            'total': len(matched_users)
        })
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def manage_skills(request):
    """View to manage user skills"""
    user_skills = UserSkill.objects.filter(user=request.user).select_related('skill')
    all_skills = Skill.objects.all().order_by('name')
    
    return render(request, 'manage_skills.html', {
        'user_skills': user_skills,
        'all_skills': all_skills
    })

@login_required
def add_skill(request):
    """AJAX view to add a skill to user profile"""
    if request.method == 'POST':
        skill_id = request.POST.get('skill_id')
        proficiency = request.POST.get('proficiency', 1)
        
        # If skill_name is provided, find or create the skill
        skill_name = request.POST.get('skill_name')
        if skill_name and not skill_id:
            skill, created = Skill.objects.get_or_create(name=skill_name)
            skill_id = skill.id
        
        if skill_id:
            skill = get_object_or_404(Skill, id=skill_id)
            user_skill, created = UserSkill.objects.get_or_create(
                user=request.user,
                skill=skill,
                defaults={'proficiency_level': proficiency}
            )
            
            if not created:
                user_skill.proficiency_level = proficiency
                user_skill.save()
            
            return JsonResponse({
                'success': True,
                'skill_id': skill.id,
                'skill_name': skill.name,
                'proficiency': user_skill.get_proficiency_level_display()
            })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def remove_skill(request, skill_id):
    """Remove a skill from user profile"""
    user_skill = get_object_or_404(UserSkill, user=request.user, skill_id=skill_id)
    user_skill.delete()
    return JsonResponse({'success': True})


@login_required
def add_interest(request):
    """AJAX view to add a project interest to user profile"""
    if request.method == 'POST':
        interest_id = request.POST.get('interest_id')
        interest_level = request.POST.get('interest_level', 2)
        
        # If interest_name is provided, find or create the interest
        interest_name = request.POST.get('interest_name')
        if interest_name and not interest_id:
            interest, created = ProjectInterest.objects.get_or_create(name=interest_name)
            interest_id = interest.id
        
        if interest_id:
            interest = get_object_or_404(ProjectInterest, id=interest_id)
            user_interest, created = UserProjectInterest.objects.get_or_create(
                user=request.user,
                project_interest=interest,
                defaults={'interest_level': interest_level}
            )
            
            if not created:
                user_interest.interest_level = interest_level
                user_interest.save()
            
            return JsonResponse({
                'success': True,
                'interest_id': interest.id,
                'interest_name': interest.name,
                'interest_level': user_interest.get_interest_level_display()
            })
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def remove_interest(request, interest_id):
    """Remove a project interest from user profile"""
    user_interest = get_object_or_404(UserProjectInterest, user=request.user, project_interest_id=interest_id)
    user_interest.delete()
    return JsonResponse({'success': True})

@login_required
def update_availability(request):
    """Update user availability settings"""
    if request.method == 'POST':
        available = request.POST.get('available') == 'true'
        hours = request.POST.get('hours', 5)
        start_date = request.POST.get('start_date', None)
        notes = request.POST.get('notes', '')
        
        availability, created = UserAvailability.objects.get_or_create(
            user=request.user,
            defaults={
                'available_for_collab': available,
                'availability_hours': hours,
                'notes': notes
            }
        )
        
        if not created:
            availability.available_for_collab = available
            availability.availability_hours = hours
            availability.notes = notes
            
            if start_date:
                availability.availability_start_date = start_date
                
            availability.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)
