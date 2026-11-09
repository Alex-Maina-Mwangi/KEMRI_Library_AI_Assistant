
import os
import re
import ast
import time
import random
from io import BytesIO
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_mistralai import ChatMistralAI
from langchain_tavily import TavilySearch

from langchain_core.prompts import (
    FewShotPromptTemplate,
    PromptTemplate,
)

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import AIMessage, HumanMessage

from examples import example_scripts


# =========================================================
# 1. STREAMLIT CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Kadzo",
    page_icon="🦈",
    layout="wide",
)

load_dotenv()


# =========================================================
# 2. ENVIRONMENT VARIABLES
# =========================================================

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


if not MISTRAL_API_KEY:
    st.error("MISTRAL_API_KEY is not configured.")
    st.stop()

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    st.error("One or more database environment variables are missing.")
    st.stop()


# =========================================================
# 3. DATABASE CONNECTION
# =========================================================

@st.cache_resource
def get_database():

    encoded_user = quote_plus(DB_USER)
    encoded_password = quote_plus(DB_PASSWORD)

    db_uri = (
        f"mysql+mysqlconnector://"
        f"{encoded_user}:{encoded_password}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    return SQLDatabase.from_uri(
        db_uri,
        sample_rows_in_table_info=0,
        pool_pre_ping=True,
    )


try:
    db = get_database()

except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()


# =========================================================
# 4. DATABASE SCHEMA
# =========================================================

@st.cache_data(ttl=1800, show_spinner=False)
def get_schema():

    return db.get_context()["table_info"]


try:
    schema_text = get_schema()

except Exception as e:
    st.error(f"Could not retrieve database schema: {e}")
    st.stop()


# =========================================================
# 5. MISTRAL CONFIGURATION
# =========================================================

@st.cache_resource
def get_llm():

    return ChatMistralAI(
        api_key=MISTRAL_API_KEY,
        model="mistral-small-latest",

        # SQL queries do not need lengthy responses.
        max_tokens=512,

        temperature=0.0,

        # Retry handling is implemented separately below.
        max_retries=0,

        timeout=30,
    )


llm = get_llm()


# =========================================================
# 6. RATE LIMIT DETECTION AND RETRY
# =========================================================

def is_rate_limit_error(error):

    message = str(error).lower()

    indicators = [
        "429",
        "rate limit",
        "rate_limit",
        "rate limited",
        "too many requests",
        "temporarily rate-limited",
        "temporarily rate limited",
    ]

    return any(
        indicator in message
        for indicator in indicators
    )


def invoke_with_retry(chain, inputs, attempts=3):

    """
    Retry temporary Mistral rate limits.

    Waits progressively longer between attempts.
    Other errors are raised immediately.
    """

    for attempt in range(attempts):

        try:

            return chain.invoke(inputs)

        except Exception as e:

            if not is_rate_limit_error(e):
                raise

            if attempt == attempts - 1:
                raise

            delay = min(
                3 * (2 ** attempt) + random.uniform(0, 1),
                15,
            )

            time.sleep(delay)

    raise RuntimeError("Mistral request failed.")


# =========================================================
# 7. FEW-SHOT SQL EXAMPLES
# =========================================================

example_prompt = PromptTemplate.from_template(
    "Question: {question}\n"
    "Query: {query}\n"
)


def get_valid_examples():

    examples = example_scripts()

    valid = []

    for example in examples:

        question = example.get("question", "")
        query = example.get("query", "")

        if not question or not query:
            continue

        # Exclude malformed examples such as LIMIT;
        if re.search(
            r"\bLIMIT\s*;?$",
            query.strip(),
            flags=re.IGNORECASE,
        ):
            continue

        valid.append({
            "question": question,
            "query": query,
        })

    # Keep the prompt compact.
    return valid[:8]


examples = get_valid_examples()


# =========================================================
# 8. SQL PROMPT
# =========================================================

