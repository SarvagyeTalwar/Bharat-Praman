import json

data = json.load(open(r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\Bharat-Praman\data\pilot_output_refined.json", encoding="utf-8"))
for mp in data:
    print("=" * 110)
    print(f"MP: {mp['mp']} ({mp['role']}) | Base Seat: {mp['base_constituency']}")
    print("=" * 110)
    for a in mp['affidavits']:
        ass = f"Rs {a['total_assets']:,}" if a['total_assets'] is not None else "No Data"
        lia = f"Rs {a['liabilities']:,}" if a['liabilities'] is not None else "No Data"
        cases = str(a['criminal_cases']) if a['criminal_cases'] is not None else "-"
        url = a['profile_url'] or "-"
        print(f"{a['election']:7} | {a['match_type']:18} | {a['party']:6} | {a['constituency']:16} | Assets: {ass:<17} | Liab: {lia:<14} | Cases: {cases:<2} | {url}")
    print()
