#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de migration pour ajouter le champ essayage_boutique à la table retouche
"""

import sqlite3
import os

def migrate_database():
    db_path = os.path.join(os.path.dirname(__file__), 'retouches.db')
    
    if not os.path.exists(db_path):
        print("Base de données introuvable.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Vérifier si la colonne existe déjà
        cursor.execute("PRAGMA table_info(retouche)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'essayage_boutique' not in columns:
            print("Ajout de la colonne essayage_boutique...")
            cursor.execute("ALTER TABLE retouche ADD COLUMN essayage_boutique BOOLEAN DEFAULT 0")
            conn.commit()
            print("Migration réussie !")
        else:
            print("La colonne essayage_boutique existe déjà.")
        
        conn.close()
        
    except Exception as e:
        print(f"Erreur lors de la migration : {e}")

if __name__ == "__main__":
    migrate_database()
