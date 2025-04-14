import mysql.connector
import os
from werkzeug.security import generate_password_hash
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Wait for database to be ready
def wait_for_db(host, user, password, max_attempts=10, delay=5):
    for attempt in range(max_attempts):
        try:
            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password
            )
            conn.close()
            logger.info("Database connection successful")
            return True
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt+1}/{max_attempts} failed: {e}")
            time.sleep(delay)
    
    logger.error("Failed to connect to database after maximum attempts")
    return False

def init_db():
    # Get database config from environment variables
    host = os.environ.get('MYSQL_HOST', 'localhost')
    user = os.environ.get('MYSQL_USER', 'rocket_user')
    password = os.environ.get('MYSQL_PASSWORD', 'RocketUser123!')
    db_name = os.environ.get('MYSQL_DB', 'rocket_data_system')
    
    # Wait for database to be ready
    if not wait_for_db(host, user, password):
        return False
    
    try:
        # Connect to the database
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"USE {db_name}")
        
        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role ENUM('user', 'admin') DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create rockets table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS rockets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            type VARCHAR(100),
            country VARCHAR(100),
            status VARCHAR(100),
            image_path VARCHAR(255),
            description TEXT,
            submitted_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (submitted_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """)
        
        # Create thoughts table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS thoughts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)
        
        # Create contact_messages table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)
        
        # Create default admin user if one doesn't exist
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'AdminPass123!')
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            hashed_password = generate_password_hash(admin_password, method='pbkdf2:sha256')
            cursor.execute(
                "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'admin')",
                (admin_username, admin_email, hashed_password)
            )
            logger.info(f"Created default admin user: {admin_username}")
        
        # Commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Database initialization completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False

if __name__ == "__main__":
    init_db()
