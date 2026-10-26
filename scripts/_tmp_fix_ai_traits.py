import io

p = r"F:\WorkBuddy\daily-why\投喂素材\AI能力特点.md"
s = open(p, encoding="utf-8").read()

anchor = "| 2026-10-23 | 白蚁吃银子·蚁酸腐蚀银 |"
idx = s.rfind(anchor)  # 取最后一个出现 = 2026-10-23 行
assert idx != -1, "anchor not found"
line_end = s.find("\n", idx)

newrow = (
    "| 2026-10-26 | 牛奶解辣·酪蛋白包裹 "
    "| **抓酪蛋白“亲油非极性分子”术语硬伤最准**（应改两亲性，v1 独立审校漏判，4家仅 DS/IMA/千问点出）——本轮最大增量；“靠洗不靠冲”机制边界把关稳 "
    "| **补“脂肪溶解+酪蛋白包裹”双机制主次最全**（酪蛋白为主、脂肪为辅，全脂冰牛奶最优补数据）；“只溶于油脂酒精”绝对化提示与DS共指 "
    "| **抓“只溶于油脂和酒精”绝对化表述最准**；但改标准四行表格为信息卡被§124拒（连续第十一次越界，直接过滤）；想加Q4行动清单（采纳为v2 Q4） "
    "| **行动清单补全最实用**（酸奶/冰淇淋/米饭/啤酒误区）；口语化过渡最自然；但“弱化Q编号改自然疑问”破坏A+C+F被拒 |\n"
)

s = s[:line_end + 1] + newrow + s[line_end + 1:]
open(p, "w", encoding="utf-8").write(s)
print("inserted 2026-10-26 row after 2026-10-23 row; new length =", len(s))
