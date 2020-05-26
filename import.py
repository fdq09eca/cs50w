import os
import csv
from application import db
import requests
file = open("books.csv")

reader = csv.reader(file)
next(reader)  # skip the header
for isbn, title, author, year in reader:

    db.execute("INSERT INTO books (isbn, title, author, year, review_count, average_score) VALUES (:isbn, :title, :author, :year, :review_count, :average_score)",
               {"isbn": isbn,
                "title": title,
                "author": author,
                "year": year})

    print(f"Added book {title} to database.")

    db.commit()
