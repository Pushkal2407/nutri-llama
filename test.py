from groq import Groq
import base64
import json
from typing import Dict, Union, Tuple
import os
from fastapi import FastAPI, HTTPException
from enum import Enum
import re

# Environment variables
os.environ["GROQ_API_KEY"] = "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"

app = FastAPI()
client = Groq()

class MessageType(Enum):
    FOOD_IMAGE = "food_image"
    FOOD_DESCRIPTION = "food_description"
    GENERAL_QUERY = "general_query"
    GREETING = "greeting"
    HELP_REQUEST = "help_request"

class MessageAnalyzer:
    def __init__(self):
        self.client = Groq()
        
    def analyze_message_type(self, message: Dict) -> Tuple[MessageType, Dict]:
        """
        Analyze WhatsApp message to determine its type and extract relevant information.
        
        Expected message format:
        {
            "text": str,              # Optional text content
            "image": str,             # Optional base64 image
            "timestamp": str,         # Message timestamp
            "sender": str             # Sender identifier
        }
        """
        message_info = {
            "original_text": message.get("text", ""),
            "has_image": bool(message.get("image")),
            "timestamp": message.get("timestamp"),
            "sender": message.get("sender")
        }

        # Check if message contains an image
        if message.get("image"):
            return MessageType.FOOD_IMAGE, message_info

        text = message.get("text", "").lower()
        
        # Common patterns for food descriptions
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
        
        # Check for food description
        if any(re.search(pattern, text) for pattern in food_patterns):
            return MessageType.FOOD_DESCRIPTION, message_info
        
        # Check for greeting
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
        if any(greeting in text for greeting in greetings):
            return MessageType.GREETING, message_info
        
        # Check for help request
        help_patterns = [r"help", r"how to", r"how do I", r"\?", r"support"]
        if any(re.search(pattern, text) for pattern in help_patterns):
            return MessageType.HELP_REQUEST, message_info
        
        # Default to general query
        return MessageType.GENERAL_QUERY, message_info

class FoodAnalyzer:
    def __init__(self):
        self.client = Groq()
        
    async def analyze_food_image(self, image_base64: str, user_thresholds: Dict) -> Dict:
        """Analyze food image using LLaMA model."""
        prompt = """Analyze this food image and provide the following information in a valid JSON format:
        {
            "food_items": ["list of identified foods"],
            "calories": numeric_value,
            "glycemic_index": numeric_value,
            "nutrition": {
                "carbs": numeric_value,
                "proteins": numeric_value,
                "fats": numeric_value,
                "fiber": numeric_value,
                "sugar": numeric_value
            },
            "serving_size": "description of portion size",
            "health_considerations": ["list of relevant health notes for diabetics"]
        }"""

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
            
            analysis = json.loads(chat_completion.choices[0].message.content)
            return self._add_warnings(analysis, user_thresholds)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Food image analysis failed: {str(e)}")

    async def analyze_food_description(self, description: str, user_thresholds: Dict) -> Dict:
        """Analyze text description of food using LLaMA model."""
        prompt = f"""Based on this food description: "{description}", provide the following information in a valid JSON format:
        {{
            "food_items": ["list of identified foods"],
            "estimated_calories": numeric_value,
            "estimated_glycemic_index": numeric_value,
            "estimated_nutrition": {{
                "carbs": numeric_value,
                "proteins": numeric_value,
                "fats": numeric_value,
                "fiber": numeric_value,
                "sugar": numeric_value
            }},
            "assumed_serving_size": "description of assumed portion size",
            "health_considerations": ["list of relevant health notes for diabetics"],
            "confidence_level": "high/medium/low"
        }}"""

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.2-11b-vision-preview",
            )
            
            analysis = json.loads(chat_completion.choices[0].message.content)
            return self._add_warnings(analysis, user_thresholds)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Food description analysis failed: {str(e)}")

    def _add_warnings(self, analysis: Dict, thresholds: Dict) -> Dict:
        """Add warning flags based on thresholds."""
        analysis['warnings'] = []
        
        # Check caloric content
        calories = analysis.get('calories') or analysis.get('estimated_calories', 0)
        if calories > thresholds.get('max_calories', float('inf')):
            analysis['warnings'].append("Calorie content exceeds recommended limit")
        
        # Check glycemic index
        gi = analysis.get('glycemic_index') or analysis.get('estimated_glycemic_index', 0)
        if gi > thresholds.get('max_glycemic_index', float('inf')):
            analysis['warnings'].append("Glycemic index is higher than recommended")
        
        # Check nutritional values
        nutrition = analysis.get('nutrition') or analysis.get('estimated_nutrition', {})
        if nutrition.get('carbs', 0) > thresholds.get('max_carbs', float('inf')):
            analysis['warnings'].append("Carbohydrate content is higher than recommended")
        if nutrition.get('sugar', 0) > thresholds.get('max_sugar', float('inf')):
            analysis['warnings'].append("Sugar content is higher than recommended")
        
        return analysis

async def handle_general_query(query: str) -> Dict:
    """Handle general questions about diabetes, diet, or the app."""
    prompt = f"""Answer this user query about diabetes management or diet: "{query}"
    Provide a helpful, concise response focused on diabetes management if relevant."""
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.2-11b-vision-preview",
        )
        
        return {
            "response_type": "general_answer",
            "answer": chat_completion.choices[0].message.content
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

# API Endpoints
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
        "user_thresholds": {          # Optional thresholds
            "max_calories": number,
            "max_glycemic_index": number,
            "max_carbs": number,
            "max_sugar": number
        }
    }
    """
    try:
        message_analyzer = MessageAnalyzer()
        food_analyzer = FoodAnalyzer()
        
        # Analyze message type
        message_type, message_info = message_analyzer.analyze_message_type(request_data["message"])
        
        # Process based on message type
        if message_type == MessageType.FOOD_IMAGE:
            analysis = await food_analyzer.analyze_food_image(
                request_data["message"]["image"],
                request_data.get("user_thresholds", {})
            )
            return {
                "message_type": "food_analysis",
                "analysis": analysis
            }
            
        elif message_type == MessageType.FOOD_DESCRIPTION:
            analysis = await food_analyzer.analyze_food_description(
                request_data["message"]["text"],
                request_data.get("user_thresholds", {})
            )
            return {
                "message_type": "food_analysis",
                "analysis": analysis
            }
            
        elif message_type == MessageType.GREETING:
            return {
                "message_type": "greeting",
                "response": "Hello! How can I help you with your meal tracking today?"
            }
            
        elif message_type == MessageType.HELP_REQUEST:
            return {
                "message_type": "help",
                "response": "I can help you track your meals and provide nutritional analysis. "
                          "You can send me food photos or describe what you ate, and I'll analyze it for you. "
                          "What would you like to know?"
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

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}