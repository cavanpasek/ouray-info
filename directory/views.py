import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg, Count, Q
from django.db.models.functions import Coalesce

from .models import Business, Review

def _annotate_reviews(queryset):
    return queryset.annotate(
        avg_rating=Coalesce(
            Avg("reviews__rating", filter=Q(reviews__is_approved=True)), 0.0
        ),
        review_count=Count("reviews", filter=Q(reviews__is_approved=True)),
    )


def _get_bookmark_ids(request):
    raw_ids = request.session.get("bookmarks", [])
    return {int(v) for v in raw_ids if str(v).isdigit()}


def _verify_recaptcha(request, recaptcha_response):
    if not settings.RECAPTCHA_SITE_KEY or not settings.RECAPTCHA_SECRET_KEY:
        return False, "reCAPTCHA is not configured. Please try again later."

    if not recaptcha_response:
        return False, "Please complete the reCAPTCHA to submit the form."

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
        return False, "Verification failed. Please try again."

    if not data.get("success"):
        return False, "reCAPTCHA verification failed. Please try again."

    return True, ""


def home(request):
    sort = request.GET.get("sort", "top")
    businesses = _annotate_reviews(Business.objects.all())

    if sort == "most":
        businesses = businesses.order_by("-review_count", "-avg_rating", "name")
    elif sort == "az":
        businesses = businesses.order_by("name")
    else:
        sort = "top"
        businesses = businesses.order_by("-avg_rating", "-review_count", "name")

    return render(request, "home.html", {"businesses": businesses, "sort": sort})

def business_detail(request, slug):
    b = get_object_or_404(Business, slug=slug)
    approved_reviews = b.reviews.filter(is_approved=True)
    stats = approved_reviews.aggregate(avg=Avg("rating"), count=Count("id"))
    avg_rating = stats["avg"] or 0
    review_count = stats["count"] or 0
    reviews = approved_reviews[:8]
    is_bookmarked = b.id in _get_bookmark_ids(request)

    context = {
        "b": b,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "reviews": reviews,
        "site_key": settings.RECAPTCHA_SITE_KEY,
        "is_bookmarked": is_bookmarked,
        "review_form": {"rating": "", "name": "", "email": "", "comment": ""},
    }
    return render(request, "business_detail.html", context)


def review_submit(request, slug):
    if request.method != "POST":
        return redirect("business_detail", slug=slug)

    b = get_object_or_404(Business, slug=slug)
    rating_raw = request.POST.get("rating", "").strip()
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    comment = request.POST.get("comment", "").strip()
    recaptcha_response = request.POST.get("g-recaptcha-response", "")

    approved_reviews = b.reviews.filter(is_approved=True)
    stats = approved_reviews.aggregate(avg=Avg("rating"), count=Count("id"))
    avg_rating = stats["avg"] or 0
    review_count = stats["count"] or 0
    reviews = approved_reviews[:8]
    is_bookmarked = b.id in _get_bookmark_ids(request)

    context = {
        "b": b,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "reviews": reviews,
        "site_key": settings.RECAPTCHA_SITE_KEY,
        "is_bookmarked": is_bookmarked,
        "review_form": {
            "rating": rating_raw,
            "name": name,
            "email": email,
            "comment": comment,
        },
    }

    try:
        rating = int(rating_raw)
    except ValueError:
        rating = 0

    if rating < 1 or rating > 5:
        context["review_error"] = "Please choose a rating between 1 and 5."
        return render(request, "business_detail.html", context)

    if not comment:
        context["review_error"] = "Please add a short comment."
        return render(request, "business_detail.html", context)

    if len(comment) > 1000:
        context["review_error"] = "Comment is too long (1000 characters max)."
        return render(request, "business_detail.html", context)

    ok, error = _verify_recaptcha(request, recaptcha_response)
    if not ok:
        context["review_error"] = error
        return render(request, "business_detail.html", context)

    Review.objects.create(
        business=b,
        rating=rating,
        name=name,
        email=email,
        comment=comment,
    )

    return redirect("business_detail", slug=slug)


def bookmark_toggle(request, slug):
    if request.method != "POST":
        return redirect("business_detail", slug=slug)

    b = get_object_or_404(Business, slug=slug)
    bookmark_ids = _get_bookmark_ids(request)

    if b.id in bookmark_ids:
        bookmark_ids.remove(b.id)
    else:
        bookmark_ids.add(b.id)

    request.session["bookmarks"] = sorted(bookmark_ids)
    return redirect("business_detail", slug=slug)


def bookmarks(request):
    bookmark_ids = _get_bookmark_ids(request)
    businesses = _annotate_reviews(
        Business.objects.filter(id__in=bookmark_ids)
    ).order_by("-avg_rating", "-review_count", "name")
    return render(request, "directory/bookmarks.html", {"businesses": businesses})


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

        if not settings.DEFAULT_FROM_EMAIL or not settings.EMAIL_HOST:
            context["error"] = "Email is not configured. Please try again later."
            return render(request, "directory/contact.html", context)

        subject = "New Ouray Info Contact Form Submission"
        body = (
            f"Name: {name}\n"
            f"Email: {email}\n\n"
            f"Message:\n{message}\n"
        )

        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                settings.CONTACT_RECIPIENTS,
                fail_silently=False,
            )
        except Exception:
            context["error"] = "Email sending failed. Please try again."
            return render(request, "directory/contact.html", context)

        return redirect("contact_success")

    return render(request, "directory/contact.html", context)


def contact_success(request):
    return render(request, "directory/contact_success.html")
