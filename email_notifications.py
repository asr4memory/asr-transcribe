"""
Send different kinds of email notifications or reports.
"""

import getpass
import smtplib
import socket
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app_config import get_config, whisper_config_html
from logger import logger

computer_host_name = socket.gethostname()
computer_host_ip = socket.gethostbyname(computer_host_name)
current_username = getpass.getuser()


def send_email(subject, body, type):
    "Sends email to recipients specified in config."

    config = get_config()
    email_config = config["email"]
    email_notifications = config["system"]["email_notifications"]
    host = email_config["smtp_server"]
    port = email_config["smtp_port"]
    from_addr = email_config["from"]
    to_addrs = email_config["to"]
    username = config["email"].get("username", None)
    password = config["email"].get("password", None)

    if not email_notifications:
        return

    server = smtplib.SMTP(host, port)
    server.starttls()
    if username and password:
        server.login(username, password)

    logger.info(f"Sending {type} email to {', '.join(to_addrs)}")
    message = MIMEMultipart("alternative")
    message["From"] = from_addr
    message["To"] = ", ".join(to_addrs)
    message["Subject"] = subject
    message.attach(MIMEText(body, "html"))
    server.sendmail(from_addr, to_addrs, message.as_string())

    server.quit()


def process_date_html():
    "Returns current date as HTML."
    result = "<b>Date of ASR process:</b> " + datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    return result


def system_info_html():
    "Returns system information of the sender computer as HTML."
    result = (
        "<b>Computer host name:</b> "
        + computer_host_name
        + " / "
        + computer_host_ip
        + "<br>"
    )
    result += "<b>Current user's username:</b> " + current_username
    return result


def send_success_email(stats, warning_count, warning_audio_inputs):
    "Sends a success email."

    email_subject = "👍 ASR Process Completed! 👍"

    email_body = "<b>ASR Process successfully completed:</b> " + "<br>"
    email_body += process_date_html() + "<br><br>"
    email_body += "<b>Whisper configuration:</b><br>" + whisper_config_html() + "<br>"

    email_body += "<ul>"

    for process_info in stats:
        email_body += "<li>"
        email_body += (
            f"<b>{process_info.filename},</b> file length "
            + f"{process_info.formatted_audio_length()}, "
        )
        email_body += f"took {process_info.formatted_process_duration()}, rtf "
        email_body += "{:.2f}".format(process_info.realtime_factor())
        email_body += "</li>"

    email_body += "</ul><br>"

    if warning_count > 0:
        email_body += (
            "<b>Number of hallucination warnings:</b> " + str(warning_count) + "<br>"
        )
        email_body += (
            "<b>Audio inputs where the warning message was found:</b> "
            + "<br><br>".join(warning_audio_inputs)
            + "<br><br>"
        )
    else:
        email_body += "No hallucination warnings occurred.<br><br>"

    email_body += system_info_html() + "<br>"

    send_email(subject=email_subject, body=email_body, type="success")


def send_warning_email(audio_input, warnings):
    "Sends a warning email."

    email_subject = "⚠️ ASR Hallucination Warning! ⚠️"
    email_body = (
        "<b>ASR hallucination warning:</b> " + "<br>" + audio_input + "<br><br>"
    )

    email_body += "<b>Possible hallucation(s):</b> " + "<br>"
    for warning in warnings:
        email_body += warning + "<br>"
    email_body += "<br>"

    email_body += process_date_html() + "<br><br>"
    email_body += (
        "<b>Whisper configuration:</b><br>" + whisper_config_html() + "<br><br>"
    )
    email_body += system_info_html() + "<br>"

    send_email(subject=email_subject, body=email_body, type="warning")


def send_failure_email(stats, audio_input, exception):
    "Sends a failure email."

    email_subject = "👎 ASR Processing file failed! 👎"
    email_body = "<b>ASR Processing file failed:</b> " + "<br>"
    email_body += "<ul>"

    for process_info in stats:
        email_body += "<li>" + process_info.filename + "</li>"

    email_body += "</ul><br>"
    email_body += (
        "<b>Error in Whisper ASR Transcription of the file:</b><br>"
        + f"{audio_input} -> {exception}</p>"
    )

    email_body += process_date_html() + "<br><br>"
    email_body += (
        "<b>Whisper configuration:</b><br>" + whisper_config_html() + "<br><br>"
    )
    email_body += system_info_html() + "<br>"

    send_email(subject=email_subject, body=email_body, type="failure")
