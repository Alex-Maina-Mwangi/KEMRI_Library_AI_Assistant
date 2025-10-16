from langchain_community.utilities import SQLDatabase
from langchain_mistralai import ChatMistralAI
#from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_tavily import TavilySearch
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from examples import example_scripts
from langchain_core.output_parsers import StrOutputParser
from langchain.schema import HumanMessage, AIMessage
import streamlit as st


from dotenv import load_dotenv
import os

load_dotenv()

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")


api_key = os.getenv("MISTRAL_API_KEY")
tavily_key = os.getenv("TAVILY_API_KEY")


db_uri = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

db = SQLDatabase.from_uri(db_uri)
context = db.get_table_info()
#schema_text = context["table_info"]
schema_text = db.get_table_info(['refs', 'author_publication1', 'author_alias', 'people'])
#print(context.keys())

llm = ChatMistralAI(api_key=api_key, model="open-mistral-7b", max_tokens=1024)


example_prompt = PromptTemplate.from_template("Question:{question}\nSQL Query:{query}")

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
    if "limit" not in sql.lower():
        sql = sql.rstrip(";") + " LIMIT 50"
    try:
        result = db.run(sql)
        return {"sql": sql, "result": result}
    except Exception as e:
        return {"sql": sql, "result": f"SQL ERROR:{str(e)}"}
    
response_prompt = PromptTemplate(
    input_variables=["question", "sql", "result"],
    template="""
                The user asked: {question}
                The SQL executed was: {sql}
                The database returned this result: {result}
                Using all three columns, list each article on a new line in the following format:
                <author(s)>, - <title>,(PMID: <PMID>\n)
                

                

                Important:
                - Do NOT summarize or omit any entries.
                - Do NOT use ellipses (...).
                - Return the complete list exactly as provided.
                - Do not add messages like "the rest are listed in the SQL query result".

                Return everything verbatim.

                If there are multiple authors, include them all as provided in the result.
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

search_tool = TavilySearch(max_results=5, tavily_api_key= tavily_key)

def agent_router(question: str, result):
    q_lower = question.lower().strip()
    greetings = {
        "niaje": "Poa sana! Naweza sort issue yako gani leo? Mi nimeiva story za publications ile deadly",
        "sasa": "Fiti sana! Naweza sort issue yako gani leo? Mi nimeiva story za publications ile deadly",
        "jambo": "Jambo! How can I help you today? Ask me any question about KWTRP Publications.",
        "habari": "Mzuri sana! Naweza kusaidia aje leo. Niulize swali yeyote kuhusu publications.",
        "hi": "Hi there! How can I help you today. Ask me any question about KWTRP publications",
        "hey": "Hey there! How can I help you today. Ask me any question about KWTRP publications",
        "hello": "Hello there! How can I help you today. Ask me any question about KWTRP publications",
    }
    if q_lower in greetings:
        return greetings[q_lower]
    
    #DB Search
   
    db_keywords = ["publication", "article", "paper", "author", "journal"]
    if any(word in q_lower for word in db_keywords):
        # Call your full_chain for DB queries
        result = full_chain.invoke({"schema": schema_text, "question": question})
        return result
    
     # --- 3. Web search intent ---
    try:
        results = search_tool.invoke(question)
        if results and "results" in results and len(results["results"]) > 0:
            # Use the first result's content as context
            context = results["results"][0]["content"]
            prompt = f"Question: {question}\nContext: {context}\nAnswer concisely in 100 words or less."
            return llm.invoke(prompt).content
        else:
            return "I am sorry, I could not find relevant web results."
    except Exception as e:
        return f"Web search failed: {str(e)}"

    # --- 4. Fallback ---
    return "Sorry, I don't understand your question. Please rephrase"

st.set_page_config(page_title = "Kadzo", page_icon= ":shark:")
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [

        AIMessage(content="Hello! I am Kadzo, ***The first ever AI-Agent to work at KEMRI***." \
        " I am a library assistant designed and developed by Alex Maina.\n **Ask me any question about KEMRI-WELLCOME TRUST RESEARCH PROGRAMME PUBLICATIONS**")
    ]

for message in st.session_state.chat_history:
    if isinstance(message,HumanMessage):
        with st.chat_message("human"):
            st.markdown(message.content)
    else:
        with st.chat_message("ai"):
            st.markdown(message.content)


question = st.chat_input("Ask a question")
if question is not None and question !="":
    st.session_state.chat_history.append(HumanMessage(question))
    with st.chat_message("human"):
        st.markdown(question)
    
    with st.chat_message("ai"):
        ai_response = agent_router(question, st.session_state.chat_history)
        st.markdown(ai_response)
    st.session_state.chat_history.append(AIMessage(ai_response))
