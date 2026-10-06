from langchain_community.utilities import SQLDatabase
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from examples import example_scripts
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import os
import ast
import re
import pandas as pd
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from langchain_tavily import TavilySearch

load_dotenv()


# =========================================================
# ENVIRONMENT
# =========================================================

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
api_key = os.getenv("MISTRAL_API_KEY")
tavily_key = os.getenv("TAVILY_API_KEY")


if not api_key:
    st.error("MISTRAL_API_KEY is not configured.")
    st.stop()


if not all([db_user, db_password, db_host, db_port, db_name]):
    st.error("One or more database environment variables are missing.")
    st.stop()


# =========================================================
# DATABASE
# =========================================================

@st.cache_resource
def get_database():

    db_uri = (
        f"mysql+mysqlconnector://{db_user}:{db_password}"
        f"@{db_host}:{db_port}/{db_name}"
    )

    return SQLDatabase.from_uri(db_uri)


db = get_database()


@st.cache_data(ttl=300)
def get_schema():

    return db.get_context()["table_info"]


schema_text = get_schema()


# =========================================================
# MISTRAL
# =========================================================

@st.cache_resource
def get_llm():

    return ChatMistralAI(
        api_key=api_key,
        model="mistral-small-latest",
        max_tokens=4096,
        temperature=0.0,
    )


llm = get_llm()


# =========================================================
# SQL PROMPT
# =========================================================

example_prompt = PromptTemplate.from_template(
    "Question: {question}\nQuery: {query}\n"
)


sql_prompt = FewShotPromptTemplate(

    examples=example_scripts(),

    example_prompt=example_prompt,

    prefix="""You are an expert SQL assistant.

Use the database schema below to write a valid MySQL query that answers the user's question.

DATABASE SCHEMA:
{schema}

Rules:
- Use only tables and columns that exist in the schema.
- Return SQL only.
- Do not use markdown.
- Do not explain the query.
""",

    suffix="""Question: {question}

Return only the valid SQL query in one line.
SQL Query:""",

    input_variables=["schema", "question"],
)


sql_chain = (
    sql_prompt
    | llm
    | StrOutputParser()
)


# =========================================================
# SQL CLEANING
# =========================================================

