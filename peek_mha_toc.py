import fitz
p = r"C:\Users\aarya\OneDrive\Desktop\Bharat Praman\ministry of internal affairs\AnnualReport_27122024.pdf"
d = fitz.open(p)
for i in range(4, 14):
    t = (d[i].get_text() or "").strip()
    print(f"===== PAGE {i+1} =====")
    print(t[:600])
d.close()
