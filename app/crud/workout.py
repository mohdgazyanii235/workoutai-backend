from sqlalchemy.orm import Session
from sqlalchemy import desc
from app import models
from app.schemas import workout as workout_schemas
import uuid
import datetime
from typing import Optional
from . import user as crud_user
from . import social as crud_social
from . import notification as crud_notification
from . import admin as crud_admin # for rubbish log logic

# --- CONFIGURATION ---
WORKOUT_CONSOLIDATION_BUFFER_MINUTES = 30

def update_workout(
    db: Session,
    workout_id: str,
    workout_update: workout_schemas.WorkoutUpdate,
    user_id: str # Ensure only the owner can update
) -> Optional[models.Workout]:

    # Fetch the existing workout, ensuring it belongs to the current user
    db_workout = db.query(models.Workout).filter(
        models.Workout.id == workout_id,
        models.Workout.user_id == user_id
    ).first()

    if not db_workout:
        return None # Workout not found or doesn't belong to the user

    # 1. Update Workout fields (notes, workout_type, status) if provided
    update_data = workout_update.model_dump(exclude_unset=True) # Get only fields present in the request
    if "notes" in update_data:
        db_workout.notes = update_data["notes"] # Handles null correctly
    if "workout_type" in update_data:
        db_workout.workout_type = update_data["workout_type"]
    if "status" in update_data:
        db_workout.status = update_data["status"]
    
    # Allow updating the date manually as well
    if "created_at" in update_data and update_data["created_at"]:
        db_workout.created_at = update_data["created_at"]

    # --- MODIFIED: Handle Notifications for Public AND Close Friends ---
    if "visibility" in update_data:
        old_visibility = db_workout.visibility
        new_visibility = update_data["visibility"]
        db_workout.visibility = new_visibility
        
        current_user = crud_user.get_user(db, user_id)
        
        # Scenario 1: Private -> Public (Notify ALL friends)
        if old_visibility != "public" and new_visibility == "public":
            friend_id_list = crud_social.get_friends_id_list(db, user_id)
            for friend_id in friend_id_list:
                crud_notification.create_notification(
                    db=db,
                    recipient_id=friend_id,
                    sender_id=user_id,
                    type="WORKOUT_SHARE",
                    title="Your Buddy Shared a Workout!",
                    message=f"{current_user.first_name} just shared a workout! Time to spot!",
                    reference_id=db_workout.id
                )
        
        # Scenario 2: Private -> Close Friends (Notify ONLY close friends)
        elif old_visibility == "private" and new_visibility == "close_friends":
            close_friend_ids = crud_social.get_close_friend_ids(db, user_id)
            for friend_id in close_friend_ids:
                crud_notification.create_notification(
                    db=db,
                    recipient_id=friend_id,
                    sender_id=user_id,
                    type="WORKOUT_SHARE",
                    title="Close Friends Only!",
                    message=f"{current_user.first_name} shared a workout with close friends.",
                    reference_id=db_workout.id
                )
    # ----------------------------------------------------------------

    db.add(db_workout)

    # 2. Handle Exercise Sets update if 'sets' field is present in the request
    if workout_update.sets is not None:
        current_sets_db = {s.id: s for s in db_workout.sets}
        incoming_set_ids = set()

        for set_data in workout_update.sets:
            if set_data.id and set_data.id in current_sets_db:
                # --- UPDATE existing set ---
                db_set = current_sets_db[set_data.id]
                db_set.exercise_name = set_data.exercise_name
                db_set.set_number = set_data.set_number 
                db_set.reps = set_data.reps
                db_set.weight = set_data.weight
                db_set.weight_unit = set_data.weight_unit
                db.add(db_set) 
                incoming_set_ids.add(set_data.id) 
            elif not set_data.id:
                # --- CREATE new set ---
                db_new_set = models.ExerciseSet(
                    id=str(uuid.uuid4()), 
                    exercise_name=set_data.exercise_name,
                    set_number=set_data.set_number, 
                    reps=set_data.reps,
                    weight=set_data.weight,
                    weight_unit=set_data.weight_unit,
                    workout_id=db_workout.id 
                )
                db.add(db_new_set)

        # --- DELETE sets that are in the DB but were NOT in the incoming payload ---
        set_ids_to_delete = current_sets_db.keys() - incoming_set_ids
        for set_id in set_ids_to_delete:
            db.delete(current_sets_db[set_id])

    # Handle Cardio Sessions update
    if workout_update.cardio_sessions is not None:
        current_cardio_db = {c.id: c for c in db_workout.cardio_sessions}
        incoming_cardio_ids = set()

        for cardio_data in workout_update.cardio_sessions:
            if cardio_data.id and cardio_data.id in current_cardio_db:
                # --- UPDATE existing cardio session ---
                db_cardio = current_cardio_db[cardio_data.id]
                db_cardio.name = cardio_data.name
                db_cardio.duration_minutes = cardio_data.duration_minutes
                db_cardio.distance = cardio_data.distance
                db_cardio.distance_unit = cardio_data.distance_unit
                db_cardio.speed = cardio_data.speed
                db_cardio.pace = cardio_data.pace
                db_cardio.pace_unit = cardio_data.pace_unit
                db_cardio.laps = cardio_data.laps
                db.add(db_cardio)
                incoming_cardio_ids.add(cardio_data.id)
            elif not cardio_data.id:
                # --- CREATE new cardio session ---
                db_new_cardio = models.CardioSession(
                    id=str(uuid.uuid4()),
                    name=cardio_data.name,
                    duration_minutes=cardio_data.duration_minutes,
                    distance=cardio_data.distance,
                    distance_unit=cardio_data.distance_unit,
                    speed=cardio_data.speed,
                    pace=cardio_data.pace,
                    pace_unit=cardio_data.pace_unit,
                    laps=cardio_data.laps,
                    workout_id=db_workout.id
                )
                db.add(db_new_cardio)

        # --- DELETE cardio sessions not in the payload ---
        cardio_ids_to_delete = current_cardio_db.keys() - incoming_cardio_ids
        for cardio_id in cardio_ids_to_delete:
            db.delete(current_cardio_db[cardio_id])


    try:
        db.commit()
        db.refresh(db_workout) 
        return db_workout
    except Exception as e:
        db.rollback() 
        print(f"Error updating workout: {e}") 
        raise e 

