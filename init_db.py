# init_db.py
from app import app, db
from werkzeug.security import generate_password_hash
import os

def init_db():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if admin user exists
        from sqlalchemy import text
        result = db.session.execute(text("SELECT COUNT(*) FROM users WHERE role = 'admin'"))
        admin_count = result.scalar()
        
        # Create default admin if none exists
        if not admin_count:
            admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
            admin_password = os.environ.get('ADMIN_PASSWORD', 'AdminPass123!')
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
            hashed_password = generate_password_hash(admin_password, method='pbkdf2:sha256')
            
            db.session.execute(text(
                "INSERT INTO users (username, email, password, role) VALUES (:username, :email, :password, 'admin')"
            ), {"username": admin_username, "email": admin_email, "password": hashed_password})
            db.session.commit()
            print(f"Created default admin user: {admin_username}")
        
        print("Database initialization completed successfully")

if __name__ == "__main__":
    init_db()
