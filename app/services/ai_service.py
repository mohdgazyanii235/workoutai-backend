from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# --- NEW: Define a custom exception ---
class InvalidWorkoutException(ValueError):
    """Custom exception for non-workout text."""
    pass
# -------------------------------------


class InvalidVoiceLogException(ValueError):
    pass

# Define the desired data structure for a single exercise set
class ExerciseSet(BaseModel):
    exercise_name: str = Field(description="The name of the exercise performed, e.g., 'Bench Press'")
    reps: int = Field(description="The number of repetitions performed in the set.")
    weight: float = Field(description="The weight used for the set.")
    weight_unit: str = Field(description="The unit of weight, e.g., 'kg' or 'lbs'.")
    sets: int = Field(description="number of sets of that exercise")

class CardioLog(BaseModel):
    exercise_name: str = Field(description="The name of the cardio exercise, e.g., 'Running', 'Rowing'")
    duration_minutes: Optional[float] = Field(description="The duration of the exercise in minutes. e.g., '20 min' becomes 20.0")
    speed: Optional[float] = Field(description="The speed, e.g., 10")
    pace: Optional[str] = Field(description="The pace, e.g., '5:30', '8:10'.")
    pace_unit: Optional[str] = Field(description="The unit of measurement for pace, this can either be Min/Mile or Min/KM")
    distance: Optional[float] = Field(description="The distance.")
    distance_unit: Optional[str] = Field(description="The unit of distance, this can either be Kilometer(s) or Mile(s)")
    laps: Optional[int] = Field(description="The number of laps.")

class VoiceLog(BaseModel):
    cardio: List[CardioLog] = Field(description="A list of all cardio exercises in the workout.")
    sets: List[ExerciseSet] = Field(description="A list of all the exercise sets in the workout.")
    note: str = Field(description="The user's notes on the workout.")
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

# Initialize the OpenAI model
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2)

# Set up a Pydantic parser
parser = PydanticOutputParser(pydantic_object=VoiceLog)


def structured_log_text(text: str) -> VoiceLog:

    print(text)

    prompt_template = """
    You are an expert JSON Parser as well as an expert fitness assistant. Your task is to parse a user's raw text description into a JSON object depending on what the user has said.
    In this situation the user can do the following things:
    1) Narrate a workout that they did (strenght exercises).
    2) Narrate a cardio session (e.g., running, swimming, rowing).
    3) Update their weight
    4) Update their bench press 1 rep max.
    5) Update their squat 1 rep max.
    6) Update their deadlift 1 rep max.
    7) Update their fat percentage.

    IMPORTANT: Only output the JSON object. Do not include any other text, greetings, or explanations.
    Here is an example:
    User input: "today I a chest workout when I started with a 20 min 1 mile run, then I did bench press 3 sets of 10 at 80kg. Overall I had a great workout."
    Your output:
    {{
        "cardio": [
            {{
                "exercise_name": "Running",
                "duration_minutes": 20.0,
                "speed": null,
                "pace": null,
                "pace_unit": null, // this can either be null, Min/KM or Min/Mile
                "distance": 1.0,
                "distance_unit": "mile",
                "laps": null
            }}
        ],
        "sets": [
            {{
                "exercise_name": "Bench Press",
                "reps": 10,
                "weight": 80,
                "weight_unit": "kg",
                "sets": 3
            }}
        ],
        "note": "You had a great workout starting with a run!",
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
        "comment": "Your chest workout and run are logged! Well done!"
    }}

    Notice how above when the user just narrated their workout the fields updated_weight and updated_bench_1rm returned null. However see the example below:

    User Input: "Hi today I recorded my weight and it is now 90 Kgs!"

    Your Output:
    {{
        "cardio": [], // this has to be a list.
        "sets": [], // this has to be a list.
        "note": "", // this has to be a string
        "workout_type": "", // this has to be a string
        "updated_weight": 90, // this has to be a number or null
        "updated_weight_unit": "" // this has to be a string
        "updated_bench_1rm: null, // this has to be a number or null
        "updated_bench_1rm_unit": "" // this has to be a string
        "updated_squat_1rm": null, // this can be a number or null
        "updated_squat_1rm_unit": "" // this has to be a string
        "updated_deadlift_1rm": null, // this can be a number or null
        "updated_deadlift_1rm_unit": "" // this has to be a string
        "updated_fat_percentage": null // this has to be a number between 1 and 100
        "comment": "Congratulations on your weight drop!"
    }}

    Notice above how when the user only updated their weight every other irrelevant field was left null or empty!
    It is important for you to provide all the fields that I have listed but I just want you to keep them equal to null or empty lists/strings.
    Also, it is very important to make sure that the 'workout_type' field is populated. This should be a generic and should be a good description of the workout regardless of what the user trained.

    
    - "duration_minutes" should be a float (e.g., "20 min" -> 20.0).
    - "distance_unit" should be "km", "miles", "meters", or null.
    - If a user specifies duration, extract it to "duration_minutes".
    - If a user does a body weight exercise, parse the weight to be 0 and unit to be 'kg'.
    - If the user ever fails to specify the unit for weight, always default the 'weight_unit' value to 'kg'.
    - "comment" field is for you to write a sentence as a response to the users log, make sure this is motivating and always ends with something like 'your new weight is tracked' or 'you workout has been logged', be logical and creative!
    - "note" field is for you to write a simple workout summary with motivating text and some key pointers from the workout! Something the user can remember.

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
        print(structured_response)

        return structured_response
    except Exception as e:
        print(f"Error processing text with LangChain after retries: {e}")
        # --- NEW: Treat any other parsing error as an invalid attempt ---
        raise InvalidVoiceLogException("Nice try")
        # -----------------------------------------------------------