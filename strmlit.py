from langchain_community.utilities import SQLDatabase
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from examples import example_scripts
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser


from dotenv import load_dotenv
import os,ast
import pandas as pd
import streamlit as st
from langchain_core.messages import AIMessage,HumanMessage
from langchain_tavily import TavilySearch

load_dotenv()

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
api_key = os.getenv("MISTRAL_API_KEY")
tavily_key = os.getenv("TAVILY_API_KEY")

#get schema text
db_uri = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
db = SQLDatabase.from_uri(db_uri)
schema_text = db.get_context()["table_info"]

#set-up llm
llm = ChatMistralAI(api_key=api_key, model="mistral-small-latest", max_tokens=4096, temperature=0.0)

#sql prompt
example_prompt = PromptTemplate.from_template("Question:{question}\nQuery:{query}\n")
sql_prompt = FewShotPromptTemplate(
    examples = example_scripts(),
    example_prompt = example_prompt,
    prefix = """You are an expert SQL assistant.Use the database {schema} below to write a valid SQL query that answers the question.""",
    suffix = """Question:{question}\n Return only a valid SQL query in one line. Do not explain, do not add text, do not format in markdown.SQL Query:""",
    input_variables = ["schema", "question"]
)

sql_chain = (RunnablePassthrough.assign(schema = lambda x: x["schema"])
             | sql_prompt
             | llm
             | StrOutputParser()
             )



# --- Intent detection prompt ---
intent_prompt = PromptTemplate(
    input_variables=["question"],
    template="""
Classify the user's question into one of the following intents:
- "count" → if the user wants to know how many (e.g., "How many", "Total", "Number of")
- "list" → if the user wants to see the items (e.g., "List", "Show", "Give me", "Display")
- "other" → if it's none of the above.

User question: {question}

Answer with one word only: count, list, or other.
"""
)

#intent chain
intent_chain = intent_prompt | llm | StrOutputParser()

#run query function to extract the sql query and the result as a dictionary(key/value)
def run_query(sql: str):
    if "limit" not in sql:
        sql = sql.rstrip(";")
    try:
        result = db.run(sql)
        if isinstance(result, str):
            return {"sql": sql, "result": [{"Result": result}]}
        elif isinstance(result,list):
            return {"sql": sql, "result": result}
        else:
            try:
                rows = [dict(row) for row in result]
                return {"sql": sql, "result": rows}
            except Exception:
                return {"sql": sql, "result": str(result)}
    except Exception as e:
        return {"sql": sql, "result": f"SQL ERROR:{str(e)}"}


def export_to_excel(data, filename="output.xlsx"):
    if not data:
        print("No data available")
        return None
    all_entries = []

    for item in data:
        raw_results = item.get("Result", "[]")
        try:
            parsed_results = ast.literal_eval(raw_results)
        except(SyntaxError,ValueError):
            parsed_results = []
    
    for author,year,title,secondary_title,volume,number,pages,pmid,doi in parsed_results:
        all_entries.append({
            "Authors": author,
            "Year": year,
            "Title": title,
            "Journal_title": secondary_title,
            "Volume": volume,
            "Issue": number,
            "Pages": pages,
            "PMID": pmid,
            "DOI": doi
        })
        
    if not all_entries:
        print("No valid Entries")
        return None
    
    df = pd.DataFrame(all_entries)
    df.to_excel(filename, index=False)
    print(f"Successfully created an excel file named: {filename}")
    return filename


# --- Response prompt for lists ---
response_prompt = PromptTemplate(
    input_variables=["question", "sql", "result"],
    template="""
The user asked: {question}
The SQL executed was: {sql}
The database returned this result: {result}

Task:
You must ONLY return a list of articles from the result data.

STRICT RULES (do NOT break these):
- Do NOT add explanations.
- Do NOT add summaries.
- Do NOT add background information.
- Do NOT add narrative paragraphs.
- Do NOT mention departments, years, journals, findings, or interpretations.
- Do NOT answer in natural-language prose.
- Do NOT provide context or commentary of any kind.
- Do NOT rewrite or explain the SQL.

If the result is empty, return exactly:
No results found.

Otherwise, return ONLY a list formatted as:
<author> — <title> (PMID: <PMID>)

Each article must be on its own line.
Return NOTHING except the list. No additional text before or after.
"""
)



#Response prompt for counts
count_response_prompt = PromptTemplate(
    input_variables=["question", "sql", "result"],
    template="""
You are a precise data assistant.

The user asked: {question}
The SQL executed was: {sql}
The database returned this result: {result}

Instructions:
- Extract the numeric value from the SQL result. For example, if the result is [{{'COUNT(DISTINCT refs.id)': 4307}}], the number is 4307.
- Respond concisely in one sentence only.
- Always use this format for total counts:

"There are a total of <number> articles."

Replace <number> with the exact count from the SQL result.
Do not include any explanations, examples, or SQL statements.
"""
)


