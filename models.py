from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class UserPassport(db.Model):
    """
    User Passport model to store persistent membership data for users across devices.
    This acts as a user's "passport" that travels with them no matter where they log in.
    """
    __tablename__ = 'user_passport'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    memberships_json = db.Column(db.Text, nullable=False, default='[]')  # JSON string of memberships
    last_updated = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship to User model
    user = db.relationship('User', backref=db.backref('passport', uselist=False, lazy=True))
    
    def __repr__(self):
        return f"<UserPassport user_id={self.user_id}>"
