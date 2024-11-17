# app.py
from fastapi import FastAPI, HTTPException
from groq import Groq
import base64
import json
from typing import Dict, Union, Tuple
from enum import Enum
import re
from dotenv import load_dotenv
import os
from datetime import datetime
from postgresql import UserManager, MealManager, store_image_and_get_url

load_dotenv()

# Environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = FastAPI()
client = Groq()


class MessageType(Enum):
    FOOD_IMAGE = "food_image"
    FOOD_DESCRIPTION = "food_description"
    GENERAL_QUERY = "general_query"
    GREETING = "greeting"
    HELP_REQUEST = "help_request"
    SUMMARY_REQUEST = "summary_request"


class MessageAnalyzer:
    def __init__(self):
        self.client = Groq()

    def analyze_message_type(self, message: Dict) -> Tuple[MessageType, Dict]:
        """
        Analyze WhatsApp message to determine its type and extract relevant information.
        """
        message_info = {
            "original_text": message.get("text", ""),
            "has_image": bool(message.get("image")),
            "timestamp": message.get("timestamp"),
            "sender": message.get("sender")
        }

        if message.get("image"):
            return MessageType.FOOD_IMAGE, message_info

        text = message.get("text", "").lower()

        # Summary request patterns
        if any(word in text for word in ["summary", "today's meals", "what did i eat", "show meals"]):
            return MessageType.SUMMARY_REQUEST, message_info

        # Food description patterns
        food_patterns = [
            r"i (?:ate|had|consumed)",
            r"my meal",
            r"for (?:breakfast|lunch|dinner|snack)",
            r"eating",
            r"food",
            r"calories",
            r"serving",
            r"portion"
        ]
        if any(re.search(pattern, text) for pattern in food_patterns):
            return MessageType.FOOD_DESCRIPTION, message_info

        # Greeting patterns
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
        if any(greeting in text for greeting in greetings):
            return MessageType.GREETING, message_info

        # Help request patterns
        help_patterns = [r"help", r"how to", r"how do I", r"support"]
        if any(re.search(pattern, text) for pattern in help_patterns):
            return MessageType.HELP_REQUEST, message_info

        return MessageType.GENERAL_QUERY, message_info


def _format_meals_for_prompt(daily_meals: Dict) -> str:
    """Format daily meals into a string for the prompt."""
    if not daily_meals["meals"]:
        return "No meals recorded yet today."

    meals_str = []
    total_calories = 0
    total_carbs = 0

    for meal in daily_meals["meals"]:
        meal_time = meal["timestamp"].strftime("%I:%M %p") if isinstance(meal["timestamp"], datetime) else meal[
            "timestamp"]
        meals_str.append(
            f"- {meal['meal_name']} at {meal_time}:\n"
            f"  Calories: {meal['estimated_calories']},"
            f" Glycemic Index: {meal['glycemic_index']}"
        )
        total_calories += meal['estimated_calories'] if meal['estimated_calories'] else 0

    summary = f"\nDaily Totals So Far:\n- Total Calories: {total_calories}"

    return "\n".join(meals_str) + summary


