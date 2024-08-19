from flask import Flask, render_template, request, redirect, url_for, flash
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from datetime import datetime
from collections import Counter
from flask_paginate import Pagination, get_page_parameter
from collections import defaultdict
import re

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://localhost:27017/ddconnect"
app.secret_key = 'bf22c0d86934b33847cfb52ed0ad40f7908264ebc805790b'  

mongo = PyMongo(app)



# We'll add routes here later
def get_users():
    return list(mongo.db.users.find())

def get_projects():
    return list(mongo.db.projects.find())

def get_time_entries():
    return list(mongo.db.time_data.find())

def get_user_by_login(login):
    return mongo.db.users.find_one({"login": login})

def add_time_entry(entry):
    return mongo.db.time_data.insert_one(entry)

def update_time_entry(entry_id, updated_data):
    return mongo.db.time_data.update_one({"_id": ObjectId(entry_id)}, {"$set": updated_data})

def delete_time_entry(entry_id):
    return mongo.db.time_data.delete_one({"_id": ObjectId(entry_id)})

@app.route('/')
def index():
    # Get project data
    projects = get_projects()
    project_names = [p['name'] for p in projects]
    
    # Count employees per project and calculate work hours
    time_entries = get_time_entries()
    project_employee_count = defaultdict(set)
    project_work_hours = defaultdict(float)
    
    for entry in time_entries:
        for project in entry['project']:
            project_employee_count[project].add(entry['login'])
            project_work_hours[project] += time_to_hours(entry['work_time'])
    
    project_employee_count = {k: len(v) for k, v in project_employee_count.items()}
    
    # Round work hours to 2 decimal places
    project_work_hours = {k: round(v, 2) for k, v in project_work_hours.items()}
    
    # Count employees per department
    users = get_users()
    department_employee_count = Counter(user['department']['name'] for user in users)
    
    return render_template('dashboard.html', 
                           project_names=project_names,
                           project_employee_count=dict(project_employee_count),
                           department_employee_count=dict(department_employee_count),
                           project_work_hours=dict(project_work_hours))


@app.route('/add_entry', methods=['GET', 'POST'])
def add_entry():
    if request.method == 'POST':
        entry = {
            "login": request.form['login'],
            "date": datetime.strptime(request.form['date'], '%Y-%m-%d'),
            "day": request.form['day'],
            "project": request.form.getlist('project'),
            "task": {project: request.form[f'task_{project}'] for project in request.form.getlist('project')},
            "start_time": request.form['start_time'],
            "stop_time": request.form['stop_time'],
            "work_time": request.form['work_time']
        }
        mongo.db.time_data.insert_one(entry)
        flash('Entry added successfully', 'success')
        return redirect(url_for('time_entries'))
    
    users = get_users()
    projects = get_projects()
    return render_template('add_entry.html', users=users, projects=projects)

@app.route('/edit_entry/<entry_id>', methods=['GET', 'POST'])
def edit_entry(entry_id):
    entry = mongo.db.time_data.find_one({"_id": ObjectId(entry_id)})
    if request.method == 'POST':
        # Convert date string to datetime object
        date_str = request.form['date']
        date_obj = datetime.strptime(date_str, '%Y-%m-%d') if isinstance(date_str, str) else date_str
        
        updated_data = {
            "login": request.form['login'],
            "date": date_obj,
            "day": request.form['day'],
            "project": request.form.getlist('project'),
            "task": {project: request.form[f'task_{project}'] for project in request.form.getlist('project')},
            "start_time": request.form['start_time'],
            "stop_time": request.form['stop_time'],
            "work_time": request.form['work_time']
        }
        mongo.db.time_data.update_one({"_id": ObjectId(entry_id)}, {"$set": updated_data})
        flash('Entry updated successfully', 'success')
        return redirect(url_for('time_entries'))
    
    users = get_users()
    projects = get_projects()
    return render_template('edit_entry.html', entry=entry, users=users, projects=projects)

@app.route('/delete_entry/<entry_id>')
def delete_entry(entry_id):
    mongo.db.time_data.delete_one({"_id": ObjectId(entry_id)})
    flash('Entry deleted successfully', 'success')
    return redirect(url_for('time_entries'))

@app.route('/projects')
def project_list():
    search = request.args.get('search', '')
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10
    
    query = {}
    if search:
        query['name'] = {'$regex': search, '$options': 'i'}
    
    offset = (page - 1) * per_page
    total = mongo.db.projects.count_documents(query)
    projects = mongo.db.projects.find(query).skip(offset).limit(per_page)
    pagination = Pagination(page=page, total=total, per_page=per_page, css_framework='bootstrap4')
    
    return render_template('project_list.html', projects=projects, pagination=pagination, search=search)


