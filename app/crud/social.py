from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app import models
from . import notification as crud_notification
from . import user as crud_user
import uuid
import datetime
from datetime import timedelta
import random
from typing import List

def get_friendship_status(db: Session, user_a: str, user_b: str) -> str:
    # Check if A sent to B
    sent = db.query(models.Friendship).filter(
        models.Friendship.requester_id == user_a,
        models.Friendship.addressee_id == user_b
    ).first()
    
    if sent:
        if sent.status == 'accepted': return 'accepted'
        return 'pending_sent'
        
    # Check if B sent to A
    received = db.query(models.Friendship).filter(
        models.Friendship.requester_id == user_b,
        models.Friendship.addressee_id == user_a
    ).first()
    
    if received:
        if received.status == 'accepted': return 'accepted'
        return 'pending_received'
        
    return 'none'

def send_friend_request(db: Session, requester_id: str, addressee_id: str):
    # Check existing
    existing = db.query(models.Friendship).filter(
        or_(
            and_(models.Friendship.requester_id == requester_id, models.Friendship.addressee_id == addressee_id),
            and_(models.Friendship.requester_id == addressee_id, models.Friendship.addressee_id == requester_id)
        )
    ).first()
    

    if existing:
        return existing

    friendship = models.Friendship(
        id=str(uuid.uuid4()),
        requester_id=requester_id,
        addressee_id=addressee_id,
        status="pending"
    )
    db.add(friendship)
    db.commit()
    db.refresh(friendship)

    current_user = crud_user.get_user(db, requester_id)

    crud_notification.create_notification(
        db=db,
        recipient_id=addressee_id,
        sender_id=requester_id,
        type="FRIEND_REQUEST",
        title="Buddy Request!!!",
        message=f"{current_user.first_name} Wants to be your buddy!",
        reference_id=friendship.id
    )

    return friendship

def respond_to_friend_request(db: Session, user_id: str, friendship_id: str, action: str):
    # User must be the addressee to accept
    friendship = db.query(models.Friendship).filter(models.Friendship.id == friendship_id).first()
    
    if not friendship:
        return None
        
    if friendship.addressee_id != user_id:
        return None # Unauthorized
        
    if action == 'accept':
        friendship.status = 'accepted'
        current_user = crud_user.get_user(db, user_id)
        
        crud_notification.create_notification(
            db=db,
            recipient_id=friendship.requester_id,
            sender_id=user_id,
            type="FRIEND_ACCEPT",
            title="Buddy Request Accepted!",
            message=f"{current_user.first_name} Has accepted your buddy request!",
            reference_id=friendship.id
        )
        
    elif action == 'reject':
        db.delete(friendship) # Or set to 'rejected'
        
    db.commit()

    return friendship

def remove_friend(db: Session, user_a: str, user_b: str):
    """
    Removes an existing friendship between user_a and user_b.
    """
    friendship = db.query(models.Friendship).filter(
        and_(
            or_(
                and_(models.Friendship.requester_id == user_a, models.Friendship.addressee_id == user_b),
                and_(models.Friendship.requester_id == user_b, models.Friendship.addressee_id == user_a)
            ),
            models.Friendship.status == 'accepted'
        )
    ).first()

    if friendship:
        db.delete(friendship)
        # Also remove any Close Friend links if they exist
        db.query(models.CloseFriend).filter(
             or_(
                and_(models.CloseFriend.owner_id == user_a, models.CloseFriend.friend_id == user_b),
                and_(models.CloseFriend.owner_id == user_b, models.CloseFriend.friend_id == user_a)
             )
        ).delete()
        db.commit()
        return True
    
    return False

def get_friends_id_list(db: Session, user_id: str):
    friendships = db.query(models.Friendship).filter(
        and_(
            or_(models.Friendship.requester_id == user_id, models.Friendship.addressee_id == user_id),
            models.Friendship.status == 'accepted'
            )
        ).all()
    friend_ids = []
    for f in friendships:
        if f.requester_id == user_id:
            friend_ids.append(f.addressee_id)
        else:
            friend_ids.append(f.requester_id)
    return friend_ids

# --- NEW: Close Friend Helpers ---
def get_close_friend_ids(db: Session, user_id: str) -> List[str]:
    results = db.query(models.CloseFriend.friend_id).filter(models.CloseFriend.owner_id == user_id).all()
    return [r[0] for r in results]

def check_is_close_friend(db: Session, owner_id: str, friend_id: str) -> bool:
    exists = db.query(models.CloseFriend).filter(
        models.CloseFriend.owner_id == owner_id,
        models.CloseFriend.friend_id == friend_id
    ).first()
    return exists is not None

def toggle_close_friend(db: Session, owner_id: str, friend_id: str, is_close: bool):
    # Ensure they are actually friends first
    if get_friendship_status(db, owner_id, friend_id) != 'accepted':
        raise ValueError("You must be buddies to add to Close Friends.")

    if is_close:
        # Add (upsert logic basically, or check exist)
        if not check_is_close_friend(db, owner_id, friend_id):
            cf = models.CloseFriend(owner_id=owner_id, friend_id=friend_id)
            db.add(cf)
    else:
        # Remove
        db.query(models.CloseFriend).filter(
            models.CloseFriend.owner_id == owner_id,
            models.CloseFriend.friend_id == friend_id
        ).delete()
    
    db.commit()
