import streamlit as st
import sqlite3
import json
from datetime import datetime
import os
import pandas as pd
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
    conn.close()

def init_expense_tracker_db():
    """Initializes the expense tracker database and creates tables."""
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
    conn.close()

# Initialize both databases when the script starts
init_users_db()
init_expense_tracker_db()


# --- User Authentication Functions ---
def register_user(username, password):
    """Hashes password and registers a new user."""
    conn = sqlite3.connect(USERS_DB_FILE)
    cursor = conn.cursor()
    hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')
    try:
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError: # Username already exists
        conn.close()
        return False
    except Exception as e:
        st.error(f"Error registering user: {e}")
        conn.close()
        return False

def verify_user(username, password):
    """Verifies user credentials."""
    conn = sqlite3.connect(USERS_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT password FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    if result:
        hashed_password = result[0].encode('utf-8')
        return checkpw(password.encode('utf-8'), hashed_password)
    return False

# --- User ID Management (Now based on authenticated user) ---
def get_current_user_id():
    # If authenticated, use the username as user_id. Otherwise, it's None.
    return st.session_state.get('user_id', None)

# --- SQLite Data Functions (Modified to use authenticated user_id) ---

@st.cache_data(ttl=30)
def get_expenses(current_user_id, month=None, year=None):
    if not current_user_id: return [] # Return empty if no user logged in
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
    conn.close()

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

def add_expense(expense_data, current_user_id):
    if not current_user_id: st.error("No user logged in."); return
    conn = sqlite3.connect(EXPENSE_TRACKER_DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO expenses (user_id, amount, description, category, date, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
            (
                current_user_id,
                float(expense_data['amount']),
                expense_data['description'],
                expense_data['category'],
                expense_data['date'],
                datetime.now().isoformat()
            )
        )
        conn.commit()
        st.success("Expense added successfully!")
        st.session_state.expense_added = True
    except Exception as e:
        st.error(f"Error adding expense: {e}")
    finally:
        conn.close()

def update_expense(expense_id, expense_data, current_user_id):
    if not current_user_id: st.error("No user logged in."); return
    conn = sqlite3.connect(EXPENSE_TRACKER_DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE expenses SET amount = ?, description = ?, category = ?, date = ? WHERE id = ? AND user_id = ?',
            (
                float(expense_data['amount']),
                expense_data['description'],
                expense_data['category'],
                expense_data['date'],
                expense_id,
                current_user_id
            )
        )
        conn.commit()
        if cursor.rowcount > 0:
            st.success("Expense updated successfully!")
            st.session_state.expense_updated = True
        else:
            st.warning("Expense not found or you don't have permission to edit it.")
    except Exception as e:
        st.error(f"Error updating expense: {e}")
    finally:
        conn.close()


def delete_expense(expense_id, current_user_id):
    if not current_user_id: st.error("No user logged in."); return
    conn = sqlite3.connect(EXPENSE_TRACKER_DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (expense_id, current_user_id))
        conn.commit()
        if cursor.rowcount > 0:
            st.success("Expense deleted successfully!")
            st.session_state.expense_deleted = True
        else:
            st.warning("Expense not found or you don't have permission to delete it.")
    except Exception as e:
        st.error(f"Error deleting expense: {e}")
    finally:
        conn.close()


@st.cache_data(ttl=30)
def get_budget(current_user_id):
    if not current_user_id: return {}
    conn = sqlite3.connect(EXPENSE_TRACKER_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT amount, last_updated FROM budget WHERE user_id = ?', (current_user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"amount": row[0], "lastUpdated": row[1]}
    return {}

def set_budget(amount, current_user_id):
    if not current_user_id: st.error("No user logged in."); return
    conn = sqlite3.connect(EXPENSE_TRACKER_DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT OR REPLACE INTO budget (user_id, amount, last_updated) VALUES (?, ?, ?)',
            (current_user_id, float(amount), datetime.now().isoformat())
        )
        conn.commit()
        st.success("Budget set successfully!")
        st.session_state.budget_set = True
    except Exception as e:
        st.error(f"Error setting budget: {e}")
    finally:
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
        .delete-button-x button {{
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0.25rem;
            min-height: auto;
            color: {COLOR_ERROR}; /* Red for delete */
            font-size: 1.25rem; /* text-xl */
        }}
        .delete-button-x button:hover {{
            color: {COLOR_ERROR};
            transform: scale(1.2);
            opacity: 0.8;
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
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-bg"><h1>Personal Expense Tracker</h1></div>', unsafe_allow_html=True)

# --- Session State Initialization ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'page' not in st.session_state:
    st.session_state.page = 'login' # default page is login/signup

# State management for app features
if 'expense_added' not in st.session_state: st.session_state.expense_added = False
if 'budget_set' not in st.session_state: st.session_state.budget_set = False
if 'expense_deleted' not in st.session_state: st.session_state.expense_deleted = False
if 'expense_updated' not in st.session_state: st.session_state.expense_updated = False
if 'show_add_expense_form' not in st.session_state: st.session_state.show_add_expense_form = False
if 'show_edit_expense_form' not in st.session_state: st.session_state.show_edit_expense_form = False
if 'edit_expense_id' not in st.session_state: st.session_state.edit_expense_id = None
if 'show_set_budget_form' not in st.session_state: st.session_state.show_set_budget_form = False
if 'show_summary' not in st.session_state: st.session_state.show_summary = False
if 'prefill_expense_data' not in st.session_state: st.session_state.prefill_expense_data = None
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
                if signup_password != signup_password_confirm:
                    st.error("Passwords do not match.")
                elif len(signup_username) < 3:
                    st.error("Username must be at least 3 characters long.")
                elif len(signup_password) < 6:
                    st.error("Password must be at least 6 characters long.")
                else:
                    if register_user(signup_username, signup_password):
                        st.success("Account created successfully! Please login.")
                    else:
                        st.error("Username already exists. Please choose a different one.")


# --- Main Application Page ---
def show_main_app():
    user_id = get_current_user_id() # Get the currently logged-in user's ID

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

    # Recalculate if operations triggered a state change
    if st.session_state.expense_added or st.session_state.budget_set or \
       st.session_state.expense_deleted or st.session_state.expense_updated:
        get_expenses.clear()
        get_budget.clear() # Clear cache
        expenses = get_expenses(user_id, st.session_state.selected_month, st.session_state.selected_year)
        budget_data = get_budget(user_id)
        st.session_state.expense_added = False
        st.session_state.budget_set = False
        st.session_state.expense_deleted = False
        st.session_state.expense_updated = False


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
    st.subheader("Actions")
    col1, col2, col3 = st.columns(3) 

    with col1:
        if st.button("➕ Add Expense", key="add_expense_btn"):
            st.session_state.show_add_expense_form = True
            st.session_state.show_edit_expense_form = False
            st.session_state.edit_expense_id = None
            st.session_state.prefill_expense_data = None

    with col2:
        if st.button("💰 Set Budget", key="set_budget_btn"):
            st.session_state.show_set_budget_form = True

    with col3:
        if st.button("📊 View Summary", key="view_summary_btn"):
            st.session_state.show_summary = True

    st.markdown("---")
    st.subheader("Quick Add Common Expenses")
    quick_add_col1, quick_add_col2, quick_add_col3 = st.columns(3)

    common_expenses = [
        {"label": "Coffee", "description": "Coffee", "category": "Food"}, 
        {"label": "Lunch", "description": "Lunch", "category": "Food"},   
        {"label": "Transport", "description": "Transport", "category": "Transport"}, 
    ]

    for i, exp in enumerate(common_expenses):
        with [quick_add_col1, quick_add_col2, quick_add_col3][i]:
            if st.button(exp["label"], key=f"quick_add_{i}_btn"):
                st.session_state.prefill_expense_data = {
                    'amount': 0.01,
                    'description': exp["description"],
                    'category': exp["category"],
                    'date': datetime.now().strftime('%Y-%m-%d')
                }
                st.session_state.show_add_expense_form = True
                st.session_state.show_edit_expense_form = False
                st.rerun()


    if st.session_state.get('show_add_expense_form'):
        st.markdown("---")
        st.subheader("Add New Expense/Income")
        with st.form("add_expense_form", clear_on_submit=True):
            prefill_data = st.session_state.get('prefill_expense_data')
            
            default_amount = float(prefill_data.get('amount', 0.01)) if prefill_data and prefill_data.get('amount') is not None else 0.01
            default_description = prefill_data.get('description', '') if prefill_data else ''
            default_category = prefill_data.get('category', 'Food') if prefill_data else 'Food'
            default_date = datetime.strptime(prefill_data['date'], '%Y-%m-%d').date() if prefill_data and prefill_data.get('date') else datetime.now().date()

            amount = st.number_input("Amount (₹)", min_value=0.01, value=default_amount, format="%.2f")
            description = st.text_input("Description", value=default_description)

            categories = [
                'Food', 'Transport', 'Utilities', 'Rent', 'Entertainment', 'Shopping',
                'Health', 'Education', 'Salary', 'Investment', 'Other Income', 'Savings', 'Misc'
            ]
            category = st.selectbox("Category", categories, index=categories.index(default_category) if default_category in categories else 0)

            date = st.date_input("Date", value=default_date)

            submitted = st.form_submit_button("Add Transaction")
            if submitted:
                if amount and description:
                    add_expense({
                        'amount': amount,
                        'description': description,
                        'category': category,
                        'date': date.strftime('%Y-%m-%d')
                    }, user_id)
                    st.session_state.prefill_expense_data = None
                    st.session_state.show_add_expense_form = False
                    st.rerun()
                else:
                    st.error("Please fill in all fields.")
        if st.button("Close Add Expense Form", key="close_add_expense"):
            st.session_state.show_add_expense_form = False
            st.session_state.prefill_expense_data = None


    if st.session_state.get('show_set_budget_form'):
        st.markdown("---")
        st.subheader("Set Monthly Budget")
        with st.form("set_budget_form", clear_on_submit=True):
            new_budget_amount = st.number_input("Budget Amount (₹)", min_value=0.01,
                                                value=current_budget_amount if current_budget_amount is not None and current_budget_amount > 0 else 0.01,
                                                format="%.2f")
            submitted_budget = st.form_submit_button("Save Budget")
            if submitted_budget:
                if new_budget_amount:
                    set_budget(new_budget_amount, user_id)
                    st.session_state.show_set_budget_form = False
                    st.rerun()
                else:
                    st.error("Please enter a valid budget amount.")
        if st.button("Close Set Budget Form", key="close_set_budget"):
            st.session_state.show_set_budget_form = False


    if st.session_state.get('show_edit_expense_form') and st.session_state.get('edit_expense_id'):
        st.markdown("---")
        st.subheader("Edit Expense")
        
        expense_to_edit = next((exp for exp in expenses if exp['id'] == st.session_state.edit_expense_id), None)

        if expense_to_edit:
            with st.form(f"edit_expense_form_{expense_to_edit['id']}"):
                edit_amount = st.number_input("Amount (₹)", min_value=0.01, value=float(expense_to_edit['amount']), format="%.2f", key=f"edit_amount_{expense_to_edit['id']}")
                edit_description = st.text_input("Description", value=expense_to_edit['description'], key=f"edit_description_{expense_to_edit['id']}")
                
                categories = [
                    'Food', 'Transport', 'Utilities', 'Rent', 'Entertainment', 'Shopping',
                    'Health', 'Education', 'Salary', 'Investment', 'Other Income', 'Savings', 'Misc'
                ]
                current_category_index = categories.index(expense_to_edit['category']) if expense_to_edit['category'] in categories else 0
                edit_category = st.selectbox("Category", categories, index=current_category_index, key=f"edit_category_{expense_to_edit['id']}")
                
                edit_date = datetime.strptime(expense_to_edit['date'], '%Y-%m-%d').date() if expense_to_edit.get('date') else datetime.now().date()
                edit_date_input = st.date_input("Date", value=edit_date, key=f"edit_date_{expense_to_edit['id']}")

                submitted_edit = st.form_submit_button("Update Transaction")
                if submitted_edit:
                    if edit_amount and edit_description:
                        update_expense(st.session_state.edit_expense_id, {
                            'amount': edit_amount,
                            'description': edit_description,
                            'category': edit_category,
                            'date': edit_date_input.strftime('%Y-%m-%d')
                        }, user_id)
                        st.session_state.show_edit_expense_form = False
                        st.session_state.edit_expense_id = None
                        st.rerun()
                    else:
                        st.error("Please fill in all fields for the update.")
            
            if st.button("Close Edit Form", key="close_edit_expense"):
                st.session_state.show_edit_expense_form = False
                st.session_state.edit_expense_id = None

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
        st.info(f"No spending data for {selected_month_name} {selected_year} to display charts yet. Add some expenses!")
    else:
        df_category_spending = pd.DataFrame(sorted_category_spending_filtered, columns=['Category', 'Amount Spent'])
        st.bar_chart(df_category_spending.set_index('Category'))

    if st.session_state.get('show_summary'):
        st.markdown("---")
        st.subheader("Detailed Spending Summary by Category")
        if not sorted_category_spending_filtered:
            st.info("No spending data to display yet.")
        else:
            for category, amount in sorted_category_spending_filtered:
                st.markdown(f"**{category}:** ₹{amount:,.2f}")
            st.markdown(f"---")
            total_spending_filtered = sum(exp.get('amount', 0) for exp in expenses_filtered)
            st.markdown(f"**Total Spent:** ₹{total_spending_filtered:,.2f}") 

        if st.button("Close Detailed Summary", key="close_detailed_summary"):
            st.session_state.show_summary = False


    st.markdown("---")
    st.subheader(f"Transactions for {selected_month_name} {selected_year}")
    if not expenses_filtered:
        st.info(f"No expenses recorded for {selected_month_name} {selected_year} yet. Add your first transaction!")
    else:
        cols_header = st.columns([0.15, 0.15, 0.3, 0.2, 0.1, 0.1]) 
        with cols_header[0]: st.markdown("**Date**")
        with cols_header[1]: st.markdown("**Category**")
        with cols_header[2]: st.markdown("**Description**")
        with cols_header[3]: st.markdown("**Amount**")
        with cols_header[4]: st.markdown("**Edit**")
        with cols_header[5]: st.markdown("**Del**")

        st.markdown("---")

        for exp in expenses_filtered:
            col_date, col_category, col_description, col_amount, col_edit, col_action = st.columns([0.15, 0.15, 0.3, 0.2, 0.1, 0.1])
            
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
            
            with col_edit:
                if st.button("✏️", key=f"edit_{exp['id']}_btn", help="Edit this expense"):
                    st.session_state.show_edit_expense_form = True
                    st.session_state.edit_expense_id = exp['id']
                    st.session_state.show_add_expense_form = False
                    st.rerun()

            with col_action:
                if st.button("❌", key=f"delete_{exp['id']}_btn", help="Delete this expense"):
                    delete_expense(exp['id'], user_id)
            st.markdown("---")


# --- Main Application Logic Flow ---
if st.session_state.authenticated:
    show_main_app()
else:
    show_login_signup()
