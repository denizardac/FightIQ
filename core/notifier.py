
import os
import requests
import logging
from datetime import datetime
import json

# Setup logger
logger = logging.getLogger(__name__)

# Default Webhook URL (Placeholder - User should set env var)
# In production, this should be loaded from os.environ.get("DISCORD_WEBHOOK_URL")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_discord_alert(message, status="INFO", webhook_url=None):
    """
    Send a formatted alert to Discord.
    
    Args:
        message (str): The message content.
        status (str): INFO, SUCCESS, WARNING, or ERROR. Determines color.
        webhook_url (str, optional): Override the default webhook URL.
    """
    url = webhook_url or DISCORD_WEBHOOK_URL
    
    if not url:
        logger.warning("Discord Webhook URL not set. Alert skipped.")
        return

    # Color codes
    colors = {
        "INFO": 3447003,      # Blue
        "SUCCESS": 5763719,   # Green
        "WARNING": 16776960,  # Yellow
        "ERROR": 15158332     # Red
    }
    
    color = colors.get(status.upper(), 3447003)
    
    payload = {
        "username": "FightIQ Bot",
        "embeds": [
            {
                "title": f"FightIQ Alert: {status.upper()}",
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "FightIQ Automation System"
                }
            }
        ]
    }

    try:
        response = requests.post(
            url, 
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        if 200 <= response.status_code < 300:
            logger.info("Discord alert sent successfully.")
        else:
            logger.error(f"Failed to send Discord alert: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")

if __name__ == "__main__":
    # Test execution
    print("Testing Notification System...")
    # Mock URL test (will fail or warn if no URL)
    send_discord_alert("This is a test message from FightIQ.", "INFO")
