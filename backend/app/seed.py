from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import User

# Exact team roster required by the official brief
TEAM_ROSTER = [
    {
        "user_id": "u_aarti",
        "name": "Aarti Menon",
        "department": "Sales — Enterprise",
        "scope": "RFPs, RFIs, tenders, and inbound deals above ₹10,00,000"
    },
    {
        "user_id": "u_rohit",
        "name": "Rohit Sharma",
        "department": "Sales — SMB",
        "scope": "Product enquiries, demo requests, deals at or below ₹10,00,000"
    },
    {
        "user_id": "u_meera",
        "name": "Meera Iyer",
        "department": "Marketing",
        "scope": "Webinars, event and conference sponsorships, content collaborations, PR and media"
    },
    {
        "user_id": "u_karan",
        "name": "Karan Doshi",
        "department": "Alliances",
        "scope": "Reseller, channel partner, and technology integration proposals"
    },
    {
        "user_id": "u_divya",
        "name": "Divya Rao",
        "department": "Finance",
        "scope": "Invoices, purchase orders, payment reminders, GST and vendor billing"
    },
    {
        "user_id": "u_triage",
        "name": "Triage Queue",
        "department": "Operations",
        "scope": "Ambiguous items requiring human review"
    }
]

def seed_users(db: Session = None):
    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True
        
    try:
        for member in TEAM_ROSTER:
            user = db.query(User).filter(User.user_id == member["user_id"]).first()
            if not user:
                new_user = User(
                    user_id=member["user_id"],
                    name=member["name"],
                    department=member["department"],
                    scope=member["scope"]
                )
                db.add(new_user)
        db.commit()
        print("Database seeded with team roster successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        if own_session:
            db.close()

if __name__ == "__main__":
    seed_users()
