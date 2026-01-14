from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import DigestSettings, DigestLog
from django.utils import timezone

@admin.register(DigestSettings)
class DigestSettingsAdmin(ModelAdmin):
    list_display = [
        'user', 
        'user_is_active',
        'is_enabled', 
        'timezone', 
        'digest_hour',
        'additional_emails_count',
        'custom_filters_enabled',
        'custom_investors_enabled',
        'custom_folders_enabled',
        'created_at'
    ]
    
    list_filter = [
        'is_enabled', 
        'user__is_active',
        'timezone', 
        'digest_hour',
        'custom_filters_enabled',
        'custom_investors_enabled',
        'custom_folders_enabled',
        'created_at'
    ]
    
    search_fields = [
        'user__username', 
        'user__email',
        'additional_emails'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('Main Settings', {
            'fields': [
                'user', 
                'is_enabled'
            ],
            'description': 'Basic digest settings'
        }),
        ('Schedule', {
            'fields': [
                'digest_hour', 
                'timezone'
            ],
            'description': 'When to send digest'
        }),
        ('Email Settings', {
            'fields': ['additional_emails'],
            'description': 'Additional email addresses for digest'
        }),
        ('Content Scope', {
            'fields': [
                'custom_filters_enabled',
                'custom_investors_enabled',
                'custom_folders_enabled'
            ],
            'description': 'Content selection mode (False = All, True = Custom)'
        }),
        ('Metadata', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def additional_emails_count(self, obj):
        """Shows count of additional emails"""
        return len(obj.additional_emails) if obj.additional_emails else 0
    additional_emails_count.short_description = 'Additional Emails'
    additional_emails_count.admin_order_field = 'additional_emails'
    
    def get_digest_time_display(self, obj):
        """Shows digest time in readable format"""
        return f"{obj.digest_hour:02d}:00"
    get_digest_time_display.short_description = 'Digest Time'
    get_digest_time_display.admin_order_field = 'digest_hour'
    
    def user_is_active(self, obj):
        """Shows user active status with color coding"""
        if obj.user.is_active:
            return "✅ Active"
        else:
            return "❌ Inactive"
    user_is_active.short_description = 'User Status'
    user_is_active.admin_order_field = 'user__is_active'
    
    # Custom actions
    actions = ['enable_digest', 'disable_digest']
    
    def enable_digest(self, request, queryset):
        """Enable digest for selected users"""
        updated = queryset.update(is_enabled=True)
        self.message_user(request, f'Enabled digest for {updated} users.')
    enable_digest.short_description = 'Enable digest for selected users'
    
    def disable_digest(self, request, queryset):
        """Disable digest for selected users"""
        updated = queryset.update(is_enabled=False)
        self.message_user(request, f'Disabled digest for {updated} users.')
    disable_digest.short_description = 'Disable digest for selected users'


@admin.register(DigestLog)
class DigestLogAdmin(ModelAdmin):
    list_display = [
        'user',
        'recipient_email',
        'status',
        'scheduled_for',
        'sent_at',
        'subject_preview',
        'user_data_summary',
        'created_at'
    ]
    
    list_filter = [
        'status',
        'scheduled_for',
        'sent_at',
        'created_at'
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'recipient_email',
        'subject',
        'error_message'
    ]
    
    readonly_fields = [
        'user',
        'recipient_email',
        'subject',
        'user_data_snapshot',
        'status',
        'sent_at',
        'scheduled_for',
        'error_message',
        'created_at'
    ]
    
    fieldsets = [
        ('Email Details', {
            'fields': [
                'user',
                'recipient_email',
                'subject',
                'status'
            ],
            'description': 'Basic email information'
        }),
        ('Timing', {
            'fields': [
                'scheduled_for',
                'sent_at',
                'created_at'
            ],
            'description': 'When email was scheduled and sent'
        }),
        ('User Data Snapshot', {
            'fields': ['user_data_snapshot'],
            'description': 'User settings at time of sending',
            'classes': ['collapse']
        }),
        ('Error Information', {
            'fields': ['error_message'],
            'description': 'Error details if sending failed',
            'classes': ['collapse']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def subject_preview(self, obj):
        """Shows subject with character limit"""
        if not obj.subject:
            return "No subject"
        
        if len(obj.subject) <= 50:
            return obj.subject
        
        return obj.subject[:50] + "..."
    subject_preview.short_description = 'Subject'
    subject_preview.admin_order_field = 'subject'
    
    def user_data_summary(self, obj):
        """Shows summary of user data"""
        return obj.get_user_data_summary()
    user_data_summary.short_description = 'User Data'
    
    # Custom actions
    actions = ['mark_as_sent', 'mark_as_failed', 'resend_digest']
    
    def mark_as_sent(self, request, queryset):
        """Mark selected logs as sent"""
        updated = 0
        for log in queryset:
            if log.status == 'PENDING':
                log.mark_as_sent()
                updated += 1
        
        self.message_user(request, f'Marked {updated} logs as sent.')
    mark_as_sent.short_description = 'Mark as sent'
    
    def mark_as_failed(self, request, queryset):
        """Mark selected logs as failed"""
        updated = 0
        for log in queryset:
            if log.status == 'PENDING':
                log.mark_as_failed("Manually marked as failed")
                updated += 1
        
        self.message_user(request, f'Marked {updated} logs as failed.')
    mark_as_failed.short_description = 'Mark as failed'
    
    def resend_digest(self, request, queryset):
        """Create new digest logs for failed sends"""
        created = 0
        for log in queryset:
            if log.status == 'FAILED':
                # Create new log entry for resending
                DigestLog.objects.create(
                    user=log.user,
                    recipient_email=log.recipient_email,
                    subject=log.subject,
                    user_data_snapshot=log.user_data_snapshot,
                    scheduled_for=timezone.now(),
                    status='PENDING'
                )
                created += 1
        
        self.message_user(request, f'Created {created} new digest logs for resending.')
    resend_digest.short_description = 'Resend failed digests'
    
    # Make it read-only by default
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