def clean_sql(sql: str) -> str:

    if not sql:
        return ""

    sql = sql.strip()

    # Remove ```sql ... ```
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

    # Remove accidental SQL Query:
    sql = re.sub(
        r"^\s*SQL\s+Query\s*:\s*",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    return sql.strip().rstrip(";")


# =========================================================
# RUN SQL
# =========================================================

def run_query(sql: str):

    sql = clean_sql(sql)

    if not sql:

        return {
            "sql": sql,
            "result": "SQL ERROR: Empty SQL query."
        }

    try:

        result = db.run(sql)

        if isinstance(result, str):

            return {
                "sql": sql,
                "result": [{"Result": result}]
            }

        if isinstance(result, list):

            return {
                "sql": sql,
                "result": result
            }

        try:

            rows = [dict(row) for row in result]

            return {
                "sql": sql,
                "result": rows
            }

        except Exception:

            return {
                "sql": sql,
                "result": str(result)
            }

    except Exception as e:

        return {
            "sql": sql,
            "result": f"SQL ERROR: {str(e)}"
        }


# =========================================================
# RESULT PARSING
# =========================================================

def parse_result(result):

    if result is None:
        return []

    if isinstance(result, list):

        if len(result) == 1 and isinstance(result[0], dict):

            raw = result[0].get("Result")

            if isinstance(raw, list):
                return raw

            if isinstance(raw, str):

                try:

                    parsed = ast.literal_eval(raw)

                    if isinstance(parsed, list):
                        return parsed

                except (SyntaxError, ValueError):
                    pass

        return result

    if isinstance(result, str):

        try:

            parsed = ast.literal_eval(result)

            if isinstance(parsed, list):
                return parsed

        except (SyntaxError, ValueError):
            pass

    return []


# =========================================================
# REMOVE LIMIT
# =========================================================

def remove_limit(sql: str):

    sql = clean_sql(sql)

    sql = re.sub(
        r"\s+LIMIT\s+(?:\d+\s*,\s*)?\d+\s*$",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    return sql.rstrip(";").strip()


# =========================================================
# EXCEL EXPORT
# =========================================================

def export_to_excel(
    data,
    filename="output.xlsx"
):

    if not data:
        return None

    parsed_results = parse_result(data)

    if not parsed_results:
        return None

    all_entries = []

    for row in parsed_results:

        if not isinstance(row, (list, tuple)):
            continue

        if len(row) < 9:
            continue

        (
            author,
            year,
            title,
            journal,
            volume,
            issue,
            pages,
            pmid,
            doi
        ) = row[:9]

        all_entries.append({

            "Authors": author,
            "Year": year,
            "Title": title,
            "Journal_title": journal,
            "Volume": volume,
            "Issue": issue,
            "Pages": pages,
            "PMID": pmid,
            "DOI": doi,

        })

    if not all_entries:
        return None

    df = pd.DataFrame(all_entries)

    df.to_excel(
        filename,
        index=False
    )

    return filename


# =========================================================
# COUNT / LIST DETECTION
#
# IMPORTANT:
# THIS DOES NOT CALL MISTRAL
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


def detect_intent(question: str):

    q = question.lower().strip()

    # Count takes priority
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

    # Default publication questions to list
    return "list"


# =========================================================
# GENERATE SQL
# =========================================================

def generate_sql(
    question: str,
    schema: str
):

    sql = sql_chain.invoke({

        "question": question,
        "schema": schema,

    })

    return clean_sql(sql)


# =========================================================
# EXTRACT COUNT
#
# NO SECOND MISTRAL CALL
# =========================================================

def extract_count(result):

    if result is None:
        return None

    if isinstance(result, list):

        for item in result:

            if isinstance(item, dict):

                for value in item.values():

                    if isinstance(
                        value,
                        (int, float)
                    ):

                        return int(value)

                    if isinstance(value, str):

                        match = re.search(
                            r"-?\d+(?:\.\d+)?",
                            value
                        )

                        if match:
                            return int(
                                float(match.group())
                            )

            elif isinstance(
                item,
                (list, tuple)
            ):

                for value in item:

                    if isinstance(
                        value,
                        (int, float)
                    ):

                        return int(value)

    if isinstance(result, str):

        match = re.search(
            r"-?\d+(?:\.\d+)?",
            result
        )

        if match:
            return int(
                float(match.group())
            )

    return None


# =========================================================
# COUNT RESULTS
# =========================================================

def count_results(
    question: str,
    schema: str
):

    sql = generate_sql(
        question,
        schema
    )

    query_result = run_query(sql)

    result = query_result["result"]

    if (
        isinstance(result, str)
        and result.startswith("SQL ERROR")
    ):

        return result

    count = extract_count(result)

    if count is None:

        return (
            "I could not determine the count "
            "from the database result."
        )

    return (
        f"There are a total of {count} articles."
    )


# =========================================================
# LIST RESULTS
# =========================================================

def list_results(
    question: str,
    schema: str
):

    sql = generate_sql(
        question,
        schema
    )

    first_result = run_query(sql)

    result = first_result["result"]

    if (
        isinstance(result, str)
        and result.startswith("SQL ERROR")
    ):

        return {

            "response": result,
            "preview_data": [],
            "full_data": [],

        }

    full_data = result

    full_list = parse_result(
        full_data
    )

    if not full_list:

        return {

            "response": "No results found.",
            "preview_data": [],
            "full_data": [],

        }

    # -----------------------------------------------------
    # FIRST 50 FOR DISPLAY
    # -----------------------------------------------------

    preview_list = full_list[:50]

    preview_data = [

        {
            "Result": str(
                preview_list
            )
        }

    ]

    # -----------------------------------------------------
    # IF SQL HAS LIMIT, RE-RUN WITHOUT LIMIT
    # -----------------------------------------------------

    if re.search(
        r"\sLIMIT\s+",
        sql,
        flags=re.IGNORECASE
    ):

        clean_sql = remove_limit(
            sql
        )

        full_result = run_query(
            clean_sql
        )

        full_data = full_result[
            "result"
        ]

    total_count = len(
        parse_result(full_data)
    )

    # -----------------------------------------------------
    # BUILD RESPONSE IN PYTHON
    #
    # NO MISTRAL CALL HERE
    # -----------------------------------------------------

    lines = [

        (
            f"Showing {len(preview_list)} "
            f"of {total_count} results. "
            "Download Excel for the full list below."
        ),

        ""

    ]

    for i, row in enumerate(
        preview_list,
        start=1
    ):

        if (
            isinstance(row, (list, tuple))
            and len(row) >= 9
        ):

            (
                authors,
                year,
                title,
                journal,
                volume,
                issue,
                pages,
                pmid,
                doi
            ) = row[:9]

            lines.append(

                f"{i}. {authors}, "
                f"{year}, "
                f"{title}, "
                f"{journal}, "
                f"{volume}, "
                f"{issue}, "
                f"{pages}, "
                f"{pmid}, "
                f"{doi}"

            )

        else:

            lines.append(
                f"{i}. {row}"
            )

    lines.extend([

        "",

        (
            '<span style="color: green; '
            'font-weight: bold;">'
            "Would you like to download this "
            "list as an Excel file? (yes/no)"
            "</span>"
        )

    ])

    return {

        "response": "\n".join(lines),

        "preview_data": preview_data,

        "full_data": full_data,

    }


# =========================================================
# FULL CHAIN
# =========================================================

def full_chain(
    question: str,
    schema: str
):

    intent = detect_intent(
        question
    )

    print(
        f"Detected intent: {intent}"
    )

    if intent == "list":

        return list_results(
            question,
            schema
        )

    if intent == "count":

        return count_results(
            question,
            schema
        )

    return {

        "response": (
            "Unfortunately, I could not "
            "determine what you are looking "
            "for. Could you rephrase your question?"
        ),

        "data": None,

    }


# =========================================================
# TAVILY
# =========================================================

search_tool = TavilySearch(

    max_results=5,

    tavily_api_key=tavily_key,

)


# =========================================================
# AGENT ROUTER
# =========================================================

def agent_router(
    question: str,
    chat_history
):

    q_lower = question.lower().strip()

    # =====================================================
    # 1. GREETINGS
    # =====================================================

    greetings = {

        "niaje":
            (
                "Poa sana! Naweza sort issue yako gani leo? "
                "Mi nimeiva story za publications ile deadly"
            ),

        "sasa":
            (
                "Fiti sana! Naweza sort issue yako gani leo? "
                "Mi nimeiva story za publications ile deadly"
            ),

        "jambo":
            (
                "Jambo! How can I help you today? "
                "Ask me any question about KWTRP Publications."
            ),

        "habari":
            (
                "Mzuri sana! Naweza kusaidia aje leo. "
                "Niulize swali yeyote kuhusu publications."
            ),

        "hi":
            (
                "Hi there! How can I help you today? "
                "Ask me any question about KWTRP publications."
            ),

        "hey":
            (
                "Hey there! How can I help you today? "
                "Ask me any question about KWTRP publications."
            ),

        "hello":
            (
                "Hello there! How can I help you today? "
                "Ask me any question about KWTRP publications."
            ),

    }

    if q_lower in greetings:

        return greetings[q_lower]


    # =====================================================
    # 2. DATABASE SEARCH
    # =====================================================

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

    ]

    if any(
        word in q_lower
        for word in db_keywords
    ):

        result = full_chain(
            question,
            schema_text
        )

        if isinstance(
            result,
            dict
        ):

            preview_data = result.get(
                "preview_data"
            )

            full_data = result.get(
                "full_data"
            )

            response = result.get(
                "response"
            )

            # -------------------------------------------------
            # LIST QUERY
            # -------------------------------------------------

            if (
                preview_data is not None
                and full_data is not None
            ):

                preview_list = parse_result(
                    preview_data
                )

                if not preview_list:

                    return "No results found."

                # Save data for Excel
                st.session_state[
                    "last_data_for_excel"
                ] = full_data

                return (
                    response
                    or
                    "No results found."
                )

            # -------------------------------------------------
            # COUNT QUERY
            # -------------------------------------------------

            return (
                response
                or
                "No results found."
            )

        return result


    # =====================================================
    # 3. WEB SEARCH
    # =====================================================

    try:

        results = search_tool.invoke(
            question
        )

        if (
            results
            and "results" in results
            and len(results["results"]) > 0
        ):

            context = "\n\n".join(

                item.get(
                    "content",
                    ""
                )

                for item in results[
                    "results"
                ][:5]

            )

            prompt = f"""

Question: {question}

Web search context:
{context}

Answer concisely in 100 words or less.

"""

            return llm.invoke(
                prompt
            ).content

        return (
            "I am sorry, I could not "
            "find relevant web results."
        )

    except Exception as e:

        if (
            "429" in str(e)
            or
            "Rate limit exceeded" in str(e)
        ):

            return (
                "The AI service is temporarily "
                "rate-limited. Please wait a "
                "moment and try again."
            )

        return (
            f"Web search failed: {str(e)}"
        )


# =========================================================
# STREAMLIT CONFIGURATION
# =========================================================

st.set_page_config(

    page_title="Kadzo",

    page_icon="🦈",

)


# =========================================================
# CHAT HISTORY
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
                "PROGRAMME PUBLICATIONS**"

            )

        )

    ]


