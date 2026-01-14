from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import json

User = get_user_model()

class DigestSettings(models.Model):
    """
    Digest settings for user notifications
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='digest_settings',
        verbose_name="User"
    )
    
    # Main settings
    is_enabled = models.BooleanField(
        default=False,
        help_text="Enable/disable digest notifications",
        verbose_name="Digest enabled"
    )
    
    # Time selection (hours)
    HOUR_CHOICES = [
        (0, '00:00'), (1, '01:00'), (2, '02:00'), (3, '03:00'), (4, '04:00'),
        (5, '05:00'), (6, '06:00'), (7, '07:00'), (8, '08:00'), (9, '09:00'),
        (10, '10:00'), (11, '11:00'), (12, '12:00'), (13, '13:00'), (14, '14:00'),
        (15, '15:00'), (16, '16:00'), (17, '17:00'), (18, '18:00'), (19, '19:00'),
        (20, '20:00'), (21, '21:00'), (22, '22:00'), (23, '23:00'),
    ]
    
    digest_hour = models.IntegerField(
        choices=HOUR_CHOICES,
        default=8,
        help_text="Hour to receive digest",
        verbose_name="Digest time"
    )
    
    # Timezone choices by cities
    TIMEZONE_CHOICES = [
        ('Europe/Moscow', 'Moscow (UTC+3)'),
        ('Europe/London', 'London (UTC+0/+1)'),
        ('Europe/Berlin', 'Berlin (UTC+1/+2)'),
        ('Europe/Paris', 'Paris (UTC+1/+2)'),
        ('Europe/Rome', 'Rome (UTC+1/+2)'),
        ('Europe/Madrid', 'Madrid (UTC+1/+2)'),
        ('Europe/Amsterdam', 'Amsterdam (UTC+1/+2)'),
        ('Europe/Zurich', 'Zurich (UTC+1/+2)'),
        ('Europe/Vienna', 'Vienna (UTC+1/+2)'),
        ('Europe/Prague', 'Prague (UTC+1/+2)'),
        ('Europe/Warsaw', 'Warsaw (UTC+1/+2)'),
        ('Europe/Kiev', 'Kiev (UTC+2/+3)'),
        ('Europe/Athens', 'Athens (UTC+2/+3)'),
        ('Europe/Istanbul', 'Istanbul (UTC+3)'),
        ('Asia/Dubai', 'Dubai (UTC+4)'),
        ('Asia/Tashkent', 'Tashkent (UTC+5)'),
        ('Asia/Almaty', 'Almaty (UTC+6)'),
        ('Asia/Shanghai', 'Shanghai (UTC+8)'),
        ('Asia/Tokyo', 'Tokyo (UTC+9)'),
        ('Asia/Seoul', 'Seoul (UTC+9)'),
        ('Asia/Singapore', 'Singapore (UTC+8)'),
        ('Asia/Hong_Kong', 'Hong Kong (UTC+8)'),
        ('Asia/Bangkok', 'Bangkok (UTC+7)'),
        ('Asia/Jakarta', 'Jakarta (UTC+7)'),
        ('Asia/Kolkata', 'Mumbai (UTC+5:30)'),
        ('Asia/Karachi', 'Karachi (UTC+5)'),
        ('Asia/Tehran', 'Tehran (UTC+3:30)'),
        ('Asia/Riyadh', 'Riyadh (UTC+3)'),
        ('Africa/Cairo', 'Cairo (UTC+2)'),
        ('Africa/Johannesburg', 'Johannesburg (UTC+2)'),
        ('Africa/Lagos', 'Lagos (UTC+1)'),
        ('Africa/Casablanca', 'Casablanca (UTC+0/+1)'),
        ('America/New_York', 'New York (UTC-5/-4)'),
        ('America/Chicago', 'Chicago (UTC-6/-5)'),
        ('America/Denver', 'Denver (UTC-7/-6)'),
        ('America/Los_Angeles', 'Los Angeles (UTC-8/-7)'),
        ('America/Toronto', 'Toronto (UTC-5/-4)'),
        ('America/Vancouver', 'Vancouver (UTC-8/-7)'),
        ('America/Sao_Paulo', 'São Paulo (UTC-3)'),
        ('America/Buenos_Aires', 'Buenos Aires (UTC-3)'),
        ('America/Mexico_City', 'Mexico City (UTC-6/-5)'),
        ('America/Lima', 'Lima (UTC-5)'),
        ('America/Bogota', 'Bogotá (UTC-5)'),
        ('America/Santiago', 'Santiago (UTC-3/-4)'),
        ('Pacific/Auckland', 'Auckland (UTC+12/+13)'),
        ('Pacific/Sydney', 'Sydney (UTC+10/+11)'),
        ('Pacific/Melbourne', 'Melbourne (UTC+10/+11)'),
        ('Pacific/Honolulu', 'Honolulu (UTC-10)'),
        ('UTC', 'UTC (UTC+0)'),
    ]
    
    timezone = models.CharField(
        max_length=50,
        choices=TIMEZONE_CHOICES,
        default='America/New_York',
        help_text="User's timezone",
        verbose_name="Timezone"
    )
    
    # Additional email addresses
    additional_emails = models.JSONField(
        default=list,
        blank=True,
        help_text="List of additional email addresses for digest",
        verbose_name="Additional emails"
    )
    
    # Custom content settings (opposite of "all")
    custom_filters_enabled = models.BooleanField(
        default=False,
        help_text="Enable custom filter selection (if False, include all filters)",
        verbose_name="Custom Filters Enabled"
    )
    
    custom_investors_enabled = models.BooleanField(
        default=False,
        help_text="Enable custom investor selection (if False, include all investors)",
        verbose_name="Custom Investors Enabled"
    )
    
    custom_folders_enabled = models.BooleanField(
        default=False,
        help_text="Enable custom folder selection (if False, include all folders)",
        verbose_name="Custom Folders Enabled"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated")
    
    class Meta:
        verbose_name = "Digest Settings"
        verbose_name_plural = "Digest Settings"
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_enabled']),
            models.Index(fields=['timezone']),
            models.Index(fields=['custom_filters_enabled']),
            models.Index(fields=['custom_investors_enabled']),
            models.Index(fields=['custom_folders_enabled']),
        ]
    
    def __str__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"Digest for {self.user.username} ({status})"


class DigestLog(models.Model):
    """
    Log of digest emails sent to users
    """
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
    ]
    
    # User and digest info
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='digest_logs',
        verbose_name="User"
    )
    
    # Email details
    recipient_email = models.EmailField(
        help_text="Email address where digest was sent",
        verbose_name="Recipient Email"
    )
    
    subject = models.CharField(
        max_length=255,
        help_text="Email subject line",
        verbose_name="Subject"
    )
    
    
    # User data snapshot
    user_data_snapshot = models.JSONField(
        default=dict,
        help_text="User data at time of sending (settings, preferences, etc.)",
        verbose_name="User Data Snapshot"
    )
    
    # Status and timing
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text="Status of email delivery",
        verbose_name="Status"
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When email was actually sent",
        verbose_name="Sent At"
    )
    
    scheduled_for = models.DateTimeField(
        help_text="When email was scheduled to be sent",
        verbose_name="Scheduled For"
    )
    
    # Error handling
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error message if sending failed",
        verbose_name="Error Message"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created")
    
    class Meta:
        verbose_name = "Digest Log"
        verbose_name_plural = "Digest Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['sent_at']),
            models.Index(fields=['scheduled_for']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'status']),
        ]
    
    def __str__(self):
        return f"Digest for {self.user.username} - {self.status}"
    
    def mark_as_sent(self):
        """Mark digest as successfully sent"""
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_failed(self, error_message=None):
        """Mark digest as failed to send"""
        self.status = 'FAILED'
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['status', 'error_message'])
    
    def get_user_data_summary(self):
        """Returns a summary of user data for display"""
        if not self.user_data_snapshot:
            return "No data"
        
        summary = []
        if 'timezone' in self.user_data_snapshot:
            summary.append(f"TZ: {self.user_data_snapshot['timezone']}")
        if 'digest_hour' in self.user_data_snapshot:
            summary.append(f"Time: {self.user_data_snapshot['digest_hour']}:00")
        if 'additional_emails' in self.user_data_snapshot:
            count = len(self.user_data_snapshot['additional_emails'])
            if count > 0:
                summary.append(f"+{count} emails")
        
        return " | ".join(summary) if summary else "Basic settings"


# Signal to automatically create digest settings when user is created
@receiver(post_save, sender=User)
def create_digest_settings(sender, instance, created, **kwargs):
    """
    Automatically creates digest settings for new user
    """
    if created:
        DigestSettings.objects.create(user=instance)


# Signal to automatically disable digest when user is deactivated
@receiver(pre_save, sender=User)
def disable_digest_on_user_deactivation(sender, instance, **kwargs):
    """
    Automatically disables digest notifications when user is deactivated
    """
    if instance.pk:  # Only for existing users, not new ones
        try:
            # Get the current state from database
            old_instance = User.objects.get(pk=instance.pk)
            
            # Check if user is being deactivated (is_active changed from True to False)
            if old_instance.is_active and not instance.is_active:
                # Disable digest settings for this user
                try:
                    digest_settings = DigestSettings.objects.get(user=instance)
                    if digest_settings.is_enabled:
                        digest_settings.is_enabled = False
                        digest_settings.save(update_fields=['is_enabled'])
                        print(f"DEBUG: Digest disabled for deactivated user {instance.username}")
                except DigestSettings.DoesNotExist:
                    # No digest settings exist, nothing to do
                    pass
            
            # Check if user is being activated (is_active changed from False to True)
            elif not old_instance.is_active and instance.is_active:
                # Note: We don't automatically enable digest when user is activated
                # because they might have intentionally disabled it before deactivation
                print(f"DEBUG: User {instance.username} activated - digest remains in current state")
                    
        except User.DoesNotExist:
            # User doesn't exist yet (shouldn't happen with pre_save)
            pass