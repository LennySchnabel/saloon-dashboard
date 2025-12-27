import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import plotly.express as px
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Saloon Dashboard", layout="wide")

DB = "saloon.db"

# ---------------- DATABASE ----------------
def get_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        stock INTEGER,
        buy_price REAL,
        sell_price REAL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity INTEGER,
        sale_time TEXT
    )
    """)

    # Default Admin
    c.execute("SELECT * FROM users")
    if not c.fetchall():
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", hash_pw("admin"), "admin")
        )

    conn.commit()
    conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ---------------- LOGIN ----------------
def login():
    st.title("🔐 Login")

    user = st.text_input("Benutzername")
    pw = st.text_input("Passwort", type="password")

    if st.button("Login"):
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT username, role FROM users WHERE username=? AND password=?",
            (user, hash_pw(pw))
        )
        result = c.fetchone()
        conn.close()

        if result:
            st.session_state.user = result[0]
            st.session_state.role = result[1]
            st.rerun()
        else:
            st.error("Falsche Login-Daten")

# ---------------- PRODUCTS ----------------
def products_page():
    st.header("📦 Produkte & Lager")

    conn = get_conn()

    df = pd.read_sql("SELECT * FROM products", conn)

    st.subheader("➕ Produkt hinzufügen")
    with st.form("add_product"):
        name = st.text_input("Name")
        stock = st.number_input("Lagerbestand", 0, 10000)
        buy = st.number_input("Einkaufspreis", 0.0)
        sell = st.number_input("Verkaufspreis", 0.0)
        if st.form_submit_button("Speichern"):
            conn.execute(
                "INSERT INTO products (name, stock, buy_price, sell_price) VALUES (?, ?, ?, ?)",
                (name, stock, buy, sell)
            )
            conn.commit()
            st.rerun()

    st.subheader("📋 Übersicht")
    st.dataframe(df, use_container_width=True)

# ---------------- SALES ----------------
def sales_page():
    st.header("💰 Verkauf")

    conn = get_conn()
    products = pd.read_sql("SELECT * FROM products", conn)

    if products.empty:
        st.warning("Keine Produkte vorhanden")
        return

    product = st.selectbox("Produkt", products["name"])
    qty = st.number_input("Menge", 1, 100)

    if st.button("Verkaufen"):
        p = products[products["name"] == product].iloc[0]
        conn.execute(
            "INSERT INTO sales (product_id, quantity, sale_time) VALUES (?, ?, ?)",
            (p["id"], qty, datetime.now().isoformat())
        )
        conn.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (qty, p["id"])
        )
        conn.commit()
        st.success("Verkauf gespeichert")

# ---------------- ANALYTICS ----------------
def analytics_page():
    st.header("📊 Analyse")

    conn = get_conn()

    df = pd.read_sql("""
        SELECT
            s.sale_time,
            p.name,
            s.quantity,
            p.sell_price,
            p.buy_price,
            s.quantity * p.sell_price AS revenue,
            s.quantity * (p.sell_price - p.buy_price) AS profit
        FROM sales s
        JOIN products p ON s.product_id = p.id
    """, conn)

    if df.empty:
        st.info("Noch keine Verkäufe")
        return

    fig1 = px.line(df, x="sale_time", y="revenue", title="Umsatz")
    fig2 = px.line(df, x="sale_time", y="profit", title="Gewinn")

    c1, c2 = st.columns(2)
    c1.plotly_chart(fig1, use_container_width=True)
    c2.plotly_chart(fig2, use_container_width=True)

# ---------------- USERS (ADMIN) ----------------
def users_page():
    st.header("👥 Benutzer (Admin)")

    conn = get_conn()
    users = pd.read_sql("SELECT id, username, role FROM users", conn)
    st.dataframe(users, use_container_width=True)

    with st.form("add_user"):
        u = st.text_input("Username")
        p = st.text_input("Passwort")
        r = st.selectbox("Rolle", ["admin", "staff"])
        if st.form_submit_button("Erstellen"):
            conn.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (u, hash_pw(p), r)
            )
            conn.commit()
            st.rerun()

# ---------------- MAIN ----------------
init_db()

if "user" not in st.session_state:
    login()
else:
    st.sidebar.success(f"👤 {st.session_state.user} ({st.session_state.role})")

    page = st.sidebar.radio(
        "Navigation",
        ["Produkte", "Verkauf", "Analyse", "Benutzer"]
        if st.session_state.role == "admin"
        else ["Produkte", "Verkauf", "Analyse"]
    )

    if page == "Produkte":
        products_page()
    elif page == "Verkauf":
        sales_page()
    elif page == "Analyse":
        analytics_page()
    elif page == "Benutzer":
        users_page()
