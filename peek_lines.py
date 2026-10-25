import fitz
p = r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\ministry of internal affairs\annual reports\AnnualReport_27122024.pdf"
d = fitz.open(p)
for pno in [4, 5, 6, 7, 8]:
    print(f"===== PAGE {pno+1} =====")
    for line in (d[pno].get_text() or "").splitlines():
        s = line.strip()
        if s:
            print(repr(s[:140]))
d.close()
