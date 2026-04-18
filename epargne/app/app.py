from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3, os
from datetime import datetime
from dateutil.relativedelta import relativedelta

app = Flask(__name__)
app.secret_key = "epargne-secret-2024"
DB_PATH = "/share/epargne/epargne.db"

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS enerfip_projets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            date_investissement TEXT NOT NULL,
            montant_investi REAL NOT NULL,
            taux_interet REAL NOT NULL,
            duree_mois INTEGER NOT NULL,
            date_fin TEXT,
            statut TEXT DEFAULT 'en cours',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS enerfip_flux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projet_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            montant REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY (projet_id) REFERENCES enerfip_projets(id)
        )
    """)
    conn.commit()
    conn.close()

def calcul_stats_projet(projet, flux):
    interets_recus = sum(f["montant"] for f in flux if f["type"] == "interet")
    capital_rembourse = sum(f["montant"] for f in flux if f["type"] == "remboursement")
    interets_theoriques = projet["montant_investi"] * (projet["taux_interet"] / 100) * (projet["duree_mois"] / 12)
    capital_restant = projet["montant_investi"] - capital_rembourse
    taux = min((interets_recus / interets_theoriques * 100) if interets_theoriques > 0 else 0, 100)
    return {
        "interets_recus": round(interets_recus, 2),
        "interets_theoriques": round(interets_theoriques, 2),
        "capital_rembourse": round(capital_rembourse, 2),
        "capital_restant": round(capital_restant, 2),
        "taux_avancement": round(taux, 1),
    }

def get_enerfip_stats():
    conn = get_db()
    projets = conn.execute("SELECT * FROM enerfip_projets").fetchall()
    total_investi = sum(p["montant_investi"] for p in projets)
    total_interets = 0
    for p in projets:
        flux = conn.execute("SELECT * FROM enerfip_flux WHERE projet_id = ?", (p["id"],)).fetchall()
        total_interets += sum(f["montant"] for f in flux if f["type"] == "interet")
    conn.close()
    return {
        "investi": round(total_investi, 2),
        "gains": round(total_interets, 2),
        "valeur": round(total_investi + total_interets, 2),
    }

# ── Dashboard ──
@app.route("/")
def dashboard():
    enerfip = get_enerfip_stats()
    total_investi = enerfip["investi"]
    total_gains = enerfip["gains"]
    total_patrimoine = enerfip["valeur"]
    return render_template("dashboard.html",
        active_page="dashboard",
        enerfip=enerfip,
        total_investi=total_investi,
        total_gains=total_gains,
        total_patrimoine=total_patrimoine,
    )

# ── Enerfip ──
@app.route("/enerfip")
def enerfip():
    conn = get_db()
    projets = conn.execute("SELECT * FROM enerfip_projets ORDER BY date_investissement DESC").fetchall()
    projets_avec_stats = []
    total_investi = 0
    total_interets = 0
    for p in projets:
        flux = conn.execute("SELECT * FROM enerfip_flux WHERE projet_id = ? ORDER BY date", (p["id"],)).fetchall()
        stats = calcul_stats_projet(p, flux)
        projets_avec_stats.append({"projet": p, "flux": flux, "stats": stats})
        total_investi += p["montant_investi"]
        total_interets += stats["interets_recus"]
    conn.close()
    return render_template("enerfip.html",
        active_page="enerfip",
        projets=projets_avec_stats,
        total_investi=round(total_investi, 2),
        total_interets=round(total_interets, 2),
    )

@app.route("/enerfip/projet/ajouter", methods=["POST"])
def enerfip_ajouter_projet():
    d = request.form
    date_debut = datetime.strptime(d["date_investissement"], "%Y-%m-%d")
    duree = int(d["duree_mois"])
    date_fin = (date_debut + relativedelta(months=duree)).strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("""
        INSERT INTO enerfip_projets (nom, date_investissement, montant_investi, taux_interet, duree_mois, date_fin, statut, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (d["nom"], d["date_investissement"], float(d["montant_investi"]),
          float(d["taux_interet"]), duree, date_fin,
          d.get("statut", "en cours"), d.get("notes", "")))
    conn.commit()
    conn.close()
    flash("Projet ajouté.", "success")
    return redirect(url_for("enerfip"))

@app.route("/enerfip/flux/ajouter", methods=["POST"])
def enerfip_ajouter_flux():
    d = request.form
    conn = get_db()
    conn.execute("""
        INSERT INTO enerfip_flux (projet_id, date, type, montant, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (int(d["projet_id"]), d["date"], d["type"], float(d["montant"]), d.get("notes", "")))
    conn.commit()
    conn.close()
    flash("Mouvement ajouté.", "success")
    return redirect(url_for("enerfip"))

@app.route("/enerfip/projet/supprimer/<int:projet_id>", methods=["POST"])
def enerfip_supprimer_projet(projet_id):
    conn = get_db()
    conn.execute("DELETE FROM enerfip_flux WHERE projet_id = ?", (projet_id,))
    conn.execute("DELETE FROM enerfip_projets WHERE id = ?", (projet_id,))
    conn.commit()
    conn.close()
    flash("Projet supprimé.", "info")
    return redirect(url_for("enerfip"))

@app.route("/enerfip/flux/supprimer/<int:flux_id>", methods=["POST"])
def enerfip_supprimer_flux(flux_id):
    conn = get_db()
    conn.execute("DELETE FROM enerfip_flux WHERE id = ?", (flux_id,))
    conn.commit()
    conn.close()
    flash("Mouvement supprimé.", "info")
    return redirect(url_for("enerfip"))

# ── Pages placeholder ──
@app.route("/pea")
def pea():
    return render_template("placeholder.html", active_page="pea", titre="PEA", sous_titre="Boursobank — Bientôt disponible")

@app.route("/epsor")
def epsor():
    return render_template("placeholder.html", active_page="epsor", titre="Epsor", sous_titre="Épargne salariale — Bientôt disponible")

@app.route("/binance")
def binance():
    return render_template("placeholder.html", active_page="binance", titre="Binance", sous_titre="Crypto — Bientôt disponible")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
