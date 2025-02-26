document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".like-button").forEach(button => {
        button.addEventListener("click", function (event) {
            event.preventDefault(); // Stop page from reloading

            let postId = this.getAttribute("data-post-id");

            fetch(`/like_post/${postId}/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCSRFToken(),
                    "Content-Type": "application/json"
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.likes !== undefined) {
                    document.getElementById(`like-count-${postId}`).innerText = data.likes;
                }
            })
            .catch(error => console.error("Error:", error));
        });
    });
});

function getCSRFToken() {
    let csrfToken = document.querySelector("input[name=csrfmiddlewaretoken]");
    return csrfToken ? csrfToken.value : "";
}

