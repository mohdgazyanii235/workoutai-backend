from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List

# Define the desired data structure for a single exercise set
class ExerciseSet(BaseModel):
    exercise_name: str = Field(description="The name of the exercise performed, e.g., 'Bench Press'")
    reps: int = Field(description="The number of repetitions performed in the set.")
    weight: float = Field(description="The weight used for the set.")
    weight_unit: str = Field(description="The unit of weight, e.g., 'kg' or 'lbs'.")
    sets: int = Field(description="number of sets of that exercise")

# Define the desired data structure for the entire workout
class WorkoutLog(BaseModel):
    sets: List[ExerciseSet] = Field(description="A list of all the exercise sets in the workout.")
    note: str = Field(description="The user's notes on the workout.")

# Initialize the OpenAI model
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.2)

# Set up a Pydantic parser
parser = PydanticOutputParser(pydantic_object=WorkoutLog)

def structure_workout_text(text: str) -> WorkoutLog:
    """
    Uses LangChain to parse raw text and return a structured WorkoutLog object.
    """
    prompt_template = """
    You are an expert fitness assistant. Your task is to parse a user's raw text description of their workout
    and extract the details for each exercise set into a structured JSON format. Further more, the user may also provide some notes about the workout which I want you to store in your response JSON.
    Make sure the notes string that you generate is a short summary and sometimes can include some suggestions.

    IMPORTANT: Only output the JSON object. Do not include any other text, greetings, or explanations.

    Here is an example:
    User input: "I did bench press 3 sets of 10 at 80kg, then 2 sets of bicep curls at 15 lbs for 12 reps. Overall I had a great workout but I think I could have pushed harder"
    Your output:
    {{
        "sets": [
            {{
                "exercise_name": "Bench Press",
                "reps": 10,
                "weight": 80,
                "weight_unit": "kg"
                "sets": 3
            }},
            {{
                "exercise_name": "Bicep Curls",
                "reps": 12,
                "weight": 15,
                "weight_unit": "lbs"
                "sets": 2
            }}
        ],
        "note": "You said that you had a great workout but next time focus on having some simple carbs before your workout so you can push harder!"
    }}
    It is important for you to note that sometimes a user may parse do a body weight exercise, in which case you want to parse the weight to be 0 and unit to be kgs.
    Now, parse the following user workout description:
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
        # The fix is to add a comma to make this a tuple
        chain_with_retry = chain.with_retry(
            retry_if_exception_type=(Exception,), # Added comma here
            stop_after_attempt=2
        )
        structured_response = chain_with_retry.invoke({"user_text": text})
        print(structured_response)
        return structured_response
    except Exception as e:
        print(f"Error processing text with LangChain after retries: {e}")
        return None