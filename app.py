from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
import requests


app = Flask(__name__)


app.secret_key = 'my_super_secret_event_key'

def get_db_connection():
    """Opens a connection to our database file."""
    db_path = os.environ.get('DATABASE_PATH', 'database.db')
    conn = sqlite3.connect(db_path)
    

    conn.row_factory = sqlite3.Row
    
    return conn


def notify_owner(subscriber_name, subscriber_email):
    """Sends an email to the wellness account owner when someone new subscribes."""


    api_key      = os.environ.get('RESEND_API_KEY')   # your Resend API key
    owner_email  = os.environ.get('OWNER_EMAIL')      # e.g. wellness@gmail.com
    sender_email = os.environ.get('SENDER_EMAIL')     # e.g. noreply@yourdomain.com

    if not api_key or not owner_email or not sender_email:
        print("Warning: Email not sent — missing RESEND_API_KEY, OWNER_EMAIL, or SENDER_EMAIL env vars")
        return

    response = requests.post(
        'https://api.resend.com/emails',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'from': sender_email,
            'to': owner_email,
            'subject': f'New subscriber: {subscriber_name}',
            'html': f'''
                <h2>New mailing list subscriber!</h2>
                <p><strong>Name:</strong> {subscriber_name}</p>
                <p><strong>Email:</strong> {subscriber_email}</p>
                <p>They signed up via your website's mailing list.</p>
            '''
        }
    )

    if response.status_code != 200:
        print(f"Resend error: {response.text}")


def init_db():
    """Creates the necessary tables if they don't already exist."""
    conn = get_db_connection()
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            capacity INTEGER NOT NULL
        )''')
        
    conn.execute('''
        CREATE TABLE IF NOT EXISTS attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id)
        )''')


    conn.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            subscribed_at TEXT DEFAULT (datetime('now'))
        )''')
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM events")
    if cursor.fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO events (title, date, capacity) VALUES (?, ?, ?)",
            ("Calgary Beauty & Tech Expo 2026", "2026-10-14", 5)
        )
        conn.commit()
        
    conn.close()


@app.route('/')
def index():
    """The Dashboard: Pulls events and calculates remaining spots."""
    conn = get_db_connection()
    

    events = conn.execute('SELECT * FROM events').fetchall()
    

    processed_events = []
    for event in events:
        
        attendee_count = conn.execute(
            'SELECT COUNT(*) FROM attendees WHERE event_id = ?', 
            (event['id'],)
        ).fetchone()[0]
        
       
        spots_left = event['capacity'] - attendee_count
        
        processed_events.append({
            'id': event['id'],
            'title': event['title'],
            'date': event['date'],
            'spots_left': spots_left
        })
        
    conn.close()
    
    return render_template('index.html', events=processed_events)


@app.route('/register/<int:event_id>', methods=['GET', 'POST'])
def register(event_id):
    """Handles showing the form and processing registration data."""
    conn = get_db_connection()
    
    event = conn.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()

    
    if request.method == 'POST':
        user_name = request.form['name']
        user_email = request.form['email']

        
        count = conn.execute('SELECT COUNT(*) FROM attendees WHERE event_id = ?', (event_id,)).fetchone()[0]
        
        if count >= event['capacity']:
            flash('Sorry, this event just sold out!', 'danger')
        else:
            
            conn.execute(
                'INSERT INTO attendees (event_id, name, email) VALUES (?, ?, ?)',
                (event_id, user_name, user_email)
            )
            conn.commit()
            flash('Success! You are registered.', 'success')
            conn.close()
            
           
            return redirect(url_for('index'))

    conn.close()
    
   
    return render_template('register.html', event=event)


@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
    """Mailing list signup page."""
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()

        if not name or not email:
            flash('Please fill in both your name and email.', 'danger')
            return render_template('subscribe.html')

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO subscribers (name, email) VALUES (?, ?)',
                (name, email)
            )
            conn.commit()
            
            notify_owner(name, email)
            flash(f"Thanks {name}! You're on the list!", 'success')
        except sqlite3.IntegrityError:
            
            flash('That email is already subscribed!', 'warning')
        finally:
            conn.close()

        return redirect(url_for('subscribe'))

    return render_template('subscribe.html')


@app.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
    """Lets someone remove themselves from the mailing list."""
    if request.method == 'POST':
        email = request.form['email'].strip()
        conn = get_db_connection()
        result = conn.execute(
            'DELETE FROM subscribers WHERE email = ?', (email,)
        )
        conn.commit()
        conn.close()

        if result.rowcount > 0:
            flash('You have been unsubscribed.', 'success')
        else:
            flash('That email was not found in our list.', 'warning')

        return redirect(url_for('unsubscribe'))

    return render_template('unsubscribe.html')


if __name__ == '__main__':
   
    init_db()
    
    app.run(debug=True, port=8080)