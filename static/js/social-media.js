// Common function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith(name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }
  
  // Document ready function
  document.addEventListener('DOMContentLoaded', () => {
    initProfilePictureUpload();
    initLikeButtons();
    initCommentForms();
    initSearchBar();
    initProfileTabs();
    initFriendRequestHandlers();
  });
  
  // Profile Picture Update - Avoid Refresh
  function initProfilePictureUpload() {
    const profileForm = document.getElementById('profile-pic-form');
    if (profileForm) {
      profileForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(profileForm);
        const submitButton = profileForm.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent;
        
        // Show loading state
        submitButton.textContent = 'Uploading...';
        submitButton.disabled = true;
        
        try {
          const response = await fetch("/update_profile_pic/", {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
            },
            body: formData
          });
          
          if (response.ok) {
            // Update the profile image without refreshing
            const fileInput = profileForm.querySelector('input[type="file"]');
            const file = fileInput.files[0];
            
            if (file) {
              const reader = new FileReader();
              reader.onload = function(e) {
                // Find all profile pictures of this user on page and update them
                const profileImages = document.querySelectorAll('.profile-picture-container img, .profile-header-img');
                profileImages.forEach(img => {
                  img.src = e.target.result;
                });
              };
              reader.readAsDataURL(file);
            }
            
            // Success message
            const successMessage = document.createElement('div');
            successMessage.className = 'alert alert-success mt-2';
            successMessage.textContent = 'Profile picture updated successfully!';
            profileForm.after(successMessage);
            
            // Remove message after 3 seconds
            setTimeout(() => {
              successMessage.remove();
            }, 3000);
            
            // Clear the file input
            fileInput.value = '';
          } else {
            throw new Error('Failed to update profile picture');
          }
        } catch (error) {
          console.error('Error updating profile picture:', error);
          
          const errorMessage = document.createElement('div');
          errorMessage.className = 'alert alert-danger mt-2';
          errorMessage.textContent = 'Failed to update profile picture. Please try again.';
          profileForm.after(errorMessage);
          
          setTimeout(() => {
            errorMessage.remove();
          }, 3000);
        } finally {
          // Restore button state
          submitButton.textContent = originalButtonText;
          submitButton.disabled = false;
        }
      });
    }
  }
  
  // Like Button Enhancement - Maintain State
  function initLikeButtons() {
    document.querySelectorAll('.like-btn').forEach(button => {
      button.addEventListener('click', async function() {
        const postId = this.getAttribute('data-post-id');
        const csrfToken = getCookie('csrftoken');
        
        try {
          const response = await fetch(`/like-post/${postId}/`, {
            method: 'POST',
            headers: {
              'X-CSRFToken': csrfToken,
              'X-Requested-With': 'XMLHttpRequest',
            }
          });
          
          if (response.ok) {
            const data = await response.json();
            
            // Get all like buttons for this post (in case displayed multiple times)
            const allButtons = document.querySelectorAll(`.like-btn[data-post-id="${postId}"]`);
            const allCounts = document.querySelectorAll(`.like-count[data-post-id="${postId}"]`);
            
            allButtons.forEach(btn => {
              const icon = btn.querySelector('i');
              
              // Set appropriate icon class based on liked status
              if (data.liked) {
                icon.className = 'bi bi-heart-fill text-danger fs-5';
                btn.classList.add('liked');
              } else {
                icon.className = 'bi bi-heart fs-5';
                btn.classList.remove('liked');
              }
            });
            
            // Update all count displays
            allCounts.forEach(count => {
              count.textContent = data.like_text; // Use the like_text from response
            });
          }
        } catch (error) {
          console.error('Error updating like status:', error);
        }
      });
    });
  }
  
  // Comments via AJAX - No Page Refresh
  function initCommentForms() {
    // For each comment form
    document.querySelectorAll('form[action^="/add_comment/"]').forEach(form => {
      // Remove any existing event listeners to prevent double-submission
      const newForm = form.cloneNode(true);
      form.parentNode.replaceChild(newForm, form);
      
      newForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const postId = this.action.split('/').slice(-2, -1)[0];
        const commentInput = this.querySelector('input[name="comment"]');
        const comment = commentInput.value.trim();
        
        if (!comment) return;
        
        const csrfToken = this.querySelector('input[name="csrfmiddlewaretoken"]').value;
        const submitButton = this.querySelector('button[type="submit"]');
        
        // Disable button while submitting
        submitButton.disabled = true;
        
        try {
          const response = await fetch(`/add_comment/${postId}/`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
              'X-CSRFToken': csrfToken,
              'X-Requested-With': 'XMLHttpRequest',
            },
            body: new URLSearchParams({
              'comment': comment
            })
          });
          
          if (response.ok) {
            const data = await response.json();
            
            // Find the comments container
            const commentsContainer = document.querySelector(`.comment-list[data-post-id="${postId}"]`);
            if (!commentsContainer) {
              console.error('Comment container not found');
              return;
            }
            
            // Create new comment element using data from the server response
            const newCommentHTML = `
              <div class="d-flex mb-2">
                <img src="${data.profile_pic_url}" class="rounded-circle me-2" style="width: 32px; height: 32px; object-fit: cover;">
                <div class="bg-light rounded-3 p-2 flex-grow-1">
                  <div class="d-flex justify-content-between">
                    <strong class="me-2">${data.username}</strong>
                    <small class="text-muted">Just now</small>
                  </div>
                  <p class="mb-0 small">${data.text}</p>
                </div>
              </div>
            `;
            
            // Add to DOM
            commentsContainer.insertAdjacentHTML('beforeend', newCommentHTML);
            
            // Clear input
            commentInput.value = '';
            
            // Update comment count if it exists
            const commentCountElement = document.querySelector(`.comment-count[data-post-id="${postId}"]`);
            if (commentCountElement) {
              const currentCount = parseInt(commentCountElement.getAttribute('data-count') || '0');
              const newCount = currentCount + 1;
              commentCountElement.setAttribute('data-count', newCount);
              commentCountElement.textContent = `${newCount} comment${newCount !== 1 ? 's' : ''}`;
            }
          } else {
            // Handle error responses
            const errorData = await response.json();
            console.error('Error from server:', errorData.error);
            // You could show an error message to the user here
          }
        } catch (error) {
          console.error('Error posting comment:', error);
        } finally {
          // Re-enable button
          submitButton.disabled = false;
        }
      });
    });
}

