# urls.py

from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from . import views

def redirect_to_feed(request):
    return redirect('feed')

urlpatterns = [
    path('', redirect_to_feed),

    # Auth
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Feed & Posts
    path('feed/', views.feed, name='feed'),
    path('post/create/', views.post_create, name='post_create'),
    path('post/<int:pk>/delete/', views.post_delete, name='post_delete'),

    # Comments
    path('post/<int:pk>/comment/', views.comment_create, name='comment_create'),
    path('comment/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    path('comment/<int:post_id>/', views.add_comment, name='add_comment'),  
    path('comment/ajax/<int:post_id>/', views.add_comment_ajax, name='add_comment_ajax'),

    # Likes (only AJAX)
    path('like/ajax/<int:post_id>/', views.like_post_ajax, name='like_post_ajax'),

    # Profiles
    path('profile/', views.user_profile, name='user_profile'),
    re_path(r'^profile/(?!change-username/)(?P<username>\w+)/$', views.user_profile, name='user_profile'),
    path('profile/<str:username>/edit/', views.edit_profile, name='edit_profile'),
    path('profile/upload-pic/', views.update_profile_pic, name='update_profile_pic'),
    path('profile/change-username/', views.change_username, name='change_username'),
    path('guest/profile/<str:username>/', views.guest_profile, name='guest_profile'),

    # Search
    path('search/', views.search_users, name='search_users'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])


