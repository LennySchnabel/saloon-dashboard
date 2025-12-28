import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import hashlib
import plotly.express as px

# ---------------- CONFIG ----------------
st.set_page_config("Salon Dashboard", layout="wide")

# ---------------- DB ----------------
def db():
    return sqlite3.connect("salon.db", check_same_thread=False)

conn = db()
c = conn.cursor()

# ---------------- TABLES ----------------
c.executescript("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    buy REAL,
    sell REAL,
    stock INTEGER
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product TEXT,
    qty INTEGER,
    revenue REAL,
    profit REAL,
    time TEXT
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    amount REAL,
    time TEXT
);

CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT,
    start TEXT,
    end TEXT,
    cash_start REAL,
    cash_end REAL,
    diff REAL
);
""")
conn.commit()

# ---------------- HELPERS ----------------
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# Create default admin
c.execute("SELECT * FROM users")
if not c.fetchall():
    c.execute("INSERT INTO users VALUES (NULL,?,?,?)",
              ("admin", hash_pw("admin"), "admin"))
    conn.commit()

# ---------------- LOGIN ----------------
def login():
    st.title("🔐 Login")
    u = st.text_input("Benutzer")
    p = st.text_input("Passwort", type="password")

    if st.button("Login"):
        c.execute("SELECT role FROM users WHERE username=? AND password=?",
                  (u, hash_pw(p)))
        r = c.fetchone()
        if r:
            st.session_state.user = u
            st.session_state.role = r[0]
            st.rerun()
        else:
            st.error("Falsch")

# ---------------- DASHBOARD ----------------
def dashboard():
    st.title("📊 Dashboard")

    sales = pd.read_sql("SELECT * FROM sales", conn)
    expenses = pd.read_sql("SELECT * FROM expenses", conn)

    revenue = sales["revenue"].sum() if not sales.empty else 0
    profit = sales["profit"].sum() if not sales.empty else 0
    costs = expenses["amount"].sum() if not expenses.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Umsatz", f"{revenue:.2f} €")
    c2.metric("Gewinn", f"{profit:.2f} €")
    c3.metric("Ausgaben", f"{costs:.2f} €")

    if not sales.empty:
        sales["time"] = pd.to_datetime(sales["time"])
        fig = px.line(sales, x="time", y="revenue", title="Umsatz Verlauf")
        st.plotly_chart(fig, use_container_width=True)

# ---------------- SALES ----------------
def sales_page():
    st.title("🧾 Verkauf eintragen")

    products = pd.read_sql("SELECT * FROM products", conn)
    if products.empty:
        st.info("Keine Produkte")
        return

    name = st.selectbox("Produkt", products["name"])
    qty = st.number_input("Menge", 1, 100, 1)

    if st.button("Verkauf speichern"):
        p = products[products["name"] == name].iloc[0]
        if p["stock"] < qty:
            st.error("Nicht genug Lagerbestand")
            return

        revenue = qty * p["sell"]
        profit = qty * (p["sell"] - p["buy"])

        c.execute("INSERT INTO sales VALUES (NULL,?,?,?,?,?)",
                  (name, qty, revenue, profit, datetime.now()))
        c.execute("UPDATE products SET stock = stock - ? WHERE name=?",
                  (qty, name))
        conn.commit()
        st.success("Gespeichert")
        st.rerun()

# ---------------- PRODUCTS ----------------
def products_page():
    st.title("📦 Produkte")

    with st.form("addp"):
        n = st.text_input("Name")
        b = st.number_input("Einkauf", 0.0)
        s = st.number_input("Verkauf", 0.0)
        stck = st.number_input("Lager", 0)
        if st.form_submit_button("Hinzufügen"):
            c.execute("INSERT INTO products VALUES (NULL,?,?,?,?)",
                      (n, b, s, stck))
            conn.commit()
            st.rerun()

    df = pd.read_sql("SELECT * FROM products", conn)
    st.dataframe(df, use_container_width=True)

    delp = st.selectbox("Produkt löschen", df["name"])
    if st.button("Löschen"):
        c.execute("DELETE FROM products WHERE name=?", (delp,))
        conn.commit()
        st.rerun()

# ---------------- STOCK UPDATE ----------------
def stock_page():
    st.title("🔄 Lager anpassen")

    df = pd.read_sql("SELECT * FROM products", conn)
    name = st.selectbox("Produkt", df["name"])
    qty = st.number_input("Neue Lagermenge", 0)

    if st.button("Aktualisieren"):
        c.execute("UPDATE products SET stock=? WHERE name=?", (qty, name))
        conn.commit()
        st.success("Aktualisiert")

# ---------------- SHIFTS ----------------
def shifts_page():
    st.title("🕒 Arbeitszeit & Kasse")

    cs = st.number_input("Kassenstand Start", 0.0)
    ce = st.number_input("Kassenstand Ende", 0.0)

    if st.button("Schicht speichern"):
        diff = ce - cs
        c.execute("INSERT INTO shifts VALUES (NULL,?,?,?,?,?,?)",
                  (st.session_state.user,
                   datetime.now(), datetime.now(),
                   cs, ce, diff))
        conn.commit()
        st.success(f"Differenz: {diff:.2f} €")

    st.dataframe(pd.read_sql("SELECT * FROM shifts", conn))

# ---------------- MAIN ----------------
if "user" not in st.session_state:
    login()
else:
    menu = st.sidebar.radio("Menü", [
        "Dashboard",
        "Verkäufe",
        "Produkte",
        "Lager",
        "Arbeitszeiten"
    ])

    if menu == "Dashboard":
        dashboard()
    elif menu == "Verkäufe":
        sales_page()
    elif menu == "Produkte":
        products_page()
    elif menu == "Lager":
        stock_page()
    elif menu == "Arbeitszeiten":
        shifts_page()
