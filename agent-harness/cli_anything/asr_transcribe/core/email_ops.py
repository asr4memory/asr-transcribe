"""Email notification operations."""

import smtplib

from cli_anything.asr_transcribe.utils.asr_backend import ensure_project_importable


def test_email() -> dict:
    """Test email connectivity using config.toml SMTP settings.

    Returns:
        Dict with "success" (bool), "message" (str), and connection details.
    """
    root = ensure_project_importable()
    from config.app_config import get_config

    config = get_config()
    email_config = config.get("email", {})

    host = email_config.get("smtp_server", "")
    port = email_config.get("smtp_port", 587)
    from_addr = email_config.get("from", "")
    to_addrs = email_config.get("to", [])

    if not host:
        return {"success": False, "message": "email.smtp_server not configured."}

    if not from_addr:
        return {"success": False, "message": "email.from not configured."}

    try:
        server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()

        username = email_config.get("username")
        password = email_config.get("password")
        if username and password:
            server.login(username, password)

        server.quit()

        return {
            "success": True,
            "smtp_server": host,
            "smtp_port": port,
            "from": from_addr,
            "to": to_addrs,
            "auth": bool(username and password),
            "message": f"SMTP connection to {host}:{port} successful.",
        }
    except smtplib.SMTPException as e:
        return {"success": False, "message": f"SMTP error: {e}"}
    except OSError as e:
        return {"success": False, "message": f"Connection error: {e}"}
