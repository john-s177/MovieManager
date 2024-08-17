from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv
import os
import mysql.connector
from flask_bootstrap import Bootstrap5
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import requests

load_dotenv()
API_KEY = os.getenv('API_KEY')
URL = 'https://api.themoviedb.org/3/search/movie?query=hereditary&include_adult=true&language=en-US&page=1'
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
Bootstrap5(app)

class RateMovieForm(FlaskForm):
    rating = StringField("Your Rating Out of 10 e.g. 7.5", validators=[DataRequired()])
    review = StringField("Your Review", validators=[DataRequired()])
    submit = SubmitField("Done")

class AddMovieForm(FlaskForm):
    name = StringField("Movie Name", validators=[DataRequired()])
    submit = SubmitField("Done")

# Database connection
try:
    connection = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    print("Connection successful")
except mysql.connector.Error as err:
    print(f"Error: {err}")

cursor = connection.cursor()

@app.route("/")
def home():
    query = "SELECT * FROM movies ORDER BY rating DESC"
    cursor.execute(query)
    all_movies = cursor.fetchall()

    ranked_movies = []
    total_movies = len(all_movies)
    for i, movie in enumerate(all_movies):
        movie_with_ranking = list(movie) 
        movie_with_ranking.append(total_movies - i)  
        ranked_movies.append(movie_with_ranking)

    return render_template("index.html", movies=ranked_movies)


@app.route("/edit", methods=["GET", "POST"])
def rate_movie():
    form = RateMovieForm()
    movie_id = request.args.get("id")

    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()
    print(movie)
    
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
def delete_movie():
    movie_id = request.args.get("id") 

    if movie_id:
        query = "DELETE FROM movies WHERE id = %s"
        data = (movie_id,)
        cursor.execute(query, data)
        connection.commit()
    
    return redirect(url_for('home'))


@app.route("/add", methods=["GET", "POST"])
def add_movie():
    form = AddMovieForm()
    
    if form.validate_on_submit():
        movie_title = form.name.data
        response = requests.get(URL, params={"api_key": API_KEY, "query": movie_title})
        data = response.json()["results"]
        return render_template("select.html", options=data)

    return render_template("add.html", form=form)

@app.route("/find")
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

        query = "INSERT INTO movies (title, year, description, img_url) VALUES (%s, %s, %s, %s)"
        db_data = (title, year, description, img_url)
        cursor.execute(query, db_data)
        connection.commit()
        cursor.execute("select id from movies where title=%s", (title,))
        movie=cursor.fetchone()

        return redirect(url_for("rate_movie", id=movie[0]))

if __name__ == '__main__':
    app.run(debug=True)
