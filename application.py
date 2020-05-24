import os
from flask import Flask, session, render_template, request, flash, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
import requests


app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

if not os.getenv('API_KEY'):
    raise RuntimeError('API_KEY is not set')

# Global var
MAX_COMMENT_LEN = 1000
GOOD_READ_API = 'https://www.goodreads.com/book/review_counts.json'
# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))
api_key = os.getenv('API_KEY')


@app.route("/")
def index():
    return render_template("index.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        flash('You have already logged in.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        q = 'select * from users where username = :username'
        user = db.execute(q, {'username': username}).fetchone()
        if not user or username != user.username or password != user.password:
            flash('Invalid credentials, try again.')
        else:
            flash(f'Hi, {username.title()}, you have logged in.')
            session['user_id'] = user.id
            return redirect(url_for('search'))
    return render_template('form.html')


@app.route("/register", methods=["post", "get"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirmed_password = request.form["password-confirm"]
        username_existed = len(db.execute('select username from users where username = :username', {
            'username': username}).fetchall())
        if username_existed:
            flash("Username existed.")
        elif password != confirmed_password:
            flash("Password unmatched.")
        else:
            insert_q = "insert into users (username, password) values (:username, :password)"
            db.execute(insert_q, {'username': username, 'password': password})
            db.commit()
            flash("you have registered.")
            return redirect(url_for('login'))
    return render_template("form.html")


@app.route("/search", methods=["GET", "POST"])
def search():
    if session.get('user_id') is None:
        flash('Please login')
        return redirect(url_for('login'))
    if request.method == "POST":
        key = request.form.get("query")
        if not key:
            flash('Please provide a search key')
            return redirect(url_for('search'))
        sel_query = "select * from books where title like :key or isbn like :key or author like :key"
        books = db.execute(
            sel_query, {'key': '%' + key.title() + '%'}).fetchall()
        flash(f'{len(books)} books found.')
        return render_template("search.html", books=books)
    return render_template("search.html")


@app.route("/<string:isbn>", methods=['GET', 'POST'])
def book(isbn: str):

    if session.get('user_id') is None:
        flash('Please login.')
        return redirect(url_for('login'))

    q = "select * from books where isbn= :isbn"
    book = db.execute(q, {'isbn': isbn}).fetchone()

    if book is None:
        flash(f'ISBN: {isbn} is not in our database.')
        return redirect(url_for('search'))

    api_rating = good_read_api(isbn, 'average_rating')
    usr_payload = {'user_id': session['user_id'], 'isbn': isbn}
    usr_review = db.execute(
        'select * from reviews where user_id = :user_id and isbn = :isbn', usr_payload).fetchone()

    if request.method == "POST":
        review_patload = {
            'rating': request.form.get("rating"),
            'comment': request.form.get("comment")
        }

        if review_patload['rating'] is None:
            flash(f'Please submit you rating for {book.title}.')
        elif review_patload['comment'] and len(review_patload['comment']) > MAX_COMMENT_LEN:
            flash(f'Comment must be less than {MAX_COMMENT_LEN} character')
        elif usr_review:
            flash(
                f'You have reviewed {book.title} for {usr_review.rating} out of 5.')
        else:
            insert_q = "insert into reviews (user_id, isbn, rating, comment) values (:user_id, :isbn, :rating, :comment);"
            db.execute(insert_q, {**usr_payload, **review_patload})
            db.commit()
            flash(
                f'You have reviewed {book.title} for {review_patload["rating"]} out of 5.')
            return redirect(url_for('book', isbn=isbn))

    sel_q = 'select * from reviews join users on (users.id = reviews.user_id) where isbn = :isbn'
    reviews = db.execute(sel_q, {'isbn': isbn}).fetchall()
    return render_template('book.html', book=book, api_rating=api_rating, reviews=reviews, usr_review=usr_review)


@app.route("/api/<string:isbn>", methods=["GET"])
def api(isbn: str):
    sel_bk = 'select * from books where isbn = :isbn'
    bk = db.execute(sel_bk, {'isbn': isbn}).fetchone()
    if bk is None:
        return jsonify({'error': 'isbn not existed'}), 422
    book = dict(bk.items())
    sel_rw = 'select avg(rating) as average_score, count(*) as review_count from reviews where isbn = :isbn'
    rw = db.execute(sel_rw, {'isbn': isbn}).fetchone()
    if rw is None:
        rw = {"review_count": 0.0, "average_score": None}
    review = dict(rw.items())
    return jsonify({**book, **review}), 200


@app.route("/logout")
def logout():
    session.pop('user_id', None)
    flash('you have logged out.')
    return redirect(url_for('index'))


def good_read_api(isbn, field):
    res = requests.get(GOOD_READ_API,
                       params={"key": api_key, "isbns": isbn})
    if res.status_code == 200:
        bk = res.json()['books'][0]
        return bk.get(field)
