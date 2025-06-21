import streamlit as st
import sqlite3
import json
from datetime import datetime
import os # Import os for environment variable check
import pandas as pd # Import pandas for data manipulation for charts
import qrcode # For generating QR codes
from PIL import Image # For QR code image handling
from io import BytesIO # For handling image bytes
from pyzbar.pyzbar import decode # For decoding QR codes from images

# --- Database Operations (SQLite) ---
DATABASE_FILE = 'expense_tracker.db'

def init_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Create expenses table
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

    # Create budget table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget (
            user_id TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database when the script starts
init_db()

# --- User ID Management (for single-user per deployment) ---
def get_current_user_id():
    # Safely get __app_id from environment variables (provided by Canvas)
    # or use a hardcoded default for local testing.
    app_id = os.environ.get('__app_id', 'local-default-app-id')
    return f"{app_id}_local_user"

user_id = get_current_user_id()

# Determine if the app is running in a local environment
# 'local-default-app-id' is the fallback provided when __app_id is not set by the environment,
# indicating a local run. Adjust this logic if your deployment setup changes.
is_local_environment = os.environ.get('__app_id', 'local-default-app-id') == 'local-default-app-id'


# --- SQLite Data Functions ---

@st.cache_data(ttl=30) # Cache data for 30 seconds
def get_expenses(current_user_id, month=None, year=None):
    """
    Fetches expenses for the current user from SQLite,
    optionally filtered by month and year.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = 'SELECT id, amount, description, category, date, timestamp FROM expenses WHERE user_id = ?'
    params = [current_user_id]

    if year and month:
        # Filter by year and month
        query += ' AND STRFTIME("%Y-%m", date) = ?'
        params.append(f"{year:04d}-{month:02d}")
    elif year: # Only filter by year
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
    """Adds a new expense to SQLite."""
    conn = sqlite3.connect(DATABASE_FILE)
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
                datetime.now().isoformat() # Use ISO format for timestamp
            )
        )
        conn.commit()
        st.success("Expense added successfully!")
        st.session_state.expense_added = True # Trigger a refresh
    except Exception as e:
        st.error(f"Error adding expense: {e}")
    finally:
        conn.close()

def update_expense(expense_id, expense_data, current_user_id):
    """Updates an existing expense in SQLite."""
    conn = sqlite3.connect(DATABASE_FILE)
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
            st.session_state.expense_updated = True # Trigger a refresh
        else:
            st.warning("Expense not found or you don't have permission to edit it.")
    except Exception as e:
        st.error(f"Error updating expense: {e}")
    finally:
        conn.close()


def delete_expense(expense_id, current_user_id):
    """Deletes an expense from SQLite."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # Ensure that only the current user can delete their own expenses
        cursor.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (expense_id, current_user_id))
        conn.commit()
        if cursor.rowcount > 0:
            st.success("Expense deleted successfully!")
            st.session_state.expense_deleted = True # Trigger a refresh
        else:
            st.warning("Expense not found or you don't have permission to delete it.")
    except Exception as e:
        st.error(f"Error deleting expense: {e}")
    finally:
        conn.close()


@st.cache_data(ttl=30)
def get_budget(current_user_id):
    """Fetches the budget for the current user from SQLite."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT amount, last_updated FROM budget WHERE user_id = ?', (current_user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"amount": row[0], "lastUpdated": row[1]}
    return {}

def set_budget(amount, current_user_id):
    """Sets or updates the budget for the current user in SQLite."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT OR REPLACE INTO budget (user_id, amount, last_updated) VALUES (?, ?, ?)',
            (current_user_id, float(amount), datetime.now().isoformat())
        )
        conn.commit()
        st.success("Budget set successfully!")
        st.session_state.budget_set = True # Trigger a refresh
    except Exception as e:
        st.error(f"Error setting budget: {e}")
    finally:
        conn.close()

