import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime
import hashlib

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
        name TEXT,
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
        cash_end REAL,
        difference REAL
    )
    """)

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

# ------------------ AUTH ------------------
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
            st.error("Login fehlgeschlagen")

# ------------------ DASHBOARD ------------------
def dashboard():
    st.markdown("## 📊 Dashboard")

    sales_df = pd.read_sql("SELECT * FROM sales", conn)
    prod_df = pd.read_sql("SELECT * FROM products", conn)
    exp_df = pd.read_sql("SELECT * FROM expenses", conn)

    if not sales_df.empty:
        sales_df["time"] = pd.to_datetime(sales_df["time"])
        merged = sales_df.merge(prod_df, left_on="product_id", right_on="id")
        merged["revenue"] = merged["quantity"] * merged["sell_price"]
        merged["profit"] = merged["quantity"] * (merged["sell_price"] - merged["buy_price"])
    else:
        merged = pd.DataFrame()

    total_rev = merged["revenue"].sum() if not merged.empty else 0
    total_profit = merged["profit"].sum() if not merged.empty else 0
    total_exp = exp_df["amount"].sum() if not exp_df.empty else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Umsatz", f"{total_rev:.2f} €")
    col2.metric("📈 Gewinn", f"{total_profit:.2f} €")
    col3.metric("🧾 Ausgaben", f"{total_exp:.2f} €")

    if not merged.empty:
        merged["week"] = merged["time"].dt.to_period("W").astype(str)
        merged["month"] = merged["time"].dt.to_period("M").astype(str)

        w = merged.groupby("week")[["revenue", "profit"]].sum().reset_index()
        m = merged.groupby("month")[["revenue", "profit"]].sum().reset_index()

        st.plotly_chart(px.line(w, x="week", y=["revenue", "profit"], title="📆 Woche"))
        st.plotly_chart(px.line(m, x="month", y=["revenue", "profit"], title="📅 Monat"))

# ------------------ PRODUCTS ------------------
def products():
    st.markdown("## 📦 Produkte")

    df = pd.read_sql("SELECT * FROM products", conn)
    st.dataframe(df, use_container_width=True)

    with st.expander("➕ Produkt hinzufügen"):
        name = st.text_input("Name")
        buy = st.number_input("Einkaufspreis")
        sell = st.number_input("Verkaufspreis")
        stock = st.number_input("Lager", step=1)

        if st.button("Speichern"):
            c.execute(
                "INSERT INTO products VALUES (NULL,?,?,?,?)",
                (name, buy, sell, stock)
            )
            conn.commit()
            st.rerun()

    with st.expander("✏️ Lagerbestand anpassen"):
        pid = st.selectbox("Produkt", df["id"])
        new_stock = st.number_input("Neuer Bestand", step=1)
        if st.button("Aktualisieren"):
            c.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, pid))
            conn.commit()
            st.rerun()

    if st.session_state.role == "admin":
        with st.expander("🗑️ Produkt löschen"):
            pid = st.selectbox("Produkt löschen", df["id"])
            if st.button("Löschen"):
                c.execute("DELETE FROM products WHERE id=?", (pid,))
                conn.commit()
                st.rerun()

# ------------------ EXPENSES ------------------
def expenses():
    st.markdown("## 🧾 Ausgaben")

    name = st.text_input("Bezeichnung")
    amount = st.number_input("Betrag")

    if st.button("Ausgabe speichern"):
        c.execute(
            "INSERT INTO expenses VALUES (NULL,?,?,?)",
            (name, amount, datetime.now().isoformat())
        )
        conn.commit()
        st.rerun()

    st.dataframe(pd.read_sql("SELECT * FROM expenses", conn))

# ------------------ SHIFTS ------------------
def shifts():
    st.markdown("## ⏱️ Arbeitszeiten")

    cash_start = st.number_input("Kassenstand Start")
    if st.button("Schicht starten"):
        c.execute(
            "INSERT INTO shifts VALUES (NULL,?,?,NULL,?,NULL,NULL)",
            (st.session_state.user, datetime.now().isoformat(), cash_start)
        )
        conn.commit()

    cash_end = st.number_input("Kassenstand Ende")
    if st.button("Schicht beenden"):
        c.execute("""
        UPDATE shifts
        SET end_time=?, cash_end=?, difference=(cash_end - cash_start)
        WHERE user=? AND end_time IS NULL
        """, (datetime.now().isoformat(), cash_end, st.session_state.user))
        conn.commit()
        st.rerun()

    st.dataframe(pd.read_sql("SELECT * FROM shifts", conn))

# ------------------ USERS ------------------
def users():
    st.markdown("## 👤 Benutzer")

    if st.session_state.role != "admin":
        st.info("Nur Admin")
        return

    df = pd.read_sql("SELECT id, username, role FROM users", conn)
    st.dataframe(df)

    u = st.text_input("Username")
    p = st.text_input("Passwort")
    r = st.selectbox("Rolle", ["admin", "mitarbeiter"])

    if st.button("Benutzer hinzufügen"):
        c.execute(
            "INSERT INTO users VALUES (NULL,?,?,?)",
            (u, hash_pw(p), r)
        )
        conn.commit()
        st.rerun()

    uid = st.selectbox("Benutzer löschen", df["id"])
    if st.button("Löschen"):
        c.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
        st.rerun()

# ------------------ MAIN ------------------
if "user" not in st.session_state:
    login()
else:
    st.sidebar.success(f"👤 {st.session_state.user} ({st.session_state.role})")
    tab = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Produkte", "Ausgaben", "Arbeitszeiten", "Benutzer"]
    )

    if tab == "Dashboard":
        dashboard()
    elif tab == "Produkte":
        products()
    elif tab == "Ausgaben":
        expenses()
    elif tab == "Arbeitszeiten":
        shifts()
    elif tab == "Benutzer":
        users()
