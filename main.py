from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
import os
import mysql.connector
import requests

# Load environment variables
load_dotenv()
API_KEY = os.getenv('API_KEY')
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
SECRET_KEY = os.getenv('SECRET_KEY')
URL = 'https://api.themoviedb.org/3/search/movie?query=hereditary&include_adult=true&language=en-US&page=1'

# Initialize Flask app and configure
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
Bootstrap5(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database connection
try:
    connection = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = connection.cursor()
    print("Database connection successful")
except mysql.connector.Error as err:
    print(f"Database connection error: {err}")

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, email, password):
        self.id = id
        self.email = email
        self.password = password

    @staticmethod
    def create_user(email, password):
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        return User(None, email, hashed_password)

    @staticmethod
    def verify_password(stored_password, provided_password):
        return check_password_hash(stored_password, provided_password)

@login_manager.user_loader
def load_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    data = cursor.fetchone()
    if data:
        return User(data[0], data[1], data[2])
    return None

# Forms
class RegisterForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")

class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class RateMovieForm(FlaskForm):
    rating = StringField("Your Rating Out of 10 e.g. 7.5", validators=[DataRequired()])
    review = StringField("Your Review", validators=[DataRequired()])
    submit = SubmitField("Done")

class AddMovieForm(FlaskForm):
    name = StringField("Movie Name", validators=[DataRequired()])
    submit = SubmitField("Done")

# Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        new_user = User.create_user(email, password)
        
        try:
            # Insert new user into the database
            query = "INSERT INTO users (email, password) VALUES (%s, %s)"
            cursor.execute(query, (new_user.email, new_user.password))
            connection.commit()
            print("User inserted into database")
            
            # Fetch the inserted user to log in
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_data = cursor.fetchone()
            if user_data:
                print(f"User fetched: {user_data}")
                login_user(User(user_data[0], user_data[1], user_data[2]))
                return redirect(url_for('home'))
            else:
                flash('Error occurred while fetching user data.', 'danger')
        except mysql.connector.Error as err:
            flash(f'Database error: {err}', 'danger')
            print(f"Database error: {err}")
    else:
        print("Form validation failed")
        print(form.errors)
    return render_template('register.html', form=form)



@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user_data = cursor.fetchone()
        if user_data and User.verify_password(user_data[2], password):
            user = User(user_data[0], user_data[1], user_data[2])
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/")
@login_required
def home():
    query = "SELECT * FROM movies WHERE user_id = %s ORDER BY rating DESC"
    cursor.execute(query, (current_user.id,))
    all_movies = cursor.fetchall()

    ranked_movies = []
    total_movies = len(all_movies)
    for i, movie in enumerate(all_movies):
        movie_with_ranking = list(movie)
        movie_with_ranking.append(total_movies - i)
        ranked_movies.append(movie_with_ranking)

    return render_template("index.html", movies=ranked_movies)

@app.route("/edit", methods=["GET", "POST"])
@login_required
def rate_movie():
    form = RateMovieForm()
    movie_id = request.args.get("id")

    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()

    if request.method == "GET":
        if movie:
            form.rating.data = movie[4]
            form.review.data = movie[5]  
    
    if form.validate_on_submit():
        rating = form.rating.data
        review = form.review.data
        
        query = "UPDATE movies SET rating = %s, review = %s WHERE id = %s"
        data = (rating, review, movie_id,)
        cursor.execute(query, data)
        connection.commit()
        
        return redirect(url_for('home'))

    return render_template("edit.html", movie=movie, form=form)

@app.route("/delete")
@login_required
def delete_movie():
    movie_id = request.args.get("id") 

    if movie_id:
        query = "DELETE FROM movies WHERE id = %s"
        data = (movie_id,)
        cursor.execute(query, data)
        connection.commit()
    
    return redirect(url_for('home'))

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_movie():
    form = AddMovieForm()
    
    if form.validate_on_submit():
        movie_title = form.name.data
        response = requests.get(URL, params={"api_key": API_KEY, "query": movie_title})
        data = response.json()["results"]
        return render_template("select.html", options=data)

    return render_template("add.html", form=form)

@app.route("/find")
@login_required
def find_movie():
    movie_api_id = request.args.get("id")
    if movie_api_id:
        movie_api_url = f"https://api.themoviedb.org/3/movie/{movie_api_id}"
        response = requests.get(movie_api_url, params={"api_key": API_KEY, "language": "en-US"})
        data = response.json()

        title = data["title"]
        year = data["release_date"].split("-")[0]
        img_url = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
        description = data["overview"]

        query = "INSERT INTO movies (title, year, description, img_url, user_id) VALUES (%s, %s, %s, %s, %s)"
        db_data = (title, year, description, img_url, current_user.id)
        cursor.execute(query, db_data)
        connection.commit()

        cursor.execute("SELECT id FROM movies WHERE title=%s AND user_id=%s", (title, current_user.id))
        movie = cursor.fetchone()

        return redirect(url_for("rate_movie", id=movie[0]))

if __name__ == '__main__':
    app.run(debug=True)
