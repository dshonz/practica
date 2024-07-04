from http.server import BaseHTTPRequestHandler, HTTPServer
import sqlite3
import random
import urllib.parse
from hashlib import sha256

PORT = 8000

def get_db_connection():
    conn = sqlite3.connect('duties.db')
    conn.row_factory = sqlite3.Row
    return conn

def authenticate_user(username, password):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if user and user['password_hash'] == sha256(password.encode()).hexdigest():
        return user
    return None

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):

        if self.path == "/":
            self.show_index()
        elif self.path == "/login":
            self.show_login()
        elif self.path == "/calendar" :
            self.show_calendar()
        elif self.path == "/register":
            self.show_register()
        elif self.path.startswith("/static/"):
            self.serve_static()
        elif self.path == "/logout?":
            self.handle_logout()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def do_POST(self):
        if self.path == "/login":
            self.handle_login()
        if self.path == "/register":
            self.handle_register()
        elif self.path == "/add":
            self.handle_add_duty()
        elif self.path == "/add_employee":
            self.handle_add_employee()
        elif self.path.startswith("/delete_duty"):
            self.handle_delete_duty()
        elif self.path.startswith("/delete_employee"):
            self.handle_delete_employee()
        elif self.path == "/logout?":
            self.handle_logout()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    
    def show_index(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open('templates/index.html', 'r', encoding='utf-8') as file:
            template = file.read()
        self.wfile.write(template.encode('utf-8'))


    def show_calendar(self, message=None):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        conn = get_db_connection()
        duties = conn.execute('''
            SELECT duties.id, duties.date, employees.name 
            FROM duties 
            JOIN employees ON duties.employee_id = employees.id
            ORDER BY duties.date ASC
        ''').fetchall()
        employees = conn.execute('SELECT * FROM employees').fetchall()
        conn.close()
        with open('templates/calendar.html', 'r', encoding='utf-8') as file:
            template = file.read()
        
        duties_html = ''.join([f'''
            <li>{duty["date"]} - {duty["name"]}
                <form action="/delete_duty" method="post" style="display:inline;">
                    <input type="hidden" name="id" value="{duty["id"]}">
                    <button type="submit">Удалить</button>
                </form>
            </li>''' for duty in duties])
        
        employees_options = ''.join([f'<option value="{employee["id"]}">{employee["name"]}</option>' for employee in employees])
        employees_html = ''.join([f'''
            <li>{employee["name"]}
                <form action="/delete_employee" method="post" style="display:inline;">
                    <input type="hidden" name="id" value="{employee["id"]}">
                    <button type="submit">Удалить</button>
                </form>
            </li>''' for employee in employees])
        
        template = template.replace('{{ duties }}', duties_html)
        template = template.replace('{{ employees }}', employees_html)
        template = template.replace('{{ employees_options }}', employees_options)
        if message:
            template = template.replace('{{ message }}', f'<p>{message}</p>')
        else:
            template = template.replace('{{ message }}', '')

        self.wfile.write(template.encode('utf-8'))

    def show_login(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open('templates/index.html', 'r', encoding='utf-8') as file:
            template = file.read()
        self.wfile.write(template.encode('utf-8'))

    def show_register(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        with open('templates/register.html', 'r', encoding='utf-8') as file:
            template = file.read()
        self.wfile.write(template.encode('utf-8'))

    def serve_static(self):
        try:
            with open(self.path[1:], 'rb') as file:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def handle_login(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))
        username = params['username'][0]
        password = params['password'][0]
        user = authenticate_user(username, password)
        if user:
            self.send_response(302)
            self.send_header('Set-Cookie', f'session_id={user["id"]}')
            self.send_header('Location', '/calendar')
            self.end_headers()
        else:
            self.send_response(302)
            self.send_header('Location', '/login')
            self.end_headers()

    def handle_register(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))
        username = params['username'][0]
        password = params['password'][0]

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, sha256(password.encode()).hexdigest()))
            conn.commit()
            self.send_response(302)
            self.send_header('Location', '/login')
            self.end_headers()
        except sqlite3.IntegrityError:
            conn.rollback()
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Username already exists')

    def handle_add_duty(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))
        date = params['date'][0]
        employee_id = params.get('employee_id', [None])[0]
        conn = get_db_connection()
        if employee_id:
            conn.execute('INSERT INTO duties (date, employee_id) VALUES (?, ?)', (date, employee_id))
        else:
            employees = conn.execute('SELECT * FROM employees').fetchall()
            if employees:
                employee = random.choice(employees)
                conn.execute('INSERT INTO duties (date, employee_id) VALUES (?, ?)', (date, employee['id']))
        conn.commit()
        conn.close()
        self.send_response(302)
        self.send_header('Location', '/calendar')
        self.end_headers()

    def handle_add_employee(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))
        name = params['name'][0].strip()

        if name:
            conn = get_db_connection()
            existing_employee = conn.execute('SELECT id FROM employees WHERE name = ?', (name,)).fetchone()
            if existing_employee:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(f'''
                    <html>
                    <head>
                        <meta http-equiv="refresh" content="2;url=/calendar" />
                    </head>
                    <body>
                        <h1>Пользователь {name} уже существует!</h1>
                    </body>
                    </html>
                '''.encode('utf-8'))
            else:
                conn.execute('INSERT INTO employees (name) VALUES (?)', (name,))
                conn.commit()
                self.send_response(302)
                self.send_header('Location', '/calendar')
                self.end_headers()
            conn.close()
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write('''
                <html>
                <head>
                    <meta http-equiv="refresh" content="2;url=/" />
                </head>
                <body>
                    <h1>Введите имя сотрудника!</h1>
                </body>
                </html>
            '''.encode('utf-8'))

    def handle_delete_duty(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))
        duty_id = params['id'][0]
        conn = get_db_connection()
        conn.execute('DELETE FROM duties WHERE id = ?', (duty_id,))
        conn.commit()
        conn.close()
        self.send_response(302)
        self.send_header('Location', '/calendar')
        self.end_headers()

    def handle_delete_employee(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        params = urllib.parse.parse_qs(post_data.decode('utf-8'))
        employee_id = params['id'][0]
        conn = get_db_connection()
        conn.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
        conn.commit()
        conn.close()
        self.send_response(302)
        self.send_header('Location', '/calendar')
        self.end_headers()

    def handle_logout(self):
        self.send_response(302)
        self.send_header('Set-Cookie', 'session_id=; Expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.send_header('Location', '/login')
        self.end_headers()

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler):
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    print(f'Server running on port {PORT}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
