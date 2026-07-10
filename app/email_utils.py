import requests
from flask import current_app

def send_verification_email(to_email, to_name, code):
    api_key = current_app.config.get("BREVO_API_KEY")
    sender_email = current_app.config.get("SENDER_EMAIL")
    sender_name = current_app.config.get("SENDER_NAME")

    if not api_key:
        current_app.logger.error("BREVO_API_KEY not configured")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email, "name": to_name}],
        "subject": "Verifiez votre compte TalibDrive",
        "htmlContent": f"""
        <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
            <h2 style="color: #15803d;">TalibDrive</h2>
            <p>Bonjour {to_name},</p>
            <p>Voici votre code de verification :</p>
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0;">
                <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #15803d;">{code}</span>
            </div>
            <p style="color: #666; font-size: 14px;">Ce code expire dans 15 minutes.</p>
            <p style="color: #999; font-size: 12px; margin-top: 30px;">Si vous n'avez pas demande ce code, ignorez cet email.</p>
        </div>
        """
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code not in (200, 201):
            current_app.logger.error(f"Brevo error {response.status_code}: {response.text}")
        return response.status_code in (200, 201)
    except requests.RequestException as e:
        current_app.logger.error(f"Failed to send email: {e}")
        return False