class FoodAnalyzer:
    def __init__(self):
        self.client = Groq()

    async def analyze_food_image(self, image_base64: str, health_goal: str, user_id: int) -> Dict:
        """Analyze food image using LLaMA model considering user's health goal and previous meals."""
        # Get today's meals first
        daily_meals = MealManager.get_user_meals_today(user_id)
        meals_context = _format_meals_for_prompt(daily_meals)

        prompt = f"""Analyze this food image in the context of the user's previous meals today and their health goal.

User's Health Goal: "{health_goal}"

Previous Meals Today:
{meals_context}

Analyze this new meal and provide information in the following JSON format. Do not say anything else and provide me the 
contents of a literal JSON file in this format, remember to store any numeric quantities WITHOUT units, use double quotes everywhere:
{{
    "food_items": ["list of identified foods"],
    "meal_name": "name of meal deduced by photo, if not confident then use caption provided by user",
    "calories": numeric_value,
    "glycemic_index": numeric_value,
    "nutrition": {{
        "carbs": numeric_value,
        "proteins": numeric_value,
        "fats": numeric_value,
        "fiber": numeric_value,
        "sugar": numeric_value
    }},
    "serving_size": "description of portion size",
    "health_considerations": [
        "list of relevant health notes for diabetics",
        "potential blood sugar impacts",
        "timing considerations"
    ],
    "daily_context": {{
        "total_calories_with_meal": numeric_value,
        "total_carbs_with_meal": numeric_value,
        "remaining_calorie_budget": numeric_value,
        "meal_timing_advice": "advice considering previous meals",
        "nutritional_balance": "analysis of daily nutritional balance with this meal"
    }},
    "goal_alignment": {{
        "score": number_between_1_and_10,
        "reasons": [
            "detailed reasons why this meal aligns or doesn't align with the user's goals",
            "consider daily totals and previous meals"
        ],
        "suggestions": [
            "specific suggestions to better align with goals",
            "include portion adjustments or alternative ingredients",
            "suggestions for remaining meals of the day"
        ]
    }},
    "health_rating": number_between_1_and_10,
    "meal_timing": {{
        "ideal_time": "best time considering previous meals",
        "spacing": "recommended hours before/after other meals"
    }}
}}"""

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}",
                                },
                            },
                        ],
                    }
                ],
                model="llama-3.2-11b-vision-preview",
            )

            print("----------------------------------------")
            print(chat_completion.choices[0].message.content)
            print("----------------------------------------")

            analysis = json.loads(chat_completion.choices[0].message.content)
            return self._process_analysis(analysis, health_goal, daily_meals)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Food image analysis failed: {str(e)}")

    async def analyze_food_description(self, description: str, health_goal: str, user_id: int) -> Dict:
        """Analyze text description of food considering user's health goal and previous meals."""
        # Get today's meals first
        daily_meals = MealManager.get_user_meals_today(user_id)
        meals_context = _format_meals_for_prompt(daily_meals)

        prompt = f"""Analyze this food description in the context of the user's previous meals today and their health goal.

User's Health Goal: "{health_goal}"

Previous Meals Today:
{meals_context}

Based on this food description: "{description}"
Provide a detailed analysis in this JSON format. Do not say anything else and provide me the 
contents of a literal JSON file in this format, remember to store any numeric quantities WITHOUT units:
{{
    "food_items": ["list of identified foods"],
    "meal_name": "name or description of meal provided by user or deduced by photo itself",
    "estimated_calories": numeric_value,
    "estimated_glycemic_index": numeric_value,
    "estimated_nutrition": {{
        "carbs": numeric_value,
        "proteins": numeric_value,
        "fats": numeric_value,
        "fiber": numeric_value,
        "sugar": numeric_value
    }},
    "assumed_serving_size": "description of portion size",
    "health_considerations": [
        "list of relevant health notes for diabetics",
        "potential blood sugar impacts",
        "timing considerations"
    ],
    "daily_context": {{
        "total_calories_with_meal": numeric_value,
        "total_carbs_with_meal": numeric_value,
        "remaining_calorie_budget": numeric_value,
        "meal_timing_advice": "advice considering previous meals",
        "nutritional_balance": "analysis of daily nutritional balance with this meal"
    }},
    "confidence_level": "high/medium/low",
    "goal_alignment": {{
        "score": number_between_1_and_10,
        "reasons": ["detailed alignment reasons considering daily context"],
        "suggestions": ["specific improvement suggestions for this meal and remaining meals"]
    }},
    "health_rating": number_between_1_and_10,
    "meal_timing": {{
        "ideal_time": "best time considering previous meals",
        "spacing": "recommended hours before/after other meals"
    }}
}}"""

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.2-11b-vision-preview",
            )

            analysis = json.loads(chat_completion.choices[0].message.content)
            return self._process_analysis(analysis, health_goal, daily_meals)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Food description analysis failed: {str(e)}")

    def _process_analysis(self, analysis: Dict, health_goal: str, daily_meals: Dict) -> Dict:
        """Process the analysis and add recommendations considering daily context."""
        # Get nutrition values
        nutrition = analysis.get('nutrition') or analysis.get('estimated_nutrition', {})
        calories = analysis.get('calories') or analysis.get('estimated_calories', 0)
        gi = analysis.get('glycemic_index') or analysis.get('estimated_glycemic_index', 0)

        # Calculate daily totals including this meal
        total_calories = daily_meals["summary"]["total_calories"] + calories

        # Add personalized recommendations
        analysis['personalized_advice'] = []

        # Daily calorie context
        if total_calories > 2000:  # Adjustable threshold
            analysis['personalized_advice'].append(
                f"📊 Daily Calories: You've reached {total_calories} calories including this meal. "
                "Consider a lighter option for remaining meals."
            )

        # Blood sugar management
        if gi > 55:
            analysis['personalized_advice'].append(
                f"🩺 Blood Sugar Impact: This meal has a high glycemic index ({gi}). "
                "Consider:\n"
                "- Eating with protein or healthy fats\n"
                "- Taking a short walk after eating\n"
                "- Monitoring blood sugar 2 hours after eating"
            )

        # Goal-specific advice considering daily context
        health_goal_lower = health_goal.lower()
        if "weight" in health_goal_lower:
            remaining_calories = 2000 - total_calories  # Adjustable target
            analysis['personalized_advice'].append(
                f"⚖️ Calorie Budget: You have {remaining_calories} calories remaining for the day. "
                f"This meal is {calories} calories."
            )

        # Add meal timing recommendations based on previous meals
        last_meal_time = None
        if daily_meals["meals"]:
            last_meal = daily_meals["meals"][-1]
            last_meal_time = last_meal["timestamp"]
            if isinstance(last_meal_time, datetime):
                hours_since_last_meal = (datetime.now() - last_meal_time).total_seconds() / 3600
                if hours_since_last_meal < 2:
                    analysis['personalized_advice'].append(
                        "⏰ Meal Timing: It's been less than 2 hours since your last meal. "
                        "Consider waiting longer between meals for better blood sugar control."
                    )

        return analysis


