#!/usr/bin/env python3

import os
import sys
import json
import re
import argparse
import requests
import openai
from datetime import datetime

CONFIG_FILE = 'config.json'
API_KEY_FILE = 'apikey.txt'
USER_AGENT = 'DemographicsLookupBot/1.0 (https://example.org/demographicslookupbot/; contact@example.org)'


def extract_json_from_response(response_content):
    json_pattern = re.compile(r'json\s*(\{.*\})', re.DOTALL)  # Match the JSON object with possible "json" prefix
    match = json_pattern.search(response_content)
    if match:
        return match.group(1)  # Return the JSON object excluding the "json" prefix
    else:
        json_pattern = re.compile(r'(\{.*\})', re.DOTALL)
        match = json_pattern.search(response_content)
        if match:
            return match.group(1)
        else:
            raise ValueError("No JSON content found in the response")


def summarize_info_and_produce_blurb(article_text):
    openai.api_key = load_apikey()

    prompt = f"""Please take the following information and produce a JSON like this, with an overall goal of giving all interesting personal information about life, origin, relationships, religion etc.
    {{
        "name": "<name>",
        "years": "<year and location of birth, year, age and cause of death (if applicable).  example 'born in mannheim 1930 and died in berlin age 15 in 1945 of a bomb explosion during a bank robbery'>,
        "origin": "<Town/region/nation of them and their ancestors, example: Jewish ancestors on mother's side, Irish/German on father's, parents were both 1st generation immigrants>",
        "race/religion of ancestors": "<both parents, and grandparents>"
        "age now":<N>,
        "locations": [example: 'he spent age 0-20 in Brooklyn, New York ', 'He retired to San Diego', ...]
        "relationships": [{{<info on parents and siblings (including jobs, important life info, achievements etc.), info on divorces, problems, current status (married/unmarried)}}, ... ] //NOTE: never say things like 'has been in relationships with multiple high-status people'. You ALWAYS must list the specific people. Never generalize like this in ways that hide interesting information. Name the people or at least give details on them rather than just generalizing. This applies to all categories, you MUST be specific.
        "number_of_children": <N or say "known 0" or if its unknown, skip the field>,
        "number_of_known_offspring_total": <M, including direct childen plus their kids, all the way down. For historical figures, this might be a lot, just say what you know. It's important to know this and think about it a lot.>,
        "children_details": [{{their age today, are they surviving, how many descendants each of them had, their sex if not obvious from the name, who their mother was if there is need to specify this}}, ...]
        "offspring_total": <total summary of all known info about offspring, alive or dead, achievements, including children alive today, their years born, their age today.>,
        "spouse_details": [<Think about details I care about based on this list, and include relevant items for each!>],
        <you can skip ANY field if there is no data about it, remember!>
        "education": [{{school name, years, the person's age (N-M) while they were there, the location, degree?}}, ...],
        "companies": [{{name, years, ages (N-M), role, location, number of employees}}, ...],
        "criminal_or_drug_issues": "[{{<major issues or null if unknown, times, penalties etc>}}",
        "intellectual output": [<list of major items, with years, effects, meaning etc.>],
        "artistic output": [<list of major items, with years, effects, meaning etc.>],
        "other_careers": [<list of all their careers, with length.>],
        "comments": "<comments here such as what languages they speak, or your commentary about whether it's easy or hard to get info in this person..>",
    }}

    Example of BAD things - you should NOT include things like this, since there is no content to these empty lists. You should just skip those. You are free to modify the json format by skipping fields.
    <<< BAD EXAMPLE: "criminal_or_drug_issues": null,
    "intellectual output": [],
    "artistic output": [], >>>

    You MUST only return JSON. As you are creating this json, if a value is unknown, DO NOT include it. Skip it totally from the output. Just go to the next one.

    Skip null or missing or unkonwn fields, and don't include them at all.

    Similarly, if you find data which is relevant and interesting, you can make up new fields and include that, too.

    If the field involves years, you must also say how old the person was at the time. For example the years they held a job.

    You MUST return ONLY a json, no other leading text. If you have comments, put them in the top-level 'comments' field. You MUST return pure JSON only my friend.

    Also, if you just so happen to know other information about the person, stick that in there too. Kapische? but mark such information (which YOU know but which wasn't in, or was contradticted by wikipedia, with leading and trailing "_" characters.

    Also, if you find that the same information is being included in multiple fields of the json, you only need to specify it once, so please revise your plan and find a way to avoid repeating things.

    Also, if a field is "unknown" just skip it. you don't need to included it if you don't know what to say, and it's okay if items in lists are irregular - i.e. you know the value of one field for one of them, and include it, but totally skip that field for another item. That's fine, just cut out the stuff that's unnecessary.

    Overall, don't include things that are uninteresting. My interests are in science, technologic, society and culture, not so much into current day political controversies or the mainstream. Focus on things that will last, like major world contributions and changes rather than ephemeral fluff.

    Here are some BAD patterns, with reasons why each is bad.

    Example 1:
    "artistic output": [
        {{
            "major_items": []
        }}
    ],
    Evaluation: This is bad because there is no content here. Instead, you should just skip the entire block since there's nothing in it.

    Example 2:
    "relationships": [
        {{
            "status": "unknown"
        }}
    ],
    Evaluation: This is bad because there is no content here. Instead, you should just skip the entire block since there's nothing in it.

    Example 3:
    "companies": [
    ],
    "criminal_or_drug_issues": [
        {{}}
    ],
    Evaluation: This is bad because there is no content here. Instead, you should just skip the entire block since there's nothing in it.

    Here is the data: {article_text}.
    """[:50000]
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=3500
    )

    # Extract and load the JSON content from the response
    response_content = response.choices[0].message['content'].strip()
    json_content = extract_json_from_response(response_content)
    try:
        person_data = json.loads(json_content)
    except Exception as ex:
        print(json_content)
        #this is when openai doesn't actually return json.
        print(ex)
        sys.exit(3)

    return person_data

