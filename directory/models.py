from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

# Primary directory listing model.
class Business(models.Model):
    # Core business identity and display fields.
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    # Optional metadata used throughout the UI.
    category = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    deal_text = models.CharField(max_length=200, blank=True)
    address = models.CharField(max_length=300, blank=True)
    hero_image = models.ImageField(upload_to="business_hero/", blank=True, null=True)
    logo_image = models.ImageField(upload_to="business_logos/", blank=True, null=True)
    google_place_id = models.CharField(max_length=200, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Auto-generate the slug from the name when not provided.
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        # Human-readable label in the admin and shell.
        return self.name


# User-submitted review for a business listing.
class Review(models.Model):
    # Relationship and rating fields.
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    # Optional reviewer identity and required comment.
    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    comment = models.TextField(max_length=1000)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Show newest reviews first in default query order.
        ordering = ["-created_at"]

    def __str__(self):
        # Compact admin display label.
        return f"{self.business.name} ({self.rating})"
