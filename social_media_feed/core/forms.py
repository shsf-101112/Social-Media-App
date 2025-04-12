from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, UserProfile, Post, Comment

class SignUpForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email')

class UsernameChangeForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username']

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ('bio', 'location', 'profile_picture')

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('content', 'image', 'video')

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('text',)