sql_prompt = FewShotPromptTemplate(

    examples=examples,

    example_prompt=example_prompt,

    prefix="""
You are an expert MySQL assistant for the
KEMRI-Wellcome Trust Research Programme
publication database.

Write one valid, read-only MySQL query.

DATABASE SCHEMA:
{schema}

RULES:

1. Use only tables and columns in the schema.
2. Use MySQL syntax.
3. Use COUNT(DISTINCT refs.id) when counting
   unique publications across author joins.
4. Do not invent columns or table names.
5. Do not generate INSERT, UPDATE, DELETE,
   DROP, ALTER, CREATE or TRUNCATE statements.
6. For publication lists, return these fields
   when available:

   author,
   year,
   title,
   secondary_title,
   volume,
   number,
   pages,
   accession_number AS PMID,
   electronic_resource_number AS DOI.

7. Do not use SELECT * unless necessary.
8. Do not include explanations or Markdown.
9. Return SQL only.
10. Never generate LIMIT without a numeric value.

""",

    suffix="""
Question: {question}

Return only the SQL query.
SQL Query:
""",

    input_variables=[
        "schema",
        "question",
    ],
)


# =========================================================
# 9. LANGCHAIN RUNNABLE
# =========================================================

sql_chain = (

    RunnablePassthrough.assign(
        schema=lambda x: x["schema"]
    )

    | sql_prompt

    | llm

    | StrOutputParser()

)


# =========================================================
# 10. SQL CLEANING
# =========================================================

