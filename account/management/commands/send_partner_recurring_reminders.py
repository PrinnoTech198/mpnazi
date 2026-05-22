from django.core.management.base import BaseCommand

from account.partner_recurring_reminders import process_due_partner_recurring_reminders


class Command(BaseCommand):
    help = "Send push reminders for due recurring partner giving schedules."

    def handle(self, *args, **options):
        count = process_due_partner_recurring_reminders()
        self.stdout.write(self.style.SUCCESS(f"Processed {count} recurring reminder(s)."))
