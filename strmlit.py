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
import os,re

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

context = db.get_context()
schema_text = context["table_info"]

llm = ChatMistralAI(api_key=api_key, model="open-mistral-7b", max_tokens=4096, temperature=0.0)


# --- Few-shot SQL prompt ---
example_prompt = PromptTemplate.from_template("Question:{question}\nQuery:{query}\n")
sql_prompt = FewShotPromptTemplate(
    examples=example_scripts(),
    example_prompt=example_prompt,
    prefix="You are an expert SQL assistant. Use the database {schema} below to write a valid SQL query that answers the question.",
    suffix="Question:{question}\nReturn only a valid SQL query in one line. Do not explain, do not add text, do not format in markdown.\nSQL Query:",
    input_variables=["schema", "question"]
)

# --- SQL generation chain ---
sql_chain = (
    RunnablePassthrough.assign(schema=lambda x: x["schema"])
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

intent_chain = intent_prompt | llm | StrOutputParser()


# --- Updated run_query() with pagination + total count ---
def run_query(sql: str, page: int = 1, page_size: int = 50):
    """
    Execute a paginated SQL query safely.
    Automatically adds LIMIT/OFFSET and computes total pages.
    """
    try:
        sql = sql.strip().rstrip(";")

        # Remove existing LIMIT/OFFSET/ORDER BY for reuse
        sql_clean = re.sub(r"(?i)\bLIMIT\s+\d+(\s*,\s*\d+)?", "", sql)
        sql_clean = re.sub(r"(?i)\bOFFSET\s+\d+", "", sql_clean)
        sql_clean = sql_clean.strip()

        # Pagination
        offset = (page - 1) * page_size
        paginated_sql = f"{sql_clean} LIMIT {page_size} OFFSET {offset}"

        # Main query
        result = db.run(paginated_sql)

        # Count query
        count_sql = re.sub(r"(?i)\bORDER\s+BY\s+[\w\s,`\.]+", "", sql_clean)
        count_sql = f"SELECT COUNT(*) as total FROM ({count_sql}) as subquery"
        total_count = 0
        try:
            count_result = db.run(count_sql)
            if isinstance(count_result, list) and count_result and "total" in count_result[0]:
                total_count = count_result[0]["total"]
        except Exception as e:
            #print(f"[DEBUG] Count query failed: {e}")
            total_count = len(result) if isinstance(result, list) else 0

        total_pages = max((total_count + page_size - 1) // page_size, 1)

        #print("\n[DEBUG] SQL executed:", paginated_sql)
        #print("[DEBUG] Count SQL:", count_sql)
        #print("[DEBUG] Total count:", total_count, "| Total pages:", total_pages)

        return {
            "sql": paginated_sql,
            "result": result,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
        }

    except Exception as e:
        print("[DEBUG] SQL ERROR:", str(e))
        return {"sql": sql, "result": f"SQL Error: {str(e)}"}


# --- Cleaned response prompt ---
response_prompt = """
You are a helpful data analysis assistant.

Your job is to read the following information and produce a **clear, human-readable answer** for the user.

Rules:
- Do NOT mention SQL queries or debug info.
- Summarize article data as a readable list:
  “**Here are the articles by [Author] ordered by the most recent**:” followed by author, title, and PMID.
- If empty, respond: “No matching records were found.”
- If many results, show only the first 10 and end with “...and more.”
---

**User Question:**
{question}

**Database Result:**
{result}
"""

# --- Count response prompt ---
count_response_prompt = PromptTemplate(
    input_variables=["question", "sql", "result"],
    template="""
You are a precise data assistant.
The user asked: {question}
The database returned this result: {result}

If the result includes a numeric count (COUNT(*) = N),
respond in this format:
"<Author name> has published a total of <N> articles."
"""
)


# --- Function-based list_result() runnable ---
def list_result(question: str, schema: str, page: int = 1, page_size: int = 50):
    """
    Generate and execute a paginated SQL query based on a 'list' request,
    then return a clean, natural-language summary of the results.
    """
    chain = (
        RunnablePassthrough.assign(schema=lambda x: x["schema"])
        | sql_chain
        | RunnableLambda(lambda sql: {"sql": sql})
        | RunnableLambda(lambda x: {
            "question": question,
            "schema": schema,
            "sql": x["sql"],
            "result_data": run_query(x["sql"], page=page, page_size=page_size),
        })
        | RunnableLambda(lambda x: response_prompt.format(
            question=x["question"],
            result=x["result_data"]["result"]
        ))
        | llm
        | StrOutputParser()
    )
    return chain.invoke({"schema": schema, "question": question})


# --- Count chain ---
def count_result(question: str, schema: str):
    chain = (
        RunnablePassthrough.assign(schema=lambda x: x["schema"])
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
    return chain.invoke({"schema": schema, "question": question})


# --- Full chain controller ---
def full_chain(question: str, schema: str):
    intent = intent_chain.invoke({"question": question}).strip().lower()
    print(f"Detected intent: {intent}")

    if intent == "count":
        return count_result(question, schema)
    elif intent == "list":
        return list_result(question, schema, page=1)
    else:
        return "I'm not sure what kind of answer you need. Could you please rephrase your question?"


# --- Test run ---
#question = "How many articles published by Edwine Barasa"
#result = full_chain(question, schema_text)
#print("\n[FINAL OUTPUT]\n", result)


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
