import datetime

from flask import Flask, request, jsonify
import logging
import requests
from dotenv import load_dotenv
import os
import postgresql
from psycopg2.errors import UniqueViolation
import wa
from flask_cors import CORS
import llm
import base64

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

logging.basicConfig(level=logging.INFO)

load_dotenv()

TWILIO_SID = os.getenv("ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("AUTH_TOKEN")

postgresql.init_database()


@app.route("/webhook", methods=["POST"])
async def receive_message():
    from_number = request.form.get("From")

    print("From number is:" + from_number)
    num_media = int(request.form.get("NumMedia", 0))  # Number of media items

    message_to_process = {"text": request.form.get("Body"), "timestamp": datetime.datetime.now().isoformat()}

    if num_media > 0:
        # Extract media details
        media_url = request.form.get("MediaUrl0")
        media_type = request.form.get("MediaContentType0")

        logging.info(f"Received media from {from_number}: {media_url} ({media_type})")

        # Replace this part in your webhook handler function
        response = requests.get(
            media_url,
            auth=(TWILIO_SID, TWILIO_TOKEN),
        )

        if response.status_code == 200:
            # Save the media file
            file_extension = media_type.split("/")[-1]
            file_name = f"downloaded_image.{file_extension}"
            with open(file_name, "wb") as file:
                file.write(response.content)
            logging.info(f"Media saved as {file_name}")
            message_to_process["image"] = image_to_base64(file_name)
        else:
            logging.error(f"Failed to download media. HTTP Status Code: {response.status_code}")

    llm_ret = await llm.process_message({"message": message_to_process, "user": postgresql.UserManager.get_user_by_phone(from_number[9:])})

    # Determine the message based on the message type
    message = ""

    if llm_ret["message_type"] == "food_analysis":
        # Food analysis response
        analysis = llm_ret["analysis"]
        message = f"Your meal has been analyzed: \n" \
                  f"Meal Name: {analysis.get('meal_name', 'Unknown Meal')}\n" \
                  f"Calories: {analysis.get('calories', 'N/A')}\n" \
                  f"Glycemic Index: {analysis.get('glycemic_index', 'N/A')}\n" \
                  f"Health Rating: {analysis.get('health_rating', '5')}"

    elif llm_ret["message_type"] == "summary":
        # Daily meal summary
        daily_summary = llm_ret["daily_summary"]
        message = f"Here’s your meal summary for today:\n{daily_summary}"

    elif llm_ret["message_type"] == "greeting":
        # Greeting message
        message = llm_ret["response"]

    elif llm_ret["message_type"] == "help":
        # Help message
        message = llm_ret["response"]

    elif llm_ret["message_type"] == "general_response":
        # General query response
        message = llm_ret["response"]

    # Send the constructed message
    wa.send_message(from_number[9:], message)
    return "", 200


@app.route("/add_user", methods=["POST"])
def add_user():
    user_data = request.get_json()  # Assumes JSON payload
    if not user_data:
        return jsonify({"status": "error", "message": "Invalid or missing JSON data"}), 400

    try:
        # Extract individual fields
        name = user_data.get("name")
        phone_number = user_data.get("phone_number")
        goal = user_data.get("goal")

        # Attempt to create the user
        postgresql.UserManager.create_user(phone_number, name, goal)

        message = f"Hi {name}! Your nutritionist has just set up this chat! I will be in touch with you daily to help you with your goal"

        wa.send_message(phone_number, message)

        message = f"To start off, please send me a picture with a caption of every meal you have had today!"

        wa.send_message(phone_number, message)

        return jsonify({"status": "success", "message": "Successfully added user"}), 200

    except UniqueViolation:
        # Handle the case where a unique constraint violation occurs (e.g., duplicate phone_number)
        return jsonify({"status": "error", "message": "User with this phone number already exists"}), 400

    except Exception as e:
        # General exception handler
        logging.error(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400

def image_to_base64(image_path):
    # Open the image file in binary mode
    with open(image_path, "rb") as image_file:
        # Read the image and encode it to base64
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
    return encoded_image

if __name__ == "__main__":
    app.run(port=5000, debug=True)
