from django import forms
from django.contrib import admin
from django.core.validators import FileExtensionValidator

from .models import Business, Review

# Whitelistinggggggg.
ALLOWED_IMAGE_EXTENSIONS = ["webp", "jpg", "jpeg", "png"]


# Custom admin form to validate image uploads. BLAH Oli, should we omit this entire chunk here since we didn't end up
# going for the images in each individual business page?
class BusinessAdminForm(forms.ModelForm):
    # Validate hero and logo images against allowed extensions. DON'T EVEN THINK THIS IS REFERENCE ANYWHERE.
    hero_image = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)],
    )
    logo_image = forms.ImageField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)],
    )

    class Meta: # keep this for now even we if don't end up using the images.
        model = Business
        fields = "__all__"

# Admin configuration for business listings.
@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin): # creates admin interface using django's method ModelAdmin
    form = BusinessAdminForm
    list_display = ("name", "category", "website", "google_place_id")
    search_fields = ("name", "category")
    prepopulated_fields = {"slug": ("name",)}
    # Explicit field order to keep the edit form predictable.
    fields = (
        "name",
        "slug",
        "category",
        "description",
        "website",
        "phone",
        "deal_text", # omit? don't want to break code though, will leave for now.
        "address",
        "logo_image", # omit?
        "hero_image", # omit?
        "google_place_id",
    )


# Admin configuration for review moderation.
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin): # references django's built in method to create admin interface
    list_display = ("business", "rating", "name", "is_approved", "created_at")
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("business__name", "name", "email", "comment")
