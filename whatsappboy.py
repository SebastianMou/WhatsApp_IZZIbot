# run with ngrok
# cd C:\
# .\ngrok http 7000
# justimex@gmail.com --> https://console.twilio.com/

from openai import OpenAI
from twilio.rest import Client
from dotenv import load_dotenv
from flask import Flask, request

load_dotenv()

# Set up OpenAI client
openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Set up Twilio client
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

# Flask app for webhook
app = Flask(__name__)

@app.route("/webhook", methods=['POST'])
def webhook():
    # Get incoming message
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    
    # System instruction for AI
    system_instruction = """
    act like a cool human
    """
    
    # Get AI response
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": incoming_msg},
        ]
    )
    
    ai_response = response.choices[0].message.content
    
    # Send AI response back via WhatsApp
    message = twilio_client.messages.create(
        from_='whatsapp:+14155238886',
        body=ai_response,
        to=sender
    )
    
    return "Message sent"

if __name__ == "__main__":
    app.run(debug=True)