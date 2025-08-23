
from mon_atelier import app, db

# Create database tables if they don't exist
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Mode développement (debug + rechargement auto)
    app.run(debug=True)
