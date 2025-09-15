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

# Define the desired data structure for the entire workout
class WorkoutLog(BaseModel):
    sets: List[ExerciseSet] = Field(description="A list of all the exercise sets in the workout.")

# Initialize the OpenAI model
llm = ChatOpenAI(model="gpt-3.5-turbo")

# Set up a Pydantic parser to automatically convert the AI's response to our data model
parser = PydanticOutputParser(pydantic_object=WorkoutLog)

def structure_workout_text(text: str) -> WorkoutLog:
    """
    Uses LangChain to parse raw text and return a structured WorkoutLog object.
    """
    prompt_template = """
    You are an expert fitness assistant. Your task is to parse a user's raw text description of their workout
    and extract the details for each exercise set into a structured JSON format.

    Here is the user's workout description:
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
        structured_response = chain.invoke({"user_text": text})
        return structured_response
    except Exception as e:
        print(f"Error processing text with LangChain: {e}")
        return None