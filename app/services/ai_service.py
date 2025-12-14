from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv
from app.schemas import workout as workout_schemas

load_dotenv()

class InvalidWorkoutException(ValueError):
    """Custom exception for non-workout text."""
    pass

class InvalidVoiceLogException(ValueError):
    pass

# We redefine these pydantic models here locally for Langchain 
# because they are slightly different in purpose (extraction vs API schema)
# or we could import them if they match perfectly. 
# Looking at your schemas, VoiceLog in ai_service is very rich.
# Let's keep them local to avoid coupling AI extraction logic with API response schemas too tightly, 
# or ensure they match. For now, I'll keep them as they were in ai_service.py to be safe.

class ExerciseSet(BaseModel):
    exercise_name: str = Field(description="The name of the exercise performed, e.g., 'Bench Press'")
    reps: int = Field(description="The number of repetitions performed in the set.")
    weight: float = Field(description="The weight used for the set.")
    weight_unit: str = Field(description="The unit of weight, e.g., 'kg' or 'lbs'.")
    sets: int = Field(description="The set number (if granular) OR the total number of sets (if summary).")

class CardioLog(BaseModel):
    exercise_name: str = Field(description="The name of the cardio exercise, e.g., 'Running', 'Rowing'")
    duration_minutes: Optional[float] = Field(description="The duration of the exercise in minutes. e.g., '20 min' becomes 20.0")
    speed: Optional[float] = Field(description="The speed, e.g., 10")
    pace: Optional[str] = Field(description="The pace, e.g., '5:30', '8:10'.")
    pace_unit: Optional[str] = Field(description="The unit for pace. EXTRACT this from text (e.g. 'per mile' -> 'Min/Mile', 'per km' -> 'Min/KM'). Default to 'Min/KM' only if unspecified.")
    distance: Optional[float] = Field(description="The distance.")
    distance_unit: Optional[str] = Field(description="The unit of distance, this can either be Kilometer(s) or Mile(s)")
    laps: Optional[int] = Field(description="The number of laps.")

class VoiceLog(BaseModel):
    cardio: List[CardioLog] = Field(description="A list of all cardio exercises in the workout.")
    sets: List[ExerciseSet] = Field(description="A list of all the exercise sets in the workout.")
    note: str = Field(description="The user's notes on the workout.")
    visibility: str = Field(description="The visibilty should be 'private' by default but 'public' if the users says it.")
    workout_type: str = Field(description="This is the type of workout the user did.")
    updated_weight: float | None = Field(description="This is filled up if the user updated their weight.")
    updated_weight_unit: str = Field(description="The unit of the users updated weight")
    updated_bench_1rm: float | None = Field(description="This is filled up if the user updated bench press 1rm.")
    updated_bench_1rm_unit: str = Field(description="The unit of the users updated bench press 1rm.")
    updated_squat_1rm: float | None = Field(description="This is filled up if the user updated squat 1rm.")
    updated_squat_1rm_unit: str = Field(description="The unit of the users updated squat 1rm.")
    updated_deadlift_1rm: float | None = Field(description="This is filled up if the user updated deadlift 1rm.")
    updated_deadlift_1rm_unit: str = Field(description="The unit of the users updated deadlift 1rm.")
    updated_fat_percentage: float | None = Field(description="The users fat percentage.")
    comment: str = Field(description="This is the AIs comment on the users log.")

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2)
parser = PydanticOutputParser(pydantic_object=VoiceLog)

