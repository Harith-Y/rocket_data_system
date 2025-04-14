from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import logging
from mysql.connector.errors import IntegrityError, OperationalError
import pymysql
from flask_sqlalchemy import SQLAlchemy

# Make PyMySQL work with SQLAlchemy's MySQL driver
pymysql.install_as_MySQLdb()

app = Flask(__name__)

# Flask configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'rocket_app_key')

# Database configuration
db_user = os.environ.get('MYSQLUSER', 'rocket_user')
db_password = os.environ.get('MYSQLPASSWORD', 'RocketUser123!')
db_host = os.environ.get('MYSQLHOST', 'localhost')
db_name = os.environ.get('MYSQLDATABASE', 'rocket_data_system')

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql://{db_user}:{db_password}@{db_host}/{db_name}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Logging setup
logging.basicConfig(level=logging.DEBUG, filename='app.log', format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.handlers = logging.getLogger().handlers

# Initialize MySQL
mysql = MySQL(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        if user:
            return User(user[0], user[1], user[2])
        app.logger.warning(f"User {user_id} not found")
        return None
    except Exception as e:
        app.logger.error(f"Error loading user {user_id}: {e}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return "Hello"

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'user')
        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('login.html')
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id, username, password, role FROM users WHERE username = %s AND role = %s", (username, role))
            user = cur.fetchone()
            cur.close()
            if user and check_password_hash(user[2], password):
                user_obj = User(user[0], user[1], user[3])
                login_user(user_obj)
                flash(f'Welcome, {user[1]}!', 'success')
                app.logger.info(f"Successful login: {username} as {role}")
                if user[3] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('dashboard'))
            flash('Invalid username, password, or role', 'danger')
        except Exception as e:
            app.logger.error(f"Login error for {username}: {e}")
            flash('An error occurred. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if not username or not email or not password:
            flash('All fields are required', 'danger')
            return render_template('register.html')
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'user')",
                        (username, email, hashed_password))
            mysql.connection.commit()
            cur.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            flash('Username or email already exists', 'danger')
        except Exception as e:
            app.logger.error(f"Registration error: {e}")
            flash('An error occurred during registration', 'danger')
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/submit_data', methods=['GET', 'POST'])
@login_required
def submit_data():
    if current_user.role == 'admin':
        flash('Admins cannot submit data', 'danger')
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        rocket_type = request.form.get('type', '').strip()
        country = request.form.get('country', '').strip()
        status = request.form.get('status', '').strip()
        description = request.form.get('description', '').strip()
        image = request.files.get('image')
        image_path = None
        if not name:
            flash('Rocket name is required', 'danger')
            app.logger.warning(f"Submit data failed: missing name, user={current_user.username}")
            return render_template('submit_data.html')
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            if image and image.filename:
                if not allowed_file(image.filename):
                    flash('Invalid image format. Use PNG, JPG, JPEG, or GIF.', 'danger')
                    app.logger.warning(f"Invalid image format: {image.filename}")
                    return render_template('submit_data.html')
                filename = f"{current_user.id}_{image.filename.replace(' ', '_')}"
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(image_path)
                image_path = f"uploads/{filename}"
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO rockets (name, type, country, status, image_path, description, submitted_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (name, rocket_type, country, status, image_path, description, current_user.id)
            )
            mysql.connection.commit()
            cur.close()
            flash('Rocket data submitted successfully', 'success')
            app.logger.info(f"Data submitted: name={name}, user={current_user.username}")
            return redirect(url_for('dashboard'))
        except Exception as e:
            app.logger.error(f"Submit data error: {str(e)}")
            flash('Error submitting data. Please try again.', 'danger')
    return render_template('submit_data.html')

@app.route('/view_data')
@login_required
def view_data():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, type, country, status, image_path, description FROM rockets ORDER BY created_at DESC")
        rockets = cur.fetchall()
        cur.execute("SELECT thoughts.content, thoughts.created_at, users.username FROM thoughts LEFT JOIN users ON thoughts.user_id = users.id ORDER BY thoughts.created_at DESC")
        comments = cur.fetchall()
        cur.execute("SELECT type, COUNT(*) as count FROM rockets GROUP BY type")
        type_data = cur.fetchall()
        cur.execute("SELECT country, COUNT(*) as count FROM rockets GROUP BY country")
        country_data = cur.fetchall()
        cur.execute("SELECT status, COUNT(*) as count FROM rockets GROUP BY status")
        status_data = cur.fetchall()
        cur.close()
        return render_template('view_data.html', rockets=rockets, comments=comments,
                             type_data=type_data, country_data=country_data, status_data=status_data)
    except Exception as e:
        app.logger.error(f"View data error: {e}")
        flash('Error loading data', 'danger')
        return render_template('view_data.html', rockets=[], comments=[], type_data=[], country_data=[], status_data=[])

@app.route('/data_hub')
@login_required
def data_hub():
    if current_user.role == 'admin':
        flash('Admins cannot access Data Hub', 'danger')
        return redirect(url_for('admin_dashboard'))
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, type, country, status, image_path, description FROM rockets WHERE submitted_by = %s ORDER BY created_at DESC", (current_user.id,))
        my_rockets = cur.fetchall()
        cur.execute("SELECT thoughts.content, thoughts.created_at, users.username FROM thoughts LEFT JOIN users ON thoughts.user_id = users.id ORDER BY thoughts.created_at DESC")
        thoughts = cur.fetchall()
        cur.execute("SELECT type, COUNT(*) as count FROM rockets GROUP BY type")
        type_data = cur.fetchall()
        cur.execute("SELECT country, COUNT(*) as count FROM rockets GROUP BY country")
        country_data = cur.fetchall()
        cur.execute("SELECT status, COUNT(*) as count FROM rockets GROUP BY status")
        status_data = cur.fetchall()
        cur.close()
        return render_template('data_hub.html', my_rockets=my_rockets, thoughts=thoughts,
                             type_data=type_data, country_data=country_data, status_data=status_data)
    except Exception as e:
        app.logger.error(f"Data hub error: {e}")
        flash('Error loading data hub', 'danger')
        return render_template('data_hub.html', my_rockets=[], thoughts=[], type_data=[], country_data=[], status_data=[])

