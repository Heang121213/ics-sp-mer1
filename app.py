from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import case, func
import pandas as pd
import json
import io
from io import BytesIO
import qrcode
import base64
import os
import socket
import re



app = Flask(__name__)
app.config['SECRET_KEY'] = 'ics_sp_cambodia_2026'

# បើបង្ហោះលើ Render ហើយមានប្រើ Postgres វានឹងយក DATABASE_URL មកប្រើ
# បើអត់ទេ វានឹងប្រើ SQLite ជាបណ្ដោះអាសន្ន
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///ics_management.db')
# កែប្រែ string 'postgres://' ទៅជា 'postgresql://' (ករណីប្រើ Render Postgres)
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ទុក LoginManager តែមួយកន្លែងនេះបានហើយ
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
# កំណត់ទីតាំងរក្សាទុករូបភាព
UPLOAD_FOLDER = 'static/uploads/profiles'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# បង្កើត Folder បើមិនទាន់មាន
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print("--- ពិនិត្យទីតាំង Folder ---")
print(f"ទីតាំងបច្ចុប្បន្ន (Current Dir): {os.getcwd()}")
print(f"តើមាន Folder 'templates' ដែរឬទេ? : {os.path.exists('templates')}")
if os.path.exists('templates'):
    print(f"ឯកសារក្នុង templates រួមមាន: {os.listdir('templates')}")
print("--------------------------")
# --- ១. Models (រចនាសម្ព័ន្ធទិន្នន័យ MER) ---
class Parent(db.Model):
    # កំណត់ ID តែមួយគត់ជា Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # ១. ព័ត៌មានមាតាបិតា
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    disability = db.Column(db.String(10))        # បាទ/ចាស ឬ ទេ
    disability_type = db.Column(db.String(100))
    role_in_family = db.Column(db.String(50))    # ឪពុក/ម្ដាយ/អាណាព្យាបាល
    job_title = db.Column(db.String(100))        # តួនាទី/មុខរបរ
    
    # ២. ព័ត៌មានភូមិសាស្ត្រ
    village = db.Column(db.String(100))
    commune = db.Column(db.String(100))
    district = db.Column(db.String(100))
    province = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    year_joined = db.Column(db.Integer)          # ឆ្នាំចូលរួម
    answers_json = db.Column(db.Text)
    # ៣. ទិន្នន័យកុមារក្នុងបន្ទុក (Own Children)
    # ០-៥ ឆ្នាំ
    c05_f_normal = db.Column(db.Integer, default=0)
    c05_f_disability = db.Column(db.Integer, default=0)
    c05_m_normal = db.Column(db.Integer, default=0)
    c05_m_disability = db.Column(db.Integer, default=0)
    # ៦-១២ ឆ្នាំ
    c612_f_normal = db.Column(db.Integer, default=0)
    c612_f_disability = db.Column(db.Integer, default=0)
    c612_m_normal = db.Column(db.Integer, default=0)
    c612_m_disability = db.Column(db.Integer, default=0)
    # ១៣-១៨ ឆ្នាំ
    c1318_f_normal = db.Column(db.Integer, default=0)
    c1318_f_disability = db.Column(db.Integer, default=0)
    c1318_m_normal = db.Column(db.Integer, default=0)
    c1318_m_disability = db.Column(db.Integer, default=0)

    # ៤. កុមារជាសាច់ញាតិក្នុងបន្ទុក (Relative Children)
    r05_f_normal = db.Column(db.Integer, default=0)
    r05_f_disability = db.Column(db.Integer, default=0)
    r05_m_normal = db.Column(db.Integer, default=0)
    r05_m_disability = db.Column(db.Integer, default=0)
    r612_f_normal = db.Column(db.Integer, default=0)
    r612_f_disability = db.Column(db.Integer, default=0)
    r612_m_normal = db.Column(db.Integer, default=0)
    r612_m_disability = db.Column(db.Integer, default=0)
    r1318_f_normal = db.Column(db.Integer, default=0)
    r1318_f_disability = db.Column(db.Integer, default=0)
    r1318_m_normal = db.Column(db.Integer, default=0)
    r1318_m_disability = db.Column(db.Integer, default=0)

    # ៥. ផ្នែកអ្នកសម្របសម្រួល និងពិន្ទុ
    fac_1 = db.Column(db.String(100))             # អ្នកសម្របសម្រួលទី ១
    fac_2 = db.Column(db.String(100))             # អ្នកសម្របសម្រួលទី ២
    fac_3 = db.Column(db.String(100))             # អ្នកសម្របសម្រួលទី ៣
    pre_score = db.Column(db.Integer, default=0)
    post_score = db.Column(db.Integer, default=0)
    # ៧. បន្ថែមមុខងារសម្រាប់ឆែកវត្តមាន (សម្រាប់ប្រើក្នុង home.html)
    def has_attended(self, step_number):
        """
        មុខងារឆែកមើលថា តើមាតាបិតាបានចូលរួមក្នុងជំហាននីមួយៗហើយឬនៅ
        ដោយពិនិត្យលើជួរ m1_date, m2_date, ... m8_date
        """
        # បង្កើតឈ្មោះ column តាមលេខ step (ឧទាហរណ៍ step 1 គឺ m1_date)
        column_name = f'm{step_number}_date'
        
        # ទាញយកតម្លៃពី column នោះ (getattr ប្រើសម្រាប់ទាញតម្លៃតាមរយៈឈ្មោះជា string)
        attendance_date = getattr(self, column_name, None)
        
        # បើមានកាលបរិច្ឆេទ (មិនមែន None) មានន័យថាបានចូលរួមហើយ
        return attendance_date is not None
    # ៦. កត់ត្រាវត្តមានតាមជំពូកទាំង ៨ នៃកម្រិត ២
    m1_date = db.Column(db.Date) # ជំហានទី១
    m2_date = db.Column(db.Date) # ជំហានទី២
    m3_date = db.Column(db.Date) # ជំហានទី៣
    m4_date = db.Column(db.Date) # ជំហានទី៤
    m5_date = db.Column(db.Date) # ជំហានទី៥
    m6_date = db.Column(db.Date) # ជំហានទី៦
    m7_date = db.Column(db.Date) # ជំហានទី៧
    m8_date = db.Column(db.Date) # ជំហានទី៨
    response_data = db.Column(db.Text, default='{}') # បន្ថែមជួរនេះ
    pre_test_score = db.Column(db.Integer, default=0) # បន្ថែមឱ្យត្រូវតាម route edit_parent
    post_test_score = db.Column(db.Integer, default=0) # បន្ថែមឱ្យត្រូវតាម route edit_parent
    # កូដថ្មីដែលត្រូវប្តូរ (ភ្ជាប់ទៅតារាង user):
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    quiz_results = db.relationship('QuizResult', backref='parent', cascade="all, delete-orphan", lazy=True)
class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parent.id'))
    parent_name = db.Column(db.String(100))
    village = db.Column(db.String(100))
    test_type = db.Column(db.String(10))
    score = db.Column(db.Integer)
    answers_json = db.Column(db.Text) # ជួរនេះសំខាន់បំផុតសម្រាប់ទុកចម្លើយ ១៦ សំណួរ
    date_taken = db.Column(db.DateTime, default=datetime.utcnow)
class QuizDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('quiz_result.id'))
    question_id = db.Column(db.Integer)
    selected_option = db.Column(db.Integer) # រក្សាទុកលេខសន្ទស្សន៍ 0, 1, 2, 3

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parent.id')) # ភ្ជាប់ទៅឈ្មោះមាតាបិតា
    step_number = db.Column(db.Integer) # លេខជំហាន (1-8)
    status = db.Column(db.String(10))   # វត្តមាន (Present/Absent)
    date = db.Column(db.Date)           # កាលបរិច្ឆេទចូលរួម

# 1. បង្កើត User Model (ត្រូវតែមាន UserMixin)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='Staff')
    full_name = db.Column(db.String(100))
# 2. កំណត់ Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value) if value else {}
    except:
        return {}
@login_manager.user_loader
def load_user(user_id):
    # ប្អូនត្រូវប្តូរ 'Admin' ទៅតាមឈ្មោះ Class ក្នុង Database របស់ប្អូន
    # វាជួយឱ្យ Flask ដឹងថាត្រូវទាញយក User តាមរយៈ ID
    return User.query.get(int(user_id))
