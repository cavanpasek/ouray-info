import os
import anthropic
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test Claude API connection"

    def handle(self, *args, **options):
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        message = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=100,
            messages=[{"role": "user", "content": "Say hello from Ouray, Colorado!"}],
        )
        self.stdout.write(self.style.SUCCESS(message.content[0].text))