# =========================================================
# DISPLAY CHAT
# =========================================================

for message in st.session_state.chat_history:

    if isinstance(
        message,
        HumanMessage
    ):

        with st.chat_message("human"):

            st.markdown(
                message.content
            )

    elif isinstance(
        message,
        AIMessage
    ):

        with st.chat_message("ai"):

            st.markdown(
                message.content,
                unsafe_allow_html=True
            )


# =========================================================
# USER QUESTION
# =========================================================

question = st.chat_input(
    "Ask a question"
)


if question:

    st.session_state.chat_history.append(

        HumanMessage(
            content=question
        )

    )

    with st.chat_message("human"):

        st.markdown(
            question
        )


    # =====================================================
    # YES / NO EXCEL DOWNLOAD
    # =====================================================

    if (
        "last_data_for_excel"
        in st.session_state
    ):

        user_answer = (
            question
            .lower()
            .strip()
        )

        if user_answer in [
            "yes",
            "y"
        ]:

            filepath = export_to_excel(

                st.session_state[
                    "last_data_for_excel"
                ]

            )

            if (
                filepath
                and os.path.exists(filepath)
            ):

                with open(
                    filepath,
                    "rb"
                ) as f:

                    excel_bytes = f.read()


                with st.chat_message("ai"):

                    st.download_button(

                        label=(
                            "Click here to "
                            "download your Excel file"
                        ),

                        data=excel_bytes,

                        file_name=os.path.basename(
                            filepath
                        ),

                        mime=(
                            "application/vnd.openxmlformats-"
                            "officedocument.spreadsheetml.sheet"
                        ),

                    )

            else:

                with st.chat_message("ai"):

                    st.markdown(
                        "No valid data available to export."
                    )

        else:

            with st.chat_message("ai"):

                st.markdown(
                    "No Excel file was created."
                )


        del st.session_state[
            "last_data_for_excel"
        ]

        st.stop()


    # =====================================================
    # NORMAL AGENT PROCESSING
    # =====================================================

    with st.chat_message("ai"):

        try:

            ai_response = agent_router(

                question,

                st.session_state.chat_history

            )

            st.markdown(

                ai_response,

                unsafe_allow_html=True

            )

        except Exception as e:

            if (
                "429" in str(e)
                or
                "Rate limit exceeded" in str(e)
            ):

                ai_response = (
                    "The Mistral AI service is "
                    "temporarily rate-limited. "
                    "Please wait a moment and try again."
                )

            else:

                ai_response = (
                    f"An error occurred: {str(e)}"
                )

            st.error(
                ai_response
            )


    st.session_state.chat_history.append(

        AIMessage(
            content=ai_response
        )

    )
