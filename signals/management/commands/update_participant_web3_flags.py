from django.core.management.base import BaseCommand
from signals.models import Participant, Signal, Category


class Command(BaseCommand):
    help = 'Update participant has_web3 flag based on their signals'

    def handle(self, *args, **options):
        self.stdout.write('Updating participant has_web3/has_web2 flags...')
        
        # Получаем всех участников с сигналами
        participants = Participant.objects.filter(signals__isnull=False).distinct()
        total_participants = participants.count()
        
        self.stdout.write(f'Found {total_participants} participants to process')
        
        updated_count = 0
        batch_size = 1000
        
        # Обрабатываем батчами
        for batch_start in range(0, total_participants, batch_size):
            batch_end = min(batch_start + batch_size, total_participants)
            batch_participants = participants[batch_start:batch_end]
            
            self.stdout.write(f'Processing batch {batch_start//batch_size + 1}/{(total_participants + batch_size - 1)//batch_size} (participants {batch_start + 1}-{batch_end})')
            
            for i, participant in enumerate(batch_participants, batch_start + 1):
                try:
                    # Сбрасываем флаги
                    participant.has_web3 = False
                    participant.has_web2 = False
                    
                    # Получаем все сигналы участника
                    signals = Signal.objects.filter(
                        participant=participant,
                        signal_card__is_open=True
                    ).select_related('signal_card')
                    
                    # Проверяем, есть ли у участника проекты web3 и не-web3
                    for signal in signals:
                        # Чтобы избежать N+1, используем prefetch выше; здесь просто проверяем категории
                        for category in signal.signal_card.categories.all():
                            if category.parent_category and category.parent_category.slug == 'web3':
                                participant.has_web3 = True
                            else:
                                # Любая категория, не находящаяся под web3, считается web2
                                participant.has_web2 = True
                        # Ранний выход, если оба флага установлены
                        if participant.has_web3 and participant.has_web2:
                            break
                    
                    # Сохраняем изменения
                    participant.save(update_fields=['has_web3', 'has_web2'])
                    
                    status = "WEB3+WEB2" if (participant.has_web3 and participant.has_web2) else ("WEB3" if participant.has_web3 else ("WEB2" if participant.has_web2 else "NONE"))
                    self.stdout.write(f'{i}/{total_participants}: {participant.name} - {status}')
                    updated_count += 1
                    
                except Exception as e:
                    self.stdout.write(f'Error processing {participant.name}: {e}')
        
        self.stdout.write(f'Updated {updated_count} participants')