def structured_log_text(text: str) -> workout_schemas.VoiceLog: # Return the schema VoiceLog
    # ... prompt template code ...
    prompt_template = """
    You are an expert JSON Parser and fitness assistant. Your task is to parse a user's raw text into a JSON object.
    The user can log two types of strength sets:
    1.  **Straight Sets (Summary):** "3 sets of 10 at 80kg".
    2.  **Pyramid Sets (Granular):** "12 reps at 50kg, 10 reps at 60, 8 reps at 70".

    You must handle both by populating the "sets" array in the JSON.
    -   For **Straight Sets**, return ONE object in the array. `sets` field = total sets.
    -   For **Pyramid Sets**, return MULTIPLE objects in the array. `sets` field = the set number (1, 2, 3...).

    ---
    **EXAMPLE 1: Straight/Summary Set**
    User input: "today I did bench press 3 sets of 10 at 80kg. Overall I had a great workout. I would like to share this with my buddies!" 
    Your output:
    {{
        "cardio": [],
        "sets": [
            {{
                "exercise_name": "Bench Press",
                "reps": 10,
                "weight": 80,
                "weight_unit": "kg",
                "sets": 3
            }}
        ],
        "note": "You had a great workout!",
        "workout_type": "Chest",
        "updated_weight": null,
        "updated_weight_unit": "",
        "updated_bench_1rm": null,
        "updated_bench_1rm_unit": "",
        "updated_squat_1rm": null,
        "updated_squat_1rm_unit": "",
        "updated_deadlift_1rm": null,
        "updated_deadlift_1rm_unit": "",
        "updated_fat_percentage": null,
        "comment": "Your chest workout is logged! Well done!",
        "visibility": "public" 

    }}
    ---
    **EXAMPLE 2: Pyramid/Granular Sets + Cardio**
    User input: "I started with a 20 min 2 mile run with an average pace of 10 minutes per mile , then I did dumbbell press 12 reps at 50kg, 10 reps at 60kg, and 8 reps at 70kg."
    Your output:
    {{
        "cardio": [
            {{
                "exercise_name": "Running",
                "duration_minutes": 20.0,
                "speed": null,
                "pace": "10",
                "pace_unit": "Min/Mile", 
                "distance": 2.0,
                "distance_unit": "Mile",
                "laps": null
            }}
        ],
        "sets": [
            {{
                "exercise_name": "Dumbbell Press",
                "reps": 12,
                "weight": 50,
                "weight_unit": "kg",
                "sets": 1
            }},
            {{
                "exercise_name": "Dumbbell Press",
                "reps": 10,
                "weight": 60,
                "weight_unit": "kg",
                "sets": 2
            }},
            {{
                "exercise_name": "Dumbbell Press",
                "reps": 8,
                "weight": 70,
                "weight_unit": "kg",
                "sets": 3
            }} 
        ],
        "note": "Great pyramid sets on the dumbbell press after your run!",
        "workout_type": "Chest",
        "updated_weight": null,
        "updated_weight_unit": "",
        "updated_bench_1rm": null,
        "updated_bench_1rm_unit": "",
        "updated_squat_1rm": null,
        "updated_squat_1rm_unit": "",
        "updated_deadlift_1rm": null,
        "updated_deadlift_1rm_unit": "",
        "updated_fat_percentage": null,
        "comment": "Your run and pyramid set workout has been logged!",
        "visibility": "private" 
    }}
    ---
    **EXAMPLE 3: Weight Update Only**
    User Input: "Hi today I recorded my weight and it is now 90 Kgs!"
    Your Output:
    {{
        "cardio": [],
        "sets": [],
        "note": "",
        "workout_type": "",
        "updated_weight": 90,
        "updated_weight_unit": "kg",
        "updated_bench_1rm": null,
        "updated_bench_1rm_unit": "",
        "updated_squat_1rm": null,
        "updated_squat_1rm_unit": "",
        "updated_deadlift_1rm": null,
        "updated_deadlift_1rm_unit": "",
        "updated_fat_percentage": null,
        "comment": "Your new weight of 90kg has been tracked!",
        "visibility": "private" 
    }}
    ---
    
    **RULES:**
    -   **"sets" field in the JSON is critical.** For "3 sets of 10", return ONE object with `"sets": 3`. For "10 reps, 8 reps, 6 reps", return THREE objects, with `"sets": 1`, `"sets": 2`, and `"sets": 3` respectively.
    -   If the user does a body weight exercise, parse the weight to be 0 and unit to be 'kg'.
    -   If the user ever fails to specify the unit for weight, always default the 'weight_unit' value to 'kg'.
    -   "comment" field is for you to write a single, motivating sentence as a response to the users log.
    -   "note" field is for you to write a simple workout summary with motivating text and a simple summary of the workout.
    -   Remember, if a user has logged a workout, or a cardio session, the workout_type field is mandatory this should be the name of the workout, like chest, cardio, running etc.
    -   If the user only updates a metric (like weight), leave `cardio`, `sets`, `note`, and `workout_type` as empty lists or strings.
    -   **Pace Units:** If the user specifies "per mile", set `pace_unit` to "Min/Mile". If "per km" or "per kilometer", set to "Min/KM". Only default to "Min/KM" if the user mentions pace but NOT the unit.
    -   It is VERY IMPORTANT to understand that workouts sets can be of 2 types, straight and pyramid. Straigt is when the user simply says 'I did 3 sets 12 reps of 50kgs of x", you need to create and object that looks like the following:
    {{
        "sets": [
            {{
                "exercise_name": "Bench Press",
                "reps": 10,
                "weight": 80,
                "weight_unit": "kg",
                "sets": 3
            }}
        ],..... Rest of the JSON
    }}
    - but if the user says they did a pyramid set, and they will usually say that by describing the entire set like 'the first set I did 12 reps and 50 kgs, the second set I did xxxx'. In this case the object should look like the following:
    {{
        "sets": [
            {{
                "exercise_name": "Dumbbell Press",
                "reps": 12,
                "weight": 50,
                "weight_unit": "kg",
                "sets": 1
            }},
            {{
                "exercise_name": "Dumbbell Press",
                "reps": 10,
                "weight": 60,
                "weight_unit": "kg",
                "sets": 2
            }},
            {{
                "exercise_name": "Dumbbell Press",
                "reps": 8,
                "weight": 70,
                "weight_unit": "kg",
                "sets": 3
            }} 
        ],..... Rest of the JSON
    }}


    Now parse the following users description:
    "{user_text}"

    Please provide the output in the following format:
    {format_instructions}
    """
    
    prompt = ChatPromptTemplate.from_template(
        template=prompt_template,
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | llm | parser

    try:
        chain_with_retry = chain.with_retry(
            retry_if_exception_type=(Exception,),
            stop_after_attempt=2
        )
        structured_response = chain_with_retry.invoke({"user_text": text})
        
        # We assume the AI output model matches the schema VoiceLog structure sufficiently 
        # to be converted or treated as such.
        # Since we use the local VoiceLog for the parser, it returns that.
        return structured_response # Returns the local Pydantic model
    except Exception as e:
        print(f"Error processing text with LangChain after retries: {e}")
        raise InvalidVoiceLogException("Nice try")