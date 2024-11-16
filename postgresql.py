import psycopg2
from datetime import datetime


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
