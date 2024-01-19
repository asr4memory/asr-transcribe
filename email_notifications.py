"""
Send different kinds of email notifications or reports.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import socket, getpass

from app_config import get_config

computer_host_name = socket.gethostname()
computer_host_ip = socket.gethostbyname(computer_host_name)
current_username = getpass.getuser()

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


def send_success_email(input_file_list, audioduration_list, workflowduration_list, real_time_factor_list, warning_count, warning_word, warning_audio_inputs):
    "Sends a success email."
    config = get_config()
    email_recipients = config['email']['to']
    language_audio = config['whisper']['language']

    email_subject =  "👍 ASR Process Completed! 👍"
    email_body = "<b>ASR Process successfully completed:</b> " + "<br>" + str(input_file_list).replace('[','').replace(']','').replace("'","").replace(",","<br>") + "<br>" + "<br>"
    email_body += "<b>Date of ASR Process:</b> " + datetime.now().strftime('%Y-%m-%d %H-%M-%S') + "<br>" + "<br>"
    email_body += "<b>Whisper audio duration list:</b> " + "<br>" + str(audioduration_list).replace('[','').replace(']','').replace("'","").replace(",","<br>") + "<br>" + "<br>"
    email_body += "<b>Whisper workflow duration list:</b> " + "<br>" + str(workflowduration_list).replace('[','').replace(']','').replace("'","").replace(",","<br>") + "<br>" + "<br>"
    email_body += "<b>Whisper real time factor list:</b>" + "<br>" + str(real_time_factor_list).replace('[','').replace(']','').replace("'","").replace(",","<br>") + "<br>" + "<br>"
    if warning_count > 0:
        email_body += f"<b>Number of times the warning word '{warning_word}' was found in the stdout output:</b> " + str(warning_count) + "<br>"
        email_body += "<b>Audio inputs where the warning message was found:</b> " + "<br>" + "<br>".join(warning_audio_inputs) + "<br>" + "<br>"
    else:
        email_body += f"<b>Number of times the warning word '{warning_word}' was found in the stdout output:</b> " + str(warning_count) + "<br>" + "<br>"
    email_body += "<b>Selected Audio Language:</b> " + str(language_audio) + "<br>" + "<br>"
    email_body += "<b>Email Recipients:</b> " + str(email_recipients) + "<br>"
    email_body += "<b>Computer Host Name:</b> " + computer_host_name + " / " + computer_host_ip + "<br>"
    email_body += "<b>Current User's Username:</b> " + current_username + "<br>"

    send_email(subject=email_subject, body=email_body, type="success")


def send_warning_email(audio_input, warning_word, line):
    "Sends a warning email."
    config = get_config()
    email_recipients = config['email']['to']
    language_audio = config['whisper']['language']

    email_subject =  "⚠️ ASR Process Warning! ⚠️"
    email_body = "<b>ASR Process Warning:</b> " + "<br>" + audio_input + "<br>" + "<br>" #+ str(input_file_list).replace('[','').replace(']','').replace("'","").replace(",","<br>") + "<br>" + "<br>"
    email_body += "<b>Warning Message:</b> " + "<br>" + "'" + warning_word + "' was found in the output line " + f"-> {line}" + "<br>" + "<br>"
    email_body += "<b>Date of ASR Process:</b> " + datetime.now().strftime('%Y-%m-%d %H-%M-%S') + "<br>" + "<br>"
    email_body += "<b>Selected Audio Language:</b> " + str(language_audio) + "<br>" + "<br>"
    email_body += "<b>Email Recipients:</b> " + str(email_recipients) + "<br>"
    email_body += "<b>Computer Host Name:</b> " + computer_host_name + " / " + computer_host_ip + "<br>"
    email_body += "<b>Current User's Username:</b> " + current_username + "<br>"

    send_email(subject=email_subject, body=email_body, type="warning")


def send_failure_email(input_file_list, audio_input, warning_count, warning_word, warning_audio_inputs):
    "Sends a failure email."
    config = get_config()
    email_recipients = config['email']['to']
    language_audio = config['whisper']['language']

    email_subject =  "👎 ASR Process Failed! 👎"
    email_body = "<b>ASR Process failed:</b> " + "<br>" + str(input_file_list).replace('[','').replace(']','').replace("'","").replace(",","<br>") + "<br>" + "<br>"
    email_body += f"<b>Error in Whisper ASR Transcription of the file:</b> <br> {audio_input} -> {e}</p>"
    email_body += "<b>Date of ASR Process:</b> " + datetime.now().strftime('%Y-%m-%d %H-%M-%S') + "<br>" + "<br>"
    if warning_count > 0:
        email_body += f"<b>Number of times the warning word '{warning_word}' was found in the stdout output:</b> " + str(warning_count) + "<br>"
        email_body += "<b>Audio inputs where the warning message was found:</b> " + "<br>" + "<br>".join(warning_audio_inputs) + "<br>" + "<br>"
    else:
        email_body += f"<b>Number of times the warning word '{warning_word}' was found in the stdout output:</b> " + str(warning_count) + "<br>" + "<br>"
    email_body += "<b>Selected Audio Language:</b> " + str(language_audio) + "<br>" + "<br>"
    email_body += "<b>Email Recipients:</b> " + str(email_recipients) + "<br>"
    email_body += "<b>Computer Host Name:</b> " + computer_host_name + " / " + computer_host_ip + "<br>"
    email_body += "<b>Current User's Username:</b> " + current_username + "<br>"

    send_email(subject=email_subject, body=email_body, type="failure")
