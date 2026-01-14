from django.core.management.base import BaseCommand
from notifications.management.utils.digest_manager import DigestManager
from notifications.models import DigestSettings


class Command(BaseCommand):
    help = 'Send digest emails to all users who are ready to receive them'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what will be sent without actual sending'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Send digest only to a specific user (by ID)'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_id = options.get('user_id')
        
        if user_id:
            try:
                settings = DigestSettings.objects.get(user_id=user_id)
                digest_settings = [settings] if (settings.is_enabled and 
                                               DigestManager.is_digest_time_reached(settings) and 
                                               not DigestManager.was_digest_sent_today(settings)) else []
            except DigestSettings.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ User with ID {user_id} not found"))
                return
        else:
            digest_settings = DigestManager.get_digest_settings_ready_for_sending()
            
        if not digest_settings:
            self.stdout.write("No digest ready to send")
            return
        
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write("DIGEST SENDING")
        self.stdout.write("="*50)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 DRY RUN MODE - emails will not be sent"))
        
        success_count = 0
        total_count = len(digest_settings)
        
        for settings in digest_settings:
            user = settings.user
            self.stdout.write(f"\n👤 Processing digest for {user.username} ({user.email})")
            
            if dry_run:
                groups = DigestManager.serialize_digest_groups(settings)
                
                if groups:
                    self.stdout.write(f"   📊 Groups to send: {len(groups)}")
                    for group in groups:
                        group_type = group.get('type', 'default')
                        cards_count = len(group.get('cards', []))
                        title = group.get('title', 'Unknown')
                        
                        if group_type == 'update':
                            self.stdout.write(f"   📈 {title} - {cards_count} updates")
                        else:
                            self.stdout.write(f"   📋 {title} - {cards_count} cards")
                    
                    self.stdout.write("   ✅ Ready to send")
                    success_count += 1
                else:
                    self.stdout.write("   ⚠️  No content to send")
            else:
                success = DigestManager.send_digest_email(settings)
                if success:
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS("   ✅ Email sent successfully"))
                else:
                    self.stdout.write(self.style.ERROR("   ❌ Email sending failed"))
        
        self.stdout.write(f"\n{'='*50}")
        if dry_run:
            self.stdout.write(f"Review completed: {success_count}/{total_count} ready to send")
        else:
            self.stdout.write(f"Sending completed: {success_count}/{total_count} successfully sent") 