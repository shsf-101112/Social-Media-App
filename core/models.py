from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.models import AbstractUser, Group, Permission

# Custom User model
class CustomUser(AbstractUser):
    # You can add custom fields here if needed.
    # For now, we'll just use AbstractUser’s default fields.

    # Optionally override the groups and permissions fields to avoid reverse relation clashes:
    groups = models.ManyToManyField(
        Group,
        related_name="customuser_set",  # a unique related name
        blank=True,
        help_text="The groups this user belongs to.",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_set",  # a unique related name
        blank=True,
        help_text="Specific permissions for this user.",
    )
    
    def __str__(self):
        return self.username

User = get_user_model()

# Consolidated UserProfile model with fields and a self-referential friends relationship.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.jpg', blank=True)

    # Use a self-referential ManyToManyField to represent established friendships.
    friends = models.ManyToManyField("self", symmetrical=True, blank=True)

    def get_mutual_friends(self, other_profile):
        """
        Return a QuerySet of mutual friends between this profile and another.
        other_profile should be another UserProfile instance.
        """
        # Get the IDs of the other profile's friends.
        other_friends_ids = other_profile.friends.all().values_list('id', flat=True)
        # Filter this profile's friends to those that are also in the other profile.
        return self.friends.filter(id__in=other_friends_ids)

    def get_image_url(self):
        """Return image URL or default if file doesn't exist"""
        try:
            return self.profile_picture.url
        except:
            return '/media/profile_pics/default.jpg'
    def __str__(self):
        return self.user.username


# Post model with support for text content, images, videos, likes, and comments.
class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    image = models.ImageField(upload_to='post_images/', blank=True, null=True)
    video = models.FileField(upload_to='post_videos/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    # ManyToMany field to store users who liked the post.
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)

    def total_likes(self):
        return self.likes.count()

    def total_comments(self):
        return self.comment_set.count()

    def __str__(self):
        return f"Post by {self.user.username}"


# Comment model for posts.
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Comment by {self.user.username} on Post {self.post.id}"


# Optional Like model if you want audit/metadata in addition to the ManyToMany "likes" on Post.
class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} likes Post {self.post.id}"


# FriendRequest model for managing friend request actions.
class FriendRequest(models.Model):
    sender = models.ForeignKey(
        User, related_name='friend_requests_sent', on_delete=models.CASCADE
    )
    receiver = models.ForeignKey(
        User, related_name='friend_requests_received', on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}"



class Friend(models.Model):
    sender = models.ForeignKey(CustomUser, related_name='friends_sent', on_delete=models.CASCADE)
    receiver = models.ForeignKey(CustomUser, related_name='friends_received', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=(('pending', 'Pending'), ('accepted', 'Accepted')))
    timestamp = models.DateTimeField(auto_now_add=True)

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE,default=1)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE,default=1)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    def __str__(self):
        return f'{self.sender} to {self.receiver}: {self.content[:30]}'
# Add these to your models.py file

class Skill(models.Model):
    name = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return self.name

class ProjectInterest(models.Model):
    name = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return self.name

class UserSkill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    proficiency_level= [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('expert', 'Expert'),
    ]
    proficiency_level = models.CharField(max_length=20, choices=proficiency_level)
    
    class Meta:
        unique_together = ('user', 'skill')
    
    def __str__(self):
        return f"{self.user.username} - {self.skill.name} ({self.get_proficiency_level_display()})"

class UserProjectInterest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_interests')
    project_interest = models.ForeignKey(ProjectInterest, on_delete=models.CASCADE)
    interest_level = models.IntegerField(
        choices=[(1, 'Curious'), (2, 'Interested'), (3, 'Very Interested')],
        default=2
    )
    
    class Meta:
        unique_together = ('user', 'project_interest')
    
    def __str__(self):
        return f"{self.user.username} - {self.project_interest.name}"

class UserAvailability(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='availability')
    available_for_collab = models.BooleanField(default=True)
    availability_hours = models.IntegerField(
        choices=[
            (5, 'Less than 5 hours/week'),
            (10, '5-10 hours/week'),
            (20, '10-20 hours/week'),
            (40, 'More than 20 hours/week')
        ],
        default=5
    )
    availability_start_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Availability"
    
class CollabInvitation(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected')
    ], default='pending')
    
    class Meta:
        unique_together = ('sender', 'recipient', 'status')