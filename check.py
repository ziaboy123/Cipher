from app import create_app
from app.extensions import db

flask_app = create_app()
with flask_app.app_context():
    db.create_all()
    inspector = db.inspect(db.engine)
    print("Tables:", inspector.get_table_names())
    print("OK")
