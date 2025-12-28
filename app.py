import streamlit as st
import sqlite3
import pandas as pd
import hashlib
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
        buy_price REAL,
        sell_price REAL,
        stock INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity INTEGER,
        time TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        amount REAL,
        time TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- AUTH ----------------
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login():
    st.title("🔐 Login")

    user = st.text_input("Username")
    pw = st.text_input("Passwort", type="password")

    if st.button("Login"):
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT username, role FROM users WHERE username=? AND password=?",
            (user, hash_pw(pw))
        )
        res = c.fetchone()
        conn.close()

        if res:
            st.session_state.user = res[0]
            st.session_state.role = res[1]
            st.rerun()
        else:
            st.error("Login fehlgeschlagen")

# ---------------- UI HELPERS ----------------
def card(title, value):
    st.markdown(
        f"""
        <div style="
            background:#1e1e1e;
            padding:20px;
            border-radius:16px;
            text-align:center;
            box-shadow:0 4px 12px rgba(0,0,0,.3)">
            <h4>{title}</h4>
            <h2>{value}</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------- MAIN ----------------
if "user" not in st.session_state:
    login()
    st.stop()

st.sidebar.success(f"👤 {st.session_state.user} ({st.session_state.role})")
page = st.sidebar.radio("Navigation", ["Dashboard", "Produkte", "Verkäufe", "Ausgaben", "Benutzer"])

conn = get_conn()

# ---------------- DASHBOARD ----------------
if page == "Dashboard":
    st.title("📊 Dashboard")

    sales = pd.read_sql("""
        SELECT s.quantity, p.sell_price, p.buy_price
        FROM sales s JOIN products p ON s.product_id=p.id
    """, conn)

    expenses = pd.read_sql("SELECT amount FROM expenses", conn)

    revenue = (sales["quantity"] * sales["sell_price"]).sum() if not sales.empty else 0
    profit = (sales["quantity"] * (sales["sell_price"] - sales["buy_price"])).sum() if not sales.empty else 0
    total_expenses = expenses["amount"].sum() if not expenses.empty else 0
    net_profit = profit - total_expenses

    c1, c2, c3, c4 = st.columns(4)
    with c1: card("Umsatz", f"{revenue:.2f} €")
    with c2: card("Gewinn", f"{profit:.2f} €")
    with c3: card("Ausgaben", f"{total_expenses:.2f} €")
    with c4: card("Netto", f"{net_profit:.2f} €")

# ---------------- PRODUKTE ----------------
elif page == "Produkte":
    st.title("📦 Produkte")

    name = st.text_input("Produktname")
    buy = st.number_input("Einkaufspreis", 0.0)
    sell = st.number_input("Verkaufspreis", 0.0)
    stock = st.number_input("Lagerbestand", 0)

    if st.button("Produkt hinzufügen"):
        conn.execute(
            "INSERT INTO products (name,buy_price,sell_price,stock) VALUES (?,?,?,?)",
            (name, buy, sell, stock)
        )
        conn.commit()
        st.rerun()

    df = pd.read_sql("SELECT * FROM products", conn)
    st.dataframe(df)

# ---------------- SALES ----------------
elif page == "Verkäufe":
    st.title("🛒 Verkauf")

    products = pd.read_sql("SELECT * FROM products", conn)
    if not products.empty:
        prod = st.selectbox("Produkt", products["name"])
        qty = st.number_input("Menge", 1)

        if st.button("Verkauf buchen"):
            pid = products[products["name"] == prod]["id"].values[0]
            conn.execute(
                "INSERT INTO sales (product_id, quantity, time) VALUES (?,?,?)",
                (pid, qty, datetime.now())
            )
            conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id=?",
                (qty, pid)
            )
            conn.commit()
            st.success("Verkauf gespeichert")

# ---------------- EXPENSES ----------------
elif page == "Ausgaben":
    st.title("💸 Ausgaben")

    title = st.text_input("Bezeichnung")
    amount = st.number_input("Betrag", 0.0)

    if st.button("Ausgabe speichern"):
        conn.execute(
            "INSERT INTO expenses (title, amount, time) VALUES (?,?,?)",
            (title, amount, datetime.now())
        )
        conn.commit()
        st.rerun()

    st.dataframe(pd.read_sql("SELECT * FROM expenses ORDER BY time DESC", conn))

# ---------------- USERS ----------------
elif page == "Benutzer" and st.session_state.role == "admin":
    st.title("👥 Benutzerverwaltung")

    u = st.text_input("Username")
    p = st.text_input("Passwort", type="password")
    r = st.selectbox("Rolle", ["admin", "mitarbeiter"])

    if st.button("Benutzer anlegen"):
        conn.execute(
            "INSERT INTO users (username,password,role) VALUES (?,?,?)",
            (u, hash_pw(p), r)
        )
        conn.commit()
        st.success("Benutzer erstellt")

    st.dataframe(pd.read_sql("SELECT id, username, role FROM users", conn))

conn.close()
