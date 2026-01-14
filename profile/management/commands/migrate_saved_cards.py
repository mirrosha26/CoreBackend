from django.core.management.base import BaseCommand
from profile.models import migrate_saved_cards

class Command(BaseCommand):
    help = 'Миграция данных из SavedCard в FolderCard'

    def handle(self, *args, **options):
        self.stdout.write('Начинаем миграцию данных...')
        migrate_saved_cards()
        self.stdout.write(self.style.SUCCESS('Миграция данных успешно завершена!')) 