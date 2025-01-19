from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash   

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a random secret key

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  # MySQL username
app.config['MYSQL_PASSWORD'] = ''  # MySQL password (blank by default for WAMP)
app.config['MYSQL_DB'] = 'consulting_system'

mysql = MySQL(app)

# Home Route (Landing Page)
@app.route('/')
def home():
    return render_template('index.html')  # We'll create this template next

# Login Route
# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM User WHERE Username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user[2], password):  # Verify hashed password
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials, please try again."
    return render_template('login.html')


# Dashboard Route (Only accessible after logging in)
@app.route('/dashboard')
def dashboard():
    # Ensure the user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login page if not logged in

    # Get the logged-in consultant's ID from the session
    user_id = session['user_id']

    # Fetch tasks assigned to this consultant
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT Task_ID, Task_Name, Task_Priority, Task_Status, Task_Deadline 
        FROM Task 
        WHERE Consultant_ID = %s
    """, (user_id,))
    tasks = cursor.fetchall()

    # Fetch active projects for this consultant
    cursor.execute("""
        SELECT Project_ID, Project_Name, Project_Status, Project_Deadline 
        FROM Project 
        WHERE Consultant_ID = %s
    """, (user_id,))
    projects = cursor.fetchall()

    cursor.close()

    # Render the dashboard template, passing the tasks and projects
    return render_template('dashboard.html', tasks=tasks, projects=projects)



# Logout Route
@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for('login'))


# Add Project Route (Only accessible by admins)
@app.route('/add_project', methods=['GET', 'POST'])
def add_project():
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            project_name = request.form['project_name']
            project_status = request.form['project_status']
            project_deadline = request.form['project_deadline']
            project_description = request.form['project_description']
            project_deliverables = request.form['project_deliverables']
            client_id = request.form['client_id']

            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO Project (Project_Name, Project_Status, Project_Deadline, Project_Description, Project_Deliverables, Client_ID)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (project_name, project_status, project_deadline, project_description, project_deliverables, client_id))
            mysql.connection.commit()
            cursor.close()

            return redirect(url_for('dashboard'))
        return render_template('add_project.html')
    return redirect(url_for('login'))

# View Projects Route
@app.route('/view_projects')
def view_projects():
    if 'role' in session:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM Project")
        projects = cursor.fetchall()
        cursor.close()
        return render_template('view_projects.html', projects=projects)
    return redirect(url_for('login'))

# Add Task Route (Only accessible by admins)
@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if 'role' in session and session['role'] == 'Admin':
        if request.method == 'POST':
            task_name = request.form['task_name']
            task_priority = request.form['task_priority']
            task_status = request.form['task_status']
            task_deadline = request.form['task_deadline']
            consultant_id = request.form['consultant_id']
            project_id = request.form['project_id']

            cursor = mysql.connection.cursor()
            cursor.execute("""
                INSERT INTO Task (Task_Name, Task_Priority, Task_Status, Task_Deadline, Consultant_ID, Project_ID)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (task_name, task_priority, task_status, task_deadline, consultant_id, project_id))
            mysql.connection.commit()
            cursor.close()

            return redirect(url_for('dashboard'))
        return render_template('add_task.html')
    return redirect(url_for('login'))

# View Tasks Route
@app.route('/view_tasks')
def view_tasks():
    if 'role' in session:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM Task")
        tasks = cursor.fetchall()
        cursor.close()
        return render_template('view_tasks.html', tasks=tasks)
    return redirect(url_for('login'))

# Analytics Route (Accessible by Admins)
@app.route('/analytics')
def analytics():
    if 'role' in session and session['role'] == 'Admin':
        # Fetch total number of clients
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM Client")
        total_clients = cursor.fetchone()[0]

        # Fetch total number of active projects
        cursor.execute("SELECT COUNT(*) FROM Project WHERE Project_Status = 'In Progress'")
        active_projects = cursor.fetchone()[0]

        # Fetch total number of completed projects
        cursor.execute("SELECT COUNT(*) FROM Project WHERE Project_Status = 'Completed'")
        completed_projects = cursor.fetchone()[0]

        # Fetch consultant performance (number of tasks completed and active tasks)
        cursor.execute("""
            SELECT Consultant_ID, 
                   SUM(CASE WHEN Task_Status = 'Completed' THEN 1 ELSE 0 END) AS tasks_completed,
                   SUM(CASE WHEN Task_Status = 'In Progress' THEN 1 ELSE 0 END) AS active_tasks
            FROM Task
            GROUP BY Consultant_ID
        """)
        consultant_performance = cursor.fetchall()
        cursor.close()

        return render_template('analytics.html', total_clients=total_clients,
                               active_projects=active_projects, completed_projects=completed_projects,
                               consultant_performance=consultant_performance)
    return redirect(url_for('login'))

# Register Route (Accessible by anyone)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']  # This will come from the registration form (admin or consultant)

        # Check role and assign accordingly
        if role not in ['admin', 'consultant']:
            Flask('Invalid role selected.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='sha256')

        # Insert the new user into the User table
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO User (Username, Password, Role) VALUES (%s, %s, %s)", (username, hashed_password, role))
        mysql.connection.commit()

        Flask('Registration successful', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')







if __name__ == '__main__':
    app.run(debug=True)
