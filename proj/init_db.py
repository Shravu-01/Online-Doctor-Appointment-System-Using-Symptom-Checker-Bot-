import sys
from pathlib import Path
from sqlalchemy import inspect

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from proj import create_app, db

# Create app instance
app = create_app()

def init_db():
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if not existing_tables:
                db.create_all()
                print("Database tables created successfully!")
            else:
                print("Database tables already exist")
                
        except Exception as e:
            print(f"⚠️ Error: {e}")
            print("Try deleting 'site.db' and running again")

if __name__ == '__main__':
    init_db()