@app.route('/thoughts', methods=['POST'])
@login_required
def thoughts():
    if current_user.role == 'admin':
        flash('Admins cannot post thoughts', 'danger')
        return redirect(url_for('admin_dashboard'))
    content = request.form.get('content', '').strip()
    if not content:
        flash('Thought content is required', 'danger')
        return redirect(url_for('data_hub'))
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO thoughts (user_id, content) VALUES (%s, %s)", (current_user.id, content))
        mysql.connection.commit()
        cur.close()
        flash('Thought posted successfully', 'success')
        return redirect(url_for('data_hub'))
    except Exception as e:
        app.logger.error(f"Thoughts post error: {e}")
        flash('Error posting thought', 'danger')
        return redirect(url_for('data_hub'))

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM rockets")
        rocket_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM contact_messages")
        message_count = cur.fetchone()[0]
        cur.close()
        return render_template('admin_dashboard.html', user_count=user_count, rocket_count=rocket_count, message_count=message_count)
    except Exception as e:
        app.logger.error(f"Admin dashboard error: {e}")
        flash('Error loading dashboard', 'danger')
        return render_template('admin_dashboard.html', user_count=0, rocket_count=0, message_count=0)

@app.route('/admin_manage_data')
@login_required
def admin_manage_data():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT rockets.id, rockets.name, rockets.type, rockets.country, rockets.status, users.username FROM rockets LEFT JOIN users ON rockets.submitted_by = users.id ORDER BY rockets.created_at DESC")
        rockets = cur.fetchall()
        cur.close()
        return render_template('admin_manage_data.html', rockets=rockets)
    except Exception as e:
        app.logger.error(f"Admin manage data error: {e}")
        flash('Error loading data', 'danger')
        return render_template('admin_manage_data.html', rockets=[])

@app.route('/admin_contact')
@login_required
def admin_contact():
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT contact_messages.message, contact_messages.created_at, users.username FROM contact_messages LEFT JOIN users ON contact_messages.user_id = users.id ORDER BY contact_messages.created_at DESC")
        messages = cur.fetchall()
        cur.close()
        return render_template('admin_contact.html', messages=messages)
    except Exception as e:
        app.logger.error(f"Admin contact error: {e}")
        flash('Error loading messages', 'danger')
        return render_template('admin_contact.html', messages=[])

@app.route('/delete_data/<int:id>')
@login_required
def delete_data(id):
    if current_user.role != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT image_path FROM rockets WHERE id = %s", (id,))
        image_path = cur.fetchone()
        if image_path and image_path[0] and os.path.exists(os.path.join('static', image_path[0])):
            os.remove(os.path.join('static', image_path[0]))
        cur.execute("DELETE FROM rockets WHERE id = %s", (id,))
        mysql.connection.commit()
        cur.close()
        flash('Data deleted successfully', 'success')
    except Exception as e:
        app.logger.error(f"Delete data error: {e}")
        flash('Error deleting data', 'danger')
    return redirect(url_for('admin_manage_data'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        new_email = request.form.get('email', '').strip()
        new_password = request.form.get('password', '').strip()
        if not new_username or not new_email:
            flash('Username and email are required', 'danger')
            return redirect(url_for('profile'))
        try:
            cur = mysql.connection.cursor()
            if new_username != current_user.username or new_email != current_user.email:
                cur.execute("SELECT id FROM users WHERE (username = %s OR email = %s) AND id != %s",
                            (new_username, new_email, current_user.id))
                if cur.fetchone():
                    cur.close()
                    flash('Username or email already exists', 'danger')
                    return redirect(url_for('profile'))
                cur.execute("UPDATE users SET username = %s, email = %s WHERE id = %s",
                            (new_username, new_email, current_user.id))
            if new_password:
                hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
                cur.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, current_user.id))
            mysql.connection.commit()
            cur.execute("SELECT id, username, role FROM users WHERE id = %s", (current_user.id,))
            user = cur.fetchone()
            current_user.username = user[1]
            cur.close()
            flash('Profile updated successfully', 'success')
        except Exception as e:
            app.logger.error(f"Profile update error: {e}")
            flash('Error updating profile', 'danger')
        return redirect(url_for('profile'))
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT email FROM users WHERE id = %s", (current_user.id,))
        email = cur.fetchone()[0]
        cur.close()
    except Exception as e:
        app.logger.error(f"Profile fetch error: {e}")
        flash('Error loading profile', 'danger')
        email = ''
    return render_template('profile.html', email=email)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    if current_user.role == 'admin':
        return redirect(url_for('admin_contact'))
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        if not message:
            flash('Message is required', 'danger')
            return redirect(url_for('contact'))
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO contact_messages (user_id, message) VALUES (%s, %s)", (current_user.id, message))
            mysql.connection.commit()
            cur.close()
            flash('Message sent successfully', 'success')
        except Exception as e:
            app.logger.error(f"Contact error: {e}")
            flash('Error sending message', 'danger')
        return redirect(url_for('contact'))
    return render_template('contact.html')
    
@app.route('/health')
def health():
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500
    
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    port = int(os.environ.get('MYSQLPORT', 8000))
    app.run(host='0.0.0.0', port=port)