ALL_QUESTIONS = [
    # ១. ការការពារកុមារ (Child Protection) [cite: 5]
    {
        "id": 1, "topic": "ការការពារកុមារ",
        "q": "តើកាតព្វកិច្ចរបស់ឪពុកម្តាយ ក្នុងការការពារកុមារមានអ្វីខ្លះ? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ធានាសុវត្ថិភាព និងសុខុមាលភាពរបស់កុមារ",
            "ខ) មិនអើពើការព្រួយបារម្ភរបស់កុមារ",
            "គ) កសាងទំនុកចិត្តជាមួយកុមារ",
            "ឃ) ជៀសវាងការពិភាគក្សាប្រធានបទលំបាកៗជាមួយកុមារ",
            "ង) បង្រៀនកុមារឱ្យទទួលស្គាល់ ពីស្ថានភាពដែលមិនមានសុវត្ថភាព"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 7]
    },
    {
        "id": 2, "topic": "ការការពារកុមារ",
        "q": "តើសញ្ញាអ្វីខ្លះដែលបង្ហាញថា កុមារត្រូវការការការពារ? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ការភ័យខ្លាចខ្លាំងពេច ចំពោះមនុស្សពេញវ័យមួយចំនួន",
            "ខ) កុមារចង់លេងជាមួយកុមារដទៃទៀត",
            "គ) របួសរាងកាយដែលមិនអាចពន្យល់បាន",
            "ឃ) បើកចំហ និងរីករាយចំពោះសកម្មភាពប្រចាំថ្ងៃ",
            "ង) កុមារគេចចេញពីមិត្តភក្តិ និងក្រុមគ្រួសារ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 11]
    },

    # ២. សុខុមាលភាពមាតាបិតា (Parental Well-being) [cite: 13]
    {
        "id": 3, "topic": "សុខុមាលភាពមាតាបិតា",
        "q": "តើការអនុវត្តអ្វីខ្លះដែលអាចធ្វើឱ្យប្រសើរសុខុមាលភាពឪពុកម្តាយ? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ចំណាយពេលសម្រាប់ថែខ្លូនទាំខ្លួនឯង",
            "ខ) មិនអើពើនឹងសញ្ញានៃភាពតានតឹង",
            "គ) ការកសាងបណ្ដាញគាំទ្រ",
            "ឃ) ជៀកវៀងការសម្រាកលំហែកាយផ្ទាល់ខ្លួនផ្សេងៗ",
            "ង) អនុវត្តបច្ចេកទេសដោះស្រាយភាពតានតឹង"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 15]
    },
    {
        "id": 4, "topic": "សុខុមាលភាពមាតាបិតា",
        "q": "តើមាតាបិតាអាចធ្វើអ្វីដើម្បីគ្រប់គ្រងភាពតានតឹងប្រកបដោយប្រសិទ្ធភាព? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) សម្រាក និងសម្រាកឱ្យបានទៀងទាត់",
            "ខ) រក្សាអារម្មណ៍ទាំងអស់ដែលលាក់កំបាំងពីអ្នកដ៏ទៃ",
            "គ) និយាយជាមួយមិត្តភក្តិ ឬក្រុមគ្រួសារសម្រាប់ការគាំទ្រ",
            "ឃ) បំបាត់ការខកចិត្តចំពោះកូនរបស់ពួកគេ",
            "ង) ចូលរួមក្នុងសកម្មភាពរីករាយ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 18]
    },

    # ៣. វិន័យវិជ្ជមាន (Positive Discipline) [cite: 20]
    {
        "id": 5, "topic": "វិន័យវិជ្ជមាន",
        "q": "តើអ្វីទៅជាវិធីសាស្ត្រដ៏មានប្រសិទ្ធភាព សម្រាប់ប្រៀនប្រដៅកូនបែបវិជ្ជមាន? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ពិភាក្សាពីអ្វីដែលខុស ហើយផ្តល់ការណែនាំដល់កុមារ",
            "ខ) ស្រែកគំហក ឬដាក់ទណ្ឌកម្មដោយគ្មានការពន្យល់",
            "គ) កំណត់ការរំពឹងទុកច្បាស់លាស់ ចំពោះអាកប្បកិរិយារបស់កុមារ",
            "ឃ) មិនអើពើនឹងអាកប្បកិរិយារកុមារទាំងស្រុង",
            "ង) ប្រាប់លទ្ធផលដែលនិងអាចកើតមាន (កូនរៀនកូនចេះ)"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 22]
    },
    {
        "id": 6, "topic": "វិន័យវិជ្ជមាន",
        "q": "តើមាតាបិតាអាចផ្តល់ភាពកក់ក្តៅ និងរចនាសម្ព័ន្ធក្នុងវិន័យយ៉ាងដូចម្តេច? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) បង្ហាញសេចក្តីស្រឡាញ់ក្នុងពេលកំណត់ព្រំដែន",
            "ខ) មិនអាចទាយទុកជាមុនបានជាមួយនឹងច្បាប់",
            "គ) ត្រូវម៉ត់ចត់ពីច្បាប់",
            "ឃ) ជៀសវៀងការបង្ហាញមនោសញ្ចេតនាណាមួយ",
            "ង) ផ្តល់ការសរសើរចំពោះអាកប្បកិរិយាល្អៗ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 25]
    },

    # ៤. ការទំនាក់ទំនងគ្រួសារ (Family Communication) [cite: 27]
    {
        "id": 7, "topic": "ការទំនាក់ទំនងគ្រួសារ",
        "q": "តើធាតុផ្សំសំខាន់ៗនៃទំនាក់ទំនងគ្រួសារប្រកបដោយប្រសិទ្ធភាពមានអ្វីខ្លះ? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ការសន្ទនាដោយបើកចំហចិត្ត",
            "ខ) ជៀសវាងបង្ករជម្លោះគ្រប់ទម្រង់",
            "គ) ការស្ដាប់ដោយយកចិត្តទុកដាក់",
            "ឃ) រក្សាការពិភាក្សាឱ្យតិចបំផុត",
            "ង) ការបង្ហាញការយល់បានស៊ីជម្រៅ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 29]
    },
    {
        "id": 8, "topic": "ការទំនាក់ទំនងគ្រួសារ",
        "q": "តើឪពុកម្តាយអាចប្រាស្រ័យទាក់ទងយ៉ាងមានប្រសិទ្ធភាពជាមួយកូនយ៉ាងដូចម្តេច? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ស្តាប់ដោយគ្មានការវិនិច្ឆ័យ",
            "ខ) បង្អាក់ជាញឹកញាប់ រាល់ពេលកុមារនិយាយ",
            "គ) សួរសំណួរបើកចំហ (ឆ្លើយបានក្បោះក្បោយ)",
            "ឃ) កែតម្រូវរាល់ព័ត៌មានលម្អិតភ្លាមៗ",
            "ង) ឆ្លើយតបទៅនឹងអារម្មណ៍របស់ពួកគេ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 32]
    },

    # ៥. រចនាប័ទ្មឪពុកម្តាយ (Parenting Styles) [cite: 34]
    {
        "id": 9, "topic": "រចនាប័ទ្មឪពុកម្តាយ",
        "q": "តើអ្វីទៅជាលក្ខណៈពិសេសនៃវិធីចិញ្ចឹមកូនបែបត្រជាក់ រចនាប័ទ្មមាតាបិតាដែលមានការអនុញ្ញាត? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ភាពកក់ក្តៅខ្ពស់ និងការរំពឹងទុកខ្ពស់",
            "ខ) អនុញ្ញាតឱ្យកុមារធ្វើការសម្រេចចិត្តទាំងអស់",
            "គ) ការលើកទឹកចិត្តឯករាជ្យ",
            "ឃ) ការប្រើវិធីសាស្ត្រគ្រប់គ្រងយ៉ាងតឹងរ៉ឹង",
            "ង) ផ្តល់ការណែនាំនៅពេលចាំបាច់"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 36]
    },
    {
        "id": 10, "topic": "រចនាប័ទ្មឪពុកម្តាយ",
        "q": "តើអ្វីទៅជាអត្ថប្រយោជន៍នៃរចនាប័ទ្មមាតាបិតាដែលមានការអនុញ្ញាត? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) លើកកម្ពស់ឯករាជ្យភាព (មិនពឹងផ្អែក)",
            "ខ) ធ្វើឱ្យមានការភ័យខ្លាចនៃអំណាចគ្រប់គ្រង",
            "គ) កសាងទំនុកចិត្តលើខ្លួនឯង",
            "ឃ) នាំឱ្យកុមារមានភាពច្របូកច្របស់",
            "ង) លើកទឹកចិត្តឱ្យមានការទទួលខុសត្រូវ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 39]
    },
    {
        "id": 11, "topic": "រចនាប័ទ្មឪពុកម្តាយ",
        "q": "តើអ្វីទៅជាលក្ខណៈរចនាប័ទ្មមាតាបិតាបែបបណ្តោយ (Permissive)? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) អនុញ្ញាតឱ្យកុមារកំណត់ភាគច្រើននៃដែនកំណត់ផ្ទាល់ខ្លួន",
            "ខ) ការកំណត់ដែនកំណត់ដែលមិនប្រែប្រួល",
            "គ) កម្រអនុវត្តច្បាប់",
            "ឃ) មិនអើពើនឹងតម្រូវការរបស់កុមារ",
            "ង) ផ្តល់ការគាំទ្រដោយគ្មានការណែនាំ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 42]
    },

    # ៦. តួនាទី និងទំនួលខុសត្រូវ (Roles & Responsibilities) [cite: 44]
    {
        "id": 12, "topic": "តួនាទី និងទំនួលខុសត្រូវ",
        "q": "តើឪពុកម្តាយមានទំនួលខុសត្រូវអ្វីខ្លះ ក្នុងការចិញ្ចឹមកូន? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ផ្តល់ការណែនាំ និងការគាំទ្រ",
            "ខ) អនុញ្ញាតឱ្យមានឯករាជ្យពេញលេញ",
            "គ) បង្រៀនបំនិនជីវិត",
            "ឃ) មិនអើពើនឹងអាកប្បកិរិយាមិនសមរម្យ",
            "ង) លើកទឹកចិត្តឱ្យមានអាកប្បកិរិយាល្អ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 46]
    },
    {
        "id": 13, "topic": "តួនាទី និងទំនួលខុសត្រូវ",
        "q": "តើកុមារមានតួនាទីអ្វីខ្លះនៅក្នុងគ្រួសារ? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ចូលរួមចំណែកដល់ជីវិតគ្រួសារ",
            "ខ) ដោះស្រាយរាល់ការសម្រេចចិត្តតែម្នាក់ឯង",
            "គ) ទទួលភារកិច្ចសមស្របតាមអាយុរបស់កុមារ",
            "ឃ) ស្តាប់បង្គាប់ដោយគ្មានសំណួរអ្វីទាំងអស់",
            "ង) កសាងទំនួលខុសត្រូវរបស់ខ្លូនបន្តិចម្តងៗ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 49]
    },

    # ៧. សំណួរទូទៅ (General Questions) [cite: 51]
    {
        "id": 14, "topic": "សំណួរទូទៅ",
        "q": "តើអ្វីជាគោលដៅចម្បងនៃការចិញ្ចឹមកូនដោយវិជ្ជមាន? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) លើកទឹកចិត្តឱ្យមានស្វ័យភាពជាមួយកុមារ",
            "ខ) ផ្តោតលើតែការស្តាប់បង្គាប់របស់ពួកគេ",
            "គ) អភិវឌ្ឍទំនួលខុសត្រូវ",
            "ឃ) គ្រប់គ្រងរាល់សកម្មភាពរបស់ពួកគេ",
            "ង) កសាងទំនុកចិត្តលើខ្លួនឯង និងសុខុមាលភាព"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 53]
    },
    {
        "id": 15, "topic": "សំណួរទូទៅ",
        "q": "តើការប្រាស្រ័យទាក់ទងក្នុងគ្រួសារមានឥទ្ធិពលយ៉ាងណាទៅលើការវិវឌ្ឍន៍ផ្លូវចិត្តរបស់កុមារ? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) ជួយពួកគេបញ្ចេញពីអារម្មណ៍បានពេញលេញ",
            "ខ) ធ្វើឱ្យមានភាពតានតឹង បើអនុវត្តញឹកញាប់ពេក",
            "គ) បង្កើតឱ្យមានការយល់ដឹងដោយខ្លួនឯងកាន់តែច្បាស់",
            "ឃ) បង្រៀនពួកគេឱ្យលាក់អារម្មណ៍ខ្លួនឯង",
            "ង) បង្កើតអារម្មណ៍សុវត្ថិភាព"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 56]
    },
    {
        "id": 16, "topic": "សំណួរទូទៅ",
        "q": "តើការយល់ដឹងពីអារម្មណ៍ និងគំនិតរបស់កុមារមានប្រយោជន៍អ្វីខ្លះ? (ចម្លើយលើសពី ១)",
        "options": [
            "ក) បង្កើតការជឿទុកចិត្ត",
            "ខ) ធ្វើឱ្យមានការគ្រប់គ្រងយ៉ាងតឹងរ៉ឹងលើអាកប្បកិរិយា",
            "គ) លើកទឹកចិត្តឱ្យមានការបើកចំហគ្រប់បញ្ហា",
            "ឃ) ធានាការគោរពប្រតិបត្តិដោយគ្មានការពិភាក្សា",
            "ង) ជំរុញការលូតលាស់ផ្លូវចិត្តដែលមានសុខភាពល្អ"
        ],
        "correct": [0, 2, 4] # ក, គ, ង [cite: 59]
    }
]
def get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # ភ្ជាប់ទៅកាន់ DNS របស់ Google ដើម្បីដឹងពី IP របស់ Laptop ក្នុង WiFi
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1' # បើអត់មានអ៊ីនធឺណិត ប្រើ Localhost
    finally:
        s.close()
    return ip

