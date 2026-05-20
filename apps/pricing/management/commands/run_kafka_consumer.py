from django.core.management.base import BaseCommand

from apps.pricing.kafka_consumer import run_consumer


class Command(BaseCommand):
    help = "Run the Kafka consumer that builds OHLCBars from the quotes topic."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Kafka consumer..."))
        run_consumer()
