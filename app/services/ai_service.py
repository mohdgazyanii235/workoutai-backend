from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List
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

# # Define the desired data structure for the entire workout
# class WorkoutLog(BaseModel):
#     sets: List[ExerciseSet] = Field(description="A list of all the exercise sets in the workout.")
#     note: str = Field(description="The user's notes on the workout.")
#     workout_type: str = Field(description="This is the type of workout the user did.")


class VoiceLog(BaseModel):
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
    1) Narrate a workout that they did.
    2) Update their weight
    3) Update their bench press 1 rep max.
    4) Update their squat 1 rep max.
    5) Update their deadlift 1 rep max.
    6) Update their fat percentage.

    IMPORTANT: Only output the JSON object. Do not include any other text, greetings, or explanations.
    Here is an example:
    User input: "I did a chest workout, I did bench press 3 sets of 10 at 80kg, then 2 sets of bicep curls at 15 lbs for 12 reps. Overall I had a great workout but I think I could have pushed harder"
    Your output:
    {{
        "sets": [
            {{
                "exercise_name": "Bench Press",
                "reps": 10,
                "weight": 80,
                "weight_unit": "kg",
                "sets": 3
            }},
            {{
                "exercise_name": "Bicep Curls",
                "reps": 12,
                "weight": 15,
                "weight_unit": "lbs",
                "sets": 2
            }}
        ],
        "note": "You said that you had a great workout but next time focus on having some simple carbs before your workout so you can push harder!",
        "workout_type": "Chest", // this has to be a string
        "updated_weight": null, // this can either be a number or null
        "updated_weight_unit": "", // this has to be a string
        "updated_bench_1rm": null, // this can be a number or null
        "updated_bench_1rm_unit": "" // this has to be a string
        "updated_squat_1rm": null, // this can be a number or null
        "updated_squat_1rm_unit": "" // this has to be a string
        "updated_deadlift_1rm": null, // this can be a number or null
        "updated_deadlift_1rm_unit": "" // this has to be a string
        "updated_fat_percentage": null // this has to be a number between 1 and 100
        "comment": "Your chest workout is logged! Well done!"
    }}

    Notice how above when the user just narrated their workout the fields updated_weight and updated_bench_1rm returned null. However see the example below:

    User Input: "Hi today I recorded my weight and it is now 90 Kgs!"

    Your Output:
    {{
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

    Notice above how when the user only updated their weight every other irrelevant field was left null! It is important for you to provide all the fields that I have listed but I just want you to keep them equal to null.
    
    Finally the same applies to other update fields like updated_bench_1rm as well! If the user says they can now lift heavier in the bench press for example I want the updated_bench_1rm field to log that.
    
    and obviosly the same rule applies if the user tracks their squat1rm, their deadlift1rm, or even their fat_percentage!

    It is important for you to note that sometimes a user may parse do a body weight exercise, in which case you want to parse the weight to be 0 and unit to be kgs.
    Moreover if the user ever fails to specify the unit, always default the the unit value to kgs.

    finally, the comment field is for you to write a very small sentence as a response to the users log!
    
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

# def structure_workout_text(text: str) -> WorkoutLog:

#     prompt_template = """
#     You are an expert fitness assistant. Your task is to parse a user's raw text description of their workout
#     and extract the details for each exercise set into a structured JSON format. Further more, the user may also provide some notes about the workout which I want you to store in your response JSON.
#     Make sure the notes string that you generate is a short summary and sometimes can include some suggestions.

#     IMPORTANT: Only output the JSON object. Do not include any other text, greetings, or explanations.

#     Here is an example:
#     User input: "I did a chest workout, I did bench press 3 sets of 10 at 80kg, then 2 sets of bicep curls at 15 lbs for 12 reps. Overall I had a great workout but I think I could have pushed harder"
#     Your output:
#     {{
#         "sets": [
#             {{
#                 "exercise_name": "Bench Press",
#                 "reps": 10,
#                 "weight": 80,
#                 "weight_unit": "kg",
#                 "sets": 3
#             }},
#             {{
#                 "exercise_name": "Bicep Curls",
#                 "reps": 12,
#                 "weight": 15,
#                 "weight_unit": "lbs",
#                 "sets": 2
#             }}
#         ],
#         "note": "You said that you had a great workout but next time focus on having some simple carbs before your workout so you can push harder!",
#         "workout_type": "Chest"
#     }}
#     It is important for you to note that sometimes a user may parse do a body weight exercise, in which case you want to parse the weight to be 0 and unit to be kgs.
#     Now, parse the following user workout description:
#     "{user_text}"

#     Please provide the output in the following format:
#     {format_instructions}
#     """

#     prompt = ChatPromptTemplate.from_template(
#         template=prompt_template,
#         partial_variables={"format_instructions": parser.get_format_instructions()},
#     )

#     chain = prompt | llm | parser
    
#     try:
#         chain_with_retry = chain.with_retry(
#             retry_if_exception_type=(Exception,),
#             stop_after_attempt=2
#         )
#         structured_response = chain_with_retry.invoke({"user_text": text})
        
#         # --- NEW: Check if the 'sets' list is empty ---
#         if not structured_response.sets:
#             raise InvalidWorkoutException("Nice try")
#         # ---------------------------------------------
            
#         print(structured_response)
#         return structured_response
        
#     # --- NEW: Catch our custom exception first ---
#     except InvalidWorkoutException as e:
#         print(f"Invalid workout text detected: {e}")
#         raise e  # Re-raise it so the API route can catch it
#     # -------------------------------------------
#     except Exception as e:
#         print(f"Error processing text with LangChain after retries: {e}")
#         # --- NEW: Treat any other parsing error as an invalid attempt ---
#         raise InvalidWorkoutException("Nice try")
#         # -----------------------------------------------------------



