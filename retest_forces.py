from mha_agent import answer
for q in ["Which organisations are under the Ministry of Home Affairs?",
          "Which police forces are under the Ministry of Home Affairs?"]:
    ans, hits, g = answer(q, k=8)
    print("Q:", q)
    print(ans[:1200])
    print("SOURCES:", [(h["title"], h["page"]) for h in hits[:4]])
    print("----")
