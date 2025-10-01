from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from sqlalchemy import func

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    skills = db.relationship('Skill', backref='user', lazy=True)

class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    hours = db.Column(db.Integer, default=0)
    minutes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    @property
    def progress(self):
        total_minutes = self.hours * 60 + self.minutes
        return min(100, (total_minutes / (10000 * 60)) * 100)
    
    @property
    def total_time(self):
        return f"{self.hours}ч {self.minutes}м"

class SkillHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    hours_changed = db.Column(db.Integer, default=0)
    minutes_changed = db.Column(db.Integer, default=0)
    old_name = db.Column(db.String(100))
    new_name = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.now)

with app.app_context():
    db.create_all()
    print("Таблицы созданы!")

def check_user():
    user = User.query.get(session.get('user_id'))
    if not user:
        session.clear()
        return None
    return user

@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['user_id'] = user.id
            print(f"Пользователь {username} вошел в систему!")
            return redirect('/profile')
        else:
            print("Неверный логин или пароль!")
            return redirect('/login')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            print("Пользователь уже существует!")
            return redirect('/register')
        
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        print(f"Пользователь {username} зарегистрирован!")
        return redirect('/login')
    
    return render_template('register.html')

@app.route('/profile')
def profile():
    user = check_user()
    if not user:
        return redirect('/login')
    
    skills = user.skills
    return render_template('profile.html', skills=skills)

@app.route('/add-skill', methods=['POST'])
def add_skill():
    user = check_user()
    if not user:
        return redirect('/login')
    
    if len(user.skills) >= 5:
        print("Достигнут лимит в 5 навыков!")
        return redirect('/profile')
    
    skill_name = request.form['skill_name'].strip()
    
    existing_skill = Skill.query.filter(
        Skill.user_id == user.id,
        db.func.lower(Skill.name) == db.func.lower(skill_name)
    ).first()
    
    if existing_skill:
        print(f"Навык '{skill_name}' уже существует!")
    else:
        new_skill = Skill(name=skill_name, hours=0, minutes=0, user_id=user.id)
        db.session.add(new_skill)
        db.session.commit()
        print(f"Создан новый навык: '{skill_name}'")
    
    return redirect('/profile')

@app.route('/add-hours/<int:skill_id>', methods=['POST'])
def add_hours(skill_id):
    user = check_user()
    if not user:
        return redirect('/login')
    
    hours_to_add = int(request.form['hours'])
    minutes_to_add = int(request.form.get('minutes', 0))
    
    skill = Skill.query.filter_by(id=skill_id, user_id=user.id).first()
    
    if skill:
        history = SkillHistory(
            skill_id=skill_id,
            action='added',
            hours_changed=hours_to_add,
            minutes_changed=minutes_to_add,
            timestamp=datetime.now()
        )
        db.session.add(history)
        
        total_minutes_to_add = hours_to_add * 60 + minutes_to_add
        total_skill_minutes = skill.hours * 60 + skill.minutes + total_minutes_to_add
        skill.hours = total_skill_minutes // 60
        skill.minutes = total_skill_minutes % 60
        
        db.session.commit()
        print(f"+{hours_to_add}ч {minutes_to_add}м к навыку '{skill.name}'")
    
    return redirect('/profile')

@app.route('/remove-hours/<int:skill_id>', methods=['POST'])
def remove_hours(skill_id):
    user = check_user()
    if not user:
        return redirect('/login')
    
    hours_to_remove = int(request.form['hours'])
    skill = Skill.query.filter_by(id=skill_id, user_id=user.id).first()
    
    if skill:
        skill.hours = max(0, skill.hours - hours_to_remove)
        
        history = SkillHistory(
            skill_id=skill_id,
            action='removed',
            hours_changed=hours_to_remove,
            minutes_changed=0,
            timestamp=datetime.now()
        )
        db.session.add(history)
        
        db.session.commit()
        print(f"-{hours_to_remove} часов от навыка '{skill.name}'")
    
    return redirect('/profile')

@app.route('/edit-skill/<int:skill_id>', methods=['POST'])
def edit_skill(skill_id):
    user = check_user()
    if not user:
        return redirect('/login')
    
    new_name = request.form['new_name'].strip()
    skill = Skill.query.filter_by(id=skill_id, user_id=user.id).first()
    
    if skill:
        skill.name = new_name
        db.session.commit()
        print(f"Навык переименован в '{new_name}'")
    
    return redirect('/profile')

@app.route('/delete-skill/<int:skill_id>', methods=['POST'])
def delete_skill(skill_id):
    user = check_user()
    if not user:
        return redirect('/login')
    
    skill = Skill.query.filter_by(id=skill_id, user_id=user.id).first()
    
    if skill:
        db.session.delete(skill)
        db.session.commit()
        print(f"Навык '{skill.name}' удален")
    
    return redirect('/profile')

@app.route('/skill-history/<int:skill_id>')
def skill_history_months(skill_id):
    user = check_user()
    if not user:
        return redirect('/login')
    
    skill = Skill.query.filter_by(id=skill_id, user_id=user.id).first()
    if not skill:
        return redirect('/profile')
    
    month_data = db.session.query(
        func.to_char(SkillHistory.timestamp, 'YYYY-MM').label('month'),
        func.sum(SkillHistory.hours_changed).filter(SkillHistory.action == 'added').label('added_hours'),
        func.sum(SkillHistory.minutes_changed).filter(SkillHistory.action == 'added').label('added_minutes'),
        func.sum(SkillHistory.hours_changed).filter(SkillHistory.action == 'removed').label('removed_hours'),
        func.sum(SkillHistory.minutes_changed).filter(SkillHistory.action == 'removed').label('removed_minutes'),
        func.count().label('total')
    ).filter_by(skill_id=skill_id).group_by('month').order_by('month').all()
    
    months = []
    for m in month_data:
        dt = datetime.strptime(m.month, '%Y-%m')
        months.append({
            'key': m.month,
            'name': dt.strftime('%B %Y'),
            'added_hours': m.added_hours or 0,
            'added_minutes': m.added_minutes or 0,
            'removed_hours': m.removed_hours or 0,
            'removed_minutes': m.removed_minutes or 0,
            'total': m.total
        })
    
    return render_template('history_months.html', skill=skill, months=months)

@app.route('/skill-history/<int:skill_id>/<string:month>')
def skill_history_days(skill_id, month):
    user = check_user()
    if not user:
        return redirect('/login')
    
    skill = Skill.query.filter_by(id=skill_id, user_id=user.id).first()
    
    history = SkillHistory.query.filter(
        SkillHistory.skill_id == skill_id,
        func.to_char(SkillHistory.timestamp, 'YYYY-MM') == month
    ).order_by(SkillHistory.timestamp.desc()).all()
    
    return render_template('skill_history.html', skill=skill, history=history)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)