from dotenv import load_dotenv
import os
import MySQLdb
from pathlib import Path

# Load .env from backend/
env_path = Path(__file__).resolve().parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

# Print loaded environment variables for verification
print("🔍 Environment values:")
print("Host:", os.getenv("DATABASE_HOST"))
print("User:", os.getenv("DATABASE_USERNAME"))
print("Password:", os.getenv("DATABASE_PASSWORD")[:5], "..." if os.getenv("DATABASE_PASSWORD") else "❌ MISSING")
print("Database:", os.getenv("DATABASE"))
print("CA Path:", os.getenv("CA_CERT_PATH"))

# Establish secure connection
connection = MySQLdb.connect(
    host=os.getenv("DATABASE_HOST"),
    user=os.getenv("DATABASE_USERNAME"),
    passwd=os.getenv("DATABASE_PASSWORD"),
    db=os.getenv("DATABASE"),
    autocommit=True,
    ssl_mode="VERIFY_IDENTITY",
    ssl={"ca": os.getenv("CA_CERT_PATH")}
)

try:
    cursor = connection.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    print("✅ Tables in the database:")
    for table in tables:
        print("-", table[0])

except MySQLdb.Error as e:
    print("❌ MySQL Error:", e)

finally:
    cursor.close()
    connection.close()
