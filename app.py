import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import hashlib
from datetime import datetime

# ===================== CONFIG =====================
st.set_page_config(page_title="Salon Dashboard", layout="wide")

DB = "salon.db"

# ===================== DB =====================
def get_db():
    return sqlite3.connect(DB, check_same_thread=False)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    db = get_db()
    c = db.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        buy_price REAL,
        sell_price REAL,
        stock INTEGER
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity INTEGER,
        time TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        amount REAL,
        time TEXT
    )""")

    # Admin anlegen falls nicht vorhanden
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username,password,role) VALUES (?,?,?)",
            ("admin", hash_pw("admin"), "admin")
        )

    db.commit()
    db.close()

init_db()

# ===================== LOGIN =====================
def login():
    st.title("🔐 Login")

    user = st.text_input("Benutzername")
    pw = st.text_input("Passwort", type="password")

    if st.button("Login"):
        db = get_db()
        c = db.cursor()
        c.execute(
            "SELECT username, role FROM users WHERE username=? AND password=?",
            (user, hash_pw(pw))
        )
        res = c.fetchone()
        db.close()

        if res:
            st.session_state.user = res[0]
            st.session_state.role = res[1]
            st.rerun()
        else:
            st.error("Login fehlgeschlagen")

if "user" not in st.session_state:
    login()
    st.stop()

# ===================== SIDEBAR =====================
st.sidebar.success(f"Eingeloggt als {st.session_state.user}")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Produkte", "Verkauf", "Ausgaben", "Benutzer"]
)

# ===================== DASHBOARD =====================
if page == "Dashboard":
    st.title("📊 Übersicht")

    db = get_db()

    sales = pd.read_sql("""
        SELECT s.quantity, p.sell_price, p.buy_price
        FROM sales s JOIN products p ON s.product_id = p.id
    """, db)

    expenses = pd.read_sql("SELECT amount FROM expenses", db)
    products = pd.read_sql("SELECT * FROM products", db)
    db.close()

    revenue = (sales.quantity * sales.sell_price).sum() if not sales.empty else 0
    profit = (sales.quantity * (sales.sell_price - sales.buy_price)).sum() if not sales.empty else 0
    cost = expenses.amount.sum() if not expenses.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Umsatz", f"{revenue:.2f} €")
    c2.metric("Gewinn", f"{profit:.2f} €")
    c3.metric("Ausgaben", f"{cost:.2f} €")
    c4.metric("Lagerartikel", len(products))

    st.divider()

    if not sales.empty:
        chart = sales.copy()
        chart["Umsatz"] = chart.quantity * chart.sell_price
        st.plotly_chart(px.bar(chart, y="Umsatz", title="Umsatz"), use_container_width=True)

# ===================== PRODUKTE =====================
elif page == "Produkte":
    st.title("📦 Produkte & Lager")

    db = get_db()
    products = pd.read_sql("SELECT * FROM products", db)

    st.subheader("➕ Produkt hinzufügen")
    with st.form("add_product"):
        name = st.text_input("Name")
        buy = st.number_input("Einkaufspreis", 0.0)
        sell = st.number_input("Verkaufspreis", 0.0)
        stock = st.number_input("Lagerbestand", 0, step=1)
        if st.form_submit_button("Speichern"):
            db.execute(
                "INSERT INTO products (name,buy_price,sell_price,stock) VALUES (?,?,?,?)",
                (name, buy, sell, stock)
            )
            db.commit()
            st.rerun()

    st.subheader("📋 Produktliste")
    for _, p in products.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3,2,2,2])
            c1.write(f"**{p.name}**")
            c2.write(f"Lager: {p.stock}")
            new_stock = c3.number_input("Anpassen", value=p.stock, key=f"s{p.id}")
            if c3.button("Update", key=f"u{p.id}"):
                db.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, p.id))
                db.commit()
                st.rerun()
            if c4.button("🗑️ Löschen", key=f"d{p.id}"):
                db.execute("DELETE FROM products WHERE id=?", (p.id,))
                db.commit()
                st.rerun()

    db.close()

# ===================== VERKAUF =====================
elif page == "Verkauf":
    st.title("🛒 Verkauf")

    db = get_db()
    products = pd.read_sql("SELECT * FROM products", db)

    if products.empty:
        st.warning("Keine Produkte vorhanden")
    else:
        prod = st.selectbox("Produkt", products.name)
        qty = st.number_input("Menge", 1, step=1)

        if st.button("Verkaufen"):
            p = products[products.name == prod].iloc[0]
            if p.stock >= qty:
                db.execute("INSERT INTO sales VALUES (NULL,?,?,?)",
                           (p.id, qty, datetime.now().isoformat()))
                db.execute("UPDATE products SET stock=stock-? WHERE id=?", (qty, p.id))
                db.commit()
                st.success("Verkauf gespeichert")
            else:
                st.error("Nicht genug Lagerbestand")

    db.close()

# ===================== AUSGABEN =====================
elif page == "Ausgaben":
    st.title("💸 Ausgaben")

    db = get_db()

    with st.form("expense"):
        title = st.text_input("Bezeichnung")
        amount = st.number_input("Betrag", 0.0)
        if st.form_submit_button("Speichern"):
            db.execute(
                "INSERT INTO expenses VALUES (NULL,?,?,?)",
                (title, amount, datetime.now().isoformat())
            )
            db.commit()
            st.rerun()

    expenses = pd.read_sql("SELECT * FROM expenses", db)
    st.dataframe(expenses, use_container_width=True)
    db.close()

# ===================== BENUTZER =====================
elif page == "Benutzer":
    if st.session_state.role != "admin":
        st.error("Nur Admin")
        st.stop()

    st.title("👥 Benutzerverwaltung")
    db = get_db()

    with st.form("add_user"):
        u = st.text_input("Benutzername")
        p = st.text_input("Passwort", type="password")
        r = st.selectbox("Rolle", ["admin", "mitarbeiter"])
        if st.form_submit_button("Anlegen"):
            db.execute(
                "INSERT INTO users VALUES (NULL,?,?,?)",
                (u, hash_pw(p), r)
            )
            db.commit()
            st.rerun()

    users = pd.read_sql("SELECT id,username,role FROM users", db)
    for _, u in users.iterrows():
        with st.container(border=True):
            st.write(f"{u.username} ({u.role})")
            if u.username != "admin":
                if st.button("🗑️ Löschen", key=f"du{u.id}"):
                    db.execute("DELETE FROM users WHERE id=?", (u.id,))
                    db.commit()
                    st.rerun()

    db.close()