// Make sure this function is called when the page loads and after any DOM updates
document.addEventListener('DOMContentLoaded', initCommentForms);

// Also call it after any AJAX updates that might add new comment forms
// For example, if you load more posts dynamically
  
  // Enhanced Profile Tabs
  function initProfileTabs() {
    const tabButtons = document.querySelectorAll('.profile-tab-btn');
    if (tabButtons.length === 0) return;
    
    tabButtons.forEach(button => {
      button.addEventListener('click', function() {
        // Remove active class from all buttons
        tabButtons.forEach(btn => {
          btn.classList.remove('active');
          btn.classList.remove('btn-primary');
          btn.classList.add('btn-outline-primary');
        });
        
        // Add active class to clicked button
        this.classList.add('active');
        this.classList.add('btn-primary');
        this.classList.remove('btn-outline-primary');
        
        // Hide all tab contents
        const tabContents = document.querySelectorAll('.profile-tab-content');
        tabContents.forEach(content => content.classList.add('d-none'));
        
        // Show the selected tab content
        const tabId = this.getAttribute('data-tab');
        document.getElementById(`${tabId}-content`).classList.remove('d-none');
      });
    });
    
    // Activate the first tab by default
    if (tabButtons.length > 0) {
      tabButtons[0].click();
    }
  }
  
  // Friend Request Handlers
  function initFriendRequestHandlers() {
    // Accept friend request
    document.querySelectorAll('.accept-friend-request').forEach(button => {
      button.addEventListener('click', async function(e) {
        e.preventDefault();
        const requestId = this.getAttribute('data-request-id');
        const container = this.closest('.friend-request-item');
        
        try {
          const response = await fetch(`/accept_friend_request/${requestId}/`, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'X-Requested-With': 'XMLHttpRequest',
            }
          });
          
          if (response.ok) {
            // Success animation
            container.classList.add('bg-success-subtle');
            this.textContent = 'Accepted!';
            setTimeout(() => {
              container.remove();
            }, 1000);
            
            // Update friend count if exists
            const friendCountEl = document.getElementById('friend-count');
            if (friendCountEl) {
              const currentCount = parseInt(friendCountEl.textContent);
              friendCountEl.textContent = currentCount + 1;
            }
          }
        } catch (error) {
          console.error('Error accepting friend request:', error);
        }
      });
    });
    
    // Decline friend request
    document.querySelectorAll('.decline-friend-request').forEach(button => {
      button.addEventListener('click', async function(e) {
        e.preventDefault();
        const requestId = this.getAttribute('data-request-id');
        const container = this.closest('.friend-request-item');
        
        try {
          const response = await fetch(`/decline_friend_request/${requestId}/`, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'X-Requested-With': 'XMLHttpRequest',
            }
          });
          
          if (response.ok) {
            // Remove with animation
            container.classList.add('bg-danger-subtle');
            setTimeout(() => {
              container.remove();
            }, 1000);
          }
        } catch (error) {
          console.error('Error declining friend request:', error);
        }
      });
    });
  }
  
  // Search Bar Functionality
  function initSearchBar() {
    const searchForm = document.getElementById('user-search-form');
    const searchInput = document.getElementById('user-search-input');
    const searchResults = document.getElementById('search-results');
    
    if (searchForm && searchInput) {
      searchInput.addEventListener('input', debounce(async function() {
        const query = searchInput.value.trim();
        
        if (query.length < 2) {
          if (searchResults) {
            searchResults.innerHTML = '';
            searchResults.style.display = 'none';
          }
          return;
        }
        
        try {
          const response = await fetch(`/search/users/?q=${encodeURIComponent(query)}`);
          if (response.ok) {
            const html = await response.text();
            if (searchResults) {
              searchResults.innerHTML = html;
              searchResults.style.display = 'block';
            }
          }
        } catch (error) {
          console.error('Error searching users:', error);
        }
      }, 300));
      
      // Hide search results when clicking outside
      document.addEventListener('click', function(e) {
        if (searchResults && !searchForm.contains(e.target)) {
          searchResults.style.display = 'none';
        }
      });
    }
  }
  
  // Utility function to prevent too many requests
  function debounce(func, wait) {
    let timeout;
    return function() {
      const context = this;
      const args = arguments;
      clearTimeout(timeout);
      timeout = setTimeout(() => {
        func.apply(context, args);
      }, wait);
    };
  }