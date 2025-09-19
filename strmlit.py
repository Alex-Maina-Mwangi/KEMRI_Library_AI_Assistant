import streamlit as st
from langchain.schema import HumanMessage, AIMessage
from langchain_community.utilities import SQLDatabase
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from examples import example_scripts
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser

from dotenv import load_dotenv
import os

load_dotenv()

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

api_key = os.getenv("MISTRAL_API_KEY")



###################################################################
def get_results(question, results):
    db_uri = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    db = SQLDatabase.from_uri(db_uri)

    context = db.get_context()
    schema_text = context["table_info"]

    llm = ChatMistralAI(api_key=api_key, model= "open-mistral-7b", max_tokens=1024, temperature=0.0)

    example_prompt = PromptTemplate.from_template("Question:{question}\nSQL Query:{query}\n")
    db_prompt = FewShotPromptTemplate(
        examples = example_scripts(),
        example_prompt = example_prompt,
        prefix = """You are an expert SQL assistant.Use the database {schema} below to write a valid SQL query that answers the question.""",
        suffix = """Question:{question}\n Return only a valid SQL query in one line. Do not explain, do not add text, do not format in markdown.SQL Query:""",
        input_variables = ["schema", "question"]
    )

    db_chain = (RunnablePassthrough.assign(schema = lambda x: x["schema"])
            | db_prompt
            | llm
            | StrOutputParser()
            )



    def run_query(sql: str):
        try:
            result = db.run(sql)
            return {"sql": sql, "result": result}
        except Exception as e:
            return {"sql": sql, "result": f"SQL ERROR: {str(e)}"}

    response_prompt = PromptTemplate(
        input_variables=["question", "sql", "result"],
        template="""
                The user asked: {question}
                The SQL executed was: {sql}
                The database returned this result: {result}
                Answer the user's question directly in natural language. 
                Do NOT explain or rewrite the SQL. Just give a concise response.
                """ 
    )

    full_chain = (RunnablePassthrough.assign(schema = lambda x: x["schema"])
              | db_prompt
              | llm
              | RunnableLambda(lambda sql: {"sql": sql.content})
              | RunnableLambda(lambda x: {
                  
                  "question": question,
                  "sql": x["sql"],
                  "result": run_query(x["sql"])["result"]
              })
              | response_prompt
              | llm
              | StrOutputParser()
              )





    #question = "How many publications were published between January and March 2025"

    result = full_chain.invoke({
        "schema": schema_text,
        "question": question
    })

    return result
####################################################################

set_page_config(page_title = "Kadzo", page_icon= ":shark:")
if "chat_history" not in st.session_state:
    st.session_state.chat_history=[
        AIMessage(content="Hello! I am Kadzo, KEMRI AI Library Assistant. Ask me any question about the publications database")
    ]

for message in st.session_state.chat_history:
    if isinstance(message,HumanMessage):
        with st.chat_message("human"):
            st.markdown(message.content)
    else:
        with st.chat_message("ai"):
            st.markdown(message.content)

question = st.chat_input("Ask a question")
if question is not None and question != "":
    st.session_state.chat_history.append(HumanMessage(question))

    with st.chat_message("human"):
        st.markdown(question)

    with st.chat_message("ai"):
        ai_response = get_results(question, st.session_state.chat_history)
        st.markdown(ai_response)
    st.session_state.chat_history.append(AIMessage(ai_response))