def setup_argparse():
    parser = argparse.ArgumentParser(description='Personal Demographics Lookup Tool')
    parser.add_argument('command', choices=['lookup', 'force_lookup'], help='Command to execute')
    parser.add_argument('name', nargs='+', help='Name of the person to look up, optionally followed by a comma and a hint')
    return parser

def log_message(message):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

def get_cached_file(name):
    cache_file = f"cache/{name}.json"
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None

def save_to_cache(name, data):
    cache_file = f"cache/{name}.json"
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'w') as f:
        json.dump(data, f, indent=4)

def load_apikey():
    with open(API_KEY_FILE, 'r') as f:
        return f.read().strip()

def download_wikipedia_article(title=None, pageid=None):
    if pageid:
        url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext&pageids={pageid}&format=json"
    else:
        url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext&titles={title}&format=json"

    headers = {'User-Agent': USER_AGENT}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    pages = response.json().get('query', {}).get('pages', {})
    page = next(iter(pages.values()))
    if 'extract' in page:
        return page['extract'], page['title']
    else:
        raise ValueError("Page does not exist")

def strip_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def search_wikipedia(title, hint=None):
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={title}&format=json"
    headers = {'User-Agent': USER_AGENT}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    search_results = response.json().get('query', {}).get('search', [])
    if search_results:
        for el in search_results:
            el['snippet']=strip_html_tags(el['snippet'])
        pageid = pick_right_page(search_results, hint)
        wikipedia_content, actual_title = download_wikipedia_article(pageid=pageid)
        return wikipedia_content, actual_title
    else:
        raise ValueError("No search results found")

def pick_right_page(search_results, hint=None):
    options = [json.dumps(result) for result in search_results]
    if hint:
        # Use GPT to determine the correct article based on the hint
        openai.api_key = load_apikey()
        prompt = f"""Given the hint '{hint}', which of the following options is most likely to be the correct Wikipedia article?
        Please return JUST the pageid field as a simple text and no other information.

        Here are your choices:
        {options}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3500
        )

        chosen_title = response.choices[0].message.content.strip()
        return chosen_title
    else:
        # Present options to the user
        print("Multiple pages detected. Please select the correct option by entering the corresponding number:")

        mm={}
        title_width = 40
        snippet_width = 80
        print("\r\n")
        for idx, option in enumerate(search_results, 1):
            title = option['title'].ljust(title_width)
            print(f"\t{idx}\t{title}\t{option['snippet']}")
            mm[idx] = option['pageid']

        choice = int(input("Enter the number of the correct option: "))
        pageid=mm[choice]
        return pageid

if __name__ == "__main__":
    parser = setup_argparse()

    if len(sys.argv) < 3:
        parser.print_help()
        sys.exit(1)

    try:
        args = parser.parse_args()

        # Join name parts into a single string
        name_parts = ' '.join(args.name)

        # Split the name and hint if a comma is present
        if ',' in name_parts:
            search_name, hint = map(str.strip, name_parts.rsplit(',', 1))
        else:
            search_name = name_parts
            hint = None

        wikipedia_content, actual_name = search_wikipedia(search_name, hint)

        cached_data = get_cached_file(actual_name)
        if args.command == "force_lookup" or cached_data is None:
            person_data = summarize_info_and_produce_blurb(wikipedia_content)
            save_to_cache(actual_name, person_data)
        else:
            person_data = cached_data

        print(json.dumps(person_data, indent=4))
    except argparse.ArgumentError as e:
        log_message(f"Argument error: {e}")
        parser.print_help()
        sys.exit(1)
    except Exception as e:
        log_message(f"Unexpected error: {e}")
        sys.exit(1)

