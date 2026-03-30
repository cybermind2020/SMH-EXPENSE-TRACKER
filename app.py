from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime, timedelta
import sqlite3
import os
import hashlib
import random
import re
import traceback

app = Flask(__name__)
CORS(app)

# Create data folder
os.makedirs('data', exist_ok=True)

# Database setup
def get_db():
    conn = sqlite3.connect('data/expenses.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            currency TEXT DEFAULT 'INR',
            monthly_income REAL DEFAULT 0,
            savings_goal REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date DATE NOT NULL,
            payment_method TEXT DEFAULT 'Cash',
            receipt_image TEXT,
            is_verified BOOLEAN DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Add missing columns to expenses table (migration)
    cursor.execute("PRAGMA table_info(expenses)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    if 'payment_method' not in existing_columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT DEFAULT 'Cash'")
    if 'receipt_image' not in existing_columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN receipt_image TEXT")
    if 'is_verified' not in existing_columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN is_verified BOOLEAN DEFAULT 0")
    if 'notes' not in existing_columns:
        cursor.execute("ALTER TABLE expenses ADD COLUMN notes TEXT")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            month TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            frequency TEXT NOT NULL,
            next_billing_date DATE NOT NULL,
            category TEXT NOT NULL,
            auto_renew BOOLEAN DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            days INTEGER NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            saved_amount REAL DEFAULT 0,
            completed BOOLEAN DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            challenge_type TEXT DEFAULT 'no_spend',
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0,
            deadline DATE,
            category TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Insert demo data if no users exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        password_hash = hashlib.sha256("demo123".encode()).hexdigest()
        cursor.execute(
            "INSERT INTO users (username, email, password, full_name, monthly_income, savings_goal) VALUES (?, ?, ?, ?, ?, ?)",
            ("demo", "demo@example.com", password_hash, "Demo User", 50000, 10000)
        )
        user_id = cursor.lastrowid
        
        categories = ['Food', 'Travel', 'Shopping', 'Entertainment', 'Bills', 'Healthcare', 'Education']
        descriptions = ['Restaurant', 'Uber', 'Amazon', 'Netflix', 'Electricity', 'Groceries', 'Movie', 'Coffee', 'Shopping Mall', 'Fuel']
        payment_methods = ['Cash', 'Credit Card', 'Debit Card', 'UPI']
        
        for i in range(60):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            amount = random.randint(50, 8000)
            category = random.choice(categories)
            description = random.choice(descriptions)
            payment = random.choice(payment_methods)
            cursor.execute(
                "INSERT INTO expenses (user_id, amount, category, description, date, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, amount, category, description, date, payment)
            )
        
        sample_subs = [
            ('Netflix', 649, 'Monthly', (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'), 'Entertainment'),
            ('Spotify', 119, 'Monthly', (datetime.now() + timedelta(days=12)).strftime('%Y-%m-%d'), 'Entertainment'),
            ('Amazon Prime', 1499, 'Yearly', (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d'), 'Shopping'),
            ('Gym Membership', 1999, 'Monthly', (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d'), 'Healthcare'),
            ('Internet Bill', 999, 'Monthly', (datetime.now() + timedelta(days=8)).strftime('%Y-%m-%d'), 'Bills')
        ]
        for name, amount, freq, date, cat in sample_subs:
            cursor.execute(
                "INSERT INTO subscriptions (user_id, name, amount, frequency, next_billing_date, category) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, amount, freq, date, cat)
            )
        
        sample_goals = [
            ('Emergency Fund', 50000, 15000, (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d'), 'Savings'),
            ('Vacation Trip', 30000, 5000, (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d'), 'Travel'),
            ('New Laptop', 60000, 25000, (datetime.now() + timedelta(days=120)).strftime('%Y-%m-%d'), 'Shopping')
        ]
        for name, target, current, deadline, cat in sample_goals:
            cursor.execute(
                "INSERT INTO goals (user_id, name, target_amount, current_amount, deadline, category) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, target, current, deadline, cat)
            )
    
    conn.commit()
    conn.close()

init_db()

# ========== HTML Template (full, unmodified) ==========
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>SMH Expense Tracker - Smart Personal Finance Manager</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root { --primary: #6366f1; --primary-dark: #4f46e5; --secondary: #8b5cf6; --success: #10b981; --danger: #ef4444; --warning: #f59e0b; --info: #3b82f6; --dark: #0f172a; --light: #f8fafc; --gray: #64748b; --card-bg: #ffffff; --sidebar-bg: #ffffff; --border: #e2e8f0; }
        body { font-family: 'Segoe UI', 'Inter', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; transition: all 0.3s; }
        body.dark-mode { --primary: #818cf8; --primary-dark: #6366f1; --dark: #f1f5f9; --light: #0f172a; --gray: #94a3b8; --card-bg: #1e293b; --sidebar-bg: #0f172a; --border: #334155; background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--border); border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: var(--primary); border-radius: 4px; }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes slideIn { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .app-container { display: flex; min-height: 100vh; }
        .sidebar { width: 280px; background: var(--sidebar-bg); backdrop-filter: blur(10px); border-right: 1px solid var(--border); padding: 30px 20px; position: fixed; height: 100vh; overflow-y: auto; transition: all 0.3s; z-index: 100; }
        .logo-area { display: flex; align-items: center; gap: 12px; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 2px solid var(--border); }
        .logo-icon { width: 48px; height: 48px; background: linear-gradient(135deg, var(--primary), var(--secondary)); border-radius: 16px; display: flex; align-items: center; justify-content: center; font-size: 24px; color: white; }
        .logo-text h1 { font-size: 20px; font-weight: 800; background: linear-gradient(135deg, var(--primary), var(--secondary)); -webkit-background-clip: text; background-clip: text; color: transparent; }
        .logo-text p { font-size: 11px; color: var(--gray); margin-top: 4px; }
        .nav-menu { list-style: none; margin-bottom: 30px; }
        .nav-item { margin-bottom: 8px; }
        .nav-link { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 12px; color: var(--gray); cursor: pointer; transition: all 0.3s; font-weight: 500; }
        .nav-link:hover { background: rgba(99,102,241,0.1); color: var(--primary); transform: translateX(4px); }
        .nav-link.active { background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; box-shadow: 0 4px 12px rgba(99,102,241,0.3); }
        .main-content { flex: 1; margin-left: 280px; padding: 30px 40px; min-height: 100vh; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid var(--border); }
        .page-title h2 { font-size: 28px; font-weight: 700; background: linear-gradient(135deg, var(--primary), var(--secondary)); -webkit-background-clip: text; background-clip: text; color: transparent; }
        .page-title p { color: var(--gray); font-size: 14px; margin-top: 5px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; margin-bottom: 30px; animation: fadeInUp 0.5s ease; }
        .stat-card { background: var(--card-bg); border-radius: 24px; padding: 24px; transition: all 0.3s; border: 1px solid var(--border); position: relative; overflow: hidden; }
        .stat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, var(--primary), var(--secondary)); }
        .stat-card:hover { transform: translateY(-4px); box-shadow: 0 12px 30px rgba(0,0,0,0.1); }
        .score-circle { width: 120px; height: 120px; border-radius: 50%; background: linear-gradient(135deg, var(--primary), var(--secondary)); display: flex; align-items: center; justify-content: center; margin: 10px auto; font-size: 32px; font-weight: bold; color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 24px; margin-bottom: 30px; }
        .card { background: var(--card-bg); border-radius: 24px; padding: 24px; border: 1px solid var(--border); transition: all 0.3s; }
        .card:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.05); }
        canvas { max-height: 300px; width: 100%; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 600; font-size: 13px; color: var(--gray); }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 12px 16px; border: 2px solid var(--border); background: var(--card-bg); border-radius: 16px; font-size: 14px; transition: all 0.3s; color: var(--dark); }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
        .btn { padding: 12px 24px; border: none; border-radius: 16px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s; display: inline-flex; align-items: center; gap: 8px; }
        .btn-primary { background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(99,102,241,0.3); }
        .btn-danger { background: var(--danger); color: white; }
        .btn-success { background: var(--success); color: white; }
        .btn-warning { background: var(--warning); color: white; }
        .btn-secondary { background: var(--gray); color: white; }
        .expense-item, .subscription-item, .goal-item { display: flex; justify-content: space-between; align-items: center; padding: 16px; border-bottom: 1px solid var(--border); transition: all 0.2s; flex-wrap: wrap; gap: 10px; }
        .expense-item:hover, .subscription-item:hover, .goal-item:hover { background: rgba(99,102,241,0.05); transform: translateX(4px); }
        .budget-item { margin-bottom: 20px; padding: 16px; background: var(--card-bg); border-radius: 16px; border: 1px solid var(--border); }
        .budget-header { display: flex; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 10px; }
        .budget-progress { width: 100%; height: 12px; background: var(--border); border-radius: 6px; overflow: hidden; margin: 12px 0; }
        .budget-progress-bar { height: 100%; transition: width 0.5s; border-radius: 6px; }
        .budget-safe { background: linear-gradient(90deg, #10b981, #34d399); }
        .budget-warning { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
        .budget-danger { background: linear-gradient(90deg, #ef4444, #f87171); }
        .subscription-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
        .subscription-card { background: var(--card-bg); border-radius: 16px; padding: 16px; border: 1px solid var(--border); transition: all 0.3s; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); backdrop-filter: blur(10px); justify-content: center; align-items: center; z-index: 1000; }
        .modal.active { display: flex; }
        .modal-content { background: var(--card-bg); border-radius: 32px; padding: 32px; width: 90%; max-width: 500px; animation: fadeInUp 0.3s ease; max-height: 80vh; overflow-y: auto; }
        .notification { position: fixed; top: 24px; right: 24px; padding: 16px 24px; border-radius: 16px; color: white; z-index: 2000; animation: slideIn 0.3s ease; border-left: 4px solid; }
        .voice-assistant { position: fixed; bottom: 30px; right: 30px; width: 60px; height: 60px; background: linear-gradient(135deg, var(--primary), var(--secondary)); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 99; transition: all 0.3s; }
        .voice-assistant:hover { transform: scale(1.1); }
        .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
        .progress-bar-container { width: 100%; height: 10px; background: var(--border); border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .progress-bar-fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--secondary)); transition: width 0.5s; border-radius: 10px; }
        .live-caption { background: var(--border); padding: 15px; border-radius: 16px; margin-top: 15px; min-height: 80px; font-size: 14px; color: var(--dark); }
        .reports-section { display: flex; flex-direction: column; gap: 24px; }
        .report-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 24px; }
        .ai-speaking { animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        @media (max-width: 1024px) { .sidebar { transform: translateX(-100%); position: fixed; } .sidebar.open { transform: translateX(0); } .main-content { margin-left: 0; padding: 20px; } .charts-grid { grid-template-columns: 1fr; } .grid-2 { grid-template-columns: 1fr; } .report-row { grid-template-columns: 1fr; } }
        .text-center { text-align: center; }
        .mt-2 { margin-top: 10px; }
        .mb-2 { margin-bottom: 10px; }
        .flex { display: flex; gap: 10px; flex-wrap: wrap; }
        .danger-text { color: var(--danger); font-weight: bold; }
        .success-text { color: var(--success); font-weight: bold; }
        .icon-btn { background: none; border: none; cursor: pointer; font-size: 16px; padding: 5px; margin: 0 3px; transition: all 0.2s; }
        .icon-btn:hover { transform: scale(1.1); }
        .warning-text { color: var(--warning); font-weight: bold; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: bold; }
        .badge-bronze { background: #cd7f32; color: white; }
        .badge-silver { background: #c0c0c0; color: white; }
        .badge-gold { background: #ffd700; color: black; }
        .alert { padding: 12px; border-radius: 12px; margin-bottom: 12px; }
        .alert-success { background: rgba(16, 185, 129, 0.1); border-left: 4px solid #10b981; }
        .alert-warning { background: rgba(245, 158, 11, 0.1); border-left: 4px solid #f59e0b; }
        .alert-danger { background: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; }
        .alert-info { background: rgba(59, 130, 246, 0.1); border-left: 4px solid #3b82f6; }
        .auth-form { display: none; }
        .auth-form.active { display: block; }
    </style>
</head>
<body>
    <div id="app">
        <!-- Auth Modal -->
        <div id="authModal" class="modal active">
            <div class="modal-content">
                <div class="auth-tabs" style="display: flex; gap: 12px; margin-bottom: 24px;">
                    <button class="tab-btn active" onclick="switchTab('login')" style="flex:1; padding:12px; border:none; background:var(--primary); color:white; border-radius:12px;">Login</button>
                    <button class="tab-btn" onclick="switchTab('register')" style="flex:1; padding:12px; border:none; background:var(--border); border-radius:12px;">Register</button>
                </div>
                <div id="loginForm" class="auth-form active">
                    <h2 style="margin-bottom:24px;">Welcome Back 👋</h2>
                    <div class="form-group"><input type="text" id="loginUsername" placeholder="Username"></div>
                    <div class="form-group"><input type="password" id="loginPassword" placeholder="Password"></div>
                    <button onclick="login()" class="btn btn-primary" style="width:100%">Login</button>
                    <p class="text-center mt-2" style="font-size:12px;color:var(--gray);">Demo: demo / demo123</p>
                </div>
                <div id="registerForm" class="auth-form">
                    <h2 style="margin-bottom:24px;">Create Account ✨</h2>
                    <div class="form-group"><input type="text" id="regUsername" placeholder="Username"></div>
                    <div class="form-group"><input type="email" id="regEmail" placeholder="Email"></div>
                    <div class="form-group"><input type="password" id="regPassword" placeholder="Password"></div>
                    <button onclick="register()" class="btn btn-primary" style="width:100%">Register</button>
                </div>
            </div>
        </div>

        <!-- Voice Recorder Modal -->
        <div id="voiceRecorderModal" class="modal">
            <div class="modal-content">
                <h3><i class="fas fa-microphone"></i> Voice Expense Recorder</h3>
                <p>Speak clearly about your expense (e.g., "Add 250 rupees for coffee")</p>
                <div class="flex mt-2">
                    <button id="startRecordBtn" onclick="startRecording()" class="btn btn-primary"><i class="fas fa-microphone"></i> Start Recording</button>
                    <button id="stopRecordBtn" onclick="stopRecording()" class="btn btn-danger" disabled><i class="fas fa-stop"></i> Stop</button>
                </div>
                <div id="liveCaptionArea" class="live-caption">
                    <i class="fas fa-comment-dots"></i> <span id="liveCaptionText">Click start and speak...</span>
                </div>
                <div id="recordingStatus" class="mt-2"></div>
                <div id="detectedExpense" class="mt-2" style="display:none;"></div>
                <div class="flex mt-2">
                    <button onclick="confirmAddExpense()" id="confirmAddBtn" class="btn btn-success" style="display:none;"><i class="fas fa-check"></i> Add to Expenses</button>
                    <button onclick="cancelAddExpense()" id="cancelAddBtn" class="btn btn-warning" style="display:none;"><i class="fas fa-times"></i> Cancel</button>
                    <button onclick="closeVoiceRecorderModal()" class="btn btn-secondary">Close</button>
                </div>
            </div>
        </div>

        <!-- Receipt Scan Modal -->
        <div id="receiptModal" class="modal">
            <div class="modal-content">
                <h3><i class="fas fa-camera"></i> Scan Receipt</h3>
                <div class="form-group mt-2">
                    <input type="file" id="receiptFile" accept="image/jpeg,image/png,application/pdf">
                </div>
                <button onclick="scanReceipt()" class="btn btn-primary">Scan Receipt</button>
                <div id="receiptResult" class="mt-2"></div>
                <div class="flex mt-2">
                    <button onclick="closeReceiptModal()" class="btn btn-secondary"><i class="fas fa-arrow-left"></i> Back</button>
                </div>
            </div>
        </div>

        <!-- Edit Modals -->
        <div id="editExpenseModal" class="modal"><div class="modal-content"><h3>Edit Expense</h3><input type="hidden" id="editExpenseId"><div class="form-group"><label>Amount (₹)</label><input type="number" id="editAmount" step="0.01"></div><div class="form-group"><label>Description</label><input type="text" id="editDescription"></div><div class="form-group"><label>Category</label><select id="editCategory"><option value="Food">Food</option><option value="Travel">Travel</option><option value="Shopping">Shopping</option><option value="Entertainment">Entertainment</option><option value="Bills">Bills</option><option value="Healthcare">Healthcare</option><option value="Education">Education</option><option value="Other">Other</option></select></div><div class="form-group"><label>Date</label><input type="date" id="editDate"></div><div class="flex"><button onclick="saveExpenseEdit()" class="btn btn-success">Save</button><button onclick="closeEditModal()" class="btn btn-danger">Cancel</button></div></div></div>
        <div id="editSubModal" class="modal"><div class="modal-content"><h3>Edit Subscription</h3><input type="hidden" id="editSubId"><div class="form-group"><label>Service Name</label><input type="text" id="editSubName"></div><div class="form-group"><label>Amount (₹)</label><input type="number" id="editSubAmount" step="0.01"></div><div class="form-group"><label>Frequency</label><select id="editSubFrequency"><option value="Monthly">Monthly</option><option value="Yearly">Yearly</option></select></div><div class="form-group"><label>Category</label><select id="editSubCategory"><option value="Entertainment">Entertainment</option><option value="Shopping">Shopping</option><option value="Bills">Bills</option><option value="Healthcare">Healthcare</option></select></div><div class="form-group"><label>Next Billing Date</label><input type="date" id="editSubNextBilling"></div><div class="flex"><button onclick="saveSubEdit()" class="btn btn-success">Save</button><button onclick="closeSubEditModal()" class="btn btn-danger">Cancel</button></div></div></div>
        <div id="goalModal" class="modal"><div class="modal-content"><h3>Add Financial Goal</h3><div class="form-group"><label>Goal Name</label><input type="text" id="goalName"></div><div class="form-group"><label>Target Amount (₹)</label><input type="number" id="goalTarget" step="0.01"></div><div class="form-group"><label>Current Amount (₹)</label><input type="number" id="goalCurrent" step="0.01" value="0"></div><div class="form-group"><label>Deadline</label><input type="date" id="goalDeadline"></div><div class="form-group"><label>Category</label><select id="goalCategory"><option value="Savings">Savings</option><option value="Travel">Travel</option><option value="Shopping">Shopping</option><option value="Investment">Investment</option></select></div><div class="flex"><button onclick="addGoal()" class="btn btn-success">Add Goal</button><button onclick="closeGoalModal()" class="btn btn-danger">Cancel</button></div></div></div>

        <!-- Main App -->
        <div id="mainApp" style="display: none;">
            <div class="app-container">
                <div class="sidebar">
                    <div class="logo-area"><div class="logo-icon"><i class="fas fa-chart-line"></i></div><div class="logo-text"><h1>SMH Tracker</h1><p>Smart Finance Manager</p></div></div>
                    <ul class="nav-menu">
                        <li class="nav-item"><a class="nav-link active" onclick="showDashboard()"><i class="fas fa-home"></i> Dashboard</a></li>
                        <li class="nav-item"><a class="nav-link" onclick="showAddExpense()"><i class="fas fa-plus-circle"></i> Add Expense</a></li>
                        <li class="nav-item"><a class="nav-link" onclick="showBudget()"><i class="fas fa-chart-pie"></i> Budget</a></li>
                        <li class="nav-item"><a class="nav-link" onclick="showSubscriptions()"><i class="fas fa-repeat"></i> Subscriptions</a></li>
                        <li class="nav-item"><a class="nav-link" onclick="showGoals()"><i class="fas fa-bullseye"></i> Goals</a></li>
                        <li class="nav-item"><a class="nav-link" onclick="showReports()"><i class="fas fa-chart-bar"></i> Reports</a></li>
                        <li class="nav-item"><a class="nav-link" onclick="showInsights()"><i class="fas fa-brain"></i> Insights</a></li>
                        <li class="nav-item"><a class="nav-link" onclick="showChallenge()"><i class="fas fa-trophy"></i> Challenges</a></li>
                    </ul>
                    <div style="margin-top: auto; padding-top: 20px;">
                        <button onclick="openVoiceRecorderModal()" class="btn btn-primary" style="width:100%; margin-bottom:10px;"><i class="fas fa-microphone"></i> Voice Expense</button>
                        <button onclick="openReceiptModal()" class="btn btn-primary" style="width:100%; margin-bottom:10px;"><i class="fas fa-camera"></i> Scan Receipt</button>
                        <button onclick="toggleDarkMode()" class="btn btn-primary" style="width:100%; margin-bottom:10px;"><i class="fas fa-moon"></i> Dark Mode</button>
                        <button onclick="logout()" class="btn btn-danger" style="width:100%;"><i class="fas fa-sign-out-alt"></i> Logout</button>
                    </div>
                </div>

                <div class="main-content">
                    <div class="header"><div class="page-title"><h2 id="pageTitle">Financial Dashboard</h2><p id="pageSubtitle">Track your spending and achieve your financial goals</p></div><button class="btn btn-primary" onclick="showAddExpense()"><i class="fas fa-plus"></i> Add Expense</button></div>

                    <!-- Dashboard Content -->
                    <div id="dashboardContent">
                        <div class="stats-grid">
                            <div class="stat-card"><h3>💰 Total Expenses</h3><p id="totalExpenses">₹0</p><small>This month</small></div>
                            <div class="stat-card"><h3>💳 Financial Health Score</h3><div class="score-circle" id="financialScore">0</div><p id="scoreMessage" style="font-size:12px;"></p></div>
                            <div class="stat-card"><h3>📊 Weekly Trend</h3><p id="weeklyTrend">0%</p><small>vs last week</small></div>
                            <div class="stat-card"><h3>🎯 Goal Progress</h3><p id="goalProgress">0%</p><div class="progress-bar-container"><div id="goalProgressBar" style="width:0%;height:100%;background:linear-gradient(90deg,var(--primary),var(--secondary));border-radius:10px;"></div></div></div>
                        </div>
                        <div class="charts-grid"><div class="card"><h3><i class="fas fa-chart-line"></i> Daily Spending Trend</h3><canvas id="trendChart"></canvas></div><div class="card"><h3><i class="fas fa-chart-pie"></i> Category Breakdown</h3><canvas id="categoryChart"></canvas></div></div>
                        <div class="card"><h3><i class="fas fa-history"></i> Recent Transactions <i class="fas fa-edit"></i></h3><div id="recentExpensesList"></div></div>
                    </div>

                    <!-- Add Expense Content - Fixed -->
                    <div id="addExpenseContent" style="display:none;">
                        <div class="card">
                            <h3>➕ Add New Expense</h3>
                            <div class="grid-2">
                                <div class="form-group">
                                    <label>Amount (₹) *</label>
                                    <input type="number" id="expenseAmount" class="form-control" step="0.01" placeholder="Enter amount" required>
                                </div>
                                <div class="form-group">
                                    <label>Description *</label>
                                    <input type="text" id="expenseDescription" class="form-control" placeholder="e.g., Restaurant, Uber, Shopping" required>
                                </div>
                            </div>
                            <div class="grid-2">
                                <div class="form-group">
                                    <label>Category</label>
                                    <select id="expenseCategory" class="form-control">
                                        <option value="">🤖 Auto-detect</option>
                                        <option value="Food">🍔 Food & Dining</option>
                                        <option value="Travel">✈️ Travel & Transport</option>
                                        <option value="Shopping">🛍️ Shopping</option>
                                        <option value="Entertainment">🎬 Entertainment</option>
                                        <option value="Bills">💡 Bills & Utilities</option>
                                        <option value="Healthcare">🏥 Healthcare</option>
                                        <option value="Education">📚 Education</option>
                                        <option value="Other">📦 Other</option>
                                    </select>
                                </div>
                                <div class="form-group">
                                    <label>Payment Method</label>
                                    <select id="expensePayment" class="form-control">
                                        <option value="Cash">💵 Cash</option>
                                        <option value="Credit Card">💳 Credit Card</option>
                                        <option value="Debit Card">💳 Debit Card</option>
                                        <option value="UPI">📱 UPI</option>
                                    </select>
                                </div>
                            </div>
                            <div class="form-group">
                                <label>Date</label>
                                <input type="date" id="expenseDate" class="form-control">
                            </div>
                            <button onclick="submitExpense()" class="btn btn-primary" style="width:100%"><i class="fas fa-save"></i> Add Expense</button>
                        </div>
                    </div>

                    <!-- Budget Content -->
                    <div id="budgetContent" style="display:none;">
                        <div class="card"><h3>🎯 Set Monthly Budget</h3><div class="grid-2"><div class="form-group"><select id="budgetCategory"><option value="Food">Food</option><option value="Travel">Travel</option><option value="Shopping">Shopping</option><option value="Entertainment">Entertainment</option><option value="Bills">Bills</option><option value="Healthcare">Healthcare</option><option value="Education">Education</option></select></div><div class="form-group"><input type="number" id="budgetAmount" placeholder="Budget Amount"></div></div><button onclick="setBudget()" class="btn btn-primary">Set Budget</button></div>
                        <div class="card"><h3>📊 Budget Status</h3><div id="budgetStatus"></div></div>
                    </div>

                    <!-- Subscriptions Content -->
                    <div id="subscriptionsContent" style="display:none;">
                        <div class="grid-2"><div class="card"><h3>➕ Add Subscription</h3><div class="form-group"><input type="text" id="subName" placeholder="Service Name"></div><div class="form-group"><input type="number" id="subAmount" placeholder="Amount (₹)"></div><div class="form-group"><select id="subFrequency"><option value="Monthly">Monthly</option><option value="Yearly">Yearly</option></select></div><div class="form-group"><select id="subCategory"><option value="Entertainment">Entertainment</option><option value="Shopping">Shopping</option><option value="Bills">Bills</option><option value="Healthcare">Healthcare</option></select></div><div class="form-group"><input type="date" id="subNextBilling"></div><button onclick="addSubscription()" class="btn btn-primary">Add Subscription</button></div><div class="card"><h3>📊 Subscription Analytics</h3><div class="stats-grid" style="grid-template-columns:1fr 1fr;"><div class="stat-card"><h3>Monthly Cost</h3><p id="totalMonthlySubs">₹0</p></div><div class="stat-card"><h3>Annual Cost</h3><p id="totalAnnualSubs">₹0</p></div></div><canvas id="subscriptionChart" style="max-height:200px;"></canvas></div></div>
                        <div class="card"><h3>📋 Your Subscriptions</h3><div id="subscriptionsList" class="subscription-grid"></div></div>
                        <div class="card"><h3>📈 Upcoming Bills</h3><div id="upcomingBills"></div></div>
                    </div>

                    <!-- Goals Content -->
                    <div id="goalsContent" style="display:none;"><div class="card"><h3>🎯 Financial Goals <button onclick="openGoalModal()" class="btn btn-success" style="float:right; padding:8px 16px;"><i class="fas fa-plus"></i> Add Goal</button></h3><div id="goalsList"></div></div></div>

                    <!-- Reports Content -->
                    <div id="reportsContent" style="display:none;">
                        <div class="reports-section">
                            <div class="card"><h3><i class="fas fa-calendar-alt"></i> Date Range Report</h3><div class="date-range-picker" style="display:flex; gap:10px; flex-wrap:wrap;"><input type="date" id="reportStartDate" style="flex:1;"><input type="date" id="reportEndDate" style="flex:1;"><button onclick="generateReport()" class="btn btn-primary">Generate Report</button></div><div class="flex mt-2"><button onclick="generateWeeklyReport()" class="btn btn-primary">Weekly Report</button><button onclick="generateMonthlyReport()" class="btn btn-primary">Monthly Report</button></div></div>
                            <div class="report-row"><div class="card"><h3><i class="fas fa-chart-line"></i> Spending Trend</h3><canvas id="reportTrendChart"></canvas></div><div class="card"><h3><i class="fas fa-chart-bar"></i> Category Summary</h3><canvas id="reportCategoryChart"></canvas></div></div>
                            <div class="report-row"><div class="card"><h3><i class="fas fa-chart-line"></i> Weekly Comparison</h3><canvas id="weeklyComparisonChart"></canvas></div><div class="card"><h3><i class="fas fa-chart-bar"></i> Monthly Summary</h3><canvas id="monthlySummaryChart"></canvas></div></div>
                            <div class="card"><h3><i class="fas fa-table"></i> Transaction Details</h3><div id="reportTransactions" style="max-height:400px;overflow-y:auto;"></div></div>
                        </div>
                    </div>

                    <!-- Insights Content with Female Voice AI -->
                    <div id="insightsContent" style="display:none;">
                        <div class="card"><h3>🤖 AI Spending Insights</h3><div id="insightsList"></div></div>
                        <div class="card"><h3>🔮 Future Prediction</h3><div id="futurePrediction"></div></div>
                        <div class="card"><h3>📊 Spending Patterns</h3><div id="spendingPatterns"></div></div>
                        <div class="card"><h3><i class="fas fa-female"></i> AI Voice Assistant (Female Voice)</h3><div class="flex"><button onclick="askAI()" class="btn btn-primary"><i class="fas fa-play"></i> Ask AI Assistant</button><button onclick="stopAI()" class="btn btn-danger"><i class="fas fa-stop"></i> Stop Speaking</button></div><div id="aiResponse" class="mt-2" style="padding:12px; background:var(--border); border-radius:12px;"></div></div>
                    </div>

                    <!-- Challenges Content -->
                    <div id="challengeContent" style="display:none;">
                        <div class="card" style="background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white;"><h3><i class="fas fa-trophy"></i> No-Spend Challenge</h3><p>Challenge yourself to save money and earn amazing rewards!</p><select id="challengeDays" style="margin:15px 0;padding:10px;border-radius:8px;"><option value="3">3 Days - 🔥 Fire Starter</option><option value="7">7 Days - ⭐ Star Saver</option><option value="14">14 Days - 💎 Diamond Saver</option><option value="30">30 Days - 👑 Money Master</option></select><button onclick="startChallenge()" class="btn" style="background:white;color:var(--primary);">Start Challenge 🚀</button><div id="challengeStatus" class="mt-2"></div></div>
                        <div class="card"><h3><i class="fas fa-chart-line"></i> Challenge Progress</h3><div id="challengeProgress"></div></div>
                        <div class="card"><h3><i class="fas fa-fire"></i> Current Streak</h3><div id="streakDisplay" class="text-center" style="font-size:48px; font-weight:bold;">0 days</div></div>
                        <div class="card"><h3><i class="fas fa-trophy"></i> Achievements & Badges</h3><div id="achievementsList"></div></div>
                        <div class="card"><h3><i class="fas fa-chart-line"></i> Leaderboard</h3><div id="challengeLeaderboard"></div></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="voice-assistant" onclick="openVoiceRecorderModal()"><i class="fas fa-microphone" style="font-size:24px;"></i></div>

    <script>
        let currentUserId = null;
        let trendChart = null, categoryChart = null, subscriptionChart = null;
        let reportTrendChart = null, reportCategoryChart = null, weeklyComparisonChart = null, monthlySummaryChart = null;
        let recognition = null;
        let isRecording = false;
        let detectedExpenseData = null;
        let currentUtterance = null;

        const savedUserId = localStorage.getItem('user_id');
        if (savedUserId) {
            currentUserId = savedUserId;
            document.getElementById('authModal').classList.remove('active');
            document.getElementById('mainApp').style.display = 'block';
            loadDashboard();
            loadSubscriptions();
            loadGoals();
            loadChallengeProgress();
        }

        // --- Authentication ---
        function switchTab(tab) {
            const loginForm = document.getElementById('loginForm');
            const registerForm = document.getElementById('registerForm');
            const tabs = document.querySelectorAll('.tab-btn');
            tabs.forEach(btn => btn.classList.remove('active'));
            if (tab === 'login') {
                loginForm.classList.add('active');
                registerForm.classList.remove('active');
                tabs[0].classList.add('active');
                tabs[0].style.background = 'var(--primary)';
                tabs[1].style.background = 'var(--border)';
            } else {
                loginForm.classList.remove('active');
                registerForm.classList.add('active');
                tabs[1].classList.add('active');
                tabs[1].style.background = 'var(--primary)';
                tabs[0].style.background = 'var(--border)';
            }
        }

        async function login() {
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            if (!username || !password) {
                showNotification('Please enter username and password', 'error');
                return;
            }
            const res = await fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username,password}) });
            const data = await res.json();
            if (res.ok) {
                currentUserId = data.user_id;
                localStorage.setItem('user_id', data.user_id);
                document.getElementById('authModal').classList.remove('active');
                document.getElementById('mainApp').style.display = 'block';
                loadDashboard();
                loadSubscriptions();
                loadGoals();
                showNotification('Welcome back!', 'success');
                speakWithFemaleVoice('Welcome back to your expense tracker!');
            } else {
                showNotification(data.message, 'error');
            }
        }

        async function register() {
            const username = document.getElementById('regUsername').value;
            const email = document.getElementById('regEmail').value;
            const password = document.getElementById('regPassword').value;
            if (!username || !email || !password) {
                showNotification('Please fill all fields', 'error');
                return;
            }
            const res = await fetch('/api/register', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username,email,password}) });
            const data = await res.json();
            if (res.ok) {
                showNotification('Account created! Please login.', 'success');
                switchTab('login');
            } else {
                showNotification(data.message, 'error');
            }
        }

        function logout() {
            localStorage.removeItem('user_id');
            location.reload();
        }

        // --- Navigation ---
        function showDashboard() {
            hideAllContent();
            document.getElementById('dashboardContent').style.display = 'block';
            loadDashboard();
        }
        function showAddExpense() {
            hideAllContent();
            document.getElementById('addExpenseContent').style.display = 'block';
            document.getElementById('expenseDate').value = new Date().toISOString().split('T')[0];
        }
        function showBudget() {
            hideAllContent();
            document.getElementById('budgetContent').style.display = 'block';
            loadBudget();
        }
        function showSubscriptions() {
            hideAllContent();
            document.getElementById('subscriptionsContent').style.display = 'block';
            loadSubscriptions();
        }
        function showGoals() {
            hideAllContent();
            document.getElementById('goalsContent').style.display = 'block';
            loadGoals();
        }
        function showReports() {
            hideAllContent();
            document.getElementById('reportsContent').style.display = 'block';
            generateWeeklyReport();
            generateMonthlyReport();
        }
        function showInsights() {
            hideAllContent();
            document.getElementById('insightsContent').style.display = 'block';
            loadInsights();
        }
        function showChallenge() {
            hideAllContent();
            document.getElementById('challengeContent').style.display = 'block';
            loadChallengeStatus();
            loadChallengeProgress();
            loadAchievements();
            loadLeaderboard();
        }
        function hideAllContent() {
            const contents = ['dashboardContent','addExpenseContent','budgetContent','subscriptionsContent','goalsContent','reportsContent','insightsContent','challengeContent'];
            contents.forEach(c => { const el = document.getElementById(c); if(el) el.style.display = 'none'; });
        }

        // --- Dashboard ---
        async function loadDashboard() {
            const res = await fetch('/api/dashboard-data?user_id=' + currentUserId);
            const data = await res.json();
            document.getElementById('totalExpenses').textContent = `₹${data.monthly_total.toFixed(2)}`;
            document.getElementById('financialScore').textContent = data.financial_score;
            document.getElementById('scoreMessage').textContent = data.financial_score >= 80 ? 'Excellent! 🎉' : data.financial_score >= 60 ? 'Good! 💪' : data.financial_score >= 40 ? 'Fair 📊' : 'Needs attention ⚠️';
            document.getElementById('weeklyTrend').textContent = (data.weekly_trend > 0 ? '+' : '') + data.weekly_trend + '%';
            if (data.goal_progress) {
                document.getElementById('goalProgress').textContent = data.goal_progress + '%';
                document.getElementById('goalProgressBar').style.width = data.goal_progress + '%';
            }
            updateTrendChart(data.expenses);
            updateCategoryChart(data.category_breakdown);
            renderExpensesList(data.expenses);
        }

        function updateTrendChart(expenses) {
            const ctx = document.getElementById('trendChart').getContext('2d');
            const daily = {};
            expenses.forEach(e => { if(!daily[e.date]) daily[e.date]=0; daily[e.date]+=e.amount; });
            const dates = Object.keys(daily).sort().slice(-30);
            const amounts = dates.map(d => daily[d]);
            if(trendChart) trendChart.destroy();
            trendChart = new Chart(ctx, { type:'line', data:{ labels:dates, datasets:[{ label:'Daily Spending (₹)', data:amounts, borderColor:'#6366f1', backgroundColor:'rgba(99,102,241,0.1)', tension:0.4, fill:true }] }, options:{ responsive:true } });
        }

        function updateCategoryChart(breakdown) {
            const ctx = document.getElementById('categoryChart').getContext('2d');
            if(categoryChart) categoryChart.destroy();
            categoryChart = new Chart(ctx, { type:'doughnut', data:{ labels:Object.keys(breakdown), datasets:[{ data:Object.values(breakdown), backgroundColor:['#6366f1','#8b5cf6','#10b981','#f59e0b','#ef4444','#3b82f6','#ec489a'] }] }, options:{ responsive:true } });
        }

        function renderExpensesList(expenses) {
            const container = document.getElementById('recentExpensesList');
            if(expenses.length === 0) { container.innerHTML = '<p class="text-center">No expenses yet</p>'; return; }
            container.innerHTML = expenses.slice(0,15).map(e => `
                <div class="expense-item">
                    <div><div style="font-weight:500">${escapeHtml(e.description)}</div><div style="font-size:12px;color:var(--gray)">${e.category} | ${e.payment_method || 'Cash'}</div></div>
                    <div class="expense-date">${e.date}</div>
                    <div style="font-weight:bold;color:#ef4444">₹${e.amount.toFixed(2)}</div>
                    <div>
                        <button onclick="editExpense(${e.id}, '${e.description}', ${e.amount}, '${e.category}', '${e.date}')" class="icon-btn" style="color:#f59e0b"><i class="fas fa-edit"></i></button>
                        <button onclick="deleteExpense(${e.id})" class="icon-btn" style="color:#ef4444"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `).join('');
        }

        // --- Expense CRUD ---
        async function submitExpense() {
            const amount = parseFloat(document.getElementById('expenseAmount').value);
            const description = document.getElementById('expenseDescription').value.trim();
            const category = document.getElementById('expenseCategory').value;
            const payment = document.getElementById('expensePayment').value;
            const date = document.getElementById('expenseDate').value;
            
            if (!amount || isNaN(amount) || amount <= 0) {
                showNotification('Please enter a valid amount greater than 0', 'error');
                return;
            }
            if (!description || description === '') {
                showNotification('Please enter a description', 'error');
                return;
            }
            
            const expenseData = {
                user_id: parseInt(currentUserId),
                amount: amount,
                description: description,
                category: category || '',
                payment_method: payment,
                date: date || new Date().toISOString().split('T')[0]
            };
            
            try {
                const res = await fetch('/api/expenses', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(expenseData)
                });
                const data = await res.json();
                if (res.ok) {
                    showNotification(`✅ Expense added! Category: ${data.category}`, 'success');
                    speakWithFemaleVoice(`Added expense of ${amount} rupees for ${description}`);
                    document.getElementById('expenseAmount').value = '';
                    document.getElementById('expenseDescription').value = '';
                    document.getElementById('expenseCategory').value = '';
                    document.getElementById('expensePayment').value = 'Cash';
                    loadDashboard();
                    showDashboard();
                } else {
                    showNotification(data.message || 'Failed to add expense', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showNotification('Network error. Please check console.', 'error');
            }
        }

        async function deleteExpense(id) {
            if(!confirm('Delete this expense?')) return;
            await fetch('/api/expenses/'+id, { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId }) });
            showNotification('Expense deleted', 'success');
            loadDashboard();
        }

        function editExpense(id, desc, amount, cat, date) {
            document.getElementById('editExpenseId').value = id;
            document.getElementById('editAmount').value = amount;
            document.getElementById('editDescription').value = desc;
            document.getElementById('editCategory').value = cat;
            document.getElementById('editDate').value = date;
            document.getElementById('editExpenseModal').classList.add('active');
        }

        async function saveExpenseEdit() {
            const id = document.getElementById('editExpenseId').value;
            const amount = parseFloat(document.getElementById('editAmount').value);
            const description = document.getElementById('editDescription').value;
            const category = document.getElementById('editCategory').value;
            const date = document.getElementById('editDate').value;
            await fetch('/api/expenses/'+id, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId, amount, description, category, date }) });
            closeEditModal();
            showNotification('Expense updated!', 'success');
            loadDashboard();
        }

        function closeEditModal() { document.getElementById('editExpenseModal').classList.remove('active'); }

        // --- Budget ---
        async function setBudget() {
            const category = document.getElementById('budgetCategory').value;
            const amount = parseFloat(document.getElementById('budgetAmount').value);
            if (!amount || isNaN(amount) || amount <= 0) {
                showNotification('Please enter a valid budget amount', 'error');
                return;
            }
            await fetch('/api/budget', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId, category, amount }) });
            showNotification('Budget set!', 'success');
            loadBudget();
        }

        async function loadBudget() {
            const res = await fetch('/api/budget/status?user_id=' + currentUserId);
            const budgets = await res.json();
            const container = document.getElementById('budgetStatus');
            if(budgets.length === 0) { container.innerHTML = '<p class="text-center">No budgets set</p>'; return; }
            container.innerHTML = budgets.map(b => {
                const p = (b.spent / b.budget) * 100;
                let statusClass = 'budget-safe';
                let statusText = 'Safe';
                if(p >= 90) { statusClass = 'budget-danger'; statusText = 'Critical!'; }
                else if(p >= 80) { statusClass = 'budget-warning'; statusText = 'Warning!'; }
                return `<div class="budget-item">
                            <div class="budget-header"><strong>${b.category}</strong><span class="${p>=80?'danger-text':p>=70?'warning-text':'success-text'}">₹${b.spent.toFixed(2)} / ₹${b.budget.toFixed(2)} (${p.toFixed(1)}%)</span></div>
                            <div class="budget-progress"><div class="budget-progress-bar ${statusClass}" style="width:${Math.min(p,100)}%"></div></div>
                            <div>Remaining: ₹${(b.budget - b.spent).toFixed(2)}</div>
                            ${p>=80 ? `<div class="alert alert-warning mt-2"><i class="fas fa-exclamation-triangle"></i> ${statusText} You have exceeded ${p.toFixed(0)}% of your budget!</div>` : (p>=70 ? `<div class="alert alert-info mt-2"><i class="fas fa-info-circle"></i> You have used ${p.toFixed(0)}% of your budget. Be careful!</div>` : '')}
                        </div>`;
            }).join('');
        }

        // --- Subscriptions ---
        async function addSubscription() {
            const name = document.getElementById('subName').value;
            const amount = parseFloat(document.getElementById('subAmount').value);
            const frequency = document.getElementById('subFrequency').value;
            const category = document.getElementById('subCategory').value;
            const next_billing = document.getElementById('subNextBilling').value;
            if(!name || !amount) { showNotification('Fill all fields', 'error'); return; }
            await fetch('/api/subscriptions', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId, name, amount, frequency, category, next_billing:next_billing||new Date().toISOString().split('T')[0] }) });
            showNotification('Subscription added!', 'success');
            loadSubscriptions();
        }

        async function deleteSubscription(id) {
            if(!confirm('Delete this subscription?')) return;
            await fetch('/api/subscriptions/'+id, { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId }) });
            showNotification('Subscription deleted', 'success');
            loadSubscriptions();
        }

        async function loadSubscriptions() {
            const res = await fetch('/api/subscriptions?user_id=' + currentUserId);
            const data = await res.json();
            document.getElementById('totalMonthlySubs').textContent = `₹${data.total_monthly.toFixed(2)}`;
            document.getElementById('totalAnnualSubs').textContent = `₹${(data.total_monthly*12).toFixed(2)}`;
            const container = document.getElementById('subscriptionsList');
            if(data.subscriptions.length === 0) { container.innerHTML = '<p class="text-center">No subscriptions</p>'; return; }
            container.innerHTML = data.subscriptions.map(sub => `
                <div class="subscription-card">
                    <div class="flex" style="justify-content:space-between;">
                        <div><strong>${escapeHtml(sub.name)}</strong><br><small>${sub.frequency} · ${sub.category}</small></div>
                        <div style="font-weight:bold;color:#ef4444;">₹${sub.amount.toFixed(2)}</div>
                    </div>
                    <div class="mt-2"><small>Next billing: ${sub.next_billing_date}</small></div>
                    <div class="flex mt-2">
                        <button onclick="editSubscription(${sub.id}, '${sub.name}', ${sub.amount}, '${sub.frequency}', '${sub.category}', '${sub.next_billing_date}')" class="btn btn-warning" style="padding:4px 8px; font-size:12px;">Edit</button>
                        <button onclick="deleteSubscription(${sub.id})" class="btn btn-danger" style="padding:4px 8px; font-size:12px;">Delete</button>
                    </div>
                </div>
            `).join('');

            const upcoming = data.subscriptions.filter(sub => {
                const days = (new Date(sub.next_billing_date) - new Date()) / (1000*60*60*24);
                return days <= 7 && days >= 0;
            }).sort((a,b) => new Date(a.next_billing_date) - new Date(b.next_billing_date));
            const uc = document.getElementById('upcomingBills');
            if(upcoming.length === 0) uc.innerHTML = '<p class="text-center">No upcoming bills in next 7 days ✅</p>';
            else uc.innerHTML = upcoming.map(sub => `
                <div class="subscription-card" style="border-left:4px solid #f59e0b;">
                    <div class="flex" style="justify-content:space-between;">
                        <div><strong>${sub.name}</strong><br><small>Due: ${sub.next_billing_date}</small></div>
                        <div class="danger-text">₹${sub.amount.toFixed(2)}</div>
                    </div>
                </div>
            `).join('');

            if(subscriptionChart) subscriptionChart.destroy();
            subscriptionChart = new Chart(document.getElementById('subscriptionChart').getContext('2d'), {
                type:'pie',
                data:{ labels:data.subscriptions.map(s=>s.name), datasets:[{ data:data.subscriptions.map(s=>s.amount), backgroundColor:['#6366f1','#8b5cf6','#10b981','#f59e0b','#ef4444'] }] },
                options:{ responsive:true, plugins:{ legend:{ position:'bottom' } } }
            });
        }

        function editSubscription(id, name, amount, frequency, category, nextBilling) {
            document.getElementById('editSubId').value = id;
            document.getElementById('editSubName').value = name;
            document.getElementById('editSubAmount').value = amount;
            document.getElementById('editSubFrequency').value = frequency;
            document.getElementById('editSubCategory').value = category;
            document.getElementById('editSubNextBilling').value = nextBilling;
            document.getElementById('editSubModal').classList.add('active');
        }

        async function saveSubEdit() {
            const id = document.getElementById('editSubId').value;
            const name = document.getElementById('editSubName').value;
            const amount = parseFloat(document.getElementById('editSubAmount').value);
            const frequency = document.getElementById('editSubFrequency').value;
            const category = document.getElementById('editSubCategory').value;
            const next_billing = document.getElementById('editSubNextBilling').value;
            await fetch('/api/subscriptions/'+id, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId, name, amount, frequency, category, next_billing }) });
            closeSubEditModal();
            showNotification('Subscription updated!', 'success');
            loadSubscriptions();
        }

        function closeSubEditModal() { document.getElementById('editSubModal').classList.remove('active'); }

        // --- Goals ---
        async function loadGoals() {
            const res = await fetch('/api/goals?user_id=' + currentUserId);
            const goals = await res.json();
            const container = document.getElementById('goalsList');
            if(goals.length === 0) { container.innerHTML = '<p class="text-center">No goals yet. Add your first financial goal!</p>'; return; }
            container.innerHTML = goals.map(g => {
                const progress = (g.current_amount / g.target_amount) * 100;
                return `<div class="goal-item">
                            <div>
                                <div class="subscription-name">🎯 ${escapeHtml(g.name)}</div>
                                <div class="subscription-details">Target: ₹${g.target_amount.toFixed(2)} | Current: ₹${g.current_amount.toFixed(2)} | ${g.deadline ? 'Deadline: '+g.deadline : 'No deadline'}</div>
                                <div class="progress-bar-container"><div class="progress-bar-fill" style="width:${Math.min(progress,100)}%"></div></div>
                            </div>
                            <div class="flex">
                                <button onclick="updateGoalProgress(${g.id})" class="btn btn-primary" style="padding:6px 12px;">Add Progress</button>
                                <button onclick="deleteGoal(${g.id})" class="btn btn-danger" style="padding:6px 12px;">Delete</button>
                            </div>
                        </div>`;
            }).join('');
        }

        function openGoalModal() { document.getElementById('goalModal').classList.add('active'); }
        function closeGoalModal() { document.getElementById('goalModal').classList.remove('active'); }

        async function addGoal() {
            const name = document.getElementById('goalName').value;
            const target = parseFloat(document.getElementById('goalTarget').value);
            const current = parseFloat(document.getElementById('goalCurrent').value);
            const deadline = document.getElementById('goalDeadline').value;
            const category = document.getElementById('goalCategory').value;
            if(!name || !target) { showNotification('Please fill required fields','error'); return; }
            await fetch('/api/goals', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId, name, target_amount:target, current_amount:current, deadline, category }) });
            closeGoalModal();
            showNotification('Goal added!','success');
            loadGoals();
            loadDashboard();
        }

        async function updateGoalProgress(id) {
            const amount = prompt('Enter additional amount saved:');
            if(amount) {
                const addAmount = parseFloat(amount);
                if(!isNaN(addAmount)) {
                    await fetch(`/api/goals/${id}/progress`, { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId, amount:addAmount }) });
                    showNotification('Goal progress updated!','success');
                    loadGoals();
                    loadDashboard();
                }
            }
        }

        async function deleteGoal(id) {
            if(!confirm('Delete this goal?')) return;
            await fetch(`/api/goals/${id}`, { method:'DELETE', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId }) });
            showNotification('Goal deleted','success');
            loadGoals();
            loadDashboard();
        }

        // --- Reports ---
        async function generateReport() {
            const startDate = document.getElementById('reportStartDate').value;
            const endDate = document.getElementById('reportEndDate').value;
            if(!startDate || !endDate) { showNotification('Please select both dates', 'error'); return; }
            const res = await fetch(`/api/report?user_id=${currentUserId}&start=${startDate}&end=${endDate}`);
            const data = await res.json();
            if(reportTrendChart) reportTrendChart.destroy();
            if(reportCategoryChart) reportCategoryChart.destroy();
            reportTrendChart = new Chart(document.getElementById('reportTrendChart').getContext('2d'), { type:'line', data:{ labels:data.dates, datasets:[{ label:'Spending (₹)', data:data.amounts, borderColor:'#6366f1', fill:true }] }, options:{ responsive:true } });
            reportCategoryChart = new Chart(document.getElementById('reportCategoryChart').getContext('2d'), { type:'bar', data:{ labels:data.categories, datasets:[{ label:'Amount (₹)', data:data.category_amounts, backgroundColor:'#6366f1' }] }, options:{ responsive:true } });
            document.getElementById('reportTransactions').innerHTML = data.transactions.map(t => `<div class="expense-item"><div><strong>${t.description}</strong><br><small>${t.category}</small></div><div>₹${t.amount.toFixed(2)}</div><div>${t.date}</div></div>`).join('');
        }

        async function generateWeeklyReport() {
            const res = await fetch(`/api/weekly-report?user_id=${currentUserId}`);
            const data = await res.json();
            if(weeklyComparisonChart) weeklyComparisonChart.destroy();
            weeklyComparisonChart = new Chart(document.getElementById('weeklyComparisonChart').getContext('2d'), { type:'bar', data:{ labels:data.weeks, datasets:[{ label:'Weekly Spending (₹)', data:data.amounts, backgroundColor:'#10b981' }] }, options:{ responsive:true } });
        }

        async function generateMonthlyReport() {
            const res = await fetch(`/api/monthly-report?user_id=${currentUserId}`);
            const data = await res.json();
            if(monthlySummaryChart) monthlySummaryChart.destroy();
            monthlySummaryChart = new Chart(document.getElementById('monthlySummaryChart').getContext('2d'), { type:'line', data:{ labels:data.months, datasets:[{ label:'Monthly Spending (₹)', data:data.amounts, borderColor:'#f59e0b', fill:true }] }, options:{ responsive:true } });
        }

        // --- Insights with Female Voice AI ---
        async function loadInsights() {
            const res = await fetch('/api/insights?user_id=' + currentUserId);
            const data = await res.json();
            document.getElementById('insightsList').innerHTML = data.insights.map(i => `<div class="alert alert-warning"><strong>💡 ${i.message}</strong><br>${i.suggestion}</div>`).join('');
            document.getElementById('futurePrediction').innerHTML = `<div class="alert alert-success"><strong>🔮 ${data.prediction.message}</strong><br>Predicted: ₹${data.prediction.amount.toFixed(2)}</div>`;
            document.getElementById('spendingPatterns').innerHTML = data.patterns.map(p => `<div class="alert alert-info"><strong>📊 ${p.pattern}</strong><br>${p.insight}</div>`).join('');
        }

        function stopAI() {
            if (window.speechSynthesis) {
                window.speechSynthesis.cancel();
                currentUtterance = null;
                document.getElementById('aiResponse').innerHTML = `<i class="fas fa-female"></i> AI Assistant stopped speaking.`;
                showNotification('AI stopped speaking', 'info');
            }
        }

        // Enhanced female voice selection
        let selectedFemaleVoice = null;

        function getFemaleVoice(callback) {
            if (selectedFemaleVoice) {
                callback(selectedFemaleVoice);
                return;
            }
            const voices = window.speechSynthesis.getVoices();
            let femaleVoice = voices.find(voice => 
                voice.name.includes('Google UK English Female') ||
                voice.name.includes('Samantha') ||
                voice.name.includes('Victoria') ||
                voice.name.includes('Karen') ||
                voice.name.includes('Susan') ||
                voice.name.includes('Moira') ||
                voice.name.includes('Tessa') ||
                (voice.lang === 'en-US' && voice.name.toLowerCase().includes('female'))
            );
            if (!femaleVoice) {
                femaleVoice = voices.find(voice => voice.lang === 'en-US');
            }
            if (!femaleVoice && voices.length > 0) {
                femaleVoice = voices[0];
            }
            selectedFemaleVoice = femaleVoice;
            callback(selectedFemaleVoice);
        }

        function speakWithFemaleVoice(text) {
            if (!window.speechSynthesis) return;
            window.speechSynthesis.cancel();
            const speak = () => {
                getFemaleVoice((voice) => {
                    const utterance = new SpeechSynthesisUtterance(text);
                    utterance.lang = 'en-US';
                    utterance.rate = 0.9;
                    utterance.pitch = 1.2;
                    utterance.volume = 1;
                    if (voice) utterance.voice = voice;
                    window.speechSynthesis.speak(utterance);
                });
            };
            if (window.speechSynthesis.getVoices().length) {
                speak();
            } else {
                window.speechSynthesis.onvoiceschanged = speak;
            }
        }

        async function askAI() {
            const res = await fetch(`/api/ai-insight?user_id=${currentUserId}`);
            const data = await res.json();
            const message = data.message;
            document.getElementById('aiResponse').innerHTML = `<i class="fas fa-female ai-speaking"></i> ${message}<br><small class="text-muted">🔊 Speaking...</small>`;
            speakWithFemaleVoice(message);
        }

        // --- Voice Recorder ---
        function openVoiceRecorderModal() {
            document.getElementById('voiceRecorderModal').classList.add('active');
            document.getElementById('liveCaptionText').innerHTML = 'Click start and speak...';
            document.getElementById('recordingStatus').innerHTML = '';
            document.getElementById('detectedExpense').style.display = 'none';
            document.getElementById('confirmAddBtn').style.display = 'none';
            document.getElementById('cancelAddBtn').style.display = 'none';
            detectedExpenseData = null;
        }

        function closeVoiceRecorderModal() {
            document.getElementById('voiceRecorderModal').classList.remove('active');
            if (recognition) {
                recognition.stop();
            }
        }

        function startRecording() {
            if (!('webkitSpeechRecognition' in window)) {
                showNotification('Speech recognition not supported in this browser', 'error');
                return;
            }
            recognition = new webkitSpeechRecognition();
            recognition.lang = 'en-US';
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.onstart = () => {
                document.getElementById('liveCaptionText').innerHTML = '<span style="color: var(--primary);">🎙️ Listening...</span>';
                document.getElementById('startRecordBtn').disabled = true;
                document.getElementById('stopRecordBtn').disabled = false;
                isRecording = true;
            };
            recognition.onresult = (event) => {
                let finalTranscript = '';
                let interim = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += transcript;
                    } else {
                        interim += transcript;
                    }
                }
                const fullText = finalTranscript + interim;
                document.getElementById('liveCaptionText').innerHTML = `<i class="fas fa-comment-dots"></i> ${escapeHtml(fullText)}`;
                if (finalTranscript) {
                    detectExpenseFromText(finalTranscript);
                }
            };
            recognition.onerror = (event) => {
                console.error('Speech recognition error', event.error);
                document.getElementById('liveCaptionText').innerHTML = '<span style="color: var(--danger);">❌ Error: ' + event.error + '</span>';
            };
            recognition.onend = () => {
                document.getElementById('startRecordBtn').disabled = false;
                document.getElementById('stopRecordBtn').disabled = true;
                isRecording = false;
            };
            recognition.start();
        }

        function detectExpenseFromText(text) {
            const amountMatch = text.match(/(\\d+(?:\\.\\d+)?)/);
            let amount = amountMatch ? parseFloat(amountMatch[1]) : 0;
            let description = text.replace(/add|spent|paid|for|on|rs|rupees/gi, '').trim();
            if (amount > 0) {
                description = description.replace(amount.toString(), '').trim();
            }
            if (description.length === 0) {
                description = 'Expense';
            }
            let category = '';
            const lowerText = text.toLowerCase();
            if (lowerText.includes('food') || lowerText.includes('restaurant') || lowerText.includes('coffee') || lowerText.includes('lunch') || lowerText.includes('dinner') || lowerText.includes('groceries')) {
                category = 'Food';
            } else if (lowerText.includes('uber') || lowerText.includes('taxi') || lowerText.includes('travel') || lowerText.includes('fuel') || lowerText.includes('petrol')) {
                category = 'Travel';
            } else if (lowerText.includes('amazon') || lowerText.includes('flipkart') || lowerText.includes('shopping') || lowerText.includes('store') || lowerText.includes('mall')) {
                category = 'Shopping';
            } else if (lowerText.includes('netflix') || lowerText.includes('movie') || lowerText.includes('cinema') || lowerText.includes('spotify') || lowerText.includes('prime')) {
                category = 'Entertainment';
            } else if (lowerText.includes('bill') || lowerText.includes('electricity') || lowerText.includes('water') || lowerText.includes('gas') || lowerText.includes('internet')) {
                category = 'Bills';
            }
            if (amount > 0) {
                detectedExpenseData = { amount, description, category };
                document.getElementById('detectedExpense').innerHTML = `
                    <div class="alert alert-success">
                        <strong><i class="fas fa-receipt"></i> Expense Detected!</strong><br>
                        Amount: ₹${amount}<br>
                        Description: ${escapeHtml(description)}<br>
                        Category: ${category || 'Auto-detect'}
                    </div>
                `;
                document.getElementById('detectedExpense').style.display = 'block';
                document.getElementById('confirmAddBtn').style.display = 'inline-flex';
                document.getElementById('cancelAddBtn').style.display = 'inline-flex';
                document.getElementById('recordingStatus').innerHTML = '<div class="alert alert-info">✅ Expense detected! Click "Add to Expenses" to confirm.</div>';
            } else {
                document.getElementById('detectedExpense').innerHTML = `
                    <div class="alert alert-warning">
                        <strong><i class="fas fa-question-circle"></i> No amount detected</strong><br>
                        Please speak clearly with the amount. Example: "Add 250 rupees for coffee"
                    </div>
                `;
                document.getElementById('detectedExpense').style.display = 'block';
            }
        }

        function stopRecording() {
            if (recognition) {
                recognition.stop();
                isRecording = false;
                document.getElementById('startRecordBtn').disabled = false;
                document.getElementById('stopRecordBtn').disabled = true;
            }
        }

        async function confirmAddExpense() {
            if (!detectedExpenseData) {
                showNotification('No expense detected to add', 'error');
                return;
            }
            const { amount, description, category } = detectedExpenseData;
            const res = await fetch('/api/expenses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: currentUserId,
                    amount,
                    description,
                    category: category || '',
                    payment_method: 'Voice',
                    date: new Date().toISOString().split('T')[0]
                })
            });
            if (res.ok) {
                showNotification(`Expense added: ₹${amount} for ${description}`, 'success');
                speakWithFemaleVoice(`Added expense of ${amount} rupees for ${description}`);
                closeVoiceRecorderModal();
                loadDashboard();
                showDashboard();
            } else {
                const err = await res.json();
                showNotification(err.message || 'Failed to add expense', 'error');
            }
        }

        function cancelAddExpense() {
            detectedExpenseData = null;
            document.getElementById('detectedExpense').style.display = 'none';
            document.getElementById('confirmAddBtn').style.display = 'none';
            document.getElementById('cancelAddBtn').style.display = 'none';
            document.getElementById('recordingStatus').innerHTML = '';
            document.getElementById('liveCaptionText').innerHTML = 'Click start and speak...';
        }

        // --- Receipt Scanner (strict validation) ---
        function openReceiptModal() { document.getElementById('receiptModal').classList.add('active'); }
        function closeReceiptModal() { document.getElementById('receiptModal').classList.remove('active'); }

        async function scanReceipt() {
            const file = document.getElementById('receiptFile').files[0];
            if (!file) { showNotification('Please select a file', 'error'); return; }
            const formData = new FormData();
            formData.append('receipt', file);
            formData.append('user_id', currentUserId);
            const res = await fetch('/api/scan-receipt', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.success) {
                if (data.is_receipt) {
                    // Valid receipt – show add button
                    document.getElementById('receiptResult').innerHTML = `
                        <div class="alert alert-success">✅ Receipt Detected!<br>Amount: ₹${data.amount}<br>Description: ${data.description}<br>Category: ${data.category}<br>
                        <button onclick="addFromReceipt(${data.amount}, '${data.description}', '${data.category}')" class="btn btn-primary mt-2">Add to Expenses</button></div>`;
                } else {
                    // Not a receipt – show warning and do NOT show add button
                    const warningMsg = "Warning: This file does not appear to be a valid receipt. Please upload a clear receipt image or document.";
                    document.getElementById('receiptResult').innerHTML = `
                        <div class="alert alert-danger">⚠️ ${warningMsg}</div>`;
                    speakWithFemaleVoice(warningMsg);
                }
            } else {
                document.getElementById('receiptResult').innerHTML = `<div class="alert alert-danger">❌ ${data.message}</div>`;
            }
        }

        async function addFromReceipt(amount, description, category) {
            const res = await fetch('/api/expenses', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId, amount, description, category, payment_method:'Receipt', date:new Date().toISOString().split('T')[0] }) });
            if(res.ok) { 
                showNotification('Expense added from receipt!', 'success');
                speakWithFemaleVoice(`Added expense from receipt: ${amount} rupees`);
                closeReceiptModal(); 
                loadDashboard();
                showDashboard();
            }
        }

        // --- Challenges ---
        async function startChallenge() {
            const days = parseInt(document.getElementById('challengeDays').value);
            const res = await fetch('/api/challenge', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ user_id:currentUserId, days }) });
            const data = await res.json();
            if (res.ok) {
                showNotification(data.message, 'success');
                speakWithFemaleVoice(data.message);
                loadChallengeStatus();
                loadChallengeProgress();
                loadAchievements();
            } else {
                showNotification(data.message, 'error');
            }
        }

        async function loadChallengeStatus() {
            const res = await fetch('/api/challenge/status?user_id=' + currentUserId);
            const data = await res.json();
            const startBtn = document.querySelector('#challengeContent button[onclick="startChallenge()"]');
            if (data.active) {
                document.getElementById('challengeStatus').innerHTML = `<div class="alert alert-success"><strong>🏆 Active Challenge!</strong><br>${data.message}<br>${data.days_remaining} days remaining!<br>${data.progress ? `<div class="progress-bar-container"><div class="progress-bar-fill" style="width:${data.progress}%"></div></div>` : ''}<br>Keep going! You're doing great! 💪</div>`;
                if (startBtn) startBtn.disabled = true;
            } else {
                document.getElementById('challengeStatus').innerHTML = '<div class="alert alert-warning">No active challenge. Start one to earn amazing rewards! 🎯</div>';
                if (startBtn) startBtn.disabled = false;
            }
        }

        async function loadChallengeProgress() {
            const res = await fetch('/api/challenge/progress?user_id=' + currentUserId);
            const data = await res.json();
            document.getElementById('streakDisplay').innerHTML = `${data.streak_days} days 🔥<br><small>Keep the streak going!</small>`;
            document.getElementById('challengeProgress').innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card"><h3>Completed Challenges</h3><p>${data.completed_challenges}</p></div>
                    <div class="stat-card"><h3>Total Days Saved</h3><p>${data.total_days}</p></div>
                    <div class="stat-card"><h3>Money Saved</h3><p>₹${data.money_saved}</p></div>
                </div>
                <div class="progress-bar-container"><div class="progress-bar-fill" style="width:${Math.min((data.total_days/100)*100,100)}%"></div></div>
                <p class="text-center">${data.total_days}/100 days to Master Saver!</p>
            `;
        }

        async function loadAchievements() {
            const res = await fetch('/api/achievements?user_id=' + currentUserId);
            const data = await res.json();
            document.getElementById('achievementsList').innerHTML = data.achievements.map(a => `
                <div class="subscription-card">
                    <div class="flex"><div><i class="fas fa-${a.icon}"></i> <strong>${a.name}</strong></div><div class="badge badge-${a.type}">${a.type.toUpperCase()}</div></div>
                    <div>${a.description}</div><div class="mt-2"><small>Achieved: ${a.date}</small></div>
                </div>
            `).join('');
        }

        async function loadLeaderboard() {
            const res = await fetch('/api/challenge/leaderboard');
            const data = await res.json();
            document.getElementById('challengeLeaderboard').innerHTML = data.leaderboard.map((u,i) => `<div class="expense-item"><div><strong>${i+1}. ${u.username}</strong><br><small>${u.challenges_completed} challenges</small></div><div>${u.total_days} days saved</div></div>`).join('');
        }

        // --- Dark Mode & Helpers ---
        function toggleDarkMode() {
            document.body.classList.toggle('dark-mode');
            localStorage.setItem('dark_mode', document.body.classList.contains('dark-mode'));
        }
        if(localStorage.getItem('dark_mode') === 'true') document.body.classList.add('dark-mode');

        function showNotification(msg, type) {
            const n = document.createElement('div');
            n.className = 'notification';
            n.style.background = type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6';
            n.style.color = 'white';
            n.innerHTML = msg;
            document.body.appendChild(n);
            setTimeout(() => n.remove(), 3000);
        }

        function escapeHtml(text) {
            const d = document.createElement('div');
            d.textContent = text;
            return d.innerHTML;
        }
    </script>
</body>
</html>'''

# ========== API Routes ==========
@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({'status': 'Server is running'}), 200

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    try:
        password_hash = hashlib.sha256(data['password'].encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (data['username'], data['email'], password_hash))
        conn.commit()
        return jsonify({'message': 'User created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'message': 'User exists'}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    password_hash = hashlib.sha256(data['password'].encode()).hexdigest()
    cursor.execute("SELECT id FROM users WHERE username = ? AND password = ?", (data['username'], password_hash))
    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify({'user_id': user[0]}), 200
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT 100", (user_id,))
    expenses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(expenses)

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    try:
        data = request.json
        if not data:
            return jsonify({'message': 'No data provided'}), 400

        required = ['user_id', 'amount', 'description']
        for field in required:
            if field not in data:
                return jsonify({'message': f'Missing field: {field}'}), 400

        user_id = int(data['user_id'])
        amount = float(data['amount'])
        description = data['description'].strip()
        payment_method = data.get('payment_method', 'Cash')
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))

        # Auto-detect category if not provided
        category = data.get('category')
        if not category or category == '':
            desc_lower = description.lower()
            keywords = {
                'Food': ['swiggy','zomato','food','restaurant','pizza','burger','cafe','coffee','lunch','dinner','groceries','grocery'],
                'Travel': ['uber','ola','taxi','travel','fuel','petrol','bus','train','flight','auto'],
                'Shopping': ['amazon','flipkart','shopping','mall','myntra','store','clothing','shoes','electronics'],
                'Entertainment': ['netflix','movie','cinema','spotify','prime','game','concert','party'],
                'Bills': ['bill','electricity','water','gas','internet','mobile','rent','wifi'],
                'Healthcare': ['hospital','doctor','medicine','clinic','pharmacy','health'],
                'Education': ['course','book','tuition','college','school','class','education']
            }
            for cat, words in keywords.items():
                if any(w in desc_lower for w in words):
                    category = cat
                    break
            if not category:
                category = 'Other'

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO expenses (user_id, amount, category, description, date, payment_method) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, amount, category, description, date, payment_method))
        conn.commit()
        conn.close()
        return jsonify({'category': category, 'message': 'Expense added successfully'}), 201

    except Exception as e:
        print("Error in add_expense:", str(e))
        traceback.print_exc()
        return jsonify({'message': f'Server error: {str(e)}'}), 500

@app.route('/api/expenses/<int:expense_id>', methods=['PUT'])
def update_expense(expense_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE expenses SET amount=?, category=?, description=?, date=? 
        WHERE id=? AND user_id=?
    """, (data['amount'], data['category'], data['description'], data['date'], expense_id, data['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Updated'}), 200

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
def delete_expense(expense_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (expense_id, data['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted'}), 200

@app.route('/api/budget', methods=['POST'])
def set_budget():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    current_month = datetime.now().strftime('%Y-%m')
    cursor.execute("""
        INSERT OR REPLACE INTO budgets (user_id, category, amount, month) 
        VALUES (?, ?, ?, ?)
    """, (data['user_id'], data['category'], data['amount'], current_month))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Budget set'}), 200

@app.route('/api/budget/status', methods=['GET'])
def get_budget_status():
    user_id = request.args.get('user_id')
    current_month = datetime.now().strftime('%Y-%m')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT category, amount FROM budgets 
        WHERE user_id = ? AND month = ?
    """, (user_id, current_month))
    budgets = cursor.fetchall()
    start_date = f"{current_month}-01"
    cursor.execute("""
        SELECT category, SUM(amount) as total 
        FROM expenses 
        WHERE user_id = ? AND date >= ? 
        GROUP BY category
    """, (user_id, start_date))
    spending = dict([(row['category'], row['total']) for row in cursor.fetchall()])
    conn.close()
    return jsonify([{'category': b[0], 'budget': b[1], 'spent': spending.get(b[0], 0)} for b in budgets])

@app.route('/api/subscriptions', methods=['GET'])
def get_subscriptions():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM subscriptions 
        WHERE user_id = ? 
        ORDER BY next_billing_date ASC
    """, (user_id,))
    subs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    total_monthly = 0
    for s in subs:
        if s['frequency'] == 'Monthly':
            total_monthly += s['amount']
        else:
            total_monthly += s['amount'] / 12
    return jsonify({'subscriptions': subs, 'total_monthly': total_monthly})

@app.route('/api/subscriptions', methods=['POST'])
def add_subscription():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO subscriptions (user_id, name, amount, frequency, next_billing_date, category) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data['user_id'], data['name'], data['amount'], data['frequency'], data['next_billing'], data['category']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Added'}), 201

@app.route('/api/subscriptions/<int:sub_id>', methods=['PUT'])
def update_subscription(sub_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE subscriptions 
        SET name=?, amount=?, frequency=?, next_billing_date=?, category=? 
        WHERE id=? AND user_id=?
    """, (data['name'], data['amount'], data['frequency'], data['next_billing'], data['category'], sub_id, data['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Updated'}), 200

@app.route('/api/subscriptions/<int:sub_id>', methods=['DELETE'])
def delete_subscription(sub_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE id=? AND user_id=?", (sub_id, data['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted'}), 200

@app.route('/api/goals', methods=['GET'])
def get_goals():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM goals 
        WHERE user_id = ? AND status = 'active' 
        ORDER BY deadline ASC
    """, (user_id,))
    goals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(goals)

@app.route('/api/goals', methods=['POST'])
def add_goal():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO goals (user_id, name, target_amount, current_amount, deadline, category) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data['user_id'], data['name'], data['target_amount'], data.get('current_amount', 0), data.get('deadline'), data.get('category', 'Savings')))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Goal added'}), 201

@app.route('/api/goals/<int:goal_id>/progress', methods=['PUT'])
def update_goal_progress(goal_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE goals 
        SET current_amount = current_amount + ? 
        WHERE id=? AND user_id=?
    """, (data['amount'], goal_id, data['user_id']))
    cursor.execute("""
        UPDATE goals SET status = 'completed' 
        WHERE id=? AND current_amount >= target_amount
    """, (goal_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Progress updated'}), 200

@app.route('/api/goals/<int:goal_id>', methods=['DELETE'])
def delete_goal(goal_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM goals WHERE id=? AND user_id=?", (goal_id, data['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted'}), 200

@app.route('/api/dashboard-data', methods=['GET'])
def get_dashboard_data():
    user_id = request.args.get('user_id')
    current_month = datetime.now().strftime('%Y-%m')
    last_month = (datetime.now() - timedelta(days=30)).strftime('%Y-%m')
    conn = get_db()
    cursor = conn.cursor()
    start_date = f"{current_month}-01"
    cursor.execute("""
        SELECT * FROM expenses 
        WHERE user_id = ? AND date >= ? 
        ORDER BY date DESC
    """, (user_id, start_date))
    expenses = [dict(row) for row in cursor.fetchall()]
    
    last_start = f"{last_month}-01"
    cursor.execute("""
        SELECT SUM(amount) as total FROM expenses 
        WHERE user_id = ? AND date >= ? AND date < ?
    """, (user_id, last_start, start_date))
    prev_total = cursor.fetchone()['total'] or 0

    this_week_total = sum(e['amount'] for e in expenses if datetime.strptime(e['date'], '%Y-%m-%d') >= datetime.now() - timedelta(days=7))
    last_week_total = sum(e['amount'] for e in expenses if datetime.strptime(e['date'], '%Y-%m-%d') < datetime.now() - timedelta(days=7) and datetime.strptime(e['date'], '%Y-%m-%d') >= datetime.now() - timedelta(days=14))
    weekly_trend = ((this_week_total - last_week_total) / last_week_total * 100) if last_week_total > 0 else 0

    cursor.execute("""
        SELECT SUM(target_amount) as total_target, SUM(current_amount) as total_current 
        FROM goals WHERE user_id = ? AND status = 'active'
    """, (user_id,))
    goal_data = cursor.fetchone()
    goal_progress = (goal_data['total_current'] / goal_data['total_target'] * 100) if goal_data['total_target'] and goal_data['total_target'] > 0 else 0
    
    conn.close()
    total = sum(e['amount'] for e in expenses)
    breakdown = {}
    for e in expenses:
        breakdown[e['category']] = breakdown.get(e['category'], 0) + e['amount']
    score = max(0, min(100, 100 - int(total / 1000)))
    
    return jsonify({
        'expenses': expenses, 
        'monthly_total': total, 
        'previous_total': prev_total, 
        'category_breakdown': breakdown, 
        'financial_score': score, 
        'weekly_trend': round(weekly_trend, 1), 
        'goal_progress': round(goal_progress, 1)
    })

@app.route('/api/report', methods=['GET'])
def get_report():
    user_id = request.args.get('user_id')
    start = request.args.get('start')
    end = request.args.get('end')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM expenses 
        WHERE user_id = ? AND date BETWEEN ? AND ? 
        ORDER BY date ASC
    """, (user_id, start, end))
    expenses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    dates = sorted(list(set(e['date'] for e in expenses)))
    amounts = [sum(e['amount'] for e in expenses if e['date'] == d) for d in dates]
    categories = {}
    for e in expenses:
        categories[e['category']] = categories.get(e['category'], 0) + e['amount']
    
    return jsonify({
        'dates': dates, 
        'amounts': amounts, 
        'categories': list(categories.keys()), 
        'category_amounts': list(categories.values()), 
        'transactions': expenses
    })

@app.route('/api/weekly-report', methods=['GET'])
def get_weekly_report():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    weeks = []
    amounts = []
    for i in range(8):
        end = datetime.now() - timedelta(days=i*7)
        start = end - timedelta(days=7)
        cursor.execute("""
            SELECT SUM(amount) FROM expenses 
            WHERE user_id = ? AND date BETWEEN ? AND ?
        """, (user_id, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')))
        total = cursor.fetchone()[0] or 0
        weeks.insert(0, f"Week {8-i}")
        amounts.insert(0, total)
    conn.close()
    return jsonify({'weeks': weeks, 'amounts': amounts})

@app.route('/api/monthly-report', methods=['GET'])
def get_monthly_report():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    months = []
    amounts = []
    for i in range(6):
        date = datetime.now() - timedelta(days=30*i)
        month_str = date.strftime('%Y-%m')
        cursor.execute("""
            SELECT SUM(amount) FROM expenses 
            WHERE user_id = ? AND date LIKE ?
        """, (user_id, f"{month_str}%"))
        total = cursor.fetchone()[0] or 0
        months.insert(0, date.strftime('%b %Y'))
        amounts.insert(0, total)
    conn.close()
    return jsonify({'months': months, 'amounts': amounts})

@app.route('/api/insights', methods=['GET'])
def get_insights():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM expenses 
        WHERE user_id = ? 
        ORDER BY date DESC LIMIT 100
    """, (user_id,))
    expenses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    insights = []
    cats = {}
    for e in expenses:
        cats[e['category']] = cats.get(e['category'], 0) + e['amount']
    
    if cats:
        top = max(cats, key=cats.get)
        insights.append({'message': f'Top spending: {top} (₹{cats[top]:.2f})', 'suggestion': f'Set a budget for {top} to save 20%'})
    
    total = sum(e['amount'] for e in expenses[:30])
    pred = (total/30)*30 if expenses else 0
    
    weekend_total = sum(e['amount'] for e in expenses if datetime.strptime(e['date'], '%Y-%m-%d').weekday() >= 5)
    weekday_total = sum(e['amount'] for e in expenses if datetime.strptime(e['date'], '%Y-%m-%d').weekday() < 5)
    patterns = []
    if weekday_total > 0:
        patterns.append({'pattern': 'Weekend vs Weekday', 'insight': f'You spend {(weekend_total/weekday_total*100):.0f}% more on weekends'})
    
    return jsonify({'insights': insights[:3], 'prediction': {'amount': pred, 'message': f'You may spend ₹{pred:.0f} this month'}, 'patterns': patterns})

@app.route('/api/ai-insight', methods=['GET'])
def get_ai_insight():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    
    # Get last 30 days spending
    cursor.execute("""
        SELECT SUM(amount) as total FROM expenses 
        WHERE user_id = ? AND date >= date('now', '-30 days')
    """, (user_id,))
    total = cursor.fetchone()['total'] or 0
    cursor.execute("""
        SELECT COUNT(*) as count FROM expenses 
        WHERE user_id = ? AND date >= date('now', '-30 days')
    """, (user_id,))
    count = cursor.fetchone()['count'] or 0
    avg = total / count if count > 0 else 0
    
    # Get current month's spending by category
    current_month = datetime.now().strftime('%Y-%m')
    start_date = f"{current_month}-01"
    cursor.execute("""
        SELECT category, SUM(amount) as total 
        FROM expenses 
        WHERE user_id = ? AND date >= ? 
        GROUP BY category
    """, (user_id, start_date))
    monthly_spending = {row['category']: row['total'] for row in cursor.fetchall()}
    
    # Get budgets for current month
    cursor.execute("""
        SELECT category, amount FROM budgets 
        WHERE user_id = ? AND month = ?
    """, (user_id, current_month))
    budgets = cursor.fetchall()
    
    # Check for budget overruns
    over_budget = []
    for b in budgets:
        spent = monthly_spending.get(b['category'], 0)
        if spent > b['amount']:
            over_budget.append((b['category'], spent, b['amount']))
    
    # General tips based on top spending
    top_category = max(monthly_spending.items(), key=lambda x: x[1])[0] if monthly_spending else None
    saving_tips = {
        'Food': 'Try cooking at home more often, use grocery apps for discounts, or pack lunch for work.',
        'Travel': 'Consider carpooling, using public transport, or consolidating trips to save on fuel.',
        'Shopping': 'Wait 24 hours before making a purchase, look for coupon codes, or use price comparison tools.',
        'Entertainment': 'Explore free local events, use library services, or share subscriptions with family.',
        'Bills': 'Switch to energy-efficient appliances, unplug devices when not in use, or negotiate with service providers.',
        'Healthcare': 'Use generic medicines, maintain a healthy lifestyle to prevent illness, or check for employer wellness programs.',
        'Education': 'Look for free online courses, use open educational resources, or apply for scholarships.'
    }
    
    # Construct message
    messages = [
        f"Your average expense is ₹{avg:.2f}. ",
        f"You've spent ₹{total:.2f} in the last 30 days. "
    ]
    
    if over_budget:
        for cat, spent, budget in over_budget:
            messages.append(f"⚠️ You are over budget in {cat} by ₹{spent - budget:.2f}. ")
        messages.append("Here are some tips to bring your spending back on track: ")
    
    if top_category and top_category in saving_tips:
        messages.append(f"For {top_category}, consider: {saving_tips[top_category]} ")
    
    messages.append("Keep tracking to achieve your financial goals! ")
    messages.append("Every small saving adds up to big results over time!")
    
    conn.close()
    return jsonify({'message': ''.join(messages)})

# Modified scan-receipt with strict validation (no magic)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/scan-receipt', methods=['POST'])
def scan_receipt():
    if 'receipt' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    file = request.files['receipt']
    filename = file.filename.lower()
    
    # Check file extension
    if not allowed_file(filename):
        return jsonify({
            'success': True,
            'is_receipt': False,
            'message': 'Invalid file type. Please upload an image (JPG, PNG) or PDF.'
        })
    
    # Check filename for receipt keywords
    receipt_keywords = ['receipt', 'bill', 'invoice', 'recipt', 'purchase']
    is_receipt = any(keyword in filename for keyword in receipt_keywords)
    
    if is_receipt:
        # Simulate receipt extraction
        amount = random.randint(100, 5000)
        descriptions = ['Restaurant Bill', 'Shopping Receipt', 'Grocery Store', 'Fuel Station', 'Movie Ticket', 'Coffee Shop', 'Supermarket']
        description = random.choice(descriptions)
        if amount < 500:
            category = 'Food'
        elif amount < 2000:
            category = 'Shopping'
        else:
            category = 'Shopping'
        return jsonify({
            'success': True,
            'is_receipt': True,
            'amount': amount,
            'description': description,
            'category': category
        })
    else:
        return jsonify({
            'success': True,
            'is_receipt': False,
            'message': 'This file does not appear to be a valid receipt. Please upload a clear receipt image or document.'
        })

# Modified challenge start with active check
@app.route('/api/challenge', methods=['POST'])
def start_challenge():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if there's already an active challenge
    cursor.execute("""
        SELECT id FROM challenges 
        WHERE user_id = ? AND completed = 0
    """, (data['user_id'],))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return jsonify({'message': 'You already have an active challenge. Complete it first!'}), 400
    
    start_date = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=data['days'])).strftime('%Y-%m-%d')
    cursor.execute("""
        INSERT INTO challenges (user_id, days, start_date, end_date, streak_days) 
        VALUES (?, ?, ?, ?, ?)
    """, (data['user_id'], data['days'], start_date, end_date, 1))
    conn.commit()
    conn.close()
    
    badges = {3: 'Fire Starter', 7: 'Star Saver', 14: 'Diamond Saver', 30: 'Money Master'}
    badge = badges.get(data['days'], 'Saver')
    return jsonify({'message': f'Challenge started! {data["days"]}-day challenge. Earn {badge} badge! 🚀'}), 200

@app.route('/api/challenge/status', methods=['GET'])
def get_challenge_status():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT days, start_date, end_date FROM challenges 
        WHERE user_id = ? AND completed = 0 
        ORDER BY start_date DESC LIMIT 1
    """, (user_id,))
    challenge = cursor.fetchone()
    conn.close()
    
    if challenge:
        end_date = datetime.strptime(challenge[2], '%Y-%m-%d')
        days_remaining = (end_date - datetime.now()).days
        total_days = challenge[0]
        days_passed = total_days - days_remaining
        progress = (days_passed / total_days) * 100 if total_days > 0 else 0
        if days_remaining > 0:
            return jsonify({
                'active': True, 
                'message': f'No spend challenge for {total_days} days!', 
                'days_remaining': days_remaining, 
                'progress': progress
            })
    return jsonify({'active': False})

@app.route('/api/challenge/progress', methods=['GET'])
def get_challenge_progress():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT days FROM challenges 
        WHERE user_id = ? AND completed = 1
    """, (user_id,))
    completed = cursor.fetchall()
    cursor.execute("""
        SELECT streak_days FROM challenges 
        WHERE user_id = ? AND completed = 0 
        ORDER BY start_date DESC LIMIT 1
    """, (user_id,))
    streak = cursor.fetchone()
    conn.close()
    
    streak_days = streak[0] if streak else 0
    total_days = sum(c[0] for c in completed)
    
    return jsonify({
        'completed_challenges': len(completed), 
        'total_days': total_days, 
        'money_saved': total_days * 500, 
        'streak_days': streak_days
    })

@app.route('/api/achievements', methods=['GET'])
def get_achievements():
    user_id = request.args.get('user_id')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT days FROM challenges 
        WHERE user_id = ? AND completed = 1
    """, (user_id,))
    completed = cursor.fetchall()
    conn.close()
    
    achievements = []
    total_days = sum(c[0] for c in completed)
    
    if len(completed) >= 1:
        achievements.append({
            'name': 'First Saver', 
            'description': 'Completed your first challenge!', 
            'type': 'bronze', 
            'icon': 'trophy', 
            'date': 'Recently'
        })
    if total_days >= 7:
        achievements.append({
            'name': 'Week Warrior', 
            'description': 'Saved for a whole week!', 
            'type': 'silver', 
            'icon': 'medal', 
            'date': 'Recently'
        })
    if total_days >= 30:
        achievements.append({
            'name': 'Money Master', 
            'description': 'Saved for 30+ days!', 
            'type': 'gold', 
            'icon': 'crown', 
            'date': 'Recently'
        })
    if total_days >= 100:
        achievements.append({
            'name': 'Legendary Saver', 
            'description': 'Saved for 100+ days!', 
            'type': 'gold', 
            'icon': 'star', 
            'date': 'Recently'
        })
    
    return jsonify({'achievements': achievements})

@app.route('/api/challenge/leaderboard', methods=['GET'])
def get_challenge_leaderboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.username, COUNT(c.id) as challenges, SUM(c.days) as total_days 
        FROM challenges c 
        JOIN users u ON c.user_id = u.id 
        WHERE c.completed = 1 
        GROUP BY u.id 
        ORDER BY total_days DESC 
        LIMIT 10
    ''')
    leaderboard = cursor.fetchall()
    conn.close()
    return jsonify({'leaderboard': [{'username': l[0], 'challenges_completed': l[1], 'total_days': l[2]} for l in leaderboard]})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)