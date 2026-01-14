from django.core.management.base import BaseCommand
from signals.models import Participant, Signal


class Command(BaseCommand):
    help = 'Update monthly signals count for all participants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to analyze (default: 30)'
        )
        parser.add_argument(
            '--participant-id',
            type=int,
            help='Update only specific participant by ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update all participants'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for processing (default: 1000)'
        )

    def handle(self, *args, **options):
        days = options['days']
        participant_id = options.get('participant_id')
        force = options['force']
        batch_size = options['batch_size']
        
        self.stdout.write(
            self.style.SUCCESS(f'Updating signals count for the last {days} days...')
        )
        
        if force:
            self.stdout.write(
                self.style.WARNING('⚠️  FORCE MODE: Updating all participants regardless of previous calculations')
            )
        
        # Определяем участников для обновления
        if participant_id:
            participants = Participant.objects.filter(id=participant_id)
            if not participants.exists():
                self.stdout.write(
                    self.style.ERROR(f'Participant with ID {participant_id} not found.')
                )
                return
        else:
            # Получаем всех участников
            participants = Participant.objects.all()
        
        total_participants = participants.count()
        updated_count = 0
        error_count = 0
        zero_signals_count = 0
        
        self.stdout.write(f'Found participants to process: {total_participants}')
        self.stdout.write(f'Batch size: {batch_size}')
        
        # Обрабатываем батчами
        for batch_start in range(0, total_participants, batch_size):
            batch_end = min(batch_start + batch_size, total_participants)
            batch_participants = participants[batch_start:batch_end]
            
            self.stdout.write(
                self.style.SUCCESS(f'\n🔄 Processing batch {batch_start//batch_size + 1}/{(total_participants + batch_size - 1)//batch_size} '
                                 f'(participants {batch_start + 1}-{batch_end})')
            )
            
            for i, participant in enumerate(batch_participants, batch_start + 1):
                try:
                    # Update signals count
                    old_count = participant.monthly_signals_count
                    new_count = participant.update_signals_count(days)
                    
                    if new_count is not None:
                        # Determine participant type
                        is_parent = participant.associated_with is None or participant.pk == participant.associated_with.pk
                        participant_type = "👑" if is_parent else "👤"
                        
                        # Form detailed information
                        assoc_id = participant.associated_with.pk if participant.associated_with else 'None'
                        calculation = f"{new_count} signals"
                        # Align slug to left with fixed width of 20 characters
                        slug_padded = f"{participant.slug:<20}"
                        detail_info = f"{slug_padded} {participant_type}[{participant.pk}/{assoc_id}] ({participant.type}) {calculation}"
                        
                        if new_count == 0:
                            self.stdout.write(
                                f'{i}/{total_participants}:\t{detail_info}'
                            )
                            zero_signals_count += 1
                        else:
                            self.stdout.write(
                                f'{i}/{total_participants}:\t{detail_info}'
                            )
                        updated_count += 1
                    else:
                        self.stdout.write(
                            f'{i}/{total_participants}: {participant.name} - calculation error'
                        )
                        error_count += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'{i}/{total_participants}: {participant.name} - error: {str(e)}'
                        )
                    )
                    error_count += 1
            
            # Show progress after each batch
            self.stdout.write(
                self.style.SUCCESS(f'✅ Batch completed. Progress: {min(batch_end, total_participants)}/{total_participants} '
                                 f'({(min(batch_end, total_participants)/total_participants*100):.1f}%)')
            )
        
        # Final statistics
        self.stdout.write(
            self.style.SUCCESS(f'\n📊 UPDATE RESULTS:')
        )
        self.stdout.write(f'Total participants: {total_participants}')
        self.stdout.write(f'Updated: {updated_count}')
        self.stdout.write(f'Errors: {error_count}')
        
        # Count zero signals participants from database
        zero_signals_in_db = Participant.objects.filter(
            monthly_signals_count=0
        ).count()
        self.stdout.write(f'Participants with zero signals: {zero_signals_in_db}')
        
        # Show top participants by signals count
        top_participants = Participant.objects.filter(
            monthly_signals_count__isnull=False
        ).order_by('-monthly_signals_count')[:10]
        
        # Get statistics for ALL participants
        all_participants = Participant.objects.filter(
            monthly_signals_count__isnull=False
        )
        all_signals_counts = [p.monthly_signals_count for p in all_participants]
        
        if top_participants:
            self.stdout.write(
                self.style.SUCCESS(f'\n🏆 TOP-10 PARTICIPANTS BY SIGNALS COUNT:')
            )
            
            # Show detailed statistics for ALL participants
            self.stdout.write(
                self.style.SUCCESS(f'\n📊 SIGNALS COUNT STATISTICS (ALL PARTICIPANTS):')
            )
            self.stdout.write(f"Total participants with signals: {len(all_signals_counts)}")
            self.stdout.write(f"Average signals count: {sum(all_signals_counts) / len(all_signals_counts):.2f}")
            self.stdout.write(f"Maximum signals: {max(all_signals_counts)}")
            self.stdout.write(f"Minimum signals: {min(all_signals_counts)}")
            self.stdout.write(f"Median of signals: {sorted(all_signals_counts)[len(all_signals_counts)//2]}")
            
            # Analysis of signals count distribution
            high_signals_count = len([p for p in all_signals_counts if p > 10])
            normal_signals_count = len([p for p in all_signals_counts if 1 < p <= 10])
            zero_signals_count = len([p for p in all_signals_counts if p == 0])
            
            self.stdout.write(
                self.style.SUCCESS(f'\n🎯 SIGNALS COUNT ANALYSIS (ALL PARTICIPANTS):')
            )
            self.stdout.write(f"High activity (>10 signals): {high_signals_count} participants")
            self.stdout.write(f"Normal activity (1-10 signals): {normal_signals_count} participants")
            self.stdout.write(f"Zero activity (0 signals): {zero_signals_count} participants")
            
            # List of participants
            self.stdout.write(
                self.style.SUCCESS(f'\n👥 PARTICIPANT LIST:')
            )
            for i, participant in enumerate(top_participants, 1):
                activity_level = ""
                if participant.monthly_signals_count > 10:
                    activity_level = " 🔥 HIGH"
                elif participant.monthly_signals_count > 0:
                    activity_level = " 📊 NORMAL"
                else:
                    activity_level = " ❌ ZERO"
                
                # Determine participant type
                is_parent = participant.associated_with is None or participant.pk == participant.associated_with.pk
                participant_type = "👑 PARENT" if is_parent else "👤 PARTICIPANT"
                
                self.stdout.write(
                    f'{i}. {participant.name} ({participant.type}) - '
                    f'{participant.monthly_signals_count} signals{activity_level} {participant_type}'
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Command completed successfully!')
        ) 