def get_visible_workouts_for_user(db: Session, target_user_id: str, viewer_id: str, limit: int = 10):
    """
    Fetches workouts of target_user_id that are visible to viewer_id.
    """
    # 1. Check if viewer is a close friend of target
    is_close_friend = crud_social.check_is_close_friend(db, owner_id=target_user_id, friend_id=viewer_id)
    
    # 2. Define visibility criteria
    visible_types = ["public"]
    if is_close_friend:
        visible_types.append("close_friends")
    
    # 3. Query
    return db.query(models.Workout).filter(
        models.Workout.user_id == target_user_id,
        models.Workout.visibility.in_(visible_types)
    ).order_by(models.Workout.created_at.desc()).limit(limit).all()

def create_workout_from_log(db: Session, log: workout_schemas.VoiceLog, user_id: str, created_at: Optional[datetime.datetime] = None) -> models.Workout:
    
    # Determine Status
    status = "completed"
    if created_at:
        # Check if created_at is in the future
        now = datetime.datetime.now(datetime.timezone.utc)
        target_time = created_at
        if target_time.tzinfo is None:
             target_time = target_time.replace(tzinfo=datetime.timezone.utc)
        
        if target_time > now:
            status = "planned"

    db_workout = models.Workout(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notes=log.note,
        workout_type=log.workout_type,
        created_at=created_at,
        visibility=log.visibility,
        status=status
    )
    db.add(db_workout)
    
    try:
        db.commit()
        db.refresh(db_workout)
    except Exception as e:
        db.rollback()
        print(f"Error creating parent workout from log: {e}")
        raise e

    if log.sets:
        for i, ai_set in enumerate(log.sets):
            db_exercise_set = models.ExerciseSet(
                id=str(uuid.uuid4()),
                exercise_name=ai_set.exercise_name,
                set_number=ai_set.sets,
                reps=ai_set.reps,
                weight=ai_set.weight,
                weight_unit=ai_set.weight_unit,
                workout_id=db_workout.id
            )
            db.add(db_exercise_set)

    if log.cardio:
        for ai_cardio in log.cardio:
            db_cardio_session = models.CardioSession(
                id=str(uuid.uuid4()),
                name=ai_cardio.exercise_name,
                duration_minutes=ai_cardio.duration_minutes,
                speed=ai_cardio.speed,
                pace=ai_cardio.pace,
                pace_unit=ai_cardio.pace_unit,
                distance=ai_cardio.distance,
                distance_unit=ai_cardio.distance_unit,
                laps=ai_cardio.laps,
                workout_id=db_workout.id
            )
            db.add(db_cardio_session)

    try:
        db.commit()
        db.refresh(db_workout)
        
        # --- MODIFIED: Handle Notifications for Public/Close Friends ---
        current_user = crud_user.get_user(db, user_id)
        
        if log.visibility == "public":
            friend_ids = crud_social.get_friends_id_list(db, user_id)
            for friend_id in friend_ids:
                crud_notification.create_notification(
                    db=db,
                    recipient_id=friend_id,
                    sender_id=user_id,
                    type="WORKOUT_SHARE",
                    title="Your Buddy Just Logged a workout!",
                    message=f"{current_user.first_name} just crushed a workout! Spot them to show your support.",
                    reference_id=db_workout.id
                )
        elif log.visibility == "close_friends":
            close_friend_ids = crud_social.get_close_friend_ids(db, user_id)
            for friend_id in close_friend_ids:
                crud_notification.create_notification(
                    db=db,
                    recipient_id=friend_id,
                    sender_id=user_id,
                    type="WORKOUT_SHARE",
                    title="Close Friends Workout!",
                    message=f"{current_user.first_name} shared a private workout with you.",
                    reference_id=db_workout.id
                )
        # -------------------------------------------------------------
                
    except Exception as e:
        db.rollback()
        print(f"Error creating workout children from log: {e}")
        raise e
        
    return db_workout

