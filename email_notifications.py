import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app_config import get_config

def send_email(subject, body, type):
    "Sends email to recipients specified in config."
    config = get_config()
    email_config = config['email']
    email_notifications = config['system']['email_notifications']

    if not email_notifications:
        print(body)
        return

    server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
    server.starttls()

    for recipient in email_config['to']:
        print(f"==> Sending {type} email to {recipient}.")
        message = MIMEMultipart('alternative')
        message['From'] = email_config['from']
        message['To'] = recipient
        message['Subject'] = subject
        message.attach(MIMEText(body, 'html'))
        text = message.as_string()
        server.sendmail(email_config['from'], recipient, text)

    server.quit()
