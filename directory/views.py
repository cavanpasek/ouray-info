import json
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg, Count, Q
from django.db.models.functions import Coalesce

from .models import Business, Review

GOOGLE_CACHE_TTL = 300
_google_cache = {}

def _annotate_reviews(queryset):
    return queryset.annotate(
        avg_rating=Coalesce(
            Avg("reviews__rating", filter=Q(reviews__is_approved=True)), 0.0
        ),
        review_count=Count("reviews", filter=Q(reviews__is_approved=True)),
    )


def _rating_to_percent(rating):
    if not rating:
        return 0
    fill = float(rating) / 5
    rounded = round(fill / 0.05) * 0.05
    return round(rounded * 100, 2)


def get_google_place_data(place_id):
    defaults = {
        "google_rating": None,
        "google_count": None,
        "google_reviews": [],
        "google_url": None,
        "google_error": None,
        "google_http_status": "none",
        "google_error_label": "",
    }

    if not place_id or not settings.GOOGLE_MAPS_API_KEY:
        return defaults

    now = time.time()
    cached = _google_cache.get(place_id)
    if cached and (now - cached["ts"] < GOOGLE_CACHE_TTL):
        return cached["data"]

    try:
        query = urllib.parse.urlencode(
            {
                "place_id": place_id,
                "fields": "rating,user_ratings_total,reviews,url,name",
                "key": settings.GOOGLE_MAPS_API_KEY,
            }
        )
        url = f"https://maps.googleapis.com/maps/api/place/details/json?{query}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if settings.DEBUG:
            print(f"[google] place_id={place_id} http_status={exc.code} error=HTTPError")
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""

        status_label = ""
        message_label = ""
        try:
            payload = json.loads(body) if body else {}
            if isinstance(payload, dict):
                if "error" in payload and isinstance(payload["error"], dict):
                    status_label = payload["error"].get("status", "") or ""
                    message_label = payload["error"].get("message", "") or ""
                else:
                    status_label = payload.get("status", "") or ""
                    message_label = payload.get("error_message", "") or ""
        except json.JSONDecodeError:
            payload = {}

        label_parts = []
        if status_label:
            label_parts.append(status_label)
        if message_label:
            label_parts.append(message_label)
        label = ": ".join(label_parts) if label_parts else "HTTPError"
        if len(label) > 140:
            label = label[:137] + "..."

        defaults["google_error"] = "http_error"
        defaults["google_http_status"] = exc.code
        defaults["google_error_label"] = label
        return defaults
    except urllib.error.URLError as exc:
        if settings.DEBUG:
            print(f"[google] place_id={place_id} http_status=none error=URLError")
        defaults["google_error"] = "url_error"
        defaults["google_http_status"] = "none"
        defaults["google_error_label"] = "URLError"
        return defaults
    except json.JSONDecodeError:
        if settings.DEBUG:
            print(f"[google] place_id={place_id} http_status=none error=JSONDecodeError")
        defaults["google_error"] = "json_error"
        defaults["google_http_status"] = "none"
        defaults["google_error_label"] = "JSONDecodeError"
        return defaults
    except Exception:
        if settings.DEBUG:
            print(f"[google] place_id={place_id} http_status=none error=Exception")
        defaults["google_error"] = "unknown_error"
        defaults["google_http_status"] = "none"
        defaults["google_error_label"] = "Exception"
        return defaults

    status_text = payload.get("status")
    if status_text and status_text != "OK":
        message = payload.get("error_message", "")
        label = f"{status_text}: {message}".strip(": ")
        if len(label) > 140:
            label = label[:137] + "..."
        defaults["google_error"] = "api_error"
        defaults["google_http_status"] = 200
        defaults["google_error_label"] = label or status_text
        return defaults

    result = payload.get("result") or {}

    data = {
        "google_rating": result.get("rating"),
        "google_count": result.get("user_ratings_total"),
        "google_reviews": [],
        "google_url": result.get("url"),
        "google_error": None,
        "google_http_status": 200,
        "google_error_label": "",
    }

    for review in result.get("reviews", []) or []:
        text_payload = review.get("text")
        if isinstance(text_payload, dict):
            text_value = text_payload.get("text")
        else:
            text_value = text_payload

        data["google_reviews"].append(
            {
                "rating": review.get("rating"),
                "author": (review.get("authorAttribution") or {}).get("displayName"),
                "relative_time": review.get("relativePublishTimeDescription"),
                "text": text_value,
                "google_maps_uri": review.get("googleMapsUri"),
            }
        )

    _google_cache[place_id] = {"ts": now, "data": data}
    return data