def append_to_existing_workout(db: Session, workout: models.Workout, log: workout_schemas.VoiceLog) -> models.Workout:
    """
    Appends new sets and cardio sessions from a log to an existing workout.
    Also appends any new notes to the existing notes.
    """
    # 1. Append Notes
    if log.note:
        if workout.notes:
            workout.notes += f"\n\n[Update]: {log.note}"
        else:
            workout.notes = log.note
    
    # 2. Append Sets
    if log.sets:
        for ai_set in log.sets:
            db_exercise_set = models.ExerciseSet(
                id=str(uuid.uuid4()),
                exercise_name=ai_set.exercise_name,
                set_number=ai_set.sets, 
                reps=ai_set.reps,
                weight=ai_set.weight,
                weight_unit=ai_set.weight_unit,
                workout_id=workout.id
            )
            db.add(db_exercise_set)

    # 3. Append Cardio
    if log.cardio:
        for ai_cardio in log.cardio:
            db_cardio_session = models.CardioSession(
                id=str(uuid.uuid4()),
                name=ai_cardio.exercise_name,
                duration_minutes=ai_cardio.duration_minutes,
                speed=ai_cardio.speed,
                pace=ai_cardio.pace,
                pace_unit=ai_cardio.pace_unit,
                distance=ai_cardio.distance,
                distance_unit=ai_cardio.distance_unit,
                laps=ai_cardio.laps,
                workout_id=workout.id
            )
            db.add(db_cardio_session)

    try:
        db.commit()
        db.refresh(workout)
        print(f"Successfully consolidated log into workout {workout.id}")
        return workout
    except Exception as e:
        db.rollback()
        print(f"Error appending to workout: {e}")
        raise e

def manage_voice_log(db: Session, voice_log: workout_schemas.VoiceLog, user_id: str, created_at: Optional[datetime.datetime] = None):
    # 1. Determine the timestamp
    # Check if the AI detected a SCHEDULED date (e.g., "Schedule for Jan 18th")
    if getattr(voice_log, "scheduled_date", None):
        # Create a datetime from the date (set time to noon or start of day to avoid timezone confusion, or keep as 00:00)
        # Using noon to be safe against minor timezone shifts
        d = voice_log.scheduled_date
        logging_timestamp = datetime.datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=datetime.timezone.utc)
        print(f"Scheduling workout for: {logging_timestamp}")
        is_future_workout = True
    else:
        # Standard log
        logging_timestamp = created_at if created_at else datetime.datetime.now(datetime.timezone.utc)
        is_future_workout = False

    db_user = crud_user.get_user(db, id=user_id)
    entry_date = logging_timestamp.date() 
    date_str = entry_date.isoformat()
    
    if not db_user:
        print(f"User not found with ID: {user_id}")
        return None

    # Only update user metrics if it's NOT a future workout. 
    # Usually you don't update your "current weight" based on a plan for next week.
    if not is_future_workout:
        if voice_log.updated_weight:
            crud_user.update_history_tracked_field(db, db_user, voice_log.updated_weight, date_str, "weight")
        
        if voice_log.updated_bench_1rm:
            crud_user.update_history_tracked_field(db, db_user, voice_log.updated_bench_1rm, date_str, "bench_1rm")

        if voice_log.updated_squat_1rm:
            crud_user.update_history_tracked_field(db, db_user, voice_log.updated_squat_1rm, date_str, "squat_1rm")

        if voice_log.updated_deadlift_1rm:
            crud_user.update_history_tracked_field(db, db_user, voice_log.updated_deadlift_1rm, date_str, "deadlift_1rm")

        if voice_log.updated_fat_percentage:
            crud_user.update_history_tracked_field(db, db_user, voice_log.updated_fat_percentage, date_str, "fat_percentage")

    # Check for sets OR cardio
    if (voice_log.sets and len(voice_log.sets) > 0) or (voice_log.cardio and len(voice_log.cardio) > 0):
        # --- NEW CONSOLIDATION LOGIC ---
        # Skip consolidation if this is a future scheduled workout
        consolidated = False
        
        if not is_future_workout:
            # 1. Find most recent workout for this user
            most_recent_workout = db.query(models.Workout).filter(
                models.Workout.user_id == user_id
            ).order_by(desc(models.Workout.created_at)).first()

            if most_recent_workout:
                # 2. Check time difference
                last_time = most_recent_workout.created_at
                current_time = logging_timestamp
                
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=datetime.timezone.utc)
                if current_time.tzinfo is None:
                    current_time = current_time.replace(tzinfo=datetime.timezone.utc)

                diff = current_time - last_time
                
                if diff < datetime.timedelta(minutes=WORKOUT_CONSOLIDATION_BUFFER_MINUTES) and diff >= datetime.timedelta(0):
                    # 3. Consolidate!
                    print(f"Consolidating log into recent workout {most_recent_workout.id} (Diff: {diff})")
                    append_to_existing_workout(db, most_recent_workout, voice_log)
                    consolidated = True
        
        if not consolidated:
            # 4. Fallback to creating a new workout (or a future scheduled one)
            create_workout_from_log(db, voice_log, user_id, logging_timestamp)
        # -------------------------------

    if not is_future_workout and not voice_log.updated_weight and not voice_log.updated_bench_1rm and not voice_log.updated_squat_1rm and not voice_log.updated_deadlift_1rm and not voice_log.updated_fat_percentage and not ((voice_log.sets and len(voice_log.sets) > 0) or (voice_log.cardio and len(voice_log.cardio) > 0)):
        crud_admin.log_rubbish_voice_log(db, user_id=user_id)
    

    return voice_log.comment

