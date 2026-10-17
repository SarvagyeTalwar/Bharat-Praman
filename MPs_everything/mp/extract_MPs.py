import requests
import json
from pathlib import Path

BASE_URL = "https://sansad.in/api_ls/member"

params = {
    "loksabha": 18,
    "state": "",
    "party": "",
    "gender": "",
    "ageFrom": "",
    "ageTo": "",
    "noOfTerms": "",
    "page": 1,
    "size": 100,
    "searchText": "",
    "constituency": "",
    "sitting": 1,
    "locale": "en",
    "month": "",
    "profession": "",
    "otherProfession": "",
    "constituencyCategory": "",
    "positionCode": "",
    "qualification": "",
    "noOfChildren": "",
    "isFreedomFighter": "",
    "memberStatus": "s",
}

session = requests.Session()

response = session.get(BASE_URL, params=params, timeout=30)
response.raise_for_status()
data = response.json()

members = list(data.get("membersDtoList", []))
total_pages = data["metaDatasDto"]["totalPages"]

for page in range(2, total_pages + 1):
    params["page"] = page
    response = session.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()

    page_data = response.json()
    members.extend(page_data.get("membersDtoList", []))
    print(f"Downloaded page {page}/{total_pages}")

output = {
    "metaDatasDto": {
        "totalElements": len(members),
        "pagesDownloaded": total_pages,
    },
    "membersDtoList": members,
}

Path("members.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"Saved {len(members)} records to members.json")