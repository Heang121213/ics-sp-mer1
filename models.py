from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# ១. តារាងព័ត៌មានមាតាបិតា និងអាណាព្យាបាល
class Parent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # ១. ព័ត៌មានមាតាបិតា (រូបភាពទី ៤)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    disability = db.Column(db.String(10))  # បាទ/ចាស ឬ ទេ
    disability_type = db.Column(db.String(100))
    role_in_family = db.Column(db.String(50)) # ឪពុក/ម្ដាយ/អាណាព្យាបាល
    
    # ២. ព័ត៌មានភូមិសាស្ត្រ
    village = db.Column(db.String(100))
    commune = db.Column(db.String(100))
    district = db.Column(db.String(100))
    province = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    
    # ៣. ទិន្នន័យកុមារក្នុងបន្ទុក (បែងចែកតាមភេទ និងពិការភាព - រូបភាពទី ៥)
    # ក្រុមអាយុ ០-៥ ឆ្នាំ
    c05_f_normal = db.Column(db.Integer, default=0) # ស្រី គ្មានពិការភាព
    c05_f_disability = db.Column(db.Integer, default=0) # ស្រី មានពិការភាព
    c05_m_normal = db.Column(db.Integer, default=0) # ប្រុស គ្មានពិការភាព
    c05_m_disability = db.Column(db.Integer, default=0) # ប្រុស មានពិការភាព

    # ក្រុមអាយុ ៦-១២ ឆ្នាំ
    c612_f_normal = db.Column(db.Integer, default=0)
    c612_f_disability = db.Column(db.Integer, default=0)
    c612_m_normal = db.Column(db.Integer, default=0)
    c612_m_disability = db.Column(db.Integer, default=0)

    # ក្រុមអាយុ ១៣-១៨ ឆ្នាំ
    c1318_f_normal = db.Column(db.Integer, default=0)
    c1318_f_disability = db.Column(db.Integer, default=0)
    c1318_m_normal = db.Column(db.Integer, default=0)
    c1318_m_disability = db.Column(db.Integer, default=0)

    # ៤. ព័ត៌មានអ្នកសម្របសម្រួល (រូបភាពទី ៤)
    facilitator_name = db.Column(db.String(100))
    session_count = db.Column(db.Integer, default=1) # វគ្គទីប៉ុន្មាន
    join_date = db.Column(db.DateTime, default=datetime.now)

# ២. តារាងលទ្ធផលតេស្ត (Pre-test & Post-test)
class TestResult(db.Model):
    __tablename__ = 'test_results'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=False)
    test_type = db.Column(db.String(20), nullable=False) # 'pre' ឬ 'post'
    score = db.Column(db.Float, nullable=False) # ពិន្ទុដែលទទួលបាន
    lesson_topic = db.Column(db.String(100)) # ប្រធានបទមេរៀន (១ ដល់ ៥)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)

# ៣. តារាងកត់ត្រាសកម្មភាពមន្ត្រី (Activity Logs)
class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(255), nullable=False) # សកម្មភាពដែលបានធ្វើ
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)