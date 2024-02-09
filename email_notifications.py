"""
Send different kinds of email notifications or reports.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import socket, getpass

from app_config import get_config, whisper_config_html

computer_host_name = socket.gethostname()
computer_host_ip = socket.gethostbyname(computer_host_name)
current_username = getpass.getuser()

def send_email(subject, body, type):
    "Sends email to recipients specified in config."
    config = get_config()
    email_config = config['email']
    email_notifications = config['system']['email_notifications']
    host = email_config["smtp_server"]
    port = email_config["smtp_port"]
    from_addr = email_config["from"]
    to_addrs = email_config["to"]
    username = config['email'].get('username', None)
    password = config['email'].get('password', None)

    if not email_notifications:
        print(body)
        return

    server = smtplib.SMTP(host, port)
    server.starttls()
    if username and password: server.login(username, password)

    print(f"==> Sending {type} email to {', '.join(to_addrs)}")
    message = MIMEMultipart('alternative')
    message['From'] = from_addr
    message['To'] = ', '.join(to_addrs)
    message['Subject'] = subject
    message.attach(MIMEText(body, 'html'))
    server.sendmail(from_addr, to_addrs, message.as_string())

    server.quit()


def process_date_html():
    "Returns current date as HTML."
    result = ("<b>Date of ASR process:</b> "
              + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return result


def system_info_html():
    "Returns system information of the sender computer as HTML."
    result = ("<b>Computer host name:</b> "
              + computer_host_name + " / " + computer_host_ip + "<br>")
    result += ("<b>Current user's username:</b> " + current_username)
    return result


def send_success_email(stats, warning_count, warning_word,
                       warning_audio_inputs):
    "Sends a success email."

    email_subject =  "👍 ASR Process Completed! 👍"

    email_body = "<b>ASR Process successfully completed:</b> " + "<br>"
    email_body += process_date_html() + "<br><br>"
    email_body += "<b>Whisper configuration:</b><br>" + whisper_config_html() + "<br>"

    email_body += "<ul>"

    for process_info in stats:
        email_body += "<li>"
        email_body += f"<b>{process_info.filename},</b> file length {process_info.formatted_audio_length()}, "
        email_body += f"took {process_info.formatted_process_duration()}, rtf "
        email_body += "{:.2f}".format(process_info.realtime_factor())
        email_body += "</li>"

    email_body += "</ul><br>"

    if warning_count > 0:
        email_body += (f"<b>Number of times the warning word '{warning_word}' was found in the stdout output:</b> "
                       + str(warning_count) + "<br>")
        email_body += ("<b>Audio inputs where the warning message was found:</b> "
                       + "<br><br>".join(warning_audio_inputs)
                       + "<br><br>")
    else:
        email_body += (f"<b>Number of times the warning word '{warning_word}' was found in the stdout output:</b> "
                       + str(warning_count) + "<br><br>")

    email_body += system_info_html() + "<br>"

    send_email(subject=email_subject, body=email_body, type="success")


def send_warning_email(audio_input, warning_word, line):
    "Sends a warning email."

    email_subject =  "⚠️ ASR Process Warning! ⚠️"
    email_body = ("<b>ASR Process Warning:</b> " + "<br>" + audio_input
                  + "<br><br>")
    email_body += ("<b>Warning Message:</b> " + "<br>" + "'" + warning_word
                   + "' was found in the output line " + f"-> {line}"
                   + "<br><br>")
    email_body += process_date_html() + "<br><br>"
    email_body += "<b>Whisper configuration:</b><br>" + whisper_config_html() + "<br><br>"
    email_body += system_info_html() + "<br>"

    send_email(subject=email_subject, body=email_body, type="warning")


def send_failure_email(stats, audio_input, warning_count,
                       warning_word, warning_audio_inputs, exception):
    "Sends a failure email."

    email_subject =  "👎 ASR Process Failed! 👎"
    email_body = "<b>ASR Process failed:</b> " + "<br>"
    email_body += "<ul>"

    for process_info in stats:
        email_body += "<li>" + process_info.filename + "</li>"

    email_body += "</ul><br>"
    email_body += f"<b>Error in Whisper ASR Transcription of the file:</b> <br> {audio_input} -> {exception}</p>"
    email_body += process_date_html() + "<br><br>"
    if warning_count > 0:
        email_body += (f"<b>Number of times the warning word '{warning_word}' was found in the stdout output:</b> "
                       + str(warning_count) + "<br>")
        email_body += ("<b>Audio inputs where the warning message was found:</b> "
                       + "<br><br>".join(warning_audio_inputs)
                       + "<br><br>")
    else:
        email_body += (f"<b>Number of times the warning word '{warning_word}' was found in the stdout output:</b> "
                       + str(warning_count) + "<br><br>")

    email_body += "<b>Whisper configuration:</b><br>" + whisper_config_html() + "<br><br>"
    email_body += system_info_html() + "<br>"

    send_email(subject=email_subject, body=email_body, type="failure")
