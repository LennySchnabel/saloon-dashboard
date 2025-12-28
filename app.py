import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Salon Dashboard", layout="wide")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("salon.db", check_same_thread=False)
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
        buy REAL,
        sell REAL,
        stock INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        qty INTEGER,
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
    c.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        start_time TEXT,
        start_cash REAL,
        end_time TEXT,
        end_cash REAL
    )
    """)
    conn.commit()

init_db()

# ---------------- HELPERS ----------------
def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def card(title, value):
    st.markdown(f"""
    <div style="padding:20px;border-radius:15px;background:#111;color:white;text-align:center">
        <h4>{title}</h4>
        <h2>{value}</h2>
    </div>
    """, unsafe_allow_html=True)

# ---------------- LOGIN ----------------
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
            st.error("Falsche Zugangsdaten")

# Create default admin
c.execute("SELECT * FROM users")
if not c.fetchall():
    c.execute("INSERT INTO users VALUES (NULL,?,?,?)", ("admin", hash_pw("admin"), "admin"))
    conn.commit()

# ---------------- MAIN APP ----------------
def app():
    st.sidebar.success(f"Angemeldet als {st.session_state.user}")

    tab = st.sidebar.radio("Navigation", [
        "Dashboard", "Produkte", "Verkauf", "Lager",
        "Ausgaben", "Schichten", "Benutzer"
    ])

    # -------- DASHBOARD --------
    if tab == "Dashboard":
        sales = pd.read_sql("SELECT s.qty, p.sell, p.buy FROM sales s JOIN products p ON s.product_id=p.id", conn)
        expenses = pd.read_sql("SELECT amount FROM expenses", conn)

        revenue = (sales.qty * sales.sell).sum() if not sales.empty else 0
        profit = (sales.qty * (sales.sell - sales.buy)).sum() if not sales.empty else 0
        cost = expenses.amount.sum() if not expenses.empty else 0

        c1, c2, c3 = st.columns(3)
        with c1: card("Umsatz", f"{revenue:.2f} €")
        with c2: card("Gewinn", f"{profit:.2f} €")
        with c3: card("Ausgaben", f"{cost:.2f} €")

    # -------- PRODUKTE --------
    if tab == "Produkte":
        st.subheader("Produkt hinzufügen")
        n = st.text_input("Name")
        b = st.number_input("Einkauf", 0.0)
        s = st.number_input("Verkauf", 0.0)
        stk = st.number_input("Startbestand", 0)

        if st.button("Hinzufügen"):
            c.execute("INSERT INTO products VALUES (NULL,?,?,?,?)", (n,b,s,stk))
            conn.commit()
            st.success("Produkt hinzugefügt")

        st.subheader("Produkte")
        df = pd.read_sql("SELECT * FROM products", conn)
        st.dataframe(df)

        del_id = st.number_input("Produkt-ID löschen", 0)
        if st.button("Löschen"):
            c.execute("DELETE FROM products WHERE id=?", (del_id,))
            conn.commit()
            st.success("Gelöscht")

    # -------- VERKAUF --------
    if tab == "Verkauf":
        df = pd.read_sql("SELECT * FROM products", conn)
        pid = st.selectbox("Produkt", df.id)
        qty = st.number_input("Menge", 1)

        if st.button("Verkaufen"):
            c.execute("INSERT INTO sales VALUES (NULL,?,?,?)", (pid,qty,datetime.now()))
            c.execute("UPDATE products SET stock=stock-? WHERE id=?", (qty,pid))
            conn.commit()
            st.success("Verkauf gespeichert")

    # -------- LAGER --------
    if tab == "Lager":
        df = pd.read_sql("SELECT * FROM products", conn)
        st.dataframe(df)

        pid = st.number_input("Produkt-ID", 0)
        change = st.number_input("Bestand ändern (+/-)", 0)

        if st.button("Anpassen"):
            c.execute("UPDATE products SET stock=stock+? WHERE id=?", (change,pid))
            conn.commit()
            st.success("Bestand aktualisiert")

    # -------- AUSGABEN --------
    if tab == "Ausgaben":
        t = st.text_input("Titel")
        a = st.number_input("Betrag", 0.0)

        if st.button("Speichern"):
            c.execute("INSERT INTO expenses VALUES (NULL,?,?,?)", (t,a,datetime.now()))
            conn.commit()
            st.success("Ausgabe gespeichert")

        st.dataframe(pd.read_sql("SELECT * FROM expenses", conn))

    # -------- SCHICHTEN --------
    if tab == "Schichten":
        st.subheader("Schicht starten")
        sc = st.number_input("Kasse Start", 0.0)
        if st.button("Start"):
            c.execute("INSERT INTO shifts VALUES (NULL,?,?,?,?,?)",
                      (st.session_state.user, datetime.now(), sc, None, None))
            conn.commit()

        st.subheader("Schicht beenden")
        ec = st.number_input("Kasse Ende", 0.0)
        if st.button("Ende"):
            c.execute("""
            UPDATE shifts SET end_time=?, end_cash=?
            WHERE user=? AND end_time IS NULL
            """, (datetime.now(), ec, st.session_state.user))
            conn.commit()

        st.dataframe(pd.read_sql("SELECT * FROM shifts", conn))

    # -------- BENUTZER --------
    if tab == "Benutzer" and st.session_state.role == "admin":
        u = st.text_input("Username")
        p = st.text_input("Passwort")
        r = st.selectbox("Rolle", ["admin","staff"])

        if st.button("Anlegen"):
            c.execute("INSERT INTO users VALUES (NULL,?,?,?)", (u, hash_pw(p), r))
            conn.commit()

        st.dataframe(pd.read_sql("SELECT id, username, role FROM users", conn))

        uid = st.number_input("User-ID löschen", 0)
        if st.button("User löschen"):
            c.execute("DELETE FROM users WHERE id=?", (uid,))
            conn.commit()

# ---------------- RUN ----------------
if "user" not in st.session_state:
    login()
else:
    app()
