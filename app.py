import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Salon Dashboard", layout="wide")

DB = "salon.db"

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = get_db()
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
        sale_time TEXT
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

    # Admin default
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users (username,password,role) VALUES (?,?,?)",
            ("admin", hash_pw("admin"), "admin")
        )

    conn.commit()
    conn.close()

# ---------------- HELPERS ----------------
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def card(title, value):
    st.markdown(f"""
    <div style="
        padding:20px;
        border-radius:16px;
        background:#111827;
        color:white;
        text-align:center;
        box-shadow:0 0 15px rgba(0,0,0,0.4)">
        <h4>{title}</h4>
        <h2>{value}</h2>
    </div>
    """, unsafe_allow_html=True)

# ---------------- LOGIN ----------------
def login():
    st.title("🔐 Login")

    user = st.text_input("Benutzername")
    pw = st.text_input("Passwort", type="password")

    if st.button("Login"):
        conn = get_db()
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

# ---------------- DASHBOARD ----------------
def dashboard():
    conn = get_db()

    sales = pd.read_sql("""
        SELECT s.quantity * p.sell_price AS revenue,
               s.quantity * (p.sell_price - p.buy_price) AS profit
        FROM sales s JOIN products p ON s.product_id = p.id
    """, conn)

    expenses = pd.read_sql("SELECT amount FROM expenses", conn)
    products = pd.read_sql("SELECT * FROM products", conn)

    revenue = sales["revenue"].sum() if not sales.empty else 0
    profit = sales["profit"].sum() if not sales.empty else 0
    cost = expenses["amount"].sum() if not expenses.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1: card("Umsatz", f"{revenue:.2f} €")
    with col2: card("Gewinn", f"{profit - cost:.2f} €")
    with col3: card("Ausgaben", f"{cost:.2f} €")
    with col4: card("Produkte", len(products))

    st.divider()

    colA, colB = st.columns(2)
    with colA:
        st.subheader("📈 Umsatz / Gewinn")
        if not sales.empty:
            st.line_chart(sales[["revenue", "profit"]])

    with colB:
        st.subheader("📦 Lagerbestand")
        if not products.empty:
            st.bar_chart(products.set_index("name")["stock"])

    conn.close()

# ---------------- PRODUCTS ----------------
def products_page():
    conn = get_db()
    st.subheader("📦 Produkte")

    with st.form("add_product"):
        name = st.text_input("Name")
        buy = st.number_input("Einkaufspreis", 0.0)
        sell = st.number_input("Verkaufspreis", 0.0)
        stock = st.number_input("Lagerbestand", 0, step=1)
        if st.form_submit_button("Hinzufügen"):
            conn.execute(
                "INSERT INTO products VALUES (NULL,?,?,?,?)",
                (name, buy, sell, stock)
            )
            conn.commit()
            st.rerun()

    df = pd.read_sql("SELECT * FROM products", conn)
    st.dataframe(df)

    if not df.empty:
        pid = st.selectbox("Produkt löschen", df["id"])
        if st.button("❌ Löschen"):
            conn.execute("DELETE FROM products WHERE id=?", (pid,))
            conn.commit()
            st.rerun()

    conn.close()

# ---------------- SALES ----------------
def sales_page():
    conn = get_db()
    st.subheader("🛒 Verkauf")

    products = pd.read_sql("SELECT * FROM products", conn)
    if products.empty:
        st.info("Keine Produkte")
        return

    product = st.selectbox("Produkt", products["name"])
    qty = st.number_input("Menge", 1, step=1)

    if st.button("Verkaufen"):
        p = products[products["name"] == product].iloc[0]
        if p.stock >= qty:
            conn.execute(
                "INSERT INTO sales VALUES (NULL,?,?,?)",
                (p.id, qty, datetime.now().isoformat())
            )
            conn.execute(
                "UPDATE products SET stock = stock - ? WHERE id=?",
                (qty, p.id)
            )
            conn.commit()
            st.success("Verkauf gespeichert")
            st.rerun()
        else:
            st.error("Nicht genug Lager")

# ---------------- EXPENSES ----------------
def expenses_page():
    conn = get_db()
    st.subheader("💸 Ausgaben")

    with st.form("add_expense"):
        title = st.text_input("Bezeichnung")
        amount = st.number_input("Betrag", 0.0)
        if st.form_submit_button("Speichern"):
            conn.execute(
                "INSERT INTO expenses VALUES (NULL,?,?,?)",
                (title, amount, datetime.now().isoformat())
            )
            conn.commit()
            st.rerun()

    df = pd.read_sql("SELECT * FROM expenses", conn)
    st.dataframe(df)

# ---------------- SHIFTS ----------------
def shifts_page():
    conn = get_db()
    st.subheader("⏱️ Arbeitszeiten")

    with st.form("shift"):
        start = st.time_input("Start")
        end = st.time_input("Ende")
        cash_s = st.number_input("Kasse Start", 0.0)
        cash_e = st.number_input("Kasse Ende", 0.0)
        if st.form_submit_button("Speichern"):
            conn.execute(
                "INSERT INTO shifts VALUES (NULL,?,?,?,?,?)",
                (st.session_state.user, start.isoformat(), end.isoformat(), cash_s, cash_e)
            )
            conn.commit()
            st.rerun()

    df = pd.read_sql("SELECT * FROM shifts", conn)
    st.dataframe(df)

# ---------------- USERS ----------------
def users_page():
    conn = get_db()
    st.subheader("👥 Benutzer (Admin)")

    with st.form("add_user"):
        u = st.text_input("Name")
        p = st.text_input("Passwort")
        r = st.selectbox("Rolle", ["admin", "staff"])
        if st.form_submit_button("Anlegen"):
            conn.execute(
                "INSERT INTO users VALUES (NULL,?,?,?)",
                (u, hash_pw(p), r)
            )
            conn.commit()
            st.rerun()

    df = pd.read_sql("SELECT id, username, role FROM users", conn)
    st.dataframe(df)

    uid = st.selectbox("Benutzer löschen", df["id"])
    if st.button("❌ Löschen"):
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
        st.rerun()

# ---------------- MAIN ----------------
init_db()

if "user" not in st.session_state:
    login()
else:
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Seite", [
        "Dashboard",
        "Verkauf",
        "Produkte",
        "Ausgaben",
        "Arbeitszeiten",
        "Benutzer"
    ])

    st.sidebar.write(f"👤 {st.session_state.user}")

    if page == "Dashboard":
        dashboard()
    elif page == "Verkauf":
        sales_page()
    elif page == "Produkte":
        products_page()
    elif page == "Ausgaben":
        expenses_page()
    elif page == "Arbeitszeiten":
        shifts_page()
    elif page == "Benutzer" and st.session_state.role == "admin":
        users_page()

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
