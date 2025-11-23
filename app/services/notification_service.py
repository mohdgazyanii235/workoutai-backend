from exponent_server_sdk import (
    PushClient,
    PushMessage,
    PushServerError,
    DeviceNotRegisteredError,
)
from sqlalchemy.orm import Session
from app import models
import logging

# Configure logging
logger = logging.getLogger(__name__)

def send_push_notification(token: str, title: str, body: str, data: dict = None):
    """
    Sends a single push notification via Expo.
    """
    if not token:
        logger.warning("Attempted to send notification but no token provided.")
        return

    try:
        response = PushClient().publish(
            PushMessage(to=token, title=title, body=body, data=data)
        )
    except PushServerError as exc:
        # Encountered some likely formatting/validation error.
        logger.error(f"PushServerError: {exc.errors}, {exc.message_data}")
    except (ConnectionError, ValueError) as exc:
        # Encountered some Connection or Value error - retry logic recommended here
        logger.error(f"Connection/Value Error sending notification: {exc}")
    except DeviceNotRegisteredError:
        # Mark the token as invalid in your DB if needed
        logger.info(f"Token {token} is no longer registered.")


def notify_friend_request(db: Session, target_user_id: str, requester_name: str):
    """
    High-level function to notify a user of a new friend request.
    """
    user = db.query(models.User).filter(models.User.id == target_user_id).first()
    
    if user and user.push_token:
        send_push_notification(
            token=user.push_token,
            title="New Buddy Request! 🏋️",
            body=f"{requester_name} wants to be your gym buddy.",
            data={"type": "friend_request", "requester_name": requester_name}
        )