
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.notifier import send_discord_alert

def test_mock_alert():
    print("Testing Discord Alert with Mock URL...")
    
    # Use httpbin to reflect the request
    mock_url = "https://httpbin.org/post"
    
    send_discord_alert(
        message="Test Alert from FightIQ Unit Test", 
        status="SUCCESS", 
        webhook_url=mock_url
    )
    print("Test Complete. Check logs for success message.")

if __name__ == "__main__":
    test_mock_alert()