@app.route('/project/add', methods=['GET', 'POST'])
def add_project():
    if request.method == 'POST':
        project = {
            "name": request.form['name'],
            "type": "Project",
            "id": int(request.form['id'])
        }
        mongo.db.projects.insert_one(project)
        flash('Project added successfully', 'success')
        return redirect(url_for('project_list'))
    return render_template('project_form.html', project=None)

@app.route('/project/edit/<project_id>', methods=['GET', 'POST'])
def edit_project(project_id):
    project = mongo.db.projects.find_one({"id": int(project_id)})
    if request.method == 'POST':
        updated_project = {
            "name": request.form['name'],
            "type": "Project",
            "id": int(request.form['id'])
        }
        mongo.db.projects.update_one({"id": int(project_id)}, {"$set": updated_project})
        flash('Project updated successfully', 'success')
        return redirect(url_for('project_list'))
    return render_template('project_form.html', project=project)

@app.route('/project/delete/<project_id>')
def delete_project(project_id):
    mongo.db.projects.delete_one({"id": int(project_id)})
    flash('Project deleted successfully', 'success')
    return redirect(url_for('project_list'))

@app.route('/users')
def user_list():
    search = request.args.get('search', '')
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10
    
    query = {}
    if search:
        query['$or'] = [
            {'firstname': {'$regex': search, '$options': 'i'}},
            {'lastname': {'$regex': search, '$options': 'i'}},
            {'email': {'$regex': search, '$options': 'i'}}
        ]
    
    offset = (page - 1) * per_page
    total = mongo.db.users.count_documents(query)
    users = mongo.db.users.find(query).skip(offset).limit(per_page)
    pagination = Pagination(page=page, total=total, per_page=per_page, css_framework='bootstrap4')
    
    return render_template('user_list.html', users=users, pagination=pagination, search=search)

@app.route('/user/add', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        user = {
            "sg_emp_id": request.form['sg_emp_id'],
            "firstname": request.form['firstname'],
            "lastname": request.form['lastname'],
            "email": request.form['email'],
            "department": {
                "type": "Department",
                "id": int(request.form['department_id']),
                "name": request.form['department_name']
            },
            "login": request.form['login'],
            "type": "HumanUser",
            "id": int(request.form['id'])
        }
        mongo.db.users.insert_one(user)
        flash('User added successfully', 'success')
        return redirect(url_for('user_list'))
    return render_template('user_form.html', user=None)

@app.route('/user/edit/<user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    user = mongo.db.users.find_one({"id": int(user_id)})
    if request.method == 'POST':
        updated_user = {
            "sg_emp_id": request.form['sg_emp_id'],
            "firstname": request.form['firstname'],
            "lastname": request.form['lastname'],
            "email": request.form['email'],
            "department": {
                "type": "Department",
                "id": int(request.form['department_id']),
                "name": request.form['department_name']
            },
            "login": request.form['login'],
            "type": "HumanUser",
            "id": int(request.form['id'])
        }
        mongo.db.users.update_one({"id": int(user_id)}, {"$set": updated_user})
        flash('User updated successfully', 'success')
        return redirect(url_for('user_list'))
    return render_template('user_form.html', user=user)

@app.route('/user/delete/<user_id>')
def delete_user(user_id):
    mongo.db.users.delete_one({"id": int(user_id)})
    flash('User deleted successfully', 'success')
    return redirect(url_for('user_list'))

def time_to_hours(time_str):
    match = re.match(r'(\d+):(\d+)', time_str)
    if match:
        hours, minutes = map(int, match.groups())
        return hours + minutes / 60
    return 0




@app.route('/time_entries')
def time_entries():
    search = request.args.get('search', '')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = {}
    if search:
        query['$or'] = [
            {'login': {'$regex': search, '$options': 'i'}},
            {'project': {'$elemMatch': {'$regex': search, '$options': 'i'}}}
        ]
    if start_date:
        query['date'] = {'$gte': datetime.strptime(start_date, '%Y-%m-%d')}
    if end_date:
        query['date'] = query.get('date', {})
        query['date']['$lte'] = datetime.strptime(end_date, '%Y-%m-%d')
    
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 10
    offset = (page - 1) * per_page
    total = mongo.db.time_data.count_documents(query)
    time_entries = mongo.db.time_data.find(query).skip(offset).limit(per_page)
    pagination = Pagination(page=page, total=total, per_page=per_page, css_framework='bootstrap4')
    
    return render_template('time_entries.html', time_entries=time_entries, pagination=pagination)


if __name__ == '__main__':
    app.run(debug=True)