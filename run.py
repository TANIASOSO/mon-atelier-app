from mon_atelier import app, db
from mon_atelier.routes import Categorie, seed_data

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not Categorie.query.first():
            seed_data()

    # Mode développement (debug + rechargement auto)
    app.run(debug=True)
