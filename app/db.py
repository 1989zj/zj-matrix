import os
from pymongo import MongoClient

# ── MongoDB 连接 ──
# In a real production app, these should be in environment variables or a config file.
MONGO_URI = os.environ.get('MONGO_URI', "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
db = client['novel_factory']

novels_col = db['projects']
chapters_col = db['chapter_memory']
reports_col = db['legacy_reports']
orders_col = db['orders']
settings_col = db['settings']
users_col = db['users']
notifications_col = db['notifications']
sms_codes_col = db['sms_codes']
drafts_col = db['drafts']
