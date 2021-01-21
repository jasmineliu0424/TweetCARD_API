from flask import Flask
from flask_pymongo import PyMongo
app = Flask(__name__)
app.config['MONGO_URI'] = "mongodb://localhost:27017/customer"
mongo = PyMongo(app) 
#API_KEY="27a198d6-c2da-4fd4-9569-23f79b2d6dfa"