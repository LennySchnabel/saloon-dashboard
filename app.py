import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime
import plotly.express as px

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Saloon Dashboard", layout="wide")

DB = "saloon.db"

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect(DB, check_same_thread=False)

conn = get_db()
c = conn.cursor()

def init_db():
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
        sale_time TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        amount REAL,
        date TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        start_time TEXT,
        end_time TEXT,
        cash_start REAL,
        cash_end REAL
    )
    """)

    conn.commit()

    # Default Admin
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

# ---------------- LOGIN ----------------
def login():
    st.title("🔐 Login")

    user = st.text_input("Benutzername")
    pw = st.text_input("Passwort", type="password")

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
            st.error("Falsche Zugangsdaten")

# ---------------- DASHBOARD ----------------
def dashboard():
    st.title("📊 Saloon Dashboard")

    # ===== KPI =====
    sales_df = pd.read_sql("""
        SELECT s.quantity, p.sell_price, p.buy_price
        FROM sales s JOIN products p ON s.product_id=p.id
    """, conn)

    expenses_df = pd.read_sql("SELECT * FROM expenses", conn)

    revenue = (sales_df["quantity"] * sales_df["sell_price"]).sum()
    profit = (sales_df["quantity"] * (sales_df["sell_price"] - sales_df["buy_price"])).sum()
    expenses = expenses_df["amount"].sum() if not expenses_df.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Umsatz", f"{revenue:.2f} €")
    col2.metric("📈 Gewinn", f"{profit:.2f} €")
    col3.metric("📉 Ausgaben", f"{expenses:.2f} €")
    col4.metric("🧮 Netto", f"{profit - expenses:.2f} €")

    # ===== DIAGRAMME =====
    st.subheader("📊 Analysen")

    if not sales_df.empty:
        fig = px.bar(
            sales_df,
            y=sales_df["quantity"] * sales_df["sell_price"],
            title="Umsatz"
        )
        st.plotly_chart(fig, use_container_width=True)

    # ===== LAGER =====
    st.subheader("📦 Lagerbestand")
    products = pd.read_sql("SELECT * FROM products", conn)
    st.dataframe(products, use_container_width=True)

# ---------------- PRODUCTS ----------------
def products_section():
    st.subheader("🛒 Produkte")

    with st.form("add_product"):
        name = st.text_input("Name")
        buy = st.number_input("Einkaufspreis", 0.0)
        sell = st.number_input("Verkaufspreis", 0.0)
        stock = st.number_input("Lagerbestand", 0)
        if st.form_submit_button("Produkt hinzufügen"):
            c.execute(
                "INSERT INTO products VALUES (NULL,?,?,?,?)",
                (name, buy, sell, stock)
            )
            conn.commit()
            st.rerun()

    products = pd.read_sql("SELECT * FROM products", conn)

    for _, p in products.iterrows():
        col1, col2, col3 = st.columns([4,2,2])
        col1.write(f"**{p['name']}** | Lager: {p['stock']}")
        if col2.button("➕ Lager +1", key=f"inc{p['id']}"):
            c.execute("UPDATE products SET stock=stock+1 WHERE id=?", (p['id'],))
            conn.commit()
            st.rerun()
        if col3.button("🗑️ Löschen", key=f"del{p['id']}"):
            c.execute("DELETE FROM products WHERE id=?", (p['id'],))
            conn.commit()
            st.rerun()

# ---------------- SALES ----------------
def sales_section():
    st.subheader("💸 Verkauf")

    products = pd.read_sql("SELECT * FROM products", conn)

    if products.empty:
        st.info("Keine Produkte")
        return

    product = st.selectbox("Produkt", products["name"])
    qty = st.number_input("Menge", 1)

    if st.button("Verkaufen"):
        pid = products[products["name"] == product]["id"].values[0]
        c.execute(
            "INSERT INTO sales VALUES (NULL,?,?,?)",
            (pid, qty, datetime.now().isoformat())
        )
        c.execute(
            "UPDATE products SET stock=stock-? WHERE id=?",
            (qty, pid)
        )
        conn.commit()
        st.success("Verkauf gespeichert")
        st.rerun()

# ---------------- EXPENSES ----------------
def expenses_section():
    st.subheader("📉 Ausgaben")

    with st.form("expense"):
        name = st.text_input("Bezeichnung")
        amount = st.number_input("Betrag", 0.0)
        if st.form_submit_button("Speichern"):
            c.execute(
                "INSERT INTO expenses VALUES (NULL,?,?,?)",
                (name, amount, datetime.now().date())
            )
            conn.commit()
            st.rerun()

    st.dataframe(pd.read_sql("SELECT * FROM expenses", conn), use_container_width=True)

# ---------------- SHIFTS ----------------
def shifts_section():
    st.subheader("⏱️ Arbeitszeiten / Kasse")

    with st.form("shift"):
        start_cash = st.number_input("Kasse Start", 0.0)
        end_cash = st.number_input("Kasse Ende", 0.0)
        if st.form_submit_button("Schicht speichern"):
            c.execute("""
                INSERT INTO shifts VALUES (NULL,?,?,?,?,?)
            """, (
                st.session_state.user,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                start_cash,
                end_cash
            ))
            conn.commit()
            st.rerun()

    st.dataframe(pd.read_sql("SELECT * FROM shifts", conn), use_container_width=True)

# ---------------- USERS ----------------
def users_section():
    if st.session_state.role != "admin":
        return

    st.subheader("👥 Benutzerverwaltung")

    users = pd.read_sql("SELECT * FROM users", conn)

    for _, u in users.iterrows():
        col1, col2, col3 = st.columns([4,3,2])
        col1.write(u["username"])
        role = col2.selectbox(
            "Rolle",
            ["admin", "staff"],
            index=0 if u["role"] == "admin" else 1,
            key=f"role{u['id']}"
        )
        if role != u["role"]:
            c.execute("UPDATE users SET role=? WHERE id=?", (role, u["id"]))
            conn.commit()
            st.rerun()
        if col3.button("🗑️", key=f"u{u['id']}"):
            c.execute("DELETE FROM users WHERE id=?", (u["id"],))
            conn.commit()
            st.rerun()

# ---------------- MAIN ----------------
if "user" not in st.session_state:
    login()
else:
    st.sidebar.success(f"👤 {st.session_state.user}")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    dashboard()
    sales_section()
    products_section()
    expenses_section()
    shifts_section()
    users_section()
