from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import smtplib
import socket

class Command(BaseCommand):
    help = 'Test email sending configuration'

    def add_arguments(self, parser):
        parser.add_argument('to_email', type=str, nargs='?', help='Email address to send the test message to')

    def handle(self, *args, **options):
        to_email = options['to_email'] or settings.EMAIL_HOST_USER
        if not to_email:
            self.stdout.write(self.style.ERROR('No target email provided and EMAIL_HOST_USER is empty.'))
            return

        to_email = 'wagnercateb@gmail.com'
        print('enviando email para: ', to_email)
        self.stdout.write(f"Attempting to send email to: {to_email}")
        self.stdout.write("Configuration:")
        self.stdout.write(f"  EMAIL_HOST: {settings.EMAIL_HOST}")
        self.stdout.write(f"  EMAIL_PORT: {settings.EMAIL_PORT}")
        self.stdout.write(f"  EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        
        try:
            send_mail(
                'VoteBem - Teste de Email',
                'Este é um email de teste para verificar a configuração SMTP.',
                settings.DEFAULT_FROM_EMAIL,
                [to_email],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS('Email sent successfully!'))
        except smtplib.SMTPAuthenticationError as e:
            self.stdout.write(self.style.ERROR(f'SMTP Authentication Error: {e}'))
            self.stdout.write(self.style.WARNING('Check your EMAIL_HOST_USER and EMAIL_HOST_PASSWORD.'))
        except smtplib.SMTPConnectError as e:
            self.stdout.write(self.style.ERROR(f'SMTP Connection Error: {e}'))
            self.stdout.write(self.style.WARNING('Check EMAIL_HOST and EMAIL_PORT.'))
        except socket.gaierror as e:
            self.stdout.write(self.style.ERROR(f'DNS Error: {e}'))
            self.stdout.write(self.style.WARNING('Could not resolve EMAIL_HOST.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An unexpected error occurred: {type(e).__name__}: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
