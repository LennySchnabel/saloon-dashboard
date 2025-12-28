import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import hashlib
from datetime import datetime

# ------------------ CONFIG ------------------
st.set_page_config(page_title="Saloon Dashboard", layout="wide")

DB = "saloon.db"

# ------------------ DATABASE ------------------
def get_db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    con = get_db()
    c = con.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY,
        name TEXT,
        buy REAL,
        sell REAL,
        stock INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales(
        id INTEGER PRIMARY KEY,
        product_id INTEGER,
        qty INTEGER,
        time TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY,
        title TEXT,
        amount REAL,
        time TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS shifts(
        id INTEGER PRIMARY KEY,
        user TEXT,
        start_cash REAL,
        end_cash REAL,
        start_time TEXT,
        end_time TEXT
    )
    """)

    # Admin anlegen falls nicht vorhanden
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO users VALUES (NULL,?,?,?)",
            ("admin", hash_pw("admin"), "admin")
        )

    con.commit()

# ------------------ AUTH ------------------
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def login():
    st.title("🔐 Login")

    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):
        con = get_db()
        c = con.cursor()
        c.execute(
            "SELECT username, role FROM users WHERE username=? AND password=?",
            (user, hash_pw(pw))
        )
        res = c.fetchone()
        if res:
            st.session_state.user = res[0]
            st.session_state.role = res[1]
            st.experimental_rerun()
        else:
            st.error("Falsche Login-Daten")

# ------------------ UI HELPERS ------------------
def card(title, value):
    st.markdown(f"""
    <div style="
        padding:20px;
        border-radius:15px;
        background:#111;
        color:white;
        text-align:center;
        box-shadow:0 0 15px rgba(0,0,0,0.4)">
        <h4>{title}</h4>
        <h2>{value}</h2>
    </div>
    """, unsafe_allow_html=True)

# ------------------ DASHBOARD ------------------
def dashboard():
    st.title("📊 Dashboard")

    con = get_db()

    sales = pd.read_sql("SELECT * FROM sales", con)
    products = pd.read_sql("SELECT * FROM products", con)
    expenses = pd.read_sql("SELECT * FROM expenses", con)

    revenue = 0
    profit = 0

    for _, s in sales.iterrows():
        p = products[products.id == s.product_id]
        if not p.empty:
            revenue += s.qty * p.sell.values[0]
            profit += s.qty * (p.sell.values[0] - p.buy.values[0])

    total_expenses = expenses.amount.sum() if not expenses.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1: card("Umsatz", f"{revenue:.2f} €")
    with c2: card("Gewinn", f"{profit:.2f} €")
    with c3: card("Ausgaben", f"{total_expenses:.2f} €")
    with c4: card("Netto", f"{profit - total_expenses:.2f} €")

    if not sales.empty:
        sales["time"] = pd.to_datetime(sales["time"])
        fig = px.line(sales, x="time", y="qty", title="Verkäufe über Zeit")
        st.plotly_chart(fig, use_container_width=True)

# ------------------ PRODUCTS ------------------
def products_view():
    st.header("📦 Produkte & Lager")

    con = get_db()
    c = con.cursor()

    with st.form("add_product"):
        name = st.text_input("Name")
        buy = st.number_input("Einkaufspreis", 0.0)
        sell = st.number_input("Verkaufspreis", 0.0)
        stock = st.number_input("Lagerbestand", 0)
        if st.form_submit_button("Hinzufügen"):
            c.execute("INSERT INTO products VALUES (NULL,?,?,?,?)",
                      (name, buy, sell, stock))
            con.commit()
            st.experimental_rerun()

    df = pd.read_sql("SELECT * FROM products", con)
    st.dataframe(df, use_container_width=True)

    for _, p in df.iterrows():
        col1, col2, col3 = st.columns([3,2,2])
        with col1:
            st.write(p.name)
        with col2:
            new_stock = st.number_input(
                "Bestand",
                value=int(p.stock),
                key=f"s{p.id}"
            )
            if new_stock != p.stock:
                c.execute("UPDATE products SET stock=? WHERE id=?",
                          (new_stock, p.id))
                con.commit()
        with col3:
            if st.button("❌ Löschen", key=f"d{p.id}"):
                c.execute("DELETE FROM products WHERE id=?", (p.id,))
                con.commit()
                st.experimental_rerun()

# ------------------ SALES ------------------
def sales_view():
    st.header("🛒 Verkauf")

    con = get_db()
    c = con.cursor()
    products = pd.read_sql("SELECT * FROM products", con)

    if products.empty:
        st.info("Keine Produkte")
        return

    prod = st.selectbox("Produkt", products.name)
    qty = st.number_input("Menge", 1)

    if st.button("Verkaufen"):
        p = products[products.name == prod].iloc[0]
        if p.stock >= qty:
            c.execute("INSERT INTO sales VALUES (NULL,?,?,?)",
                      (p.id, qty, datetime.now().isoformat()))
            c.execute("UPDATE products SET stock=stock-? WHERE id=?",
                      (qty, p.id))
            con.commit()
            st.success("Verkauf gespeichert")
            st.experimental_rerun()
        else:
            st.error("Nicht genug Lager")

# ------------------ EXPENSES ------------------
def expenses_view():
    st.header("💸 Ausgaben")

    con = get_db()
    c = con.cursor()

    with st.form("add_exp"):
        title = st.text_input("Titel")
        amount = st.number_input("Betrag", 0.0)
        if st.form_submit_button("Speichern"):
            c.execute("INSERT INTO expenses VALUES (NULL,?,?,?)",
                      (title, amount, datetime.now().isoformat()))
            con.commit()
            st.experimental_rerun()

    st.dataframe(pd.read_sql("SELECT * FROM expenses", con),
                 use_container_width=True)

# ------------------ SHIFTS ------------------
def shifts_view():
    st.header("🕒 Schichten & Kasse")

    con = get_db()
    c = con.cursor()

    with st.form("shift"):
        start_cash = st.number_input("Kassenstand Start", 0.0)
        end_cash = st.number_input("Kassenstand Ende", 0.0)
        if st.form_submit_button("Speichern"):
            c.execute("""
            INSERT INTO shifts VALUES (NULL,?,?,?,?,?)
            """, (st.session_state.user,
                  start_cash,
                  end_cash,
                  datetime.now().isoformat(),
                  datetime.now().isoformat()))
            con.commit()
            st.experimental_rerun()

    st.dataframe(pd.read_sql("SELECT * FROM shifts", con),
                 use_container_width=True)

# ------------------ USERS ------------------
def users_view():
    if st.session_state.role != "admin":
        return

    st.header("👤 Benutzerverwaltung")

    con = get_db()
    c = con.cursor()

    with st.form("add_user"):
        u = st.text_input("Username")
        p = st.text_input("Passwort")
        r = st.selectbox("Rolle", ["admin", "staff"])
        if st.form_submit_button("Erstellen"):
            c.execute("INSERT INTO users VALUES (NULL,?,?,?)",
                      (u, hash_pw(p), r))
            con.commit()
            st.experimental_rerun()

    users = pd.read_sql("SELECT id,username,role FROM users", con)
    for _, u in users.iterrows():
        if u.username != "admin":
            if st.button(f"❌ {u.username} löschen"):
                c.execute("DELETE FROM users WHERE id=?", (u.id,))
                con.commit()
                st.experimental_rerun()

# ------------------ MAIN ------------------
init_db()

if "user" not in st.session_state:
    login()
else:
    menu = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Verkauf", "Produkte", "Ausgaben", "Schichten", "Benutzer"]
    )

    if menu == "Dashboard": dashboard()
    if menu == "Verkauf": sales_view()
    if menu == "Produkte": products_view()
    if menu == "Ausgaben": expenses_view()
    if menu == "Schichten": shifts_view()
    if menu == "Benutzer": users_view()

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.experimental_rerun()
