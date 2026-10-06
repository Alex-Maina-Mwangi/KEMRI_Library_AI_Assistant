def example_scripts():
    examples = [

        # ============================================================
        # GENERAL PUBLICATIONS
        # ============================================================

        {
            "question": "List all publications",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM refs
                ORDER BY id DESC
                LIMIT 100;
            """
        },

        {
            "question": "How many publications are there",
            "query": """
                SELECT COUNT(*) AS total_publications
                FROM refs;
            """
        },


        # ============================================================
        # PUBLICATIONS BY DATE RANGE
        # ============================================================

        {
            "question": "List all publications published between January and June 2025",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM (
                    SELECT
                        refs.*,
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                WHERE YEAR(pub_date) = 2025
                  AND MONTH(pub_date) BETWEEN 1 AND 6
                ORDER BY id DESC;
            """
        },

        {
            "question": "How many publications were published between January and June 2025",
            "query": """
                SELECT COUNT(*) AS total_publications
                FROM (
                    SELECT
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                WHERE YEAR(pub_date) = 2025
                  AND MONTH(pub_date) BETWEEN 1 AND 6;
            """
        },


        # ============================================================
        # PUBLICATIONS BY YEAR
        # ============================================================

        {
            "question": "How many publications were published in 2025",
            "query": """
                SELECT COUNT(*) AS total_publications
                FROM (
                    SELECT
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                WHERE YEAR(pub_date) = 2025;
            """
        },

        {
            "question": "List all publications published in 2025",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM (
                    SELECT
                        refs.*,
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                WHERE YEAR(pub_date) = 2025
                ORDER BY id DESC;
            """
        },


        # ============================================================
        # AUTHOR - COUNTS
        # ============================================================

        {
            "question": "How many publications has Philip Bejon published",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Bejon P%';
            """
        },

        {
            "question": "How many publications has Edwine Barasa published",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Barasa E%';
            """
        },

        {
            "question": "How many publications has Faith Osier published",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Osier F%';
            """
        },

        {
            "question": "How many publications has Mike English published",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%English M%';
            """
        },

        {
            "question": "How many publications has Jay Berkley published",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Berkley J%';
            """
        },

        {
            "question": "How many publications has Emelda Okiro published",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Okiro E%';
            """
        },


        # ============================================================
        # AUTHOR - LIST PUBLICATIONS
        # ============================================================

        {
            "question": "List all publications published by Philip Bejon",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Bejon P%'
                ORDER BY refs.id DESC;
            """
        },

        {
            "question": "List all publications published by Edwine Barasa",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Barasa E%'
                ORDER BY refs.id DESC;
            """
        },

        {
            "question": "List all publications published by Faith Osier",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Osier F%'
                ORDER BY refs.id DESC;
            """
        },

        {
            "question": "List all publications published by Sophie Uyoga",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Uyoga S%'
                ORDER BY refs.id DESC;
            """
        },

        {
            "question": "List all publications published by Anthony Etyang",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Etyang A%'
                ORDER BY refs.id DESC;
            """
        },


        # ============================================================
        # AUTHOR + YEAR
        # ============================================================

        {
            "question": "List all publications published by Philip Bejon in 2025",
            "query": """
                SELECT
                    author,
                    year,
                    title,
                    secondary_title,
                    volume,
                    number,
                    pages,
                    accession_number AS PMID,
                    electronic_resource_number AS doi
                FROM (
                    SELECT
                        refs.*,
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                INNER JOIN author_publication1
                    ON r.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Bejon P%'
                  AND YEAR(pub_date) = 2025
                ORDER BY r.id DESC;
            """
        },


        # ============================================================
        # AUTHOR + DATE RANGE
        # ============================================================

        {
            "question": "How many publications did Philip Bejon publish between January and June 2025",
            "query": """
                SELECT COUNT(DISTINCT r.id) AS total_publications
                FROM (
                    SELECT
                        refs.*,
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                INNER JOIN author_publication1
                    ON r.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Bejon P%'
                  AND YEAR(r.pub_date) = 2025
                  AND MONTH(r.pub_date) BETWEEN 1 AND 6;
            """
        },

        {
            "question": "List all publications published by Philip Bejon between January and June 2025",
            "query": """
                SELECT
                    r.author,
                    r.year,
                    r.title,
                    r.secondary_title,
                    r.volume,
                    r.number,
                    r.pages,
                    r.accession_number AS PMID,
                    r.electronic_resource_number AS doi
                FROM (
                    SELECT
                        refs.*,
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                INNER JOIN author_publication1
                    ON r.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                WHERE people.authorname LIKE '%Bejon P%'
                  AND YEAR(r.pub_date) = 2025
                  AND MONTH(r.pub_date) BETWEEN 1 AND 6
                ORDER BY r.id DESC;
            """
        },


        # ============================================================
        # DEPARTMENT - COUNTS
        # ============================================================

        {
            "question": "How many publications have been published by the Biosciences department",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                INNER JOIN people_department
                    ON people.id = people_department.id
                WHERE people_department.dept_id = 1;
            """
        },

        {
            "question": "How many publications have been published by the Epidemiology and Demography EDD department",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                INNER JOIN people_department
                    ON people.id = people_department.id
                WHERE people_department.dept_id = 4;
            """
        },

        {
            "question": "How many publications have been published by the Health Systems and Research Ethics HSRE department",
            "query": """
                SELECT COUNT(DISTINCT refs.id) AS total_publications
                FROM refs
                INNER JOIN author_publication1
                    ON refs.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                INNER JOIN people_department
                    ON people.id = people_department.id
                WHERE people_department.dept_id = 5;
            """
        },


        # ============================================================
        # DEPARTMENT + YEAR
        # ============================================================

        {
            "question": "List all publications published by the Biosciences department in 2025",
            "query": """
                SELECT DISTINCT
                    r.author,
                    r.year,
                    r.title,
                    r.secondary_title,
                    r.volume,
                    r.number,
                    r.pages,
                    r.accession_number AS PMID,
                    r.electronic_resource_number AS doi
                FROM (
                    SELECT
                        refs.*,
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                INNER JOIN author_publication1
                    ON r.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                INNER JOIN people_department
                    ON people.id = people_department.id
                WHERE people_department.dept_id = 1
                  AND YEAR(r.pub_date) = 2025
                ORDER BY r.accession_number DESC;
            """
        },

        {
            "question": "List all publications published by the EDD department in 2025",
            "query": """
                SELECT DISTINCT
                    r.author,
                    r.year,
                    r.title,
                    r.secondary_title,
                    r.volume,
                    r.number,
                    r.pages,
                    r.accession_number AS PMID,
                    r.electronic_resource_number AS doi
                FROM (
                    SELECT
                        refs.*,
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                INNER JOIN author_publication1
                    ON r.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                INNER JOIN people_department
                    ON people.id = people_department.id
                WHERE people_department.dept_id = 4
                  AND YEAR(r.pub_date) = 2025
                ORDER BY r.accession_number DESC;
            """
        },

        {
            "question": "List all publications published by the HSRE department in 2025",
            "query": """
                SELECT DISTINCT
                    r.author,
                    r.year,
                    r.title,
                    r.secondary_title,
                    r.volume,
                    r.number,
                    r.pages,
                    r.accession_number AS PMID,
                    r.electronic_resource_number AS doi
                FROM (
                    SELECT
                        refs.*,
                        CASE
                            WHEN edition LIKE '%/%'
                                THEN STR_TO_DATE(edition, '%Y/%m/%d')
                            ELSE
                                STR_TO_DATE(edition, '%Y%m%d')
                        END AS pub_date
                    FROM refs
                ) r
                INNER JOIN author_publication1
                    ON r.id = author_publication1.rid
                INNER JOIN author_alias
                    ON author_publication1.auid = author_alias.auid
                INNER JOIN people
                    ON author_alias.pid = people.id
                INNER JOIN people_department
                    ON people.id = people_department.id
                WHERE people_department.dept_id = 5
                  AND YEAR(r.pub_date) = 2025
                ORDER BY r.accession_number DESC;
            """
        }
    ]

    return examples
