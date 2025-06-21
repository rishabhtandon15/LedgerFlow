import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime
import os
from bcrypt import hashpw, gensalt, checkpw # For secure password hashing

# --- Database Paths ---
USERS_DB_FILE = 'users.db'
EXPENSE_TRACKER_DB_FILE = 'expense_tracker.db'

# --- Define Color Palette ---
COLOR_PRIMARY = "#008080" # A shade of Teal
COLOR_SECONDARY = "#000000" # Black
COLOR_BACKGROUND = "#F5F5DC" # Off-white/Beige (Closest to the provided image's third color)
COLOR_TEXT_DARK = "#333333" # Darker text for readability on light background
COLOR_TEXT_LIGHT = "#FFFFFF" # Light text for readability on dark background
COLOR_SUCCESS = "#228B22" # Forest Green for success messages
COLOR_ERROR = "#B22222" # Firebrick for error messages
COLOR_INFO = "#4682B4" # Steel Blue for info messages
COLOR_WARNING = "#FFD700" # Gold for warning messages

# --- Database Initialization Functions ---
def init_users_db():
    """Initializes the users database and creates the users table."""
    try:
        conn = sqlite3.connect(USERS_DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database Error: Could not initialize users database. {e}")
    finally:
        if conn:
            conn.close()

def init_expense_tracker_db():
    """Initializes the expense tracker database and creates tables."""
    try:
        conn = sqlite3.connect(EXPENSE_TRACKER_DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budget (
                user_id TEXT PRIMARY KEY,
                amount REAL NOT NULL,
                last_updated TEXT NOT NULL
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database Error: Could not initialize expense database. {e}")
    finally:
        if conn:
            conn.close()

# Initialize both databases when the script starts
init_users_db()
init_expense_tracker_db()


# --- User Authentication Functions ---
def register_user(username, password):
    """Hashes password and registers a new user."""
    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(USERS_DB_FILE)
        cursor = conn.cursor()
        hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        conn.commit()
        return True
    except sqlite3.IntegrityError: # Username already exists
        st.error("Username already exists. Please choose a different one.")
        return False
    except sqlite3.Error as e:
        st.error(f"Database Error during registration: {e}")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred during registration: {e}")
        return False
    finally:
        if conn:
            conn.close()

def verify_user(username, password):
    """Verifies user credentials."""
    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(USERS_DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        if result:
            hashed_password = result[0].encode('utf-8')
            return checkpw(password.encode('utf-8'), hashed_password)
        return False # User not found
    except sqlite3.Error as e:
        st.error(f"Database Error during login verification: {e}")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred during login verification: {e}")
        return False
    finally:
        if conn:
            conn.close()

# --- User ID Management (Now based on authenticated user) ---
def get_current_user_id():
    # If authenticated, use the username as user_id. Otherwise, it's None.
    return st.session_state.get('user_id', None)

# --- SQLite Data Functions (Read-only for users) ---

@st.cache_data(ttl=30)
def get_expenses(current_user_id, month=None, year=None):
    if not current_user_id: return [] # Return empty if no user logged in
    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(EXPENSE_TRACKER_DB_FILE)
        cursor = conn.cursor()
        query = 'SELECT id, amount, description, category, date, timestamp FROM expenses WHERE user_id = ?'
        params = [current_user_id]

        if year and month:
            query += ' AND STRFTIME("%Y-%m", date) = ?'
            params.append(f"{year:04d}-{month:02d}")
        elif year:
            query += ' AND STRFTIME("%Y", date) = ?'
            params.append(f"{year:04d}")

        query += ' ORDER BY timestamp DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()

        expenses_list = []
        for row in rows:
            expense_dict = {
                "id": row[0],
                "amount": row[1],
                "description": row[2],
                "category": row[3],
                "date": row[4],
                "timestamp": row[5]
            }
            expenses_list.append(expense_dict)
        return expenses_list
    except sqlite3.Error as e:
        st.error(f"Database Error fetching expenses: {e}")
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred fetching expenses: {e}")
        return []
    finally:
        if conn:
            conn.close()

@st.cache_data(ttl=30)
def get_budget(current_user_id):
    if not current_user_id: return {}
    conn = None # Initialize conn to None
    try:
        conn = sqlite3.connect(EXPENSE_TRACKER_DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT amount, last_updated FROM budget WHERE user_id = ?', (current_user_id,))
        row = cursor.fetchone()
        if row:
            return {"amount": row[0], "lastUpdated": row[1]}
        return {}
    except sqlite3.Error as e:
        st.error(f"Database Error fetching budget: {e}")
        return {}
    except Exception as e:
        st.error(f"An unexpected error occurred fetching budget: {e}")
        return {}
    finally:
        if conn:
            conn.close()

# --- Streamlit UI Components ---
st.set_page_config(layout="centered", page_title="Personal Expense Tracker")

st.markdown(f"""
    <style>
        body {{
            background-color: {COLOR_BACKGROUND}; /* Apply overall background color */
            color: {COLOR_TEXT_DARK}; /* Default text color */
        }}
        .stButton>button {{
            border-radius: 9999px; /* Rounded-full */
            font-weight: bold;
            padding: 0.75rem 1.5rem;
            transition: all 0.3s ease-in-out;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            background-color: {COLOR_PRIMARY}; /* Teal for buttons */
            color: {COLOR_TEXT_LIGHT};
            border: none; /* Remove default button border */
        }}
        .stButton>button:hover {{
            transform: scale(1.05);
            background-color: {COLOR_PRIMARY}; /* Keep primary color on hover */
            opacity: 0.9;
        }}
        .header-bg {{
            background: {COLOR_PRIMARY}; /* Teal for header */
            padding: 1rem;
            border-bottom-left-radius: 0.75rem;
            border-bottom-right-radius: 0.75rem;
            color: {COLOR_TEXT_LIGHT};
            text-align: center;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }}
        .stTextInput>div>div>input, .stSelectbox>div>div>select, .stDateInput>div>div>input {{
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            background-color: {COLOR_BACKGROUND}; /* Off-white for inputs */
            color: {COLOR_TEXT_DARK};
            border: 1px solid {COLOR_PRIMARY}; /* Teal border for inputs */
        }}
        /* Style for selected option in selectbox for better visibility */
        .stSelectbox [data-testid="stSelectbox"] > div > div > div > div:first-child {{
            color: {COLOR_TEXT_DARK}; 
            background-color: {COLOR_BACKGROUND};
        }}
        .stSelectbox [data-testid="stSelectbox"] > div > div > div > div > div {{ /* Dropdown arrow */
             color: {COLOR_PRIMARY};
        }}
        .stSelectbox [data-testid="stSelectbox"] > div > div > div > div:hover {{
            border-color: {COLOR_PRIMARY};
        }}
        .stRadio>label>div>div {{
            border-radius: 9999px;
        }}
        .stMarkdown h1, .stMarkdown h2 {{
            color: {COLOR_SECONDARY}; /* Black for headings */
        }}
        .stAlert {{
            border-radius: 0.5rem;
        }}
        /* Streamlit containers don't have a direct class. Targeting their parent 'div' */
        .stContainer {{
            border-radius: 1rem;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            background-color: {COLOR_BACKGROUND}; /* Off-white for containers */
            border: 1px solid {COLOR_PRIMARY}30; /* Light teal border for containers */
        }}
        /* Styles for the budget progress bar */
        .progress-container {{
            width: 100%;
            background-color: {COLOR_TEXT_DARK}; /* Black for progress background */
            border-radius: 10px;
            overflow: hidden;
            margin-top: 10px;
        }}
        .progress-bar {{
            height: 25px;
            border-radius: 10px;
            text-align: center;
            color: {COLOR_TEXT_LIGHT};
            line-height: 25px;
            font-weight: bold;
            transition: width 0.5s ease-in-out, background-color 0.5s ease-in-out;
        }}
        /* Specific colors for success/error messages */
        .stSuccess {{ background-color: {COLOR_SUCCESS}20; color: {COLOR_SUCCESS}; border: 1px solid {COLOR_SUCCESS}; }}
        .stError {{ background-color: {COLOR_ERROR}20; color: {COLOR_ERROR}; border: 1px solid {COLOR_ERROR}; }}
        .stWarning {{ background-color: {COLOR_WARNING}20; color: {COLOR_WARNING}; border: 1px solid {COLOR_WARNING}; }}
        .stInfo {{ background-color: {COLOR_INFO}20; color: {COLOR_INFO}; border: 1px solid {COLOR_INFO}; }}
        .readonly-notice {{
            background-color: {COLOR_INFO}20;
            color: {COLOR_INFO};
            border: 1px solid {COLOR_INFO};
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            margin-bottom: 1rem;
        }}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-bg"><h1>Personal Expense Tracker - View Only</h1></div>', unsafe_allow_html=True)

# --- Session State Initialization ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'page' not in st.session_state:
    st.session_state.page = 'login' # default page is login/signup

# State management for app features (simplified for read-only)
if 'show_summary' not in st.session_state: st.session_state.show_summary = False
if 'selected_month' not in st.session_state: st.session_state.selected_month = datetime.now().month
if 'selected_year' not in st.session_state: st.session_state.selected_year = datetime.now().year


# --- Login/Signup Page ---
def show_login_signup():
    st.subheader("Login / Sign Up")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            login_username = st.text_input("Username", key="login_user")
            login_password = st.text_input("Password", type="password", key="login_pass")
            login_button = st.form_submit_button("Login")

            if login_button:
                if not login_username.strip() or not login_password.strip():
                    st.error("Please enter both username and password.")
                else:
                    if verify_user(login_username, login_password):
                        st.session_state.authenticated = True
                        st.session_state.user_id = login_username # Use username as user_id
                        st.success(f"Welcome, {login_username}!")
                        st.session_state.page = 'main_app'
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

    with tab2:
        with st.form("signup_form"):
            signup_username = st.text_input("New Username", key="signup_user")
            signup_password = st.text_input("New Password", type="password", key="signup_pass")
            signup_password_confirm = st.text_input("Confirm Password", type="password", key="signup_pass_confirm")
            signup_button = st.form_submit_button("Sign Up")

            if signup_button:
                if not signup_username.strip() or not signup_password.strip() or not signup_password_confirm.strip():
                    st.error("Please fill in all fields.")
                elif signup_password != signup_password_confirm:
                    st.error("Passwords do not match.")
                elif len(signup_username) < 3:
                    st.error("Username must be at least 3 characters long.")
                elif len(signup_password) < 6:
                    st.error("Password must be at least 6 characters long.")
                else:
                    if register_user(signup_username, signup_password):
                        st.success("Account created successfully! Please login.")

# --- Main Application Page (Read-Only) ---
def show_main_app():
    user_id = get_current_user_id() # Get the currently logged-in user's ID

    # Display read-only notice
    st.markdown(f"""
        <div class="readonly-notice">
            <h3>📊 View-Only Mode</h3>
            <p>This is a read-only version of the expense tracker. You can view your data and analytics, but cannot make changes.</p>
        </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown(f"**Logged in as:** {user_id}")
    if st.sidebar.button("Logout", key="logout_btn"):
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.page = 'login'
        st.session_state.clear() # Clear all session state on logout for security
        st.rerun()

    # Fetch data based on selected month/year for the logged-in user
    expenses = get_expenses(user_id, st.session_state.selected_month, st.session_state.selected_year)
    budget_data = get_budget(user_id)

    current_budget_amount = budget_data.get('amount')
    total_spending = sum(exp.get('amount', 0) for exp in expenses)
    remaining_budget = (current_budget_amount - total_spending) if current_budget_amount is not None else None

    budget_display_str = f"₹{current_budget_amount:,.2f}" if current_budget_amount is not None else 'N/A'
    remaining_display_str = f"₹{remaining_budget:,.2f}" if remaining_budget is not None else 'N/A'

    budget_percentage = 0
    if current_budget_amount and current_budget_amount > 0:
        budget_percentage = min(100, (total_spending / current_budget_amount) * 100)

    # Adjust progress bar colors based on palette
    progress_color_bar = COLOR_SUCCESS # Green for on track
    if budget_percentage > 75:
        progress_color_bar = COLOR_WARNING # Yellow for nearing limit
    if budget_percentage > 100:
        progress_color_bar = COLOR_ERROR # Red for over budget

    st.container(border=True).markdown(f"""
        <div style="text-align: center;">
            <h2 style="color: {COLOR_SECONDARY}; margin-bottom: 1rem;">Your Budget Overview</h2>
            <div style="display: flex; flex-wrap: wrap; justify-content: space-around; gap: 1rem;">
                <div>
                    <p style="font-size: 1.125rem; color: {COLOR_TEXT_DARK};">Monthly Budget:</p>
                    <p style="font-size: 1.875rem; font-weight: bold; color: {COLOR_PRIMARY};">{budget_display_str}</p>
                </div>
                <div>
                    <p style="font-size: 1.125rem; color: {COLOR_TEXT_DARK};">Total Spent (Current Period):</p>
                    <p style="font-size: 1.875rem; font-weight: bold; color: {COLOR_ERROR};">₹{total_spending:,.2f}</p>
                </div>
                <div>
                    <p style="font-size: 1.125rem; color: {COLOR_TEXT_DARK};">Remaining:</p>
                    <p style="font-size: 1.875rem; font-weight: bold; color: {
                        COLOR_ERROR if remaining_budget is not None and remaining_budget < 0 else COLOR_SUCCESS
                    };">{remaining_display_str}</p>
                </div>
            </div>
            <div class="progress-container">
                <div class="progress-bar" style="width: {budget_percentage}%; background-color: {progress_color_bar};">
                    {budget_percentage:.0f}%
                </div>
            </div>
            <p style="font-size: 0.875rem; color: {COLOR_TEXT_DARK}; margin-top: 5px;">
                Budget progress for {datetime(st.session_state.selected_year, st.session_state.selected_month, 1).strftime('%B %Y')}
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("View Options")
    col1, col2 = st.columns(2) 

    with col1:
        if st.button("📊 View Summary", key="view_summary_btn"):
            st.session_state.show_summary = True

    with col2:
        if st.button("📈 Analytics Dashboard", key="analytics_btn"):
            st.info("Analytics dashboard - showing current filtered data below")

    if st.session_state.get('show_summary'):
        st.markdown("---")
        st.subheader("Detailed Spending Summary by Category")
        
        category_spending_data = {}
        for expense in expenses:
            category = expense.get('category', 'Uncategorized')
            category_spending_data[category] = category_spending_data.get(category, 0) + expense.get('amount', 0)

        sorted_category_spending = sorted(category_spending_data.items(), key=lambda item: item[1], reverse=True)
        
        if not sorted_category_spending:
            st.info("No spending data to display yet.")
        else:
            for category, amount in sorted_category_spending:
                st.markdown(f"**{category}:** ₹{amount:,.2f}")
            st.markdown(f"---")
            total_spending_filtered = sum(exp.get('amount', 0) for exp in expenses)
            st.markdown(f"**Total Spent:** ₹{total_spending_filtered:,.2f}") 

        if st.button("Close Detailed Summary", key="close_detailed_summary"):
            st.session_state.show_summary = False

    st.markdown("---")
    st.subheader("Spending Analytics")

    current_month = datetime.now().month
    current_year = datetime.now().year

    all_expenses_for_years = get_expenses(user_id) 
    available_years = sorted(list(set(datetime.strptime(exp['date'], '%Y-%m-%d').year for exp in all_expenses_for_years if 'date' in exp)))
    if not available_years:
        available_years = [current_year]

    available_months = ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December']

    col_month_filter, col_year_filter = st.columns(2)
    with col_month_filter:
        selected_month_name = st.selectbox(
            "Select Month",
            options=available_months,
            index=st.session_state.selected_month - 1,
            key="month_filter_select"
        )
        st.session_state.selected_month = available_months.index(selected_month_name) + 1

    with col_year_filter:
        selected_year = st.selectbox(
            "Select Year",
            options=available_years,
            index=available_years.index(st.session_state.selected_year) if st.session_state.selected_year in available_years else (len(available_years) - 1),
            key="year_filter_select"
        )
        st.session_state.selected_year = selected_year

    expenses_filtered = get_expenses(user_id, st.session_state.selected_month, st.session_state.selected_year)

    category_spending_data_filtered = {}
    for expense in expenses_filtered:
        category = expense.get('category', 'Uncategorized')
        category_spending_data_filtered[category] = category_spending_data_filtered.get(category, 0) + expense.get('amount', 0)

    sorted_category_spending_filtered = sorted(category_spending_data_filtered.items(), key=lambda item: item[1], reverse=True)

    if not sorted_category_spending_filtered:
        st.info(f"No spending data for {selected_month_name} {selected_year} to display charts yet.")
    else:
        df_category_spending = pd.DataFrame(sorted_category_spending_filtered, columns=['Category', 'Amount Spent'])
        st.bar_chart(df_category_spending.set_index('Category'))

    st.markdown("---")
    st.subheader(f"Transactions for {selected_month_name} {selected_year}")
    if not expenses_filtered:
        st.info(f"No expenses recorded for {selected_month_name} {selected_year}.")
    else:
        # Display transactions in a clean table format without edit/delete options
        cols_header = st.columns([0.2, 0.2, 0.4, 0.2]) 
        with cols_header[0]: st.markdown("**Date**")
        with cols_header[1]: st.markdown("**Category**")
        with cols_header[2]: st.markdown("**Description**")
        with cols_header[3]: st.markdown("**Amount**")

        st.markdown("---")

        for exp in expenses_filtered:
            col_date, col_category, col_description, col_amount = st.columns([0.2, 0.2, 0.4, 0.2])
            
            display_date = exp.get('date', 'N/A')
            amount_color = 'red' if exp.get('amount', 0) < 0 else 'green'

            with col_date:
                st.markdown(f"<p style='font-size: small;'>{display_date}</p>", unsafe_allow_html=True)
            with col_category:
                st.markdown(f"<p style='font-size: small;'>{exp.get('category', 'Uncategorized')}</p>", unsafe_allow_html=True)
            with col_description:
                st.markdown(f"<p style='font-size: small;'>{exp.get('description', 'N/A')}</p>", unsafe_allow_html=True)
            with col_amount:
                st.markdown(f"<p style='font-weight: bold; color: {amount_color};'>₹{exp.get('amount', 0):,.2f}</p>", unsafe_allow_html=True)
            
            st.markdown("---")

        # Display transaction summary
        st.markdown("### Transaction Summary")
        total_transactions = len(expenses_filtered)
        total_amount = sum(exp.get('amount', 0) for exp in expenses_filtered)
        avg_transaction = total_amount / total_transactions if total_transactions > 0 else 0
        
        summary_cols = st.columns(3)
        with summary_cols[0]:
            st.metric("Total Transactions", total_transactions)
        with summary_cols[1]:
            st.metric("Total Amount", f"₹{total_amount:,.2f}")
        with summary_cols[2]:
            st.metric("Average per Transaction", f"₹{avg_transaction:,.2f}")


# --- Main Application Logic Flow ---
if st.session_state.authenticated:
    show_main_app()
else:
    show_login_signup()