def list_results(question: str, schema: str):
    chain = (RunnablePassthrough.assign(schema = lambda x: x["schema"])
             | sql_chain
             | RunnableLambda(lambda sql: {"sql": sql})
             | RunnableLambda(lambda x: {
                 "question": question,
                 "sql": x["sql"],
                 "result": run_query(x["sql"])["result"]
             })
             | RunnablePassthrough.assign(
                 question = lambda x: x["question"],
                 sql = lambda x: x["sql"],
                 result = lambda x: x["result"]
             )
             | response_prompt
             | llm
             | StrOutputParser()
             )
    response_text = chain.invoke({"question": question, "schema": schema})
    sql = sql_chain.invoke({"question": question, "schema": schema_text})
    data = run_query(sql)["result"]
    return {"response": response_text, "data": data }




def count_results(question: str, schema: str):
    chain = (RunnablePassthrough.assign(schema = lambda x: x["schema"])
             | sql_chain
             | RunnableLambda(lambda sql: {"sql": sql})
             | RunnableLambda(lambda x: {
                "question": question,
                 "sql": x["sql"],
                 "result": run_query(x["sql"])["result"]
             })
             
             | count_response_prompt
             | llm
             | StrOutputParser()
             )
    return chain.invoke({"question": question, "schema": schema})
    

def full_chain(question: str, schema: str):
    intent = intent_chain.invoke({"question":question}).strip().lower()
    print(f"Detected intent:{intent}")
    if intent == "list":
        return list_results(question, schema)
    elif intent == "count":
        return count_results(question, schema)
    else:
        return {"response": ("Unfortunately, I am not able to get what you rae looking for. Could you rephrase your question"),
                "data": None
                }


#question = "What is the total number of publications"
#question = "List all publications published in the year 2024"
#result = sql_chain.invoke({"question": question, "schema": schema_text})
#result = full_chain(question, schema_text)


#print(last_query_data)

#if isinstance (result,dict):
#    final_data = result.get("data")
#    print(final_data)
#else:
#    print(result)

def user_feedback(user_reply: str):
    if user_reply.strip().lower() in ["y", "yes", "yeah", "ok", "sure"]:
        filepath = export_to_excel(final_data)
        if filepath:
            return f"Successfully exported data to Excel file {filepath}"
        else:
            return "No valid data available"
    else:
        return "No Excel file was created"





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
        result = full_chain(question, schema_text)
        if isinstance(result,dict):
            final_data = result.get("data")
            result_str = final_data[0]["Result"]
            # safely convert string → Python list
            result_list = ast.literal_eval(result_str)
            response_str = ""

            for i, (authors,year,title,secondary_title,volume,number,pages,pmid,doi) in enumerate(result_list, start=1):
                response_str += (f"{i}. {authors},{year},{title},{secondary_title},{volume},{number},{pages},{pmid},{doi} \n")
            #st.markdown(response_str.strip(), unsafe_allow_html=True)
            st.session_state["last_data_for_excel"] = final_data
            #response_str += "\n\nWould you like to download this list as an Excel file? (yes/no)"
            response_str += '\n\n<span style="color: green; font-weight: bold;">Would you like to download this list as an Excel file? (yes/no)</span>'


            return response_str.strip()
        else:
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
if question is not None and question != "":
    st.session_state.chat_history.append(HumanMessage(question))
    with st.chat_message("human"):
        st.markdown(question)

    # --- Intercept YES/NO for Excel download if a list was previously generated ---
    if "last_data_for_excel" in st.session_state:
        user_answer = question.lower().strip()
        if user_answer in ["yes", "y"]:
            filepath = export_to_excel(st.session_state["last_data_for_excel"])
            if filepath:
        # Read the Excel file as bytes
                with open(filepath, "rb") as f:
                    excel_bytes = f.read()
                st.download_button(
                    label="Click here to download your Excel file",
                    data=excel_bytes,
                    file_name=filepath,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.markdown("No valid data available to export.")
        del st.session_state["last_data_for_excel"]
        st.stop()

    # --- Normal agent processing ---
    with st.chat_message("ai"):
        ai_response = agent_router(question, st.session_state.chat_history)

    with st.chat_message("ai"):
        #st.markdown(ai_response)
        st.markdown(ai_response, unsafe_allow_html=True)
    
    st.session_state.chat_history.append(AIMessage(ai_response))

