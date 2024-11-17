from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    # Parse the incoming request
    incoming_message = request.form.get("Body")
    from_number = request.form.get("From")
    logging.info(f"Message from {from_number}: {incoming_message}")

    # Example: Respond to the message (optional)
    response = "Thanks for your message!"
    return f"<Response><Message>{response}</Message></Response>", 200

if __name__ == "_main_":
    app.run(port=5000, debug=True)