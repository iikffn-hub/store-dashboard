from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
import sqlite3, os, json
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'store.db')
SEED_PATH = os.path.join(BASE_DIR, 'seed_data.json')
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-secret-key')
DEFAULT_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
DEFAULT_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Store@12345')

app = Flask(__name__)
app.secret_key = SECRET_KEY

PRODUCT_MAP = {
    'YO': 'Youtube', 'YT': 'Youtube', 'IP': 'IPTV', 'IPTV': 'IPTV', 'CR': 'Crunchyroll', 'VPN': 'VPN',
    'CN': 'Canva', 'CG': 'ChatGPT', 'SH': 'Shahid', 'NE': 'Netflix', 'NF': 'Netflix ',
    'WI': 'Windows ', 'MO': 'MicrosoftOFFICE', 'NI': 'Nitro'
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def parse_date(value):
    if not value:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    value = str(value).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except Exception:
            pass
    return value


def days_left(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value)).date()
        return (d - date.today()).days
    except Exception:
        return None


def init_db(force=False):
    if os.path.exists(DB_PATH) and not force:
        return
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = get_conn()
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT
    );
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_code TEXT UNIQUE,
        name TEXT,
        phone TEXT,
        city TEXT,
        purchase_count INTEGER DEFAULT 0
    );
    CREATE TABLE email_banks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_code TEXT,
        email TEXT,
        password TEXT,
        account_ref TEXT,
        notes TEXT
    );
    CREATE TABLE orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_ref TEXT,
        order_number TEXT,
        customer_code TEXT,
        subscription_type TEXT,
        order_date TEXT,
        end_date TEXT,
        total REAL,
        source TEXT,
        status TEXT,
        send_expiry_notice INTEGER DEFAULT 0,
        password_changed INTEGER DEFAULT 0,
        send_new_password INTEGER DEFAULT 0,
        sync_files INTEGER DEFAULT 0
    );
    CREATE TABLE subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        program_name TEXT,
        account_id TEXT,
        renew_date TEXT,
        account_end_date TEXT,
        renew_value REAL,
        login_identifier TEXT,
        login_password TEXT,
        source_order_number TEXT,
        customer_code TEXT,
        product_name TEXT,
        start_date TEXT,
        customer_end_date TEXT,
        extra1 TEXT,
        extra2 TEXT,
        extra3 TEXT,
        notes TEXT
    );
    ''')
    cur.execute('INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)', (DEFAULT_USERNAME, DEFAULT_PASSWORD, 'مدير المتجر'))

    if os.path.exists(SEED_PATH):
        with open(SEED_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for c in data.get('customers', []):
            cur.execute('INSERT INTO customers (customer_code, name, phone, city, purchase_count) VALUES (?,?,?,?,?)', (
                c.get('customer_code'), c.get('name'), c.get('phone'), c.get('city'), c.get('purchase_count') or 0
            ))
        for e in data.get('email_banks', []):
            cur.execute('INSERT INTO email_banks (email_code, email, password, account_ref, notes) VALUES (?,?,?,?,?)', (
                e.get('email_code'), e.get('email'), e.get('password'), e.get('account_ref'), e.get('notes')
            ))
        for o in data.get('orders', []):
            cur.execute('''INSERT INTO orders
                (email_ref, order_number, customer_code, subscription_type, order_date, end_date, total, source, status,
                 send_expiry_notice, password_changed, send_new_password, sync_files)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                o.get('email_ref'), o.get('order_number'), o.get('customer_code'), o.get('subscription_type'),
                parse_date(o.get('order_date')), parse_date(o.get('end_date')), o.get('total'), o.get('source'), o.get('status'),
                int(bool(o.get('send_expiry_notice'))), int(bool(o.get('password_changed'))),
                int(bool(o.get('send_new_password'))), int(bool(o.get('sync_files')))
            ))
        for s in data.get('subscriptions', []):
            cur.execute('''INSERT INTO subscriptions
                (program_name, account_id, renew_date, account_end_date, renew_value, login_identifier, login_password,
                 source_order_number, customer_code, product_name, start_date, customer_end_date, extra1, extra2, extra3, notes)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                s.get('program_name'), s.get('account_id'), parse_date(s.get('renew_date')), parse_date(s.get('account_end_date')),
                s.get('renew_value'), s.get('login_identifier'), s.get('login_password'), s.get('source_order_number'),
                s.get('customer_code'), s.get('product_name'), parse_date(s.get('start_date')), parse_date(s.get('customer_end_date')),
                s.get('extra1'), s.get('extra2'), s.get('extra3'), s.get('notes')
            ))

    conn.commit()
    conn.close()


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        conn = get_conn()
        user = conn.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user'] = username
            return redirect(url_for('dashboard'))
        flash('بيانات الدخول غير صحيحة')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    conn = get_conn()
    stats = {
        'orders': conn.execute('SELECT COUNT(*) c FROM orders').fetchone()['c'],
        'customers': conn.execute('SELECT COUNT(*) c FROM customers').fetchone()['c'],
        'emails': conn.execute('SELECT COUNT(*) c FROM email_banks').fetchone()['c'],
        'subscriptions': conn.execute('SELECT COUNT(*) c FROM subscriptions').fetchone()['c'],
        'active_subscriptions': conn.execute("SELECT COUNT(*) c FROM subscriptions WHERE customer_end_date IS NOT NULL AND customer_end_date >= date('now')").fetchone()['c'],
        'expiring_soon': conn.execute("SELECT COUNT(*) c FROM subscriptions WHERE customer_end_date IS NOT NULL AND julianday(customer_end_date) - julianday('now') BETWEEN 0 AND 7").fetchone()['c'],
        'sales_total': conn.execute('SELECT ROUND(COALESCE(SUM(total),0),2) c FROM orders').fetchone()['c'],
    }
    recent_orders = rows_to_dicts(conn.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 10').fetchall())
    expiring = rows_to_dicts(conn.execute("SELECT * FROM subscriptions WHERE customer_end_date IS NOT NULL ORDER BY customer_end_date ASC LIMIT 10").fetchall())
    conn.close()
    for row in recent_orders:
        row['days_left'] = days_left(row.get('end_date'))
    for row in expiring:
        row['days_left'] = days_left(row.get('customer_end_date'))
    return render_template('dashboard.html', stats=stats, recent_orders=recent_orders, expiring=expiring, user=session.get('user'))


@app.route('/data/<table_name>')
@login_required
def data_list(table_name):
    if table_name not in {'orders', 'customers', 'email_banks', 'subscriptions'}:
        return 'Not found', 404
    conn = get_conn()
    q = request.args.get('q', '').strip()
    if q:
        cols = {
            'orders': 'order_number, customer_code, subscription_type, status, source',
            'customers': 'customer_code, name, phone, city',
            'email_banks': 'email_code, email, account_ref',
            'subscriptions': 'program_name, account_id, customer_code, product_name, login_identifier'
        }[table_name]
        sql = f"SELECT * FROM {table_name} WHERE ({' OR '.join([c.strip()+' LIKE ?' for c in cols.split(',')])}) ORDER BY id DESC LIMIT 500"
        params = tuple([f'%{q}%'] * len(cols.split(',')))
        rows = rows_to_dicts(conn.execute(sql, params).fetchall())
    else:
        rows = rows_to_dicts(conn.execute(f'SELECT * FROM {table_name} ORDER BY id DESC LIMIT 500').fetchall())
    conn.close()
    for row in rows:
        if 'end_date' in row:
            row['days_left'] = days_left(row.get('end_date'))
        if 'customer_end_date' in row:
            row['days_left'] = days_left(row.get('customer_end_date'))
    return render_template('table.html', table_name=table_name, rows=rows, q=q)


@app.route('/api/<table_name>', methods=['POST'])
@login_required
def create_record(table_name):
    payload = request.get_json(force=True)
    conn = get_conn(); cur = conn.cursor()
    if table_name == 'customers':
        cur.execute('INSERT INTO customers (customer_code, name, phone, city, purchase_count) VALUES (?,?,?,?,?)', (
            payload.get('customer_code'), payload.get('name'), payload.get('phone'), payload.get('city'), payload.get('purchase_count') or 0
        ))
    elif table_name == 'email_banks':
        cur.execute('INSERT INTO email_banks (email_code, email, password, account_ref, notes) VALUES (?,?,?,?,?)', (
            payload.get('email_code'), payload.get('email'), payload.get('password'), payload.get('account_ref'), payload.get('notes')
        ))
    elif table_name == 'orders':
        cur.execute('''INSERT INTO orders (email_ref, order_number, customer_code, subscription_type, order_date, end_date, total, source, status,
                    send_expiry_notice, password_changed, send_new_password, sync_files) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            payload.get('email_ref'), payload.get('order_number'), payload.get('customer_code'), payload.get('subscription_type'), payload.get('order_date'),
            payload.get('end_date'), payload.get('total'), payload.get('source'), payload.get('status'), int(bool(payload.get('send_expiry_notice'))),
            int(bool(payload.get('password_changed'))), int(bool(payload.get('send_new_password'))), int(bool(payload.get('sync_files')))
        ))
    elif table_name == 'subscriptions':
        cur.execute('''INSERT INTO subscriptions (program_name, account_id, renew_date, account_end_date, renew_value, login_identifier, login_password,
                    source_order_number, customer_code, product_name, start_date, customer_end_date, extra1, extra2, extra3, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            payload.get('program_name'), payload.get('account_id'), payload.get('renew_date'), payload.get('account_end_date'), payload.get('renew_value'),
            payload.get('login_identifier'), payload.get('login_password'), payload.get('source_order_number'), payload.get('customer_code'), payload.get('product_name'),
            payload.get('start_date'), payload.get('customer_end_date'), payload.get('extra1'), payload.get('extra2'), payload.get('extra3'), payload.get('notes')
        ))
    else:
        return jsonify({'ok': False, 'error': 'invalid table'}), 400
    conn.commit(); new_id = cur.lastrowid; conn.close()
    return jsonify({'ok': True, 'id': new_id})


@app.route('/api/<table_name>/<int:row_id>', methods=['PUT'])
@login_required
def update_record(table_name, row_id):
    payload = request.get_json(force=True)
    conn = get_conn(); cur = conn.cursor()
    allowed = {
        'customers': ['customer_code','name','phone','city','purchase_count'],
        'email_banks': ['email_code','email','password','account_ref','notes'],
        'orders': ['email_ref','order_number','customer_code','subscription_type','order_date','end_date','total','source','status','send_expiry_notice','password_changed','send_new_password','sync_files'],
        'subscriptions': ['program_name','account_id','renew_date','account_end_date','renew_value','login_identifier','login_password','source_order_number','customer_code','product_name','start_date','customer_end_date','extra1','extra2','extra3','notes']
    }
    if table_name not in allowed:
        return jsonify({'ok': False, 'error': 'invalid table'}), 400
    fields = [k for k in allowed[table_name] if k in payload]
    if not fields:
        return jsonify({'ok': False, 'error': 'no fields'}), 400
    sql = f"UPDATE {table_name} SET {', '.join([f'{f}=?' for f in fields])} WHERE id=?"
    vals = [payload[f] for f in fields] + [row_id]
    cur.execute(sql, vals)
    conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.route('/api/<table_name>/<int:row_id>', methods=['DELETE'])
@login_required
def delete_record(table_name, row_id):
    if table_name not in {'orders', 'customers', 'email_banks', 'subscriptions'}:
        return jsonify({'ok': False, 'error': 'invalid table'}), 400
    conn = get_conn(); conn.execute(f'DELETE FROM {table_name} WHERE id=?', (row_id,)); conn.commit(); conn.close()
    return jsonify({'ok': True})


@app.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    message = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username and password:
            conn = get_conn()
            conn.execute('UPDATE users SET username=?, password=? WHERE id=1', (username, password))
            conn.commit(); conn.close()
            session['user'] = username
            message = 'تم تحديث بيانات الدخول.'
    return render_template('settings.html', message=message)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