def _attach_google_summaries(businesses):
    for b in businesses:
        b.ouray_fill_percent = _rating_to_percent(getattr(b, "avg_rating", 0))
        b.google_rating = None
        b.google_user_count = None
        b.google_fill_percent = None
        b.google_maps_uri = None
        if b.google_place_id:
            google = get_google_place_data(b.google_place_id)
            if google.get("google_rating") is not None:
                b.google_rating = google.get("google_rating")
                b.google_user_count = google.get("google_count") or 0
                b.google_fill_percent = _rating_to_percent(b.google_rating)
                b.google_maps_uri = google.get("google_url")


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
    businesses = list(_annotate_reviews(Business.objects.all()))

    _attach_google_summaries(businesses)

    if sort == "az":
        businesses.sort(key=lambda b: (b.name,))
    elif sort == "google":
        businesses.sort(
            key=lambda b: (
                -(b.google_rating or 0),
                -(b.google_user_count or 0),
                b.name,
            )
        )
    else:
        sort = "top"
        businesses.sort(key=lambda b: (-(b.avg_rating or 0), -b.review_count, b.name))

    return render(request, "home.html", {"businesses": businesses, "sort": sort})

def business_detail(request, slug):
    b = get_object_or_404(Business, slug=slug)
    approved_reviews = b.reviews.filter(is_approved=True)
    stats = approved_reviews.aggregate(avg=Avg("rating"), count=Count("id"))
    avg_rating = stats["avg"] or 0
    review_count = stats["count"] or 0
    reviews = list(approved_reviews)
    is_bookmarked = b.id in _get_bookmark_ids(request)
    google_place_id = b.google_place_id or ""
    google = get_google_place_data(google_place_id)
    google_reviews = google.get("google_reviews", [])

    combined_reviews = []
    for review in google_reviews:
        combined_reviews.append(
            {
                "source": "google",
                "rating": review.get("rating"),
                "name": review.get("author"),
                "date": review.get("relative_time"),
                "comment": review.get("text"),
                "google_maps_uri": review.get("google_maps_uri"),
            }
        )
    for review in reviews:
        if len(combined_reviews) >= 20:
            break
        combined_reviews.append(
            {
                "source": "ouray",
                "rating": review.rating,
                "name": review.name,
                "date": review.created_at,
                "comment": review.comment,
            }
        )

    ouray_fill_percent = _rating_to_percent(avg_rating)
    google_rating = google.get("google_rating")
    google_user_count = google.get("google_count") or 0
    google_fill_percent = _rating_to_percent(google_rating)
    google_maps_uri = google.get("google_url")
    context = {
        "b": b,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "combined_reviews": combined_reviews[:20],
        "site_key": settings.RECAPTCHA_SITE_KEY,
        "is_bookmarked": is_bookmarked,
        "review_form": {"rating": "", "name": "", "email": "", "comment": ""},
        "ouray_fill_percent": ouray_fill_percent,
        "google_rating": google_rating,
        "google_user_count": google_user_count,
        "google_fill_percent": google_fill_percent,
        "google_maps_uri": google_maps_uri,
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
    reviews = list(approved_reviews)
    is_bookmarked = b.id in _get_bookmark_ids(request)
    google = get_google_place_data(b.google_place_id)
    google_reviews = google.get("google_reviews", [])

    combined_reviews = []
    for review in google_reviews:
        combined_reviews.append(
            {
                "source": "google",
                "rating": review.get("rating"),
                "name": review.get("author"),
                "date": review.get("relative_time"),
                "comment": review.get("text"),
                "google_maps_uri": review.get("google_maps_uri"),
            }
        )
    for review in reviews:
        if len(combined_reviews) >= 20:
            break
        combined_reviews.append(
            {
                "source": "ouray",
                "rating": review.rating,
                "name": review.name,
                "date": review.created_at,
                "comment": review.comment,
            }
        )

    ouray_fill_percent = _rating_to_percent(avg_rating)
    google_rating = google.get("google_rating")
    google_user_count = google.get("google_count") or 0
    google_fill_percent = _rating_to_percent(google_rating)
    google_maps_uri = google.get("google_url")

    context = {
        "b": b,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "combined_reviews": combined_reviews[:20],
        "site_key": settings.RECAPTCHA_SITE_KEY,
        "is_bookmarked": is_bookmarked,
        "review_form": {
            "rating": rating_raw,
            "name": name,
            "email": email,
            "comment": comment,
        },
        "ouray_fill_percent": ouray_fill_percent,
        "google_rating": google_rating,
        "google_user_count": google_user_count,
        "google_fill_percent": google_fill_percent,
        "google_maps_uri": google_maps_uri,
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
    businesses = list(
        _annotate_reviews(Business.objects.filter(id__in=bookmark_ids)).order_by(
            "-avg_rating", "-review_count", "name"
        )
    )
    _attach_google_summaries(businesses)
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
