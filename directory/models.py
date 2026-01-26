from django.db import models
from django.utils.text import slugify

class Business(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    category = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=300, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
