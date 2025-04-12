from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt 
from django.contrib import messages
from pathlib import Path
from .models import Post, Comment, Like, UserProfile
from .forms import PostForm, CommentForm, UsernameChangeForm, SignUpForm, UserProfileForm
import json

User = get_user_model()


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
def comment_create(request, pk):
    post = get_object_or_404(Post, pk=pk)
    form = CommentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        comment = form.save(commit=False)
        comment.user = request.user
        comment.post = post
        comment.save()
        return redirect('feed')
    return render(request, 'comment_create.html', {'form': form, 'post': post})


@login_required
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk, user=request.user)
    comment.delete()
    return redirect('feed')


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        text = request.POST.get('comment')
        if text:
            Comment.objects.create(
                user=request.user,
                post=post,
                text=text
            )
    return redirect(request.META.get('HTTP_REFERER', 'feed'))


@login_required
@csrf_exempt
def add_comment_ajax(request, post_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get('text')
            post = get_object_or_404(Post, id=post_id)
            comment = Comment.objects.create(user=request.user, post=post, text=text)
            return JsonResponse({
                'username': request.user.username,
                'text': comment.text,
                'timestamp': comment.timestamp.strftime('%Y-%m-%d %H:%M')
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


# ---------------- LIKE VIEW ----------------
@login_required
def like_post_ajax(request, post_id):
    if request.method == "POST":
        post = get_object_or_404(Post, id=post_id)
        user = request.user

        if user in post.likes.all():
            post.likes.remove(user)
            liked = False
        else:
            post.likes.add(user)
            liked = True

        return JsonResponse({
            'liked': liked,
            'total_likes': post.likes.count()
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)


# ---------------- PROFILE VIEWS ----------------
def user_profile(request, username):
    user = get_object_or_404(User, username=username)
    posts = Post.objects.filter(user=user).order_by('-created_at')  # ✅ Correct
    likes = Like.objects.filter(user=user)
    profile = UserProfile.objects.filter(user=user).first()

    return render(request, 'user_profile.html', {
        'profile_user': user,
        'profile': profile,
        'posts': posts,
        'likes': likes,
    })


def guest_profile(request, username):
    user = get_object_or_404(User, username=username)
    posts = Post.objects.filter(user=user)
    return render(request, 'guest_profile.html', {'profile_user': user, 'posts': posts})


@login_required
def change_username(request):
    return JsonResponse({'message': 'Change username logic not implemented yet'})


# ---------------- SEARCH VIEW ----------------
def search_users(request):
    query = request.GET.get('q', '')
    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    )
    return render(request, 'search_users.html', {'users': users, 'query': query})


# ---------------- SIDEBAR VIEW ----------------
@login_required
def sidebar(request):
    user_profile = UserProfile.objects.filter(user=request.user).first()
    friends = user_profile.followers.all() if user_profile else []
    return render(request, 'sidebar.html', {'friends': friends})

