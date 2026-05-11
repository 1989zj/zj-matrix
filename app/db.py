import os
from pymongo import MongoClient

# ── MongoDB 连接 ──
# In a real production app, these should be in environment variables or a config file.
MONGO_URI = os.environ.get('MONGO_URI', "mongodb://mongo_8F6dTZ:mongo_dxx8nA@192.168.2.30:27017/")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
db = client['novel']

novels_col = db['novels']
chapters_col = db['chapters']
reports_col = db['reports']
orders_col = db['orders']
settings_col = db['settings']
users_col = db['users']  # New collection for Phase 2
notifications_col = db['notifications']  # New collection for Phase 4
sms_codes_col = db['sms_codes'] # Collection for SMS verification codes
