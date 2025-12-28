import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Saloon Dashboard", layout="wide")

# ---------------- DATABASE ----------------
conn = sqlite3.connect("saloon.db", check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        buy_price REAL,
        sell_price REAL,
        stock INTEGER
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        quantity INTEGER,
        revenue REAL,
        profit REAL,
        sale_time TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        amount REAL,
        date TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        role TEXT
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        start_time TEXT,
        end_time TEXT,
        cash_start REAL,
        cash_end REAL,
        cash_diff REAL
    )""")

    conn.commit()

init_db()

# ---------------- HELPERS ----------------
def get_df(query):
    return pd.read_sql(query, conn)

def card(title, value):
    st.markdown(
        f"""
        <div style="padding:20px;border-radius:15px;background:#111;color:white">
        <h4>{title}</h4>
        <h2>{value}</h2>
        </div>
        """, unsafe_allow_html=True
    )

# ---------------- MENU ----------------
menu = st.sidebar.radio("Menü", [
    "Dashboard",
    "Verkäufe",
    "Produkte & Lager",
    "Analysen",
    "Ausgaben",
    "Arbeitszeiten & Kasse",
    "Benutzerverwaltung"
])

# ---------------- DASHBOARD ----------------
if menu == "Dashboard":
    sales = get_df("SELECT * FROM sales")
    expenses = get_df("SELECT * FROM expenses")

    total_revenue = sales["revenue"].sum() if not sales.empty else 0
    total_profit = sales["profit"].sum() if not sales.empty else 0
    total_expenses = expenses["amount"].sum() if not expenses.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.markdown(card("Umsatz", f"{total_revenue:.2f} €"), unsafe_allow_html=True)
    c2.markdown(card("Gewinn", f"{total_profit:.2f} €"), unsafe_allow_html=True)
    c3.markdown(card("Ausgaben", f"{total_expenses:.2f} €"), unsafe_allow_html=True)

# ---------------- VERKÄUFE ----------------
elif menu == "Verkäufe":
    st.subheader("Verkauf eintragen")

    products = get_df("SELECT * FROM products")
    if products.empty:
        st.warning("Keine Produkte vorhanden")
    else:
        product = st.selectbox("Produkt", products["name"])
        qty = st.number_input("Menge", 1, 100, 1)

        if st.button("Verkaufen"):
            p = products[products["name"] == product].iloc[0]
            if p["stock"] < qty:
                st.error("Nicht genug Lagerbestand")
            else:
                revenue = qty * p["sell_price"]
                profit = qty * (p["sell_price"] - p["buy_price"])

                c.execute("""
                INSERT INTO sales VALUES (NULL,?,?,?,?,?)
                """, (product, qty, revenue, profit, datetime.now().isoformat()))

                c.execute("""
                UPDATE products SET stock = stock - ? WHERE name=?
                """, (qty, product))

                conn.commit()
                st.success("Verkauf gespeichert")

# ---------------- PRODUKTE & LAGER ----------------
elif menu == "Produkte & Lager":
    st.subheader("Produkt hinzufügen")
    name = st.text_input("Name")
    buy = st.number_input("Einkaufspreis", 0.0)
    sell = st.number_input("Verkaufspreis", 0.0)
    stock = st.number_input("Startbestand", 0)

    if st.button("Produkt speichern"):
        try:
            c.execute("INSERT INTO products VALUES (NULL,?,?,?,?)",
                      (name, buy, sell, stock))
            conn.commit()
            st.success("Produkt gespeichert")
        except:
            st.error("Produkt existiert bereits")

    st.subheader("Lagerbestand anpassen")
    products = get_df("SELECT * FROM products")
    if not products.empty:
        p = st.selectbox("Produkt wählen", products["name"])
        change = st.number_input("Änderung (+ Lieferung / - Korrektur)", -1000, 1000, 0)
        if st.button("Bestand ändern"):
            c.execute("UPDATE products SET stock = stock + ? WHERE name=?", (change, p))
            conn.commit()
            st.success("Lagerbestand aktualisiert")

    st.dataframe(products)

# ---------------- ANALYSEN ----------------
elif menu == "Analysen":
    sales = get_df("SELECT * FROM sales")
    expenses = get_df("SELECT * FROM expenses")

    if not sales.empty:
        sales["date"] = pd.to_datetime(sales["sale_time"]).dt.date
        fig = px.line(
            sales.groupby("date").sum().reset_index(),
            x="date",
            y=["revenue", "profit"],
            title="Umsatz & Gewinn"
        )
        st.plotly_chart(fig, use_container_width=True)

    if not expenses.empty:
        expenses["date"] = pd.to_datetime(expenses["date"])
        fig2 = px.line(expenses, x="date", y="amount", title="Ausgaben")
        st.plotly_chart(fig2, use_container_width=True)

# ---------------- AUSGABEN ----------------
elif menu == "Ausgaben":
    name = st.text_input("Ausgabe")
    amount = st.number_input("Betrag", 0.0)
    if st.button("Speichern"):
        c.execute("INSERT INTO expenses VALUES (NULL,?,?,?)",
                  (name, amount, datetime.now().isoformat()))
        conn.commit()
        st.success("Ausgabe gespeichert")

    st.dataframe(get_df("SELECT * FROM expenses"))

# ---------------- ARBEITSZEITEN & KASSE ----------------
elif menu == "Arbeitszeiten & Kasse":
    users = get_df("SELECT * FROM users")
    if users.empty:
        st.warning("Keine Benutzer")
    else:
        user = st.selectbox("Mitarbeiter", users["username"])
        cash_start = st.number_input("Kassenstand Start", 0.0)
        cash_end = st.number_input("Kassenstand Ende", 0.0)

        if st.button("Schicht speichern"):
            diff = cash_end - cash_start
            c.execute("""
            INSERT INTO shifts VALUES (NULL,?,?,?,?,?,?)
            """, (user, datetime.now().isoformat(), datetime.now().isoformat(),
                  cash_start, cash_end, diff))
            conn.commit()
            st.success(f"Kassendifferenz: {diff:.2f} €")

    st.dataframe(get_df("SELECT * FROM shifts"))

# ---------------- BENUTZERVERWALTUNG ----------------
elif menu == "Benutzerverwaltung":
    st.subheader("Benutzer anlegen")
    u = st.text_input("Username")
    role = st.selectbox("Rolle", ["Admin", "Mitarbeiter"])
    if st.button("Erstellen"):
        try:
            c.execute("INSERT INTO users VALUES (NULL,?,?)", (u, role))
            conn.commit()
            st.success("Benutzer erstellt")
        except:
            st.error("Benutzer existiert")

    st.subheader("Benutzer löschen")
    users = get_df("SELECT * FROM users")
    if not users.empty:
        del_user = st.selectbox("Benutzer", users["username"])
        if st.button("Löschen"):
            c.execute("DELETE FROM users WHERE username=?", (del_user,))
            conn.commit()
            st.success("Benutzer gelöscht")

    st.dataframe(users)
