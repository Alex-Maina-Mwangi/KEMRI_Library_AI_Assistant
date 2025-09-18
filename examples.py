def example_scripts():
    examples = [
        {"question": "List all publications", "query": "SELECT * FROM refs;",},

        {"question": "List all publications published between the months of January and June in the year 2025",
        "query":"SELECT COUNT(*) FROM refs WHERE YEAR(STR_TO_DATE(edition, '%Y/%m/%d')) = 2025 AND 					MONTH(STR_TO_DATE(edition, '%Y/%m/%d')) BETWEEN 1 AND 6;",
        }, 
        
        {"question": "What is the total number of publications published by Philip Bejon between the months of January and June in 		the year 2025",
        "query":"SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id WHERE authorname LIKE '%Bejon P%' AND YEAR(STR_TO_DATE(edition, '%Y/%m/%d')) = 2025 AND MONTH(STR_TO_DATE(edition, '%Y/%m/%d')) BETWEEN 1 AND 6;",
        },

        {"question": "What is the total number of publications published by biosciences department",
        "query": "SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id INNER JOIN people_department ON people.id = people_department.id WHERE people_department.dept_id = 1;",
        
        },
        {"question": "What is the total number of publications published by Epidemiology and Demography EDD department",
        "query": "SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id INNER JOIN people_department ON people.id = people_department.id WHERE people_department.dept_id = 4;",
        
        },

        {"question": "What is the total number of publications published by Health Sysytems and Research Ethics HSRE department",
        "query": "SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id INNER JOIN people_department ON people.id = people_department.id WHERE people_department.dept_id = 5;",
        
        },

        {"question": "What is the total number publications published by Faith Osier",

        "query": "SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id WHERE people.authorname LIKE '%Osier F%';",


        },
        
        {"question": "How many publications have been published by Emelda Okiro",

        "query": "SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id WHERE people.authorname LIKE '%Okiro E%';",


        },
        {"question": "How many articles has Mike English published",
        "query": "SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id WHERE people.authorname LIKE '%English M%';",	
        },
        {"question": "What is the total number of articles published by Jay Berkley",
         "query": "SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id WHERE people.authorname LIKE '%Berkley J%';",
        },
        {"question":"What is the total number of articles published by Edwine Barasa",
         "query": "SELECT COUNT(DISTINCT refs.id) FROM refs INNER JOIN author_publication1 ON refs.id = author_publication1.rid INNER JOIN author_alias ON author_publication1.auid = author_alias.auid INNER JOIN people ON author_alias.pid = people.id WHERE people.authorname LIKE '%Barasa E%';",
         
        },
    ]
    return examples