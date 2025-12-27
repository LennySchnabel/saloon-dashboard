import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import hashlib
from datetime import datetime

# ------------------ CONFIG ------------------
st.set_page_config(page_title="Saloon Dashboard", layout="wide")

# ------------------ DATABASE ------------------
conn = sqlite3.connect("saloon.db", check_same_thread=False)
c = conn.cursor()

def init_db():
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
        sale_time TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        start_time TEXT,
        end_time TEXT,
        cash_start REAL,
        cash_end REAL
    )""")

    conn.commit()

    # Admin erstellen falls nicht existiert
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users VALUES (NULL, ?, ?, ?)",
            ("admin", hash_pw("admin"), "admin")
        )
        conn.commit()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

init_db()

# ------------------ LOGIN ------------------
def login():
    st.title("🔐 Login")

    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):
        c.execute(
            "SELECT username, role FROM users WHERE username=? AND password=?",
            (user, hash_pw(pw))
        )
        res = c.fetchone()
        if res:
            st.session_state.user = res[0]
            st.session_state.role = res[1]
            st.rerun()
        else:
            st.error("Falsche Login-Daten")

if "user" not in st.session_state:
    login()
    st.stop()

# ------------------ UI STYLE ------------------
st.markdown("""
<style>
.card {
    background: #1e1e1e;
    padding: 20px;
    border-radius: 15px;
    margin-bottom: 15px;
}
h1,h2,h3 { color: white; }
</style>
""", unsafe_allow_html=True)

# ------------------ SIDEBAR ------------------
st.sidebar.title("📊 Menü")
tab = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Produkte", "Verkäufe", "Analyse", "Schichten", "Benutzer"]
)

# ------------------ DASHBOARD ------------------
if tab == "Dashboard":
    st.title("📈 Übersicht")

    df = pd.read_sql("SELECT * FROM sales", conn)
    total_sales = len(df)

    st.markdown(f"""
    <div class='card'>
        <h2>Gesamtverkäufe</h2>
        <h1>{total_sales}</h1>
    </div>
    """, unsafe_allow_html=True)

# ------------------ PRODUKTE ------------------
if tab == "Produkte":
    st.title("📦 Produkte & Lager")

    with st.form("add_product"):
        name = st.text_input("Name")
        buy = st.number_input("Einkaufspreis", 0.0)
        sell = st.number_input("Verkaufspreis", 0.0)
        stock = st.number_input("Lagerbestand", 0, step=1)
        if st.form_submit_button("Hinzufügen"):
            c.execute(
                "INSERT INTO products VALUES (NULL, ?, ?, ?, ?)",
                (name, buy, sell, stock)
            )
            conn.commit()
            st.rerun()

    df = pd.read_sql("SELECT * FROM products", conn)
    st.dataframe(df)

    if not df.empty:
        pid = st.selectbox("Produkt auswählen", df["id"])
        new_stock = st.number_input("Lager anpassen", step=1)
        if st.button("Lager aktualisieren"):
            c.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, pid))
            conn.commit()
            st.rerun()

        if st.button("Produkt löschen"):
            c.execute("DELETE FROM products WHERE id=?", (pid,))
            conn.commit()
            st.rerun()

# ------------------ VERKÄUFE ------------------
if tab == "Verkäufe":
    st.title("🧾 Verkauf")

    df = pd.read_sql("SELECT * FROM products", conn)
    if df.empty:
        st.info("Keine Produkte")
    else:
        pid = st.selectbox("Produkt", df["id"])
        qty = st.number_input("Menge", 1, step=1)

        if st.button("Verkaufen"):
            c.execute(
                "INSERT INTO sales VALUES (NULL, ?, ?, ?)",
                (pid, qty, datetime.now().isoformat())
            )
            c.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, pid))
            conn.commit()
            st.success("Verkauf gespeichert")
            st.rerun()

# ------------------ ANALYSE ------------------
if tab == "Analyse":
    st.title("📊 Analyse")

    df = pd.read_sql("""
    SELECT s.sale_time,
           p.name,
           s.quantity,
           p.sell_price,
           p.buy_price,
           (s.quantity * p.sell_price) AS revenue,
           (s.quantity * (p.sell_price - p.buy_price)) AS profit
    FROM sales s
    JOIN products p ON s.product_id = p.id
    """, conn)

    if not df.empty:
        fig = px.bar(df, x="sale_time", y="revenue", title="Umsatz")
        st.plotly_chart(fig, use_container_width=True)
        st.metric("Gesamtgewinn", f"{df['profit'].sum():.2f} €")
    else:
        st.info("Keine Daten")

# ------------------ SCHICHTEN ------------------
if tab == "Schichten":
    st.title("⏱ Schichten")

    with st.form("shift"):
        cash_start = st.number_input("Kassenstand Anfang", 0.0)
        if st.form_submit_button("Schicht starten"):
            c.execute(
                "INSERT INTO shifts VALUES (NULL, ?, ?, NULL, ?, NULL)",
                (st.session_state.user, datetime.now().isoformat(), cash_start)
            )
            conn.commit()
            st.rerun()

    with st.form("end_shift"):
        cash_end = st.number_input("Kassenstand Ende", 0.0)
        if st.form_submit_button("Schicht beenden"):
            c.execute("""
            UPDATE shifts SET end_time=?, cash_end=?
            WHERE user=? AND end_time IS NULL
            """, (datetime.now().isoformat(), cash_end, st.session_state.user))
            conn.commit()
            st.rerun()

    st.dataframe(pd.read_sql("SELECT * FROM shifts", conn))

# ------------------ BENUTZER ------------------
if tab == "Benutzer" and st.session_state.role == "admin":
    st.title("👥 Benutzer")

    with st.form("user"):
        u = st.text_input("Username")
        p = st.text_input("Passwort")
        r = st.selectbox("Rolle", ["admin", "staff"])
        if st.form_submit_button("Erstellen"):
            c.execute(
                "INSERT INTO users VALUES (NULL, ?, ?, ?)",
                (u, hash_pw(p), r)
            )
            conn.commit()
            st.rerun()

    df = pd.read_sql("SELECT id, username, role FROM users", conn)
    st.dataframe(df)

    uid = st.selectbox("User löschen", df["id"])
    if st.button("Löschen"):
        c.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
        st.rerun()
