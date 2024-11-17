import psycopg2
from datetime import datetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import gridfs


def example():
  POSTGRES_URL = "postgresql://maindb_owner:G03JPyoDbQhx@ep-empty-paper-a2mflvxi.eu-central-1.aws.neon.tech/maindb?sslmode=require"
  try:
      # Connect to PostgreSQL
      conn = psycopg2.connect(POSTGRES_URL)
      cur = conn.cursor()

      # Create table with compound primary key
      create_table_query = """
      CREATE TABLE IF NOT EXISTS phone_logs (
          phone_no VARCHAR(15),
          log_time TIMESTAMP,
          attribute VARCHAR(1000),
          PRIMARY KEY (phone_no, log_time)
      );
      """
      cur.execute(create_table_query)
      conn.commit()

      # Insert a sample record
      insert_query = """
      INSERT INTO phone_logs (phone_no, log_time, attribute)
      VALUES (%s, %s, %s);
      """
      cur.execute(insert_query, ('+1234567890', '2024-11-16 10:30:00', 'Sample Attribute'))
      conn.commit()

      # Fetch records
      cur.execute("SELECT * FROM phone_logs;")
      rows = cur.fetchall()
      for row in rows:
          print(row)

      # Close the connection
      cur.close()
      conn.close()

  except Exception as e:
      print("Error:", e)


# Get current time
current_time = datetime.now()

# Format as a string (optional, PostgreSQL accepts datetime objects)
formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')

print(formatted_time)  # Example: "2024-11-16 14:30:45"

def getCurTime():
  # Get current time
  current_time = datetime.now()

  # Format as a string (optional, PostgreSQL accepts datetime objects)
  return current_time.strftime('%Y-%m-%d %H:%M:%S')

uri = "mongodb+srv://nutrillama:Q9OuXiA6kbtbZQd2@nutrillama.yc7vv.mongodb.net/?retryWrites=true&w=majority&appName=NutriLlama"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

# Connect to MongoDB
db = client['image_database']  # database name
imageCollection = db['imageCollection']  # Replace with the collection name

fs = gridfs.GridFS(db)

# DONT USE THIS USE THE COLLECTIONS FUNCTIONS BELOW
def image_example():
  # Open and read the image
  with open('example.jpg', 'rb') as file:
      image_data = file.read()

  # Store the image in GridFS
  file_id = fs.put(image_data, filename='example.jpg', description='A sample image')

  # Retrieve the image
  stored_file = fs.get(file_id)
  with open('output_example.jpg', 'wb') as output_file:
      output_file.write(stored_file.read())

  print(f"Image stored with ID: {file_id}")

def store_image(phoneNo, jpgImage):
  return imageCollection.insert_one({
    'filename': phoneNo+getCurTime(),
    'jpgImage': jpgImage
  })

def get_images(phoneNo):
  # Query to find documents where the 'filename' field starts with 'example'
  return imageCollection.find({"filename": {"$regex": f"^{phoneNo}", "$options": "i"}})
  