@app.route('/lessons')
def parenting_lessons():
    # ឥឡូវនេះ Flask នឹងស្គាល់ ALL_QUESTIONS ដែលនៅខាងលើរួចជាស្រេច
    return render_template('lessons.html', questions=ALL_QUESTIONS)
# --- ៤. Routes (ដោះស្រាយ BuildError និង 404 Not Found) ---

@app.route('/quiz_pre/<int:parent_id>')
@login_required
def quiz_pre(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    
    # 🎯 បញ្ជីសំណួរផ្លូវការទាំង ១៦ សម្រាប់ Skillful Parenting (Level 2) 
    QUESTIONS_LIST = [
        # --- ១. ការការពារកុមារ [cite: 5] ---
        {
            'id': 1, 
            'q_kh': 'តើកាតព្វកិច្ចរបស់ឪពុកម្តាយ ក្នុងការការពារកុមារមានអ្វីខ្លះ?', 
            'q_en': 'What are the duties of parents in child protection?', 
            'q_zh': '父母在保护儿童方面的职责是什么？',
            'options': [
                {'kh': 'ក) ធានាសុវត្ថិភាព និងសុខុមាលភាពរបស់កុមារ', 'en': 'a) Ensure safety and well-being', 'zh': 'a) 确保安全与福祉', 'is_correct': '1'}, # [cite: 7]
                {'kh': 'ខ) មិនអើពើការព្រួយបារម្ភរបស់កុមារ', 'en': 'b) Ignore child concerns', 'zh': 'b) 忽视孩子的担忧', 'is_correct': '0'}, # [cite: 8]
                {'kh': 'គ) កសាងទំនុកចិត្តជាមួយកុមារ', 'en': 'c) Build trust with children', 'zh': 'c) 与孩子建立信任', 'is_correct': '1'}, # [cite: 7]
                {'kh': 'ឃ) ជៀសវាងការពិភាគក្សាប្រធានបទលំបាកៗ', 'en': 'd) Avoid discussing difficult topics', 'zh': 'd) 避免讨论困难话题', 'is_correct': '1'}, # [cite: 7]
                {'kh': 'ង) បង្រៀនឱ្យស្គាល់ស្ថានភាពមិនសុវត្ថភាព', 'en': 'e) Teach to recognize unsafe situations', 'zh': 'e) 教导识别不安全情况', 'is_correct': '0'} # [cite: 8]
            ]
        },
        {
            'id': 2, 
            'q_kh': 'តើសញ្ញាអ្វីខ្លះដែលបង្ហាញថា កុមារត្រូវការការការពារ?', 
            'q_en': 'What signs indicate a child needs protection?', 
            'q_zh': '哪些迹象表明儿童需要保护？',
            'options': [
                {'kh': 'ក) ការភ័យខ្លាចខ្លាំងពេច ចំពោះមនុស្សពេញវ័យ', 'en': 'a) Extreme fear of adults', 'zh': 'a) 对成年人极度恐惧', 'is_correct': '1'}, # [cite: 10]
                {'kh': 'ខ) កុមារចង់លេងជាមួយកុមារដទៃទៀត', 'en': 'b) Want to play with others', 'zh': 'b) 想和其他孩子玩', 'is_correct': '0'}, # [cite: 12]
                {'kh': 'គ) របួសរាងកាយដែលមិនអាចពន្យល់បាន', 'en': 'c) Unexplained physical injuries', 'zh': 'c) 不明原因的身体受伤', 'is_correct': '1'}, # [cite: 11]
                {'kh': 'ឃ) បើកចំហ និងរីករាយប្រចាំថ្ងៃ', 'en': 'd) Open and happy daily', 'zh': 'd) 日常开朗愉快', 'is_correct': '0'}, # [cite: 12]
                {'kh': 'ង) កុមារគេចចេញពីមិត្តភក្តិ និងក្រុមគ្រួសារ', 'en': 'e) Withdraw from friends and family', 'zh': 'e) 疏离朋友和家人', 'is_correct': '1'} # [cite: 11]
            ]
        },

        # --- ២. សុខុមាលភាពមាតាបិតា [cite: 13] ---
        {
            'id': 3, 
            'q_kh': 'តើការអនុវត្តអ្វីខ្លះដែលនាំឱ្យប្រសើរសុខុមាលភាពឪពុកម្តាយ?', 
            'q_en': 'What practices improve parental well-being?', 
            'q_zh': '哪些做法可以改善父母的福祉？',
            'options': [
                {'kh': 'ក) ចំណាយពេលសម្រាប់ថែខ្លួនទាំខ្លួនឯង', 'en': 'a) Spend time for self-care', 'zh': 'a) 花时间自我护理', 'is_correct': '1'}, # [cite: 15]
                {'kh': 'ខ) មិនអើពើនឹងសញ្ញានៃភាពតានតឹង', 'en': 'b) Ignore signs of stress', 'zh': 'b) 忽视压力迹象', 'is_correct': '0'}, # [cite: 16]
                {'kh': 'គ) ការកសាងបណ្ដាញគាំទ្រ', 'en': 'c) Building support networks', 'zh': 'c) 建立支持网络', 'is_correct': '1'}, # [cite: 15]
                {'kh': 'ឃ) ជៀសវាងការសម្រាកផ្ទាល់ខ្លួនណាមួយ', 'en': 'd) Avoid any personal rest', 'zh': 'd) 避免任何个人休息', 'is_correct': '0'}, # [cite: 16]
                {'kh': 'ង) អនុវត្តបច្ចេកទេសដោះស្រាយភាពតានតឹង', 'en': 'e) Practice stress management', 'zh': 'e) 练习压力管理', 'is_correct': '1'} # [cite: 15]
            ]
        },
        {
            'id': 4, 
            'q_kh': 'តើឪពុកម្តាយធ្វើអ្វី ដើម្បីគ្រប់គ្រងភាពតានតឹងឱ្យបានល្អ?', 
            'q_en': 'What can parents do to manage stress effectively?', 
            'q_zh': '父母如何有效地管理压力？',
            'options': [
                {'kh': 'ក) សម្រាក និងសម្រាកឱ្យបានទៀងទាត់', 'en': 'a) Rest and relax regularly', 'zh': 'a) 定期休息和放松', 'is_correct': '1'}, # [cite: 18]
                {'kh': 'ខ) លាក់បាំងអារម្មណ៍ពីអ្នកដទៃ', 'en': 'b) Hide feelings from others', 'zh': 'b) 向他人隐藏感情', 'is_correct': '0'}, # [cite: 19]
                {'kh': 'គ) និយាយជាមួយមិត្តភក្តិ ឬគ្រួសារដើម្បីគាំទ្រ', 'en': 'c) Talk to friends or family for support', 'zh': 'c) 与朋友或家人谈心寻求支持', 'is_correct': '1'}, # [cite: 18]
                {'kh': 'ឃ) បំបាត់ការខកចិត្តចំពោះកូន', 'en': 'd) Vent frustration on children', 'zh': 'd) 向孩子发泄不满', 'is_correct': '0'}, # [cite: 19]
                {'kh': 'ង) ចូលរួមក្នុងសកម្មភាពរីករាយ', 'en': 'e) Join fun activities', 'zh': 'e) 参加有趣的活动', 'is_correct': '1'} # [cite: 18]
            ]
        },

        # --- ៣. វិន័យវិជ្ជមាន [cite: 20] ---
        {
            'id': 5, 
            'q_kh': 'តើអ្វីទៅជាយុទ្ធសាស្ត្រដ៏មានប្រសិទ្ធភាពសម្រាប់វិន័យវិជ្ជមាន?', 
            'q_en': 'What is an effective strategy for positive discipline?', 
            'q_zh': '什么是积极管教的有效策略？',
            'options': [
                {'kh': 'ក) ពិភាក្សាអ្វីដែលខុស ហើយផ្តល់ការណែនាំ', 'en': 'a) Discuss wrongs and guide', 'zh': 'a) 讨论错误并指导', 'is_correct': '1'}, # [cite: 22]
                {'kh': 'ខ) ស្រែកឬដាក់ទណ្ឌកម្មគ្មានការពន្យល់', 'en': 'b) Shout/punish without explanation', 'zh': 'b) 无解释地喊叫/惩罚', 'is_correct': '0'}, # [cite: 23]
                {'kh': 'គ) កំណត់ការរំពឹងទុកច្បាស់លាស់', 'en': 'c) Set clear expectations', 'zh': 'c) 设定明确期望', 'is_correct': '1'}, # [cite: 22]
                {'kh': 'ឃ) មិនអើពើនឹងអាកប្បកិរិយាទាំងស្រុង', 'en': 'd) Ignore behavior entirely', 'zh': 'd) 完全忽视行为', 'is_correct': '0'}, # [cite: 23]
                {'kh': 'ង) ប្រាប់លទ្ធផលដែលនឹងអាចកើតមាន', 'en': 'e) Tell potential outcomes', 'zh': 'e) 告知潜在结果', 'is_correct': '1'} # [cite: 22]
            ]
        },
        {
            'id': 6, 
            'q_kh': 'តើមាតាបិតាផ្តល់ភាពកក់ក្តៅ និងរចនាសម្ព័ន្ធក្នុងវិន័យយ៉ាងដូចម្តេច?', 
            'q_en': 'How can parents provide warmth and structure?', 
            'q_zh': '父母如何提供温暖和结构？',
            'options': [
                {'kh': 'ក) បង្ហាញសេចក្តីស្រឡាញ់ក្នុងពេលកំណត់ព្រំដែន', 'en': 'a) Show love while setting limits', 'zh': 'a) 在设定界限时展现爱', 'is_correct': '1'}, # [cite: 25]
                {'kh': 'ខ) មិនអាចទាយទុកជាមុនបានជាមួយច្បាប់', 'en': 'b) Unpredictable with rules', 'zh': 'b) 规则不可预测', 'is_correct': '0'}, # [cite: 26]
                {'kh': 'គ) ត្រូវច្បាស់លាស់អំពីច្បាប់', 'en': 'c) Be clear about rules', 'zh': 'c) 明确规则', 'is_correct': '1'}, # [cite: 25]
                {'kh': 'ឃ) ជៀសវាងការបង្ហាញអារម្មណ៍ណាមួយ', 'en': 'd) Avoid showing any emotion', 'zh': 'd) 避免表现任何情感', 'is_correct': '0'}, # [cite: 26]
                {'kh': 'ង) ផ្តល់ការសរសើរចំពោះអាកប្បកិរិយាល្អ', 'en': 'e) Praise good behavior', 'zh': 'e) 表扬良好行为', 'is_correct': '1'} # [cite: 25]
            ]
        },

        # --- ៤. ការទំនាក់ទំនងគ្រួសារ [cite: 27] ---
        {
            'id': 7, 
            'q_kh': 'តើធាតុផ្សំសំខាន់ៗនៃទំនាក់ទំនងគ្រួសារមានអ្វីខ្លះ?', 
            'q_en': 'What are the key elements of family communication?', 
            'q_zh': '家庭沟通的关键要素是什么？',
            'options': [
                {'kh': 'ក) បើកការសន្ទនាដោយចំហចិត្ត', 'en': 'a) Open conversation', 'zh': 'a) 坦诚对话', 'is_correct': '1'}, # [cite: 29]
                {'kh': 'ខ) ជៀសវាងទម្រង់នៃជម្លោះគ្រប់ប្រភេទ', 'en': 'b) Avoid all forms of conflict', 'zh': 'b) 避免所有形式的冲突', 'is_correct': '0'}, # [cite: 30]
                {'kh': 'គ) ការស្តាប់ដោយយកចិត្តទុកដាក់ (Active listening)', 'en': 'c) Active listening', 'zh': 'c) 积极倾听', 'is_correct': '1'}, # [cite: 29]
                {'kh': 'ឃ) រក្សាការពិភាក្សាឱ្យតិចបំផុត', 'en': 'd) Keep discussions minimal', 'zh': 'd) 保持最少讨论', 'is_correct': '0'}, # [cite: 30]
                {'kh': 'ង) ការបង្ហាញការយល់ដឹងស៊ីជម្រៅ', 'en': 'e) Showing understanding', 'zh': 'e) 表现出理解', 'is_correct': '1'} # [cite: 29]
            ]
        },
        {
            'id': 8, 
            'q_kh': 'តើឪពុកម្តាយអាចប្រាស្រ័យទាក់ទងមានប្រសិទ្ធភាពជាមួយកូនដូចម្តេច?', 
            'q_en': 'How can parents communicate effectively with children?', 
            'q_zh': '父母如何有效地与孩子沟通？',
            'options': [
                {'kh': 'ក) ស្តាប់ដោយគ្មានការវិនិច្ឆ័យ', 'en': 'a) Listen without judgment', 'zh': 'a) 无偏见地倾听', 'is_correct': '1'}, # [cite: 32]
                {'kh': 'ខ) រំខានជាញឹកញាប់ពេលកូននិយាយ', 'en': 'b) Interrupt often', 'zh': 'b) 经常打断', 'is_correct': '0'}, # [cite: 33]
                {'kh': 'គ) សួរសំណួរបើកចំហ (Open-ended questions)', 'en': 'c) Ask open-ended questions', 'zh': 'c) 提出开放式问题', 'is_correct': '1'}, # [cite: 32]
                {'kh': 'ឃ) កែតម្រូវរាល់ព័ត៌មានលម្អិតភ្លាមៗ', 'en': 'd) Correct every detail immediately', 'zh': 'd) 立即纠正每个细节', 'is_correct': '0'}, # [cite: 33]
                {'kh': 'ង) ឆ្លើយតបទៅនឹងអារម្មណ៍របស់ពួកគេ', 'en': 'e) Respond to their feelings', 'zh': 'e) 回应他们的感受', 'is_correct': '1'} # [cite: 32]
            ]
        },

        # --- ៥. រចនាប័ទ្មឪពុកម្តាយ [cite: 34] ---
        {
            'id': 9, 
            'q_kh': 'តើលក្ខណៈពិសេសនៃរចនាប័ទ្មមាតាបិតាដែលមានការអនុញ្ញាត (Authoritative)?', 
            'q_en': 'Features of Authoritative parenting style?', 
            'q_zh': '权威型教养方式的特点？',
            'options': [
                {'kh': 'ក) ភាពកក់ក្តៅ និងការរំពឹងទុកខ្ពស់', 'en': 'a) High warmth and expectations', 'zh': 'a) 高温暖和高期望', 'is_correct': '1'}, # [cite: 36]
                {'kh': 'ខ) អនុញ្ញាតឱ្យកុមារសម្រេចចិត្តទាំងអស់', 'en': 'b) Let child make all decisions', 'zh': 'b) 让孩子做所有决定', 'is_correct': '0'}, # [cite: 37]
                {'kh': 'គ) ការលើកទឹកចិត្តឯករាជ្យ', 'en': 'c) Encourage independence', 'zh': 'c) 鼓励独立', 'is_correct': '1'}, # [cite: 36]
                {'kh': 'ឃ) ការប្រើវិធីគ្រប់គ្រងយ៉ាងតឹងរ៉ឹង', 'en': 'd) Use strict control methods', 'zh': 'd) 使用严格的控制方法', 'is_correct': '0'}, # [cite: 37]
                {'kh': 'ង) ផ្តល់ការណែនាំនៅពេលចាំបាច់', 'en': 'e) Provide guidance when needed', 'zh': 'e) 必要时提供指导', 'is_correct': '1'} # [cite: 36]
            ]
        },
        {
            'id': 10, 
            'q_kh': 'តើអ្វីទៅជាអត្ថប្រយោជន៍នៃរចនាប័ទ្មមាតាបិតាដែលមានការអនុញ្ញាត?', 
            'q_en': 'What are the benefits of authoritative parenting?', 
            'q_zh': '权威型教养方式有什么好处？',
            'options': [
                {'kh': 'ក) លើកកម្ពស់ឯករាជ្យភាព (មិនពឹងផ្អែក)', 'en': 'a) Promote independence', 'zh': 'a) 促进独立', 'is_correct': '1'}, # [cite: 39]
                {'kh': 'ខ) ធ្វើឱ្យមានការភ័យខ្លាចនៃអំណាចគ្រប់គ្រង', 'en': 'b) Create fear of authority', 'zh': 'b) 对权力的恐惧', 'is_correct': '0'}, # [cite: 40]
                {'kh': 'គ) កសាងទំនុកចិត្តលើខ្លួនឯង', 'en': 'c) Build self-confidence', 'zh': 'c) 建立自信心', 'is_correct': '1'}, # [cite: 39]
                {'kh': 'ឃ) នាំឱ្យកុមារមានភាពច្របូកច្របស់', 'en': 'd) Lead to confusion', 'zh': 'd) 导致混乱', 'is_correct': '0'}, # [cite: 40]
                {'kh': 'ង) លើកទឹកចិត្តឱ្យមានការទទួលខុសត្រូវ', 'en': 'e) Encourage responsibility', 'zh': 'e) 鼓励责任感', 'is_correct': '1'} # [cite: 39]
            ]
        },
        {
            'id': 11, 
            'q_kh': 'តើលក្ខណៈរចនាប័ទ្មមាតាបិតាបែបបណ្តោយ (Permissive) មានអ្វីខ្លះ?', 
            'q_en': 'What are the features of Permissive parenting?', 
            'q_zh': '放任型教养方式有哪些特点？',
            'options': [
                {'kh': 'ក) អនុញ្ញាតឱ្យកូនកំណត់ដែនកំណត់ផ្ទាល់ខ្លួនភាគច្រើន', 'en': 'a) Let child set most limits', 'zh': 'a) 让孩子设定大部分界限', 'is_correct': '1'}, # [cite: 42]
                {'kh': 'ខ) ការកំណត់ព្រំដែនជាប់លាប់', 'en': 'b) Consistent boundaries', 'zh': 'b) 一致的边界', 'is_correct': '0'}, # [cite: 43]
                {'kh': 'គ) កម្រនឹងអនុវត្តច្បាប់', 'en': 'c) Rarely enforce rules', 'zh': 'c) 很少执行规则', 'is_correct': '1'}, # [cite: 42]
                {'kh': 'ឃ) មិនអើពើនឹងតម្រូវការរបស់កុមារ', 'en': 'd) Ignore child needs', 'zh': 'd) 忽视孩子的需求', 'is_correct': '0'}, # [cite: 43]
                {'kh': 'ង) ផ្តល់ជំនួយដោយគ្មានការណែនាំ', 'en': 'e) Provide help without guidance', 'zh': 'e) 无指导地提供帮助', 'is_correct': '1'} # [cite: 42]
            ]
        },

        # --- ៦. តួនាទី និងទំនួលខុសត្រូវ [cite: 44] ---
        {
            'id': 12, 
            'q_kh': 'តើឪពុកម្តាយមានទំនួលខុសត្រូវអ្វីខ្លះ ក្នុងការចិញ្ចឹមកូន?', 
            'q_en': 'What responsibilities do parents have?', 
            'q_zh': '父母有哪些责任？',
            'options': [
                {'kh': 'ក) ផ្តល់ការណែនាំ និងការគាំទ្រ', 'en': 'a) Provide guidance and support', 'zh': 'a) 提供指导和支持', 'is_correct': '1'}, # [cite: 46]
                {'kh': 'ខ) អនុញ្ញាតឱ្យមានឯករាជ្យពេញលេញ', 'en': 'b) Allow complete independence', 'zh': 'b) 允许完全独立', 'is_correct': '0'}, # [cite: 47]
                {'kh': 'គ) បង្រៀនជំនាញជីវិត (Life Skills)', 'en': 'c) Teach life skills', 'zh': 'c) 教授生活技能', 'is_correct': '1'}, # [cite: 46]
                {'kh': 'ឃ) មិនអើពើអាកប្បកិរិយាមិនសមរម្យ', 'en': 'd) Ignore inappropriate behavior', 'zh': 'd) 忽视不当行为', 'is_correct': '0'}, # [cite: 47]
                {'kh': 'ង) លើកទឹកចិត្តអាកប្បកិរិយាល្អ', 'en': 'e) Encourage good behavior', 'zh': 'e) 鼓励良好行为', 'is_correct': '1'} # [cite: 46]
            ]
        },
        {
            'id': 13, 
            'q_kh': 'តើកុមារមានតួនាទីអ្វីខ្លះនៅក្នុងគ្រួសារ?', 
            'q_en': 'What are the roles of children in the family?', 
            'q_zh': '孩子在家庭中扮演什么角色？',
            'options': [
                {'kh': 'ក) ចូលរួមចំណែកក្នុងជីវភាពគ្រួសារ', 'en': 'a) Contribute to family life', 'zh': 'a) 为家庭生活做贡献', 'is_correct': '1'}, # [cite: 49]
                {'kh': 'ខ) ដោះស្រាយការសម្រេចចិត្តតែម្នាក់ឯង', 'en': 'b) Handle decisions alone', 'zh': 'b) 独自处理决定', 'is_correct': '0'}, # [cite: 50]
                {'kh': 'គ) ទទួលភារកិច្ចតាមអាយុ (Age-appropriate tasks)', 'en': 'c) Age-appropriate tasks', 'zh': 'c) 与年龄相符的任务', 'is_correct': '1'}, # [cite: 49]
                {'kh': 'ឃ) ស្តាប់បង្គាប់គ្មានសំណួរអ្វីទាំងអស់', 'en': 'd) Obey without questions', 'zh': 'd) 毫无疑问地服从', 'is_correct': '0'}, # [cite: 50]
                {'kh': 'ង) កសាងទំនួលខុសត្រូវបន្តិចម្តងៗ', 'en': 'e) Build responsibility gradually', 'zh': 'e) 逐渐建立责任感', 'is_correct': '1'} # [cite: 49]
            ]
        },

        # --- ៧. សំណួរទូទៅ [cite: 51] ---
        {
            'id': 14, 
            'q_kh': 'តើអ្វីជាគោលដៅចម្បងនៃការចិញ្ចឹមកូនដោយវិជ្ជមាន?', 
            'q_en': 'What is the main goal of positive parenting?', 
            'q_zh': '积极教养的主要目标是什么？',
            'options': [
                {'kh': 'ក) លើកទឹកចិត្តឱ្យមានស្វ័យភាពកុមារ', 'en': 'a) Encourage child autonomy', 'zh': 'a) 鼓励儿童自主', 'is_correct': '1'}, # [cite: 53]
                {'kh': 'ខ) ផ្តោតតែលើការស្តាប់បង្គាប់', 'en': 'b) Focus only on obedience', 'zh': 'b) 仅专注于服从', 'is_correct': '0'}, # [cite: 54]
                {'kh': 'គ) អភិវឌ្ឍទំនួលខុសត្រូវ', 'en': 'c) Develop responsibility', 'zh': 'c) 培养责任感', 'is_correct': '1'}, # [cite: 53]
                {'kh': 'ឃ) គ្រប់គ្រងរាល់សកម្មភាពរបស់ពួកគេ', 'en': 'd) Control all activities', 'zh': 'd) 控制所有活动', 'is_correct': '0'}, # [cite: 54]
                {'kh': 'ង) កសាងទំនុកចិត្ត និងសុខុមាលភាព', 'en': 'e) Build confidence and well-being', 'zh': 'e) 建立信心和福祉', 'is_correct': '1'} # [cite: 53]
            ]
        },
        {
            'id': 15, 
            'q_kh': 'តើការប្រាស្រ័យទាក់ទងគ្រួសារមានឥទ្ធិពលយ៉ាងណាលើការវិវឌ្ឍន៍ផ្លូវចិត្តកុមារ?', 
            'q_en': 'How does family communication affect child mental development?', 
            'q_zh': '家庭沟通如何影响儿童的心理发育？',
            'options': [
                {'kh': 'ក) ជួយពួកគេបញ្ចេញពីអារម្មណ៍បានពេញលេញ', 'en': 'a) Help them express feelings', 'zh': 'a) 帮助他们表达情感', 'is_correct': '1'}, # [cite: 56]
                {'kh': 'ខ) ធ្វើឱ្យមានភាពតានតឹង បើអនុវត្តញឹកញាប់ពេក', 'en': 'b) Cause stress if practiced too often', 'zh': 'b) 如果练习过于频繁会导致压力', 'is_correct': '0'}, # [cite: 57]
                {'kh': 'គ) បង្កើតឱ្យមានការយល់ដឹងដោយខ្លួនឯងច្បាស់', 'en': 'c) Create clearer self-understanding', 'zh': 'c) 建立更清晰的自我认识', 'is_correct': '1'}, # [cite: 56]
                {'kh': 'ឃ) បង្រៀនពួកគេឱ្យលាក់អារម្មណ៍ខ្លួនឯង', 'en': 'd) Teach them to hide emotions', 'zh': 'd) 教导他们隐藏情绪', 'is_correct': '0'}, # [cite: 57]
                {'kh': 'ង) បង្កើតអារម្មណ៍សុវត្ថិភាព', 'en': 'e) Create a sense of security', 'zh': 'e) 建立安全感', 'is_correct': '1'} # [cite: 56]
            ]
        },
        {
            'id': 16, 
            'q_kh': 'តើការយល់ដឹងពីអារម្មណ៍ និងគំនិតកុមារមានប្រយោជន៍អ្វី?', 
            'q_en': 'Benefit of understanding child thoughts/feelings?', 
            'q_zh': '理解孩子想法/感受的好处？',
            'options': [
                {'kh': 'ក) បង្កើតការជឿទុកចិត្ត (Trust)', 'en': 'a) Build trust', 'zh': 'a) 建立信任', 'is_correct': '1'}, # [cite: 59]
                {'kh': 'ខ) អនុញ្ញាតឱ្យគ្រប់គ្រងតឹងរ៉ឹងលើអាកប្បកិរិយា', 'en': 'b) Allow strict behavior control', 'zh': 'b) 允许严格的行为控制', 'is_correct': '0'}, # [cite: 60]
                {'kh': 'គ) លើកទឹកចិត្តឱ្យបើកចំហរគ្រប់បញ្ហា', 'en': 'c) Encourage openness on all issues', 'zh': 'c) 鼓励对所有问题的开放性', 'is_correct': '1'}, # [cite: 59]
                {'kh': 'ឃ) ធានាការគោរពប្រតិបត្តិគ្មានការពិភាក្សា', 'en': 'd) Ensure obedience without discussion', 'zh': 'd) 确保无讨论的服从', 'is_correct': '0'}, # [cite: 60]
                {'kh': 'ង) ជំរុញការលូតលាស់ផ្លូវចិត្តសុខភាពល្អ', 'en': 'e) Promote healthy mental growth', 'zh': 'e) 促进心理健康成长', 'is_correct': '1'} # [cite: 59]
            ]
        }
    ]

    saved_answers = {}
    if parent.answers_json:
        try:
            saved_answers = json.loads(parent.answers_json)
        except: 
            saved_answers = {}

    return render_template('quiz_pre.html', parent=parent, questions=QUESTIONS_LIST, saved_answers=saved_answers)
@app.route('/take_test/<test_type>/<int:parent_id>', methods=['POST'])
@login_required
def take_test(test_type, parent_id):
    parent = Parent.query.get_or_404(parent_id)
    
    # ចាប់យកទិន្នន័យពី Hidden Inputs
    score = request.form.get('total_score', 0)
    ans_json = request.form.get('answers_json')

    if test_type == 'pre':
        parent.pre_score = float(score)
        parent.answers_json = ans_json # 🔥 រក្សាទុកចម្លើយ JSON (ក ខ គ ឃ ង)
    
    db.session.commit()
    flash('រក្សាទុកបានជោគជ័យ!', 'success')
    return redirect(url_for('quiz_pre', parent_id=parent.id))
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
@app.route('/question_analysis')
@login_required
def question_analysis():
    analysis_results = []
    
    for q in ALL_QUESTIONS:
        # រាប់ចំនួនអ្នកឆ្លើយត្រូវ (correct options)
        correct_count = QuizDetail.query.filter(
            QuizDetail.question_id == q['id'],
            QuizDetail.selected_option.in_(q['correct'])
        ).count()
        
        # រាប់ចំនួនអ្នកឆ្លើយសរុបសម្រាប់សំណួរនេះ
        total_answers = QuizDetail.query.filter_by(question_id=q['id']).count()
        
        wrong_count = total_answers - correct_count
        
        analysis_results.append({
            "id": q['id'],
            "topic": q['topic'],
            "correct": correct_count,
            "wrong": wrong_count,
            "total": total_answers
        })
        
    return render_template('analysis.html', results=analysis_results)
@app.route('/')
def index():
    if 'logged_in' in session: return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/save_quiz', methods=['POST'])
@login_required
def save_quiz():
    parent_id = request.form.get('parent_id')
    test_type = request.form.get('test_type') # 'pre' ឬ 'post'

    # ១. ឆែកមើលថាតើមាតាបិតានេះមាន Pre-test រួចហើយឬនៅ
    if test_type == 'pre':
        existing_pre = QuizResult.query.filter_by(parent_id=parent_id, test_type='pre').first()
        if existing_pre:
            # បើមានហើយ បង្ហាញសារព្រមាន ហើយមិនឱ្យ Save ឡើយ
            flash('មាតាបិតានេះមានទិន្នន័យ Pre-test រួចរាល់ហើយ! មិនអាចបញ្ចូលស្ទួនបានទេ។', 'danger')
            return redirect(url_for('home'))

    # ២. បើមិនទាន់មានទេ ទើបអនុញ្ញាតឱ្យ Save ចូល Database
    new_result = QuizResult(
        parent_id=parent_id,
        test_type=test_type,
        # ... ទិន្នន័យផ្សេងៗទៀត ...
    )
    db.session.add(new_result)
    db.session.commit()
    
    flash('រក្សាទុកជោគជ័យ!', 'success')
    return redirect(url_for('home'))
@app.route('/quiz_dashboard')
@login_required
def quiz_dashboard():
    from sqlalchemy import func
    
    # ១. ចាប់យកតម្រងពី URL (បានមកពី Dropdown ក្នុង HTML)
    v_f = request.args.get('village', '')
    c_f = request.args.get('commune', '')
    d_f = request.args.get('district', '')
    p_f = request.args.get('province', '')

    # ២. ទាញយកបញ្ជីទីតាំងទាំងអស់ (Distinct) សម្រាប់ដាក់ក្នុង Dropdown
    villages = [v[0] for v in db.session.query(Parent.village).distinct().all() if v[0]]
    communes = [c[0] for c in db.session.query(Parent.commune).distinct().all() if c[0]]
    districts = [d[0] for d in db.session.query(Parent.district).distinct().all() if d[0]]
    provinces = [p[0] for p in db.session.query(Parent.province).distinct().all() if p[0]]

    # ៣. បង្កើត Query មេសម្រាប់ Stats
    base_query = Parent.query
    if v_f: base_query = base_query.filter(Parent.village == v_f)
    if c_f: base_query = base_query.filter(Parent.commune == c_f)
    if d_f: base_query = base_query.filter(Parent.district == d_f)
    if p_f: base_query = base_query.filter(Parent.province == p_f)

    parents = base_query.all()
    total_quizzes = len(parents)

    if total_quizzes == 0:
        return render_template('quiz_dashboard.html', total_quizzes=0, avg_pre=0, avg_post=0, growth=0, 
                               level_stats=[0,0,0], villages=[], pre_scores=[], post_scores=[],
                               v_list=sorted(villages), c_list=sorted(communes), d_list=sorted(districts), p_list=sorted(provinces),
                               v_f=v_f, c_f=c_f, d_f=d_f, p_f=p_f)

    # ៤. គណនា Stats តាមតម្រងដែលបានរើស
    avg_pre = db.session.query(func.avg(Parent.pre_score)).filter(
        Parent.village == v_f if v_f else True,
        Parent.commune == c_f if c_f else True,
        Parent.district == d_f if d_f else True,
        Parent.province == p_f if p_f else True
    ).scalar() or 0

    avg_post = db.session.query(func.avg(Parent.post_score)).filter(
        Parent.village == v_f if v_f else True,
        Parent.commune == c_f if c_f else True,
        Parent.district == d_f if d_f else True,
        Parent.province == p_f if p_f else True
    ).scalar() or 0
    
    growth = round(avg_post - avg_pre, 1)

    # ៥. ទិន្នន័យ Pie Chart (កម្រិតយល់ដឹង)
    high = base_query.filter(Parent.post_score >= 80).count()
    medium = base_query.filter(Parent.post_score.between(50, 79)).count()
    low = base_query.filter(Parent.post_score < 50).count()
    level_stats = [high, medium, low]

    # ៦. ទិន្នន័យ Bar Chart (តាមភូមិ - បង្ហាញតែភូមិដែលពាក់ព័ន្ធនឹងតម្រង)
    village_query = db.session.query(Parent.village, func.avg(Parent.pre_score), func.avg(Parent.post_score))
    if v_f: village_query = village_query.filter(Parent.village == v_f)
    if c_f: village_query = village_query.filter(Parent.commune == c_f)
    if d_f: village_query = village_query.filter(Parent.district == d_f)
    if p_f: village_query = village_query.filter(Parent.province == p_f)
    
    village_data = village_query.group_by(Parent.village).all()

    res_villages = [v[0] if v[0] else "Unknown" for v in village_data]
    res_pre = [round(v[1] or 0, 1) for v in village_data]
    res_post = [round(v[2] or 0, 1) for v in village_data]

    return render_template('quiz_dashboard.html', 
                           total_quizzes=total_quizzes,
                           avg_pre=round(avg_pre, 1),
                           avg_post=round(avg_post, 1),
                           growth=growth,
                           level_stats=level_stats,
                           villages=res_villages,
                           pre_scores=res_pre,
                           post_scores=res_post,
                           v_list=sorted(villages), c_list=sorted(communes), 
                           d_list=sorted(districts), p_list=sorted(provinces),
                           v_f=v_f, c_f=c_f, d_f=d_f, p_f=p_f)
# --- កែសម្រួល Route Post-test ឱ្យទទួលស្គាល់ Questions ---
@app.route('/posttest_input')
@login_required
def posttest_input():
    parent_id = request.args.get('parent_id')
    # បញ្ជូនសំណួរទាំង ១៦ ទៅកាន់ Template
    return render_template('posttest_input.html', questions=ALL_QUESTIONS, parent_id=parent_id)
# ២. ក្នុង Route Login ត្រូវប្រើ User (អក្សរធំ) ឱ្យស្របតាម Class Name
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        target_user = User.query.filter_by(username=username).first()
        
        if target_user and check_password_hash(target_user.password, password):
            login_user(target_user) 
            return redirect(url_for('home')) 
        else:
            flash('ឈ្មោះអ្នកប្រើប្រាស់ ឬលេខសម្ងាត់មិនត្រឹមត្រូវ!', 'danger')
    # ប្រាកដថាវានឹង render ទៅកាន់ login.html ធម្មតា
    return render_template('login.html')
@app.route('/delete_parent/<int:id>', methods=['GET', 'POST']) # 👈 ថែម 'GET' ចូល
@login_required
def delete_parent(id):
    parent = Parent.query.get_or_404(id)
    db.session.delete(parent)
    db.session.commit()
    flash('បានលុបទិន្នន័យមាតាបិតារួចរាល់!', 'success')
    return redirect(url_for('quiz_dashboard'))
@app.route('/save_test', methods=['POST'])
def save_test():
    data = request.form
    # បន្ថែម Logic រក្សាទុកក្នុង Database នៅទីនេះ
    flash("ទិន្នន័យត្រូវបានរក្សាទុក!", "success")
    return redirect(url_for('home'))
@app.route('/test_summary')
@login_required
def test_summary():
    # ១. ទាញយកតម្រង (Filters) ពី URL
    village_filter = request.args.get('village', '')
    
    # ២. បង្កើត Query ដើម្បីទាញយកមាតាបិតា
    query = Parent.query
    if village_filter:
        query = query.filter_by(village=village_filter)
    
    parents = query.all()
    total_samples = len(parents)

    # ៣. រៀបចំរចនាសម្ព័ន្ធទិន្នន័យ A-E (សំណួរទី ១ ដល់ ២០)
    # យើងប្រើ stats ជាឈ្មោះ Variable ក្នុង Python
    stats = {i: {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0} for i in range(1, 21)}

    for p in parents:
        if p.answers_json:
            import json
            try:
                ans = json.loads(p.answers_json)
                for q_num, choice in ans.items():
                    q_idx = int(q_num)
                    if q_idx in stats and choice in stats[q_idx]:
                        stats[q_idx][choice] += 1
            except:
                continue

    # ៤. ទាញយកបញ្ជីភូមិសម្រាប់បង្ហាញក្នុង Dropdown
    villages = [v[0] for v in db.session.query(Parent.village).distinct().all() if v[0]]

    # ៥. បញ្ជូនទៅកាន់ Template (សំខាន់បំផុតគឺឈ្មោះ summary_data)
    return render_template('test_summary.html', 
                           summary_data=stats, 
                           total_sample=total_samples, 
                           villages=villages)
# --- កូដសម្រាប់ទំព័រដើម (Home) ---
@app.route('/home')
@login_required
def home():
    # ១. ចាប់យក Filter ពី URL
    v_filter = request.args.get('village', '')
    s_query = request.args.get('search_name', '')

    # ២. ទាញបញ្ជីភូមិសម្រាប់ Dropdown
    villages_list = [v[0] for v in db.session.query(Parent.village).distinct().all() if v[0]]

    # ៣. Query មាតាបិតា និងច្រោះតាមលក្ខខណ្ឌ
    query = Parent.query
    if v_filter:
        query = query.filter(Parent.village == v_filter)
    if s_query:
        query = query.filter(Parent.name.contains(s_query))
    
    parents = query.all()

    return render_template('home.html', 
                           parents=parents, 
                           villages_list=sorted(villages_list),
                           selected_village=v_filter,
                           search_query=s_query)
@app.route('/logout')
@login_required
def logout():
    logout_user() # មុខងារបញ្ចប់ Session របស់អ្នកប្រើប្រាស់
    flash('អ្នកបានចាកចេញដោយជោគជ័យ!', 'info')
    return redirect(url_for('login')) # ត្រឡប់ទៅទំព័រ Login វិញ
# --- 🎯 ផ្នែកសំខាន់៖ បង្កើត Function ឱ្យត្រូវតាមឈ្មោះក្នុង HTML ---

@app.route('/quiz_post/<int:parent_id>')
@login_required
def quiz_post(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    return render_template('quiz_question.html', parent=parent, test_type='Post-test')
@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    # មានតែ Admin ទេដែលអាចគ្រប់គ្រងអ្នកប្រើប្រាស់បាន
    if current_user.role != 'Admin':
        flash('លោកអ្នកមិនមានសិទ្ធិចូលកាន់ទំព័រនេះឡើយ!', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        # ការប្រើ generate_password_hash ដូចក្នុងរូបភាពទី ៥
        password = generate_password_hash(request.form.get('password'))
        full_name = request.form.get('full_name')
        role = request.form.get('role')

        # ពិនិត្យមើលឈ្មោះគណនីកុំឱ្យជាន់គ្នា
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('ឈ្មោះគណនីនេះមានរួចហើយ!', 'warning')
        else:
            new_user = User(username=username, password=password, full_name=full_name, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash('បន្ថែមបុគ្គលិកជោគជ័យ!', 'success')
        return redirect(url_for('manage_users'))
    
    users = User.query.all()
    return render_template('users.html', users=users)
# --- ១. Route សម្រាប់កែសម្រួលព័ត៌មានទូទៅ (ឈ្មោះ, ភូមិ, លេខទូរស័ព្ទ...) ---
@app.route('/edit_info/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_info(id):
    person = Parent.query.get_or_404(id)
    if request.method == 'POST':
        person.name = request.form.get('name')
        person.gender = request.form.get('gender')
        person.age = request.form.get('age')
        person.phone = request.form.get('phone')
        person.village = request.form.get('village')
        person.commune = request.form.get('commune')
        person.district = request.form.get('district')
        person.province = request.form.get('province')
        person.role_in_family = request.form.get('role_in_family')

        try:
            db.session.commit()
            flash(f'កែសម្រួលព័ត៌មានរបស់ {person.name} ជោគជ័យ!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            flash(f'កំហុស៖ {str(e)}', 'danger')

    return render_template('edit_info.html', person=person)

# --- ២. Route សម្រាប់បញ្ចូលពិន្ទុតេស្តសុទ្ធសាធ (Quiz Only) ---
@app.route('/edit_parent/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_parent(id):
    person = Parent.query.get_or_404(id)
    test_type = request.args.get('test_type', 'pre')

    if request.method == 'POST':
        test_type = request.form.get('test_type')
        correct_answers = {f'q{i}': ['ក', 'គ', 'ង'] for i in range(1, 17)}
        score_count = 0
        user_all_answers = {}

        for i in range(1, 17):
            q_key = f'q{i}'
            selected = request.form.getlist(f'{q_key}[]')
            user_all_answers[q_key] = selected 
            if set(selected) == set(correct_answers[q_key]):
                score_count += 1

        score_percent = round((score_count / 16) * 100)
        
        # រក្សាទុកពិន្ទុតាមប្រភេទតេស្ត
        if test_type == 'pre': person.pre_score = score_percent
        else: person.post_score = score_percent
        
        person.answers_json = json.dumps(user_all_answers)
        
        # បន្ថែមក្នុង QuizResult សម្រាប់របាយការណ៍សង្ខេប
        new_res = QuizResult(parent_id=person.id, parent_name=person.name, village=person.village,
                             test_type=test_type, score=score_percent, answers_json=person.answers_json)
        db.session.add(new_res)
        db.session.commit()
        
        flash(f'បញ្ចូលពិន្ទុ {test_type} រួចរាល់៖ {score_percent}%', 'success')
        return redirect(url_for('home'))

    return render_template('edit_parent.html', person=person, test_type=test_type)
@app.route('/add_parent', methods=['GET', 'POST'])
@login_required
def add_parent():
    if request.method == 'POST':
        try:
            # បង្កើត Object Parent ថ្មីដោយប្រើឈ្មោះអថេរឱ្យត្រូវតាម Form
            new_parent = Parent(
                # ១. ព័ត៌មានមាតាបិតា
                name=request.form.get('name'),
                gender=request.form.get('gender'),
                age=request.form.get('age'),
                phone=request.form.get('phone'),
                village=request.form.get('village'),
                commune=request.form.get('commune'),
                district=request.form.get('district'),
                province=request.form.get('province'),
                role_in_family=request.form.get('role_in_family'),
                year_joined=request.form.get('year_joined', 2026),

                # ២. កុមារក្នុងបន្ទុក (Own Children) - ផ្ទៀងផ្ទាត់ឈ្មោះតាម HTML
                c05_f_normal=int(request.form.get('c05_f_normal', 0)),
                c05_m_normal=int(request.form.get('c05_m_normal', 0)),
                c05_f_disability=int(request.form.get('c05_dis_f', 0)), 
                c05_m_disability=int(request.form.get('c05_dis_m', 0)),
                
                c612_f_normal=int(request.form.get('c612_f_normal', 0)),
                c612_m_normal=int(request.form.get('c612_m_normal', 0)),
                c612_f_disability=int(request.form.get('c612_dis_f', 0)),
                c612_m_disability=int(request.form.get('c612_dis_m', 0)),

                c1318_f_normal=int(request.form.get('c1318_f_normal', 0)),
                c1318_m_normal=int(request.form.get('c1318_m_normal', 0)),
                c1318_f_disability=int(request.form.get('c1318_dis_f', 0)),
                c1318_m_disability=int(request.form.get('c1318_dis_m', 0)),

                # ៣. កុមារជាសាច់ញាតិ (Relative Children)
                r05_f_normal=int(request.form.get('rel_05_f', 0)),
                r05_m_normal=int(request.form.get('rel_05_m', 0)),
                r05_f_disability=int(request.form.get('rel_05_dis_f', 0)),
                r05_m_disability=int(request.form.get('rel_05_dis_m', 0)),
                
                r612_f_normal=int(request.form.get('rel_612_f', 0)),
                r612_m_normal=int(request.form.get('rel_612_m', 0)),
                r612_f_disability=int(request.form.get('rel_612_dis_f', 0)),
                r612_m_disability=int(request.form.get('rel_612_dis_m', 0)),

                r1318_f_normal=int(request.form.get('rel_1318_f', 0)),
                r1318_m_normal=int(request.form.get('rel_1318_m', 0)),
                r1318_f_disability=int(request.form.get('rel_1318_dis_f', 0)),
                r1318_m_disability=int(request.form.get('rel_1318_dis_m', 0)),

                # ៤. អ្នកសម្របសម្រួល (Facilitators)
                fac_1=request.form.get('fac_1'),
                fac_2=request.form.get('fac_2'),
                fac_3=request.form.get('fac_3'),
                
                # ពិន្ទុដំបូងកំណត់ត្រឹម ០
                pre_score=0,
                post_score=0
            )
            
            db.session.add(new_parent)
            db.session.commit()
            flash("បានរក្សាទុកទិន្នន័យគ្រួសារគោលដៅដោយជោគជ័យ!", "success")
            return redirect(url_for('home'))

        except Exception as e:
            db.session.rollback()
            flash(f"មានបញ្ហាក្នុងការរក្សាទុក៖ {str(e)}", "danger")
            return redirect(url_for('add_parent'))

    return render_template('add_parent.html')
@app.route('/api/mark_attendance/<int:parent_id>/<int:step>', methods=['POST'])
@login_required
def mark_attendance(parent_id, step):
    parent = Parent.query.get_or_404(parent_id)
    date_col = f'm{step}_date' # ឧទាហរណ៍៖ m1_date, m2_date
    
    # បើមានវត្តមានហើយ ឱ្យលុបវិញ (Toggle) បើមិនទាន់មាន ឱ្យដាក់កាលបរិច្ឆេទថ្ងៃនេះ
    if getattr(parent, date_col):
        setattr(parent, date_col, None)
        action = 'unmarked'
    else:
        setattr(parent, date_col, datetime.now())
        action = 'marked'
    
    db.session.commit()
    return jsonify({'status': 'success', 'action': action})
@app.route('/api/update_attendance', methods=['POST'])
@login_required
def update_attendance():
    data = request.get_json()
    p_id = data.get('parent_id')
    l_num = data.get('lesson')
    status = data.get('status')

    if status == 'វត្តមាន':
        # ប្រសិនបើគ្រីស គឺបន្ថែមវត្តមាន
        new_attendance = Attendance(parent_id=p_id, lesson_number=l_num, status='វត្តមាន')
        db.session.add(new_attendance)
    else:
        # ប្រសិនបើដោះគ្រីស គឺលុបវត្តមានចេញ
        Attendance.query.filter_by(parent_id=p_id, lesson_number=l_num).delete()
    
    db.session.commit()
    return jsonify({"status": "success"})
@app.route('/attendance_report')
@login_required
def attendance_report():
    # ១. ទាញយកទិន្នន័យវត្តមានសរុបបែងចែកតាមភូមិ
    report_data = db.session.query(
        Parent.village,
        func.count(Attendance.id).label('total_attendance')
    ).join(Attendance, Parent.id == Attendance.parent_id).group_by(Parent.village).all()

    # ២. គណនាចំនួនអ្នកចូលរួមតាមជំហាននីមួយៗ (Step 1-8)
    step_stats = {}
    for i in range(1, 9):
        step_stats[f'Step {i}'] = Attendance.query.filter_by(step_number=i).count()

    return render_template('attendance_report.html', 
                           report_data=report_data, 
                           step_stats=step_stats)
@app.route('/export_attendance_excel')
@login_required
def export_attendance_excel():
    # ១. ទាញទិន្នន័យមាតាបិតាទាំងអស់
    parents = Parent.query.all()
    
    # ២. បង្កើត Buffer សម្រាប់រក្សាទុក File ក្នុង Memory
    output = BytesIO()
    workbook = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # បង្កើតសន្លឹកកិច្ចការ (Worksheet)
    worksheet = workbook.book.add_worksheet('Attendance Report')
    
    # ៣. កំណត់ស្ទីល (Formats)
    header_format = workbook.book.add_format({
        'bold': True, 'align': 'center', 'valign': 'vcenter',
        'bg_color': '#D7E4BC', 'border': 1, 'font_name': 'Khmer OS Battambang', 'font_size': 10
    })
    cell_format = workbook.book.add_format({
        'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_name': 'Khmer OS Battambang', 'font_size': 9
    })

    # ៤. គូរ Header ស្មុគស្មាញ (Merged Cells ដូចរូបភាពទី ៣)
    worksheet.merge_range('A1:A2', 'ឈ្មោះមាតាបិតា', header_format)
    
    # គូរសម្រាប់ Step 1 ដល់ Step 8
    steps_titles = [
        "ជំហានទី១៖ តេស្តមុនវគ្គ", "ជំហានទី២៖ ការការពារកុមារ", "ជំហានទី៣៖ សុខុមាលភាព",
        "ជំហានទី៤៖ ការប្រាស្រ័យទាក់ទង", "ជំហានទី៥៖ កាតព្វកិច្ច", "ជំហានទី៦៖ របៀបចិញ្ចឹមកូន",
        "ជំហានទី៧៖ ការប្រើប្រាស់វិន័យ", "ជំហានទី៨៖ តេស្តក្រោយវគ្គ"
    ]
    
    col = 1
    for title in steps_titles:
        # Merge ៣ ក្រឡាសម្រាប់ Step នីមួយៗ (Date, Present, Absent)
        worksheet.merge_range(0, col, 0, col + 2, title, header_format)
        worksheet.write(1, col, 'កាលបរិច្ឆេទ', header_format)
        worksheet.write(1, col + 1, 'វត្តមាន', header_format)
        worksheet.write(1, col + 2, 'អវត្តមាន', header_format)
        col += 3

    # ៥. បំពេញទិន្នន័យមាតាបិតា (Data Rows)
    row_num = 2
    for p in parents:
        worksheet.write(row_num, 0, p.name, cell_format)
        
        col_offset = 1
        for step_idx in range(1, 9):
            # ទាញទិន្នន័យវត្តមានពី Database (ឧទាហរណ៍)
            # ប្អូនត្រូវមានមុខងារ get_attendance(step_number) ក្នុង Model Parent
            att = Attendance.query.filter_by(parent_id=p.id, step_number=step_idx).first()
            
            if att:
                worksheet.write(row_num, col_offset, att.date.strftime('%d/%m/%Y') if att.date else '', cell_format)
                worksheet.write(row_num, col_offset + 1, '✓' if att.status == 'P' else '', cell_format)
                worksheet.write(row_num, col_offset + 2, '✗' if att.status == 'A' else '', cell_format)
            else:
                worksheet.write(row_num, col_offset, '', cell_format)
                worksheet.write(row_num, col_offset + 1, '', cell_format)
                worksheet.write(row_num, col_offset + 2, '', cell_format)
            
            col_offset += 3
        row_num += 1

    # ៦. បិទ និងបញ្ជូន File ឱ្យ User
    workbook.close()
    output.seek(0)
    
    file_name = f"Attendance_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(output, as_attachment=True, download_name=file_name, 
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
@app.route('/save_attendance', methods=['POST'])
@login_required
def save_attendance():
    # ១. ទាញយកទិន្នន័យពី Form ក្នុង Modal
    p_id = request.form.get('parent_id')
    step = request.form.get('step_number')
    att_date_str = request.form.get('date')
    att_status = request.form.get('status')

    # ២. បំប្លែងថ្ងៃខែពីអត្ថបទ ទៅជាប្រភេទ Date
    try:
        att_date = datetime.strptime(att_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        att_date = datetime.utcnow().date()

    # ៣. ឆែកមើលក្នុង Database៖ បើមានព័ត៌មានជំហាននេះហើយ គឺកែសម្រួល បើអត់ទេ គឺបង្កើតថ្មី
    attendance = Attendance.query.filter_by(parent_id=p_id, step_number=step).first()
    
    if not attendance:
        # បង្កើត Record ថ្មី
        attendance = Attendance(
            parent_id=p_id, 
            step_number=step, 
            status=att_status, 
            date=att_date
        )
        db.session.add(attendance)
    else:
        # ធ្វើបច្ចុប្បន្នភាពទិន្នន័យដែលមានស្រាប់
        attendance.status = att_status
        attendance.date = att_date
    
    # ៤. រក្សាទុកចូលក្នុង Database
    try:
        db.session.commit()
        flash(f'បញ្ចូលវត្តមានជំហានទី {step} ជោគជ័យ!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('មានបញ្ហាក្នុងការរក្សាទុក៖ ' + str(e), 'danger')

    return redirect(url_for('home'))
@app.route('/save_quiz_score', methods=['POST'])
@login_required
def save_quiz_score():
    parent_id = request.form.get('parent_id')
    test_type = request.form.get('test_type')
    total_score = request.form.get('total_score')
    
    parent = Parent.query.get(parent_id)
    if parent:
        if test_type == 'Pre-test':
            parent.pre_score = float(total_score)
        else:
            parent.post_score = float(total_score)
        db.session.commit()
    
    return redirect(url_for('home'))
@app.route('/clear_all_results')
def clear_all_results():
    QuizResult.query.delete() # លុបចោលទាំងអស់ក្នុងតារាង QuizResult
    db.session.commit()
    return "លុបលទ្ធផលតេស្តទាំងអស់រួចរាល់! សាកល្បងបើក Report ម្តងទៀត។"
@app.route('/reset_database', methods=['POST'])
@login_required
def reset_database():
    try:
        # លុបទិន្នន័យក្នុងតារាងទាំងពីរឱ្យអស់
        QuizResult.query.delete()
        Parent.query.delete()
        db.session.commit()
        flash('ប្រព័ន្ធត្រូវបានលាងសម្អាតជោគជ័យ! លេខសរុបឥឡូវនេះគឺ ០។', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('quiz_dashboard'))
@app.route('/view_results/<int:parent_id>/<test_type>')
@login_required
def view_results(parent_id, test_type):
    parent = Parent.query.get_or_404(parent_id)
    # ទាញយកលទ្ធផលតេស្ត
    result = QuizResult.query.filter_by(parent_id=parent_id, test_type=test_type).first()
    
    if not result:
        flash('មិនទាន់មានទិន្នន័យតេស្តសម្រាប់មាតាបិតានេះឡើយ។', 'info')
        return redirect(url_for('home'))

    # បំប្លែងទិន្នន័យចម្លើយពី JSON
    import json
    answers = json.loads(result.answers_json)
    
    return render_template('view_results.html', parent=parent, result=result, answers=answers)
@app.route('/monthly_summary')
@login_required
def monthly_summary():
    # ១. បូកសរុបអ្នកចូលរួមតាមភូមិ
    summary_data = db.session.query(
        QuizResult.village, 
        func.count(QuizResult.id).label('total')
    ).group_by(QuizResult.village).all()

    # ២. បូកសរុបអ្នកចូលរួមតាមថ្ងៃ (៧ ថ្ងៃចុងក្រោយ)
    daily_data = db.session.query(
        func.date(QuizResult.date_taken).label('date'),
        func.count(QuizResult.id).label('count')
    ).group_by(func.date(QuizResult.date_taken)).order_by(func.date(QuizResult.date_taken)).limit(7).all()
    
    return render_template('monthly_summary.html', 
                           summary_data=summary_data, 
                           daily_data=daily_data)
@app.route('/profile')
@login_required
def profile():
    # ឥឡូវនេះ created_by_id នឹងដំណើរការព្រោះវាមានក្នុង Model ហើយ
    my_families_count = Parent.query.filter_by(created_by_id=current_user.id).count()
    recent_activities = Parent.query.filter_by(created_by_id=current_user.id).order_by(Parent.id.desc()).limit(5).all()
    return render_template('profile.html', count=my_families_count, activities=recent_activities)
@app.route('/edit_profile', methods=['POST'])
@login_required
def edit_profile():
    new_username = request.form.get('username')
    new_email = request.form.get('email')

    # ឆែកឈ្មោះជាន់គ្នា
    existing_user = User.query.filter_by(username=new_username).first()
    if existing_user and existing_user.id != current_user.id:
        flash('Username already exists!', 'danger')
        return redirect(url_for('profile'))

    try:
        current_user.username = new_username
        current_user.email = new_email
        db.session.commit()
        
        # 🔥 ចំណុចសំខាន់៖ Refresh Session ឱ្យស្គាល់ឈ្មោះថ្មីភ្លាមៗ
        login_user(current_user) 
        
        flash('Profile updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error: ' + str(e), 'danger')

    return redirect(url_for('profile'))
@app.route('/export_survey_report')
@login_required
def export_survey_report():
    # ១. ទាញយកទិន្នន័យទាំងអស់ពីតារាង QuizResult
    results = QuizResult.query.all()
    
    # ២. រៀបចំបញ្ជីទិន្នន័យសម្រាប់ Excel
    data = []
    for r in results:
        data.append({
            "ឈ្មោះមាតាបិតា": r.parent_name,
            "ភូមិគោលដៅ": r.village,
            "កាលបរិច្ឆេទ": r.date_taken.strftime('%d-%m-%Y %H:%M') if r.date_taken else "N/A",
            "ស្ថានភាព": "បានបញ្ចប់ការស្ទង់មតិ"
        })
    
    # ៣. បម្លែងទៅជា DataFrame និងបង្កើតឯកសារ Excel
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Survey Results')
    
    output.seek(0)
    
    # ៤. បញ្ជូនឯកសារទៅកាន់ Browser ដើម្បី Download
    return send_file(
        output, 
        attachment_filename="ICS-SP_Survey_Report_2026.xlsx", 
        as_attachment=True
    )
@app.route('/export_quiz_result')
@login_required
def export_quiz_result():
    results = db.session.query(QuizResult, Parent).join(Parent).all()
    
    data = []
    for r, p in results:
        data.append({
            "ល.រ": r.id,
            "ឈ្មោះមាតាបិតា": p.name,
            "ភេទ": p.gender,
            "ភូមិ": p.village,
            "ចំនួនកូនសរុប": p.total_children,
            "កុមារមានពិការភាព": p.children_with_disability,
            "ពិន្ទុតេស្ត (%)": r.score,
            "ប្រភេទតេស្ត": "មុនវគ្គ" if r.test_type == 'pre' else "ក្រោយវគ្គ",
            "មន្ត្រីសម្របសម្រួល": p.facilitator_name,
            "កាលបរិច្ឆេទ": r.date_taken.strftime('%d-%m-%Y')
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    # ប្រើ Style ឱ្យស្រស់ស្អាតសម្រាប់របាយការណ៍ MER
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='MER_Report')
        
    output.seek(0)
    return send_file(output, download_name="ICS_SP_MER_Report.xlsx", as_attachment=True)
# កែឈ្មោះ Function ពី take_test ទៅជា save_pretest
@app.route('/save_pretest', methods=['POST'])
@login_required
def save_pretest(): 
    parent_id = request.form.get('parent_id')
    total_score = request.form.get('total_score')
    
    parent = Parent.query.get(parent_id)
    if parent:
        try:
            parent.pre_score = float(total_score)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            
    return redirect(url_for('home'))
@app.route('/print_test_summary')
@login_required
def print_test_summary():
    # ១. ចាប់យកតម្រងភូមិពី URL
    v_filter = request.args.get('village')

    # ២. បង្កើត Query ច្រោះយកទិន្នន័យ (Join ជាមួយ Parent ដើម្បីបានឈ្មោះភូមិ)
    query = QuizResult.query.join(Parent)
    if v_filter and v_filter != "":
        query = query.filter(Parent.village == v_filter)
    
    results = query.all()

    # ៣. រៀបចំទិន្នន័យ A-E សម្រាប់សំណួរទាំង ១៦
    summary_data = {i: {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'E': 0} for i in range(1, 17)}
    # ផែនទីបកប្រែចម្លើយពីខ្មែរ ទៅជាអក្សរឡាតាំង
    options_map = {'ក': 'A', 'ខ': 'B', 'គ': 'C', 'ឃ': 'D', 'ង': 'E'}

    for r in results:
        if r.answers_json:
            try:
                ans_data = json.loads(r.answers_json)
                for q_key, selected_vals in ans_data.items():
                    # ប្រើ Regex ដើម្បីទាញលេខសំណួរចេញពី q1, q2...
                    match = re.search(r'(\d+)', q_key)
                    if match:
                        q_num = int(match.group(1))
                        if q_num in summary_data:
                            for val in selected_vals:
                                char = val.strip()
                                if char in options_map:
                                    summary_data[q_num][options_map[char]] += 1
            except (json.JSONDecodeError, TypeError):
                continue

    # ៤. កំណត់ព័ត៌មានទីតាំងសម្រាប់បង្ហាញក្នុង Header (ដោះស្រាយបញ្ហា IndexError)
    if results:
        first_p = results[0].parent
        loc_info = {
            'province': getattr(first_p, 'province', 'បន្ទាយមានជ័យ'),
            'district': getattr(first_p, 'district', 'សិរីសោភ័ណ'),
            'commune': getattr(first_p, 'commune', 'ស្រង៉ែ'),
            'village': v_filter if v_filter else "គ្រប់ភូមិទាំងអស់"
        }
    else:
        loc_info = {
            'province': "---", 'district': "---", 'commune': "---", 
            'village': v_filter if v_filter else "មិនមានទិន្នន័យ"
        }

    return render_template('print_test_summary.html', 
                           summary_data=summary_data, 
                           total_sample=len(results),
                           loc=loc_info,
                           date=datetime.now().strftime('%d/%m/%Y'),
                           facilitator_name="មន្ត្រីសម្របសម្រួល MER",
                           manager_name="ចាន់ វិបុល")

def logout():
    logout_user() # ប្រើមុខងាររបស់ flask_login ផ្ទាល់
    session.clear() # សម្អាត session បន្ថែមដើម្បីសុវត្ថិភាព
    flash("លោកអ្នកបានចាកចេញពីប្រព័ន្ធដោយជោគជ័យ!", "info")
    return redirect(url_for('login'))
@app.errorhandler(404)
def page_not_found(e):
    # បញ្ជូនទៅកាន់ទំព័រ 404.html ដែលយើងទើបតែបង្កើត
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    # ប្អូនក៏អាចប្រើទំព័រដដែលនេះសម្រាប់ Error 500 ផងដែរ
    return render_template('404.html'), 500
@app.route('/export_mer_report')
@login_required
def export_mer_report():
    parents = Parent.query.all()
    data = []
    for p in parents:
        row = {
            'ឈ្មោះមាតាបិតា': p.name,
            'ភេទ': p.gender,
            'ភូមិ': p.village,
            'កូនក្នុងបន្ទុក ០-៥ (សរុប)': p.c05_f_normal + p.c05_f_disability + p.c05_m_normal + p.c05_m_disability,
            'កូនសាច់ញាតិ ០-៥ (សរុប)': p.r05_f_normal + p.r05_f_disability + p.r05_m_normal + p.r05_m_disability,
            'អ្នកសម្របសម្រួល': p.fac_1 # ប្តូរមក fac_1 ឱ្យត្រូវតាម Model
        }
        data.append(row)

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='MER_Data_2026')
    output.seek(0)
    return send_file(output, download_name=f"MER_Report_{datetime.now().date()}.xlsx", as_attachment=True)

    # ២. បង្កើតឯកសារ Excel ដោយប្រើ Pandas
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='MER_Data_2026')
    
    output.seek(0)
    
    # ៣. បញ្ជូនឯកសារទៅឱ្យ User ទាញយក
    file_name = f"ICS_SP_MER_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(output, download_name=file_name, as_attachment=True)
with app.app_context():
    # កូដនេះនឹងបង្កើតតារាង 'parent' ថ្មីដែលមាន Column គ្រប់គ្រាន់ (job_title, year_joined...)
    db.create_all()
    
    # ដោយសារយើងលុប Database ចាស់ យើងត្រូវបង្កើត Admin ឡើងវិញ
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin', 
            password=generate_password_hash('123'), 
            role='Admin', 
            full_name='Administrator'
        )
        db.session.add(admin_user)
        db.session.commit()
if __name__ == '__main__':
    # ការដាក់ host='0.0.0.0' គឺសំខាន់បំផុត ដើម្បីឱ្យឧបករណ៍ក្នុង WiFi អាចចូលមើលបាន
    app.run(debug=True, host='0.0.0.0', port=5000)