async def handle_general_query(query: str):
    """Handle general questions about diabetes and diet."""
    prompt = f"""Answer this user query about diabetes management or diet: \"{query}\"
    Provide a helpful, concise response focused on diabetes management if relevant.
    Include practical tips and clear explanations. The output should be less than 1500 characters."""

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.2-11b-vision-preview",
        )

        # return {
        #     "message_type": "general_answer",
        #     "response": chat_completion.choices[0].message.content
        # }

        return chat_completion.choices[0].message.content

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@app.post("/process-message")
async def process_message(request_data: Dict):
    """
    Process incoming WhatsApp message.

    Expected request_data format:
    {
        "message": {
            "text": str,              # Optional text content
            "image": str,             # Optional base64 image
            "timestamp": str,
            "sender": str
        },
        "user": {
            "user_id": int,
            "phone_number": str,
            "health_goal": str
        }
    }
    """
    try:
        message_analyzer = MessageAnalyzer()
        food_analyzer = FoodAnalyzer()

        # Get user info
        user_id = request_data["user"]["user_id"]
        health_goal = request_data["user"]["health_goal"]

        # Analyze message type
        message_type, message_info = message_analyzer.analyze_message_type(request_data["message"])

        # Process based on message type
        if message_type == MessageType.FOOD_IMAGE:
            # Store image
            image_url = store_image_and_get_url(
                request_data["user"]["phone_number"],
                base64.b64decode(request_data["message"]["image"])
            )

            # Analyze food
            analysis = await food_analyzer.analyze_food_image(
                request_data["message"]["image"],
                health_goal,
                user_id
            )

            # Record meal
            meal_id = MealManager.record_meal(
                user_id=user_id,
                meal_name=analysis.get("meal_name", "Unknown Meal"),
                image_url=image_url,
                estimated_calories=analysis.get("calories"),
                glycemic_index=analysis.get("glycemic_index"),
                health_rating=analysis.get("health_rating", 5)
            )

            # Get daily summary
            daily_summary = MealManager.get_user_meals_today(user_id)

            return {
                "message_type": "food_analysis",
                "analysis": analysis,
                "meal_id": meal_id,
                "daily_summary": daily_summary
            }

        elif message_type == MessageType.FOOD_DESCRIPTION:
            analysis = await food_analyzer.analyze_food_description(
                request_data["message"]["text"],
                health_goal,
                user_id
            )

            # Record meal
            meal_id = MealManager.record_meal(
                user_id=user_id,
                meal_name=analysis.get("meal_name", "Unknown Meal"),
                image_url=None,
                estimated_calories=analysis.get("estimated_calories"),
                glycemic_index=analysis.get("estimated_glycemic_index"),
                health_rating=analysis.get("health_rating", 5)
            )

            # Get daily summary
            daily_summary = MealManager.get_user_meals_today(user_id)

            return {
                "message_type": "food_analysis",
                "analysis": analysis,
                "meal_id": meal_id,
                "daily_summary": daily_summary
            }

        elif message_type == MessageType.SUMMARY_REQUEST:
            daily_summary = _format_meals_for_prompt(MealManager.get_user_meals_today(user_id))
            return {
                "message_type": "summary",
                "daily_summary": daily_summary
            }

        elif message_type == MessageType.GREETING:
            daily_summary = MealManager.get_user_meals_today(user_id)
            return {
                "message_type": "greeting",
                "response": "Hello! How can I help you with your meal tracking today?",
                "daily_summary": daily_summary
            }

        elif message_type == MessageType.HELP_REQUEST:
            return {
                "message_type": "help",
                "response": (
                    "I can help you track your meals and provide nutritional analysis. "
                    "You can:\n"
                    "1. Send food photos for analysis\n"
                    "2. Describe what you ate\n"
                    "3. Ask for your meal summary\n"
                    "4. Ask questions about diabetes and diet\n"
                    "What would you like to know?"
                )
            }

        else:
            answer = await handle_general_query(request_data["message"]["text"])
            return {
                "message_type": "general_response",
                "response": answer
            }

    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user-meals/today/{user_id}")
async def get_user_meals_today(user_id: int):
    """Get user's meals for today."""
    try:
        return MealManager.get_user_meals_today(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user-meals/{user_id}/{date}")
async def get_user_meals_by_date(user_id: int, date=datetime.now()):
    """Get user's meals for a specific date."""
    try:
        return MealManager.get_user_meals_today(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)