# --- QR Code Functions (kept for completeness if future use is desired) ---
def generate_expense_qr(expense_data):
    """Generates a QR code image for expense data."""
    # Encode expense data as JSON string
    qr_data = json.dumps({
        "amount": expense_data['amount'],
        "description": expense_data['description'],
        "category": expense_data['category'],
        "date": expense_data['date']
    })
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def decode_qr_code_from_image(image_bytes):
    """Decodes QR code from an image buffer and returns parsed data."""
    try:
        img = Image.open(BytesIO(image_bytes))
        decoded_objects = decode(img)
        if decoded_objects:
            # Assuming the first QR code contains the desired data
            qr_data_str = decoded_objects[0].data.decode('utf-8')
            return json.loads(qr_data_str)
        return None
    except Exception as e:
        st.error(f"Error decoding QR code: {e}")
        return None


# --- Streamlit UI Components ---

st.set_page_config(layout="centered", page_title="Personal Expense Tracker")

st.markdown("""
    <style>
        .stButton>button {
            border-radius: 9999px; /* Rounded-full */
            font-weight: bold;
            padding: 0.75rem 1.5rem;
            transition: all 0.3s ease-in-out;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .stButton>button:hover {
            transform: scale(1.05);
        }
        .header-bg {
            background: linear-gradient(to right, #8B5CF6, #6366F1); /* purple-600 to indigo-600 */
            padding: 1rem;
            border-bottom-left-radius: 0.75rem;
            border-bottom-right-radius: 0.75rem;
            color: white;
            text-align: center;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .stTextInput>div>div>input, .stSelectbox>div>div>select, .stDateInput>div>div>input {
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        }
        .stRadio>label>div>div { /* Style for radio buttons, if used */
            border-radius: 9999px;
        }
        .stMarkdown h1, .stMarkdown h2 {
            color: #4B5563; /* gray-700 */
        }
        .stAlert {
            border-radius: 0.5rem;
        }
        .stContainer {
            border-radius: 1rem;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .delete-button-x button {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0.25rem;
            min-height: auto;
            color: #EF4444; /* red-500 */
            font-size: 1.25rem; /* text-xl */
        }
        .delete-button-x button:hover {
            color: #DC2626; /* red-600 */
            transform: scale(1.2);
        }

        /* Styles for the budget progress bar */
        .progress-container {
            width: 100%;
            background-color: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-bar {
            height: 25px;
            border-radius: 10px;
            text-align: center;
            color: white;
            line-height: 25px;
            font-weight: bold;
            transition: width 0.5s ease-in-out, background-color 0.5s ease-in-out;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-bg"><h1>Personal Expense Tracker</h1><p class="text-sm opacity-80">User ID: ' + user_id + '</p></div>', unsafe_allow_html=True)

# State management for triggering re-runs after successful operations
if 'expense_added' not in st.session_state:
    st.session_state.expense_added = False
if 'budget_set' not in st.session_state:
    st.session_state.budget_set = False
if 'expense_deleted' not in st.session_state:
    st.session_state.expense_deleted = False
if 'expense_updated' not in st.session_state: # New state for expense update
    st.session_state.expense_updated = False
if 'show_add_expense_form' not in st.session_state:
    st.session_state.show_add_expense_form = False
if 'show_edit_expense_form' not in st.session_state: # New state for edit form
    st.session_state.show_edit_expense_form = False
if 'edit_expense_id' not in st.session_state: # To store ID of expense being edited
    st.session_state.edit_expense_id = None
if 'show_set_budget_form' not in st.session_state:
    st.session_state.show_set_budget_form = False
if 'show_summary' not in st.session_state:
    st.session_state.show_summary = False
if 'prefill_expense_data' not in st.session_state:
    st.session_state.prefill_expense_data = None
if 'selected_month' not in st.session_state:
    st.session_state.selected_month = datetime.now().month
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = datetime.now().year


# Fetch data based on selected month/year
expenses = get_expenses(user_id, st.session_state.selected_month, st.session_state.selected_year)
budget_data = get_budget(user_id)

# Recalculate if operations triggered a state change
if st.session_state.expense_added or st.session_state.budget_set or \
   st.session_state.expense_deleted or st.session_state.expense_updated:
    # Clear cache for relevant functions to force a fresh fetch
    get_expenses.clear()
    get_budget.clear()

    expenses = get_expenses(user_id, st.session_state.selected_month, st.session_state.selected_year)
    budget_data = get_budget(user_id)
    st.session_state.expense_added = False
    st.session_state.budget_set = False
    st.session_state.expense_deleted = False # Reset deletion flag
    st.session_state.expense_updated = False


current_budget_amount = budget_data.get('amount')
total_spending = sum(exp.get('amount', 0) for exp in expenses)
remaining_budget = (current_budget_amount - total_spending) if current_budget_amount is not None else None

# Prepare display strings for budget and remaining amount
budget_display_str = f"₹{current_budget_amount:,.2f}" if current_budget_amount is not None else 'N/A'
remaining_display_str = f"₹{remaining_budget:,.2f}" if remaining_budget is not None else 'N/A'

# Calculate budget percentage for the progress bar
budget_percentage = 0
if current_budget_amount and current_budget_amount > 0:
    budget_percentage = min(100, (total_spending / current_budget_amount) * 100)

progress_color = "#22C55E" # Green for on track
if budget_percentage > 75:
    progress_color = "#F59E0B" # Yellow for nearing limit
if budget_percentage > 100:
    progress_color = "#EF4444" # Red for over budget


# Budget Summary Card
st.container(border=True).markdown(f"""
    <div style="text-align: center;">
        <h2 style="color: #4B5563; margin-bottom: 1rem;">Your Budget Overview</h2>
        <div style="display: flex; flex-wrap: wrap; justify-content: space-around; gap: 1rem;">
            <div>
                <p style="font-size: 1.125rem; color: #4B5563;">Monthly Budget:</p>
                <p style="font-size: 1.875rem; font-weight: bold; color: #3B82F6;">{budget_display_str}</p>
            </div>
            <div>
                <p style="font-size: 1.125rem; color: #4B5563;">Total Spent (Current Period):</p>
                <p style="font-size: 1.875rem; font-weight: bold; color: #EF4444;">₹{total_spending:,.2f}</p>
            </div>
            <div>
                <p style="font-size: 1.125rem; color: #4B5563;">Remaining:</p>
                <p style="font-size: 1.875rem; font-weight: bold; color: {
                    '#EF4444' if remaining_budget is not None and remaining_budget < 0 else '#22C55E'
                };">{remaining_display_str}</p>
            </div>
        </div>
        <div class="progress-container">
            <div class="progress-bar" style="width: {budget_percentage}%; background-color: {progress_color};">
                {budget_percentage:.0f}%
            </div>
        </div>
        <p style="font-size: 0.875rem; color: #6B7280; margin-top: 5px;">
            Budget progress for {datetime(st.session_state.selected_year, st.session_state.selected_month, 1).strftime('%B %Y')}
        </p>
    </div>
