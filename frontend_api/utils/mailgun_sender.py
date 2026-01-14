import requests
import logging
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class MailgunSender:
    """
    Утилита для отправки email через Mailgun API
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'MAILGUN_API_KEY', None)
        self.domain = getattr(settings, 'MAILGUN_DOMAIN', None)
        self.api_url = f"https://api.mailgun.net/v3/{self.domain}/messages"
        
        if not self.api_key or not self.domain:
            logger.warning("Mailgun credentials not configured. Using fallback email backend.")
    
    def send_email(self, to_email, subject, template_name, context, from_email=None):
        """
        Отправляет email через Mailgun API
        
        Args:
            to_email: Email получателя
            subject: Тема письма
            template_name: Имя Django шаблона (без расширения)
            context: Контекст для шаблона
            from_email: Email отправителя (опционально)
        
        Returns:
            bool: True если email отправлен успешно
        """
        try:
            if not self.api_key or not self.domain:
                logger.warning("Mailgun not configured, skipping email send")
                return False
            
            # Рендерим HTML и текстовую версии письма из общей директории
            html_content = render_to_string(f'emails/{template_name}.html', context)
            text_content = render_to_string(f'emails/{template_name}.txt', context)
            
            # Настройки отправителя
            if not from_email:
                from_email = f"noreply@{self.domain}"
            
            # Данные для Mailgun API
            data = {
                'from': from_email,
                'to': to_email,
                'subject': subject,
                'html': html_content,
                'text': text_content
            }
            
            # Отправляем через Mailgun API
            response = requests.post(
                self.api_url,
                auth=('api', self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email to {to_email}. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    def send_password_reset_email(self, user, reset_url):
        """
        Отправляет email для сброса пароля
        
        Args:
            user: Пользователь Django
            reset_url: Ссылка для сброса пароля
        
        Returns:
            bool: True если email отправлен успешно
        """
        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': 'TheVeck',
            'support_email': 'support@theveck.com'
        }
        
        subject = 'Password Reset Request - TheVeck'
        template_name = 'password_reset/email'
        
        return self.send_email(
            to_email=user.email,
            subject=subject,
            template_name=template_name,
            context=context
        )


# Создаем глобальный экземпляр
mailgun_sender = MailgunSender() 