def clean_sql(sql):

    if not sql:
        return ""

    sql = sql.strip()

    sql = re.sub(
        r"^```(?:sql)?\s*",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(
        r"\s*```$",
        "",
        sql,
    )

    sql = re.sub(
        r"^\s*SQL\s+Query\s*:\s*",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    return sql.strip().rstrip(";")


# =========================================================
# 11. SQL VALIDATION
# =========================================================

def validate_sql(sql):

    sql = clean_sql(sql)

    if not sql:
        raise ValueError("The generated SQL query is empty.")

    # Only SELECT and WITH queries are allowed.
    if not re.match(
        r"^\s*(SELECT|WITH)\b",
        sql,
        flags=re.IGNORECASE,
    ):
        raise ValueError(
            "Only SELECT queries are permitted."
        )

    # Prevent multiple SQL statements.
    if ";" in sql:
        raise ValueError(
            "Multiple SQL statements are not permitted."
        )

    forbidden = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "REPLACE",
        "GRANT",
        "REVOKE",
        "LOAD_FILE",
        "INTO OUTFILE",
        "INTO DUMPFILE",
    ]

    for keyword in forbidden:

        if re.search(
            rf"\b{re.escape(keyword)}\b",
            sql,
            flags=re.IGNORECASE,
        ):
            raise ValueError(
                f"Unsafe SQL keyword detected: {keyword}"
            )

    return sql


# =========================================================
# 12. GENERATE SQL WITH CACHE
# =========================================================

@st.cache_data(
    ttl=900,
    show_spinner=False,
)
def generate_sql_cached(question, schema):

    """
    Identical questions reuse previously generated SQL.

    Cache duration: 15 minutes.
    """

    response = invoke_with_retry(

        sql_chain,

        {
            "question": question,
            "schema": schema,
        },

        attempts=3,

    )

    return clean_sql(response)


def generate_sql(question, schema):

    sql = generate_sql_cached(
        question.strip(),
        schema,
    )

    return validate_sql(sql)


# =========================================================
# 13. PARSE MYSQL RESULTS
# =========================================================

def parse_result(result):

    if result is None:
        return []

    if isinstance(result, list):

        if len(result) == 1 and isinstance(
            result[0], dict
        ):

            raw = result[0].get("Result")

            if isinstance(raw, str):

                try:
                    parsed = ast.literal_eval(raw)

                    if isinstance(parsed, list):
                        return parsed

                except (ValueError, SyntaxError):
                    pass

        return result

    if isinstance(result, str):

        try:

            parsed = ast.literal_eval(result)

            if isinstance(parsed, list):
                return parsed

        except (ValueError, SyntaxError):
            pass

    return []


# =========================================================
# 14. RUN SQL
# =========================================================

def run_query(sql):

    try:

        sql = validate_sql(sql)

        result = db.run(sql)

        if isinstance(result, str):

            return {
                "sql": sql,
                "result": [
                    {"Result": result}
                ],
            }

        if isinstance(result, list):

            return {
                "sql": sql,
                "result": result,
            }

        return {
            "sql": sql,
            "result": str(result),
        }

    except Exception as e:

        return {
            "sql": sql,
            "result": f"SQL ERROR: {str(e)}",
        }


# =========================================================
# 15. REMOVE SQL LIMIT
# =========================================================

def remove_limit(sql):

    sql = clean_sql(sql)

    sql = re.sub(
        r"\s+LIMIT\s+(?:\d+\s*,\s*)?\d+\s*$",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    return sql.strip()


# =========================================================
# 16. DETECT QUESTION INTENT
# =========================================================

COUNT_PATTERNS = [
    r"\bhow many\b",
    r"\bhow much\b",
    r"\btotal\b",
    r"\bnumber of\b",
    r"\bcount\b",
    r"\bcounts\b",
]

LIST_PATTERNS = [
    r"\blist\b",
    r"\bshow\b",
    r"\bgive me\b",
    r"\bdisplay\b",
    r"\bwhich\b",
    r"\bwhat are\b",
]


def detect_intent(question):

    q = question.lower().strip()

    if any(
        re.search(pattern, q)
        for pattern in COUNT_PATTERNS
    ):
        return "count"

    if any(
        re.search(pattern, q)
        for pattern in LIST_PATTERNS
    ):
        return "list"

    return "list"


# =========================================================
# 17. EXTRACT COUNT
# =========================================================

def extract_count(result):

    rows = parse_result(result)

    if rows:

        first_row = rows[0]

        if isinstance(first_row, dict):

            for value in first_row.values():

                if isinstance(value, (int, float)):
                    return int(value)

        if isinstance(first_row, (list, tuple)):

            for value in first_row:

                if isinstance(value, (int, float)):
                    return int(value)

    return None


# =========================================================
# 18. COUNT PUBLICATIONS
# =========================================================

def count_results(question, schema):

    sql = generate_sql(
        question,
        schema,
    )

    query_result = run_query(sql)

    result = query_result["result"]

    if isinstance(result, str):

        if result.startswith("SQL ERROR"):
            return result

    count = extract_count(result)

    if count is None:

        return (
            "I could not determine the count "
            "from the database result."
        )

    return (
        f"There are a total of {count:,} articles."
    )


# =========================================================
# 19. FORMAT PUBLICATION ROWS
# =========================================================

PUBLICATION_COLUMNS = [
    "Authors",
    "Year",
    "Title",
    "Journal_title",
    "Volume",
    "Issue",
    "Pages",
    "PMID",
    "DOI",
]


def format_publication(row):

    if isinstance(row, dict):
        return ", ".join(
            str(value) for value in row.values()
        )

    if isinstance(row, (list, tuple)):

        if len(row) >= 9:

            (
                authors,
                year,
                title,
                journal,
                volume,
                issue,
                pages,
                pmid,
                doi,
            ) = row[:9]

            return (
                f"{authors}, {year}, {title}, "
                f"{journal}, {volume}, {issue}, "
                f"{pages}, PMID: {pmid}, DOI: {doi}"
            )

    return str(row)


# =========================================================
# 20. LIST PUBLICATIONS
# =========================================================

def list_results(question, schema):

    sql = generate_sql(
        question,
        schema,
    )

    first_result = run_query(sql)

    result = first_result["result"]

    if (
        isinstance(result, str)
        and result.startswith("SQL ERROR")
    ):

        return {
            "response": result,
            "full_data": None,
        }

    full_data = result

    full_list = parse_result(full_data)

    if not full_list:

        return {
            "response": "No results found.",
            "full_data": None,
        }

    # If SQL contains LIMIT, fetch the complete list.
    if re.search(
        r"\sLIMIT\s+\d+",
        sql,
        flags=re.IGNORECASE,
    ):

        unrestricted_sql = remove_limit(sql)

        complete_result = run_query(
            unrestricted_sql
        )

        if (
            isinstance(
                complete_result["result"],
                str,
            )
            and complete_result["result"].startswith(
                "SQL ERROR"
            )
        ):
            return {
                "response": complete_result["result"],
                "full_data": None,
            }

        full_data = complete_result["result"]
        full_list = parse_result(full_data)

    total_count = len(full_list)

    preview_list = full_list[:50]

    lines = [

        (
            f"Showing {len(preview_list)} "
            f"of {total_count:,} results."
        ),

        "",
    ]

    for index, row in enumerate(
        preview_list,
        start=1,
    ):

        lines.append(
            f"{index}. {format_publication(row)}"
        )

    lines.extend([
        "",
        "**Would you like to download the complete "
        "publication list as an Excel file? (yes/no)**",
    ])

    return {
        "response": "\n".join(lines),
        "full_data": full_data,
    }


# =========================================================
# 21. FULL DATABASE CHAIN
# =========================================================

def full_chain(question, schema):

    intent = detect_intent(question)

    print(f"Detected intent: {intent}")

    if intent == "count":

        return {
            "response": count_results(
                question,
                schema,
            ),
            "full_data": None,
        }

    return list_results(
        question,
        schema,
    )


# =========================================================
# 22. EXCEL EXPORT
# =========================================================

def export_to_excel(data):

    rows = parse_result(data)

    if not rows:
        return None

    entries = []

    for row in rows:

        if isinstance(row, dict):

            entries.append(row)

        elif isinstance(row, (list, tuple)):

            if len(row) >= 9:

                entries.append(
                    dict(zip(
                        PUBLICATION_COLUMNS,
                        row[:9],
                    ))
                )

    if not entries:
        return None

    df = pd.DataFrame(entries)

    output = BytesIO()

    df.to_excel(
        output,
        index=False,
        engine="openpyxl",
    )

    output.seek(0)

    return output.getvalue()


# =========================================================
# 23. TAVILY WEB SEARCH
# =========================================================

@st.cache_resource
def get_search_tool():

    if not TAVILY_API_KEY:
        return None

    return TavilySearch(
        max_results=5,
        tavily_api_key=TAVILY_API_KEY,
    )


search_tool = get_search_tool()


def web_search(question):

    if search_tool is None:

        return (
            "Web search is unavailable because "
            "TAVILY_API_KEY is not configured."
        )

    try:

        results = search_tool.invoke(question)

        if isinstance(results, str):

            return results

        search_results = results.get(
            "results",
            [],
        )

        if not search_results:

            return "I could not find relevant web results."

        lines = []

        for index, item in enumerate(
            search_results[:5],
            start=1,
        ):

            title = item.get("title", "Search result")
            url = item.get("url", "")
            content = item.get("content", "")

            lines.append(
                f"**{index}. [{title}]({url})**\n\n"
                f"{content[:700]}\n"
            )

        # No second Mistral request.
        return "\n".join(lines)

    except Exception as e:

        return f"Web search failed: {str(e)}"


# =========================================================
# 24. AGENT ROUTER
# =========================================================

def agent_router(question):

    q = question.lower().strip()

    # -----------------------------------------------------
    # GREETINGS
    # -----------------------------------------------------

    greetings = {

        "niaje": (
            "Poa sana! Naweza sort issue yako gani leo? "
            "Mi nimeiva story za publications ile deadly."
        ),

        "sasa": (
            "Fiti sana! Naweza sort issue yako gani leo? "
            "Mi nimeiva story za publications ile deadly."
        ),

        "jambo": (
            "Jambo! How can I help you today? "
            "Ask me any question about KWTRP Publications."
        ),

        "habari": (
            "Mzuri sana! Naweza kusaidia aje leo? "
            "Niulize swali lolote kuhusu publications."
        ),

        "hi": (
            "Hi there! How can I help you today? "
            "Ask me any question about KWTRP publications."
        ),

        "hey": (
            "Hey there! How can I help you today? "
            "Ask me any question about KWTRP publications."
        ),

        "hello": (
            "Hello there! How can I help you today? "
            "Ask me any question about KWTRP publications."
        ),
    }

    if q in greetings:
        return greetings[q]

    # -----------------------------------------------------
    # DATABASE ROUTING
    # -----------------------------------------------------

    db_keywords = [

        "publication",
        "publications",
        "article",
        "articles",
        "paper",
        "papers",
        "author",
        "authors",
        "journal",
        "journals",
        "pmid",
        "doi",
        "published",
        "department",
        "researcher",
        "scientist",
    ]

    if any(
        word in q
        for word in db_keywords
    ):

        try:

            result = full_chain(
                question,
                schema_text,
            )

            response = result["response"]

            full_data = result.get("full_data")

            if full_data is not None:

                st.session_state[
                    "pending_excel_data"
                ] = full_data

            return response

        except Exception as e:

            if is_rate_limit_error(e):

                return (
                    "Mistral is currently rate-limited. "
                    "I attempted controlled retries, but "
                    "the request could not be completed. "
                    "Please try again shortly."
                )

            return (
                f"Database question failed: {str(e)}"
            )

    # -----------------------------------------------------
    # WEB SEARCH
    # -----------------------------------------------------

    return web_search(question)


# =========================================================
# 25. CHAT HISTORY
# =========================================================

if "chat_history" not in st.session_state:

    st.session_state.chat_history = [

        AIMessage(

            content=(
                "Hello! I am Kadzo, "
                "***The first ever AI-Agent to work at KEMRI***. "
                "I am a library assistant designed and "
                "developed by Alex Maina.\n\n"
                "**Ask me any question about "
                "KEMRI-WELLCOME TRUST RESEARCH "
                "PROGRAMME PUBLICATIONS.**"
            )

        )

    ]


# =========================================================
# 26. DISPLAY CHAT HISTORY
# =========================================================

for message in st.session_state.chat_history:

    if isinstance(message, HumanMessage):

        with st.chat_message("human"):
            st.markdown(message.content)

    elif isinstance(message, AIMessage):

        with st.chat_message("ai"):
            st.markdown(
                message.content,
                unsafe_allow_html=True,
            )


# =========================================================
# 27. EXCEL DOWNLOAD HANDLING
# =========================================================

def handle_excel_answer(answer):

    answer = answer.lower().strip()

    if answer in ["yes", "y"]:

        data = st.session_state.get(
            "pending_excel_data"
        )

        if data is None:
            return False

        excel_bytes = export_to_excel(data)

        if excel_bytes is None:

            with st.chat_message("ai"):
                st.error("No valid publication data to export.")

        else:

            with st.chat_message("ai"):

                st.download_button(

                    label="Download complete Excel file",

                    data=excel_bytes,

                    file_name="KWTRP_Publications.xlsx",

                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),

                )

        st.session_state.pop(
            "pending_excel_data",
            None,
        )

        return True

    if answer in ["no", "n"]:

        st.session_state.pop(
            "pending_excel_data",
            None,
        )

        with st.chat_message("ai"):
            st.markdown("No Excel file was created.")

        return True

    return False


# =========================================================
# 28. USER INPUT
# =========================================================

question = st.chat_input("Ask a question")


if question:

    st.session_state.chat_history.append(
        HumanMessage(content=question)
    )

    with st.chat_message("human"):
        st.markdown(question)

    # -----------------------------------------------------
    # CHECK EXCEL RESPONSE
    # -----------------------------------------------------

    pending_data = st.session_state.get(
        "pending_excel_data"
    )

    if pending_data is not None:

        handled = handle_excel_answer(question)

        if handled:

            st.session_state.chat_history.append(
                AIMessage(
                    content=(
                        "Excel download requested."
                        if question.lower().strip() in ["yes", "y"]
                        else "No Excel file was created."
                    )
                )
            )

            st.stop()

        # A new question is not treated as "no".
        # Clear the old pending export and continue.
        st.session_state.pop(
            "pending_excel_data",
            None,
        )

    # -----------------------------------------------------
    # NORMAL AGENT PROCESSING
    # -----------------------------------------------------

    with st.chat_message("ai"):

        try:

            with st.spinner("Kadzo is working..."):

                ai_response = agent_router(question)

            st.markdown(
                ai_response,
                unsafe_allow_html=True,
            )

        except Exception as e:

            ai_response = f"An unexpected error occurred: {e}"

            st.error(ai_response)

    st.session_state.chat_history.append(
        AIMessage(content=ai_response)
    )
