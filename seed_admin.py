from werkzeug.security import generate_password_hash
from pymongo import MongoClient
import os

MONGO_URI = os.environ.get('MONGO_URI', "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/")
client = MongoClient(MONGO_URI)
db = client['novel']
users_col = db['users']

def seed_admin():
    username = 'admin'
    password = 'password123' # Default password
    
    if users_col.find_one({'username': username}):
        print("Admin user already exists.")
        return

    hashed_pw = generate_password_hash(password)
    users_col.insert_one({
        'username': username,
        'password': hashed_pw,
        'role': 'admin',
        'email': 'admin@example.com'
    })
    print(f"Admin user created. Username: {username}, Password: {password}")

if __name__ == '__main__':
    seed_admin()
