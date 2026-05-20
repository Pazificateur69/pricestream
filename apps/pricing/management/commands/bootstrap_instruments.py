from django.conf import settings
from django.core.management.base import BaseCommand

from apps.pricing.models import Instrument


class Command(BaseCommand):
    help = "Create the default Instrument rows declared in settings.INSTRUMENTS."

    def handle(self, *args, **options):
        created = 0
        for symbol in settings.INSTRUMENTS:
            base, quote = Instrument.parse_symbol(symbol)
            _, was_created = Instrument.objects.get_or_create(
                symbol=symbol, defaults={"base": base, "quote": quote}
            )
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(f"Instruments OK ({created} created, {len(settings.INSTRUMENTS)} total).")
        )
