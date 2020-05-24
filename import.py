import os
import csv
from application import db
import requests
api_key = os.getenv('API_KEY')


def api_res(isbn):
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
                       params={"key": api_key, "isbns": isbn})
    if res.status_code == 200:
        bk = res.json()['books'][0]
        return bk.get('work_ratings_count'), bk.get('average_rating')


file = open("books.csv")

reader = csv.reader(file)
next(reader)
for isbn, title, author, year in reader:
    review_count, average_score = api_res(isbn)

    db.execute("INSERT INTO books (isbn, title, author, year, review_count, average_score) VALUES (:isbn, :title, :author, :year, :review_count, :average_score)",
               {"isbn": isbn,
                "title": title,
                "author": author,
                "year": year,
                "review_count": review_count,
                "average_score": average_score})
    # print(isbn, title, author, year)
    print(f"Added book {title} to database.")

    db.commit()
