# -*- coding: utf-8 -*-
"""向 topic_candidates.json 追加 L2 反哺候选（source=l2），写入后 json.loads 校验"""
import json

PATH = r"F:\WorkBuddy\daily-why\config\topic_candidates.json"

NEW = [
    {
        "topic": "为什么地球的一天在慢慢变长？",
        "category": "宇宙探索",
        "why_hot": "金星日比年长 v2 结尾直接引出：月球潮汐像刹车持续拖慢地球自转，6亿多年前一天只有约21.9小时，如今每百年再拉长约1.7毫秒；'一天不是天经地义'反转点足",
        "evidence": "强，光明日报《科学之谜》/大众科学中文版/陕西省地震局多源一致（1.7毫秒每世纪、6.2亿年前21.9小时），20260916 L2 已核实",
        "source": "l2",
        "added": "2026-09-16"
    },
    {
        "topic": "为什么金星的大气转得比金星本人还快（超旋）？",
        "category": "宇宙探索",
        "why_hot": "金星日投喂中 IMA 提出：高层大气约4天绕金星一圈，比金星自转（243天）快约60倍，'行星慢吞吞转、大气狂飙'反直觉；且超旋拖曳可能是金星自转超慢的原因之一，与自转话题互为因果",
        "evidence": "中，需WebSearch核实金星大气超旋（superrotation）周期与速度倍数后再采信",
        "source": "l2",
        "added": "2026-09-16"
    },
    {
        "topic": "为什么天王星是躺着打滚转的？",
        "category": "宇宙探索",
        "why_hot": "金星逆行自转的同族反直觉：天王星自转轴倾斜约98度，几乎躺在轨道面上滚，主流假说同样是远古巨大撞击；与金星'被撞反着转'可作行星怪自转姊妹篇",
        "evidence": "中强，自转轴98度为成熟天文常识（20260916 人民网科普中国已核实提及），撞击假说需标注'主流推测'，可少量查证",
        "source": "l2",
        "added": "2026-09-16"
    }
]

with open(PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

existing = {c.get("topic", "") for c in data["candidates"]}
added = []
for item in NEW:
    if item["topic"] not in existing:
        data["candidates"].append(item)
        added.append(item["topic"])

data["updated"] = "2026-09-16"

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 回读校验
with open(PATH, "r", encoding="utf-8") as f:
    check = json.load(f)

with open(r"F:\WorkBuddy\daily-why\.workbuddy\tmp_topic_add_out.txt", "w", encoding="utf-8") as f:
    f.write("added=%d\ntotal_candidates=%d\njson_valid=True\n" % (len(added), len(check["candidates"])))
    for t in added:
        f.write("+ " + t + "\n")
print("ok")