# ---------------------------------

def get_friends(db: Session, user_id: str):
    """Get all accepted friendships with enriched Close Friend status"""
    friendships = db.query(models.Friendship).filter(
        and_(
            or_(models.Friendship.requester_id == user_id, models.Friendship.addressee_id == user_id),
            models.Friendship.status == 'accepted'
        )
    ).all()
    
    friend_ids = []
    for f in friendships:
        if f.requester_id == user_id:
            friend_ids.append(f.addressee_id)
        else:
            friend_ids.append(f.requester_id)
            
    users = db.query(models.User).filter(models.User.id.in_(friend_ids)).all()
    
    close_friend_ids = set(get_close_friend_ids(db, user_id))
    
    for u in users:
        u.is_close_friend = (u.id in close_friend_ids)
        
    return users

def search_users(db: Session, query: str, current_user_id: str):
    """Search users by name/email, excluding self"""
    search = f"%{query}%"
    return db.query(models.User).filter(
        and_(
            models.User.id != current_user_id,
            or_(
                models.User.first_name.ilike(search),
                models.User.last_name.ilike(search),
                models.User.email.ilike(search)
            )
        )
    ).limit(20).all()

def get_pending_requests(db: Session, user_id: str):
    return db.query(models.Friendship).filter(
        models.Friendship.addressee_id == user_id,
        models.Friendship.status == "pending"
    )

def get_public_user(db: Session, user_id: str):
    return db.query(models.User).filter(models.User.id == user_id).first()

def check_is_friend(db: Session, user_id_1: str, user_id_2: str) -> bool:
    """Check if two users are friends."""
    friendship = db.query(models.Friendship).filter(
        ((models.Friendship.requester_id == user_id_1) & (models.Friendship.addressee_id == user_id_2)) |
        ((models.Friendship.requester_id == user_id_2) & (models.Friendship.addressee_id == user_id_1)),
        models.Friendship.status == 'accepted'
    ).first()
    return friendship is not None

def get_friend_count(db: Session, user_id: str) -> int:
    """Calculates number of accepted friends"""
    return db.query(models.Friendship).filter(
        and_(
            or_(models.Friendship.requester_id == user_id, models.Friendship.addressee_id == user_id),
            models.Friendship.status == 'accepted'
        )
    ).count()

def get_weekly_interaction_count(db: Session, sender_id: str, action_type: str) -> int:
    """Counts how many actions of this type the user has performed in the last 7 days"""
    seven_days_ago = datetime.datetime.utcnow() - timedelta(days=7)
    return db.query(models.UserInteraction).filter(
        models.UserInteraction.sender_id == sender_id,
        models.UserInteraction.action_type == action_type,
        models.UserInteraction.created_at >= seven_days_ago
    ).count()

def perform_social_action(db: Session, sender_id: str, recipient_id: str, action: str) -> bool:
    """
    Performs 'nudge' or 'spot'. Enforces limits.
    Returns True if successful, False (or raises exception) if failed.
    """
    # 1. Enforce Limits (3 per week)
    count = get_weekly_interaction_count(db, sender_id, action)
    if count >= 3:
        raise ValueError(f"You have used all your {action}s for the week!")

    # 2. Check Spam (Optional - 1 per day per person)
    one_day_ago = datetime.datetime.utcnow() - timedelta(days=1)
    recent = db.query(models.UserInteraction).filter(
        models.UserInteraction.sender_id == sender_id,
        models.UserInteraction.recipient_id == recipient_id,
        models.UserInteraction.action_type == action,
        models.UserInteraction.created_at >= one_day_ago
    ).first()
    
    if recent:
        raise ValueError(f"You already sent a {action} to this user today!")

    # 3. Create Interaction Record
    interaction = models.UserInteraction(
        id=str(uuid.uuid4()),
        sender_id=sender_id,
        recipient_id=recipient_id,
        action_type=action
    )
    db.add(interaction)

    # 4. Increment User Counters
    recipient = crud_user.get_user(db, recipient_id)
    sender = crud_user.get_user(db, sender_id)
    
    if action == 'nudge':
        recipient.nudge_count += 1
        title = "Someone is thinking of you!"
        # Cheeky messages
        messages = [
            f"{sender.first_name} thinks you're slacking. Get to the gym!",
            f"{sender.first_name} says: Those weights won't lift themselves.",
            f"Reminder from {sender.first_name}: Your muscles are shrinking as we speak.",
            f"{sender.first_name} is nudging you. Don't let them down!",
            f"Hey! {sender.first_name} noticed you haven't logged a workout lately."
        ]
        msg = random.choice(messages)
        
    elif action == 'spot':
        recipient.spot_count += 1
        title = "You've been Spotted!"
        msg = f"{sender.first_name} spotted you! Keep crushing it! 💪"

    db.add(recipient)
    
    # 5. Send Notification
    crud_notification.create_notification(
        db=db,
        recipient_id=recipient_id,
        sender_id=sender_id,
        type=action.upper(), # NUDGE or SPOT
        title=title,
        message=msg,
        reference_id=interaction.id
    )

    try:
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise e