import hashlib
import feedparser
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import strip_tags
import datetime

from directory.models import NewsPost

RSS_FEEDS = [
    {
        "name": "Ouray County News",
        "url": "https://ouraycountyco.gov/RSSFeed.aspx?ModID=1&CID=Ouray-County-News-Flash-Items-8",
    },
    {
        "name": "Ouray County Alerts",
        "url": "https://ouraycountyco.gov/RSSFeed.aspx?ModID=63&CID=All-0",
    },
]


def _to_datetime(struct_time):
    if struct_time:
        try:
            return datetime.datetime(*struct_time[:6], tzinfo=datetime.timezone.utc)
        except Exception:
            pass
    return timezone.now()


class Command(BaseCommand):
    help = "Fetch news from configured RSS feeds"

    def handle(self, *args, **options):
        created = 0
        for feed_cfg in RSS_FEEDS:
            feed = feedparser.parse(feed_cfg["url"])
            if feed.bozo and not feed.entries:
                self.stderr.write(f"[{feed_cfg['name']}] failed: {feed.bozo_exception}")
                continue

            for entry in feed.entries:
                title = (entry.get("title") or "").strip()
                link = entry.get("link", "")
                summary = strip_tags(entry.get("summary") or entry.get("description") or "").strip()
                guid_raw = entry.get("id") or link or title
                guid = hashlib.sha256(guid_raw.encode()).hexdigest()
                published_at = _to_datetime(entry.get("published_parsed") or entry.get("updated_parsed"))

                if not title or NewsPost.objects.filter(guid=guid).exists():
                    continue

                NewsPost.objects.create(
                    title=title,
                    summary=summary[:1000],
                    source_name=feed_cfg["name"],
                    source_url=link,
                    guid=guid,
                    published_at=published_at,
                )
                created += 1
                self.stdout.write(f"  + {title[:80]}")

        self.stdout.write(self.style.SUCCESS(f"Done — {created} new posts imported."))
