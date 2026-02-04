from django.urls import path
from .views import (
    home,
    business_detail,
    contact,
    contact_success,
    review_submit,
    bookmark_toggle,
    bookmarks,
)

# Public routes for the directory app.
urlpatterns = [
    path("", home, name="home"),
    path("contact/", contact, name="contact"),
    path("contact/success/", contact_success, name="contact_success"),
    path("bookmarks/", bookmarks, name="bookmarks"),
    path("business/<slug:slug>/", business_detail, name="business_detail"),
    path("business/<slug:slug>/review/", review_submit, name="review_submit"),
    path("business/<slug:slug>/bookmark/", bookmark_toggle, name="bookmark_toggle"),
]