def delete_workout(db: Session, workout_id: str, user_id: str) -> models.Workout | None:
    db_workout = (
        db.query(models.Workout)
        .filter(
            models.Workout.id == workout_id,
            models.Workout.user_id == user_id
        )
        .first()
    )
    
    if not db_workout:
        return None  

    # 1. Delete the workout itself.
    db.delete(db_workout)
    
    # 2. Commit the transaction
    db.commit()
    
    return db_workout

def create_manual_workout(db: Session, workout_data: workout_schemas.WorkoutUpdate, user_id: str) -> models.Workout:
    # 1. Determine creation time
    # If the user provided a specific date/time (e.g. scheduling for future), use it.
    # Otherwise use now.
    if workout_data.created_at:
        creation_time = workout_data.created_at
    else:
        creation_time = datetime.datetime.now(datetime.timezone.utc)

    # Determine Status
    status = "completed"
    now = datetime.datetime.now(datetime.timezone.utc)
    target_time = creation_time
    if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=datetime.timezone.utc)
    
    if target_time > now:
        status = "planned"

    # 2. Create the parent Workout
    db_workout = models.Workout(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notes=workout_data.notes,
        workout_type=workout_data.workout_type,
        created_at=creation_time,
        status=status
    )
    db.add(db_workout)
    
    try:
        db.commit()
        db.refresh(db_workout)
    except Exception as e:
        db.rollback()
        print(f"Error creating parent workout: {e}")
        raise e

    # 3. Create the child ExerciseSets
    if workout_data.sets:
        for set_data in workout_data.sets:
            db_exercise_set = models.ExerciseSet(
                id=str(uuid.uuid4()),
                exercise_name=set_data.exercise_name,
                set_number=set_data.set_number,
                reps=set_data.reps,
                weight=set_data.weight,
                weight_unit=set_data.weight_unit,
                workout_id=db_workout.id 
            )
            db.add(db_exercise_set)

    # 4. Create the child CardioSessions
    if workout_data.cardio_sessions:
        for cardio_data in workout_data.cardio_sessions:
            db_cardio_session = models.CardioSession(
                id=str(uuid.uuid4()),
                name=cardio_data.name,
                duration_minutes=cardio_data.duration_minutes,
                distance=cardio_data.distance,
                distance_unit=cardio_data.distance_unit,
                speed=cardio_data.speed,
                pace=cardio_data.pace,
                pace_unit=cardio_data.pace_unit,
                laps=cardio_data.laps,
                workout_id=db_workout.id
            )
            db.add(db_cardio_session)

    # 5. Commit the transaction (for children)
    try:
        db.commit()
        db.refresh(db_workout) # Refresh to get all data
        return db_workout
    except Exception as e:
        db.rollback()
        print(f"Error creating manual workout children: {e}") 
        raise e