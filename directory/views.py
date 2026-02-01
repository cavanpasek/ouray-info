import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.shortcuts import render, get_object_or_404
from .models import Business

def home(request):
    businesses = Business.objects.all()
    return render(request, "home.html", {"businesses": businesses})

def business_detail(request, slug):
    b = get_object_or_404(Business, slug=slug)
    return render(request, "business_detail.html", {"b": b})


def contact(request):
    context = {"site_key": settings.RECAPTCHA_SITE_KEY}

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()
        recaptcha_response = request.POST.get("g-recaptcha-response", "")

        context.update({"name": name, "email": email, "message": message})

        if not settings.RECAPTCHA_SITE_KEY or not settings.RECAPTCHA_SECRET_KEY:
            context["error"] = "reCAPTCHA is not configured. Please try again later."
            return render(request, "directory/contact.html", context)

        if not recaptcha_response:
            context["error"] = "Please complete the reCAPTCHA to submit the form."
            return render(request, "directory/contact.html", context)

        payload = urllib.parse.urlencode(
            {
                "secret": settings.RECAPTCHA_SECRET_KEY,
                "response": recaptcha_response,
                "remoteip": request.META.get("REMOTE_ADDR", ""),
            }
        ).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://www.google.com/recaptcha/api/siteverify",
                data=payload,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ValueError):
            context["error"] = "Verification failed. Please try again."
            return render(request, "directory/contact.html", context)

        if not data.get("success"):
            context["error"] = "reCAPTCHA verification failed. Please try again."
            return render(request, "directory/contact.html", context)

        context["success"] = "Thanks! Your message has been received."
        return render(request, "directory/contact.html", context)

    return render(request, "directory/contact.html", context)
