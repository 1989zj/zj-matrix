from app import create_app
from dotenv import load_dotenv
import os

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = create_app()

if __name__ == '__main__':
    # On Windows, threaded=True can sometimes cause [WinError 10038] during reloads.
    # Setting threaded=False or disabling the reloader can stabilize it.
    app.run(host='0.0.0.0', port=5003, debug=True, threaded=False)
