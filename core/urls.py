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
    path('profile/<str:username>/', views.user_profile, name='user_profile'),
    re_path(r'^profile/(?!change-username/)(?P<username>\w+)/$', views.user_profile, name='user_profile'),
    path('guest/profile/<str:username>/', views.guest_profile, name='guest_profile'),
    path('friend/request/send/<str:username>/', views.send_friend_request, name='send_friend_request'),
    path('friend/remove/<str:username>/', views.remove_friend, name='remove_friend'),
    # ... your other URL patterns ...
    path('friend/request/accept/<int:request_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('friend/requests/', views.view_friend_requests, name='view_friend_requests'),
    path('friend/suggestions/', views.suggest_friends, name='friend_suggestions'),
    # Auth
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Feed & Posts
    path('feed/', views.feed, name='feed'),
    path('post/create/', views.post_create, name='post_create'),
    path('post/<int:pk>/delete/', views.post_delete, name='post_delete'),

    # Comments
    path('add_comment/<int:post_id>/', views.add_comment, name='add_comment'),
    path('comment/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    

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
    path('search/users/', views.search_users_ajax, name='search_users_ajax'),
    path('send-friend-request/<str:username>/', views.send_friend_request, name='send_friend_request'),
    path('accept-friend-request/<int:request_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('remove-friend/<str:username>/', views.remove_friend, name='remove_friend'),
    path('friend-requests/', views.view_friend_requests, name='view_friend_requests'),
    
    # Like post URL
    path('like-post/<int:post_id>/', views.like_post_ajax, name='like_post_ajax'),
    path('decline-friend-request/<int:request_id>/', views.decline_friend_request, name='decline_friend_request'),
    # Add this to your urls.py
    path('suggest/mutual-friends/', views.suggest_mutual_friends, name='suggest_mutual_friends'),

    
    path('friend-requests/cancel/<int:request_id>/', views.cancel_friend_request, name='cancel_friend_request'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])