""", unsafe_allow_html=True)


# --- Action Buttons ---
st.markdown("---")
st.subheader("Actions")
col1, col2, col3 = st.columns(3) 

# Conditional rendering for editing options
if is_local_environment:
    with col1:
        if st.button("➕ Add Expense", key="add_expense_btn"):
            st.session_state.show_add_expense_form = True
            st.session_state.show_edit_expense_form = False # Hide edit form
            st.session_state.edit_expense_id = None # Clear edit ID
            st.session_state.prefill_expense_data = None # Clear any prefilled data

    with col2:
        if st.button("💰 Set Budget", key="set_budget_btn"):
            st.session_state.show_set_budget_form = True

    with col3:
        if st.button("📊 View Summary", key="view_summary_btn"):
            st.session_state.show_summary = True

    # --- Quick Add Buttons ---
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
                # When quick add button is clicked, set prefill data and show add form
                st.session_state.prefill_expense_data = {
                    'amount': 0.01, # Default to min_value, user will change
                    'description': exp["description"],
                    'category': exp["category"],
                    'date': datetime.now().strftime('%Y-%m-%d')
                }
                st.session_state.show_add_expense_form = True
                st.session_state.show_edit_expense_form = False # Hide other forms
                st.rerun()


    # --- Add New Expense Form ---
    if st.session_state.get('show_add_expense_form'):
        st.markdown("---")
        st.subheader("Add New Expense/Income")
        with st.form("add_expense_form", clear_on_submit=True):
            # Prefill if data is available from Quick Add or QR scan
            prefill_data = st.session_state.get('prefill_expense_data')
            
            # Ensure default value is not less than min_value, allowing user to change
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
                    st.session_state.prefill_expense_data = None # Clear after submission
                    st.session_state.show_add_expense_form = False # Hide the form
                    st.rerun()
                else:
                    st.error("Please fill in all fields.")
        if st.button("Close Add Expense Form", key="close_add_expense"):
            st.session_state.show_add_expense_form = False
            st.session_state.prefill_expense_data = None


    # --- Set Monthly Budget Form ---
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
                    st.session_state.show_set_budget_form = False # Hide the form
                    st.rerun()
                else:
                    st.error("Please enter a valid budget amount.")
        if st.button("Close Set Budget Form", key="close_set_budget"):
            st.session_state.show_set_budget_form = False


    # --- Edit Expense Form ---
    if st.session_state.get('show_edit_expense_form') and st.session_state.get('edit_expense_id'):
        st.markdown("---")
        st.subheader("Edit Expense")
        
        # Find the expense being edited
        expense_to_edit = next((exp for exp in expenses if exp['id'] == st.session_state.edit_expense_id), None)

        if expense_to_edit:
            with st.form(f"edit_expense_form_{expense_to_edit['id']}"):
                # Prefill form fields with existing expense data
                edit_amount = st.number_input("Amount (₹)", min_value=0.01, value=float(expense_to_edit['amount']), format="%.2f", key=f"edit_amount_{expense_to_edit['id']}")
                edit_description = st.text_input("Description", value=expense_to_edit['description'], key=f"edit_description_{expense_to_edit['id']}")
                
                categories = [
                    'Food', 'Transport', 'Utilities', 'Rent', 'Entertainment', 'Shopping',
                    'Health', 'Education', 'Salary', 'Investment', 'Other Income', 'Savings', 'Misc'
                ]
                current_category_index = categories.index(expense_to_edit['category']) if expense_to_edit['category'] in categories else 0
                edit_category = st.selectbox("Category", categories, index=current_category_index, key=f"edit_category_{expense_to_edit['id']}")
                
                # Convert date string to datetime.date object for st.date_input
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
                        st.session_state.show_edit_expense_form = False # Hide the form
                        st.session_state.edit_expense_id = None # Clear edit ID
                        st.rerun()
                    else:
                        st.error("Please fill in all fields for the update.")
            
            if st.button("Close Edit Form", key="close_edit_expense"):
                st.session_state.show_edit_expense_form = False
                st.session_state.edit_expense_id = None # Clear edit ID

# --- Spending Summary & Visualization ---
st.markdown("---")
st.subheader("Spending Analytics")

# Month and Year filter for analytics and transactions
current_month = datetime.now().month
current_year = datetime.now().year

# Generate a list of available months/years from expenses, or a default range
# Fetch all expenses (without month/year filter) to get all available years
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
        index=st.session_state.selected_month - 1, # Adjust for 0-based index
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

# Re-fetch expenses based on selected filters (already done at the top, but this ensures re-run on filter change)
expenses_filtered = get_expenses(user_id, st.session_state.selected_month, st.session_state.selected_year)


category_spending_data_filtered = {}
for expense in expenses_filtered:
    category = expense.get('category', 'Uncategorized')
    category_spending_data_filtered[category] = category_spending_data_filtered.get(category, 0) + expense.get('amount', 0)

# Sort categories by spending amount for the chart
sorted_category_spending_filtered = sorted(category_spending_data_filtered.items(), key=lambda item: item[1], reverse=True)

if not sorted_category_spending_filtered:
    st.info(f"No spending data for {selected_month_name} {selected_year} to display charts yet. Add some expenses!")
else:
    # Create a DataFrame for the bar chart
    df_category_spending = pd.DataFrame(sorted_category_spending_filtered, columns=['Category', 'Amount Spent'])
    st.bar_chart(df_category_spending.set_index('Category'))

# Only the "View Summary" button remains unconditionally visible.
with col3: # Re-use col3 from action buttons section for the view summary button if editing is off
    if not is_local_environment: # If not local, only show this button here
        if st.button("📊 View Summary", key="view_summary_btn_non_local"):
            st.session_state.show_summary = True
    else: # If local, ensure original button is still used
        if st.button("📊 View Summary", key="view_summary_btn"):
            st.session_state.show_summary = True # This one is already handled above within is_local_environment block, but kept for clarity


if st.session_state.get('show_summary'):
    st.markdown("---")
    st.subheader("Detailed Spending Summary by Category")
    if not sorted_category_spending_filtered:
        st.info("No spending data to display yet.")
    else:
        for category, amount in sorted_category_spending_filtered:
            st.markdown(f"**{category}:** ₹{amount:,.2f}")
        st.markdown(f"---")
        # Ensure this total is also for the filtered period
        total_spending_filtered = sum(exp.get('amount', 0) for exp in expenses_filtered)
        st.markdown(f"**Total Spent:** ₹{total_spending_filtered:,.2f}") 

    if st.button("Close Detailed Summary", key="close_detailed_summary"):
        st.session_state.show_summary = False


# --- Expense List with Delete and Edit Option ---
st.markdown("---")
st.subheader(f"Transactions for {selected_month_name} {selected_year}")
if not expenses_filtered:
    st.info(f"No expenses recorded for {selected_month_name} {selected_year} yet. Add your first transaction!")
else:
    # Manual table rendering with delete buttons
    # Define columns for layout: Date, Category, Description, Amount, Edit, Delete
    
    # Adjust column layout based on whether editing options are visible
    if is_local_environment:
        cols_header = st.columns([0.15, 0.15, 0.3, 0.2, 0.1, 0.1]) 
    else:
        cols_header = st.columns([0.2, 0.2, 0.4, 0.2]) # Fewer columns if no edit/delete

    with cols_header[0]: st.markdown("**Date**")
    with cols_header[1]: st.markdown("**Category**")
    with cols_header[2]: st.markdown("**Description**")
    with cols_header[3]: st.markdown("**Amount**")
    if is_local_environment:
        with cols_header[4]: st.markdown("**Edit**")
        with cols_header[5]: st.markdown("**Del**")

    st.markdown("---") # Separator for header

    for exp in expenses_filtered:
        if is_local_environment:
            col_date, col_category, col_description, col_amount, col_edit, col_action = st.columns([0.15, 0.15, 0.3, 0.2, 0.1, 0.1])
        else:
            col_date, col_category, col_description, col_amount = st.columns([0.2, 0.2, 0.4, 0.2])
        
        display_date = exp.get('date', 'N/A')
        amount_color = 'red' if exp.get('amount', 0) < 0 else 'green' # Color for income/expense

        with col_date:
            st.markdown(f"<p style='font-size: small;'>{display_date}</p>", unsafe_allow_html=True)
        with col_category:
            st.markdown(f"<p style='font-size: small;'>{exp.get('category', 'Uncategorized')}</p>", unsafe_allow_html=True)
        with col_description:
            st.markdown(f"<p style='font-size: small;'>{exp.get('description', 'N/A')}</p>", unsafe_allow_html=True)
        with col_amount:
            st.markdown(f"<p style='font-weight: bold; color: {amount_color};'>₹{exp.get('amount', 0):,.2f}</p>", unsafe_allow_html=True)
        
        if is_local_environment: # Only show edit and delete buttons in local environment
            with col_edit:
                if st.button("✏️", key=f"edit_{exp['id']}_btn", help="Edit this expense"):
                    st.session_state.show_edit_expense_form = True
                    st.session_state.edit_expense_id = exp['id']
                    st.session_state.show_add_expense_form = False # Hide add form
                    st.rerun()

            with col_action:
                if st.button("❌", key=f"delete_{exp['id']}_btn", help="Delete this expense"):
                    delete_expense(exp['id'], user_id)
        st.markdown("---") # Separator for rows
