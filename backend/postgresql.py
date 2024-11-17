# database.py
import psycopg2
from datetime import datetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from typing import Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()

# Database connection strings
POSTGRES_URL = os.getenv("POSTGRES_URL",
                         "postgresql://maindb_owner:G03JPyoDbQhx@ep-empty-paper-a2mflvxi.eu-central-1.aws.neon.tech/maindb?sslmode=require")
MONGO_URI = os.getenv("MONGO_URI",
                      "mongodb+srv://nutrillama:Q9OuXiA6kbtbZQd2@nutrillama.yc7vv.mongodb.net/?retryWrites=true&w=majority&appName=NutriLlama")

# MongoDB setup
mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = mongo_client['image_database']
image_collection = db['imageCollection']


def init_database():
    """Initialize database tables."""
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()

        # Create users table with health_goal field
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            phone_number VARCHAR(15) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            health_goal TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Create meals table
        create_meals_table = """
        CREATE TABLE IF NOT EXISTS meals (
            meal_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            meal_name VARCHAR(100),
            image_url VARCHAR(500),
            estimated_calories FLOAT,
            glycemic_index FLOAT,
            health_rating INTEGER CHECK (health_rating BETWEEN 0 AND 10),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        # Execute creation queries
        cur.execute(create_users_table)
        cur.execute(create_meals_table)
        conn.commit()

        print("Database tables created successfully!")

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


class UserManager:
    @staticmethod
    def create_user(phone_number: str, name: str, health_goal: str = None) -> int:
        """Create a new user and return user_id."""
        try:
            conn = psycopg2.connect(POSTGRES_URL)
            cur = conn.cursor()

            insert_query = """
            INSERT INTO users (phone_number, name, health_goal)
            VALUES (%s, %s, %s)
            RETURNING user_id;
            """

            cur.execute(insert_query, (phone_number, name, health_goal))
            user_id = cur.fetchone()[0]
            conn.commit()

            return user_id

        except Exception as e:
            print(f"Error creating user: {e}")
            raise

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @staticmethod
    def update_health_goal(user_id: int, new_goal: str) -> bool:
        """Update a user's health goal."""
        try:
            conn = psycopg2.connect(POSTGRES_URL)
            cur = conn.cursor()

            update_query = """
            UPDATE users
            SET health_goal = %s
            WHERE user_id = %s
            RETURNING user_id;
            """

            cur.execute(update_query, (new_goal, user_id))
            updated = cur.fetchone() is not None
            conn.commit()

            return updated

        except Exception as e:
            print(f"Error updating health goal: {e}")
            raise

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @staticmethod
    def get_user_by_phone(phone_number: str) -> Optional[Dict]:
        """Get user details by phone number."""
        try:
            conn = psycopg2.connect(POSTGRES_URL)
            cur = conn.cursor()

            select_query = """
            SELECT user_id, phone_number, name, health_goal, created_at
            FROM users
            WHERE phone_number = %s;
            """

            cur.execute(select_query, (phone_number,))
            user = cur.fetchone()

            if user:
                return {
                    "user_id": user[0],
                    "phone_number": user[1],
                    "name": user[2],
                    "health_goal": user[3],
                    "created_at": user[4]
                }
            return None

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()


class MealManager:
    @staticmethod
    def record_meal(
            user_id: int,
            meal_name: str,
            image_url: Optional[str],
            estimated_calories: float,
            glycemic_index: float,
            health_rating: int
    ) -> int:
        """Record a meal and return meal_id."""
        try:
            conn = psycopg2.connect(POSTGRES_URL)
            cur = conn.cursor()

            insert_query = """
            INSERT INTO meals (
                user_id, meal_name, image_url, estimated_calories,
                glycemic_index, health_rating
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING meal_id;
            """

            cur.execute(insert_query, (
                user_id, meal_name, image_url, estimated_calories,
                glycemic_index, health_rating
            ))
            meal_id = cur.fetchone()[0]
            conn.commit()

            return meal_id

        except Exception as e:
            print(f"Error recording meal: {e}")
            raise

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @staticmethod
    def get_user_meals_today(user_id: int) -> Dict:
        """Get all meals for a user from the current day."""
        try:
            conn = psycopg2.connect(POSTGRES_URL)
            cur = conn.cursor()

            select_query = """
            SELECT 
                meal_id, 
                timestamp, 
                meal_name, 
                image_url,
                estimated_calories, 
                glycemic_index, 
                health_rating
            FROM meals
            WHERE 
                user_id = %s 
                AND DATE(timestamp) = CURRENT_DATE
            ORDER BY timestamp ASC;
            """

            cur.execute(select_query, (user_id,))
            meals = cur.fetchall()

            total_calories = 0
            total_meals = len(meals)
            meals_data = []

            for meal in meals:
                meal_dict = {
                    "meal_id": meal[0],
                    "timestamp": meal[1],
                    "meal_name": meal[2],
                    "image_url": meal[3],
                    "estimated_calories": meal[4],
                    "glycemic_index": meal[5],
                    "health_rating": meal[6]
                }
                meals_data.append(meal_dict)
                total_calories += meal[4] if meal[4] is not None else 0

            return {
                "meals": meals_data,
                "summary": {
                    "total_meals": total_meals,
                    "total_calories": total_calories,
                    "date": datetime.now().date().isoformat()
                }
            }

        except Exception as e:
            print(f"Error fetching today's meals: {e}")
            raise

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

def get_patient_data(phone_number: str) -> Dict:
    """
    Fetch patient data including user details and meals information.

    :param phone_number: The phone number of the user.
    :return: A dictionary containing user details and meals data.
    """
    try:
        # Get user details by phone number
        user = UserManager.get_user_by_phone(phone_number)
        if not user:
            raise ValueError(f"User with phone number {phone_number} not found")

        # Get user's meals for today
        meals_data = MealManager.get_user_meals_today(user["user_id"])

        # Combine user details and meals into a single response
        patient_data = {
            "user": user,
            "meals": meals_data.get("meals", []),
            "summary": meals_data.get("summary", {})
        }

        return patient_data

    except Exception as e:
        print(f"Error fetching patient data: {e}")
        raise


def store_image_and_get_url(phone_number: str, image_data: bytes) -> str:
    """Store image in MongoDB and return URL-like reference."""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{phone_number}_{timestamp}"

        result = image_collection.insert_one({
            'filename': filename,
            'jpgImage': image_data,
            'uploaded_at': datetime.now()
        })

        return f"mongodb://image_database/{str(result.inserted_id)}"

    except Exception as e:
        print(f"Error storing image: {e}")
        raise


# Initialize database if running directly
if __name__ == "__main__":
    init_database()