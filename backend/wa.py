from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

# Twilio credentials
ACCOUNT_SID = os.getenv("ACCOUNT_SID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")

WHATSAPP_FROM = os.getenv("WHATSAPP_FROM")  # Twilio Sandbox WhatsApp number

client = Client(ACCOUNT_SID, AUTH_TOKEN)


def send_message(number_to, message):

    # Send a WhatsApp message
    message = client.messages.create(
        from_=WHATSAPP_FROM,
        to=f"whatsapp:{number_to}",
        body=message
    )

    print(f"Message sent: {message.sid}")

